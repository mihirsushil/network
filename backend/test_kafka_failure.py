"""
test_kafka_failure.py — the same failure-injection proof as
test_stream_failure.py, run against the Kafka port instead of Redis
Streams: kills a real consumer process mid-batch and confirms the
production consumer recovers every uncommitted message exactly once.

Uses a fresh topic + consumer group per run (via env vars) so this test
never collides with the live dashboard's own topic or a previous run's
leftover state.

Run directly: python test_kafka_failure.py
"""

import os
import subprocess
import sys
import time
import uuid

import analyzer_kafka as ak

TOTAL_EVENTS = 12
KILL_AFTER   = 5


def isolate_topic_and_group():
    suffix = uuid.uuid4().hex[:8]
    os.environ["KAFKA_TOPIC"] = f"packets-raw-test-{suffix}"
    os.environ["KAFKA_GROUP"] = f"dashboard-group-test-{suffix}"
    ak._ensure_topic()


def publish_known_events(n):
    protocols = ["TCP", "UDP", "ICMP", "Other"]
    for i in range(n):
        ak._publish_packet(protocols[i % len(protocols)], 100 + i)
    ak._producer.flush(timeout=10)


def run_worker_and_kill(kill_after):
    """Launches the real worker process and SIGKILLs it mid-batch."""
    proc = subprocess.Popen(
        [sys.executable, "kafka_consumer_worker.py"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        env=os.environ.copy(),
    )

    committed_before_kill = 0
    for line in proc.stdout:
        if line.startswith("committed offset "):
            committed_before_kill += 1
            if committed_before_kill == kill_after:
                proc.kill()   # real SIGKILL — no graceful shutdown, no final commit
                break

    proc.wait(timeout=10)
    return committed_before_kill


def main():
    print("=== Kafka failure-injection test: kill a consumer mid-batch ===\n")

    isolate_topic_and_group()
    publish_known_events(TOTAL_EVENTS)
    print(f"published {TOTAL_EVENTS} events to topic {os.environ['KAFKA_TOPIC']}")

    committed_before_kill = run_worker_and_kill(KILL_AFTER)
    print(f"worker committed {committed_before_kill} offsets, then was SIGKILLed")
    assert committed_before_kill == KILL_AFTER, "worker didn't reach the expected kill point"

    # Unlike Redis Streams (where a stale pending entry is claimable the
    # instant a reader decides it's stale), Kafka won't reassign the dead
    # worker's partitions until the group coordinator stops seeing its
    # heartbeats for session.timeout.ms. A SIGKILL sends no LeaveGroup
    # notice, so this wait is real — it's the actual failure-detection
    # floor, not a test artifact.
    print("waiting out Kafka's session timeout before attempting recovery...")
    time.sleep(8)

    # Recovery: run the real production consumer. Kafka redelivers from the
    # last committed offset automatically — no separate reclaim step needed,
    # unlike Redis Streams' XAUTOCLAIM.
    recovered = ak.consume_activity()
    print(f"\nrecovery consume_activity(): {recovered}")
    assert recovered["total"] == TOTAL_EVENTS - KILL_AFTER, \
        "recovery didn't pick up exactly the messages the killed worker left uncommitted"

    # Idempotency: run it again immediately — must be all zeros, proving
    # the recovered messages don't get redelivered a second time.
    replay = ak.consume_activity()
    print(f"replay consume_activity():   {replay}")
    assert replay["total"] == 0, "messages were redelivered — idempotency broken"

    print("\nPASS — zero data loss and zero duplicate processing across a real SIGKILL (Kafka)")


if __name__ == "__main__":
    main()
