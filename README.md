# LLDB MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes [LLDB](https://lldb.llvm.org/) debugging functionality as tools via HTTP streaming. This allows LLM agents and clients to initialize debugger sessions, run commands, and manage debugging workflows programmatically.

## Features

- **HTTP Streamable Transport**: Uses Server-Sent Events (SSE) for real-time communication.
- **Rich Logging**: Console output for tool calls is beautifully formatted using `rich`.
- **Full LLDB Control**: Execute any LLDB command, set breakpoints, and inspect process state.
- **Output Redirection**: Option to save long command outputs to files.

## Prerequisites

- Python 3.13+
- `lldb` (The `lldb` python module must be available in your environment. On many systems, this comes with the LLDB installation, but you may need to ensure your Python environment can see it).

## Installation

This project is managed with `uv`.

```bash
uv sync
```

Or using pip:

```bash
pip install -r requirements.txt
```

## Usage

Start the server:

```bash
# Using uv
uv run lldb_mcp.py

# Or directly with python (if dependencies are installed)
python3 lldb_mcp.py
```

### Command Line Arguments

- `--host`: Host to bind to (default: `0.0.0.0`)
- `--port`: Port to bind to (default: `8000`)

Example:
```bash
uv run lldb_mcp.py --host 127.0.0.1 --port 9000
```

## Tools

The server exposes the following tools to MCP clients:

### `lldb_initialize_debugger`
Initialize a new debugger session for a target executable.
- **Args**:
    - `filename`: Path to the executable.
    - `arch` (optional): Target architecture (default: `x86_64`).

### `lldb_run_command`
Execute a raw LLDB command.
- **Args**:
    - `command`: The LLDB command (e.g., `run`, `bt`, `frame var`).
    - `output_filename` (optional): Path to write the output to (useful for long outputs).
- **Returns**: Dictionary with `lldb_output` and `program_stdout`.

### `lldb_set_breakpoint`
Set a breakpoint.
- **Args**:
    - `location`: Function name (`main`), file:line (`main.cpp:42`), or address (`0x...`).
    - `condition` (optional): Breakpoint condition (e.g., `x > 10`).

### `lldb_list_breakpoints`
List all current breakpoints.

### `lldb_get_status`
Get the current state of the debugger and process (e.g., running, stopped, exited).

### `lldb_terminate`
Terminate the current session and clean up resources.
