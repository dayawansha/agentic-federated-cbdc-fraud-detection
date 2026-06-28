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

function ActionButton({ href, label, background = COLORS.neutral }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      style={{
        display: 'inline-block',
        padding: '10px 14px',
        borderRadius: 8,
        background,
        color: '#fff',
        textDecoration: 'none',
        fontWeight: 700,
      }}
    >
      {label}
    </a>
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

function AccessPanel({ accent, eyebrow, title, description, href, actionLabel, status, statusCaption, children }) {
  return (
    <div
      style={{
        display: 'grid',
        gap: 16,
        padding: 18,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 16,
        background: `linear-gradient(180deg, ${accent}14 0%, ${COLORS.card} 38%)`,
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)',
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
        <div style={{ marginTop: 6, fontSize: 22, fontWeight: 800, color: COLORS.text }}>{title}</div>
        <p style={{ margin: '8px 0 0', color: COLORS.subtext, lineHeight: 1.5 }}>{description}</p>
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
            subtitle={`${analytics.criticalOrHigh} high/critical alerts, ${alertSummary.recent_detector_alerts || 0} detected from transaction stream`}
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
            subtitle={`History source: ${alertSummary.persistence_mode || 'unknown'}`}
          />
          <StatCard
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
                  <div><strong>Last Inference:</strong> {formatTimestamp(agentStatus?.last_inference_at)}</div>
                  <div><strong>Data Feeds:</strong> {fetchState.statusLoaded && fetchState.alertsLoaded && fetchState.graphLoaded && fetchState.inferenceLoaded ? 'Loaded' : 'Refreshing...'}</div>
                  <div><strong>Alert Detector:</strong> {alertSummary.detector_enabled ? 'Transaction Stream Active' : 'Unavailable'}</div>
                  <div><strong>Alert Sources:</strong> {analytics.sourceCounts.length > 0 ? analytics.sourceCounts.map((item) => `${item.source} (${item.count})`).join(', ') : 'N/A'}</div>
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
            subtitle="Separated access zones for streaming observability and workflow-state inspection."
          >
            <div style={{ display: 'grid', gap: 16 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                  gap: 16,
                }}
              >
                <AccessPanel
                  accent={COLORS.neutral}
                  eyebrow="Streaming Observability"
                  title="Kafka UI"
                  description="Inspect brokers, topics, and the live fraud-event pipeline in a dedicated workspace."
                  href={kafkaUiUrl}
                  actionLabel="Open Kafka UI"
                  status={<StatusPill label={operatorShortcutHealth.kafka ? 'Healthy' : 'Unavailable'} healthy={operatorShortcutHealth.kafka} />}
                  statusCaption="Kafka Service"
                >
                  <div style={{ display: 'grid', gap: 10 }}>
                    <div><strong>Cluster:</strong> federated-fraud-kafka</div>
                    <div><strong>Broker:</strong> kafka:9092 (id: 1)</div>
                    <div><strong>Pipeline:</strong> {`${alertSummary.transaction_topic || 'transactions.events'} -> alerting -> ${alertSummary.alerts_topic || 'fraud.alerts'}`}</div>
                  </div>
                </AccessPanel>
                <AccessPanel
                  accent="#7c3aed"
                  eyebrow="Workflow State"
                  title="Redis Insight"
                  description="Inspect orchestration state, stored keys, and runtime coordination data without mixing it with Kafka tooling."
                  href={redisInsightUrl}
                  actionLabel="Open Redis Insight"
                  status={<StatusPill label={operatorShortcutHealth.redis ? 'Healthy' : 'Unavailable'} healthy={operatorShortcutHealth.redis} />}
                  statusCaption="Redis Service"
                >
                  <div style={{ display: 'grid', gap: 10 }}>
                    <div><strong>Store:</strong> redis:6379</div>
                    <div><strong>Purpose:</strong> workflow state for `agentic-coordinator`</div>
                    <div><strong>Access URL:</strong> {redisInsightUrl}</div>
                  </div>
                </AccessPanel>
              </div>
              <div><strong>CBDC Fraud Detection Dashboard:</strong> {dashboardUiUrl}</div>
              <div><strong>Notification Channels:</strong> {alertSummary.outbound_channels.filter((item) => item.configured).map((item) => item.channel).join(', ') || 'None configured'}</div>
              <div><strong>Transaction Graph API:</strong> {serviceDefinitions.find((item) => item.name === 'transaction-graph')?.url}</div>
              <div><strong>Alerting API:</strong> {serviceDefinitions.find((item) => item.name === 'alerting')?.url}</div>
              <div><strong>Alerting WebSocket:</strong> {`${wsOrigin}/ws/alerts`}</div>
              <div style={{ display: 'grid', gap: 8, padding: 12, border: `1px solid ${COLORS.border}`, borderRadius: 10, background: '#f9fafb' }}>
                <div style={{ fontWeight: 700 }}>Core Service Access Index</div>
                <div>{[
                  `Dashboard ${dashboardUiUrl}`,
                  `Kafka UI ${kafkaUiUrl}`,
                  `Model Registry ${serviceDefinitions.find((item) => item.name === 'model-registry')?.url}`,
                  `Policy Manager ${serviceDefinitions.find((item) => item.name === 'policy-manager')?.url}`,
                  `Local Agent ${serviceDefinitions.find((item) => item.name === 'local-agent')?.url}`,
                  `Local GNN ${serviceDefinitions.find((item) => item.name === 'local-gnn')?.url}`,
                  `Privacy Layer ${serviceDefinitions.find((item) => item.name === 'privacy-layer')?.url}`,
                  `Transaction Graph ${serviceDefinitions.find((item) => item.name === 'transaction-graph')?.url}`,
                  `Alerting ${serviceDefinitions.find((item) => item.name === 'alerting')?.url}`,
                ].join(' | ')}</div>
              </div>
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

          <SectionCard title="Alert Sources" subtitle="Distribution of recent alerts by producing detector or upstream source.">
            {analytics.sourceCounts.length === 0 ? (
              <EmptyState text="No alert-source distribution available yet." />
            ) : (
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analytics.sourceCounts}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="source" hide />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill={COLORS.high} radius={[6, 6, 0, 0]} />
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

          <div style={{ display: 'grid', gap: 16 }}>
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

            <SectionCard
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
          </div>
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
                <div style={{ overflowX: 'auto', maxHeight: '320px' }}>
                  {modelVersions.length === 0 ? (
                    <EmptyState text="No model versions registered yet." />
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: '#f3f4f6' }}>
                          {['Status', 'Version ID', 'Created At', 'Type', 'Metrics'].map((heading) => (
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
                        {modelVersions.map((mv) => {
                          const isActive = activeModelVersionId && mv.version_id === activeModelVersionId;
                          return (
                            <tr key={mv.version_id} style={{ background: isActive ? '#f0fdf4' : 'transparent' }}>
                              <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>
                                {isActive ? (
                                  <span
                                    style={{
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: 4,
                                      borderRadius: 999,
                                      padding: '2px 8px',
                                      fontSize: 11,
                                      fontWeight: 700,
                                      color: '#15803d',
                                      background: '#dcfce7',
                                    }}
                                  >
                                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#16a34a' }} />
                                    Active
                                  </span>
                                ) : (
                                  <span
                                    style={{
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: 4,
                                      borderRadius: 999,
                                      padding: '2px 8px',
                                      fontSize: 11,
                                      fontWeight: 700,
                                      color: COLORS.subtext,
                                      background: '#f3f4f6',
                                    }}
                                  >
                                    Registered
                                  </span>
                                )}
                              </td>
                              <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}`, fontFamily: 'monospace', fontWeight: isActive ? 700 : 'normal' }}>
                                {mv.version_id}
                              </td>
                              <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}`, fontSize: 13 }}>
                                {formatTimestamp(mv.created_at)}
                              </td>
                              <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}` }}>
                                <span
                                  style={{
                                    display: 'inline-block',
                                    borderRadius: 999,
                                    padding: '2px 6px',
                                    fontSize: 11,
                                    background: mv.is_global ? '#e0f2fe' : '#fef3c7',
                                    color: mv.is_global ? '#0369a1' : '#b45309',
                                    fontWeight: 600,
                                  }}
                                >
                                  {mv.is_global ? 'Global' : 'Local'}
                                </span>
                              </td>
                              <td style={{ padding: '10px 12px', borderBottom: `1px solid ${COLORS.border}`, fontSize: 12, fontFamily: 'monospace' }}>
                                {mv.metrics && Object.keys(mv.metrics).length > 0 ? (
                                  Object.entries(mv.metrics).map(([name, val]) => (
                                    <div key={name}>
                                      <strong>{name}:</strong> {typeof val === 'number' ? val.toFixed(4) : String(val)}
                                    </div>
                                  ))
                                ) : (
                                  <span style={{ color: COLORS.subtext }}>No metrics</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title="Model Performance Trends"
            subtitle="Comparing Accuracy and Loss metrics over registered versions."
          >
            <div style={{ display: 'grid', gap: 16 }}>
              <div style={{ height: 260 }}>
                {modelVersions.length === 0 ? (
                  <EmptyState text="Awaiting model registry versions data." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={[...modelVersions].reverse()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="version_id" tick={{ fontSize: 10 }} />
                      <YAxis domain={[0, 1]} />
                      <Tooltip />
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
