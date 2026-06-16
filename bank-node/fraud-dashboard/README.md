# Fraud Dashboard

Visual operational monitor, real-time alert feed interface, and federated training status console.

## Port
- **`3001`** (Served via Nginx / Node.js development server)

## Service Responsibilities
The `fraud-dashboard` is the graphical user interface (GUI) of the system, designed to give operators a live, unified overview of threat intelligence and training progress across the network.

- **Real-Time Alert Feed**: Establishes a persistent WebSocket connection to the `Alerting` service, displaying new fraud detections instantly with details on sender/receiver accounts, bank of origin, transaction amounts, and GNN confidence scores.
- **Interactive Graph Visualizer**: Renders transactional network structures, allowing operators to trace payment chains, inspect specific account features, and visualize GNN-classified illicit paths.
- **Service Status Dashboard**: Periodically queries `/health` endpoints of all coordination and node microservices, indicating cluster-wide operational health in a traffic-light view.
- **Training Round Console**: Displays active federated learning rounds, tracking agent participation, validation metrics, and privacy budget sweeps.
- **Operator Tooling Integration**: Embeds quick-links to monitoring utilities, including pgAdmin and the Kafka UI.

---

## Configuration & Environment

The frontend reads variables at compile/run time to bind backend endpoints:

| Variable | Description | Default / Example |
|----------|-------------|-------------------|
| `REACT_APP_PROXY_API_BASE` | Base API gateway or local agent proxy address | `"/api"` (relative) or `"http://127.0.0.1:9001"` |
| `REACT_APP_WS_URL` | WebSocket path for streaming alerts | `"ws://127.0.0.1:9005"` |

---

## Production Deployment (Nginx)
In production, the dashboard is containerized and served using a light-weight Nginx configuration, which is set up to route API calls to local endpoints and fallback to `index.html` for single-page routing.

---

## Technology Stack
- **Framework**: React.js, HTML5, Vanilla CSS
- **Graphics & Graphs**: Cytoscape.js or similar visual network libraries, Chart.js for metric plotting
- **Web Server (Production)**: Nginx
