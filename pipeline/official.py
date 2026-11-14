"""The official numbers: DefiLlama's daily volume, fees and revenue for NEAR Intents
(which DefiLlama takes from NEAR's own Dune dataset), the NEAR price, and NEAR's
split of volume into public and confidential."""
import csv
import os

from .common import DATA, day_of, env, http_json

LLAMA = "https://api.llama.fi/summary/{kind}/near-intents?dataType={series}"
PRICE = "https://coins.llama.fi/prices/current/coingecko:near"
# NEAR's own saved query, "NEAR Intents - All-time Volume".
DUNE_QUERY = 5179085
DUNE = "https://api.dune.com/api/v1/query/{query}/results?limit=5000"
SPLIT = os.path.join(DATA, "confidential.csv")
# NEAR's saved query 5157527, "NEAR Intents - Token Volume": volume per token and day.
TOKEN_FILE = os.path.join(DATA, "official_tokens.csv")


def series(kind, name):
    reply = http_json(LLAMA.format(kind=kind, series=name))
    return {day_of(stamp): float(value) for stamp, value in reply["totalDataChart"]}


def llama():
    return {
        "volume": series("dexs", "dailyVolume"),
        "fees": series("fees", "dailyFees"),
        "revenue": series("fees", "dailyRevenue"),
    }


def near_price():
    return float(http_json(PRICE)["coins"]["coingecko:near"]["price"])


def refresh_split():
    """Rewrites data/confidential.csv from NEAR's Dune query when a Dune key is set."""
    key = env("DUNE_API_KEY")
    if not key:
        return False
    reply = http_json(DUNE.format(query=DUNE_QUERY), headers={"X-Dune-API-Key": key})
    rows = sorted(reply["result"]["rows"], key=lambda row: row["date_at"])
    with open(SPLIT, "w", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(["date", "confidential_usd"])
        for row in rows:
            if row.get("confidential_volume_usd"):
                out.writerow([row["date_at"][:10], round(row["confidential_volume_usd"])])
    return True


# DefiLlama's volume leaves confidential volume out before this day and includes it
# from this day on (checked against NEAR's query on 13 days either side).
COUNTED_FROM = "2026-09-01"


def split(volume):
    """day -> {total, public, confidential}, from the official volume and NEAR's split."""
    with open(SPLIT) as handle:
        hidden = {row["date"]: float(row["confidential_usd"]) for row in csv.DictReader(handle)}
    out = {}
    last = max(hidden)
    for day, value in volume.items():
        dark = hidden.get(day, 0.0)
        if day > last:  # the split has not been read for this day yet
            out[day] = {"total": value, "public": None, "confidential": None}
        elif day >= COUNTED_FROM:
            out[day] = {"total": value, "public": max(value - dark, 0.0), "confidential": dark}
        else:
            out[day] = {"total": value + dark, "public": value, "confidential": dark}
    return out, last


def tokens():
    """day -> {symbol: dollars}, the official volume per token. It counts both sides of a swap."""
    out = {}
    if not os.path.exists(TOKEN_FILE):
        return out
    with open(TOKEN_FILE) as handle:
        for row in csv.DictReader(handle):
            out.setdefault(row["date"], {})[row["symbol"]] = float(row["volume_usd"])
    return out


SWAPS_FILE = os.path.join(DATA, "official_swaps.csv")


def swap_counts():
    """day -> the official number of swaps (NEAR's Dune query 4374089). Counted per token, like the volume."""
    if not os.path.exists(SWAPS_FILE):
        return {}
    with open(SWAPS_FILE) as handle:
        return {row["date"]: float(row["swaps"]) for row in csv.DictReader(handle)}


# Other venues that swap native assets between chains, as DefiLlama lists them.
PEERS = (("THORChain", "thorchain-dex"), ("Chainflip", "chainflip-amm"), ("Maya", "maya-protocol"))


def peers(days):
    """Volume of each peer venue over the same days, from DefiLlama. Missing venues are skipped."""
    out = []
    for name, slug in PEERS:
        try:
            reply = http_json(LLAMA.format(kind="dexs", series="dailyVolume").replace("near-intents", slug))
        except Exception:
            continue
        by_day = {day_of(stamp): float(value) for stamp, value in reply["totalDataChart"]}
        out.append({"name": name, "slug": slug, "volume": sum(by_day.get(day, 0) for day in days)})
    return out


INFLOW_FILE = os.path.join(DATA, "dune_wallet_inflows.csv")


def wallet_inflows():
    """day -> NEAR arriving in the revenue wallets, from SQL over chain tables (Dune query 6740088)."""
    if not os.path.exists(INFLOW_FILE):
        return {}
    with open(INFLOW_FILE) as handle:
        return {row["date"]: float(row["near"]) for row in csv.DictReader(handle)}
