"""The same five hard shots (self-contained prompts with their place) on three picture models, on the RTX 3060 (ComfyUI 8188).
Per model: seconds per picture, the card's peak memory, the server's lowest free RAM and highest swap. Then one sheet: rows = shots, columns = models.
    python bench_models.py [zimage klein qwen]"""
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import paramiko
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"C:\Users\Roy\Desktop\ultimate-video-tool")
from vt.comfy import ComfyClient, picture_workflow  # noqa: E402
from vt.comfy.client import output_files  # noqa: E402
from vt.reel.style import cast_for, drawing_style, prompt_for  # noqa: E402

URL = "http://192.168.123.47:8188"
OUT = Path(r"C:\Users\Roy\Videos\Video Tool Lab\story\one-gpu\bench")
PLAN = json.loads(Path(r"C:\Users\Roy\Videos\Video Tool Lab\story\projects\the-last-lamp-places\plan_doc.json").read_text(encoding="utf-8"))
SHOTS = (sys.argv[sys.argv.index("--shots") + 1].split(",") if "--shots" in sys.argv else ["s3", "s9", "s10", "s21", "s22"])
W, H = 720, 1280
style = drawing_style(PLAN["idea"]["style"], "style-watercolor")
moments = {m["id"]: m for m in PLAN["moments"]}
PROMPTS = {s: prompt_for(moments[s]["draw"], style, cast_for(moments[s]["draw"], PLAN["idea"].get("cast", {})) or PLAN["idea"]["character"],
                         PLAN["idea"]["places"].get(moments[s]["place"], "")) for s in SHOTS}


def zimage(prompt, seed):
    g, _ = picture_workflow("zimage-fp8").patched(image="", prompt=prompt, aspect="9:16", seconds=1, seed=seed, prefix="bench/zimage")
    g["7"]["inputs"].update(width=W, height=H)
    return g


def klein(prompt, seed, dtype="default"):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b.safetensors", "weight_dtype": dtype}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b_fp8_mixed.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1.0}},
        "7": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "8": {"class_type": "Flux2Scheduler", "inputs": {"steps": 4, "width": W, "height": H}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["6", 0], "sampler": ["7", 0], "sigmas": ["8", 0], "latent_image": ["10", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": f"bench/klein_{uuid.uuid4().hex[:6]}"}},
    }


def qwen(prompt, seed):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_turbo_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_w4a8.safetensors", "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
        "4": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["2", 0], "prompt": prompt, "negative_prompt": "", "resolution": 1024}},
        "5": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
        "6": {"class_type": "CFGGuider", "inputs": {"model": ["5", 0], "positive": ["4", 0], "negative": ["4", 1], "cfg": 1.0}},
        "7": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "8": {"class_type": "ManualSigmas", "inputs": {"sigmas": "1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0"}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["6", 0], "sampler": ["7", 0], "sigmas": ["8", 0], "latent_image": ["10", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": f"bench/qwen_{uuid.uuid4().hex[:6]}"}},
    }


MODELS = {"zimage": ("Z-Image Turbo 8-bit", zimage), "klein": ("FLUX.2 Klein 4B", klein), "klein8": ("FLUX.2 Klein 4B 8-bit", lambda p, s: klein(p, s, "fp8_e4m3fn")),
          "qwen": ("Qwen-Image 2.1 Turbo", qwen)}


class Watch:
    """The 3060's memory, the server's free RAM and swap, every 3 s, over SSH."""

    def __init__(self):
        self.peak_card = 0
        self.min_avail = 10**9
        self.max_swap = 0
        self.stop = threading.Event()
        self.t = threading.Thread(target=self.run, daemon=True)
        self.t.start()

    def run(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect("192.168.123.47", username="roy", password=os.environ["GPU_PASS"], timeout=15, look_for_keys=False, allow_agent=False)
        while not self.stop.is_set():
            _, o, _ = ssh.exec_command("nvidia-smi -i 1 --query-gpu=memory.used --format=csv,noheader,nounits; free -m | awk '/Mem/{print $7} /Swap/{print $3}'")
            v = o.read().decode().split()
            try:
                self.peak_card, self.min_avail, self.max_swap = max(self.peak_card, int(v[0])), min(self.min_avail, int(v[1])), max(self.max_swap, int(v[2]))
            except (ValueError, IndexError):
                pass
            time.sleep(3)
        ssh.close()

    def done(self):
        self.stop.set()
        self.t.join(10)
        return {"card_peak_gb": round(self.peak_card / 1024, 1), "ram_avail_min_gb": round(self.min_avail / 1024, 1), "swap_max_gb": round(self.max_swap / 1024, 1)}


def run(name):
    label, make = MODELS[name]
    c = ComfyClient(URL)
    c.free_memory()
    time.sleep(5)
    (OUT / name).mkdir(parents=True, exist_ok=True)
    w = Watch()
    times = []
    for i, s in enumerate(SHOTS):
        seed = 1000 + i
        t = time.time()
        pid = c.submit(make(PROMPTS[s], seed))
        entry = c.wait(pid, timeout=1200)
        times.append(round(time.time() - t, 1))
        f = output_files(entry)[0]
        c.download(f["filename"], f["subfolder"], f["type"], OUT / name / f"{s}.png")
        print(name, s, times[-1], "s", flush=True)
    mem = w.done()
    rec = {"model": label, "seconds": times, "first_s": times[0], "warm_s": round(sum(times[1:]) / max(1, len(times) - 1), 1), **mem}
    (OUT / name / "result.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print("RESULT", json.dumps(rec), flush=True)
    c.free_memory()
    return rec


def sheet(names):
    tw, th = 270, 480
    img = Image.new("RGB", (60 + tw * len(names), 50 + th * len(SHOTS)), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for j, n in enumerate(names):
        r = json.loads((OUT / n / "result.json").read_text()) if (OUT / n / "result.json").exists() else {}
        d.text((60 + j * tw + 6, 6), f"{MODELS[n][0]}", fill="black", font=font)
        d.text((60 + j * tw + 6, 26), f"{r.get('warm_s', '?')} s, card {r.get('card_peak_gb', '?')} GB", fill="gray", font=font)
        for i, s in enumerate(SHOTS):
            p = OUT / n / f"{s}.png"
            if p.exists():
                img.paste(Image.open(p).convert("RGB").resize((tw, th)), (60 + j * tw, 50 + i * th))
    for i, s in enumerate(SHOTS):
        d.text((8, 50 + i * th + th // 2), s, fill="black", font=font)
    img.save(OUT / "sheet.png")
    print("SHEET", OUT / "sheet.png", flush=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prompts.json").write_text(json.dumps(PROMPTS, indent=1, ensure_ascii=False), encoding="utf-8")
    names = [a for a in sys.argv[1:] if a in MODELS] or list(MODELS)
    for n in names:
        try:
            run(n)
        except Exception as e:                                          # one model failing must not hide the others
            print("FAILED", n, type(e).__name__, str(e)[:400], flush=True)
    sheet([n for n in MODELS if (OUT / n / "result.json").exists()])
