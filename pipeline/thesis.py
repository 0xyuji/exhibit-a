"""Writes the paper (THESIS.md, docs/thesis.html and its figures) from the built numbers,
so the text can never drift from the data."""
import datetime
import os

from . import figures, paper


def usd(x):
    a = abs(x)
    if a >= 1e9:
        return f"${x / 1e9:.2f}B"
    if a >= 1e6:
        return f"${x / 1e6:.1f}M"
    if a >= 1e4:
        return f"${x / 1e3:.0f}K"
    return f"${x:,.0f}"


def pct(x, digits=0):
    return f"{x * 100:.{digits}f}%"


def long_date(day):
    return datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%-d %B %Y")


def write(d, path):
    p, o, dark, chain = d["partner"], d["official"], d["dark"], d["chain"]
    win, m = d["window"], d["model"]
    kinds = {k["name"]: k for k in d["kinds"]}
    assets = {a["name"]: a for a in d["assets"]}
    scen = {s["name"]: s for s in m["scenarios"]}
    half = scen["NEAR takes its published half of partner fees"]
    five = scen["Swaps outside the partner API pay 5 bps more"]
    capped = scen["Issuance at the 1.6% cap already voted in"]
    half_capped = scen["Published half, at the 1.6% cap"]
    gone = next((s for s in m["scenarios"] if s["name"].startswith("The largest integrator")), None)
    even = m["breakeven"]
    halved = scen["Nothing changes but volume halves"]
    sampled = [h for h in d["history"] if not h.get("average")]
    now = d["history"][-1]
    peak = lambda name: max(sampled, key=lambda h: h["kinds"].get(name, 0))
    btc, zec = peak("Bitcoin"), peak("Zcash")
    top, fee_top = p["top_front"], p["top_front_by_fees"]
    names = {"swapkit": "SwapKit", "lifi": "LI.FI", "(none)": "Unlabelled swaps"}
    top_name = names.get(top["name"], top["name"])
    fee_name = names.get(fee_top["name"], fee_top["name"])
    g = d["growth"]
    fronts = {f["name"]: f for f in d["front_ends"]}
    routed = [(label, fronts[key]) for key, label in (("lifi", "LI.FI"), ("rango", "Rango"), ("swapkit", "SwapKit")) if key in fronts]
    routers = ("aggregators that can route anywhere send swaps here ("
               + ", ".join(f"{label} {pct(f['volume_share'])}" for label, f in routed) + " of partner volume)") if routed else "wallets and aggregators route here by choice"
    issuance_near = chain["supply"] * chain["max_inflation"] * win["days"] / 365
    xrp = assets.get("XRP")

    wires = "\n".join(
        f"| {w['name']} | {pct(w['now'], 1)} | {'**tripped**' if w['tripped'] else 'not tripped'} |"
        for w in d["tripwires"]
    )
    rows = "\n".join(
        f"| {s['name']} | {usd(s['revenue'])} | {usd(s['revenue_year'])} | {pct(s['covered'], 1)} | {s['multiple']:,.0f}x |"
        for s in m["scenarios"]
    )

    months = (int(win["to"][:4]) - int(g["from_day"][:4])) * 12 + int(win["to"][5:7]) - int(g["from_day"][5:7])
    tripped = sum(1 for w in d["tripwires"] if w["tripped"])
    b, z, st = kinds["Bitcoin"], kinds["Zcash"], kinds["Stablecoin pair"]
    none_or = lambda x: "none" if x < 1 else usd(x)
    def show(k):
        v = k["value"]
        return {"usd": usd(v), "pct": pct(v, 1 if v < 0.1 or v > 1 else 0), "bps": f"{v:.0f} bps", "x": f"{v:.1f}x",
                "near": f"{v:,.0f} NEAR", "bytes": f"{v / 1e6:,.0f} MB", "num": f"{v:,.0f}"}[k["kind"]]
    score = "\n".join(f"| {k['group']} | {k['name']} | {show(k)} | {k['note']} |" for k in d["kpis"])
    growth_kpi = next((k for k in d["kpis"] if k["group"] == "Growth"), None)
    yoy = (f"\n\nOne caveat before anyone gets carried away: against a year ago, partner fees a day are only "
           f"{growth_kpi['value']:.1f}x ({growth_kpi['note']}). Most of the climb happened in 2025.") if growth_kpi else ""
    ch = d.get("chain_history") or {}
    grew = [r for r in ch.get("days", []) if r.get("state_growth") is not None]
    before_s = [r["state_growth"] for r in grew if r["day"] < "2026-11-01"]
    after_s = [r["state_growth"] for r in grew if r["day"] >= dark["switch_day"]]
    chain_para = ""
    if grew:
        chain_para = ("### 3.6 What the chain says\n\nEverything above leans on NEAR's own API. So we went to the chain, with no key and no dashboard, and read "
                      f"{len(ch['days'])} days of it from an archive node.\n\n")
        if ch.get("inflow_window") is not None and ch.get("issued_window") is not None:
            chain_para += (f"- **The wallets.** The three revenue wallets took in {ch['inflow_window']:,.0f} NEAR over the window. "
                           f"Total supply grew by {ch['issued_window']:,.0f} NEAR in the same days. That's {pct(ch['inflow_window'] / ch['issued_window'], 1)}, "
                           "from balances and supply alone. No prices involved.\n")
        else:
            chain_para += (f"- **The wallets.** The three revenue wallets hold {chain['moved']:,.0f} NEAR more than {chain['window_days']} days ago, "
                           "read from their balances.\n")
        if before_s and after_s:
            chain_para += (f"- **A meter nobody publishes.** The intents contract stores {grew[-1]['state_bytes'] / 1e9:.1f} GB of state on chain. "
                           f"It grew {sum(before_s) / len(before_s) / 1e6:.0f} MB a day before the switch and {sum(after_s) / len(after_s) / 1e6:.0f} MB a day after. "
                           "Going private did not make the public footprint smaller.\n")
        held_b = [r["holdings_usd"] for r in ch["days"] if r["day"] < "2026-11-01"]
        held_a = [r["holdings_usd"] for r in ch["days"] if r["day"] >= dark["switch_day"]]
        if held_b and held_a:
            chain_para += (f"- **The money never left.** The contract's {len(ch['tokens'])} largest holdings averaged {usd(sum(held_b) / len(held_b))} before the switch "
                           f"and {usd(sum(held_a) / len(held_a))} after, at today's prices. Volume went private; the float stayed where anyone can count it.\n")
        agree = next((c for c in d["checks"] if c["name"].startswith("Two ways")), None)
        if agree:
            chain_para += f"- **And it checks out.** {agree['detail']}\n"
    if ch.get("inflow_window") is not None and ch.get("issued_window") is not None:
        wallet_line = (f"NEAR's three revenue wallets took in {ch['inflow_window']:,.0f} NEAR in the window, "
                       f"{pct(ch['inflow_window'] / ch['issued_window'], 1)} of the net new NEAR the chain created in the same days.")
    else:
        wallet_line = (f"NEAR's three revenue wallets hold {chain['moved']:,.0f} NEAR more than {chain['window_days']} days ago. "
                       f"That's {pct(chain['moved'] / issuance_near, 1)} of what the protocol's {pct(chain['max_inflation'], 1)} issuance setting mints over the same stretch.")
    was = max((h for h in sampled if h["top"] == top["name"]), key=lambda h: h["top_share"], default=None)
    was_line = (f" (It used to be nearly the whole thing: {pct(was['top_share'])} of the volume on {long_date(was['day'])}. "
                "The crowd around it is new.)") if was and was["top_share"] > top["volume_share"] + 0.15 else ""
    mo = d.get("monthly") or []
    rising = ""
    if len(mo) >= 3:
        month_name = lambda m: datetime.datetime.strptime(m, "%Y-%m").strftime("%B %Y")
        low = min(mo[:-1], key=lambda r: r["capture"])
        rising = (f"Here's the thing, though: it's already moving. Month by month, on the official series, NEAR kept {pct(mo[0]['capture'])} of gross fees in "
                  f"{month_name(mo[0]['month'])}, {pct(low['capture'])} at the low in {month_name(low['month'])}, and {pct(mo[-1]['capture'])} in {month_name(mo[-1]['month'])}. "
                  f"Revenue went from {usd(mo[0]['revenue'])} to {usd(mo[-1]['revenue'])} a month over the same stretch. Nobody announced a new fee policy. "
                  "The number just kept going up.\n\n")
    split_line = ""
    lifi, kit = fronts.get("lifi"), fronts.get("swapkit")
    if lifi and kit and lifi["fees"] > 0 and kit["fees"] > 0:
        split_line = (f"\n\nAnd the schedule is real, for some. LI.FI charges {lifi['bps']:.0f} bps and a NEAR wallet is named on "
                      f"{pct(lifi['to_near'] / lifi['fees'])} of it, which is the published split to the decimal. SwapKit carries "
                      f"{kit['volume'] / lifi['volume']:.1f} times LI.FI's volume, charges {kit['bps']:.0f} bps, and names NEAR on "
                      f"{'none' if kit['to_near'] < 1 else pct(kit['to_near'] / kit['fees'])} of it. The biggest customer got the best deal. It usually does.")
    peers = d.get("peers")
    peers_para = ""
    if peers:
        rank = [r["name"] for r in peers["rows"]].index("NEAR Intents") + 1
        others = ", ".join(f"{r['name']} {usd(r['volume'])}" for r in peers["rows"] if not r["near"])
        peers_para = ("\n### 3.7 The neighbours\n\nIf a wallet wants to swap native Bitcoin, these are the places it can send the order. "
                      f"Over the same {win['days']} days DefiLlama shows {others}. NEAR Intents is listed at {usd(peers['reported'])}, "
                      f"which is {usd(o['swap_value'])} once you count each swap once. That makes it number {rank} of {len(peers['rows'])}.\n\n"
                      "Two honest footnotes. We halved NEAR's number and left the others as reported, because we only audited NEAR's. "
                      "And SwapKit, the biggest sender of flow here, routes to THORChain, Chainflip and Maya as well. The flow is earned every day, not owned.\n")

    cap = d.get("capture")
    cap_line = ""
    if cap:
        cap_line = (f" NEAR's own revenue dashboard ({long_date(cap['read'])}) splits what it keeps three ways, as shares of gross fees: "
                    f"{pct(cap['front_end'], 1)} from its own front-end, {pct(cap['partners'], 1)} from partners, {pct(cap['quote_improvement'], 1)} from quote improvement. "
                    f"So about {pct(cap['front_end'] / (cap['front_end'] + cap['partners'] + cap['quote_improvement']))} of NEAR's take comes from its own app. "
                    "NEAR earns more from the half it owns than from the half that made it famous.")
    tok = d.get("tokens")
    tok_line = tok_para = tok_gap = ""
    if tok:
        by_symbol = {r["symbol"]: r for r in tok["rows"]}
        named = [by_symbol[s] for s in ("XRP", "BTC", "SOL", "ZEC") if s in by_symbol]
        tok_para = ("\n\nHow do we know? Token by token, over " + str(tok["days"]) + " days, partner swaps that touch a token come to "
                    + ", ".join(f"{pct(r['share'])} of the official {r['symbol']} volume" for r in named)
                    + ". You can't get that close to a one-sided number.")
        stables = [by_symbol[s] for s in ("USDT", "USDC") if s in by_symbol]
        tok_gap = (f" {pct(tok['stable_gap_share'])} of the gap is USDT and USDC that never touches the partner API"
                   + (" (partner swaps are only " + " and ".join(f"{pct(r['share'])} of official {r['symbol']}" for r in stables) + ")" if stables else "")
                   + f". Stablecoins changing chains.\n\nAnd it does pay, just at stablecoin prices. Take partner fees out of the official fee figure and "
                   f"{usd(o['rest_fees'])} is left: about {o['rest_bps']:.0f} bps on that flow. Stablecoin pairs inside the partner API pay "
                   f"{st['bps']:.0f}. Same product, same price. What differs is who collects." + cap_line)
        tok_line = (f" {pct(tok['stable_gap_share'])} of that gap is USDT and USDC, paying about {o['rest_bps']:.0f} bps. "
                    "Useful, and NEAR's own, but stablecoin margins won't carry the token.")
        out = d.get("outside")
        if out and out["swaps"] > 0:
            tok_gap += (f"\n\nAnd it isn't whales. By NEAR's own swap counts that is roughly {out['swaps']:,.0f} swaps in {out['days']} days at about "
                        f"${out['average']:,.0f} each. Partner swaps average ${out['partner_average']:,.0f}. Ordinary-sized transfers, and a lot of them.")

    # ---- the paper's apparatus: numbered figures, tables and references ----
    figs = figures.write_all(d, os.path.join(os.path.dirname(path), "docs", "figures"))
    order = [key for key in ("mechanism", "pipeline", "units", "fronts", "payers", "growth", "dark", "inflow", "peers", "feeflow", "capture", "model") if key in figs]
    F = {key: n + 1 for n, key in enumerate(order)}

    def fig(key, caption):
        if key not in figs:
            return ""
        return f"\n![Figure {F[key]}](docs/figures/{figs[key]})\n\n**Figure {F[key]}.** {caption}\n"

    var = lambda name, sub="": f"<i>{name}</i>" + (f"<sub>{sub}</sub>" if sub else "")
    frac = lambda top, bottom: f'<span class="frac"><span>{top}</span><span>{bottom}</span></span>'
    outside_term = f"{var('I')} &minus; ({var('R', '0')} &minus; {var('c', '0')}{var('F')})"
    cap_term = f"{var('S')} &middot; {var('P')}"
    year_term = f"{var('R')} &middot; 365 / {var('T')}"
    equations = [
        (r"\text{rate} = 10^{4}\cdot\frac{F}{V}",
         f"rate = 10<sup>4</sup> &middot; {frac(var('F'), var('V'))}"),
        (r"\text{capture} = \frac{R}{G}",
         f"capture = {frac(var('R'), var('G'))}"),
        (r"N_{\text{eff}} = \frac{1}{\sum_i s_i^{2}}",
         f"{var('N', 'eff')} = {frac('1', '&Sigma;<sub><i>i</i></sub> <i>s</i><sub><i>i</i></sub><sup>2</sup>')}"),
        (r"R(c, b, g) = g\left[(R_0 - c_0 F) + cF + \frac{b}{10^{4}}V_o\right]",
         f"{var('R')}(<i>c</i>, <i>b</i>, <i>g</i>) = <i>g</i> [ ({var('R', '0')} &minus; {var('c', '0')}{var('F')}) + {var('c')}{var('F')} + {frac(var('b'), '10<sup>4</sup>')} {var('V', 'o')} ]"),
        (r"I(\kappa) = N \cdot P \cdot \frac{\kappa}{\kappa_0}",
         f"{var('I')}(<i>&kappa;</i>) = {var('N')} &middot; {var('P')} &middot; {frac('<i>&kappa;</i>', '<i>&kappa;</i><sub>0</sub>')}"),
        (r"C = \frac{R}{I}",
         f"{var('C')} = {frac(var('R'), var('I'))}"),
        (r"c^{*} = \frac{I - (R_0 - c_0 F)}{F}",
         f"<i>c</i>* = {frac(outside_term, var('F'))}"),
        (r"M = \frac{S \cdot P}{R \cdot 365 / T}",
         f"{var('M')} = {frac(cap_term, year_term)}"),
    ]
    eq = lambda n: f"$${equations[n - 1][0]} \\qquad ({n})$$"
    shares = [f["volume_share"] for f in d["front_ends"]]
    fee_shares = [f["fee_share"] for f in d["front_ends"]]
    n_eff = 1 / sum(x * x for x in shares) if shares else 0
    n_eff_fees = 1 / sum(x * x for x in fee_shares) if fee_shares else 0

    refs = [
        ("explorer", "NEAR Intents Explorer API. Every settled partner swap in the window, read with the author's key (`pipeline/swaps.py`)."),
        ("llama", "DefiLlama. Daily volume, fees and revenue for NEAR Intents, which DefiLlama takes from NEAR's own Dune dataset: api.llama.fi/summary/dexs/near-intents and api.llama.fi/summary/fees/near-intents (`pipeline/official.py`)."),
        ("split", "NEAR. Dune query 5179085, \"NEAR Intents - All-time Volume\": public and confidential volume by day. dune.com/queries/5179085 (`data/confidential.csv`)."),
        ("tokens", "NEAR. Dune query 5157527, \"NEAR Intents - Token Volume\": volume by token and day. dune.com/queries/5157527 (`data/official_tokens.csv`)."),
        ("counts", "NEAR. Dune query 4374089: swap counts by day. dune.com/queries/4374089 (`data/official_swaps.csv`)."),
        ("pip", "Third party. Dune query 9074851: what the protocol fee earns next to what front-ends charge. dune.com/queries/9074851."),
        ("inflows", "Third party. Dune query 6740088: NEAR arriving in the revenue wallets, from chain tables. dune.com/queries/6740088 (`data/dune_wallet_inflows.csv`)."),
        ("rpc", f"NEAR mainnet RPC and archival RPC (FastNEAR). Wallet balances, total supply, the issuance setting, contract holdings and contract state, {len(ch.get('days', []))} days of it (`pipeline/chain.py`, `pipeline/history.py`)."),
        ("docs", "NEAR Intents documentation: the fee schedule, and the changelog entries of 13 July, 27 October and 11 November 2026."),
        ("dash", "NEAR. Revenue dashboard, revenue.near.org: how NEAR's take splits by mechanism."),
        ("vote", "NEAR Protocol. Announcement of the issuance vote, HSP-029. x.com/NEARProtocol/status/2117338455189385533."),
        ("ledger", "Ledger. \"NEAR Intents joins Ledger Wallet via SwapKit\". ledger.com/blog-near-intents-joins-ledger-wallet-via-swapkit."),
        ("zodl", "Zodl. Swaps powered by NEAR Intents in the Zcash wallet. zodl.com/zashi-swaps-decentralized-on-ramp-is-live."),
        ("defiant", "The Defiant, 18 September 2026, on near.com. thedefiant.io/news/markets/bitcoin-81000-near-tokenization-tokens-lead-rally-sep-18-2026."),
        ("peers", "DefiLlama. Daily volume for THORChain, Chainflip and Maya (`pipeline/official.py`)."),
    ]
    R = {key: f"[{n + 1}]" for n, (key, _) in enumerate(refs)}
    ref_list = "\n".join(f"{n + 1}. {text}" for n, (_, text) in enumerate(refs))

    checks = "\n".join(f"- **{c['name']}.** {c['detail']}" for c in d["checks"])
    month_word = lambda value: datetime.datetime.strptime(value, "%Y-%m").strftime("%B %Y")
    result4 = (f" (4) And the share NEAR keeps is already rising: {pct(mo[0]['capture'])} of gross fees in {month_word(mo[0]['month'])}, "
               f"{pct(mo[-1]['capture'])} in {month_word(mo[-1]['month'])}. Nobody announced a new fee policy.") if len(mo) >= 2 else ""
    h4 = "- **H4. That share is going up.** Section 4, on the official monthly series.\n" if len(mo) >= 2 else ""
    xrp_line = (f" (XRP does have an exchange of its own and still pays {xrp['bps']:.0f} bps here. Make of that what you will.)") if xrp else ""
    bear = [
        (f"**The maths doesn't close yet.** To match issuance at today's volume NEAR would need {pct(even['cut'])} of partner fees"
         f"{', which is more than all of them' if even['cut'] > 1 else ''}. At the published half it needs {even['growth_at_half']:.1f}x the volume; "
         f"at today's cut, {even['growth_at_todays_cut']:.1f}x."),
        (f"**It's one integrator.** {fee_name} produces {pct(fee_top['fee_share'])} of partner fees, which is "
         f"{pct(p['top_front_fee_share_of_official'])} of every fee NEAR Intents reports. NEAR is named on {none_or(fee_top['to_near'])} of them. "
         "If that relationship sours, every chart here looks different."
         + (f" (Run the model with them gone: partner fees fall to {usd(gone['partner_fees'])}, and NEAR's revenue in the records doesn't move, "
            "because it was never named on those fees. Either NEAR is paid some other way, or it is giving away its biggest channel.)" if gone else "")),
        (f"**The cut may be thin for a reason.** {usd(p['to_near'])} of {usd(p['fees'])}. The partners own the customer, "
         "and whoever owns the customer sets the terms."),
        (f"**Half the volume is thin.** Counted the same way, partner swaps are {pct(p['share_of_official'])} of official volume and "
         f"{pct(p['fee_share_of_official'])} of official fees. The other {pct(1 - p['share_of_official'])} brings the remaining "
         f"{pct(1 - p['fee_share_of_official'])}.{tok_line}"),
        f"**Whales.** The largest 1% of swaps carry {pct(p['top_1pct_share'])} of partner volume.",
        (f"**The switch broke things.** On {long_date(p['worst_day']['day'])}, {pct(p['worst_day']['not_done_share'])} of swaps were refunded or failed. "
         f"Over the whole window {pct(p['not_done_share'], 1)} didn't complete. Strip out the worst days and it's {pct(p['not_done_share_calm'], 1)}... "
         "but users don't get to strip out the worst days."),
        (f"**\"Private\" has an asterisk.** Every swap we counted was read from NEAR's own Explorer API {R['explorer']}, after the switch. "
         "Users trust the operator the way they'd trust an exchange, and an exchange without identity checks carries regulatory risk "
         "that no chart here can measure."),
        (f"**It's small next to issuance.** {usd(o['revenue'])} of revenue in {win['days']} days against roughly {usd(m['today']['issuance'])} of new NEAR. "
         f"Halve the volume and cover falls to {pct(halved['covered'], 1)}."),
        (f"**The official series moved the goalposts.** DefiLlama's volume {R['llama']} counts confidential volume only from 1 September 2026, "
         "which flatters growth across that date. Worth knowing before you draw a trendline."),
    ]
    bear_list = "\n".join(f"{n + 1}. {text}" for n, text in enumerate(bear))

    text = f"""# The Exchange With No Order Book

### NEAR pivoted into a real business. Now it has to get paid for it.

**0xyuji**

[0xyuji.github.io/exhibit-a](https://0xyuji.github.io/exhibit-a/)

Version 1 · {long_date(d['built'][:10])} · data from {long_date(win['from'])} to {long_date(win['to'])}

*Every number, table and figure below is written by `python3 build.py` from the sources in Section 2. We didn't type any of them. Also as a [PDF](https://0xyuji.github.io/exhibit-a/exhibit-a-thesis.pdf) and as live charts on the [dashboard](https://0xyuji.github.io/exhibit-a/).*

## Abstract

NEAR Intents settles swaps that begin inside other companies' wallets. We counted every partner swap of a {win['days']}-day window ({p['swaps']:,} swaps, {usd(p['volume'])}) from NEAR's own API, checked the totals against the official series, and read wallet balances, token supply and contract state straight from the chain. (1) The venue has customers who pay: partners charged users {usd(p['fees'])}, {p['bps']:.0f} bps on average, and holders of coins with no exchange on their own chain supply {pct(p['utxo_fee_share'])} of those fees. (2) In about a week {pct(dark['share_last'])} of the volume went private, and daily volume didn't flinch. (3) NEAR keeps very little of it: a NEAR wallet is named on {pct(p['near_cut'])} of partner fees, and official revenue of {usd(o['revenue'])} covers {pct(m['today']['covered'], 1)} of the dollar value of new NEAR issuance.{result4} So the business is real, and what the token gets out of it is, for now, a rounding error on a fee somebody else collects. The thing to watch isn't volume. It's the cut. We argue the bear case as hard as the bull case, list {len(d['tripwires'])} things that would change our mind ({tripped} {'is' if tripped == 1 else 'are'} tripped today), and publish the code so you can re-run all of it.

## 1. Introduction

Picture someone with a hardware wallet. They hold Bitcoin, they want dollars, they tap "swap" inside the wallet's app, and a minute later it's done. They paid about {b['bps']:.0f} bps for the privilege. Ask them which blockchain did the work and you'll get a blank stare.

It was NEAR.

That's the thesis in one scene. NEAR started in AI, became a chain, went back to AI, and somewhere along the way built the thing that actually works: a venue that settles swaps which begin inside other people's wallets. It has customers who pay. It has money sitting inside it. It has an operator who sees the flow. What it doesn't have is an order book... and since early November it doesn't have much you can see on-chain either.

**Our claim: this is the business NEAR's long-term value rests on, and it's worth owning for years on one condition. NEAR has to start keeping more of what the business earns.** Partners charge users {p['bps']:.0f} bps on average. A NEAR wallet is named on {pct(p['near_cut'])} of that. The distribution is there. The pricing power is there. The capture isn't. Yet.

{fig('mechanism', "One swap, end to end. The user sees a wallet. The front-end sets the fee. Solvers quote, and NEAR Intents settles, now almost always out of public view.")}
A claim like that is easy to like and hard to check. So we cut it into pieces that can each fail.

- **H1. The venue has customers who pay.** Sections 3.1 to 3.3.
- **H2. Going private didn't cost it volume.** Section 3.4.
- **H3. NEAR keeps very little of what the venue earns.** Section 4.
{h4}
Section 5 asks what any of this is worth to the token. Section 6 is the bear case, and we'd be doing the thing we make fun of if we skipped it. Section 7 lists what would change our mind, re-tested on every build.

## 2. Data and method

### 2.1 Sources

**Table 1.** Where each number comes from.

| Source | What we take | Reference |
|---|---|---|
| NEAR Intents Explorer API | Every partner swap in the window: status, value, fees, fee recipients, the coins on each side, the referring front-end | {R['explorer']} |
| DefiLlama | Official daily volume, fees and revenue; volume of three peer venues | {R['llama']}, {R['peers']} |
| NEAR's Dune queries | Confidential volume by day, volume by token, swap counts | {R['split']}, {R['tokens']}, {R['counts']} |
| NEAR RPC and archive | Revenue-wallet balances, total supply, the issuance setting, contract holdings, contract state | {R['rpc']} |
| NEAR documentation and dashboard | The published fee schedule, dates of changes, how NEAR's take splits | {R['docs']}, {R['dash']} |

{fig('pipeline', "The whole paper is the output of one command. Sources on the left, what the build writes on the right.")}
### 2.2 Counting rules

- **A partner swap** is one record from the Explorer API. Records are de-duplicated by deposit address and memo and counted once. Dollar values are the API's own; we don't re-price them.
- **Fees** are the fees the front-end set on the swap. A fee is **named to NEAR** when its recipient is one of NEAR's three revenue wallets.
- **Kind of swap.** Two stablecoins make a stablecoin pair. Otherwise it's Bitcoin if either side is BTC, then Zcash if either side is ZEC, then "other UTXO coin" for Litecoin, Dogecoin and Bitcoin Cash, then everything else.
- **Two units of volume.** NEAR's official volume is a sum of volume per token, so one swap is in there twice, once under each coin (Section 3.5). We call the official figure halved **swap value**, and we only compare partner swaps with the official figure on the both-sides basis.
- **History.** Before the window we counted three full days a month, the 5th, 15th and 25th, from June 2025.
- **Chain reads.** Balances, supply and contract state are read at the last block of each day from an archive node. No prices are involved in those series.
- **What is kept.** The API's terms don't allow single records to be stored, so the repository holds daily totals only. A full re-run needs your own free API key; `python3 build.py --offline` rebuilds everything else from the saved totals.

{fig('units', "Why the official volume is twice the swap value. Every comparison in this paper is made in one unit or the other, never across them.")}
### 2.3 Definitions

Three ratios do most of the work below. With *F* the fees charged on a volume *V*, the rate in basis points is

{eq(1)}

With *R* NEAR's revenue and *G* the gross fees on the official series, the capture is

{eq(2)}

And with *s* the share of each front-end, the effective number of front-ends is

{eq(3)}

which is 1 when one front-end has everything and *n* when *n* of them split it evenly.

### 2.4 Checks

We don't ask you to trust our counting. The build compares its own numbers with outside ones and prints the result every time.

{checks}

### 2.5 Reproducing this paper

    python3 build.py                 # count, read the chain, run the model, write this paper
    python3 build.py --offline       # the same from saved daily totals, no key needed
    python3 -m pipeline.model --cut 0.5 --growth 2 --cap 0.016
    python3 -m unittest discover -s tests

The pipeline uses only Python's standard library. SQL for the Dune side is in `queries/`, with a note on which files we could run and which we couldn't.

## 3. Results

### 3.1 Nobody opens a NEAR app

{p['swaps']:,} partner swaps in {win['days']} days, worth {usd(p['volume'])}. Up to {g['to_fronts']} different wallets and apps sending flow on a single day. The biggest, {top_name}, carries {pct(top['volume_share'])} of it, and its fee accounts are named for Ledger, Trust, Tangem and Trezor {R['ledger']}. You may have heard of them.{was_line} Zcash's own wallet routes its swaps here too {R['zodl']}.

None of these users "use NEAR" in any way they'd recognise. That's the point. It's also the first warning: the customer belongs to the front-end (Figure {F['fronts']}). By volume the flow behaves as if it came from {n_eff:.1f} equal front-ends (Equation 3). By fees, {n_eff_fees:.1f}.
{fig('fronts', f"Partner fees by front-end, {win['days']} days. One integrator produces {pct(fee_top['fee_share'])} of them.")}
### 3.2 Who's paying?

Here's the part we didn't expect. The best customers aren't DeFi natives shuffling stablecoins. They're holders of coins that can't run a swap on their own chain.

- **Bitcoin:** {pct(b['volume_share'])} of partner volume, {pct(b['fee_share'])} of partner fees, {b['bps']:.0f} bps.
- **Zcash:** {z['bps']:.0f} bps.
- **Stablecoin pairs:** {pct(st['volume_share'])} of the volume... and {st['bps']:.0f} bps.

Bitcoin, Zcash, Litecoin, Dogecoin and Bitcoin Cash together are {pct(p['utxo_volume_share'])} of the volume and {pct(p['utxo_fee_share'])} of the fees (Figure {F['payers']}). If you hold a coin with no exchange at home, you pay up to leave. NEAR is the door.{xrp_line}
{fig('payers', "Share of partner fees (bright) against share of partner volume (dim), by what is swapped. The price follows the customer's alternatives, not the size of the flow.")}
### 3.3 From lunch money to real money

On {long_date(g['from_day'])} partners charged {usd(g['from_fees'])}. Not a typo. In this window it's {usd(g['to_fees'])} a day (Figure {F['growth']}). Front-ends active in a day went from {g['from_fronts']} to {g['to_fronts']}.

And the mix keeps rotating underneath. Bitcoin was {pct(btc['kinds']['Bitcoin'])} of partner volume on {long_date(btc['day'])}. Zcash was {pct(zec['kinds']['Zcash'])} on {long_date(zec['day'])}. Stablecoin pairs are {pct(now['kinds'].get('Stablecoin pair', 0))} now. Three different stories in {months} months, and the fees showed up for all of them. The venue doesn't need to pick the winner.{yoy}
{fig('growth', "Partner fees on each sampled day since June 2025. The last bar is the daily average of this window.")}
### 3.4 Lights out

Confidential volume first showed up on {long_date(dark['first_day'])} {R['split']}. For months it was a rounding error. In the second half of October it was {pct(dark['share_before'])} of the total. From {long_date(dark['switch_day'])}: {pct(dark['share_after'])}. On {long_date(dark['last']['day'])}: {pct(dark['share_last'])} (Figure {F['dark']}).

In about a week, the whole venue went dark.

What makes that interesting rather than alarming is that volume didn't flinch: {usd(dark['per_day_before'])} a day before, {usd(dark['per_day_after'])} a day after. NEAR's changelog dates the switch for partner swaps to 27 October 2026, and says partners didn't have to change anything {R['docs']}.

What is it, mechanically? The same changelog (13 July 2026) describes confidential swaps as executing on a private chain with shielded balances and settling back to public NEAR through a bridge. That fits what the chain shows in Section 3.6: the swaps vanished from view, the money didn't move.

To be clear about what "private" means here: private from the chain, not from the operator. More on that in the bear case.
{fig('dark', "Official volume by day. Brass is the part NEAR's dataset marks confidential. H2 holds. The venue went dark and nobody left.")}
### 3.5 The other side of the ledger

A word on the headline number, because it tripped us up for a while.

NEAR's official volume is a sum of volume per token {R['tokens']}. Swap Bitcoin for dollars and that one swap is in there twice: once under BTC, once under USDT. It isn't wrong, it's just a different unit, and DefiLlama carries it as is.{tok_para}

So what's the rest? Counted on the same basis, partner swaps are {pct(p['share_of_official'])} of official volume. The other {pct(1 - p['share_of_official'])} is not a mystery asset class. It's dollars.{tok_gap}

{chain_para}{fig('inflow', "NEAR arriving in the three revenue wallets each day, from balances at the last block of the day.")}
{peers_para}{fig('peers', f"Volume over the same {win['days']} days at venues that swap native assets between chains. NEAR's figure is halved to count each swap once; the others are as reported.")}
## 4. So where's the money?

Some of it is sitting inside. The intents contract held about {usd(chain['held']['total'])} when we built this ({chain['held']['tokens_read']} of {chain['held']['tokens_listed']} listed tokens could be read).

Some of it lands in wallets anyone can read. {wallet_line}

Put the two halves side by side (Figure {F['feeflow']}).
{fig('feeflow', f"Every fee dollar of the window. The thin green ribbon is the {pct(p['near_cut'])} of partner fees with a NEAR wallet's name on it.")}

**Table 2.** The two halves of the venue, same {win['days']} days.

| | Share of volume | Fees charged | Rate | What NEAR gets |
|---|---|---|---|---|
| Partner API (wallets, aggregators) | {pct(p['share_of_official'])} | {usd(p['fees'])} | {p['bps']:.0f} bps | named on {usd(p['to_near'])} |
| Everything else (mostly stablecoins) | {pct(1 - p['share_of_official'])} | {usd(o['rest_fees'])} | {o['rest_bps']:.0f} bps | {"booked to its own front-end, per its dashboard" if d.get('capture') else "not established"} |

Official revenue for the window is {usd(o['revenue'])}. The famous half does the volume and the pricing. The quiet half does most of the earning.

That quiet half has a name, by the way. NEAR's own front-end is near.com, which The Defiant describes as an account product built on NEAR Intents that lists perpetual futures, tokenized stocks, bonds and precious metals alongside crypto {R['defiant']}. So "becoming an exchange" isn't only a metaphor for what happens behind other people's wallets. NEAR is building the storefront too.

Now the uncomfortable number, and it's H3. Of the {usd(p['fees'])} partners charged, a NEAR wallet is named on {usd(p['to_near'])}. NEAR's own published fee schedule says it takes half {R['docs']}.{split_line}

{rising}{fig('capture', "NEAR's revenue as a share of gross fees, month by month, on the official series. H4 holds, and nobody had to announce anything.")}
## 5. What's it worth to the token?

The bull case fits in one line: **the upside is a setting, not a new market.** Take the published half and revenue goes from {usd(m['today']['revenue'])} to {usd(half['revenue'])} per {win['days']} days, from {pct(m['today']['covered'], 1)} to {pct(half['covered'], 1)} of the dollar value of new issuance. No new customers required. (The other lever, charging 5 bps more on the stablecoin half, only gets you to {pct(five['covered'], 1)}.)

There's a second lever, and this one is already pulled. On 2 November 2026 NEAR's governance voted to lower the issuance cap from 2.5% to 1.6%, phased in over two years {R['vote']}. At 1.6% today's revenue covers {pct(capped['covered'], 1)} instead of {pct(m['today']['covered'], 1)}; with the published half as well, {pct(half_capped['covered'], 1)}.

The model is four lines. Revenue in a window, as a function of NEAR's cut *c* of partner fees, an extra fee of *b* basis points on swap value outside the partner API, and volume growth *g*:

{eq(4)}

Here *R*<sub>0</sub> and *c*<sub>0</sub> are today's revenue and cut, *F* is partner fees and *V*<sub>o</sub> is swap value outside the partner API. Issuance, in dollars, at an issuance cap of *κ* against today's *κ*<sub>0</sub> = 2.5%, with *N* the net new NEAR in the window and *P* the price:

{eq(5)}

The share of issuance that revenue covers, and the cut that would cover all of it at today's volume:

{eq(6)}

{eq(7)}

Today *c*\\* is {pct(even['cut'])}. And the multiple, with *S* the supply and *T* the days in the window:

{eq(8)}

**Table 3.** Scenarios. Inputs are measured by the build; the levers are assumptions.

| Case | Revenue per {win['days']} days | Per year | Share of new issuance | All NEAR / a year of it |
|---|---|---|---|---|
{rows}
{fig('model', "The scenarios of Table 3, as the share of new issuance that revenue would cover. At today's volume nothing gets to 100% on its own.")}
The model assumes every dollar of revenue could buy NEAR and a NEAR price of ${d['price']:.2f}. Issuance is {"the net new NEAR the chain actually created in the window, read from total supply" if m.get('issuance_basis') == 'measured' else "the protocol's maximum setting"}. At today's price every NEAR in existence is worth {m['today']['multiple']:,.0f} times a year of this revenue; at the published half, {half['multiple']:,.0f} times. Nobody is buying NEAR for today's fee line.

## 6. The bear case

Evidence against. We'd be doing the thing we make fun of if we stopped at the bull case. Here's how we could be wrong, roughly in the order it worries us.

{bear_list}

## 7. What would change our mind

Every line gets re-tested on each build. {tripped} of {len(d['tripwires'])} {'is' if tripped == 1 else 'are'} tripped right now.

**Table 4.** Tripwires.

| Tripwire | Now | State |
|---|---|---|
{wires}

## 8. The Hyperliquid rhyme, and the trade

We're not going to compare numbers with Hyperliquid, because they aren't comparable. The shape is.

Hyperliquid showed what happens when the liquidity for one thing gathers in one decentralised venue. Everybody else plugs in rather than building their own, and the venue gets very hard to route around. NEAR Intents is taking that seat for moving value between chains, above all for coins with no exchange at home.

The tell is who sends the flow: {routers}. Aggregators have no loyalty, which is exactly why it matters that they keep showing up.

So what's the trade? Long the venue, with eyes open about the token. The business is real and it grew without anyone noticing. What the token gets out of it is, today, a rounding error on a fee somebody else collects. So the thing to watch isn't volume. It's the cut.

## 9. What we couldn't pin down

- Who sends the other {pct(1 - p['share_of_official'])} of official volume. We know what it's made of and roughly what it pays (Section 3.5); NEAR's dashboard points at its own front-end.
- Whether NEAR Intents gives the best price. Aggregators routing to it suggests so, but we ran no price comparison, so we aren't claiming "the best liquidity".
- Exactly how the fees on the stablecoin half split between NEAR's wallets. We get the total by subtraction and the attribution from NEAR's dashboard, not from single swaps.
- What the closing of the old Bridge API on 11 November 2026 does. NEAR's changelog tells integrators to use the 1Click API instead {R['docs']}. If some of that flow came through the old door, the partner share should rise over the next weeks. Through {long_date(win['to'])} it hadn't.
- How NEAR's dataset decides that a dollar of volume is "confidential".
- How much of NEAR's partner revenue arrives outside the swap records. NEAR's own dashboard implies somewhat more than the {pct(p['near_cut'])} named in them.
- The path between history points. Before the window we counted three days a month.
- Whether the neighbours' volumes are counted the way NEAR's is. We audited the unit of NEAR's figure only.
- Three SQL files in `queries/` are written but were never run, because the Dune account we used can read saved results and can't execute queries. Nothing in this paper depends on them.
- The scheduled daily rebuild hasn't run yet. Until it has, "live" means the chain readings in the browser plus a build made by hand.
- Dollar values are the Explorer API's own, not re-priced.

## Appendix A. The scorecard

**Table A1.** Every figure the build reports, with its basis.

| Group | Figure | Now | Basis |
|---|---|---|---|
{score}

## References

{ref_list}

## Disclosure

Not investment advice. Written for the NEAR hackathon, thesis track. This text is generated by `pipeline/thesis.py` from the build's numbers; the code and the wording were drafted with an AI coding assistant (Claude Code) and directed, checked and corrected by the author.
"""
    with open(path, "w") as handle:
        handle.write(text)
    paper.write(text, d, os.path.join(os.path.dirname(path), "docs", "thesis.html"), {latex: markup for latex, markup in equations})
