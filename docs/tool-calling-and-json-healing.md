# Native Tool Calling & JSON Healing in SuperCoder

## Overview

This document explains how native tool calling works in SuperCoder and how OpenRouter's response-healing plugin helps reduce JSON parsing errors by ~80%.

## How Native Tool Calling Works

### The Basic Flow

Native tool calling (also called function calling) enables LLMs to interact with external tools, APIs, and system functions. Here's the complete flow:

1. **User Query** → User sends a request (e.g., "create a Python file")

2. **Context Assembly** → System combines:
   - System prompt (from `Agents/Executor.md`)
   - Tool definitions (from `NATIVE_TOOLS` in `Agentic.py`)
   - Conversation history
   - User message

3. **Tool Decision** → LLM analyzes context and decides:
   - Does this require a tool call?
   - Which tool(s) to call?
   - What parameters to pass?

4. **Tool Execution** → SuperCoder receives the tool call and:
   - Parses the tool name and arguments
   - Executes the actual function (from `tools.py`)
   - Captures the result

5. **Observation** → Tool result is added to conversation as a "tool" message

6. **Response Generation** → LLM receives the tool result and:
   - Generates a natural language response
   - May call additional tools if needed
   - Or calls `finish()` when complete

### What the LLM Actually Returns

When the LLM decides to call a tool, it returns a structured JSON response:

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "fsWrite",
          "arguments": "{\"path\": \"test.py\", \"content\": \"print('hello')\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

**Key points:**
- `content` is `null` when tool calls are made
- `arguments` is a **JSON string** (not an object)
- `finish_reason` is `"tool_calls"` instead of `"stop"`

### Tool Definitions

Tool definitions tell the LLM what tools are available. They're defined in `Agentic.py`:

```python
NATIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fsWrite",
            "description": "Create or overwrite a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    }
                },
                "required": ["path", "content"]
            }
        }
    }
]
```

**Important:** Tool definitions consume tokens on every API call. They're part of the context.

### The Agent Loop

SuperCoder implements an agentic loop in `main.py`:

```python
while state.auto_steps < state.auto_cap:
    # 1. Call LLM with tools
    content, tool_calls = agent.PromptWithTools(prompt, tools=NATIVE_TOOLS)
    
    # 2. If no tool calls, we're done
    if not tool_calls:
        break
    
    # 3. Execute each tool call
    for tc in tool_calls:
        result = execute_tool(tc["name"], tc["args"])
        agent.AddToolResult(tc["id"], tc["name"], result)
    
    # 4. Loop continues with tool results in context
    state.auto_steps += 1
```

This allows the agent to:
- Call multiple tools in sequence
- Use results from one tool to inform the next
- Build up context over multiple iterations

---

## JSON Healing: Fixing Malformed Tool Calls

### The Problem

LLMs sometimes generate malformed JSON in tool call arguments:

**Common issues:**
- Missing closing brackets: `{"path": "test.py", "content": "hello"`
- Trailing commas: `{"path": "test.py", "content": "hello",}`
- Markdown wrappers: ` ```json\n{"path": "test.py"}\n``` `
- Mixed text and JSON: `Here's the file: {"path": "test.py"}`
- Unescaped quotes: `{"content": "He said "hello""}`

These cause `JSON.parse()` to fail, breaking the entire tool calling flow.

### The Solution: Response-Healing Plugin

OpenRouter's response-healing plugin automatically fixes malformed JSON **before** it reaches your application.

**How to enable it:**

In `Agentic.py`, we add the plugin to API requests:

```python
resp = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    json={
        "model": self.model,
        "messages": self.messages,
        "tools": tools,
        "plugins": [{"id": "response-healing"}]  # ← This line
    }
)
```

### How Response-Healing Works

The plugin operates at the OpenRouter API level:

1. **LLM generates response** → May contain malformed JSON in `tool_calls[].function.arguments`

2. **OpenRouter intercepts** → Before sending to client

3. **Validates JSON** → Checks if `arguments` string is valid JSON

4. **Repairs if needed** → Fixes common issues:
   - Adds missing brackets
   - Removes trailing commas
   - Strips markdown wrappers
   - Escapes unescaped quotes

5. **Returns repaired response** → Client receives valid JSON

**Performance:** Adds <1ms latency

**Success rate:** Reduces JSON defects by ~80% according to [OpenRouter's announcement](https://openrouter.ai/docs/guides/features/plugins/response-healing)

### When Response-Healing Activates

The plugin works with:
- ✅ Tool calling (our use case)
- ✅ Structured outputs with `response_format`
- ✅ Non-streaming requests
- ✅ Streaming requests (repairs each chunk)

It does **not** work with:
- ❌ Regular text responses (no JSON to repair)
- ❌ Already-valid JSON (no changes needed)

### Example: Before and After

**Before (malformed):**
```json
{
  "tool_calls": [{
    "function": {
      "name": "fsWrite",
      "arguments": "{\"path\": \"test.py\", \"content\": \"print('hello')\"" // Missing }
    }
  }]
}
```

**After (repaired):**
```json
{
  "tool_calls": [{
    "function": {
      "name": "fsWrite",
      "arguments": "{\"path\": \"test.py\", \"content\": \"print('hello')\"}" // Fixed!
    }
  }]
}
```

---

## Implementation in SuperCoder

### Where Tool Calling Happens

**1. Tool Definitions** (`Agentic.py`)
- `NATIVE_TOOLS` array defines all available tools
- Sent with every API request

**2. API Calls** (`Agentic.py`)
- `_call_api_with_tools()` sends tools to OpenRouter
- Includes `plugins: [{"id": "response-healing"}]`
- Handles both streaming and non-streaming

**3. Tool Execution** (`main.py`)
- Parses tool calls from LLM response
- Calls `execute_tool()` from `tools.py`
- Adds results back to conversation

**4. Tool Implementations** (`tools.py`)
- Actual Python functions that do the work
- Return results as strings or dicts

### Error Handling

Even with response-healing, we still handle errors:

```python
try:
    args = json.loads(tc["function"]["arguments"])
except json.JSONDecodeError as e:
    # Fallback: try to extract args manually
    # Or return error to LLM so it can retry
    result = {"error": f"Invalid JSON: {e}"}
```

This provides a safety net for edge cases the plugin can't fix.

### Streaming with Tool Calls

When streaming is enabled, tool calls arrive in chunks:

```python
for chunk in response.iter_lines():
    data = json.loads(chunk)
    delta = data["choices"][0]["delta"]
    
    if "tool_calls" in delta:
        # Accumulate tool call chunks
        # Response-healing repairs each chunk
```

The plugin ensures each chunk contains valid JSON.

---

## Best Practices

### 1. Clear Tool Descriptions

Help the LLM generate correct tool calls:

```python
{
    "name": "fsWrite",
    "description": "Create or overwrite a file. Use this when the user wants to create a new file or replace existing content.",
    "parameters": {
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file (e.g., 'src/main.py')"
            }
        }
    }
}
```

### 2. Validate Tool Arguments

Even with healing, validate inputs:

```python
def fs_write(path: str, content: str):
    if not isinstance(path, str):
        return {"error": "path must be a string"}
    if not isinstance(content, str):
        return {"error": "content must be a string"}
    # ... actual implementation
```

### 3. Return Structured Results

Make it easy for the LLM to understand results:

```python
# Good
return {"written": path, "bytes": len(content)}

# Avoid
return "File written successfully"
```

### 4. Handle Tool Errors Gracefully

Return errors as structured data:

```python
try:
    Path(path).write_text(content)
    return {"success": True, "path": path}
except Exception as e:
    return {"error": str(e), "path": path}
```

The LLM can then decide how to handle the error (retry, ask user, etc.)

### 5. Keep Tool Definitions Concise

Tool definitions consume tokens. Be descriptive but concise:

```python
# Good (concise but clear)
"description": "Search for files by name pattern"

# Avoid (too verbose)
"description": "This function allows you to search through the filesystem to find files that match a given pattern. It will recursively search through directories and return a list of matching file paths."
```

---

## Debugging Tool Calls

### Enable Verbose Mode

In SuperCoder, use `verbose on` to see full tool call details:

```
▸ fsWrite(path='test.py', content='print("hello")')
╭──────────────────────────────────────────────────────────────────────
│ FILE: test.py
│ CONTENT (13 chars):
├──────────────────────────────────────────────────────────────────────
│    1 print("hello")
├──────────────────────────────────────────────────────────────────────
│ RESULT:
│ {"written": "test.py", "bytes": 13}
╰──────────────────────────────────────────────────────────────────────
```

### Check Raw API Responses

Add logging to see what OpenRouter returns:

```python
print(f"[DEBUG] Raw response: {resp.text}")
```

### Common Issues

**Tool not being called:**
- Check tool description is clear
- Verify tool is in `NATIVE_TOOLS` array
- Check if model supports tool calling

**Wrong arguments:**
- Improve parameter descriptions
- Add examples in descriptions
- Use `enum` to constrain values

**JSON parse errors (even with healing):**
- Check if model supports tool calling well
- Try a different model
- Add manual fallback parsing

---

## References

- [OpenRouter Tool Calling Docs](https://openrouter.ai/docs/guides/features/tool-calling)
- [OpenRouter Response-Healing Plugin](https://openrouter.ai/docs/guides/features/plugins/response-healing)
- [Response-Healing Announcement](https://openrouter.ai/announcements/response-healing-reduce-json-defects-by-80percent)

---

*Content rephrased for compliance with licensing restrictions. Original information from OpenRouter documentation and research articles.*
