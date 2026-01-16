import json
import time
import os
import sys
import re
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Iterator, Set
import uuid

# --- G4F Import ---
try:
    import g4f
    G4F_AVAILABLE = True
except ImportError:
    G4F_AVAILABLE = False

# --- PyInstaller Path Helper ---
def _get_agentic_base_path() -> Path:
    """Get base path - works both in dev and when bundled with PyInstaller."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

# --- Token Management ---
class TokenManager:
    _tokens = None
    _current_index = 0
    _global_tokens_path = Path.home() / ".supercoder" / "tokens.txt"

    @classmethod
    def load_tokens(cls):
        if cls._tokens is None:
            paths = [
                cls._global_tokens_path,
                _get_agentic_base_path() / ".Information" / "tokens.txt",
                Path(".Information/tokens.txt"),
            ]
            for p in paths:
                if p.exists():
                    try:
                        cls._tokens = [line.strip() for line in p.read_text().splitlines() if line.strip()]
                        if cls._tokens:
                            print(f"[Loaded {len(cls._tokens)} API token(s) from {p}]")
                            return
                    except Exception as e:
                        print(f"[Warning: Could not read tokens from {p}: {e}]")
            # For g4f models, tokens are optional
            cls._tokens = []

    @classmethod
    def get_token(cls):
        cls.load_tokens()
        if not cls._tokens:
            return None
        return cls._tokens[cls._current_index]

    @classmethod
    def rotate_token(cls):
        if cls._tokens and len(cls._tokens) > 1:
            cls._current_index = (cls._current_index + 1) % len(cls._tokens)
            print(f"[Rotated to token {cls._current_index + 1}/{len(cls._tokens)}]")


# --- Token Counter ---
class TokenCounter:
    """Simple token counter - estimates ~4 chars per token."""

    def __init__(self):
        self._encoder = None
        if getattr(sys, 'frozen', False):
            return
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except:
            pass

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoder:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass
        return max(len(text) // 4, 1)

    def count_messages(self, messages: List[dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content") or ""
            if isinstance(content, list):
                text_content = ""
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        text_content += part["text"]
                total += self.count(text_content) + 4
            else:
                total += self.count(content) + 4
        return total + 3


# --- G4F Free Models (no API key required) ---
G4F_FREE_MODELS = {
    # Top Coding Models
    "kimi-k2": {"context": 128000, "description": "Kimi K2 - Best free coding"},
    "deepseek-v3": {"context": 128000, "description": "DeepSeek V3 - Excellent coder"},
    "deepseek-r1": {"context": 128000, "description": "DeepSeek R1 - Reasoning"},
    "deepseek-r1-turbo": {"context": 128000, "description": "DeepSeek R1 Turbo"},
    "deepseek-r1-distill-qwen-32b": {"context": 128000, "description": "DeepSeek R1 Distill"},
    "deepseek-prover-v2": {"context": 128000, "description": "DeepSeek Prover V2"},
    "deepseek-prover-v2-671b": {"context": 128000, "description": "DeepSeek Prover 671B"},
    "deepseek-v3-0324": {"context": 128000, "description": "DeepSeek V3 0324"},
    "deepseek-v3-0324-turbo": {"context": 128000, "description": "DeepSeek V3 Turbo"},
    "deepseek-r1-0528": {"context": 128000, "description": "DeepSeek R1 0528"},
    "deepseek-r1-0528-turbo": {"context": 128000, "description": "DeepSeek R1 0528 Turbo"},
    
    # Gemini Models
    "gemini-2.0": {"context": 128000, "description": "Gemini 2.0"},
    "gemini-2.0-flash": {"context": 128000, "description": "Gemini 2.0 Flash"},
    "gemini-2.0-flash-thinking": {"context": 128000, "description": "Gemini 2.0 Thinking"},
    "gemini-2.0-flash-thinking-with-apps": {"context": 128000, "description": "Gemini 2.0 w/ Apps"},
    "gemini-2.5-flash": {"context": 128000, "description": "Gemini 2.5 Flash"},
    "gemini-2.5-pro": {"context": 128000, "description": "Gemini 2.5 Pro"},
    
    # Qwen Models
    "qwen-3-235b": {"context": 128000, "description": "Qwen 3 235B"},
    "qwen-3-32b": {"context": 128000, "description": "Qwen 3 32B"},
    "qwen-3-30b": {"context": 128000, "description": "Qwen 3 30B"},
    "qwen-3-14b": {"context": 128000, "description": "Qwen 3 14B"},
    "qwen-3-4b": {"context": 128000, "description": "Qwen 3 4B"},
    "qwen-3-1.7b": {"context": 128000, "description": "Qwen 3 1.7B"},
    "qwen-3-0.6b": {"context": 128000, "description": "Qwen 3 0.6B"},
    "qwq-32b": {"context": 128000, "description": "QwQ 32B Reasoning"},
    
    # Llama Models
    "llama-3.2-90b": {"context": 128000, "description": "Llama 3.2 90B"},
    "llama-3.3-70b": {"context": 128000, "description": "Llama 3.3 70B"},
    "llama-4-scout": {"context": 128000, "description": "Llama 4 Scout"},
    "llama-4-maverick": {"context": 128000, "description": "Llama 4 Maverick"},
    
    # Gemma Models
    "codegemma-7b": {"context": 128000, "description": "CodeGemma 7B"},
    "gemma-1.1-7b": {"context": 128000, "description": "Gemma 1.1 7B"},
    "gemma-2-9b": {"context": 128000, "description": "Gemma 2 9B"},
    "gemma-3-4b": {"context": 128000, "description": "Gemma 3 4B"},
    "gemma-3-12b": {"context": 128000, "description": "Gemma 3 12B"},
    "gemma-3-27b": {"context": 128000, "description": "Gemma 3 27B"},
    
    # GPT Models
    "gpt-4": {"context": 128000, "description": "GPT-4 via g4f"},
    "gpt-4.1-nano": {"context": 128000, "description": "GPT-4.1 Nano"},
    "gpt-oss-120b": {"context": 128000, "description": "GPT OSS 120B"},
    "gpt-image": {"context": 128000, "description": "GPT Image"},
    
    # Phi Models
    "phi-4": {"context": 128000, "description": "Microsoft Phi-4"},
    "phi-4-multimodal": {"context": 128000, "description": "Phi-4 Multimodal"},
    "phi-4-reasoning-plus": {"context": 128000, "description": "Phi-4 Reasoning"},
    "wizardlm-2-7b": {"context": 128000, "description": "WizardLM 2 7B"},
    
    # Other Models
    "grok-3": {"context": 128000, "description": "Grok 3"},
    "command-r": {"context": 128000, "description": "Cohere Command R"},
    "command-a": {"context": 128000, "description": "Cohere Command A"},
    "r1-1776": {"context": 128000, "description": "R1-1776"},
    "airoboros-70b": {"context": 128000, "description": "Airoboros 70B"},
    "lzlv-70b": {"context": 128000, "description": "LZLV 70B"},
    "aria": {"context": 128000, "description": "Aria"},
}

# --- Native Tool Definitions ---
NATIVE_TOOLS = [
    {"type": "function", "function": {"name": "executePwsh", "description": "Execute a shell command inside Docker (Linux)", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Command to execute"}, "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "runOnHost", "description": "Execute a command on the Windows host machine (not in Docker). Use this for GUI apps, opening files with default programs, or Windows-specific commands.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Windows command to execute on host"}, "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "controlPwshProcess", "description": "Start or stop background processes", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["start", "stop"], "description": "Action to perform"}, "command": {"type": "string", "description": "Command to run (for start)"}, "processId": {"type": "integer", "description": "Process ID (for stop)"}, "path": {"type": "string", "description": "Working directory (for start)"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "listProcesses", "description": "List running background processes", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "getProcessOutput", "description": "Get output from a background process", "parameters": {"type": "object", "properties": {"processId": {"type": "integer", "description": "Process ID"}, "lines": {"type": "integer", "description": "Number of lines to return"}}, "required": ["processId"]}}},
    {"type": "function", "function": {"name": "listDirectory", "description": "List files and directories", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path (default: .)"}}, "required": []}}},
    {"type": "function", "function": {"name": "readFile", "description": "Read a file's contents", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the file"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "readMultipleFiles", "description": "Read multiple files at once", "parameters": {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}, "description": "List of file paths"}}, "required": ["paths"]}}},
    {"type": "function", "function": {"name": "readCode", "description": "Intelligently read code files with AST-based structure analysis.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the code file"}, "symbol": {"type": "string", "description": "Optional symbol name to search for"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "fileSearch", "description": "Search for files by name pattern", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Filename pattern to search"}, "path": {"type": "string", "description": "Directory to search (default: .)"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "grepSearch", "description": "Search for regex pattern in files", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Regex pattern to search"}, "path": {"type": "string", "description": "Directory to search (default: .)"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "deleteFile", "description": "Delete a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to delete"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "fsWrite", "description": "Create or overwrite a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to write"}, "content": {"type": "string", "description": "Content to write"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "fsAppend", "description": "Append content to a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to append to"}, "content": {"type": "string", "description": "Content to append"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "strReplace", "description": "Replace text in a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the file"}, "old": {"type": "string", "description": "Text to find"}, "new": {"type": "string", "description": "Replacement text"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {"name": "getDiagnostics", "description": "Check for syntax/lint errors in code", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to check"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "insertLines", "description": "Insert text at line number", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "lineNumber": {"type": "integer"}, "content": {"type": "string"}}, "required": ["path", "lineNumber", "content"]}}},
    {"type": "function", "function": {"name": "removeLines", "description": "Remove lines from file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "startLine": {"type": "integer"}, "endLine": {"type": "integer"}}, "required": ["path", "startLine", "endLine"]}}},
    {"type": "function", "function": {"name": "moveFile", "description": "Move/rename a file", "parameters": {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]}}},
    {"type": "function", "function": {"name": "copyFile", "description": "Copy a file", "parameters": {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]}}},
    {"type": "function", "function": {"name": "createDirectory", "description": "Create directory", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "undo", "description": "Undo last file operation", "parameters": {"type": "object", "properties": {"transactionId": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {"name": "getSymbols", "description": "Extract functions/classes from Python file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "findReferences", "description": "Find references to symbol", "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}, "path": {"type": "string"}}, "required": ["symbol"]}}},
    {"type": "function", "function": {"name": "fileDiff", "description": "Compare two files", "parameters": {"type": "object", "properties": {"path1": {"type": "string"}, "path2": {"type": "string"}}, "required": ["path1", "path2"]}}},
    {"type": "function", "function": {"name": "httpRequest", "description": "Make HTTP request", "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}, "body": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "downloadFile", "description": "Download file from URL", "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "destination": {"type": "string"}}, "required": ["url", "destination"]}}},
    {"type": "function", "function": {"name": "systemInfo", "description": "Get system info", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "runTests", "description": "Run tests", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "formatCode", "description": "Format code file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "webSearch", "description": "Search the web for programming help", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}, "site": {"type": "string", "description": "Optional site filter"}, "maxResults": {"type": "integer", "description": "Max results (default 5)"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "interactWithUser", "description": "Interact with the user when task is complete, blocked, or needs clarification", "parameters": {"type": "object", "properties": {"message": {"type": "string", "description": "Message to show"}, "interactionType": {"type": "string", "enum": ["complete", "question", "error"], "description": "Type of interaction"}}, "required": ["message", "interactionType"]}}},
    {"type": "function", "function": {"name": "finish", "description": "Signal task completion", "parameters": {"type": "object", "properties": {"summary": {"type": "string", "description": "Summary of what was accomplished"}, "status": {"type": "string", "enum": ["complete", "blocked", "partial"], "description": "Task status"}}, "required": ["summary"]}}}
]

# Model context limits
MODEL_LIMITS = {
    "anthropic/claude-opus-4.5": 200000,
    "anthropic/claude-sonnet-4": 200000,
    "qwen/qwen3-coder": 262144,
    "deepseek/deepseek-v3.2": 160000,
    "qwen/qwen3-235b-a22b": 128000,
    "anthropic/claude-3-opus": 200000,
    "anthropic/claude-3-sonnet": 200000,
    "openai/gpt-4-turbo": 128000,
    "default": 128000
}

# Models that work better with text-based tool calling instead of native
TEXT_TOOL_MODELS = {
    "qwen/qwen3-coder",  # Has issues with native tool calling
}


# --- Tool Call Parser for G4F (text-based) ---
def _build_tools_prompt(tools: List[dict]) -> str:
    """Build a prompt describing available tools for text-based tool calling."""
    lines = [
        "You have access to the following tools. To use a tool, respond with a JSON block in this EXACT format:",
        "",
        "```tool_call",
        '{"tool": "tool_name", "args": {"param1": "value1", "param2": "value2"}}',
        "```",
        "",
        "You can call multiple tools by including multiple ```tool_call``` blocks.",
        "After tool results are provided, continue working on the task.",
        "When the task is complete, call the 'finish' tool with a summary.",
        "",
        "Available tools:",
        ""
    ]
    for tool in tools:
        func = tool.get("function", {})
        name = func.get("name", "")
        desc = func.get("description", "")
        params = func.get("parameters", {}).get("properties", {})
        required = func.get("parameters", {}).get("required", [])
        
        param_strs = []
        for pname, pinfo in params.items():
            req = "*" if pname in required else ""
            ptype = pinfo.get("type", "string")
            pdesc = pinfo.get("description", "")
            param_strs.append(f"    - {pname}{req} ({ptype}): {pdesc}")
        
        lines.append(f"- {name}: {desc}")
        if param_strs:
            lines.extend(param_strs)
        lines.append("")
    
    return "\n".join(lines)


def _parse_tool_calls_from_text(text: str) -> List[dict]:
    """Parse tool calls from model text response."""
    tool_calls = []
    
    # Pattern to match ```tool_call ... ``` blocks
    pattern = r'```tool_call\s*(.*?)\s*```'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        try:
            # Clean up the JSON
            json_str = match.strip()
            # Handle potential issues with the JSON
            data = json.loads(json_str)
            
            tool_name = data.get("tool") or data.get("name") or data.get("function")
            args = data.get("args") or data.get("arguments") or data.get("parameters") or {}
            
            if tool_name:
                tool_calls.append({
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": tool_name,
                    "args": args
                })
        except json.JSONDecodeError:
            # Try to extract tool name and args with regex as fallback
            try:
                tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', match)
                if tool_match:
                    tool_name = tool_match.group(1)
                    # Try to parse args
                    args_match = re.search(r'"args"\s*:\s*(\{[^}]+\})', match)
                    args = json.loads(args_match.group(1)) if args_match else {}
                    tool_calls.append({
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "name": tool_name,
                        "args": args
                    })
            except:
                pass
    
    return tool_calls


def _strip_tool_calls_from_text(text: str) -> str:
    """Remove tool call blocks from text to get just the content."""
    # Remove ```tool_call ... ``` blocks
    cleaned = re.sub(r'```tool_call\s*.*?\s*```', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Clean up extra whitespace
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


# --- Lightweight File Indexer ---
class FileIndexer:
    def __init__(self, index_path: Path = None, max_file_bytes: int = 200_000):
        self.index_path = index_path or Path(".supercoder/index.json")
        self.max_file_bytes = max_file_bytes
        self.index: Dict[str, Any] = {"files": {}, "built_at": time.time()}
        self._stop = {"the","a","an","and","or","of","to","in","on","for","with","at","by","from","is","are","was","were","be","it","this","that","as","so","if","then","else","elif","when","while","do","does","did","but","not"}
        self._ignore_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".supercoder", ".Information"}
        self._ignore_exts = {".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib"}
        self.load()

    def _tokenize(self, text: str) -> List[str]:
        tokens = []
        word = []
        for ch in text.lower():
            if ch.isalnum() or ch == '_':
                word.append(ch)
            else:
                if word:
                    tokens.append("".join(word))
                    word = []
        if word:
            tokens.append("".join(word))
        return [t for t in tokens if t and t not in self._stop and len(t) > 2]

    def _file_tokens(self, path: Path) -> List[str]:
        try:
            data = path.read_bytes()[:self.max_file_bytes]
            try:
                text = data.decode("utf-8", errors="ignore")
            except Exception:
                return []
            return self._tokenize(text)
        except Exception:
            return []

    def build(self, root: str = ".") -> None:
        root_path = Path(root)
        files = {}
        for r, dirs, filenames in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in self._ignore_dirs]
            for fname in filenames:
                p = Path(r) / fname
                if p.suffix in self._ignore_exts:
                    continue
                tokens = self._file_tokens(p)
                if not tokens:
                    continue
                files[str(p)] = {"mtime": p.stat().st_mtime, "size": p.stat().st_size, "tokens": tokens[:800]}
        self.index = {"files": files, "built_at": time.time()}
        self.save()

    def save(self):
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.index_path.write_text(json.dumps(self.index))
        except Exception:
            pass

    def load(self):
        if self.index_path.exists():
            try:
                self.index = json.loads(self.index_path.read_text())
            except Exception:
                self.index = {"files": {}, "built_at": time.time()}

    def search(self, query: str, limit: int = 8) -> List[str]:
        if not query or not self.index.get("files"):
            return []
        q_tokens = set(self._tokenize(query))
        if not q_tokens:
            return []
        scored = []
        for path, meta in self.index["files"].items():
            file_tokens = meta.get("tokens", [])
            if not file_tokens:
                continue
            score = sum(1 for qt in q_tokens if qt in set(file_tokens))
            if score > 0:
                scored.append((score, meta.get("mtime", 0), path))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [p for _, _, p in scored[:limit]]


# --- Agent Class ---
class Agent:
    def __init__(self, initial_prompt: str, model: str = "kimi-k2", streaming: bool = False, embedding_model: str = None):
        self.model = model
        self.streaming = streaming
        self.messages = []
        self.context_files = []
        self.mandatory_files = []
        self._context_cache = {}
        self.indexer = FileIndexer()
        self.token_counter = TokenCounter()
        self.reserved_output = 4096
        
        # Track tokens for cost calculation
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        
        # Determine if using g4f or OpenRouter
        self.use_g4f = model in G4F_FREE_MODELS
        
        # Set context limit
        if self.use_g4f:
            self.max_context = G4F_FREE_MODELS.get(model, {}).get("context", 128000)
        else:
            self.max_context = MODEL_LIMITS.get(model, MODEL_LIMITS["default"])
        
        self.messages.append({"role": "system", "content": initial_prompt})

    def add_context(self, files):
        if isinstance(files, str):
            files = [files]
        for f in files:
            if Path(f).exists():
                self.context_files.append(f)

    def set_mandatory_files(self, files: List[str]):
        self.mandatory_files = [f for f in files if Path(f).exists()]

    def _extract_keywords(self, text: str) -> set:
        stop = {"the","a","an","and","or","of","to","in","on","for","with","at","by","from","is","are","was","were","be","it","this","that","as","so","if","then","else","elif","when","while","do","does","did","but","not"}
        tokens = []
        word = []
        for ch in text.lower():
            if ch.isalnum() or ch == '_':
                word.append(ch)
            else:
                if word:
                    tokens.append("".join(word))
                    word = []
        if word:
            tokens.append("".join(word))
        return {t for t in tokens if t and t not in stop and len(t) > 2}

    def _get_cached_content(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return ""
        mtime = p.stat().st_mtime
        cached = self._context_cache.get(path)
        if cached and cached.get("mtime") == mtime:
            return cached.get("content", "")
        try:
            content = p.read_text(encoding='utf-8')
        except Exception:
            content = ""
        self._context_cache[path] = {"mtime": mtime, "content": content}
        return content

    def _score_file(self, path: str, hint_text: str) -> int:
        if not hint_text:
            return 0
        try:
            file_text = self._get_cached_content(path)
        except Exception:
            return 0
        if not file_text:
            return 0
        query_keywords = self._extract_keywords(hint_text)
        if not query_keywords:
            return 0
        return sum(1 for kw in query_keywords if kw in file_text.lower())

    def _build_context_string(self, hint_text: str = "") -> str:
        all_files = self.mandatory_files + [f for f in self.context_files if f not in self.mandatory_files]
        if not all_files:
            retrieval_hits = self.indexer.search(hint_text, limit=8) if self.indexer else []
            all_files = retrieval_hits
            self.context_files = retrieval_hits
            if not all_files:
                return ""

        current_tokens = self.token_counter.count_messages(self.messages)
        available = self.max_context - self.reserved_output - current_tokens - 1000
        parts = ["## Context Files:\n"]
        used_tokens = self.token_counter.count(parts[0])
        included = 0
        skipped_files = []

        for f in self.mandatory_files:
            try:
                file_content = Path(f).read_text(encoding='utf-8')
                file_block = f"### {f}\n```\n{file_content}\n```\n"
                file_tokens = self.token_counter.count(file_block)
                parts.append(file_block)
                used_tokens += file_tokens
                included += 1
            except Exception as e:
                print(f"[Warning: Could not read mandatory file {f}: {e}]")

        optional_files = [f for f in self.context_files if f not in self.mandatory_files]
        if self.indexer:
            if not self.indexer.index.get("files"):
                try:
                    self.indexer.build(".")
                except Exception as e:
                    print(f"[Warning: Could not build index: {e}]")
            retrieved = self.indexer.search(hint_text, limit=12)
            for f in retrieved:
                if f not in optional_files and f not in self.mandatory_files:
                    optional_files.append(f)

        if hint_text:
            ranked = sorted(optional_files, key=lambda p: (self._score_file(p, hint_text), Path(p).stat().st_mtime if Path(p).exists() else 0), reverse=True)
        else:
            ranked = sorted(optional_files, key=lambda p: Path(p).stat().st_mtime if Path(p).exists() else 0, reverse=True)

        for f in ranked:
            try:
                file_content = self._get_cached_content(f)
                file_block = f"### {f}\n```\n{file_content}\n```\n"
                file_tokens = self.token_counter.count(file_block)
                if used_tokens + file_tokens <= available:
                    parts.append(file_block)
                    used_tokens += file_tokens
                    included += 1
                else:
                    skipped_files.append(f)
            except Exception as e:
                print(f"[Warning: Could not read optional file {f}: {e}]")

        if skipped_files:
            print(f"[Context: {included} files, {len(skipped_files)} skipped, ~{used_tokens} tokens]")
            parts.append("## Skipped files (available via tools):\n")
            for f in skipped_files:
                parts.append(f"- {f}\n")
        return "\n".join(parts)

    def Prompt(self, user_input: str, streaming: bool = None) -> str:
        if streaming is None:
            streaming = self.streaming
        context = self._build_context_string(user_input)
        full_input = f"{context}\n\n{user_input}" if context else user_input
        self.messages.append({"role": "user", "content": full_input})
        
        if self.use_g4f:
            response = self._call_g4f(streaming=streaming)
        else:
            response = self._call_openrouter(streaming=streaming)
        
        self.messages.append({"role": "assistant", "content": response})
        self.context_files = []
        return response

    def PromptWithTools(self, user_input: str, tools: List[dict] = None, streaming: bool = False, on_chunk=None) -> Tuple[str, List[dict]]:
        if tools is None:
            tools = NATIVE_TOOLS
        
        context = self._build_context_string(user_input)
        current_messages = list(self.messages)
        full_input = f"{context}\n\n{user_input}" if context else user_input
        current_messages.append({"role": "user", "content": full_input})
        self.messages.append({"role": "user", "content": user_input})
        
        original_messages = self.messages
        self.messages = current_messages
        
        try:
            if self.use_g4f:
                content, tool_calls = self._call_g4f_with_tools(tools, streaming=streaming, on_chunk=on_chunk)
            elif self.model in TEXT_TOOL_MODELS:
                # Use text-based tool calling for models that don't handle native tools well
                content, tool_calls = self._call_openrouter_text_tools(tools, streaming=streaming, on_chunk=on_chunk)
            else:
                content, tool_calls = self._call_openrouter_with_tools(tools, streaming=streaming, on_chunk=on_chunk)
        finally:
            self.messages = original_messages

        assistant_msg = {"role": "assistant", "content": content or None}
        if tool_calls:
            assistant_msg["tool_calls"] = [{"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}} for tc in tool_calls]
        self.messages.append(assistant_msg)
        self.context_files = []
        return content, tool_calls

    def clear_history(self, keep_system: bool = True, keep_last: int = 0):
        if keep_system and self.messages and self.messages[0].get("role") == "system":
            system = self.messages[0]
            self.messages = [system] + self.messages[-(keep_last):] if keep_last > 0 else [system]
        else:
            self.messages = self.messages[-(keep_last):] if keep_last > 0 else []
        print(f"[Cleared history, kept {len(self.messages)} messages]")

    def get_token_usage(self) -> dict:
        used = self.token_counter.count_messages(self.messages)
        return {"used": used, "max": self.max_context, "available": self.max_context - used - self.reserved_output, "percent": round(used / self.max_context * 100, 1)}

    def AddToolResult(self, tool_call_id: str, tool_name: str, result: str):
        if self.use_g4f or self.model in TEXT_TOOL_MODELS:
            # For g4f and text-tool models, add tool results as user messages with clear formatting
            self.messages.append({"role": "user", "content": f"Tool '{tool_name}' returned:\n```\n{result}\n```\n\nContinue with the task. Use more tools if needed, or call 'finish' when done."})
        else:
            self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": str(result)})


    # --- G4F API Methods ---
    def _call_g4f(self, streaming: bool = False) -> str:
        """Call g4f API without tools."""
        if not G4F_AVAILABLE:
            return "[Error: g4f not installed. Run: pip install g4f]"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Convert messages to g4f format
                g4f_messages = []
                for msg in self.messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "tool":
                        continue
                    if role in ("system", "user", "assistant"):
                        g4f_messages.append({"role": role, "content": str(content) if content else ""})
                
                response = g4f.ChatCompletion.create(
                    model=self.model,
                    messages=g4f_messages,
                    stream=streaming
                )
                
                if streaming:
                    result = ""
                    for chunk in response:
                        if chunk and isinstance(chunk, str):
                            print(chunk, end='', flush=True)
                            result += chunk
                    print()
                    return result
                else:
                    # Handle various response types
                    if isinstance(response, str):
                        return response
                    elif hasattr(response, '__iter__') and not isinstance(response, (str, dict)):
                        # It's a generator/iterator, consume it
                        return "".join(str(c) for c in response if isinstance(c, str))
                    else:
                        return str(response)
                    
            except Exception as e:
                print(f"[G4F Error, attempt {attempt + 1}] {e}")
                time.sleep(2 ** attempt)
        
        return "[Error: G4F API failed]"

    def _call_g4f_with_tools(self, tools: List[dict], streaming: bool = False, on_chunk=None) -> Tuple[str, List[dict]]:
        """Call g4f API with text-based tool calling."""
        if not G4F_AVAILABLE:
            return "[Error: g4f not installed]", []
        
        # Build tools prompt and inject into system message
        tools_prompt = _build_tools_prompt(tools)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Convert messages to g4f format with tools prompt
                g4f_messages = []
                for i, msg in enumerate(self.messages):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    
                    if role == "system":
                        content = f"{content}\n\n{tools_prompt}"
                    elif role == "tool":
                        continue
                    
                    if role in ("system", "user", "assistant"):
                        g4f_messages.append({"role": role, "content": str(content) if content else ""})
                
                response = g4f.ChatCompletion.create(
                    model=self.model,
                    messages=g4f_messages,
                    stream=streaming
                )
                
                if streaming:
                    result = ""
                    for chunk in response:
                        # Only process string chunks
                        if chunk and isinstance(chunk, str):
                            if on_chunk:
                                on_chunk(chunk)
                            result += chunk
                    content = result
                else:
                    # Handle various response types
                    if isinstance(response, str):
                        content = response
                    elif hasattr(response, '__iter__') and not isinstance(response, (str, dict)):
                        content = "".join(str(c) for c in response if isinstance(c, str))
                    else:
                        content = str(response)
                
                # Parse tool calls from response
                tool_calls = _parse_tool_calls_from_text(content)
                
                # Strip tool call blocks from content for display
                display_content = _strip_tool_calls_from_text(content)
                
                return display_content, tool_calls
                    
            except Exception as e:
                print(f"[G4F Error, attempt {attempt + 1}] {e}")
                time.sleep(2 ** attempt)
        
        return "[Error: G4F API failed]", []

    # --- OpenRouter API Methods ---
    def _call_openrouter(self, streaming: bool = False) -> str:
        """Call OpenRouter API without tools."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                token = TokenManager.get_token()
                if not token:
                    return "[Error: No API token. Use 'tokens' command to add one.]"
                
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": self.messages, "stream": streaming},
                    timeout=120, stream=streaming
                )
                resp.raise_for_status()
                
                if streaming:
                    result = ""
                    for line in resp.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            if line.startswith('data: '):
                                line = line[6:]
                            if line == '[DONE]':
                                break
                            try:
                                data = json.loads(line)
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    chunk = delta['content']
                                    print(chunk, end='', flush=True)
                                    result += chunk
                            except:
                                pass
                    print()
                    return result
                else:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                    
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 0
                if status in (401, 403, 429):
                    TokenManager.rotate_token()
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[Error: {type(e).__name__}: {e}, attempt {attempt + 1}]")
                time.sleep(2 ** attempt)
        
        return "[Error: All API attempts failed]"

    def _call_openrouter_text_tools(self, tools: List[dict], streaming: bool = False, on_chunk=None) -> Tuple[str, List[dict]]:
        """Call OpenRouter API with text-based tool calling (for models that don't handle native tools well)."""
        # Build tools prompt and inject into system message
        tools_prompt = _build_tools_prompt(tools)
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                token = TokenManager.get_token()
                if not token:
                    return "[Error: No API token]", []
                
                # Convert messages with tools prompt injected into system
                api_messages = []
                for i, msg in enumerate(self.messages):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    
                    if role == "system":
                        content = f"{content}\n\n{tools_prompt}"
                    elif role == "tool":
                        # Skip tool messages - they're handled as user messages for text-based
                        continue
                    
                    if role in ("system", "user", "assistant"):
                        api_messages.append({"role": role, "content": str(content) if content else ""})
                
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": api_messages, "stream": streaming},
                    timeout=120, stream=streaming
                )
                resp.raise_for_status()
                
                if streaming:
                    content = ""
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            line = line[6:]
                        if line == '[DONE]':
                            break
                        try:
                            data = json.loads(line)
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta and delta['content']:
                                chunk = delta['content']
                                content += chunk
                                if on_chunk:
                                    on_chunk(chunk)
                        except:
                            pass
                else:
                    data = resp.json()
                    content = data["choices"][0]["message"].get("content", "")
                
                # Estimate tokens for cost tracking
                self.last_prompt_tokens = self.token_counter.count_messages(api_messages)
                self.last_completion_tokens = self.token_counter.count(content)
                
                # Parse tool calls from response text
                tool_calls = _parse_tool_calls_from_text(content)
                
                # Strip tool call blocks from content for display
                display_content = _strip_tool_calls_from_text(content)
                
                return display_content, tool_calls
                    
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 0
                if status in (401, 403, 429):
                    TokenManager.rotate_token()
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[Error: {type(e).__name__}: {e}, attempt {attempt + 1}]")
                time.sleep(2 ** attempt)
        
        return "[Error: All API attempts failed]", []

    def _call_openrouter_with_tools(self, tools: List[dict], streaming: bool = False, on_chunk=None) -> Tuple[str, List[dict]]:
        """Call OpenRouter API with native tool calling."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                token = TokenManager.get_token()
                if not token:
                    return "[Error: No API token]", []
                
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": self.messages, "tools": tools, "tool_choice": "auto", "stream": streaming},
                    timeout=120, stream=streaming
                )
                resp.raise_for_status()
                
                if streaming:
                    content = ""
                    tool_calls_data = {}
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            line = line[6:]
                        if line == '[DONE]':
                            break
                        try:
                            data = json.loads(line)
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta and delta['content']:
                                chunk = delta['content']
                                content += chunk
                                if on_chunk:
                                    on_chunk(chunk)
                            if 'tool_calls' in delta:
                                for tc in delta['tool_calls']:
                                    idx = tc.get('index', 0)
                                    if idx not in tool_calls_data:
                                        tool_calls_data[idx] = {'id': '', 'name': '', 'arguments': ''}
                                    if 'id' in tc:
                                        tool_calls_data[idx]['id'] = tc['id']
                                    if 'function' in tc:
                                        if 'name' in tc['function']:
                                            tool_calls_data[idx]['name'] = tc['function']['name']
                                        if 'arguments' in tc['function']:
                                            tool_calls_data[idx]['arguments'] += tc['function']['arguments']
                                            # Signal tool call progress to spinner
                                            if on_chunk:
                                                on_chunk(f"\x00TOOL:{len(tc['function']['arguments'])}")
                        except:
                            pass
                    
                    # Estimate tokens for cost tracking
                    self.last_prompt_tokens = self.token_counter.count_messages(self.messages)
                    self.last_completion_tokens = self.token_counter.count(content)
                    
                    parsed_calls = []
                    for idx in sorted(tool_calls_data.keys()):
                        tc = tool_calls_data[idx]
                        try:
                            args = json.loads(tc['arguments']) if tc['arguments'] else {}
                        except:
                            args = {}
                        if tc['name']:
                            parsed_calls.append({"id": tc['id'], "name": tc['name'], "args": args})
                    return content, parsed_calls
                else:
                    data = resp.json()
                    message = data["choices"][0]["message"]
                    content = message.get("content") or ""
                    raw_tool_calls = message.get("tool_calls", [])
                    
                    # Get actual usage if available, otherwise estimate
                    usage = data.get("usage", {})
                    self.last_prompt_tokens = usage.get("prompt_tokens", self.token_counter.count_messages(self.messages))
                    self.last_completion_tokens = usage.get("completion_tokens", self.token_counter.count(content))
                    
                    parsed_calls = []
                    for tc in raw_tool_calls:
                        if tc.get("type") == "function":
                            try:
                                args = json.loads(tc["function"]["arguments"])
                            except:
                                args = {}
                            parsed_calls.append({"id": tc["id"], "name": tc["function"]["name"], "args": args})
                    return content, parsed_calls
                    
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 0
                if status in (401, 403, 429):
                    TokenManager.rotate_token()
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[Error: {type(e).__name__}: {e}, attempt {attempt + 1}]")
                time.sleep(2 ** attempt)
        
        return "[Error: All API attempts failed]", []


# --- Tool Execution ---
def execute_tool(tool_call: dict) -> str:
    """Execute a tool call and return result"""
    from tools import (
        execute_pwsh, run_on_host, control_pwsh_process, list_processes, get_process_output,
        list_directory, read_file, read_multiple_files, read_code, file_search, grep_search,
        delete_file, fs_write, fs_append, str_replace, get_diagnostics, property_coverage,
        insert_lines, remove_lines, move_file, copy_file, create_directory, undo,
        get_symbols, find_references, file_diff, http_request, download_file,
        system_info, run_tests, format_code, web_search, search_stackoverflow,
        interact_with_user, finish
    )

    name = tool_call["name"]
    args = tool_call.get("args", {})

    REQUIRED_PARAMS = {
        "executePwsh": ["command"], "runOnHost": ["command"], "readFile": ["path"], "fsWrite": ["path", "content"],
        "fsAppend": ["path", "content"], "strReplace": ["path", "old", "new"],
        "deleteFile": ["path"], "getDiagnostics": ["path"], "fileSearch": ["pattern"],
        "grepSearch": ["pattern"], "getProcessOutput": ["processId"], "controlPwshProcess": ["action"],
        "interactWithUser": ["message", "interactionType"],
    }

    if name in REQUIRED_PARAMS:
        missing = [p for p in REQUIRED_PARAMS[name] if p not in args or args[p] is None]
        if missing:
            return f"ERROR: {name} requires parameters: {missing}. You provided: {list(args.keys())}. Please call again with all required parameters."

    try:
        if name == "executePwsh":
            result = execute_pwsh(args["command"], args.get("timeout", 60))
            return f"stdout: {result['stdout']}\nstderr: {result['stderr']}\nreturncode: {result['returncode']}"
        elif name == "runOnHost":
            result = run_on_host(args["command"], args.get("timeout", 60))
            return f"stdout: {result['stdout']}\nstderr: {result['stderr']}\nreturncode: {result['returncode']}"
        elif name == "controlPwshProcess":
            return json.dumps(control_pwsh_process(args["action"], args.get("command"), args.get("processId"), args.get("path")))
        elif name == "listProcesses":
            return json.dumps(list_processes())
        elif name == "getProcessOutput":
            return json.dumps(get_process_output(args["processId"], args.get("lines", 100)))
        elif name == "listDirectory":
            result = list_directory(args.get("path", "."))
            if "error" in result:
                return f"Error: {result['error']}"
            entries = result["entries"]
            lines = []
            for e in entries:
                prefix = "[DIR] " if e["is_dir"] else "      "
                size_str = f" ({e['size']} bytes)" if e.get("size") else ""
                lines.append(f"{prefix}{e['name']}{size_str}")
            return "\n".join(lines) if lines else "(empty)"
        elif name == "readFile":
            return read_file(args["path"])
        elif name == "readMultipleFiles":
            result = read_multiple_files(args["paths"])
            output = []
            for p, content in result.items():
                if isinstance(content, dict) and "error" in content:
                    output.append(f"=== {p} ===\nError: {content['error']}")
                else:
                    output.append(f"=== {p} ===\n{content}")
            return "\n\n".join(output)
        elif name == "readCode":
            result = read_code(args["path"], symbol=args.get("symbol"), include_structure=args.get("includeStructure", True))
            if "error" in result:
                return f"Error: {result['error']}"
            output = [f"=== {result['path']} ({result['lines']} lines, {result['size_bytes']} bytes) ===", result['content']]
            if 'structure' in result:
                s = result['structure']
                output.append("\n--- Structure ---")
                if s.get('functions'):
                    output.append(f"Functions: {', '.join(f['name'] for f in s['functions'])}")
                if s.get('classes'):
                    output.append(f"Classes: {', '.join(c['name'] for c in s['classes'])}")
            return "\n".join(output)
        elif name == "fileSearch":
            result = file_search(args["pattern"], args.get("path", "."))
            return "\n".join(result.get("matches", [])) or "No files found"
        elif name == "grepSearch":
            result = grep_search(args["pattern"], args.get("path", "."))
            if "error" in result:
                return f"Error: {result['error']}"
            return "\n".join([f"{h['file']}:{h['line']}: {h['text']}" for h in result.get("hits", [])]) or "No matches found"
        elif name == "deleteFile":
            return json.dumps(delete_file(args["path"]))
        elif name == "fsWrite":
            return json.dumps(fs_write(args["path"], args["content"]))
        elif name == "fsAppend":
            return json.dumps(fs_append(args["path"], args["content"]))
        elif name == "strReplace":
            return json.dumps(str_replace(args["path"], args["old"], args["new"]))
        elif name == "getDiagnostics":
            return json.dumps(get_diagnostics(args["path"]))
        elif name == "propertyCoverage":
            return json.dumps(property_coverage(args["specPath"], args["codePath"]))
        elif name == "insertLines":
            return json.dumps(insert_lines(args["path"], args["lineNumber"], args["content"]))
        elif name == "removeLines":
            return json.dumps(remove_lines(args["path"], args["startLine"], args["endLine"]))
        elif name == "moveFile":
            return json.dumps(move_file(args["source"], args["destination"]))
        elif name == "copyFile":
            return json.dumps(copy_file(args["source"], args["destination"]))
        elif name == "createDirectory":
            return json.dumps(create_directory(args["path"]))
        elif name == "undo":
            return json.dumps(undo(args.get("transactionId")))
        elif name == "getSymbols":
            return json.dumps(get_symbols(args["path"]))
        elif name == "findReferences":
            return json.dumps(find_references(args["symbol"], args.get("path", ".")))
        elif name == "fileDiff":
            return json.dumps(file_diff(args["path1"], args["path2"]))
        elif name == "httpRequest":
            return json.dumps(http_request(args["url"], args.get("method", "GET"), args.get("body")))
        elif name == "downloadFile":
            return json.dumps(download_file(args["url"], args["destination"]))
        elif name == "systemInfo":
            return json.dumps(system_info())
        elif name == "runTests":
            return json.dumps(run_tests(args.get("path", ".")))
        elif name == "formatCode":
            return json.dumps(format_code(args["path"]))
        elif name == "webSearch":
            result = web_search(args["query"], site=args.get("site"), max_results=args.get("maxResults", 5))
            if "error" in result:
                return f"Search error: {result['error']}"
            output = [f"Search results for: {result['query']}"]
            for i, r in enumerate(result.get("results", []), 1):
                output.append(f"{i}. {r['title']}")
                output.append(f"   URL: {r['url']}")
            return "\n".join(output) or "No results found"
        elif name == "searchStackOverflow":
            result = search_stackoverflow(args["query"], max_results=args.get("maxResults", 5))
            if "error" in result:
                return f"Search error: {result['error']}"
            output = [f"Stack Overflow results for: {result['query']}"]
            for i, r in enumerate(result.get("results", []), 1):
                output.append(f"{i}. {r['title']}")
                output.append(f"   URL: {r['url']}")
            return "\n".join(output) or "No results found"
        elif name == "interactWithUser":
            return json.dumps(interact_with_user(args["message"], args.get("interactionType", "info")))
        elif name == "finish":
            return json.dumps(finish(args["summary"], args.get("status", "complete")))
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error executing {name}: {e}"
