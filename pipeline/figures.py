"""Draws the paper's figures as SVG files, in the page's ink, brass and green.

The files are plain SVG, so they show in THESIS.md on GitHub and in docs/thesis.html
without any script. Standard library only.
"""
import os
from xml.sax.saxutils import escape

RAMP = ".,:;'-+/\\|!*=%#&$@"
CW, CH = 6.0, 10.0  # the unit the charts are sized in, and one cell of the cipher texture
FONT = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
TONE = {
    "clear": "#ece7de",
    "cipher": "#c8a46a",
    "near": "#00ec97",
    "ghost": "#6f6c66",
    "faint": "#3a3936",
}
INK, DIM, LINE = "#0b0c0e", "#9a968e", "#2a2a2c"


def _hash(c, r):
    return ((c + 11) * 73856093 ^ (r + 7) * 19349663) & 0xFFFFFFFF


def _frame(width, height, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" '
        f'font-family="{FONT}" font-size="9">\n'
        f'<rect width="{width:.0f}" height="{height:.0f}" rx="14" fill="{INK}"/>\n'
        f'<rect x="0.5" y="0.5" width="{width - 1:.0f}" height="{height - 1:.0f}" rx="14" fill="none" stroke="{LINE}"/>\n'
        f"{body}\n</svg>\n"
    )


def _label(x, y, text, fill=DIM, anchor="start", size=10):
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}">{escape(text)}</text>'


def _bar(x, top, w, bottom, fill, cap):
    """One segment of a column. The top one of a stack gets rounded upper corners."""
    h = bottom - top
    r = min(2.5, w / 2, h) if cap else 0
    if r < 0.5:
        return f'<rect x="{x:.2f}" y="{top:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{fill}"/>'
    return (f'<path d="M{x:.2f} {bottom:.2f} V{top + r:.2f} Q{x:.2f} {top:.2f} {x + r:.2f} {top:.2f} H{x + w - r:.2f} '
            f'Q{x + w:.2f} {top:.2f} {x + w:.2f} {top + r:.2f} V{bottom:.2f} Z" fill="{fill}"/>')


def columns(items, legend, left, right, top_label, marks=(), cols=132, rows=24):
    """Stacked columns through time, one solid bar per item. items[i] is a list of (value, tone), bottom first."""
    pad, head = 22, 34
    wide, tall = cols * CW, rows * CH
    peak = max(sum(v for v, _ in item) for item in items) or 1
    slot = wide / len(items)
    thick = min(slot * 0.7, 24.0) if slot >= 5 else max(slot - 1, slot / 2)  # thin bars, each centred in its slot
    gap = 2.0 if slot >= 5 else 1.0  # the break between the parts of one bar
    floor = head + tall
    bars, notes = [], []
    for i, item in enumerate(items):
        x = pad + i * slot + (slot - thick) / 2
        parts = [(value / peak * tall, tone) for value, tone in item]
        parts = [(h, tone) for h, tone in parts if h >= 0.4]
        y = floor
        for n, (h, tone) in enumerate(parts):
            lift = gap if n and h > gap + 1 else 0  # the lower part shows through as a thin break
            bars.append(_bar(x, y - h, thick, y - lift, TONE[tone], n == len(parts) - 1))
            y -= h
        for index, text in marks:
            if index == i:
                cx = x + thick / 2
                if y - 5 > head + 2:
                    bars.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{head + 2}" y2="{y - 5:.1f}" stroke="{TONE["ghost"]}" stroke-dasharray="2 3"/>')
                notes.append((cx, text))
    width = wide + pad * 2
    height = head + tall + 34
    body = []
    x = pad
    for tone, text in legend:
        body.append(f'<rect x="{x:.1f}" y="13.5" width="9" height="9" rx="2" fill="{TONE[tone]}"/>')
        body.append(_label(x + 16, 22, text))
        x += 28 + len(text) * 6.2
    body.append(_label(width - pad, 22, top_label, anchor="end"))
    body.extend(bars)
    base = floor + 1.5
    body.append(f'<line x1="{pad}" x2="{width - pad}" y1="{base}" y2="{base}" stroke="#4a4844"/>')
    body.append(_label(pad, base + 17, left))
    body.append(_label(width - pad, base + 17, right, anchor="end"))
    for cx, text in notes:  # the note sits on whichever side of its mark has room
        if cx > width / 2:
            body.append(_label(cx - 8, head + 9, text, "#c8a46a", "end"))
        else:
            body.append(_label(cx + 8, head + 9, text, "#c8a46a"))
    return _frame(width, height, "\n".join(body))


# ---- diagrams: boxes, arrows, ribbons and horizontal bars ----
W = 836.0  # every figure is this wide, so they line up in the paper
PAPER, BRASS, NEAR = "#ece7de", "#c8a46a", "#00ec97"
ARROW = ('<defs><marker id="tip" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">'
         f'<path d="M0 0.6 L7.2 4 L0 7.4 Z" fill="{BRASS}"/></marker></defs>')


def _text(x, y, text, fill=DIM, size=10, anchor="start", weight=400):
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(text)}</text>')


def _box(x, y, w, h, title, lines=(), stroke=BRASS, fill="#121316"):
    out = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="9" fill="{fill}" stroke="{stroke}" stroke-opacity="0.55"/>',
           _text(x + 12, y + 20, title, PAPER, 11, weight=500)]
    for n, line in enumerate(lines):
        out.append(_text(x + 12, y + 37 + n * 13, line, DIM, 9.5))
    return "\n".join(out)


def _arrow(x1, y1, x2, y2, label=None, dash=False):
    dashes = 'stroke-dasharray="3 3" ' if dash else ""
    out = [f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{BRASS}" stroke-opacity="0.8" '
           f'{dashes}marker-end="url(#tip)"/>']
    if label:
        out.append(_text((x1 + x2) / 2, min(y1, y2) - 6, label, DIM, 9, "middle"))
    return "\n".join(out)


def _cipher(x, y, cells, seed=0, fill=BRASS, opacity=0.8):
    """A short run of cipher glyphs, used as texture where something is hidden."""
    chars = "".join(RAMP[7 + _hash(c, seed) % 11] for c in range(cells))
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" fill-opacity="{opacity}" font-size="9" textLength="{cells * CW:.1f}" '
            f'lengthAdjust="spacingAndGlyphs">{escape(chars)}</text>')


def mechanism(d):
    """How one swap travels: the wallet, the front-end, the quote, the solver, the payout, and the venue under them."""
    p, dark = d["partner"], d["dark"]
    pad, gap, w, h = 24.0, 22.0, 140.0, 76.0
    xs = [pad + n * (w + gap) for n in range(5)]
    y = 46.0
    body = [ARROW, _text(pad, 26, "ONE SWAP, LEFT TO RIGHT", BRASS, 9.5, weight=500)]
    boxes = [
        ("The user", ["holds BTC, wants USDT", "taps swap in a wallet"]),
        ("A front-end", ["wallet or aggregator", f"sets the fee: {p['bps']:.0f} bps"]),
        ("1Click API", ["quotes, then gives a", "one-time address"]),
        ("A solver", ["fills the order from", "its own inventory"]),
        ("The payout", ["USDT arrives on the", "chain the user chose"]),
    ]
    for x, (title, lines) in zip(xs, boxes):
        body.append(_box(x, y, w, h, title, lines))
    for n in range(4):
        body.append(_arrow(xs[n] + w + 3, y + h / 2, xs[n + 1] - 4, y + h / 2))
    # the venue: one band under the quote and the solver, with a public and a confidential lane
    vx, vy, vw, vh = xs[1], y + h + 44, xs[4] + w - xs[1], 112.0
    body.append(f'<rect x="{vx:.1f}" y="{vy:.1f}" width="{vw:.1f}" height="{vh:.1f}" rx="11" fill="#0f1012" stroke="{PAPER}" stroke-opacity="0.22"/>')
    body.append(_text(vx + 14, vy + 22, "NEAR INTENTS, THE VENUE", PAPER, 10, weight=500))
    body.append(_text(vx + vw - 14, vy + 22, "no order book: solvers quote, the contract settles", DIM, 9.5, "end"))
    lane = (vw - 42) / 2
    body.append(_box(vx + 14, vy + 36, lane, 62, "Public settlement", ["on NEAR, in the intents.near contract", f"{(1 - dark['share_last']) * 100:.0f}% of volume on the last day read"], stroke=PAPER))
    cx = vx + 28 + lane
    body.append(_box(cx, vy + 36, lane, 62, "Confidential settlement", ["shielded balances on a private chain,", f"bridged back to NEAR: {dark['share_last'] * 100:.0f}% of volume"]))
    body.append(_cipher(cx + lane - 12 - 16 * CW, vy + 56, 16, 3))
    body.append(_arrow(xs[2] + w / 2, y + h + 3, xs[2] + w / 2, vy - 4))
    body.append(_arrow(xs[3] + w / 2, vy - 3, xs[3] + w / 2, y + h + 4))
    body.append(_text(xs[2] + w / 2 + 8, y + h + 26, "deposit", DIM, 9))
    body.append(_text(xs[3] + w / 2 + 8, y + h + 26, "release", DIM, 9))
    body.append(_text(xs[0], vy + 30, "The fee is charged", DIM, 9.5))
    body.append(_text(xs[0], vy + 43, "by the front-end.", DIM, 9.5))
    body.append(_text(xs[0], vy + 62, "A NEAR wallet is", DIM, 9.5))
    body.append(_text(xs[0], vy + 75, f"named on {p['near_cut'] * 100:.0f}% of it.", NEAR, 9.5))
    return _frame(W, vy + vh + 22, "\n".join(body))


def pipeline(d):
    """Where the numbers come from and what the one command writes."""
    pad = 24.0
    left = [
        ("NEAR Intents Explorer API", "every partner swap in the window"),
        ("DefiLlama, NEAR's Dune queries", "the official volume, fees, revenue"),
        ("NEAR RPC and archive node", "wallets, supply, contract state"),
        ("NEAR docs and dashboard", "fee schedule, dates, revenue split"),
    ]
    right = [
        ("docs/data.json", "the dashboard reads it"),
        ("THESIS.md, thesis.html", "this paper, numbers and all"),
        ("docs/figures/", "every figure here"),
        (f"{len(d['checks'])} checks, {len(d['tripwires'])} tripwires", "printed on every build"),
    ]
    bw, bh, gap = 248.0, 46.0, 12.0
    top = 44.0
    body = [ARROW, _text(pad, 26, "SOURCES", BRASS, 9.5, weight=500), _text(W - pad, 26, "WRITTEN BY THE BUILD", BRASS, 9.5, "end", 500)]
    mid_w, mid_h = 176.0, 4 * bh + 3 * gap
    mx = (W - mid_w) / 2
    body.append(f'<rect x="{mx:.1f}" y="{top:.1f}" width="{mid_w:.1f}" height="{mid_h:.1f}" rx="11" fill="#14130f" stroke="{BRASS}"/>')
    body.append(_text(mx + mid_w / 2, top + 30, "python3 build.py", PAPER, 12, "middle", 500))
    for n, step in enumerate(("count each swap once", "fold into daily totals", "check against outside", "run the token model", "write everything")):
        body.append(_text(mx + mid_w / 2, top + 62 + n * 21, step, DIM, 9.5, "middle"))
        if n:
            body.append(_text(mx + mid_w / 2, top + 51 + n * 21, "|", BRASS, 8, "middle"))
    body.append(_text(mx + mid_w / 2, top + mid_h - 16, "standard library only", BRASS, 9, "middle"))
    for n, (title, sub) in enumerate(left):
        y = top + n * (bh + gap)
        body.append(_box(pad, y, bw, bh, title, [sub]))
        body.append(_arrow(pad + bw + 3, y + bh / 2, mx - 5, top + 36 + n * (mid_h - 72) / 3))
    for n, (title, sub) in enumerate(right):
        y = top + n * (bh + gap)
        body.append(_box(W - pad - bw, y, bw, bh, title, [sub], stroke=PAPER))
        body.append(_arrow(mx + mid_w + 3, top + 36 + n * (mid_h - 72) / 3, W - pad - bw - 5, y + bh / 2))
    return _frame(W, top + mid_h + 24, "\n".join(body))


def units(d):
    """One swap is two entries in the official volume and one in ours."""
    pad = 24.0
    body = [ARROW, _text(pad, 26, "ONE SWAP, TWO WAYS TO COUNT IT", BRASS, 9.5, weight=500)]
    body.append(_box(pad, 46, 230, 74, "One swap", ["$100 of BTC goes in", "$100 of USDT comes out"]))
    rx = 356.0
    body.append(_box(rx, 40, W - pad - rx, 48, "Official volume: $200", ["BTC +$100 and USDT +$100, a sum of volume per token"], stroke=PAPER))
    body.append(_box(rx, 98, W - pad - rx, 48, "Swap value, as used in this paper: $100", ["each swap once, so the official figure is halved"]))
    body.append(_arrow(pad + 233, 74, rx - 5, 64))
    body.append(_arrow(pad + 233, 96, rx - 5, 122))
    o, p = d["official"], d["partner"]
    body.append(_text(pad, 172, f"In this window: official volume ${o['volume'] / 1e9:.2f}B, swap value ${o['swap_value'] / 1e9:.2f}B, "
                                f"of which partner swaps ${p['volume'] / 1e9:.2f}B.", DIM, 10))
    return _frame(W, 190, "\n".join(body))


def _ribbon(x1, y1, h1, x2, y2, h2, fill, opacity):
    mid = (x1 + x2) / 2
    return (f'<path d="M{x1:.1f} {y1:.1f} C{mid:.1f} {y1:.1f} {mid:.1f} {y2:.1f} {x2:.1f} {y2:.1f} '
            f'L{x2:.1f} {y2 + h2:.1f} C{mid:.1f} {y2 + h2:.1f} {mid:.1f} {y1 + h1:.1f} {x1:.1f} {y1 + h1:.1f} Z" '
            f'fill="{fill}" fill-opacity="{opacity}"/>')


def fee_flow(d, usd):
    """Every fee dollar of the window: who paid it, through which door, and whose name is on it."""
    p, o = d["partner"], d["official"]
    kinds = sorted(d["kinds"], key=lambda k: -k["fees"])
    total = p["fees"] + o["rest_fees"]
    pad, top, tall, node = 24.0, 50.0, 250.0, 10.0
    gap = 9.0
    scale = (tall - gap * len(kinds)) / total
    x1, x2, x3 = 236.0, 436.0, 616.0
    body = [_text(pad, 26, "WHO PAID", BRASS, 9.5, weight=500), _text(x2 + node / 2, 26, "THROUGH", BRASS, 9.5, "middle", 500),
            _text(W - pad, 26, "WHOSE NAME IS ON IT", BRASS, 9.5, "end", 500)]
    # middle and right nodes
    my = top
    partner_h, rest_h = p["fees"] * scale, o["rest_fees"] * scale
    rest_y = top + tall - rest_h
    keep_h, near_h = (p["fees"] - p["to_near"]) * scale, p["to_near"] * scale
    near_y = my + keep_h + 16
    own_y = rest_y + 0.0
    # left nodes and ribbons into the partner door
    y, into = top, my
    for k in kinds:
        h = k["fees"] * scale
        body.append(f'<rect x="{x1:.1f}" y="{y:.1f}" width="{node}" height="{max(h, 1.5):.1f}" fill="{PAPER}"/>')
        body.append(_text(x1 - 10, y + min(h, 30) / 2 + 4, k["name"], PAPER, 10.5, "end"))
        body.append(_text(x1 - 10, y + min(h, 30) / 2 + 17, f"{usd(k['fees'])} at {k['bps']:.0f} bps", DIM, 9, "end") if h > 22 else
                    _text(x1 - 10 - len(k["name"]) * 6.4 - 8, y + min(h, 30) / 2 + 4, f"{usd(k['fees'])}", DIM, 9, "end"))
        body.append(_ribbon(x1 + node, y, h, x2, into, h, PAPER, 0.16))
        into += h
        y += h + gap
    ry = top + tall - rest_h
    body.append(f'<rect x="{x1:.1f}" y="{ry:.1f}" width="{node}" height="{rest_h:.1f}" fill="{BRASS}"/>')
    body.append(_text(x1 - 10, ry + rest_h / 2 - 2, "Outside the partner API", BRASS, 10.5, "end"))
    body.append(_text(x1 - 10, ry + rest_h / 2 + 11, f"{usd(o['rest_fees'])} at {o['rest_bps']:.0f} bps, mostly stablecoins", DIM, 9, "end"))
    body.append(_ribbon(x1 + node, ry, rest_h, x2, rest_y, rest_h, BRASS, 0.22))
    body.append(f'<rect x="{x2:.1f}" y="{my:.1f}" width="{node}" height="{partner_h:.1f}" fill="{PAPER}"/>')
    body.append(f'<rect x="{x2:.1f}" y="{rest_y:.1f}" width="{node}" height="{rest_h:.1f}" fill="{BRASS}"/>')
    body.append(_text(x2 + node + 9, my + partner_h / 2 - 2, "Partner API", PAPER, 10.5))
    body.append(_text(x2 + node + 9, my + partner_h / 2 + 11, usd(p["fees"]), DIM, 9))
    # right: what front-ends keep, what is named to NEAR, what NEAR's own front-end books
    body.append(_ribbon(x2 + node, my, keep_h, x3, my, keep_h, PAPER, 0.16))
    body.append(_ribbon(x2 + node, my + keep_h, near_h, x3, near_y, near_h, NEAR, 0.5))
    body.append(_ribbon(x2 + node, rest_y, rest_h, x3, own_y, rest_h, BRASS, 0.22))
    body.append(f'<rect x="{x3:.1f}" y="{my:.1f}" width="{node}" height="{keep_h:.1f}" fill="{PAPER}"/>')
    body.append(f'<rect x="{x3:.1f}" y="{near_y:.1f}" width="{node}" height="{max(near_h, 2):.1f}" fill="{NEAR}"/>')
    body.append(f'<rect x="{x3:.1f}" y="{own_y:.1f}" width="{node}" height="{rest_h:.1f}" fill="{BRASS}"/>')
    body.append(_text(x3 + node + 10, my + keep_h / 2 - 2, "Front-ends and their partners", PAPER, 10.5))
    body.append(_text(x3 + node + 10, my + keep_h / 2 + 11, f"{usd(p['fees'] - p['to_near'])}, {(1 - p['near_cut']) * 100:.0f}% of partner fees", DIM, 9))
    body.append(_text(x3 + node + 10, near_y + near_h / 2 + 1, "A NEAR wallet", NEAR, 10.5))
    body.append(_text(x3 + node + 10, near_y + near_h / 2 + 14, f"{usd(p['to_near'])}, {p['near_cut'] * 100:.0f}% of partner fees", DIM, 9))
    body.append(_text(x3 + node + 10, own_y + rest_h / 2 - 2, "NEAR's own front-end", BRASS, 10.5))
    body.append(_text(x3 + node + 10, own_y + rest_h / 2 + 11, "per NEAR's revenue dashboard", DIM, 9))
    return _frame(W, top + tall + 24, "\n".join(body))


def slope(d):
    """Share of volume against share of fees, by what is swapped. A line that rises is a customer who pays more than their size."""
    kinds = d["kinds"]
    pad, top, tall = 24.0, 58.0, 200.0
    xl, xr = 300.0, 540.0
    peak = max(max(k["volume_share"], k["fee_share"]) for k in kinds) * 1.08
    y = lambda share: top + tall - share / peak * tall
    body = [_text(xl, 26, "SHARE OF VOLUME", BRASS, 9.5, "end", 500), _text(xr, 26, "SHARE OF FEES", BRASS, 9.5, "start", 500),
            f'<line x1="{xl}" x2="{xl}" y1="{top - 8}" y2="{top + tall}" stroke="#4a4844"/>',
            f'<line x1="{xr}" x2="{xr}" y1="{top - 8}" y2="{top + tall}" stroke="#4a4844"/>']
    for k in sorted(kinds, key=lambda k: k["fee_share"]):
        up = k["fee_share"] >= k["volume_share"]
        tone = PAPER if up else BRASS
        if k["name"] == "Everything else":
            tone = "#8f8b84"
        width = 2.4 if k["name"] in ("Bitcoin", "Stablecoin pair") else 1.3
        ya, yb = y(k["volume_share"]), y(k["fee_share"])
        body.append(f'<line x1="{xl}" y1="{ya:.1f}" x2="{xr}" y2="{yb:.1f}" stroke="{tone}" stroke-width="{width}" stroke-linecap="round"/>')
        body.append(f'<circle cx="{xl}" cy="{ya:.1f}" r="3.4" fill="{tone}"/><circle cx="{xr}" cy="{yb:.1f}" r="3.4" fill="{tone}"/>')
        body.append(_text(xl - 12, ya + 3.5, f"{k['name']}  {k['volume_share'] * 100:.0f}%", tone, 10.5, "end"))
        body.append(_text(xr + 12, yb + 3.5, f"{k['fee_share'] * 100:.0f}%  at {k['bps']:.0f} bps", tone, 10.5))
    body.append(_text(pad, top + tall + 24, "A rising line is a customer who pays more than their share of the volume.", DIM, 10))
    return _frame(W, top + tall + 40, "\n".join(body))


def strip(d, names):
    """Partner fees as one strip, cut by front-end, with the part named to NEAR laid over each piece."""
    p = d["partner"]
    fronts = sorted(d["front_ends"], key=lambda f: -f["fees"])
    pad, top, tall = 24.0, 44.0, 44.0
    wide = W - pad * 2
    body = [_text(pad, 26, f"PARTNER FEES, {d['window']['days']} DAYS, BY FRONT-END", BRASS, 9.5, weight=500),
            _text(W - pad, 26, "green: the part named to a NEAR wallet", NEAR, 9.5, "end")]
    shades = ["#ece7de", "#b9b4ab", "#8f8b84", "#6c6963", "#55534e", "#44423e", "#383734"]
    x = pad
    shown = fronts[:6]
    rest = sum(f["fees"] for f in fronts[6:])
    pieces = [(names.get(f["name"], f["name"]), f["fees"], f["to_near"]) for f in shown] + ([(f"{len(fronts) - 6} others", rest, sum(f["to_near"] for f in fronts[6:]))] if rest else [])
    for n, (name, fees, near) in enumerate(pieces):
        w = fees / p["fees"] * wide
        body.append(f'<rect x="{x:.1f}" y="{top}" width="{max(w - 1.5, 0.8):.1f}" height="{tall}" fill="{shades[min(n, 6)]}"/>')
        if near > 0:
            body.append(f'<rect x="{x:.1f}" y="{top + tall - 12}" width="{max(near / p["fees"] * wide, 1.2):.1f}" height="12" fill="{NEAR}"/>')
        if w > 90:
            body.append(_text(x + 12, top + 19, name, "#0b0c0e", 11.5, weight=500))
            body.append(_text(x + 12, top + 34, f"{fees / p['fees'] * 100:.0f}% of partner fees", "#0b0c0e", 9.5))
        x += w
    # the legend: every piece, its share, and how much of it names NEAR
    cols, row = 4, 30.0
    for n, (name, fees, near) in enumerate(pieces):
        cx = pad + (n % cols) * (wide / cols)
        cy = top + tall + 28 + (n // cols) * row
        body.append(f'<rect x="{cx:.1f}" y="{cy - 9:.1f}" width="9" height="9" fill="{shades[min(n, 6)]}"/>')
        body.append(_text(cx + 15, cy - 1, f"{name}  {fees / p['fees'] * 100:.0f}%", PAPER, 10.5))
        body.append(_text(cx + 15, cy + 12, f"NEAR named on {near / fees * 100:.0f}%" if fees else "", NEAR if near > 0 else DIM, 9))
    return _frame(W, top + tall + 28 + ((len(pieces) - 1) // cols + 1) * row + 4, "\n".join(body))


def hbars(rows, scale, title, mark=None, name=250.0):
    """Plain horizontal bars: a thin track, a solid fill, the value at the end."""
    pad, line = 24.0, 26.0
    x0 = pad + name
    wide = W - pad - 190 - x0
    body = [_text(pad, 26, title, BRASS, 9.5, weight=500)]
    top = 44.0
    if mark:
        mx = x0 + min(mark[0] / scale, 1) * wide
        body.append(f'<line x1="{mx:.1f}" x2="{mx:.1f}" y1="{top - 8}" y2="{top + len(rows) * line - 4}" stroke="{PAPER}" stroke-opacity="0.5" stroke-dasharray="2 3"/>')
        body.append(_text(mx, 26, mark[1], PAPER, 9.5, "middle"))
    for n, (label, value, text, tone) in enumerate(rows):
        y = top + n * line
        body.append(_text(pad, y + 11, label, PAPER if tone != DIM else DIM, 10.5))
        body.append(f'<rect x="{x0:.1f}" y="{y + 3:.1f}" width="{wide:.1f}" height="9" rx="4.5" fill="{PAPER}" fill-opacity="0.07"/>')
        body.append(f'<rect x="{x0:.1f}" y="{y + 3:.1f}" width="{max(min(value / scale, 1) * wide, 2):.1f}" height="9" rx="4.5" fill="{tone if tone != DIM else "#8f8b84"}"/>')
        body.append(_text(W - pad, y + 11, text, PAPER, 10.5, "end"))
    return _frame(W, top + len(rows) * line + 10, "\n".join(body))


def write_all(d, folder):
    """Writes every figure the paper uses and returns {key: file name}."""
    os.makedirs(folder, exist_ok=True)
    out = {}
    short = lambda day: f"{int(day[8:10])} {('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec').split()[int(day[5:7]) - 1]} {day[:4]}"
    usd = lambda x: f"${x / 1e9:.2f}B" if abs(x) >= 1e9 else f"${x / 1e6:.1f}M" if abs(x) >= 1e6 else f"${x / 1e3:.0f}K" if abs(x) >= 1e4 else f"${x:,.0f}"
    pct = lambda x, digits=0: f"{x * 100:.{digits}f}%"

    def save(key, svg):
        name = f"{key}.svg"
        with open(os.path.join(folder, name), "w") as handle:
            handle.write(svg)
        out[key] = name

    dark = [r for r in d["dark"]["days"] if r["day"] >= "2026-08-01" and r.get("public") is not None and r.get("confidential") is not None]
    switch = next((i for i, r in enumerate(dark) if r["day"] == "2026-10-27"), None)
    save("dark", columns(
        [[(r["public"], "clear"), (r["confidential"], "cipher")] for r in dark],
        [("clear", "public"), ("cipher", "confidential")],
        short(dark[0]["day"]), short(dark[-1]["day"]),
        f"top of chart {usd(max(r['public'] + r['confidential'] for r in dark))} a day",
        marks=[(switch, "27 Oct: partner swaps settle confidentially")] if switch is not None else (),
    ))

    names = {"swapkit": "SwapKit", "lifi": "LI.FI", "(none)": "No label", "rango": "Rango", "zodl": "Zodl", "trustwallet": "Trust Wallet"}
    save("mechanism", mechanism(d))
    save("pipeline", pipeline(d))
    save("units", units(d))
    save("feeflow", fee_flow(d, usd))
    save("payers", slope(d))
    save("fronts", strip(d, names))

    mo = d.get("monthly") or []
    if mo:
        save("capture", columns(
            [[(r["capture"], "near")] for r in mo], [("near", "NEAR's revenue as a share of gross fees")],
            mo[0]["month"], mo[-1]["month"], f"top of chart {pct(max(r['capture'] for r in mo))}", cols=96, rows=20,
        ))

    past = [h for h in d["history"] if h.get("fees") is not None]
    save("growth", columns(
        [[(h["fees"], "clear")] for h in past], [("clear", "partner fees on a sampled day")],
        short(past[0]["day"]), f"this window ({short(d['window']['to'])})", f"top of chart {usd(max(h['fees'] for h in past))} a day",
    ))

    flow = [r for r in (d.get("chain_history") or {}).get("days", []) if r.get("inflow") is not None]
    if flow:
        save("inflow", columns(
            [[(max(0.0, r["inflow"]), "near")] for r in flow], [("near", "NEAR arriving in the three revenue wallets")],
            short(flow[0]["day"]), short(flow[-1]["day"]), f"top of chart {max(r['inflow'] for r in flow):,.0f} NEAR a day",
        ))

    scen = d["model"]["scenarios"]
    top = max(1.2, min(1.6, max(s["covered"] for s in scen) * 1.05))
    save("model", hbars(
        [(s["name"], s["covered"], f"{pct(s['covered'], 1)} of new issuance", NEAR if s["covered"] >= 1 else BRASS) for s in scen],
        top, "SHARE OF NEW ISSUANCE THAT REVENUE WOULD COVER", mark=(1.0, "break-even"), name=300.0,
    ))

    peers = d.get("peers")
    if peers:
        save("peers", hbars(
            [(r["name"], r["volume"], f"{usd(r['volume'])}  {'halved to one side' if r['near'] else 'as reported'}", NEAR if r["near"] else "#b9b4ab") for r in peers["rows"]],
            max(r["volume"] for r in peers["rows"]), f"VOLUME OVER THE SAME {d['window']['days']} DAYS", name=120.0,
        ))
    return out
