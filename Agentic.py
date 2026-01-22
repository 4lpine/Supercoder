"""
Agentic - Simple LLM Agent with Native Tool Calling
"""
import json
import time
import os
import sys
import requests
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Iterator, Set

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
            raise FileNotFoundError("No API tokens found. Use 'tokens' command to add your OpenRouter API key.")

    @classmethod
    def get_token(cls):
        cls.load_tokens()
        return cls._tokens[cls._current_index]

    @classmethod
    def rotate_token(cls):
        if cls._tokens and len(cls._tokens) > 1:
            cls._current_index = (cls._current_index + 1) % len(cls._tokens)
            print(f"[Rotated to token {cls._current_index + 1}/{len(cls._tokens)}]")


# --- Token Counter ---
class TokenCounter:
    """Simple token counter - estimates ~4 chars per token"""

    def __init__(self):
        self._encoder = None
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except ImportError:
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


# --- Native Tool Definitions ---
NATIVE_TOOLS = [
    {"type": "function", "function": {"name": "executePwsh", "description": "Execute a shell command. For interactive commands, provide responses list or map. Output streams in real-time.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Command to execute"}, "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"}, "interactiveResponses": {"type": ["array", "object"], "items": {"type": "string"}, "additionalProperties": {"type": "string"}, "description": "Optional: list of responses (e.g., ['Y','Y','N']) or map of prompt->response (e.g., {'package name': 'my-app', 'license': 'MIT', '*': ''})"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "controlPwshProcess", "description": "Start or stop background processes", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["start", "stop"], "description": "Action to perform"}, "command": {"type": "string", "description": "Command to run (for start)"}, "processId": {"type": "integer", "description": "Process ID (for stop)"}, "path": {"type": "string", "description": "Working directory (for start)"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "listProcesses", "description": "List running background processes", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "getProcessOutput", "description": "Get output from a background process", "parameters": {"type": "object", "properties": {"processId": {"type": "integer", "description": "Process ID"}, "lines": {"type": "integer", "description": "Number of lines to return"}}, "required": ["processId"]}}},
    {"type": "function", "function": {"name": "listDirectory", "description": "List files and directories", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path (default: .)"}}, "required": []}}},
    {"type": "function", "function": {"name": "readFile", "description": "Read a file's contents, optionally with line range", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the file"}, "start_line": {"type": "integer", "description": "Starting line number (1-indexed, inclusive). Optional - if omitted, starts from beginning"}, "end_line": {"type": "integer", "description": "Ending line number (1-indexed, inclusive). Optional - if omitted, reads to end"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "readMultipleFiles", "description": "Read multiple files at once", "parameters": {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}, "description": "List of file paths"}}, "required": ["paths"]}}},
    {"type": "function", "function": {"name": "readCode", "description": "Intelligently read code files with AST-based structure analysis. Returns file content plus extracted functions, classes, imports, and global variables. Supports optional symbol search.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the code file"}, "symbol": {"type": "string", "description": "Optional symbol name to search for"}, "includeStructure": {"type": "boolean", "description": "Whether to include AST structure analysis (default true)"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "fileSearch", "description": "Search for files by name pattern", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Filename pattern to search"}, "path": {"type": "string", "description": "Directory to search (default: .)"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "grepSearch", "description": "Search for regex pattern in files", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Regex pattern to search"}, "path": {"type": "string", "description": "Directory to search (default: .)"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "deleteFile", "description": "Delete a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to delete"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "fsWrite", "description": "Create or overwrite a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to write"}, "content": {"type": "string", "description": "Content to write"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "fsAppend", "description": "Append content to a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to append to"}, "content": {"type": "string", "description": "Content to append"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "strReplace", "description": "Replace text in a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the file"}, "old": {"type": "string", "description": "Text to find"}, "new": {"type": "string", "description": "Replacement text"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {"name": "getDiagnostics", "description": "Check for syntax/lint errors in code", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to check"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "propertyCoverage", "description": "Analyze how well code covers spec requirements", "parameters": {"type": "object", "properties": {"specPath": {"type": "string", "description": "Path to spec/requirements file"}, "codePath": {"type": "string", "description": "Path to code file"}}, "required": ["specPath", "codePath"]}}},
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
    {"type": "function", "function": {"name": "webSearch", "description": "Search the web for programming help, documentation, or solutions. Use when you need to look up how to do something, find examples, or troubleshoot errors.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query (e.g., 'python async await example')"}, "site": {"type": "string", "description": "Optional site to restrict search (e.g., 'stackoverflow.com', 'github.com')"}, "maxResults": {"type": "integer", "description": "Maximum results to return (default 5)"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "searchStackOverflow", "description": "Search Stack Overflow specifically for programming questions and solutions.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}, "maxResults": {"type": "integer", "description": "Maximum results to return (default 5)"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "interactWithUser", "description": "Interact with the user. Use ONLY when: (1) task is FULLY complete, (2) you hit a blocker that requires user decision, (3) you need clarification. Do NOT use mid-task.", "parameters": {"type": "object", "properties": {"message": {"type": "string", "description": "Message to show the user"}, "interactionType": {"type": "string", "enum": ["complete", "question", "error"], "description": "complete=task done, question=need user input, error=hit a blocker"}}, "required": ["message", "interactionType"]}}},
    {"type": "function", "function": {"name": "requestUserCommand", "description": "Ask user to run an interactive command manually (for commands with menus/prompts that would hang). Returns when user confirms completion.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Command to ask user to run"}, "reason": {"type": "string", "description": "Why this needs to be run manually"}, "workingDirectory": {"type": "string", "description": "Optional directory where command should be run"}}, "required": ["command", "reason"]}}},
    {"type": "function", "function": {"name": "finish", "description": "Signal that you have COMPLETED your current task and want the user to review your work. Call this when you are done.", "parameters": {"type": "object", "properties": {"summary": {"type": "string", "description": "A summary of what you accomplished"}, "status": {"type": "string", "enum": ["complete", "blocked", "partial"], "description": "complete=task done, blocked=needs user help, partial=some progress made"}}, "required": ["summary"]}}},
    {"type": "function", "function": {"name": "getFileInfo", "description": "Get file metadata (size, modification time, type). Use before reading large files.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file or directory"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "listDirectoryTree", "description": "Get recursive tree view of directory structure. Better than listDirectory for understanding project layout.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Root directory (default: .)"}, "maxDepth": {"type": "integer", "description": "Max recursion depth (default: 3)"}, "ignorePatterns": {"type": "array", "items": {"type": "string"}, "description": "Patterns to ignore (default: ['.git', '__pycache__', 'node_modules'])"}}, "required": []}}},
    {"type": "function", "function": {"name": "replaceMultiple", "description": "Make multiple find/replace operations in one file efficiently", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file"}, "replacements": {"type": "array", "items": {"type": "object", "properties": {"old": {"type": "string"}, "new": {"type": "string"}}}, "description": "Array of {old, new} replacement pairs"}}, "required": ["path", "replacements"]}}},
    {"type": "function", "function": {"name": "gitStatus", "description": "Get current git status - branch, modified files, staged changes", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "gitDiff", "description": "Show git diff for file or entire repo", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Optional path to specific file"}, "staged": {"type": "boolean", "description": "Show staged changes (default: false)"}}, "required": []}}},
    {"type": "function", "function": {"name": "findInFile", "description": "Search for pattern in a specific file with context lines around matches", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file"}, "pattern": {"type": "string", "description": "Text or regex pattern"}, "contextLines": {"type": "integer", "description": "Lines of context (default: 2)"}, "caseSensitive": {"type": "boolean", "description": "Case sensitive search (default: false)"}}, "required": ["path", "pattern"]}}},
    {"type": "function", "function": {"name": "getEnvironmentVariable", "description": "Get environment variable value", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Variable name"}, "default": {"type": "string", "description": "Default if not found"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "validateJson", "description": "Validate JSON file and return detailed error information if invalid", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to JSON file"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "countLines", "description": "Count lines, words, characters in a file. Useful before reading large files.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "backupFile", "description": "Create a backup copy of a file before modifying it", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file"}, "backupSuffix": {"type": "string", "description": "Backup suffix (default: .bak)"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "generateTests", "description": "Auto-generate unit tests for a Python file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to source file"}, "testFramework": {"type": "string", "description": "Test framework (pytest, unittest)"}, "coverage": {"type": "boolean", "description": "Include coverage annotations"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "analyzeTestCoverage", "description": "Analyze test coverage for Python files", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to analyze (default: .)"}}, "required": []}}},
    {"type": "function", "function": {"name": "setBreakpointTrace", "description": "Insert a breakpoint/trace statement in code for debugging", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file"}, "lineNumber": {"type": "integer", "description": "Line number to insert breakpoint"}, "condition": {"type": "string", "description": "Optional condition for conditional breakpoint"}}, "required": ["path", "lineNumber"]}}},
    {"type": "function", "function": {"name": "removeBreakpoints", "description": "Remove all SuperCoder breakpoints from a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "analyzeStackTrace", "description": "Analyze a Python stack trace and extract useful debugging information", "parameters": {"type": "object", "properties": {"errorOutput": {"type": "string", "description": "The error/stack trace text"}}, "required": ["errorOutput"]}}},
    {"type": "function", "function": {"name": "renameSymbol", "description": "Rename a symbol (function, class, variable) across multiple files", "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Current symbol name"}, "newName": {"type": "string", "description": "New symbol name"}, "path": {"type": "string", "description": "Root directory (default: .)"}, "filePattern": {"type": "string", "description": "File pattern (default: *.py)"}}, "required": ["symbol", "newName"]}}},
    {"type": "function", "function": {"name": "generateCommitMessage", "description": "Generate a descriptive commit message based on git diff", "parameters": {"type": "object", "properties": {"staged": {"type": "boolean", "description": "Generate for staged changes (default: true)"}}, "required": []}}},
    {"type": "function", "function": {"name": "createPullRequest", "description": "Create a pull request using GitHub CLI", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "PR title"}, "body": {"type": "string", "description": "PR description"}, "base": {"type": "string", "description": "Base branch (default: main)"}, "head": {"type": "string", "description": "Head branch (default: current)"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "resolveMergeConflict", "description": "Attempt to resolve merge conflicts in a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to file with conflicts"}, "strategy": {"type": "string", "enum": ["ours", "theirs", "both"], "description": "Resolution strategy"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "loadContextGuide", "description": "Load specialized context guides for specific tasks. Use when you recognize a web app request or other specialized task. Available: 'web-apps' (for building Next.js + Supabase applications)", "parameters": {"type": "object", "properties": {"guideName": {"type": "string", "description": "Guide to load: 'web-apps' for web application development"}}, "required": ["guideName"]}}},
    # Selenium Browser Automation Tools
    {"type": "function", "function": {"name": "seleniumStartBrowser", "description": "Start a browser session for automation. Returns session_id to use in other selenium commands.", "parameters": {"type": "object", "properties": {"browser": {"type": "string", "enum": ["chrome", "firefox", "edge"], "description": "Browser type (default: chrome)"}, "headless": {"type": "boolean", "description": "Run without GUI (default: false)"}}, "required": []}}},
    {"type": "function", "function": {"name": "seleniumCloseBrowser", "description": "Close a browser session", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}}, "required": ["sessionId"]}}},
    {"type": "function", "function": {"name": "seleniumListSessions", "description": "List all active browser sessions", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "seleniumNavigate", "description": "Navigate to a URL in the browser", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}, "url": {"type": "string", "description": "URL to navigate to"}}, "required": ["sessionId", "url"]}}},
    {"type": "function", "function": {"name": "seleniumClick", "description": "Click an element on the page", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}, "selector": {"type": "string", "description": "Element selector"}, "selectorType": {"type": "string", "enum": ["css", "xpath", "id", "name", "class", "tag"], "description": "Selector type (default: css)"}}, "required": ["sessionId", "selector"]}}},
    {"type": "function", "function": {"name": "seleniumType", "description": "Type text into an input field", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}, "selector": {"type": "string", "description": "Element selector"}, "text": {"type": "string", "description": "Text to type"}, "selectorType": {"type": "string", "description": "Selector type (default: css)"}, "clearFirst": {"type": "boolean", "description": "Clear field before typing (default: true)"}}, "required": ["sessionId", "selector", "text"]}}},
    {"type": "function", "function": {"name": "seleniumGetElement", "description": "Get element properties (text, attributes, location, size)", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}, "selector": {"type": "string", "description": "Element selector"}, "selectorType": {"type": "string", "description": "Selector type (default: css)"}}, "required": ["sessionId", "selector"]}}},
    {"type": "function", "function": {"name": "seleniumExecuteScript", "description": "Execute JavaScript in the browser", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}, "script": {"type": "string", "description": "JavaScript code to execute"}}, "required": ["sessionId", "script"]}}},
    {"type": "function", "function": {"name": "seleniumScreenshot", "description": "Take a screenshot of the browser. Saves to .supercoder/screenshots/ by default. Use this to capture UI for visual analysis.", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}, "savePath": {"type": "string", "description": "Optional path to save screenshot"}, "elementSelector": {"type": "string", "description": "Optional CSS selector to screenshot specific element"}, "fullPage": {"type": "boolean", "description": "Capture entire scrollable page (default: false)"}}, "required": ["sessionId"]}}},
    {"type": "function", "function": {"name": "seleniumWaitForElement", "description": "Wait for an element to appear on the page", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}, "selector": {"type": "string", "description": "Element selector"}, "selectorType": {"type": "string", "description": "Selector type (default: css)"}, "timeout": {"type": "integer", "description": "Maximum wait time in seconds (default: 10)"}}, "required": ["sessionId", "selector"]}}},
    {"type": "function", "function": {"name": "seleniumGetPageSource", "description": "Get the HTML source of the current page", "parameters": {"type": "object", "properties": {"sessionId": {"type": "integer", "description": "Browser session ID"}}, "required": ["sessionId"]}}},
    # Vision Analysis Tools
    {"type": "function", "function": {"name": "visionSetMode", "description": "Set vision model mode (local or api) and model size", "parameters": {"type": "object", "properties": {"mode": {"type": "string", "enum": ["local", "api"], "description": "Vision mode"}, "modelSize": {"type": "string", "enum": ["2b", "4b", "8b", "32b"], "description": "Model size for local mode"}}, "required": ["mode"]}}},
    {"type": "function", "function": {"name": "visionGetStatus", "description": "Get current vision model configuration and status", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "visionAnalyzeUI", "description": "Analyze a UI screenshot for layout, elements, issues, and suggestions. Use this after taking a screenshot to understand what's on the page.", "parameters": {"type": "object", "properties": {"screenshotPath": {"type": "string", "description": "Path to screenshot file"}, "prompt": {"type": "string", "description": "Optional specific question about the UI"}}, "required": ["screenshotPath"]}}},
    {"type": "function", "function": {"name": "visionFindElement", "description": "Find a UI element by visual description (e.g., 'blue login button')", "parameters": {"type": "object", "properties": {"screenshotPath": {"type": "string", "description": "Path to screenshot"}, "description": {"type": "string", "description": "Natural language description of element"}}, "required": ["screenshotPath", "description"]}}},
    {"type": "function", "function": {"name": "visionVerifyLayout", "description": "Verify that expected UI elements are present and correctly positioned", "parameters": {"type": "object", "properties": {"screenshotPath": {"type": "string", "description": "Path to screenshot"}, "expectedElements": {"type": "array", "items": {"type": "string"}, "description": "List of elements that should be visible"}}, "required": ["screenshotPath", "expectedElements"]}}},
    {"type": "function", "function": {"name": "visionAccessibilityCheck", "description": "Check UI screenshot for accessibility issues (contrast, text size, labels, etc.)", "parameters": {"type": "object", "properties": {"screenshotPath": {"type": "string", "description": "Path to screenshot"}}, "required": ["screenshotPath"]}}},
    {"type": "function", "function": {"name": "visionCompareScreenshots", "description": "Compare two screenshots for visual differences (visual regression testing)", "parameters": {"type": "object", "properties": {"screenshot1Path": {"type": "string", "description": "Path to first screenshot (baseline)"}, "screenshot2Path": {"type": "string", "description": "Path to second screenshot (current)"}}, "required": ["screenshot1Path", "screenshot2Path"]}}}
]


# Model context limits
MODEL_LIMITS = {
    "anthropic/claude-opus-4.5": 200000,
    "anthropic/claude-sonnet-4": 200000,
    "qwen/qwen3-coder": 128000,
    "deepseek/deepseek-v3.2": 160000,
    "qwen/qwen3-235b-a22b": 128000,
    "anthropic/claude-3-opus": 200000,
    "anthropic/claude-3-sonnet": 200000,
    "openai/gpt-4-turbo": 128000,
    "default": 128000
}


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


class Agent:
    def __init__(self, initial_prompt: str, model: str = "qwen/qwen3-coder:free", streaming: bool = False, embedding_model: str = None):
        self.model = model
        self.streaming = streaming
        self.messages = []
        self.context_files = []
        self.mandatory_files = []
        self._context_cache = {}
        self.indexer = FileIndexer()
        self.token_counter = TokenCounter()
        self.max_context = MODEL_LIMITS.get(model, MODEL_LIMITS["default"])
        self.reserved_output = 4096
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

        if used_tokens > available:
            print(f"[WARNING: Mandatory files exceed available context! {used_tokens} tokens used, {available} available]")
        if skipped_files:
            print(f"[Context: {included} files, {len(skipped_files)} optional files skipped, ~{used_tokens} tokens]")
            parts.append("## Skipped files (not included, available via tools):\n")
            for f in skipped_files:
                parts.append(f"- {f}\n")
        return "\n".join(parts)


    def Prompt(self, user_input: str, streaming: bool = None) -> str:
        if streaming is None:
            streaming = self.streaming
        context = self._build_context_string(user_input)
        full_input = f"{context}\n\n{user_input}" if context else user_input
        self.messages.append({"role": "user", "content": full_input})
        response = self._call_api(streaming=streaming)
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
            content, tool_calls = self._call_api_with_tools(tools, streaming=streaming, on_chunk=on_chunk)
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
        self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": str(result)})


    def _call_api(self, streaming: bool = False) -> str:
        """
        Call API without tools. Includes hard timeout protection to prevent infinite hangs.
        """
        max_retries = 5
        max_total_time = 240  # Hard limit: 4 minutes total for all retries
        start_time = time.time()
        
        for attempt in range(max_retries):
            # Check if we've exceeded total time budget
            elapsed = time.time() - start_time
            if elapsed > max_total_time:
                print(f"\n[API call exceeded total time budget of {max_total_time}s]")
                return "[Error: API call timed out]"
            
            try:
                token = TokenManager.get_token()
                
                # Add read timeout for streaming to prevent hangs
                # (connect_timeout, read_timeout)
                # Connect timeout: 10s (just to check if server responds)
                # Read timeout: 180s (for full response to complete)
                timeout = (10, 180) if streaming else (10, 120)
                
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": self.messages,
                        "stream": streaming,
                        "plugins": [{"id": "response-healing"}]
                    },
                    timeout=timeout, stream=streaming
                )
                resp.raise_for_status()
                if streaming:
                    result = ""
                    last_data_time = time.time()
                    stream_timeout = 60  # Max seconds between chunks
                    loop_start = time.time()
                    max_loop_time = 180  # Max 3 minutes for entire stream
                    
                    # Wrap streaming in a thread to prevent indefinite hangs
                    def stream_response():
                        nonlocal result
                        try:
                            for line in resp.iter_lines(decode_unicode=True):
                                # Check for stream timeout (no data received)
                                current_time = time.time()
                                
                                # Hard timeout for entire streaming loop
                                if current_time - loop_start > max_loop_time:
                                    print(f"\n[Stream exceeded max time of {max_loop_time}s]")
                                    return
                                
                                # Timeout between chunks
                                if current_time - last_data_time > stream_timeout:
                                    print(f"\n[Stream timeout: no data for {stream_timeout}s]")
                                    return
                                
                                if line:
                                    last_data_time = current_time  # Reset timeout on data
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
                        except Exception as e:
                            print(f"\n[Stream error: {e}]")
                    
                    # Execute streaming in thread with timeout
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(stream_response)
                        try:
                            future.result(timeout=max_loop_time + 10)  # Extra buffer
                        except concurrent.futures.TimeoutError:
                            print(f"\n[Stream thread timeout after {max_loop_time + 10}s]")
                            raise requests.exceptions.Timeout("Stream thread timeout")
                    
                    print()
                    return result
                else:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 0
                body = ""
                try:
                    body = e.response.text[:500] if e.response else ""
                except:
                    pass
                print(f"[HTTP Error {status}, attempt {attempt + 1}] {body}")
                if status in (401, 403, 429):
                    TokenManager.rotate_token()
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                print(f"[Connection Error, attempt {attempt + 1}] {e}")
                time.sleep(2 ** attempt)
            except requests.exceptions.Timeout as e:
                print(f"[Timeout Error, attempt {attempt + 1}] {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[Error: {type(e).__name__}: {e}, attempt {attempt + 1}]")
                time.sleep(2 ** attempt)
        return "[Error: All API attempts failed]"


    def _call_api_with_tools(self, tools: List[dict], streaming: bool = False, on_chunk=None) -> Tuple[str, List[dict]]:
        """
        Call API with tools. Includes hard timeout protection to prevent infinite hangs.
        """
        max_retries = 5
        max_total_time = 240  # Hard limit: 4 minutes total for all retries
        start_time = time.time()
        
        for attempt in range(max_retries):
            # Check if we've exceeded total time budget
            elapsed = time.time() - start_time
            if elapsed > max_total_time:
                print(f"\n[API call exceeded total time budget of {max_total_time}s]")
                return "[Error: API call timed out]", []
            
            try:
                token = TokenManager.get_token()
                
                # Add read timeout for streaming to prevent hangs
                # (connect_timeout, read_timeout)
                # Connect timeout: 10s (just to check if server responds)
                # Read timeout: 180s (for full response to complete)
                timeout = (10, 180) if streaming else (10, 120)
                
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": self.messages,
                        "tools": tools,
                        "tool_choice": "auto",
                        "stream": streaming,
                        "plugins": [{"id": "response-healing"}]
                    },
                    timeout=timeout, stream=streaming
                )
                resp.raise_for_status()
                
                if streaming:
                    content = ""
                    tool_calls_data = {}
                    last_data_time = [time.time()]  # Use list for nonlocal mutation
                    stream_timeout = 60  # Max seconds between chunks
                    loop_start = time.time()
                    max_loop_time = 180  # Max 3 minutes for entire stream
                    
                    # Wrap streaming in a thread to prevent indefinite hangs
                    def stream_response():
                        nonlocal content, tool_calls_data
                        try:
                            line_count = 0
                            for line in resp.iter_lines(decode_unicode=True):
                                line_count += 1
                                
                                # Check for stream timeout (no data received)
                                current_time = time.time()
                                
                                # Hard timeout for entire streaming loop
                                if current_time - loop_start > max_loop_time:
                                    print(f"\n[Stream exceeded max time of {max_loop_time}s]")
                                    return
                                
                                # Timeout between chunks
                                if current_time - last_data_time[0] > stream_timeout:
                                    print(f"\n[Stream timeout: no data for {stream_timeout}s]")
                                    return
                                
                                if not line:
                                    continue
                                
                                last_data_time[0] = current_time  # Reset timeout on data
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
                                            on_chunk(chunk, line_count)  # Pass line count to callback
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
                                except:
                                    pass
                        except Exception as e:
                            print(f"\n[Stream error: {e}]")
                    
                    # Execute streaming in thread with timeout
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(stream_response)
                        try:
                            future.result(timeout=max_loop_time + 10)  # Extra buffer
                        except concurrent.futures.TimeoutError:
                            print(f"\n[Stream thread timeout after {max_loop_time + 10}s]")
                            raise requests.exceptions.Timeout("Stream thread timeout")
                    
                    # Parse tool calls after streaming completes
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
                body = ""
                try:
                    body = e.response.text[:500] if e.response else ""
                except:
                    pass
                print(f"[HTTP Error {status}, attempt {attempt + 1}] {body}")
                if status in (401, 403, 429):
                    TokenManager.rotate_token()
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                print(f"[Connection Error, attempt {attempt + 1}] {e}")
                time.sleep(2 ** attempt)
            except requests.exceptions.Timeout as e:
                print(f"[Timeout Error, attempt {attempt + 1}] {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[Error: {type(e).__name__}: {e}, attempt {attempt + 1}]")
                time.sleep(2 ** attempt)
        return "[Error: All API attempts failed]", []


def execute_tool(tool_call: dict) -> str:
    """Execute a tool call and return result"""
    from tools import (
        execute_pwsh, control_pwsh_process, list_processes, get_process_output,
        list_directory, read_file, read_multiple_files, read_code, file_search, grep_search,
        delete_file, fs_write, fs_append, str_replace, get_diagnostics, property_coverage,
        insert_lines, remove_lines, move_file, copy_file, create_directory, undo,
        get_symbols, find_references, file_diff, http_request, download_file,
        system_info, run_tests, format_code, web_search, search_stackoverflow,
        interact_with_user, finish,
        get_file_info, list_directory_tree, replace_multiple, git_status, git_diff,
        find_in_file, get_environment_variable, validate_json, count_lines, backup_file,
        generate_tests, analyze_test_coverage, set_breakpoint_trace, remove_breakpoints,
        analyze_stack_trace, rename_symbol, generate_commit_message, create_pull_request,
        resolve_merge_conflict, load_context_guide
    )
    import selenium_tools
    import vision_tools

    name = tool_call["name"]
    args = tool_call.get("args", {})

    REQUIRED_PARAMS = {
        "executePwsh": ["command"], "readFile": ["path"], "fsWrite": ["path", "content"],
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
            result = execute_pwsh(
                args["command"], 
                args.get("timeout", 60),
                args.get("interactiveResponses")
            )
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
                if s.get('imports'):
                    output.append(f"Imports: {len(s['imports'])} imports")
            if 'symbol_search' in result:
                ss = result['symbol_search']
                output.append(f"\n--- Symbol '{ss['symbol']}' found {ss['occurrences']} times ---")
                for loc in ss['locations'][:10]:
                    output.append(f"{'[DEF] ' if loc['is_definition'] else '      '}Line {loc['line']}: {loc['text']}")
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
            if result.get("site_filter"):
                output.append(f"(filtered to: {result['site_filter']})")
            output.append("")
            for i, r in enumerate(result.get("results", []), 1):
                output.append(f"{i}. {r['title']}")
                output.append(f"   URL: {r['url']}")
                if r.get('snippet'):
                    output.append(f"   {r['snippet'][:200]}")
                output.append("")
            return "\n".join(output) or "No results found"
        elif name == "searchStackOverflow":
            result = search_stackoverflow(args["query"], max_results=args.get("maxResults", 5))
            if "error" in result:
                return f"Search error: {result['error']}"
            output = [f"Stack Overflow results for: {result['query']}", ""]
            for i, r in enumerate(result.get("results", []), 1):
                output.append(f"{i}. {r['title']}")
                output.append(f"   URL: {r['url']}")
                if r.get('snippet'):
                    output.append(f"   {r['snippet'][:200]}")
                output.append("")
            return "\n".join(output) or "No results found"
        elif name == "interactWithUser":
            return json.dumps(interact_with_user(args["message"], args.get("interactionType", "info")))
        elif name == "requestUserCommand":
            return json.dumps(request_user_command(args["command"], args["reason"], args.get("workingDirectory")))
        elif name == "finish":
            return json.dumps(finish(args["summary"], args.get("status", "complete")))
        # New tools
        elif name == "getFileInfo":
            return json.dumps(get_file_info(args["path"]))
        elif name == "listDirectoryTree":
            return json.dumps(list_directory_tree(args.get("path", "."), args.get("maxDepth", 3), args.get("ignorePatterns")))
        elif name == "replaceMultiple":
            return json.dumps(replace_multiple(args["path"], args["replacements"]))
        elif name == "gitStatus":
            return json.dumps(git_status())
        elif name == "gitDiff":
            return json.dumps(git_diff(args.get("path"), args.get("staged", False)))
        elif name == "findInFile":
            return json.dumps(find_in_file(args["path"], args["pattern"], args.get("contextLines", 2), args.get("caseSensitive", False)))
        elif name == "getEnvironmentVariable":
            return json.dumps(get_environment_variable(args["name"], args.get("default")))
        elif name == "validateJson":
            return json.dumps(validate_json(args["path"]))
        elif name == "countLines":
            return json.dumps(count_lines(args["path"]))
        elif name == "backupFile":
            return json.dumps(backup_file(args["path"], args.get("backupSuffix", ".bak")))
        elif name == "generateTests":
            return json.dumps(generate_tests(args["path"], args.get("testFramework", "pytest"), args.get("coverage", True)))
        elif name == "analyzeTestCoverage":
            return json.dumps(analyze_test_coverage(args.get("path", ".")))
        elif name == "setBreakpointTrace":
            return json.dumps(set_breakpoint_trace(args["path"], args["lineNumber"], args.get("condition")))
        elif name == "removeBreakpoints":
            return json.dumps(remove_breakpoints(args["path"]))
        elif name == "analyzeStackTrace":
            return json.dumps(analyze_stack_trace(args["errorOutput"]))
        elif name == "renameSymbol":
            return json.dumps(rename_symbol(args["symbol"], args["newName"], args.get("path", "."), args.get("filePattern", "*.py")))
        elif name == "generateCommitMessage":
            return json.dumps(generate_commit_message(args.get("staged", True)))
        elif name == "createPullRequest":
            return json.dumps(create_pull_request(args["title"], args.get("body", ""), args.get("base", "main"), args.get("head")))
        elif name == "resolveMergeConflict":
            return json.dumps(resolve_merge_conflict(args["path"], args.get("strategy", "ours")))
        elif name == "loadContextGuide":
            return json.dumps(load_context_guide(args["guideName"]))
        # Selenium Browser Automation Tools
        elif name == "seleniumStartBrowser":
            return json.dumps(selenium_tools.selenium_start_browser(
                args.get("browser", "chrome"),
                args.get("headless", False)
            ))
        elif name == "seleniumCloseBrowser":
            return json.dumps(selenium_tools.selenium_close_browser(args["sessionId"]))
        elif name == "seleniumListSessions":
            return json.dumps(selenium_tools.selenium_list_sessions())
        elif name == "seleniumNavigate":
            return json.dumps(selenium_tools.selenium_navigate(args["sessionId"], args["url"]))
        elif name == "seleniumClick":
            return json.dumps(selenium_tools.selenium_click(
                args["sessionId"],
                args["selector"],
                args.get("selectorType", "css")
            ))
        elif name == "seleniumType":
            return json.dumps(selenium_tools.selenium_type(
                args["sessionId"],
                args["selector"],
                args["text"],
                args.get("selectorType", "css"),
                args.get("clearFirst", True)
            ))
        elif name == "seleniumGetElement":
            return json.dumps(selenium_tools.selenium_get_element(
                args["sessionId"],
                args["selector"],
                args.get("selectorType", "css")
            ))
        elif name == "seleniumExecuteScript":
            return json.dumps(selenium_tools.selenium_execute_script(
                args["sessionId"],
                args["script"]
            ))
        elif name == "seleniumScreenshot":
            return json.dumps(selenium_tools.selenium_screenshot(
                args["sessionId"],
                args.get("savePath"),
                args.get("elementSelector"),
                args.get("fullPage", False)
            ))
        elif name == "seleniumWaitForElement":
            return json.dumps(selenium_tools.selenium_wait_for_element(
                args["sessionId"],
                args["selector"],
                args.get("selectorType", "css"),
                args.get("timeout", 10)
            ))
        elif name == "seleniumGetPageSource":
            return json.dumps(selenium_tools.selenium_get_page_source(args["sessionId"]))
        # Vision Analysis Tools
        elif name == "visionSetMode":
            return json.dumps(vision_tools.vision_set_mode(
                args["mode"],
                args.get("modelSize", "2b")
            ))
        elif name == "visionGetStatus":
            return json.dumps(vision_tools.vision_get_status())
        elif name == "visionAnalyzeUI":
            return json.dumps(vision_tools.vision_analyze_ui(
                args["screenshotPath"],
                args.get("prompt")
            ))
        elif name == "visionFindElement":
            return json.dumps(vision_tools.vision_find_element(
                args["screenshotPath"],
                args["description"]
            ))
        elif name == "visionVerifyLayout":
            return json.dumps(vision_tools.vision_verify_layout(
                args["screenshotPath"],
                args["expectedElements"]
            ))
        elif name == "visionAccessibilityCheck":
            return json.dumps(vision_tools.vision_accessibility_check(args["screenshotPath"]))
        elif name == "visionCompareScreenshots":
            return json.dumps(vision_tools.vision_compare_screenshots(
                args["screenshot1Path"],
                args["screenshot2Path"]
            ))

        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error executing {name}: {e}"
