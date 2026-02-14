"""
Episodic Memory System for Supercoder + Qwen3-Coder-Next

Inspired by EM-LLM (Human-inspired Episodic Memory for Infinite Context LLMs)
and adapted for agentic coding workflows.

Architecture:
- Episodes: Bounded segments of interaction (task start -> task end)
- Events: Individual meaningful units within episodes (tool calls, decisions, errors, solutions)
- Memory Index: Fast similarity-based retrieval using TF-IDF + cosine similarity
- Consolidation: Periodic compression of old episodes into semantic summaries
- Persistence: JSON-based storage in ~/.supercoder/memory/

The memory system captures:
1. What tasks were attempted and how they were solved
2. What errors occurred and how they were fixed
3. What tools were used in what contexts
4. User preferences and patterns
5. Project-specific knowledge (file structures, tech stacks, etc.)
"""

from __future__ import annotations
import json
import time
import hashlib
import re
import math
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import Counter, defaultdict
import threading

# ==============================================================================
# Constants
# ==============================================================================

MEMORY_DIR = Path.home() / ".supercoder" / "memory"
EPISODES_DIR = MEMORY_DIR / "episodes"
INDEX_FILE = MEMORY_DIR / "index.json"
CONSOLIDATED_FILE = MEMORY_DIR / "consolidated.json"
STATS_FILE = MEMORY_DIR / "stats.json"
PREFERENCES_FILE = MEMORY_DIR / "preferences.json"

MAX_EVENTS_PER_EPISODE = 200
MAX_ACTIVE_EPISODES = 50
CONSOLIDATION_THRESHOLD = 30  # Consolidate after this many episodes
SIMILARITY_THRESHOLD = 0.15
MAX_RECALL_RESULTS = 10
TOKEN_BUDGET_FOR_MEMORY = 2000  # Max tokens to inject from memory


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class Event:
    """A single meaningful unit within an episode."""
    timestamp: float
    event_type: str          # "tool_call", "tool_result", "error", "solution", "decision", "user_input", "model_output"
    content: str             # The actual content
    metadata: Dict[str, Any] = field(default_factory=dict)  # tool name, file paths, error types, etc.
    importance: float = 0.5  # 0.0 - 1.0, auto-computed

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(**d)


@dataclass
class Episode:
    """A bounded segment of interaction, typically one task/goal."""
    episode_id: str
    created_at: float
    updated_at: float
    title: str                          # Auto-generated summary of the episode
    tags: List[str] = field(default_factory=list)           # e.g., ["python", "web", "debugging", "react"]
    events: List[Event] = field(default_factory=list)
    outcome: str = "in_progress"        # "success", "failure", "abandoned", "in_progress"
    project_path: str = ""              # The working directory
    model_used: str = ""                # Which model handled this
    consolidated_summary: str = ""      # Set after consolidation
    importance_score: float = 0.5       # Overall importance

    def add_event(self, event: Event):
        self.events.append(event)
        self.updated_at = time.time()
        # Cap events
        if len(self.events) > MAX_EVENTS_PER_EPISODE:
            # Keep first 10 (context) + last 150 (recent)
            self.events = self.events[:10] + self.events[-150:]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Episode":
        events = [Event.from_dict(e) for e in d.pop("events", [])]
        ep = cls(**{k: v for k, v in d.items() if k != "events"}, events=events)
        return ep

    def get_text_for_indexing(self) -> str:
        """Extract searchable text from this episode."""
        parts = [self.title]
        parts.extend(self.tags)
        for ev in self.events:
            if ev.event_type in ("error", "solution", "decision", "user_input"):
                parts.append(ev.content[:500])
            if ev.metadata.get("tool_name"):
                parts.append(ev.metadata["tool_name"])
            if ev.metadata.get("file_paths"):
                parts.extend(ev.metadata["file_paths"])
        if self.consolidated_summary:
            parts.append(self.consolidated_summary)
        return " ".join(parts)


# ==============================================================================
# TF-IDF Similarity Engine (no external deps)
# ==============================================================================

class TFIDFIndex:
    """Lightweight TF-IDF index for memory retrieval. No numpy/sklearn needed."""

    def __init__(self):
        self.documents: Dict[str, str] = {}      # doc_id -> text
        self.idf: Dict[str, float] = {}
        self.tf_cache: Dict[str, Dict[str, float]] = {}
        self._dirty = True

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric."""
        return re.findall(r'[a-z0-9_]+', text.lower())

    def add_document(self, doc_id: str, text: str):
        self.documents[doc_id] = text
        self._dirty = True

    def remove_document(self, doc_id: str):
        self.documents.pop(doc_id, None)
        self.tf_cache.pop(doc_id, None)
        self._dirty = True

    def _rebuild(self):
        """Rebuild IDF and TF caches."""
        if not self._dirty:
            return
        n = len(self.documents)
        if n == 0:
            self._dirty = False
            return

        # Document frequency
        df: Dict[str, int] = Counter()
        self.tf_cache.clear()

        for doc_id, text in self.documents.items():
            tokens = self._tokenize(text)
            tf = Counter(tokens)
            total = len(tokens) or 1
            self.tf_cache[doc_id] = {t: c / total for t, c in tf.items()}
            for t in set(tokens):
                df[t] += 1

        # IDF with smoothing
        self.idf = {t: math.log((n + 1) / (freq + 1)) + 1 for t, freq in df.items()}
        self._dirty = False

    def query(self, text: str, top_k: int = MAX_RECALL_RESULTS) -> List[Tuple[str, float]]:
        """Find most similar documents to query text. Returns [(doc_id, score)]."""
        self._rebuild()
        if not self.documents:
            return []

        query_tokens = self._tokenize(text)
        if not query_tokens:
            return []

        query_tf = Counter(query_tokens)
        total_q = len(query_tokens)
        query_vec = {t: (c / total_q) * self.idf.get(t, 0) for t, c in query_tf.items()}

        # Magnitude of query vector
        q_mag = math.sqrt(sum(v * v for v in query_vec.values()))
        if q_mag == 0:
            return []

        scores = []
        for doc_id, doc_tf in self.tf_cache.items():
            # Dot product
            dot = sum(query_vec.get(t, 0) * doc_tf.get(t, 0) * self.idf.get(t, 0)
                      for t in set(query_vec) & set(doc_tf))
            # Doc magnitude
            d_mag = math.sqrt(sum((v * self.idf.get(t, 0)) ** 2 for t, v in doc_tf.items()))
            if d_mag == 0:
                continue
            cosine = dot / (q_mag * d_mag)
            if cosine >= SIMILARITY_THRESHOLD:
                scores.append((doc_id, cosine))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ==============================================================================
# Importance Scoring
# ==============================================================================

def compute_event_importance(event: Event) -> float:
    """Auto-score event importance based on type and content."""
    base_scores = {
        "error": 0.8,
        "solution": 0.9,
        "decision": 0.7,
        "user_input": 0.6,
        "tool_call": 0.3,
        "tool_result": 0.3,
        "model_output": 0.4,
    }
    score = base_scores.get(event.event_type, 0.5)

    content_lower = event.content.lower()

    # Boost for error-related content
    if any(w in content_lower for w in ["error", "exception", "traceback", "failed", "bug"]):
        score = min(score + 0.2, 1.0)

    # Boost for fix/solution content
    if any(w in content_lower for w in ["fixed", "solved", "resolved", "workaround", "solution"]):
        score = min(score + 0.2, 1.0)

    # Boost for important tools
    tool = event.metadata.get("tool_name", "")
    if tool in ("fsWrite", "strReplace", "executePwsh"):
        score = min(score + 0.1, 1.0)

    return round(score, 2)


def compute_episode_importance(episode: Episode) -> float:
    """Score overall episode importance."""
    if not episode.events:
        return 0.3

    # Average event importance
    avg = sum(e.importance for e in episode.events) / len(episode.events)

    # Bonus for successful outcomes
    if episode.outcome == "success":
        avg = min(avg + 0.15, 1.0)
    elif episode.outcome == "failure":
        avg = min(avg + 0.1, 1.0)  # Failures are also valuable to remember

    # Bonus for having errors + solutions (learning moments)
    has_error = any(e.event_type == "error" for e in episode.events)
    has_solution = any(e.event_type == "solution" for e in episode.events)
    if has_error and has_solution:
        avg = min(avg + 0.2, 1.0)

    return round(avg, 2)


# ==============================================================================
# Episode Consolidation (Compression)
# ==============================================================================

def consolidate_episode(episode: Episode) -> str:
    """Compress an episode into a concise semantic summary."""
    parts = [f"Task: {episode.title}"]
    parts.append(f"Outcome: {episode.outcome}")
    if episode.project_path:
        parts.append(f"Project: {episode.project_path}")
    if episode.tags:
        parts.append(f"Tags: {', '.join(episode.tags)}")

    # Extract key events
    errors = [e.content[:200] for e in episode.events if e.event_type == "error"]
    solutions = [e.content[:200] for e in episode.events if e.event_type == "solution"]
    decisions = [e.content[:200] for e in episode.events if e.event_type == "decision"]

    tools_used = Counter(
        e.metadata.get("tool_name", "unknown")
        for e in episode.events if e.event_type == "tool_call"
    )

    if errors:
        parts.append(f"Errors encountered ({len(errors)}): " + "; ".join(errors[:3]))
    if solutions:
        parts.append(f"Solutions applied ({len(solutions)}): " + "; ".join(solutions[:3]))
    if decisions:
        parts.append(f"Key decisions ({len(decisions)}): " + "; ".join(decisions[:3]))
    if tools_used:
        top_tools = tools_used.most_common(5)
        parts.append(f"Tools: {', '.join(f'{t}({c})' for t, c in top_tools)}")

    # Extract file paths mentioned
    all_paths: Set[str] = set()
    for e in episode.events:
        if e.metadata.get("file_paths"):
            all_paths.update(e.metadata["file_paths"][:5])
    if all_paths:
        parts.append(f"Files: {', '.join(list(all_paths)[:8])}")

    return " | ".join(parts)


# ==============================================================================
# User Preference Tracker
# ==============================================================================

class PreferenceTracker:
    """Tracks user preferences and patterns over time."""

    def __init__(self):
        self.data: Dict[str, Any] = {
            "preferred_model": None,
            "common_languages": Counter(),
            "common_frameworks": Counter(),
            "tool_frequency": Counter(),
            "error_patterns": Counter(),       # Common errors the user hits
            "solution_patterns": Counter(),    # Common solutions that work
            "project_types": Counter(),
            "interaction_style": {
                "avg_prompt_length": 0,
                "prefers_auto_mode": False,
                "prefers_verbose": False,
            },
            "total_sessions": 0,
            "total_tasks_completed": 0,
            "total_errors_resolved": 0,
        }

    def update_from_episode(self, episode: Episode):
        self.data["total_sessions"] += 1
        if episode.outcome == "success":
            self.data["total_tasks_completed"] += 1

        for tag in episode.tags:
            # Infer category
            langs = {"python", "javascript", "typescript", "java", "go", "rust", "c", "cpp", "ruby", "php"}
            frameworks = {"react", "nextjs", "vue", "angular", "django", "flask", "express", "fastapi", "svelte"}
            if tag.lower() in langs:
                self.data["common_languages"][tag.lower()] += 1
            elif tag.lower() in frameworks:
                self.data["common_frameworks"][tag.lower()] += 1

        for ev in episode.events:
            if ev.event_type == "tool_call" and ev.metadata.get("tool_name"):
                self.data["tool_frequency"][ev.metadata["tool_name"]] += 1
            if ev.event_type == "error":
                # Extract error type
                err_type = _extract_error_type(ev.content)
                if err_type:
                    self.data["error_patterns"][err_type] += 1
                    self.data["total_errors_resolved"] += 1

        if episode.model_used:
            self.data["preferred_model"] = episode.model_used

    def get_context_hints(self) -> str:
        """Generate context hints from preferences for the system prompt."""
        hints = []
        langs = self.data["common_languages"]
        if langs:
            top_langs = langs.most_common(3)
            hints.append(f"User frequently works with: {', '.join(l for l, _ in top_langs)}")

        frameworks = self.data["common_frameworks"]
        if frameworks:
            top_fw = frameworks.most_common(3)
            hints.append(f"Common frameworks: {', '.join(f for f, _ in top_fw)}")

        errors = self.data["error_patterns"]
        if errors:
            top_err = errors.most_common(3)
            hints.append(f"Frequently encountered errors: {', '.join(e for e, _ in top_err)}")

        tools = self.data["tool_frequency"]
        if tools:
            top_tools = tools.most_common(5)
            hints.append(f"Most used tools: {', '.join(t for t, _ in top_tools)}")

        if self.data["total_tasks_completed"] > 0:
            hints.append(f"Sessions: {self.data['total_sessions']}, Tasks completed: {self.data['total_tasks_completed']}")

        return " | ".join(hints) if hints else ""

    def save(self, path: Path = PREFERENCES_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Convert Counters to dicts for JSON serialization
        serializable = {}
        for k, v in self.data.items():
            if isinstance(v, Counter):
                serializable[k] = dict(v)
            else:
                serializable[k] = v
        path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def load(self, path: Path = PREFERENCES_FILE):
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    if k in self.data:
                        if isinstance(self.data[k], Counter):
                            self.data[k] = Counter(v)
                        else:
                            self.data[k] = v
            except Exception:
                pass


def _extract_error_type(content: str) -> Optional[str]:
    """Extract a short error type from error content."""
    patterns = [
        r'(\w+Error):', r'(\w+Exception):', r'(\w+Warning):',
        r'(ENOENT|EACCES|EPERM)', r'(SyntaxError|TypeError|ValueError|KeyError|ImportError)',
        r'(404|500|403|401)\s',
    ]
    for pat in patterns:
        m = re.search(pat, content)
        if m:
            return m.group(1)
    return None


# ==============================================================================
# Auto-Tagging
# ==============================================================================

def auto_tag_episode(episode: Episode) -> List[str]:
    """Automatically generate tags for an episode based on content."""
    text = " ".join(e.content.lower() for e in episode.events[:30])
    all_paths = []
    for e in episode.events:
        if e.metadata.get("file_paths"):
            all_paths.extend(e.metadata["file_paths"])

    tags: Set[str] = set()

    # Language detection from file extensions
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "react", ".jsx": "react", ".java": "java",
        ".go": "go", ".rs": "rust", ".c": "c", ".cpp": "cpp",
        ".rb": "ruby", ".php": "php", ".cs": "csharp",
        ".html": "html", ".css": "css", ".scss": "scss",
    }
    for p in all_paths:
        ext = Path(p).suffix.lower()
        if ext in ext_map:
            tags.add(ext_map[ext])

    # Framework detection from content
    fw_patterns = {
        "react": [r"react", r"jsx", r"tsx", r"usestate", r"useeffect"],
        "nextjs": [r"next\.js", r"nextjs", r"next/", r"app router"],
        "vue": [r"vue\.js", r"vuejs", r"\.vue"],
        "django": [r"django", r"manage\.py"],
        "flask": [r"flask", r"app\.route"],
        "fastapi": [r"fastapi", r"uvicorn"],
        "express": [r"express", r"app\.get\(", r"app\.post\("],
        "supabase": [r"supabase", r"createclient"],
        "tailwind": [r"tailwind", r"tw-"],
    }
    for fw, patterns in fw_patterns.items():
        if any(re.search(p, text) for p in patterns):
            tags.add(fw)

    # Task type detection
    task_patterns = {
        "debugging": [r"error", r"bug", r"fix", r"debug", r"traceback"],
        "web": [r"website", r"web app", r"frontend", r"backend", r"api"],
        "testing": [r"test", r"pytest", r"unittest", r"spec"],
        "refactoring": [r"refactor", r"cleanup", r"restructure"],
        "deployment": [r"deploy", r"docker", r"ci/cd", r"pipeline"],
        "database": [r"database", r"sql", r"postgres", r"mongodb", r"supabase"],
    }
    for task, patterns in task_patterns.items():
        if any(re.search(p, text) for p in patterns):
            tags.add(task)

    return sorted(tags)


# ==============================================================================
# Main Memory Manager
# ==============================================================================

class EpisodicMemory:
    """
    Main episodic memory system. Manages episodes, events, indexing, and retrieval.
    Thread-safe for concurrent access.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.current_episode: Optional[Episode] = None
        self.episodes: Dict[str, Episode] = {}  # episode_id -> Episode
        self.index = TFIDFIndex()
        self.preferences = PreferenceTracker()
        self.stats: Dict[str, Any] = {
            "total_episodes": 0,
            "total_events": 0,
            "total_recalls": 0,
            "avg_recall_relevance": 0.0,
        }
        self._initialized = False

    def initialize(self):
        """Load persisted memory from disk."""
        if self._initialized:
            return
        with self._lock:
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            EPISODES_DIR.mkdir(parents=True, exist_ok=True)
            self._load_episodes()
            self._load_stats()
            self.preferences.load()
            self._rebuild_index()
            self._initialized = True

    def _load_episodes(self):
        """Load episodes from disk."""
        for f in EPISODES_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                ep = Episode.from_dict(data)
                self.episodes[ep.episode_id] = ep
            except Exception:
                continue

    def _load_stats(self):
        if STATS_FILE.exists():
            try:
                self.stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_episode(self, episode: Episode):
        """Persist a single episode to disk."""
        path = EPISODES_DIR / f"{episode.episode_id}.json"
        path.write_text(json.dumps(episode.to_dict(), indent=1), encoding="utf-8")

    def _save_stats(self):
        STATS_FILE.write_text(json.dumps(self.stats, indent=2), encoding="utf-8")

    def _rebuild_index(self):
        """Rebuild the TF-IDF index from all episodes."""
        self.index = TFIDFIndex()
        for ep_id, ep in self.episodes.items():
            text = ep.get_text_for_indexing()
            if ep.consolidated_summary:
                text += " " + ep.consolidated_summary
            self.index.add_document(ep_id, text)

    def _generate_episode_id(self) -> str:
        ts = str(time.time()).encode()
        return hashlib.sha256(ts).hexdigest()[:12]

    # --- Episode Lifecycle ---

    def start_episode(self, title: str = "Untitled Task", project_path: str = "", model: str = "") -> Episode:
        """Begin a new episode."""
        self.initialize()
        with self._lock:
            # Finalize previous episode if still open
            if self.current_episode and self.current_episode.outcome == "in_progress":
                self._finalize_episode(self.current_episode, "abandoned")

            ep = Episode(
                episode_id=self._generate_episode_id(),
                created_at=time.time(),
                updated_at=time.time(),
                title=title,
                project_path=project_path,
                model_used=model,
            )
            self.current_episode = ep
            self.episodes[ep.episode_id] = ep
            self.stats["total_episodes"] += 1
            return ep

    def end_episode(self, outcome: str = "success"):
        """End the current episode."""
        with self._lock:
            if self.current_episode:
                self._finalize_episode(self.current_episode, outcome)
                self.current_episode = None

    def _finalize_episode(self, episode: Episode, outcome: str):
        """Finalize and persist an episode."""
        episode.outcome = outcome
        episode.updated_at = time.time()
        episode.tags = auto_tag_episode(episode)
        episode.importance_score = compute_episode_importance(episode)

        # Update preferences
        self.preferences.update_from_episode(episode)
        self.preferences.save()

        # Update index
        text = episode.get_text_for_indexing()
        self.index.add_document(episode.episode_id, text)

        # Persist
        self._save_episode(episode)
        self._save_stats()

        # Check if consolidation needed
        active_count = sum(1 for ep in self.episodes.values() if not ep.consolidated_summary)
        if active_count > CONSOLIDATION_THRESHOLD:
            self._consolidate_old_episodes()

    # --- Event Recording ---

    def record_event(self, event_type: str, content: str, metadata: Optional[Dict] = None):
        """Record an event in the current episode."""
        if not self.current_episode:
            return

        event = Event(
            timestamp=time.time(),
            event_type=event_type,
            content=content[:2000],  # Cap content size
            metadata=metadata or {},
        )
        event.importance = compute_event_importance(event)

        with self._lock:
            self.current_episode.add_event(event)
            self.stats["total_events"] += 1

    def record_tool_call(self, tool_name: str, args: Dict, result: str):
        """Convenience: record a tool call + result."""
        # Extract file paths from args
        file_paths = []
        for key in ("path", "source", "destination"):
            if key in args and isinstance(args[key], str):
                file_paths.append(args[key])
        if "paths" in args and isinstance(args["paths"], list):
            file_paths.extend(args["paths"])

        self.record_event("tool_call", f"{tool_name}({json.dumps(args)[:300]})", {
            "tool_name": tool_name,
            "file_paths": file_paths,
        })

        # Record errors specially
        result_lower = result.lower() if isinstance(result, str) else ""
        if any(w in result_lower for w in ["error", "exception", "traceback", "failed"]):
            self.record_event("error", result[:1000], {
                "tool_name": tool_name,
                "file_paths": file_paths,
            })

    def record_solution(self, description: str, related_error: str = ""):
        """Record a solution/fix."""
        self.record_event("solution", description, {"related_error": related_error})

    def record_decision(self, description: str):
        """Record an architectural or approach decision."""
        self.record_event("decision", description)

    def record_user_input(self, prompt: str):
        """Record user input and use it to set episode title."""
        self.record_event("user_input", prompt[:500])
        if self.current_episode and self.current_episode.title == "Untitled Task":
            # Use first user input as episode title
            self.current_episode.title = prompt[:120]

    # --- Memory Retrieval ---

    def recall(self, query: str, top_k: int = MAX_RECALL_RESULTS) -> List[Dict[str, Any]]:
        """Retrieve relevant memories for a given query/context."""
        self.initialize()
        results = self.index.query(query, top_k=top_k)

        self.stats["total_recalls"] += 1

        memories = []
        for ep_id, score in results:
            ep = self.episodes.get(ep_id)
            if not ep:
                continue

            # Build memory snippet
            snippet = ep.consolidated_summary if ep.consolidated_summary else self._build_snippet(ep)
            memories.append({
                "episode_id": ep_id,
                "title": ep.title,
                "score": round(score, 3),
                "outcome": ep.outcome,
                "tags": ep.tags,
                "snippet": snippet,
                "age_hours": round((time.time() - ep.created_at) / 3600, 1),
                "importance": ep.importance_score,
            })

        # Update average recall relevance
        if memories:
            avg_score = sum(m["score"] for m in memories) / len(memories)
            n = self.stats["total_recalls"]
            old_avg = self.stats["avg_recall_relevance"]
            self.stats["avg_recall_relevance"] = round(old_avg + (avg_score - old_avg) / n, 4)

        return memories

    def recall_for_prompt(self, query: str) -> str:
        """Retrieve memories formatted for injection into the system prompt."""
        memories = self.recall(query, top_k=5)
        if not memories:
            return ""

        lines = ["[Relevant memories from past sessions:]"]
        token_count = 0
        for m in memories:
            line = f"- [{m['outcome']}] {m['title']} (relevance: {m['score']}, {m['age_hours']}h ago): {m['snippet']}"
            est_tokens = len(line) // 4
            if token_count + est_tokens > TOKEN_BUDGET_FOR_MEMORY:
                break
            lines.append(line)
            token_count += est_tokens

        # Add preference hints
        pref_hints = self.preferences.get_context_hints()
        if pref_hints:
            lines.append(f"[User patterns: {pref_hints}]")

        return "\n".join(lines)

    def _build_snippet(self, episode: Episode) -> str:
        """Build a short snippet from an episode's events."""
        parts = []
        # Get most important events
        sorted_events = sorted(episode.events, key=lambda e: e.importance, reverse=True)
        for ev in sorted_events[:5]:
            parts.append(f"{ev.event_type}: {ev.content[:150]}")
        return " | ".join(parts)

    # --- Consolidation ---

    def _consolidate_old_episodes(self):
        """Consolidate older episodes into summaries to save memory."""
        # Sort by creation time, consolidate oldest
        unconsolidated = [
            ep for ep in self.episodes.values()
            if not ep.consolidated_summary and ep.outcome != "in_progress"
        ]
        unconsolidated.sort(key=lambda e: e.created_at)

        # Keep the most recent N unconsolidated, consolidate the rest
        to_consolidate = unconsolidated[:-MAX_ACTIVE_EPISODES] if len(unconsolidated) > MAX_ACTIVE_EPISODES else []

        for ep in to_consolidate:
            ep.consolidated_summary = consolidate_episode(ep)
            # Remove raw events to save space (keep summary)
            ep.events = ep.events[:3] + ep.events[-3:]  # Keep just bookends
            self._save_episode(ep)
            # Update index with consolidated text
            self.index.add_document(ep.episode_id, ep.consolidated_summary)

    # --- Session Summary ---

    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the memory system state."""
        return {
            "total_episodes": self.stats["total_episodes"],
            "total_events": self.stats["total_events"],
            "active_episodes": sum(1 for ep in self.episodes.values() if not ep.consolidated_summary),
            "consolidated_episodes": sum(1 for ep in self.episodes.values() if ep.consolidated_summary),
            "total_recalls": self.stats["total_recalls"],
            "avg_recall_relevance": self.stats["avg_recall_relevance"],
            "preference_hints": self.preferences.get_context_hints(),
        }

    def get_current_episode_info(self) -> Optional[Dict[str, Any]]:
        """Get info about the current active episode."""
        if not self.current_episode:
            return None
        ep = self.current_episode
        return {
            "episode_id": ep.episode_id,
            "title": ep.title,
            "events_count": len(ep.events),
            "tags": ep.tags,
            "duration_minutes": round((time.time() - ep.created_at) / 60, 1),
        }


# ==============================================================================
# Singleton Instance
# ==============================================================================

_memory_instance: Optional[EpisodicMemory] = None

def get_memory() -> EpisodicMemory:
    """Get the global episodic memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = EpisodicMemory()
    return _memory_instance
