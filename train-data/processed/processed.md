# Processed Dataset Documentation

This directory contains the processed and normalized files derived from the Elliptic++ dataset, prepared for training the Agentic Federated Learning model.

## Data Preparation Summary
The data was processed using the `data_preparation.py` script. Key processing steps included:
- **Merging**: Features and labels (classes) were merged into single node files.
- **Normalization**: Numerical features were scaled using `StandardScaler` (zero mean, unit variance).
- **Indexing**: A mapping from original Transaction IDs (`txId`) to integer indices was created for graph compatibility.
- **Federated Splitting**: The transaction dataset was partitioned into shards based on time steps to simulate a distributed banking environment.

---

## File Descriptions

### Transactions Dataset (Primary)

| File Name | Description |
|-----------|-------------|
| `txs_nodes_processed.csv` | Normalized transaction nodes containing 183 features and the target `class`. |
| `txs_edges_processed.csv` | Edgelist representing the flow of Bitcoin between transactions (`txId1` -> `txId2`). |
| `txs_node_mapping.pkl` | A Python pickle file containing a dictionary mapping `txId` to numerical indices (0 to N-1). |

### Federated Shards
These files are used to simulate local data held by different participants in the federated learning framework.

| File Name | Time Steps | Description |
|-----------|------------|-------------|
| `txs_shard_1.csv` | 1 - 13 | Local data for Node 1 |
| `txs_shard_2.csv` | 14 - 25 | Local data for Node 2 |
| `txs_shard_3.csv` | 26 - 37 | Local data for Node 3 |
| `txs_shard_4.csv` | 38 - 49 | Local data for Node 4 |

### Actors Dataset (Wallet Addresses)

| File Name | Description |
|-----------|-------------|
| `actors_nodes_processed.csv` | Normalized wallet address nodes with actor-level features and classes. |
| `actors_edges_processed.csv` | Edgelist representing direct interactions between wallet addresses (Address-to-Address). |

---

## Usage Note
When training GNN models, use the `txs_node_mapping.pkl` to translate original IDs in the edgelists to the row indices in the processed node CSVs.
