"""Details shows a useful question preview without loading huge replies."""
from vt.ai import talk
from vt.server.log_routes import ai_talk,ai_talk_row


def test_question_preview_and_complete_answer_are_both_available(ref):
    talk.record("claude-pc","sonnet",prompt="Measure this frame\nand move the label away from Maya.",answer="The full answer",folder=ref.dir)
    rows=ai_talk(ref.id)["rows"]
    assert rows[-1]["preview"]=="Measure this frame and move the label away from Maya."
    assert "answer" not in rows[-1] and "prompt" not in rows[-1]
    assert ai_talk_row(ref.id,rows[-1]["seq"])["answer"]=="The full answer"


def test_tool_preview_is_the_tool_name(ref):
    talk.record("claude-pc","sonnet",kind="tool",prompt={"tool":"frame_facts","project":ref.id},folder=ref.dir)
    assert ai_talk(ref.id)["rows"][-1]["preview"]=="frame_facts"


def test_sent_image_is_kept_once_and_can_only_be_read_in_its_project(ref):
    import io
    from PIL import Image
    from vt.server.log_routes import ai_talk_image
    from fastapi import HTTPException
    import pytest
    stream=io.BytesIO();Image.new("RGB",(8,8),"red").save(stream,format="PNG")
    data=stream.getvalue()
    for _ in range(2):talk.record("claude-pc","sonnet",images=1,image_data=[data],folder=ref.dir)
    files=list((ref.dir/"ai-talk-images").glob("*"))
    assert len(files)==1 and files[0].read_bytes()==data
    row=ai_talk_row(ref.id,1)
    assert row["image_files"]==[files[0].name]
    assert str(ai_talk_image(ref.id,files[0].name).path)==str(files[0])
    with pytest.raises(HTTPException):ai_talk_image(ref.id,"../../settings.json")


def test_actual_provider_call_records_the_picture_it_was_sent(ref):
    import io
    from PIL import Image
    from types import SimpleNamespace
    from vt.ai.providers import complete_json
    stream=io.BytesIO();Image.new("RGB",(8,8),"blue").save(stream,format="PNG")
    sent=[]
    def answer(system,prompt,schema,images,*args):
        sent.extend(images)
        return '{"ok":true}'
    provider=SimpleNamespace(name="test",model=lambda:"fake",supports_images=True,complete=answer)
    with talk.for_project(ref.dir):
        complete_json("Check the frame",{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]},images=[stream.getvalue()],provider=provider,cache=False)
    row=talk.load(ref.dir)[-1]
    assert row["images"]==1
    assert (ref.dir/"ai-talk-images"/row["image_files"][0]).read_bytes()==sent[0]


def test_image_storage_failure_keeps_the_question_and_answer(ref,monkeypatch):
    import io
    from pathlib import Path
    from PIL import Image
    stream=io.BytesIO();Image.new("RGB",(8,8),"red").save(stream,format="PNG")
    monkeypatch.setattr(Path,"write_bytes",lambda *args:(_ for _ in ()).throw(OSError("Disk full")))
    talk.record("test","fake",prompt="A question",answer="An answer",images=1,image_data=[stream.getvalue()],folder=ref.dir)
    row=talk.load(ref.dir)[-1]
    assert row["answer"]=="An answer" and row["prompt"]=="A question"
    assert "storage" in row["image_save_error"]
