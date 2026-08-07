"""
Per-user cost & resource controls (the cost-abuse mitigation core).

In-memory (resets on process restart). Composed of:
  - Token-bucket request rate limiter per user  -> 429 on burst.
  - Usage counters (STT sec / NMT chars / TTS chars) with a monthly cap.
  - Active connection cap per user.
  - WebSocket message-size cap.

All limits are configurable via env. When a limit is not configured / zero, the
corresponding control is disabled, so operators can adopt gradually.
"""
import os
import time
import threading
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("QuotaEngine")

# ---- Configuration (from env) ----
_RATE_LIMIT_RPM = float(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))      # token bucket refill per minute
_RATE_BURST = float(os.getenv("RATE_LIMIT_BURST", "20"))                 # bucket capacity (burst)
_MONTHLY_CREDITS = float(os.getenv("USER_MONTHLY_CREDITS", "0"))         # 0 = unlimited
_MAX_CONNS_PER_USER = int(os.getenv("MAX_CONNECTIONS_PER_USER", "2"))    # 0 = unlimited
_MAX_WS_MSG_BYTES = int(os.getenv("MAX_WS_MSG_BYTES", str(2 * 1024 * 1024)))  # 2 MB


def max_ws_message_bytes() -> int:
    return _MAX_WS_MSG_BYTES


class RateLimiter:
    """Minimal thread-safe token bucket keyed by user."""

    def __init__(self, refill_per_min: float, capacity: float):
        self._refill_per_sec = refill_per_min / 60.0 if refill_per_min > 0 else 0.0
        self._capacity = capacity
        self._buckets: Dict[str, Dict[str, float]] = {}
        self._lock = threading.Lock()

    def enabled(self) -> bool:
        return self._refill_per_sec > 0 and self._capacity > 0

    def allow(self, key: str, cost: float = 1.0) -> bool:
        if not self.enabled():
            return True
        now = time.monotonic()
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = {"tokens": self._capacity, "last": now}
                self._buckets[key] = b
            elapsed = now - b["last"]
            b["tokens"] = min(self._capacity, b["tokens"] + elapsed * self._refill_per_sec)
            b["last"] = now
            if b["tokens"] < cost:
                return False
            b["tokens"] -= cost
            return True


class UsageQuota:
    """Per-user rolling usage counters with a monthly cap."""

    def __init__(self, monthly_credits: float):
        self._monthly_credits = monthly_credits
        self._usage: Dict[str, Dict[str, float]] = {}
        self._month_key: Dict[str, str] = {}
        self._lock = threading.Lock()

    def _month(self) -> str:
        return time.strftime("%Y-%m")

    def reset_if_month_changed(self, user_id: str):
        key = self._month()
        with self._lock:
            if self._month_key.get(user_id) != key:
                self._month_key[user_id] = key
                self._usage[user_id] = {"stt_sec": 0.0, "nmt_chars": 0.0, "tts_chars": 0.0, "total": 0.0}

    def ensure(self, user_id: str):
        self.reset_if_month_changed(user_id)
        with self._lock:
            self._usage.setdefault(user_id, {"stt_sec": 0.0, "nmt_chars": 0.0, "tts_chars": 0.0, "total": 0.0})

    def check(self, user_id: str) -> Tuple[bool, Dict[str, float]]:
        """Return (allowed, current_usage). Hard-stop when total >= cap."""
        self.ensure(user_id)
        with self._lock:
            usage = dict(self._usage[user_id])
        if self._monthly_credits > 0 and usage["total"] >= self._monthly_credits:
            return False, usage
        return True, usage

    def add(self, user_id: str, metric: str, amount: float):
        self.ensure(user_id)
        with self._lock:
            u = self._usage[user_id]
            u[metric] = u.get(metric, 0.0) + amount
            u["total"] = u["total"] + amount


class ConnectionTracker:
    """Active connection counter per user."""

    def __init__(self, max_conns: int):
        self._max = max_conns
        self._counts: Dict[str, int] = {}
        self._lock = threading.Lock()

    def enabled(self) -> bool:
        return self._max > 0

    def try_acquire(self, user_id: str) -> bool:
        if not self.enabled():
            return True
        with self._lock:
            c = self._counts.get(user_id, 0)
            if c >= self._max:
                return False
            self._counts[user_id] = c + 1
            return True

    def release(self, user_id: str):
        with self._lock:
            c = self._counts.get(user_id, 0)
            if c <= 1:
                self._counts.pop(user_id, None)
            else:
                self._counts[user_id] = c - 1


# Singleton instances used by main.py
rate_limiter = RateLimiter(_RATE_LIMIT_RPM, _RATE_BURST)
usage_quota = UsageQuota(_MONTHLY_CREDITS)
connection_tracker = ConnectionTracker(_MAX_CONNS_PER_USER)
