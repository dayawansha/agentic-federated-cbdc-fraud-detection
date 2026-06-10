import asyncio
import logging
from concurrent import futures
import grpc
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from typing import Optional, Dict

# Attempt to import generated gRPC code
try:
    import transaction_pb2
    import transaction_pb2_grpc
except ImportError:
    # This is expected if the user hasn't generated the code yet
    pass

from database import db
from services.graph_service import graph_service
from services.cdc_service import cdc_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Transaction Graph Service")

class TransactionSchema(BaseModel):
    transaction_id: str
    source_account: str
    target_account: str
    amount: float
    asset_type: Optional[str] = "CBDC"
    metadata: Optional[Dict[str, str]] = {}

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Transaction Graph Service...")
    db.connect()
    # Start gRPC in the background
    asyncio.create_task(serve_grpc())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Transaction Graph Service...")
    db.close()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/transactions")
async def add_transaction(tx: TransactionSchema):
    try:
        tx_dict = tx.dict()
        result = graph_service.add_transaction(tx_dict)
        # Publish event to Kafka for CDC
        cdc_service.publish_transaction(tx_dict)
        return {"success": True, "transaction_id": result}
    except Exception as e:
        logger.error(f"Error in add_transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# gRPC Implementation
class TransactionGraphServicer:
    async def AddTransaction(self, request, context):
        logger.info(f"gRPC: Received transaction {request.transaction_id}")
        try:
            tx_data = {
                "transaction_id": request.transaction_id,
                "source_account": request.source_account,
                "target_account": request.target_account,
                "amount": request.amount,
                "asset_type": request.asset_type,
            }
            graph_service.add_transaction(tx_data)
            cdc_service.publish_transaction(tx_data)
            
            # Note: transaction_pb2 is only available if code is generated
            if 'transaction_pb2' in globals():
                return transaction_pb2.TransactionResponse(
                    success=True, 
                    message="Transaction recorded",
                    node_id=request.transaction_id
                )
            return {"success": True} # Fallback
        except Exception as e:
            logger.error(f"Error in AddTransaction: {e}")
            if 'transaction_pb2' in globals():
                return transaction_pb2.TransactionResponse(success=False, message=str(e))
            return {"success": False, "message": str(e)}

    async def GetSubGraph(self, request, context):
        logger.info(f"gRPC: Querying subgraph for {request.center_node_id}")
        try:
            subgraph = graph_service.get_subgraph(request.center_node_id, request.depth)
            
            if 'transaction_pb2' in globals():
                grpc_nodes = [
                    transaction_pb2.GraphNode(id=n['id'], type=n['type'], properties=n['properties'])
                    for n in subgraph['nodes']
                ]
                grpc_rels = [
                    transaction_pb2.GraphRelationship(
                        id=r['id'], source_id=r['source_id'], target_id=r['target_id'],
                        type=r['type'], properties=r['properties']
                    )
                    for r in subgraph['relationships']
                ]
                return transaction_pb2.GraphData(nodes=grpc_nodes, relationships=grpc_rels)
            return subgraph
        except Exception as e:
            logger.error(f"Error in GetSubGraph: {e}")
            if 'transaction_pb2' in globals():
                return transaction_pb2.GraphData()
            return {}

async def serve_grpc():
    server = grpc.aio.server()
    
    if 'transaction_pb2_grpc' in globals():
        transaction_pb2_grpc.add_TransactionGraphServiceServicer_to_server(
            TransactionGraphServicer(), server
        )
    
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting gRPC server on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9004)
