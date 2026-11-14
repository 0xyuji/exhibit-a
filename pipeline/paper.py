"""Sets the paper as a web page: docs/thesis.html, from the same text as THESIS.md.

The text is a small, fixed subset of Markdown (headings, paragraphs, lists, tables, indented
code, images, bold, italic, code, links), so the conversion is done here with the standard
library and no Markdown package.
"""
import html
import re

RAMP = ".,:;'-+/\\|!*=%#&$@"
HOSTS = r"(?:dune\.com|api\.llama\.fi|revenue\.near\.org|x\.com|ledger\.com|zodl\.com|thedefiant\.io)"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def inline(text, cite=True):
    """Bold, italic, code, links and numbered citations, on escaped text."""
    text = html.escape(text, quote=False).replace("\\*", "&#42;")
    text = re.sub(r"&lt;(/?su[bp])&gt;", r"<\1>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    if cite:
        text = re.sub(r"\[(\d+)\](?!\()", r'<a class="cite" href="#ref-\1">\1</a>', text)
    return text


def table(lines):
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    head, body = rows[0], rows[2:]
    numeric = lambda cell: bool(re.match(r"^[$+-]?\d[\d,.]*\s?(%|x|bps|[KMB]|NEAR|MB)?$", cell))
    out = [f'<div class="tableWrap{" long" if len(body) > 14 else ""}"><table><thead><tr>', "".join(f"<th>{inline(cell)}</th>" for cell in head), "</tr></thead><tbody>"]
    for row in body:
        out.append("<tr>" + "".join(("<td class='n'>" if numeric(cell) else "<td>") + inline(cell) + "</td>" for cell in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def convert(text, equations=None):
    """Returns (title, html of the title block, html of the body, [(id, label)] for the contents)."""
    equations = equations or {}
    lines = text.split("\n")
    out, front, contents = [], [], []
    title = ""
    section = ""
    in_front = True
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            i += 1
        elif line.startswith("### ") and in_front:
            front.append(f'<p class="deck">{inline(line[4:])}</p>')
            i += 1
        elif line.startswith("## "):
            if in_front:
                in_front = False
            elif section == "Abstract":
                out.append("</section>")
            section = line[3:].strip()
            number = re.match(r"^(\d+|Appendix [A-Z])\.\s+(.*)$", section)
            label = number.group(2) if number else section
            mark = f'<span class="num">{number.group(1)}</span>' if number else ""
            ident = slug(section)
            contents.append((ident, number.group(1).replace("Appendix ", "") if number else "", label))
            if section == "Abstract":
                out.append(f'<section class="abstract" id="{ident}"><h2>{html.escape(label)}</h2>')
            else:
                out.append(f'<h2 id="{ident}">{mark}{inline(label)}</h2>')
            i += 1
        elif line.startswith("### "):
            head = line[4:].strip()
            number = re.match(r"^(\d+\.\d+)\s+(.*)$", head)
            mark = f'<span class="num">{number.group(1)}</span>' if number else ""
            out.append(f'<h3 id="{slug(head)}">{mark}{inline(number.group(2) if number else head)}</h3>')
            i += 1
        elif line.startswith("$$"):
            latex, number = re.match(r"^\$\$(.*?)(?:\s*\\tag\{(\d+)\})?\$\$$", line.strip()).groups()
            out.append(f'<div class="eq" id="eq-{number}"><span class="m">{equations.get(latex.strip(), html.escape(latex))}</span><span class="no">({number})</span></div>')
            i += 1
        elif line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            out.append(table(block))
        elif line.startswith("    "):
            block = []
            while i < len(lines) and (lines[i].startswith("    ") or (not lines[i].strip() and i + 1 < len(lines) and lines[i + 1].startswith("    "))):
                block.append(lines[i][4:])
                i += 1
            out.append(f"<pre>{html.escape(chr(10).join(block))}</pre>")
        elif re.match(r"^!\[[^\]]*\]\(([^)]+)\)$", line.strip()):
            alt, src = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line.strip()).groups()
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            caption = ""
            if i < len(lines) and lines[i].startswith("**Figure"):
                caption = f"<figcaption>{inline(lines[i])}</figcaption>"
                i += 1
            out.append(f'<figure class="plate" id="{slug(alt)}"><img src="{src.replace("docs/", "", 1)}" alt="{html.escape(alt)}" loading="lazy">{caption}</figure>')
        elif re.match(r"^(- |\d+\. )", line):
            ordered = not line.startswith("- ")
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            if section == "References":
                rows = []
                for n, item in enumerate(items, 1):
                    linked = re.sub(rf"(?<![\w/@.])({HOSTS}[^\s<)]*[^\s<).,])", r'<a href="https://\1">\1</a>', inline(item, cite=False))
                    rows.append(f'<li id="ref-{n}">{linked}</li>')
                out.append(f'<ol class="refs">{"".join(rows)}</ol>')
            else:
                out.append(f"<{tag}>" + "".join(f"<li>{inline(item)}</li>" for item in items) + f"</{tag}>")
        else:
            block = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||    |- |\d+\. |!\[|\$\$)", lines[i]):
                block.append(lines[i].strip())
                i += 1
            para = " ".join(block)
            if in_front:
                kind = ("author", "site", "version", "note")[min(sum(1 for item in front if not item.startswith('<p class="deck"')), 3)]
                front.append(f'<p class="{kind}">{inline(para)}</p>')
            elif para.startswith("**Table"):
                out.append(f'<p class="caption">{inline(para)}</p>')
            else:
                out.append(f"<p>{inline(para)}</p>")
    return title, "".join(front), "\n".join(out), contents


def rule(cells=120):
    """A line of glyphs under the title, the first stretch of it still cipher."""
    lit = "".join(RAMP[7 + ((c * 7919 + 13) % 11)] for c in range(int(cells * 0.18)))
    return f'<p class="rule" aria-hidden="true"><em>{html.escape(lit)}</em>{"." * (cells - len(lit))}</p>'


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Exhibit A</title>
<meta name="description" content="A working paper on NEAR Intents: every number, table and figure is written by one command from public data.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400;1,6..72,500&family=Schibsted+Grotesk:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="paper.css">
</head>
<body>
<header class="masthead">
  <a class="lockup" href="./"><canvas class="markGlyph" width="60" height="60" aria-hidden="true"></canvas><span>Exhibit A</span></a>
  <nav>
    <a href="./">Dashboard</a>
    <a href="https://github.com/0xyuji/exhibit-a">Code</a>
    <a class="out" href="exhibit-a-thesis.pdf">PDF</a>
  </nav>
</header>
<div class="sheet">
  <nav class="contents" aria-label="Contents">
    <p>Contents</p>
    <ol>{contents}</ol>
    <a class="back" href="./">Back to the dashboard</a>
  </nav>
  <main>
    <header class="front">
      <p class="band" aria-hidden="true">{band}</p>
      <h1>{title}</h1>
      {front}
      {rule}
    </header>
    {body}
    <p class="end"><a class="button" href="./">See the live charts</a><a href="https://github.com/0xyuji/exhibit-a">Read the code</a></p>
  </main>
</div>
<script>
// The mark: a small tile of cipher glyphs that never quite settles.
(() => {{
  const ramp = "/\\\\|!*=%#&$@";
  const canvas = document.querySelector(".markGlyph");
  const ctx = canvas.getContext("2d");
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cells = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) cells.push([c, r, ramp[Math.floor(Math.random() * ramp.length)]]);
  const draw = () => {{
    ctx.clearRect(0, 0, 60, 60);
    ctx.font = '17px "JetBrains Mono", ui-monospace, Menlo, monospace';
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(200,164,106,0.9)";
    for (const [c, r, g] of cells) ctx.fillText(g, 6 + c * 12, 5 + r * 17);
  }};
  draw();
  document.fonts?.ready.then(draw);
  if (!still) setInterval(() => {{ cells[Math.floor(Math.random() * cells.length)][2] = ramp[Math.floor(Math.random() * ramp.length)]; draw(); }}, 220);

  // Which section the reader is in.
  const links = new Map([...document.querySelectorAll(".contents ol a")].map((a) => [a.getAttribute("href").slice(1), a]));
  const seen = new IntersectionObserver((entries) => {{
    for (const entry of entries) {{
      if (!entry.isIntersecting) continue;
      links.forEach((a) => a.classList.remove("here"));
      links.get(entry.target.id)?.classList.add("here");
    }}
  }}, {{ rootMargin: "-20% 0px -70% 0px" }});
  links.forEach((_, id) => {{ const el = document.getElementById(id); if (el) seen.observe(el); }});

  // Figures and tables come up into place the first time they are reached.
  if (!still) {{
    const rise = new IntersectionObserver((entries) => {{
      for (const entry of entries) if (entry.isIntersecting) {{ entry.target.classList.add("in"); rise.unobserve(entry.target); }}
    }}, {{ threshold: 0.12 }});
    document.querySelectorAll(".plate, .tableWrap, .abstract").forEach((el) => {{ el.classList.add("rise"); rise.observe(el); }});
  }}
}})();
</script>
</body>
</html>
"""


def write(text, d, path, equations=None):
    title, front, body, contents = convert(text, equations)
    local = lambda markup: markup.replace('href="https://0xyuji.github.io/exhibit-a/exhibit-a-thesis.pdf"', 'href="exhibit-a-thesis.pdf"').replace('href="https://0xyuji.github.io/exhibit-a/"', 'href="./"')
    body, front = local(body), local(front)
    band = html.escape("".join(RAMP[7 + ((c * 2654435761 + 97) >> 7) % 11] for c in range(150)))
    listing = "".join(f'<li><a href="#{ident}"><span>{number}</span>{html.escape(label)}</a></li>' for ident, number, label in contents)
    with open(path, "w") as handle:
        handle.write(PAGE.format(title=html.escape(title), front=front, body=body, contents=listing, rule=rule(), band=band))
