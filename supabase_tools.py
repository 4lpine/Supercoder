"""
Supabase Database Integration Tools for SuperCoder
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

# Supabase client will be initialized when enabled
_supabase_client = None
_supabase_enabled = False

def init_supabase(url: str = None, key: str = None) -> Dict[str, Any]:
    """
    Initialize Supabase client with credentials.
    
    Args:
        url: Supabase project URL (or from SUPABASE_URL env var)
        key: Supabase anon/service key (or from SUPABASE_KEY env var)
    
    Returns:
        Dict with initialization status
    """
    global _supabase_client, _supabase_enabled
    
    try:
        from supabase import create_client, Client
    except ImportError:
        return {
            "error": "Supabase not installed. Run: pip install supabase",
            "install_command": "pip install supabase"
        }
    
    # Get credentials
    url = url or os.environ.get("SUPABASE_URL")
    key = key or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        return {
            "error": "Missing credentials. Set SUPABASE_URL and SUPABASE_KEY environment variables or pass them as arguments",
            "example": "supabase init https://xxx.supabase.co your-anon-key"
        }
    
    try:
        _supabase_client = create_client(url, key)
        _supabase_enabled = True
        return {
            "enabled": True,
            "url": url,
            "message": "Supabase initialized successfully"
        }
    except Exception as e:
        return {"error": f"Failed to initialize Supabase: {str(e)}"}


def disable_supabase() -> Dict[str, Any]:
    """Disable Supabase integration"""
    global _supabase_client, _supabase_enabled
    _supabase_client = None
    _supabase_enabled = False
    return {"enabled": False, "message": "Supabase disabled"}


def is_supabase_enabled() -> bool:
    """Check if Supabase is enabled"""
    return _supabase_enabled and _supabase_client is not None


def supabase_query(table: str, operation: str = "select", filters: Dict[str, Any] = None, 
                   data: Dict[str, Any] = None, columns: str = "*") -> Dict[str, Any]:
    """
    Execute a Supabase query.
    
    Args:
        table: Table name
        operation: select, insert, update, delete
        filters: Filter conditions (e.g., {"id": 1, "status": "active"})
        data: Data for insert/update operations
        columns: Columns to select (default: "*")
    
    Returns:
        Dict with query results or error
    """
    if not is_supabase_enabled():
        return {"error": "Supabase not enabled. Use 'supabase on' command first"}
    
    try:
        if operation == "select":
            query = _supabase_client.table(table).select(columns)
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            response = query.execute()
            return {
                "operation": "select",
                "table": table,
                "count": len(response.data),
                "data": response.data
            }
        
        elif operation == "insert":
            if not data:
                return {"error": "Data required for insert operation"}
            
            response = _supabase_client.table(table).insert(data).execute()
            return {
                "operation": "insert",
                "table": table,
                "inserted": len(response.data),
                "data": response.data
            }
        
        elif operation == "update":
            if not data:
                return {"error": "Data required for update operation"}
            
            query = _supabase_client.table(table).update(data)
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            else:
                return {"error": "Filters required for update operation (safety check)"}
            
            response = query.execute()
            return {
                "operation": "update",
                "table": table,
                "updated": len(response.data),
                "data": response.data
            }
        
        elif operation == "delete":
            if not filters:
                return {"error": "Filters required for delete operation (safety check)"}
            
            query = _supabase_client.table(table).delete()
            
            # Apply filters
            for key, value in filters.items():
                query = query.eq(key, value)
            
            response = query.execute()
            return {
                "operation": "delete",
                "table": table,
                "deleted": len(response.data)
            }
        
        else:
            return {"error": f"Unknown operation: {operation}"}
    
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}


def supabase_list_tables() -> Dict[str, Any]:
    """
    List all tables in the Supabase database.
    
    Returns:
        Dict with table list or error
    """
    if not is_supabase_enabled():
        return {"error": "Supabase not enabled. Use 'supabase on' command first"}
    
    try:
        # Query information_schema to get tables
        response = _supabase_client.rpc('get_tables').execute()
        return {
            "tables": response.data if response.data else []
        }
    except Exception as e:
        # Fallback: try to query a few common tables to see what exists
        return {
            "error": "Could not list tables automatically",
            "suggestion": "Use supabaseQuery with a known table name",
            "details": str(e)
        }


def supabase_get_schema(table: str) -> Dict[str, Any]:
    """
    Get schema information for a table.
    
    Args:
        table: Table name
    
    Returns:
        Dict with schema information
    """
    if not is_supabase_enabled():
        return {"error": "Supabase not enabled. Use 'supabase on' command first"}
    
    try:
        # Get a sample row to infer schema
        response = _supabase_client.table(table).select("*").limit(1).execute()
        
        if response.data and len(response.data) > 0:
            sample = response.data[0]
            schema = {
                "table": table,
                "columns": [
                    {
                        "name": key,
                        "type": type(value).__name__,
                        "sample": str(value)[:50] if value else None
                    }
                    for key, value in sample.items()
                ]
            }
            return schema
        else:
            return {
                "table": table,
                "message": "Table exists but is empty",
                "columns": []
            }
    
    except Exception as e:
        return {"error": f"Failed to get schema: {str(e)}"}


def supabase_raw_sql(query: str) -> Dict[str, Any]:
    """
    Execute raw SQL query (requires RPC function setup).
    
    Args:
        query: SQL query string
    
    Returns:
        Dict with query results
    """
    if not is_supabase_enabled():
        return {"error": "Supabase not enabled. Use 'supabase on' command first"}
    
    try:
        # Note: This requires a custom RPC function in Supabase
        response = _supabase_client.rpc('execute_sql', {'query': query}).execute()
        return {
            "query": query,
            "results": response.data
        }
    except Exception as e:
        return {
            "error": "Raw SQL execution failed. You may need to create an RPC function in Supabase.",
            "details": str(e),
            "suggestion": "Use supabaseQuery for standard CRUD operations"
        }


def supabase_count(table: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Count rows in a table.
    
    Args:
        table: Table name
        filters: Optional filter conditions
    
    Returns:
        Dict with count
    """
    if not is_supabase_enabled():
        return {"error": "Supabase not enabled. Use 'supabase on' command first"}
    
    try:
        query = _supabase_client.table(table).select("*", count="exact")
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        response = query.execute()
        return {
            "table": table,
            "count": response.count,
            "filters": filters
        }
    except Exception as e:
        return {"error": f"Count failed: {str(e)}"}
