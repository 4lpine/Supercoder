"""
Supabase integration for Supercoder using the official Python client
Simple configuration via input prompts with persistent storage
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
from supabase import create_client, Client

# Config file location
CONFIG_DIR = Path.home() / ".supercoder"
CONFIG_FILE = CONFIG_DIR / "supabase_config.json"

class SupabaseConnection:
    """Manages Supabase connection and operations"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.url: Optional[str] = None
        self.service_role_key: Optional[str] = None
        self.anon_key: Optional[str] = None
        self.enabled = False
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from disk if it exists"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    url = config.get('url')
                    anon_key = config.get('anon_key')
                    service_role_key = config.get('service_role_key')
                    
                    if url and anon_key:
                        # Silently configure from saved config
                        self.configure(url, anon_key, service_role_key)
        except Exception:
            # Silently fail - config will need to be set up manually
            pass
    
    def _save_config(self) -> None:
        """Save configuration to disk"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            config = {
                'url': self.url,
                'anon_key': self.anon_key,
                'service_role_key': self.service_role_key
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            # Non-fatal - just means config won't persist
            pass
    
    def configure(self, url: str, anon_key: str, service_role_key: str = None) -> Dict[str, Any]:
        """
        Configure Supabase connection
        
        Args:
            url: Supabase project URL (e.g., https://xxx.supabase.co)
            anon_key: Anon/public key
            service_role_key: Service role key (optional, for admin operations)
        
        Returns:
            Configuration status
        """
        try:
            self.url = url
            self.anon_key = anon_key
            self.service_role_key = service_role_key
            
            # Use service role key if provided, otherwise anon key
            key = service_role_key if service_role_key else anon_key
            
            self.client = create_client(url, key)
            
            # Test connection - just verify the client was created successfully
            # Don't query any tables since they may not exist yet
            if self.client:
                self.enabled = True
                self._save_config()  # Persist configuration
                return {
                    "success": True,
                    "enabled": True,
                    "url": url,
                    "using_service_role": bool(service_role_key),
                    "message": "Supabase configured successfully"
                }
            else:
                self.enabled = False
                return {"error": "Failed to create Supabase client"}
            
        except Exception as e:
            self.enabled = False
            return {"error": f"Configuration failed: {str(e)}"}
    
    def execute_sql(self, query: str) -> Dict[str, Any]:
        """
        Execute raw SQL query using RPC
        
        Args:
            query: SQL query to execute
        
        Returns:
            Query results
        """
        if not self.enabled or not self.client:
            return {"error": "Not configured. Use supabase_configure first"}
        
        try:
            # Use the REST API's RPC endpoint for SQL execution
            # Note: This requires a database function to be created
            result = self.client.rpc('exec_sql', {'query': query}).execute()
            
            return {
                "success": True,
                "query": query,
                "data": result.data
            }
            
        except Exception as e:
            return {"error": f"SQL execution failed: {str(e)}"}
    
    def select(self, table: str, columns: str = "*", filters: Dict[str, Any] = None, 
               limit: int = None, order_by: str = None) -> Dict[str, Any]:
        """
        Select data from a table
        
        Args:
            table: Table name
            columns: Columns to select (default: "*")
            filters: Dict of column: value filters (equality only)
            limit: Max rows to return
            order_by: Column to order by
        
        Returns:
            Query results
        """
        if not self.enabled or not self.client:
            return {"error": "Not configured"}
        
        try:
            query = self.client.table(table).select(columns)
            
            if filters:
                for col, val in filters.items():
                    query = query.eq(col, val)
            
            if order_by:
                query = query.order(order_by)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            
            return {
                "success": True,
                "table": table,
                "count": len(result.data),
                "data": result.data
            }
            
        except Exception as e:
            return {"error": f"Select failed: {str(e)}"}
    
    def insert(self, table: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert data into a table
        
        Args:
            table: Table name
            data: Single dict or list of dicts to insert
        
        Returns:
            Insert result
        """
        if not self.enabled or not self.client:
            return {"error": "Not configured"}
        
        try:
            result = self.client.table(table).insert(data).execute()
            
            return {
                "success": True,
                "table": table,
                "inserted": len(result.data),
                "data": result.data
            }
            
        except Exception as e:
            return {"error": f"Insert failed: {str(e)}"}
    
    def update(self, table: str, data: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update data in a table
        
        Args:
            table: Table name
            data: Data to update
            filters: Dict of column: value filters (equality only)
        
        Returns:
            Update result
        """
        if not self.enabled or not self.client:
            return {"error": "Not configured"}
        
        try:
            query = self.client.table(table).update(data)
            
            for col, val in filters.items():
                query = query.eq(col, val)
            
            result = query.execute()
            
            return {
                "success": True,
                "table": table,
                "updated": len(result.data),
                "data": result.data
            }
            
        except Exception as e:
            return {"error": f"Update failed: {str(e)}"}
    
    def delete(self, table: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete data from a table
        
        Args:
            table: Table name
            filters: Dict of column: value filters (equality only)
        
        Returns:
            Delete result
        """
        if not self.enabled or not self.client:
            return {"error": "Not configured"}
        
        try:
            query = self.client.table(table).delete()
            
            for col, val in filters.items():
                query = query.eq(col, val)
            
            result = query.execute()
            
            return {
                "success": True,
                "table": table,
                "deleted": len(result.data)
            }
            
        except Exception as e:
            return {"error": f"Delete failed: {str(e)}"}
    
    def list_tables(self) -> Dict[str, Any]:
        """List all tables in the public schema"""
        if not self.enabled or not self.client:
            return {"error": "Not configured"}
        
        try:
            # Query information_schema
            result = self.client.rpc('get_tables').execute()
            
            return {
                "success": True,
                "tables": result.data
            }
            
        except Exception as e:
            # Fallback: try direct query if RPC not available
            return {"error": f"List tables failed: {str(e)}. You may need to create the get_tables RPC function."}
    
    def get_schema(self, table: str) -> Dict[str, Any]:
        """Get schema information for a table"""
        if not self.enabled or not self.client:
            return {"error": "Not configured"}
        
        try:
            result = self.client.rpc('get_table_schema', {'table_name': table}).execute()
            
            return {
                "success": True,
                "table": table,
                "schema": result.data
            }
            
        except Exception as e:
            return {"error": f"Get schema failed: {str(e)}. You may need to create the get_table_schema RPC function."}
    
    def disable(self) -> Dict[str, Any]:
        """Disable Supabase connection"""
        self.enabled = False
        self.client = None
        self.url = None
        self.anon_key = None
        self.service_role_key = None
        
        # Remove saved config
        try:
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
        except Exception:
            pass
        
        return {"enabled": False, "message": "Supabase disabled"}


# Global instance
_supabase_conn: Optional[SupabaseConnection] = None

def get_supabase() -> SupabaseConnection:
    """Get or create global Supabase connection"""
    global _supabase_conn
    if _supabase_conn is None:
        _supabase_conn = SupabaseConnection()
    return _supabase_conn


# Tool functions for Supercoder

def supabase_status() -> Dict[str, Any]:
    """Check if Supabase is configured and get status"""
    conn = get_supabase()
    return {
        "enabled": conn.enabled,
        "configured": conn.enabled,
        "url": conn.url if conn.enabled else None,
        "using_service_role": bool(conn.service_role_key) if conn.enabled else False
    }


def supabase_configure(url: str, anon_key: str, service_role_key: str = None) -> Dict[str, Any]:
    """
    Configure Supabase connection
    
    Args:
        url: Supabase project URL (https://xxx.supabase.co)
        anon_key: Anon/public key
        service_role_key: Service role key (optional, for admin operations)
    """
    conn = get_supabase()
    return conn.configure(url, anon_key, service_role_key)


def supabase_select(table: str, columns: str = "*", filters: Dict[str, Any] = None, 
                    limit: int = None, order_by: str = None) -> Dict[str, Any]:
    """
    Select data from a table
    
    Args:
        table: Table name
        columns: Columns to select (comma-separated, default: "*")
        filters: Dict of column: value filters
        limit: Max rows to return
        order_by: Column to order by
    """
    conn = get_supabase()
    return conn.select(table, columns, filters, limit, order_by)


def supabase_insert(table: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Insert data into a table
    
    Args:
        table: Table name
        data: Single dict or list of dicts to insert
    """
    conn = get_supabase()
    return conn.insert(table, data)


def supabase_update(table: str, data: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update data in a table
    
    Args:
        table: Table name
        data: Data to update
        filters: Dict of column: value filters
    """
    conn = get_supabase()
    return conn.update(table, data, filters)


def supabase_delete(table: str, filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete data from a table
    
    Args:
        table: Table name
        filters: Dict of column: value filters
    """
    conn = get_supabase()
    return conn.delete(table, filters)


def supabase_execute_sql(query: str) -> Dict[str, Any]:
    """
    Execute raw SQL query (requires RPC function)
    
    Args:
        query: SQL query to execute
    """
    conn = get_supabase()
    return conn.execute_sql(query)


def supabase_list_tables() -> Dict[str, Any]:
    """List all tables in the public schema"""
    conn = get_supabase()
    return conn.list_tables()


def supabase_get_schema(table: str) -> Dict[str, Any]:
    """
    Get schema information for a table
    
    Args:
        table: Table name
    """
    conn = get_supabase()
    return conn.get_schema(table)


def supabase_disable() -> Dict[str, Any]:
    """Disable Supabase connection"""
    conn = get_supabase()
    return conn.disable()
