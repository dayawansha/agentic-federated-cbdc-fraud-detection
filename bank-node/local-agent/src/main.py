import logging
import os
import sys
import asyncio
import base64
from datetime import datetime, timezone
from fastapi import FastAPI
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END
import httpx

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs from environment variables
LOCAL_GNN_URL = os.getenv("LOCAL_GNN_URL", "http://localhost:9002")
PRIVACY_LAYER_URL = os.getenv("PRIVACY_LAYER_URL", "http://localhost:9003")
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8001")

# --- LangGraph State Definition ---
class LocalAgentState(TypedDict):
    agent_id: str
    round_id: str
    data_ready: bool
    training_complete: bool
    privacy_applied: bool
    weights: bytes
    encrypted_weights: bytes
    sample_size: int
    metrics: Dict[str, float]
    current_step: str

# --- Node Functions ---
async def check_data_availability(state: LocalAgentState):
    logger.info(f"Checking data availability for round {state['round_id']}")
    # In production, check if shard file exists or Neo4j has data
    state['data_ready'] = True
    state['current_step'] = "training_triggered"
    return state

async def run_local_training(state: LocalAgentState):
    logger.info("Triggering Local GNN Training...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LOCAL_GNN_URL}/train",
                json={"round_id": state["round_id"]},
                timeout=180.0,
            )
            if response.status_code == 200:
                payload = response.json()
                state["weights"] = base64.b64decode(payload["weights"])
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
                json={"weights": base64.b64encode(state.get("weights", b"")).decode("ascii"), "noise_multiplier": 0.01},
                timeout=180.0,
            )
            if dp_response.status_code == 200:
                dp_payload = dp_response.json()
                state["weights"] = base64.b64decode(dp_payload["weights"])
                state['privacy_applied'] = True
                logger.info("Privacy measures applied successfully")
            else:
                logger.error(f"Privacy application failed: {dp_response.text}")

            encrypt_response = await client.post(
                f"{PRIVACY_LAYER_URL}/privacy/encrypt",
                json={"data": base64.b64encode(state.get("weights", b"")).decode("ascii")},
                timeout=180.0,
            )
            if encrypt_response.status_code == 200:
                encrypt_payload = encrypt_response.json()
                state["encrypted_weights"] = base64.b64decode(encrypt_payload["encrypted_data"])
            else:
                logger.error(f"Encryption failed: {encrypt_response.text}")
        except Exception as e:
            logger.error(f"Error calling Privacy service: {e}")

    state['current_step'] = "submitting_update"
    return state

async def submit_update_to_coordinator(state: LocalAgentState):
    logger.info("Submitting model update to Coordinator...")
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "agent_id": state["agent_id"],
                "round_id": state["round_id"],
                "weights": base64.b64encode(state.get("weights", b"")).decode("ascii"),
                "sample_size": int(state.get("sample_size", 0)),
                "metrics": state.get("metrics", {}) or {},
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            resp = await client.post(f"{COORDINATOR_URL}/updates/submit", json=payload, timeout=60.0)
            if resp.status_code != 200:
                logger.error(f"Coordinator update submission failed: {resp.text}")
        except Exception as e:
            logger.error(f"Error submitting update to Coordinator: {e}")
    state["current_step"] = "done"
    return state

# --- Graph Construction ---
workflow = StateGraph(LocalAgentState)
workflow.add_node("check_data", check_data_availability)
workflow.add_node("train", run_local_training)
workflow.add_node("privacy", apply_privacy_measures)
workflow.add_node("submit_update", submit_update_to_coordinator)

workflow.set_entry_point("check_data")
workflow.add_edge("check_data", "train")
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
}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/agent/status")
async def get_status():
    return agent_status

@app.post("/agent/round/start")
async def start_local_round(round_id: str, agent_id: str):
    logger.info(f"Local Agent {agent_id} starting round {round_id}")
    initial_state: LocalAgentState = {
        "agent_id": agent_id,
        "round_id": round_id,
        "data_ready": False,
        "training_complete": False,
        "privacy_applied": False,
        "weights": b"",
        "encrypted_weights": b"",
        "sample_size": 0,
        "metrics": {},
        "current_step": "init"
    }
    
    final_state = await app_graph.ainvoke(initial_state)
    agent_status["agent_id"] = agent_id
    agent_status["last_round_id"] = round_id
    agent_status["last_update_at"] = datetime.now(timezone.utc).isoformat()
    agent_status["last_metrics"] = final_state.get("metrics", {}) if isinstance(final_state, dict) else {}
    return {"status": "success", "final_state": final_state}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
