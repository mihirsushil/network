"""
discovery.py — ARP-based network device scanner

Sends ARP probes across a subnet, collects every device that responds,
resolves MAC-to-vendor, and measures ICMP round-trip latency.

KIOXIA relevance: before running SSD qualification tests on a server rack
you need to enumerate every device on the network and verify it is reachable
and responding within an acceptable latency window.  This script automates
that enumeration step the same way a qualification test harness would.
"""

import re
import subprocess
import platform

from scapy.all import arping
from scapy.layers.l2 import getmacbyip
from mac_vendor_lookup import MacLookup

# Validates dotted-decimal IPv4 with optional CIDR suffix (e.g. 192.168.1.0/24)
IP_PATTERN = (
    r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    r'(/(3[0-2]|[12]?[0-9]))?$'
)

# Single MacLookup instance — avoids reloading the vendor database on every call
_mac_lookup = MacLookup()


def ping_latency_ms(ip: str) -> float | None:
    """
    Returns ICMP round-trip time in milliseconds for a single ping to `ip`.

    Analogous to measuring SSD read latency: one I/O request is sent and
    the time until the response arrives is the latency sample.
    Returns None if the host does not respond within 1 second.
    """
    # -n on Windows, -c on macOS/Linux (count flag name differs)
    count_flag = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        result = subprocess.run(
            ["ping", count_flag, "1", "-W", "1", ip],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            # macOS: "round-trip min/avg/max/stddev = 0.5/0.5/0.5/0.0 ms"
            # Linux:  "rtt min/avg/max/mdev = 0.5/0.5/0.5/0.0 ms"
            if "avg" in line and "=" in line:
                avg_field = line.split("=")[1].strip().split("/")[1]
                return round(float(avg_field), 2)
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        pass
    return None


def get_devices(ip_address: str) -> list[dict]:
    """
    Scans `ip_address` (a subnet like 192.168.1.0/24) with ARP and returns
    a list of device records: {ip, mac, vendor, latency_ms}.

    Falls back to mock data when no real devices respond so the dashboard
    remains functional during development without root/sudo access.
    """
    if not re.match(IP_PATTERN, ip_address):
        print(f"[discovery] Invalid address: {ip_address}")
        return []

    print(f"[discovery] Scanning {ip_address} ...")
    devices = []

    try:
        # arping() returns (answered, unanswered); we only care about answered
        ans, _ = arping(ip_address, verbose=False)

        for _, received in ans:
            ip = received.psrc                          # IP extracted from ARP reply
            mac = getmacbyip(ip) or "Unavailable"       # MAC resolved from ARP cache

            try:
                vendor = _mac_lookup.lookup(mac)
            except Exception:
                vendor = "Unknown"

            # RTT to each device — key metric for qualifying devices on a test rack
            latency = ping_latency_ms(ip)

            devices.append({
                "ip":         ip,
                "mac":        mac,
                "vendor":     vendor,
                "latency_ms": latency,
            })
    except Exception as e:
        # Raw sockets need root on macOS/Linux — fall through to mock data
        # instead of taking down the whole endpoint when running unprivileged.
        print(f"[discovery] ARP scan failed ({e}) — falling back to mock data")

    if not devices:
        # No real ARP responses — use mock data so the UI still renders
        print("[discovery] No devices found — returning mock data")
        devices = [
            {"ip": "192.168.40.10", "mac": "AA:BB:CC:DD:EE:FF", "vendor": "MockPhone",  "latency_ms": 2.1},
            {"ip": "192.168.40.15", "mac": "11:22:33:44:55:66", "vendor": "MockLaptop", "latency_ms": 0.8},
            {"ip": "192.168.40.20", "mac": "DE:AD:BE:EF:00:01", "vendor": "MockServer", "latency_ms": 15.3},
        ]

    return devices
