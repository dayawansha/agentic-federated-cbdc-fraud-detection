import React, { useEffect, useMemo, useState } from 'react';

function App() {
  const localAgentUrl = useMemo(() => {
    return process.env.REACT_APP_LOCAL_AGENT_URL || 'http://localhost:9001';
  }, []);

  const alertingUrl = useMemo(() => {
    return process.env.REACT_APP_ALERTING_URL || 'http://localhost:9005';
  }, []);

  const alertingWsUrl = useMemo(() => {
    const override = process.env.REACT_APP_ALERTING_WS_URL;
    if (override) return override;
    return alertingUrl.replace(/^http/, 'ws');
  }, [alertingUrl]);

  const [agentStatus, setAgentStatus] = useState(null);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    let cancelled = false;

    const fetchAll = async () => {
      try {
        const statusResp = await fetch(`${localAgentUrl}/agent/status`);
        if (statusResp.ok) {
          const statusJson = await statusResp.json();
          if (!cancelled) setAgentStatus(statusJson);
        }
      } catch (e) {}

      try {
        const alertsResp = await fetch(`${alertingUrl}/alerts/recent?limit=25`);
        if (alertsResp.ok) {
          const alertsJson = await alertsResp.json();
          if (!cancelled) setAlerts(alertsJson);
        }
      } catch (e) {}
    };

    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [alertingUrl, localAgentUrl]);

  useEffect(() => {
    let ws;
    try {
      ws = new WebSocket(`${alertingWsUrl}/ws/alerts`);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setAlerts((prev) => [payload, ...prev].slice(0, 50));
        } catch (e) {}
      };
    } catch (e) {}
    return () => {
      if (ws) ws.close();
    };
  }, [alertingWsUrl]);

  const fraudAlertsCount = alerts.length;
  const modelAccuracy = agentStatus?.last_metrics?.accuracy;

  return (
    <div className="App">
      <header className="App-header">
        <h1>CBDC Fraud Detection Dashboard</h1>
        <p>Real-time monitoring and analytics for federated fraud detection.</p>
      </header>
      <main>
        <div className="stats-container">
          <div className="card">
            <h3>Total Transactions</h3>
            <p>-</p>
          </div>
          <div className="card">
            <h3>Fraud Alerts</h3>
            <p>{fraudAlertsCount}</p>
          </div>
          <div className="card">
            <h3>Model Accuracy</h3>
            <p>{typeof modelAccuracy === 'number' ? `${(modelAccuracy * 100).toFixed(2)}%` : '-'}</p>
          </div>
        </div>

        <div className="card" style={{ marginTop: 16 }}>
          <h3>Recent Alerts</h3>
          {alerts.length === 0 ? (
            <p>No alerts.</p>
          ) : (
            <ul>
              {alerts.slice(0, 10).map((a, idx) => (
                <li key={a.alert_id || `${idx}`}>
                  <strong>{a.severity || 'unknown'}</strong> — {a.alert_id || 'n/a'} — tx {a.txId || a.tx_id || 'n/a'}
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
