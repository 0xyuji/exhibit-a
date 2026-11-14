"""Reads straight from NEAR: the revenue wallets, the supply, the issuance setting,
the protocol fee, and the money sitting inside the intents contract. No key needed."""
import base64
import concurrent.futures
import json
import time
import urllib.error

from .common import http_json
from .swaps import TOKENS

RPC = "https://rpc.mainnet.fastnear.com"
ARCHIVE = "https://archival-rpc.mainnet.fastnear.com"
CONTRACT = "intents.near"
WALLETS = {
    "fefundsadmin.sputnik-dao.near": "Front-end fees",
    "1csfundsadmin.sputnik-dao.near": "Partner fees",
    "buybacks.multisignature.near": "Buybacks",
}
YOCTO = 1e24
PAUSE = 0.25  # seconds between calls: the public nodes limit how fast one caller may ask


_last_call = [0.0]


def rpc(method, params, url=RPC):
    """One JSON-RPC call. Calls are spaced out and a "too many requests" reply is waited out."""
    for attempt in range(7):
        wait = PAUSE - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        try:
            reply = http_json(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=30)
            _last_call[0] = time.time()
        except urllib.error.HTTPError as error:
            _last_call[0] = time.time()
            if error.code != 429 or attempt == 6:
                raise
            time.sleep(4 * (attempt + 1))
            continue
        if "error" in reply:
            raise RuntimeError(str(reply["error"])[:200])
        return reply["result"]


def view(account, method, args, block=None, url=RPC):
    params = {
        "request_type": "call_function",
        "account_id": account,
        "method_name": method,
        "args_base64": base64.b64encode(json.dumps(args).encode()).decode(),
    }
    params.update({"block_id": block} if block else {"finality": "final"})
    return json.loads(bytes(rpc("query", params, url)["result"]).decode())


def balance(account, block=None):
    params = {"request_type": "view_account", "account_id": account}
    params.update({"block_id": block} if block else {"finality": "final"})
    return int(rpc("query", params, ARCHIVE if block else RPC)["amount"]) / YOCTO


def block_at(unix, tip):
    """The first block at or after a time, by bisection on the archive node."""
    low, high = tip["height"] - int((tip["timestamp"] / 1e9 - unix) / 0.4), tip["height"]
    while high - low > 1:
        middle = (low + high) // 2
        try:
            stamp = rpc("block", {"block_id": middle}, ARCHIVE)["header"]["timestamp"] / 1e9
        except RuntimeError:  # a height with no block
            middle += 1
            stamp = rpc("block", {"block_id": middle}, ARCHIVE)["header"]["timestamp"] / 1e9
        if stamp < unix:
            low = middle
        else:
            high = middle
    return high


def held_inside():
    """Dollar value of the tokens the intents contract holds, token by token."""
    listed = [t for t in http_json(TOKENS) if t["assetId"].startswith("nep141:") and t.get("price")]

    def one(token):
        try:
            raw = view(token["assetId"][7:], "ft_balance_of", {"account_id": CONTRACT})
            return token, int(raw) / 10 ** token["decimals"] * token["price"]
        except Exception:
            return token, None

    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        results = list(pool.map(one, listed))
    found = [(t, v) for t, v in results if v is not None]
    by_symbol = {}
    for token, value in found:
        by_symbol[token["symbol"]] = by_symbol.get(token["symbol"], 0) + value
    top = sorted(by_symbol.items(), key=lambda item: -item[1])[:8]
    return {
        "total": sum(v for _, v in found),
        "tokens_read": len(found),
        "tokens_listed": len(listed),
        "top": [{"symbol": s, "usd": v} for s, v in top],
    }


def read(window_days=30):
    tip = rpc("block", {"finality": "final"})["header"]
    config = rpc("EXPERIMENTAL_protocol_config", {"finality": "final"})
    rate = config["max_inflation_rate"]
    then = block_at(tip["timestamp"] / 1e9 - window_days * 86400, tip)
    wallets = []
    for account, label in WALLETS.items():
        wallets.append({"account": account, "label": label, "now": balance(account), "before": balance(account, then)})
    return {
        "block": tip["height"],
        "block_before": then,
        "window_days": window_days,
        "time": int(tip["timestamp"] / 1e9),
        "supply": int(tip["total_supply"]) / YOCTO,
        "max_inflation": rate[0] / rate[1],
        "protocol_version": config["protocol_version"],
        "fee_pips": view(CONTRACT, "fee", {}),
        "wallets": wallets,
        "held": held_inside(),
    }
