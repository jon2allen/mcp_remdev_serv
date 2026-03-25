import os
import asyncio
import logging
import sys
import subprocess
import tempfile
import re
import shlex
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP

# --- Logging setup ---
LOG_FILE = "mcp_remdev_serv.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger("mcp_remdev_serv")

# --- Configuration from Environment Variables ---
# Required for Antigravity remote dev session
REMOTE_HOST = os.environ.get("REMOTE_HOST")
REMOTE_PORT = os.environ.get("REMOTE_PORT", "22")
REMOTE_USER = os.environ.get("REMOTE_USER")  # Optional: assume user in ssh config if not set
REMOTE_START_DIR = os.environ.get("REMOTE_START_DIR") or os.environ.get("REMOTE_DIR", ".")
REMOTE_OS_TYPE = os.environ.get("REMOTE_OS_TYPE", "linux").lower()

# Security settings (matching template structure)
PROHIBITED_COMMANDS = os.environ.get("REMOTE_PROHIBITED_CMDS", "rm ,mv ,sudo ,su ").split(",")
RESTRICTED_FILES = os.environ.get("REMOTE_RESTRICTED_FILES", "").split(",")
OVERRIDE_SECURITY = os.environ.get("REMOTE_OVERRIDE_SECURITY", "true").lower() == "true"

# --- State Management ---
class SessionState:
    def __init__(self, start_dir: str):
        self.current_remote_dir = start_dir

state = SessionState(REMOTE_START_DIR)

# --- SSH Utility Functions ---

def get_ssh_cmd_base() -> List[str]:
    """Constructs the base ssh command arguments."""
    base = ["ssh", "-o", "BatchMode=yes", "-p", REMOTE_PORT]
    if REMOTE_USER:
        base.append(f"{REMOTE_USER}@{REMOTE_HOST}")
    else:
        base.append(REMOTE_HOST)
    return base

class ExecResult:
    """A simple data class to hold the result of a command execution."""
    def __init__(self, stdout: str, stderr: str, code: Optional[int] = None):
        self.stdout = stdout
        self.stderr = stderr
        self.code = code

async def exec_remote_command(command: str, stdin: Optional[str] = None) -> ExecResult:
    """Executes a command on the remote server asynchronously via SSH."""
    if not REMOTE_HOST:
        return ExecResult("", "Error: REMOTE_HOST environment variable not set", 1)

    # Prepend directory change to the command
    # We use '&&' to ensure the command only runs if 'cd' succeeds
    # We use sh -c to ensure consistent behavior across different remote shells
    remote_shell_command = f"cd {state.current_remote_dir} && {command}"
    
    ssh_args = get_ssh_cmd_base() + [remote_shell_command]
    
    logger.debug("Executing remote command: %s", " ".join(ssh_args))
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *ssh_args,
            stdin=asyncio.subprocess.PIPE if stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout_bytes, stderr_bytes = await proc.communicate(
            input=stdin.encode("utf-8") if stdin else None
        )
        
        return ExecResult(
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
            proc.returncode
        )
    except Exception as e:
        logger.error("SSH execution failed: %s", e)
        return ExecResult("", str(e), 1)

def format_result_messages(result: ExecResult) -> List[Dict[str, Any]]:
    """Formats the execution result into a list of MCP content dictionaries."""
    messages = []
    if result.code is not None:
        messages.append({"type": "text", "text": str(result.code), "name": "EXIT_CODE"})
    if result.stdout:
        messages.append({"type": "text", "text": result.stdout, "name": "STDOUT"})
    if result.stderr:
        messages.append({"type": "text", "text": result.stderr, "name": "STDERR"})
    return messages

# --- Command Blocking Logic (from template) ---

def is_command_blocked(command: str) -> bool:
    """Checks if a command contains prohibited whole words."""
    if OVERRIDE_SECURITY:
        return False
    
    cleaned_prohibited = [cmd.strip() for cmd in PROHIBITED_COMMANDS if cmd.strip()]
    if not cleaned_prohibited:
        return False

    pattern = r'\b(' + '|'.join(re.escape(cmd) for cmd in cleaned_prohibited) + r')\b[\s-]'
    command_parts = re.split(r'[;&|]+', command)
    command_lower = command.lower()

    for part in command_parts:
        if re.search(pattern, part.strip().lower()):
            return True

    for block in cleaned_prohibited:
        if re.search(rf'\b{re.escape(block)}\b', command_lower):
            return True

    return False

def is_restricted_file_access(command: str) -> bool:
    """Checks if a command involves accessing restricted files."""
    if OVERRIDE_SECURITY:
        return False
        
    for restricted_file in RESTRICTED_FILES:
        if restricted_file and restricted_file in command:
            return True
    return False

# --- MCP Tool Definitions ---

mcp = FastMCP("mcp-remdev-serv")

async def remote_system_info() -> Dict[str, str]:
    """Provides basic information about the remote operating system."""
    logger.info("remote_system_info() called")
    return {
        "host": REMOTE_HOST,
        "port": REMOTE_PORT,
        "os_type": REMOTE_OS_TYPE,
        "current_dir": state.current_remote_dir
    }

async def run_command(
    command: str,
    stdin: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a shell command on the remote machine and get the output.

    Args:
        command: The shell command to execute on the remote server.
        stdin: Optional stdin to pipe into the command.
    """
    logger.info("Received run_command: %s", command)

    if is_command_blocked(command):
        logger.warning("Blocked command denied: '%s'", command)
        return {
            "content": [
                {"type": "text", "text": "1", "name": "EXIT_CODE"},
                {"type": "text", "text": "Security block: This command is prohibited.\n", "name": "STDERR"},
            ],
            "is_error": True
        }

    if is_restricted_file_access(command):
        logger.warning("Restricted file access denied: '%s'", command)
        return {
            "content": [
                {"type": "text", "text": "1", "name": "EXIT_CODE"},
                {"type": "text", "text": "Security block: Access to this file is restricted.\n", "name": "STDERR"},
            ],
            "is_error": True
        }

    exec_result = await exec_remote_command(command, stdin)
    
    return {
        "content": format_result_messages(exec_result),
        "is_error": exec_result.code != 0
    }

async def get_current_dir() -> str:
    """
    Get the current working directory on the remote server.
    """
    logger.info("Received get_current_dir")
    return state.current_remote_dir

async def change_dir(new_dir: str) -> str:
    """
    Change the current working directory on the remote server.
    Paths can be absolute or relative to the current directory.
    
    Returns:
        The new absolute path on success, or an error message.
    """
    logger.info("Received change_dir: %s", new_dir)
    
    # We validate by running 'pwd' in the new directory
    # Note: we use -P to get the physical path if possible
    test_cmd = f"cd {new_dir} && pwd"
    result = await exec_remote_command(test_cmd)
    
    if result.code == 0:
        state.current_remote_dir = result.stdout.strip()
        logger.info("Directory changed to: %s", state.current_remote_dir)
        return state.current_remote_dir
    else:
        logger.warning("Failed to change directory: %s", result.stderr)
        return f"error: invalid directory - {result.stderr.strip()}"

async def file_write(
    file_path: str,
    content: str
) -> str:
    """
    Write text content to a file on the remote server.
    If file_path is relative, it is resolved against the current remote working directory.
    Uses scp for reliable transfer.

    Args:
        file_path: Remote path to the file.
        content: Text content to write.
    """
    logger.info("Received file_write: %s", file_path)
    
    # Check restrictions
    if is_restricted_file_access(file_path):
        return "Error: Access to this file is restricted."

    # Create local temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tf:
        tf.write(content)
        temp_local_path = tf.name
        
    try:
        # Determine remote destination
        remote_dest = file_path
        if not (remote_dest.startswith("/") or remote_dest.startswith("~")):
            remote_dest = os.path.join(state.current_remote_dir, remote_dest)
            
        # scp -P port local_file [user@]host:remote_path
        remote_spec = f"{REMOTE_HOST}:{remote_dest}"
        if REMOTE_USER:
            remote_spec = f"{REMOTE_USER}@{remote_spec}"
            
        scp_args = ["scp", "-P", REMOTE_PORT, "-o", "BatchMode=yes", temp_local_path, remote_spec]
        
        logger.debug("Executing scp: %s", " ".join(scp_args))
        
        proc = await asyncio.create_subprocess_exec(
            *scp_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            logger.info("Successfully wrote file to %s", remote_dest)
            return f"Successfully wrote to {remote_dest}"
        else:
            err_msg = stderr.decode("utf-8").strip()
            logger.error("SCP failed: %s", err_msg)
            return f"Error writing file via scp: {err_msg}"
    finally:
        if os.path.exists(temp_local_path):
            os.remove(temp_local_path)

async def view_file(
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    grep_pattern: Optional[str] = None
) -> str:
    """
    View the content of a file on the remote server.
    
    Args:
        file_path: Path to the file on the remote server.
        start_line: Optional start line number (1-based, inclusive).
        end_line: Optional end line number (1-based, inclusive).
        grep_pattern: Optional extended regular expression to filter lines.
    """
    logger.info("Received view_file: %s (start=%s, end=%s, grep=%s)", 
                file_path, start_line, end_line, grep_pattern)
    
    if is_restricted_file_access(file_path):
        return "Error: Access to this file is restricted."

    # Construct the command
    if grep_pattern:
        # Use grep -E for extended regex support
        cmd = f"grep -E {shlex.quote(grep_pattern)} {shlex.quote(file_path)}"
        if start_line or end_line:
             sed_cmd = ""
             if start_line and end_line:
                 sed_cmd = f" | sed -n '{start_line},{end_line}p'"
             elif start_line:
                 sed_cmd = f" | sed -n '{start_line},$p'"
             elif end_line:
                 sed_cmd = f" | sed -n '1,{end_line}p'"
             cmd += sed_cmd
    else:
        if start_line or end_line:
            # use sed for slicing
            if start_line and end_line:
                cmd = f"sed -n '{start_line},{end_line}p' {shlex.quote(file_path)}"
            elif start_line:
                cmd = f"sed -n '{start_line},$p' {shlex.quote(file_path)}"
            elif end_line:
                cmd = f"sed -n '1,{end_line}p' {shlex.quote(file_path)}"
        else:
            # Default to first 2000 lines as per OpenCode/Vibe inspiration
            cmd = f"head -n 2000 {shlex.quote(file_path)}"
        
    result = await exec_remote_command(cmd)
    
    if result.code == 0:
        return result.stdout
    else:
        return f"Error viewing file: {result.stderr.strip()}"

async def list_dir(directory_path: str = ".", sort_by: str = "name") -> str:
    """
    List the contents of a directory on the remote server.
    
    Args:
        directory_path: Path to list (absolute or relative to current dir).
        sort_by: 'name' or 'time' (last modified).
    """
    logger.info("Received list_dir: %s (sort_by=%s)", directory_path, sort_by)
    
    # ls -F: mark dirs with / and executables with *
    # ls -t: sort by time (newest first)
    ls_flags = "-F"
    if sort_by == "time":
        ls_flags += "t"
        
    cmd = f"ls {ls_flags} {shlex.quote(directory_path)}"
    result = await exec_remote_command(cmd)
    
    if result.code == 0:
        return result.stdout
    else:
        return f"Error listing directory: {result.stderr.strip()}"

async def find_by_name(
    pattern: str,
    search_directory: str = ".",
    max_depth: Optional[int] = None,
    type_filter: str = "any", # any, file, directory
    sort_by: str = "name" # name or time
) -> str:
    """
    Search for files and directories matching a pattern.
    
    Args:
        pattern: The glob-style pattern to search for (use * for wildcards).
        search_directory: Where to start searching.
        max_depth: Optional maximum search depth.
        type_filter: One of "any", "file", or "directory".
        sort_by: 'name' or 'time' (newest first).
    """
    logger.info("Received find_by_name: %s in %s (sort_by=%s)", pattern, search_directory, sort_by)
    
    cmd = f"find {shlex.quote(search_directory)}"
    if max_depth is not None:
        cmd += f" -maxdepth {max_depth}"
    
    if type_filter == "file":
        cmd += " -type f"
    elif type_filter == "directory":
        cmd += " -type d"
        
    # We escape the pattern for the shell
    cmd += f" -name {shlex.quote(pattern)}"
    
    if sort_by == "time":
        # For cross-platform support (FreeBSD, Linux), we'll piping to ls -t
        # This will sort based on the results from find
        # We use xargs to handle the filenames
        cmd += " -print0 | xargs -0 ls -td"
    
    result = await exec_remote_command(cmd)
    
    if result.code == 0:
        return result.stdout
    else:
        return f"Error finding files: {result.stderr.strip()}"

async def grep_search(
    query: str,
    search_path: str = ".",
    case_insensitive: bool = True,
    is_regex: bool = False
) -> str:
    """
    Search for text patterns within files on the remote server.
    
    Args:
        query: The string or pattern to search for.
        search_path: Directory or file to search within.
        case_insensitive: Whether to ignore case.
        is_regex: Whether the query should be treated as a regex.
    """
    logger.info("Received grep_search: '%s' in %s", query, search_path)
    
    # Flags: 
    # -r: recursive
    # -n: show line numbers
    # -I: ignore binary files
    flags = "-rnI"
    if case_insensitive:
        flags += "i"
    if is_regex:
        flags += "E"
    else:
        flags += "F" # Fixed string
        
    cmd = f"grep {flags} {shlex.quote(query)} {shlex.quote(search_path)}"
    result = await exec_remote_command(cmd)
    
    # grep returns 0 on match, 1 on no match, 2 on error
    if result.code == 0:
        return result.stdout
    elif result.code == 1:
        return "" # No matches found
    else:
        return f"Error in grep_search: {result.stderr.strip()}"

async def replace_file_content(
    file_path: str,
    target_content: str,
    replacement_content: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    replace_all: bool = False
) -> str:
    """
    Replace a specific block of text in a remote file.
    
    Args:
        file_path: Path to the remote file.
        target_content: The exact text to be replaced.
        replacement_content: The text to replace with.
        start_line: Optional line constraint (1-based, inclusive).
        end_line: Optional line constraint (1-based, inclusive).
        replace_all: If True, replace all occurrences in the file.
    """
    logger.info("Received replace_file_content for %s (replace_all=%s)", file_path, replace_all)
    
    # Strategy: Read the file, replace in memory on host, write back via file_write
    
    # We use view_file with a large limit for full file read
    # If file_write was to be used on huge files, we'd need a different strategy
    current_content = await view_file(file_path)
    if current_content.startswith("Error"):
        return current_content
        
    if target_content not in current_content:
        return "Error: targetContent not found in the file."
    
    count = current_content.count(target_content)
    if not replace_all and count > 1 and (start_line is None or end_line is None):
        return f"Error: targetContent appears {count} times. Please provide line constraints, ensure it is unique, or set replace_all=True."
    
    if replace_all:
        new_content = current_content.replace(target_content, replacement_content)
    else:
        new_content = current_content.replace(target_content, replacement_content, 1)
    
    return await file_write(file_path, new_content)

async def multi_replace_file_content(
    file_path: str,
    replacement_chunks: List[Dict[str, Any]]
) -> str:
    """
    Apply multiple non-contiguous replacements to a remote file.
    
    Args:
        file_path: Path to the remote file.
        replacement_chunks: List of dicts with 'TargetContent' and 'ReplacementContent'.
    """
    logger.info("Received multi_replace_file_content for %s", file_path)
    
    current_content = await view_file(file_path)
    if current_content.startswith("Error"):
        return current_content
        
    new_content = current_content
    for chunk in replacement_chunks:
        target = chunk.get("TargetContent")
        replacement = chunk.get("ReplacementContent")
        if not target or replacement is None:
            continue
            
        if target not in new_content:
            return f"Error: targetContent '{target}' not found in the file."
            
        # We replace only once per chunk to follow the 'non-contiguous' philosophy
        new_content = new_content.replace(target, replacement, 1)
        
    return await file_write(file_path, new_content)

async def search_replace(
    file_path: str,
    blocks: str
) -> str:
    """
    Edit a file using one or more SEARCH/REPLACE blocks.
    
    Format for 'blocks' parameter:
    <<<<<<< SEARCH
    exact code to find
    =======
    new code to insert
    >>>>>>> REPLACE

    Args:
        file_path: Path to the remote file.
        blocks: One or more SEARCH/REPLACE formatted blocks.
    """
    logger.info("Received search_replace for %s", file_path)
    
    content = await view_file(file_path)
    if content.startswith("Error"):
        return content

    # Regex to find all blocks
    # We use re.DOTALL to match across multiple lines
    pattern = r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE"
    matches = re.findall(pattern, blocks, re.DOTALL)
    
    if not matches:
        return "Error: No valid SEARCH/REPLACE blocks found in the input. Ensure exact format including newlines."

    new_content = content
    for search_text, replace_text in matches:
        if search_text not in new_content:
            # Provide helpful context for why SEARCH failed
            logger.warning("SEARCH block not found in %s", file_path)
            return f"Error: SEARCH block not found in file. Ensure whitespace matches exactly:\n{search_text}"
        
        # Check for uniqueness to avoid accidental multiple replacements
        if new_content.count(search_text) > 1:
            logger.warning("SEARCH block not unique in %s", file_path)
            return f"Error: SEARCH block is not unique in file. Please provide more context lines."

        new_content = new_content.replace(search_text, replace_text)
    
    return await file_write(file_path, new_content)

async def git_grep(
    query: str,
    search_path: str = ".",
    case_insensitive: bool = True
) -> str:
    """
    Search for text patterns using 'git grep', which respects .gitignore.
    Falls back to normal grep if not in a git repository.
    
    Args:
        query: The pattern to search for.
        search_path: Path to search within.
        case_insensitive: Whether to ignore case.
    """
    logger.info("Received git_grep: '%s' in %s", query, search_path)
    
    # Check if we are in a git repo remotely
    check_git = await exec_remote_command("git rev-parse --is-inside-work-tree")
    
    if check_git.code != 0:
        # Fallback to standard grep with common exclusions
        logger.warning("Not in a git repo, falling back to grep with common exclusions")
        flags = "-rnI"
        if case_insensitive: flags += "i"
        # Combine exclusions for better relevance
        cmd = f"grep {flags} --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=build --exclude-dir=.venv {shlex.quote(query)} {shlex.quote(search_path)}"
    else:
        flags = "-nI"
        if case_insensitive: flags += "i"
        cmd = f"git grep {flags} {shlex.quote(query)} {shlex.quote(search_path)}"
        
    result = await exec_remote_command(cmd)
    
    if result.code == 0:
        return result.stdout
    elif result.code == 1:
        return "" # No matches found
    else:
        return f"Error in git_grep: {result.stderr.strip()}"

async def project_todo(
    action: str, # read, add, update, delete
    task_id: Optional[int] = None,
    content: Optional[str] = None,
    priority: Optional[str] = "medium", # high, medium, low
    status: Optional[str] = "todo" # todo, in-progress, done
) -> str:
    """
    Manage a structured project TODO list (TODO.json) on the remote server.
    
    Args:
        action: 'read', 'add', 'update', or 'delete'.
        task_id: Required for 'update' and 'delete'.
        content: The task description (for 'add' or 'update').
        priority: 'high', 'medium', or 'low'.
        status: 'todo', 'in-progress', or 'done'.
    """
    import json
    todo_file = "TODO.json"
    logger.info("Received project_todo: %s", action)
    
    # helper to read remote json
    remote_read = await view_file(todo_file)
    if remote_read.startswith("Error") or not remote_read.strip():
        todos = []
    else:
        try:
            todos = json.loads(remote_read)
        except Exception as e:
            logger.error("Failed to parse TODO.json: %s", e)
            todos = []

    if action == "read":
        if not todos:
            return "Task list is currently empty."
        return json.dumps(todos, indent=2)
    
    elif action == "add":
        if not content:
            return "Error: 'content' parameter is required to add a task."
        new_id = max([t.get("id", 0) for t in todos] + [0]) + 1
        todos.append({
            "id": new_id,
            "content": content,
            "priority": priority,
            "status": status
        })
    
    elif action == "update":
        if task_id is None:
            return "Error: 'task_id' is required for the update action."
        for t in todos:
            if t.get("id") == task_id:
                if content: t["content"] = content
                if priority: t["priority"] = priority
                if status: t["status"] = status
                break
        else:
            return f"Error: Task with ID {task_id} not found."
            
    elif action == "delete":
        if task_id is None:
            return "Error: 'task_id' is required for the delete action."
        original_count = len(todos)
        todos = [t for t in todos if t.get("id") != task_id]
        if len(todos) == original_count:
            return f"Error: Task with ID {task_id} not found."
        
    else:
        return f"Error: Invalid action '{action}'. Use read, add, update, or delete."

    # Write the updated list back to the remote server
    res = await file_write(todo_file, json.dumps(todos, indent=2))
    if res.startswith("Successfully"):
        return json.dumps(todos, indent=2)
    return res

# --- MCP Resource Definitions ---

@mcp.resource("remote://{path}")
async def remote_file_resource(path: str) -> str:
    """Read a remote file as an MCP resource."""
    logger.info("Resource request: remote://%s", path)
    # Reuse view_file logic
    return await view_file(path)

async def list_remote_files(recursive: bool = False) -> str:
    """
    List files in the current remote working directory.
    
    Args:
        recursive: If True, list files in all subdirectories as well.
    """
    logger.info("Received list_remote_files (recursive=%s)", recursive)
    
    cmd = "find . -maxdepth 2 -not -path '*/.*'" if not recursive else "find . -not -path '*/.*'"
    result = await exec_remote_command(cmd)
    
    if result.code == 0:
        return result.stdout
    else:
        return f"Error listing files: {result.stderr.strip()}"

# Register the tools with FastMCP
mcp.tool()(remote_system_info)
mcp.tool()(run_command)
mcp.tool()(get_current_dir)
mcp.tool()(change_dir)
mcp.tool()(file_write)
mcp.tool()(view_file)
mcp.tool()(list_remote_files)
mcp.tool()(list_dir)
mcp.tool()(find_by_name)
mcp.tool()(grep_search)
mcp.tool()(replace_file_content)
mcp.tool()(multi_replace_file_content)
mcp.tool()(search_replace)
mcp.tool()(git_grep)
mcp.tool()(project_todo)

if __name__ == "__main__":
    if not REMOTE_HOST:
        print("Error: REMOTE_HOST environment variable is required to start the server.", file=sys.stderr)
        sys.exit(1)
        
    logger.info("Starting MCP Remote Dev Server")
    logger.info("Target: %s:%s (OS: %s)", REMOTE_HOST, REMOTE_PORT, REMOTE_OS_TYPE)
    logger.info("Start directory: %s", state.current_remote_dir)
    
    mcp.run()
