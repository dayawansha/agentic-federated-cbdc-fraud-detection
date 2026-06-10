import logging
import os
from fastapi import FastAPI
from typing import Dict, List, TypedDict, Annotated
from langgraph.graph import StateGraph, END
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- LangGraph State Definition ---
class AgentState(TypedDict):
    round_id: str
    active_agents: List[str]
    updates_received: List[str]
    aggregation_complete: bool
    metrics: Dict[str, float]
    current_step: str

# --- Node Functions ---
async def select_agents(state: AgentState):
    logger.info(f"Selecting agents for round {state['round_id']}")
    # Logic to select agents based on health and availability
    state['active_agents'] = ["bank-1", "bank-2", "bank-3"]
    state['current_step'] = "training_triggered"
    return state

async def trigger_training(state: AgentState):
    logger.info(f"Triggering training for agents: {state['active_agents']}")
    # gRPC/Kafka calls to local agents
    await asyncio.sleep(1) 
    state['current_step'] = "waiting_for_updates"
    return state

async def aggregate_results(state: AgentState):
    logger.info("Aggregating results via Secure Aggregator")
    # Call Secure Aggregator service
    state['aggregation_complete'] = True
    state['current_step'] = "round_complete"
    return state

# --- Graph Construction ---
workflow = StateGraph(AgentState)
workflow.add_node("select_agents", select_agents)
workflow.add_node("trigger_training", trigger_training)
workflow.add_node("aggregate_results", aggregate_results)

workflow.set_entry_point("select_agents")
workflow.add_edge("select_agents", "trigger_training")
workflow.add_edge("trigger_training", "aggregate_results")
workflow.add_edge("aggregate_results", END)

app_graph = workflow.compile()

# --- FastAPI Setup ---
app = FastAPI(title="Agentic Coordinator Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/rounds/start")
async def start_round(round_id: str):
    logger.info(f"Starting federated round: {round_id}")
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
