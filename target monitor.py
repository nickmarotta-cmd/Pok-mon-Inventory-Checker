#!/usr/bin/env python3
"""
Target Pokemon TCG Stock Monitor
----------------------------------
Searches Target.com for Pokemon trading card products (ETBs, booster boxes,
booster packs, and related merchandise), checks online/shipping availability,
and sends a push notification via ntfy.sh whenever an item flips from
out-of-stock to in-stock.

This is a MONITORING-ONLY tool. It does not add items to a cart, does not
check out, and does not bypass any login or paywall. It calls the same
public product/search endpoints Target's own website uses to render stock
badges. Those endpoints are undocumented and can change or rate-limit
without notice -- if this stops working, that's almost certainly why.

State (which TCINs we've already alerted on) is persisted to state.json so
we don't spam you with repeat notifications for the same restock.
"""

import json
import os
import sys
import time
import random
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STATE_FILE = Path(__file__).parent / "state.json"
CONFIG_FILE = Path(__file__).parent / "config.json"

# Target's public "RedSky" API key used by their own web/app frontends.
# This is the same key visible in Target.com's public network traffic.
REDSKY_API_KEY = "9f36aeafbe60771e321a7cc95a78140772ab3e96"

SEARCH_TERMS = [
    "pokemon trading card elite trainer box",
    "pokemon trading card booster box",
    "pokemon trading card booster pack",
    "pokemon trading card merchandise",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}

SEARCH_URL = "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
PRODUCT_URL = "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1"


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return default
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def load_config():
    """
    config.json fields:
      store_id   - Target store number for "pick up in store" checks (optional)
      zip        - zip code used for shipping availability
      ntfy_topic - your unique ntfy.sh topic name
    """
    cfg = load_json(CONFIG_FILE, {})
    if "ntfy_topic" not in cfg:
        print("ERROR: config.json must include 'ntfy_topic'. See README.md.")
        sys.exit(1)
    cfg.setdefault("zip", "55401")
    cfg.setdefault("store_id", None)
    return cfg


def search_products(term):
    """Search Target for a keyword, return list of (tcin, title)."""
    params = {
        "key": REDSKY_API_KEY,
        "channel": "WEB",
        "count": 48,
        "keyword": term,
        "offset": 0,
        "page": f"/s/{term.replace(' ', '+')}",
        "platform": "desktop",
        "pricing_store_id": "3991",
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [warn] search failed for '{term}': {e}")
        return []

    items = []
    try:
        products = data["data"]["search"]["products"]
        for p in products:
            tcin = p.get("tcin")
            title = p.get("item", {}).get("product_description", {}).get("title", "Unknown")
            if tcin:
                items.append((tcin, title))
    except (KeyError, TypeError) as e:
        print(f"  [warn] unexpected search response shape: {e}")
    return items


def check_stock(tcin, cfg):
    """
    Returns a dict: {"in_stock": bool, "label": str}
    Checks shipping (ship-to-address) availability for the given zip.
    """
    params = {
        "key": REDSKY_API_KEY,
        "tcin": tcin,
        "store_id": cfg.get("store_id") or "3991",
        "pricing_store_id": cfg.get("store_id") or "3991",
        "has_pricing_store_id": "true",
        "has_financing_options": "true",
        "zip": cfg["zip"],
        "state": "MN",
        "latitude": "44.98",
        "longitude": "-93.27",
        "scheduled_delivery_store_id": cfg.get("store_id") or "3991",
    }
    try:
        resp = requests.get(PRODUCT_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [warn] stock check failed for tcin {tcin}: {e}")
        return {"in_stock": False, "label": "check failed"}

    try:
        fulfillment = data["data"]["product"]["fulfillment"]
        shipping = fulfillment.get("shipping_options", {})
        avail = shipping.get("availability_status", "")
        in_stock = avail == "IN_STOCK"
        return {"in_stock": in_stock, "label": avail or "UNKNOWN"}
    except (KeyError, TypeError):
        return {"in_stock": False, "label": "UNKNOWN"}


def send_push(cfg, title, message, url=None):
    topic = cfg["ntfy_topic"]
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "high",
                **({"Click": url} if url else {}),
            },
            timeout=10,
        )
        print(f"  [notify] sent: {title}")
    except Exception as e:
        print(f"  [warn] notification failed: {e}")


def main():
    cfg = load_config()
    state = load_json(STATE_FILE, {})  # tcin -> last known in_stock bool

    all_items = {}
    for term in SEARCH_TERMS:
        print(f"Searching: {term}")
        for tcin, title in search_products(term):
            all_items[tcin] = title
        time.sleep(random.uniform(1.5, 3.0))  # be polite, avoid hammering the endpoint

    print(f"\nTracking {len(all_items)} unique products. Checking stock...\n")

    for tcin, title in all_items.items():
        result = check_stock(tcin, cfg)
        was_in_stock = state.get(tcin, False)
        now_in_stock = result["in_stock"]

        status = "IN STOCK" if now_in_stock else result["label"]
        print(f"  {tcin} | {title[:60]:<60} | {status}")

        if now_in_stock and not was_in_stock:
            url = f"https://www.target.com/p/-/A-{tcin}"
            send_push(
                cfg,
                title="Target restock!",
                message=f"{title} is back in stock.",
                url=url,
            )

        state[tcin] = now_in_stock
        time.sleep(random.uniform(1.0, 2.0))  # be polite between product checks

    save_json(STATE_FILE, state)
    print("\nDone.")


if __name__ == "__main__":
    main()
