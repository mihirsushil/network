// api.js — Axios client for the Flask backend
//
// All network calls go through this module so the base URL and timeout
// live in one place — the same pattern used in automated test harnesses
// where the target host address changes between lab environments.

import axios from 'axios';

// Force IPv4 explicitly — 'localhost' can resolve to the IPv6 loopback (::1)
// first, which Flask's dev server isn't listening on by default. That mismatch
// surfaces in Chrome as a misleading CORS error instead of a connection failure.
const BASE_URL = 'http://127.0.0.1:5000';

const api = axios.create({
    baseURL: BASE_URL,
    timeout: 15000,  // ARP scans and packet captures can take several seconds
    headers: { 'Content-Type': 'application/json' },
});

// Log every outgoing request — useful for debugging timing between the
// frontend trigger and the backend scan start (same as timestamping when
// a test script sends an NVMe command vs. when the drive responds).
api.interceptors.request.use(config => {
    console.log(`[api] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
});

// ── Public helpers ────────────────────────────────────────────────────────────

/** Fetches ARP-discovered devices for the given subnet. */
export async function fetchDevices(subnet = '192.168.40.0/24') {
    const { data } = await api.get('/discovery', { params: { ip: subnet } });
    return data;
}

/** Fetches a live packet-capture protocol breakdown. */
export async function fetchActivity() {
    const { data } = await api.get('/activity');
    return data;
}

/**
 * Fetches a combined test report (devices + traffic) suitable for export.
 * Mirrors the structured result files produced by automated SSD test scripts:
 * one JSON file per test run, with timestamp, verdicts, and raw metrics.
 */
export async function fetchReport(subnet = '192.168.40.0/24') {
    const { data } = await api.get('/report', { params: { ip: subnet } });
    return data;
}

export default api;
