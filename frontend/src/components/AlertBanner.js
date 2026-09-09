// AlertBanner.js — dismissible notification banner
//
// Surfaces both hard errors (backend unreachable) and soft warnings
// (elevated ICMP ratio).  The three-tier ERROR / WARN / INFO framing
// mirrors the verdict system used in hardware qualification reports:
// a single component handles all severity levels so callers don't need
// to build their own alert UI.

import React, { useEffect, useState } from 'react';

// Visual properties keyed by severity level — border color drives everything
// else (badge color, tinted background) so there's one source of truth per level.
const LEVEL = {
    error: { border: 'var(--fail)',   icon: '✕', label: 'ERROR' },
    warn:  { border: 'var(--warn)',   icon: '⚠', label: 'WARN'  },
    info:  { border: 'var(--accent)', icon: 'ℹ', label: 'INFO'  },
};

export default function AlertBanner({ message, type = 'info', onDismiss }) {
    const [mounted, setMounted] = useState(false);
    const [closing, setClosing] = useState(false);

    // Animate in on mount — rAF ensures the starting styles paint first
    // before we flip to the mounted state, so the transition actually runs.
    useEffect(() => {
        if (!message) return;
        setClosing(false);
        const id = requestAnimationFrame(() => setMounted(true));
        return () => cancelAnimationFrame(id);
    }, [message]);

    function handleDismiss() {
        setClosing(true);
        // Matches the 150ms exit transition in App.css — remove from the
        // DOM only after the animation finishes, not before.
        setTimeout(() => onDismiss?.(), 150);
    }

    if (!message) return null;

    const s = LEVEL[type] || LEVEL.info;

    return (
        <div
            className="alert-banner"
            data-mounted={mounted}
            data-closing={closing}
            style={{ borderColor: s.border, background: `color-mix(in srgb, ${s.border} 12%, transparent)` }}
        >
            <span className="alert-badge" style={{ color: s.border }}>{s.icon} {s.label}</span>
            <span className="alert-message">{message}</span>

            {onDismiss && (
                <button className="alert-dismiss" onClick={handleDismiss} aria-label="Dismiss">×</button>
            )}
        </div>
    );
}
