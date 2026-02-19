import copy
from pathlib import Path

import fal
from fal.toolkit import Image, download_file
from pydantic import BaseModel, Field


class ChordInput(BaseModel):
    image_url: str = Field(description="Source image URL")


class ChordOutput(BaseModel):
    images: list[Image] = Field(
        description="[basecolor, normal, roughness, metalness, relit]"
    )


HF_REPO_ID = "Ubisoft/ubisoft-laforge-chord"
HF_FILENAME = "chord_v1.safetensors"


class ChordPBR(fal.App):
    app_name = "chord-pbr-python"
    auth_mode = "private"
    machine_type = "GPU-A100"
    keep_alive = 300
    max_concurrency = 1
    app_files = ["chord", "config"]

    requirements = [
        "torch",
        "torchvision",
        "huggingface_hub[hf_xet]",
        "diffusers==0.35.2",
        "transformers==4.57.1",
        "tokenizers==0.22.1",
        "omegaconf",
        "imageio",
        "pillow",
        "requests",
        "safetensors",
    ]

    def setup(self):
        import os

        import torch
        from huggingface_hub import hf_hub_download
        from omegaconf import OmegaConf

        from chord import ChordModel
        from chord.io import load_torch_file

        # Cache HF downloads to persistent storage
        os.environ.setdefault("HF_HOME", "/data/.cache/huggingface")

        # Download Chord weights (requires HF_TOKEN fal secret for gated repo)
        ckpt_path = hf_hub_download(repo_id=HF_REPO_ID, filename=HF_FILENAME)

        # Load config and model
        config = OmegaConf.load(str(Path(__file__).parent / "config" / "chord.yaml"))
        model = ChordModel(config)
        model.load_state_dict(load_torch_file(str(ckpt_path)))

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.eval()
        model.to(self.device)
        self.model = model

    @fal.endpoint("/generate")
    def generate(self, input: ChordInput) -> ChordOutput:
        import torch
        from torchvision.transforms import v2
        from torchvision.transforms.functional import to_pil_image

        from chord.module import make
        from chord.util import get_positions, rgb_to_srgb

        # Fetch input image
        from PIL import Image as PILImage

        img_path = download_file(input.image_url)
        src = PILImage.open(str(img_path)).convert("RGB")
        ori_h, ori_w = src.size[1], src.size[0]

        # Tensor transform + resize to 1024x1024
        to_tensor = v2.Compose([v2.ToImage(), v2.ToDtype(torch.float32, scale=True)])
        image = to_tensor(src).to(self.device)
        x = v2.Resize(size=(1024, 1024), antialias=True)(image).unsqueeze(0)

        # Inference
        with torch.no_grad(), torch.autocast(device_type=self.device.type):
            out = self.model(x)

        # Relit computation
        maps = copy.deepcopy(out)
        maps["metallic"] = maps.get("metalness", torch.zeros_like(maps["basecolor"]))
        h, w = maps["basecolor"].shape[-2:]
        light = make("point-light", {"position": [0, 0, 10]}).to(self.device)
        pos = get_positions(h, w, 10).to(self.device)
        camera = torch.tensor([0, 0, 10.0]).to(self.device)
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

        # Resize outputs back to original dimensions
        resize_back = v2.Resize(size=(ori_h, ori_w), antialias=True)

        images = [
            Image.from_pil(to_pil_image(resize_back(out["basecolor"]).squeeze(0))),
            Image.from_pil(to_pil_image(resize_back(out["normal"]).squeeze(0))),
            Image.from_pil(to_pil_image(resize_back(out["roughness"]).squeeze(0))),
            Image.from_pil(to_pil_image(resize_back(out["metalness"]).squeeze(0))),
            Image.from_pil(to_pil_image(resize_back(rendered).squeeze(0))),
        ]

        return ChordOutput(images=images)
