"""
================================================================================
GRAPH SERVICE ENGINE - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the GraphService as the "network analysis engine." It runs queries on Neo4j
(using Cypher) to extract key patterns that help the GNN spot money laundering.

It extracts structural network statistics for accounts and transactions, including:
1. DEGREE (In-Degree & Out-Degree): Measures the number of incoming and outgoing
   connections. Accounts connected to an unusually high number of other accounts
   are suspicious.
2. PAGERANK & BETWEENNESS PROXY: Measures how "central" or "influential" an account is.
   An account acting as a central hub (a bridge) between many disconnected groups
   is a typical money laundering mule sign.
3. VELOCITY (1h, 24h, 7d): Tracks transaction counts over short, medium, and long
   durations. A sudden burst of payments (burst ratio) or rapid pass-through of funds
   (net flow, in-out ratio) indicates potential shell company activity.
4. RECIPROCAL COUNTERPARTIES: Identifies accounts sending funds back and forth
   repeatedly to generate fake volume.
================================================================================
"""
import logging
from database import db
from datetime import datetime

logger = logging.getLogger(__name__)


class GraphService:
    TRANSACTION_EXPORT_FEATURE_NAMES = [
        "tx_amount",
        "source_total_tx_count",
        "source_total_amount",
        "source_avg_amount",
        "source_counterparty_diversity",
        "source_reciprocal_counterparties",
        "source_two_hop_reach",
        "source_in_degree",
        "source_out_degree",
        "source_betweenness_proxy",
        "source_pagerank_approx",
        "source_tx_count_1h",
        "source_tx_count_24h",
        "source_tx_count_7d",
        "source_velocity_7d",
        "source_burst_ratio",
        "source_net_flow",
        "source_in_out_ratio",
        "target_total_tx_count",
        "target_total_amount",
        "target_avg_amount",
        "target_counterparty_diversity",
        "target_reciprocal_counterparties",
        "target_two_hop_reach",
        "target_in_degree",
        "target_out_degree",
        "target_betweenness_proxy",
        "target_pagerank_approx",
        "target_tx_count_1h",
        "target_tx_count_24h",
        "target_tx_count_7d",
        "target_velocity_7d",
        "target_burst_ratio",
        "target_net_flow",
        "target_in_out_ratio",
        "tx_age_hours",
    ]

    @staticmethod
    def _parse_tx_age_hours(timestamp_value) -> float:
        if not timestamp_value:
            return 0.0
        try:
            parsed = datetime.fromisoformat(str(timestamp_value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                age_seconds = (datetime.now() - parsed).total_seconds()
            else:
                age_seconds = (datetime.now(parsed.tzinfo) - parsed).total_seconds()
            return max(0.0, age_seconds / 3600.0)
        except Exception:
            return 0.0

    @staticmethod
    def _transaction_feature_vector(
        source_features: dict,
        target_features: dict,
        amount: float,
        timestamp_value,
    ) -> list[float]:
        return [
            float(amount),
            float(source_features.get("total_tx_count", 0.0)),
            float(source_features.get("total_amount", 0.0)),
            float(source_features.get("avg_amount", 0.0)),
            float(source_features.get("counterparty_diversity", 0.0)),
            float(source_features.get("reciprocal_counterparties", 0.0)),
            float(source_features.get("two_hop_reach", 0.0)),
            float(source_features.get("in_degree", 0.0)),
            float(source_features.get("out_degree", 0.0)),
            float(source_features.get("betweenness_proxy", 0.0)),
            float(source_features.get("pagerank_approx", 0.0)),
            float(source_features.get("tx_count_1h", 0.0)),
            float(source_features.get("tx_count_24h", 0.0)),
            float(source_features.get("tx_count_7d", 0.0)),
            float(source_features.get("velocity_7d", 0.0)),
            float(source_features.get("burst_ratio", 0.0)),
            float(source_features.get("net_flow", 0.0)),
            float(source_features.get("in_out_ratio", 0.0)),
            float(target_features.get("total_tx_count", 0.0)),
            float(target_features.get("total_amount", 0.0)),
            float(target_features.get("avg_amount", 0.0)),
            float(target_features.get("counterparty_diversity", 0.0)),
            float(target_features.get("reciprocal_counterparties", 0.0)),
            float(target_features.get("two_hop_reach", 0.0)),
            float(target_features.get("in_degree", 0.0)),
            float(target_features.get("out_degree", 0.0)),
            float(target_features.get("betweenness_proxy", 0.0)),
            float(target_features.get("pagerank_approx", 0.0)),
            float(target_features.get("tx_count_1h", 0.0)),
            float(target_features.get("tx_count_24h", 0.0)),
            float(target_features.get("tx_count_7d", 0.0)),
            float(target_features.get("velocity_7d", 0.0)),
            float(target_features.get("burst_ratio", 0.0)),
            float(target_features.get("net_flow", 0.0)),
            float(target_features.get("in_out_ratio", 0.0)),
            GraphService._parse_tx_age_hours(timestamp_value),
        ]

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
        fallback_query = (
            "MATCH path = (a:Account {id: $center_id})-[r*..2]-(b) "
            "RETURN nodes(path) as nodes, relationships(path) as rels"
        )

        with db.get_session() as session:
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
    def get_account_centrality(account_id: str) -> dict:
        """
        Computes Cypher-native graph centrality proxies without requiring APOC or GDS.

        Fields returned:
          - in_degree: number of transactions received (direct senders reaching this account).
          - out_degree: number of transactions sent by this account.
          - two_hop_reach: distinct accounts reachable within 2 hops.
          - betweenness_proxy: (two_hop_reach - direct_neighbours) / two_hop_reach
              — fraction of two-hop accounts accessible *only* through this node.
          - pagerank_approx: sum of (1 / sender_out_degree) over direct senders
              — one power-iteration approximation of PageRank.
        """
        _ZERO = {
            "account_id": account_id,
            "in_degree": 0,
            "out_degree": 0,
            "two_hop_reach": 0,
            "betweenness_proxy": 0.0,
            "pagerank_approx": 0.0,
        }

        degree_query = (
            "MATCH (a:Account {id: $account_id}) "
            "OPTIONAL MATCH (a)-[:SENDS]->(sent:Transaction) "
            "WITH a, count(sent) AS out_degree "
            "OPTIONAL MATCH (a)<-[:RECEIVES]-(recv:Transaction) "
            "RETURN out_degree, count(recv) AS in_degree"
        )

        betweenness_query = (
            "MATCH (a:Account {id: $account_id}) "
            "OPTIONAL MATCH (a)-[:SENDS|RECEIVES*1..2]-(two_hop:Account) "
            "  WHERE two_hop <> a "
            "WITH a, count(DISTINCT two_hop) AS two_hop_reach "
            "OPTIONAL MATCH (a)-[:SENDS|RECEIVES]-(direct:Account) "
            "  WHERE direct <> a "
            "WITH two_hop_reach, count(DISTINCT direct) AS direct_neighbours "
            "RETURN two_hop_reach, "
            "  CASE WHEN two_hop_reach > 0 "
            "    THEN toFloat(two_hop_reach - direct_neighbours) / toFloat(two_hop_reach) "
            "    ELSE 0.0 END AS betweenness_proxy"
        )

        pagerank_query = (
            "MATCH (a:Account {id: $account_id}) "
            "MATCH (sender:Account)-[:SENDS]->(:Transaction)-[:RECEIVES]->(a) "
            "  WHERE sender <> a "
            "WITH DISTINCT sender "
            "MATCH (sender)-[:SENDS]->(st:Transaction) "
            "WITH sender, count(st) AS sender_out_deg "
            "RETURN sum(1.0 / toFloat(CASE WHEN sender_out_deg > 0 THEN sender_out_deg ELSE 1 END)) "
            "  AS pagerank_approx"
        )

        try:
            with db.get_session() as session:
                deg_rec = session.run(degree_query, account_id=account_id).single()
                if not deg_rec:
                    return _ZERO

                bet_rec = session.run(betweenness_query, account_id=account_id).single()
                pr_rec = session.run(pagerank_query, account_id=account_id).single()

                return {
                    "account_id": account_id,
                    "in_degree": int(deg_rec["in_degree"]),
                    "out_degree": int(deg_rec["out_degree"]),
                    "two_hop_reach": int(bet_rec["two_hop_reach"]) if bet_rec else 0,
                    "betweenness_proxy": float(bet_rec["betweenness_proxy"]) if bet_rec else 0.0,
                    "pagerank_approx": float(pr_rec["pagerank_approx"])
                        if (pr_rec and pr_rec["pagerank_approx"] is not None) else 0.0,
                }
        except Exception as exc:
            logger.warning("Centrality query failed for %s: %s", account_id, exc)
            return _ZERO

    @staticmethod
    def get_account_temporal_features(account_id: str) -> dict:
        """
        Computes temporal windowing features using ISO-8601 timestamp comparison in Cypher.
        Requires Transaction.timestamp to be stored as ISO-8601 strings.

        Fields returned:
          - tx_count_1h / tx_count_24h / tx_count_7d: rolling window counts.
          - velocity_7d: average transactions per hour over the 7-day window.
          - burst_ratio: tx_count_1h / tx_count_24h (spike indicator).
          - first_tx_timestamp / last_tx_timestamp: boundary timestamps.
        """
        from datetime import timezone, timedelta

        _ZERO = {
            "account_id": account_id,
            "tx_count_1h": 0,
            "tx_count_24h": 0,
            "tx_count_7d": 0,
            "velocity_7d": 0.0,
            "burst_ratio": 0.0,
            "first_tx_timestamp": None,
            "last_tx_timestamp": None,
        }

        now = datetime.now(tz=timezone.utc)
        ts_1h  = (now - timedelta(hours=1)).isoformat()
        ts_24h = (now - timedelta(hours=24)).isoformat()
        ts_7d  = (now - timedelta(days=7)).isoformat()

        # Covers both sent and received transactions for this account
        temporal_query = (
            "MATCH (a:Account {id: $account_id}) "
            "OPTIONAL MATCH (a)-[:SENDS|RECEIVES*1]-(tx:Transaction) "
            "WHERE tx IS NOT NULL AND tx.timestamp IS NOT NULL "
            "RETURN "
            "  count(CASE WHEN toString(tx.timestamp) >= $ts_1h  THEN 1 END) AS tx_count_1h, "
            "  count(CASE WHEN toString(tx.timestamp) >= $ts_24h THEN 1 END) AS tx_count_24h, "
            "  count(CASE WHEN toString(tx.timestamp) >= $ts_7d  THEN 1 END) AS tx_count_7d, "
            "  min(toString(tx.timestamp)) AS first_tx_timestamp, "
            "  max(toString(tx.timestamp)) AS last_tx_timestamp"
        )

        try:
            with db.get_session() as session:
                rec = session.run(
                    temporal_query,
                    account_id=account_id,
                    ts_1h=ts_1h,
                    ts_24h=ts_24h,
                    ts_7d=ts_7d,
                ).single()

                if not rec:
                    return _ZERO

                tx_count_1h  = int(rec["tx_count_1h"]  or 0)
                tx_count_24h = int(rec["tx_count_24h"] or 0)
                tx_count_7d  = int(rec["tx_count_7d"]  or 0)

                velocity_7d = tx_count_7d / (7 * 24) if tx_count_7d else 0.0
                burst_ratio = (tx_count_1h / tx_count_24h) if tx_count_24h else float(tx_count_1h)

                return {
                    "account_id": account_id,
                    "tx_count_1h": tx_count_1h,
                    "tx_count_24h": tx_count_24h,
                    "tx_count_7d": tx_count_7d,
                    "velocity_7d": round(velocity_7d, 6),
                    "burst_ratio": round(burst_ratio, 6),
                    "first_tx_timestamp": rec["first_tx_timestamp"],
                    "last_tx_timestamp": rec["last_tx_timestamp"],
                }
        except Exception as exc:
            logger.warning("Temporal query failed for %s: %s", account_id, exc)
            return _ZERO

    @staticmethod
    def get_account_features(account_id: str) -> dict:
        """
        Retrieves richer account-level graph features for model use and operator analysis.
        Now merges centrality proxies (PageRank, betweenness, degree) and temporal windowing
        features (1h/24h/7d counts, velocity, burst ratio) alongside all existing metrics.
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

        _ZERO_CENTRALITY = {
            "in_degree": 0, "out_degree": 0,
            "betweenness_proxy": 0.0, "pagerank_approx": 0.0,
        }
        _ZERO_TEMPORAL = {
            "tx_count_1h": 0, "tx_count_24h": 0, "tx_count_7d": 0,
            "velocity_7d": 0.0, "burst_ratio": 0.0,
            "first_tx_timestamp": None, "last_tx_timestamp": None,
        }

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
                    **_ZERO_CENTRALITY,
                    **_ZERO_TEMPORAL,
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

            base = {
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

        # Merge centrality and temporal features (run as separate queries)
        centrality = GraphService.get_account_centrality(account_id)
        temporal = GraphService.get_account_temporal_features(account_id)

        base["in_degree"]           = centrality["in_degree"]
        base["out_degree"]          = centrality["out_degree"]
        base["betweenness_proxy"]   = centrality["betweenness_proxy"]
        base["pagerank_approx"]     = centrality["pagerank_approx"]

        base["tx_count_1h"]         = temporal["tx_count_1h"]
        base["tx_count_24h"]        = temporal["tx_count_24h"]
        base["tx_count_7d"]         = temporal["tx_count_7d"]
        base["velocity_7d"]         = temporal["velocity_7d"]
        base["burst_ratio"]         = temporal["burst_ratio"]
        base["first_tx_timestamp"]  = temporal["first_tx_timestamp"]
        base["last_tx_timestamp"]   = temporal["last_tx_timestamp"]

        return base

    @staticmethod
    def export_tensors() -> dict:
        """
        Exports the live graph as transaction nodes so the GNN can train against
        transaction-level labels instead of account identifiers. Each transaction
        feature vector includes richer graph-derived source/target account context.
        """
        query_nodes = (
            "MATCH (src:Account)-[:SENDS]->(tx:Transaction)-[:RECEIVES]->(tgt:Account) "
            "RETURN tx.id AS tx_id, "
            "src.id AS source_account_id, "
            "tgt.id AS target_account_id, "
            "coalesce(tx.amount, 0.0) AS amount, "
            "coalesce(tx.asset_type, 'CBDC') AS asset_type, "
            "tx.timestamp AS timestamp "
            "ORDER BY tx_id"
        )

        query_edges = (
            "MATCH (tx1:Transaction)<-[:SENDS]-(shared_src:Account)-[:SENDS]->(tx2:Transaction) "
            "WHERE tx1 <> tx2 "
            "RETURN DISTINCT tx1.id AS source, tx2.id AS target "
            "UNION "
            "MATCH (tx1:Transaction)-[:RECEIVES]->(shared_tgt:Account)<-[:RECEIVES]-(tx2:Transaction) "
            "WHERE tx1 <> tx2 "
            "RETURN DISTINCT tx1.id AS source, tx2.id AS target "
            "UNION "
            "MATCH (tx1:Transaction)-[:RECEIVES]->(mid:Account)-[:SENDS]->(tx2:Transaction) "
            "WHERE tx1 <> tx2 "
            "RETURN DISTINCT tx1.id AS source, tx2.id AS target"
        )

        try:
            with db.get_session() as session:
                res_nodes = session.run(query_nodes)
                nodes = []
                features = []
                node_map = {}
                account_feature_cache = {}

                def get_cached_account_features(account_id: str) -> dict:
                    if account_id not in account_feature_cache:
                        account_feature_cache[account_id] = GraphService.get_account_features(account_id)
                    return account_feature_cache[account_id]

                for r in res_nodes:
                    tx_id = r["tx_id"]
                    if not tx_id:
                        continue
                    source_account_id = r["source_account_id"]
                    target_account_id = r["target_account_id"]
                    source_features = get_cached_account_features(source_account_id)
                    target_features = get_cached_account_features(target_account_id)

                    node_map[tx_id] = len(nodes)
                    nodes.append(tx_id)
                    features.append(
                        GraphService._transaction_feature_vector(
                            source_features=source_features,
                            target_features=target_features,
                            amount=float(r["amount"] or 0.0),
                            timestamp_value=r["timestamp"],
                        )
                    )

                res_edges = session.run(query_edges)
                src_list = []
                tgt_list = []
                for r in res_edges:
                    src_id = r["source"]
                    tgt_id = r["target"]
                    if src_id in node_map and tgt_id in node_map:
                        src_list.append(node_map[src_id])
                        tgt_list.append(node_map[tgt_id])
                
                edge_index = [src_list, tgt_list]
                return {
                    "status": "success",
                    "node_type": "transaction",
                    "feature_schema_version": 2,
                    "feature_names": list(GraphService.TRANSACTION_EXPORT_FEATURE_NAMES),
                    "node_ids": nodes,
                    "x": features,
                    "edge_index": edge_index
                }
        except Exception as exc:
            logger.error("Failed to export tensors: %s", exc)
            return {
                "status": "error",
                "detail": str(exc),
                "node_type": "transaction",
                "feature_schema_version": 2,
                "feature_names": list(GraphService.TRANSACTION_EXPORT_FEATURE_NAMES),
                "node_ids": [],
                "x": [],
                "edge_index": [[], []]
            }


graph_service = GraphService()
