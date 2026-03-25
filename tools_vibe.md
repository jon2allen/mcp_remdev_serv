# Tools Available for File Editing and Navigation

## File Reading and Navigation

### `read_file`
- **Purpose**: Reads content from a specified file.
- **Features**:
  - Supports `offset` (line number) and `limit` (number of lines) for reading specific sections.
  - Returns `was_truncated: true` if the file content is cut short due to size limits.
- **Use Case**: Efficiently read large files or specific sections of a file.

### `grep`
- **Purpose**: Recursively searches for a regex pattern in files.
- **Features**:
  - Respects `.gitignore` and `.codeignore` files by default.
  - Supports `max_matches` and `use_default_ignore` options.
- **Use Case**: Find where functions are defined, how variables are used, or locate specific error messages.

### `bash`
- **Purpose**: Runs one-off shell commands.
- **Features**:
  - Useful for directory listings, system checks, and git operations.
- **Use Case**: Run commands like `ls`, `pwd`, `find`, `git status`, etc.

## File Editing

### `search_replace`
- **Purpose**: Edits files using SEARCH/REPLACE blocks.
- **Features**:
  - Requires exact text matching (including whitespace and indentation).
  - Supports multiple SEARCH/REPLACE blocks in a single call.
- **Use Case**: Make targeted changes to files while preserving the rest of the content.

### `write_file`
- **Purpose**: Creates or overwrites a file.
- **Features**:
  - Requires `overwrite: true` to overwrite existing files.
  - Automatically creates parent directories if they don't exist.
- **Use Case**: Create new files or overwrite existing ones with new content.

## Task Management

### `todo`
- **Purpose**: Manages a task list for tracking progress.
- **Features**:
  - Supports actions: `read` (view current list) and `write` (update entire list).
  - Each task has `id`, `content`, `status`, and `priority`.
- **Use Case**: Track progress on complex or multi-step tasks.

## Delegation

### `task`
- **Purpose**: Delegates tasks to a subagent for independent execution.
- **Features**:
  - Useful for exploration, research, or parallel work.
- **Use Case**: Delegate tasks that require autonomous execution without user interaction.

## Constraints

- **No direct file modification**: Avoid using `bash` for file operations (e.g., `cat`, `sed`, `echo`). Use dedicated tools like `read_file`, `search_replace`, or `write_file`.
- **Read before editing**: Always read a file before modifying it.
- **Minimal changes**: Only modify what is explicitly requested.
