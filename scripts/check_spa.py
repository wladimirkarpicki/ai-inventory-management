"""Quick smoke-check for the SPA mount on the FastAPI origin."""

import urllib.parse
import urllib.request

# Local smoke check: 5s is long enough for a cold dev server to answer and
# short enough that a hung server fails fast instead of hanging the check.
TIMEOUT = 5
# The dev origin is plain HTTP, so file:, ftp: and custom schemes are never a
# legitimate target: reject them instead of letting urlopen fetch them.
ALLOWED_SCHEMES = ("http",)
# Explicit opener: the same default handler chain urllib.request.urlopen()
# builds internally, so every request goes through open_url() and is checked.
OPENER = urllib.request.build_opener()


def open_url(req: urllib.request.Request):
    """Open one request, refusing any URL outside the permitted schemes."""
    scheme = urllib.parse.urlsplit(req.full_url).scheme
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(
            f"refusing to open {req.full_url!r}: "
            f"scheme must be {' or '.join(ALLOWED_SCHEMES)}, got {scheme!r}"
        )
    return OPENER.open(req, timeout=TIMEOUT)


def get(url: str):
    req = urllib.request.Request(url)
    try:
        resp = open_url(req)
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
