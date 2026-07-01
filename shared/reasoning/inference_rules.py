"""
Self-contained autonomous inference rules for federated CBDC fraud-detection agents.

Implements a transparent expert-system style reasoning pipeline:
  Perception (signal extraction) → Memory recall → Rule inference → Action

No external LLM or third-party inference APIs are used.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.reasoning.memory import AgentMemory

REASONING_ENGINE_ID = "expert-inference"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _memory_performance_bias(memory: AgentMemory) -> Tuple[float, List[str]]:
    """Recall long-term outcomes to bias conservatism when recent rounds underperformed."""
    steps: List[str] = []
    bias = 0.0
    recent = list(memory.long_term)[-5:]
    weak_rounds = 0
    for record in recent:
        decision = record.get("decision", {})
        if not isinstance(decision, dict):
            continue
        metrics = decision.get("metrics") or decision.get("previous_metrics") or {}
        if isinstance(metrics, dict):
            accuracy = float(metrics.get("accuracy", 1.0))
            if accuracy < 0.7:
                weak_rounds += 1
    if weak_rounds >= 2:
        bias = 0.15
        steps.append(
            f"Memory recall: {weak_rounds} recent rounds had accuracy below 0.70; increasing training conservatism."
        )
    return bias, steps


def infer_local_training_plan(context: Dict[str, Any], memory: AgentMemory) -> Dict[str, Any]:
    checks = context.get("participation_checks", {}) or {}
    privacy_budget = checks.get("privacy_budget", {}) if isinstance(checks, dict) else {}
    policy_constraints = checks.get("policy_constraints", {}) if isinstance(checks, dict) else {}
    previous_metrics = context.get("previous_metrics", {}) or {}
    inference_summary = context.get("inference_summary", {}) or {}

    dp_noise_multiplier = float(context.get("dp_noise_multiplier", 0.01))
    default_epochs = int(context.get("default_local_training_epochs", 1))
    max_epochs = int(context.get("max_adaptive_local_epochs", 3))
    fedprox_mu_default = float(context.get("fedprox_mu", 1.0))
    pseudo_label_weight_default = float(context.get("pseudo_label_weight_default", 0.35))
    pseudo_label_confidence_default = float(context.get("pseudo_label_confidence_default", 0.9))
    alert_publish_limit = int(context.get("alert_publish_limit", 5))
    auto_alert = bool(context.get("auto_alert_on_round_complete", True))

    reasoning_steps: List[str] = ["Perception: extracting local telemetry and policy signals."]

    previous_accuracy = _clamp(float(previous_metrics.get("accuracy", 0.75)), 0.0, 1.0)
    previous_loss = max(0.0, float(previous_metrics.get("loss", 0.4)))
    previous_labeled_ratio = _clamp(float(previous_metrics.get("labeled_ratio", 1.0)), 0.0, 1.0)
    previous_sparse_mode = float(previous_metrics.get("sparse_label_mode", 0.0)) >= 0.5

    high_risk_count = max(0.0, float(inference_summary.get("high_risk_count", 0.0)))
    top_confidence = _clamp(float(inference_summary.get("top_confidence", 0.0)), 0.0, 1.0)
    risk_pressure = _clamp((high_risk_count / max(alert_publish_limit, 1)) * 0.6 + top_confidence * 0.4, 0.0, 1.0)
    performance_pressure = _clamp(
        ((1.0 - previous_accuracy) * 0.65) + (_clamp(previous_loss / 2.0, 0.0, 1.0) * 0.35),
        0.0,
        1.0,
    )
    sparse_label_pressure = _clamp(max(1.0 - previous_labeled_ratio, 0.8 if previous_sparse_mode else 0.0), 0.0, 1.0)

    remaining_epsilon = float(privacy_budget.get("remaining_epsilon", 1.0))
    epsilon = max(float(privacy_budget.get("epsilon", max(remaining_epsilon, 1.0))), 1e-6)
    required_reserve = float(privacy_budget.get("required_reserve_epsilon", 0.0))
    usable_epsilon = max(0.0, remaining_epsilon - required_reserve)
    budget_ratio = _clamp(usable_epsilon / epsilon, 0.0, 1.0)
    budget_pressure = 1.0 - budget_ratio

    memory_bias, memory_steps = _memory_performance_bias(memory)
    reasoning_steps.extend(memory_steps)
    performance_pressure = _clamp(performance_pressure + memory_bias, 0.0, 1.0)

    reasoning_steps.append(
        f"Inference: risk={risk_pressure:.2f}, performance={performance_pressure:.2f}, "
        f"sparse_labels={sparse_label_pressure:.2f}, budget_pressure={budget_pressure:.2f}."
    )

    min_noise = float(policy_constraints.get("min_noise_multiplier", 0.0))
    max_noise = max(min_noise, float(policy_constraints.get("max_noise_multiplier", max(dp_noise_multiplier, 0.05))))
    target_noise = dp_noise_multiplier
    if budget_pressure >= 0.5:
        target_noise = dp_noise_multiplier + (max_noise - dp_noise_multiplier) * budget_pressure
        reasoning_steps.append("Rule: privacy budget tightening → increase DP noise within policy bounds.")
    elif performance_pressure >= 0.45 and budget_pressure < 0.4:
        target_noise = dp_noise_multiplier - (dp_noise_multiplier - min_noise) * performance_pressure * 0.6
        reasoning_steps.append("Rule: weak local quality with budget headroom → reduce noise to preserve signal.")
    target_noise = _clamp(target_noise, min_noise, max_noise)

    adaptivity_score = _clamp(
        (performance_pressure * 0.4) + (sparse_label_pressure * 0.35) + (risk_pressure * 0.25),
        0.0,
        1.0,
    )
    local_epochs = default_epochs
    if adaptivity_score >= 0.35:
        local_epochs += 1
        reasoning_steps.append("Rule: moderate adaptivity score → allocate one additional local epoch.")
    if adaptivity_score >= 0.7:
        local_epochs += 1
        reasoning_steps.append("Rule: high adaptivity score → allocate a second additional local epoch.")
    local_epochs = min(local_epochs, max_epochs)
    if budget_pressure >= 0.85:
        local_epochs = min(local_epochs, max(default_epochs, 2))
        reasoning_steps.append("Rule: severe budget pressure → cap epoch count to limit privacy spend.")

    selected_strategy = str(context.get("selected_strategy", "FedAvg"))
    global_model_loaded = bool(context.get("global_model_loaded", False))
    local_training_strategy = selected_strategy
    if global_model_loaded and (
        selected_strategy == "FedProxGNN" or sparse_label_pressure >= 0.6 or performance_pressure >= 0.6
    ):
        local_training_strategy = "FedProxGNN"
        reasoning_steps.append("Rule: global reference available with heterogeneity/sparsity → select FedProxGNN.")

    fedprox_mu = fedprox_mu_default
    if local_training_strategy == "FedProxGNN":
        fedprox_mu = round(max(0.25, fedprox_mu * (1.0 + (0.5 * sparse_label_pressure))), 4)

    pseudo_label_weight = 0.0
    pseudo_label_confidence = pseudo_label_confidence_default
    if sparse_label_pressure >= 0.25:
        pseudo_label_weight = round(_clamp(pseudo_label_weight_default + (0.25 * sparse_label_pressure), 0.1, 0.75), 4)
        pseudo_label_confidence = round(
            _clamp(
                pseudo_label_confidence_default - (0.15 * sparse_label_pressure) + (0.05 * performance_pressure),
                0.7,
                0.97,
            ),
            4,
        )
        reasoning_steps.append("Rule: sparse labels detected → enable semi-supervised pseudo-label training.")

    run_post_round_inference = auto_alert and (
        risk_pressure >= 0.2 or performance_pressure >= 0.5 or sparse_label_pressure >= 0.5
    )
    post_round_inference_limit = max(
        alert_publish_limit,
        min(25, alert_publish_limit + int(risk_pressure * 10) + int(sparse_label_pressure * 5)),
    )
    if run_post_round_inference:
        reasoning_steps.append("Action: schedule post-round inference sweep for fraud alert publishing.")

    if len(reasoning_steps) == 1:
        reasoning_steps.append("Action: stable local conditions → lightweight round configuration.")

    confidence = round(0.5 + (adaptivity_score * 0.5), 4)
    reasoning_steps.append(f"Decision confidence: {confidence:.2f} (engine={REASONING_ENGINE_ID}).")

    return {
        "risk_pressure": round(risk_pressure, 4),
        "performance_pressure": round(performance_pressure, 4),
        "sparse_label_pressure": round(sparse_label_pressure, 4),
        "budget_pressure": round(budget_pressure, 4),
        "plan_confidence": confidence,
        "local_epochs": int(local_epochs),
        "noise_multiplier": round(target_noise, 6),
        "local_training_strategy": local_training_strategy,
        "fedprox_mu": round(fedprox_mu, 4),
        "pseudo_label_weight": round(pseudo_label_weight, 4),
        "pseudo_label_confidence": round(pseudo_label_confidence, 4),
        "run_post_round_inference": bool(run_post_round_inference),
        "post_round_inference_limit": int(post_round_inference_limit),
        "reasoning_steps": reasoning_steps,
        "confidence": confidence,
    }


def infer_participation(context: Dict[str, Any], memory: AgentMemory) -> Tuple[bool, List[str], str, float]:
    steps: List[str] = ["Perception: evaluating participation constraints and historical context."]
    hard_allowed = bool(context.get("hard_constraints_passed", True))
    if not hard_allowed:
        reason = str(context.get("hard_constraint_reason", "Hard participation constraints failed."))
        steps.append(f"Action: reject participation — {reason}")
        return False, steps, reason, 1.0

    last_metrics = context.get("last_metrics", {}) or {}
    if isinstance(last_metrics, dict):
        last_accuracy = float(last_metrics.get("accuracy", 1.0))
        if last_accuracy < 0.55:
            steps.append(
                f"Inference: last round accuracy ({last_accuracy:.3f}) is critically low; "
                "agent defers participation to avoid amplifying poor updates."
            )
            return (
                False,
                steps,
                "Participation rejected: autonomous agent deferred due to critically low prior round quality",
                0.85,
            )

    memory_bias, memory_steps = _memory_performance_bias(memory)
    steps.extend(memory_steps)
    if memory_bias >= 0.15:
        checks = context.get("checks", {})
        privacy = checks.get("privacy_budget", {}) if isinstance(checks, dict) else {}
        remaining = float(privacy.get("remaining_epsilon", 1.0))
        if remaining < 0.5:
            steps.append("Action: reject — memory and privacy signals both indicate high-risk participation.")
            return (
                False,
                steps,
                "Participation rejected: memory-informed risk assessment with tight privacy budget",
                0.8,
            )

    steps.append("Action: approve participation — constraints satisfied and risk within autonomous tolerance.")
    return True, steps, "Participation approved by autonomous expert inference engine", 0.9


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
