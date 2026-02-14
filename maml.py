"""
MAML-Inspired Continuous Meta-Learning System for Supercoder + Qwen3-Coder-Next

Inspired by La-MAML (Look-ahead MAML for Continual Learning, NeurIPS 2020)
adapted for LLM-based agentic coding workflows.

Since we can't do gradient-based fine-tuning at runtime on an API-served LLM,
this system implements "prompt-space MAML" — a meta-learning approach that:

1. Learns per-task adaptation strategies (which prompts/context work best)
2. Maintains a replay buffer of high-value task experiences
3. Adapts system prompts based on accumulated task performance
4. Tracks per-tool, per-language, per-pattern "learning rates" (confidence weights)
5. Implements experience replay for catastrophic forgetting prevention
6. Provides adaptive context injection based on task similarity

Architecture:
- TaskAdaptation: Records how a task was approached and its outcome
- MetaLearner: The core MAML engine that learns from task outcomes
- ReplayBuffer: Experience replay for continual learning
- AdaptivePromptBuilder: Generates optimized prompts based on learned patterns
- PerformanceTracker: Tracks metrics across sessions for learning signal

Storage: ~/.supercoder/maml/
"""

from __future__ import annotations
import json
import time
import math
import hashlib
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import Counter, defaultdict
import threading
import random


# ==============================================================================
# Constants
# ==============================================================================

MAML_DIR = Path.home() / ".supercoder" / "maml"
ADAPTATIONS_FILE = MAML_DIR / "adaptations.json"
META_PARAMS_FILE = MAML_DIR / "meta_params.json"
REPLAY_BUFFER_FILE = MAML_DIR / "replay_buffer.json"
PERFORMANCE_FILE = MAML_DIR / "performance.json"
STRATEGIES_FILE = MAML_DIR / "strategies.json"

# Meta-learning hyperparameters
META_LR = 0.1                # Meta learning rate (how fast we update global beliefs)
TASK_LR = 0.3                # Task-level learning rate (how much we adapt per task)
REPLAY_BUFFER_SIZE = 200     # Max experiences in replay buffer
REPLAY_SAMPLE_SIZE = 5       # How many past experiences to replay per new task
ADAPTATION_DECAY = 0.95      # Decay factor for old adaptations
MIN_CONFIDENCE = 0.1         # Minimum confidence for any learned parameter
MAX_CONFIDENCE = 0.95        # Maximum confidence cap
STRATEGY_HISTORY_SIZE = 100  # Max strategies to keep


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class TaskAdaptation:
    """Records how a specific task was approached and its outcome."""
    task_id: str
    timestamp: float
    task_description: str
    task_category: str              # "debugging", "web_app", "refactoring", etc.
    approach_taken: str             # Description of the approach
    tools_used: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)
    solutions_applied: List[str] = field(default_factory=list)
    outcome: str = "unknown"        # "success", "failure", "partial"
    quality_score: float = 0.5      # 0.0 - 1.0
    duration_seconds: float = 0.0
    context_injected: str = ""      # What memory/context was injected
    context_helped: bool = False    # Did the injected context help?

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TaskAdaptation":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class MetaParameter:
    """A learned parameter in the meta-learning system.

    Represents confidence/skill level in a specific dimension
    (tool usage, language, framework, error pattern, strategy).
    """
    name: str                   # e.g., "tool:fsWrite", "lang:python", "strategy:debug_first"
    category: str               # "tool", "language", "framework", "error_pattern", "strategy"
    value: float = 0.5          # Current learned value (0-1, higher = more confident/skilled)
    learning_rate: float = 0.1  # Per-parameter learning rate (La-MAML style)
    update_count: int = 0       # How many times this has been updated
    last_updated: float = 0.0
    success_rate: float = 0.5   # Running success rate when this param is involved
    decay_factor: float = 0.95  # How fast old signal decays

    def update(self, signal: float, task_lr: float = TASK_LR):
        """Update this parameter with a new learning signal.

        signal: 0.0 (negative) to 1.0 (positive)
        """
        # Adaptive learning rate: decreases as we get more confident
        effective_lr = self.learning_rate * task_lr
        if self.update_count > 20:
            effective_lr *= 0.5  # Slow down for well-established params

        # Update value with exponential moving average
        self.value = self.value * (1 - effective_lr) + signal * effective_lr
        self.value = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, self.value))

        # Update running success rate
        n = self.update_count + 1
        self.success_rate = self.success_rate + (signal - self.success_rate) / n

        self.update_count += 1
        self.last_updated = time.time()

    def decay(self):
        """Apply temporal decay — unused parameters drift toward 0.5."""
        hours_since = (time.time() - self.last_updated) / 3600 if self.last_updated else 0
        if hours_since > 24:  # Only decay after 24h of inactivity
            decay_steps = int(hours_since / 24)
            for _ in range(min(decay_steps, 10)):
                self.value = self.value * self.decay_factor + 0.5 * (1 - self.decay_factor)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MetaParameter":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Strategy:
    """A learned strategy — a pattern of approach that worked (or didn't)."""
    strategy_id: str
    description: str
    category: str               # Task category this applies to
    steps: List[str]            # Ordered steps/approach
    preconditions: List[str]    # When to use this strategy
    success_count: int = 0
    failure_count: int = 0
    avg_quality: float = 0.5
    last_used: float = 0.0

    @property
    def win_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        return self.success_count / total

    @property
    def confidence(self) -> float:
        """Bayesian confidence based on sample size."""
        total = self.success_count + self.failure_count
        # Wilson score interval lower bound (simplified)
        if total == 0:
            return 0.0
        z = 1.96  # 95% confidence
        p = self.win_rate
        denominator = 1 + z * z / total
        center = p + z * z / (2 * total)
        spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
        return max(0, (center - spread) / denominator)

    def to_dict(self) -> dict:
        d = {
            "strategy_id": self.strategy_id,
            "description": self.description,
            "category": self.category,
            "steps": self.steps,
            "preconditions": self.preconditions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_quality": self.avg_quality,
            "last_used": self.last_used,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Strategy":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ==============================================================================
# Replay Buffer (Experience Replay for Continual Learning)
# ==============================================================================

class ReplayBuffer:
    """
    Experience replay buffer inspired by La-MAML.
    Stores high-value task experiences and replays them during learning
    to prevent catastrophic forgetting.
    """

    def __init__(self, max_size: int = REPLAY_BUFFER_SIZE):
        self.max_size = max_size
        self.buffer: List[TaskAdaptation] = []
        self._priorities: List[float] = []  # Priority scores for sampling

    def add(self, adaptation: TaskAdaptation):
        """Add experience with priority-based eviction."""
        priority = self._compute_priority(adaptation)

        if len(self.buffer) >= self.max_size:
            # Evict lowest priority
            min_idx = self._priorities.index(min(self._priorities))
            if priority > self._priorities[min_idx]:
                self.buffer[min_idx] = adaptation
                self._priorities[min_idx] = priority
        else:
            self.buffer.append(adaptation)
            self._priorities.append(priority)

    def sample(self, n: int = REPLAY_SAMPLE_SIZE, category: str = None) -> List[TaskAdaptation]:
        """Sample experiences with priority-weighted sampling."""
        if not self.buffer:
            return []

        candidates = list(range(len(self.buffer)))
        if category:
            candidates = [i for i in candidates if self.buffer[i].task_category == category]
            if not candidates:
                candidates = list(range(len(self.buffer)))

        n = min(n, len(candidates))
        if n == 0:
            return []

        # Weighted sampling by priority
        weights = [self._priorities[i] for i in candidates]
        total_w = sum(weights)
        if total_w == 0:
            selected = random.sample(candidates, n)
        else:
            probs = [w / total_w for w in weights]
            selected = []
            for _ in range(n):
                r = random.random()
                cumulative = 0
                for i, p in zip(candidates, probs):
                    cumulative += p
                    if r <= cumulative and i not in selected:
                        selected.append(i)
                        break
            # Fill remaining if needed
            remaining = [i for i in candidates if i not in selected]
            while len(selected) < n and remaining:
                selected.append(remaining.pop(0))

        return [self.buffer[i] for i in selected]

    def _compute_priority(self, adaptation: TaskAdaptation) -> float:
        """Compute priority score for an experience."""
        priority = 0.5

        # High quality outcomes are more valuable
        priority += adaptation.quality_score * 0.3

        # Failures with solutions are extremely valuable (learning moments)
        if adaptation.outcome == "failure" and adaptation.solutions_applied:
            priority += 0.3
        elif adaptation.outcome == "success":
            priority += 0.2

        # Recency bonus
        age_hours = (time.time() - adaptation.timestamp) / 3600
        recency = math.exp(-age_hours / (24 * 7))  # ~1 week half-life
        priority += recency * 0.2

        return min(1.0, priority)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "buffer_size": len(self.buffer),
            "max_size": self.max_size,
            "categories": dict(Counter(a.task_category for a in self.buffer)),
            "avg_quality": round(sum(a.quality_score for a in self.buffer) / max(len(self.buffer), 1), 3),
            "success_rate": round(
                sum(1 for a in self.buffer if a.outcome == "success") / max(len(self.buffer), 1), 3
            ),
        }

    def save(self, path: Path = REPLAY_BUFFER_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.to_dict() for a in self.buffer]
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def load(self, path: Path = REPLAY_BUFFER_FILE):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.buffer = [TaskAdaptation.from_dict(d) for d in data]
                self._priorities = [self._compute_priority(a) for a in self.buffer]
            except Exception:
                pass


# ==============================================================================
# Core Meta-Learner
# ==============================================================================

class MetaLearner:
    """
    MAML-inspired meta-learning engine.

    Instead of gradient-based inner/outer loops on model weights,
    we maintain meta-parameters in "prompt space" — learned beliefs about:
    - Which tools work best for which tasks
    - Which approaches succeed for which categories
    - User-specific patterns and preferences
    - Error-solution mappings

    The inner loop (task adaptation) adjusts these for a specific task.
    The outer loop (meta update) updates global beliefs after task completion.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.meta_params: Dict[str, MetaParameter] = {}
        self.strategies: Dict[str, Strategy] = {}
        self.replay_buffer = ReplayBuffer()
        self.current_adaptation: Optional[TaskAdaptation] = None
        self.performance_log: List[Dict[str, Any]] = []
        self._initialized = False

    def initialize(self):
        """Load persisted meta-learning state."""
        if self._initialized:
            return
        with self._lock:
            MAML_DIR.mkdir(parents=True, exist_ok=True)
            self._load_meta_params()
            self._load_strategies()
            self.replay_buffer.load()
            self._load_performance()
            # Apply decay to old parameters
            for p in self.meta_params.values():
                p.decay()
            self._initialized = True

    def _load_meta_params(self):
        if META_PARAMS_FILE.exists():
            try:
                data = json.loads(META_PARAMS_FILE.read_text(encoding="utf-8"))
                self.meta_params = {k: MetaParameter.from_dict(v) for k, v in data.items()}
            except Exception:
                pass

    def _save_meta_params(self):
        data = {k: v.to_dict() for k, v in self.meta_params.items()}
        META_PARAMS_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def _load_strategies(self):
        if STRATEGIES_FILE.exists():
            try:
                data = json.loads(STRATEGIES_FILE.read_text(encoding="utf-8"))
                self.strategies = {k: Strategy.from_dict(v) for k, v in data.items()}
            except Exception:
                pass

    def _save_strategies(self):
        data = {k: v.to_dict() for k, v in self.strategies.items()}
        STRATEGIES_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def _load_performance(self):
        if PERFORMANCE_FILE.exists():
            try:
                self.performance_log = json.loads(PERFORMANCE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_performance(self):
        # Keep only recent entries
        self.performance_log = self.performance_log[-500:]
        PERFORMANCE_FILE.write_text(json.dumps(self.performance_log, indent=1), encoding="utf-8")

    def _get_or_create_param(self, name: str, category: str) -> MetaParameter:
        """Get existing param or create new one."""
        if name not in self.meta_params:
            self.meta_params[name] = MetaParameter(
                name=name,
                category=category,
                value=0.5,
                learning_rate=META_LR,
                last_updated=time.time(),
            )
        return self.meta_params[name]

    # --- Inner Loop: Task Adaptation ---

    def begin_task(self, description: str, category: str = "general") -> TaskAdaptation:
        """Start adapting to a new task (inner loop begins)."""
        self.initialize()
        with self._lock:
            task_id = hashlib.sha256(f"{time.time()}{description}".encode()).hexdigest()[:12]
            self.current_adaptation = TaskAdaptation(
                task_id=task_id,
                timestamp=time.time(),
                task_description=description[:500],
                task_category=category,
                approach_taken="",
            )
            return self.current_adaptation

    def record_tool_usage(self, tool_name: str):
        """Record tool usage during task."""
        if self.current_adaptation:
            self.current_adaptation.tools_used.append(tool_name)

    def record_file_modified(self, file_path: str):
        """Record file modification during task."""
        if self.current_adaptation:
            if file_path not in self.current_adaptation.files_modified:
                self.current_adaptation.files_modified.append(file_path)

    def record_error(self, error: str):
        """Record an error encountered during task."""
        if self.current_adaptation:
            self.current_adaptation.errors_encountered.append(error[:300])

    def record_solution(self, solution: str):
        """Record a solution applied during task."""
        if self.current_adaptation:
            self.current_adaptation.solutions_applied.append(solution[:300])

    def record_language(self, lang: str):
        if self.current_adaptation and lang not in self.current_adaptation.languages:
            self.current_adaptation.languages.append(lang)

    def record_framework(self, fw: str):
        if self.current_adaptation and fw not in self.current_adaptation.frameworks:
            self.current_adaptation.frameworks.append(fw)

    # --- Outer Loop: Meta Update ---

    def complete_task(self, outcome: str = "success", quality_score: float = 0.7):
        """
        Complete the current task and perform the meta-update (outer loop).
        This is where the actual "learning" happens.
        """
        if not self.current_adaptation:
            return

        with self._lock:
            adapt = self.current_adaptation
            adapt.outcome = outcome
            adapt.quality_score = quality_score
            adapt.duration_seconds = time.time() - adapt.timestamp

            # --- OUTER LOOP: Update meta-parameters ---

            signal = quality_score if outcome == "success" else (quality_score * 0.3)

            # Update tool parameters
            tool_counts = Counter(adapt.tools_used)
            for tool, count in tool_counts.items():
                param = self._get_or_create_param(f"tool:{tool}", "tool")
                # Tools used in successful tasks get positive signal
                tool_signal = signal * min(count / 3, 1.0)  # Cap influence
                param.update(tool_signal)

            # Update language parameters
            for lang in adapt.languages:
                param = self._get_or_create_param(f"lang:{lang}", "language")
                param.update(signal)

            # Update framework parameters
            for fw in adapt.frameworks:
                param = self._get_or_create_param(f"fw:{fw}", "framework")
                param.update(signal)

            # Update category parameters
            cat_param = self._get_or_create_param(f"cat:{adapt.task_category}", "category")
            cat_param.update(signal)

            # Update error-solution mappings
            for error in adapt.errors_encountered:
                err_key = self._normalize_error(error)
                param = self._get_or_create_param(f"err:{err_key}", "error_pattern")
                # Errors with solutions are positive signals
                if adapt.solutions_applied:
                    param.update(0.8)  # We learned to handle this
                else:
                    param.update(0.2)  # Still struggling

            # --- Experience Replay ---
            # Replay past experiences to prevent forgetting
            replayed = self.replay_buffer.sample(
                REPLAY_SAMPLE_SIZE, category=adapt.task_category
            )
            for past in replayed:
                past_signal = past.quality_score if past.outcome == "success" else 0.3
                # Gentle replay update (lower learning rate)
                for tool in set(past.tools_used):
                    param = self._get_or_create_param(f"tool:{tool}", "tool")
                    param.update(past_signal, task_lr=TASK_LR * 0.3)  # Reduced LR for replay

            # Add current experience to replay buffer
            self.replay_buffer.add(adapt)

            # --- Strategy Learning ---
            self._learn_strategy(adapt)

            # --- Log Performance ---
            self.performance_log.append({
                "task_id": adapt.task_id,
                "timestamp": adapt.timestamp,
                "category": adapt.task_category,
                "outcome": outcome,
                "quality": quality_score,
                "duration": adapt.duration_seconds,
                "tools_count": len(adapt.tools_used),
                "errors_count": len(adapt.errors_encountered),
                "solutions_count": len(adapt.solutions_applied),
            })

            # Persist everything
            self._save_meta_params()
            self._save_strategies()
            self.replay_buffer.save()
            self._save_performance()

            self.current_adaptation = None

    def _normalize_error(self, error: str) -> str:
        """Normalize error text to a canonical key."""
        import re
        # Extract error type
        m = re.search(r'(\w+(?:Error|Exception|Warning))', error)
        if m:
            return m.group(1).lower()
        # Fallback: hash
        return hashlib.sha256(error[:100].encode()).hexdigest()[:8]

    def _learn_strategy(self, adapt: TaskAdaptation):
        """Learn or update a strategy from task outcome."""
        # Build strategy description from task
        strategy_key = f"{adapt.task_category}:{self._strategy_fingerprint(adapt)}"

        if strategy_key in self.strategies:
            strat = self.strategies[strategy_key]
            if adapt.outcome == "success":
                strat.success_count += 1
            else:
                strat.failure_count += 1
            # Update average quality
            n = strat.success_count + strat.failure_count
            strat.avg_quality = strat.avg_quality + (adapt.quality_score - strat.avg_quality) / n
            strat.last_used = time.time()
        else:
            # New strategy
            steps = []
            if adapt.tools_used:
                # Extract unique tool sequence
                seen = set()
                for t in adapt.tools_used:
                    if t not in seen:
                        steps.append(f"Use {t}")
                        seen.add(t)
                        if len(steps) >= 8:
                            break

            self.strategies[strategy_key] = Strategy(
                strategy_id=strategy_key,
                description=adapt.task_description[:200],
                category=adapt.task_category,
                steps=steps,
                preconditions=[f"category={adapt.task_category}"],
                success_count=1 if adapt.outcome == "success" else 0,
                failure_count=0 if adapt.outcome == "success" else 1,
                avg_quality=adapt.quality_score,
                last_used=time.time(),
            )

        # Prune old strategies
        if len(self.strategies) > STRATEGY_HISTORY_SIZE:
            # Remove lowest confidence strategies
            sorted_strats = sorted(
                self.strategies.items(),
                key=lambda x: x[1].confidence
            )
            for key, _ in sorted_strats[:len(self.strategies) - STRATEGY_HISTORY_SIZE]:
                del self.strategies[key]

    def _strategy_fingerprint(self, adapt: TaskAdaptation) -> str:
        """Generate a fingerprint for the strategy used."""
        # Based on unique tools used (ordered by first appearance)
        seen = set()
        tools = []
        for t in adapt.tools_used:
            if t not in seen:
                tools.append(t)
                seen.add(t)
                if len(tools) >= 5:
                    break
        return "_".join(tools) if tools else "unknown"

    # --- Task Prediction & Guidance ---

    def get_task_guidance(self, description: str, category: str = "general") -> Dict[str, Any]:
        """
        Get meta-learned guidance for approaching a new task.
        This is the "fast adaptation" — using learned knowledge to guide behavior.
        """
        self.initialize()
        guidance = {
            "recommended_tools": [],
            "recommended_strategy": None,
            "confidence_level": 0.5,
            "past_similar_outcomes": [],
            "warnings": [],
            "meta_context": "",
        }

        # Find relevant meta-parameters
        cat_param = self.meta_params.get(f"cat:{category}")
        if cat_param:
            guidance["confidence_level"] = cat_param.value

        # Recommend tools based on learned parameters
        tool_params = {
            k: v for k, v in self.meta_params.items()
            if v.category == "tool" and v.value > 0.5 and v.update_count > 2
        }
        sorted_tools = sorted(tool_params.items(), key=lambda x: x[1].value, reverse=True)
        guidance["recommended_tools"] = [
            {"tool": k.replace("tool:", ""), "confidence": round(v.value, 2), "uses": v.update_count}
            for k, v in sorted_tools[:8]
        ]

        # Find best strategy for this category
        category_strategies = [
            s for s in self.strategies.values()
            if s.category == category and s.confidence > 0.3
        ]
        if category_strategies:
            best = max(category_strategies, key=lambda s: s.confidence)
            guidance["recommended_strategy"] = {
                "description": best.description,
                "steps": best.steps,
                "win_rate": round(best.win_rate, 2),
                "confidence": round(best.confidence, 2),
                "times_used": best.success_count + best.failure_count,
            }

        # Find similar past outcomes from replay buffer
        similar = self.replay_buffer.sample(3, category=category)
        for past in similar:
            guidance["past_similar_outcomes"].append({
                "description": past.task_description[:100],
                "outcome": past.outcome,
                "quality": past.quality_score,
                "tools_used": list(set(past.tools_used))[:5],
            })

        # Generate warnings from error patterns
        error_params = {
            k: v for k, v in self.meta_params.items()
            if v.category == "error_pattern" and v.value < 0.4
        }
        for k, v in error_params.items():
            err_type = k.replace("err:", "")
            guidance["warnings"].append(
                f"Watch for {err_type} — historically problematic (confidence: {round(v.value, 2)})"
            )

        # Build meta-context string for prompt injection
        guidance["meta_context"] = self._build_meta_context(category)

        return guidance

    def _build_meta_context(self, category: str) -> str:
        """Build a concise meta-context string for system prompt injection."""
        parts = []

        # Category experience
        cat_param = self.meta_params.get(f"cat:{category}")
        if cat_param and cat_param.update_count > 0:
            parts.append(
                f"[Meta-learned: {category} tasks — {cat_param.update_count} past experiences, "
                f"success rate: {round(cat_param.success_rate, 2)}]"
            )

        # Top strategies
        cat_strats = [
            s for s in self.strategies.values()
            if s.category == category and s.confidence > 0.4
        ]
        if cat_strats:
            best = max(cat_strats, key=lambda s: s.confidence)
            parts.append(f"[Best strategy: {', '.join(best.steps[:5])} (win rate: {round(best.win_rate, 2)})]")

        # Known error patterns
        err_parts = []
        for k, v in self.meta_params.items():
            if v.category == "error_pattern" and v.update_count > 2:
                err_type = k.replace("err:", "")
                if v.value > 0.6:
                    err_parts.append(f"{err_type} (handled)")
                elif v.value < 0.4:
                    err_parts.append(f"{err_type} (tricky)")
        if err_parts:
            parts.append(f"[Error experience: {', '.join(err_parts[:5])}]")

        return " ".join(parts)

    # --- Adaptive Prompt Building ---

    def build_adaptive_prompt_section(self, task_description: str, category: str = "general") -> str:
        """
        Build an adaptive section to inject into the system prompt.
        This is the key output of the MAML system — learned context that
        makes the model better at the current task.
        """
        self.initialize()
        sections = []

        guidance = self.get_task_guidance(task_description, category)

        if guidance["meta_context"]:
            sections.append(guidance["meta_context"])

        # Add recommended approach
        if guidance["recommended_strategy"]:
            strat = guidance["recommended_strategy"]
            if strat["confidence"] > 0.4:
                sections.append(
                    f"[Learned approach for {category}: {' → '.join(strat['steps'][:5])} "
                    f"(worked {round(strat['win_rate'] * 100)}% of the time)]"
                )

        # Add warnings
        if guidance["warnings"]:
            sections.append(f"[Warnings: {'; '.join(guidance['warnings'][:3])}]")

        # Add relevant past successes
        successes = [p for p in guidance["past_similar_outcomes"] if p["outcome"] == "success"]
        if successes:
            sections.append(
                f"[Similar past success: {successes[0]['description']} — "
                f"tools: {', '.join(successes[0]['tools_used'][:4])}]"
            )

        return "\n".join(sections) if sections else ""

    # --- Performance Analytics ---

    def get_learning_progress(self) -> Dict[str, Any]:
        """Get analytics on learning progress over time."""
        self.initialize()
        if not self.performance_log:
            return {"status": "No data yet", "sessions": 0}

        recent = self.performance_log[-50:]  # Last 50 tasks
        older = self.performance_log[:-50] if len(self.performance_log) > 50 else []

        recent_success = sum(1 for p in recent if p["outcome"] == "success") / max(len(recent), 1)
        older_success = sum(1 for p in older if p["outcome"] == "success") / max(len(older), 1) if older else 0

        recent_quality = sum(p["quality"] for p in recent) / max(len(recent), 1)
        older_quality = sum(p["quality"] for p in older) / max(len(older), 1) if older else 0

        recent_duration = sum(p["duration"] for p in recent) / max(len(recent), 1)
        older_duration = sum(p["duration"] for p in older) / max(len(older), 1) if older else 0

        return {
            "total_tasks": len(self.performance_log),
            "recent_success_rate": round(recent_success, 3),
            "older_success_rate": round(older_success, 3),
            "success_improvement": round(recent_success - older_success, 3),
            "recent_avg_quality": round(recent_quality, 3),
            "quality_improvement": round(recent_quality - older_quality, 3),
            "recent_avg_duration_s": round(recent_duration, 1),
            "duration_improvement": round(older_duration - recent_duration, 1),  # Lower is better
            "meta_params_count": len(self.meta_params),
            "strategies_count": len(self.strategies),
            "replay_buffer": self.replay_buffer.get_stats(),
            "top_skills": self._get_top_skills(),
            "growth_areas": self._get_growth_areas(),
        }

    def _get_top_skills(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get areas where the system is most confident."""
        sorted_params = sorted(
            self.meta_params.values(),
            key=lambda p: p.value * min(p.update_count / 5, 1.0),  # Weight by experience
            reverse=True
        )
        return [
            {"name": p.name, "confidence": round(p.value, 2), "uses": p.update_count}
            for p in sorted_params[:n] if p.update_count > 1
        ]

    def _get_growth_areas(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get areas where improvement is needed."""
        sorted_params = sorted(
            self.meta_params.values(),
            key=lambda p: p.value if p.update_count > 2 else 1.0  # Only flag well-sampled low params
        )
        return [
            {"name": p.name, "confidence": round(p.value, 2), "uses": p.update_count}
            for p in sorted_params[:n] if p.update_count > 2 and p.value < 0.5
        ]


# ==============================================================================
# Singleton Instance
# ==============================================================================

_maml_instance: Optional[MetaLearner] = None

def get_meta_learner() -> MetaLearner:
    """Get the global meta-learner instance."""
    global _maml_instance
    if _maml_instance is None:
        _maml_instance = MetaLearner()
    return _maml_instance
