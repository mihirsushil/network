"""
kafka_consumer_worker.py — standalone Kafka consumer process used by
test_kafka_failure.py.

Mirrors stream_consumer_worker.py's role for the Redis Streams pipeline:
read a message, "process" it (a short sleep stands in for real work),
commit its offset individually, and print progress after each commit so
the test harness can SIGKILL this process at a precise, repeatable point
mid-batch — the same failure mode a crash or OOM kill would produce in
production.

Topic/group are read from KAFKA_TOPIC / KAFKA_GROUP env vars so the test
can point this at an isolated topic per run.
"""

import time

from confluent_kafka import Consumer, KafkaException

import analyzer_kafka as ak


def main():
    consumer = Consumer({
        "bootstrap.servers": ak.BOOTSTRAP_SERVERS,
        "group.id": ak._group(),
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "session.timeout.ms": 6000,
        "heartbeat.interval.ms": 2000,
    })
    consumer.subscribe([ak._topic()])

    try:
        idle = 0
        while idle < 5:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                idle += 1
                continue
            idle = 0
            if msg.error():
                raise KafkaException(msg.error())

            time.sleep(0.05)  # stand-in for real processing work
            consumer.commit(message=msg, asynchronous=False)
            print(f"committed offset {msg.offset()}", flush=True)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
