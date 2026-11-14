# exhibit[A]

**A long-term thesis on NEAR, tested against every partner swap of a 30-day window.**

The name comes from the track's own rule: a thesis here is "judged on the evidence, not the
conviction". So this one is laid out as evidence. Every chart on the page is a numbered
exhibit, drawn from data you can rebuild with one command.

The claim: NEAR has become the exchange everyone asked for but nobody shipped.

- **Private and simple like a CEX, without the formalities.** Send in one coin, take out another. Nothing public links the two, and nobody asks for your ID.
- **Yours, and fair, like a DEX.** It starts and ends in your own wallet. No account, and no house setting the price: solvers compete for your swap.

People swap Bitcoin,
Zcash and dollars inside wallets they already use, NEAR settles the trade, and in
one week of November 2026 nearly all of that volume went private. The business has
customers and pricing power; NEAR does not yet keep much of what it earns.

The principle behind it is the one Hyperliquid showed for perps: liquidity gathers
in one decentralised venue and other products plug into it. THESIS.md argues the
shape, not the numbers.

- The argument, with evidence for and against: [THESIS.md](THESIS.md)
- The dashboard: `docs/` (a static page; every chart shows its query)
- Entry for NEAR HACKATHON, **thesis** track

**What it is.** A data pipeline, a paper written from its output (with figures drawn from the same numbers), and a dashboard that draws from the same output.

**The problem it solves.** NEAR's headline numbers (volume, fees, revenue) come from NEAR's own dashboards, as totals.
They do not show who pays, which front-ends are paid, or how the fees split swap by swap. This counts it from single
swaps and from the chain, and shows where the official figures and the count agree and where they don't.

## Try it: do X, see Y

No key and no packages are needed for any of these. Python 3.10 or newer.

| Do | See |
|---|---|
| `python3 -m unittest discover tests` | `Ran 22 tests` and `OK`. Works with no network. |
| `python3 -m pipeline.model` | Nine scenarios, one line each, ending with what it would take for revenue to match issuance. Works with no network. |
| `python3 -m pipeline.model --cut 0.5 --growth 2 --cap 0.016` | One line, "Your levers", with revenue and the share of issuance it covers. |
| `python3 build.py --offline` | A summary (official volume, partner swaps, fees, NEAR's share), four cross-checks and nine tripwires marked `ok` or `TRIPPED`; rewrites `docs/data.json`, `THESIS.md`, `docs/thesis.html` and the figures in `docs/figures/`. Needs network for DefiLlama and the NEAR RPC; takes a few minutes because the public nodes limit callers. |
| `python3 -m http.server -d docs 8787`, then open http://localhost:8787 | The dashboard. The strip under the header and the line beside the scorecard show the live block height, NEAR price and revenue-wallet balance, read in your browser. Each chart has a "Query" toggle with the request or SQL behind it. |
| Open `docs/exhibit-a-thesis.pdf`, or `THESIS.md`, or http://localhost:8787/thesis.html | The thesis as a whitepaper: abstract, four hypotheses, data and method, numbered equations, results with twelve figures and diagrams, the model, "The bear case", "What would change our mind", "What we couldn't pin down", a scorecard of 36 figures, and numbered references. |
| Open `queries/README.md` | Eight SQL files for Dune, each marked with where it comes from and whether we ran it or read a saved result. |

## What the track asks for, and where it is

| The track says | Here |
|---|---|
| A long-term investment thesis | [The paper (PDF)](docs/exhibit-a-thesis.pdf), the same text as [THESIS.md](THESIS.md) and at `docs/thesis.html`: the claim cut into four hypotheses, the evidence for each, the bear case, what would change our mind, what we could not pin down |
| Onchain analytics | `pipeline/history.py` reads day-by-day wallet balances, total supply and contract state from an archive node; `pipeline/chain.py` reads today's state; `queries/` has the SQL form |
| Live dashboards | `docs/` reads the chain and the price in your browser on load. A daily workflow rebuilds the rest and commits it (`.github/workflows/rebuild.yml`; its runs are in the Actions tab). The paper states the date its figures are as of |
| Models anyone can re-run | `python3 -m pipeline.model --cut 0.5 --growth 2 --cap 0.016`, and the same model as sliders on the page |
| Judged on the evidence | the numbers are written by the build; cross-checks and tripwires run and print on each build; tests cover the counting rules and the model |

## Rebuild everything

One command:

```sh
python3 build.py --offline                 # no key at all: rebuilds from the saved day totals,
                                           # for the 30 days ending at the last saved day
python3 -m http.server -d docs 8787        # then open http://localhost:8787
```

With a key it also counts new days from the API:

```sh
cp .env.example .env      # add an Explorer API key, see below
python3 build.py
```

`build.py` counts the swaps, reads the official series and the chain, runs the
model, and rewrites `docs/data.json`, `THESIS.md`, `docs/thesis.html` and the figures
in `docs/figures/`. The numbers on the page and in the thesis are written by that
one build. The exceptions are in `data/notes.json` (five figures read by hand from two
public dashboards) and a few fixed facts in the text, such as dates of changes and the
issuance cap.

Offline, the build uses the day totals in `data/days/` and the saved chain history, and
refreshes prices, the official series and today's chain state. With a key it also counts
any day not yet saved (about two minutes per new day). Other runs:

| Run | What it does |
|---|---|
| `python3 build.py --days 7` | A 7-day window |
| `python3 build.py --fresh` | Counts every day again from the API (a couple of hours) |
| `python3 -m pipeline.history 90` | Reads more on-chain history (about a minute a day) |

The Explorer API allows one request every five seconds and the public NEAR nodes
limit callers too. That is what sets the time.

## Keys

| Key | Needed | Where to get it |
|---|---|---|
| `EXPLORER_API_KEY` | Only to count days that are not already in `data/days/` | Free, from the NEAR Intents partner portal (partners.near-intents.org) |
| `DUNE_API_KEY` | Optional | With it, the build refreshes `data/confidential.csv` from NEAR's own Dune query 5179085 |

DefiLlama and the NEAR RPC need no key.

## Where each number comes from

| Source | What it gives | Code |
|---|---|---|
| NEAR Intents Explorer API | Every partner swap (completed, refunded or failed): value, assets, front-end, fee and who receives it, refunds | `pipeline/swaps.py` |
| NEAR archival RPC | Day by day: the three revenue wallets, total supply, the contract's stored state, its largest holdings | `pipeline/history.py` |
| NEAR RPC | Today: wallets, supply, the issuance setting, the protocol fee, tokens held by `intents.near` | `pipeline/chain.py` |
| DefiLlama | Official daily volume, fees and revenue (taken from NEAR's Dune dataset); volume of THORChain, Chainflip and Maya | `pipeline/official.py` |
| NEAR's saved Dune queries | Volume split into public and confidential; volume per token; swap counts | `data/confidential.csv`, `data/official_tokens.csv`, `data/official_swaps.csv`, `queries/` |
| A third party's saved Dune queries | NEAR arriving in the revenue wallets (a cross-check); what the protocol fee earns | `data/dune_wallet_inflows.csv`, `data/notes.json` |
| NEAR's revenue dashboard | How NEAR's take splits by mechanism (three shares, read by hand) | `data/notes.json` |
| The model | Revenue against new issuance under different levers, a stress test, the breakeven | `pipeline/model.py` |

The official volume counts both sides of every swap (it is a sum of volume per
token). We found that by matching it token by token against our own count, and we
compare on that basis throughout. The page shows the table.

## What is stored, and what is not

The NEAR Intents API terms (4.1(e)) say not to "cache, store, or archive API data for
more than twenty-four (24) hours". So the build never writes a swap record to disk.
Each record is added to running totals and dropped.

`data/days/*.json` holds counts and sums per day, grouped by front-end label, kind of
swap, asset and named fee-recipient account. It holds no user or deposit address, no
transaction hash and no per-swap row. Fee recipients that are bare addresses, or that
took under 0.5% of a day's fees, are summed as "(others)". On a quiet day a small group
can still be a single swap. We read the clause as covering records, not daily totals;
if NEAR reads it differently, these files will be removed.

`data/confidential.csv`, `data/official_tokens.csv` and `data/official_swaps.csv`
are copies of the saved results of NEAR's public Dune queries, read on 14 November
2026. `data/dune_wallet_inflows.csv` is a copy of a third party's saved Dune result.
`data/notes.json` holds five figures read by hand: two from a third party's saved Dune
query and three from NEAR's revenue dashboard. `data/chain_days.json` is public chain
data, read once per day and reused.

## Limits

- Before the 30-day window, history is three full days a month (the 5th, 15th and 25th).
- Dollar values are the Explorer API's own.
- Partner swaps are a little over half of official volume. Most of the rest is
  USDT and USDC moving outside the partner API. Its fees are measured by subtraction
  (official fees less partner fees). NEAR's dashboard attributes most of it to NEAR's
  own front-end; we could not confirm that from single swaps.
- The model assumes every dollar of revenue could buy NEAR.
- "Nothing public links the two" rests on NEAR's own dataset marking the volume
  confidential. The operator still sees every swap, and THESIS.md says so in the bear case.
- Our Dune account can read saved results but cannot run queries. `queries/README.md`
  says which SQL files we could not run ourselves.

## Layout

```
build.py              the one command
pipeline/             swaps, official series, chain reads, history, assemble (writes data.json),
                      model, thesis writer, figures, paper page
.github/workflows/    tests on every push; the daily rebuild
queries/              SQL for Dune, with what each one answers and whether we ran it
tests/                the counting rules, the model, the chain history
data/days/            per-day totals (counts and sums)
data/                 saved official series and the chain history
docs/                 the page: index.html, app.js, style.css, data.json
docs/thesis.html      the paper, typeset (written by the build), with paper.css
docs/exhibit-a-thesis.pdf  the paper as a PDF
docs/figures/         the paper's figures and diagrams as SVG (written by the build)
tools/make_pdf.mjs    prints the PDF from thesis.html with Chrome (the only step that is not Python)
docs/glyph/           the glyph drawing modules (field, traced solid)
THESIS.md             written by the build
```

The charts are drawn as grids of small glyphs on a plain 2D canvas, with no chart
library: readable text for what is public, rolling cipher glyphs for what is
confidential.

## Disclosures

- **Second entry by the same author.** The author also entered **Rahasya** (privacy and
  security tracks): https://rahasya.chat, https://github.com/0xyuji/rahasya. The two
  projects are independent.
- **Libraries.** No third-party libraries. The pipeline uses only Python's standard
  library. The page is plain HTML, CSS and JavaScript with no framework or chart
  library. It loads four typefaces from Google Fonts. The PDF of the paper is printed from `docs/thesis.html` by
  `tools/make_pdf.mjs`, which needs Node 22 and Google Chrome and no packages.
- **AI-written code.** Most code in this repository was written with an AI coding
  assistant (Claude Code), directed, checked and corrected by the author. The thesis
  text is generated by `pipeline/thesis.py` from the build's numbers; its wording was
  drafted with the same assistant and edited by the author.
- **Data.** Everything is read from public endpoints or with the author's own free API
  key. What is kept is described under "What is stored, and what is not".
- Not investment advice.

## Licence

MIT. See [LICENSE](LICENSE).
