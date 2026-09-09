"""
throughput_test.py — measures event-processing throughput at 1 vs 3
concurrent consumers pulling from the same Redis Streams consumer group,
to get a real number for how horizontal scaling behaves here rather than
an assumed one.

Each consumer repeatedly claims a small batch of new entries and acks
them one at a time, backing off only after a few consecutive empty reads
— the same incremental-claim pattern a real long-running consumer would
use, not a single greedy read that would starve the other workers.

Run directly: python throughput_test.py
"""

import multiprocessing
import time

import analyzer

EVENTS_PER_RUN      = 300
BATCH_SIZE          = 20
PROCESSING_DELAY_S  = 0.01   # stand-in for real per-event work
IDLE_READS_TO_STOP  = 3      # consecutive empty polls before a worker assumes it's done


def reset_stream():
    analyzer._redis.delete(analyzer.STREAM_KEY)
    try:
        analyzer._redis.xgroup_destroy(analyzer.STREAM_KEY, analyzer.CONSUMER_GROUP)
    except Exception:
        pass


def publish_events(n):
    protocols = ["TCP", "UDP", "ICMP", "Other"]
    for i in range(n):
        analyzer._publish_packet(protocols[i % len(protocols)], 100)


def consumer_loop(consumer_name, counter):
    """Repeatedly claims small batches until the stream has nothing new left."""
    r = analyzer._redis
    processed = 0
    idle_reads = 0

    while idle_reads < IDLE_READS_TO_STOP:
        response = r.xreadgroup(
            analyzer.CONSUMER_GROUP, consumer_name,
            {analyzer.STREAM_KEY: ">"}, count=BATCH_SIZE, block=200,
        )
        entries = [
            (entry_id, fields)
            for _stream_name, records in (response or [])
            for entry_id, fields in records
        ]

        if not entries:
            idle_reads += 1
            continue
        idle_reads = 0

        for entry_id, _fields in entries:
            time.sleep(PROCESSING_DELAY_S)
            r.xack(analyzer.STREAM_KEY, analyzer.CONSUMER_GROUP, entry_id)
            processed += 1

    with counter.get_lock():
        counter.value += processed


def run_scenario(num_consumers):
    reset_stream()
    publish_events(EVENTS_PER_RUN)
    analyzer._ensure_group()

    counter = multiprocessing.Value("i", 0)
    start = time.perf_counter()

    procs = [
        multiprocessing.Process(target=consumer_loop, args=(f"worker-{i}", counter))
        for i in range(num_consumers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    elapsed = time.perf_counter() - start
    throughput = counter.value / elapsed if elapsed > 0 else 0
    return counter.value, elapsed, throughput


def main():
    print("=== Throughput: 1 vs 3 concurrent consumers ===\n")

    processed_1, time_1, tput_1 = run_scenario(1)
    print(f"1 consumer:  {processed_1} events in {time_1:.2f}s  ->  {tput_1:.1f} events/sec")

    processed_3, time_3, tput_3 = run_scenario(3)
    print(f"3 consumers: {processed_3} events in {time_3:.2f}s  ->  {tput_3:.1f} events/sec")

    speedup = tput_3 / tput_1 if tput_1 > 0 else 0
    print(f"\nSpeedup with 3 consumers: {speedup:.2f}x")

    assert processed_1 == EVENTS_PER_RUN, "1-consumer run lost or duplicated events"
    assert processed_3 == EVENTS_PER_RUN, "3-consumer run lost or duplicated events"
    print("\nPASS — both runs processed every event exactly once")


if __name__ == "__main__":
    main()
