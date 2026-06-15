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
        with db.get_session() as session:
            sent = session.run(
                "MATCH (a:Account {id: $id})-[:SENDS]->(t:Transaction) RETURN count(t) as c, coalesce(sum(t.amount), 0) as s",
                id=account_id,
            ).single()
            received = session.run(
                "MATCH (a:Account {id: $id})<-[:RECEIVES]-(t:Transaction) RETURN count(t) as c, coalesce(sum(t.amount), 0) as s",
                id=account_id,
            ).single()
            neighbors = session.run(
                "MATCH (a:Account {id: $id})-[:SENDS|RECEIVES*1..2]-(b:Account) RETURN count(DISTINCT b) as c",
                id=account_id,
            ).single()

        sent_count = int(sent["c"]) if sent else 0
        recv_count = int(received["c"]) if received else 0
        sent_sum = float(sent["s"]) if sent else 0.0
        recv_sum = float(received["s"]) if received else 0.0
        neighbor_count = int(neighbors["c"]) if neighbors else 0

        total_count = sent_count + recv_count
        avg_amount = (sent_sum + recv_sum) / total_count if total_count else 0.0
        return {
            "account_id": account_id,
            "sent_count": sent_count,
            "received_count": recv_count,
            "sent_amount_sum": sent_sum,
            "received_amount_sum": recv_sum,
            "counterparty_diversity": neighbor_count,
            "avg_amount": avg_amount,
        }
    except Exception as e:
        logger.error(f"Error in get_account_features: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9004)
