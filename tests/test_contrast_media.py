import subprocess

import numpy as np
import pytest
from PIL import Image

from vt.director import contrast as K
from vt.director import media as M
from vt.project import Project
from vt.util import find_tool


def solid(v, h=320, w=180):
    return np.full((h, w, 3), v, dtype="uint8")


def noise(seed, h=320, w=180):
    return np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype="uint8")


def checker(h=320, w=180, n=8):
    ys, xs = np.mgrid[0:h, 0:w]
    return (((ys // n + xs // n) % 2) * 255).astype("uint8")[..., None].repeat(3, axis=2)


def check_independently(img, scrim, aspect="9:16"):
    """Re-do the maths from the Scrim only: blend what the renderer draws, then measure the worst contrast."""
    zt, zb = K.zone(aspect)
    h = img.shape[0]
    r0, r1 = int(zt * h), int(zb * h)
    ys = np.linspace(zt, zb, r1 - r0)
    alpha = K.alpha_profile(ys, scrim.strength, scrim.edge)[:, None]
    under = img[r0:r1].astype("float64") * (1 - alpha[..., None]) + (0 if scrim.ink == "light" else 255) * alpha[..., None]
    lum = K.luminance(under)
    ink = 1.0 if scrim.ink == "light" else 0.0
    return K.worst_ratio(lum, ink)


def test_wcag_basics():
    assert K.contrast_ratio(1.0, 0.0) == pytest.approx(21.0)
    assert K.luminance(np.array([255, 255, 255])) == pytest.approx(1.0)
    assert K.luminance(np.array([0, 0, 0])) == pytest.approx(0.0)


def test_plain_backgrounds_need_no_scrim_and_pick_the_right_ink():
    white = K.decide([solid(250)])
    black = K.decide([solid(8)])
    assert (white.ink, white.kind) == ("dark", "none") and white.ratio >= 4.5
    assert (black.ink, black.kind) == ("light", "none") and black.ratio >= 4.5


def test_busy_background_gets_the_lightest_scrim_that_reaches_the_target():
    for img in (checker(), noise(1), noise(2)):
        sc = K.decide([img])
        assert sc.kind in ("gradient", "panel") and sc.strength > 0
        assert check_independently(img, sc) >= 4.5 - 1e-6, sc
        # lighter treatments must not already have been enough (minimal intervention)
        lower = sc.model_copy(update={"strength": max(0.0, round(sc.strength - 0.05, 2))})
        if sc.strength > 0.15:
            assert check_independently(img, lower) < 4.5 or lower.ink != sc.ink


def test_random_photos_always_end_readable():
    for seed in range(12):
        rng = np.random.default_rng(seed)
        base = rng.integers(0, 256, (1, 1, 3))
        img = np.clip(base + rng.normal(0, 70, (320, 180, 3)), 0, 255).astype("uint8")
        sc = K.decide([img])
        assert sc.ratio >= 4.5 or sc.strength == pytest.approx(0.93)
        assert check_independently(img, sc) == pytest.approx(sc.ratio, abs=0.05)


def test_worst_case_over_several_video_frames_is_used():
    dark, bright = solid(10), solid(245)
    sc = K.decide([dark, bright])                   # the clip is dark in one moment and bright in another: no ink alone is safe without a scrim
    assert sc.kind != "none"
    for fr in (dark, bright):
        assert check_independently(fr, sc) >= 4.5 - 1e-6


def test_landscape_aspect_uses_its_own_zone():
    sc = K.decide([noise(3, 180, 320)], "16:9")
    assert check_independently(noise(3, 180, 320), sc, "16:9") >= 4.5 - 1e-6


def test_cover_crop_keeps_the_subject_in_frame():
    im = np.zeros((100, 400, 3), dtype="uint8")
    im[:, 360:] = 255                                # subject at the far right
    assert K.cover_crop(im, "9:16", 0.9, 0.5)[:, -5:].mean() == 255
    assert K.cover_crop(im, "9:16", 0.9, 0.5).shape[1] == 56
    tall = np.zeros((400, 100, 3), dtype="uint8")
    assert K.cover_crop(tall, "16:9", 0.5, 0.5).shape == (56, 100, 3)


# ---------------------------------------------------------------------------------------------- media bin
@pytest.fixture()
def proj(projects_dir):
    import soundfile as sf
    sf.write(str(projects_dir / "a.wav"), np.zeros(1600, dtype="float32"), 16000)
    return Project.create("m", projects_dir / "a.wav")


def test_images_are_normalised_and_get_a_subject_position(proj, tmp_path):
    im = Image.new("RGB", (3000, 2000), (30, 30, 30))
    im.paste((255, 200, 160), (2200, 700, 2600, 1100))        # a skin-toned blob on the right
    f = tmp_path / "Big Photo.PNG"
    im.save(f)
    item = M.add_media(proj, f, caption="a family")
    assert item.kind == "image" and max(item.width, item.height) <= 2400 and (proj.dir / item.file).exists()
    assert item.fx > 0.55 and 0.2 <= item.fy <= 0.8                  # the subject is on the right
    assert [m.id for m in proj.meta().media] == [item.id]
    again = M.add_media(proj, f)
    assert again.id != item.id                                        # ids stay unique


def test_gif_becomes_a_looping_mp4_and_video_loses_its_audio(proj, tmp_path):
    frames = [Image.new("RGB", (64, 48), (i * 40, 80, 200 - i * 30)) for i in range(5)]
    g = tmp_path / "anim.gif"
    frames[0].save(g, save_all=True, append_images=frames[1:], duration=100, loop=0)
    gi = M.add_media(proj, g)
    assert gi.kind == "gif" and gi.file.endswith(".mp4") and gi.duration > 0.3 and gi.width % 2 == 0
    clip = tmp_path / "clip.mp4"
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=2", "-f", "lavfi", "-i", "sine=duration=2",
                    "-shortest", "-c:v", "libx264", "-c:a", "aac", str(clip)], check=True)
    vi = M.add_media(proj, clip)
    assert vi.kind == "video" and 1.8 < vi.duration < 2.3
    streams = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(proj.dir / vi.file)],
                             capture_output=True, text=True).stdout.split()
    assert streams == ["video"]
    comp = M.composition_media(proj)
    assert comp[gi.id]["loop"] is True and comp[vi.id]["kind"] == "video" and comp[vi.id]["src"].startswith("media/")


def test_bad_files_are_refused_with_a_clear_message(proj, tmp_path):
    for name, data in (("x.exe", b"MZ"), ("empty.jpg", b""), ("fake.png", b"not a picture"), ("fake.mp4", b"not a video")):
        f = tmp_path / name
        f.write_bytes(data)
        with pytest.raises(M.MediaError):
            M.add_media(proj, f)
    assert proj.meta().media == []


def test_remove_media_deletes_the_file(proj, tmp_path):
    f = tmp_path / "p.jpg"
    Image.new("RGB", (50, 50), "red").save(f)
    it = M.add_media(proj, f)
    assert M.remove_media(proj, it.id) and not (proj.dir / it.file).exists() and not M.remove_media(proj, it.id)


def test_decide_for_media_uses_the_cropped_frame(proj, tmp_path):
    f = tmp_path / "noisy.png"
    Image.fromarray(noise(5, 640, 480)).save(f)
    it = M.add_media(proj, f)
    sc = M.__dict__.get("x") or K.decide_for_media(proj, it.id, "9:16")
    assert sc.ratio >= 4.5 or sc.strength > 0.9


def test_speech_envelope_follows_loudness(tmp_path):
    import soundfile as sf
    t = np.arange(16000 * 4) / 16000
    x = np.where((t > 1) & (t < 2), 0.5, 0.01) * np.sin(2 * np.pi * 200 * t)
    wav = tmp_path / "v.wav"
    sf.write(str(wav), x.astype("float32"), 16000)
    env = M.speech_envelope(wav)
    v = np.array(env["v"])
    assert env["dt"] == 0.04 and v[int(1.5 / 0.04)] > 0.8 and v[int(0.5 / 0.04)] < 0.2 and v.max() <= 1


def test_square_aspect_has_its_own_zone_and_crop():
    sc = K.decide([noise(7, 360, 360)], "1:1")
    assert check_independently(noise(7, 360, 360), sc, "1:1") >= 4.5 - 1e-6
    assert K.cover_crop(np.zeros((200, 400, 3), dtype="uint8"), "1:1", 0.5, 0.5).shape[:2] == (200, 200)
    zt, zb = K.zone("1:1")
    assert 0 < zt < zb < 1 and K.zone("1:1", "lower")[0] > zt


# ---------------------------------------------------------------------------------------------- faces
FACE = __import__("pathlib").Path(__file__).parent / "fixtures" / "face.jpg"        # a public-domain NASA portrait (Eileen Collins)


def test_a_real_face_is_found_and_becomes_the_camera_focus(proj):
    pytest.importorskip("cv2")
    item = M.add_media(proj, FACE, caption="portrait")
    assert len(item.faces) == 1
    x, y, w, h = item.faces[0]
    assert 0.2 < x < 0.5 and 0.05 < y < 0.3 and 0.12 < w < 0.3                          # upper middle of the portrait, about a fifth wide
    assert abs(item.fx - (x + w / 2)) < 0.02 and abs(item.fy - (y + h / 2)) < 0.02       # the camera looks at the face, not at the centre of the frame
    assert M.detect_faces(np.zeros((200, 200, 3), dtype="uint8")) == []                  # no face, no box


def test_text_goes_where_the_people_are_not():
    def item(faces, w=1200, h=800):
        from vt.schema import MediaItem
        return MediaItem(id="x", file="media/x.jpg", width=w, height=h, faces=faces, fx=0.5, fy=0.5)

    assert M.text_layout(item([]), "9:16") == "lower"
    assert M.text_layout(item([[0.4, 0.1, 0.15, 0.2]]), "16:9") == "lower"                 # a face in the upper part: text stays low
    assert M.text_layout(item([[0.4, 0.62, 0.15, 0.2]]), "16:9") == "upper"                 # a face in the lower part: text moves up
    # a face that the portrait crop cuts out of the frame does not matter
    assert M.faces_in_frame(item([[0.02, 0.4, 0.08, 0.1]]), "9:16") == []
    inside = M.faces_in_frame(item([[0.46, 0.4, 0.08, 0.1]]), "9:16")
    assert len(inside) == 1 and 0 <= inside[0][0] <= 1 and inside[0][2] > 0.08                # cropping zooms in: the face is a bigger part of the frame


def test_upper_layout_measures_the_top_and_the_caption_not_the_middle():
    zs = K.zones("9:16", "upper")
    assert len(zs) == 2 and zs[0][1] < zs[1][0]
    img = np.zeros((600, 340, 3), dtype="uint8")
    img[int(0.45 * 600):int(0.68 * 600)] = 255                                          # a bright band exactly where the people are
    quiet = K.decide([img], "9:16", "upper")
    loud = K.decide([img], "9:16", "stack")
    assert quiet.kind == "none" and loud.kind != "none"                                  # the bright middle only matters when text could be there


def test_planner_moves_text_above_people_low_in_the_picture():
    from vt.director import plan as D
    from vt.schema import MediaItem
    from test_director import make, PRODUCT
    tr, beats = make(PRODUCT)
    low = MediaItem(id="m1", file="media/m1.jpg", width=1600, height=900, faces=[[0.4, 0.6, 0.15, 0.25]], caption="customers reviews")
    sf = D.plan(tr, beats, usecase="product", seed="f", media=[low], language="en", aspect="16:9")
    bd = [s for s in sf.scenes if s.backdrop]
    assert bd and all(s.layout == "upper" for s in bd)
