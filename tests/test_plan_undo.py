"""A plan change made by an assistant over MCP can be undone from the app (AI panel, "Undo the last plan change"): the server keeps the plan as
it was before each save, GET says whether there is one, POST brings it back, and a second POST puts the change back."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_an_assistants_change_is_undone_from_the_app_and_redone(client, ref):
    from vt.mcp import server as mcp

    (ref.dir / "scenes.prev.json").unlink(missing_ok=True)
    assert client.get("/api/projects/reference/scenes/undo").json() == {"available": False, "at": None}

    before = client.get("/api/projects/reference/scenes").json()
    first = before["plan"]["scenes"][0] if "plan" in before else before["scenes"][0]
    fn = getattr(mcp.update_scene, "fn", mcp.update_scene)
    assert fn("reference", first["id"], {"caption": {"y": 0.31}})["ok"]
    changed = ref.scenes().scenes[0].model_dump(exclude_none=True)
    assert changed.get("caption", {}).get("y") == 0.31

    state = client.get("/api/projects/reference/scenes/undo").json()
    assert state["available"] is True and state["at"]

    assert client.post("/api/projects/reference/scenes/undo").status_code == 200
    assert (ref.scenes().scenes[0].model_dump(exclude_none=True).get("caption") or {}).get("y") != 0.31   # the assistant's change is gone
    assert client.post("/api/projects/reference/scenes/undo").status_code == 200
    assert ref.scenes().scenes[0].model_dump(exclude_none=True)["caption"]["y"] == 0.31                   # and pressing again puts it back
