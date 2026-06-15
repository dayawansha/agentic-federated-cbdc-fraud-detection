import unittest
from unittest.mock import MagicMock, patch
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
        self.assertIn("CREATE (tx:Transaction", args[0])
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

if __name__ == '__main__':
    unittest.main()
