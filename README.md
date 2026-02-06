# MCP Remote Development Server

A Model Context Protocol (MCP) server for remote development over SSH. This server enables AI assistants to interact with code projects hosted on remote servers, supporting multiple Unix-like operating systems including Linux, FreeBSD, and AIX.

## Overview

The MCP Remote Development Server provides a secure bridge between AI coding assistants (such as Antigravity) and remote development environments. It exposes tools for command execution, file management, and directory navigation on remote servers via SSH, while maintaining security through configurable command blocking and file access restrictions.

## Features

- **Remote Command Execution**: Run shell commands on remote servers with full output capture
- **File Operations**: Read and write files on remote systems using secure SCP transfers
- **Directory Management**: Navigate and manage remote working directories with state persistence
- **MCP Resources**: Expose remote files as MCP resources for seamless AI integration
- **Security Controls**: Configurable command blocking and file access restrictions
- **Multi-OS Support**: Compatible with Linux, FreeBSD, and AIX remote servers
- **SSH Key Authentication**: Leverages existing SSH key infrastructure for passwordless access

## Requirements

- Python 3.8 or higher
- `fastmcp` library
- SSH client with key-based authentication configured
- Network access to target remote server

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/mcp_remdev_serv.git
cd mcp_remdev_serv
```

2. Create a virtual environment and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastmcp
```

3. Ensure SSH keys are configured for passwordless access to your remote server:
```bash
ssh-copy-id -p <port> user@remote-host
```

## Configuration

The server is configured entirely through environment variables:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `REMOTE_HOST` | IP address or hostname of remote server | Yes | - |
| `REMOTE_PORT` | SSH port number | No | `22` |
| `REMOTE_USER` | SSH username (if not in ssh config) | No | - |
| `REMOTE_DIR` | Initial working directory on remote server | No | `.` |
| `REMOTE_OS_TYPE` | Remote OS type (linux, freebsd, aix) | No | `linux` |
| `REMOTE_OVERRIDE_SECURITY` | Bypass security restrictions | No | `true` |
| `REMOTE_PROHIBITED_CMDS` | Comma-separated list of blocked commands | No | `rm ,mv ,sudo ,su ` |
| `REMOTE_RESTRICTED_FILES` | Comma-separated list of restricted files | No | - |

### Example Configuration for MCP Clients

For Claude Desktop or similar MCP clients, add the following to your configuration file:

```json
{
  "mcpServers": {
    "mcp_remdev_serv": {
      "command": "/path/to/mcp_remdev_serv/.venv/bin/python",
      "args": [
        "/path/to/mcp_remdev_serv/mcp_remdev_serv.py"
      ],
      "env": {
        "REMOTE_HOST": "192.168.1.100",
        "REMOTE_PORT": "22",
        "REMOTE_DIR": "/home/user/project",
        "REMOTE_OS_TYPE": "linux",
        "REMOTE_OVERRIDE_SECURITY": "true"
      },
      "disabled": false
    }
  }
}
```

## Tools

The server exposes the following MCP tools:

### `remote_system_info()`
Returns information about the remote system configuration.

**Returns:** Dictionary with host, port, OS type, and current directory.

### `run_command(command: str, stdin: str = None)`
Executes a shell command on the remote server.

**Parameters:**
- `command`: Shell command to execute
- `stdin`: Optional input to pipe to the command

**Returns:** Dictionary with stdout, stderr, exit code, and error status.

### `get_current_dir()`
Returns the current working directory on the remote server.

**Returns:** String path of current directory.

### `change_dir(new_dir: str)`
Changes the current working directory on the remote server.

**Parameters:**
- `new_dir`: Target directory (absolute or relative path)

**Returns:** New absolute path on success, or error message.

### `file_write(file_path: str, content: str)`
Writes text content to a file on the remote server using SCP.

**Parameters:**
- `file_path`: Remote file path (absolute or relative)
- `content`: Text content to write

**Returns:** Success message or error description.

### `view_file(file_path: str, grep_pattern: str = None)`
Reads a file from the remote server, optionally filtering with grep.

**Parameters:**
- `file_path`: Remote file path
- `grep_pattern`: Optional extended regex pattern for filtering

**Returns:** File content or error message.

### `list_remote_files(recursive: bool = False)`
Lists files in the current remote working directory.

**Parameters:**
- `recursive`: If true, recursively list all subdirectories

**Returns:** Newline-separated list of file paths.

## Resources

The server provides an MCP resource template for direct file access:

### `remote://{path}`
Reads a remote file as an MCP resource, allowing AI assistants to access remote files directly.

**Example:** `remote://src/main.py`

## Testing

A test script is provided to verify server functionality:

```bash
# Set environment variables
export REMOTE_HOST="192.168.1.100"
export REMOTE_PORT="22"
export REMOTE_DIR="/home/user/project"
export REMOTE_OS_TYPE="linux"

# Run tests
python3 test_tools.py
```

Alternatively, use the provided bash wrapper:

```bash
./run_test.sh
```

## Security Considerations

- The server uses SSH key-based authentication; ensure private keys are properly secured
- Command blocking is enabled by default for destructive commands (rm, mv, sudo, su)
- File access restrictions can be configured via environment variables
- Set `REMOTE_OVERRIDE_SECURITY` to `false` in production environments for enhanced security
- All operations are logged to `mcp_remdev_serv.log` for audit purposes

## Logging

The server maintains detailed logs in `mcp_remdev_serv.log`, including:
- All command executions and their results
- File operations and transfers
- Security blocks and access denials
- Connection information and errors

## License

MIT License

Copyright (c) 2025 Jon Allen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Acknowledgments

Built using the [FastMCP](https://github.com/jlowin/fastmcp) framework for Model Context Protocol server development.
