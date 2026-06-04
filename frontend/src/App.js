import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis, YAxis
} from 'recharts';
import {
  fetchAlerts,
  fetchEvents,
  fetchFunnel,
  fetchHourly,
  fetchMetrics,
  fetchZones
} from './api';

// ─── Colour palette ───────────────────────────────────────────────────────────
const C = {
  purple : '#7C3AED',
  pink   : '#EC4899',
  teal   : '#0D9488',
  amber  : '#D97706',
  red    : '#DC2626',
  green  : '#16A34A',
  bg     : '#0F0F1A',
  card   : '#1A1A2E',
  border : '#2D2D4E',
  text   : '#E2E8F0',
  muted  : '#94A3B8',
};

// ─── Reusable components ──────────────────────────────────────────────────────

function MetricCard({ label, value, sub, color }) {
  return (
    <div style={{
      background: C.card, border: `0.5px solid ${C.border}`,
      borderRadius: 12, padding: '20px 22px',
      borderLeft: `3px solid ${color || C.purple}`,
    }}>
      <div style={{ fontSize: 12, color: C.muted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || C.text }}>
        {value ?? '—'}
      </div>
      {sub && <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <h2 style={{ fontSize: 15, fontWeight: 600, color: C.text, margin: '28px 0 12px', borderBottom: `0.5px solid ${C.border}`, paddingBottom: 8 }}>
      {children}
    </h2>
  );
}

function Badge({ text, type }) {
  const colors = {
    OVERCROWDING : { bg: '#3b1a1a', text: '#f87171' },
    EMPTY_ENTRANCE: { bg: '#1a2a1a', text: '#4ade80' },
    LONG_QUEUE   : { bg: '#2a2a1a', text: '#facc15' },
  };
  const c = colors[text] || { bg: '#1e1e3a', text: '#a78bfa' };
  return (
    <span style={{ background: c.bg, color: c.text, fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
      {text}
    </span>
  );
}

// ─── Funnel component ─────────────────────────────────────────────────────────
function Funnel({ data }) {
  if (!data) return null;
  const stages = [
    { key: 'stage1_entered_store',       emoji: '🚪', color: C.purple },
    { key: 'stage2_browsed_zone',        emoji: '🛍️', color: C.teal   },
    { key: 'stage3_reached_billing',     emoji: '💳', color: C.amber  },
    { key: 'stage4_completed_purchase',  emoji: '✅', color: C.green  },
  ];
  const max = Math.max(...stages.map(s => data[s.key]?.count || 0), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {stages.map((s, i) => {
        const stage = data[s.key];
        if (!stage) return null;
        const pct = Math.round((stage.count / max) * 100);
        return (
          <div key={s.key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 13, color: C.text }}>{s.emoji} {stage.label}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: s.color }}>{stage.count}</span>
            </div>
            <div style={{ background: C.border, borderRadius: 4, height: 8 }}>
              <div style={{ width: `${pct}%`, height: 8, background: s.color, borderRadius: 4, transition: 'width 0.6s' }} />
            </div>
          </div>
        );
      })}
      {data.overall_conversion && (
        <div style={{ marginTop: 8, fontSize: 13, color: C.muted }}>
          Overall conversion: <strong style={{ color: C.green }}>{data.overall_conversion}</strong>
        </div>
      )}
    </div>
  );
}

// ─── Zone heatmap ──────────────────────────────────────────────────────────────
function ZoneGrid({ zones }) {
  if (!zones?.length) return <div style={{ color: C.muted, fontSize: 13 }}>No zone data yet</div>;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
      {zones.map(z => (
        <div key={z.zone} style={{
          background: C.card, border: `0.5px solid ${C.border}`,
          borderRadius: 10, padding: '14px 16px'
        }}>
          <div style={{ fontSize: 11, color: C.muted, textTransform: 'uppercase', letterSpacing: 1 }}>{z.zone?.replace('_', ' ')}</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: C.purple, margin: '6px 0 2px' }}>{z.maxPeople}</div>
          <div style={{ fontSize: 11, color: C.muted }}>peak · avg {z.avgPeople}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [metrics, setMetrics] = useState(null);
  const [alerts,  setAlerts]  = useState(null);
  const [funnel,  setFunnel]  = useState(null);
  const [hourly,  setHourly]  = useState([]);
  const [zones,   setZones]   = useState([]);
  const [events,  setEvents]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadAll = async () => {
    try {
      const [m, a, f, h, z, e] = await Promise.all([
        fetchMetrics(), fetchAlerts(), fetchFunnel(),
        fetchHourly(), fetchZones(), fetchEvents(),
      ]);
      setMetrics(m.data);
      setAlerts(a.data);
      setFunnel(f.data);
      setHourly(h.data || []);
      setZones(z.data || []);
      // Show latest 50 events, most recent first
      const evts = Array.isArray(e.data) ? e.data : [];
      setEvents(evts.slice(-50).reverse());
      setLastRefresh(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      setError('Cannot reach backend. Make sure Spring Boot is running on port 8080.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    // Auto-refresh every 15 seconds
    const interval = setInterval(loadAll, 15000);
    return () => clearInterval(interval);
  }, []);

  // ── Styles ─────────────────────────────────────────────────────────────────
  const page = {
    minHeight: '100vh', background: C.bg,
    color: C.text, fontFamily: "'Inter', 'Segoe UI', sans-serif",
    padding: '0 0 60px',
  };
  const container = { maxWidth: 1200, margin: '0 auto', padding: '0 20px' };
  const grid2 = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 };
  const grid4 = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 };
  const cardBox = { background: C.card, border: `0.5px solid ${C.border}`, borderRadius: 12, padding: '20px 22px' };

  // ── Render ─────────────────────────────────────────────────────────────────
  if (loading) return (
    <div style={{ ...page, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>⚙️</div>
        <div style={{ color: C.muted }}>Loading store data…</div>
      </div>
    </div>
  );

  return (
    <div style={page}>
      {/* ── Header ── */}
      <div style={{ background: C.card, borderBottom: `0.5px solid ${C.border}`, padding: '16px 20px', marginBottom: 28 }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: C.text }}>
              🏪 Purplle Store Intelligence
            </h1>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>
              Brigade Road, Bangalore · April 10, 2026
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <button onClick={loadAll} style={{
              background: C.purple, color: '#fff', border: 'none', borderRadius: 8,
              padding: '8px 16px', fontSize: 13, cursor: 'pointer', marginBottom: 4
            }}>↻ Refresh</button>
            {lastRefresh && <div style={{ fontSize: 11, color: C.muted }}>Last updated: {lastRefresh}</div>}
          </div>
        </div>
      </div>

      <div style={container}>

        {/* ── Error banner ── */}
        {error && (
          <div style={{ background: '#3b1a1a', border: '0.5px solid #f87171', borderRadius: 10, padding: '12px 16px', marginBottom: 20, color: '#f87171', fontSize: 13 }}>
            ⚠ {error}
          </div>
        )}

        {/* ── Key metric cards ── */}
        <SectionTitle>Store Overview · April 10 2026</SectionTitle>
        <div style={grid4}>
          <MetricCard label="Total Footfall"     value={metrics?.totalFootfall}      color={C.purple} sub="people entered today" />
          <MetricCard label="Conversion Rate"    value={metrics?.conversionRatePct ? `${metrics.conversionRatePct}%` : '—'} color={C.green} sub={`${metrics?.uniqueBuyers} buyers / ${metrics?.totalFootfall} visitors`} />
          <MetricCard label="Peak Occupancy"     value={metrics?.peakPeopleCount}    color={C.amber}  sub="max people at once" />
          <MetricCard label="Total Alerts"       value={metrics?.totalAlerts}        color={C.red}    sub="anomalies detected" />
        </div>

        <div style={{ ...grid4, marginTop: 12 }}>
          <MetricCard label="Total Orders"       value={metrics?.totalOrders}        color={C.teal}   sub="from POS data" />
          <MetricCard label="Unique Buyers"      value={metrics?.uniqueBuyers}       color={C.teal}   sub="unique customers" />
          <MetricCard label="Total GMV"          value={metrics?.totalGMV ? `₹${metrics.totalGMV.toLocaleString()}` : '—'} color={C.pink} sub="gross merchandise value" />
          <MetricCard label="Avg Occupancy"      value={metrics?.avgPeopleCount}     color={C.purple} sub="avg people in store" />
        </div>

        {/* ── Hourly chart + Funnel ── */}
        <div style={{ ...grid2, marginTop: 4 }}>
          <div>
            <SectionTitle>Hourly People Count</SectionTitle>
            <div style={cardBox}>
              {hourly.length === 0
                ? <div style={{ color: C.muted, fontSize: 13 }}>No hourly data yet — run detector.py first</div>
                : (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={hourly}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                      <XAxis dataKey="hour" tick={{ fill: C.muted, fontSize: 11 }} />
                      <YAxis tick={{ fill: C.muted, fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: C.card, border: `0.5px solid ${C.border}`, color: C.text, fontSize: 12 }} />
                      <Bar dataKey="avgPeople" fill={C.purple} radius={[4, 4, 0, 0]} name="Avg People" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
            </div>
          </div>

          <div>
            <SectionTitle>Conversion Funnel</SectionTitle>
            <div style={cardBox}>
              <Funnel data={funnel} />
            </div>
          </div>
        </div>

        {/* ── Zone heatmap ── */}
        <SectionTitle>Zone Activity</SectionTitle>
        <ZoneGrid zones={zones} />

        {/* ── Alerts table ── */}
        <SectionTitle>
          Anomaly Alerts
          {alerts?.totalAlerts > 0 && (
            <span style={{ marginLeft: 10, fontSize: 12, color: C.red, fontWeight: 400 }}>
              {alerts.totalAlerts} total
            </span>
          )}
        </SectionTitle>
        <div style={cardBox}>
          {!alerts?.alerts?.length
            ? <div style={{ color: C.muted, fontSize: 13 }}>No alerts detected</div>
            : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr>
                      {['Camera', 'Zone', 'Time', 'People', 'Alert'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: C.muted, fontWeight: 500, borderBottom: `0.5px solid ${C.border}` }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {alerts.alerts.slice(0, 20).map((a, i) => (
                      <tr key={i} style={{ borderBottom: `0.5px solid ${C.border}` }}>
                        <td style={{ padding: '8px 12px', color: C.text }}>{a.cameraId}</td>
                        <td style={{ padding: '8px 12px', color: C.muted }}>{a.zone}</td>
                        <td style={{ padding: '8px 12px', color: C.muted, fontFamily: 'monospace', fontSize: 11 }}>
                          {a.timestamp?.substring(11, 19)}
                        </td>
                        <td style={{ padding: '8px 12px', color: C.amber, fontWeight: 600 }}>{a.peopleCount}</td>
                        <td style={{ padding: '8px 12px' }}><Badge text={a.alert} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </div>

        {/* ── Recent events table ── */}
        <SectionTitle>Recent Events (latest 50)</SectionTitle>
        <div style={cardBox}>
          {events.length === 0
            ? <div style={{ color: C.muted, fontSize: 13 }}>No events yet — run detector.py first</div>
            : (
              <div style={{ overflowX: 'auto', maxHeight: 340, overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead style={{ position: 'sticky', top: 0, background: C.card }}>
                    <tr>
                      {['#', 'Camera', 'Zone', 'Time', 'People', 'Alert'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: '8px 10px', color: C.muted, fontWeight: 500, borderBottom: `0.5px solid ${C.border}` }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((e, i) => (
                      <tr key={i} style={{ borderBottom: `0.5px solid ${C.border}` }}>
                        <td style={{ padding: '6px 10px', color: C.muted }}>{i + 1}</td>
                        <td style={{ padding: '6px 10px', color: C.text }}>{e.cameraId}</td>
                        <td style={{ padding: '6px 10px', color: C.muted }}>{e.zone}</td>
                        <td style={{ padding: '6px 10px', color: C.muted, fontFamily: 'monospace' }}>
                          {e.timestamp?.substring(11, 19)}
                        </td>
                        <td style={{ padding: '6px 10px', fontWeight: 600, color: e.peopleCount > 8 ? C.red : C.text }}>
                          {e.peopleCount}
                        </td>
                        <td style={{ padding: '6px 10px' }}>
                          {e.alert ? <Badge text={e.alert} /> : <span style={{ color: C.border }}>—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </div>

        {/* ── Footer ── */}
        <div style={{ marginTop: 40, textAlign: 'center', fontSize: 11, color: C.border }}>
          Purplle Tech Challenge 2026 · Store Intelligence System · Brigade Road Bangalore
        </div>

      </div>
    </div>
  );
}