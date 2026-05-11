# File Operations

Manage files within a hosted agent session. All file operations require an active session with a running sandbox.

## Overview

Hosted agent sessions provide a persistent filesystem rooted at `$HOME` (`/home/session`). Files written to this path survive across requests within the same session. Use the session file tools to upload input data, download outputs, and manage the session filesystem externally.

> ⚠️ **Warning:** All file paths are relative to `$HOME`. For example, `filePath: '/data/input.csv'` maps to `/home/session/data/input.csv` inside the container.

## MCP Tool Details

### Upload File

Use `session_file_upload` to write a file into the session:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `projectEndpoint` | ✅ | AI Foundry project endpoint |
| `agentName` | ✅ | Name of the hosted agent |
| `sessionId` | ✅ | Active session ID |
| `filePath` | ✅ | Destination path (e.g., `/data/input.csv`) |
| `contentBase64` | ✅ | File content as a base64-encoded string |

> 💡 **Tip:** For text files, encode the content to base64 before passing it. For binary files (images, PDFs), read the raw bytes and base64-encode them.

### Download File

Use `session_file_download` to retrieve a file from the session:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `projectEndpoint` | ✅ | AI Foundry project endpoint |
| `agentName` | ✅ | Name of the hosted agent |
| `sessionId` | ✅ | Active session ID |
| `filePath` | ✅ | Path to the file to download (e.g., `/data/output.csv`) |

Returns: File content as a base64-encoded string.

### List Files

Use `session_file_list` to browse the session filesystem:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `projectEndpoint` | ✅ | AI Foundry project endpoint |
| `agentName` | ✅ | Name of the hosted agent |
| `sessionId` | ✅ | Active session ID |
| `path` | ❌ | Directory path to list (defaults to root `/`) |

Returns: List of files and directories with metadata.

### Delete File

Use `session_file_delete` to remove a file or directory:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `projectEndpoint` | ✅ | AI Foundry project endpoint |
| `agentName` | ✅ | Name of the hosted agent |
| `sessionId` | ✅ | Active session ID |
| `filePath` | ✅ | Path to delete |
| `recursive` | ❌ | Set `true` to recursively delete a directory and its contents (default `false`) |

> ⚠️ **Warning:** Non-recursive delete on a non-empty directory will fail. Use `recursive: true` for directories with contents.

### Get File Metadata

Use `session_file_stat` to inspect a file or directory:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `projectEndpoint` | ✅ | AI Foundry project endpoint |
| `agentName` | ✅ | Name of the hosted agent |
| `sessionId` | ✅ | Active session ID |
| `filePath` | ✅ | Path to inspect |

Returns: File name, size, whether it is a directory, and last modified time.

### Create Directory

Use `session_file_mkdir` to create directories:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `projectEndpoint` | ✅ | AI Foundry project endpoint |
| `agentName` | ✅ | Name of the hosted agent |
| `sessionId` | ✅ | Active session ID |
| `path` | ✅ | Directory path to create (e.g., `/data/results`) |
| `createParents` | ❌ | Create parent directories if needed (default `true`) |
| `mode` | ❌ | Unix permission mode (e.g., `755`). Uses system default if omitted |

## Common Patterns

### Upload Input → Invoke → Download Output

```text
1. session_create       → get sessionId
2. session_file_mkdir   → create /data/input/
3. session_file_upload  → upload input files to /data/input/
4. agent_invoke         → tell agent to process /data/input/
5. session_file_list    → check /data/output/ for results
6. session_file_download → retrieve output files
7. session_delete       → clean up when done
```

### Check Agent-Generated Files

```text
1. session_file_list    → browse $HOME to see what the agent created
2. session_file_stat    → check size/type of specific files
3. session_file_download → retrieve files of interest
```

## Storage Limits

- Maximum `$HOME` size: **10 GiB** per session
- Files outside `$HOME` (e.g., `/tmp`) are ephemeral and may be cleared between requests

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Session not active | Session expired or not yet running | Use `session_get` to check status; create a new session if expired |
| File not found | Invalid path or file does not exist | Use `session_file_list` to verify the path |
| Directory not empty | Non-recursive delete on a directory with contents | Use `recursive: true` |
| Storage limit exceeded | `$HOME` exceeds 10 GiB | Delete unnecessary files with `session_file_delete` |
