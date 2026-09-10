# Network Monitor

A local network dashboard: ARP-based device discovery, live packet-capture
traffic analysis, and latency-based PASS/WARN/FAIL verdicts, served by a
Flask API to a React frontend.

Packet capture and traffic classification run through a Redis Streams
pipeline rather than being computed inline on each request — see
[Why Redis Streams](#why-redis-streams) for the reasoning and what it
actually buys.

## Stack

- **Frontend** — React (Create React App), Recharts, no component library.
  Dark theme, custom easing curves, staggered entrance animations, skeleton
  loading states.
- **Backend** — Flask, Scapy (ARP scan + packet capture), Redis Streams
  (event pipeline), `mac-vendor-lookup`.
- **c-modules/** — a standalone libpcap capture tool in C for
  higher-precision timing. Not currently wired into the Flask app.

## Running it

```bash
# Redis (required)
brew install redis
redis-server /opt/homebrew/etc/redis.conf &

# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r ../requirements.txt
python app.py                     # http://127.0.0.1:5000

# Frontend
cd frontend
npm install
npm start                         # http://localhost:3001 (PORT=3001)
```

### Or with Docker Compose

```bash
docker compose up --build
# backend  → http://localhost:5000
# frontend → http://localhost:3001
```

Raw sockets need `NET_RAW`/`NET_ADMIN`, granted to the backend container in
`docker-compose.yml`; without host-level access to the physical interface
(e.g. Docker Desktop on macOS) it still runs fine on the mock-data fallback.

Raw sockets (ARP scan, live packet capture) need root on macOS/Linux.
Running unprivileged is fully supported — both `discovery.py` and
`analyzer.py` fall back to synthetic mock data instead of failing, so the
UI and the Streams pipeline are exercisable without `sudo`.

## Why Redis Streams

The dashboard used to call `scapy.sniff()` synchronously inside the
`/activity` request handler — capture and processing were the same step,
in the same process, on every request. That's fine for a demo, but it
means:

- Capture speed is coupled to processing speed — a slow consumer downstream
  would eventually mean dropped packets, not just a slow response.
- A crash or bug in the processing logic takes capture down with it.
- There's no way to replay a captured burst to debug a stats bug — the
  data's gone the moment the request finishes.

Splitting capture (**producer**) from classification (**consumer**) over a
Redis stream (`packets:raw`) fixes this: `capture_to_stream()` in
`analyzer.py` publishes each packet as an event and returns immediately;
`consume_activity()` reads from a consumer group (`dashboard-group`),
tallies the protocol breakdown, and acknowledges each event once handled.

### What's actually verified, not just claimed

- **`test_stream_failure.py`** — publishes 12 events, runs a real separate
  consumer process, and sends it a genuine `SIGKILL` after it acks 5 of
  them. Confirms the production consumer recovers **exactly the 7**
  entries the killed process left stuck in Redis's pending list (zero data
  loss), and that running it again afterward picks up nothing further
  (zero duplicate processing). Recovery works by claiming
  delivered-but-unacked entries via `XAUTOCLAIM` and tallying them keyed by
  entry ID, so a redelivered entry can never be counted twice.

  ```bash
  cd backend && python test_stream_failure.py
  ```

- **`throughput_test.py`** — runs the same 300-event workload through 1
  consumer, then through 3 concurrent consumer processes pulling from the
  same group, and measures wall-clock throughput for each.

  ```bash
  cd backend && python throughput_test.py
  ```

  Measured result: **58.9 events/sec at 1 consumer, 109.3 events/sec at
  3 consumers — a 1.86x speedup, not 3x.** That's the honest number, and
  it's explainable rather than being a modeling error: each worker still
  pays a fixed ~600ms idle-polling cost to confirm the stream is drained
  before exiting, and every `XACK` is its own network round trip. Adding
  more workers doesn't shrink that per-worker tail cost, so scaling here is
  real but sub-linear — the same reason parallel fan-out in general is
  bounded by its slowest/highest-overhead part, not by consumer count
  alone.

## Kafka port

`analyzer_kafka.py` is the same producer/consumer pipeline re-implemented
against Kafka instead of Redis Streams, kept as a separate module so the
validated Redis path isn't disturbed. The concepts map directly — a Kafka
topic instead of a stream, its built-in consumer groups instead of
`XGROUP`, manual offset commits instead of `XACK`.

```bash
brew install kafka
kafka-storage format -t "$(kafka-storage random-uuid)" \
  -c /opt/homebrew/etc/kafka/server.properties --standalone
kafka-server-start /opt/homebrew/etc/kafka/server.properties &

cd backend && python test_kafka_failure.py
```

**One real, non-obvious difference the port surfaced:** Redis Streams lets
any consumer reclaim a stale pending entry the instant it decides to
(`XAUTOCLAIM` with `min_idle_time`) — there's no coordination step. Kafka
won't reassign a dead consumer's partitions until the group coordinator
stops receiving its heartbeats for `session.timeout.ms`; a `SIGKILL` sends
no `LeaveGroup` notice, so that wait is unavoidable. `test_kafka_failure.py`
has to sleep out that window before recovery — Redis's failure detection
is pull-based and immediate, Kafka's is push-based and has a real MTTR
floor. Same guarantee (zero loss, zero duplication), different recovery
latency, for a structural reason rather than a tuning difference.

## API

| Endpoint | Description |
|---|---|
| `GET /discovery?ip=<subnet>` | ARP-scans `subnet`, returns device list with vendor + latency |
| `GET /activity` | Publishes a fresh capture burst to the stream and returns the consumed protocol breakdown |
| `GET /report?ip=<subnet>` | Combines both, adds PASS/WARN/FAIL verdicts per device |
