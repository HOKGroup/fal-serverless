import copy
import logging
from pathlib import Path
from typing import Optional

import fal
from fal.toolkit import FAL_MODEL_WEIGHTS_DIR, Image
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class Input(BaseModel):
    image: Image = Field(description="Source image to extract PBR maps from")
    resolution: int = Field(
        default=1024, ge=512, le=2048,
        description="Processing resolution (output matches input dimensions)",
    )
    light_position: list[float] = Field(
        default=[0.0, 0.0, 10.0],
        description="Point light [x,y,z] for relit output",
    )
    include_relit: bool = Field(
        default=True,
        description="Whether to compute relit image (skip saves ~10% time)",
    )


class Output(BaseModel):
    basecolor: Image = Field(description="Basecolor / albedo map")
    normal: Image = Field(description="Normal map in tangent space")
    roughness: Image = Field(description="Roughness map (grayscale)")
    metalness: Image = Field(description="Metalness map (grayscale)")
    relit: Optional[Image] = Field(default=None, description="Re-rendered image under point light")


HF_REPO_ID = "Ubisoft/ubisoft-laforge-chord"
HF_FILENAME = "chord_v1.safetensors"


class ChordPBR(fal.App):
    app_name = "chord-pbr-python"
    machine_type = "GPU-H100"
    keep_alive = 300
    max_concurrency = 1
    app_files = ["chord", "config"]
    app_files_ignore = [r"\.pyc$", r"__pycache__/"]

    requirements = [
        "torch==2.10.0",
        "torchvision==0.25.0",
        "huggingface_hub[hf_xet]",
        "diffusers==0.35.2",
        "transformers==4.57.1",
        "tokenizers==0.22.1",
        "omegaconf==2.3.0",
        "imageio==2.37.2",
        "pillow==11.3.0",
        "requests==2.32.5",
        "safetensors==0.7.0",
        "hf-transfer",
    ]

    def setup(self):
        import os
        import time

        import torch
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import LocalEntryNotFoundError
        from omegaconf import OmegaConf

        from chord import ChordModel
        from chord.io import load_torch_file

        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

        # XET high-performance mode: more concurrency for large weight files
        os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
        os.environ["HF_XET_CHUNK_CACHE_SIZE_BYTES"] = "1000000000000"
        os.environ["HF_XET_NUM_CONCURRENT_RANGE_GETS"] = "32"

        # Download Chord weights — try local cache first to skip API calls on warm starts
        weights_dir = str(FAL_MODEL_WEIGHTS_DIR / "chord")
        dl_kwargs = dict(
            repo_id=HF_REPO_ID,
            filename=HF_FILENAME,
            local_dir=weights_dir,
        )
        t0 = time.monotonic()
        try:
            ckpt_path = hf_hub_download(**dl_kwargs, local_files_only=True)
            log.info("Weights cache hit (%s)", weights_dir)
        except LocalEntryNotFoundError:
            log.info("Downloading weights from %s ...", HF_REPO_ID)
            ckpt_path = hf_hub_download(**dl_kwargs)
        log.info("Weights ready in %.1fs", time.monotonic() - t0)

        # Load config — app_files land in cwd on fal, not next to __file__
        config_path = Path(__file__).parent / "config" / "chord.yaml"
        if not config_path.exists():
            config_path = Path("config") / "chord.yaml"
        config = OmegaConf.load(str(config_path))

        t0 = time.monotonic()
        model = ChordModel(config)
        model.load_state_dict(load_torch_file(str(ckpt_path)))
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.eval()
        model.to(self.device)
        self.model = model
        log.info("Model loaded to %s in %.1fs", self.device, time.monotonic() - t0)

    @fal.endpoint("/")
    def run(self, request: Input) -> Output:
        import torch
        from torchvision.transforms import v2
        from torchvision.transforms.functional import to_pil_image

        from chord.module import make
        from chord.util import get_positions, rgb_to_srgb

        src = request.image.to_pil("RGB")
        if src.width < 1 or src.height < 1:
            raise ValueError("Invalid image: width and height must be >= 1")
        ori_h, ori_w = src.size[1], src.size[0]
        res = request.resolution

        to_tensor = v2.Compose([v2.ToImage(), v2.ToDtype(torch.float32, scale=True)])
        image = to_tensor(src).to(self.device)
        x = v2.Resize(size=(res, res), antialias=True)(image).unsqueeze(0)

        try:
            with torch.no_grad(), torch.autocast(device_type=self.device.type):
                out = self.model(x)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            raise RuntimeError(
                f"CUDA out of memory at resolution {res}. "
                "Try a lower resolution (e.g. 512)."
            )

        # Conditional relit computation
        rendered_img = None
        if request.include_relit:
            maps = copy.deepcopy(out)
            maps["metallic"] = maps.get("metalness", torch.zeros_like(maps["basecolor"]))
            h, w = maps["basecolor"].shape[-2:]
            lp = request.light_position
            light = make("point-light", {"position": lp}).to(self.device)
            pos = get_positions(h, w, lp[2]).to(self.device)
            camera = torch.tensor([0, 0, lp[2]], dtype=torch.float32).to(self.device)
            for key in maps:
                if maps[key].dim() == 3:
                    maps[key] = maps[key].unsqueeze(0)
                maps[key] = maps[key].permute(0, 2, 3, 1)
            rgb = (
                self.model.model.compute_render(maps, camera, pos, light)
                .squeeze(0)
                .permute(0, 3, 1, 2)
            )
            rendered = torch.clamp(rgb_to_srgb(rgb), 0, 1)
            resize_back = v2.Resize(size=(ori_h, ori_w), antialias=True)
            rendered_img = Image.from_pil(to_pil_image(resize_back(rendered).squeeze(0)))

        resize_back = v2.Resize(size=(ori_h, ori_w), antialias=True)

        return Output(
            basecolor=Image.from_pil(to_pil_image(resize_back(out["basecolor"]).squeeze(0))),
            normal=Image.from_pil(to_pil_image(resize_back(out["normal"]).squeeze(0))),
            roughness=Image.from_pil(to_pil_image(resize_back(out["roughness"]).squeeze(0))),
            metalness=Image.from_pil(to_pil_image(resize_back(out["metalness"]).squeeze(0))),
            relit=rendered_img,
        )

# # gradio
# if __name__ == "__main__":
#     import copy as _copy

#     import gradio as gr
#     import torch
#     from huggingface_hub import hf_hub_download
#     from omegaconf import OmegaConf
#     from torchvision.transforms import v2
#     from torchvision.transforms.functional import to_pil_image

#     from chord import ChordModel
#     from chord.io import load_torch_file
#     from chord.module import make
#     from chord.util import get_positions, rgb_to_srgb

#     # Load model
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     ckpt_path = hf_hub_download(repo_id=HF_REPO_ID, filename=HF_FILENAME)
#     config = OmegaConf.load(str(Path(__file__).parent / "config" / "chord.yaml"))
#     model = ChordModel(config)
#     model.load_state_dict(load_torch_file(str(ckpt_path)))
#     model.eval().to(device)

#     def inference(img):
#         if img is None:
#             return None, None, None, None, None

#         ori_h, ori_w = img.size[1], img.size[0]

#         to_tensor = v2.Compose([v2.ToImage(), v2.ToDtype(torch.float32, scale=True)])
#         image = to_tensor(img).to(device)
#         x = v2.Resize(size=(1024, 1024), antialias=True)(image).unsqueeze(0)

#         with torch.no_grad(), torch.autocast(device_type=device.type):
#             out = model(x)

#         # Relit
#         maps = _copy.deepcopy(out)
#         maps["metallic"] = maps.get("metalness", torch.zeros_like(maps["basecolor"]))
#         h, w = maps["basecolor"].shape[-2:]
#         light = make("point-light", {"position": [0, 0, 10]}).to(device)
#         pos = get_positions(h, w, 10).to(device)
#         camera = torch.tensor([0, 0, 10.0]).to(device)
#         for key in maps:
#             if maps[key].dim() == 3:
#                 maps[key] = maps[key].unsqueeze(0)
#             maps[key] = maps[key].permute(0, 2, 3, 1)
#         rgb = model.model.compute_render(maps, camera, pos, light).squeeze(0).permute(0, 3, 1, 2)
#         rendered = torch.clamp(rgb_to_srgb(rgb), 0, 1)

#         resize_back = v2.Resize(size=(ori_h, ori_w), antialias=True)
#         return (
#             to_pil_image(resize_back(out["basecolor"]).squeeze(0)),
#             to_pil_image(resize_back(out["normal"]).squeeze(0)),
#             to_pil_image(resize_back(out["roughness"]).squeeze(0)),
#             to_pil_image(resize_back(out["metalness"]).squeeze(0)),
#             to_pil_image(resize_back(rendered).squeeze(0)),
#         )

#     demo = gr.Interface(
#         fn=inference,
#         inputs=gr.Image(type="pil", label="Input Image"),
#         outputs=[
#             gr.Image(label="Basecolor"),
#             gr.Image(label="Normal"),
#             gr.Image(label="Roughness"),
#             gr.Image(label="Metalness"),
#             gr.Image(label="Relit"),
#         ],
#         title="Chord PBR",
#     )
#     demo.launch()
