"""Media-layer static transforms must survive validation, history and composition."""
from vt import layers


def doc(transform):
    return {"v":1,"tracks":[{"id":"track","kind":"visual"}],"clips":[{
        "id":"picture","track":"track","type":"media","media":"photo","start":0,"dur":2,
        "scale":1.4,"rotation":20,"transform":transform}]}


def test_static_media_effects_survive_validation():
    clean, errors = layers.validate(doc({"stretch_x":2,"tilt_y":30,"blur":4,"crop":[.1,0,0,0]}), 5, {"photo":"image"})
    assert not errors
    clip = clean["clips"][0]
    assert clip["scale"] == 1.4 and clip["rotation"] == 20
    assert clip["transform"]["stretch_x"] == 2
    assert clip["transform"]["tilt_y"] == 30 and clip["transform"]["blur"] == 4


def test_invalid_media_effects_are_refused():
    _, errors = layers.validate(doc({"blur":-3}), 5, {"photo":"image"})
    assert errors and "picture" in errors[0]


def test_media_effects_are_kept_in_layer_history(ref):
    first, errors = layers.validate(doc({"skew_x":15}), 5, {"photo":"image"})
    assert not errors
    layers.save(ref, first)
    second, _ = layers.validate(doc({"skew_x":25}), 5, {"photo":"image"})
    layers.save(ref, second)
    assert layers.step(ref,"undo")["clips"][0]["transform"]["skew_x"] == 15
    assert layers.step(ref,"redo")["clips"][0]["transform"]["skew_x"] == 25
