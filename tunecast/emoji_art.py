"""TuneCast animated emoji, drawn in code as Lottie (TGS).

Telegram requirements: 512×512 canvas, 60 fps, up to 3 seconds, looped,
no masks, expressions, texts or images. Each icon is a function that
returns a list of layers.
"""

import gzip
import json
import math

FPS = 60
FRAMES = 180  # 3 seconds
C = 256  # canvas center

WHITE = [1, 1, 1, 1]
GREEN = [0.118, 0.843, 0.376, 1]
DARK = [0.08, 0.08, 0.08, 1]
GREY = [0.32, 0.32, 0.32, 1]
RED = [1, 0.36, 0.42, 1]


# ---------- Lottie primitives ----------


def _static(value):
    return {"a": 0, "k": value}


def _ease(dims: int):
    return {"i": {"x": [0.42] * dims, "y": [1] * dims}, "o": {"x": [0.58] * dims, "y": [0] * dims}}


def anim(*keys):
    """anim((frame, value), ...) — eased property animation."""
    frames = []
    for n, (t, value) in enumerate(keys):
        value = value if isinstance(value, list) else [value]
        frame = {"t": t, "s": value}
        if n < len(keys) - 1:
            frame.update(_ease(len(value)))
        frames.append(frame)
    return {"a": 1, "k": frames}


def linear(*keys):
    frames = []
    for n, (t, value) in enumerate(keys):
        value = value if isinstance(value, list) else [value]
        frame = {"t": t, "s": value}
        if n < len(keys) - 1:
            frame.update({"i": {"x": [1] * len(value), "y": [1] * len(value)}, "o": {"x": [0] * len(value), "y": [0] * len(value)}})
        frames.append(frame)
    return {"a": 1, "k": frames}


def _prop(value):
    if isinstance(value, dict):
        return value
    return _static(value)


def transform(p=(0, 0), a=(0, 0), s=(100, 100), r=0, o=100):
    return {
        "ty": "tr",
        "p": _prop(list(p) if not isinstance(p, dict) else p),
        "a": _prop(list(a)),
        "s": _prop(list(s) if not isinstance(s, dict) else s),
        "r": _prop(r),
        "o": _prop(o),
        "sk": _static(0),
        "sa": _static(0),
    }


def _bottom_up(items):
    # In Lottie the first item is drawn on top; icons are written bottom-up and reversed here
    if items and all(item.get("ty") == "gr" for item in items):
        return list(reversed(items))
    return list(items)


def group(*items, **tr):
    return {"ty": "gr", "it": [*_bottom_up(items), transform(**tr)], "nm": "g"}


def rect(w, h, x=C, y=C, radius=0, size=None, pos=None):
    return {
        "ty": "rc",
        "d": 1,
        "s": size or _static([w, h]),
        "p": pos or _static([x, y]),
        "r": _static(radius),
    }


def ellipse(w, h, x=C, y=C, size=None):
    return {"ty": "el", "d": 1, "s": size or _static([w, h]), "p": _static([x, y])}


def path(points, closed=True, ins=None, outs=None):
    n = len(points)
    return {
        "ty": "sh",
        "d": 1,
        "ks": _static(
            {
                "v": [list(p) for p in points],
                "i": [list(p) for p in (ins or [(0, 0)] * n)],
                "o": [list(p) for p in (outs or [(0, 0)] * n)],
                "c": closed,
            }
        ),
    }


def arc(cx, cy, radius, a0, a1):
    """Circular arc as Bezier curves (degrees, 0 = right, clockwise)."""
    steps = max(1, math.ceil(abs(a1 - a0) / 90))
    angles = [math.radians(a0 + (a1 - a0) * i / steps) for i in range(steps + 1)]
    delta = (angles[1] - angles[0]) if steps else 0
    k = 4 / 3 * math.tan(delta / 4) * radius
    pts, ins, outs = [], [], []
    for ang in angles:
        x, y = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
        tx, ty = -math.sin(ang) * k, math.cos(ang) * k
        pts.append((x, y))
        ins.append((-tx, -ty))
        outs.append((tx, ty))
    ins[0] = (0, 0)
    outs[-1] = (0, 0)
    return path(pts, closed=False, ins=ins, outs=outs)


def fill(color, opacity=100):
    return {"ty": "fl", "c": _static(color), "o": _prop(opacity), "r": 1}


def stroke(color, width, opacity=100):
    return {"ty": "st", "c": _static(color), "o": _prop(opacity), "w": _static(width), "lc": 2, "lj": 2}


def layer(*shapes, index=1, **tr):
    t = transform(**tr)
    ks = {key: t[key] for key in ("p", "a", "s", "r", "o")}
    for key in ("p", "a", "s"):
        prop = ks[key]
        if prop["a"] == 0:
            prop["k"] = list(prop["k"]) + [0] if len(prop["k"]) == 2 else prop["k"]
    return {
        "ddd": 0,
        "ind": index,
        "ty": 4,
        "nm": f"l{index}",
        "sr": 1,
        "ks": ks,
        "ao": 0,
        "shapes": _bottom_up(shapes),
        "ip": 0,
        "op": FRAMES,
        "st": 0,
        "bm": 0,
    }


# ---------- alignment: real artwork bounds ----------


def _at0(prop):
    """Property value at the first frame."""
    return prop["k"] if prop["a"] == 0 else prop["k"][0]["s"]


def _cubic(p0, c1, c2, p1, steps=12):
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        yield (
            mt**3 * p0[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * p1[0],
            mt**3 * p0[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * p1[1],
        )


def _shape_points(item):
    ty = item["ty"]
    if ty in ("rc", "el"):
        (w, h), (x, y) = _at0(item["s"]), _at0(item["p"])
        return [(x - w / 2, y - h / 2), (x + w / 2, y + h / 2)]
    if ty == "sh":
        k = _at0(item["ks"])
        v, i_, o_ = k["v"], k["i"], k["o"]
        n = len(v)
        pts = []
        segments = n if k["c"] else n - 1
        for s in range(segments):
            a, b = v[s], v[(s + 1) % n]
            c1 = (a[0] + o_[s][0], a[1] + o_[s][1])
            c2 = (b[0] + i_[(s + 1) % n][0], b[1] + i_[(s + 1) % n][1])
            pts.extend(_cubic(a, c1, c2, b))
        return pts or [tuple(p) for p in v]
    return []


def _apply(tr, pts):
    px, py = _at0(tr["p"])[:2]
    ax, ay = _at0(tr["a"])[:2]
    sx, sy = (v / 100 for v in _at0(tr["s"])[:2])
    r = math.radians(_at0(tr["r"]) if not isinstance(_at0(tr["r"]), list) else _at0(tr["r"])[0])
    cos, sin = math.cos(r), math.sin(r)
    out = []
    for x, y in pts:
        x, y = (x - ax) * sx, (y - ay) * sy
        out.append((x * cos - y * sin + px, x * sin + y * cos + py))
    return out


def _items_points(items):
    pad = max((_at0(it["w"]) / 2 for it in items if it["ty"] == "st"), default=0)
    pts = []
    for it in items:
        if it["ty"] == "gr":
            tr = next(x for x in it["it"] if x["ty"] == "tr")
            pts.extend(_apply(tr, _items_points([x for x in it["it"] if x["ty"] != "tr"])))
        else:
            for x, y in _shape_points(it):
                pts.extend([(x - pad, y - pad), (x + pad, y + pad)])
    return pts


def bounds(layers):
    pts = []
    for lay in layers:
        pts.extend(_apply(lay["ks"], _items_points(lay["shapes"])))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def fit(layers, size: float, nudge=(0, 0)):
    """Move and scale the artwork: bounds center to canvas center, larger side to size."""
    x0, y0, x1, y1 = bounds(layers)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    k = size / max(x1 - x0, y1 - y0)
    for lay in layers:
        # All TuneCast layers are static at layer level, so the transform can be replaced
        lay["ks"]["a"] = _static([cx, cy, 0])
        lay["ks"]["p"] = _static([C + nudge[0], C + nudge[1], 0])
        lay["ks"]["s"] = _static([k * 100, k * 100, 100])
    return layers


ICON_SIZE = 330  # of 512: leaves room for the animations to breathe
ART_SIZE = 380
# Vertical artwork offset. Not needed for the official Telegram apps.
# (Unigram draws custom emoji below center; -40 helped there.)
LIFT = 0
NUDGE = {"play": (10, 0)}  # a triangle looks centered when shifted slightly right
SIZE = {"live": 150}  # the expanding ring needs room at the edges


def document(name: str, layers: list, size: float = ICON_SIZE) -> dict:
    dx, dy = NUDGE.get(name, (0, 0))
    layers = fit(list(reversed(layers)), SIZE.get(name, size), (dx, dy + LIFT))
    for i, lay in enumerate(layers, 1):
        lay["ind"] = i
    return {
        "v": "5.7.4",
        "fr": FPS,
        "ip": 0,
        "op": FRAMES,
        "w": 512,
        "h": 512,
        "nm": name,
        "ddd": 0,
        "assets": [],
        "layers": layers,
        "tgs": 1,
    }


def tgs(doc: dict) -> bytes:
    raw = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()
    return gzip.compress(raw, compresslevel=9, mtime=0)


def pulse(peak=112, at=0, length=80):
    """A soft scale breath, then a pause until the loop ends."""
    half = length // 2
    return anim((at, [100, 100]), (at + half, [peak, peak]), (at + length, [100, 100]), (FRAMES, [100, 100]))


def solid(color, outline=36):
    """Fill + stroke of the same color: gives rounded corners."""
    return [fill(color), stroke(color, outline)]


# ---------- icons (white, repainted to the text color) ----------


def icon_play(color=WHITE):
    tri = path([(196, 140), (384, 256), (196, 372)])
    return [layer(group(tri, *solid(color), p=(C, C), a=(C, C), s=pulse(114)))]


def icon_pause(color=WHITE):
    bars = []
    for i, x in enumerate((196, 316)):
        start = i * 30
        scale = anim((start, [100, 100]), (start + 30, [100, 78]), (start + 60, [100, 100]), (FRAMES, [100, 100]))
        bars.append(group(rect(70, 250, x, C, radius=28), fill(color), p=(x, C), a=(x, C), s=scale))
    return [layer(*bars)]


def _skip(direction: int, color):
    # direction 1 = forward, -1 = back
    def fx(x):
        return C + (x - C) * direction

    tri = path([(fx(150), 150), (fx(310), 256), (fx(150), 362)])
    bar = rect(52, 230, fx(362), C, radius=24)
    shift = anim((0, [C, C]), (30, [C + 22 * direction, C]), (60, [C, C]), (FRAMES, [C, C]))
    return [layer(group(tri, *solid(color), p=shift, a=(C, C)), group(bar, fill(color)))]


def icon_next(color=WHITE):
    return _skip(1, color)


def icon_prev(color=WHITE):
    return _skip(-1, color)


def _arrow_head(x, y, direction, size=44):
    return path([(x - size * direction, y - size), (x + size * 0.35 * direction, y), (x - size * direction, y + size)])


def icon_shuffle(color=WHITE):
    a = path([(110, 172), (182, 172), (322, 340), (378, 340)], closed=False,
             ins=[(0, 0), (-40, 0), (-50, 0), (0, 0)], outs=[(40, 0), (50, 0), (0, 0), (0, 0)])
    b = path([(110, 340), (182, 340), (322, 172), (378, 172)], closed=False,
             ins=[(0, 0), (-40, 0), (-50, 0), (0, 0)], outs=[(40, 0), (50, 0), (0, 0), (0, 0)])
    nudge = anim((0, [0, 0]), (35, [14, 0]), (70, [0, 0]), (FRAMES, [0, 0]))
    heads = group(
        group(_arrow_head(400, 172, 1, 40), *solid(color, 24)),
        group(_arrow_head(400, 340, 1, 40), *solid(color, 24)),
        p=nudge,
    )
    return [layer(group(a, stroke(color, 38)), group(b, stroke(color, 38)), heads)]


def _repeat_arrows(color):
    top = path([(150, 300), (150, 230), (205, 175), (360, 175)], closed=False,
               ins=[(0, 0), (0, 0), (-30, 0), (0, 0)], outs=[(0, 0), (0, -30), (0, 0), (0, 0)])
    bottom = path([(362, 212), (362, 282), (307, 337), (152, 337)], closed=False,
                  ins=[(0, 0), (0, 0), (30, 0), (0, 0)], outs=[(0, 0), (0, 30), (0, 0), (0, 0)])
    return [
        group(top, stroke(color, 38)),
        group(bottom, stroke(color, 38)),
        group(_arrow_head(392, 175, 1, 40), *solid(color, 22)),
        group(_arrow_head(120, 337, -1, 40), *solid(color, 22)),
    ]


def icon_repeat(color=WHITE):
    spin = anim((0, 0), (70, 180), (FRAMES, 180))
    return [layer(group(*_repeat_arrows(color), p=(C, C), a=(C, C), r=spin))]


def icon_repeat_one(color=WHITE):
    spin = anim((0, 0), (70, 180), (FRAMES, 180))
    one = path([(236, 232), (262, 214), (262, 300)], closed=False)
    return [
        layer(group(*_repeat_arrows(color), p=(C, C), a=(C, C), r=spin)),
        layer(group(one, stroke(color, 30))),
    ]


def _speaker(color):
    body = path([(118, 212), (178, 212), (252, 146), (252, 366), (178, 300), (118, 300)])
    return group(body, *solid(color, 30))


def _wave(radius, opacity, color):
    return group(arc(258, C, radius, -48, 48), stroke(color, 34, opacity))


def icon_vol_down(color=WHITE):
    op = anim((0, 100), (45, 25), (90, 100), (FRAMES, 100))
    return [layer(_speaker(color), _wave(78, op, color))]


def icon_vol_up(color=WHITE):
    op1 = anim((0, 100), (40, 30), (80, 100), (FRAMES, 100))
    op2 = anim((0, 100), (20, 100), (60, 30), (100, 100), (FRAMES, 100))
    return [layer(_speaker(color), _wave(78, op1, color), _wave(142, op2, color))]


def icon_queue(color=WHITE):
    rows = []
    for i, y in enumerate((170, 256, 342)):
        t = i * 12
        slide = anim((t, [0, 0]), (t + 25, [16, 0]), (t + 50, [0, 0]), (FRAMES, [0, 0]))
        rows.append(group(rect(200, 42, 300, y, radius=21), fill(color), p=slide))
    dot = group(path([(118, 138), (178, 170), (118, 202)]), *solid(color, 20), p=(148, 170), a=(148, 170), s=pulse(125, 0, 60))
    dots = [group(ellipse(40, 40, 140, y), fill(color)) for y in (256, 342)]
    return [layer(*rows, dot, *dots)]


def icon_library(color=WHITE):
    books = [group(rect(48, 270, x, C, radius=20), fill(color)) for x in (140, 218)]
    tilt = anim((0, -22), (45, -8), (90, -22), (FRAMES, -22))
    slant = group(rect(48, 270, 330, C, radius=20), fill(color), p=(330, 390), a=(330, 390), r=tilt)
    return [layer(*books, slant)]


def icon_devices(color=WHITE):
    laptop = group(rect(230, 160, 210, 220, radius=18), stroke(color, 30))
    base = group(path([(80, 340), (340, 340)], closed=False), stroke(color, 34))
    bob = anim((0, [0, 0]), (45, [0, -14]), (90, [0, 0]), (FRAMES, [0, 0]))
    phone = group(rect(100, 180, 384, 300, radius=20), fill(color), p=bob)
    return [layer(laptop, base, phone)]


def _head_at(angle_deg, radius, size=46, color=WHITE):
    """Arrowhead at the end of an arc, pointing along it."""
    a = math.radians(angle_deg)
    x, y = C + radius * math.cos(a), C + radius * math.sin(a)
    dx, dy = -math.sin(a), math.cos(a)
    nx, ny = -dy, dx
    tip = (x + dx * size, y + dy * size)
    b1 = (x + nx * size - dx * 6, y + ny * size - dy * 6)
    b2 = (x - nx * size - dx * 6, y - ny * size - dy * 6)
    return group(path([tip, b1, b2]), *solid(color, 18))


def icon_refresh(color=WHITE):
    ring = group(arc(C, C, 120, 20, 290), stroke(color, 38))
    head = _head_at(290, 120, color=color)
    spin = anim((0, 0), (90, 360), (FRAMES, 360))
    return [layer(group(ring, head, p=(C, C), a=(C, C), r=spin))]


def icon_search(color=WHITE):
    lens = group(ellipse(200, 200, 226, 226), stroke(color, 40))
    handle = group(path([(304, 304), (392, 392)], closed=False), stroke(color, 48))
    wobble = anim((0, 0), (25, -12), (50, 10), (75, 0), (FRAMES, 0))
    return [layer(group(lens, handle, p=(C, C), a=(C, C), r=wobble))]


def icon_plus(color=WHITE):
    spin = anim((0, 0), (50, 90), (FRAMES, 90))
    cross = [group(rect(54, 280, radius=27), fill(color)), group(rect(280, 54, radius=27), fill(color))]
    return [layer(group(*cross, p=(C, C), a=(C, C), r=spin))]


def icon_close(color=WHITE):
    cross = [group(rect(54, 300, radius=27), fill(color)), group(rect(300, 54, radius=27), fill(color))]
    return [layer(group(*cross, p=(C, C), a=(C, C), r=45, s=pulse(110, 0, 60)))]


def icon_back(color=WHITE):
    shape = group(path([(240, 150), (140, 256), (240, 362)], closed=False), stroke(color, 46))
    line = group(path([(150, 256), (380, 256)], closed=False), stroke(color, 46))
    shift = anim((0, [0, 0]), (30, [-22, 0]), (60, [0, 0]), (FRAMES, [0, 0]))
    return [layer(group(shape, line, p=shift))]


def icon_computer(color=WHITE):
    screen = group(rect(320, 210, C, 220, radius=22), stroke(color, 30))
    glow = group(rect(250, 140, C, 220, radius=10), fill(color, anim((0, 18), (60, 45), (120, 18), (FRAMES, 18))))
    stand = group(path([(196, 392), (316, 392)], closed=False), stroke(color, 34))
    neck = group(path([(C, 326), (C, 388)], closed=False), stroke(color, 30))
    return [layer(glow, screen, neck, stand)]


def icon_phone(color=WHITE):
    body = group(rect(190, 330, radius=36), stroke(color, 30))
    dot = group(ellipse(30, 30, C, 378), fill(color))
    glow = group(rect(130, 220, C, 236, radius=12), fill(color, anim((0, 18), (60, 45), (120, 18), (FRAMES, 18))))
    return [layer(glow, body, dot)]


def icon_speaker(color=WHITE):
    body = group(rect(230, 330, radius=36), stroke(color, 30))
    tweeter = group(ellipse(44, 44, C, 172), fill(color))
    woofer = group(ellipse(120, 120, C, 300), stroke(color, 26), p=(C, 300), a=(C, 300),
                   s=anim((0, [100, 100]), (15, [112, 112]), (30, [100, 100]), (45, [112, 112]), (60, [100, 100]), (FRAMES, [100, 100])))
    return [layer(body, tweeter, woofer)]


def icon_music(color=WHITE):
    stem = group(path([(300, 120), (300, 330)], closed=False), stroke(color, 36))
    flag = group(path([(300, 120), (390, 160), (390, 220), (300, 186)]), *solid(color, 16))
    head = group(ellipse(140, 110, 244, 340), fill(color))
    bob = anim((0, -6), (45, 6), (90, -6), (135, 6), (FRAMES, -6))
    return [layer(group(stem, flag, head, p=(C, C), a=(C, C), r=bob))]


def icon_heart_outline(color=WHITE):
    return [layer(group(_heart_path(), stroke(color, 34), p=(C, C), a=(C, C), s=pulse(112, 0, 50)))]


def icon_disc(color=WHITE):
    outer = group(ellipse(330, 330), stroke(color, 30))
    label = group(ellipse(110, 110), stroke(color, 26))
    shine = group(arc(C, C, 120, 200, 250), stroke(color, 22))
    spin = linear((0, 0), (FRAMES, 360))
    return [layer(group(outer, label, shine, p=(C, C), a=(C, C), r=spin))]


def icon_clock(color=WHITE):
    face = group(ellipse(320, 320), stroke(color, 32))
    hand_m = group(path([(C, C), (C, 140)], closed=False), stroke(color, 30), p=(C, C), a=(C, C), r=linear((0, 0), (FRAMES, 360)))
    hand_h = group(path([(C, C), (330, C)], closed=False), stroke(color, 30))
    return [layer(face, hand_h, hand_m)]


# ---------- accents (colored, not repainted) ----------


def art_equalizer():
    bars = []
    phases = [(120, 300, 170, 260), (260, 140, 300, 180), (180, 280, 120, 300), (300, 200, 260, 130)]
    for i, heights in enumerate(phases):
        x = 128 + i * 85
        seq = list(heights) + [heights[0]]
        times = [int(FRAMES * k / 4) for k in range(5)]
        size = anim(*[(t, [62, h]) for t, h in zip(times, seq)])
        pos = anim(*[(t, [x, 410 - h / 2]) for t, h in zip(times, seq)])
        bars.append(group(rect(62, 0, radius=26, size=size, pos=pos), fill(GREEN)))
    return [layer(*bars)]


def art_equalizer_paused():
    heights = (110, 170, 90, 140)
    bars = [group(rect(62, h, 128 + i * 85, 410 - h / 2, radius=26), fill(GREY)) for i, h in enumerate(heights)]
    return [layer(*bars)]


def art_vinyl():
    disc = group(ellipse(400, 400), fill(DARK))
    grooves = [group(ellipse(d, d), stroke([1, 1, 1, 1], 4, 14)) for d in (330, 270, 210)]
    shine = group(arc(C, C, 165, 200, 245), stroke([1, 1, 1, 1], 16, 40))
    shine2 = group(arc(C, C, 165, 20, 65), stroke([1, 1, 1, 1], 16, 40))
    label = group(ellipse(140, 140), fill(GREEN))
    dot = group(ellipse(34, 34, C + 34, C - 20), fill([1, 1, 1, 1], 60))
    hole = group(ellipse(24, 24), fill(DARK))
    spin = linear((0, 0), (FRAMES, 360))
    return [layer(group(disc, *grooves, shine, shine2, label, dot, hole, p=(C, C), a=(C, C), r=spin))]


def _heart_path():
    return path(
        [(C, 410), (96, 236), (176, 118), (C, 170), (336, 118), (416, 236)],
        ins=[(70, -60), (0, 60), (-50, 0), (-12, -46), (-50, 0), (0, -60)],
        outs=[(-70, -60), (0, -60), (50, 0), (12, -46), (50, 0), (0, 60)],
    )


def art_heart():
    beat = anim((0, [100, 100]), (12, [118, 118]), (24, [100, 100]), (36, [112, 112]), (52, [100, 100]), (FRAMES, [100, 100]))
    return [layer(group(_heart_path(), fill(GREEN), stroke(GREEN, 10), p=(C, C), a=(C, C), s=beat))]


def art_note():
    bob = anim((0, [C, C + 10]), (45, [C, C - 14]), (90, [C, C + 10]), (135, [C, C - 14]), (FRAMES, [C, C + 10]))
    stem = group(path([(300, 120), (300, 330)], closed=False), stroke(GREEN, 36))
    flag = group(path([(300, 120), (390, 160), (390, 220), (300, 186)]), *solid(GREEN, 16))
    head = group(ellipse(140, 110, 244, 340), fill(GREEN))
    return [layer(group(stem, flag, head, p=bob, a=(C, C)))]


def art_live():
    ring = group(ellipse(150, 150), stroke(GREEN, 18, anim((0, 100), (90, 0), (FRAMES, 0))),
                 p=(C, C), a=(C, C), s=anim((0, [100, 100]), (90, [260, 260]), (FRAMES, [260, 260])))
    core = group(ellipse(150, 150), fill(GREEN))
    return [layer(ring), layer(core)]


def art_sad():
    face = group(ellipse(330, 330), fill(GREY))
    eyes = [group(ellipse(40, 56, x, 220), fill(DARK)) for x in (200, 312)]
    mouth = group(arc(C, 380, 80, 230, 310), stroke(DARK, 26))
    zz = group(path([(380, 110), (430, 110), (380, 160), (430, 160)], closed=False), stroke(WHITE, 16),
               o=anim((0, 0), (40, 100), (120, 100), (FRAMES, 0)))
    return [layer(face, *eyes, mouth, zz)]


# key: (function, regular fallback emoji)
ICONS = {
    "play": (icon_play, "▶️"),
    "pause": (icon_pause, "⏸"),
    "next": (icon_next, "⏭"),
    "prev": (icon_prev, "⏮"),
    "shuffle": (icon_shuffle, "🔀"),
    "repeat": (icon_repeat, "🔁"),
    "repeat_one": (icon_repeat_one, "🔂"),
    "vol_down": (icon_vol_down, "🔉"),
    "vol_up": (icon_vol_up, "🔊"),
    "queue": (icon_queue, "📜"),
    "library": (icon_library, "📚"),
    "devices": (icon_devices, "📱"),
    "refresh": (icon_refresh, "🔄"),
    "search": (icon_search, "🔎"),
    "plus": (icon_plus, "➕"),
    "close": (icon_close, "✖️"),
    "back": (icon_back, "◀️"),
    "computer": (icon_computer, "💻"),
    "phone": (icon_phone, "📱"),
    "speaker": (icon_speaker, "🔈"),
    "music": (icon_music, "🎵"),
    "heart_outline": (icon_heart_outline, "🤍"),
    "disc": (icon_disc, "💿"),
    "clock": (icon_clock, "⏱"),
}

ART = {
    "equalizer": (art_equalizer, "🎶"),
    "equalizer_paused": (art_equalizer_paused, "⏸"),
    "vinyl": (art_vinyl, "💿"),
    "heart": (art_heart, "💚"),
    "note": (art_note, "🎵"),
    "live": (art_live, "🟢"),
    "sleep": (art_sad, "😴"),
}


def build_all() -> dict[str, dict[str, dict]]:
    """{'icons': {key: lottie}, 'art': {key: lottie}}"""
    return {
        "icons": {key: document(key, fn()) for key, (fn, _) in ICONS.items()},
        "art": {key: document(key, fn(), ART_SIZE) for key, (fn, _) in ART.items()},
    }


FALLBACK = {key: fb for key, (_, fb) in {**ICONS, **ART}.items()}
