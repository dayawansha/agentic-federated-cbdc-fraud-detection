import logging
import os
import base64
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
import asyncio
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configuration
LOCAL_AGENT_URLS = os.getenv("LOCAL_AGENT_URLS", "http://localhost:9001").split(",")
SECURE_AGGREGATOR_URL = os.getenv("SECURE_AGGREGATOR_URL", "http://localhost:8002")
POLICY_MANAGER_URL = os.getenv("POLICY_MANAGER_URL", "http://localhost:8003")
MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://localhost:8004")
ROUND_WAIT_SECONDS = float(os.getenv("ROUND_WAIT_SECONDS", "300"))

class UpdateSubmission(BaseModel):
    agent_id: str
    round_id: str
    weights: bytes
    sample_size: int
    metrics: Dict[str, float] = {}
    client_timestamp: Optional[str] = None

class SubmissionAck(BaseModel):
    accepted: bool
    message: str

round_updates: Dict[str, List[UpdateSubmission]] = {}
round_expected_agents: Dict[str, List[str]] = {}
round_events: Dict[str, asyncio.Event] = {}

# --- LangGraph State Definition ---
class AgentState(TypedDict):
    round_id: str
    active_agents: List[str]
    updates_received: List[UpdateSubmission]
    aggregation_complete: bool
    metrics: Dict[str, float]
    current_step: str

# --- Node Functions ---
async def select_agents(state: AgentState):
    logger.info(f"Selecting agents for round {state['round_id']}")
    # Logic to select agents based on health and availability
    # For now, use all configured agents
    state['active_agents'] = LOCAL_AGENT_URLS
    state['current_step'] = "training_triggered"
    return state

async def trigger_training(state: AgentState):
    logger.info(f"Triggering training for agents: {state['active_agents']}")
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for agent_url in state['active_agents']:
            # Call each local agent to start its local round
            tasks.append(client.post(
                f"{agent_url}/agent/round/start",
                params={"round_id": state['round_id'], "agent_id": agent_url}
            ))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.error(f"Error triggering agent {state['active_agents'][i]}: {resp}")
            elif resp.status_code == 200:
                logger.info(f"Successfully triggered agent {state['active_agents'][i]}")
            else:
                logger.error(f"Agent {state['active_agents'][i]} failed: {resp.text}")

    state['current_step'] = "waiting_for_updates"
    return state

async def wait_for_updates(state: AgentState):
    round_id = state["round_id"]
    expected = round_expected_agents.get(round_id, [])
    event = round_events.get(round_id)
    if event is None:
        event = asyncio.Event()
        round_events[round_id] = event

    try:
        await asyncio.wait_for(event.wait(), timeout=ROUND_WAIT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning(f"Timed out waiting for updates for round {round_id}")

    received = round_updates.get(round_id, [])
    state["updates_received"] = received
    state["current_step"] = "aggregating"
    return state

async def aggregate_results(state: AgentState):
    logger.info("Aggregating results via Secure Aggregator")
    round_id = state["round_id"]
    updates = state.get("updates_received", [])
    if not updates:
        state["aggregation_complete"] = False
        state["current_step"] = "round_complete"
        return state

    async with httpx.AsyncClient() as client:
        agg_payload = {
            "round_id": round_id,
            "updates": [
                {
                    "agent_id": u.agent_id,
                    "weights": base64.b64encode(u.weights).decode("ascii"),
                    "sample_size": u.sample_size,
                    "metrics": u.metrics,
                }
                for u in updates
            ],
            "strategy": "FedAvg",
            "noise_multiplier": 0.0,
        }
        agg_resp = await client.post(f"{SECURE_AGGREGATOR_URL}/aggregate", json=agg_payload, timeout=180.0)
        if agg_resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Aggregation failed: {agg_resp.text}")

        agg_data = agg_resp.json()
        state["aggregation_complete"] = bool(agg_data.get("success", False))
        state["metrics"] = agg_data.get("global_metrics", {}) or {}

        try:
            await client.post(
                f"{MODEL_REGISTRY_URL}/models/register",
                json={
                    "metrics": state["metrics"],
                    "artifact_path": "",
                    "is_global": True,
                    "weights": agg_data.get("aggregated_weights"),
                },
                timeout=60.0,
            )
        except Exception as e:
            logger.warning(f"Model registry registration failed: {e}")

        for u in updates:
            try:
                await client.post(
                    f"{POLICY_MANAGER_URL}/policies/budget/update",
                    json={"agent_id": u.agent_id, "epsilon_spent": 0.1, "delta_spent": 0.0},
                    timeout=30.0,
                )
            except Exception as e:
                logger.warning(f"Policy budget update failed for {u.agent_id}: {e}")

    state["current_step"] = "round_complete"
    return state

# --- Graph Construction ---
workflow = StateGraph(AgentState)
workflow.add_node("select_agents", select_agents)
workflow.add_node("trigger_training", trigger_training)
workflow.add_node("wait_for_updates", wait_for_updates)
workflow.add_node("aggregate_results", aggregate_results)

workflow.set_entry_point("select_agents")
workflow.add_edge("select_agents", "trigger_training")
workflow.add_edge("trigger_training", "wait_for_updates")
workflow.add_edge("wait_for_updates", "aggregate_results")
workflow.add_edge("aggregate_results", END)

app_graph = workflow.compile()

# --- FastAPI Setup ---
app = FastAPI(title="Agentic Coordinator Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/updates/submit", response_model=SubmissionAck)
async def submit_update(update: UpdateSubmission):
    updates = round_updates.setdefault(update.round_id, [])
    updates.append(update)

    expected = round_expected_agents.get(update.round_id, [])
    if expected and len({u.agent_id for u in updates}) >= len(expected):
        event = round_events.get(update.round_id)
        if event is None:
            event = asyncio.Event()
            round_events[update.round_id] = event
        event.set()
        return SubmissionAck(accepted=True, message="Update received (round complete)")

    return SubmissionAck(accepted=True, message="Update received")

@app.post("/rounds/start")
async def start_round(round_id: str):
    logger.info(f"Starting federated round: {round_id}")
    round_updates[round_id] = []
    round_expected_agents[round_id] = LOCAL_AGENT_URLS
    round_events[round_id] = asyncio.Event()
    initial_state: AgentState = {
        "round_id": round_id,
        "active_agents": [],
        "updates_received": [],
        "aggregation_complete": False,
        "metrics": {},
        "current_step": "init"
    }
    
    # Run the agentic workflow
    final_state = await app_graph.ainvoke(initial_state)
    return {"status": "success", "final_state": final_state}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
