# Supabase Integration Guide

## Setup

1. **Install the Supabase Python client:**
   ```bash
   pip install supabase
   ```

2. **Configure Supabase in Supercoder:**
   ```bash
   supercoder
   > supabase config
   ```
   
   You'll be prompted for:
   - **Project URL**: Your Supabase project URL (e.g., `https://xxxxx.supabase.co`)
   - **Anon Key**: Your public/anon key (safe to use in client-side code)
   - **Service Role Key** (optional): Admin key for bypassing RLS (keep secret!)

3. **Get your credentials:**
   - Go to: https://supabase.com/dashboard/project/_/settings/api
   - Copy your Project URL and API keys

## Commands

- `supabase config` - Interactive configuration
- `supabase status` - Show current connection status
- `supabase disable` - Disable Supabase connection

## Using Supabase Tools

Once configured, the AI agent can use these tools:

### Query Data
```python
# Select all columns
supabaseSelect("users")

# Select specific columns with filters
supabaseSelect("users", columns="id,email,name", filters={"active": True}, limit=10)

# Order results
supabaseSelect("posts", columns="*", orderBy="created_at", limit=5)
```

### Insert Data
```python
# Insert single row
supabaseInsert("users", {"email": "test@example.com", "name": "Test User"})

# Insert multiple rows
supabaseInsert("users", [
    {"email": "user1@example.com", "name": "User 1"},
    {"email": "user2@example.com", "name": "User 2"}
])
```

### Update Data
```python
# Update rows matching filter
supabaseUpdate("users", {"name": "Updated Name"}, {"email": "test@example.com"})
```

### Delete Data
```python
# Delete rows matching filter
supabaseDelete("users", {"email": "test@example.com"})
```

### Schema Operations
```python
# List all tables
supabaseListTables()

# Get table schema
supabaseGetSchema("users")
```

### Raw SQL (Advanced)
```python
# Execute raw SQL (requires RPC function setup)
supabaseExecuteSql("SELECT * FROM users WHERE created_at > NOW() - INTERVAL '7 days'")
```

**Note:** Raw SQL execution requires creating an RPC function in your Supabase database:

```sql
CREATE OR REPLACE FUNCTION exec_sql(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result json;
BEGIN
  EXECUTE query INTO result;
  RETURN result;
END;
$$;
```

## Example Workflow

```bash
# In Supercoder
> supabase config
# Enter your credentials

# Then ask the AI:
> "List all users in the database"
> "Insert a new user with email test@example.com"
> "Show me the schema for the posts table"
> "Delete all inactive users"
```

## Security Notes

- **Anon Key**: Safe for client-side use, respects Row Level Security (RLS)
- **Service Role Key**: Bypasses RLS, use only when needed for admin operations
- Never commit your Service Role Key to version control
- Always use RLS policies to protect your data

## Troubleshooting

**Connection failed:**
- Verify your Project URL is correct (should start with `https://`)
- Check that your API keys are valid
- Ensure your Supabase project is active

**Permission denied:**
- Check your Row Level Security (RLS) policies
- Use Service Role Key if you need admin access
- Verify the table exists and you have access

**Tool not working:**
- Run `supabase status` to check if configured
- Reconfigure with `supabase config` if needed
