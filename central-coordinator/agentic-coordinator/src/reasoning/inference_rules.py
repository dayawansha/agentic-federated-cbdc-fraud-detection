"""
Self-contained autonomous inference rules for the agentic coordinator.

Implements a transparent expert-system style reasoning pipeline:
  Perception (signal extraction) → Memory recall → Rule inference → Action

No external LLM or third-party inference APIs are used.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from reasoning.memory import AgentMemory

REASONING_ENGINE_ID = "expert-inference"


def infer_aggregation_strategy(
    valid_updates: List[Dict[str, Any]],
    policies: Dict[str, Any],
    current_strategy: str,
    supported_strategies: Optional[Set[str]] = None,
    memory: Optional[AgentMemory] = None,
) -> Tuple[str, List[str], float]:
    supported = supported_strategies or set()
    steps: List[str] = ["Perception: analysing submitted model update quality."]
    if not valid_updates:
        steps.append(f"Action: retain strategy {current_strategy} — no valid updates.")
        return current_strategy, steps, 0.5

    accuracies = [float((u.get("metrics") or {}).get("accuracy", 0.0)) for u in valid_updates]
    avg_accuracy = sum(accuracies) / len(accuracies)
    accuracy_spread = max(accuracies) - min(accuracies) if len(accuracies) > 1 else 0.0
    low_quality_count = sum(
        1 for acc in accuracies if acc < float(policies.get("low_performance_accuracy", 0.0))
    )
    rejected_ratio = low_quality_count / len(valid_updates)
    fallback = str(policies.get("fallback_aggregation_strategy", current_strategy))

    steps.append(
        f"Inference: avg_accuracy={avg_accuracy:.3f}, spread={accuracy_spread:.3f}, "
        f"low_quality_ratio={rejected_ratio:.2f}."
    )

    if avg_accuracy < float(policies.get("low_performance_accuracy", 0.0)) and fallback in supported:
        steps.append(f"Rule: low average quality → switch to {fallback}.")
        return fallback, steps, 0.88

    adaptive_strategy = str(policies.get("adaptive_strategy_on_rejection", fallback))
    if rejected_ratio >= float(policies.get("adaptive_rejected_update_ratio", 1.0)) and adaptive_strategy in supported:
        steps.append(f"Rule: elevated rejection pressure → select {adaptive_strategy}.")
        return adaptive_strategy, steps, 0.86

    if accuracy_spread >= 0.2 and "FedProxGNN" in supported:
        steps.append("Rule: high cross-agent accuracy heterogeneity → select FedProxGNN.")
        return "FedProxGNN", steps, 0.84

    if accuracy_spread >= 0.15 and "RobustMedian" in supported and memory and len(memory.long_term) >= 3:
        steps.append("Rule: memory indicates recurring heterogeneity → select RobustMedian.")
        return "RobustMedian", steps, 0.82

    steps.append(f"Action: retain strategy {current_strategy}.")
    return current_strategy, steps, 0.8


def infer_coordinator_round(
    candidate_agents: List[str],
    policies: Dict[str, Any],
    agent_profiles: Dict[str, Dict[str, float]],
    memory: AgentMemory,
) -> Tuple[List[str], str, bool, List[str], float]:
    steps: List[str] = ["Perception: reviewing candidate bank nodes for round eligibility."]
    min_reliability = float(policies.get("minimum_agent_reliability_score", 0.25))
    selected: List[str] = []
    escalate = False

    for agent_url in candidate_agents:
        profile = agent_profiles.get(agent_url, {})
        reliability = float(profile.get("reliability_score", 1.0))
        last_accuracy = float(profile.get("last_accuracy", reliability))
        if reliability < min_reliability:
            steps.append(f"Inference: exclude {agent_url} — reliability {reliability:.3f} < {min_reliability:.3f}.")
            escalate = True
            continue
        if last_accuracy < float(policies.get("low_performance_accuracy", 0.8)) * 0.75:
            steps.append(
                f"Inference: exclude {agent_url} — last accuracy {last_accuracy:.3f} below autonomous safety floor."
            )
            escalate = True
            continue
        selected.append(agent_url)
        steps.append(f"Inference: include {agent_url} — reliability={reliability:.3f}, last_accuracy={last_accuracy:.3f}.")

    hint = str(policies.get("aggregation_strategy", "FedAvg"))
    if len(selected) >= 3:
        accuracies = [float(agent_profiles.get(a, {}).get("last_accuracy", 0.8)) for a in selected]
        if max(accuracies) - min(accuracies) >= 0.15:
            hint = str(policies.get("fallback_aggregation_strategy", "AdaptiveFedAvg"))
            steps.append(f"Rule: multi-agent heterogeneity detected → strategy hint {hint}.")

    if not selected and candidate_agents:
        steps.append("Action: no agent passed autonomous screening; round cannot proceed safely.")
    else:
        steps.append(f"Action: coordinator selected {len(selected)} agent(s) for participation.")

    confidence = 0.9 if selected else 0.4
    steps.append(f"Decision confidence: {confidence:.2f} (engine={REASONING_ENGINE_ID}).")
    return selected, hint, escalate, steps, confidence
