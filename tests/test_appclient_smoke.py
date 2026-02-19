import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_FAL_APPC_TEST"),
    reason="Set RUN_FAL_APPC_TEST=1 to run AppClient smoke test",
)


def test_fal_appclient_smoke():
    import fal
    from fal_chord_python_app import ChordPBR

    with fal.app.AppClient(ChordPBR) as client:
        # Intentional invalid URL to verify endpoint wiring and error propagation path.
        with pytest.raises(Exception):
            client.generate({"image_url": "https://invalid.example/not-found.png"})
