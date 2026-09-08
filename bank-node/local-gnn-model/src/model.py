"""
================================================================================
FRAUD GNN MODEL - NEURAL NETWORK ARCHITECTURE
================================================================================
Defines the Graph Neural Network (GNN) that reads the transaction graph and
outputs, per transaction node, a probability distribution over 3 classes:
licit (0), illicit (1), and unknown (2).

Four architectures are supported via `model_type`:
- GCN: Graph Convolutional Network - simplest, averages neighbor features.
- GAT: Graph Attention Network - learns to weigh some neighbors more than others.
- SAGE: GraphSAGE - samples/aggregates neighbor features, scales well.
- HYBRID (default): Stacks SAGE -> GAT -> SAGE with skip connections and
  concatenates every layer's output before a final classifier MLP, combining
  the strengths of all three conv types.
================================================================================
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, SAGEConv

class FraudGNN(torch.nn.Module):
    """
    The fraud-detection Graph Neural Network. Builds one of GCN/GAT/SAGE/HYBRID
    stacks of graph-convolution layers depending on `model_type`, and exposes a
    `forward` pass that turns node features + graph edges into class log-probabilities.
    """
    def __init__(self, input_dim, hidden_dim, output_dim, model_type='HYBRID', num_heads=4, dropout=0.3):
        """
        Builds the layer stack for the chosen `model_type`.
        - input_dim: number of features per transaction node.
        - hidden_dim: width of the internal representation.
        - output_dim: number of output classes (3: licit/illicit/unknown).
        - num_heads: number of attention heads used by GAT layers.
        - dropout: fraction of activations randomly zeroed during training to reduce overfitting.
        """
        super(FraudGNN, self).__init__()
        self.model_type = model_type
        self.dropout = float(dropout)

        if model_type == 'GCN':
            # Two plain graph-convolution layers: input -> hidden -> output classes.
            self.conv1 = GCNConv(input_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, output_dim)
            self.norm1 = nn.LayerNorm(hidden_dim)
        elif model_type == 'GAT':
            # First layer keeps all attention heads concatenated (wider hidden state);
            # second layer averages a single head down to the output classes.
            self.conv1 = GATConv(input_dim, hidden_dim, heads=num_heads, concat=True)
            self.conv2 = GATConv(hidden_dim * num_heads, output_dim, heads=1, concat=False)
            self.norm1 = nn.LayerNorm(hidden_dim * num_heads)
        elif model_type == 'SAGE':
            # Two GraphSAGE layers: sample-and-aggregate neighbor features, input -> hidden -> output classes.
            self.conv1 = SAGEConv(input_dim, hidden_dim)
            self.conv2 = SAGEConv(hidden_dim, output_dim)
            self.norm1 = nn.LayerNorm(hidden_dim)
        else:
            # HYBRID (default): SAGE -> GAT -> SAGE stack with residual "skip" connections
            # and a final MLP classifier fed by the concatenation of all three layer outputs.
            attn_dim = hidden_dim * num_heads
            reduced_dim = max(hidden_dim // 2, output_dim)
            self.conv1 = SAGEConv(input_dim, hidden_dim)
            self.conv2 = GATConv(hidden_dim, hidden_dim, heads=num_heads, concat=True)
            self.conv3 = SAGEConv(attn_dim, reduced_dim)
            self.norm1 = nn.LayerNorm(hidden_dim)
            self.norm2 = nn.LayerNorm(attn_dim)
            self.norm3 = nn.LayerNorm(reduced_dim)
            # Linear projections used to add a skip/residual connection between layers
            # so gradients and low-level signal can bypass the graph-conv layers directly.
            self.skip_input = nn.Linear(input_dim, hidden_dim)
            self.skip_attn = nn.Linear(hidden_dim, attn_dim)
            # Final classifier: takes the concatenated outputs of all 3 conv layers
            # and reduces them down to the 3 output class logits.
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
        """
        Runs one forward pass of the network: takes node feature matrix `x` and the
        graph connectivity `edge_index`, and returns log-probabilities per node over
        the 3 classes (licit/illicit/unknown), ready to be used with `F.nll_loss`.
        """
        if self.model_type == 'HYBRID':
            # Layer 1 (SAGE): aggregate neighbor features, then add a skip connection
            # from the raw input features so early signal isn't lost.
            h1 = self.conv1(x, edge_index)
            h1 = self.norm1(h1 + self.skip_input(x))
            h1 = F.relu(h1)
            h1 = F.dropout(h1, p=self.dropout, training=self.training)

            # Layer 2 (GAT): attention-weighted aggregation, with a skip connection from layer 1.
            h2 = self.conv2(h1, edge_index)
            h2 = self.norm2(h2 + self.skip_attn(h1))
            h2 = F.elu(h2)
            h2 = F.dropout(h2, p=self.dropout, training=self.training)

            # Layer 3 (SAGE): further aggregation/reduction of the attention output.
            h3 = self.conv3(h2, edge_index)
            h3 = self.norm3(h3)
            h3 = F.relu(h3)
            h3 = F.dropout(h3, p=self.dropout, training=self.training)

            # Fuse all three layers' representations together and classify.
            fused = torch.cat([h1, h2, h3], dim=1)
            logits = self.classifier(fused)
            return F.log_softmax(logits, dim=1)

        # GCN / GAT / SAGE path: simple two-layer conv stack -> log-probabilities.
        x = self.conv1(x, edge_index)
        x = self.norm1(x)
        x = F.relu(x)
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.conv2(x, edge_index)
        return F.log_softmax(x, dim=1)

def get_model(input_dim, hidden_dim=64, output_dim=3, model_type='HYBRID', num_heads=4, dropout=0.3):
    """
    Factory function that constructs and returns a new `FraudGNN` instance with
    the given dimensions/architecture. Used by the service so the model can be
    (re)built consistently from environment-driven configuration.
    """
    return FraudGNN(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        output_dim=output_dim,
        model_type=model_type,
        num_heads=num_heads,
        dropout=dropout,
    )
