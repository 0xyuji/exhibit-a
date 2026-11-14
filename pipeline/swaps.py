"""Counts every partner swap of one UTC day from the NEAR Intents Explorer API.

The API terms forbid keeping its records for more than 24 hours, so records are
never written to disk: each one is folded into running totals and dropped. What
is saved per day is counts and sums only: no addresses, no single swaps.
"""
import collections
import re
import sys
import time
import urllib.error
import urllib.parse

from .common import DAYS, env, http_json, read_json, unix_of, write_json
import os

API = "https://explorer.near-intents.org/api/v0/transactions"
TOKENS = "https://1click.chaindefuser.com/v0/tokens"
SPACING = 5.2  # the API allows one request every five seconds
PAGE = 1000

# The three assets NEAR's fee schedule treats as stablecoins.
STABLE = {"USDC", "USDT", "DAI"}
# Coins whose own chains cannot run a swap contract.
UTXO = {"BTC", "ZEC", "LTC", "DOGE", "BCH"}
# Wallets NEAR sweeps its revenue into.
NEAR_OWNED = {
    "buybacks.multisignature.near",
    "fefundsadmin.sputnik-dao.near",
    "1csfundsadmin.sputnik-dao.near",
}
SIZE_EDGES = [1, 10, 100, 1_000, 10_000, 100_000]

_last = [0.0]
_tokens = {}


def tokens():
    """assetId -> {symbol, same}. Read live at build time and kept in memory only."""
    if not _tokens:
        for token in http_json(TOKENS):
            symbol = re.sub(r"\(.*\)$", "", token["symbol"]).strip()
            _tokens[token["assetId"]] = {"symbol": symbol, "same": token.get("coingeckoId") or symbol}
    return _tokens


def fetch(params):
    key = env("EXPLORER_API_KEY")
    if not key:
        raise SystemExit("EXPLORER_API_KEY is missing. Copy .env.example to .env and add a key (see README).")
    while True:
        wait = SPACING - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            reply = http_json(API + "?" + urllib.parse.urlencode(params), headers={"Authorization": "Bearer " + key})
            _last[0] = time.time()
            return reply
        except urllib.error.HTTPError as error:
            _last[0] = time.time()
            if error.code in (401, 403):
                raise SystemExit(f"The Explorer API refused the key (HTTP {error.code}).")
            print(f"    explorer HTTP {error.code}, waiting", file=sys.stderr, flush=True)
            time.sleep(20)
        except Exception as error:  # network trouble: wait and try again
            _last[0] = time.time()
            print(f"    explorer {type(error).__name__}, waiting", file=sys.stderr, flush=True)
            time.sleep(20)


def records(start, end):
    """Every settled swap created in [start, end), newest first, each one once."""
    seen = set()
    cursor = end
    while cursor > start:
        page = fetch({
            "numberOfTransactions": PAGE,
            "statuses": "SUCCESS,REFUNDED,FAILED",
            "endTimestampUnix": cursor,
            "startTimestampUnix": start - 1,
        })
        if not page:
            return
        fresh = 0
        for record in page:
            mark = (record.get("depositAddress"), record.get("depositMemo"))
            if mark in seen or not (start <= record["createdAtTimestamp"] < end):
                continue
            seen.add(mark)
            fresh += 1
            yield record
        if len(page) < PAGE:
            return
        lowest = min(record["createdAtTimestamp"] for record in page)
        # Step back; the +1 keeps swaps that share the boundary second.
        cursor = lowest + 1 if (lowest < cursor - 1 or fresh) else lowest


def num(value):
    return float(value or 0)


class Day:
    """Running totals for one day."""

    def __init__(self):
        self.status = collections.Counter()
        self.refund_reasons = collections.Counter()
        self.volume = 0.0
        self.fees = 0.0
        self.fees_to_near = 0.0
        self.no_fee_volume = 0.0
        self.paid_in = 0.0
        self.paid_out = 0.0
        self.route = collections.defaultdict(lambda: [0.0, 0.0, 0])   # volume, fees, swaps
        self.kind = collections.defaultdict(lambda: [0.0, 0.0, 0])
        self.asset = collections.defaultdict(lambda: [0.0, 0.0, 0])
        self.front = collections.defaultdict(lambda: [0.0, 0.0, 0, 0.0])  # volume, fees, swaps, fees to NEAR
        self.recipient = collections.Counter()
        self.sizes = [[0, 0.0] for _ in range(len(SIZE_EDGES) + 1)]
        self.largest = []

    def add(self, record):
        self.status[record["status"]] += 1
        if record["status"] != "SUCCESS":
            if record.get("refundReason"):
                self.refund_reasons[str(record["refundReason"])[:60]] += 1
            return
        known = tokens()
        a = known.get(record["originAsset"])
        b = known.get(record["destinationAsset"])
        value = num(record.get("amountInUsd"))
        out = num(record.get("amountOutUsd"))
        fee = 0.0
        to_near = 0.0
        for part in record.get("appFees") or []:
            share = value * part["fee"] / 1e4
            fee += share
            self.recipient[part["recipient"]] += share
            if part["recipient"] in NEAR_OWNED:
                to_near += share
        self.volume += value
        self.fees += fee
        self.fees_to_near += to_near
        if not fee:
            self.no_fee_volume += value
        if value > 0 and out > 0:
            self.paid_in += value
            self.paid_out += out

        pair = {a["symbol"] if a else "?", b["symbol"] if b else "?"}
        if a and b and pair <= STABLE:
            route = "stable pair"
        elif a and b and a["same"] == b["same"]:
            route = "same asset"
        else:
            route = "cross asset"
        if route == "stable pair":
            kind = "Stablecoin pair"
        elif "BTC" in pair:
            kind = "Bitcoin"
        elif "ZEC" in pair:
            kind = "Zcash"
        elif pair & UTXO:
            kind = "Other UTXO coin"
        else:
            kind = "Everything else"
        for table, name in ((self.route, route), (self.kind, kind)):
            table[name][0] += value
            table[name][1] += fee
            table[name][2] += 1
        for symbol in pair:
            row = self.asset[symbol]
            row[0] += value
            row[1] += fee
            row[2] += 1
        row = self.front[record.get("referral") or "(none)"]
        row[0] += value
        row[1] += fee
        row[2] += 1
        row[3] += to_near

        slot = sum(1 for edge in SIZE_EDGES if value >= edge)
        self.sizes[slot][0] += 1
        self.sizes[slot][1] += value
        self.largest.append(value)
        if len(self.largest) > 4000:
            self.largest = sorted(self.largest, reverse=True)[:2000]

    def result(self):
        done = self.status.get("SUCCESS", 0)
        top = sorted(self.largest, reverse=True)[: max(1, done // 100)] if done else []
        recipients = dict(self.recipient.most_common(30))
        recipients["(others)"] = sum(self.recipient.values()) - sum(recipients.values())
        table = lambda rows, keys: {name: dict(zip(keys, values)) for name, values in rows.items()}
        return {
            "swaps": sum(self.status.values()),
            "status": dict(self.status),
            "refund_reasons": dict(self.refund_reasons.most_common(8)),
            "volume": self.volume,
            "fees": self.fees,
            "fees_to_near": self.fees_to_near,
            "no_fee_volume": self.no_fee_volume,
            "paid_in": self.paid_in,
            "paid_out": self.paid_out,
            "route": table(self.route, ("volume", "fees", "swaps")),
            "kind": table(self.kind, ("volume", "fees", "swaps")),
            "asset": table(self.asset, ("volume", "fees", "swaps")),
            "front_ends": table(self.front, ("volume", "fees", "swaps", "fees_to_near")),
            "recipients": recipients,
            "sizes": self.sizes,
            "top_1pct_volume": sum(top),
        }


def path_of(day):
    return os.path.join(DAYS, day + ".json")


def count_day(day, fresh=False):
    """Totals for one UTC day, from the saved file when there is one."""
    saved = None if fresh else read_json(path_of(day))
    if saved is not None:
        return saved
    start = unix_of(day)
    totals = Day()
    seen = 0
    for record in records(start, start + 86400):
        totals.add(record)
        seen += 1
        if seen % 5000 == 0:
            print(f"    {day}: {seen:,} swaps so far", flush=True)
    result = totals.result()
    write_json(path_of(day), result)
    return result
