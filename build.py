#!/usr/bin/env python3
"""One command rebuilds everything:  python3 build.py

It counts partner swaps day by day from the Explorer API (days already counted are
reused), reads the official series from DefiLlama, reads NEAR itself over RPC, runs
the model and writes docs/data.json (which the page in docs/ draws from), THESIS.md,
docs/thesis.html and the figures in docs/figures/.

  python3 build.py            the last 30 full days plus three days a month of history
  python3 build.py --days 7   a shorter window (a 7-day run takes about 15 minutes cold)
  python3 build.py --fresh    count every day again instead of reusing saved totals
  python3 build.py --offline  no key at all: rebuild from the day totals saved in data/days/,
                              for the 30 days ending at the last saved day
"""
import argparse
import os
import sys

from pipeline import assemble, chain, events, history, official, swaps, thesis
from pipeline.common import ROOT, SITE, env, read_json, shift, today, write_json

RAMP = ".,:;'-+/\\|!*=%#&$@"


def bar(share, width=28):
    filled = max(0, min(width, round(share * width)))
    return "".join(RAMP[(i * 7 + filled) % len(RAMP)] for i in range(filled)).ljust(width, "·")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--offline", action="store_true", help="use only the day totals already saved; needs no key")
    args = parser.parse_args()

    print("exhibit-a build")
    print("  official series (DefiLlama)")
    llama = official.llama()
    if official.refresh_split():
        print("  confidential split refreshed from NEAR's Dune query")
    volumes, last_split = official.split(llama["volume"])
    price = official.near_price()

    # Two days back, so the official series for the last day is complete.
    end = min(shift(today(), -2), max(llama["volume"]))
    offline = args.offline or not env("EXPLORER_API_KEY")
    if offline:  # without a key no new day can be counted, so the window ends at the last saved day
        saved = sorted(name[:-5] for name in os.listdir(os.path.dirname(swaps.path_of(end))) if name.endswith(".json"))
        if saved and saved[-1] < end:
            end = saved[-1]
            print(f"  no Explorer key in use: the window ends at the last saved day, {end}")
    window = [shift(end, -offset) for offset in range(args.days - 1, -1, -1)]
    wanted = assemble.history_days(window[0]) + window
    print(f"  window {window[0]} to {window[-1]}, plus {len(wanted) - len(window)} history days")

    if offline:
        missing = [day for day in window if not os.path.exists(swaps.path_of(day))]
        if missing:
            raise SystemExit(f"No key, and no saved totals for {missing[0]} (and {len(missing) - 1} more). Add EXPLORER_API_KEY to .env.")
        wanted = [day for day in wanted if os.path.exists(swaps.path_of(day))]
        print("  no Explorer key in use: rebuilding from the saved day totals")

    totals = {}
    for day in wanted:
        cold = args.fresh or not os.path.exists(swaps.path_of(day))
        if cold:
            print(f"  counting swaps of {day} (Explorer API, one request per five seconds)", flush=True)
        totals[day] = swaps.count_day(day, fresh=args.fresh)

    print("  reading NEAR over RPC (wallets, supply, issuance, contract holdings)")
    onchain = chain.read(window_days=args.days)

    print("  on-chain history from the archive node (days already read are reused)")
    try:
        chain_days = read_json(history.OUT) if args.offline else history.read(args.days + 2, quiet=True)
    except Exception as error:  # the public archive node limits callers; the saved days still serve
        print("    archive node unavailable:", str(error)[:80])
        chain_days = read_json(history.OUT)
    data = assemble.build(totals, window, llama, volumes, onchain, price, official.tokens(), chain_days,
                          official.peers(window), official.swap_counts(), read_json(os.path.join(ROOT, "data", "notes.json"), {}),
                          official.wallet_inflows())
    data["events"] = events.build(data, totals)
    write_json(os.path.join(SITE, "data.json"), data)
    thesis.write(data, os.path.join(ROOT, "THESIS.md"))

    p, o, d, m = data["partner"], data["official"], data["dark"], data["model"]["today"]
    print()
    print(f"  {window[0]} to {window[-1]}")
    print(f"  official volume        ${o['volume']:>16,.0f}")
    print(f"  partner swaps counted  ${p['volume']:>16,.0f}   {bar(p['share_of_official'])} {p['share_of_official']:.0%} of official, both sides counted")
    print(f"  fees partners charged  ${p['fees']:>16,.0f}   {p['bps']:.1f} bps of partner volume")
    print(f"  of which named to NEAR ${p['to_near']:>16,.0f}   {bar(p['near_cut'])} {p['near_cut']:.1%}")
    print(f"  confidential, last day                     {bar(d['share_last'])} {d['share_last']:.0%}")
    print(f"  revenue against new issuance               {bar(m['covered'])} {m['covered']:.1%}")
    print()
    for check in data["checks"]:
        print(f"  [ check ] {check['name']}. {check['detail']}")
    print()
    for wire in data["tripwires"]:
        print(f"  [{'TRIPPED' if wire['tripped'] else '  ok   '}] {wire['name']}: {wire['now']:.1%} (limit {wire['limit']:.0%})")
    print()
    print("  wrote docs/data.json, THESIS.md, docs/thesis.html and docs/figures/. Open the page with:  python3 -m http.server -d docs 8787")


if __name__ == "__main__":
    sys.exit(main())
