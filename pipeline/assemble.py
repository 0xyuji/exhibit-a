"""Turns the day totals, the official series and the chain reads into docs/data.json,
the one file the page draws from. Every number on the page comes from here."""
import datetime

from . import model
from .common import UTC, shift
from .swaps import NEAR_OWNED, SIZE_EDGES

FIRST_HISTORY = "2025-06"
HISTORY_DATES = (5, 15, 25)
SWITCH = ("2026-11-04", "the first day confidential volume passed 90% of the total")


def add_into(total, part):
    for key, value in part.items():
        if isinstance(value, dict):
            add_into(total.setdefault(key, {}), value)
        elif isinstance(value, list):
            base = total.setdefault(key, [[0, 0.0] for _ in value])
            for slot, (count, volume) in enumerate(value):
                base[slot][0] += count
                base[slot][1] += volume
        else:
            total[key] = total.get(key, 0) + value
    return total


def merged(days):
    total = {}
    for day in days:
        add_into(total, day)
    return total


def bps(fees, volume):
    return fees / volume * 1e4 if volume else 0.0


def history_days(window_start):
    """The 5th, 15th and 25th of every month from FIRST_HISTORY up to the window."""
    out = []
    year, month = map(int, FIRST_HISTORY.split("-"))
    while True:
        for date in HISTORY_DATES:
            day = f"{year:04d}-{month:02d}-{date:02d}"
            if day >= window_start:
                return out
            out.append(day)
        month += 1
        if month == 13:
            year, month = year + 1, 1


def rows_of(table, total_volume, total_fees, limit=None, order="volume"):
    rows = []
    for name, cell in table.items():
        rows.append({
            "name": name,
            "volume": cell["volume"],
            "fees": cell["fees"],
            "swaps": cell["swaps"],
            "bps": bps(cell["fees"], cell["volume"]),
            "volume_share": cell["volume"] / total_volume if total_volume else 0,
            "fee_share": cell["fees"] / total_fees if total_fees else 0,
            "to_near": cell.get("fees_to_near", 0.0),
            "near_bps": bps(cell.get("fees_to_near", 0.0), cell["volume"]),
        })
    rows.sort(key=lambda row: -row[order])
    return rows[:limit] if limit else rows


def short(account):
    return account if len(account) <= 28 else account[:8] + "…" + account[-6:]


def chain_history(saved, window):
    """Day-by-day series from the archival reads: wallet inflow, new state, net new NEAR, holdings."""
    known = saved.get("days", {})
    tokens = saved.get("tokens", [])
    rows = []
    for day in sorted(known):
        before = known.get(shift(day, -1))
        here = known[day]
        value = sum((here["holdings"].get(contract) or 0) * price for contract, _, _, price in tokens)
        row = {"day": day, "wallets": sum(here["wallets"].values()), "state_bytes": here["state_bytes"], "holdings_usd": value,
               "supply": here.get("supply"),
               "holdings": {symbol: (here["holdings"].get(contract) or 0) * price for contract, symbol, _, price in tokens}}
        if before:
            row["inflow"] = row["wallets"] - sum(before["wallets"].values())
            row["state_growth"] = here["state_bytes"] - before["state_bytes"]
            if here.get("supply") and before.get("supply"):
                row["issued"] = here["supply"] - before["supply"]
        rows.append(row)
    in_window = [row for row in rows if window[0] <= row["day"] <= window[-1]]
    full = len(in_window) == len(window)
    total = lambda key: sum(row[key] for row in in_window) if full and all(key in row for row in in_window) else None
    return {
        "days": rows,
        "tokens": [symbol for _, symbol, _, _ in tokens],
        "inflow_window": total("inflow"),
        "issued_window": total("issued"),
        "state_growth_window": total("state_growth"),
        "holdings_usd": rows[-1]["holdings_usd"] if rows else None,
    }


def build(day_totals, window, llama, volumes, chain, price, official_tokens=None, chain_days=None, peers=None, official_swaps=None, notes=None, sql_inflows=None):
    """day_totals: day -> totals for every counted day. window: list of the window's days."""
    days = len(window)
    span = merged([day_totals[d] for d in window])
    volume, fees = span["volume"], span["fees"]
    swaps = span["swaps"]
    done = span["status"].get("SUCCESS", 0)

    # The official volume adds up volume per token, so every swap is in it twice: once for the
    # token that went in and once for the token that came out. `both` is our count on that basis.
    official_volume = sum(volumes[d]["total"] for d in window)
    both = 2 * volume
    official_fees = sum(llama["fees"].get(d, 0) for d in window)
    official_revenue = sum(llama["revenue"].get(d, 0) for d in window)

    fronts = rows_of(span["front_ends"], volume, fees)
    kinds = rows_of(span["kind"], volume, fees)
    assets = rows_of(span["asset"], volume, fees, order="fees")
    routes = rows_of(span["route"], volume, fees)
    top_front = fronts[0]
    top_front_by_fees = max(fronts, key=lambda row: row["fees"])
    utxo = [k for k in kinds if k["name"] in ("Bitcoin", "Zcash", "Other UTXO coin")]

    recipients = [{
        "name": short(name),
        "usd": usd,
        "share": usd / fees,
        "near": name in NEAR_OWNED,
    } for name, usd in sorted(span["recipients"].items(), key=lambda item: -item[1]) if name != "(others)"][:10]

    daily = []
    for d in window:
        t = day_totals[d]
        ok = t["status"].get("SUCCESS", 0)
        daily.append({
            "day": d,
            "swaps": t["swaps"],
            "done": ok,
            "not_done": t["swaps"] - ok,
            "not_done_share": (t["swaps"] - ok) / t["swaps"] if t["swaps"] else 0,
            "volume": t["volume"],
            "fees": t["fees"],
            "to_near": t["fees_to_near"],
            "official": volumes[d]["total"],
            "both_sides": 2 * t["volume"],
            "share": 2 * t["volume"] / volumes[d]["total"] if volumes[d]["total"] else 0,
        })
    calm = [row for row in daily if row["not_done_share"] < 0.2]
    worst = max(daily, key=lambda row: row["not_done_share"])

    history = []
    for d in history_days(window[0]):
        t = day_totals.get(d)
        if not t or not t["volume"]:
            continue
        ranked = rows_of(t["front_ends"], t["volume"], t["fees"])
        history.append({
            "day": d,
            "swaps": t["swaps"],
            "volume": t["volume"],
            "fees": t["fees"],
            "bps": bps(t["fees"], t["volume"]),
            "to_near": t["fees_to_near"],
            "front_ends": len(t["front_ends"]),
            "top": ranked[0]["name"],
            "top_share": ranked[0]["volume_share"],
            "kinds": {name: cell["volume"] / t["volume"] for name, cell in t["kind"].items()},
            "official_volume": volumes.get(d, {}).get("total", 0),
            "official_fees": llama["fees"].get(d, 0),
        })
    history.append({
        "day": f"{window[0]} to {window[-1]}",
        "average": True,
        "swaps": swaps / days,
        "volume": volume / days,
        "fees": fees / days,
        "bps": bps(fees, volume),
        "to_near": span["fees_to_near"] / days,
        "front_ends": max(len(day_totals[d]["front_ends"]) for d in window),
        "top": top_front["name"],
        "top_share": top_front["volume_share"],
        "kinds": {k["name"]: k["volume_share"] for k in kinds},
        "official_volume": official_volume / days,
        "official_fees": official_fees / days,
    })
    first = history[0]

    split_known = lambda d: volumes[d]["confidential"] is not None
    dark = [{"day": d, "public": v["public"], "confidential": v["confidential"]}
            for d, v in sorted(volumes.items()) if "2026-03-01" <= d <= window[-1] and v["confidential"] is not None]
    # Before and after the switch, from the days the split is known for (not only this window).
    before = [volumes[d] for d in sorted(volumes) if "2026-10-14" <= d < "2026-11-01" and split_known(d)]
    after = [volumes[d] for d in sorted(volumes) if d >= SWITCH[0] and split_known(d)]
    share = lambda rows: sum(r["confidential"] for r in rows) / sum(r["total"] for r in rows) if rows else 0
    per_day = lambda rows: sum(r["total"] for r in rows) / len(rows) if rows else 0
    last_day = dark[-1]["day"]
    last = volumes[last_day]
    first_dark = next((row["day"] for row in dark if row["confidential"] > 0), None)

    moved = sum(w["now"] - w["before"] for w in chain["wallets"])
    inputs = {
        "days": days,
        "official_volume": official_volume,
        "partner_volume": volume,
        "rest_volume": (official_volume - both) / 2,  # swap value outside the partner API
        "partner_fees": fees,
        "fees_to_near": span["fees_to_near"],
        "revenue": official_revenue,
        "price": price,
        "supply": chain["supply"],
        "max_inflation": chain["max_inflation"],
    }
    history_block = chain_history(chain_days, window) if chain_days else None
    if history_block and history_block.get("issued_window") is not None:
        inputs["issued_near"] = history_block["issued_window"]
    inputs["top_front"] = {"name": top_front_by_fees["name"], "fees": top_front_by_fees["fees"], "to_near": top_front_by_fees["to_near"],
                           "volume": top_front_by_fees["volume"]}
    today = model.run(inputs)

    old = [h for h in history if not h.get("average") and h["day"] < "2026-01-01" and h["official_fees"] > 0]
    checks = [
        {
            "name": "The official fee figure is what partners charge",
            "detail": "On the sampled days of 2025 the fees counted from single swaps come to "
                      f"{sum(h['fees'] for h in old) / sum(h['official_fees'] for h in old) * 100:.1f}% "
                      "of the official fee figure for the same days.",
            "rows": [{"day": h["day"], "counted": h["fees"], "official": h["official_fees"]} for h in old],
        },
        {
            "name": "The revenue wallets grew by about what the official revenue says",
            "detail": f"The three wallets hold {moved:,.0f} NEAR more than {chain['window_days']} days earlier, "
                      f"about ${moved * price:,.0f} at today's price, against ${official_revenue:,.0f} of official "
                      "revenue. The gap includes price moves and anything the wallets paid out.",
        },
    ]

    tripwires = [
        {"name": "Partner swaps fall below 40% of official volume, counted the same way", "now": both / official_volume, "limit": 0.40, "bad": "below", "unit": "share"},
        {"name": "One front-end carries more than 60% of partner volume", "now": top_front["volume_share"], "limit": 0.60, "bad": "above", "unit": "share"},
        {"name": "One front-end produces more than 85% of partner fees", "now": top_front_by_fees["fee_share"], "limit": 0.85, "bad": "above", "unit": "share"},
        {"name": "NEAR is still named on under 10% of partner fees", "now": span["fees_to_near"] / fees, "limit": 0.10, "bad": "below", "unit": "share"},
        {"name": "More than 5% of swaps fail or refund on ordinary days", "now": sum(r["not_done"] for r in calm) / sum(r["swaps"] for r in calm), "limit": 0.05, "bad": "above", "unit": "share"},
        {"name": "Revenue covers under 10% of new NEAR issued", "now": today["covered"], "limit": 0.10, "bad": "below", "unit": "share"},
        {"name": "Daily volume after the switch is under 70% of before", "now": per_day(after) / per_day(before) if before and after else 1, "limit": 0.70, "bad": "below", "unit": "share"},
    ]
    for wire in tripwires:
        wire["tripped"] = wire["now"] < wire["limit"] if wire["bad"] == "below" else wire["now"] > wire["limit"]

    sizes = [{"from": ([0] + SIZE_EDGES)[i], "swaps": c, "volume": v} for i, (c, v) in enumerate(span["sizes"])]

    # Other venues for swapping native assets across chains. Ours is halved to one side of each swap.
    peers_block = None
    if peers:
        rows = [{"name": "NEAR Intents", "volume": official_volume / 2, "near": True, "note": "official volume, halved to one side"}]
        rows += [{"name": peer["name"], "volume": peer["volume"], "near": False, "note": "as DefiLlama reports it"} for peer in peers]
        rows.sort(key=lambda row: -row["volume"])
        peers_block = {"rows": rows, "reported": official_volume}

    # Do the official swap counts agree with the both-sides reading?
    counts = official_swaps or {}
    counted_days = [d for d in window if d in counts]
    count_share = (2 * sum(day_totals[d]["status"].get("SUCCESS", 0) for d in counted_days) / sum(counts[d] for d in counted_days)) if counted_days else None

    outside = None
    if counted_days:
        rest_swaps = sum(counts[d] for d in counted_days) / 2 - sum(day_totals[d]["status"].get("SUCCESS", 0) for d in counted_days)
        rest_value = (sum(volumes[d]["total"] for d in counted_days) - 2 * sum(day_totals[d]["volume"] for d in counted_days)) / 2
        outside = {"days": len(counted_days), "swaps": rest_swaps, "value": rest_value, "average": rest_value / rest_swaps if rest_swaps > 0 else 0,
                   "partner_average": volume / done}

    # Two ways of measuring the same wallets: an archive node (ours) and SQL over chain tables (a third party's).
    agree = None
    if history_block and sql_inflows:
        ours = {row["day"]: row["inflow"] for row in history_block["days"] if row.get("inflow") is not None}
        both_days = sorted(set(ours) & set(sql_inflows))
        if both_days:
            worst_gap = max(abs(ours[d] - sql_inflows[d]) for d in both_days)
            agree = {"days": len(both_days), "ours": sum(ours[d] for d in both_days), "sql": sum(sql_inflows[d] for d in both_days), "worst_gap": worst_gap}
            checks.append({
                "name": "Two ways of reading the revenue wallets agree",
                "detail": f"Over {len(both_days)} days our archive-node balances show {agree['ours']:,.0f} NEAR arriving; SQL over the chain's transfer tables "
                          f"(a third party's saved Dune query) shows {agree['sql']:,.0f}. The largest gap on any one day is "
                          + ("under 1 NEAR." if worst_gap < 1 else f"{worst_gap:,.0f} NEAR."),
            })

    small = sum(c for c, _ in span["sizes"][:3]) / done            # under $100
    large = span["sizes"][-1]                                       # $100K and up
    shares = [row["volume_share"] for row in fronts]
    hhi = sum(x * x for x in shares)
    year_ago = [h for h in history if not h.get("average") and shift(window[0], -365) <= h["day"] <= shift(window[-1], -365)]
    fees_year_ago = sum(h["fees"] for h in year_ago) / len(year_ago) if year_ago else None
    if fees_year_ago:
        ratio = (fees / days) / fees_year_ago
        tripwires.append({"name": "Partner fees a day fall below their level a year ago", "now": ratio, "limit": 1.0, "bad": "below",
                          "unit": "share", "tripped": ratio < 1.0})
    # Month by month from the official series: gross fees, NEAR's revenue, and the share NEAR keeps.
    months = {}
    for day_key, value in llama["fees"].items():
        months.setdefault(day_key[:7], [0.0, 0.0, 0])
        months[day_key[:7]][0] += value
        months[day_key[:7]][2] += 1
    for day_key, value in llama["revenue"].items():
        if day_key[:7] in months:
            months[day_key[:7]][1] += value
    this_month = shift(window[-1], 2)[:7]  # the month still running when this was built
    monthly = [{"month": m, "fees": f, "revenue": r, "capture": r / f if f else 0}
               for m, (f, r, n) in sorted(months.items()) if m < this_month and f > 0 and r > 0.005 * f][-13:]  # months with revenue on record
    if len(monthly) >= 2:
        latest, earliest = monthly[-1], monthly[0]
        tripwires.append({"name": "NEAR keeps under 20% of gross fees in the latest full month", "now": latest["capture"], "limit": 0.20,
                          "bad": "below", "unit": "share", "tripped": latest["capture"] < 0.20})
    even = model.breakeven(inputs)
    hb = history_block or {}
    notes = notes or {}

    def kpi(group, name, value, kind, note=""):
        return {"group": group, "name": name, "value": value, "kind": kind, "note": note}

    kpis = [
        kpi("Scale", "Swap value settled", official_volume / 2, "usd", f"{days} days; official volume halved, because it counts both sides"),
        kpi("Scale", "Of which partner swaps", volume, "usd", f"{both / official_volume * 100:.0f}% of the total"),
        kpi("Scale", "Partner swaps completed", done, "num", f"{done / days:,.0f} a day"),
        kpi("Scale", "Wallets and apps sending swaps", history[-1]["front_ends"], "num", "most on a single day"),
        kpi("Scale", "Swaps under $100", small, "pct", "share of completed swaps"),
        kpi("Scale", "Swaps of $100K or more", large[1] / volume, "pct", f"share of partner volume, from {large[0]:,} swaps"),
        kpi("Take", "Fees partners charge", fees, "usd", f"{bps(fees, volume):.0f} bps of partner volume"),
        kpi("Take", "All-in cost to the user", bps(span["paid_in"] - span["paid_out"], span["paid_in"]), "bps", "dollars in minus dollars out"),
        kpi("Take", "Named to a NEAR wallet", span["fees_to_near"], "usd", f"{span['fees_to_near'] / fees * 100:.1f}% of partner fees"),
        kpi("Take", "Fees on swaps outside the partner API", official_fees - fees, "usd", f"{bps(official_fees - fees, (official_volume - both) / 2):.0f} bps; official fees less partner fees"),
        kpi("Take", "NEAR's revenue, official", official_revenue, "usd", f"{bps(official_revenue, official_volume / 2):.1f} bps of swap value"),
        kpi("Concentration", "Largest front-end, share of volume", top_front["volume_share"], "pct", top_front["name"]),
        kpi("Concentration", "Largest front-end, share of fees", top_front_by_fees["fee_share"], "pct", top_front_by_fees["name"]),
        kpi("Concentration", "Front-ends that matter", 1 / hhi if hhi else 0, "x", "effective number: 1 / sum of squared volume shares"),
        kpi("Concentration", "Largest 1% of swaps", sum(day_totals[d]["top_1pct_volume"] for d in window) / volume, "pct", "share of partner volume"),
        kpi("Customers", "Coins with no exchange at home", sum(k["fee_share"] for k in utxo), "pct", f"share of fees, from {sum(k['volume_share'] for k in utxo) * 100:.0f}% of volume"),
        kpi("Customers", "Bitcoin swaps pay", next(k["bps"] for k in kinds if k["name"] == "Bitcoin"), "bps", "stablecoin pairs pay " + f"{next((k['bps'] for k in kinds if k['name'] == 'Stablecoin pair'), 0):.0f}"),
        kpi("Privacy", "Confidential share of volume", last["confidential"] / last["total"], "pct", f"on {last_day}; {share(before) * 100:.0f}% in the second half of October"),
        kpi("Reliability", "Swaps that fail or refund", sum(r["not_done"] for r in calm) / sum(r["swaps"] for r in calm), "pct", f"ordinary days; {worst['not_done_share'] * 100:.0f}% on {worst['day']}"),
    ]
    if notes.get("protocol_fee"):
        n = notes["protocol_fee"]
        kpis.append(kpi("Take", "The 1-pip protocol fee earned", n["usd"], "usd", f"30 days to {n['to']}, of ${n['gross'] / 1e6:.1f}M gross fees"))
    if fees_year_ago:
        kpis.append(kpi("Growth", "Partner fees a day, against a year ago", (fees / days) / fees_year_ago, "x", f"${fees_year_ago:,.0f} then, ${fees / days:,.0f} now"))
    then = [llama["fees"].get(shift(d, -365)) for d in window]
    if all(v is not None for v in then) and sum(then) > 0:
        kpis.append(kpi("Growth", "Official fees, against the same days a year ago", official_fees / sum(then), "x",
                        f"${sum(then) / 1e6:.1f}M then, ${official_fees / 1e6:.1f}M now; every day counted, not sampled"))
    revenue_then = [llama["revenue"].get(shift(d, -180)) for d in window]
    if all(v is not None for v in revenue_then) and sum(revenue_then) > 0:
        kpis.append(kpi("Growth", "Official revenue, against six months ago", official_revenue / sum(revenue_then), "x",
                        f"${sum(revenue_then) / 1e6:.2f}M then, ${official_revenue / 1e6:.2f}M now"))
    if count_share is not None:
        kpis.append(kpi("Scale", "Partner share of official swap count", count_share, "pct", "counted per token, like the volume"))
    if hb.get("inflow_window") is not None:
        kpis.append(kpi("Token", "NEAR into the revenue wallets", hb["inflow_window"], "near", f"{days} days, read from chain"))
    if hb.get("issued_window") is not None:
        kpis.append(kpi("Token", "Net new NEAR", hb["issued_window"], "near", f"{days} days, from total supply on chain"))
        if hb.get("inflow_window") is not None:
            kpis.append(kpi("Token", "Inflow against new supply", hb["inflow_window"] / hb["issued_window"], "pct", "both read from chain, no prices"))
    held_near = sum(w["now"] for w in chain["wallets"])
    kpis.append(kpi("Token", "NEAR in the revenue wallets", held_near, "near", f"{held_near / chain['supply'] * 100:.2f}% of supply"))
    if outside and outside["swaps"] > 0:
        kpis.append(kpi("Scale", "Swaps outside the partner API", outside["swaps"], "num", f"{outside['days']} days; ${outside['average']:,.0f} each on average, against ${outside['partner_average']:,.0f} for partner swaps"))
    kpis.append(kpi("Token", "Revenue against new issuance", today["covered"], "pct", "dollars; the model's base case"))
    kpis.append(kpi("Token", "All NEAR at today's price, over a year of this revenue", today["multiple"], "x", f"supply x ${price:.2f}, against ${today['revenue_year'] / 1e6:.1f}M a year"))
    if len(monthly) >= 2:
        kpis.append(kpi("Take", "NEAR's share of gross fees", monthly[-1]["capture"], "pct",
                        f"{monthly[-1]['month']}; it was {monthly[0]['capture'] * 100:.0f}% in {monthly[0]['month']}"))
    kpis.append(kpi("Token", "Cut that would match issuance", even["cut"], "pct", "NEAR's share of partner fees, at today's volume"))
    kpis.append(kpi("Token", "Volume that would match issuance", even["growth_at_half"], "x", "at the published half of partner fees"))
    if hb.get("state_growth_window") is not None:
        kpis.append(kpi("Scale", "New contract state", hb["state_growth_window"], "bytes", f"{days} days of intents.near storage growth"))
    if hb.get("holdings_usd") is not None:
        kpis.append(kpi("Scale", "Held by the contract, six largest tokens", hb["holdings_usd"], "usd", "at today's prices"))

    # Token by token: the official volume against partner swaps that touch the token.
    official_tokens = official_tokens or {}
    covered = [d for d in window if d in official_tokens]
    by_token = []
    if covered:
        symbols = sorted({s for d in covered for s in official_tokens[d]})
        for symbol in symbols:
            theirs = sum(official_tokens[d].get(symbol, 0) for d in covered)
            ours = sum(day_totals[d]["asset"].get(symbol, {}).get("volume", 0) for d in covered)
            by_token.append({"symbol": symbol, "official": theirs, "partner": ours, "share": ours / theirs if theirs else 0,
                             "stable": symbol in ("USDT", "USDC", "DAI")})
        by_token.sort(key=lambda row: -row["official"])
        covered_official = sum(volumes[d]["total"] for d in covered)
        covered_partner = 2 * sum(day_totals[d]["volume"] for d in covered)
        gap = covered_official - covered_partner
        stable_gap = sum(row["official"] - row["partner"] for row in by_token if row["stable"])
        tokens_block = {
            "days": len(covered), "from": covered[0], "to": covered[-1], "rows": by_token,
            "official": covered_official, "partner": covered_partner, "gap": gap,
            "stable_gap_share": stable_gap / gap if gap else 0,
            "listed_share": sum(row["official"] for row in by_token) / covered_official,
        }
    else:
        tokens_block = None

    if tokens_block:
        close = [row for row in tokens_block["rows"] if not row["stable"] and row["share"] > 0.75]
        checks.append({
            "name": "The official volume counts both sides of every swap",
            "detail": "It is a sum of volume per token, so a swap of Bitcoin for dollars is in it twice. Counting our partner "
                      "swaps the same way (every swap that touches a token), we get "
                      + ", ".join(f"{row['share'] * 100:.0f}% of the official {row['symbol']} volume" for row in close[:4])
                      + f" over {tokens_block['days']} days. A one-sided official figure could not be matched this closely. "
                      "So we compare partner swaps to the official total on the both-sides basis throughout.",
            "tokens": tokens_block["rows"],
        })


    order = ["Scale", "Take", "Customers", "Concentration", "Token", "Privacy", "Reliability", "Growth"]
    kpis.sort(key=lambda k: order.index(k["group"]))

    return {
        "built": datetime.datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"from": window[0], "to": window[-1], "days": days},
        "price": price,
        "partner": {
            "swaps": swaps,
            "done": done,
            "not_done_share": (swaps - done) / swaps,
            "not_done_share_calm": sum(r["not_done"] for r in calm) / sum(r["swaps"] for r in calm),
            "worst_day": worst,
            "refund_reasons": span.get("refund_reasons", {}),
            "volume": volume,
            "fees": fees,
            "bps": bps(fees, volume),
            "to_near": span["fees_to_near"],
            "near_cut": span["fees_to_near"] / fees,
            "no_fee_share": span["no_fee_volume"] / volume,
            "all_in_bps": bps(span["paid_in"] - span["paid_out"], span["paid_in"]),
            "front_end_count": history[-1]["front_ends"],
            "top_1pct_share": sum(day_totals[d]["top_1pct_volume"] for d in window) / volume,
            "share_of_official": both / official_volume,
            "one_side_share": volume / official_volume,
            "fee_share_of_official": fees / official_fees,
            "top_front": top_front,
            "top_front_fee_share_of_official": top_front_by_fees["fees"] / official_fees,
            "top_front_by_fees": top_front_by_fees,
            "utxo_volume_share": sum(k["volume_share"] for k in utxo),
            "utxo_fee_share": sum(k["fee_share"] for k in utxo),
        },
        "official": {"volume": official_volume, "fees": official_fees, "revenue": official_revenue,
                     "swap_value": official_volume / 2,
                     # what is left of the official fee figure once partner fees are taken out, and its rate on the rest of the flow
                     "rest_fees": official_fees - fees, "rest_value": (official_volume - both) / 2,
                     "rest_bps": bps(official_fees - fees, (official_volume - both) / 2),
                     "fee_bps": bps(official_fees, official_volume / 2), "revenue_bps": bps(official_revenue, official_volume / 2)},
        "dark": {
            "days": dark,
            "first_day": first_dark,
            "switch_day": SWITCH[0],
            "share_before": share(before),
            "share_after": share(after),
            "share_last": last["confidential"] / last["total"],
            "last": {"day": last_day, **last},
            "per_day_before": per_day(before),
            "per_day_after": per_day(after),
        },
        "daily": daily,
        "kinds": kinds,
        "routes": routes,
        "assets": assets[:12],
        "front_ends": fronts[:12],
        "recipients": recipients,
        "sizes": sizes,
        "tokens": tokens_block,
        "outside": outside,
        "monthly": monthly,
        "capture": notes.get("capture"),
        "history": history,
        "growth": {"from_day": first["day"], "from_fees": first["fees"], "to_fees": fees / days,
                   "from_fronts": first["front_ends"], "to_fronts": history[-1]["front_ends"]},
        "chain": dict(chain, moved=moved, moved_usd=moved * price),
        "model": {"inputs": inputs, "today": today, "scenarios": model.scenarios(inputs), "breakeven": model.breakeven(inputs),
                  "issuance_basis": "measured" if inputs.get("issued_near") else "setting"},
        "chain_history": history_block,
        "peers": peers_block,
        "kpis": kpis,
        "checks": checks,
        "tripwires": tripwires,
    }
