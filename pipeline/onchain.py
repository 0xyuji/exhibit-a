"""An independent look at the chain itself: what the intents contract logged, day by day.

For each day it reads a fixed number of evenly spaced blocks (no key needed) and counts the
events `intents.near` emitted in them. Nothing here comes from NEAR's dashboards or APIs, so it
can confirm or contradict them.

    python3 -m pipeline.onchain                 # the default range, 60 blocks a day
    python3 -m pipeline.onchain 2026-10-15 2026-11-12 60
"""
import collections
import concurrent.futures
import json
import os
import sys
import time
import urllib.request

from . import chain
from .common import DATA, read_json, shift, unix_of, write_json

BLOCKS = "https://mainnet.neardata.xyz/v0/block/{height}"
CONTRACT = "intents.near"
OUT = os.path.join(DATA, "onchain.json")


def fetch(height):
    for attempt in range(8):
        try:
            request = urllib.request.Request(BLOCKS.format(height=height), headers={"user-agent": "exhibit-a-build"})
            with urllib.request.urlopen(request, timeout=40) as reply:
                return json.load(reply)
        except Exception:
            time.sleep(0.8 * (attempt + 1))
    return None


def read_block(height):
    """Counts of what the contract did in one block, or None when the block could not be read."""
    block = fetch(height) or fetch(height + 1)  # some heights have no block
    if not block:
        return None
    events = collections.Counter()
    methods = collections.Counter()
    receipts = 0
    for shard in block.get("shards", []):
        for item in shard.get("receipt_execution_outcomes", []):
            receipt = item["receipt"]
            if receipt.get("receiver_id") != CONTRACT:
                continue
            receipts += 1
            for action in receipt.get("receipt", {}).get("Action", {}).get("actions", []):
                if "FunctionCall" in action:
                    methods[action["FunctionCall"]["method_name"]] += 1
            for line in item["execution_outcome"]["outcome"]["logs"]:
                if not line.startswith("EVENT_JSON:"):
                    continue
                try:
                    event = json.loads(line[11:])
                except ValueError:
                    continue
                name = f"{event.get('standard')}/{event.get('event')}"
                events[name] += 1
                if name == "dip4/token_diff":  # one entry per account whose balances changed in a swap
                    events["token_diff accounts"] += len(event.get("data") or [])
    return receipts, events, methods


def count_day(day, per_day, tip):
    start = chain.block_at(unix_of(day), tip)
    end = chain.block_at(unix_of(day) + 86400, tip)
    heights = [start + (end - start) * i // per_day for i in range(per_day)]
    total = {"blocks": 0, "blocks_in_day": end - start, "receipts": 0, "events": collections.Counter(), "methods": collections.Counter()}
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        for result in pool.map(read_block, heights):
            if result is None:
                continue
            receipts, events, methods = result
            total["blocks"] += 1
            total["receipts"] += receipts
            total["events"].update(events)
            total["methods"].update(methods)
    total["events"] = dict(total["events"])
    total["methods"] = dict(total["methods"])
    return total


def main():
    first = sys.argv[1] if len(sys.argv) > 1 else "2026-10-15"
    last = sys.argv[2] if len(sys.argv) > 2 else "2026-11-12"
    per_day = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    saved = read_json(OUT, {})
    tip = chain.rpc("block", {"finality": "final"})["header"]
    day = first
    while day <= last:
        if saved.get(day, {}).get("blocks", 0) < per_day * 0.6:
            saved[day] = count_day(day, per_day, tip)
            write_json(OUT, saved)
            got = saved[day]
            print(day, "blocks", got["blocks"], "receipts", got["receipts"], {k: v for k, v in sorted(got["events"].items())}, flush=True)
        day = shift(day, 1)


if __name__ == "__main__":
    main()
