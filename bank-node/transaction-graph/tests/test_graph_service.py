import unittest
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVICE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

if "neo4j" not in sys.modules:
    neo4j_stub = types.ModuleType("neo4j")

    class _GraphDatabase:
        @staticmethod
        def driver(*_args, **_kwargs):
            raise RuntimeError("neo4j driver should not be used in unit tests")

    neo4j_stub.GraphDatabase = _GraphDatabase
    sys.modules["neo4j"] = neo4j_stub

if "pydantic_settings" not in sys.modules:
    settings_stub = types.ModuleType("pydantic_settings")

    class _BaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    settings_stub.BaseSettings = _BaseSettings
    sys.modules["pydantic_settings"] = settings_stub

from services.graph_service import GraphService

class TestGraphService(unittest.TestCase):
    @patch('services.graph_service.db')
    def test_add_transaction_logic(self, mock_db):
        # Setup mock session and result
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        
        tx_data = {
            'transaction_id': 'tx123',
            'source_account': 'acc1',
            'target_account': 'acc2',
            'amount': 100.0,
            'asset_type': 'CBDC'
        }
        
        # Run the method
        GraphService.add_transaction(tx_data)
        
        # Verify transaction query was run
        mock_session.run.assert_called_once()
        args, kwargs = mock_session.run.call_args
        self.assertIn("MERGE (tx:Transaction", args[0])
        self.assertEqual(kwargs['transaction_id'], 'tx123')
        self.assertEqual(kwargs['source_account'], 'acc1')

    @patch('services.graph_service.db')
    def test_get_subgraph_logic(self, mock_db):
        # Setup mock session and result
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        
        # Mocking the record return
        mock_record = MagicMock()
        mock_node = MagicMock()
        mock_node.get.return_value = 'acc1'
        mock_node.labels = ['Account']
        mock_record.__getitem__.side_effect = lambda k: [mock_node] if k == 'nodes' else []
        mock_session.run.return_value = [mock_record]
        
        # Run the method
        result = GraphService.get_subgraph('acc1', depth=1)
        
        # Verify nodes were processed
        self.assertEqual(len(result['nodes']), 1)
        self.assertEqual(result['nodes'][0]['id'], 'acc1')

    @patch('services.graph_service.db')
    def test_get_all_accounts_logic(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        mock_record = {
            'account_id': 'acc1',
            'sent_count': 2,
            'received_count': 3,
        }
        mock_session.run.return_value = [mock_record]

        result = GraphService.get_all_accounts(limit=25)

        mock_session.run.assert_called_once()
        args, kwargs = mock_session.run.call_args
        self.assertIn("MATCH (a:Account)", args[0])
        self.assertEqual(kwargs['limit'], 25)
        self.assertEqual(result, [{'account_id': 'acc1', 'sent_count': 2, 'received_count': 3}])

    @patch('services.graph_service.db')
    def test_get_account_features_logic(self, mock_db):
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        mock_record = {
            'account_id': 'acc1',
            'sent_count': 2,
            'received_count': 3,
            'total_tx_count': 5,
            'sent_amount_sum': 120.0,
            'received_amount_sum': 80.0,
            'total_amount': 200.0,
            'sent_amount_avg': 60.0,
            'received_amount_avg': 26.6666667,
            'sent_amount_max': 75.0,
            'received_amount_max': 40.0,
            'sent_counterparties': ['acc2', 'acc3'],
            'received_counterparties': ['acc3', 'acc4'],
            'sent_asset_types': ['CBDC'],
            'received_asset_types': ['CBDC', 'TOKEN'],
            'sent_counterparty_count': 2,
            'received_counterparty_count': 2,
            'counterparty_touchpoints': 4,
            'reciprocal_counterparties': 1,
            'two_hop_reach': 6,
        }
        mock_session.run.return_value.single.return_value = mock_record

        result = GraphService.get_account_features('acc1')

        mock_session.run.assert_called_once()
        args, kwargs = mock_session.run.call_args
        self.assertIn("two_hop_reach", args[0])
        self.assertEqual(kwargs['account_id'], 'acc1')
        self.assertEqual(result['account_id'], 'acc1')
        self.assertEqual(result['total_tx_count'], 5)
        self.assertEqual(result['counterparty_diversity'], 3)
        self.assertEqual(result['reciprocal_counterparties'], 1)
        self.assertEqual(result['unique_asset_types'], 2)
        self.assertEqual(result['net_flow'], -40.0)
        self.assertEqual(result['avg_amount'], 40.0)
        self.assertEqual(result['in_out_ratio'], 1.5)

if __name__ == '__main__':
    unittest.main()
