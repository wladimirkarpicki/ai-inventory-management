"""
Security response headers.

The hardening middleware is registered before the routers, so it is the
outermost layer of the app: it must attach the full header set to API
JSON, the SPA shell and in-app error responses alike. These tests pin
every expected value on each of those response kinds.
"""

import pytest
from conftest import ADMIN_PASSWORD, ADMIN_USERNAME
from fastapi.testclient import TestClient

import main as main_module


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# The exact values every response must carry.
EXPECTED_CSP = (
    "default-src 'self'; "
    "object-src 'none'; "
    "upgrade-insecure-requests; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

EXPECTED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": EXPECTED_CSP,
}


def _assert_headers(response):
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers[name] == value, name


@pytest.mark.parametrize("name", sorted(EXPECTED_HEADERS))
def test_api_endpoint_carries_every_security_header(name):
    """The public liveness endpoint is a plain JSON response; each of the
    nine header/directive values must ride on it exactly."""

    response = TestClient(main_module.app).get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers[name] == EXPECTED_HEADERS[name]


def test_authenticated_api_endpoint_carries_every_security_header():
    """An authenticated JSON response (bearer token resolved against the
    throwaway database) gets the same treatment as the public one."""

    api = TestClient(main_module.app)
    setup = api.post(
        "/api/auth/setup",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert setup.status_code == 200

    response = api.get("/api/auth/me", headers=_bearer(setup.json()["access_token"]))

    assert response.status_code == 200
    _assert_headers(response)


def test_spa_shell_route_carries_every_security_header():
    """The SPA shell (index.html served for "/") is HTML, not JSON, and
    must carry the same header set — the CSP's same-origin policy is what
    keeps the built SPA's /assets/* loads legal."""

    response = TestClient(main_module.app).get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    _assert_headers(response)


def test_spa_client_side_route_falls_back_to_the_shell_with_headers():
    """A hard refresh on a client-side route serves the same shell."""

    response = TestClient(main_module.app).get("/login")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    _assert_headers(response)


def test_error_responses_carry_every_security_header():
    """In-app error pages are responses too. Every class the app raises —
    401 from the bearer guard, 404 from a missing order, 422 from request
    validation and 405 from a wrong method — must come back with the full
    header set, which is only possible because the middleware runs
    outside the routers."""

    api = TestClient(main_module.app)
    setup = api.post(
        "/api/auth/setup",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    token = setup.json()["access_token"]

    cases = [
        api.get("/api/users"),  # 401: no bearer token
        api.post("/api/orders/999999/cancel", headers=_bearer(token)),  # 404: no such order
        api.post("/api/auth/login"),  # 422: body failed validation
        api.post("/api/health"),  # 405: method not allowed on a GET route
    ]
    statuses = [response.status_code for response in cases]

    assert statuses == [401, 404, 422, 405]

    for response in cases:
        _assert_headers(response)


def test_unmatched_api_path_still_carries_every_security_header():
    """An unmatched path is answerable by the SPA catch-all (index.html,
    200) once a build exists and by the router 404 without one; either
    way the header set must be attached, because the middleware sits
    outside both."""

    api = TestClient(main_module.app)

    response = api.get("/api/does-not-exist")

    assert response.status_code in (200, 404)
    _assert_headers(response)


def test_security_headers_present_on_rejected_order_replay():
    """An app-level error (re-receiving an order that is no longer open —
    400 "Order is 'received', not open for receiving.") is not a framework
    error; the header set must not depend on how the error was produced.
    The 409 race path only fires between two concurrent receives."""

    api = TestClient(main_module.app)
    setup = api.post(
        "/api/auth/setup",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    headers = _bearer(setup.json()["access_token"])

    brand = api.post("/api/brands", json={"name": "Acme"}, headers=headers).json()
    product = api.post(
        "/api/products",
        json={"name": "Widget", "brand_id": brand["id"], "price": "5.00", "quantity": 10},
        headers=headers,
    ).json()
    order = api.post(
        "/api/orders",
        json={"product_id": product["id"], "qty": 2},
        headers=headers,
    ).json()

    first = api.post(f"/api/orders/{order['id']}/receive", headers=headers)
    second = api.post(f"/api/orders/{order['id']}/receive", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 400
    _assert_headers(second)
