# Import Python's built-in logging module (used to write logs/status messages during execution)
import logging
# Import type-hinting annotations (tells developers the expected types of dictionary keys, values, etc.)
from typing import Any, Dict, List, Set

# Import the inference functions from our rules file.
# The 'shared/reasoning/inference_rules.py' file contains the hard rules that make decisions.
from shared.reasoning.inference_rules import (
    REASONING_ENGINE_ID,
    infer_aggregation_strategy,
    infer_coordinator_round,
    infer_local_training_plan,
    infer_participation,
)
# Import memory managers to get or store agent history
from shared.reasoning.memory import get_agent_memory
# Import schemas (Pydantic classes that validate structure/data types of our outputs)
from shared.reasoning.schemas import (
    AggregationStrategyDecision,
    CoordinatorRoundDecision,
    LocalTrainingPlanDecision,
    ParticipationDecisionReasoning,
)

# Import the Q-learning reinforcement learning agent instance we just commented
from shared.reasoning.rl import rl_agent

# Set up a logger specifically for this file's namespace
logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Autonomous reasoning engine for coordinator and bank-node agents.

    Uses a self-contained expert-inference pipeline (perception → memory → rules → action).
    No external LLM or third-party inference APIs are used.
    
    For non-Python readers:
    - This class acts as the "brain" for the bank agents (local-agent) and the central manager (coordinator).
    - It decides:
      1) Whether a bank should participate in a round.
      2) How to tune the training parameters (using rules + reinforcement learning).
      3) How the coordinator aggregates models.
      4) Which agents the coordinator selects.
    """

    def __init__(self, agent_id: str, role: str):
        # 'self.agent_id' holds the name/id of the bank (e.g. "bank_1")
        self.agent_id = agent_id
        # 'self.role' holds the role (e.g. "coordinator" or "local_agent")
        self.role = role
        # Retrieve the memory object associated with this agent from memory storage
        self.memory = get_agent_memory(agent_id)

    @property
    def provider(self) -> str:
        # A 'property' is a special Python method that can be accessed like a variable (without parentheses)
        return REASONING_ENGINE_ID

    async def reason_local_training_plan(self, context: Dict[str, Any]) -> LocalTrainingPlanDecision:
        """
        Decides the training parameters (epochs, DP noise, regularization mu) for a bank node.
        Includes a Reinforcement Learning feedback loop to optimize these parameters over rounds.
        """
        # First, infer the baseline plan using the static rules in inference_rules.py
        plan = infer_local_training_plan(context, self.memory)
        
        # Check if RL (Reinforcement Learning) is enabled in the configuration
        if not context.get("rl_enabled", True):
            # If RL is disabled, simply validate the raw rule-based plan and save it to memory
            decision = LocalTrainingPlanDecision.model_validate(plan)
            decision.provider = self.provider
            self.memory.remember(
                {
                    "summary": (
                        f"Local plan (RL disabled): epochs={decision.local_epochs}, strategy={decision.local_training_strategy}, "
                        f"noise={decision.noise_multiplier}"
                    ),
                    "decision": decision.model_dump(),
                    "previous_metrics": context.get("previous_metrics", {}),
                },
                long_term=True,
            )
            return decision

        # --- RL Adaptive Tuning Integration ---
        # Read the "pressures" derived by the rules. Pressures are numbers indicating problems:
        # - performance_pressure: global model accuracy is low
        # - sparse_label_pressure: the bank has very few labeled fraudulent transactions
        # - budget_pressure: differential privacy budget is running low
        perf_p = plan.get("performance_pressure", 0.0)
        sparse_p = plan.get("sparse_label_pressure", 0.0)
        budget_p = plan.get("budget_pressure", 0.0)
        
        # Discretize these continuous pressures into a single text State (e.g., "perf:H|sparse:L|budget:L")
        current_state = rl_agent.get_state(perf_p, sparse_p, budget_p)
        
        # Check if we have feedback from prior round execution (i.e. did we make a decision in the previous round?)
        if hasattr(self.memory, "last_rl_state") and hasattr(self.memory, "last_rl_action"):
            # Get the metrics from the previous round (accuracy, loss) and the current round's start metrics
            prev_metrics = getattr(self.memory, "last_rl_metrics", {}) or {}
            curr_metrics = context.get("previous_metrics", {}) or {}
            
            prev_acc = float(prev_metrics.get("accuracy", 0.5))
            curr_acc = float(curr_metrics.get("accuracy", 0.5))
            
            prev_loss = float(prev_metrics.get("loss", 1.0))
            curr_loss = float(curr_metrics.get("loss", 1.0))
            
            # --- Reward Calculation ---
            # The agent is rewarded if accuracy improved (curr_acc - prev_acc > 0)
            # and penalized if loss increased (curr_loss - prev_loss > 0)
            reward = (curr_acc - prev_acc) * 5.0 - (curr_loss - prev_loss) * 0.5
            
            # Update the Q-table with the reward we just earned for taking last_rl_action in last_rl_state
            rl_agent.update(
                self.memory,
                self.memory.last_rl_state,
                self.memory.last_rl_action,
                reward,
                current_state
            )
            # Log the update so developers can monitor the learning process in the console/logs
            logger.info(
                f"RL Update [{self.agent_id}]: state={self.memory.last_rl_state} "
                f"action={self.memory.last_rl_action} reward={reward:.3f} next_state={current_state}"
            )
            
        # Select the next action (0 to 3) using the Q-learning policy
        action = rl_agent.select_action(self.memory, current_state)
        
        # Apply the adjustments associated with the chosen action to our training parameters
        adjusted_plan, rl_steps = rl_agent.apply_action_adjustments(action, plan)
        
        # If the plan has a list of reasoning steps (for explainability), inject our RL logs into it
        if "reasoning_steps" in adjusted_plan:
            steps_list = list(adjusted_plan["reasoning_steps"])
            # Insert RL decision steps right before the confidence step
            if steps_list and "Decision confidence:" in steps_list[-1]:
                steps_list = steps_list[:-1] + rl_steps + [steps_list[-1]]
            else:
                steps_list.extend(rl_steps)
            adjusted_plan["reasoning_steps"] = steps_list

        # Save the current RL state, action, and metrics so we can calculate the reward in the next round
        self.memory.last_rl_state = current_state
        self.memory.last_rl_action = action
        self.memory.last_rl_metrics = context.get("previous_metrics", {}) or {}

        # Validate our adjusted plan against our Pydantic schema and save it to memory
        decision = LocalTrainingPlanDecision.model_validate(adjusted_plan)
        decision.provider = self.provider
        self.memory.remember(
            {
                "summary": (
                    f"Local plan (with RL action {action}): epochs={decision.local_epochs}, strategy={decision.local_training_strategy}, "
                    f"noise={decision.noise_multiplier}"
                ),
                "decision": decision.model_dump(),
                "previous_metrics": context.get("previous_metrics", {}),
            },
            long_term=True,
        )
        return decision

    async def reason_participation(self, context: Dict[str, Any]) -> ParticipationDecisionReasoning:
        """
        Decides whether a bank node should participate in the current learning round based on policies & constraints.
        """
        # Call rule-based function to check if CPU/battery/privacy budgets allow participation
        participate, steps, rationale, confidence = infer_participation(context, self.memory)
        
        # Construct the reasoning decision response
        decision = ParticipationDecisionReasoning(
            participate=participate,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=rationale,
        )
        # Store in the agent's long-term memory for auditing/tracking
        self.memory.remember(
            {"summary": f"Participation decision: participate={decision.participate}", "decision": decision.model_dump()},
            long_term=True,
        )
        return decision

    async def reason_aggregation_strategy(
        self,
        valid_updates: List[Dict[str, Any]],
        policies: Dict[str, Any],
        current_strategy: str,
        supported_strategies: Set[str],
    ) -> AggregationStrategyDecision:
        """
        Decides which weight aggregation algorithm the coordinator should use (FedAvg, RobustMedian, etc.).
        """
        # Evaluate rules based on the reliability scores of reporting agents and policy requirements
        strategy, steps, confidence = infer_aggregation_strategy(
            valid_updates,
            policies,
            current_strategy,
            supported_strategies,
            self.memory,
        )
        # Construct output schema
        decision = AggregationStrategyDecision(
            aggregation_strategy=strategy,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=f"Autonomous coordinator selected {strategy} for aggregation.",
        )
        # Persist decision in memory
        self.memory.remember(
            {"summary": f"Aggregation strategy: {decision.aggregation_strategy}", "decision": decision.model_dump()},
            long_term=True,
        )
        return decision

    async def reason_coordinator_round(
        self,
        candidate_agents: List[str],
        policies: Dict[str, Any],
        agent_profiles: Dict[str, Dict[str, float]],
    ) -> CoordinatorRoundDecision:
        """
        Decides which bank nodes to invite to the current federated learning round.
        """
        # Evaluate compliance, reliability history, and online status to filter candidates
        selected, hint, escalate, steps, confidence = infer_coordinator_round(
            candidate_agents,
            policies,
            agent_profiles,
            self.memory,
        )
        # Construct output schema
        decision = CoordinatorRoundDecision(
            selected_agent_ids=selected,
            aggregation_strategy_hint=hint,
            escalate_anomaly_review=escalate,
            reasoning_steps=steps,
            confidence=confidence,
            provider=self.provider,
            rationale_summary=f"Coordinator autonomously selected {len(selected)} participating agent(s).",
        )
        # Persist in memory
        self.memory.remember(
            {"summary": decision.rationale_summary, "decision": decision.model_dump()},
            long_term=True,
        )
        return decision


# Create a dictionary to cache ReasoningEngine instances so we don't recreate them on every call
_ENGINES: Dict[str, ReasoningEngine] = {}


def get_reasoning_engine(agent_id: str, role: str) -> ReasoningEngine:
    """
    Helper function to get or create a ReasoningEngine for a specific agent/role combination.
    """
    key = f"{role}:{agent_id}"
    if key not in _ENGINES:
        _ENGINES[key] = ReasoningEngine(agent_id, role)
    return _ENGINES[key]
