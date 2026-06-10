import pandas as pd
import numpy as np
import os
from sklearn.preprocessing import StandardScaler
import pickle

def is_lfs_pointer(file_path):
    """Checks if a file is a Git LFS pointer instead of the actual data."""
    try:
        with open(file_path, 'r') as f:
            first_line = f.readline()
            return first_line.startswith("version https://git-lfs.github.com/spec/v1")
    except Exception:
        return False

def prepare_transactions_data(base_path, output_path):
    print("Processing Transactions Dataset...")
    txs_features_path = os.path.join(base_path, "Transactions Dataset/txs_features.csv")
    txs_classes_path = os.path.join(base_path, "Transactions Dataset/txs_classes.csv")
    txs_edgelist_path = os.path.join(base_path, "Transactions Dataset/txs_edgelist.csv")

    # Check for LFS pointers
    for p in [txs_features_path, txs_classes_path, txs_edgelist_path]:
        if is_lfs_pointer(p):
            print(f"Warning: {os.path.basename(p)} is a Git LFS pointer. Please ensure data is pulled.")
            return None, None

    # Load data
    df_features = pd.read_csv(txs_features_path)
    df_classes = pd.read_csv(txs_classes_path)
    df_edges = pd.read_csv(txs_edgelist_path)

    # Merge features and classes
    df_nodes = pd.merge(df_features, df_classes, on="txId")

    # Separate features and labels
    # txId and Time step are not training features
    feature_cols = [c for c in df_nodes.columns if c not in ["txId", "Time step", "class"]]
    
    # Scale features
    scaler = StandardScaler()
    df_nodes[feature_cols] = scaler.fit_transform(df_nodes[feature_cols])

    # Save processed nodes and edges
    df_nodes.to_csv(os.path.join(output_path, "txs_nodes_processed.csv"), index=False)
    df_edges.to_csv(os.path.join(output_path, "txs_edges_processed.csv"), index=False)
    
    # Create a mapping for txId to node index (useful for GNNs)
    node_mapping = {txId: i for i, txId in enumerate(df_nodes["txId"])}
    with open(os.path.join(output_path, "txs_node_mapping.pkl"), "wb") as f:
        pickle.dump(node_mapping, f)

    print(f"Transactions data processed. Total nodes: {len(df_nodes)}, Total edges: {len(df_edges)}")
    return df_nodes, df_edges

def prepare_actors_data(base_path, output_path):
    print("Processing Actors Dataset...")
    wallets_combined_path = os.path.join(base_path, "Actors Dataset/wallets_features_classes_combined.csv")
    addr_addr_path = os.path.join(base_path, "Actors Dataset/AddrAddr_edgelist.csv")

    # Use combined file if available and not a pointer
    if os.path.exists(wallets_combined_path) and not is_lfs_pointer(wallets_combined_path):
        df_nodes = pd.read_csv(wallets_combined_path)
    else:
        features_path = os.path.join(base_path, "Actors Dataset/wallets_features.csv")
        classes_path = os.path.join(base_path, "Actors Dataset/wallets_classes.csv")
        if is_lfs_pointer(features_path) or is_lfs_pointer(classes_path):
            print("Warning: Actor features/classes are LFS pointers.")
            return
        df_features = pd.read_csv(features_path)
        df_classes = pd.read_csv(classes_path)
        df_nodes = pd.merge(df_features, df_classes, on="address")

    # Scale features
    feature_cols = [c for c in df_nodes.columns if c not in ["address", "Time step", "class"]]
    scaler = StandardScaler()
    df_nodes[feature_cols] = scaler.fit_transform(df_nodes[feature_cols])

    # Save processed nodes
    df_nodes.to_csv(os.path.join(output_path, "actors_nodes_processed.csv"), index=False)

    # Check edges
    if is_lfs_pointer(addr_addr_path):
        print("Warning: AddrAddr_edgelist.csv is an LFS pointer. Skipping edges.")
    else:
        df_edges = pd.read_csv(addr_addr_path)
        df_edges.to_csv(os.path.join(output_path, "actors_edges_processed.csv"), index=False)
        print(f"Actors edges processed: {len(df_edges)}")

    print(f"Actors data processed. Total nodes: {len(df_nodes)}")

def simulate_federated_split(df_nodes, output_path, n_shards=4):
    print(f"Simulating Federated Split into {n_shards} shards...")
    # Split by Time step to simulate different time-based data at nodes
    time_steps = sorted(df_nodes["Time step"].unique())
    shards = np.array_split(time_steps, n_shards)
    
    for i, shard_steps in enumerate(shards):
        shard_df = df_nodes[df_nodes["Time step"].isin(shard_steps)]
        shard_file = os.path.join(output_path, f"txs_shard_{i+1}.csv")
        shard_df.to_csv(shard_file, index=False)
        print(f"  Shard {i+1} saved with {len(shard_df)} nodes (Time steps: {shard_steps[0]}-{shard_steps[-1]})")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "EllipticPlusPlus-main")
    processed_path = os.path.join(base_dir, "processed")

    if not os.path.exists(processed_path):
        os.makedirs(processed_path)

    # Prepare Transactions
    df_txs_nodes, df_txs_edges = prepare_transactions_data(data_path, processed_path)
    
    # Simulate Federated Split for Transactions if data is available
    if df_txs_nodes is not None:
        simulate_federated_split(df_txs_nodes, processed_path)
    
    # Prepare Actors
    prepare_actors_data(data_path, processed_path)

    print("\nData preparation complete. All processed files are in 'train-data/processed/'")
