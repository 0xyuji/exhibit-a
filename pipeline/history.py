"""On-chain history, read day by day from NEAR's archival RPC. No key needed.

For the end of each UTC day it reads, at that block:
  - the NEAR held by each of the three revenue wallets,
  - how many bytes of state the intents contract stores (a measure of activity nobody reports),
  - how much of each major token the intents contract holds.

Past days never change, so each day is read once and saved in data/chain_days.json.

    python3 -m pipeline.history          # the last 60 days
    python3 -m pipeline.history 90
"""
import concurrent.futures
import os
import sys

from . import chain
from .common import DATA, http_json, read_json, shift, today, unix_of, write_json
from .swaps import TOKENS

OUT = os.path.join(DATA, "chain_days.json")
TOKENS_KEPT = 6


def block_near(unix, tip):
    """A block within a minute of a time: guess from the block rate, look, correct, repeat."""
    rate = 0.6
    height = tip["height"] - int((tip["timestamp"] / 1e9 - unix) / rate)
    last = (tip["height"], tip["timestamp"] / 1e9)
    for _ in range(8):
        try:
            header = chain.rpc("block", {"block_id": height}, chain.ARCHIVE)["header"]
            stamp = header["timestamp"] / 1e9
        except RuntimeError:  # a height with no block
            height += 1
            continue
        if abs(stamp - unix) < 60:
            return height, header
        if height != last[0] and stamp != last[1]:
            rate = max(0.3, min(1.5, (last[1] - stamp) / (last[0] - height)))
        last = (height, stamp)
        height += int((unix - stamp) / rate)
    return height, chain.rpc("block", {"block_id": height}, chain.ARCHIVE)["header"]


def major_tokens():
    """The tokens the contract holds most of today, by dollar value: [(contract, symbol, decimals, price)]."""
    listed = [t for t in http_json(TOKENS) if t["assetId"].startswith("nep141:") and t.get("price")]

    def held(token):
        try:
            raw = chain.view(token["assetId"][7:], "ft_balance_of", {"account_id": chain.CONTRACT})
            return int(raw) / 10 ** token["decimals"] * token["price"]
        except Exception:
            return 0.0

    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        values = list(pool.map(held, listed))
    ranked = sorted(zip(values, listed), key=lambda pair: -pair[0])[:TOKENS_KEPT]
    return [(t["assetId"][7:], f"{t['symbol']} ({t['blockchain']})", t["decimals"], t["price"]) for _, t in ranked]


def read_day(day, tip, tokens):
    block, header = block_near(unix_of(day) + 86400, tip)  # the end of the day
    account = chain.rpc("query", {"request_type": "view_account", "block_id": block, "account_id": chain.CONTRACT}, chain.ARCHIVE)
    holdings = {}
    for contract, symbol, decimals, _ in tokens:
        try:
            raw = chain.view(contract, "ft_balance_of", {"account_id": chain.CONTRACT}, block=block, url=chain.ARCHIVE)
            holdings[contract] = int(raw) / 10 ** decimals
        except Exception:
            holdings[contract] = None
    return {
        "block": block,
        "supply": int(header["total_supply"]) / chain.YOCTO,
        "wallets": {account_id: chain.balance(account_id, block) for account_id in chain.WALLETS},
        "state_bytes": account["storage_usage"],
        "holdings": holdings,
    }


def read(days=60, quiet=False):
    saved = read_json(OUT, {"days": {}, "tokens": []})
    tip = chain.rpc("block", {"finality": "final"})["header"]
    tokens = [tuple(t) for t in saved["tokens"]] or major_tokens()
    saved["tokens"] = [list(t) for t in tokens]
    end = shift(today(), -1)
    wanted = [shift(end, -offset) for offset in range(days - 1, -1, -1)]
    missing = [day for day in wanted if day not in saved["days"]]

    def one(day):
        try:
            return day, read_day(day, tip, tokens)
        except Exception as error:
            return day, {"error": str(error)[:120]}

    for day in reversed(missing):  # newest first, one call at a time
        day, result = one(day)
        if "error" in result:
            if not quiet:
                print("   ", day, "could not be read:", result["error"], flush=True)
            continue
        saved["days"][day] = result
        write_json(OUT, saved)
        if not quiet:
            print("   ", day, "block", result["block"], "state", f"{result['state_bytes'] / 1e9:.3f} GB", flush=True)
    return saved


if __name__ == "__main__":
    read(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
