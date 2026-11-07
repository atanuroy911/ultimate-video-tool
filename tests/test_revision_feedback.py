"""The single revision reads measured problems first and preserves correct parts."""
from vt.director_review import _scene_prompt, apply_changes


def test_exact_frame_facts_lead_the_single_revision_prompt(ref):
    scene=ref.scenes().scenes[0]
    fact="element 0 covers 70% of Maya's face."
    prompt=_scene_prompt(scene,"Maya found a coin.",[fact])
    assert prompt.index(fact)<prompt.index("The narrator")
    assert "For each problem fact, give one change" in prompt
    assert "one revision" in prompt and "leave correct parts alone" in prompt


def test_refused_change_reports_the_field_not_just_a_validation_header(ref):
    scene=ref.scenes().scenes[0]
    same,notes=apply_changes(scene,[{"element":0,"set":{"opacity":9}}])
    assert same==scene
    assert any("opacity" in note for note in notes),notes
