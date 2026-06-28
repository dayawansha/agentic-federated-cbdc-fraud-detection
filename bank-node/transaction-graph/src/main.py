"""
================================================================================
TRANSACTION GRAPH SERVICE - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Transaction Graph service as the bank's "Interactive Ledger Map" or
"Financial Social Network."

If you list transactions in a traditional spreadsheet, it is very hard to see circular
payments or money laundering pathways. But this service stores payments in a graph
database (Neo4j) where:
- Circles (Nodes): Accounts and transactions.
- Lines (Edges): The flow of money (who sent what to whom).

Its core business roles are:
1. LEDGER RECORDING: Receives new transaction details and adds them to the Neo4j graph.
2. CHANGE DATA CAPTURE (CDC) STREAMING: Whenever a new transaction is recorded, it immediately
   publishes an event to a Kafka stream (`transactions.events`). This alerts other services
   (like the Alerting service) so they can verify the transaction in real-time.
3. NETWORK ANALYTICS: Calculates graph features (e.g. "centrality" — how much of a hub an account
   is, or "temporal metrics" — how fast money is entering and leaving) and exports these
   features to train the GNN Model.
================================================================================
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel, Field
from typing import Optional, Dict

from database import db
from services.graph_service import graph_service
from services.cdc_service import cdc_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting Transaction Graph Service...")
    try:
        db.connect()
    except Exception as e:
        logger.warning(f"Neo4j unavailable at startup, continuing without an active DB connection: {e}")
    try:
        yield
    finally:
        logger.info("Shutting down Transaction Graph Service...")
        db.close()

app = FastAPI(title="Transaction Graph Service", lifespan=lifespan)

class TransactionSchema(BaseModel):
    """
    BUSINESS REASON: Defines the standard structure of a CBDC payment transaction.
    - 'transaction_id': Unique identifier of the payment.
    - 'source_account': Who sent the funds.
    - 'target_account': Who received the funds.
    - 'amount': The amount transferred.
    - 'asset_type': The currency unit (defaults to CBDC).
    """
    transaction_id: str
    source_account: str
    target_account: str
    amount: float
    asset_type: Optional[str] = "CBDC"
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict)

@app.get("/health")
async def health_check():
    """
    BUSINESS PURPOSE / REASON: Checked by orchestrators and local agent to ensure the ledger graph service is online.
    """
    return {"status": "healthy"}

@app.post("/transactions")
async def add_transaction(tx: TransactionSchema):
    """
    BUSINESS PURPOSE / REASON: Called when a new transaction is executed on the core banking system.
    It writes the transaction node and edges to the Neo4j ledger database, and publishes a change
    event (CDC) to Kafka so alerting microservices can run checks immediately.
    """
    try:
        tx_dict = tx.model_dump()
        result = graph_service.add_transaction(tx_dict)
        # Publish event to Kafka for CDC
        cdc_service.publish_transaction(tx_dict)
        return {"success": True, "transaction_id": result}
    except Exception as e:
        logger.error(f"Error in add_transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts")
async def get_all_accounts(limit: int = 100):
    """
    BUSINESS PURPOSE / REASON: Used by the dashboard to fetch a list of accounts that have active
    payment histories in this node.
    """
    try:
        accounts = graph_service.get_all_accounts(limit=limit)
        return {
            "accounts": accounts,
            "count": len(accounts),
        }
    except Exception as e:
        logger.error(f"Error in get_all_accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts/{account_id}/features")
async def get_account_features(account_id: str):
    """
    BUSINESS PURPOSE / REASON: Returns combined structural and connection characteristics for a specific
    account, which are used to evaluate whether the account fits known fraud typologies.
    """
    try:
        return graph_service.get_account_features(account_id)
    except Exception as e:
        logger.error(f"Error in get_account_features: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts/{account_id}/centrality")
async def get_account_centrality(account_id: str):
    """
    BUSINESS PURPOSE / REASON: Returns centrality metrics (degree, page rank proxy, reach)
    explaining how "connected" an account is. The business goal is to flag intermediary accounts
    used to funnel and distribute illegal money.
    """
    try:
        return graph_service.get_account_centrality(account_id)
    except Exception as e:
        logger.error(f"Error in get_account_centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts/{account_id}/temporal")
async def get_account_temporal(account_id: str):
    """
    BUSINESS PURPOSE / REASON: Calculates velocity metrics (transactions per hour/day/week) for an account.
    The business goal is to detect rapid burst transfers typical of structured layering and micro-structuring.
    """
    try:
        return graph_service.get_account_temporal_features(account_id)
    except Exception as e:
        logger.error(f"Error in get_account_temporal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph/export-tensors")
async def export_tensors():
    """
    BUSINESS PURPOSE / REASON: This is called by the GNN model service to extract the entire graph structure,
    node attributes, and edge indices as Pytorch-compatible tensors. The business goal is to provide the GNN
    with a complete network topology for local model updates.
    """
    try:
        return graph_service.export_tensors()
    except Exception as e:
        logger.error(f"Error in export_tensors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9004)
