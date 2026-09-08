/*
================================================================================
FRAUD DASHBOARD - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Fraud Dashboard as the "Control Center Screen" or "Cockpit" for the bank's
fraud analysis team. 

While the GNN models, database engines, and secure networks work invisibly in the
background, this React application translates all that complex mathematics and data
into clean, interactive charts and tables that a human officer can read in seconds.

THE DASHBOARD EXPOSES FIVE KEY WORKSPACES:
1. OVERVIEW SCREEN: Displays primary metrics — like overall system health, total alerts
   created, and the GNN detective's current accuracy percentage.
2. LIVE ALERTS WORKSPACE: Shows a real-time list of alerts streaming in via WebSockets.
   It categorizes them by color-coded severity (Critical, High, Medium, Low) and lets
   officers inspect the transaction details and mark them as reviewed.
3. INFERENCE WATCHLIST: Displays a list of accounts that the GNN model flagged as having
   high-probability suspicious transaction patterns.
4. PIPELINE STATE MONITOR: Lets the team monitor active federated learning rounds. They can
   see what training strategy is running, how much privacy budget is left, and the
   node's current CPU/Battery levels.
5. NETWORK UTILITIES: Exposes buttons to trigger demo runs, generate mock transactions,
   and test the alerting configurations.
================================================================================
*/
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
  bg: '#f4f6fb',
  card: '#ffffff',
  text: '#0f172a',
  subtext: '#64748b',
  border: '#e5e9f2',
  success: '#16a34a',
  successSoft: '#f0fdf4',
  warning: '#d97706',
  warningSoft: '#fffbeb',
  danger: '#dc2626',
  dangerSoft: '#fef2f2',
  info: '#2563eb',
  infoSoft: '#eff6ff',
  mono: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
};

const TONE_MAP = {
  success: { fg: COLORS.success, bg: COLORS.successSoft },
  warning: { fg: COLORS.warning, bg: COLORS.warningSoft },
  danger: { fg: COLORS.danger, bg: COLORS.dangerSoft },
  info: { fg: COLORS.info, bg: COLORS.infoSoft },
  neutral: { fg: COLORS.subtext, bg: '#f8fafc' },
};

const ICONS = {
  alerts: '⚠️',
  accuracy: '\u{1F3AF}',
  graph: '\u{1F578}️',
  confidence: '\u{1F4CA}',
  risk: '\u{1F6A8}',
  agent: '\u{1F916}',
  services: '\u{1F50C}',
  shortcuts: '\u{1F517}',
  kafka: '\u{1F4E1}',
  redis: '\u{1F5C3}️',
  pie: '\u{1F967}',
  bars: '\u{1F4C8}',
  sources: '\u{1F9ED}',
  accounts: '\u{1F3E6}',
  timeline: '⏱️',
  metrics: '\u{1F9EA}',
  watchlist: '\u{1F440}',
  registry: '\u{1F4DA}',
  trends: '\u{1F4C9}',
  feed: '\u{1F4EC}',
  endpoints: '\u{1F9ED}',
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
        padding: '5px 12px',
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: '0.01em',
        color: healthy ? '#15803d' : '#b91c1c',
        background: healthy ? COLORS.successSoft : COLORS.dangerSoft,
        border: `1px solid ${healthy ? '#bbf7d0' : '#fecaca'}`,
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: healthy ? COLORS.success : COLORS.danger,
          boxShadow: healthy ? '0 0 0 3px rgba(22,163,74,0.15)' : '0 0 0 3px rgba(220,38,38,0.15)',
        }}
      />
      {label}
    </span>
  );
}

function ActionButton({ href, label, background = COLORS.neutral }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      style={{
        display: 'inline-block',
        padding: '10px 16px',
        borderRadius: 9,
        background,
        color: '#fff',
        textDecoration: 'none',
        fontWeight: 700,
        fontSize: 13,
        boxShadow: `0 4px 10px ${background}40`,
        transition: 'transform 0.15s ease, box-shadow 0.15s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-1px)';
        e.currentTarget.style.boxShadow = `0 6px 14px ${background}55`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = `0 4px 10px ${background}40`;
      }}
    >
      {label}
    </a>
  );
}

function StatCard({ icon, title, value, subtitle, tone = 'neutral' }) {
  const toneColor = TONE_MAP[tone] || TONE_MAP.neutral;
  return (
    <div
      style={{
        position: 'relative',
        background: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 14,
        padding: '18px 18px 18px 20px',
        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
        overflow: 'hidden',
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: 4, background: toneColor.fg }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: COLORS.subtext, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {title}
        </div>
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 9,
            background: toneColor.bg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 15,
          }}
        >
          {icon}
        </div>
      </div>
      <div style={{ marginTop: 12, fontSize: 30, fontWeight: 800, color: COLORS.text, letterSpacing: '-0.02em' }}>{value}</div>
      <div style={{ marginTop: 6, fontSize: 12.5, color: COLORS.subtext, lineHeight: 1.4 }}>{subtitle}</div>
    </div>
  );
}

function SectionCard({ icon, title, subtitle, children, action }) {
  return (
    <section
      style={{
        background: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 16,
        padding: 20,
        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
        breakInside: 'avoid',
        WebkitColumnBreakInside: 'avoid',
        marginBottom: 16,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          {icon ? (
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                background: COLORS.infoSoft,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 16,
                flexShrink: 0,
              }}
            >
              {icon}
            </div>
          ) : null}
          <div>
            <h3 style={{ margin: 0, color: COLORS.text, fontSize: 16.5, fontWeight: 700, letterSpacing: '-0.01em' }}>{title}</h3>
            {subtitle ? <p style={{ margin: '5px 0 0', color: COLORS.subtext, fontSize: 13, lineHeight: 1.5 }}>{subtitle}</p> : null}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function AccessPanel({ icon, accent, eyebrow, title, description, href, actionLabel, status, statusCaption, children }) {
  return (
    <div
      style={{
        display: 'grid',
        gap: 16,
        padding: 18,
        border: `1px solid ${accent}30`,
        borderRadius: 16,
        background: `linear-gradient(160deg, ${accent}12 0%, ${COLORS.card} 42%)`,
        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
      }}
    >
      <div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: accent,
            }}
          >
            {eyebrow}
          </div>
          {status ? (
            <div style={{ display: 'grid', gap: 4, justifyItems: 'end' }}>
              {status}
              {statusCaption ? (
                <div style={{ fontSize: 11, color: COLORS.subtext, fontWeight: 600 }}>{statusCaption}</div>
              ) : null}
            </div>
          ) : null}
        </div>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
          {icon ? (
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: `${accent}1a`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 17,
                flexShrink: 0,
              }}
            >
              {icon}
            </div>
          ) : null}
          <div style={{ fontSize: 21, fontWeight: 800, color: COLORS.text, letterSpacing: '-0.01em' }}>{title}</div>
        </div>
        <p style={{ margin: '8px 0 0', color: COLORS.subtext, lineHeight: 1.5, fontSize: 13.5 }}>{description}</p>
      </div>
      {children}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          paddingTop: 14,
          borderTop: `1px solid ${COLORS.border}`,
        }}
      >
        <div style={{ fontSize: 12, color: COLORS.subtext }}>Opens in a separate tab for deeper inspection.</div>
        <ActionButton href={href} label={actionLabel} background={accent} />
      </div>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div
      style={{
        minHeight: 240,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        alignItems: 'center',
        justifyContent: 'center',
        color: COLORS.subtext,
        border: `1.5px dashed ${COLORS.border}`,
        borderRadius: 14,
        background: '#fafbfd',
        fontSize: 13.5,
      }}
    >
      <div style={{ fontSize: 22, opacity: 0.5 }}>&#128203;</div>
      {text}
    </div>
  );
}

function EndpointChip({ label, value, mono = true }) {
  return (
    <div
      style={{
        display: 'grid',
        gap: 3,
        padding: '10px 12px',
        borderRadius: 10,
        background: '#f8fafc',
        border: `1px solid ${COLORS.border}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: 10.5, fontWeight: 700, color: COLORS.subtext, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 12.5,
          fontWeight: 600,
          color: COLORS.text,
          fontFamily: mono ? COLORS.mono : 'inherit',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={value}
      >
        {value}
      </div>
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
  const modelRegistryDirectUrl = useMemo(
    () => process.env.REACT_APP_MODEL_REGISTRY_URL || 'http://localhost:8004',
    []
  );
  const policyManagerDirectUrl = useMemo(
    () => process.env.REACT_APP_POLICY_MANAGER_URL || 'http://localhost:8003',
    []
  );
  const kafkaUiDirectUrl = useMemo(() => process.env.REACT_APP_KAFKA_UI_URL || 'http://localhost:18080', []);
  const redisInsightDirectUrl = useMemo(
    () => process.env.REACT_APP_REDIS_INSIGHT_URL || 'http://localhost:5540',
    []
  );
  const wsDirectOrigin = useMemo(() => {
    const override = process.env.REACT_APP_ALERTING_WS_URL;
    return override || alertingDirectUrl.replace(/^http/, 'ws');
  }, [alertingDirectUrl]);

  const dashboardUiUrl = useMemo(() => window.location.origin, []);
  const wsProxyOrigin = useMemo(() => window.location.origin.replace(/^http/, 'ws'), []);
  const [useProxy, setUseProxy] = useState(null);
  const shouldUseProxy = useMemo(() => useProxy !== false, [useProxy]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${proxyApiBase}/local-agent/health`)
      .then((response) => {
        const contentType = response.headers.get('content-type') || '';
        const hasJsonHealthResponse = response.ok && contentType.includes('application/json');
        if (!cancelled) setUseProxy(hasJsonHealthResponse);
      })
      .catch(() => {
        if (!cancelled) setUseProxy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [proxyApiBase]);

  const kafkaUiUrl = useMemo(() => (shouldUseProxy ? '/kafka-ui/' : kafkaUiDirectUrl), [kafkaUiDirectUrl, shouldUseProxy]);
  const redisInsightUrl = useMemo(
    () => (shouldUseProxy ? '/redis-insight/' : redisInsightDirectUrl),
    [redisInsightDirectUrl, shouldUseProxy]
  );
  const wsOrigin = useMemo(() => (shouldUseProxy ? wsProxyOrigin : wsDirectOrigin), [shouldUseProxy, wsDirectOrigin, wsProxyOrigin]);

  const serviceDefinitions = useMemo(
    () => [
      {
        name: 'local-agent',
        label: 'Local Agent',
        url: shouldUseProxy ? `${proxyApiBase}/local-agent` : localAgentDirectUrl,
      },
      { name: 'local-gnn', label: 'Local GNN', url: shouldUseProxy ? `${proxyApiBase}/local-gnn` : localGnnDirectUrl },
      {
        name: 'privacy-layer',
        label: 'Privacy Layer',
        url: shouldUseProxy ? `${proxyApiBase}/privacy-layer` : privacyLayerDirectUrl,
      },
      {
        name: 'transaction-graph',
        label: 'Transaction Graph',
        url: shouldUseProxy ? `${proxyApiBase}/transaction-graph` : transactionGraphDirectUrl,
      },
      { name: 'alerting', label: 'Alerting', url: shouldUseProxy ? `${proxyApiBase}/alerting` : alertingDirectUrl },
      {
        name: 'model-registry',
        label: 'Model Registry',
        url: shouldUseProxy ? `${proxyApiBase}/model-registry` : modelRegistryDirectUrl,
      },
      {
        name: 'policy-manager',
        label: 'Policy Manager',
        url: shouldUseProxy ? `${proxyApiBase}/policy-manager` : policyManagerDirectUrl,
      },
    ],
    [
      alertingDirectUrl,
      localAgentDirectUrl,
      localGnnDirectUrl,
      modelRegistryDirectUrl,
      policyManagerDirectUrl,
      privacyLayerDirectUrl,
      proxyApiBase,
      transactionGraphDirectUrl,
      shouldUseProxy,
    ]
  );

  const [agentStatus, setAgentStatus] = useState(null);
  const [inferenceSnapshot, setInferenceSnapshot] = useState({ prediction_count: 0, predictions: [] });
  const [alerts, setAlerts] = useState([]);
  const [alertSummary, setAlertSummary] = useState({
    alert_count: 0,
    severity_counts: {},
    source_counts: {},
    detector_enabled: false,
    transaction_topic: 'transactions.events',
    alerts_topic: 'fraud.alerts',
    recent_detector_alerts: 0,
    persistence_mode: 'unknown',
    outbound_channels: [],
  });
  const [accountsSnapshot, setAccountsSnapshot] = useState({ count: null, accounts: [] });
  const [modelVersions, setModelVersions] = useState([]);
  const [governanceSnapshot, setGovernanceSnapshot] = useState({
    globalPolicies: null,
    privacyBudget: null,
    governanceAgent: null,
    auditEvents: [],
  });
  const [serviceHealth, setServiceHealth] = useState({});
  const [operatorShortcutHealth, setOperatorShortcutHealth] = useState({
    kafka: false,
    redis: false,
  });
  const [fetchState, setFetchState] = useState({
    alertsLoaded: false,
    inferenceLoaded: false,
    statusLoaded: false,
    graphLoaded: false,
    modelRegistryLoaded: false,
    governanceLoaded: false,
    websocketConnected: false,
  });

  useEffect(() => {
    if (useProxy === null) {
      return undefined;
    }

    let cancelled = false;

    async function fetchDashboardData() {
      const fetchJsonIfOk = async (url) => {
        const response = await fetch(url);
        if (!response.ok) return null;
        return response.json();
      };
      const checkShortcutAvailability = async (url) => {
        try {
          const response = await fetch(url, {
            method: 'GET',
            mode: shouldUseProxy ? 'same-origin' : 'no-cors',
          });
          return response.type === 'opaque' || response.ok;
        } catch (error) {
          return false;
        }
      };
      const serviceChecks = serviceDefinitions.map(async (service) => {
        try {
          const response = await fetch(`${service.url}/health`);
          const payload = response.ok ? await response.json() : null;
          return [service.name, Boolean(response.ok && payload?.status === 'healthy')];
        } catch (error) {
          return [service.name, false];
        }
      });
      let resolvedAgentId = null;

      try {
        const statusResponse = await fetch(
          shouldUseProxy ? `${proxyApiBase}/local-agent/agent/status` : `${localAgentDirectUrl}/agent/status`
        );
        if (statusResponse.ok) {
          const payload = await statusResponse.json();
          resolvedAgentId = payload?.agent_id || null;
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
        const inferenceResponse = await fetch(
          shouldUseProxy
            ? `${proxyApiBase}/local-agent/agent/inference?limit=5`
            : `${localAgentDirectUrl}/agent/inference?limit=5`
        );
        if (inferenceResponse.ok) {
          const payload = await inferenceResponse.json();
          if (!cancelled) {
            setInferenceSnapshot({
              prediction_count: payload?.prediction_count ?? 0,
              predictions: Array.isArray(payload?.predictions) ? payload.predictions : [],
              generated_at: payload?.generated_at || null,
            });
            setFetchState((prev) => ({ ...prev, inferenceLoaded: true }));
          }
        }
      } catch (error) {
        if (!cancelled) {
          setFetchState((prev) => ({ ...prev, inferenceLoaded: true }));
        }
      }

      try {
        const alertSummaryResponse = await fetch(
          shouldUseProxy ? `${proxyApiBase}/alerting/alerts/summary?limit=200` : `${alertingDirectUrl}/alerts/summary?limit=200`
        );
        if (alertSummaryResponse.ok) {
          const payload = await alertSummaryResponse.json();
          if (!cancelled) {
            setAlertSummary({
              alert_count: payload?.alert_count ?? 0,
              severity_counts: payload?.severity_counts || {},
              source_counts: payload?.source_counts || {},
              detector_enabled: Boolean(payload?.detector_enabled),
              transaction_topic: payload?.transaction_topic || 'transactions.events',
              alerts_topic: payload?.alerts_topic || 'fraud.alerts',
              recent_detector_alerts: payload?.recent_detector_alerts ?? 0,
              persistence_mode: payload?.persistence_mode || 'unknown',
              outbound_channels: Array.isArray(payload?.outbound_channels) ? payload.outbound_channels : [],
            });
          }
        }
      } catch (error) {
        // Keep prior summary when the endpoint is unavailable.
      }

      try {
        const alertsResponse = await fetch(
          shouldUseProxy ? `${proxyApiBase}/alerting/alerts/recent?limit=50` : `${alertingDirectUrl}/alerts/recent?limit=50`
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
          shouldUseProxy
            ? `${proxyApiBase}/transaction-graph/accounts?limit=200`
            : `${transactionGraphDirectUrl}/accounts?limit=200`
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

      try {
        const modelRegistryResponse = await fetch(
          shouldUseProxy
            ? `${proxyApiBase}/model-registry/models/versions`
            : `${modelRegistryDirectUrl}/models/versions`
        );
        if (modelRegistryResponse.ok) {
          const payload = await modelRegistryResponse.json();
          if (!cancelled) {
            setModelVersions(Array.isArray(payload) ? payload : []);
            setFetchState((prev) => ({ ...prev, modelRegistryLoaded: true }));
          }
        }
      } catch (error) {
        if (!cancelled) {
          setFetchState((prev) => ({ ...prev, modelRegistryLoaded: true }));
        }
      }

      try {
        const governanceBaseUrl = shouldUseProxy ? `${proxyApiBase}/policy-manager` : policyManagerDirectUrl;
        const encodedAgentId = resolvedAgentId ? encodeURIComponent(resolvedAgentId) : null;
        const [globalPoliciesPayload, privacyBudgetPayload, governanceAgentPayload, governanceAuditPayload] = await Promise.all([
          fetchJsonIfOk(`${governanceBaseUrl}/policies/global`),
          encodedAgentId ? fetchJsonIfOk(`${governanceBaseUrl}/policies/budget/${encodedAgentId}`) : Promise.resolve(null),
          encodedAgentId ? fetchJsonIfOk(`${governanceBaseUrl}/governance/agent/${encodedAgentId}`) : Promise.resolve(null),
          fetchJsonIfOk(`${governanceBaseUrl}/governance/audit?limit=6`),
        ]);
        if (!cancelled) {
          setGovernanceSnapshot({
            globalPolicies: globalPoliciesPayload,
            privacyBudget: privacyBudgetPayload,
            governanceAgent: governanceAgentPayload,
            auditEvents: Array.isArray(governanceAuditPayload) ? governanceAuditPayload : [],
          });
          setFetchState((prev) => ({ ...prev, governanceLoaded: true }));
        }
      } catch (error) {
        if (!cancelled) {
          setFetchState((prev) => ({ ...prev, governanceLoaded: true }));
        }
      }

      const healthChecks = await Promise.all(serviceChecks);
      const [kafkaShortcutHealthy, redisShortcutHealthy] = await Promise.all([
        checkShortcutAvailability(kafkaUiUrl),
        checkShortcutAvailability(redisInsightUrl),
      ]);
      if (!cancelled) {
        setServiceHealth(Object.fromEntries(healthChecks));
        setOperatorShortcutHealth({
          kafka: kafkaShortcutHealthy,
          redis: redisShortcutHealthy,
        });
      }
    }

    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [alertingDirectUrl, kafkaUiUrl, localAgentDirectUrl, modelRegistryDirectUrl, policyManagerDirectUrl, proxyApiBase, redisInsightUrl, serviceDefinitions, shouldUseProxy, transactionGraphDirectUrl, useProxy]);

  useEffect(() => {
    if (useProxy === null) {
      return undefined;
    }

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
  }, [useProxy, wsOrigin]);

  const analytics = useMemo(() => {
    const sourceCounts = Object.entries(alertSummary.source_counts || {})
      .map(([source, count]) => ({ source, count }))
      .sort((a, b) => b.count - a.count);

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

    const highRiskPredictions = (inferenceSnapshot.predictions || []).filter(
      (prediction) => String(prediction.predicted_class || '').toLowerCase() === 'illicit'
    );

    const topInferenceConfidence = highRiskPredictions.length > 0 ? highRiskPredictions[0].confidence : null;

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
      sourceCounts,
      alertsByTransaction,
      alertTimeline,
      avgConfidence,
      criticalOrHigh,
      highRiskPredictions,
      topActiveAccounts,
      topInferenceConfidence,
    };
  }, [accountsSnapshot.accounts, alertSummary.source_counts, alerts, inferenceSnapshot.predictions]);

  const activeModelVersionId = agentStatus?.last_model_version || modelVersions[0]?.version_id || null;
  const activeRegistryModel = modelVersions.find((version) => version.version_id === activeModelVersionId) || null;
  const latestRegistryModel = modelVersions[0] || null;
  const latestRegistryModelWithMetrics = modelVersions.find(
    (version) => version?.metrics && Object.keys(version.metrics).length > 0
  ) || null;
  const activeRegistryMetrics =
    activeRegistryModel?.metrics && Object.keys(activeRegistryModel.metrics).length > 0 ? activeRegistryModel.metrics : null;
  const latestRegistryMetrics =
    latestRegistryModel?.metrics && Object.keys(latestRegistryModel.metrics).length > 0 ? latestRegistryModel.metrics : null;
  const fallbackRegistryMetrics =
    latestRegistryModelWithMetrics?.metrics && Object.keys(latestRegistryModelWithMetrics.metrics).length > 0
      ? latestRegistryModelWithMetrics.metrics
      : null;
  const runtimeMetrics =
    agentStatus?.last_metrics && Object.keys(agentStatus.last_metrics).length > 0 ? agentStatus.last_metrics : null;
  const effectiveModelMetrics = runtimeMetrics || activeRegistryMetrics || latestRegistryMetrics || fallbackRegistryMetrics || null;
  const modelAccuracy = effectiveModelMetrics?.accuracy;
  const modelLoss = effectiveModelMetrics?.loss;
  const totalTransactions = accountsSnapshot.count;
  const allCoreServicesHealthy = serviceDefinitions.every((service) => serviceHealth[service.name]);
  const globalPolicies = governanceSnapshot.globalPolicies;
  const privacyBudget = governanceSnapshot.privacyBudget;
  const governanceAgent = governanceSnapshot.governanceAgent;
  const governanceAuditEvents = governanceSnapshot.auditEvents;
  const policyVersion = globalPolicies?.policy_version;
  const aggregationStrategy = globalPolicies?.aggregation_strategy;
  const privacyBudgetUsage =
    privacyBudget && typeof privacyBudget.total_spent_epsilon === 'number' && typeof privacyBudget.epsilon === 'number'
      ? `${privacyBudget.total_spent_epsilon.toFixed(2)} / ${privacyBudget.epsilon.toFixed(2)}`
      : 'N/A';
  const privacyDeltaUsage =
    privacyBudget && typeof privacyBudget.total_spent_delta === 'number' && typeof privacyBudget.delta === 'number'
      ? `${privacyBudget.total_spent_delta.toExponential(2)} / ${privacyBudget.delta.toExponential(2)}`
      : 'N/A';

  const alertsTone = analytics.criticalOrHigh > 0 ? 'danger' : alerts.length > 0 ? 'warning' : 'success';
  const accuracyTone =
    typeof modelAccuracy !== 'number' ? 'neutral' : modelAccuracy >= 0.85 ? 'success' : modelAccuracy >= 0.7 ? 'warning' : 'danger';
  const riskTone = analytics.highRiskPredictions.length > 0 ? 'danger' : 'success';

  return (
    <div
      style={{
        minHeight: '100vh',
        background: `radial-gradient(1200px 600px at 8% -10%, #eef2ff 0%, ${COLORS.bg} 45%)`,
        color: COLORS.text,
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
      }}
    >
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: '28px 24px 40px' }}>
        <header style={{ marginBottom: 28, paddingBottom: 20, borderBottom: `1px solid ${COLORS.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 13,
                  background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 22,
                  flexShrink: 0,
                  boxShadow: '0 6px 16px rgba(37, 99, 235, 0.35)',
                }}
              >
                &#128737;&#65039;
              </div>
              <div>
                <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em' }}>CBDC Fraud Detection</h1>
                <p style={{ margin: '5px 0 0', color: COLORS.subtext, maxWidth: 620, fontSize: 13.5, lineHeight: 1.5 }}>
                  Real-time operational view of local training, live fraud alerts, transaction graph activity, and supporting service health.
                </p>
              </div>
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
            icon={ICONS.alerts}
            tone={alertsTone}
            title="Fraud Alerts"
            value={alerts.length}
            subtitle={`${analytics.criticalOrHigh} high/critical alerts, ${alertSummary.recent_detector_alerts || 0} detected from transaction stream`}
          />
          <StatCard
            icon={ICONS.accuracy}
            tone={accuracyTone}
            title="Model Accuracy"
            value={typeof modelAccuracy === 'number' ? `${(modelAccuracy * 100).toFixed(2)}%` : 'N/A'}
            subtitle={typeof modelLoss === 'number' ? `Latest loss ${modelLoss.toFixed(4)}` : 'Awaiting latest training metrics'}
          />
          <StatCard
            icon={ICONS.graph}
            tone="info"
            title="Graph Accounts"
            value={typeof totalTransactions === 'number' ? totalTransactions : 'N/A'}
            subtitle="Current transaction-graph account snapshot"
          />
          <StatCard
            icon={ICONS.confidence}
            tone="info"
            title="Avg Alert Confidence"
            value={typeof analytics.avgConfidence === 'number' ? `${(analytics.avgConfidence * 100).toFixed(1)}%` : 'N/A'}
            subtitle={`History source: ${alertSummary.persistence_mode || 'unknown'}`}
          />
          <StatCard
            icon={ICONS.risk}
            tone={riskTone}
            title="High-Risk Predictions"
            value={analytics.highRiskPredictions.length}
            subtitle={
              typeof analytics.topInferenceConfidence === 'number'
                ? `Top confidence ${(analytics.topInferenceConfidence * 100).toFixed(1)}%`
                : 'Awaiting inference snapshot'
            }
          />
        </div>

        <div
          style={{
            columns: '3 380px',
            columnGap: 16,
          }}
        >
          <SectionCard
            icon={ICONS.agent}
            title="Operational Snapshot"
            subtitle="Live agent status, round metadata, and supporting service availability."
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div style={{ display: 'grid', gap: 8, alignContent: 'start' }}>
                {[
                  ['Agent ID', agentStatus?.agent_id || 'N/A'],
                  ['Last Round', agentStatus?.last_round_id || 'N/A'],
                  ['Last Update', formatTimestamp(agentStatus?.last_update_at)],
                  ['Update Age', formatRelativeTime(agentStatus?.last_update_at)],
                  ['Last Inference', formatTimestamp(agentStatus?.last_inference_at)],
                  [
                    'Data Feeds',
                    fetchState.statusLoaded && fetchState.alertsLoaded && fetchState.graphLoaded && fetchState.inferenceLoaded
                      ? 'Loaded'
                      : 'Refreshing…',
                  ],
                  ['Alert Detector', alertSummary.detector_enabled ? 'Transaction Stream Active' : 'Unavailable'],
                  [
                    'Alert Sources',
                    analytics.sourceCounts.length > 0
                      ? analytics.sourceCounts.map((item) => `${item.source} (${item.count})`).join(', ')
                      : 'N/A',
                  ],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 12,
                      padding: '8px 2px',
                      borderBottom: `1px solid ${COLORS.border}`,
                    }}
                  >
                    <span style={{ fontSize: 12.5, color: COLORS.subtext, fontWeight: 600 }}>{label}</span>
                    <span
                      style={{
                        fontSize: 12.5,
                        fontWeight: 700,
                        color: COLORS.text,
                        textAlign: 'right',
                        maxWidth: '65%',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={String(value)}
                    >
                      {value}
                    </span>
                  </div>
                ))}
              </div>
              <div>
                <div style={{ display: 'grid', gap: 8 }}>
                  {serviceDefinitions.map((service) => {
                    const healthy = Boolean(serviceHealth[service.name]);
                    return (
                      <div
                        key={service.name}
                        style={{
                          position: 'relative',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          border: `1px solid ${COLORS.border}`,
                          borderRadius: 10,
                          padding: '9px 12px 9px 14px',
                          background: '#fafbfd',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            bottom: 0,
                            width: 3,
                            background: healthy ? COLORS.success : COLORS.danger,
                          }}
                        />
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 700, fontSize: 13 }}>{service.label}</div>
                          <div
                            style={{
                              fontSize: 11,
                              color: COLORS.subtext,
                              fontFamily: COLORS.mono,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {service.url}
                          </div>
                        </div>
                        <StatusPill label={healthy ? 'Healthy' : 'Unavailable'} healthy={healthy} />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            icon={ICONS.shortcuts}
            title="Operator Shortcuts"
            subtitle="Separated access zones for streaming observability and workflow-state inspection."
          >
            <div style={{ display: 'grid', gap: 18 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                  gap: 16,
                }}
              >
                <AccessPanel
                  icon={ICONS.kafka}
                  accent={COLORS.neutral}
                  eyebrow="Streaming Observability"
                  title="Kafka UI"
                  description="Inspect brokers, topics, and the live fraud-event pipeline in a dedicated workspace."
                  href={kafkaUiUrl}
                  actionLabel="Open Kafka UI"
                  status={<StatusPill label={operatorShortcutHealth.kafka ? 'Healthy' : 'Unavailable'} healthy={operatorShortcutHealth.kafka} />}
                  statusCaption="Kafka Service"
                >
                  <div style={{ display: 'grid', gap: 8 }}>
                    <div><strong>Cluster:</strong> federated-fraud-kafka</div>
                    <div><strong>Broker:</strong> kafka:9092 (id: 1)</div>
                    <div><strong>Pipeline:</strong> {`${alertSummary.transaction_topic || 'transactions.events'} -> alerting -> ${alertSummary.alerts_topic || 'fraud.alerts'}`}</div>
                  </div>
                </AccessPanel>
                <AccessPanel
                  icon={ICONS.redis}
                  accent="#7c3aed"
                  eyebrow="Workflow State"
                  title="Redis Insight"
                  description="Inspect orchestration state, stored keys, and runtime coordination data without mixing it with Kafka tooling."
                  href={redisInsightUrl}
                  actionLabel="Open Redis Insight"
                  status={<StatusPill label={operatorShortcutHealth.redis ? 'Healthy' : 'Unavailable'} healthy={operatorShortcutHealth.redis} />}
                  statusCaption="Redis Service"
                >
                  <div style={{ display: 'grid', gap: 8 }}>
                    <div><strong>Store:</strong> redis:6379</div>
                    <div><strong>Purpose:</strong> workflow state for `agentic-coordinator`</div>
                    <div><strong>Access URL:</strong> {redisInsightUrl}</div>
                  </div>
                </AccessPanel>
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: COLORS.text }}>{ICONS.endpoints} Endpoint Directory</span>
                  <span style={{ fontSize: 11.5, color: COLORS.subtext }}>Notifications: {alertSummary.outbound_channels.filter((item) => item.configured).map((item) => item.channel).join(', ') || 'none configured'}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 10 }}>
                  <EndpointChip label="Dashboard" value={dashboardUiUrl} />
                  <EndpointChip label="Alerting WebSocket" value={`${wsOrigin}/ws/alerts`} />
                  {serviceDefinitions.map((service) => (
                    <EndpointChip key={service.name} label={service.label} value={service.url} />
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard icon={ICONS.pie} title="Alerts by Severity" subtitle="Current in-memory distribution from the Alerting service.">
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

          <SectionCard icon={ICONS.bars} title="Most Alerted Transactions" subtitle="Top transaction IDs by recent alert count.">
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

          <SectionCard icon={ICONS.sources} title="Alert Sources" subtitle="Distribution of recent alerts by producing detector or upstream source.">
            {analytics.sourceCounts.length === 0 ? (
              <EmptyState text="No alert-source distribution available yet." />
            ) : (
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analytics.sourceCounts} barCategoryGap="35%">
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="source" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} width={32} />
                    <Tooltip />
                    <Bar dataKey="count" fill={COLORS.high} radius={[6, 6, 0, 0]} maxBarSize={64} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </SectionCard>

          <SectionCard icon={ICONS.accounts} title="Most Active Accounts" subtitle="Accounts with the highest combined sent/received activity.">
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

          <SectionCard icon={ICONS.timeline} title="Alert Timeline" subtitle="Sequential view of recent alert intensity across the current window.">
            {analytics.alertTimeline.length === 0 ? (
              <EmptyState text="No alert timeline available yet." />
            ) : (
              <>
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

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                    gap: 10,
                    marginTop: 18,
                  }}
                >
                  {[
                    {
                      label: 'Peak Severity',
                      value: SEVERITY_ORDER.find((s) => alerts.some((a) => String(a.severity || '').toLowerCase() === s)) || 'N/A',
                      tone: 'danger',
                    },
                    {
                      label: 'Trend',
                      value: (() => {
                        const points = analytics.alertTimeline;
                        if (points.length < 2) return 'Stable';
                        const mid = Math.floor(points.length / 2);
                        const firstAvg = points.slice(0, mid).reduce((s, p) => s + p.severityScore, 0) / Math.max(mid, 1);
                        const secondAvg = points.slice(mid).reduce((s, p) => s + p.severityScore, 0) / Math.max(points.length - mid, 1);
                        if (secondAvg > firstAvg + 0.15) return 'Rising';
                        if (secondAvg < firstAvg - 0.15) return 'Falling';
                        return 'Stable';
                      })(),
                      tone: 'info',
                    },
                    {
                      label: 'Latest Alert',
                      value: alerts.length > 0 ? formatRelativeTime(alerts[0]?.received_at || alerts[0]?.timestamp) : 'N/A',
                      tone: 'neutral',
                    },
                    {
                      label: 'Window Size',
                      value: `${alerts.length} alert${alerts.length === 1 ? '' : 's'}`,
                      tone: 'neutral',
                    },
                  ].map((item) => {
                    const tone = TONE_MAP[item.tone] || TONE_MAP.neutral;
                    return (
                      <div
                        key={item.label}
                        style={{
                          border: `1px solid ${COLORS.border}`,
                          borderRadius: 10,
                          padding: '10px 12px',
                          background: '#fafbfd',
                        }}
                      >
                        <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.subtext, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          {item.label}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 15, fontWeight: 800, color: tone.fg, textTransform: 'capitalize' }}>
                          {item.value}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div style={{ marginTop: 18 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.text, marginBottom: 10 }}>Recent Highlights</div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {alerts.slice(0, 5).map((alert, index) => (
                      <div
                        key={alert.alert_id || `${index}-${alert.txId || alert.tx_id || 'tx'}`}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: 12,
                          border: `1px solid ${COLORS.border}`,
                          borderRadius: 10,
                          padding: '9px 12px',
                          background: '#fafbfd',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                          <span
                            style={{
                              display: 'inline-block',
                              borderRadius: 999,
                              padding: '3px 8px',
                              fontSize: 10.5,
                              fontWeight: 700,
                              textTransform: 'capitalize',
                              background: `${severityColor(alert.severity)}18`,
                              color: severityColor(alert.severity),
                              flexShrink: 0,
                            }}
                          >
                            {alert.severity || 'unknown'}
                          </span>
                          <span
                            style={{
                              fontFamily: COLORS.mono,
                              fontSize: 12,
                              color: COLORS.text,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {alert.txId || alert.tx_id || alert.alert_id || 'N/A'}
                          </span>
                        </div>
                        <span style={{ fontSize: 11.5, color: COLORS.subtext, flexShrink: 0 }}>
                          {formatRelativeTime(alert.received_at || alert.timestamp)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </SectionCard>

          <SectionCard icon={ICONS.metrics} title="Training Metrics" subtitle="Latest metrics reported by the Local Agent after a training round.">
              {agentStatus?.last_metrics && Object.keys(agentStatus.last_metrics).length > 0 ? (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
                    gap: 8,
                  }}
                >
                  {Object.entries(agentStatus.last_metrics).map(([key, value]) => (
                    <div
                      key={key}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 10,
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: 9,
                        padding: '9px 12px',
                        background: '#fafbfd',
                      }}
                    >
                      <span style={{ fontSize: 12.5, fontWeight: 600, textTransform: 'capitalize', color: COLORS.text }}>
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span style={{ fontFamily: COLORS.mono, fontSize: 12, color: COLORS.subtext, fontWeight: 600 }}>
                        {typeof value === 'number' ? value.toFixed(4) : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState text="Training metrics have not been reported yet." />
              )}
            </SectionCard>

            <SectionCard
              icon={ICONS.watchlist}
              title="Inference Watchlist"
              subtitle="Top ranked Local GNN fraud predictions routed through the Local Agent."
            >
              {inferenceSnapshot.predictions.length === 0 ? (
                <EmptyState text="No inference predictions available yet." />
              ) : (
                <div style={{ display: 'grid', gap: 10 }}>
                  {inferenceSnapshot.predictions.map((prediction) => (
                    <div
                      key={prediction.tx_id}
                      style={{
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: 10,
                        padding: '12px 14px',
                        background: '#f9fafb',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                        <strong style={{ fontFamily: 'monospace' }}>tx {prediction.tx_id}</strong>
                        <span
                          style={{
                            display: 'inline-block',
                            borderRadius: 999,
                            padding: '4px 8px',
                            background:
                              String(prediction.predicted_class).toLowerCase() === 'illicit' ? '#fee2e2' : '#dbeafe',
                            color:
                              String(prediction.predicted_class).toLowerCase() === 'illicit' ? '#991b1b' : '#1d4ed8',
                            fontWeight: 700,
                            textTransform: 'capitalize',
                          }}
                        >
                          {prediction.predicted_class}
                        </span>
                      </div>
                      <div style={{ display: 'grid', gap: 4, color: COLORS.subtext, fontSize: 13 }}>
                        <div><strong>Confidence:</strong> {(Number(prediction.confidence || 0) * 100).toFixed(2)}%</div>
                        <div><strong>Illicit Probability:</strong> {(Number(prediction.illicit_probability || 0) * 100).toFixed(2)}%</div>
                        <div><strong>Known Label:</strong> {prediction.known_label || 'unknown'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>

          <SectionCard
            icon={ICONS.registry}
            title="Model Registry & Governance"
            subtitle="Combines backend model-registry history with live governance policy, privacy budget, and audit data from policy-manager."
          >
            <div style={{ display: 'grid', gap: 16 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
                  gap: 12,
                }}
              >
                {[
                  {
                    label: 'Policy Version',
                    value: typeof policyVersion === 'number' ? `v${policyVersion}` : 'N/A',
                    detail: `Updated ${formatRelativeTime(globalPolicies?.updated_at)}`,
                  },
                  {
                    label: 'Aggregation Strategy',
                    value: aggregationStrategy || 'N/A',
                    detail: globalPolicies?.fallback_aggregation_strategy
                      ? `Fallback ${globalPolicies.fallback_aggregation_strategy}`
                      : 'Awaiting policy payload',
                  },
                  {
                    label: 'Privacy Budget',
                    value: privacyBudgetUsage,
                    detail: `Delta ${privacyDeltaUsage}`,
                  },
                  {
                    label: 'Governed Agent',
                    value: governanceAgent?.active ? 'Active' : governanceAgent ? 'Inactive' : 'N/A',
                    detail:
                      typeof governanceAgent?.minimum_reliability_score === 'number'
                        ? `Min reliability ${governanceAgent.minimum_reliability_score.toFixed(2)}`
                        : 'Awaiting governance agent profile',
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    style={{
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: 12,
                      padding: '14px 16px',
                      background: '#f9fafb',
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 700, color: COLORS.subtext }}>{item.label}</div>
                    <div style={{ marginTop: 8, fontSize: 22, fontWeight: 800, color: COLORS.text }}>{item.value}</div>
                    <div style={{ marginTop: 6, fontSize: 12, color: COLORS.subtext }}>{item.detail}</div>
                  </div>
                ))}
              </div>

              <div
                style={{
                  display: 'grid',
                  gap: 16,
                }}
              >
                <div>
                  {modelVersions.length === 0 ? (
                    <EmptyState text="No model versions registered yet." />
                  ) : (
                    <div style={{ display: 'grid', gap: 10, maxHeight: 420, overflowY: 'auto', paddingRight: 4 }}>
                      {modelVersions.map((mv) => {
                        const isActive = activeModelVersionId && mv.version_id === activeModelVersionId;
                        return (
                          <div
                            key={mv.version_id}
                            style={{
                              position: 'relative',
                              border: `1px solid ${isActive ? '#bbf7d0' : COLORS.border}`,
                              borderRadius: 12,
                              padding: '12px 14px 12px 16px',
                              background: isActive ? COLORS.successSoft : '#fafbfd',
                              overflow: 'hidden',
                            }}
                          >
                            {isActive ? (
                              <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: 3, background: COLORS.success }} />
                            ) : null}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                              <span
                                style={{
                                  fontFamily: COLORS.mono,
                                  fontSize: 12.5,
                                  fontWeight: 700,
                                  color: COLORS.text,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                                title={mv.version_id}
                              >
                                {mv.version_id}
                              </span>
                              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                                <span
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4,
                                    borderRadius: 999,
                                    padding: '2px 8px',
                                    fontSize: 10.5,
                                    fontWeight: 700,
                                    color: isActive ? '#15803d' : COLORS.subtext,
                                    background: isActive ? '#dcfce7' : '#f3f4f6',
                                  }}
                                >
                                  {isActive ? (
                                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#16a34a' }} />
                                  ) : null}
                                  {isActive ? 'Active' : 'Registered'}
                                </span>
                                <span
                                  style={{
                                    display: 'inline-block',
                                    borderRadius: 999,
                                    padding: '2px 8px',
                                    fontSize: 10.5,
                                    fontWeight: 700,
                                    background: mv.is_global ? '#e0f2fe' : '#fef3c7',
                                    color: mv.is_global ? '#0369a1' : '#b45309',
                                  }}
                                >
                                  {mv.is_global ? 'Global' : 'Local'}
                                </span>
                              </div>
                            </div>
                            <div style={{ marginTop: 4, fontSize: 11.5, color: COLORS.subtext }}>{formatTimestamp(mv.created_at)}</div>
                            {mv.metrics && Object.keys(mv.metrics).length > 0 ? (
                              <div
                                style={{
                                  marginTop: 8,
                                  display: 'grid',
                                  gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
                                  gap: 6,
                                }}
                              >
                                {Object.entries(mv.metrics).map(([name, val]) => (
                                  <div key={name} style={{ fontSize: 11, fontFamily: COLORS.mono, color: COLORS.subtext }}>
                                    <span style={{ textTransform: 'capitalize' }}>{name.replace(/_/g, ' ')}</span>
                                    <div style={{ color: COLORS.text, fontWeight: 700 }}>
                                      {typeof val === 'number' ? val.toFixed(4) : String(val)}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div style={{ marginTop: 6, fontSize: 11.5, color: COLORS.subtext }}>No metrics</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            icon={ICONS.trends}
            title="Model Performance Trends"
            subtitle="Comparing Accuracy and Loss metrics over registered versions."
          >
            <div style={{ display: 'grid', gap: 16 }}>
              <div style={{ height: 260 }}>
                {modelVersions.length === 0 ? (
                  <EmptyState text="Awaiting model registry versions data." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={[...modelVersions].reverse().map((mv) => ({
                        version_id: mv.version_id,
                        metrics: {
                          accuracy:
                            typeof mv.metrics?.accuracy === 'number' ? Math.min(1, Number(mv.metrics.accuracy.toFixed(4))) : null,
                          loss: typeof mv.metrics?.loss === 'number' ? Math.min(1, Number(mv.metrics.loss.toFixed(4))) : null,
                        },
                      }))}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="version_id" tick={{ fontSize: 10 }} />
                      <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={(v) => v.toFixed(2)} />
                      <Tooltip formatter={(value) => (typeof value === 'number' ? value.toFixed(4) : value)} />
                      <Legend />
                      <Line type="monotone" dataKey="metrics.accuracy" stroke="#16a34a" strokeWidth={2} name="Accuracy" />
                      <Line type="monotone" dataKey="metrics.loss" stroke="#dc2626" strokeWidth={2} name="Loss" />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div
                style={{
                  display: 'grid',
                  gap: 10,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: 12,
                  padding: 14,
                  background: '#f9fafb',
                  minHeight: 320,
                }}
              >
                <div style={{ fontWeight: 700, color: COLORS.text }}>Governance Audit Trail</div>
                {governanceAuditEvents.length === 0 ? (
                  <div style={{ color: COLORS.subtext, fontSize: 13 }}>
                    {fetchState.governanceLoaded ? 'No governance audit events available.' : 'Loading governance audit events...'}
                  </div>
                ) : (
                  governanceAuditEvents.map((event) => (
                    <div
                      key={event.id}
                      style={{
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: 10,
                        padding: '10px 12px',
                        background: COLORS.card,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 4 }}>
                        <strong style={{ fontSize: 13 }}>{event.event_type}</strong>
                        <span style={{ fontSize: 12, color: COLORS.subtext }}>{formatTimestamp(event.created_at)}</span>
                      </div>
                      <div style={{ fontSize: 12, color: COLORS.subtext }}>
                        <strong>Agent:</strong> {event.agent_id || 'system'}
                      </div>
                      <div style={{ marginTop: 4, fontSize: 12, color: COLORS.subtext, fontFamily: 'monospace' }}>
                        {JSON.stringify(event.details || {})}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </SectionCard>
        </div>

        <SectionCard icon={ICONS.feed} title="Recent Alerts Feed" subtitle="Live alert stream from the Alerting service, enriched with timestamps and confidence.">
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
