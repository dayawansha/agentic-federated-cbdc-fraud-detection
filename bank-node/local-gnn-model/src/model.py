import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, SAGEConv

class FraudGNN(torch.nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, model_type='HYBRID', num_heads=4, dropout=0.3):
        super(FraudGNN, self).__init__()
        self.model_type = model_type
        self.dropout = float(dropout)

        if model_type == 'GCN':
            self.conv1 = GCNConv(input_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, output_dim)
            self.norm1 = nn.LayerNorm(hidden_dim)
        elif model_type == 'GAT':
            self.conv1 = GATConv(input_dim, hidden_dim, heads=num_heads, concat=True)
            self.conv2 = GATConv(hidden_dim * num_heads, output_dim, heads=1, concat=False)
            self.norm1 = nn.LayerNorm(hidden_dim * num_heads)
        elif model_type == 'SAGE':
            self.conv1 = SAGEConv(input_dim, hidden_dim)
            self.conv2 = SAGEConv(hidden_dim, output_dim)
            self.norm1 = nn.LayerNorm(hidden_dim)
        else:
            attn_dim = hidden_dim * num_heads
            reduced_dim = max(hidden_dim // 2, output_dim)
            self.conv1 = SAGEConv(input_dim, hidden_dim)
            self.conv2 = GATConv(hidden_dim, hidden_dim, heads=num_heads, concat=True)
            self.conv3 = SAGEConv(attn_dim, reduced_dim)
            self.norm1 = nn.LayerNorm(hidden_dim)
            self.norm2 = nn.LayerNorm(attn_dim)
            self.norm3 = nn.LayerNorm(reduced_dim)
            self.skip_input = nn.Linear(input_dim, hidden_dim)
            self.skip_attn = nn.Linear(hidden_dim, attn_dim)
            self.classifier = nn.Sequential(
                nn.Linear(hidden_dim + attn_dim + reduced_dim, hidden_dim * 2),
                nn.ReLU(),
                nn.Dropout(self.dropout),
                nn.Linear(hidden_dim * 2, hidden_dim),
                nn.ReLU(),
                nn.Dropout(self.dropout),
                nn.Linear(hidden_dim, output_dim),
            )

    def forward(self, x, edge_index):
        if self.model_type == 'HYBRID':
            h1 = self.conv1(x, edge_index)
            h1 = self.norm1(h1 + self.skip_input(x))
            h1 = F.relu(h1)
            h1 = F.dropout(h1, p=self.dropout, training=self.training)

            h2 = self.conv2(h1, edge_index)
            h2 = self.norm2(h2 + self.skip_attn(h1))
            h2 = F.elu(h2)
            h2 = F.dropout(h2, p=self.dropout, training=self.training)

            h3 = self.conv3(h2, edge_index)
            h3 = self.norm3(h3)
            h3 = F.relu(h3)
            h3 = F.dropout(h3, p=self.dropout, training=self.training)

            fused = torch.cat([h1, h2, h3], dim=1)
            logits = self.classifier(fused)
            return F.log_softmax(logits, dim=1)

        x = self.conv1(x, edge_index)
        x = self.norm1(x)
        x = F.relu(x)
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.conv2(x, edge_index)
        return F.log_softmax(x, dim=1)

def get_model(input_dim, hidden_dim=64, output_dim=3, model_type='HYBRID', num_heads=4, dropout=0.3):
    return FraudGNN(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        output_dim=output_dim,
        model_type=model_type,
        num_heads=num_heads,
        dropout=dropout,
    )
