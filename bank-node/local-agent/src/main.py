import logging
import os
import sys
import asyncio
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
            response = await client.post(f"{LOCAL_GNN_URL}/train")
            if response.status_code == 200:
                logger.info("Local training successful")
                state['training_complete'] = True
                # Placeholder for weights (in real scenario, fetch from GNN service)
                state['weights'] = b"model_weights_data"
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
                json={"weights": state.get('weights', b"").hex(), "noise_multiplier": 0.01}
            )
            if dp_response.status_code == 200:
                state['weights'] = bytes.fromhex(dp_response.json()["weights"])
                state['privacy_applied'] = True
                logger.info("Privacy measures applied successfully")
            else:
                logger.error(f"Privacy application failed: {dp_response.text}")
        except Exception as e:
            logger.error(f"Error calling Privacy service: {e}")

    state['current_step'] = "submitting_update"
    return state

# --- Graph Construction ---
workflow = StateGraph(LocalAgentState)
workflow.add_node("check_data", check_data_availability)
workflow.add_node("train", run_local_training)
workflow.add_node("privacy", apply_privacy_measures)

workflow.set_entry_point("check_data")
workflow.add_edge("check_data", "train")
workflow.add_edge("train", "privacy")
workflow.add_edge("privacy", END)

app_graph = workflow.compile()

# --- FastAPI Setup ---
app = FastAPI(title="Local Agent Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/agent/round/start")
async def start_local_round(round_id: str, agent_id: str):
    logger.info(f"Local Agent {agent_id} starting round {round_id}")
    initial_state: LocalAgentState = {
        "agent_id": agent_id,
        "round_id": round_id,
        "data_ready": False,
        "training_complete": False,
        "privacy_applied": False,
        "metrics": {},
        "current_step": "init"
    }
    
    final_state = await app_graph.ainvoke(initial_state)
    return {"status": "success", "final_state": final_state}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
