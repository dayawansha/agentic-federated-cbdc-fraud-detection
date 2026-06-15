import logging
from database import db
from datetime import datetime

logger = logging.getLogger(__name__)

class GraphService:
    @staticmethod
    def add_transaction(tx_data: dict):
        """
        Adds or updates a transaction in Neo4j.
        Creates (Account)-[:SENDS]->(Transaction)-[:RECEIVES]->(Account) structure.
        """
        query = (
            "MERGE (src:Account {id: $source_account}) "
            "MERGE (tgt:Account {id: $target_account}) "
            "MERGE (tx:Transaction {id: $transaction_id}) "
            "ON CREATE SET tx.amount = $amount, tx.timestamp = $timestamp, tx.asset_type = $asset_type "
            "ON MATCH SET tx.amount = $amount, tx.asset_type = $asset_type, tx.timestamp = coalesce(tx.timestamp, $timestamp) "
            "MERGE (src)-[:SENDS]->(tx) "
            "MERGE (tx)-[:RECEIVES]->(tgt) "
            "RETURN tx.id"
        )
        
        with db.get_session() as session:
            result = session.run(
                query,
                source_account=tx_data['source_account'],
                target_account=tx_data['target_account'],
                transaction_id=tx_data['transaction_id'],
                amount=tx_data['amount'],
                timestamp=tx_data.get('timestamp', datetime.now().isoformat()),
                asset_type=tx_data.get('asset_type', 'CBDC')
            )
            record = result.single()
            return record[0] if record else tx_data['transaction_id']

    @staticmethod
    def get_subgraph(center_node_id: str, depth: int = 1):
        """
        Retrieves a subgraph around a specific account node.
        """
        # Note: APOC might not be available by default, fallback to standard Cypher if needed
        fallback_query = (
            "MATCH path = (a:Account {id: $center_id})-[r*..2]-(b) "
            "RETURN nodes(path) as nodes, relationships(path) as rels"
        )
        
        with db.get_session() as session:
            # For simplicity, returning the results of the fallback query
            result = session.run(fallback_query, center_id=center_node_id, depth=depth)
            
            nodes = []
            relationships = []
            
            for record in result:
                for node in record['nodes']:
                    node_data = {
                        "id": node.get('id'),
                        "type": list(node.labels)[0] if node.labels else "Unknown",
                        "properties": dict(node)
                    }
                    if node_data not in nodes:
                        nodes.append(node_data)
                
                for rel in record['rels']:
                    rel_data = {
                        "id": str(rel.id),
                        "source_id": rel.start_node.get('id'),
                        "target_id": rel.end_node.get('id'),
                        "type": rel.type,
                        "properties": dict(rel)
                    }
                    if rel_data not in relationships:
                        relationships.append(rel_data)
                        
            return {"nodes": nodes, "relationships": relationships}

    @staticmethod
    def get_all_accounts(limit: int = 1000):
        """
        Retrieves account nodes with lightweight summary counts for UI/API browsing.
        """
        query = (
            "MATCH (a:Account) "
            "OPTIONAL MATCH (a)-[:SENDS]->(sent:Transaction) "
            "WITH a, count(sent) AS sent_count "
            "OPTIONAL MATCH (a)<-[:RECEIVES]-(received:Transaction) "
            "RETURN a.id AS account_id, sent_count, count(received) AS received_count "
            "ORDER BY account_id "
            "LIMIT $limit"
        )

        with db.get_session() as session:
            result = session.run(query, limit=max(1, int(limit)))
            accounts = []
            for record in result:
                accounts.append(
                    {
                        "account_id": record["account_id"],
                        "sent_count": int(record["sent_count"]),
                        "received_count": int(record["received_count"]),
                    }
                )
            return accounts

    @staticmethod
    def get_account_features(account_id: str):
        """
        Retrieves richer account-level graph features for model use and operator analysis.
        """
        query = (
            "MATCH (a:Account {id: $account_id}) "
            "OPTIONAL MATCH (a)-[:SENDS]->(sent:Transaction)-[:RECEIVES]->(sent_counterparty:Account) "
            "WITH a, "
            "count(sent) AS sent_count, "
            "coalesce(sum(sent.amount), 0.0) AS sent_amount_sum, "
            "coalesce(avg(sent.amount), 0.0) AS sent_amount_avg, "
            "coalesce(max(sent.amount), 0.0) AS sent_amount_max, "
            "collect(DISTINCT sent_counterparty.id) AS sent_counterparties, "
            "collect(DISTINCT sent.asset_type) AS sent_asset_types "
            "OPTIONAL MATCH (a)<-[:RECEIVES]-(received:Transaction)<-[:SENDS]-(recv_counterparty:Account) "
            "WITH a, sent_count, sent_amount_sum, sent_amount_avg, sent_amount_max, sent_counterparties, sent_asset_types, "
            "count(received) AS received_count, "
            "coalesce(sum(received.amount), 0.0) AS received_amount_sum, "
            "coalesce(avg(received.amount), 0.0) AS received_amount_avg, "
            "coalesce(max(received.amount), 0.0) AS received_amount_max, "
            "collect(DISTINCT recv_counterparty.id) AS received_counterparties, "
            "collect(DISTINCT received.asset_type) AS received_asset_types "
            "OPTIONAL MATCH (a)-[:SENDS|RECEIVES*1..2]-(reachable:Account) "
            "WITH a, sent_count, sent_amount_sum, sent_amount_avg, sent_amount_max, "
            "received_count, received_amount_sum, received_amount_avg, received_amount_max, "
            "sent_counterparties, received_counterparties, sent_asset_types, received_asset_types, "
            "count(DISTINCT reachable) AS two_hop_reach "
            "RETURN a.id AS account_id, "
            "sent_count, received_count, "
            "(sent_count + received_count) AS total_tx_count, "
            "sent_amount_sum, received_amount_sum, "
            "(sent_amount_sum + received_amount_sum) AS total_amount, "
            "sent_amount_avg, received_amount_avg, "
            "sent_amount_max, received_amount_max, "
            "sent_counterparties, received_counterparties, "
            "sent_asset_types, received_asset_types, "
            "size(sent_counterparties) AS sent_counterparty_count, "
            "size(received_counterparties) AS received_counterparty_count, "
            "size([cp IN sent_counterparties + received_counterparties WHERE cp IS NOT NULL]) AS counterparty_touchpoints, "
            "size([cp IN sent_counterparties WHERE cp IN received_counterparties]) AS reciprocal_counterparties, "
            "two_hop_reach"
        )

        with db.get_session() as session:
            record = session.run(query, account_id=account_id).single()
            if not record:
                return {
                    "account_id": account_id,
                    "sent_count": 0,
                    "received_count": 0,
                    "total_tx_count": 0,
                    "sent_amount_sum": 0.0,
                    "received_amount_sum": 0.0,
                    "total_amount": 0.0,
                    "sent_amount_avg": 0.0,
                    "received_amount_avg": 0.0,
                    "sent_amount_max": 0.0,
                    "received_amount_max": 0.0,
                    "sent_counterparty_count": 0,
                    "received_counterparty_count": 0,
                    "counterparty_touchpoints": 0,
                    "counterparty_diversity": 0,
                    "reciprocal_counterparties": 0,
                    "two_hop_reach": 0,
                    "unique_asset_types": 0,
                    "avg_amount": 0.0,
                    "net_flow": 0.0,
                    "in_out_ratio": 0.0,
                }

            sent_count = int(record["sent_count"])
            received_count = int(record["received_count"])
            total_tx_count = int(record["total_tx_count"])
            sent_amount_sum = float(record["sent_amount_sum"])
            received_amount_sum = float(record["received_amount_sum"])
            total_amount = float(record["total_amount"])
            sent_counterparties = {cp for cp in (record["sent_counterparties"] or []) if cp is not None}
            received_counterparties = {cp for cp in (record["received_counterparties"] or []) if cp is not None}
            asset_types = {
                asset
                for asset in (record["sent_asset_types"] or []) + (record["received_asset_types"] or [])
                if asset is not None
            }

            return {
                "account_id": record["account_id"],
                "sent_count": sent_count,
                "received_count": received_count,
                "total_tx_count": total_tx_count,
                "sent_amount_sum": sent_amount_sum,
                "received_amount_sum": received_amount_sum,
                "total_amount": total_amount,
                "sent_amount_avg": float(record["sent_amount_avg"]),
                "received_amount_avg": float(record["received_amount_avg"]),
                "sent_amount_max": float(record["sent_amount_max"]),
                "received_amount_max": float(record["received_amount_max"]),
                "sent_counterparty_count": int(record["sent_counterparty_count"]),
                "received_counterparty_count": int(record["received_counterparty_count"]),
                "counterparty_touchpoints": int(record["counterparty_touchpoints"]),
                "counterparty_diversity": len(sent_counterparties | received_counterparties),
                "reciprocal_counterparties": int(record["reciprocal_counterparties"]),
                "two_hop_reach": int(record["two_hop_reach"]),
                "unique_asset_types": len(asset_types),
                "avg_amount": (total_amount / total_tx_count) if total_tx_count else 0.0,
                "net_flow": received_amount_sum - sent_amount_sum,
                "in_out_ratio": (received_count / sent_count) if sent_count else float(received_count),
            }

graph_service = GraphService()
