import asyncio
import httpx
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("e2e-test")

# Service URLs (assuming running locally for test)
COORDINATOR_URL = "http://localhost:8001"
LOCAL_AGENT_URL = "http://localhost:9001"
LOCAL_GNN_URL = "http://localhost:9002"
PRIVACY_LAYER_URL = "http://localhost:9003"

async def check_services_health():
    services = {
        "Coordinator": COORDINATOR_URL,
        "Local Agent": LOCAL_AGENT_URL,
        "Local GNN": LOCAL_GNN_URL,
        "Privacy Layer": PRIVACY_LAYER_URL
    }
    async with httpx.AsyncClient() as client:
        for name, url in services.items():
            try:
                resp = await client.get(f"{url}/health")
                if resp.status_code == 200:
                    logger.info(f"✅ {name} is healthy")
                else:
                    logger.error(f"❌ {name} returned status {resp.status_code}")
            except Exception as e:
                logger.error(f"❌ {name} is unreachable: {e}")

async def run_federated_round():
    round_id = f"test-round-{int(time.time())}"
    logger.info(f"🚀 Starting E2E Federated Learning Round: {round_id}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Trigger Coordinator to start round
        logger.info("Triggering Coordinator...")
        try:
            resp = await client.post(f"{COORDINATOR_URL}/rounds/start", params={"round_id": round_id})
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"✅ Round initiated successfully")
                logger.info(f"Final State Step: {result['final_state']['current_step']}")
                
                if result['final_state']['current_step'] == "round_complete":
                    logger.info("🎉 E2E TEST PASSED: Full cycle completed from Coordinator to Local Agent and back.")
                else:
                    logger.warning(f"⚠️ Round stopped at step: {result['final_state']['current_step']}")
            else:
                logger.error(f"❌ Failed to start round: {resp.text}")
        except Exception as e:
            logger.error(f"❌ E2E test error: {e}")

if __name__ == "__main__":
    print("--- Federated CBDC Fraud Detection E2E Test ---")
    asyncio.run(check_services_health())
    asyncio.run(run_federated_round())
