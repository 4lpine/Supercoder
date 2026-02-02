# PostgreSQL Integration Guide for Supercoder

This guide covers all PostgreSQL database operations available in Supercoder.

## Table of Contents
1. [Installation](#installation)
2. [Connection Management](#connection-management)
3. [Basic Operations](#basic-operations)
4. [Advanced Queries](#advanced-queries)
5. [Transaction Management](#transaction-management)
6. [Best Practices](#best-practices)
7. [Common Patterns](#common-patterns)
8. [Troubleshooting](#troubleshooting)

---

## Installation

### Install PostgreSQL Driver

```bash
pip install psycopg2-binary
```

Or add to your `requirements.txt`:
```
psycopg2-binary>=2.9.9
```

### Verify Installation

```python
import psycopg2
print(psycopg2.__version__)
```

---

## Connection Management

### Connect to Database

**Method 1: Connection String (Recommended)**

```python
postgresConnect(
    connectionName="mydb",
    connectionString="postgresql://username:password@localhost:5432/mydatabase"
)
```

**Method 2: Individual Parameters**

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

**Environment Variables (Best Practice)**

```python
import os

postgresConnect(
    connectionName="prod",
    connectionString=os.getenv("DATABASE_URL")
)
```

### Multiple Connections

You can maintain multiple database connections simultaneously:

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

# List all connections
postgresListConnections()
```

### Disconnect

```python
# Disconnect specific connection
postgresDisconnect(connectionName="mydb")

# Disconnect default connection
postgresDisconnect()
```

---

## Basic Operations

### List Tables

```python
# List tables in public schema
postgresListTables()

# List tables in specific schema
postgresListTables(schema="myschema")

# List tables in specific connection
postgresListTables(connectionName="prod", schema="public")
```

### Describe Table Structure

```python
# Get table structure
postgresDescribeTable(tableName="users")

# Returns:
# {
#     "table_name": "users",
#     "schema": "public",
#     "columns": [
#         {
#             "column_name": "id",
#             "data_type": "integer",
#             "is_nullable": "NO",
#             "column_default": "nextval('users_id_seq'::regclass)"
#         },
#         {
#             "column_name": "email",
#             "data_type": "character varying",
#             "character_maximum_length": 255,
#             "is_nullable": "NO",
#             "column_default": null
#         }
#     ],
#     "primary_keys": ["id"],
#     "column_count": 2
# }
```

### Count Rows

```python
# Count all rows
postgresCountRows(tableName="users")

# Count with filter
postgresCountRows(
    tableName="users",
    where="status = %s",
    whereParams=["active"]
)
```

---

## Basic CRUD Operations

### INSERT

**Simple Insert**

```python
postgresInsert(
    tableName="users",
    data={
        "email": "user@example.com",
        "name": "John Doe",
        "age": 30
    }
)
```

**Insert with RETURNING**

```python
# Get auto-generated ID
result = postgresInsert(
    tableName="users",
    data={
        "email": "user@example.com",
        "name": "John Doe"
    },
    returning="id"
)

print(result["returned"]["id"])  # e.g., 42
```

**Insert into Specific Schema**

```python
postgresInsert(
    tableName="users",
    schema="myschema",
    data={"email": "user@example.com"}
)
```

### SELECT (Query)

**Simple Query**

```python
result = postgresQuery(
    query="SELECT * FROM users WHERE age > %s",
    params=[25]
)

# Returns:
# {
#     "query": "SELECT * FROM users WHERE age > %s",
#     "row_count": 3,
#     "columns": ["id", "email", "name", "age"],
#     "rows": [
#         {"id": 1, "email": "user1@example.com", "name": "John", "age": 30},
#         {"id": 2, "email": "user2@example.com", "name": "Jane", "age": 28},
#         {"id": 3, "email": "user3@example.com", "name": "Bob", "age": 35}
#     ]
# }
```

**Fetch Single Row**

```python
result = postgresQuery(
    query="SELECT * FROM users WHERE id = %s",
    params=[1],
    fetchAll=False
)

# Returns only one row
```

**Complex Query with JOINs**

```python
result = postgresQuery(
    query="""
        SELECT u.name, o.order_date, o.total
        FROM users u
        JOIN orders o ON u.id = o.user_id
        WHERE o.total > %s
        ORDER BY o.order_date DESC
    """,
    params=[100]
)
```

### UPDATE

**Simple Update**

```python
postgresUpdate(
    tableName="users",
    data={"name": "Jane Smith", "age": 31},
    where="id = %s",
    whereParams=[1]
)
```

**Update Multiple Rows**

```python
postgresUpdate(
    tableName="users",
    data={"status": "inactive"},
    where="last_login < %s",
    whereParams=["2023-01-01"]
)
```

**Update with Complex WHERE**

```python
postgresUpdate(
    tableName="products",
    data={"price": 99.99},
    where="category = %s AND stock > %s",
    whereParams=["electronics", 0]
)
```

### DELETE

**Delete Specific Row**

```python
postgresDelete(
    tableName="users",
    where="id = %s",
    whereParams=[1]
)
```

**Delete Multiple Rows**

```python
postgresDelete(
    tableName="logs",
    where="created_at < %s",
    whereParams=["2023-01-01"]
)
```

**Delete with Complex Condition**

```python
postgresDelete(
    tableName="sessions",
    where="expired = %s AND last_activity < %s",
    whereParams=[True, "2024-01-01"]
)
```

---

## Advanced Queries

### Raw SQL Execution

**DDL Operations (CREATE, ALTER, DROP)**

```python
# Create table
postgresExecute(
    query="""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
)

# Add column
postgresExecute(
    query="ALTER TABLE products ADD COLUMN description TEXT"
)

# Create index
postgresExecute(
    query="CREATE INDEX idx_products_name ON products(name)"
)
```

**Aggregations**

```python
# Count, sum, average
result = postgresQuery(
    query="""
        SELECT 
            category,
            COUNT(*) as product_count,
            AVG(price) as avg_price,
            SUM(stock) as total_stock
        FROM products
        GROUP BY category
        HAVING COUNT(*) > %s
    """,
    params=[5]
)
```

**Subqueries**

```python
result = postgresQuery(
    query="""
        SELECT name, email
        FROM users
        WHERE id IN (
            SELECT user_id 
            FROM orders 
            WHERE total > %s
        )
    """,
    params=[1000]
)
```

**Window Functions**

```python
result = postgresQuery(
    query="""
        SELECT 
            name,
            salary,
            department,
            AVG(salary) OVER (PARTITION BY department) as dept_avg_salary,
            RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank
        FROM employees
    """
)
```

**CTEs (Common Table Expressions)**

```python
result = postgresQuery(
    query="""
        WITH high_value_customers AS (
            SELECT user_id, SUM(total) as lifetime_value
            FROM orders
            GROUP BY user_id
            HAVING SUM(total) > %s
        )
        SELECT u.name, u.email, hvc.lifetime_value
        FROM users u
        JOIN high_value_customers hvc ON u.id = hvc.user_id
        ORDER BY hvc.lifetime_value DESC
    """,
    params=[10000]
)
```

---

## Transaction Management

### Manual Transactions

**Basic Transaction**

```python
# Begin transaction
postgresTransactionBegin()

try:
    # Execute multiple operations
    postgresExecute(
        query="UPDATE accounts SET balance = balance - %s WHERE id = %s",
        params=[100, 1],
        commit=False
    )
    
    postgresExecute(
        query="UPDATE accounts SET balance = balance + %s WHERE id = %s",
        params=[100, 2],
        commit=False
    )
    
    # Commit if all succeeded
    postgresTransactionCommit()
    print("Transaction committed successfully")
    
except Exception as e:
    # Rollback on error
    postgresTransactionRollback()
    print(f"Transaction rolled back: {e}")
```

**Complex Transaction**

```python
postgresTransactionBegin(connectionName="prod")

try:
    # Insert order
    order_result = postgresInsert(
        tableName="orders",
        data={
            "user_id": 1,
            "total": 299.99,
            "status": "pending"
        },
        returning="id",
        connectionName="prod"
    )
    
    order_id = order_result["returned"]["id"]
    
    # Insert order items
    for item in cart_items:
        postgresInsert(
            tableName="order_items",
            data={
                "order_id": order_id,
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "price": item["price"]
            },
            connectionName="prod"
        )
    
    # Update inventory
    for item in cart_items:
        postgresExecute(
            query="UPDATE products SET stock = stock - %s WHERE id = %s",
            params=[item["quantity"], item["product_id"]],
            commit=False,
            connectionName="prod"
        )
    
    # Commit transaction
    postgresTransactionCommit(connectionName="prod")
    print(f"Order {order_id} created successfully")
    
except Exception as e:
    postgresTransactionRollback(connectionName="prod")
    print(f"Order creation failed: {e}")
```

---

## Best Practices

### 1. Always Use Parameterized Queries

**❌ BAD (SQL Injection Risk)**

```python
user_input = "admin' OR '1'='1"
postgresQuery(
    query=f"SELECT * FROM users WHERE username = '{user_input}'"
)
```

**✅ GOOD (Safe)**

```python
user_input = "admin' OR '1'='1"
postgresQuery(
    query="SELECT * FROM users WHERE username = %s",
    params=[user_input]
)
```

### 2. Use Connection Pooling for Production

```python
# For production, consider using connection pooling
# This is handled automatically by psycopg2, but you can configure it:

from psycopg2 import pool

connection_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host="localhost",
    database="mydb",
    user="user",
    password="password"
)
```

### 3. Handle Errors Gracefully

```python
try:
    result = postgresQuery(
        query="SELECT * FROM users WHERE id = %s",
        params=[user_id]
    )
    
    if "error" in result:
        print(f"Query failed: {result['error']}")
        return None
    
    if result["row_count"] == 0:
        print("User not found")
        return None
    
    return result["rows"][0]
    
except Exception as e:
    print(f"Unexpected error: {e}")
    return None
```

### 4. Use Transactions for Related Operations

```python
# Always use transactions when multiple operations must succeed together
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

### 5. Close Connections When Done

```python
# Always disconnect when finished
try:
    # Do database work
    result = postgresQuery(query="SELECT * FROM users")
finally:
    postgresDisconnect()
```

### 6. Use Environment Variables for Credentials

```python
import os

# Never hardcode credentials
postgresConnect(
    connectionString=os.getenv("DATABASE_URL")
)

# Or use individual env vars
postgresConnect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)
```

---

## Common Patterns

### Pattern 1: Pagination

```python
def get_users_page(page=1, page_size=20):
    offset = (page - 1) * page_size
    
    result = postgresQuery(
        query="""
            SELECT * FROM users
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
        params=[page_size, offset]
    )
    
    # Get total count
    count_result = postgresCountRows(tableName="users")
    
    return {
        "users": result["rows"],
        "page": page,
        "page_size": page_size,
        "total": count_result["count"],
        "total_pages": (count_result["count"] + page_size - 1) // page_size
    }
```

### Pattern 2: Bulk Insert

```python
def bulk_insert_users(users):
    postgresTransactionBegin()
    
    try:
        for user in users:
            postgresInsert(
                tableName="users",
                data=user
            )
        
        postgresTransactionCommit()
        return {"status": "success", "inserted": len(users)}
        
    except Exception as e:
        postgresTransactionRollback()
        return {"status": "error", "message": str(e)}
```

### Pattern 3: Upsert (INSERT or UPDATE)

```python
def upsert_user(email, name, age):
    # Check if user exists
    result = postgresQuery(
        query="SELECT id FROM users WHERE email = %s",
        params=[email],
        fetchAll=False
    )
    
    if result["row_count"] > 0:
        # Update existing user
        user_id = result["rows"][0]["id"]
        postgresUpdate(
            tableName="users",
            data={"name": name, "age": age},
            where="id = %s",
            whereParams=[user_id]
        )
        return {"action": "updated", "id": user_id}
    else:
        # Insert new user
        result = postgresInsert(
            tableName="users",
            data={"email": email, "name": name, "age": age},
            returning="id"
        )
        return {"action": "inserted", "id": result["returned"]["id"]}
```

### Pattern 4: Search with Filters

```python
def search_products(filters):
    conditions = []
    params = []
    
    if filters.get("category"):
        conditions.append("category = %s")
        params.append(filters["category"])
    
    if filters.get("min_price"):
        conditions.append("price >= %s")
        params.append(filters["min_price"])
    
    if filters.get("max_price"):
        conditions.append("price <= %s")
        params.append(filters["max_price"])
    
    if filters.get("search"):
        conditions.append("name ILIKE %s")
        params.append(f"%{filters['search']}%")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    result = postgresQuery(
        query=f"SELECT * FROM products WHERE {where_clause} ORDER BY name",
        params=params
    )
    
    return result["rows"]
```

### Pattern 5: Soft Delete

```python
def soft_delete_user(user_id):
    postgresUpdate(
        tableName="users",
        data={
            "deleted_at": "NOW()",
            "status": "deleted"
        },
        where="id = %s",
        whereParams=[user_id]
    )
```

---

## Troubleshooting

### Connection Issues

**Problem: "Connection refused"**

```python
# Check if PostgreSQL is running
# Linux/Mac: sudo systemctl status postgresql
# Windows: Check Services for PostgreSQL

# Verify connection details
postgresConnect(
    host="localhost",  # Try 127.0.0.1 if localhost fails
    port=5432,         # Default PostgreSQL port
    database="postgres",  # Try default database first
    user="postgres",
    password="your_password"
)
```

**Problem: "psycopg2 not installed"**

```bash
# Install the binary version (easier)
pip install psycopg2-binary

# Or build from source (requires PostgreSQL dev libraries)
pip install psycopg2
```

### Query Issues

**Problem: "Column does not exist"**

```python
# Check table structure first
result = postgresDescribeTable(tableName="users")
print(result["columns"])

# Verify column names match exactly (case-sensitive)
```

**Problem: "Syntax error in query"**

```python
# Test query in psql or pgAdmin first
# Use parameterized queries to avoid syntax issues

# Debug: Print the query
query = "SELECT * FROM users WHERE id = %s"
print(f"Query: {query}")
print(f"Params: {[user_id]}")
```

### Transaction Issues

**Problem: "Deadlock detected"**

```python
# Use shorter transactions
# Lock rows in consistent order
# Add timeouts

postgresExecute(
    query="SET lock_timeout = '5s'"
)
```

**Problem: "Transaction already in progress"**

```python
# Always commit or rollback before starting new transaction
try:
    postgresTransactionCommit()
except:
    postgresTransactionRollback()

# Then start new transaction
postgresTransactionBegin()
```

---

## Performance Tips

### 1. Use Indexes

```python
# Create indexes for frequently queried columns
postgresExecute(
    query="CREATE INDEX idx_users_email ON users(email)"
)

# Create composite indexes for multi-column queries
postgresExecute(
    query="CREATE INDEX idx_orders_user_date ON orders(user_id, order_date)"
)
```

### 2. Use EXPLAIN to Analyze Queries

```python
result = postgresQuery(
    query="EXPLAIN ANALYZE SELECT * FROM users WHERE email = %s",
    params=["user@example.com"]
)

print(result["rows"])
```

### 3. Limit Result Sets

```python
# Always use LIMIT for large tables
result = postgresQuery(
    query="SELECT * FROM logs ORDER BY created_at DESC LIMIT 100"
)
```

### 4. Use Connection Pooling

```python
# Reuse connections instead of creating new ones
# Use named connections for different purposes

postgresConnect(connectionName="readonly", ...)
postgresConnect(connectionName="readwrite", ...)
```

---

## Security Checklist

- ✅ Always use parameterized queries
- ✅ Never hardcode credentials
- ✅ Use environment variables for sensitive data
- ✅ Limit database user permissions (principle of least privilege)
- ✅ Use SSL/TLS for remote connections
- ✅ Validate and sanitize user input
- ✅ Use transactions for data integrity
- ✅ Implement proper error handling
- ✅ Log database operations (but not sensitive data)
- ✅ Regularly backup your database

---

## Additional Resources

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
- [SQL Tutorial](https://www.postgresql.org/docs/current/tutorial.html)
- [PostgreSQL Performance Tips](https://wiki.postgresql.org/wiki/Performance_Optimization)

---

**Happy coding with PostgreSQL and Supercoder!** 🚀
