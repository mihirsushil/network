"""
stream_consumer_worker.py — standalone consumer process used by
test_stream_failure.py.

Reads a batch of packet events from the stream and processes each one
(a short sleep stands in for real work) before acking it individually.
Printing progress after every ack lets the test harness SIGKILL this
process at a precise, repeatable point mid-batch — the same failure mode
a crash or OOM kill would produce in production.
"""

import sys
import time

import analyzer


def main():
    consumer_name = sys.argv[1] if len(sys.argv) > 1 else "worker-under-test"
    analyzer._ensure_group()

    response = analyzer._redis.xreadgroup(
        analyzer.CONSUMER_GROUP, consumer_name, {analyzer.STREAM_KEY: ">"}, count=10_000
    )
    entries = [
        (entry_id, fields)
        for _stream_name, records in response
        for entry_id, fields in records
    ]

    for entry_id, _fields in entries:
        time.sleep(0.05)  # stand-in for real processing work
        analyzer._redis.xack(analyzer.STREAM_KEY, analyzer.CONSUMER_GROUP, entry_id)
        print(f"acked {entry_id}", flush=True)


if __name__ == "__main__":
    main()
