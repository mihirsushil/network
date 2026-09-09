"""
analyzer_kafka.py — the same producer/consumer pipeline as analyzer.py's
Redis Streams implementation, ported to Kafka.

Kept as a separate module rather than replacing analyzer.py so the
already-validated Redis Streams pipeline (with its own failure-injection
and throughput tests) stays intact. The concepts map directly:

  Redis Streams              Kafka
  ------------------------   -----------------------------------------
  stream                     topic
  consumer group (XGROUP)    consumer group (built in, same idea)
  XACK per entry             manual offset commit, only after processing
  stale PEL + XCLAIM         automatic: an uncommitted message is just
                             redelivered from the last committed offset
                             to whichever consumer picks up that
                             partition next — no separate reclaim step
"""

import os
import random
import time

from confluent_kafka import Consumer, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic
from scapy.all import sniff

ICMP_ALERT_THRESHOLD = 0.15

# Overridable via env vars so tests can run against an isolated
# topic/group without touching the live dashboard's data.
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")


def _topic() -> str:
    return os.environ.get("KAFKA_TOPIC", "packets-raw")


def _group() -> str:
    return os.environ.get("KAFKA_GROUP", "dashboard-group-kafka")


_producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})


def _ensure_topic() -> None:
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    existing = admin.list_topics(timeout=5).topics
    if _topic() in existing:
        return
    fs = admin.create_topics([NewTopic(_topic(), num_partitions=3, replication_factor=1)])
    for _name, f in fs.items():
        try:
            f.result()
        except KafkaException as e:
            if "already exists" not in str(e):
                raise
    time.sleep(1)  # give the broker a moment before anyone tries to use it


def _protocol_of(packet) -> str:
    if packet.haslayer("TCP"):
        return "TCP"
    if packet.haslayer("UDP"):
        return "UDP"
    if packet.haslayer("ICMP"):
        return "ICMP"
    return "Other"


def _publish_packet(proto: str, size: int) -> None:
    _producer.produce(_topic(), key=proto, value=f"{time.time()}|{proto}|{size}")


def capture_to_stream(count: int = 100) -> int:
    """Producer — same contract as analyzer.capture_to_stream(), Kafka-backed."""
    _ensure_topic()
    published = 0

    def _on_packet(packet):
        nonlocal published
        _publish_packet(_protocol_of(packet), len(packet))
        published += 1

    try:
        sniff(count=count, timeout=10, prn=_on_packet, store=False)
    except Exception as e:
        print(f"[analyzer_kafka] Packet capture failed ({e}) — publishing mock events")
        mock_protocols = (["TCP"] * 27) + (["UDP"] * 11) + (["ICMP"] * 3) + (["Other"] * 1)
        for proto in mock_protocols:
            _publish_packet(proto, random.randint(60, 1500))
            published += 1

    _producer.flush(timeout=10)
    return published


def consume_activity(idle_polls_to_stop: int = 5, poll_timeout: float = 1.0) -> dict:
    """
    Consumer — reads everything since the last committed offset, tallies
    a protocol breakdown, and commits only after processing succeeds. If
    this crashes mid-batch, whatever wasn't committed gets redelivered to
    the next consumer that joins the group — Kafka's built-in equivalent
    of reclaiming Redis's pending-entries list.
    """
    _ensure_topic()

    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": _group(),
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        # A dead consumer isn't evicted from the group (and its partitions
        # reassigned) until the coordinator stops seeing its heartbeats for
        # this long. Redis Streams has no equivalent wait — any consumer can
        # XCLAIM a stale pending entry the moment it decides to look stale.
        # Kafka's failure detection is coordinator-driven and has a real,
        # unavoidable floor on recovery time.
        "session.timeout.ms": 6000,
        "heartbeat.interval.ms": 2000,
    })
    consumer.subscribe([_topic()])

    tally = {"total": 0, "TCP": 0, "UDP": 0, "ICMP": 0, "Other": 0}
    idle = 0

    try:
        while idle < idle_polls_to_stop:
            msg = consumer.poll(timeout=poll_timeout)
            if msg is None:
                idle += 1
                continue
            idle = 0
            if msg.error():
                raise KafkaException(msg.error())

            _ts, proto, _size = msg.value().decode().split("|")
            tally["total"] += 1
            tally[proto if proto in ("TCP", "UDP", "ICMP") else "Other"] += 1

        if tally["total"] > 0:
            consumer.commit(asynchronous=False)
    finally:
        consumer.close()

    return tally


def get_activity(count: int = 100) -> dict:
    """Same shape/contract as analyzer.get_activity(), Kafka-backed."""
    capture_to_stream(count)
    breakdown = consume_activity()

    total = breakdown["total"]
    tcp   = breakdown["TCP"]
    udp   = breakdown["UDP"]
    icmp  = breakdown["ICMP"]
    other = breakdown["Other"]

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
