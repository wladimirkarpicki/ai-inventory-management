"""Quick smoke-check for the SPA mount on the FastAPI origin."""
import urllib.request


def get(url: str):
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, resp.headers.get("content-type"), resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get("content-type"), err.read().decode()


for url in (
    "http://127.0.0.1:8000/",
    "http://127.0.0.1:8000/login",
    "http://127.0.0.1:8000/api/health",
    "http://127.0.0.1:8000/api/products",
):
    status, ctype, body = get(url)
    marker = ""
    if "root" in body:
        marker = " (index.html served)"
    print(f"GET {url:42} -> {status} {ctype}{marker}")
