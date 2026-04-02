from fal_chord_python_app import ChordInput, ChordOutput, ChordPBR


def test_app_config_and_packaging():
    assert ChordPBR.app_name == "chord-pbr-python"
    assert ChordPBR.auth_mode == "private"
    assert ChordPBR.machine_type == "GPU-A100"
    assert ChordPBR.keep_alive == 300
    assert ChordPBR.max_concurrency == 1
    assert "chord" in ChordPBR.app_files
    assert "config" in ChordPBR.app_files


def test_requirements_include_key_packages():
    reqs = ChordPBR.requirements
    assert "torch==2.10.0" in reqs
    assert "torchvision==0.25.0" in reqs
    assert "omegaconf==2.3.0" in reqs
    assert "safetensors==0.7.0" in reqs
    assert "huggingface_hub[hf_xet]" in reqs


def test_input_defaults_and_bounds():
    payload = ChordInput(image={"url": "https://example.com/input.png"})

    assert payload.image.url == "https://example.com/input.png"
    assert payload.resolution == 1024
    assert payload.include_relit is False


def test_output_includes_height_map():
    assert "height" in ChordOutput.model_fields


def test_height_conversion_helper_exists_on_fal_module():
    assert hasattr(ChordPBR.generate.__globals__["chord_normal_to_height"], "__call__")
