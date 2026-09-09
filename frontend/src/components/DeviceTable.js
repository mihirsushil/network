// DeviceTable.js — renders the ARP-discovered device list
//
// Each row shows the data a test engineer would log before running
// SSD validation on a rack: device address, hardware ID, manufacturer,
// and measured round-trip latency.  Rows are color-coded using the same
// PASS / WARN / FAIL thresholds defined in backend/utils.py so the UI
// and the exported JSON report always agree.

import React from 'react';

// Mirrors LATENCY_WARN_MS and LATENCY_CRITICAL_MS in utils.py
const WARN_MS     = 50;
const CRITICAL_MS = 200;

// Solid colors reference the same CSS variables the rest of the app uses,
// so a palette change in App.css doesn't need to be repeated here.
const STATUS_COLOR = {
    PASS:    'var(--pass)',
    WARN:    'var(--warn)',
    FAIL:    'var(--fail)',
    UNKNOWN: 'var(--text-muted)',
};

function latencyStatus(ms) {
    if (ms === null || ms === undefined) return 'UNKNOWN';
    if (ms > CRITICAL_MS) return 'FAIL';
    if (ms > WARN_MS)     return 'WARN';
    return 'PASS';
}

// Small badge that shows the PASS/WARN/FAIL verdict with matching color
function StatusBadge({ status }) {
    const color = STATUS_COLOR[status] || STATUS_COLOR.UNKNOWN;
    return (
        <span style={{
            color,
            background:   `color-mix(in srgb, ${color} 18%, transparent)`,
            border:       `1px solid ${color}`,
            borderRadius: '4px',
            padding:      '2px 8px',
            fontSize:     '11px',
            fontWeight:   600,
            letterSpacing:'0.5px',
        }}>
            {status}
        </span>
    );
}

const HEADERS = ['IP Address', 'MAC Address', 'Vendor', 'Latency (ms)', 'Status'];

// Rows past this index all share the same (capped) stagger delay, so a
// 40-device scan doesn't take 1.5s to finish animating in.
const MAX_STAGGER_INDEX = 8;
const STAGGER_STEP_MS   = 40;

export default function DeviceTable({ devices, loading }) {
    if (loading) {
        return (
            <div className="skeleton-table">
                {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="skeleton-row" style={{ animationDelay: `${i * 80}ms` }} />
                ))}
            </div>
        );
    }
    if (!devices || devices.length === 0) {
        return (
            <p className="empty-state">
                No devices found. Try a different subnet or check that the
                backend has permission to send ARP requests (may need sudo).
            </p>
        );
    }

    return (
        <div style={{ overflowX: 'auto' }}>
            <table className="device-table">
                <thead>
                    <tr>
                        {HEADERS.map(col => <th key={col}>{col}</th>)}
                    </tr>
                </thead>
                <tbody>
                    {devices.map((device, i) => {
                        const status = latencyStatus(device.latency_ms);
                        return (
                            <tr
                                key={device.ip || i}
                                className="device-row"
                                style={{ animationDelay: `${Math.min(i, MAX_STAGGER_INDEX) * STAGGER_STEP_MS}ms` }}
                            >
                                <td className="cell">{device.ip}</td>
                                <td className="cell cell-mono">{device.mac}</td>
                                <td className="cell">{device.vendor}</td>
                                <td className="cell">
                                    {device.latency_ms != null
                                        ? <span style={{ color: STATUS_COLOR[status] }}>{device.latency_ms} ms</span>
                                        : <span className="cell-muted">—</span>
                                    }
                                </td>
                                <td className="cell">
                                    <StatusBadge status={status} />
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
