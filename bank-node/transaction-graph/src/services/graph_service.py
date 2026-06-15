import logging
from database import db
from datetime import datetime

logger = logging.getLogger(__name__)

class GraphService:
    @staticmethod
    def add_transaction(tx_data: dict):
        """
        Adds a transaction to Neo4j.
        Creates (Account)-[:SENDS]->(Transaction)-[:RECEIVES]->(Account) structure.
        """
        query = (
            "MERGE (src:Account {id: $source_account}) "
            "MERGE (tgt:Account {id: $target_account}) "
            "CREATE (tx:Transaction {id: $transaction_id, amount: $amount, timestamp: $timestamp, asset_type: $asset_type}) "
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
        query = (
            "MATCH (a:Account {id: $center_id}) "
            "CALL apoc.path.subgraphAll(a, {maxLevel: $depth}) "
            "YIELD nodes, relationships "
            "RETURN nodes, relationships"
        )
        
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

graph_service = GraphService()
