# Fraud Dashboard

Visual operational monitor, real-time alert feed interface, and federated training status console.

## Port
- **`3001`** (Served via Nginx / Node.js development server)

## Service Responsibilities
The `fraud-dashboard` is the **dashboard (control screen)** of the system. It is the visual website/interface that bank operators use to see live fraud alerts and watch the training metrics.

1. **Live Alert Feed (Real-Time Alert Feed)**
   - **What it does:** Displays new fraud alerts on the screen as soon as they are detected.
   - **How it works:** It connects to the `Alerting` service via WebSockets, receiving push-notifications of suspicious transactions, sender/receiver details, and the AI's confidence score.

2. **Network Map Visualizer (Interactive Graph Visualizer)**
   - **What it does:** Shows a visual map of how money flows between accounts to help operators trace fraud rings.
   - **How it works:** It draws the transaction connections using charting/network libraries, highlighting paths that the GNN AI flagged as illicit or structuring loops.

3. **System Health Check (Service Status Dashboard)**
   - **What it does:** Shows a green/red checklist of whether all services are online and working.
   - **How it works:** It regularly asks the `/health` endpoints of all services (like Neo4j, Kafka, and the coordinator services) to check if they are running.

4. **Federated Training Monitor (Training Round Console)**
   - **What it does:** Displays progress charts of the federated learning rounds.
   - **How it works:** It pulls records from the coordinator to show how many rounds have run, which banks took part, their accuracy scores, and how much privacy limit has been used.

5. **Shortcut Links (Operator Tooling Integration)**
   - **What it does:** Provides quick shortcuts to admin dashboards (like the Kafka console and PostgreSQL admin).
   - **How it works:** It embeds links directly inside the navigation bar so administrators can quickly manage the databases and message queues.

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
