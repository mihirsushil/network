"""
utils.py — Shared constants and helper functions

Centralizing thresholds here means they can be tuned without touching
business logic — the same practice as storing SSD pass/fail criteria
in a configuration file rather than hard-coding them inside test scripts.
"""

# ── Latency thresholds (milliseconds) ─────────────────────────────────────────
# These mirror the RTT SLAs used when qualifying devices on a server rack.
LATENCY_WARN_MS     = 50    # yellow — degraded but operational
LATENCY_CRITICAL_MS = 200   # red    — likely hardware problem or saturated link

# ── Packet-capture settings ────────────────────────────────────────────────────
ICMP_ALERT_RATIO  = 0.15   # >15 % ICMP → flag potential errors
MIN_PACKET_SAMPLE = 20     # captures smaller than this are statistically unreliable


def classify_latency(latency_ms: float | None) -> str:
    """
    Maps a round-trip time to a three-state verdict: PASS / WARN / FAIL.

    Using three states (not just pass/fail) is standard in hardware
    qualification reports — it separates devices that are clearly broken
    from those that are degraded but still usable for lower-priority tests.
    """
    if latency_ms is None:
        return "UNKNOWN"
    if latency_ms > LATENCY_CRITICAL_MS:
        return "FAIL"
    if latency_ms > LATENCY_WARN_MS:
        return "WARN"
    return "PASS"


def safe_subnet_filename(subnet: str) -> str:
    """Returns a filesystem-safe filename stem for a report on `subnet`."""
    return "network_report_" + subnet.replace("/", "_").replace(".", "-")
