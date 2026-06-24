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
    transaction_id: str
    source_account: str
    target_account: str
    amount: float
    asset_type: Optional[str] = "CBDC"
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/transactions")
async def add_transaction(tx: TransactionSchema):
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
    try:
        return graph_service.get_account_features(account_id)
    except Exception as e:
        logger.error(f"Error in get_account_features: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts/{account_id}/centrality")
async def get_account_centrality(account_id: str):
    """
    Returns Cypher-native centrality proxies for an account:
    in_degree, out_degree, two_hop_reach, betweenness_proxy, pagerank_approx.
    No APOC or GDS plugin required.
    """
    try:
        return graph_service.get_account_centrality(account_id)
    except Exception as e:
        logger.error(f"Error in get_account_centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts/{account_id}/temporal")
async def get_account_temporal(account_id: str):
    """
    Returns temporal windowing features for an account:
    tx_count_1h, tx_count_24h, tx_count_7d, velocity_7d, burst_ratio,
    first_tx_timestamp, last_tx_timestamp.
    """
    try:
        return graph_service.get_account_temporal_features(account_id)
    except Exception as e:
        logger.error(f"Error in get_account_temporal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9004)
