"""Draws the paper's figures as SVG files, in the same glyphs as the page's charts.

A figure is a grid of small monospace glyphs: each cell holds one character and one tone.
The files are plain SVG text, so they show in THESIS.md on GitHub and in docs/thesis.html
without any script. Standard library only.
"""
import os
from xml.sax.saxutils import escape

RAMP = ".,:;'-+/\\|!*=%#&$@"
CW, CH = 6.0, 10.0  # one glyph cell, in SVG units
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


def _glyph(tone, word, c, r):
    """Readable tones repeat a word; cipher is dense symbols; ghost and faint are light ones."""
    if tone == "cipher":
        return RAMP[7 + _hash(c, r) % 11]
    if tone == "ghost":
        return RAMP[2 + _hash(c, r) % 8]
    if tone == "faint":
        return RAMP[_hash(c, r) % 3]
    return word[(c + r * 2) % len(word)]


class Grid:
    """Cells addressed by column and row, row 0 at the bottom."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.cells = {}

    def put(self, c, r, tone, word="#"):
        if 0 <= c < self.cols and 0 <= r < self.rows:
            ch = _glyph(tone, word, c, r)
            if ch != " ":
                self.cells[(c, r)] = (ch, tone)

    def svg(self, x0, y0):
        """One <text> per run of same-toned glyphs, stretched to the grid so any monospace font lines up."""
        out = []
        for r in range(self.rows):
            y = y0 + (self.rows - r) * CH - 2.2
            c = 0
            while c < self.cols:
                cell = self.cells.get((c, r))
                if not cell:
                    c += 1
                    continue
                tone, start, chars = cell[1], c, []
                while c < self.cols and self.cells.get((c, r), (None, None))[1] == tone:
                    chars.append(self.cells[(c, r)][0])
                    c += 1
                out.append(
                    f'<text x="{x0 + start * CW:.1f}" y="{y:.1f}" fill="{TONE[tone]}" textLength="{len(chars) * CW:.1f}" '
                    f'lengthAdjust="spacingAndGlyphs">{escape("".join(chars))}</text>'
                )
        return "\n".join(out)


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


def columns(items, legend, left, right, top_label, marks=(), cols=132, rows=24):
    """Stacked columns through time. items[i] is a list of (value, tone, word), bottom first."""
    pad = 22
    grid = Grid(cols, rows)
    peak = max(sum(v for v, _, _ in item) for item in items) or 1
    n = len(items)
    spaced = cols >= n * 3
    notes = []
    for c in range(cols):
        a = min(n - 1, c * n // cols)
        nxt = (c + 1) * n // cols
        if spaced and nxt != a:
            continue  # a one-cell gap between bars
        b = a + 1 if spaced else max(a + 1, min(n, nxt))
        total = 0.0
        for part in range(len(items[a])):
            value = sum(items[i][part][0] for i in range(a, b)) / (b - a)
            lo = round(total / peak * rows)
            total += value
            hi = round(total / peak * rows)
            for r in range(lo, hi):
                grid.put(c, r, items[a][part][1], items[a][part][2])
        for index, text in marks:
            if index == a and (c == 0 or min(n - 1, (c - 1) * n // cols) != a):
                for r in range(round(total / peak * rows) + 1, rows):
                    grid.put(c, r, "ghost", ":")
                notes.append((c, text))
    width = cols * CW + pad * 2
    head = 34
    height = head + rows * CH + 34
    body = []
    x = pad
    for tone, text in legend:
        body.append(_label(x, 22, "##", TONE[tone]))
        body.append(_label(x + 16, 22, text))
        x += 28 + len(text) * 6.2
    body.append(_label(width - pad, 22, top_label, anchor="end"))
    body.append(grid.svg(pad, head))
    base = head + rows * CH + 1.5
    body.append(f'<line x1="{pad}" x2="{width - pad}" y1="{base}" y2="{base}" stroke="#4a4844"/>')
    body.append(_label(pad, base + 17, left))
    body.append(_label(width - pad, base + 17, right, anchor="end"))
    for c, text in notes:  # the note sits on whichever side of its mark has room
        if c > cols / 2:
            body.append(_label(pad + c * CW - 6, head + 9, text, "#c8a46a", "end"))
        else:
            body.append(_label(pad + c * CW + 11, head + 9, text, "#c8a46a"))
    return _frame(width, height, "\n".join(body))


def bars(rows, scale=None, cells=74, note=None, name=168, value=150):
    """Horizontal bars. Each row: (label, [(share, tone, word), ...], value text). A row of None is a gap."""
    pad = 22
    top = max((share for row in rows if row for share, _, _ in [max(row[1], key=lambda p: p[0])]), default=1)
    full = scale or top or 1
    width = pad * 2 + name + cells * CW + value
    line = 22
    height = 18 + sum(line if row else 10 for row in rows) + (30 if note else 12)
    body = []
    y = 18
    for row in rows:
        if not row:
            y += 10
            continue
        label, parts, text = row
        grid = Grid(cells, 1)
        for c in range(cells):
            grid.put(c, 0, "faint")
        at = 0
        for share, tone, word in parts:
            n = max(1, round(share / full * cells)) if share > 0 else 0
            for c in range(at, min(cells, at + n)):
                grid.put(c, 0, tone, word)
            at += n
        body.append(_label(pad, y + 13, label, "#ece7de" if parts and parts[0][1] != "ghost" else DIM, size=10.5))
        body.append(grid.svg(pad + name, y + 5.5))
        body.append(_label(width - pad, y + 13, text, "#ece7de", "end", 10.5))
        y += line
    if note:
        body.append(_label(pad, y + 14, note))
    return _frame(width, height, "\n".join(body))


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
        [[(r["public"], "clear", "public "), (r["confidential"], "cipher", "#")] for r in dark],
        [("clear", "public"), ("cipher", "confidential")],
        short(dark[0]["day"]), short(dark[-1]["day"]),
        f"top of chart {usd(max(r['public'] + r['confidential'] for r in dark))} a day",
        marks=[(switch, "27 Oct: partner swaps settle confidentially")] if switch is not None else (),
    ))

    kinds = sorted(d["kinds"], key=lambda k: -k["fee_share"])
    rows = []
    for k in kinds:
        rows.append((k["name"], [(k["fee_share"], "clear", "fees ")], f"{pct(k['fee_share'])} of fees at {k['bps']:.0f} bps"))
        rows.append(("", [(k["volume_share"], "ghost", "#")], f"{pct(k['volume_share'])} of volume"))
        rows.append(None)
    save("payers", bars(rows[:-1], scale=max(max(k["fee_share"], k["volume_share"]) for k in kinds)))

    names = {"swapkit": "SwapKit", "lifi": "LI.FI", "(none)": "No label", "rango": "Rango", "zodl": "Zodl"}
    fronts = sorted(d["front_ends"], key=lambda f: -f["fees"])[:7]
    save("fronts", bars(
        [(names.get(f["name"], f["name"]), [(f["to_near"] / d["partner"]["fees"], "near", "near"), ((f["fees"] - f["to_near"]) / d["partner"]["fees"], "clear", "fees ")],
          f"{pct(f['fee_share'])} of fees, NEAR named on {pct(f['to_near'] / f['fees']) if f['fees'] else '0%'}") for f in fronts],
        note="Green is the part of each front-end's fees on which a NEAR wallet is named.", cells=66, name=120, value=210,
    ))

    mo = d.get("monthly") or []
    if mo:
        save("capture", columns(
            [[(r["capture"], "near", "near")] for r in mo], [("near", "NEAR's revenue as a share of gross fees")],
            mo[0]["month"], mo[-1]["month"], f"top of chart {pct(max(r['capture'] for r in mo))}", cols=96, rows=20,
        ))

    past = [h for h in d["history"] if h.get("fees") is not None]
    save("growth", columns(
        [[(h["fees"], "clear", "fees ")] for h in past], [("clear", "partner fees on a sampled day")],
        short(past[0]["day"]), f"this window ({short(d['window']['to'])})", f"top of chart {usd(max(h['fees'] for h in past))} a day",
    ))

    flow = [r for r in (d.get("chain_history") or {}).get("days", []) if r.get("inflow") is not None]
    if flow:
        save("inflow", columns(
            [[(max(0.0, r["inflow"]), "near", "near")] for r in flow], [("near", "NEAR arriving in the three revenue wallets")],
            short(flow[0]["day"]), short(flow[-1]["day"]), f"top of chart {max(r['inflow'] for r in flow):,.0f} NEAR a day",
        ))

    scen = d["model"]["scenarios"]
    save("model", bars(
        [(s["name"], [(min(s["covered"], 1.5), "near" if s["covered"] >= 1 else "cipher", "#")], f"{pct(s['covered'], 1)} of new issuance") for s in scen],
        scale=max(1.0, min(1.5, max(s["covered"] for s in scen))), cells=50, name=290, value=150,
        note="Share of the dollar value of new NEAR issuance that revenue would cover. 100% is break-even.",
    ))

    peers = d.get("peers")
    if peers:
        save("peers", bars(
            [(r["name"], [(r["volume"], "near" if r["near"] else "clear", "near" if r["near"] else "swap ")], f"{usd(r['volume'])}, {r['note']}") for r in peers["rows"]],
            cells=56, name=110, value=290,
        ))
    return out
