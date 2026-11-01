"""More hand-built clipart: technology, nature, economics. Same frame and style as concepts.py (square 128 x 128, flat colour)."""
from __future__ import annotations

import math

from .concepts import V, _space_disc


def neural_network() -> str:
    xs, ys = (18, 64, 110), ((30, 64, 98), (22, 48, 80, 106), (46, 82))
    lines, dots = [], []
    for i in range(2):
        for a in ys[i]:
            for b in ys[i + 1]:
                lines.append(f'<line x1="{xs[i]}" y1="{a}" x2="{xs[i + 1]}" y2="{b}" stroke="#a5b4fc" stroke-width="2"/>')
    for i, col in enumerate(("#38bdf8", "#a78bfa", "#f472b6")):
        for y in ys[i]:
            dots.append(f'<circle cx="{xs[i]}" cy="{y}" r="9" fill="{col}"/><circle cx="{xs[i] - 2.5}" cy="{y - 2.5}" r="3" fill="#fff" opacity=".5"/>')
    return f'<svg {V}>' + "".join(lines) + "".join(dots) + "</svg>"


def network() -> str:
    pts = [(64, 62, 14, "#6366f1"), (22, 28, 9, "#22c55e"), (106, 30, 9, "#f59e0b"), (24, 100, 9, "#ec4899"), (104, 98, 9, "#06b6d4"), (64, 14, 7, "#94a3b8"), (64, 114, 7, "#94a3b8")]
    lines = "".join(f'<line x1="64" y1="62" x2="{x}" y2="{y}" stroke="#cbd5e1" stroke-width="3.5"/>' for x, y, _, _ in pts[1:])
    lines += '<line x1="22" y1="28" x2="24" y2="100" stroke="#cbd5e1" stroke-width="3"/><line x1="106" y1="30" x2="104" y2="98" stroke="#cbd5e1" stroke-width="3"/>'
    return f'<svg {V}>{lines}' + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x, y, r, c in pts) + "</svg>"


def water_cycle() -> str:
    return (f'<svg {V}><path d="M6 100q20-12 40 0t40 0 36 0v22H6z" fill="#38bdf8"/><path d="M6 108q20-10 40 0t40 0 36 0" fill="none" stroke="#bae6fd" stroke-width="3"/>'
            '<circle cx="104" cy="22" r="13" fill="#fbbf24"/><path d="M26 66a14 14 0 0 1 4-27 18 18 0 0 1 34-3 15 15 0 0 1 8 30z" fill="#e2e8f0"/>'
            '<path d="M34 90V74M30 80l4-6 4 6" stroke="#0ea5e9" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M54 74v14M50 84l4 6 4-6" stroke="#0ea5e9" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M86 94V60M80 68l6-8 6 8" stroke="#f97316" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1 7"/></svg>')


def photosynthesis() -> str:
    rays = "".join(f'<path d="M100 24L{100 - 40 * math.cos(math.radians(a)):.0f} {24 + 40 * math.sin(math.radians(a)):.0f}" stroke="#fde68a" stroke-width="3" stroke-linecap="round" stroke-dasharray="2 8"/>' for a in (20, 45, 70))
    return (f'<svg {V}><circle cx="100" cy="24" r="15" fill="#fbbf24"/>{rays}'
            '<path d="M60 118V70" stroke="#16a34a" stroke-width="6" stroke-linecap="round"/><path d="M60 82C30 82 26 56 38 44c22 0 30 16 22 38zM60 96c24 0 40-14 38-36-22-2-40 10-38 36z" fill="#22c55e"/>'
            '<path d="M60 82c-6-12-10-20-18-34M60 96c10-12 20-22 32-30" stroke="#15803d" stroke-width="2.5" fill="none"/><rect x="26" y="112" width="68" height="8" rx="4" fill="#92400e"/></svg>')


def greenhouse() -> str:
    return (f'<svg {V}>' + _space_disc("#1e3a8a", "#0b1230") + '<path d="M4 98Q64 84 124 98v24H4z" fill="#22c55e"/><path d="M4 74Q64 58 124 74" fill="none" stroke="#fca5a5" stroke-width="7" opacity=".8"/>'
            '<path d="M34 22v44M30 32l4-8 4 8M64 18v40M60 28l4-8 4 8M94 22v44M90 32l4-8 4 8" stroke="#fde047" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M44 90l-8-14M64 94V78M84 90l8-14" stroke="#fb923c" stroke-width="4" stroke-linecap="round"/></svg>')


def circuit() -> str:
    return (f'<svg {V}><path d="M22 36h84v64H22z" fill="none" stroke="#475569" stroke-width="5" stroke-linejoin="round"/><rect x="50" y="26" width="28" height="20" fill="#fff"/><path d="M52 40h24M52 32h24" stroke="#ef4444" stroke-width="5"/>'
            '<rect x="12" y="62" width="20" height="14" fill="#fff"/><path d="M16 66h12M16 72h12" stroke="#22c55e" stroke-width="4"/><circle cx="96" cy="68" r="11" fill="#fde047" stroke="#f59e0b" stroke-width="3"/>'
            '<path d="M91 74l5-12 5 12" fill="none" stroke="#f59e0b" stroke-width="2.4"/><rect x="50" y="92" width="28" height="16" rx="3" fill="#cbd5e1" stroke="#475569" stroke-width="3"/></svg>')


def supply_demand() -> str:
    return (f'<svg {V}><path d="M20 12v100h100" stroke="#475569" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M32 30L104 96" stroke="#ef4444" stroke-width="7" stroke-linecap="round"/><path d="M32 96L104 30" stroke="#3b82f6" stroke-width="7" stroke-linecap="round"/>'
            '<circle cx="68" cy="63" r="9" fill="#fde047" stroke="#f59e0b" stroke-width="3"/></svg>')


def inflation() -> str:
    coins = "".join(f'<ellipse cx="{x}" cy="{y}" rx="16" ry="7" fill="#fbbf24" stroke="#d97706" stroke-width="2.4"/>' for x, y in ((30, 104), (30, 96), (30, 88)))
    return (f'<svg {V}>{coins}'
            '<path d="M58 100L82 70l16 16 20-34" fill="none" stroke="#ef4444" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><path d="M100 50h18v18" fill="none" stroke="#ef4444" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'
            '<circle cx="70" cy="26" r="16" fill="#fff" stroke="#ef4444" stroke-width="4"/><text x="70" y="33" font-size="22" font-weight="800" text-anchor="middle" fill="#ef4444" font-family="sans-serif">$</text></svg>')


def compound_growth() -> str:
    bars = "".join(f'<rect x="{14 + i * 18}" y="{110 - h}" width="14" height="{h}" rx="3" fill="{c}"/>' for i, (h, c) in enumerate(((10, "#86efac"), (16, "#6ee7b7"), (26, "#34d399"), (42, "#10b981"), (66, "#059669"), (96, "#047857"))))
    return f'<svg {V}>{bars}<path d="M14 92Q60 86 116 22" fill="none" stroke="#f59e0b" stroke-width="4" stroke-dasharray="1 8" stroke-linecap="round"/></svg>'


def food_chain() -> str:
    def arrow(x: int) -> str:
        return f'<path d="M{x} 64h12M{x + 8} 58l6 6-6 6" stroke="#64748b" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    return (f'<svg {V}><circle cx="20" cy="60" r="13" fill="#4ade80"/><path d="M20 74v18" stroke="#16a34a" stroke-width="4"/>' + arrow(38) +
            '<ellipse cx="66" cy="68" rx="13" ry="10" fill="#fbbf24"/><circle cx="75" cy="60" r="6" fill="#fbbf24"/><path d="M80 58l7 2-7 3z" fill="#f97316"/>' + arrow(86) +
            '<path d="M106 84q-8-22 6-30 12 8 8 30z" fill="#a16207"/><circle cx="112" cy="50" r="7" fill="#a16207"/></svg>')


def tectonic() -> str:
    return (f'<svg {V}><path d="M4 66L62 56 58 124H4z" fill="#a16207"/><path d="M124 56L68 62 72 124h52z" fill="#b45309"/><path d="M4 66L62 56" stroke="#4ade80" stroke-width="8" stroke-linecap="round"/><path d="M124 56L68 62" stroke="#4ade80" stroke-width="8" stroke-linecap="round"/>'
            '<path d="M65 70l-5 18 8 6-6 22" stroke="#ef4444" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M30 40l14 12M98 40L84 52" stroke="#64748b" stroke-width="4" stroke-linecap="round"/></svg>')


def big_bang() -> str:
    rays = "".join(f'<path d="M64 64L{64 + 56 * math.cos(math.radians(a)):.1f} {64 + 56 * math.sin(math.radians(a)):.1f}" stroke="#f9a8d4" stroke-width="2.4" opacity=".8"/>' for a in range(0, 360, 20))
    dots = "".join(f'<circle cx="{64 + r * math.cos(math.radians(a)):.1f}" cy="{64 + r * math.sin(math.radians(a)):.1f}" r="{3.5 - r / 30:.1f}" fill="#fff"/>' for r in (26, 38, 50) for a in range(10, 360, 40 + int(r)))
    return f'<svg {V}>' + _space_disc("#3b1d6e", "#080616") + rays + dots + '<circle cx="64" cy="64" r="20" fill="#fde68a"/><circle cx="64" cy="64" r="12" fill="#fff"/></svg>'


def evolution() -> str:
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x, y, r, c in ((18, 104, 8, "#86efac"), (44, 76, 10, "#4ade80"), (60, 52, 12, "#22c55e"), (88, 32, 14, "#16a34a"), (108, 22, 8, "#15803d")))
    return f'<svg {V}><path d="M14 112c12-30 30-30 40-52 8-18 22-26 34-30" fill="none" stroke="#a16207" stroke-width="6" stroke-linecap="round"/>{dots}</svg>'


KEYS = {
    "art-neural-network": ("neural network", neural_network), "art-network": ("network", network), "art-water-cycle": ("water cycle", water_cycle),
    "art-photosynthesis": ("photosynthesis", photosynthesis), "art-greenhouse": ("greenhouse effect", greenhouse), "art-circuit": ("circuit", circuit),
    "art-supply-demand": ("supply and demand", supply_demand), "art-inflation": ("inflation", inflation), "art-compound-growth": ("compound growth", compound_growth),
    "art-food-chain": ("food chain", food_chain), "art-tectonic": ("tectonic plates", tectonic), "art-big-bang": ("big bang", big_bang), "art-evolution": ("evolution", evolution),
}

_WORDS = {
    "art-neural-network": "neural-network neural-networks deep-learning machine-learning ai artificial-intelligence algorithm algorithms",
    "art-network": "network networks internet networking connectivity", "art-water-cycle": "water-cycle evaporation condensation precipitation hydrological vapor vapour steam",
    "art-photosynthesis": "photosynthesis chlorophyll", "art-greenhouse": "greenhouse greenhouse-effect global-warming climate-change",
    "art-circuit": "circuit circuits electronics electronic electricity", "art-supply-demand": "supply-and-demand demand supply",
    "art-inflation": "inflation inflationary", "art-compound-growth": "compound-interest compounding compound-growth exponential",
    "art-food-chain": "food-chain food-web ecosystem predator", "art-tectonic": "tectonic tectonics fault-line", "art-big-bang": "big-bang",
    "art-evolution": "evolution evolve evolutionary natural-selection",
}
WORDS = {w: k for k, ws in _WORDS.items() for w in ws.split()}
WORDS.update({"জলচক্র": "art-water-cycle", "পানিচক্র": "art-water-cycle", "বাষ্পীভবন": "art-water-cycle", "বাষ্প": "art-water-cycle", "ঘনীভবন": "art-water-cycle", "মুদ্রাস্ফীতি": "art-inflation", "ইন্টারনেট": "art-network", "নেটওয়ার্ক": "art-network", "সালোকসংশ্লেষণ": "art-photosynthesis", "বিবর্তন": "art-evolution",
              "বিগ ব্যাং": "art-big-bang", "বৈদ্যুতিক": "art-circuit"})
