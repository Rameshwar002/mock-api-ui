@app.route("/api/v1/vehicle/<vin>/remote/stop", methods=["POST"])
def remote_stop(vin):
    """Step 1 of the flow for stop — same pattern as start."""

    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401

    state = _vehicle_or_404(vin)

    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404

    if not state["engineOn"]:
        return jsonify(error="engine is not running"), 409

    # Get request body
    body = request.get_json(silent=True)

    # Convert string JSON to dictionary
    if isinstance(body, str):
        try:
            import json
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = {}

    # Make sure body is a dictionary
    if not isinstance(body, dict):
        body = {}

    simulate_failure = bool(body.get("simulateFailure", False))

    cmd = _new_command(vin, "ENGINE_STOP")

    threading.Thread(
        target=_process_command_async,
        args=(
            cmd["commandId"],
            vin,
            "ENGINE_STOP",
            simulate_failure
        ),
        daemon=True,
    ).start()

    return jsonify(
        commandId=cmd["commandId"],
        vin=vin,
        type="ENGINE_STOP",
        status="PENDING",
        requestedAt=cmd["requestedAt"]
    ), 202

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
import threading
import time
from datetime import datetime

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


# ── Connected Vehicle Services (CVS) — remote commands + service activation ──
# In-memory per-VIN state so remote commands behave realistically: you can't
# remote-start an already-running engine, can't lock with the doors open,
# can't activate a service that's already active, etc. This is what gives
# generated positive/negative tests something real and stateful to assert
# against, not just static request validation.
_KNOWN_VINS = {"1HGCM82633A004352", "5YJ3E1EA7JF000123", "JTDKARFP9J3061234"}
_REMOTE_PIN = "1234"
_KNOWN_SERVICES = {"REMOTE_START", "WIFI_HOTSPOT", "STOLEN_VEHICLE_LOCATOR", "REMOTE_DIAGNOSTICS"}

_vehicle_state = {
    vin: {"locked": True, "engineOn": False, "doorsOpen": False, "activeServices": ["REMOTE_START"]}
    for vin in _KNOWN_VINS
}


def _vehicle_or_404(vin):
    if vin not in _KNOWN_VINS:
        return None
    return _vehicle_state.setdefault(vin, {"locked": True, "engineOn": False, "doorsOpen": False, "activeServices": []})


@app.route("/api/v1/_reset", methods=["POST"])
def reset_state():
    """Reset all in-memory vehicle state back to its initial defaults.
    Vehicle state persists across calls (that's what makes 409 conflicts
    realistic), which also means re-running the same positive test twice in
    a row will fail the second time unless state is reset in between. Call
    this before a repeat run for reproducibility."""
    global _vehicle_state, _commands
    _vehicle_state = {
        vin: {"locked": True, "engineOn": False, "doorsOpen": False, "activeServices": ["REMOTE_START"]}
        for vin in _KNOWN_VINS
    }
    _commands = {}
    return jsonify(status="ok", reset=list(_KNOWN_VINS)), 200



# ── REMOTE ENGINE START/STOP — real asynchronous command flow ───────────────
# This models how a real connected-vehicle system actually works: the cloud
# does NOT talk to the vehicle synchronously inside the HTTP request. It:
#   1. Validates the request immediately (auth, PIN, vehicle preconditions)
#      and rejects it right away if anything's wrong (400/401/403/404/409).
#   2. If valid, creates a Command record (status PENDING) and returns
#      immediately (202 Accepted) with a commandId — it has NOT yet reached
#      the vehicle.
#   3. In the background, the command is "dispatched" over the simulated
#      cellular channel to the vehicle (status -> DISPATCHED), the vehicle
#      "executes" it, and acks back (status -> COMPLETED or FAILED). Only at
#      COMPLETED does the vehicle's actual engine state change.
#   4. The mobile app polls GET .../remote/commands/{commandId} until the
#      status is terminal (COMPLETED, FAILED, or CANCELLED).
#
# State machine:
#   PENDING --(dispatch, ~1s)--> DISPATCHED --(vehicle executes, ~1.5s)--> COMPLETED
#                                                                      \--> FAILED
#   PENDING --(user cancels)--> CANCELLED   (cancellation is only allowed
#                                             before dispatch — once a real
#                                             vehicle has been sent the
#                                             command, it can't be recalled)
_commands = {}  # commandId -> command record (shared in-memory "command log")

_DISPATCH_DELAY_S = 1.0   # simulated cellular network handshake time
_EXECUTE_DELAY_S  = 1.5   # simulated time for the vehicle to physically act


def _new_command(vin, cmd_type):
    cmd_id = str(uuid.uuid4())
    _commands[cmd_id] = {
        "commandId": cmd_id, "vin": vin, "type": cmd_type, "status": "PENDING",
        "requestedAt": datetime.utcnow().isoformat() + "Z",
        "dispatchedAt": None, "completedAt": None, "failureReason": None,
    }
    return _commands[cmd_id]


def _process_command_async(command_id, vin, cmd_type, simulate_failure):
    """Runs in a background thread — simulates the real round trip: cloud
    dispatches to the vehicle over cellular, the vehicle executes the
    physical action, then acks back. This is deliberately NOT instant, so a
    test polling the status endpoint actually observes PENDING ->
    DISPATCHED -> a terminal state, the same way a real mobile app would."""
    time.sleep(_DISPATCH_DELAY_S)
    cmd = _commands.get(command_id)
    if not cmd or cmd["status"] == "CANCELLED":
        return  # cancelled before we even reached the vehicle
    cmd["status"] = "DISPATCHED"
    cmd["dispatchedAt"] = datetime.utcnow().isoformat() + "Z"

    time.sleep(_EXECUTE_DELAY_S)
    cmd = _commands.get(command_id)
    if not cmd or cmd["status"] == "CANCELLED":
        return

    if simulate_failure:
        cmd["status"] = "FAILED"
        cmd["failureReason"] = "Vehicle did not acknowledge the command (simulated failure)"
    else:
        cmd["status"] = "COMPLETED"
        state = _vehicle_state.get(vin)
        if state is not None:
            if cmd_type == "ENGINE_START":
                state["engineOn"] = True
            elif cmd_type == "ENGINE_STOP":
                state["engineOn"] = False
    cmd["completedAt"] = datetime.utcnow().isoformat() + "Z"


@app.route("/api/v1/vehicle/<vin>/remote/start", methods=["POST"])
def remote_start(vin):
    """Step 1 of the flow: mobile app submits a start request. Validated
    and accepted immediately (202) — the vehicle hasn't received it yet."""
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    body = request.get_json(silent=True) or {}
    pin = body.get("pin")
    if not pin:
        return jsonify(error="pin is required"), 400
    if pin != _REMOTE_PIN:
        return jsonify(error="invalid PIN"), 403
    if "REMOTE_START" not in state["activeServices"]:
        return jsonify(error="Remote Start service is not active on this vehicle"), 403
    if state["engineOn"]:
        return jsonify(error="engine is already running"), 409
    if state["doorsOpen"]:
        return jsonify(error="cannot remote start while a door is open"), 409

    cmd = _new_command(vin, "ENGINE_START")
    threading.Thread(
        target=_process_command_async,
        args=(cmd["commandId"], vin, "ENGINE_START", bool(body.get("simulateFailure"))),
        daemon=True,
    ).start()
    return jsonify(commandId=cmd["commandId"], vin=vin, type="ENGINE_START",
                    status="PENDING", requestedAt=cmd["requestedAt"]), 202


@app.route("/api/v1/vehicle/<vin>/remote/stop", methods=["POST"])
def remote_stop(vin):
    """Step 1 of the flow for stop — same pattern as start."""
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    if not state["engineOn"]:
        return jsonify(error="engine is not running"), 409

    body = request.get_json(silent=True) or {}
    cmd = _new_command(vin, "ENGINE_STOP")
    threading.Thread(
        target=_process_command_async,
        args=(cmd["commandId"], vin, "ENGINE_STOP", bool(body.get("simulateFailure"))),
        daemon=True,
    ).start()
    return jsonify(commandId=cmd["commandId"], vin=vin, type="ENGINE_STOP",
                    status="PENDING", requestedAt=cmd["requestedAt"]), 202


@app.route("/api/v1/vehicle/<vin>/remote/commands/<command_id>", methods=["GET"])
def get_command_status(vin, command_id):
    """Step 2 of the flow: mobile app polls this repeatedly until status is
    terminal (COMPLETED, FAILED, or CANCELLED)."""
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    cmd = _commands.get(command_id)
    if not cmd or cmd["vin"] != vin:
        return jsonify(error=f"command {command_id} not found for vehicle {vin}"), 404
    return jsonify(**cmd), 200


@app.route("/api/v1/vehicle/<vin>/remote/commands", methods=["GET"])
def list_commands(vin):
    """Command history for a vehicle — useful for audit/debugging, and for
    a test to find a commandId without having captured it from the submit
    response."""
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    if vin not in _KNOWN_VINS:
        return jsonify(error=f"vehicle {vin} not found"), 404
    cmds = [c for c in _commands.values() if c["vin"] == vin]
    return jsonify(vin=vin, commands=cmds, total=len(cmds)), 200


@app.route("/api/v1/vehicle/<vin>/remote/commands/<command_id>", methods=["DELETE"])
def cancel_command(vin, command_id):
    """Cancel a command — only while it's still PENDING. Once dispatched to
    the (simulated) vehicle, it can no longer be recalled, matching how a
    real cellular-connected vehicle command would behave."""
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    cmd = _commands.get(command_id)
    if not cmd or cmd["vin"] != vin:
        return jsonify(error=f"command {command_id} not found for vehicle {vin}"), 404
    if cmd["status"] != "PENDING":
        return jsonify(error=f"cannot cancel a command in status {cmd['status']}"), 409
    cmd["status"] = "CANCELLED"
    return jsonify(commandId=command_id, status="CANCELLED"), 200


@app.route("/api/v1/vehicle/<vin>/remote/lock", methods=["POST"])
def remote_lock(vin):
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    if state["doorsOpen"]:
        return jsonify(error="cannot lock while a door is open"), 409
    state["locked"] = True
    return jsonify(commandId=str(uuid.uuid4()), status="LOCKED"), 200


@app.route("/api/v1/vehicle/<vin>/remote/unlock", methods=["POST"])
def remote_unlock(vin):
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    body = request.get_json(silent=True) or {}
    pin = body.get("pin")
    if not pin:
        return jsonify(error="pin is required"), 400
    if pin != _REMOTE_PIN:
        return jsonify(error="invalid PIN"), 403
    state["locked"] = False
    return jsonify(commandId=str(uuid.uuid4()), status="UNLOCKED"), 200


@app.route("/api/v1/vehicle/<vin>/remote/locate", methods=["POST"])
def remote_locate(vin):
    """'Find my vehicle' — flash lights and/or sound the horn."""
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "lights_and_horn")
    if mode not in ("lights", "horn", "lights_and_horn"):
        return jsonify(error="mode must be one of: lights, horn, lights_and_horn"), 400
    return jsonify(commandId=str(uuid.uuid4()), status="TRIGGERED", mode=mode), 200


@app.route("/api/v1/vehicle/<vin>/status", methods=["GET"])
def vehicle_status(vin):
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    return jsonify(vin=vin, locked=state["locked"], engineOn=state["engineOn"],
                    doorsOpen=state["doorsOpen"], activeServices=state["activeServices"],
                    fuelLevelPct=72, odometerMiles=18422), 200


@app.route("/api/v1/services/<vin>/activate", methods=["POST"])
def activate_service(vin):
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    body = request.get_json(silent=True) or {}
    service_code = body.get("serviceCode")
    if not service_code:
        return jsonify(error="serviceCode is required"), 400
    if service_code not in _KNOWN_SERVICES:
        return jsonify(error=f"unknown serviceCode '{service_code}'"), 400
    if service_code in state["activeServices"]:
        return jsonify(error=f"{service_code} is already active on this vehicle"), 409
    state["activeServices"].append(service_code)
    return jsonify(activationId=str(uuid.uuid4()), serviceCode=service_code, status="ACTIVE"), 200


@app.route("/api/v1/services/<vin>/deactivate", methods=["POST"])
def deactivate_service(vin):
    if _needs_auth():
        return jsonify(error="missing or invalid Authorization header"), 401
    state = _vehicle_or_404(vin)
    if state is None:
        return jsonify(error=f"vehicle {vin} not found"), 404
    body = request.get_json(silent=True) or {}
    service_code = body.get("serviceCode")
    if not service_code:
        return jsonify(error="serviceCode is required"), 400
    if service_code not in state["activeServices"]:
        return jsonify(error=f"{service_code} is not active on this vehicle"), 409
    state["activeServices"].remove(service_code)
    return jsonify(serviceCode=service_code, status="INACTIVE"), 200


@app.route("/health")
def health():
    return jsonify(status="ok", service="mock-microservice"), 200


if __name__ == "__main__":
    print("Mock microservice running on http://localhost:9000")
    print("Endpoints: /api/v1/auth/login, /api/v1/auth/token/refresh,")
    print("           /api/v1/payments/charge, /api/v1/checkout/session,")
    print("           /api/v1/users/<id>, /api/v1/search, /api/v1/health/db,")
    print("           /api/v1/vehicle/<vin>/remote/{start,stop,lock,unlock,locate},")
    print("           /api/v1/vehicle/<vin>/status, /api/v1/services/<vin>/{activate,deactivate}")
    app.run(host="0.0.0.0", port=9000)
