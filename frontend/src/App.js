// App.js — root component and application state manager
//
// Orchestrates data fetching from the Flask backend and passes results
// down to child components.  The flow mirrors a test harness:
//   1. Trigger a scan (ARP discovery + packet capture run in parallel)
//   2. Receive structured results
//   3. Evaluate thresholds → set alert state
//   4. Display results and offer a JSON report export
//
// This pattern — automated collection, threshold evaluation, structured
// export — is the same one used in SSD qualification test scripts.

import React, { useState, useEffect } from 'react';
import './App.css';

import { fetchDevices, fetchActivity, fetchReport } from './services/api';
import DeviceTable   from './components/DeviceTable';
import ActivityChart from './components/ActivityChart';
import AlertBanner   from './components/AlertBanner';

export default function App() {
    const [subnet,   setSubnet]   = useState('192.168.40.0/24');
    const [devices,  setDevices]  = useState([]);
    const [activity, setActivity] = useState(null);
    const [alert,    setAlert]    = useState(null);   // {message, type} or null
    const [error,    setError]    = useState(null);
    const [loading,  setLoading]  = useState(false);
    const [lastScan, setLastScan] = useState(null);

    // Run discovery + packet-capture in parallel, then merge results into state
    async function runScan() {
        setLoading(true);
        setError(null);

        try {
            // Fire both requests at the same time — mirrors parallel test execution
            const [deviceData, activityData] = await Promise.all([
                fetchDevices(subnet),
                fetchActivity(),
            ]);

            setDevices(deviceData);
            setActivity(activityData);

            // Surface the backend alert flag as a banner
            setAlert(
                activityData.alert
                    ? { message: activityData.alert_message, type: 'warn' }
                    : null
            );

            setLastScan(new Date().toLocaleTimeString());
        } catch {
            setError('Could not reach the backend. Make sure Flask is running: cd backend && python app.py');
        } finally {
            setLoading(false);
        }
    }

    // Initial scan on mount — same as a test harness running its setup phase
    useEffect(() => {
        runScan();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Build and trigger a browser download of the JSON test report
    async function downloadReport() {
        try {
            const report = await fetchReport(subnet);
            const blob   = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
            const url    = URL.createObjectURL(blob);
            const a      = Object.assign(document.createElement('a'), {
                href:     url,
                download: `network_report_${subnet.replace(/\//g, '_')}.json`,
            });
            a.click();
            URL.revokeObjectURL(url);
        } catch {
            setError('Could not generate report. Is the backend running?');
        }
    }

    // Derive the "best latency" stat from the current device list
    const latencies   = devices.map(d => d.latency_ms).filter(l => l != null);
    const bestLatency = latencies.length > 0 ? `${Math.min(...latencies)} ms` : '—';

    // Overall network status badge
    const netStatus = activity?.alert ? 'warn' : 'pass';

    return (
        <div className="app">
            <header className="app-header">
                <div className="header-left">
                    <h1>Network Monitor</h1>
                    <span className="subtitle">Device Discovery &amp; Traffic Analysis</span>
                </div>
                {lastScan && <span className="last-scan">Last scan: {lastScan}</span>}
            </header>

            <main className="app-main">
                {/* Error and alert banners */}
                {error && (
                    <AlertBanner message={error} type="error" onDismiss={() => setError(null)} />
                )}
                {alert && (
                    <AlertBanner message={alert.message} type={alert.type} onDismiss={() => setAlert(null)} />
                )}

                {/* Scan controls */}
                <div className="controls-bar">
                    <div className="subnet-input-group">
                        <label htmlFor="subnet">Subnet</label>
                        <input
                            id="subnet"
                            type="text"
                            className="subnet-input"
                            value={subnet}
                            onChange={e => setSubnet(e.target.value)}
                            placeholder="e.g. 192.168.1.0/24"
                        />
                    </div>
                    <button className="btn btn-primary" onClick={runScan} disabled={loading}>
                        {loading ? 'Scanning…' : 'Scan Network'}
                    </button>
                    <button className="btn btn-secondary" onClick={downloadReport} disabled={loading}>
                        Export Report
                    </button>
                </div>

                {/* Summary stat cards — equivalent to the header summary row in a test report */}
                <div className="stats-row">
                    <div className="stat-card">
                        <span key={devices.length} className="stat-value">{devices.length}</span>
                        <span className="stat-label">Devices Found</span>
                    </div>
                    <div className="stat-card">
                        <span key={activity?.total_packets ?? 'none'} className="stat-value">
                            {activity?.total_packets ?? '—'}
                        </span>
                        <span className="stat-label">Packets Captured</span>
                    </div>
                    <div className="stat-card">
                        <span key={netStatus} className={`stat-value status-${netStatus}`}>
                            {activity ? (activity.alert ? 'WARN' : 'PASS') : '—'}
                        </span>
                        <span className="stat-label">Network Status</span>
                    </div>
                    <div className="stat-card">
                        <span key={bestLatency} className="stat-value">{bestLatency}</span>
                        <span className="stat-label">Best Latency</span>
                    </div>
                </div>

                {/* Main panels */}
                <div className="panels">
                    <section className="panel">
                        <h2 className="panel-title">Discovered Devices</h2>
                        <DeviceTable devices={devices} loading={loading} />
                    </section>

                    <section className="panel">
                        <h2 className="panel-title">Traffic Analysis</h2>
                        {activity
                            ? <ActivityChart activity={activity} />
                            : <p style={{ color: '#8b949e' }}>
                                {loading ? 'Capturing packets…' : 'Run a scan to see traffic data.'}
                              </p>
                        }
                    </section>
                </div>
            </main>
        </div>
    );
}
