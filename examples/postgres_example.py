#!/usr/bin/env python3
"""
PostgreSQL Integration Example for Supercoder

This example demonstrates how to use PostgreSQL with Supercoder.
"""

import os
import sys

# Add parent directory to path to import tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools

def main():
    print("=" * 60)
    print("PostgreSQL Integration Example")
    print("=" * 60)
    print()
    
    # Example 1: Connect to database
    print("1. Connecting to PostgreSQL...")
    result = tools.postgres_connect(
        connection_name="example",
        host="localhost",
        port=5432,
        database="testdb",
        user="postgres",
        password="password"
    )
    
    if "error" in result:
        print(f"   ❌ Connection failed: {result['error']}")
        print()
        print("Make sure PostgreSQL is running and credentials are correct.")
        print("You can also use a connection string:")
        print('   connection_string="postgresql://user:pass@localhost:5432/dbname"')
        return
    
    print(f"   ✅ Connected to {result['database']} at {result['host']}:{result['port']}")
    print(f"   Version: {result['version'][:50]}...")
    print()
    
    # Example 2: List tables
    print("2. Listing tables...")
    result = tools.postgres_list_tables(connection_name="example")
    
    if "error" in result:
        print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   Found {result['table_count']} tables:")
        for table in result['tables'][:5]:  # Show first 5
            print(f"   - {table}")
        if result['table_count'] > 5:
            print(f"   ... and {result['table_count'] - 5} more")
    print()
    
    # Example 3: Create a test table
    print("3. Creating test table 'users'...")
    result = tools.postgres_execute(
        connection_name="example",
        query="""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                age INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    )
    
    if "error" in result:
        print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   ✅ Table created successfully")
    print()
    
    # Example 4: Insert data
    print("4. Inserting test data...")
    users = [
        {"email": "john@example.com", "name": "John Doe", "age": 30},
        {"email": "jane@example.com", "name": "Jane Smith", "age": 28},
        {"email": "bob@example.com", "name": "Bob Johnson", "age": 35}
    ]
    
    for user in users:
        result = tools.postgres_insert(
            connection_name="example",
            table_name="users",
            data=user,
            returning="id"
        )
        
        if "error" in result:
            print(f"   ⚠️  Skipped {user['email']}: {result['error']}")
        else:
            print(f"   ✅ Inserted {user['name']} (ID: {result['returned']['id']})")
    print()
    
    # Example 5: Query data
    print("5. Querying users...")
    result = tools.postgres_query(
        connection_name="example",
        query="SELECT * FROM users WHERE age > %s ORDER BY age",
        params=[25]
    )
    
    if "error" in result:
        print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   Found {result['row_count']} users:")
        for row in result['rows']:
            print(f"   - {row['name']} ({row['email']}) - Age: {row['age']}")
    print()
    
    # Example 6: Update data
    print("6. Updating user...")
    result = tools.postgres_update(
        connection_name="example",
        table_name="users",
        data={"age": 31},
        where="email = %s",
        where_params=["john@example.com"]
    )
    
    if "error" in result:
        print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   ✅ Updated {result['affected_rows']} row(s)")
    print()
    
    # Example 7: Count rows
    print("7. Counting users...")
    result = tools.postgres_count_rows(
        connection_name="example",
        table_name="users"
    )
    
    if "error" in result:
        print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   Total users: {result['count']}")
    print()
    
    # Example 8: Describe table
    print("8. Describing table structure...")
    result = tools.postgres_describe_table(
        connection_name="example",
        table_name="users"
    )
    
    if "error" in result:
        print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   Table: {result['table_name']}")
        print(f"   Columns: {result['column_count']}")
        print(f"   Primary Keys: {', '.join(result['primary_keys'])}")
        print()
        print("   Column Details:")
        for col in result['columns']:
            nullable = "NULL" if col['is_nullable'] == "YES" else "NOT NULL"
            print(f"   - {col['column_name']}: {col['data_type']} {nullable}")
    print()
    
    # Example 9: Transaction example
    print("9. Transaction example (transfer between accounts)...")
    
    # Create accounts table
    tools.postgres_execute(
        connection_name="example",
        query="""
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                balance DECIMAL(10, 2) DEFAULT 0
            )
        """
    )
    
    # Insert test accounts
    tools.postgres_insert(
        connection_name="example",
        table_name="accounts",
        data={"name": "Account A", "balance": 1000}
    )
    
    tools.postgres_insert(
        connection_name="example",
        table_name="accounts",
        data={"name": "Account B", "balance": 500}
    )
    
    # Begin transaction
    tools.postgres_transaction_begin(connection_name="example")
    
    try:
        # Deduct from Account A
        tools.postgres_execute(
            connection_name="example",
            query="UPDATE accounts SET balance = balance - %s WHERE name = %s",
            params=[100, "Account A"],
            commit=False
        )
        
        # Add to Account B
        tools.postgres_execute(
            connection_name="example",
            query="UPDATE accounts SET balance = balance + %s WHERE name = %s",
            params=[100, "Account B"],
            commit=False
        )
        
        # Commit transaction
        tools.postgres_transaction_commit(connection_name="example")
        print("   ✅ Transaction completed: Transferred $100 from A to B")
        
    except Exception as e:
        tools.postgres_transaction_rollback(connection_name="example")
        print(f"   ❌ Transaction failed: {e}")
    print()
    
    # Example 10: Cleanup
    print("10. Cleaning up...")
    tools.postgres_execute(
        connection_name="example",
        query="DROP TABLE IF EXISTS users, accounts"
    )
    print("   ✅ Test tables dropped")
    print()
    
    # Disconnect
    print("11. Disconnecting...")
    result = tools.postgres_disconnect(connection_name="example")
    print(f"   ✅ Disconnected from database")
    print()
    
    print("=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
