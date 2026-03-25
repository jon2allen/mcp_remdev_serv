# Available Tools for Editing, Viewing, and File Navigation

## Viewing/Reading Files
- **read**: Reads file contents with line numbers. Supports `offset` and `limit` parameters for pagination. Returns up to 2000 lines by default. Essential before editing files.
- **glob**: Finds files by name patterns (e.g., `"**/*.js"`, `"src/**/*.ts"`). Returns matching file paths sorted by modification time. Primary tool for file discovery.
- **grep**: Searches file contents using regular expressions. Returns file paths and line numbers with matches. Can filter by file patterns via `include` parameter.

## Editing Files
- **edit**: Performs exact string replacements in files. Requires reading the file first. Can replace a single occurrence or all occurrences (`replaceAll: true`).
- **write**: Overwrites or creates a file with specified content. If modifying an existing file, must read it first; if creating new, can write directly.

## File Navigation/Discovery
- While **glob** is the dedicated tool for finding files by pattern, the **bash** tool can execute navigation commands like `ls`, `find`, etc. However, for most file operations, the dedicated file tools (`read`, `glob`, `grep`, `edit`, `write`) are preferred and safer.

## Important Notes
- All file modification tools (`edit`, `write`) require reading the file first (unless creating a new file) to prevent accidental changes.
- The `read` tool is essential before any editing operations.
- These tools are designed to work together: use `glob` or `grep` to locate files, `read` to examine them, and `edit`/`write` to modify them.