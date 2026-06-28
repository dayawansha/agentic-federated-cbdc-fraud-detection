# Debug Session: `model-metrics-persistence`

- Status: RESOLVED
- Started: 2026-06-27
- Symptom: The dashboard can compute model accuracy during a round, but the latest backend sources do not retain those metrics for `local-agent` status or the latest `model-registry` model entry.
- Expected: After a completed round, the latest round metrics should persist into `local-agent` status and the latest registered model so the dashboard reflects the latest round without historical fallback.

## Hypotheses

1. The local round completes, but `local-agent` status is read too early and metrics are only written after a delayed post-round step.
2. `local-agent` computes and forwards metrics, but its in-memory `agent_status` is not being updated or is being reset afterward.
3. The coordinator computes aggregate metrics, but the `model-registry` registration call silently fails or returns a non-200 response that is currently ignored.
4. The coordinator registers a new model, but ordering/latest-model selection in `model-registry` still surfaces an older empty-metrics entry.

## Evidence Log

- **Hypothesis 3 — CONFIRMED (primary root cause):** In `aggregate_results` (coordinator, line 1016-1028), the `await client.post(MODEL_REGISTRY_URL/models/register, ...)` call had its HTTP response completely ignored. The `except` block only caught network exceptions — a 400 or 500 from the registry was silently swallowed with just a generic `logger.warning(f"Model registry registration failed: {e}")` that never fired for HTTP-level errors. Result: the model registry never received the round metrics, so every `GET /models/latest` returned a row with `metrics={}`.

- **Hypothesis 4 — CONFIRMED (secondary root cause):** In `model-registry` startup `_synchronize_registry_with_local_artifacts()`, orphaned `.pt` files were re-imported with `created_at = st_mtime`. If the coordinator had just written a new `.pt` artifact file (triggering `st_mtime` to "now"), the orphan import gave it a timestamp newer than earlier DB rows, making it sort first in `ORDER BY created_at DESC`. That entry had `metrics={}`, so `GET /models/latest` returned empty metrics even when the DB contained a valid coordinator-registered row.

- **Hypothesis 2 — PARTIALLY CONFIRMED (tertiary cause):** After a round, `agent_status["last_metrics"]` was set from the local GNN `final_state["metrics"]`, which contains local training metrics (accuracy, loss, etc.). These metrics are correct. However, `agent_status["last_model_version"]` was set from `final_state.get("model_version_id")`, which is the version_id fetched at the *start* of the round (the global model the agent loaded), never the newly registered one. So `activeModelVersionId` in the dashboard resolved to a stale version and `activeRegistryMetrics` fetched from a potentially older model row.

## Fix Log

- **[FIXED] Coordinator registration response check** (`central-coordinator/agentic-coordinator/src/main.py`):
  Changed `await client.post(...)` (fire-and-forget) to assign the response and check `reg_response.status_code`. On 200 the version_id is logged at INFO. On non-200 a `logger.warning` captures the status code and full response body.

- **[FIXED] Local-agent post-round registry hydration** (`bank-node/local-agent/src/main.py`):
  After the round graph completes and `agent_status["last_metrics"]` is set from local GNN output, added a best-effort `GET /models/latest` call to the model registry. If the registry now holds a row with real metrics (because the coordinator just registered one), `agent_status["last_metrics"]` and `agent_status["last_model_version"]` are overwritten with the canonical globally-aggregated values. Failures are caught silently so the round response is never blocked.

- **[FIXED] Model registry orphan import ordering** (`central-coordinator/model-registry/src/main.py`):
  Before importing orphaned `.pt` files, the sync function now computes `oldest_db_timestamp = min(created_at for all existing rows)`. Any orphan file is registered with `created_at = min(file_mtime, oldest_db_timestamp - 1 second)`. This guarantees orphaned, empty-metrics entries never sort ahead of coordinator-registered models in `ORDER BY created_at DESC`.

## Verification

- Trigger a federated round via `POST /rounds/start` on the coordinator.
- After round completes, call `GET /agent/status` on the local agent — `last_metrics` should now contain `accuracy` and `loss` from the global aggregation.
- Call `GET /models/latest` on the model registry — `metrics` should be non-empty.
- The dashboard "Model Accuracy" stat card should now display the percentage instead of N/A.
- In coordinator logs, confirm `"Successfully registered aggregated model with version_id=..."` appears.

