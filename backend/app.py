"""
app.py — Flask REST API for the network monitoring dashboard

Exposes three endpoints consumed by the React frontend:
  GET /discovery?ip=<subnet>  — ARP device list
  GET /activity               — packet-capture protocol breakdown
  GET /report?ip=<subnet>     — combined test report (devices + traffic)

KIOXIA relevance: the /report endpoint mirrors the structured result files
produced by automated SSD qualification scripts — a timestamped JSON record
that documents every device found, its measured latency, and a go/no-go verdict.
"""

from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

from discovery import get_devices
from analyzer   import get_activity
from utils      import classify_latency, LATENCY_WARN_MS

app = Flask(__name__)
CORS(app)   # allow the React dev server (port 3000) to call this API (port 5000)


@app.route("/")
def home():
    return jsonify({
        "message":   "Network Monitor API",
        "endpoints": ["/discovery", "/activity", "/report"],
    })


@app.route("/discovery")
def discovery():
    """Returns ARP-discovered devices for the requested subnet."""
    ip = request.args.get("ip", "192.168.40.0/24")
    return jsonify(get_devices(ip))


@app.route("/activity")
def activity():
    """Returns a live packet-capture protocol breakdown."""
    return jsonify(get_activity())


@app.route("/report")
def report():
    """
    Combines device discovery and packet-capture data into a single report.

    The structure intentionally matches the test-result records kept by
    qualification engineers: timestamp, device inventory, traffic metrics,
    per-device latency verdicts, and an overall PASS/WARN status.
    """
    ip = request.args.get("ip", "192.168.40.0/24")

    devices       = get_devices(ip)
    activity_data = get_activity()

    # Tag each device with a latency verdict using the shared threshold from utils.py
    for device in devices:
        device["latency_status"] = classify_latency(device.get("latency_ms"))

    # Overall status is WARN if any network alert is active
    overall = "WARN" if activity_data.get("alert") else "PASS"

    # Count devices by latency verdict — gives a quick health summary
    verdict_counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "UNKNOWN": 0}
    for d in devices:
        verdict_counts[d["latency_status"]] = verdict_counts.get(d["latency_status"], 0) + 1

    return jsonify({
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "subnet_scanned":  ip,
        "device_count":    len(devices),
        "devices":         devices,
        "traffic":         activity_data,
        "verdict_counts":  verdict_counts,
        "overall_status":  overall,
    })


if __name__ == "__main__":
    app.run(debug=True)
