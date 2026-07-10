"""
mock_service.py — a single mock microservice standing in for every
"application" listed in config/api_specs.json (Auth, Payment, User Profile,
Search, Database).

Why one service for everything: api_specs.json still models real region/env
base URLs per application (so the config shape matches what you'd use in
production), but for local testing every one of those URLs points at this
single mock instance on http://localhost:9000 — see the "note" field seeded
into api_specs.json's applications.

Run it alongside app.py:
    python3 mock_service.py     # listens on :9000
    python3 app.py              # listens on :8000

Each endpoint below deliberately returns different status codes depending on
the request, so both the "positive" and "negative" scenarios AutoBot
generates have something real to assert against:
  - valid request                       -> 200
  - missing/invalid required field       -> 400
  - missing/invalid Authorization header -> 401
  - unknown resource id (profile update) -> 404
"""
from flask import Flask, request, jsonify
import uuid

app = Flask(__name__)


def _needs_auth():
    """Simple mock auth check: any 'Authorization: Bearer <non-empty>' passes."""
    auth = request.headers.get("Authorization", "")
    return not auth.startswith("Bearer ") or len(auth) <= len("Bearer ")


# ── Auth Service ──────────────────────────────────────────────────────────
@app.route("/api/v1/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    if not body.get("username") or not body.get("password"):
        return jsonify(error="username and password are required"), 400
    if body.get("password") == "wrong":
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=str(uuid.uuid4()), expires_in=3600), 200


@app.route("/api/v1/auth/token/refresh", methods=["POST"])
def refresh_token():
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    body = request.get_json(silent=True) or {}
    if not body.get("refresh_token"):
        return jsonify(error="refresh_token is required"), 400
    return jsonify(token=str(uuid.uuid4()), expires_in=3600), 200


# ── Payment ───────────────────────────────────────────────────────────────
@app.route("/api/v1/payments/charge", methods=["POST"])
def charge():
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    body = request.get_json(silent=True) or {}
    if not body.get("amount") or not body.get("payment_method_id"):
        return jsonify(error="amount and payment_method_id are required"), 400
    return jsonify(charge_id=str(uuid.uuid4()), status="succeeded", amount=body["amount"]), 200


@app.route("/api/v1/checkout/session", methods=["POST"])
def checkout_session():
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    body = request.get_json(silent=True) or {}
    if not body.get("cart_id"):
        return jsonify(error="cart_id is required"), 400
    return jsonify(session_id=str(uuid.uuid4()), checkout_url="/checkout/" + str(uuid.uuid4())), 200


# ── User Profile ──────────────────────────────────────────────────────────
_KNOWN_USER_IDS = {"1", "2", "3", "demo-user"}

@app.route("/api/v1/users/<user_id>", methods=["PUT"])
def update_profile(user_id):
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    if user_id not in _KNOWN_USER_IDS:
        return jsonify(error=f"user {user_id} not found"), 404
    body = request.get_json(silent=True) or {}
    if "email" in body and "@" not in body["email"]:
        return jsonify(error="invalid email"), 400
    return jsonify(id=user_id, **body), 200


# ── Search ────────────────────────────────────────────────────────────────
@app.route("/api/v1/search", methods=["GET"])
def search():
    q = request.args.get("q")
    if not q:
        return jsonify(error="query param 'q' is required"), 400
    page = request.args.get("page", "1")
    if not page.isdigit() or int(page) < 1:
        return jsonify(error="page must be a positive integer"), 400
    return jsonify(query=q, page=int(page), results=[{"id": i, "title": f"{q} result {i}"} for i in range(1, 4)]), 200


# ── Database ──────────────────────────────────────────────────────────────
@app.route("/api/v1/health/db", methods=["GET"])
def db_health():
    return jsonify(status="ok", collation="utf8mb4_unicode_ci"), 200


@app.route("/health")
def health():
    return jsonify(status="ok", service="mock-microservice"), 200


if __name__ == "__main__":
    print("Mock microservice running on http://localhost:9000")
    print("Endpoints: /api/v1/auth/login, /api/v1/auth/token/refresh,")
    print("           /api/v1/payments/charge, /api/v1/checkout/session,")
    print("           /api/v1/users/<id>, /api/v1/search, /api/v1/health/db")
    app.run(host="0.0.0.0", port=9000)
