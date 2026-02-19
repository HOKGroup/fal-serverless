from fal_chord_python_app import ChordPBR


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
    assert "torch" in reqs
    assert "torchvision" in reqs
    assert "omegaconf" in reqs
    assert "safetensors" in reqs
    assert "huggingface_hub[hf_xet]" in reqs
