"""Login and fetch one page of products to confirm seeded data via the API."""

import json
import os
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

username = os.environ.get("SEED_USER", "nbk0000000013")
password = os.environ.get("SEED_PASS", "admin-temp-123")


def post_json(url: str, payload: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode())


def get_json(url: str, token: str):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode())


status, body = post_json(f"{BASE}/api/auth/login", {"username": username, "password": password})
if status != 200:
    print(f"login -> {status} {body.get('detail', '')}")
    print("fall back to scripts/verify_seed.py (direct SQL) if the password changed")
    sys.exit(0)

token = body["access_token"]
print(f"login -> 200 as {body['user']['username']} ({body['user']['role']})")

status, stats = get_json(f"{BASE}/api/dashboard/stats", token)
print(f"GET /api/dashboard/stats -> {status}: {json.dumps(stats, ensure_ascii=False)}")

status, page = get_json(f"{BASE}/api/products?page=1", token)
print(
    f"GET /api/products?page=1 -> {status}: "
    f"total={page['total']}, pages={page['pages']}, items_on_page={len(page['items'])}"
)
for item in page["items"][:3]:
    print(
        f"   {item['brand']:12} | {item['name'][:38]:38} | ${item['price']:>8} | qty {item['quantity']}"
    )
