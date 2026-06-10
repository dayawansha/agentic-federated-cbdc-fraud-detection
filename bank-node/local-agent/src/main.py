import logging
import os
import sys
import asyncio
from fastapi import FastAPI
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- LangGraph State Definition ---
class LocalAgentState(TypedDict):
    agent_id: str
    round_id: str
    data_ready: bool
    training_complete: bool
    privacy_applied: bool
    metrics: Dict[str, float]
    current_step: str

# --- Node Functions ---
async def check_data_availability(state: LocalAgentState):
    logger.info(f"Checking data availability for round {state['round_id']}")
    # Logic to check Transaction Graph and Shards
    state['data_ready'] = True
    state['current_step'] = "training_triggered"
    return state

async def run_local_training(state: LocalAgentState):
    logger.info("Triggering Local GNN Training...")
    # Call Local GNN Service
    await asyncio.sleep(1) 
    state['training_complete'] = True
    state['current_step'] = "apply_privacy"
    return state

async def apply_privacy_measures(state: LocalAgentState):
    logger.info("Applying Differential Privacy and Encryption...")
    # Call Privacy Layer Service
    state['privacy_applied'] = True
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
