"""The server's own pages carry the graphics card question (PLAN-PERFECT K5): the script is served, both pages load it, and the install tab no longer asks for a card."""
from fastapi.testclient import TestClient


def client():
    from vt.server.app import app

    return TestClient(app)


def test_the_server_serves_the_question_script():
    js = client().get("/gpu-choice.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert "data-gpu-choice" in js.text and "/api/system/gpus" in js.text and "/api/system/gpu'" in js.text and "/api/system/engine-own" in js.text


def test_the_overview_and_the_settings_page_use_it():
    c = client()
    home = c.get("/")
    assert home.status_code == 200 and "data-gpu-choice" in home.text and '<script src="/gpu-choice.js">' in home.text
    manage = c.get("/manage")
    assert manage.status_code == 200 and 'data-tab="cards"' in manage.text and '<script src="/gpu-choice.js">' in manage.text and "data-gpu-choice" in manage.text
    assert 'id="gpu"' not in manage.text and "see Graphics cards" in manage.text           # the install tab no longer asks for a card
    script = c.get("/manage.js").text
    assert "$('gpu')" not in script and "#cards" in script and "needs_choice" in script    # and the page opens on the cards when a choice is waiting
