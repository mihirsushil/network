"""
analyzer.py — Live packet capture and protocol classification

Captures a burst of packets on the active interface and buckets them
by protocol (TCP / UDP / ICMP / Other).

KIOXIA relevance: this mirrors collecting an I/O trace from a server —
you capture a fixed burst of NVMe commands and categorize them by
operation type (reads, writes, flushes) to profile the storage workload.
High ICMP counts in a server network are a proxy for error traffic and
can indicate hardware faults or firmware instability on storage devices.
"""

import random
import time

import redis
from scapy.all import sniff

# Packets with an ICMP share above this threshold are flagged as a potential
# network problem — the same kind of go/no-go threshold used in SSD test scripts
ICMP_ALERT_THRESHOLD = 0.15   # >15 % ICMP → possible network instability

# ── Redis stream producer ───────────────────────────────────────────────────
# Decouples packet capture from whatever processes the events downstream —
# capture publishes and returns immediately instead of blocking on analysis.
STREAM_KEY = "packets:raw"

_redis = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)


def _protocol_of(packet) -> str:
    if packet.haslayer("TCP"):
        return "TCP"
    if packet.haslayer("UDP"):
        return "UDP"
    if packet.haslayer("ICMP"):
        return "ICMP"
    return "Other"


def _publish_packet(proto: str, size: int) -> None:
    _redis.xadd(STREAM_KEY, {"ts": str(time.time()), "proto": proto, "size": str(size)})


def capture_to_stream(count: int = 100) -> int:
    """
    Producer: captures live packets and publishes each one as an event to
    the Redis stream, decoupled from whatever consumes them downstream.

    Falls back to publishing synthetic events when raw sockets aren't
    available (no root) — same reasoning as the mock fallback in
    get_activity() and discovery.get_devices().

    Returns the number of events published.
    """
    published = 0

    def _on_packet(packet):
        nonlocal published
        _publish_packet(_protocol_of(packet), len(packet))
        published += 1

    try:
        # timeout=10 prevents the call from hanging if the network is quiet
        sniff(count=count, timeout=10, prn=_on_packet, store=False)
    except Exception as e:
        print(f"[analyzer] Packet capture failed ({e}) — publishing mock events")
        mock_protocols = (["TCP"] * 27) + (["UDP"] * 11) + (["ICMP"] * 3) + (["Other"] * 1)
        for proto in mock_protocols:
            _publish_packet(proto, random.randint(60, 1500))
            published += 1

    return published


# ── Redis stream consumer ───────────────────────────────────────────────────
CONSUMER_GROUP = "dashboard-group"
CONSUMER_NAME  = "dashboard-consumer-1"

# An entry idle this long in the pending list was delivered to some consumer
# that crashed (or is stuck) before acking it — safe to reclaim and retry.
STALE_PENDING_MS = 30_000


def _ensure_group() -> None:
    """Creates the consumer group once; a no-op if it already exists."""
    try:
        _redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def _reclaim_stale_entries() -> list[tuple[str, dict]]:
    """
    Claims entries that were delivered to a consumer but never acknowledged
    — e.g. a consumer crashed between XREADGROUP and XACK. Reprocessing them
    here is safe: tallying is a pure function of each entry's own fields, so
    handling the same entry_id twice can't inflate a count, and an entry
    that's already been acked can never be redelivered at all.
    """
    claimed = []
    cursor = "0-0"
    while True:
        cursor, entries, _ = _redis.xautoclaim(
            STREAM_KEY, CONSUMER_GROUP, CONSUMER_NAME,
            min_idle_time=STALE_PENDING_MS, start_id=cursor, count=500,
        )
        claimed.extend(entries)
        if cursor == "0-0":
            break
    return claimed


def consume_activity() -> dict:
    """
    Consumer: reclaims any abandoned (delivered-but-unacked) entries, reads
    everything new, aggregates a protocol breakdown keyed by entry ID so a
    given event is only ever counted once, and acknowledges each one so it
    isn't redelivered. Independent of capture_to_stream() — it only cares
    about what's sitting in the stream, however it got there.
    """
    _ensure_group()

    new_response = _redis.xreadgroup(CONSUMER_GROUP, CONSUMER_NAME, {STREAM_KEY: ">"}, count=10_000)
    new_entries = [
        (entry_id, fields)
        for _stream_name, records in new_response
        for entry_id, fields in records
    ]

    seen = set()
    tally = {"total": 0, "TCP": 0, "UDP": 0, "ICMP": 0, "Other": 0}
    ack_ids = []

    for entry_id, fields in _reclaim_stale_entries() + new_entries:
        if entry_id in seen:
            continue
        seen.add(entry_id)

        tally["total"] += 1
        proto = fields.get("proto", "Other")
        tally[proto if proto in ("TCP", "UDP", "ICMP") else "Other"] += 1
        ack_ids.append(entry_id)

    if ack_ids:
        _redis.xack(STREAM_KEY, CONSUMER_GROUP, *ack_ids)

    return tally


def get_activity(count: int = 100) -> dict:
    """
    Publishes a fresh burst of `count` packet events to the stream, then
    consumes whatever the group hasn't seen yet and returns a protocol
    breakdown with a derived alert flag.

    The `count` parameter is the "sample size" — analogous to the IOPS burst
    window used in SSD benchmark scripts to get a statistically stable reading.
    """
    capture_to_stream(count)
    breakdown = consume_activity()

    total = breakdown["total"]
    tcp   = breakdown["TCP"]
    udp   = breakdown["UDP"]
    icmp  = breakdown["ICMP"]
    other = breakdown["Other"]

    # ICMP ratio is a lightweight error-rate indicator; spikes often signal
    # retransmits or hardware faults in storage-heavy server traffic
    icmp_ratio = round(icmp / total, 3) if total > 0 else 0.0
    alert = icmp_ratio > ICMP_ALERT_THRESHOLD

    return {
        "total_packets": total,
        "TCP":           tcp,
        "UDP":           udp,
        "ICMP":          icmp,
        "Other":         other,
        "icmp_ratio":    icmp_ratio,
        "alert":         alert,
        "alert_message": (
            f"High ICMP ratio ({icmp_ratio:.1%}) — possible network instability"
            if alert else None
        ),
    }
