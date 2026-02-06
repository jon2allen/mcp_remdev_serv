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
    grep_pattern: Optional[str] = None
) -> str:
    """
    View the content of a file on the remote server.
    
    Args:
        file_path: Path to the file on the remote server.
        grep_pattern: Optional extended regular expression to filter lines.
    """
    logger.info("Received view_file: %s (grep=%s)", file_path, grep_pattern)
    
    if is_restricted_file_access(file_path):
        return "Error: Access to this file is restricted."

    if grep_pattern:
        # Use grep -E for extended regex support
        cmd = f"grep -E {shlex.quote(grep_pattern)} {shlex.quote(file_path)}"
    else:
        cmd = f"cat {shlex.quote(file_path)}"
        
    result = await exec_remote_command(cmd)
    
    if result.code == 0:
        return result.stdout
    else:
        return f"Error viewing file: {result.stderr.strip()}"

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

if __name__ == "__main__":
    if not REMOTE_HOST:
        print("Error: REMOTE_HOST environment variable is required to start the server.", file=sys.stderr)
        sys.exit(1)
        
    logger.info("Starting MCP Remote Dev Server")
    logger.info("Target: %s:%s (OS: %s)", REMOTE_HOST, REMOTE_PORT, REMOTE_OS_TYPE)
    logger.info("Start directory: %s", state.current_remote_dir)
    
    mcp.run()
