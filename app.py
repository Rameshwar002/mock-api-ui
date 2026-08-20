"""
AutoBot — Flask Backend
=======================
Serves the UI and exposes all REST APIs consumed by:
  - loginpage.html  (auth)
  - chat.html       (NLU, run control, status, results, Jira proxy)
  - dashboard.html  (admin: runs, users, registry, feed)

Spring Boot handles real Jira creation; this layer proxies to it.
"""

import os
import io
import re
import sys
import json
import hmac
import hashlib
import base64
import zipfile
import threading
import subprocess
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, send_file

# ── PATHS ────────────────────────────────────────────────────────────────────
BASE        = os.path.abspath(os.path.dirname(__file__))
PUBLIC_DIR  = os.path.join(BASE, "public")
RESULTS_DIR = os.path.join(BASE, "results")
TESTS_DIR   = os.path.join(BASE, "tests")
DATA_DIR    = os.path.join(BASE, "data")
CONFIG_DIR  = os.path.join(BASE, "config")

RUNS_FILE    = os.path.join(DATA_DIR, "runs.json")
BUGS_FILE    = os.path.join(DATA_DIR, "bugs.json")
USERS_FILE   = os.path.join(DATA_DIR, "users.json")
FEED_FILE    = os.path.join(DATA_DIR, "feed.json")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
CATALOG_FILE = os.path.join(DATA_DIR, "test_catalog.json")
API_SPECS_FILE = os.path.join(CONFIG_DIR, "api_specs.json")

for d in [PUBLIC_DIR, RESULTS_DIR, TESTS_DIR, DATA_DIR]:
    os.makedirs(d, exist_ok=True)

# ── CONFIG ───────────────────────────────────────────────────────────────────
SECRET          = os.environ.get("AUTOBOT_SECRET", "autobot-secret-dev-key")
SPRINGBOOT_URL  = os.environ.get("JIRA_SERVICE_URL", "http://localhost:8080")

# ── USERS (replace with DB in production) ────────────────────────────────────
USERS_DB = {
    "admin":  {"password": "admin",   "role": "admin"},
    "qa":     {"password": "qa123",   "role": "user"},
    "tester": {"password": "test123", "role": "user"},
}

# ── SEED / DEFAULT MOCK TICKETS (written to tickets.json on first run) ───────
_SEED_TICKETS = [
    {
        "id": "IT-6", "title": "Incorrect database collation", "status": "Open",
        "priority": "Low", "urgency": "Medium", "impact": "Moderate / Limited",
        "service": "Database", "reporter": "Rachel Wright", "assignee": None,
        "desc": "I noticed that the MySQL collation in the test environment is "
                "<em>utf8_unicode_ci</em>.<br>It should be updated to match the settings in production.",
        "robotTags": ["database", "regression", "sanity"],
        "reqType": "Report a system problem", "severity": "None", "labels": "None",
        "comments": [], "created": "Today 10:00 AM", "updated": "Today 04:34 PM",
        "testResults": None,
    },
    {
        "id": "IT-7", "title": "Login page 500 error on prod", "status": "In Progress",
        "priority": "High", "urgency": "High", "impact": "Major",
        "service": "Auth Service", "reporter": "qa", "assignee": "dev",
        "desc": "Login endpoint returns HTTP 500 under high load on production environment.",
        "robotTags": ["login", "auth", "smoke"],
        "reqType": "Report a system problem", "severity": "High", "labels": "prod, critical",
        "comments": [], "created": "Yesterday", "updated": "Today 09:00 AM",
        "testResults": None,
    },
    {
        "id": "IT-8", "title": "Payment gateway timeout", "status": "Open",
        "priority": "Critical", "urgency": "Critical", "impact": "Extensive",
        "service": "Payment", "reporter": "tester", "assignee": None,
        "desc": "Payment gateway times out after 30 seconds during peak hours.",
        "robotTags": ["payment", "checkout", "regression"],
        "reqType": "Report a system problem", "severity": "Critical", "labels": "None",
        "comments": [], "created": "2 days ago", "updated": "Yesterday",
        "testResults": None,
    },
    {
        "id": "IT-9", "title": "User profile update returns 404", "status": "In Review",
        "priority": "Medium", "urgency": "Medium", "impact": "Moderate / Limited",
        "service": "User API", "reporter": "qa", "assignee": "dev",
        "desc": "PUT /users/profile returns 404 Not Found on staging environment.",
        "robotTags": ["profile", "api", "regression"],
        "reqType": "Report a system problem", "severity": "Medium", "labels": "staging",
        "comments": [], "created": "3 days ago", "updated": "Today 11:00 AM",
        "testResults": None,
    },
    {
        "id": "IT-10", "title": "Search results pagination broken", "status": "Open",
        "priority": "Low", "urgency": "Low", "impact": "Minor",
        "service": "Search", "reporter": "tester", "assignee": None,
        "desc": "Search results page 2+ returns duplicate items from page 1.",
        "robotTags": ["search", "pagination", "e2e"],
        "reqType": "Report a system problem", "severity": "Low", "labels": "None",
        "comments": [], "created": "4 days ago", "updated": "4 days ago",
        "testResults": None,
    },
]

# ── SEED TEST CATALOG (the 'data source' of already-automated test cases) ───
# Each entry says: "tag X is already covered by test case Y living in file Z".
# When a ticket's robotTags don't match anything here, AutoBot generates a new
# Robot Framework script and appends an entry so it's covered next time.
_SEED_CATALOG = [
    {"tag": "login",      "name": "Login_Validation_Flow",   "file": "tests/login_tests.robot",      "suite": "Smoke"},
    {"tag": "auth",       "name": "API_Auth_Token_Check",     "file": "tests/auth_tests.robot",       "suite": "Smoke"},
    {"tag": "database",   "name": "DB_Collation_Check",       "file": "tests/database_tests.robot",   "suite": "Sanity"},
    {"tag": "regression", "name": "Regression_Suite",         "file": "tests/regression_tests.robot", "suite": "Regression"},
    {"tag": "sanity",     "name": "Sanity_Suite",             "file": "tests/sanity_tests.robot",     "suite": "Sanity"},
    {"tag": "smoke",      "name": "Smoke_Suite",              "file": "tests/smoke_tests.robot",      "suite": "Smoke"},
    {"tag": "payment",    "name": "Payment_Gateway_Test",     "file": "tests/payment_tests.robot",    "suite": "Regression"},
    {"tag": "checkout",   "name": "Checkout_Flow_E2E",        "file": "tests/checkout_tests.robot",   "suite": "E2E"},
    {"tag": "profile",    "name": "Profile_Update_Test",      "file": "tests/profile_tests.robot",    "suite": "Regression"},
    {"tag": "api",        "name": "API_Contract_Test",        "file": "tests/api_tests.robot",        "suite": "Regression"},
    {"tag": "search",     "name": "Search_Results_Test",      "file": "tests/search_tests.robot",     "suite": "E2E"},
    {"tag": "pagination", "name": "Pagination_Test",          "file": "tests/search_tests.robot",     "suite": "E2E"},
    {"tag": "e2e",        "name": "E2E_Suite",                "file": "tests/e2e_tests.robot",        "suite": "E2E"},
]

# ── SEED API SPECS (config/api_specs.json) ───────────────────────────────────
# The "brain" AutoBot reads to know which application/endpoint/method/URL to
# target for a given ticket tag + region + environment — AND the mock dataset
# it grounds test generation on: real request fields, response shape, and the
# exact conditions that trigger each error status in mock_service.py. This is
# what stops the LLM (or the deterministic fallback) from guessing field names
# out of thin air — it's given the actual contract to work from.
#
# NOTE ON MOCK URLS: every region/env below currently points at the single
# local mock microservice in mock_service.py (http://localhost:9000). The
# region/env structure is kept as-is on purpose — swap in real per-region URLs
# here when you're ready to point at actual environments; nothing else in the
# generation pipeline needs to change.
_MOCK_URL = "http://localhost:9000"
_SEED_API_SPECS = {
    "applications": [
        {
            "name": "Auth Service", "tags": ["auth", "login"],
            "base_urls": {
                "US":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "EU":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "APAC": {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
            },
            "endpoints": [
                {
                    "path": "/api/v1/auth/login", "method": "POST", "tags": ["login", "auth"],
                    "description": "Authenticate a user and return a session token",
                    "requires_auth": False,
                    "request_schema": [
                        {"field": "username", "type": "string", "required": True, "example": "demo"},
                        {"field": "password", "type": "string", "required": True, "example": "demo123"},
                    ],
                    "success_response": [
                        {"field": "token", "type": "string"}, {"field": "expires_in", "type": "integer"},
                    ],
                    "error_cases": [
                        {"status": 400, "trigger": "username or password missing"},
                        {"status": 401, "trigger": "password is literally 'wrong'",
                         "payload_patch": {"password": "wrong"}},
                    ],
                },
                {
                    "path": "/api/v1/auth/token/refresh", "method": "POST", "tags": ["auth"],
                    "description": "Refresh an expired auth token",
                    "requires_auth": True,
                    "request_schema": [
                        {"field": "refresh_token", "type": "string", "required": True, "example": "mock-refresh-token-abc"},
                    ],
                    "success_response": [
                        {"field": "token", "type": "string"}, {"field": "expires_in", "type": "integer"},
                    ],
                    "error_cases": [
                        {"status": 400, "trigger": "refresh_token missing"},
                        {"status": 401, "trigger": "missing or invalid Authorization header", "no_auth": True},
                    ],
                },
            ],
        },
        {
            "name": "Payment", "tags": ["payment", "checkout"],
            "base_urls": {
                "US":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "EU":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "APAC": {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
            },
            "endpoints": [
                {
                    "path": "/api/v1/payments/charge", "method": "POST", "tags": ["payment"],
                    "description": "Charge a payment method",
                    "requires_auth": True,
                    "request_schema": [
                        {"field": "amount", "type": "number", "required": True, "example": 49.99},
                        {"field": "payment_method_id", "type": "string", "required": True, "example": "pm_mock_123"},
                    ],
                    "success_response": [
                        {"field": "charge_id", "type": "string"}, {"field": "status", "type": "string"},
                        {"field": "amount", "type": "number"},
                    ],
                    "error_cases": [
                        {"status": 400, "trigger": "amount or payment_method_id missing"},
                        {"status": 401, "trigger": "missing or invalid Authorization header", "no_auth": True},
                    ],
                },
                {
                    "path": "/api/v1/checkout/session", "method": "POST", "tags": ["checkout"],
                    "description": "Create a checkout session",
                    "requires_auth": True,
                    "request_schema": [
                        {"field": "cart_id", "type": "string", "required": True, "example": "cart_mock_123"},
                    ],
                    "success_response": [
                        {"field": "session_id", "type": "string"}, {"field": "checkout_url", "type": "string"},
                    ],
                    "error_cases": [
                        {"status": 400, "trigger": "cart_id missing"},
                        {"status": 401, "trigger": "missing or invalid Authorization header", "no_auth": True},
                    ],
                },
            ],
        },
        {
            "name": "User Profile", "tags": ["profile", "user"],
            "base_urls": {
                "US":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "EU":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "APAC": {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
            },
            "endpoints": [
                {
                    "path": "/api/v1/users/1", "method": "PUT", "tags": ["profile", "api"],
                    "description": "Update a user's profile. Mock only recognizes ids 1, 2, 3, demo-user.",
                    "requires_auth": True,
                    "request_schema": [
                        {"field": "email", "type": "string", "required": False, "example": "user@example.com",
                         "notes": "must contain '@' if provided"},
                    ],
                    "success_response": [{"field": "id", "type": "string"}, {"field": "email", "type": "string"}],
                    "error_cases": [
                        {"status": 400, "trigger": "email present but missing '@'",
                         "payload_patch": {"email": "not-an-email"}},
                        {"status": 401, "trigger": "missing or invalid Authorization header", "no_auth": True},
                        {"status": 404, "trigger": "unknown user id",
                         "path_override": "/api/v1/users/does-not-exist"},
                    ],
                },
            ],
        },
        {
            "name": "Search", "tags": ["search", "pagination"],
            "base_urls": {
                "US":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "EU":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "APAC": {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
            },
            "endpoints": [
                {
                    "path": "/api/v1/search", "method": "GET", "tags": ["search", "pagination"],
                    "description": "Search with pagination",
                    "requires_auth": False,
                    "request_schema": [
                        {"field": "q",    "type": "string",  "required": True,  "example": "test", "in": "query"},
                        {"field": "page", "type": "integer", "required": False, "example": 1,       "in": "query"},
                    ],
                    "success_response": [
                        {"field": "query", "type": "string"}, {"field": "page", "type": "integer"},
                        {"field": "results", "type": "array"},
                    ],
                    "error_cases": [
                        {"status": 400, "trigger": "q missing", "path_override": "/api/v1/search"},
                        {"status": 400, "trigger": "page not a positive integer",
                         "path_override": "/api/v1/search?q=test&page=0"},
                    ],
                },
            ],
        },
        {
            "name": "Database", "tags": ["database"],
            "base_urls": {
                "US":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "EU":   {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
                "APAC": {"DEV": _MOCK_URL, "INT": _MOCK_URL, "PROD": _MOCK_URL},
            },
            "endpoints": [
                {
                    "path": "/api/v1/health/db", "method": "GET", "tags": ["database"],
                    "description": "Check DB health/collation",
                    "requires_auth": False, "request_schema": [], "success_response": [
                        {"field": "status", "type": "string"}, {"field": "collation", "type": "string"},
                    ],
                    "error_cases": [],
                },
            ],
        },
    ]
}

# ── APP ───────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=PUBLIC_DIR)

# ── EXECUTION STATE ───────────────────────────────────────────────────────────
_state_lock = threading.Lock()
execution_state = {
    "status":      "idle",   # idle | running | completed
    "stage":       None,     # understanding | generating | executing | None
    "mode":        None,     # real | demo | None
    "analysis":    None,     # {matchedTests, generated, note} once known (ticket runs)
    "total":       0,
    "passed":      0,
    "failed":      0,
    "skipped":     0,
    "test_type":   "",
    "region":      "",
    "env":         "",
    "user":        "",
    "started_at":  None,
    "finished_at": None,
    "duration_s":  0,
    "failures":    [],
}


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

def _make_token(username, role):
    payload = f"{username}:{role}:{datetime.utcnow().isoformat()}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode()

def _ok(data, code=200):
    return jsonify({"error": False, **data}), code

def _err(msg, code=400):
    return jsonify({"error": True, "message": msg}), code

def _add_feed(user, action, ftype="run"):
    feeds = _load(FEED_FILE, [])
    feeds.append({
        "user":   user,
        "action": action,
        "type":   ftype,
        "time":   datetime.utcnow().isoformat()
    })
    _save(FEED_FILE, feeds[-200:])  # keep last 200

def _now():
    return datetime.utcnow().isoformat()

def _load_tickets():
    """Load tickets from disk, seeding with the default mock tickets on first run."""
    if not os.path.exists(TICKETS_FILE):
        _save(TICKETS_FILE, _SEED_TICKETS)
        return json.loads(json.dumps(_SEED_TICKETS))  # deep copy
    return _load(TICKETS_FILE, [])

def _save_tickets(tickets):
    _save(TICKETS_FILE, tickets)

def _next_ticket_id(tickets, prefix="IT"):
    nums = []
    for t in tickets:
        try:
            nums.append(int(str(t.get("id", "IT-0")).split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}-{(max(nums) + 1) if nums else 11}"


def _load_catalog():
    """Load the test-case catalog — the 'data source' AutoBot references to
    check whether a test case already exists for a given tag."""
    if not os.path.exists(CATALOG_FILE):
        _save(CATALOG_FILE, _SEED_CATALOG)
        return json.loads(json.dumps(_SEED_CATALOG))
    return _load(CATALOG_FILE, [])


def _save_catalog(catalog):
    _save(CATALOG_FILE, catalog)


def _canonical_ticket_file(ticket_id):
    """The one true filename a ticket's generated script must live at.
    Any catalog entry pointing anywhere else is stale (e.g. left over from
    an older per-tag generation scheme) and must not be trusted."""
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", ticket_id)
    return f"tests/{safe_id}_generated.robot"


def _analyze_ticket(ticket):
    """Understand a ticket and decide which test case(s) it needs.
    Returns (matched, missing) — matched catalog entries (whose backing .robot
    file genuinely exists on disk, at the current canonical path) vs. tags
    with no real coverage yet.

    STRICT PER-TICKET SCOPE: an entry only counts as a match if it was
    auto-generated specifically FOR THIS ticket (generatedFor == ticket id)
    AND its file is the current canonical per-ticket file — not a stale
    entry left over from a previous generation scheme or a coincidentally
    named pre-existing file. We deliberately do NOT fall back to any other
    file just because it shares a tag — a ticket run must only ever execute
    scripts that genuinely belong to that ticket."""
    catalog  = _load_catalog()
    tags     = ticket.get("robotTags") or ["regression"]
    canonical = _canonical_ticket_file(ticket["id"])
    matched, missing = [], []
    for tag in tags:
        entry = next((c for c in catalog
                      if c.get("tag", "").lower() == tag.lower()
                      and c.get("generatedFor", "").lower() == ticket["id"].lower()
                      and c.get("file") == canonical), None)
        entry_file = os.path.join(BASE, entry["file"]) if entry else None
        if entry and entry_file and os.path.exists(entry_file):
            matched.append(entry)
        else:
            missing.append(tag)
    return matched, missing


def _load_api_specs():
    """Load config/api_specs.json — the 'brain' AutoBot reads to resolve which
    application, endpoint, method, and base URL a ticket tag maps to for a
    given region + environment. Seeded on first run; edit the file on disk to
    add real applications/endpoints."""
    if not os.path.exists(API_SPECS_FILE):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        _save(API_SPECS_FILE, _SEED_API_SPECS)
        return json.loads(json.dumps(_SEED_API_SPECS))
    return _load(API_SPECS_FILE, _SEED_API_SPECS)


def _resolve_endpoint(tag, region="US", env="DEV"):
    """Find the application/endpoint that covers `tag`, and resolve the base
    URL for the given region + environment. Returns None if nothing in the
    config matches — the caller should fall back to a generic placeholder."""
    specs = _load_api_specs()
    region = (region or "US").upper()
    env    = (env or "DEV").upper()

    for app_spec in specs.get("applications", []):
        endpoints = app_spec.get("endpoints", [])
        endpoint  = next((e for e in endpoints if tag.lower() in [t.lower() for t in e.get("tags", [])]), None)
        if not endpoint and tag.lower() in [t.lower() for t in app_spec.get("tags", [])]:
            endpoint = endpoints[0] if endpoints else None
        if endpoint:
            region_urls = app_spec.get("base_urls", {}).get(region) or app_spec.get("base_urls", {}).get("US", {})
            base_url = region_urls.get(env) or next(iter(region_urls.values()), "https://api.example.com")
            return {"application": app_spec["name"], "endpoint": endpoint, "base_url": base_url,
                    "region": region, "env": env}
    return None


def _build_valid_request(endpoint):
    """From an endpoint's request_schema (the mock dataset), build the base
    valid request: (path including query params, body payload dict).
    Query fields (schema entries with "in": "query") go on the URL; everything
    else goes in the JSON body."""
    schema = endpoint.get("request_schema") or []
    body   = {f["field"]: f["example"] for f in schema if f.get("in") != "query" and "example" in f}
    query  = {f["field"]: f["example"] for f in schema if f.get("in") == "query" and "example" in f}
    path = endpoint["path"]
    if query:
        qs = "&".join(f"{k}={v}" for k, v in query.items())
        path = f"{path}?{qs}"
    return path, body


def _call_llm_for_scenarios(ticket, tag, resolved):
    """Design positive + negative API test scenarios for this ticket, using a
    LOCAL LLM. This is the MANDATORY primary path for scenario design — the
    LLM is what actually reads the ticket's own description and decides what
    a meaningful positive case and a meaningful negative case look like FOR
    THIS TICKET, grounded in the endpoint's real request/response schema and
    known error conditions when one is resolved (config/api_specs.json — the
    mock dataset), so it isn't left guessing field names.

    This is attempted for EVERY tag, whether or not an endpoint could be
    resolved — an unresolved tag still gets an LLM-designed scenario set
    grounded in the ticket text alone, rather than skipping straight to the
    generic deterministic fallback.

    Configured entirely via environment variables so it works with whatever
    local runner you're using:

      LOCAL_LLM_URL   default: http://localhost:11434/api/generate  (Ollama)
      LOCAL_LLM_MODEL default: llama3.1
      LOCAL_LLM_API   "ollama" (default) or "openai" — set to "openai" if your
                      local server exposes an OpenAI-compatible
                      /v1/chat/completions endpoint (LM Studio, vLLM,
                      text-generation-webui, etc.) instead of Ollama's API.

    Returns None ONLY if the local LLM is genuinely unreachable or replies
    with something unparsable — this triggers the deterministic fallback in
    _fallback_scenarios, which is a DEGRADED resilience mode, not the
    intended path, so a run is never blocked entirely just because the LLM
    is temporarily offline."""
    llm_url   = os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/api/generate")
    llm_model = os.environ.get("LOCAL_LLM_MODEL", "llama3.1")
    llm_api   = os.environ.get("LOCAL_LLM_API", "ollama").lower()

    ticket_desc = re.sub('<[^<]+?>', ' ', ticket.get('desc', ''))[:600]

    if resolved:
        endpoint = resolved["endpoint"]
        schema_lines = "\n".join(
            f"  - {f['field']} ({f.get('type','string')}, {'required' if f.get('required') else 'optional'}"
            f"{', query param' if f.get('in')=='query' else ''}): example = {json.dumps(f.get('example'))}"
            + (f"  [{f['notes']}]" if f.get("notes") else "")
            for f in endpoint.get("request_schema", [])
        ) or "  (no request fields)"
        response_lines = "\n".join(
            f"  - {f['field']} ({f.get('type','string')})" for f in endpoint.get("success_response", [])
        ) or "  (no documented response fields)"
        error_lines = "\n".join(
            f"  - {e['status']}: {e['trigger']}" for e in endpoint.get("error_cases", [])
        ) or "  (no documented error cases)"

        prompt = f"""You are designing API test scenarios for a Robot Framework RequestsLibrary suite.
Use ONLY the schema below — do not invent field names that aren't listed.

Ticket: {ticket['id']} — {ticket.get('title','')}
Description: {ticket_desc}

Application: {resolved['application']}
Endpoint: {endpoint['method']} {endpoint['path']}
Endpoint description: {endpoint.get('description','')}
Requires auth: {endpoint.get('requires_auth', False)}

Request fields (this is the real schema — use these exact field names):
{schema_lines}

Success response fields:
{response_lines}

Known error conditions for this endpoint:
{error_lines}

Return ONLY a JSON array (no markdown, no prose) of 2-5 test scenario objects, each with:
- "name": short PascalCase test name (no spaces)
- "type": "positive" or "negative"
- "description": one sentence of what it verifies — tie it back to the ticket's own
  description where relevant, not a generic statement
- "payload": a JSON object using ONLY the field names above (or {{}} if none needed)
- "expected_status": the expected HTTP status code (int), matching one of the known error
  conditions for negative cases, or 200/201 for the positive case

Include exactly one positive scenario (all required fields present, valid values) and one
scenario per known error condition above. Prioritize a negative scenario that specifically
reproduces the bug described in the ticket, if one of the known error conditions matches it."""
    else:
        # No resolved endpoint/schema for this tag — still ask the LLM to
        # reason from the ticket text alone, rather than skipping straight
        # to the generic template fallback.
        prompt = f"""You are designing API test scenarios for a Robot Framework RequestsLibrary suite.
No API schema is available for this tag ("{tag}") yet, so base your scenarios on the ticket
description alone. Keep field names generic and clearly placeholder (e.g. "field_under_test")
since there is no confirmed schema to rely on.

Ticket: {ticket['id']} — {ticket.get('title','')}
Description: {ticket_desc}
Tag: {tag}

Return ONLY a JSON array (no markdown, no prose) of 2-3 test scenario objects, each with:
- "name": short PascalCase test name (no spaces)
- "type": "positive" or "negative"
- "description": one sentence of what it verifies, tied to the ticket's own description
- "payload": a small JSON object representative of what this request might need (or {{}})
- "expected_status": the expected HTTP status code (int) — best guess: 200 for positive,
  400 for negative

Include at least one positive and one negative scenario."""

    try:
        if llm_api == "openai":
            body = json.dumps({
                "model": llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }).encode("utf-8")
            req = urllib.request.Request(
                llm_url, data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
        else:
            # Ollama's /api/generate
            body = json.dumps({
                "model": llm_model,
                "prompt": prompt,
                "stream": False,
            }).encode("utf-8")
            req = urllib.request.Request(
                llm_url, data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data.get("response", "")

        text = text.strip().strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        # Local models sometimes wrap the array in prose despite instructions —
        # pull out the first [...] block if a direct parse fails.
        try:
            scenarios = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\[.*\]", text, re.S)
            scenarios = json.loads(m.group(0)) if m else None
        if isinstance(scenarios, list) and scenarios:
            return scenarios
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        pass
    return None


def _fallback_scenarios(ticket, tag, resolved):
    """Deterministic positive + negative scenarios, used whenever the local
    LLM is unreachable or its reply can't be parsed — keeps generation always
    working. Built directly from the endpoint's request_schema + error_cases
    (the mock dataset in config/api_specs.json), so the "positive" case is a
    genuinely valid request and each "negative" case reproduces one of the
    endpoint's real, documented error conditions — not a guess."""
    endpoint = resolved["endpoint"] if resolved else {
        "method": "GET", "path": "/api/v1/unknown", "requires_auth": False,
        "request_schema": [], "error_cases": [],
    }
    requires_auth = endpoint.get("requires_auth", False)
    base_path, base_payload = _build_valid_request(endpoint)

    scenarios = [{
        "name": "ValidRequest_ReturnsSuccess", "type": "positive",
        "description": f"Verifies {endpoint['method']} {endpoint['path']} succeeds with a valid, fully-formed request.",
        "payload": base_payload, "path": base_path,
        "expected_status": 200, "auth": requires_auth,
    }]

    for case in endpoint.get("error_cases", []):
        payload = dict(base_payload)
        payload.update(case.get("payload_patch", {}))
        scenarios.append({
            "name": f"ErrorCase_{case['status']}_{re.sub(r'[^a-zA-Z0-9]+', '', case['trigger'])[:30]}",
            "type": "negative",
            "description": f"Verifies the API returns {case['status']} when: {case['trigger']}.",
            "payload": payload,
            "path": case.get("path_override", base_path),
            "expected_status": case["status"],
            "auth": not case.get("no_auth", False) and requires_auth,
        })

    return scenarios


def _generate_ticket_script(ticket, missing_tags, region="US", env="DEV"):
    """Generate ONE Robot Framework file for this ticket, named after the
    ticket ID (tests/{TICKET_ID}_generated.robot) — not per-tag — covering
    every missing tag in a single suite. For each tag: resolve which
    application/endpoint/URL applies (config/api_specs.json, the 'brain'),
    design positive + negative scenarios (via the local LLM if reachable,
    otherwise a deterministic fallback), and register each tag in the
    catalog (scoped to this ticket) so it's found next time — for THIS
    ticket only; a different ticket sharing the same tag still gets its
    own generated file, so filenames never collide across tickets.

    Returns the list of new catalog entries (one per generated tag)."""
    ticket_id  = ticket["id"]
    rel_path   = _canonical_ticket_file(ticket_id)
    fpath      = os.path.join(BASE, rel_path)

    sessions   = {}   # application name -> (alias, base_url)
    case_blocks = []
    entries    = []

    for tag in missing_tags:
        safe_tag = re.sub(r"[^a-zA-Z0-9_]+", "_", tag.strip().lower()).strip("_") or "case"
        resolved = _resolve_endpoint(tag, region, env)
        llm_scenarios = _call_llm_for_scenarios(ticket, tag, resolved)
        scenarios     = llm_scenarios or _fallback_scenarios(ticket, tag, resolved)
        generated_via = "llm" if llm_scenarios else "template"

        base_url = resolved["base_url"] if resolved else "https://api.example.com"
        endpoint = resolved["endpoint"] if resolved else {"method": "GET", "path": "/api/v1/unknown", "description": ""}
        app_name = resolved["application"] if resolved else "Unresolved application"
        method   = endpoint["method"].upper()
        ep_path  = endpoint["path"]

        if app_name not in sessions:
            sessions[app_name] = (re.sub(r"[^a-zA-Z0-9_]+", "_", app_name.lower()), base_url)
        alias = sessions[app_name][0]

        method_kw = {"GET": "Get On Session", "POST": "Post On Session", "PUT": "Put On Session",
                     "DELETE": "Delete On Session", "PATCH": "Patch On Session"}.get(method, "Get On Session")

        for sc in scenarios:
            name = re.sub(r"[^a-zA-Z0-9_]+", "_", sc.get("name", "Scenario")).strip("_")
            case_name = f"{ticket_id}_{safe_tag.capitalize()}_{name}"
            sc_path  = sc.get("path", ep_path)
            use_auth = sc.get("auth", True)
            header_kw   = "    &{headers}=    Create Dictionary    Authorization=Bearer mock-token\n" if use_auth else ""
            headers_arg = "    headers=${headers}" if use_auth else ""
            origin_tag  = "llm-generated" if generated_via == "llm" else "template-fallback"
            origin_note = ("Scenario designed by the local LLM." if generated_via == "llm" else
                           "DEGRADED: local LLM unreachable/unparsable -- generic deterministic "
                           "template used instead. Not tailored to this ticket's description.")

            payload = sc.get("payload")
            if payload is not None and method in ("POST", "PUT", "PATCH"):
                body_line = (f"{header_kw}"
                             f"    ${{resp}}=    {method_kw}    {alias}    {sc_path}"
                             f"    json={json.dumps(payload)}{headers_arg}    expected_status=any")
            else:
                body_line = (f"{header_kw}"
                             f"    ${{resp}}=    {method_kw}    {alias}    {sc_path}{headers_arg}    expected_status=any")

            case_blocks.append(f"""{case_name}
    [Documentation]    {sc.get('description','')}
    ...                {origin_note}
    [Tags]    {sc.get('type','positive')}    {safe_tag}    {ticket_id}    {origin_tag}
{body_line}
    Status Should Be    {sc.get('expected_status', 200)}    ${{resp}}
""")

        entries.append({
            "tag": tag, "name": f"{ticket_id}_{safe_tag.capitalize()}_Suite", "file": rel_path,
            "suite": "Generated", "generatedFor": ticket_id, "generatedAt": _now(),
            "application": app_name, "endpoint": f"{method} {ep_path}", "baseUrl": base_url,
            "scenarios": [{"name": s.get("name"), "type": s.get("type")} for s in scenarios],
            "generatedVia": generated_via,
        })

    llm_tags      = [t for t in missing_tags if any(e["tag"] == t and e["generatedVia"] == "llm" for e in entries)]
    template_tags = [t for t in missing_tags if t not in llm_tags]
    origin_summary = (
        f"LLM-designed scenarios for: {', '.join(llm_tags) or '(none)'}. "
        f"Template-fallback (degraded) for: {', '.join(template_tags) or '(none)'}."
    )
    setup_lines = "\n".join(f"    Create Session    {alias}    {url}" for alias, url in sessions.values())
    content = f"""*** Settings ***
Documentation    Auto-generated by AutoBot for ticket {ticket_id} - {ticket.get('title','')}
...              Covers tag(s) with no existing coverage: {', '.join(missing_tags)}
...              Resolved against config/api_specs.json and generated positive +
...              negative scenarios per tag.
...              {origin_summary}
Library          RequestsLibrary
Library          Collections
Suite Setup      Initialize Sessions
Force Tags       {ticket_id}    auto-generated

*** Keywords ***
Initialize Sessions
{setup_lines}

*** Test Cases ***
{"".join(case_blocks)}"""

    os.makedirs(TESTS_DIR, exist_ok=True)
    with open(fpath, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    # Replace any previous entries generated for THIS ticket (a re-run
    # regenerates cleanly) — leave every other ticket's/tag's entries alone.
    catalog = _load_catalog()
    catalog = [c for c in catalog if c.get("generatedFor", "").lower() != ticket_id.lower()]
    catalog.extend(entries)
    _save_catalog(catalog)
    return entries


# ── AUTH DECORATOR ────────────────────────────────────────────────────────────

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        role = request.headers.get("X-User-Role", "user")
        if role != "admin":
            return _err("Admin access required.", 403)
        return f(*args, **kwargs)
    return wrapper


# ── ROBOT EXECUTION ───────────────────────────────────────────────────────────

def _parse_output_xml():
    """Parse output.xml written by Robot Framework."""
    xml_path = os.path.join(RESULTS_DIR, "output.xml")
    if not os.path.exists(xml_path):
        return

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Overall totals
    for stat in root.findall(".//statistics/total/stat"):
        text = (stat.text or "").strip()
        if "All Tests" in text or text == "":
            p = int(stat.get("pass", 0))
            f = int(stat.get("fail", 0))
            s = int(stat.get("skip", 0))
            with _state_lock:
                execution_state.update({
                    "passed":  p,
                    "failed":  f,
                    "skipped": s,
                    "total":   p + f + s,
                })
            break

    # Individual failures
    failures = []
    for test in root.findall(".//test"):
        status = test.find("status")
        if status is not None and status.get("status") == "FAIL":
            failures.append({
                "name":    test.get("name", "Unknown"),
                "message": (status.text or "No error message.").strip(),
            })
    with _state_lock:
        execution_state["failures"] = failures


def _demo_result():
    """Generate realistic demo results when Robot Framework is absent."""
    import random
    total   = random.randint(12, 40)
    failed  = random.randint(0, min(5, total // 5))
    skipped = random.randint(0, 2)
    passed  = total - failed - skipped
    names   = [
        "Login_Validation_Flow", "API_Auth_Token_Check", "Dashboard_Load_Test",
        "Checkout_Flow_E2E", "Payment_Gateway_Test", "Profile_Update_Check",
        "Search_Results_Verify", "Cart_Price_Mismatch", "Session_Timeout_Test",
    ]
    codes = [404, 500, 503]
    with _state_lock:
        execution_state.update({
            "total":    total,
            "passed":   passed,
            "failed":   failed,
            "skipped":  skipped,
            "failures": [
                {
                    "name":    names[i % len(names)],
                    "message": f"AssertionError: Expected 200 but got {codes[i % 3]}.",
                }
                for i in range(failed)
            ],
        })


def run_robot_tests(test_type, region, env, user, target_files=None):
    """Run Robot Framework in a thread; fall back to demo data if Robot
    Framework isn't actually installed/runnable. Used directly for
    suite-based (non-ticket) runs. Ticket-based runs go through
    _run_ticket_pipeline instead, which also handles the understand/generate
    steps before calling _execute_robot."""
    with _state_lock:
        execution_state.update({
            "status":      "running",
            "stage":       "executing",
            "total":       0, "passed": 0, "failed": 0, "skipped": 0,
            "test_type":   test_type,
            "region":      region,
            "env":         env,
            "user":        user,
            "mode":        None,
            "analysis":    None,
            "started_at":  _now(),
            "finished_at": None,
            "duration_s":  0,
            "failures":    [],
        })
    _add_feed(user, f"started {test_type} · {region} · {env}", "run")
    _execute_robot(test_type, region, env, user, target_files)


def _preflight_check():
    """Fast check that the libraries our generated scripts depend on are
    actually importable, before handing off to Robot Framework. Catches the
    #1 confusing failure mode: 'pip install requests' (the plain HTTP
    library) instead of 'pip install robotframework-requests' (the Robot
    Framework wrapper that actually provides RequestsLibrary's keywords,
    like Create Session). Without this check, that mistake surfaces as a
    cryptic 'No keyword with name Create Session found' deep in a suite
    setup failure instead of a clear, actionable message."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import RequestsLibrary"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return ("RequestsLibrary isn't installed (or failed to import) in this Python "
                    "environment. This is what causes \"No keyword with name 'Create Session' "
                    "found\". Fix: pip install robotframework-requests  "
                    "(NOT just 'pip install requests' — that's a different package and won't "
                    f"provide Robot Framework keywords). Import error: {result.stderr.strip()[:300]}")
    except FileNotFoundError:
        return None  # can't even find python/robot — the existing demo-fallback path handles this
    except subprocess.TimeoutExpired:
        return None  # don't block a run over a slow environment check
    return None


def _execute_robot(test_type, region, env, user, target_files=None):
    """The actual subprocess/parse/demo-fallback core, shared by both
    suite-based and ticket-based runs. Assumes execution_state["status"] is
    already "running" and "started_at" already set by the caller."""
    if target_files:
        preflight_error = _preflight_check()
        if preflight_error:
            finished = datetime.utcnow()
            started  = datetime.fromisoformat(execution_state["started_at"])
            duration = round((finished - started).total_seconds(), 1)
            with _state_lock:
                execution_state.update({
                    "status": "completed", "stage": "completed", "mode": "error",
                    "total": 0, "passed": 0, "failed": 0, "skipped": 0,
                    "failures": [{"name": "ENVIRONMENT_ERROR", "message": preflight_error}],
                    "finished_at": finished.isoformat(), "duration_s": duration,
                })
            return

        cmd = [
            sys.executable, "-m", "robot",
            "--outputdir", RESULTS_DIR,
            "--variable",  f"REGION:{region}",
            "--variable",  f"ENV:{env}",
        ] + target_files
    else:
        cmd = [
            sys.executable, "-m", "robot",
            "--outputdir", RESULTS_DIR,
            "--variable",  f"REGION:{region}",
            "--variable",  f"ENV:{env}",
            "--include",   test_type.lower(),
            TESTS_DIR,
        ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if os.path.exists(os.path.join(RESULTS_DIR, "output.xml")):
            _parse_output_xml()
            with _state_lock:
                execution_state["mode"] = "real"
        else:
            # Robot Framework isn't actually installed/runnable on this
            # machine — use demo data so the UI still gets a result instead
            # of an empty 0/0/0 run. This is clearly marked, not silently
            # passed off as a genuine execution.
            _demo_result()
            with _state_lock:
                execution_state["mode"] = "demo"
    except FileNotFoundError:
        _demo_result()
        with _state_lock:
            execution_state["mode"] = "demo"
    except subprocess.TimeoutExpired:
        with _state_lock:
            execution_state["failures"].append({
                "name": "TIMEOUT", "message": "Run exceeded 600s."
            })
            execution_state["mode"] = "real"
    except Exception as e:
        with _state_lock:
            execution_state["failures"].append({
                "name": "RUNNER_ERROR", "message": str(e)
            })
            execution_state["mode"] = "demo"

    finished = datetime.utcnow()
    started  = datetime.fromisoformat(execution_state["started_at"])
    duration = round((finished - started).total_seconds(), 1)

    with _state_lock:
        execution_state["status"]      = "completed"
        execution_state["stage"]       = "completed"
        execution_state["finished_at"] = finished.isoformat()
        execution_state["duration_s"]  = duration

    # Persist run
    runs = _load(RUNS_FILE, [])
    runs.append({
        "id":         len(runs) + 1,
        "user":       user,
        "suite":      test_type,
        "region":     region,
        "env":        env,
        "total":      execution_state["total"],
        "passed":     execution_state["passed"],
        "failed":     execution_state["failed"],
        "skipped":    execution_state["skipped"],
        "duration":   duration,
        "started_at": execution_state["started_at"],
        "finished_at":execution_state["finished_at"],
        "timestamp":  datetime.now().strftime("%I:%M %p"),
    })
    _save(RUNS_FILE, runs[-500:])

    status_word = "completed with failures" if execution_state["failed"] > 0 else "passed all tests"
    _add_feed(user, f"run {status_word} — {execution_state['passed']}P {execution_state['failed']}F",
              "fail" if execution_state["failed"] > 0 else "pass")


def _run_ticket_pipeline(ticket_id, region, env, user):
    """The full ticket-based run, entirely inside a background thread so the
    HTTP request that triggered it (POST /confirm_run or
    POST /api/tickets/<id>/run) returns almost immediately — the caller
    should NOT block on this. Progress is reported via execution_state,
    which the frontend polls (GET /status): stage moves
    'understanding' -> 'generating' (only if needed) -> 'executing' -> done.
    This is what fixes runs appearing to 'hang' — before, the understand +
    generate step ran synchronously inside the request handler, so a slow
    local LLM call meant the client's fetch() just sat there with no
    visible progress at all."""
    with _state_lock:
        execution_state.update({
            "status": "running", "stage": "understanding",
            "total": 0, "passed": 0, "failed": 0, "skipped": 0,
            "test_type": ticket_id, "region": region, "env": env, "user": user,
            "mode": None, "analysis": None,
            "started_at": _now(), "finished_at": None, "duration_s": 0,
            "failures": [],
        })
    _add_feed(user, f"started {ticket_id} · {region} · {env}", "run")

    tickets = _load_tickets()
    idx = next((i for i, t in enumerate(tickets) if t.get("id") == ticket_id), None)
    if idx is None:
        with _state_lock:
            execution_state["status"] = "completed"
            execution_state["stage"] = "completed"
            execution_state["finished_at"] = _now()
            execution_state["failures"].append({"name": "TICKET_NOT_FOUND", "message": f"{ticket_id} not found."})
        return
    tk = tickets[idx]

    # ── BUG-TICKET DELEGATION ────────────────────────────────────────────
    # If this ticket is a bug linked back to a parent ticket, don't run the
    # full understand-and-generate pipeline from scratch — the parent was,
    # by definition, already tested to produce this bug, so reuse its
    # existing test case directly. Falls through to the normal flow only if
    # the parent has no real, on-disk coverage to delegate to (e.g. it was
    # cleaned up since), so a run never silently does nothing.
    parent_id = tk.get("parentTicket")
    if parent_id:
        parent = next((t for t in tickets if t.get("id") == parent_id), None)
        if parent:
            p_matched, p_missing = _analyze_ticket(parent)
            if p_matched and not p_missing:
                note = (f"AutoBot: {ticket_id} is linked to parent ticket {parent_id} - "
                        f"reusing its existing test case ({', '.join(m['name'] for m in p_matched)}) "
                        f"instead of generating a new one. No generation needed.")
                tk.setdefault("comments", []).append({
                    "id": int(datetime.utcnow().timestamp() * 1000), "author": "AutoBot",
                    "time": "Just now", "content": note, "isBot": True, "avatar": "#4f8ef7",
                })
                tickets[idx] = tk
                _save_tickets(tickets)
                with _state_lock:
                    execution_state["analysis"] = {
                        "matchedTests": p_matched, "generated": [], "note": note,
                        "delegatedTo": parent_id,
                    }
                    execution_state["stage"] = "executing"
                target_files = [os.path.join(BASE, e["file"]) for e in p_matched]
                _execute_robot(ticket_id, region, env, user, target_files)
                return
            # Parent exists but has no real coverage to delegate to (e.g. its
            # files were removed) — note this and fall through to the normal
            # pipeline below as a safety net, rather than silently doing nothing.
            tk.setdefault("comments", []).append({
                "id": int(datetime.utcnow().timestamp() * 1000), "author": "AutoBot",
                "time": "Just now", "isBot": True, "avatar": "#4f8ef7",
                "content": (f"AutoBot: {ticket_id} is linked to parent ticket {parent_id}, but "
                            f"{parent_id} has no existing test coverage to reuse right now - "
                            f"generating a fresh script for {ticket_id} instead."),
            })
        else:
            tk.setdefault("comments", []).append({
                "id": int(datetime.utcnow().timestamp() * 1000), "author": "AutoBot",
                "time": "Just now", "isBot": True, "avatar": "#4f8ef7",
                "content": (f"AutoBot: {ticket_id} references parent ticket {parent_id}, but it "
                            f"no longer exists - generating a fresh script for {ticket_id} instead."),
            })

    matched, missing = _analyze_ticket(tk)
    if missing:
        with _state_lock:
            execution_state["stage"] = "generating"
        generated = _generate_ticket_script(tk, missing, region, env)
    else:
        generated = []

    if generated:
        gen_desc = ", ".join(
            f"{g['name']} ({g.get('application','?')} \u2192 {g.get('endpoint','?')}, "
            f"{len(g.get('scenarios', []))} scenarios, via {g.get('generatedVia','template')})"
            for g in generated
        )
        degraded = [g["tag"] for g in generated if g.get("generatedVia") != "llm"]
        note = (f"AutoBot: no existing test case for tag(s) "
                f"[{', '.join(missing)}] - generated {gen_desc} before running.")
        if degraded:
            note += (f" WARNING: tag(s) [{', '.join(degraded)}] used the DETERMINISTIC "
                     f"TEMPLATE fallback, not the LLM - the local LLM was unreachable or "
                     f"returned something unparsable. This is a degraded result; the "
                     f"scenarios are generic, not tailored to this ticket's actual "
                     f"description. Check LOCAL_LLM_URL / that your local LLM is running.")
    else:
        note = (f"AutoBot: matched existing test case(s) - {', '.join(m['name'] for m in matched)}."
                if matched else "AutoBot: no tags to resolve - running as-is.")

    tk.setdefault("comments", []).append({
        "id": int(datetime.utcnow().timestamp() * 1000), "author": "AutoBot",
        "time": "Just now", "content": note, "isBot": True, "avatar": "#4f8ef7",
    })
    tickets[idx] = tk
    _save_tickets(tickets)

    with _state_lock:
        execution_state["analysis"] = {"matchedTests": matched, "generated": generated, "note": note}
        execution_state["stage"] = "executing"

    target_files = [os.path.join(BASE, e["file"]) for e in (matched + generated)]
    _execute_robot(ticket_id, region, env, user, target_files)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — PAGES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def root():
    return send_from_directory(PUBLIC_DIR, "loginpage.html")

@app.route("/chat.html")
def chat_page():
    return send_from_directory(PUBLIC_DIR, "chat.html")

@app.route("/dashboard.html")
def dashboard_page():
    return send_from_directory(PUBLIC_DIR, "dashboard.html")

@app.route("/dev.html")
def dev_page():
    return send_from_directory(PUBLIC_DIR, "dev.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(PUBLIC_DIR, filename)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password:
        return _err("Username and password are required.", 400)

    user = USERS_DB.get(username)
    if not user or user["password"] != password:
        return _err("Invalid username or password.", 401)

    token = _make_token(username, user["role"])
    _add_feed(username, "signed in", "run")
    return _ok({"token": token, "role": user["role"], "username": username})


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — CHAT / NLU
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/chat", methods=["POST"])
def handle_chat():
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").lower()
    user = data.get("user", "unknown")

    SUITES  = ["sanity", "regression", "smoke", "e2e", "performance"]
    REGIONS = ["us-east", "us-west", "us", "eu", "apac"]
    ENVS    = ["preprod", "stage", "prod", "int", "dev", "uat"]

    test_type = next((t for t in SUITES  if t in text), "sanity")
    region    = next((r for r in REGIONS if r in text), "us")
    env       = next((e for e in ENVS    if e in text), "dev")

    return jsonify({
        "type":    "confirmation",
        "message": f"Prepared {test_type.upper()} for {region.upper()} on {env.upper()}.",
        "params":  {
            "test_type": test_type.capitalize(),
            "region":    region.upper(),
            "env":       env.upper(),
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/confirm_run", methods=["POST"])
def confirm_run():
    if execution_state.get("status") == "running":
        return _err("A run is already in progress.", 409)

    data      = request.get_json(silent=True) or {}
    params    = data.get("params", {})
    user      = data.get("user", "unknown")
    ticket_id = data.get("ticketId")
    test_type = params.get("test_type", "Sanity")
    region    = params.get("region", "US")
    env       = params.get("env", "DEV")

    # ── Ticket-based run ────────────────────────────────────────────────
    # Understanding the ticket + generating any missing script(s) can take
    # real time (a local LLM call per tag), so this ALWAYS happens inside
    # the background thread — never inline here. The endpoint returns
    # immediately; poll GET /status for "stage" (understanding -> generating
    # -> executing) and the "analysis" field once it's ready.
    if ticket_id:
        t = threading.Thread(target=_run_ticket_pipeline, args=(ticket_id, region, env, user), daemon=True)
        t.start()
        return _ok({"status": "started", "ticketId": ticket_id})

    # ── Suite-based run (no ticket) ─────────────────────────────────────
    t = threading.Thread(target=run_robot_tests, args=(test_type, region, env, user), daemon=True)
    t.start()
    return _ok({"status": "started"})


@app.route("/status")
def get_status():
    return jsonify(execution_state)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — RESULTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/results/<path:filename>")
def serve_results(filename):
    return send_from_directory(RESULTS_DIR, filename)


@app.route("/download_results")
def download_results():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, _, files in os.walk(RESULTS_DIR):
            for fname in files:
                full = os.path.join(root_dir, fname)
                zf.write(full, os.path.relpath(full, RESULTS_DIR))
    buf.seek(0)
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    suite = execution_state.get("test_type", "run")
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"AutoBot_{suite}_{ts}.zip")


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — RUNS (admin reads all; user saves own run)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/runs", methods=["GET"])
def get_runs():
    runs  = _load(RUNS_FILE, [])
    user  = request.args.get("user")       # filter by user if provided
    limit = int(request.args.get("limit", 200))
    if user:
        runs = [r for r in runs if r.get("user") == user]
    return _ok({"runs": runs[-limit:]})


@app.route("/api/runs/save", methods=["POST"])
def save_run():
    """Called from chat.html after each run to persist it server-side."""
    data = request.get_json(silent=True) or {}
    runs = _load(RUNS_FILE, [])
    # Avoid double-save if server already wrote it (robot path)
    existing_ids = {r.get("started_at") for r in runs}
    if data.get("started_at") not in existing_ids:
        data["id"] = len(runs) + 1
        runs.append(data)
        _save(RUNS_FILE, runs[-500:])
    return _ok({"saved": True})


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — TICKETS  (mock Jira tickets, persisted in data/tickets.json)
#  Shared by jira.html (the mock Jira board) and dashboard.html (the portal),
#  so a ticket created or run from either page is visible/runnable from both.
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/tickets", methods=["GET"])
def list_tickets():
    tickets = _load_tickets()
    status  = request.args.get("status")
    if status:
        tickets = [t for t in tickets if t.get("status", "").lower() == status.lower()]
    return _ok({"tickets": tickets, "total": len(tickets)})


@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    """Add a mock ticket. Callable from the jira.html 'Create' modal or from
    dashboard.html (the portal) — both hit this same endpoint."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return _err("title is required.", 400)

    tickets  = _load_tickets()
    new_id   = _next_ticket_id(tickets)
    reporter = data.get("reporter") or request.args.get("username") or "unknown"
    tags     = data.get("robotTags") or ["regression"]
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    ticket = {
        "id":         new_id,
        "title":      title,
        "status":     data.get("status", "Open"),
        "priority":   data.get("priority", "Medium"),
        "urgency":    data.get("urgency", "Medium"),
        "impact":     data.get("impact", "Moderate / Limited"),
        "service":    data.get("service", "General"),
        "reporter":   reporter,
        "assignee":   data.get("assignee"),
        "desc":       data.get("desc") or title,
        "robotTags":  tags,
        "reqType":    data.get("reqType", "Report a system problem"),
        "severity":   data.get("severity", "None"),
        "labels":     data.get("labels", "None"),
        "comments":   [],
        "created":    "Just now",
        "updated":    "Just now",
        "testResults": None,
        "source":     data.get("source", "jira"),  # 'jira' or 'portal'
    }
    tickets.insert(0, ticket)
    _save_tickets(tickets)
    _add_feed(reporter, f"created mock ticket {new_id} — {title}", "ticket")
    return _ok({"ticket": ticket}, 201)


@app.route("/api/tickets/<ticket_id>", methods=["GET"])
def get_ticket(ticket_id):
    tickets = _load_tickets()
    t = next((t for t in tickets if t.get("id") == ticket_id), None)
    if not t:
        return _err(f"{ticket_id} not found.", 404)
    return _ok({"ticket": t})


@app.route("/api/tickets/<ticket_id>", methods=["PATCH"])
def update_ticket(ticket_id):
    """Partial update — status changes, assignee, comments, test results.
    Used by jira.html and dashboard.html to keep the ticket 'database' in sync."""
    data    = request.get_json(silent=True) or {}
    tickets = _load_tickets()
    idx     = next((i for i, t in enumerate(tickets) if t.get("id") == ticket_id), None)
    if idx is None:
        return _err(f"{ticket_id} not found.", 404)

    allowed = {"status", "assignee", "comments", "testResults", "priority",
               "urgency", "severity", "labels", "robotTags"}
    for key in allowed:
        if key in data:
            tickets[idx][key] = data[key]
    tickets[idx]["updated"] = "Just now"

    _save_tickets(tickets)
    return _ok({"ticket": tickets[idx]})


@app.route("/api/test-catalog", methods=["GET"])
def get_test_catalog():
    """The 'data source' AutoBot references to check whether a test case
    already exists before deciding to generate a new one."""
    return _ok({"catalog": _load_catalog()})


@app.route("/api/api-specs", methods=["GET"])
def get_api_specs():
    """The config-folder 'brain' AutoBot reads to resolve which application/
    endpoint/method/base-url a ticket's tags map to, per region + environment."""
    return _ok({"specs": _load_api_specs()})


@app.route("/api/tickets/<ticket_id>/analyze", methods=["GET"])
def analyze_ticket(ticket_id):
    """Collect ticket details and decide what needs testing — no side effects.
    Used by chat.html to show its reasoning before running or generating anything."""
    tickets = _load_tickets()
    t = next((t for t in tickets if t.get("id") == ticket_id), None)
    if not t:
        return _err(f"{ticket_id} not found.", 404)

    region = (request.args.get("region") or "US").upper()
    env    = (request.args.get("env")    or "DEV").upper()

    matched, missing = _analyze_ticket(t)

    # Preview (no file written yet) of what generation *would* target, so
    # chat.html can show "will target: Payment → POST /checkout/session"
    # before anything is actually generated.
    previews = []
    for tag in missing:
        resolved = _resolve_endpoint(tag, region, env)
        previews.append({
            "tag": tag,
            "application": resolved["application"] if resolved else None,
            "endpoint": f"{resolved['endpoint']['method']} {resolved['endpoint']['path']}" if resolved else None,
            "resolved": resolved is not None,
        })

    return _ok({
        "ticket": t,
        "matchedTests": matched,
        "missingTags": missing,
        "generationPreview": previews,
        "needsGeneration": len(missing) > 0,
    })


@app.route("/api/tickets/<ticket_id>/run", methods=["POST"])
def run_ticket_script(ticket_id):
    """Run the robot-framework script(s) tied to a ticket. Returns
    immediately — the actual understand/generate/execute pipeline runs in a
    background thread (_run_ticket_pipeline). Poll GET /status for progress
    ("stage": understanding -> generating -> executing) and the "analysis"
    field once it's ready. Works identically whether triggered from
    jira.html or the portal (dashboard.html)."""
    if execution_state.get("status") == "running":
        return _err("A run is already in progress.", 409)

    tickets = _load_tickets()
    if not any(t.get("id") == ticket_id for t in tickets):
        return _err(f"{ticket_id} not found.", 404)

    body   = request.get_json(silent=True) or {}
    user   = request.args.get("username") or body.get("user", "unknown")
    region = (request.args.get("region") or body.get("region") or "US").upper()
    env    = (request.args.get("env")    or body.get("env")    or "INT").upper()

    thread = threading.Thread(target=_run_ticket_pipeline, args=(ticket_id, region, env, user), daemon=True)
    thread.start()

    return _ok({"status": "started", "ticketId": ticket_id})


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — JIRA / BUG REGISTRY  (proxies to Spring Boot)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/registry/check", methods=["GET"])
def check_bug():
    """Duplicate-check before raising a bug — used by the manual 'Report Bug'
    modal in chat.html. Mirrors the dedup logic already in raise_bug()."""
    test_name = (request.args.get("testName") or "").strip()
    if not test_name:
        return _ok({"canRaise": True})
    bugs = _load(BUGS_FILE, [])
    existing = next((b for b in bugs if b["testCaseName"] == test_name), None)
    if existing:
        bug_ticket = _find_bug_ticket_by_key(existing["jiraKey"])
        resp = {
            "canRaise": False, "jiraKey": existing["jiraKey"],
            "raisedBy": existing["raisedBy"],
            "message": f"A bug for '{test_name}' is already open ({existing['jiraKey']}).",
        }
        if bug_ticket:
            resp["bugTicket"] = bug_ticket["id"]
            resp["message"] += f" Run it via ticket {bug_ticket['id']}."
        return _ok(resp)
    return _ok({"canRaise": True})


@app.route("/api/registry/raise", methods=["POST"])
def raise_bug():
    data     = request.get_json(silent=True) or {}
    username = request.args.get("username", "unknown")

    test_name = (data.get("testCaseName") or "").strip()
    error_msg = data.get("errorMessage", "")
    env       = data.get("env", "")
    priority  = data.get("priority", "High")
    epic      = data.get("epic", "")
    suite     = data.get("suite", "")

    if not test_name:
        return _err("testCaseName is required.", 400)

    # ── Try Spring Boot first ─────────────────────────────────────────────────
    try:
        import urllib.request as urlreq
        payload = json.dumps({
            "testCaseName": test_name,
            "errorMessage": error_msg,
            "env":          env,
            "priority":     priority,
            "epic":         epic,
            "suite":        suite,
            "raisedBy":     username,
        }).encode()
        req = urlreq.Request(
            f"{SPRINGBOOT_URL}/api/jira/raise?username={username}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlreq.urlopen(req, timeout=5) as resp:
            sb_data = json.loads(resp.read())
            # Persist locally too for dashboard
            _persist_bug(sb_data.get("jiraKey", ""), test_name, error_msg,
                         env, priority, epic, suite, username, sb_data.get("status", "success"))
            is_duplicate = str(sb_data.get("status", "")).upper() == "EXISTS"
            bug_ticket = (_find_bug_ticket_by_key(sb_data.get("jiraKey", "")) if is_duplicate
                          else _link_bug_ticket(suite, sb_data.get("jiraKey", ""), test_name, error_msg, priority, username))
            _add_feed(username, f"raised bug {sb_data.get('jiraKey','')} — {test_name}", "bug")
            resp_data = dict(sb_data)
            if bug_ticket:
                resp_data["bugTicket"] = bug_ticket["id"]
            return _ok(resp_data)
    except Exception:
        pass  # Spring Boot not running — fall through to local logic

    # ── Local dedup + fake key ────────────────────────────────────────────────
    bugs = _load(BUGS_FILE, [])
    existing = next(
        (b for b in bugs if b["testCaseName"] == test_name and b["env"] == env), None
    )
    if existing:
        bug_ticket = _find_bug_ticket_by_key(existing["jiraKey"])
        resp = {
            "status":  "EXISTS",
            "jiraKey": existing["jiraKey"],
            "user":    existing["raisedBy"],
        }
        if bug_ticket:
            resp["bugTicket"] = bug_ticket["id"]
        return _ok(resp)

    jira_key = f"QA-{1000 + len(bugs) + 1}"
    _persist_bug(jira_key, test_name, error_msg, env, priority, epic, suite, username, "success")
    bug_ticket = _link_bug_ticket(suite, jira_key, test_name, error_msg, priority, username)
    _add_feed(username, f"raised bug {jira_key} — {test_name}", "bug")
    resp = {"status": "success", "jiraKey": jira_key, "user": username}
    if bug_ticket:
        resp["bugTicket"] = bug_ticket["id"]
    return _ok(resp)


def _find_bug_ticket_by_key(bug_key):
    """Find the bug ticket already linked to a given Jira bug key, if one
    exists. Used whenever a bug turns out to be a duplicate of one already
    raised — without this, the caller only ever gets the Jira bug key back
    (e.g. 'QA-1001'), which was never a valid, runnable ticket ID."""
    if not bug_key:
        return None
    tickets = _load_tickets()
    return next((t for t in tickets if t.get("linkedBugKey") == bug_key), None)


def _link_bug_ticket(parent_ticket_id, bug_key, test_name, error_msg, priority, username):
    """When a bug is raised from a ticket-based run, create a companion 'bug
    ticket' on the Jira board linked back to the parent via parentTicket.
    Running this bug ticket will DELEGATE to the parent's existing test
    case instead of generating a new one from scratch (see
    _run_ticket_pipeline) — the parent was, by definition, already tested
    to produce this failure, so its script already covers this case.
    Returns the new ticket dict, or None if there's no real parent ticket
    to link to (suite wasn't a ticket ID — e.g. a plain suite-based run)."""
    if not parent_ticket_id:
        return None
    tickets = _load_tickets()
    parent = next((t for t in tickets if t.get("id") == parent_ticket_id), None)
    if not parent:
        return None  # 'suite' wasn't actually a ticket ID (a plain suite run) — nothing to link

    new_id = _next_ticket_id(tickets, prefix="BUG")
    bug_ticket = {
        "id": new_id, "title": f"Bug: {test_name}", "status": "Open",
        "priority": priority, "urgency": priority, "impact": "Moderate / Limited",
        "service": parent.get("service", "General"), "reporter": username, "assignee": None,
        "desc": error_msg or f"Failure raised from a run of {parent_ticket_id}.",
        "robotTags": parent.get("robotTags", []),
        "reqType": "Report a system problem", "severity": priority, "labels": "auto-linked-bug",
        "comments": [{
            "id": int(datetime.utcnow().timestamp() * 1000), "author": "AutoBot",
            "time": "Just now", "isBot": True, "avatar": "#4f8ef7",
            "content": (f"Linked to parent ticket {parent_ticket_id} (bug {bug_key}). "
                        f"Running this ticket will reuse {parent_ticket_id}'s existing "
                        f"test case instead of generating a new one."),
        }],
        "created": "Just now", "updated": "Just now", "testResults": None,
        "parentTicket": parent_ticket_id, "linkedBugKey": bug_key, "isBug": True,
    }
    tickets.insert(0, bug_ticket)
    _save_tickets(tickets)
    return bug_ticket


def _persist_bug(jira_key, test_name, error_msg, env, priority, epic, suite, username, status):
    bugs = _load(BUGS_FILE, [])
    bugs.append({
        "key":          jira_key,
        "jiraKey":      jira_key,
        "testCaseName": test_name,
        "name":         test_name,
        "errorMessage": error_msg,
        "env":          env,
        "priority":     priority,
        "epic":         epic,
        "suite":        suite,
        "raisedBy":     username,
        "user":         username,
        "status":       status,
        "time":         datetime.now().strftime("%I:%M %p"),
        "raisedAt":     _now(),
    })
    _save(BUGS_FILE, bugs)


@app.route("/api/registry", methods=["GET"])
def list_bugs():
    bugs  = _load(BUGS_FILE, [])
    user  = request.args.get("user")
    env_f = request.args.get("env")
    if user:
        bugs = [b for b in bugs if b.get("user") == user or b.get("raisedBy") == user]
    if env_f:
        bugs = [b for b in bugs if b.get("env", "").lower() == env_f.lower()]
    return _ok({"bugs": bugs, "total": len(bugs)})


@app.route("/api/registry/<jira_key>", methods=["DELETE"])
@require_admin
def delete_bug(jira_key):
    bugs   = _load(BUGS_FILE, [])
    before = len(bugs)
    bugs   = [b for b in bugs if b.get("jiraKey") != jira_key]
    if len(bugs) == before:
        return _err(f"{jira_key} not found.", 404)
    _save(BUGS_FILE, bugs)
    return _ok({"deleted": jira_key})


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — ADMIN: users summary
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/admin/users", methods=["GET"])
@require_admin
def admin_users():
    runs  = _load(RUNS_FILE, [])
    bugs  = _load(BUGS_FILE, [])
    users = []

    for uname, info in USERS_DB.items():
        u_runs = [r for r in runs if r.get("user") == uname]
        u_bugs = [b for b in bugs if b.get("user") == uname or b.get("raisedBy") == uname]
        total  = sum(r.get("total",   0) for r in u_runs)
        passed = sum(r.get("passed",  0) for r in u_runs)
        failed = sum(r.get("failed",  0) for r in u_runs)
        skip   = sum(r.get("skipped", 0) for r in u_runs)
        last   = u_runs[-1].get("timestamp", "Never") if u_runs else "Never"
        pending_bugs = [b for b in u_bugs if b.get("status") not in ("resolved", "closed")]
        users.append({
            "name":        uname,
            "role":        info["role"],
            "runs":        len(u_runs),
            "tests":       total,
            "passed":      passed,
            "failed":      failed,
            "skipped":     skip,
            "bugs":        len(u_bugs),
            "pending":     len(pending_bugs),
            "lastActive":  last,
        })
    return _ok({"users": users})


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — LIVE FEED
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/feed", methods=["GET"])
def get_feed():
    feeds = _load(FEED_FILE, [])
    limit = int(request.args.get("limit", 50))
    return _ok({"events": feeds[-limit:]})


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — HEALTH
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/health")
def health():
    return _ok({
        "service":    "AutoBot Flask",
        "version":    "1.0.0",
        "status":     "healthy",
        "run_status": execution_state["status"],
        "timestamp":  _now(),
    })


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(_):
    return _err("Not found.", 404)

@app.errorhandler(405)
def method_not_allowed(_):
    return _err("Method not allowed.", 405)

@app.errorhandler(500)
def internal_error(e):
    return _err(f"Internal error: {e}", 500)


# ── CORS ──────────────────────────────────────────────────────────────────────
@app.after_request
def cors(resp):
    if app.debug:
        resp.headers["Access-Control-Allow-Origin"]  = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,X-User-Role,X-Auth-Token"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
    return resp

@app.route("/api/<path:p>", methods=["OPTIONS"])
def options(_=None, p=None):
    return "", 204


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
  ╔═══════════════════════════════════════╗
  ║   AutoBot · AI Test Automation        ║
  ║   Flask Backend  v4.0                 ║
  ╠═══════════════════════════════════════╣
  ║  URL  → http://localhost:8000         ║
  ║  Demo: admin/admin · qa/qa123         ║
  ║        tester/test123                 ║
  ╚═══════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=8000, debug=True, threaded=True)