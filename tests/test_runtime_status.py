import json

from visionguard.runtime.status import StatusWriter


def test_status_writer_atomically_publishes_handshake(tmp_path):
    path = tmp_path / "状态" / "runtime.json"
    writer = StatusWriter(path, runtime_version="0.1.0", api_version="v1")
    writer.update(state="launching", endpoint="http://127.0.0.1:54321")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["state"] == "launching"
    assert payload["endpoint"].endswith(":54321")
    assert payload["pid"] > 0
