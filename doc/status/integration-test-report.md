# Integration Test Report

Date: 2026-06-27
Project: Agentic Federated CBDC Fraud Detection
Environment: Local Docker Compose stack on macOS

## Scope

This report captures the latest integration and end-to-end validation run after fixing the `local-agent` inference endpoint failure that previously surfaced in the dashboard as a `500` on `/api/local-agent/agent/inference`.

The validation covered:

- direct service health across the core federated learning path
- end-to-end federated round execution
- dashboard proxy integration for key operator-facing APIs
- regression verification for the `local-agent` inference fix

## Fix Under Test

Service: `bank-node/local-agent`

Issue:

- `GET /agent/inference?limit=5` could fail with `500 Internal Server Error`
- the failure was caused by upstream inference payloads containing `None` for numeric fields such as:
  - `confidence`
  - `illicit_probability`
  - `licit_probability`
  - `unknown_probability`

Fix applied:

- inference records are now normalized before `AgentInferencePrediction` model construction
- null numeric fields are converted to safe numeric defaults instead of causing Pydantic validation failure

Relevant files:

- [main.py](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/local-agent/src/main.py)
- [test_main.py](file:///Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/bank-node/local-agent/tests/test_main.py)

## Commands Run

### Focused Local-Agent Regression Test

```bash
python3 -m unittest bank-node/local-agent/tests/test_main.py
```

Result:

- Passed
- Total tests: `16`

### End-to-End Federated Learning Test

```bash
python3 scripts/e2e_fl_test.py
```

Result:

- Passed
- Verified:
  - coordinator health
  - local-agent health
  - local-gnn health
  - privacy-layer health
  - federated round startup
  - federated round completion at `round_complete`

### Dashboard Proxy Integration Smoke Check

Checked:

- `http://localhost:3000`
- `http://localhost:3000/api/local-agent/health`
- `http://localhost:3000/api/local-agent/agent/inference?limit=5`
- `http://localhost:3000/api/policy-manager/health`
- `http://localhost:3000/api/alerting/health`
- `http://localhost:3000/api/model-registry/health`
- `http://localhost:3000/api/local-gnn/health`
- `http://localhost:3000/api/transaction-graph/health`

Result:

- Final verification passed
- All checked dashboard routes returned `200`

## Observations

### Local-Agent Inference

- Direct endpoint check after fix:
  - `http://localhost:9001/agent/inference?limit=5`
- Result:
  - returned `200`

- Dashboard proxy check after fix:
  - `http://localhost:3000/api/local-agent/agent/inference?limit=5`
- Result:
  - returned `200`

### Temporary Dashboard Proxy Errors

During verification, the dashboard briefly returned `502` for some proxied services including:

- `policy-manager`
- `model-registry`
- `transaction-graph`
- `local-gnn`

Root cause:

- after Docker Compose rebuilds, the dashboard nginx proxy held stale upstream container IPs
- direct service checks still showed healthy services

Mitigation performed:

```bash
docker restart infrastructure-fraud-dashboard-1
```

Result:

- dashboard proxy routing recovered
- all rechecked proxy endpoints returned `200`

## Overall Result

Status: Passed

Summary:

- the original `local-agent` inference integration issue is fixed
- the federated learning round completes successfully end to end
- the dashboard integration path is healthy after refreshing the dashboard container following Compose rebuilds

## Remaining Note

There is one non-blocking code-quality note still present in `local-agent`:

- FastAPI `on_event` usage is deprecated and should eventually be migrated to lifespan handlers

This did not affect the integration outcome of the current validation run.
