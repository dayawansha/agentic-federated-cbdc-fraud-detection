# Import the standard 'random' module to generate random choices (used for exploration in RL)
import random
# Import helper types for type-hinting (helps developers see what types are expected, but doesn't change runtime behavior)
from typing import Any, Dict, List, Tuple
# Import the custom memory module where the agent stores its experience/Q-tables
from shared.reasoning.memory import AgentMemory

class QLearningRLAgent:
    """
    A self-contained Q-learning agent for tuning training parameters.
    Discretizes the continuous pressure metrics into discrete states and selects adjustment actions.
    
    Explanation for non-Python/non-RL readers:
    - Reinforcement Learning (RL) is like training a dog: the agent takes actions, gets rewards, and learns what actions are best.
    - 'Q-learning' is a specific way of doing this. It keeps a table (a grid of numbers) where:
        - The rows are "States" (the situation the agent is currently in, e.g., low battery, high pressure).
        - The columns are "Actions" (what the agent can do, e.g., run faster, run private, do nothing).
        - The cells contain a score (called a 'Q-value') representing how good that action is for that state.
    """
    def __init__(self, learning_rate: float = 0.2, discount_factor: float = 0.9, epsilon: float = 0.15):
        # 'self.alpha' is the learning rate (how fast the agent updates its beliefs when it gets a reward).
        # A value of 0.2 means it changes its score by 20% of the new experience.
        self.alpha = learning_rate
        
        # 'self.gamma' is the discount factor (how much the agent cares about future rewards vs. immediate rewards).
        # A value of 0.9 means future rewards are worth 90% of their face value.
        self.gamma = discount_factor
        
        # 'self.epsilon' is the exploration rate (probability of choosing a random action to try new things).
        # A value of 0.15 means 15% of the time, the agent tries a random action; 85% of the time, it picks the best known action.
        self.epsilon = epsilon
        
        # The agent has 4 possible actions it can take (detailed below)
        # Action 0: Do nothing (keep parameters as is)
        # Action 1: Aggressive (train more epochs, reduce differential privacy noise, reduce proximal regularization)
        # Action 2: Private/Conservative (train fewer epochs, increase differential privacy noise, increase regularization)
        # Action 3: Robust Semi-Supervised (increase regularization, increase pseudo-labeling weight, train more epochs)
        self.num_actions = 4

    def _get_q_table(self, memory: AgentMemory) -> Dict[str, List[float]]:
        # In Python, a 'dict' (dictionary) holds key-value pairs (like a real dictionary where you look up a word/key to find its definition/value).
        # We store the Q-table inside the agent's persistent memory object so it isn't lost between rounds.
        if not hasattr(memory, "rl_q_table"):
            # If the memory object doesn't have an "rl_q_table" attribute yet, create an empty dictionary
            setattr(memory, "rl_q_table", {})
        return getattr(memory, "rl_q_table")

    def get_state(self, performance_pressure: float, sparse_label_pressure: float, budget_pressure: float) -> str:
        # RL requires discrete states, but our system gets real numbers (decimals between 0.0 and 1.0) for pressures.
        # Here we 'discretize' them: if a pressure is >= 0.5, we label it 'H' (High), otherwise 'L' (Low).
        perf_bin = "H" if performance_pressure >= 0.5 else "L"
        sparse_bin = "H" if sparse_label_pressure >= 0.5 else "L"
        budget_bin = "H" if budget_pressure >= 0.5 else "L"
        
        # Combine the 3 bins into a single text string (a State ID) like "perf:H|sparse:L|budget:H"
        return f"perf:{perf_bin}|sparse:{sparse_bin}|budget:{budget_bin}"

    def select_action(self, memory: AgentMemory, state: str) -> int:
        # Get the Q-table from memory
        q_table = self._get_q_table(memory)
        
        # If we have never seen this state before, initialize its action scores to all 0.0
        if state not in q_table:
            q_table[state] = [0.0] * self.num_actions

        # Epsilon-Greedy strategy: choose whether to explore (random action) or exploit (best action)
        if random.random() < self.epsilon:
            # 15% chance: Pick a random integer from 0 to 3
            return random.randint(0, self.num_actions - 1)
        
        # 85% chance: Find the action(s) with the highest score (Q-value)
        max_q = max(q_table[state])
        
        # Collect all actions that have that maximum score (in case there is a tie)
        actions_with_max_q = [i for i, q in enumerate(q_table[state]) if q == max_q]
        
        # Pick randomly among the actions that tied for the best score
        return random.choice(actions_with_max_q)

    def update(self, memory: AgentMemory, prev_state: str, action: int, reward: float, next_state: str) -> None:
        # Retrieve the Q-table
        q_table = self._get_q_table(memory)
        
        # Make sure both the previous state and new state exist in the Q-table
        if prev_state not in q_table:
            q_table[prev_state] = [0.0] * self.num_actions
        if next_state not in q_table:
            q_table[next_state] = [0.0] * self.num_actions

        # Temporal Difference (TD) Q-learning update formula:
        # New Q = Old Q + Alpha * (Reward + Gamma * Max Q of Next State - Old Q)
        max_next_q = max(q_table[next_state])
        old_q = q_table[prev_state][action]
        q_table[prev_state][action] = old_q + self.alpha * (reward + self.gamma * max_next_q - old_q)

    def apply_action_adjustments(self, action: int, plan: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        # Take the standard training plan dictionary and create a copy to modify
        adjusted_plan = dict(plan)
        steps = [] # A list of text steps to explain what we did (for debugging/logs)
        
        if action == 0:
            steps.append("RL Action: 0 (No adjustments applied, utilizing standard inference rules).")
        elif action == 1:
            # Action 1: Aggressive
            # - Increase local training epochs by 1 (max cap of 10)
            # - Decrease Differential Privacy noise multiplier by 0.005 (minimum of 0.0)
            # - Decrease FedProx mu regularization by 0.25 (minimum of 0.0)
            adjusted_plan["local_epochs"] = min(adjusted_plan["local_epochs"] + 1, 10)
            adjusted_plan["noise_multiplier"] = max(0.0, adjusted_plan["noise_multiplier"] - 0.005)
            adjusted_plan["fedprox_mu"] = max(0.0, adjusted_plan["fedprox_mu"] - 0.25)
            steps.append("RL Action: 1 (Aggressive training adjustments: epochs+1, noise-0.005, fedprox_mu-0.25).")
        elif action == 2:
            # Action 2: Private/Conservative
            # - Decrease epochs by 1 (minimum of 1)
            # - Increase Differential Privacy noise multiplier by 0.01 (maximum of 5.0)
            # - Increase regularization mu by 0.25 (maximum of 10.0)
            adjusted_plan["local_epochs"] = max(1, adjusted_plan["local_epochs"] - 1)
            adjusted_plan["noise_multiplier"] = min(5.0, adjusted_plan["noise_multiplier"] + 0.01)
            adjusted_plan["fedprox_mu"] = min(10.0, adjusted_plan["fedprox_mu"] + 0.25)
            steps.append("RL Action: 2 (Conservative/Private adjustments: epochs-1, noise+0.01, fedprox_mu+0.25).")
        elif action == 3:
            # Action 3: Robust Semi-Supervised (designed for learning when we have very few labels)
            # - Increase regularizer mu by 0.5 (max 10.0)
            # - Increase the weight of pseudo-labels by 0.15 (max 1.0)
            # - Increase local epochs by 1 (max 10)
            adjusted_plan["fedprox_mu"] = min(10.0, adjusted_plan["fedprox_mu"] + 0.5)
            adjusted_plan["pseudo_label_weight"] = min(1.0, adjusted_plan["pseudo_label_weight"] + 0.15)
            adjusted_plan["local_epochs"] = min(adjusted_plan["local_epochs"] + 1, 10)
            steps.append("RL Action: 3 (Robust Semi-Supervised adjustments: fedprox_mu+0.5, pseudo_label_weight+0.15, epochs+1).")
        
        # Return the adjusted plan dictionary and the text log steps as a pair (Tuple)
        return adjusted_plan, steps

# Instantiate one global instance of the RL agent that can be imported/used by other parts of the system
rl_agent = QLearningRLAgent()
