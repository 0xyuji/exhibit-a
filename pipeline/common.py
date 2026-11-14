"""Shared helpers: paths, the .env reader, dates and a small HTTP client."""
import datetime
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DAYS = os.path.join(DATA, "days")
SITE = os.path.join(ROOT, "docs")
UTC = datetime.timezone.utc


def env(name):
    """A setting from the environment or from .env in the project root. Never printed."""
    if os.environ.get(name):
        return os.environ[name].strip()
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def http_json(url, body=None, headers=None, timeout=60):
    head = {"user-agent": "exhibit-a-build", "accept": "application/json"}
    head.update(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        head["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=head)
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.load(reply)


def day_of(unix):
    return datetime.datetime.fromtimestamp(unix, UTC).strftime("%Y-%m-%d")


def unix_of(day):
    return int(datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())


def today():
    return datetime.datetime.now(UTC).strftime("%Y-%m-%d")


def shift(day, days):
    return day_of(unix_of(day) + days * 86400)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as handle:
        return json.load(handle)


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.write("\n")
