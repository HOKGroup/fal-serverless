import copy
from pathlib import Path

import fal
from fal.toolkit import Image, download_file
from pydantic import BaseModel, Field


class ChordImageInput(BaseModel):
    url: str = Field(description="Source image URL")


class ChordInput(BaseModel):
    image: ChordImageInput = Field(description="Source image")
    resolution: int = Field(
        default=1024,
        ge=512,
        le=2048,
        description="Square inference resolution",
    )
    include_relit: bool = Field(
        default=False,
        description="Whether to return the relit preview image",
    )


class ChordOutput(BaseModel):
    basecolor: Image = Field(description="Estimated albedo/basecolor map")
    normal: Image = Field(description="Estimated normal map")
    height: Image = Field(description="Derived height map from the estimated normal")
    roughness: Image = Field(description="Estimated roughness map")
    metalness: Image = Field(description="Estimated metalness map")
    relit: Image | None = Field(default=None, description="Optional relit preview")


HF_REPO_ID = "Ubisoft/ubisoft-laforge-chord"
HF_FILENAME = "chord_v1.safetensors"


def resolve_config_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "config" / "chord.yaml",
        Path.cwd() / "config" / "chord.yaml",
        Path("config/chord.yaml").resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not find config/chord.yaml. Tried: {candidates}")


def chord_normal_to_height(normal_map, integration_resolution=1024, height_var_threshold=5e-4):
    import torch
    import torch.fft as fft_module
    import torch.nn.functional as F

    def compute_divergence(fx, fy):
        div_x = F.pad(fx[:, :, 1:] - fx[:, :, :-1], (0, 1, 0, 0), mode="constant")
        div_y = F.pad(fy[:, 1:, :] - fy[:, :-1, :], (0, 0, 0, 1), mode="constant")
        return div_x + div_y

    def solve_poisson_fft(div, h, w):
        fft_div = fft_module.fft2(div)

        kx = fft_module.fftfreq(2 * w, device=div.device) * 2 * torch.pi
        ky = fft_module.fftfreq(2 * h, device=div.device) * 2 * torch.pi
        kx, ky = torch.meshgrid(kx, ky, indexing="xy")
        epsilon = 1e-9
        denom = 4 - 2 * torch.cos(kx) - 2 * torch.cos(ky)
        denom = torch.where(torch.abs(denom) > epsilon, denom, epsilon)

        height_map_full = torch.real(fft_module.ifft2(fft_div / denom))
        return torch.nan_to_num(height_map_full[:, :h, :w])

    def apply_window_function(gradient):
        hann_window = torch.hann_window(gradient.shape[-2], device=gradient.device)[:, None]
        hann_window = hann_window * torch.hann_window(
            gradient.shape[-1], device=gradient.device
        )[None, :]
        return gradient * hann_window

    def compute_height(single_normal_map, epsilon=1e-8):
        h, w = single_normal_map.shape[-2:]
        nz = single_normal_map[:, 2]
        nz_safe = torch.where(torch.abs(nz) > epsilon, nz, epsilon)
        fx = single_normal_map[:, 0] / nz_safe
        fy = single_normal_map[:, 1] / nz_safe

        fx = apply_window_function(fx)
        fy = apply_window_function(fy)

        div = compute_divergence(fx, fy)
        div = F.pad(div, (0, w, 0, h), mode="constant")
        height_map = solve_poisson_fft(div, h, w)
        return height_map - torch.mean(height_map)

    def define_subregions(h, w, min_region_size=128, overlap_factor=0.5):
        step_size = int(min_region_size - min_region_size * overlap_factor)
        if step_size <= 0:
            step_size = min_region_size
        overlap_size = int(min_region_size * overlap_factor)
        subregions = []
        for y in range(0, h, step_size):
            for x in range(0, w, step_size):
                y_end = min(y + min_region_size + overlap_size, h)
                x_end = min(x + min_region_size + overlap_size, w)
                subregions.append((y, y_end, x, x_end))
        return subregions

    def cosine_smoothing(x):
        return 0.5 * (1 - torch.cos(torch.pi * x))

    def normal_to_height(single_normal_map, subdivisions=16, min_region_size=128, skip_normalize_normal=False):
        if single_normal_map.dim() == 4:
            if single_normal_map.shape[0] != 1:
                raise ValueError("normal_to_height expects a single-item batch")
            single_normal_map = single_normal_map.squeeze(0)

        h, w = single_normal_map.shape[-2:]
        if not skip_normalize_normal:
            single_normal_map = F.normalize(single_normal_map * 2.0 - 1.0, dim=0)

        region_size = min(max(min(h, w) // subdivisions, min_region_size), min(h, w))
        larger_normal_map = F.pad(
            single_normal_map,
            (region_size, region_size, region_size, region_size),
            mode="circular",
        )
        lh, lw = larger_normal_map.shape[-2:]
        subregions = define_subregions(lh, lw, region_size)

        height_maps = []
        for y_start, y_end, x_start, x_end in subregions:
            sub_map = larger_normal_map[:, y_start:y_end, x_start:x_end]
            sub_height_map = compute_height(sub_map.unsqueeze(0)).squeeze(0)
            sub_weight_map = torch.ones_like(sub_height_map)
            h_sub, w_sub = sub_weight_map.shape[-2:]

            if y_start > 0:
                overlap = min(region_size, h_sub)
                y_smooth = cosine_smoothing(torch.linspace(0, 1, overlap, device=sub_weight_map.device))[:, None]
                sub_weight_map[:overlap, :] *= y_smooth
            if y_end < lh:
                overlap = min(region_size, h_sub)
                y_smooth = cosine_smoothing(torch.linspace(1, 0, overlap, device=sub_weight_map.device))[:, None]
                sub_weight_map[-overlap:, :] *= y_smooth
            if x_start > 0:
                overlap = min(region_size, w_sub)
                x_smooth = cosine_smoothing(torch.linspace(0, 1, overlap, device=sub_weight_map.device))
                sub_weight_map[:, :overlap] *= x_smooth
            if x_end < lw:
                overlap = min(region_size, w_sub)
                x_smooth = cosine_smoothing(torch.linspace(1, 0, overlap, device=sub_weight_map.device))
                sub_weight_map[:, -overlap:] *= x_smooth

            height_maps.append((y_start, y_end, x_start, x_end, sub_height_map, sub_weight_map))

        height_map = torch.zeros((lh, lw), device=single_normal_map.device)
        weight_map = torch.zeros((lh, lw), device=single_normal_map.device)
        for y_start, y_end, x_start, x_end, sub_height_map, sub_weight_map in height_maps:
            height_map[y_start:y_end, x_start:x_end] += sub_height_map * sub_weight_map
            weight_map[y_start:y_end, x_start:x_end] += sub_weight_map

        height_cropped = (height_map / (weight_map + 1e-8))[
            region_size : region_size + h,
            region_size : region_size + w,
        ]
        return (height_cropped - height_cropped.min()) / (
            height_cropped.max() - height_cropped.min() + 1e-8
        )

    if normal_map.dim() == 3:
        normal_map = normal_map.unsqueeze(0)
    if normal_map.dim() != 4 or normal_map.shape[1] != 3:
        raise ValueError("chord_normal_to_height expects a tensor shaped Bx3xHxW")

    original_size = normal_map.shape[-2:]
    resized = F.interpolate(
        normal_map,
        size=(integration_resolution, integration_resolution),
        mode="bilinear",
        align_corners=False,
        antialias=True,
    )

    height_maps = []
    for index in range(resized.shape[0]):
        height = normal_to_height(resized[index])[None, None]
        if 0 < height.var() < height_var_threshold:
            height = normal_to_height(resized[index], skip_normalize_normal=True)[None, None]
        height_maps.append(height)

    height = torch.cat(height_maps, dim=0)
    if height.shape[-2:] != original_size:
        height = F.interpolate(
            height,
            size=original_size,
            mode="bilinear",
            align_corners=False,
            antialias=True,
        )
    return height


class ChordPBR(fal.App):
    app_name = "chord-pbr-python"
    auth_mode = "private"
    machine_type = "GPU-A100"
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

        import torch
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import LocalEntryNotFoundError
        from omegaconf import OmegaConf

        from chord import ChordModel
        from chord.io import load_torch_file

        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
        os.environ.setdefault("HF_HOME", "/data/.cache/huggingface")
        os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
        os.environ["HF_XET_CHUNK_CACHE_SIZE_BYTES"] = "1000000000000"
        os.environ["HF_XET_NUM_CONCURRENT_RANGE_GETS"] = "32"

        dl_kwargs = dict(
            repo_id=HF_REPO_ID,
            filename=HF_FILENAME,
            local_dir="/data/models/chord",
        )
        try:
            ckpt_path = hf_hub_download(**dl_kwargs, local_files_only=True)
        except LocalEntryNotFoundError:
            ckpt_path = hf_hub_download(**dl_kwargs)

        config = OmegaConf.load(str(resolve_config_path()))
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

        from PIL import Image as PILImage

        target_dir = Path("/tmp/chord-pbr-inputs")
        target_dir.mkdir(parents=True, exist_ok=True)
        img_path = download_file(input.image.url, target_dir)
        src = PILImage.open(str(img_path)).convert("RGB")
        ori_h, ori_w = src.size[1], src.size[0]

        to_tensor = v2.Compose([v2.ToImage(), v2.ToDtype(torch.float32, scale=True)])
        image = to_tensor(src).to(self.device)
        x = v2.Resize(size=(input.resolution, input.resolution), antialias=True)(image).unsqueeze(0)

        with torch.no_grad(), torch.autocast(device_type=self.device.type):
            out = self.model(x)

        resize_back = v2.Resize(size=(ori_h, ori_w), antialias=True)
        basecolor = Image.from_pil(to_pil_image(resize_back(out["basecolor"]).squeeze(0)))
        normal = Image.from_pil(to_pil_image(resize_back(out["normal"]).squeeze(0)))
        height_tensor = chord_normal_to_height(out["normal"])
        height = Image.from_pil(to_pil_image(resize_back(height_tensor).squeeze(0)))
        roughness = Image.from_pil(to_pil_image(resize_back(out["roughness"]).squeeze(0)))
        metalness = Image.from_pil(to_pil_image(resize_back(out["metalness"]).squeeze(0)))

        relit = None
        if input.include_relit:
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
            relit = Image.from_pil(to_pil_image(resize_back(rendered).squeeze(0)))

        return ChordOutput(
            basecolor=basecolor,
            normal=normal,
            height=height,
            roughness=roughness,
            metalness=metalness,
            relit=relit,
        )


if __name__ == "__main__":
    import copy as _copy

    import gradio as gr
    import torch
    from huggingface_hub import hf_hub_download
    from omegaconf import OmegaConf
    from torchvision.transforms import v2
    from torchvision.transforms.functional import to_pil_image

    from chord import ChordModel
    from chord.io import load_torch_file
    from chord.module import make
    from chord.util import get_positions, rgb_to_srgb

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt_path = hf_hub_download(repo_id=HF_REPO_ID, filename=HF_FILENAME)
    config = OmegaConf.load(str(resolve_config_path()))
    model = ChordModel(config)
    model.load_state_dict(load_torch_file(str(ckpt_path)))
    model.eval().to(device)

    def inference(img, resolution, include_relit):
        if img is None:
            return None, None, None, None, None, None

        ori_h, ori_w = img.size[1], img.size[0]
        to_tensor = v2.Compose([v2.ToImage(), v2.ToDtype(torch.float32, scale=True)])
        image = to_tensor(img).to(device)
        x = v2.Resize(size=(resolution, resolution), antialias=True)(image).unsqueeze(0)

        with torch.no_grad(), torch.autocast(device_type=device.type):
            out = model(x)

        height = chord_normal_to_height(out["normal"])
        rendered = None
        if include_relit:
            maps = _copy.deepcopy(out)
            maps["metallic"] = maps.get("metalness", torch.zeros_like(maps["basecolor"]))
            h, w = maps["basecolor"].shape[-2:]
            light = make("point-light", {"position": [0, 0, 10]}).to(device)
            pos = get_positions(h, w, 10).to(device)
            camera = torch.tensor([0, 0, 10.0]).to(device)
            for key in maps:
                if maps[key].dim() == 3:
                    maps[key] = maps[key].unsqueeze(0)
                maps[key] = maps[key].permute(0, 2, 3, 1)
            rgb = model.model.compute_render(maps, camera, pos, light).squeeze(0).permute(0, 3, 1, 2)
            rendered = torch.clamp(rgb_to_srgb(rgb), 0, 1)

        resize_back = v2.Resize(size=(ori_h, ori_w), antialias=True)
        return (
            to_pil_image(resize_back(out["basecolor"]).squeeze(0)),
            to_pil_image(resize_back(out["normal"]).squeeze(0)),
            to_pil_image(resize_back(height).squeeze(0)),
            to_pil_image(resize_back(out["roughness"]).squeeze(0)),
            to_pil_image(resize_back(out["metalness"]).squeeze(0)),
            to_pil_image(resize_back(rendered).squeeze(0)) if rendered is not None else None,
        )

    demo = gr.Interface(
        fn=inference,
        inputs=[
            gr.Image(type="pil", label="Input Image"),
            gr.Slider(minimum=512, maximum=2048, step=128, value=1024, label="Resolution"),
            gr.Checkbox(value=False, label="Include relit output"),
        ],
        outputs=[
            gr.Image(label="Basecolor"),
            gr.Image(label="Normal"),
            gr.Image(label="Height"),
            gr.Image(label="Roughness"),
            gr.Image(label="Metalness"),
            gr.Image(label="Relit"),
        ],
        title="Chord PBR",
    )
    demo.launch()
