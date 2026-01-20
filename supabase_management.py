"""
Supabase Management API Integration
Provides SQL execution and schema management capabilities
Similar to Supabase MCP but using direct API calls
"""
import requests
from typing import Any, Dict, Optional

class SupabaseManagement:
    """Supabase Management API client"""
    
    def __init__(self):
        self.access_token: Optional[str] = None
        self.project_ref: Optional[str] = None
        self.enabled = False
        self.base_url = "https://api.supabase.com/v1"
    
    def configure(self, access_token: str, project_ref: str) -> Dict[str, Any]:
        """
        Configure with Supabase credentials
        
        Args:
            access_token: Personal Access Token from https://supabase.com/dashboard/account/tokens
            project_ref: Project reference ID (e.g., 'khmnxujtyvgrvgbxfemr')
        
        Returns:
            Configuration status
        """
        self.access_token = access_token
        self.project_ref = project_ref
        self.enabled = True
        
        # Test the connection
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                f"{self.base_url}/projects/{project_ref}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                project = response.json()
                return {
                    "enabled": True,
                    "project_ref": project_ref,
                    "project_name": project.get("name", "Unknown"),
                    "message": "Supabase Management API configured successfully"
                }
            else:
                self.enabled = False
                return {"error": f"Failed to connect: {response.status_code} - {response.text}"}
                
        except Exception as e:
            self.enabled = False
            return {"error": f"Configuration failed: {str(e)}"}
    
    def execute_sql(self, query: str) -> Dict[str, Any]:
        """
        Execute SQL query
        
        Args:
            query: SQL query to execute
        
        Returns:
            Query results
        """
        if not self.enabled:
            return {"error": "Not configured. Use supabase_mgmt_configure first"}
        
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Use the SQL endpoint
            response = requests.post(
                f"{self.base_url}/projects/{self.project_ref}/database/query",
                headers=headers,
                json={"query": query},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "query": query,
                    "result": result
                }
            else:
                return {
                    "error": f"Query failed: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            return {"error": f"Failed to execute SQL: {str(e)}"}
    
    def create_table(self, table: str, columns: Dict[str, str], primary_key: str = "id") -> Dict[str, Any]:
        """
        Create a new table
        
        Args:
            table: Table name
            columns: Dict of column_name: data_type (e.g., {"name": "TEXT", "age": "INTEGER"})
            primary_key: Primary key column (default: "id")
        
        Returns:
            Creation result
        """
        # Build CREATE TABLE statement
        col_defs = [f"{primary_key} BIGSERIAL PRIMARY KEY"]
        col_defs.extend([f"{name} {dtype}" for name, dtype in columns.items()])
        col_defs.append("created_at TIMESTAMPTZ DEFAULT NOW()")
        
        columns_sql = ", ".join(col_defs)
        query = f"CREATE TABLE IF NOT EXISTS {table} ({columns_sql});"
        
        result = self.execute_sql(query)
        
        if "error" not in result:
            # Also enable RLS and create a permissive policy for testing
            rls_query = f"""
            ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
            CREATE POLICY "Allow all for testing" ON {table} FOR ALL USING (true) WITH CHECK (true);
            """
            self.execute_sql(rls_query)
        
        return result
    
    def list_tables(self) -> Dict[str, Any]:
        """List all tables in the public schema"""
        query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """
        return self.execute_sql(query)
    
    def get_table_schema(self, table: str) -> Dict[str, Any]:
        """Get schema information for a table"""
        query = f"""
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = '{table}'
        ORDER BY ordinal_position;
        """
        return self.execute_sql(query)
    
    def drop_table(self, table: str) -> Dict[str, Any]:
        """Drop a table"""
        query = f"DROP TABLE IF EXISTS {table} CASCADE;"
        return self.execute_sql(query)
    
    def disable(self) -> Dict[str, Any]:
        """Disable the management API"""
        self.enabled = False
        self.access_token = None
        self.project_ref = None
        return {"enabled": False, "message": "Supabase Management API disabled"}


# Global instance
_supabase_mgmt: Optional[SupabaseManagement] = None

def get_supabase_mgmt() -> SupabaseManagement:
    """Get or create global instance"""
    global _supabase_mgmt
    if _supabase_mgmt is None:
        _supabase_mgmt = SupabaseManagement()
    return _supabase_mgmt


# Tool functions for Supercoder

def supabase_mgmt_configure(access_token: str, project_ref: str) -> Dict[str, Any]:
    """Configure Supabase Management API with PAT and project ref"""
    mgmt = get_supabase_mgmt()
    return mgmt.configure(access_token, project_ref)


def supabase_mgmt_execute_sql(query: str) -> Dict[str, Any]:
    """Execute raw SQL query"""
    mgmt = get_supabase_mgmt()
    return mgmt.execute_sql(query)


def supabase_mgmt_create_table(table: str, columns: Dict[str, str], primary_key: str = "id") -> Dict[str, Any]:
    """Create a new table with columns"""
    mgmt = get_supabase_mgmt()
    return mgmt.create_table(table, columns, primary_key)


def supabase_mgmt_list_tables() -> Dict[str, Any]:
    """List all tables"""
    mgmt = get_supabase_mgmt()
    return mgmt.list_tables()


def supabase_mgmt_get_schema(table: str) -> Dict[str, Any]:
    """Get table schema"""
    mgmt = get_supabase_mgmt()
    return mgmt.get_table_schema(table)


def supabase_mgmt_drop_table(table: str) -> Dict[str, Any]:
    """Drop a table"""
    mgmt = get_supabase_mgmt()
    return mgmt.drop_table(table)


def supabase_mgmt_disable() -> Dict[str, Any]:
    """Disable Supabase Management API"""
    mgmt = get_supabase_mgmt()
    return mgmt.disable()
