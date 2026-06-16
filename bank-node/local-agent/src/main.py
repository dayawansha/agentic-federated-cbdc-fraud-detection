import logging
import os
import sys
import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
import httpx

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.schemas.models import (
    WeightNegotiationRequest,
    WeightNegotiationResponse,
    FraudPatternProposal,
    ConsensusVote,
    WeightNegotiationItem,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs from environment variables
LOCAL_GNN_URL = os.getenv("LOCAL_GNN_URL", "http://localhost:9002")
PRIVACY_LAYER_URL = os.getenv("PRIVACY_LAYER_URL", "http://localhost:9003")
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8001")
MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://localhost:8004")
DP_NOISE_MULTIPLIER = float(os.getenv("DP_NOISE_MULTIPLIER", "0.01"))
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_FRAUD_ALERTS_TOPIC = os.getenv("KAFKA_FRAUD_ALERTS_TOPIC", "fraud.alerts")
AUTO_ALERT_ON_ROUND_COMPLETE = os.getenv("AUTO_ALERT_ON_ROUND_COMPLETE", "true").strip().lower() not in {"0", "false", "no", "off"}
ALERT_CONFIDENCE_THRESHOLD = float(os.getenv("ALERT_CONFIDENCE_THRESHOLD", "0.9"))
ALERT_PUBLISH_LIMIT = int(os.getenv("ALERT_PUBLISH_LIMIT", "5"))

# --- LangGraph State Definition ---
class LocalAgentState(TypedDict):
    agent_id: str
    round_id: str
    data_ready: bool
    global_model_loaded: bool
    training_complete: bool
    privacy_applied: bool
    raw_weights: bytes
    protected_weights: bytes
    masked_weights: bytes
    encrypted_weights: bytes
    encrypted_mask_share: str
    protected_payload_sha256: str
    encrypted_payload_sha256: str
    sample_size: int
    metrics: Dict[str, float]
    global_weights: bytes
    model_version_id: Optional[str]
    noise_multiplier: float
    current_step: str


class AgentInferencePrediction(BaseModel):
    tx_id: int
    predicted_class: str
    predicted_label: int
    confidence: float
    illicit_probability: float
    licit_probability: float
    unknown_probability: float
    known_label: Optional[str] = None


class AgentInferenceResponse(BaseModel):
    status: str
    agent_id: str
    generated_at: str
    prediction_count: int
    predictions: List[AgentInferencePrediction]

# --- Node Functions ---
async def check_data_availability(state: LocalAgentState):
    logger.info(f"Checking data availability for round {state['round_id']}")
    # In production, check if shard file exists or Neo4j has data
    state['data_ready'] = True
    state['current_step'] = "global_model_fetch"
    return state

async def fetch_latest_global_model(state: LocalAgentState):
    logger.info("Fetching latest global model from Model Registry...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MODEL_REGISTRY_URL}/models/latest/weights", timeout=60.0)
            if response.status_code == 404:
                logger.info("No global model found yet, proceeding with local initialization")
                state["global_weights"] = b""
                state["model_version_id"] = None
                state["global_model_loaded"] = False
            else:
                response.raise_for_status()
                payload = response.json()
                state["global_weights"] = base64.b64decode(payload["weights"])
                state["model_version_id"] = payload.get("version_id")
                state["global_model_loaded"] = True
        except httpx.HTTPStatusError as exc:
            logger.error("Model Registry returned an error while fetching latest model: %s", exc.response.text)
            raise HTTPException(status_code=502, detail="Model Registry latest model request failed") from exc
        except Exception as exc:
            logger.error("Error fetching latest global model: %s", exc)
            state["global_weights"] = b""
            state["model_version_id"] = None
            state["global_model_loaded"] = False

    state["current_step"] = "training_triggered"
    return state

async def run_local_training(state: LocalAgentState):
    logger.info("Triggering Local GNN Training...")
    async with httpx.AsyncClient() as client:
        try:
            payload = {"round_id": state["round_id"]}
            if state.get("global_weights"):
                payload["global_weights"] = base64.b64encode(state["global_weights"]).decode("ascii")
            response = await client.post(
                f"{LOCAL_GNN_URL}/train",
                json=payload,
                timeout=180.0,
            )
            if response.status_code == 200:
                payload = response.json()
                state["raw_weights"] = base64.b64decode(payload["weights"])
                state["sample_size"] = int(payload.get("sample_size", 0))
                state["metrics"] = payload.get("metrics", {}) or {}
                state['training_complete'] = True
                logger.info("Local training successful")
            else:
                logger.error(f"Training failed: {response.text}")
        except Exception as e:
            logger.error(f"Error calling GNN service: {e}")
            
    state['current_step'] = "apply_privacy"
    return state

async def apply_privacy_measures(state: LocalAgentState):
    logger.info("Applying Differential Privacy and Encryption...")
    async with httpx.AsyncClient() as client:
        try:
            # Call Privacy Layer to apply DP
            dp_response = await client.post(
                f"{PRIVACY_LAYER_URL}/privacy/apply-dp",
                json={
                    "weights": base64.b64encode(state.get("raw_weights", b"")).decode("ascii"),
                    "noise_multiplier": float(state.get("noise_multiplier", DP_NOISE_MULTIPLIER)),
                },
                timeout=180.0,
            )
            if dp_response.status_code == 200:
                dp_payload = dp_response.json()
                state["protected_weights"] = base64.b64decode(dp_payload["weights"])
                state['privacy_applied'] = True
                logger.info("Privacy measures applied successfully")
            else:
                logger.error(f"Privacy application failed: {dp_response.text}")

            secure_update_response = await client.post(
                f"{PRIVACY_LAYER_URL}/privacy/prepare-secure-update",
                json={"weights": base64.b64encode(state.get("protected_weights", b"")).decode("ascii")},
                timeout=180.0,
            )
            if secure_update_response.status_code == 200:
                secure_payload = secure_update_response.json()
                masked_weights_b64 = secure_payload.get("masked_weights", "")
                state["masked_weights"] = base64.b64decode(masked_weights_b64) if masked_weights_b64 else state.get("protected_weights", b"")
                state["encrypted_mask_share"] = secure_payload.get("encrypted_mask_share", "")
            else:
                logger.error(f"Secure aggregation preparation failed: {secure_update_response.text}")
                state["masked_weights"] = state.get("protected_weights", b"")
                state["encrypted_mask_share"] = ""

            encrypt_response = await client.post(
                f"{PRIVACY_LAYER_URL}/privacy/encrypt",
                json={"data": base64.b64encode(state.get("masked_weights", b"")).decode("ascii")},
                timeout=180.0,
            )
            if encrypt_response.status_code == 200:
                encrypt_payload = encrypt_response.json()
                state["encrypted_weights"] = base64.b64decode(encrypt_payload["encrypted_data"])
            else:
                logger.error(f"Encryption failed: {encrypt_response.text}")

            if state.get("protected_weights"):
                protected_weights_b64 = base64.b64encode(state.get("masked_weights", b"")).decode("ascii")
                encrypted_weights_b64 = base64.b64encode(state.get("encrypted_weights", b"")).decode("ascii")
                state["protected_payload_sha256"] = hashlib.sha256(protected_weights_b64.encode("ascii")).hexdigest()
                state["encrypted_payload_sha256"] = hashlib.sha256(encrypted_weights_b64.encode("ascii")).hexdigest() if encrypted_weights_b64 else ""

                evaluation_response = await client.post(
                    f"{PRIVACY_LAYER_URL}/privacy/evaluate",
                    json={
                        "raw_weights": base64.b64encode(state.get("raw_weights", b"")).decode("ascii"),
                        "protected_weights": protected_weights_b64,
                        "encrypted_data": encrypted_weights_b64,
                        "noise_multiplier": float(state.get("noise_multiplier", DP_NOISE_MULTIPLIER)),
                    },
                    timeout=180.0,
                )
                if evaluation_response.status_code == 200:
                    evaluation = evaluation_response.json()
                    state["metrics"].update(
                        {
                            "privacy_byte_change_ratio": float(evaluation.get("byte_change_ratio", 0.0)),
                            "privacy_size_overhead_ratio": float(evaluation.get("size_overhead_ratio", 0.0)),
                            "privacy_tensor_l2_delta": float(evaluation.get("tensor_l2_delta", 0.0)),
                            "privacy_tensor_change_ratio": float(evaluation.get("tensor_change_ratio", 0.0)),
                        }
                    )
                else:
                    logger.error("Privacy evaluation failed: %s", evaluation_response.text)
        except Exception as e:
            logger.error(f"Error calling Privacy service: {e}")

    state['current_step'] = "submitting_update"
    return state

async def submit_update_to_coordinator(state: LocalAgentState):
    logger.info("Submitting model update to Coordinator...")
    async with httpx.AsyncClient() as client:
        try:
            metrics = {
                key: float(value)
                for key, value in (state.get("metrics", {}) or {}).items()
                if isinstance(value, (int, float)) and value is not None
            }
            payload = {
                "agent_id": state["agent_id"],
                "round_id": state["round_id"],
                "weights": base64.b64encode(state.get("masked_weights", b"")).decode("ascii"),
                "encrypted_weights": base64.b64encode(state.get("encrypted_weights", b"")).decode("ascii"),
                "encrypted_mask_share": state.get("encrypted_mask_share", ""),
                "protected_payload_sha256": state.get("protected_payload_sha256"),
                "encrypted_payload_sha256": state.get("encrypted_payload_sha256"),
                "sample_size": int(state.get("sample_size", 0)),
                "metrics": metrics,
                "privacy_applied": bool(state.get("privacy_applied", False)),
                "encryption_applied": bool(state.get("encrypted_weights")),
                "noise_multiplier": float(state.get("noise_multiplier", DP_NOISE_MULTIPLIER)),
                "model_version_id": state.get("model_version_id"),
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            resp = await client.post(f"{COORDINATOR_URL}/updates/submit", json=payload, timeout=60.0)
            if resp.status_code != 200:
                logger.error(f"Coordinator update submission failed: {resp.text}")
        except Exception as e:
            logger.error(f"Error submitting update to Coordinator: {e}")

    if AUTO_ALERT_ON_ROUND_COMPLETE:
        try:
            inference_response = await fetch_inference_predictions(limit=ALERT_PUBLISH_LIMIT)
            publish_inference_alerts(state["agent_id"], inference_response.predictions)
        except Exception as exc:
            logger.warning("Inference-driven alert publication skipped: %s", exc)

    state["current_step"] = "done"
    return state

# --- Graph Construction ---
workflow = StateGraph(LocalAgentState)
workflow.add_node("check_data", check_data_availability)
workflow.add_node("fetch_global_model", fetch_latest_global_model)
workflow.add_node("train", run_local_training)
workflow.add_node("privacy", apply_privacy_measures)
workflow.add_node("submit_update", submit_update_to_coordinator)

workflow.set_entry_point("check_data")
workflow.add_edge("check_data", "fetch_global_model")
workflow.add_edge("fetch_global_model", "train")
workflow.add_edge("train", "privacy")
workflow.add_edge("privacy", "submit_update")
workflow.add_edge("submit_update", END)

app_graph = workflow.compile()

# --- FastAPI Setup ---
app = FastAPI(title="Local Agent Service")

agent_status: Dict[str, object] = {
    "agent_id": os.getenv("AGENT_ID", "local-agent"),
    "last_round_id": None,
    "last_update_at": None,
    "last_metrics": {},
    "last_model_version": None,
    "last_alert_publish_at": None,
    "last_alert_publish_count": 0,
    "last_inference_at": None,
    "last_inference_summary": {},
}

def _severity_for_confidence(confidence: float) -> str:
    if confidence >= 0.98:
        return "critical"
    if confidence >= 0.93:
        return "high"
    if confidence >= ALERT_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"

def _build_alerts_from_predictions(agent_id: str, predictions: List[AgentInferencePrediction]) -> List[Dict[str, object]]:
    alerts: List[Dict[str, object]] = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for prediction in predictions:
        if str(prediction.predicted_class).lower() != "illicit":
            continue
        confidence = float(prediction.confidence)
        if confidence < ALERT_CONFIDENCE_THRESHOLD:
            continue
        alerts.append(
            {
                "alert_id": f"{agent_id}-{prediction.tx_id}-{uuid.uuid4().hex[:8]}",
                "txId": int(prediction.tx_id),
                "timestamp": timestamp,
                "severity": _severity_for_confidence(confidence),
                "confidence_score": confidence,
                "reason": f"Local GNN predicted illicit activity with confidence {confidence:.4f}",
                "status": "open",
                "source": "local-agent-inference",
                "agent_id": agent_id,
            }
        )
        if len(alerts) >= ALERT_PUBLISH_LIMIT:
            break
    return alerts

def publish_inference_alerts(agent_id: str, predictions: List[AgentInferencePrediction]) -> int:
    alerts = _build_alerts_from_predictions(agent_id, predictions)
    if not alerts:
        return 0

    try:
        from confluent_kafka import Producer
    except Exception as exc:
        logger.warning("Kafka producer unavailable for inference alert publishing: %s", exc)
        return 0

    producer = Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": f"{agent_id}-inference-alert-publisher",
        }
    )
    for alert in alerts:
        producer.produce(
            KAFKA_FRAUD_ALERTS_TOPIC,
            key=str(alert["alert_id"]),
            value=json.dumps(alert),
        )
        producer.poll(0)
    producer.flush(5.0)

    published_at = datetime.now(timezone.utc).isoformat()
    agent_status["last_alert_publish_at"] = published_at
    agent_status["last_alert_publish_count"] = len(alerts)
    logger.info("Published %s inference-driven alert(s) for agent %s", len(alerts), agent_id)
    return len(alerts)


async def fetch_inference_predictions(limit: int = 10, tx_ids: Optional[List[int]] = None) -> AgentInferenceResponse:
    payload: Dict[str, object] = {"limit": max(1, min(int(limit), 50))}
    if tx_ids:
        payload["tx_ids"] = [int(tx_id) for tx_id in tx_ids]

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{LOCAL_GNN_URL}/infer", json=payload, timeout=180.0)
            response.raise_for_status()
            inference_payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Local GNN inference request failed: %s", exc.response.text)
            raise HTTPException(status_code=502, detail="Local GNN inference request failed") from exc
        except Exception as exc:
            logger.error("Error calling Local GNN inference: %s", exc)
            raise HTTPException(status_code=502, detail="Local GNN inference service unreachable") from exc

    predictions = [
        AgentInferencePrediction(**prediction)
        for prediction in (inference_payload.get("predictions") or [])
    ]
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "prediction_count": len(predictions),
        "high_risk_count": sum(1 for prediction in predictions if prediction.predicted_class == "illicit"),
        "top_tx_id": predictions[0].tx_id if predictions else None,
        "top_confidence": predictions[0].confidence if predictions else None,
    }
    agent_status["last_inference_at"] = generated_at
    agent_status["last_inference_summary"] = summary

    return AgentInferenceResponse(
        status="success",
        agent_id=str(agent_status["agent_id"]),
        generated_at=generated_at,
        prediction_count=len(predictions),
        predictions=predictions,
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/agent/status")
async def get_status():
    return agent_status


@app.get("/agent/inference", response_model=AgentInferenceResponse)
async def get_agent_inference(limit: int = 10):
    return await fetch_inference_predictions(limit=limit)

@app.post("/agent/round/start")
async def start_local_round(round_id: str, agent_id: str):
    logger.info(f"Local Agent {agent_id} starting round {round_id}")
    initial_state: LocalAgentState = {
        "agent_id": agent_id,
        "round_id": round_id,
        "data_ready": False,
        "global_model_loaded": False,
        "training_complete": False,
        "privacy_applied": False,
        "raw_weights": b"",
        "protected_weights": b"",
        "masked_weights": b"",
        "encrypted_weights": b"",
        "encrypted_mask_share": "",
        "protected_payload_sha256": "",
        "encrypted_payload_sha256": "",
        "sample_size": 0,
        "metrics": {},
        "global_weights": b"",
        "model_version_id": None,
        "noise_multiplier": DP_NOISE_MULTIPLIER,
        "current_step": "init"
    }
    
    final_state = await app_graph.ainvoke(initial_state)
    agent_status["agent_id"] = agent_id
    agent_status["last_round_id"] = round_id
    agent_status["last_update_at"] = datetime.now(timezone.utc).isoformat()
    agent_status["last_metrics"] = final_state.get("metrics", {}) if isinstance(final_state, dict) else {}
    agent_status["last_model_version"] = final_state.get("model_version_id") if isinstance(final_state, dict) else None
    return {
        "status": "success",
        "final_state": {
            "agent_id": final_state.get("agent_id"),
            "round_id": final_state.get("round_id"),
            "current_step": final_state.get("current_step"),
            "data_ready": final_state.get("data_ready"),
            "global_model_loaded": final_state.get("global_model_loaded"),
            "training_complete": final_state.get("training_complete"),
            "privacy_applied": final_state.get("privacy_applied"),
            "sample_size": final_state.get("sample_size"),
            "model_version_id": final_state.get("model_version_id"),
            "metrics": final_state.get("metrics", {}),
        },
    }

@app.post("/agent/negotiate/propose-weights", response_model=WeightNegotiationResponse)
async def propose_weights(request: WeightNegotiationRequest):
    logger.info(f"Local Agent negotiating weights for round {request.round_id}")
    proposed_weights = {}
    scores = {}
    for agent in request.agents:
        f1 = agent.metrics.get("f1_score", 0.8)
        if f1 is None:
            f1 = 0.8
        f1 = max(0.01, min(1.0, float(f1)))
        
        reliability = agent.reliability_score
        if reliability is None:
            reliability = 1.0
        reliability = max(0.1, min(1.0, float(reliability)))
        
        sample_size = agent.sample_size
        if sample_size is None or sample_size < 1:
            sample_size = 1
            
        scores[agent.agent_id] = float(sample_size) * f1 * reliability

    total_score = sum(scores.values())
    for agent_id, score in scores.items():
        proposed_weights[agent_id] = score / total_score if total_score > 0 else 1.0 / len(request.agents)

    my_id = str(agent_status.get("agent_id", "local-agent"))
    return WeightNegotiationResponse(agent_id=my_id, proposed_weights=proposed_weights)


@app.post("/agent/consensus/evaluate-pattern", response_model=ConsensusVote)
async def evaluate_pattern(proposal: FraudPatternProposal):
    logger.info(f"Local Agent evaluating fraud pattern proposal {proposal.proposal_id} ({proposal.pattern_name})")
    vote = "APPROVE"
    reason = "All pattern indicators are within valid statistical and structural ranges"
    
    for key, val in proposal.feature_indicators.items():
        val = float(val)
        if "ratio" in key or "score" in key or "probability" in key or "percent" in key:
            if val < 0.0 or val > 1.0:
                vote = "REJECT"
                reason = f"Indicator {key} value {val} is out of bounds [0, 1]"
                break
        if "threshold" in key or "velocity" in key or "count" in key:
            if val < 0.0:
                vote = "REJECT"
                reason = f"Indicator {key} value {val} cannot be negative"
                break
                
    my_id = str(agent_status.get("agent_id", "local-agent"))
    return ConsensusVote(agent_id=my_id, proposal_id=proposal.proposal_id, vote=vote, reason=reason)


@app.post("/agent/consensus/propose-pattern")
async def propose_pattern(proposal_data: dict):
    proposal_id = f"prop-{uuid.uuid4().hex[:8]}"
    my_id = str(agent_status.get("agent_id", "local-agent"))
    proposal = FraudPatternProposal(
        proposal_id=proposal_id,
        proposer_id=my_id,
        pattern_name=proposal_data.get("pattern_name", "Unknown Pattern"),
        feature_indicators=proposal_data.get("feature_indicators", {}),
        rationale=proposal_data.get("rationale", "No rationale provided")
    )
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{COORDINATOR_URL}/consensus/propose-fraud-pattern", json=proposal.model_dump(mode="json"), timeout=60.0)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
        except Exception as e:
            logger.error(f"Failed to propose pattern to coordinator: {e}")
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
