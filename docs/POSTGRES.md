# PostgreSQL Integration for Supercoder

Complete guide to using PostgreSQL databases with Supercoder's AI coding assistant.

## Overview

Supercoder now includes comprehensive PostgreSQL integration with 15+ specialized tools for database operations. This allows the AI to:

- Connect to PostgreSQL databases
- Execute queries and commands
- Manage transactions
- Inspect database schema
- Perform CRUD operations
- Handle multiple connections

## Quick Start

### 1. Install Dependencies

```bash
pip install psycopg2-binary
```

Or add to your `requirements.txt`:
```
psycopg2-binary>=2.9.9
```

### 2. Connect to Database

In Supercoder, simply ask:

```
Connect to my PostgreSQL database at localhost with user postgres and password mypassword, database name is mydb
```

Or use a connection string:

```
Connect to PostgreSQL using connection string postgresql://user:pass@localhost:5432/mydb
```

### 3. Start Using

Once connected, you can ask Supercoder to:

```
Show me all tables in the database
```

```
Create a users table with id, email, name, and created_at columns
```

```
Insert a new user with email john@example.com and name John Doe
```

```
Query all users where age is greater than 25
```

## Available Tools

### Connection Management

| Tool | Description |
|------|-------------|
| `postgresConnect` | Connect to a PostgreSQL database |
| `postgresDisconnect` | Close a database connection |
| `postgresListConnections` | List all active connections |

### Schema Inspection

| Tool | Description |
|------|-------------|
| `postgresListTables` | List all tables in a schema |
| `postgresDescribeTable` | Get detailed table structure |
| `postgresCountRows` | Count rows with optional filtering |

### CRUD Operations

| Tool | Description |
|------|-------------|
| `postgresQuery` | Execute SELECT queries |
| `postgresInsert` | Insert rows into tables |
| `postgresUpdate` | Update existing rows |
| `postgresDelete` | Delete rows from tables |
| `postgresExecute` | Execute any SQL (DDL, DML) |

### Transaction Management

| Tool | Description |
|------|-------------|
| `postgresTransactionBegin` | Start a transaction |
| `postgresTransactionCommit` | Commit current transaction |
| `postgresTransactionRollback` | Rollback current transaction |

## Usage Examples

### Example 1: Basic CRUD Operations

**User Request:**
```
Create a products table and add some sample products
```

**Supercoder will:**
1. Connect to the database (if not already connected)
2. Create the table with appropriate columns
3. Insert sample data
4. Verify the data was inserted

### Example 2: Complex Query

**User Request:**
```
Show me all orders from the last 30 days with customer names and total amounts, sorted by total descending
```

**Supercoder will:**
1. Construct a JOIN query between orders and customers tables
2. Add date filtering
3. Sort by total amount
4. Return formatted results

### Example 3: Data Migration

**User Request:**
```
Copy all users from the old_users table to the new users table, but only active users
```

**Supercoder will:**
1. Begin a transaction
2. Query active users from old_users
3. Insert them into users table
4. Verify the migration
5. Commit the transaction

### Example 4: Schema Analysis

**User Request:**
```
Analyze my database schema and suggest improvements
```

**Supercoder will:**
1. List all tables
2. Describe each table structure
3. Check for missing indexes
4. Suggest foreign key relationships
5. Recommend optimizations

## Connection Methods

### Method 1: Connection String (Recommended)

```python
postgresConnect(
    connectionName="mydb",
    connectionString="postgresql://username:password@host:port/database"
)
```

**Advantages:**
- Single parameter
- Easy to use with environment variables
- Standard PostgreSQL format

### Method 2: Individual Parameters

```python
postgresConnect(
    connectionName="mydb",
    host="localhost",
    port=5432,
    database="mydatabase",
    user="username",
    password="password"
)
```

**Advantages:**
- More explicit
- Easier to construct programmatically
- Better for configuration files

### Method 3: Environment Variables (Best Practice)

```python
import os

postgresConnect(
    connectionName="prod",
    connectionString=os.getenv("DATABASE_URL")
)
```

**Advantages:**
- Secure (no hardcoded credentials)
- Environment-specific
- Standard practice for production

## Multiple Connections

Supercoder supports multiple simultaneous database connections:

```python
# Connect to production database
postgresConnect(
    connectionName="prod",
    connectionString="postgresql://user:pass@prod-server:5432/proddb"
)

# Connect to development database
postgresConnect(
    connectionName="dev",
    connectionString="postgresql://user:pass@localhost:5432/devdb"
)

# Use specific connection
postgresQuery(
    connectionName="prod",
    query="SELECT * FROM users"
)
```

## Security Best Practices

### 1. Never Hardcode Credentials

❌ **Bad:**
```python
postgresConnect(
    user="admin",
    password="secretpassword123"
)
```

✅ **Good:**
```python
import os
postgresConnect(
    connectionString=os.getenv("DATABASE_URL")
)
```

### 2. Always Use Parameterized Queries

❌ **Bad (SQL Injection Risk):**
```python
user_input = request.get("username")
postgresQuery(
    query=f"SELECT * FROM users WHERE username = '{user_input}'"
)
```

✅ **Good:**
```python
user_input = request.get("username")
postgresQuery(
    query="SELECT * FROM users WHERE username = %s",
    params=[user_input]
)
```

### 3. Use Transactions for Related Operations

```python
postgresTransactionBegin()

try:
    # Multiple related operations
    postgresExecute(query1, commit=False)
    postgresExecute(query2, commit=False)
    postgresExecute(query3, commit=False)
    
    postgresTransactionCommit()
except:
    postgresTransactionRollback()
```

### 4. Limit Database User Permissions

- Create separate database users for different purposes
- Grant only necessary permissions
- Use read-only users for reporting
- Never use superuser accounts in applications

## Performance Tips

### 1. Use Indexes

```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_orders_user_date ON orders(user_id, order_date);
```

### 2. Limit Result Sets

```sql
SELECT * FROM logs ORDER BY created_at DESC LIMIT 100;
```

### 3. Use EXPLAIN to Analyze Queries

```sql
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'user@example.com';
```

### 4. Batch Operations

Instead of:
```python
for user in users:
    postgresInsert(tableName="users", data=user)
```

Use transactions:
```python
postgresTransactionBegin()
for user in users:
    postgresInsert(tableName="users", data=user)
postgresTransactionCommit()
```

## Common Patterns

### Pattern 1: Upsert (Insert or Update)

```python
# Check if record exists
result = postgresQuery(
    query="SELECT id FROM users WHERE email = %s",
    params=[email],
    fetchAll=False
)

if result["row_count"] > 0:
    # Update existing
    postgresUpdate(
        tableName="users",
        data={"name": name},
        where="email = %s",
        whereParams=[email]
    )
else:
    # Insert new
    postgresInsert(
        tableName="users",
        data={"email": email, "name": name}
    )
```

### Pattern 2: Pagination

```python
page = 1
page_size = 20
offset = (page - 1) * page_size

result = postgresQuery(
    query="SELECT * FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s",
    params=[page_size, offset]
)
```

### Pattern 3: Soft Delete

```python
postgresUpdate(
    tableName="users",
    data={"deleted_at": "NOW()", "status": "deleted"},
    where="id = %s",
    whereParams=[user_id]
)
```

### Pattern 4: Bulk Insert

```python
postgresTransactionBegin()

try:
    for record in records:
        postgresInsert(tableName="data", data=record)
    
    postgresTransactionCommit()
except:
    postgresTransactionRollback()
```

## Troubleshooting

### Connection Issues

**Problem:** "Connection refused"

**Solutions:**
1. Check if PostgreSQL is running
2. Verify host and port
3. Check firewall settings
4. Try `127.0.0.1` instead of `localhost`

**Problem:** "Authentication failed"

**Solutions:**
1. Verify username and password
2. Check `pg_hba.conf` for authentication method
3. Ensure user has access to the database

### Query Issues

**Problem:** "Column does not exist"

**Solutions:**
1. Use `postgresDescribeTable` to check column names
2. Column names are case-sensitive
3. Check for typos

**Problem:** "Syntax error"

**Solutions:**
1. Test query in psql or pgAdmin first
2. Use parameterized queries
3. Check SQL syntax for your PostgreSQL version

### Performance Issues

**Problem:** Slow queries

**Solutions:**
1. Add indexes on frequently queried columns
2. Use `EXPLAIN ANALYZE` to identify bottlenecks
3. Limit result sets with `LIMIT`
4. Consider query optimization

## Integration with Supercoder Features

### With Task Planning

```
plan create a user management system with PostgreSQL backend
```

Supercoder will:
1. Design database schema
2. Create tables with proper relationships
3. Implement CRUD operations
4. Add indexes for performance
5. Create API endpoints
6. Write tests

### With Browser Automation

```
Test the user registration form and verify data is saved to PostgreSQL
```

Supercoder will:
1. Open browser
2. Fill registration form
3. Submit form
4. Query database to verify user was created
5. Report results

### With Vision Analysis

```
Check if the user dashboard displays correct data from the database
```

Supercoder will:
1. Query database for expected data
2. Take screenshot of dashboard
3. Use vision to verify data matches
4. Report any discrepancies

## Advanced Features

### Custom SQL Functions

```python
postgresExecute(
    query="""
        CREATE OR REPLACE FUNCTION get_user_stats(user_id INT)
        RETURNS TABLE(total_orders INT, total_spent DECIMAL) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                COUNT(*)::INT,
                SUM(total)::DECIMAL
            FROM orders
            WHERE orders.user_id = $1;
        END;
        $$ LANGUAGE plpgsql;
    """
)
```

### Triggers

```python
postgresExecute(
    query="""
        CREATE TRIGGER update_modified_timestamp
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_modified_column();
    """
)
```

### Views

```python
postgresExecute(
    query="""
        CREATE VIEW active_users AS
        SELECT * FROM users
        WHERE status = 'active' AND deleted_at IS NULL;
    """
)
```

## Resources

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
- [SQL Tutorial](https://www.postgresql.org/docs/current/tutorial.html)
- [Supercoder PostgreSQL Guide](../Agents/postgres-guide.md)

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [PostgreSQL Guide](../Agents/postgres-guide.md)
3. Open an issue on [GitHub](https://github.com/4lpine/Supercoder/issues)
4. Join our [Discord](https://discord.gg/GyS225bRJx)

---

**Happy coding with PostgreSQL and Supercoder!** 🚀
