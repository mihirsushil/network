"""
test_stream_failure.py — failure-injection test for the Redis Streams
pipeline in analyzer.py.

Publishes a known batch of events, runs a real separate consumer process
against them, and SIGKILLs it partway through — a genuine crash, not a
simulated one. Then proves the production consume_activity() recovers
every entry the killed process never acked (zero data loss) and that
running it again afterward picks up nothing further (zero duplicate
processing).

Run directly: python test_stream_failure.py
"""

import subprocess
import sys

import analyzer

TOTAL_EVENTS = 12
KILL_AFTER   = 5   # SIGKILL the worker after it has acked this many entries


def reset_stream():
    analyzer._redis.delete(analyzer.STREAM_KEY)
    try:
        analyzer._redis.xgroup_destroy(analyzer.STREAM_KEY, analyzer.CONSUMER_GROUP)
    except Exception:
        pass


def publish_known_events(n):
    protocols = ["TCP", "UDP", "ICMP", "Other"]
    for i in range(n):
        analyzer._publish_packet(protocols[i % len(protocols)], 100 + i)


def pending_count():
    summary = analyzer._redis.xpending(analyzer.STREAM_KEY, analyzer.CONSUMER_GROUP)
    return summary["pending"] if summary else 0


def run_worker_and_kill(kill_after):
    """Launches the real worker process and SIGKILLs it mid-batch."""
    proc = subprocess.Popen(
        [sys.executable, "stream_consumer_worker.py", "worker-under-test"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )

    acked_before_kill = 0
    for line in proc.stdout:
        if line.startswith("acked "):
            acked_before_kill += 1
            if acked_before_kill == kill_after:
                proc.kill()   # real SIGKILL — no graceful shutdown, no final ack
                break

    proc.wait(timeout=5)
    return acked_before_kill


def main():
    print("=== Failure-injection test: kill a consumer mid-batch ===\n")

    reset_stream()
    publish_known_events(TOTAL_EVENTS)
    print(f"published {TOTAL_EVENTS} events")

    acked_before_kill = run_worker_and_kill(KILL_AFTER)
    print(f"worker acked {acked_before_kill} entries, then was SIGKILLed")
    assert acked_before_kill == KILL_AFTER, "worker didn't reach the expected kill point"

    stuck = pending_count()
    print(f"entries left pending in Redis after the kill: {stuck}")
    assert stuck == TOTAL_EVENTS - KILL_AFTER, "unexpected number of entries stuck in the PEL"

    # Recovery: run the real production consumer. Force immediate reclaim
    # instead of waiting out the normal 30s staleness window — the mechanism
    # being tested is the reclaim logic itself, not the timeout.
    analyzer.STALE_PENDING_MS = 0
    recovered = analyzer.consume_activity()
    print(f"\nrecovery consume_activity(): {recovered}")
    assert recovered["total"] == TOTAL_EVENTS - KILL_AFTER, \
        "recovery didn't pick up exactly the entries the killed worker left behind"

    # Idempotency: run it again immediately — must be all zeros, proving
    # the recovered entries don't get redelivered a second time.
    replay = analyzer.consume_activity()
    print(f"replay consume_activity():   {replay}")
    assert replay["total"] == 0, "entries were redelivered — idempotency broken"

    assert pending_count() == 0, "entries left un-acked after recovery"

    print("\nPASS — zero data loss and zero duplicate processing across a real SIGKILL")


if __name__ == "__main__":
    main()
