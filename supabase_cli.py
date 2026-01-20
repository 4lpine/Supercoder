"""
Supabase CLI wrapper tools for Supercoder
Provides non-interactive Supabase CLI commands
"""
import subprocess
from typing import Any, Dict, Optional

def _run_supabase_cmd(command: str, cwd: str = None) -> Dict[str, Any]:
    """Run a Supabase CLI command"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def supabase_db_push(project_path: str = ".", project_ref: str = None) -> Dict[str, Any]:
    """
    Push local migrations to remote Supabase database
    
    Args:
        project_path: Path to project with supabase folder (default: current dir)
        project_ref: Optional project reference (if not linked)
    
    Returns:
        Command result
    """
    cmd = "supabase db push"
    if project_ref:
        cmd += f" --project-ref {project_ref}"
    
    return _run_supabase_cmd(cmd, cwd=project_path)


def supabase_db_pull(project_path: str = ".", project_ref: str = None) -> Dict[str, Any]:
    """
    Pull remote schema to local migrations
    
    Args:
        project_path: Path to project
        project_ref: Optional project reference
    
    Returns:
        Command result
    """
    cmd = "supabase db pull"
    if project_ref:
        cmd += f" --project-ref {project_ref}"
    
    return _run_supabase_cmd(cmd, cwd=project_path)


def supabase_gen_types(project_path: str = ".", project_ref: str = None, lang: str = "typescript") -> Dict[str, Any]:
    """
    Generate types from database schema
    
    Args:
        project_path: Path to project
        project_ref: Optional project reference
        lang: Language (typescript, go, swift, kotlin)
    
    Returns:
        Command result with types in stdout
    """
    cmd = f"supabase gen types {lang}"
    if project_ref:
        cmd += f" --project-ref {project_ref}"
    else:
        cmd += " --local"
    
    return _run_supabase_cmd(cmd, cwd=project_path)


def supabase_projects_list() -> Dict[str, Any]:
    """
    List all Supabase projects
    
    Returns:
        Command result with projects list
    """
    return _run_supabase_cmd("supabase projects list")


def supabase_status(project_path: str = ".") -> Dict[str, Any]:
    """
    Check Supabase project status
    
    Args:
        project_path: Path to project
    
    Returns:
        Status information
    """
    return _run_supabase_cmd("supabase status", cwd=project_path)


def supabase_db_reset(project_path: str = ".") -> Dict[str, Any]:
    """
    Reset local database
    
    Args:
        project_path: Path to project
    
    Returns:
        Command result
    """
    return _run_supabase_cmd("supabase db reset", cwd=project_path)


def supabase_migration_new(name: str, project_path: str = ".") -> Dict[str, Any]:
    """
    Create a new migration file
    
    Args:
        name: Migration name
        project_path: Path to project
    
    Returns:
        Command result
    """
    return _run_supabase_cmd(f"supabase migration new {name}", cwd=project_path)


def supabase_db_diff(name: str, project_path: str = ".") -> Dict[str, Any]:
    """
    Create migration from local database changes
    
    Args:
        name: Migration name
        project_path: Path to project
    
    Returns:
        Command result
    """
    return _run_supabase_cmd(f"supabase db diff -f {name}", cwd=project_path)


def supabase_link(project_ref: str, project_path: str = ".") -> Dict[str, Any]:
    """
    Link project to a Supabase project (non-interactive)
    
    Args:
        project_ref: Supabase project reference ID (e.g., 'khmnxujtyvgrvgbxfemr')
        project_path: Path to project
    
    Returns:
        Command result
    """
    cmd = f"supabase link --project-ref {project_ref}"
    return _run_supabase_cmd(cmd, cwd=project_path)


def supabase_unlink(project_path: str = ".") -> Dict[str, Any]:
    """
    Unlink project from Supabase
    
    Args:
        project_path: Path to project
    
    Returns:
        Command result
    """
    return _run_supabase_cmd("supabase unlink", cwd=project_path)
