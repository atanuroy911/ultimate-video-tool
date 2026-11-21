"""Which models fit which card: the sum the VRAM calculators do (apxml.com/tools/vram-calculator, llm-speed.com/tools/vram-fit), for our models.

    on the card  =  weights at the precision they run in  +  working memory for one 720x1280 picture  +  CUDA's own share
    in RAM       =  what ComfyUI parks there between steps  +  a reading buffer (files are memory-mapped: their pages are dropped, not swapped)

A picture recipe is one set of files for the same Z-Image Turbo graph (the loaders change, nothing else). Recipes are ranked by quality; the
best one whose numbers fit the card is chosen, and nothing that would spill into RAM-and-swap is chosen at all: on the owner's GPU server a
20 GB set on a 16 GB card parked the rest in RAM and the box swapped until it crashed (2026-11-01).

Modes, best first:
    resident    everything stays on the card: fastest
    sequential  the text encoder and the picture model take turns on the card (ComfyUI moves one to RAM while the other runs): about a
                second slower per picture over PCIe, same quality
    partial     the picture model itself does not fit and ComfyUI streams part of it from RAM: works, several times slower; only offered
                when nothing else fits
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

HF = "https://huggingface.co/Comfy-Org/Z-Image-Turbo/resolve/6fc90a3b1b653e935a0d175e260736de25b84df5/split_files/"
GB = 1e9

# every file a recipe may use: where it goes, its size on disk, and its checksum (Hugging Face's LFS sha256)
FILES: dict[str, dict[str, Any]] = {
    "diffusion_models/z_image_turbo_bf16.safetensors": {"size": 12309866400, "sha256": "2407613050b809ffdff18a4ac99af83ea6b95443ecebdf80e064a79c825574a6"},
    "diffusion_models/z_image_turbo_nvfp4.safetensors": {"size": 4509509600, "sha256": "a553c889dbcb910de4c98293237573219a37007c1074a3f04576646a088bd5c8"},
    "text_encoders/qwen_3_4b.safetensors": {"size": 8044982048, "sha256": "6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a"},
    "text_encoders/qwen_3_4b_fp8_mixed.safetensors": {"size": 5631994051, "sha256": "72450b19758172c5a7273cf7de729d1c17e7f434a104a00167624cba94f68f15"},
    "text_encoders/qwen_3_4b_fp4_mixed.safetensors": {"size": 3479416193, "sha256": "7ca32dcf07dfe7692945d80fff86e3a74cb83c6206b9b223ac6836b939bb85d6"},
    "vae/ae.safetensors": {"size": 335304388, "sha256": ""},
}
for _p, _f in FILES.items():
    _f["url"] = HF + _p
KLEIN = "https://huggingface.co/Comfy-Org/Flux-2-Klein-4B/resolve/5b3abca5c0dc1ecd4eaf3340868d09063fc1c965/split_files/"
QWEN = "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/aacf31a6d48e707f352ecba714cee0680da3479b/"
FILES.update({
    "diffusion_models/flux-2-klein-4b.safetensors": {"size": 7751105712, "sha256": "ec3d4e733a771f61c052fb4856c48b336c55eaf2c65487c2a1faeb9bbda7a343",
                                                     "url": KLEIN + "diffusion_models/flux-2-klein-4b.safetensors"},
    "vae/flux2-vae.safetensors": {"size": 336211292, "sha256": "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3", "url": KLEIN + "vae/flux2-vae.safetensors"},
    "diffusion_models/qwen_image_2.1_turbo_int8_convrot.safetensors": {"size": 7256787829, "sha256": "8144a0182964aa8403ad6dbc011db837304167d235161b9aabaa8532e967314c",
                                                                       "url": QWEN + "diffusion_models/qwen_image_2.1_turbo_int8_convrot.safetensors"},
    "text_encoders/qwen3vl_8b_w4a8.safetensors": {"size": 6312105364, "sha256": "7754425e55e7bea2bfde4dde59a4cc236cb44e5ee9c215ea66ef8d47012824eb",
                                                  "url": QWEN + "text_encoders/qwen3vl_8b_w4a8.safetensors"},
    "vae/qwen_image_2.1_vae_bf16.safetensors": {"size": 675509688, "sha256": "bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9",
                                                "url": QWEN + "vae/qwen_image_2.1_vae_bf16.safetensors"},
})
# Small cards (6 GB and less): the same Klein 4B and its Qwen3-4B text reader, squeezed to 4 or 3 bits (GGUF, Apache-2.0, unsloth). ComfyUI reads them
# through the ComfyUI-GGUF add-on (city96), which the installer puts in custom_nodes; they stay squeezed on the card and are unpacked layer by layer.
KLEIN_GGUF = "https://huggingface.co/unsloth/FLUX.2-klein-4B-GGUF/resolve/a09d5bb51ac4000ccd9643d10e9db3ed14200508/"
QWEN3_GGUF = "https://huggingface.co/unsloth/Qwen3-4B-GGUF/resolve/22c9fc8a8c7700b76a1789366280a6a5a1ad1120/"
FILES.update({
    "diffusion_models/flux-2-klein-4b-Q4_K_M.gguf": {"size": 2604311104, "sha256": "0b25d143c8469b342bc5af3bce92b783bf6b0636d285f7b2f75e38af63af9a15",
                                                    "url": KLEIN_GGUF + "flux-2-klein-4b-Q4_K_M.gguf"},
    "diffusion_models/flux-2-klein-4b-Q3_K_M.gguf": {"size": 2124489280, "sha256": "0f27104f7b5842b7bfd5909645c60208cbb6b8d43f5d65f58b085f45ed18c9e1",
                                                    "url": KLEIN_GGUF + "flux-2-klein-4b-Q3_K_M.gguf"},
    "text_encoders/Qwen3-4B-Q4_K_M.gguf": {"size": 2497281312, "sha256": "f6f851777709861056efcdad3af01da38b31223a3ba26e61a4f8bf3a2195813a",
                                          "url": QWEN3_GGUF + "Qwen3-4B-Q4_K_M.gguf"},
    "text_encoders/Qwen3-4B-Q3_K_M.gguf": {"size": 2075618592, "sha256": "e78ff54a67f3b3f57e637fbf0770d5b73c1e215ea7c0153980f1e8140c2b2486",
                                          "url": QWEN3_GGUF + "Qwen3-4B-Q3_K_M.gguf"},
})
GGUF_ADDON = {"name": "ComfyUI-GGUF", "repo": "https://github.com/city96/ComfyUI-GGUF", "commit": "6ea2651e7df66d7585f6ffee804b20e92fb38b8a",
              "nodes": ["UnetLoaderGGUF", "CLIPLoaderGGUF"]}

CUDA_SHARE = 0.9          # GB the CUDA context, cuBLAS workspaces and PyTorch's allocator take before any weight
COMFORT = 1.0            # headroom rule: 0.85 kept 15 % of the card free; switched off by the owner for now (2026-11-01). Lower it to bring it back
MARGIN = 0.07             # of the card kept free: other programs' contexts, fragmentation
READ_BUFFER = 2.0         # GB while a weight file is read and cast to the precision it runs in
RAM_FOR_SYSTEM = 4.0      # GB of the server's RAM never counted on: the OS, the Video Tool server, the browser


@dataclass
class Recipe:
    id: str
    label: str
    quality: int                                  # 100 = the reference set; lower draws a little less faithfully
    unet: str
    unet_dtype: str                               # UNETLoader weight_dtype: "default" keeps the file's precision
    unet_card: float                              # GB on the card at that precision
    text: str
    text_card: float
    vae: str = "vae/ae.safetensors"
    vae_card: float = 0.34
    work: float = 1.6                             # GB of working memory while sampling one 720x1280 picture
    decode: float = 1.9                           # GB the picture decoder needs on top of its weights
    min_compute: float = 0.0                      # nvfp4 runs only on Blackwell (10.0+)
    note: str = ""
    workflow: str = "zimage_t2i"                  # the graph (assets/comfy/workflows); its loaders are nodes 1, 2, 3
    seconds: float = 0.0                          # measured seconds a picture, warm, on an RTX 3060 at 720x1280 (0 = not measured)
    gguf: bool = False                            # squeezed files: loaded by ComfyUI-GGUF's loaders instead of ComfyUI's own

    def files(self) -> list[str]:
        return [self.unet, self.text, self.vae]

    def download_gb(self, have: set[str] = frozenset()) -> float:
        return round(sum(FILES[f]["size"] for f in self.files() if f.rsplit("/", 1)[-1] not in have) / GB, 1)

    def resident(self) -> float:
        return self.unet_card + self.text_card + self.vae_card + max(self.work, self.decode) + CUDA_SHARE

    def sequential(self) -> float:
        return max(self.text_card, self.unet_card + self.vae_card + max(self.work, self.decode)) + CUDA_SHARE

    def partial(self) -> float:
        return self.vae_card + max(self.work, self.decode) + CUDA_SHARE + 1.5     # the smallest slice of the model ComfyUI keeps on the card

    def ram(self, mode: str) -> float:
        """GB of the server's RAM this recipe holds: the parked models, plus a buffer while a file is read and cast."""
        loading = READ_BUFFER
        parked = {"resident": 0.0, "sequential": self.text_card, "partial": self.text_card + self.unet_card}[mode]
        return round(loading + parked, 1)

    def graph_inputs(self) -> dict[str, dict[str, str]]:
        """What the recipe writes into its graph: only its three loaders."""
        if self.gguf:
            return {"1": {"unet_name": self.unet.rsplit("/", 1)[-1]}, "2": {"clip_name": self.text.rsplit("/", 1)[-1]}, "3": {"vae_name": self.vae.rsplit("/", 1)[-1]}}
        return {"1": {"unet_name": self.unet.rsplit("/", 1)[-1], "weight_dtype": self.unet_dtype}, "2": {"clip_name": self.text.rsplit("/", 1)[-1]},
                "3": {"vae_name": self.vae.rsplit("/", 1)[-1]}}

    def graph_classes(self) -> dict[str, str]:
        """Loader nodes this recipe swaps in (squeezed files need the add-on's loaders); empty when the graph's own loaders read the files."""
        return {"1": "UnetLoaderGGUF", "2": "CLIPLoaderGGUF"} if self.gguf else {}

    def addons(self) -> list[dict]:
        return [GGUF_ADDON] if self.gguf else []


PICTURES: list[Recipe] = [
    # quality = how faithfully it draws what the shot says (The Last Lamp bench, 2026-11-01: place, scale, close-ups, weather)
    Recipe("klein-4b", "FLUX.2 Klein 4B", 104, "diffusion_models/flux-2-klein-4b.safetensors", "default", 7.75,
           "text_encoders/qwen_3_4b_fp8_mixed.safetensors", 5.63, vae="vae/flux2-vae.safetensors", workflow="klein_t2i", seconds=9.2,
           note="follows directions best and fastest: 12 GB cards and up"),
    Recipe("klein-4b-fp8", "FLUX.2 Klein 4B, 8-bit", 102, "diffusion_models/flux-2-klein-4b.safetensors", "fp8_e4m3fn", 3.9,
           "text_encoders/qwen_3_4b_fp8_mixed.safetensors", 5.63, vae="vae/flux2-vae.safetensors", workflow="klein_t2i", seconds=8.7,
           note="8 and 10 GB cards"),
    Recipe("qwen21-turbo", "Qwen-Image 2.1 Turbo", 98, "diffusion_models/qwen_image_2.1_turbo_int8_convrot.safetensors", "default", 7.26,
           "text_encoders/qwen3vl_8b_w4a8.safetensors", 6.31, vae="vae/qwen_image_2.1_vae_bf16.safetensors", vae_card=0.68, workflow="qwen21_t2i",
           seconds=42.0, note="finest detail of real objects; about 5 times slower than Klein"),
    Recipe("zimage-full", "Z-Image Turbo, full precision", 97, "diffusion_models/z_image_turbo_bf16.safetensors", "default", 12.31,
           "text_encoders/qwen_3_4b.safetensors", 8.04, seconds=21.0, note="24 GB cards"),
    Recipe("zimage-fp8", "Z-Image Turbo, 8-bit", 95, "diffusion_models/z_image_turbo_bf16.safetensors", "fp8_e4m3fn", 6.16,
           "text_encoders/qwen_3_4b_fp8_mixed.safetensors", 5.63, note="half the memory, pictures nearly the same: 12 and 16 GB cards"),
    Recipe("zimage-fp8-small-text", "Z-Image Turbo, 8-bit, 4-bit text reader", 90, "diffusion_models/z_image_turbo_bf16.safetensors", "fp8_e4m3fn", 6.16,
           "text_encoders/qwen_3_4b_fp4_mixed.safetensors", 3.48, note="when the server has little RAM to park the text reader in"),
    Recipe("zimage-nvfp4", "Z-Image Turbo, 4-bit (Blackwell)", 88, "diffusion_models/z_image_turbo_nvfp4.safetensors", "default", 4.51,
           "text_encoders/qwen_3_4b_fp4_mixed.safetensors", 3.48, min_compute=10.0, note="RTX 50-series: 8 GB cards"),
    Recipe("klein-4b-q4", "FLUX.2 Klein 4B, small", 96, "diffusion_models/flux-2-klein-4b-Q4_K_M.gguf", "default", 2.6,
           "text_encoders/Qwen3-4B-Q4_K_M.gguf", 2.5, vae="vae/flux2-vae.safetensors", workflow="klein_t2i", gguf=True,
           note="the same model squeezed to 4 bits: 6 GB cards"),          # RTX 4050 Laptop 6 GB (2026-11-09): 16.5 s a picture warm, 33 s the first, 5.5 GB peak
    Recipe("klein-4b-q3", "FLUX.2 Klein 4B, smallest", 91, "diffusion_models/flux-2-klein-4b-Q3_K_M.gguf", "default", 2.12,
           "text_encoders/Qwen3-4B-Q3_K_M.gguf", 2.08, vae="vae/flux2-vae.safetensors", workflow="klein_t2i", gguf=True,
           note="3 bits, a little rougher: when another program holds part of a 6 GB card"),
]
BY_ID = {r.id: r for r in PICTURES}


@dataclass
class Card:
    """What we know about the card (and the computer) a ComfyUI runs on. Any field may be unknown (0)."""
    name: str = ""
    vram_gb: float = 0.0
    vram_free_gb: float = 0.0
    compute: float = 0.0
    ram_gb: float = 0.0
    ram_free_gb: float = 0.0

    @property
    def size(self) -> int:
        """The size on the box: cards are sold in GiB (a "16 GB" V100 reports 16.9e9 bytes)."""
        return round(self.vram_gb * GB / 2**30)


@dataclass
class Fit:
    recipe: Optional[str]
    mode: str = ""                                # resident | sequential | partial | "" (nothing fits)
    card_gb: float = 0.0
    ram_gb: float = 0.0
    why: str = ""
    warnings: list[str] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)

    def public(self) -> dict:
        return {"recipe": self.recipe, "label": BY_ID[self.recipe].label if self.recipe else "", "mode": self.mode, "card_gb": round(self.card_gb, 1),
                "ram_gb": round(self.ram_gb, 1), "why": self.why, "warnings": self.warnings, "options": self.options}


def usable(card: Card) -> float:
    return card.vram_gb * (1 - MARGIN)


def check(r: Recipe, card: Card) -> dict:
    """One recipe against one card: the best mode it runs in, or why it does not."""
    out = {"recipe": r.id, "label": r.label, "quality": r.quality, "resident_gb": round(r.resident(), 1), "sequential_gb": round(r.sequential(), 1), "mode": "", "why": ""}
    if r.min_compute and card.compute < r.min_compute:
        out["why"] = f"needs an RTX 50-series card (compute {r.min_compute:g}+); this one is {card.compute:g}" if card.compute else "needs an RTX 50-series card"
        return out
    room = usable(card)
    ram_room = card.ram_gb - RAM_FOR_SYSTEM if card.ram_gb else float("inf")
    runs = []
    for mode, need in (("resident", r.resident()), ("sequential", r.sequential()), ("partial", r.partial())):
        if need > room:
            continue
        if r.ram(mode) > ram_room:
            out["why"] = f"{mode} needs {r.ram(mode):.0f} GB of the server's RAM; it has {card.ram_gb:.0f} GB"
            continue
        runs.append((mode, need))
    if runs:                                                            # the fastest mode with room to spare, else the fastest that fits
        mode, need = next(((m, n) for m, n in runs if n <= card.vram_gb * COMFORT and m != "partial"), runs[0])
        out.update(mode=mode, card_gb=round(need, 1), ram_gb=r.ram(mode), why="")
        return out
    if not out["why"]:
        out["why"] = f"needs {r.sequential():.1f} GB on the card; {card.size} GB cards have {room:.1f} GB to give"
    return out


def choose(card: Card, allow_partial: bool = True) -> Fit:
    """The best picture recipe for this card. Quality first among the fast modes; partial only when nothing else fits."""
    if card.vram_gb <= 0:
        return Fit(None, why="no graphics card was found on this ComfyUI's computer; pictures need an NVIDIA card with 6 GB or more")
    options = [check(r, card) for r in PICTURES]
    fast = [o for o in options if o["mode"] in ("resident", "sequential")]
    slow = [o for o in options if o["mode"] == "partial"]
    pick = None
    roomy = [o for o in fast if o["card_gb"] <= card.vram_gb * COMFORT]          # estimates, not measurements: leave room for them to be wrong
    if fast:
        pool = roomy or fast
        best_q = max(o["quality"] for o in pool)
        top = [o for o in pool if o["quality"] == best_q]
        pick = next((o for o in top if o["mode"] == "resident"), top[0])
    elif slow and allow_partial:
        pick = max(slow, key=lambda o: o["quality"])
    if pick is None:
        near = next((o for o in reversed(options) if "RTX 50" not in o["why"]), options[-1])
        return Fit(None, why=f"no picture set fits a {card.size} GB card: {near['why']}", options=options)
    fit = Fit(pick["recipe"], pick["mode"], pick["card_gb"], pick["ram_gb"], options=options,
              why={"resident": f"everything stays on the {card.size} GB card ({pick['card_gb']} GB used)",
                   "sequential": f"the text reader and the picture model take turns on the {card.size} GB card ({pick['card_gb']} GB at most); about a second slower per picture",
                   "partial": f"the picture model does not fit the {card.size} GB card, so part of it streams from RAM: pictures take several times longer"}[pick["mode"]])
    if card.vram_free_gb and card.vram_free_gb + 0.5 < pick["card_gb"]:
        fit.warnings.append(f"only {card.vram_free_gb:.1f} GB of the card is free right now: another program is using it. Pictures wait or fail until it lets go.")
    if card.ram_free_gb and card.ram_free_gb < pick["ram_gb"]:
        fit.warnings.append(f"the server has {card.ram_free_gb:.0f} GB of RAM free and this needs about {pick['ram_gb']:.0f} GB: close other programs there, or it will swap.")
    return fit


# ----------------------------------------------------------------------------- the language model (Ollama)
# ----- the language models, MEASURED on the card (docs/plans/PLAN-LOCAL-AI-6GB.MD, 2026-11-21, RTX 4050 Laptop 6 GB, Ollama 0.40.16)
# card_gb: what the model takes on the card at a 32k context with our Ollama settings (llm.OLLAMA_TUNING: flash attention, 8-bit context cache),
#          as nvidia-smi showed after loading minus what was in use before (models not measured here are estimates, marked so).
# pictures: it can read a frame (the director's frame review sends one); a model without pictures cannot do that step.
# The order is the ranking, best first, decided by the same videos made with each (section 3.3 of the plan).
@dataclass(frozen=True)
class LanguageModel:
    name: str
    card_gb: float
    download_gb: float
    pictures: bool = True
    measured: bool = True
    note: str = ""


LANGUAGE_MODELS: list[LanguageModel] = [
    LanguageModel("gemma3:12b", 9.6, 8.1, measured=False, note="12 GB cards and up"),
    # 6 GB card, the same 4 videos each (plan 3.3): E2B made them in 140-208 s with the most sensible pictures; Gemma 3 4B took 250-533 s and picked
    # wrong meanings (a moon cake for "snooze"); E4B left the Bangla video nearly empty; Qwen 3.5 wrote numbers where text belongs and fell back.
    LanguageModel("gemma4:e2b", 2.79, 7.2),
    LanguageModel("gemma3:4b", 3.64, 3.3),
    LanguageModel("gemma4:e4b", 4.17, 9.6),
    LanguageModel("qwen3.5:4b", 3.93, 3.4),
    LanguageModel("gemma3:1b", 1.6, 0.8, pictures=False, measured=False, note="tiny cards and the processor"),
]
LANGUAGE = [(m.name, m.card_gb) for m in LANGUAGE_MODELS]                       # (name, GB on the card), the form setup.py reads
LANGUAGE_DOWNLOAD_GB = {m.name: m.download_gb for m in LANGUAGE_MODELS}
BY_NAME = {m.name: m for m in LANGUAGE_MODELS}
OTHER_PROGRAMS_GB = 1.5          # what Windows, the browser and our own windows kept on the card before the model loaded (measured: 1550 MiB)


def language_room(vram_gb: float) -> float:
    """What the language model may take of a card: the card less the safety margin and what other programs already hold."""
    return max(0.0, vram_gb * (1 - MARGIN) - OTHER_PROGRAMS_GB) if vram_gb else 0.0


def fits_card(name: str, vram_gb: float) -> bool:
    """A model we measured (or estimated) that stays whole on this card at a 32k context. An unknown model is not judged (False)."""
    m = BY_NAME.get(name)
    return bool(m and vram_gb and m.card_gb <= language_room(vram_gb))


def max_context(name: str, vram_gb: float) -> int:
    """The largest context worth asking this model for on this card: 64k only with 2 GB to spare (64k was not measured), else 32k (measured), else 16k."""
    m = BY_NAME.get(name)
    room = language_room(vram_gb)
    if not m or not vram_gb:
        return 32768
    if m.card_gb + 2.0 <= room:
        return 65536
    return 32768 if m.card_gb <= room else 16384


# Short clips (Wan 2.2: two 14B experts at 8 bits that take turns). ComfyUI streams what does not fit from RAM, but below these sizes it
# swaps or runs out of memory. Estimates from the model sizes, not a bench on every card.
CLIPS_CARD_GB = 12
CLIPS_RAM_GB = 32


def clips_fit(vram_gb: float, ram_gb: float) -> dict:
    """Whether this computer can make short video clips; if not, why, in plain words. vram_gb in GB (1e9), as Card.vram_gb."""
    size = round(vram_gb * GB / 2**30) if vram_gb else 0
    if size < CLIPS_CARD_GB:
        return {"fits": False, "why": f"Needs a graphics card with {CLIPS_CARD_GB} GB or more; " + (f"this one has {size} GB." if size else "none was found.")}
    if ram_gb and ram_gb < CLIPS_RAM_GB:
        return {"fits": False, "why": f"Needs {CLIPS_RAM_GB} GB of memory; this computer has {ram_gb:.0f} GB."}
    return {"fits": True, "why": ""}


def language_model(vram_gb: float, ram_gb: float = 0.0) -> dict:
    """The language model for this card. On one card it runs before the pictures and is unloaded after (llm.release), so it may use the whole card."""
    for name, need in LANGUAGE:
        if vram_gb and need <= language_room(vram_gb):
            return {"model": name, "card_gb": need, "where": "card", "max_context": max_context(name, vram_gb)}
    for name, need in LANGUAGE[1:]:                                   # no card, or a small one: on the processor, slowly
        if not ram_gb or need + RAM_FOR_SYSTEM <= ram_gb:
            return {"model": name, "card_gb": 0.0, "where": "processor", "note": "no card big enough: it runs on the processor, a few times slower"}
    return {"model": LANGUAGE[-1][0], "card_gb": 0.0, "where": "processor"}


def card_from_stats(stats: dict, device: int = 0, compute: float = 0.0) -> Card:
    """A Card from ComfyUI's /system_stats (vram in bytes)."""
    sysinfo = stats.get("system", {}) or {}
    devs = [d for d in stats.get("devices", []) or [] if str(d.get("type", "")).lower() == "cuda"]
    d = devs[device] if len(devs) > device else {}
    return Card(name=gpu_name(d.get("name", "")), vram_gb=round(float(d.get("vram_total", 0)) / GB, 1), vram_free_gb=round(float(d.get("vram_free", 0)) / GB, 1),
                compute=compute or compute_of(d.get("name", "")), ram_gb=round(float(sysinfo.get("ram_total", 0)) / GB, 1), ram_free_gb=round(float(sysinfo.get("ram_free", 0)) / GB, 1))


def gpu_name(raw: str) -> str:
    """'cuda:0 NVIDIA GeForce RTX 3060 : cudaMallocAsync' -> 'NVIDIA GeForce RTX 3060'."""
    s = raw.split(" : ")[0]
    return s.split(" ", 1)[1] if s.startswith("cuda:") and " " in s else s


def compute_of(name: str) -> float:
    """The compute capability from the card's name when nvidia-smi is not at hand (ComfyUI does not report it). 0 when unknown."""
    n = name.lower()
    table = [("rtx 50", 12.0), ("b200", 10.0), ("b100", 10.0), ("h100", 9.0), ("h200", 9.0), ("l40", 8.9), ("l4", 8.9), ("rtx 40", 8.9), ("ada", 8.9),
             ("rtx 30", 8.6), ("a40", 8.6), ("a10", 8.6), ("a6000", 8.6), ("a5000", 8.6), ("a4000", 8.6), ("a2000", 8.6), ("a100", 8.0), ("a30", 8.0),
             ("rtx 20", 7.5), ("gtx 16", 7.5), ("t4", 7.5), ("quadro rtx", 7.5), ("titan v", 7.0), ("v100", 7.0), ("gtx 10", 6.1), ("p100", 6.0), ("p40", 6.1)]
    for key, cc in table:
        if key in n:
            return cc
    return 0.0

# ----- the voices, MEASURED on one laptop (RTX 4050 Laptop 6 GB, 2026-11-22): seconds of work for one second of speech, after the first load.
# Kokoro runs on the processor and is quick enough for a one-minute video; the cloning voice is not (it needs the speaker's own audio and a stronger machine).
VOICE_SPEED = {
    "kokoro": {"seconds_per_second": 1.5, "first_load_s": 20, "device": "processor (int8)", "note": "7.4 s for 4.8 s of English"},
    "chatterbox-turbo": {"seconds_per_second": 17.0, "first_load_s": 15, "device": "ONNX, processor or card (the same either way here)", "note": "56 s for 3.2 s of speech; use only for short lines or on a stronger machine"},
}
