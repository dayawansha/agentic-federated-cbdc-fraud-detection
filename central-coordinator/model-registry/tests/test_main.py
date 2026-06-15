import asyncio
import base64
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import JSON
import sqlalchemy.dialects.postgresql as postgres_dialect

SERVICE_ROOT = Path("/Users/dusman/Documents/MSC/research/research-development/agentic-federated-cbdc-fraud-detection/central-coordinator/model-registry")
SERVICE_SRC = SERVICE_ROOT / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

TEMP_DIR = tempfile.mkdtemp(prefix="model-registry-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEMP_DIR) / 'registry.db'}"
os.environ["ARTIFACT_DIR"] = str(Path(TEMP_DIR) / "artifacts")
postgres_dialect.JSONB = JSON

main = importlib.import_module("main")


class TestModelRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(main.startup_event())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    def setUp(self):
        main.Base.metadata.drop_all(bind=main.engine)
        main.Base.metadata.create_all(bind=main.engine)
        artifact_dir = Path(main.ARTIFACT_DIR)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        for path in artifact_dir.iterdir():
            if path.is_file():
                path.unlink()

    def test_register_model_with_artifact_path_and_fetch_latest(self):
        response = asyncio.run(
            main.register_model(
                main.RegisterModelRequest(
                    version_id="v-test-1",
                    metrics={"accuracy": 0.91},
                    artifact_path="/tmp/model.pt",
                    is_global=True,
                )
            )
        )

        latest = asyncio.run(main.get_latest_model())
        versions = asyncio.run(main.list_versions())

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["version_id"], "v-test-1")
        self.assertEqual(latest.version_id, "v-test-1")
        self.assertEqual(latest.metrics["accuracy"], 0.91)
        self.assertEqual(len(versions), 1)

    def test_register_model_with_weights_writes_artifact_file(self):
        payload = base64.b64encode(b"demo-weights").decode("ascii")

        response = asyncio.run(
            main.register_model(
                main.RegisterModelRequest(
                    version_id="v-test-weights",
                    metrics={"loss": 0.12},
                    weights=payload,
                    is_global=False,
                )
            )
        )

        latest = asyncio.run(main.get_latest_model())
        artifact_path = Path(latest.artifact_path)

        self.assertEqual(response["version_id"], "v-test-weights")
        self.assertFalse(latest.is_global)
        self.assertTrue(artifact_path.exists())
        self.assertEqual(artifact_path.read_bytes(), b"demo-weights")

    def test_get_latest_model_weights_returns_base64_artifact_payload(self):
        payload = base64.b64encode(b"global-weights").decode("ascii")
        asyncio.run(
            main.register_model(
                main.RegisterModelRequest(
                    version_id="v-latest-weights",
                    metrics={"accuracy": 0.95},
                    weights=payload,
                    is_global=True,
                )
            )
        )

        response = asyncio.run(main.get_latest_model_weights())

        self.assertEqual(response.version_id, "v-latest-weights")
        self.assertEqual(base64.b64decode(response.weights), b"global-weights")

    def test_register_model_requires_artifact_or_weights(self):
        with self.assertRaises(main.HTTPException) as exc:
            asyncio.run(
                main.register_model(
                    main.RegisterModelRequest(
                        version_id="v-missing",
                        metrics={},
                    )
                )
            )

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "artifact_path or weights must be provided")


if __name__ == "__main__":
    unittest.main()
