"""
Native Tool Execution Bridge with JSON Healing for AI Models

This module provides a simplified interface for AI models to call
the native PowerShell tool execution with automatic JSON healing.

Usage:
    from native_tool_bridge import call_tool
    result = call_tool("execute_pwsh", {"command": "echo hello"})
"""

from typing import Any, Dict, Optional, Callable
import json
import re
import sys

# Import native tools from tools.py
try:
    from tools import (
        execute_pwsh,
        control_pwsh_process,
        list_processes,
        get_process_output,
        # File operations
        list_directory, read_file, fs_write, fs_append, str_replace,
        delete_file, move_file, copy_file, create_directory,
        # Other tools
        grep_search, file_diff, system_info, http_request,
        git_status, git_diff,
    )
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    print("Warning: tools.py not found. Using mock implementations.", file=sys.stderr)


class JSONHealer:
    """Attempts to fix malformed JSON from model outputs."""
    
    @staticmethod
    def heal(json_str: str) -> tuple[bool, Any]:
        """
        Attempt to repair malformed JSON.
        
        Returns:
            (success, repaired_data or None)
        """
        original = json_str.strip()
        
        # Try parsing as-is first
        try:
            return True, json.loads(original)
        except json.JSONDecodeError:
            pass
        
        # Common fixes to try
        fixes = [
            # Fix 1: Add missing quotes around keys
            lambda s: JSONHealer._fix_unquoted_keys(s),
            # Fix 2: Fix single quotes to double quotes
            lambda s: s.replace("'", '"'),
            # Fix 3: Fix trailing commas
            lambda s: re.sub(r',\s*([}\]])', r'\1', s),
            # Fix 4: Add missing closing braces/brackets
            lambda s: JSONHealer._fix_unclosed_brackets(s),
            # Fix 5: Fix Python True/False/None to JSON true/false/null
            lambda s: JSONHealer._fix_python_literals(s),
        ]
        
        for fix in fixes:
            try:
                fixed = fix(original)
                result = json.loads(fixed)
                return True, result
            except (json.JSONDecodeError, TypeError):
                continue
        
        return False, None
    
    @staticmethod
    def _fix_unquoted_keys(s: str) -> str:
        """Add quotes around unquoted object keys."""
        # Match word characters at start of object
        pattern = r'([{\s,])([A-Za-z_][A-Za-z0-9_]*)\s*:'
        return re.sub(pattern, r'\1"\2":', s)
    
    @staticmethod
    def _fix_unclosed_brackets(s: str) -> str:
        """Attempt to balance brackets."""
        stack = []
        for char in s:
            if char in '([{':
                stack.append(char)
            elif char in ')]}':
                if stack:
                    opener = stack.pop()
                    if (char == ')' and opener != '(') or \
                       (char == ']' and opener != '[') or \
                       (char == '}' and opener != '{'):
                        pass
        
        # Close remaining brackets
        while stack:
            opener = stack.pop()
            if opener == '(': s += ')'
            elif opener == '[': s += ']'
            elif opener == '{': s += '}'
        
        return s
    
    @staticmethod
    def _fix_python_literals(s: str) -> str:
        """Convert Python literals to JSON equivalents."""
        # Word boundaries to avoid matching inside strings
        s = re.sub(r'\bTrue\b', 'true', s)
        s = re.sub(r'\bFalse\b', 'false', s)
        s = re.sub(r'\bNone\b', 'null', s)
        return s


# Tool registry mapping function names to actual functions
_TOOL_REGISTRY: Dict[str, Callable] = {}


def _register_tools():
    """Register available tools."""
    if not TOOLS_AVAILABLE:
        return
    
    _TOOL_REGISTRY.update({
        "execute_pwsh": execute_pwsh,
        "control_pwsh_process": control_pwsh_process,
        "list_processes": list_processes,
        "get_process_output": get_process_output,
        "list_directory": list_directory,
        "read_file": read_file,
        "fs_write": fs_write,
        "fs_append": fs_append,
        "str_replace": str_replace,
        "delete_file": delete_file,
        "move_file": move_file,
        "copy_file": copy_file,
        "create_directory": create_directory,
        "grep_search": grep_search,
        "file_diff": file_diff,
        "system_info": system_info,
        "http_request": http_request,
        "git_status": git_status,
        "git_diff": git_diff,
    })


# Initialize on import
_register_tools()


def call_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call a native tool by name with parameters.
    
    Args:
        tool_name: Name of the tool to call (e.g., "execute_pwsh")
        params: Dictionary of arguments for the tool
    
    Returns:
        Result dictionary with status and data
    """
    if tool_name not in _TOOL_REGISTRY:
        return {
            "status": "error",
            "error": f"Unknown tool: {tool_name}",
            "available_tools": list(_TOOL_REGISTRY.keys())
        }
    
    try:
        func = _TOOL_REGISTRY[tool_name]
        result = func(**params)
        
        # Normalize result to dict
        if isinstance(result, dict):
            return {"status": "success", "result": result}
        return {"status": "success", "result": result}
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "tool": tool_name
        }


def call_with_json_healing(json_input: str) -> Dict[str, Any]:
    """
    Parse JSON input (with healing) and call the appropriate tool.
    
    Args:
        json_input: JSON string describing tool call like:
            {"tool": "execute_pwsh", "params": {"command": "echo hello"}}
    
    Returns:
        Tool execution result or error
    """
    # Try to heal and parse JSON
    success, data = JSONHealer.heal(json_input)
    
    if not success:
        # Try to extract what we can
        return {
            "status": "parse_error",
            "error": "Could not parse JSON input after healing attempts",
            "input": json_input[:500]
        }
    
    # Validate structure
    if not isinstance(data, dict):
        return {"status": "error", "error": "Expected message to be a JSON object"}
    
    tool_name = data.get("tool") or data.get("name") or data.get("function")
    params = data.get("params") or data.get("parameters") or data.get("arguments") or {}
    
    if not tool_name:
        return {"status": "error", "error": "Missing tool name in request"}
    
    # Execute the tool
    return call_tool(tool_name, params)


def example_usage():
    """Show example usage patterns."""
    return """
Examples:

1. Execute a command:
   {"tool": "execute_pwsh", "params": {"command": "dir", "timeout": 30}}

2. List directory:
   {"tool": "list_directory", "params": {"path": "."}}

3. Read a file:
   {"tool": "read_file", "params": {"path": "README.md"}}

4. System info:
   {"tool": "system_info", "params": {}}

5. HTTP request:
   {"tool": "http_request", "params": {"url": "https://api.example.com"}}
"""


def get_available_tools() -> list:
    """Return list of available tool names."""
    return list(_TOOL_REGISTRY.keys())


if __name__ == "__main__":
    print("Native Tool Bridge with JSON Healing")
    print("=" * 40)
    print(f"Tools available: {len(get_available_tools())}")
    print(f"Tools: {', '.join(get_available_tools())}")
    print()
    print(example_usage())
