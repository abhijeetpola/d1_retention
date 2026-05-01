"""Sheet store — fetch, cache, and freshness for the registered Google Sheets tabs.

This module is the only place network I/O happens for sheet ingestion. Every
data-reading helper (`tools._common.sheet`, `get_rows`, the math tools) goes
through `ensure_fresh(name)` before reading the local CSV.

Design notes (see /Users/santosh.kumar1/.claude/plans/i-want-this-whole-transient-glade.md):

- Google publish-to-web does NOT support conditional GET. We do not send
  If-Modified-Since or If-None-Match. Every refresh outside the schedule
  window is a full body download.
- A SHA-256 hash of the response body is the only correctness mechanism for
  detecting genuine content change. The hash is what gates the disk write
  and the in-memory DataFrame invalidation.
- Schedule: the first ./tune run on or after 11:00 IST refreshes any
  pre_fetch tab whose last_fetched_at is earlier than today's threshold.
  Same-day later runs are silent.
- Concurrency: per-tab fcntl.flock. Two parallel runs cannot corrupt one
  cache. POSIX-only; the project is mac/Linux per CLAUDE.md.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = (PROJECT_ROOT / "data").resolve()
SHEETS_DIR = DATA_DIR / "sheets"
CACHE_DIR = SHEETS_DIR / "_cache"
REGISTRY_PATH = SHEETS_DIR / "_registry.yaml"

IST = ZoneInfo("Asia/Kolkata")

_URL_TEMPLATE = (
    "https://docs.google.com/spreadsheets/d/e/{pub_key}/pub"
    "?gid={gid}&single=true&output=csv"
)


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

_REGISTRY_CACHE: dict[str, Any] | None = None


def _load_registry() -> dict[str, Any]:
    """Read and validate _registry.yaml. Cached after first call."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE

    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Sheet registry missing: {REGISTRY_PATH}")

    raw = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{REGISTRY_PATH} must be a YAML mapping at the top level")
    for key in ("spreadsheet", "refresh_schedule", "tabs"):
        if key not in raw:
            raise ValueError(f"{REGISTRY_PATH} missing required key: {key}")
    if not isinstance(raw["tabs"], dict) or not raw["tabs"]:
        raise ValueError(f"{REGISTRY_PATH}: 'tabs' must be a non-empty mapping")
    if "pub_key" not in raw["spreadsheet"]:
        raise ValueError(f"{REGISTRY_PATH}: spreadsheet.pub_key is required")

    # Light per-tab validation; surface gid typos early.
    for name, entry in raw["tabs"].items():
        if not isinstance(entry, dict):
            raise ValueError(f"{REGISTRY_PATH}: tabs.{name} must be a mapping")
        if "gid" not in entry or not str(entry["gid"]).strip():
            raise ValueError(f"{REGISTRY_PATH}: tabs.{name}.gid is required")

    _REGISTRY_CACHE = raw
    return raw


def _resolve_alias(name: str) -> str:
    """Map an alias to the canonical sheet name. Returns name unchanged if no alias matches."""
    reg = _load_registry()
    if name in reg["tabs"]:
        return name
    for canonical, entry in reg["tabs"].items():
        aliases = entry.get("aliases") or []
        if name in aliases:
            return canonical
    known = sorted(reg["tabs"].keys())
    raise KeyError(f"unknown sheet name: {name!r}. Known: {known}")


def _tab_url(name: str) -> str:
    reg = _load_registry()
    pub_key = reg["spreadsheet"]["pub_key"]
    gid = reg["tabs"][name]["gid"]
    return _URL_TEMPLATE.format(pub_key=pub_key, gid=gid)


def _csv_path(name: str) -> Path:
    return SHEETS_DIR / f"{name}.csv"


def _meta_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.meta"


def _lock_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.lock"


def _read_meta(name: str) -> dict[str, Any]:
    p = _meta_path(name)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(name: str, meta: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _meta_path(name)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


def _threshold_hour() -> int:
    reg = _load_registry()
    raw = reg["refresh_schedule"].get("daily_threshold_ist", "11:00")
    return int(str(raw).split(":")[0])


def latest_threshold_passed_utc() -> datetime:
    """Return the most recent IST threshold instant that has elapsed, in UTC."""
    hour = _threshold_hour()
    now_ist = datetime.now(IST)
    today_threshold_ist = datetime.combine(
        now_ist.date(), time(hour), tzinfo=IST,
    )
    if now_ist >= today_threshold_ist:
        return today_threshold_ist.astimezone(timezone.utc)
    return (today_threshold_ist - timedelta(days=1)).astimezone(timezone.utc)


def is_due_for_refresh(name: str) -> bool:
    name = _resolve_alias(name)
    csv = _csv_path(name)
    meta = _read_meta(name)
    if not csv.exists():
        return True
    last = meta.get("last_fetched_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True
    return last_dt < latest_threshold_passed_utc()


# ---------------------------------------------------------------------------
# Fetch + cache
# ---------------------------------------------------------------------------


def _fetch_body(url: str, timeout: int) -> bytes:
    """GET the URL and return the body. Raises urllib errors on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "tune-sheet-store/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _looks_like_csv(body: bytes) -> bool:
    """Cheap sanity check: rule out HTML rate-limit pages dressed as 200 OK."""
    head = body[:1024].lstrip().lower()
    if not head:
        return False
    return not head.startswith(b"<")


def _format_ist(utc_iso: str | None) -> str:
    """Render a UTC ISO timestamp as 'YYYY-MM-DD HH:MM IST', or '(never)' if absent."""
    if not utc_iso:
        return "(never)"
    try:
        dt = datetime.fromisoformat(utc_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")
    except (ValueError, TypeError):
        return utc_iso


def _refresh_one(name: str, *, force: bool) -> dict[str, Any]:
    """Refresh one sheet. Returns a status dict with keys:
       name, status (fetched|no-change|cached|skipped|error), bytes, message,
       last_fetched_at (UTC ISO), last_fetched_ist (display string).
    """
    name = _resolve_alias(name)
    reg = _load_registry()
    timeout = int(reg["refresh_schedule"].get("network_timeout_seconds", 30))
    url = _tab_url(name)
    csv = _csv_path(name)
    meta = _read_meta(name)

    def _result(status: str, message: str, byte_count: int | None = None) -> dict[str, Any]:
        """Build a result dict, picking up the latest last_fetched_at from the meta on disk."""
        current_meta = _read_meta(name)
        ts = current_meta.get("last_fetched_at")
        return {
            "name": name,
            "status": status,
            "bytes": byte_count if byte_count is not None else (csv.stat().st_size if csv.exists() else 0),
            "message": message,
            "last_fetched_at": ts,
            "last_fetched_ist": _format_ist(ts),
        }

    if not force and not is_due_for_refresh(name):
        return _result("skipped", "not due (within schedule window)")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)

    lock_file = _lock_path(name)
    lock_file.touch(exist_ok=True)

    with lock_file.open("rb") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            # Re-check after acquiring the lock — another process may have refreshed.
            if not force and not is_due_for_refresh(name):
                return _result("skipped", "another run refreshed it while we waited")

            try:
                body = _fetch_body(url, timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if csv.exists():
                    return _result("cached", f"network error ({e}); using cached copy")
                return _result("error", f"network error ({e}); no cache available", byte_count=0)

            if not _looks_like_csv(body):
                if csv.exists():
                    return _result("cached", "response was not CSV; using cached copy")
                return _result("error", "response was not CSV and no cache available", byte_count=0)

            new_hash = hashlib.sha256(body).hexdigest()
            now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

            if csv.exists() and meta.get("content_sha256") == new_hash:
                meta["last_fetched_at"] = now_utc
                _write_meta(name, meta)
                return _result("no-change", "content identical to cached copy")

            tmp = csv.with_suffix(csv.suffix + ".tmp")
            tmp.write_bytes(body)
            os.replace(tmp, csv)

            meta = {
                "content_sha256": new_hash,
                "last_fetched_at": now_utc,
                "last_changed_at": now_utc,
                "schema_columns": _peek_columns(csv),
            }
            _write_meta(name, meta)
            return _result("fetched", "updated", byte_count=len(body))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _peek_columns(csv: Path) -> list[str]:
    try:
        with csv.open("r", encoding="utf-8", errors="replace") as f:
            header = f.readline().strip()
        return [c.strip() for c in header.split(",") if c.strip()]
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_fresh(name: str) -> Path:
    """Return a path to the local CSV for `name`, refreshing if due.

    Resolves aliases. Network failures fall back to the cached file with no
    error raised; the caller can read what is on disk. Raises only if the
    sheet is unknown or has no cache and the network fails.
    """
    canonical = _resolve_alias(name)
    csv = _csv_path(canonical)

    if not csv.exists() or is_due_for_refresh(canonical):
        result = _refresh_one(canonical, force=False)
        if result["status"] == "error":
            raise FileNotFoundError(
                f"sheet {canonical!r} could not be fetched and has no cached copy: "
                f"{result['message']}"
            )

    return csv


def force_refresh(name: str) -> dict[str, Any]:
    """Bypass the schedule check and refresh `name` now."""
    canonical = _resolve_alias(name)
    return _refresh_one(canonical, force=True)


def prefetch_due_sheets() -> list[dict[str, Any]]:
    """Refresh every pre_fetch tab whose schedule window has passed.

    Called from `tune` preflight. Returns one result dict per tab so the
    caller can render a status line per sheet.
    """
    reg = _load_registry()
    out: list[dict[str, Any]] = []
    for name, entry in reg["tabs"].items():
        if not entry.get("pre_fetch"):
            continue
        out.append(_refresh_one(name, force=False))
    return out


def force_refresh_all() -> list[dict[str, Any]]:
    """Force-refresh every pre_fetch tab. For ./tune --refresh."""
    reg = _load_registry()
    out: list[dict[str, Any]] = []
    for name, entry in reg["tabs"].items():
        if not entry.get("pre_fetch"):
            continue
        out.append(_refresh_one(name, force=True))
    return out


def list_sheets() -> list[dict[str, Any]]:
    """Return registered tabs with metadata for discovery (no network calls)."""
    reg = _load_registry()
    threshold = latest_threshold_passed_utc()
    out: list[dict[str, Any]] = []
    for name, entry in reg["tabs"].items():
        meta = _read_meta(name)
        last_fetched = meta.get("last_fetched_at")
        try:
            last_dt = (
                datetime.fromisoformat(last_fetched) if last_fetched else None
            )
            if last_dt and last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            last_dt = None
        out.append({
            "name": name,
            "primary": bool(entry.get("primary", False)),
            "pre_fetch": bool(entry.get("pre_fetch", False)),
            "description": entry.get("description", ""),
            "dictionary": entry.get("dictionary"),
            "aliases": entry.get("aliases") or [],
            "last_fetched_at": last_fetched,
            "last_changed_at": meta.get("last_changed_at"),
            "schema_columns": meta.get("schema_columns") or [],
            "due_for_refresh": (
                last_dt is None or last_dt < threshold
            ),
        })
    return out


def synthesize_url(name: str) -> str:
    """Public wrapper around _tab_url for the doctor check."""
    return _tab_url(_resolve_alias(name))


def registry_summary() -> dict[str, Any]:
    """Compact summary the doctor uses."""
    reg = _load_registry()
    return {
        "tab_count": len(reg["tabs"]),
        "tab_names": list(reg["tabs"].keys()),
        "threshold_ist": reg["refresh_schedule"].get("daily_threshold_ist"),
        "threshold_utc": latest_threshold_passed_utc().isoformat(timespec="seconds"),
        "cache_dir": str(CACHE_DIR),
    }
