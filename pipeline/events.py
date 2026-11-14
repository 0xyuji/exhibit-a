"""Dates on which the charts jump, with what our data shows and what was announced.

"shows" is measured by the build. "said" is what a named public source says; we link it and
did not measure it. Where we found no source, "said" says so.
"""
CHANGELOG = "https://docs.near-intents.org/changelog/overview"


def build(data, day_totals):
    dark = {r["day"]: r for r in data["dark"]["days"] if r.get("confidential") is not None}
    share = lambda day: dark[day]["confidential"] / ((dark[day]["public"] + dark[day]["confidential"]) or 1) if day in dark else None
    volume = lambda day: dark[day]["public"] + dark[day]["confidential"] if day in dark else None
    monthly = {m["month"]: m["capture"] for m in data.get("monthly") or []}
    usd = lambda x: f"${x / 1e6:.0f}M"
    pct = lambda x: f"{x * 100:.0f}%"
    rows = []

    def add(date, shows, said, source=None, link=None):
        if shows:
            rows.append({"date": date, "shows": shows, "said": said, "source": source, "link": link})

    if "2026-01" in monthly and "2026-02" in monthly:
        add("24 Feb 2026", f"NEAR's share of gross fees goes from {pct(monthly['2026-01'])} in January to {pct(monthly['2026-02'])} in February.",
            "NEAR announces that the Intents fee switch is live: protocol fees go to NEAR, and distribution fees are shared between NEAR and its partners.",
            "NEAR blog, \"Evolving NEAR Tokenomics\"", "https://www.near.org/blog/evolving-near-tokenomics")
    first = data["dark"].get("first_day")
    if first:
        add("23 Mar 2026", "Confidential volume appears in NEAR's dataset for the first time.", "We found no announcement for that day.")
    if volume("2026-06-05"):
        add("5 Jun 2026", f"One of the largest days on record: {usd(volume('2026-06-05'))} of official volume.",
            "Zcash fell by about a third in a day after a counterfeiting bug in its Orchard pool was disclosed. NEAR Intents is a major place to swap Zcash. Nobody official has linked the two.",
            "Zcash community forum", "https://forum.zcashcommunity.com/t/the-orchard-counterfeiting-vulnerability-and-next-steps/56015")
    add("13 Jul 2026", "Confidential volume is still a small share.",
        "Confidential Intents goes live for business partners: swaps execute on a private chain with shielded balances and settle back to public NEAR.",
        "NEAR Intents changelog", CHANGELOG)
    if volume("2026-09-17"):
        add("17 Sep 2026", f"The largest day on record, {usd(volume('2026-09-17'))}, and the largest inflows to NEAR's revenue wallets.",
            "We could not confirm a cause from a source we can link.")
    if share("2026-10-27") is not None:
        add("27 Oct 2026", f"The confidential share is {pct(share('2026-10-27'))} that day.",
            "1Click swaps settle confidentially by default from this day. The API is unchanged, so integrators change nothing.",
            "NEAR Intents changelog", CHANGELOG)
    if share("2026-10-29") is not None and share("2026-11-05") is not None:
        add("29 Oct to 5 Nov 2026", f"The confidential share climbs from {pct(share('2026-10-29'))} to {pct(share('2026-11-05'))}.",
            "We found no announcement of a staged rollout. It looks like the 27 October default taking effect.")
    code = "INTENT_SUBMIT_FAILED"
    burst = {day: day_totals[day]["refund_reasons"].get(code, 0) for day in ("2026-11-04", "2026-11-05", "2026-11-06") if day in day_totals}
    if burst.get("2026-11-05"):
        done = [day_totals[day]["status"].get("SUCCESS", 0) for day in ("2026-11-03", "2026-11-04", "2026-11-05") if day in day_totals]
        add("4 and 5 Nov 2026",
            f"{burst.get('2026-11-04', 0) + burst['2026-11-05']:,} swaps are refunded with one error, {code}, against {burst.get('2026-11-06', 0)} the day after. "
            f"Completed swaps hold at {min(done):,} to {max(done):,} a day.",
            "We found no incident report. A burst of one error with completed swaps unchanged points to one sender retrying, not to users being failed. Daily totals cannot show which sender.")
    if share("2026-11-10") is not None:
        add("9 Nov 2026", f"The confidential share dips to {pct(share('2026-11-10'))} the next day.",
            "Tokens on BNB Chain, Polygon and Avalanche move to new asset IDs. We cannot say the two are related.",
            "NEAR Intents changelog", CHANGELOG)
    add("11 Nov 2026", "The partner share of official volume has not moved by the end of the window.",
        "The old Bridge API closes, and integrators are told to use the 1Click Swap API.", "NEAR Intents changelog", CHANGELOG)
    return rows
