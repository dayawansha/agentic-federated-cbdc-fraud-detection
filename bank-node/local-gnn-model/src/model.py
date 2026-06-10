import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, SAGEConv

class FraudGNN(torch.nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, model_type='SAGE'):
        super(FraudGNN, self).__init__()
        self.model_type = model_type
        
        if model_type == 'GCN':
            self.conv1 = GCNConv(input_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, output_dim)
        elif model_type == 'GAT':
            self.conv1 = GATConv(input_dim, hidden_dim, heads=4, concat=True)
            self.conv2 = GATConv(hidden_dim * 4, output_dim, heads=1, concat=False)
        else: # Default to GraphSAGE
            self.conv1 = SAGEConv(input_dim, hidden_dim)
            self.conv2 = SAGEConv(hidden_dim, output_dim)

    def forward(self, x, edge_index):
        # First layer
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.5, training=self.training)
        
        # Second layer
        x = self.conv2(x, edge_index)
        
        return F.log_softmax(x, dim=1)

def get_model(input_dim, hidden_dim=64, output_dim=3, model_type='SAGE'):
    return FraudGNN(input_dim, hidden_dim, output_dim, model_type)
