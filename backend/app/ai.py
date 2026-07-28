"""AI features via FAU Trussed.ai (an OpenAI-compatible LLM gateway, model gpt-5.4).

The API key lives ONLY server-side in TRUSSED_API_KEY (never shipped to the
browser). Two grounded features are exposed through the API:
  1. nl_to_filters() — turn plain English into structured fleet filters
  2. fleet_briefing() — summarize live fleet stats into a manager-readable briefing

All calls are defensive: missing key, timeouts, and provider errors map to
friendly messages (see AIError) rather than crashing.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env here too — this module may be imported before app.db (which also
# loads it), and it reads the Trussed config at import time.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE_URL = os.environ.get("TRUSSED_BASE_URL", "https://fauengtrussed.fau.edu/provider/generic")
MODEL = os.environ.get("TRUSSED_MODEL", "gpt-5.4")
API_KEY = os.environ.get("TRUSSED_API_KEY", "")
TIMEOUT = 30


class AIError(Exception):
    """An AI failure with an HTTP status and a user-friendly message."""
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def is_configured() -> bool:
    return bool(API_KEY)


# --- simple per-user rate limiter (protects the shared course budget) --------
_RL_MAX = 15          # requests
_RL_WINDOW = 60.0     # seconds
_rl_lock = threading.Lock()
_rl: dict[str, list[float]] = {}


def check_rate_limit(key: str) -> bool:
    now = time.monotonic()
    with _rl_lock:
        hits = [t for t in _rl.get(key, []) if now - t < _RL_WINDOW]
        if len(hits) >= _RL_MAX:
            _rl[key] = hits
            return False
        hits.append(now)
        _rl[key] = hits
        return True


def _provider_error(status: int) -> str:
    if status in (401, 403):
        return "The Trussed API key is invalid or unauthorized (check TRUSSED_API_KEY)."
    if status == 404:
        return "That model isn't on your allowlist — set TRUSSED_MODEL (e.g. gpt-5.4)."
    if status == 429:
        return "AI is rate-limited or out of budget — wait a moment and try again."
    return "The AI service returned an error. Please try again."


def _chat(messages: list[dict], *, json_mode: bool = False,
          max_tokens: int = 500, temperature: float = 0.3) -> str:
    if not API_KEY:
        raise AIError("AI is not configured on the server (missing TRUSSED_API_KEY).", 503)
    body = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=TIMEOUT,
        )
    except requests.Timeout:
        raise AIError("The AI service timed out. Please try again.", 504)
    except requests.RequestException:
        raise AIError("Couldn't reach the AI service. Please try again.", 502)

    if not resp.ok:
        status = resp.status_code if 400 <= resp.status_code < 600 else 502
        raise AIError(_provider_error(resp.status_code), status)

    data = resp.json()
    return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()


def _extract_json(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


# --- Feature 1: natural-language fleet search -------------------------------
_SITES = ["Depot-North", "Depot-South", "Yard-A", "Yard-B", "Substation-3"]
_COMPANIES = ["Northwind Energy", "Cascade Logistics", "Harbor Marine", "Summit Materials", "Delta Freight"]
_EQUIPMENT = ["Forklift", "AGV", "Yard Tractor", "Backup UPS", "Ground Power Unit", "Reach Stacker"]


def nl_to_filters(query: str) -> dict:
    system = f"""You convert a plain-English request into structured filters for a battery-fleet dashboard.

Return ONLY a JSON object with exactly these keys:
- status: one of "ok", "warning", "critical", or "" (all)
- site: one of {_SITES} or ""
- company: one of {_COMPANIES} or ""
- equipment: one of {_EQUIPMENT} or ""
- soc_max: a number 0-100 for "state of charge at or below N", or null
- soc_min: a number 0-100 for "at or above N", or null
- search: free-text device id/label keyword, or ""
- explanation: one short sentence describing how you interpreted the request

Use "" or null for anything not constrained. Map "low/critical battery" to status or soc_max sensibly."""
    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": query}],
        json_mode=True, max_tokens=300, temperature=0.1,
    )
    filters = _extract_json(content)
    if filters is None:
        raise AIError("Couldn't interpret that request — try rephrasing.", 502)
    return filters


# --- Feature 3: in-app support assistant (chatbot) --------------------------
ASSISTANT_SYSTEM = """You are the Symbern Fleet Intelligence in-app assistant. You help users
use this web application and, when they need human help, you guide them to open a support ticket.

The platform has two domains, switched via the "Fleet / Production" toggle in the header:
- FLEET INTELLIGENCE: a live grid of deployed battery packs (state of charge, pack voltage,
  current, temperature, status). Features: click a pack for trend charts + notes; the "Ask AI"
  bar (plain-English fleet search); "AI Briefing"; an Active Alerts panel; status pills and an
  advanced Filters panel (site/company/equipment/SoC range/alarms); CSV/Excel export; a Daily
  Report; a no-code Query Builder; a manual Refresh; and a "Realtime" WebSocket badge.
- PRODUCTION TEST RECORDS: manufacturing QA. A Daily Production Summary (tested/pass/fail,
  pass%, most-failed product/fixture/station), a Pass/Fail lookup table with filters, a universal
  search (serial/part/product/station/fixture/operator), serial drill-down history, and export.

Roles: viewer (read-only), engineer/supervisor (can add pack notes), administrator (also manages
users via the "Users" button). Alert thresholds are configurable by an admin in backend config.

Answer concisely (2-4 sentences), specific to this app. If the user reports a bug, needs access/
permissions, needs data changed, or needs IT or management help you can't resolve, tell them to
click "Start a support ticket" in this chat and pick IT or Management. Never invent live data or
numbers — point them to the relevant screen instead."""


def assistant_reply(messages: list[dict]) -> str:
    convo = [{"role": "system", "content": ASSISTANT_SYSTEM}] + messages[-12:]
    return _chat(convo, max_tokens=350, temperature=0.4)


# --- Feature 2: fleet health briefing ---------------------------------------
def fleet_briefing(stats: dict) -> str:
    system = (
        "You are a battery-fleet operations assistant. Given live fleet statistics as "
        "JSON, write a concise 3-4 sentence health briefing for a fleet manager. Lead "
        "with overall status, call out the most urgent packs/alarms by name, and note any "
        "site or equipment pattern. Be specific with numbers. Plain prose, no markdown, no headers."
    )
    return _chat(
        [{"role": "system", "content": system},
         {"role": "user", "content": json.dumps(stats)}],
        max_tokens=350, temperature=0.4,
    )
