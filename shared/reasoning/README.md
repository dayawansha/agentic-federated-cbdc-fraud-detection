# Autonomous Reasoning Engine

Self-contained agentic reasoning layer used by `agentic-coordinator` and `local-agent`.

## Design

This MSc research prototype implements **autonomous AI reasoning without external LLM APIs**.
Decisions are produced by a transparent expert-inference pipeline:

```
Perception → Memory recall → Rule inference → Action
```

| Stage | Description |
|-------|-------------|
| **Perception** | Extract signals from telemetry, policies, metrics, and fraud-risk indicators |
| **Memory** | Short-term and long-term recall of prior decisions and outcomes |
| **Rule inference** | Weighted multi-criteria rules with explicit reasoning traces |
| **Action** | Structured decisions (participation, training plan, aggregation strategy) |

## Capabilities

- Local agent participation reasoning
- Adaptive local training plan generation
- Coordinator agent selection reasoning
- Federated aggregation strategy selection
- Explainable `reasoning_trace` on every decision

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `REASONING_ENABLED` | `true` | Master switch (reserved for future use) |

No API keys or external inference services are required.

## Module layout

| File | Role |
|------|------|
| `inference_rules.py` | Expert-system rules and signal scoring |
| `engine.py` | Orchestrates perception, memory, and inference |
| `memory.py` | Agent short-term / long-term memory |
| `schemas.py` | Structured decision models |
