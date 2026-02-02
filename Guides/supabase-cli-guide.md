# Supabase CLI Usage Guide for Supercoder

## Overview

This guide explains how to use Supabase CLI commands within Supercoder. **Note:** There are no special Supabase tools in Supercoder - you use the Supabase CLI directly via `executePwsh`.

## Prerequisites

1. **Install Supabase CLI:**
   ```bash
   npm install -g supabase
   # or
   brew install supabase/tap/supabase
   ```

2. **Verify installation:**
   ```bash
   supabase --version
   ```

3. **Have your Supabase project credentials ready:**
   - Project URL: `https://xxx.supabase.co`
   - Project Ref: `xxx` (from the URL)
   - Anon/Public Key
   - Service Role Key (optional, for admin operations)

## Common Workflows

### 1. Link Project to Supabase

```python
# Check if already linked
executePwsh("cd your-project; supabase status")

# Link to remote project
executePwsh("cd your-project; supabase link --project-ref YOUR_PROJECT_REF")
```

### 2. Push Migrations to Remote Database

```python
# Push migrations (will prompt for confirmation)
result = executePwsh("cd your-project; supabase db push")

# Handle the confirmation prompt
if result["status"] == "need_input":
    result = executePwsh(sessionId=result["sessionId"], input="Y")
```

### 3. Pull Remote Schema to Local

```python
# Pull schema from remote database
executePwsh("cd your-project; supabase db pull")
```

### 4. Create New Migration

```python
# Create a new migration file
executePwsh("cd your-project; supabase migration new add_users_table")
```

### 5. Generate TypeScript Types

```python
# Generate types from database schema
executePwsh("cd your-project; supabase gen types typescript --local > lib/database.types.ts")
```

### 6. Reset Local Database

```python
# Reset local database to match migrations
executePwsh("cd your-project; supabase db reset")
```

## Handling Interactive Prompts

Supabase CLI commands often prompt for confirmation. Handle them using the session-based approach:

```python
# Start the command
result = executePwsh("cd chat-app; supabase db push")

# Check if it needs input
if result["status"] == "need_input":
    print(f"Prompt: {result['prompt']}")
    print(f"Output so far: {result['stdout']}")
    
    # Respond to the prompt
    result = executePwsh(
        sessionId=result["sessionId"],
        input="Y"  # or "yes", "", "no", etc.
    )
    
    # May need multiple responses
    while result["status"] == "need_input":
        result = executePwsh(
            sessionId=result["sessionId"],
            input=""  # Press Enter for defaults
        )

# Command completed
print(result["stdout"])
```

Common responses:
- `"Y"` or `"yes"` - confirm
- `"N"` or `"no"` - decline  
- `""` - press Enter (accept default)
- Any text - type that text

## Common Issues and Solutions

### Issue: "Project not linked"

**Solution:**
```python
executePwsh("cd your-project; supabase link --project-ref YOUR_PROJECT_REF")
```

### Issue: "Migration history mismatch"

**Solution:**
```python
# Repair migration history
executePwsh("cd your-project; supabase migration repair --status applied 001")

# Or pull remote schema
executePwsh("cd your-project; supabase db pull")
```

### Issue: "Docker not running" (for local development)

**Solution:**
- Supabase CLI requires Docker for local development
- For remote-only operations (link, push, pull), Docker is not needed
- Start Docker Desktop if you need local development

## Database Queries in Your App

For database queries in your Next.js/React app, use the Supabase JavaScript client:

```typescript
// lib/supabase/client.ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

// Usage in components
const { data, error } = await supabase
  .from('users')
  .select('*')
  .limit(10)
```

## Environment Variables

Always use environment variables for Supabase credentials:

```bash
# .env.local
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Complete Example Workflow

```python
# 1. Check if project is linked
result = executePwsh("cd chat-app; supabase status")

# 2. If not linked, link it
if "not linked" in result["stdout"].lower():
    result = executePwsh("cd chat-app; supabase link --project-ref iejbuctvanhklevusxio")
    # Handle any prompts
    while result["status"] == "need_input":
        result = executePwsh(sessionId=result["sessionId"], input="")

# 3. Create migration file
executePwsh("cd chat-app; supabase migration new initial_schema")

# 4. Edit the migration file (use fsWrite or strReplace)
fsWrite(
    "chat-app/supabase/migrations/001_initial_schema.sql",
    """
    CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        email TEXT UNIQUE NOT NULL,
        name TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
)

# 5. Push migration to remote
result = executePwsh("cd chat-app; supabase db push")
if result["status"] == "need_input":
    result = executePwsh(sessionId=result["sessionId"], input="Y")

# 6. Generate TypeScript types
executePwsh("cd chat-app; supabase gen types typescript --local > lib/database.types.ts")

# 7. Verify the migration
executePwsh("cd chat-app; supabase db pull")
```

## Summary

- **No special Supabase tools** - use `executePwsh` with Supabase CLI commands
- **Handle prompts with sessions** - when `status: "need_input"`, use `sessionId` + `input` to respond
- **Always change directory** - use `cd project-dir;` before Supabase commands
- **Use JavaScript client** - for database queries in your app code
- **Environment variables** - never hardcode credentials

**Interactive Response Pattern:**
```python
result = executePwsh("command that prompts")
while result["status"] == "need_input":
    result = executePwsh(sessionId=result["sessionId"], input="Y")
```
