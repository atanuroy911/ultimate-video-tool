"""Nothing is placed on a person: the person mask, the crop mapping, the free-rectangle search and what the composer does with them."""
import itertools
import json

import numpy as np
import pytest

from vt import people as PE

FACE = [0.42, 0.10, 0.14, 0.22]


def test_a_body_shape_from_a_face_covers_the_head_and_the_body_below_and_not_the_corners():
    m = PE.face_body_mask(FACE, 90, 160)
    cy, cx = int((0.10 + 0.11) * 90), int(0.49 * 160)
    assert m[cy, cx] and m[80, cx] and m[70, cx + 20]                                          # head, torso, shoulder
    assert not m[5, 5] and not m[5, 155] and not m[cy, 5]                                      # corners and the wall beside the head are free


def test_the_grid_is_grown_by_a_margin_and_survives_packing():
    m = np.zeros((90, 160), dtype=bool)
    m[30:60, 70:90] = True
    g = PE.to_grid(m, margin=0.0)
    g2 = PE.to_grid(m, margin=0.05)
    assert g.shape == (PE.GH, PE.GW) and g2.sum() > g.sum() > 0
    assert (PE.unpack(PE.pack(g2)) == g2).all() and all(len(r) == PE.GW for r in PE.pack(g2))


def test_the_crop_window_follows_object_fit_cover_and_the_punch_in():
    x0, y0, x1, y1 = PE.window(16 / 9, 9 / 16, 0.5, 0.4)
    assert abs((x1 - x0) - (9 / 16) / (16 / 9)) < 1e-6 and y0 == 0 and y1 == 1                  # a tall crop of a wide picture keeps the full height
    assert abs((x0 + x1) / 2 - 0.5) < 1e-6
    left = PE.window(16 / 9, 9 / 16, 0.0, 0.4)
    assert left[0] == 0                                                                        # object-position 0 %: the left edge
    z = PE.window(16 / 9, 9 / 16, 0.5, 0.4, zoom=1.2)
    assert (z[2] - z[0]) < (x1 - x0) and z[1] > 0                                              # zooming in shows less
    a = PE.window(1.0, 16 / 9, 0.5, 0.5)
    assert abs((a[3] - a[1]) - 1 / (16 / 9)) < 1e-6 and a[2] - a[0] == 1.0                      # a square picture in a wide frame loses top and bottom


def test_a_person_filling_a_tall_crop_leaves_no_room_but_a_wide_one_has_the_sides():
    body = PE.to_grid(PE.face_body_mask([0.43, 0.08, 0.14, 0.24], 90, 160), margin=0.03)
    tall = PE.to_output(body, 16 / 9, 9 / 16, 0.5, 0.4)
    assert PE.largest_free_rect(tall, 0.04, 0.66, 0.30, 0.12) is None                          # the crop is all person: no place for anything
    wide = PE.to_output(body, 16 / 9, 16 / 9, 0.5, 0.4)
    r = PE.largest_free_rect(wide, 0.04, 0.78, 0.22, 0.20)
    assert r is not None and (r[0] + r[2] <= 0.42 or r[0] >= 0.58)                             # beside the person, not on them
    x, y, w, h = r
    sub = wide[int(y * wide.shape[0]):int((y + h) * wide.shape[0]), int(x * wide.shape[1]):int((x + w) * wide.shape[1])]
    assert not sub.any()


def test_the_free_rectangle_is_the_largest_one_when_checked_against_brute_force():
    rng = np.random.default_rng(5)
    for _ in range(25):
        occ = rng.random((9, 12)) < 0.3
        got = PE.largest_free_rect(occ, 0.0, 1.0, 0.0, 0.0)
        best = 0
        for r0, r1 in itertools.combinations(range(10), 2):
            for c0, c1 in itertools.combinations(range(13), 2):
                if not occ[r0:r1, c0:c1].any():
                    best = max(best, (r1 - r0) * (c1 - c0))
        if best == 0:
            assert got is None
        else:
            assert abs(got[2] * 12 * got[3] * 9 - best) < 1e-6, (got, best)
    assert PE.largest_free_rect(np.zeros((9, 12), bool), 0.0, 0.5, 0.5, 0.6) is None             # too small for what was asked


def test_only_the_part_touching_the_face_is_the_person_not_a_big_object_beside_them(monkeypatch):
    from vt import cutout

    h, w = 360, 640
    a = np.zeros((h, w), dtype="float32")
    a[40:340, 250:390] = 1.0                      # the person (head and body)
    a[200:340, 20:180] = 1.0                      # a big box beside them: salient, but not a person
    monkeypatch.setattr(cutout, "available", lambda: True)
    monkeypatch.setattr(cutout, "matte", lambda im: a)
    frame = np.zeros((h, w, 3), dtype="uint8")
    m = PE.person_mask(frame, [250 / w, 40 / h, 140 / w, 100 / h])
    hh, ww = m.shape
    assert m[int(0.5 * hh), int(0.5 * ww)] and not m[int(0.75 * hh), int(0.15 * ww)]            # the person yes, the box no
    # without a model the body shape from the face box is used
    monkeypatch.setattr(cutout, "available", lambda: False)
    m2 = PE.person_mask(frame, [250 / w, 40 / h, 140 / w, 100 / h])
    assert m2[int(0.5 * hh), int(0.5 * ww)] and not m2[int(0.75 * hh), int(0.1 * ww)]
    assert not PE.person_mask(frame, None, use_model=False).any()                                # no face and no model: nothing is claimed


def _scene_with_person(ref, grid_rows, motion="none", media_w=1920, media_h=1080):
    from vt.planner import plan_rules
    from vt.schema import Backdrop, MediaItem, Scrim, Sticker

    sf = plan_rules(ref.transcript(), ref.beats(), ref.meta().theme, language="bn")
    sc = sf.scenes[0]
    first = ref.beats().beats[0].word_ids[0]
    sc.elements = [Sticker(at_word=first, emoji="1f44f", label="Applause")]
    sc.backdrop = Backdrop(media="aroll", motion=motion, fx=0.5, fy=0.3, scrim=Scrim(), person=grid_rows)
    item = MediaItem(id="aroll", file="media/aroll.mp4", kind="video", role="a_roll", width=media_w, height=media_h, duration=18.0, fx=0.5, fy=0.3)
    ref.update_meta(media=[item])
    (ref.dir / "media").mkdir(exist_ok=True)
    (ref.dir / "media" / "aroll.mp4").write_bytes(b"")
    ref.save_scenes(sf)
    return sf


def _compose(ref, aspect):
    from vt.compose import compose_project

    return json.loads((compose_project(ref, aspect).parent / "data.json").read_text(encoding="utf-8"))


def test_the_composer_puts_elements_beside_a_person_in_a_wide_frame_and_drops_them_in_a_tall_one(ref):
    body = PE.pack(PE.to_grid(PE.face_body_mask([0.43, 0.08, 0.14, 0.24], 90, 160), margin=0.03))
    _scene_with_person(ref, body)
    wide = _compose(ref, "16:9")["scenes"][0]
    assert wide["elements"] and wide["stage"] and (wide["stage"][0] + wide["stage"][2] <= 0.45 or wide["stage"][0] >= 0.55)
    tall = _compose(ref, "9:16")["scenes"][0]
    assert tall["elements"] == [] and tall.get("cleared_for_person") is True and "stage" not in tall      # the speaker fills the crop: nothing goes on them
    # nobody in the picture: the usual layout is kept
    empty = ["0" * PE.GW] * PE.GH
    _scene_with_person(ref, empty)
    free = _compose(ref, "9:16")["scenes"][0]
    assert free["elements"] and "stage" not in free


def test_a_photo_with_a_face_gets_the_same_care_without_any_stored_mask(ref):
    from vt.planner import plan_rules
    from vt.schema import Backdrop, MediaItem, Scrim, Sticker

    sf = plan_rules(ref.transcript(), ref.beats(), ref.meta().theme, language="bn")
    sc = sf.scenes[0]
    sc.elements = [Sticker(at_word=ref.beats().beats[0].word_ids[0], emoji="1f44f", label="x")]
    sc.backdrop = Backdrop(media="pic", motion="none", fx=0.5, fy=0.3, scrim=Scrim())
    ref.update_meta(media=[MediaItem(id="pic", file="media/pic.jpg", kind="image", width=1600, height=900, fx=0.5, fy=0.3, faces=[[0.43, 0.08, 0.14, 0.24]])])
    from PIL import Image

    (ref.dir / "media").mkdir(exist_ok=True)
    Image.new("RGB", (160, 90), (120, 120, 120)).save(ref.dir / "media" / "pic.jpg")
    ref.save_scenes(sf)
    wide = _compose(ref, "16:9")["scenes"][0]
    assert wide.get("stage") and (wide["stage"][0] + wide["stage"][2] <= 0.45 or wide["stage"][0] >= 0.55)


def test_the_crop_follows_the_head_of_the_person_in_each_scene():
    from vt import aroll as AR

    def person_at(cx):                                                  # a head and shoulders centred at cx (fraction of the picture width)
        m = np.zeros((90, 160), dtype=bool)
        m[10:30, int((cx - 0.05) * 160):int((cx + 0.05) * 160)] = True          # head
        m[30:90, int((cx - 0.18) * 160):int((cx + 0.18) * 160)] = True          # body
        return PE.pack(PE.to_grid(m, margin=0.0))
    fx_left, _ = AR.head_focus(person_at(0.3), 16 / 9, (0.5, 0.4))
    fx_mid, _ = AR.head_focus(person_at(0.5), 16 / 9, (0.5, 0.4))
    fx_right, fy = AR.head_focus(person_at(0.75), 16 / 9, (0.5, 0.4))
    assert fx_left < fx_mid < fx_right and abs(fx_mid - 0.5) < 0.06 and fx_left < 0.3 and fx_right > 0.8
    # the crop window that results really contains the head
    for cx, fx in ((0.3, fx_left), (0.75, fx_right)):
        x0, _, x1, _ = PE.window(16 / 9, 9 / 16, fx, 0.4)
        assert x0 < cx - 0.04 and x1 > cx + 0.04
    assert 0.1 < fy < 0.5
    assert AR.head_focus([], 16 / 9, (0.4, 0.3)) == (0.4, 0.3) and AR.head_focus(["0" * PE.GW] * PE.GH, 16 / 9, (0.4, 0.3)) == (0.4, 0.3)
