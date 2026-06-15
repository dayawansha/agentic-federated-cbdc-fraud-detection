#!/usr/bin/env python3
"""Bootstrap transaction-graph with a controlled subset of processed training data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib import error, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDGES_PATH = PROJECT_ROOT / "train-data" / "processed" / "txs_edges_processed.csv"
DEFAULT_NODES_PATH = PROJECT_ROOT / "train-data" / "processed" / "txs_nodes_processed.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a small processed-data subset into transaction-graph via POST /transactions."
    )
    parser.add_argument("--api-base-url", default="http://127.0.0.1:9004", help="Transaction Graph base URL.")
    parser.add_argument("--edges-path", default=str(DEFAULT_EDGES_PATH), help="Path to txs_edges_processed.csv.")
    parser.add_argument("--nodes-path", default=str(DEFAULT_NODES_PATH), help="Path to txs_nodes_processed.csv.")
    parser.add_argument("--limit", type=int, default=10, help="Number of edge rows to ingest.")
    parser.add_argument("--timeout-seconds", type=int, default=15, help="HTTP timeout for each request.")
    return parser.parse_args()


def read_edge_subset(edges_path: Path, limit: int) -> Tuple[List[Tuple[int, str, str]], set[str]]:
    rows: List[Tuple[int, str, str]] = []
    tx_ids: set[str] = set()
    with edges_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader, start=1):
            source_tx = row["txId1"].strip()
            target_tx = row["txId2"].strip()
            rows.append((index, source_tx, target_tx))
            tx_ids.add(source_tx)
            tx_ids.add(target_tx)
            if len(rows) >= limit:
                break
    return rows, tx_ids


def read_node_lookup(nodes_path: Path, tx_ids: Iterable[str]) -> Dict[str, Dict[str, str]]:
    pending = set(tx_ids)
    lookup: Dict[str, Dict[str, str]] = {}
    with nodes_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            tx_id = row["txId"].strip()
            if tx_id in pending:
                lookup[tx_id] = row
                pending.remove(tx_id)
                if not pending:
                    break
    return lookup


def derive_amount(node_row: Dict[str, str] | None) -> float:
    if not node_row:
        return 1.0

    for column_name in ("Local_feature_1", "Aggregate_feature_1", "Time step"):
        value = node_row.get(column_name)
        if value in (None, ""):
            continue
        try:
            numeric = abs(float(value))
            return round(min(1000000.0, max(1.0, numeric * 100.0 + 1.0)), 2)
        except ValueError:
            continue
    return 1.0


def build_payload(edge_index: int, source_tx: str, target_tx: str, node_lookup: Dict[str, Dict[str, str]]) -> dict:
    source_node = node_lookup.get(source_tx, {})
    target_node = node_lookup.get(target_tx, {})
    source_step = source_node.get("Time step", "unknown")
    source_class = source_node.get("class", "unknown")
    target_step = target_node.get("Time step", "unknown")
    target_class = target_node.get("class", "unknown")

    return {
        "transaction_id": f"elliptic-edge-{edge_index}-{source_tx}-{target_tx}",
        "source_account": f"acct-{source_tx}",
        "target_account": f"acct-{target_tx}",
        "amount": derive_amount(source_node),
        "asset_type": "CBDC",
        "metadata": {
            "source": "train-data/processed",
            "source_txId": source_tx,
            "target_txId": target_tx,
            "source_time_step": str(source_step),
            "source_class": str(source_class),
            "target_time_step": str(target_step),
            "target_class": str(target_class),
        },
    }


def post_transaction(api_base_url: str, payload: dict, timeout_seconds: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    endpoint = f"{api_base_url.rstrip('/')}/transactions"
    http_request = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    args = parse_args()
    edges_path = Path(args.edges_path)
    nodes_path = Path(args.nodes_path)

    if args.limit <= 0:
        raise SystemExit("--limit must be greater than 0")
    if not edges_path.exists():
        raise SystemExit(f"Edges file not found: {edges_path}")
    if not nodes_path.exists():
        raise SystemExit(f"Nodes file not found: {nodes_path}")

    edge_rows, tx_ids = read_edge_subset(edges_path, args.limit)
    node_lookup = read_node_lookup(nodes_path, tx_ids)

    successes = 0
    failures: List[str] = []
    inserted_accounts = set()

    for edge_index, source_tx, target_tx in edge_rows:
        payload = build_payload(edge_index, source_tx, target_tx, node_lookup)
        inserted_accounts.add(payload["source_account"])
        inserted_accounts.add(payload["target_account"])
        try:
            response = post_transaction(args.api_base_url, payload, args.timeout_seconds)
            print(
                f"Inserted {payload['transaction_id']} -> {response.get('transaction_id', payload['transaction_id'])}"
            )
            successes += 1
        except error.HTTPError as exc:
            failures.append(f"{payload['transaction_id']}: HTTP {exc.code} {exc.reason}")
        except error.URLError as exc:
            failures.append(f"{payload['transaction_id']}: {exc.reason}")

    print(
        json.dumps(
            {
                "api_base_url": args.api_base_url,
                "edges_loaded": len(edge_rows),
                "successful_inserts": successes,
                "failed_inserts": len(failures),
                "sample_accounts": sorted(inserted_accounts)[:5],
            },
            indent=2,
        )
    )

    if failures:
        print("Failures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
