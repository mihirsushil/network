// ActivityChart.js — bar chart of captured packet protocol distribution
//
// Visualizes TCP / UDP / ICMP / Other packet counts from the live capture.
// This is analogous to the workload breakdown chart in an SSD benchmark
// report: you capture a burst of I/O operations and show what fraction
// were reads, writes, and flushes.  The ICMP ratio overlay serves as the
// error-rate indicator — elevated ICMP in a server network can signal
// storage hardware faults or firmware issues worth investigating.

import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis,
    CartesianGrid, Tooltip,
    ResponsiveContainer, Cell,
} from 'recharts';

// One consistent color per protocol — used in both bars and the tooltip
const PROTOCOL_COLORS = {
    TCP:   '#58a6ff',
    UDP:   '#3fb950',
    ICMP:  '#d29922',
    Other: '#8b949e',
};

// Custom hover tooltip that shows the packet count in the right color
function CustomTooltip({ active, payload }) {
    if (!active || !payload?.length) return null;
    const { name, value } = payload[0];
    return (
        <div style={{
            background:   '#1c2230',
            border:       '1px solid #30363d',
            borderRadius: '6px',
            padding:      '8px 12px',
            fontSize:     '12px',
        }}>
            <span style={{ color: PROTOCOL_COLORS[name] || '#e6edf3', fontWeight: 600 }}>{name}</span>
            <span style={{ color: '#e6edf3', marginLeft: '8px' }}>{value} packets</span>
        </div>
    );
}

export default function ActivityChart({ activity }) {
    // Flatten the activity object into the [{name, value}] shape recharts expects
    const data = ['TCP', 'UDP', 'ICMP', 'Other'].map(proto => ({
        name:  proto,
        value: activity[proto] ?? 0,
    }));

    const icmpPct = activity.icmp_ratio != null
        ? `${(activity.icmp_ratio * 100).toFixed(1)}%`
        : '—';

    return (
        <div>
            {/* Summary metrics above the chart — mirrors the header row of a test report */}
            <div style={{ display: 'flex', gap: '24px', marginBottom: '20px', flexWrap: 'wrap' }}>
                <Metric label="Total packets" value={activity.total_packets} />
                <Metric
                    label="ICMP ratio"
                    value={icmpPct}
                    warn={activity.alert}
                    title="High ICMP can indicate network errors or hardware faults"
                />
                <Metric
                    label="Status"
                    value={activity.alert ? 'WARN' : 'PASS'}
                    warn={activity.alert}
                />
            </div>

            <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" vertical={false} />
                    <XAxis
                        dataKey="name"
                        tick={{ fill: '#8b949e', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                    />
                    <YAxis
                        tick={{ fill: '#8b949e', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                    />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: '#21262d' }} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {data.map(entry => (
                            <Cell key={entry.name} fill={PROTOCOL_COLORS[entry.name] || '#8b949e'} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

// Small stat block used above the chart
function Metric({ label, value, warn, title }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }} title={title}>
            <span style={{
                fontSize:   '20px',
                fontWeight: 600,
                color:      warn ? '#d29922' : '#e6edf3',
            }}>
                {value}
            </span>
            <span style={{
                fontSize:      '11px',
                color:         '#8b949e',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
            }}>
                {label}
            </span>
        </div>
    );
}
