from fal_chord_python_app import ChordPBR, Input, Output


def test_app_config_and_packaging():
    assert ChordPBR.app_name == "chord-pbr-python"
    assert ChordPBR.machine_type == "GPU-H100"
    assert ChordPBR.keep_alive == 300
    assert ChordPBR.min_concurrency == 0
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


def test_output_has_named_fields():
    fields = set(Output.model_fields.keys())
    assert fields == {"basecolor", "normal", "roughness", "metalness", "relit"}


def test_input_defaults():
    schema = Input.model_json_schema()
    props = schema["properties"]
    assert props["resolution"]["default"] == 1024
    assert props["light_position"]["default"] == [0.0, 0.0, 10.0]
    assert props["include_relit"]["default"] is True
