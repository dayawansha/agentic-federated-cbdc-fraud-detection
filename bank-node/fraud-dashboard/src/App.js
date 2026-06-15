import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const COLORS = {
  critical: '#b91c1c',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#16a34a',
  neutral: '#2563eb',
  neutralSoft: '#93c5fd',
  bg: '#f8fafc',
  card: '#ffffff',
  text: '#111827',
  subtext: '#4b5563',
  border: '#d1d5db',
};

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'];

function formatTimestamp(value) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function formatRelativeTime(value) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'N/A';
  const deltaMs = Date.now() - date.getTime();
  const deltaMinutes = Math.round(deltaMs / 60000);
  if (deltaMinutes < 1) return 'just now';
  if (deltaMinutes < 60) return `${deltaMinutes}m ago`;
  const deltaHours = Math.round(deltaMinutes / 60);
  if (deltaHours < 24) return `${deltaHours}h ago`;
  return `${Math.round(deltaHours / 24)}d ago`;
}

function severityColor(severity) {
  return COLORS[String(severity || '').toLowerCase()] || COLORS.neutral;
}

function StatusPill({ label, healthy }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        borderRadius: 999,
        padding: '4px 10px',
        fontSize: 12,
        fontWeight: 700,
        color: healthy ? '#166534' : '#991b1b',
        background: healthy ? '#dcfce7' : '#fee2e2',
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: healthy ? '#16a34a' : '#dc2626',
        }}
      />
      {label}
    </span>
  );
}

function StatCard({ title, value, subtitle }) {
  return (
    <div
      style={{
        background: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 12,
        padding: 18,
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)',
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.subtext }}>{title}</div>
      <div style={{ marginTop: 10, fontSize: 28, fontWeight: 800, color: COLORS.text }}>{value}</div>
      <div style={{ marginTop: 6, fontSize: 13, color: COLORS.subtext }}>{subtitle}</div>
    </div>
  );
}

function SectionCard({ title, subtitle, children, action }) {
  return (
    <section
      style={{
        background: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 14,
        padding: 18,
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div>
          <h3 style={{ margin: 0, color: COLORS.text }}>{title}</h3>
          {subtitle ? <p style={{ margin: '6px 0 0', color: COLORS.subtext }}>{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function EmptyState({ text }) {
  return (
    <div
      style={{
        minHeight: 240,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: COLORS.subtext,
        border: `1px dashed ${COLORS.border}`,
        borderRadius: 12,
        background: '#f8fafc',
      }}
    >
      {text}
    </div>
  );
}

function App() {
  const proxyApiBase = useMemo(() => process.env.REACT_APP_API_BASE || '/api', []);
  const localAgentDirectUrl = useMemo(() => process.env.REACT_APP_LOCAL_AGENT_URL || 'http://localhost:9001', []);
  const localGnnDirectUrl = useMemo(() => process.env.REACT_APP_LOCAL_GNN_URL || 'http://localhost:9002', []);
  const privacyLayerDirectUrl = useMemo(() => process.env.REACT_APP_PRIVACY_LAYER_URL || 'http://localhost:9003', []);
  const transactionGraphDirectUrl = useMemo(
    () => process.env.REACT_APP_TRANSACTION_GRAPH_URL || 'http://localhost:9004',
    []
  );
  const alertingDirectUrl = useMemo(() => process.env.REACT_APP_ALERTING_URL || 'http://localhost:9005', []);
  const kafkaUiDirectUrl = useMemo(() => process.env.REACT_APP_KAFKA_UI_URL || 'http://localhost:18080', []);
  const wsDirectOrigin = useMemo(() => {
    const override = process.env.REACT_APP_ALERTING_WS_URL;
    return override || alertingDirectUrl.replace(/^http/, 'ws');
  }, [alertingDirectUrl]);

  const wsProxyOrigin = useMemo(() => window.location.origin.replace(/^http/, 'ws'), []);
  const [useProxy, setUseProxy] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${proxyApiBase}/local-agent/health`)
      .then((response) => {
        if (!cancelled) setUseProxy(Boolean(response.ok));
      })
      .catch(() => {
        if (!cancelled) setUseProxy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [proxyApiBase]);

  const kafkaUiUrl = useMemo(() => (useProxy === false ? kafkaUiDirectUrl : '/kafka-ui/'), [kafkaUiDirectUrl, useProxy]);
  const wsOrigin = useMemo(() => (useProxy === false ? wsDirectOrigin : wsProxyOrigin), [useProxy, wsDirectOrigin, wsProxyOrigin]);

  const serviceDefinitions = useMemo(
    () => [
      {
        name: 'local-agent',
        label: 'Local Agent',
        url: useProxy === false ? localAgentDirectUrl : `${proxyApiBase}/local-agent`,
      },
      { name: 'local-gnn', label: 'Local GNN', url: useProxy === false ? localGnnDirectUrl : `${proxyApiBase}/local-gnn` },
      {
        name: 'privacy-layer',
        label: 'Privacy Layer',
        url: useProxy === false ? privacyLayerDirectUrl : `${proxyApiBase}/privacy-layer`,
      },
      {
        name: 'transaction-graph',
        label: 'Transaction Graph',
        url: useProxy === false ? transactionGraphDirectUrl : `${proxyApiBase}/transaction-graph`,
      },
      { name: 'alerting', label: 'Alerting', url: useProxy === false ? alertingDirectUrl : `${proxyApiBase}/alerting` },
    ],
    [
      alertingDirectUrl,
      localAgentDirectUrl,
      localGnnDirectUrl,
      privacyLayerDirectUrl,
      proxyApiBase,
      transactionGraphDirectUrl,
      useProxy,
    ]
  );

  const [agentStatus, setAgentStatus] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [accountsSnapshot, setAccountsSnapshot] = useState({ count: null, accounts: [] });
  const [serviceHealth, setServiceHealth] = useState({});
  const [fetchState, setFetchState] = useState({
    alertsLoaded: false,
    statusLoaded: false,
    graphLoaded: false,
    websocketConnected: false,
  });

  useEffect(() => {
    let cancelled = false;

    async function fetchDashboardData() {
      const serviceChecks = serviceDefinitions.map(async (service) => {
        try {
          const response = await fetch(`${service.url}/health`);
          const payload = response.ok ? await response.json() : null;
          return [service.name, Boolean(response.ok && payload?.status === 'healthy')];
        } catch (error) {
          return [service.name, false];
        }
      });

      try {
        const statusResponse = await fetch(
          useProxy === false ? `${localAgentDirectUrl}/agent/status` : `${proxyApiBase}/local-agent/agent/status`
        );
        if (statusResponse.ok) {
          const payload = await statusResponse.json();
          if (!cancelled) {
            setAgentStatus(payload);
            setFetchState((prev) => ({ ...prev, statusLoaded: true }));
          }
        }
      } catch (error) {
        if (!cancelled) {
          setFetchState((prev) => ({ ...prev, statusLoaded: true }));
        }
      }

      try {
        const alertsResponse = await fetch(
          useProxy === false ? `${alertingDirectUrl}/alerts/recent?limit=50` : `${proxyApiBase}/alerting/alerts/recent?limit=50`
        );
        if (alertsResponse.ok) {
          const payload = await alertsResponse.json();
          if (!cancelled) {
            setAlerts(Array.isArray(payload) ? payload : []);
            setFetchState((prev) => ({ ...prev, alertsLoaded: true }));
          }
        }
      } catch (error) {
        if (!cancelled) {
          setFetchState((prev) => ({ ...prev, alertsLoaded: true }));
        }
      }

      try {
        const accountsResponse = await fetch(
          useProxy === false
            ? `${transactionGraphDirectUrl}/accounts?limit=200`
            : `${proxyApiBase}/transaction-graph/accounts?limit=200`
        );
        if (accountsResponse.ok) {
          const payload = await accountsResponse.json();
          if (!cancelled) {
            setAccountsSnapshot({
              count: payload?.count ?? null,
              accounts: Array.isArray(payload?.accounts) ? payload.accounts : [],
            });
            setFetchState((prev) => ({ ...prev, graphLoaded: true }));
          }
        }
      } catch (error) {
        if (!cancelled) {
          setFetchState((prev) => ({ ...prev, graphLoaded: true }));
        }
      }

      const healthChecks = await Promise.all(serviceChecks);
      if (!cancelled) {
        setServiceHealth(Object.fromEntries(healthChecks));
      }
    }

    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [alertingDirectUrl, localAgentDirectUrl, proxyApiBase, serviceDefinitions, transactionGraphDirectUrl, useProxy]);

  useEffect(() => {
    let ws;
    try {
      ws = new WebSocket(`${wsOrigin}/ws/alerts`);
      ws.onopen = () => {
        setFetchState((prev) => ({ ...prev, websocketConnected: true }));
      };
      ws.onclose = () => {
        setFetchState((prev) => ({ ...prev, websocketConnected: false }));
      };
      ws.onerror = () => {
        setFetchState((prev) => ({ ...prev, websocketConnected: false }));
      };
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setAlerts((prev) => {
            const next = [payload, ...prev];
            const seen = new Set();
            return next.filter((item) => {
              const key = item.alert_id || `${item.txId || item.tx_id}-${item.timestamp || item.received_at}`;
              if (seen.has(key)) return false;
              seen.add(key);
              return true;
            }).slice(0, 50);
          });
        } catch (error) {
          // Ignore malformed WS payloads and keep dashboard live.
        }
      };
    } catch (error) {
      setFetchState((prev) => ({ ...prev, websocketConnected: false }));
    }

    return () => {
      if (ws) ws.close();
    };
  }, [wsOrigin]);

  const analytics = useMemo(() => {
    const severityCounts = SEVERITY_ORDER.map((severity) => ({
      name: severity.charAt(0).toUpperCase() + severity.slice(1),
      value: alerts.filter((alert) => String(alert.severity || '').toLowerCase() === severity).length,
      color: severityColor(severity),
    })).filter((item) => item.value > 0);

    const alertsByTransaction = Object.entries(
      alerts.reduce((acc, alert) => {
        const key = String(alert.txId ?? alert.tx_id ?? 'unknown');
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {})
    )
      .map(([txId, count]) => ({ txId, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);

    const alertTimeline = alerts
      .slice()
      .reverse()
      .map((alert, index) => ({
        index: index + 1,
        alerts: index + 1,
        severityScore: ['low', 'medium', 'high', 'critical'].indexOf(String(alert.severity || '').toLowerCase()) + 1 || 0,
      }));

    const avgConfidence =
      alerts.length > 0
        ? alerts.reduce((sum, alert) => sum + Number(alert.confidence_score || 0), 0) / alerts.length
        : null;

    const criticalOrHigh = alerts.filter((alert) => ['critical', 'high'].includes(String(alert.severity || '').toLowerCase())).length;

    const topActiveAccounts = accountsSnapshot.accounts
      .slice()
      .sort((a, b) => (b.sent_count || 0) + (b.received_count || 0) - ((a.sent_count || 0) + (a.received_count || 0)))
      .slice(0, 5)
      .map((account) => ({
        account: account.account_id,
        sent: account.sent_count || 0,
        received: account.received_count || 0,
      }));

    return {
      severityCounts,
      alertsByTransaction,
      alertTimeline,
      avgConfidence,
      criticalOrHigh,
      topActiveAccounts,
    };
  }, [accountsSnapshot.accounts, alerts]);

  const modelAccuracy = agentStatus?.last_metrics?.accuracy;
  const modelLoss = agentStatus?.last_metrics?.loss;
  const totalTransactions = accountsSnapshot.count;
  const allCoreServicesHealthy = serviceDefinitions.every((service) => serviceHealth[service.name]);

  return (
    <div
      style={{
        minHeight: '100vh',
        background: COLORS.bg,
        color: COLORS.text,
        fontFamily: 'Inter, Arial, sans-serif',
      }}
    >
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: 24 }}>
        <header style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <h1 style={{ margin: 0, fontSize: 32 }}>CBDC Fraud Detection Dashboard</h1>
              <p style={{ margin: '8px 0 0', color: COLORS.subtext, maxWidth: 900 }}>
                Real-time operational view of local training, live fraud alerts, transaction graph activity, and supporting service health.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <StatusPill label={allCoreServicesHealthy ? 'Core Services Healthy' : 'Service Attention Needed'} healthy={allCoreServicesHealthy} />
              <StatusPill label={fetchState.websocketConnected ? 'Alert Stream Connected' : 'Alert Stream Disconnected'} healthy={fetchState.websocketConnected} />
            </div>
          </div>
        </header>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 16,
            marginBottom: 20,
          }}
        >
          <StatCard
            title="Fraud Alerts"
            value={alerts.length}
            subtitle={`${analytics.criticalOrHigh} high/critical alerts in memory`}
          />
          <StatCard
            title="Model Accuracy"
            value={typeof modelAccuracy === 'number' ? `${(modelAccuracy * 100).toFixed(2)}%` : 'N/A'}
            subtitle={typeof modelLoss === 'number' ? `Latest loss ${modelLoss.toFixed(4)}` : 'Awaiting latest training metrics'}
          />
          <StatCard
            title="Graph Accounts"
            value={typeof totalTransactions === 'number' ? totalTransactions : 'N/A'}
            subtitle="Current transaction-graph account snapshot"
          />
          <StatCard
            title="Avg Alert Confidence"
            value={typeof analytics.avgConfidence === 'number' ? `${(analytics.avgConfidence * 100).toFixed(1)}%` : 'N/A'}
            subtitle="Calculated from recent alert payloads"
          />
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.2fr 1fr',
            gap: 16,
            marginBottom: 16,
          }}
        >
          <SectionCard
            title="Operational Snapshot"
            subtitle="Live agent status, round metadata, and supporting service availability."
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
              <div>
                <div style={{ display: 'grid', gap: 10 }}>
                  <div><strong>Agent ID:</strong> {agentStatus?.agent_id || 'N/A'}</div>
                  <div><strong>Last Round:</strong> {agentStatus?.last_round_id || 'N/A'}</div>
                  <div><strong>Last Update:</strong> {formatTimestamp(agentStatus?.last_update_at)}</div>
                  <div><strong>Update Age:</strong> {formatRelativeTime(agentStatus?.last_update_at)}</div>
                  <div><strong>Data Feeds:</strong> {fetchState.statusLoaded && fetchState.alertsLoaded && fetchState.graphLoaded ? 'Loaded' : 'Refreshing...'}</div>
                </div>
              </div>
              <div>
                <div style={{ display: 'grid', gap: 10 }}>
                  {serviceDefinitions.map((service) => (
                    <div
                      key={service.name}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: 10,
                        padding: '10px 12px',
                        background: '#f9fafb',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700 }}>{service.label}</div>
                        <div style={{ fontSize: 12, color: COLORS.subtext }}>{service.url}</div>
                      </div>
                      <StatusPill label={serviceHealth[service.name] ? 'Healthy' : 'Unavailable'} healthy={Boolean(serviceHealth[service.name])} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title="Operator Shortcuts"
            subtitle="Direct access to supporting runtime tools."
            action={
              <a
                href={kafkaUiUrl}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'inline-block',
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: COLORS.neutral,
                  color: '#fff',
                  textDecoration: 'none',
                  fontWeight: 700,
                }}
              >
                Open Kafka UI
              </a>
            }
          >
            <div style={{ display: 'grid', gap: 12 }}>
              <div><strong>Kafka Cluster:</strong> federated-fraud-kafka</div>
              <div><strong>Broker:</strong> kafka:9092 (id: 1)</div>
              <div><strong>Topics:</strong> transactions.events, fraud.alerts, __consumer_offsets</div>
              <div><strong>Transaction Graph API:</strong> {serviceDefinitions.find((item) => item.name === 'transaction-graph')?.url}</div>
              <div><strong>Alerting API:</strong> {serviceDefinitions.find((item) => item.name === 'alerting')?.url}</div>
              <div><strong>Alerting WebSocket:</strong> {`${wsOrigin}/ws/alerts`}</div>
            </div>
          </SectionCard>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 16,
            marginBottom: 16,
          }}
        >
          <SectionCard title="Alerts by Severity" subtitle="Current in-memory distribution from the Alerting service.">
            {analytics.severityCounts.length === 0 ? (
              <EmptyState text="No recent alerts to visualize." />
            ) : (
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={analytics.severityCounts} dataKey="value" nameKey="name" innerRadius={55} outerRadius={88} paddingAngle={3}>
                      {analytics.severityCounts.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Most Alerted Transactions" subtitle="Top transaction IDs by recent alert count.">
            {analytics.alertsByTransaction.length === 0 ? (
              <EmptyState text="No alert-heavy transactions yet." />
            ) : (
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analytics.alertsByTransaction}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="txId" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill={COLORS.neutral} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Most Active Accounts" subtitle="Accounts with the highest combined sent/received activity.">
            {analytics.topActiveAccounts.length === 0 ? (
              <EmptyState text="Transaction graph activity is not available yet." />
            ) : (
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analytics.topActiveAccounts}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="account" hide />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="sent" stackId="activity" fill={COLORS.neutral} radius={[6, 6, 0, 0]} />
                    <Bar dataKey="received" stackId="activity" fill={COLORS.neutralSoft} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </SectionCard>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.2fr 1fr',
            gap: 16,
            marginBottom: 16,
          }}
        >
          <SectionCard title="Alert Timeline" subtitle="Sequential view of recent alert intensity across the current window.">
            {analytics.alertTimeline.length === 0 ? (
              <EmptyState text="No alert timeline available yet." />
            ) : (
              <div style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={analytics.alertTimeline}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="index" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="alerts" stroke={COLORS.neutral} strokeWidth={3} dot={false} name="Alert Volume" />
                    <Line type="monotone" dataKey="severityScore" stroke={COLORS.high} strokeWidth={2} dot={false} name="Severity Score" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Training Metrics" subtitle="Latest metrics reported by the Local Agent after a training round.">
            <div style={{ display: 'grid', gap: 12 }}>
              {agentStatus?.last_metrics && Object.keys(agentStatus.last_metrics).length > 0 ? (
                Object.entries(agentStatus.last_metrics).map(([key, value]) => (
                  <div
                    key={key}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: 10,
                      padding: '12px 14px',
                      background: '#f9fafb',
                    }}
                  >
                    <span style={{ fontWeight: 700, textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
                    <span style={{ fontFamily: 'monospace', color: COLORS.subtext }}>
                      {typeof value === 'number' ? value.toFixed(4) : String(value)}
                    </span>
                  </div>
                ))
              ) : (
                <EmptyState text="Training metrics have not been reported yet." />
              )}
            </div>
          </SectionCard>
        </div>

        <SectionCard title="Recent Alerts Feed" subtitle="Live alert stream from the Alerting service, enriched with timestamps and confidence.">
          {alerts.length === 0 ? (
            <EmptyState text="No recent alerts available." />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f3f4f6' }}>
                    {['Severity', 'Alert ID', 'Transaction', 'Confidence', 'Reason', 'Received', 'Status'].map((heading) => (
                      <th
                        key={heading}
                        style={{
                          textAlign: 'left',
                          padding: '10px 12px',
                          borderBottom: `1px solid ${COLORS.border}`,
                          color: COLORS.subtext,
                          fontSize: 13,
                        }}
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {alerts.slice(0, 12).map((alert, index) => (
                    <tr key={alert.alert_id || `${index}-${alert.txId || alert.tx_id || 'tx'}`}>
                      <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>
                        <span
                          style={{
                            display: 'inline-block',
                            borderRadius: 999,
                            padding: '4px 8px',
                            background: `${severityColor(alert.severity)}18`,
                            color: severityColor(alert.severity),
                            fontWeight: 700,
                            textTransform: 'capitalize',
                          }}
                        >
                          {alert.severity || 'unknown'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}`, fontFamily: 'monospace' }}>{alert.alert_id || 'N/A'}</td>
                      <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>{alert.txId || alert.tx_id || 'N/A'}</td>
                      <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>
                        {typeof alert.confidence_score === 'number' ? `${(alert.confidence_score * 100).toFixed(1)}%` : 'N/A'}
                      </td>
                      <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>{alert.reason || 'N/A'}</td>
                      <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>{formatTimestamp(alert.received_at || alert.timestamp)}</td>
                      <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>{alert.status || 'open'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

export default App;
