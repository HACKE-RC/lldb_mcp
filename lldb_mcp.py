"""
LLDB MCP Server - HTTP Streamable Version

An MCP server that exposes LLDB debugging functionality as tools via HTTP streaming.
Allows clients to initialize debugger sessions, run commands, and manage debugging workflows.
"""

import lldb
import os
import functools
from fastmcp import FastMCP
from rich.console import Console

# Initialize FastMCP server with transport mode
mcp = FastMCP("LLDB Debugger Server")
console = Console()

# Global state management
debugger_state = {
    "debugger": None,
    "interpreter": None,
    "target": None,
    "filename": None,
    "arch": None
}

def log_tool_call(func):
    """Decorator to log tool input and output using rich console."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Log input
        func_name = func.__name__
        input_str = f"Tool '{func_name}' called with args={args}, kwargs={kwargs}"
        console.print(f"[bold blue]INPUT:[/bold blue] {input_str}")
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Log output (truncated)
        output_str = str(result)
        if len(output_str) > 200:
            output_str = output_str[:197] + "..."
            
        console.print(f"[bold green]OUTPUT:[/bold green] {output_str}")
        
        return result
    return wrapper

@mcp.tool()
@log_tool_call
def initialize_debugger(filename: str, arch: str = "x86_64") -> str:
    """
    Initialize an LLDB debugger session for a target executable.
    
    This tool creates a new LLDB debugger instance, sets it to synchronous mode,
    and creates a target for the specified executable file.
    
    Args:
        filename: The path to the executable file to debug. Must exist on the filesystem.
        arch: The target architecture (default: "x86_64"). Common values include:
              - "x86_64" for 64-bit Intel/AMD
              - "arm64" for 64-bit ARM
              - "i386" for 32-bit Intel/AMD
    
    Returns:
        A success message with the target filename, or an error message if initialization fails.
    
    Raises:
        FileNotFoundError: If the specified executable file does not exist.
        RuntimeError: If LLDB debugger or target creation fails.
    
    Example:
        initialize_debugger("/path/to/my/program", "x86_64")
    """
    global debugger_state
    
    # Validate file exists
    if not os.path.exists(filename):
        return f"Error: The file '{filename}' does not exist."
    
    # Create debugger instance
    debugger = lldb.SBDebugger.Create()
    if not debugger:
        return "Error: Failed to create SBDebugger instance."
    
    # Set to synchronous mode
    debugger.SetAsync(False)
    
    # Get command interpreter
    interpreter = debugger.GetCommandInterpreter()
    if not interpreter:
        lldb.SBDebugger.Terminate()
        return "Error: Failed to get command interpreter."
    
    # Create target
    error = lldb.SBError()
    target = debugger.CreateTarget(filename, arch, None, True, error)
    if not target.IsValid() or not error.Success():
        lldb.SBDebugger.Terminate()
        return f"Error: Failed to create target: {error.GetCString()}"
    
    # Store state
    debugger_state["debugger"] = debugger
    debugger_state["interpreter"] = interpreter
    debugger_state["target"] = target
    debugger_state["filename"] = filename
    debugger_state["arch"] = arch
    
    return f"Successfully initialized LLDB debugger for target: {filename} (arch: {arch})"


def run_lldb_command_func(command: str) -> dict:
    global debugger_state
    
    # Check if debugger is initialized
    if not debugger_state["interpreter"] or not debugger_state["target"]:
        return {
            "error": "LLDB not initialized. Call initialize_debugger() first.",
            "lldb_output": "",
            "program_stdout": ""
        }
    
    interpreter = debugger_state["interpreter"]
    target = debugger_state["target"]
    
    # Execute command
    result = lldb.SBCommandReturnObject()
    interpreter.HandleCommand(command, result)
    
    # Get LLDB output
    lldb_output = result.GetOutput()
    if not result.Succeeded():
        lldb_output += result.GetError()
    
    # Get program stdout
    program_stdout = ""
    process = target.GetProcess()
    
    if process and process.IsValid():
        output_read = ""
        while True:
            stdout_chunk = process.GetSTDOUT(1024)
            if not stdout_chunk:
                break
            output_read += stdout_chunk
        program_stdout = output_read
    
    return {
        "command": command,
        "lldb_output": lldb_output,
        "program_stdout": program_stdout
    }


@mcp.tool()
@log_tool_call
def run_lldb_command(command: str, output_filename: str = "") -> dict:
    """
    Execute an LLDB command in the current debugger session. The output is written to the specified file if specified. Always specify this for commands which are expected to have long output. Make sure the output file is in a writable and existing directory. 
    
    This tool runs any valid LLDB command and captures both the LLDB interpreter
    output and any stdout from the debugged program. Common commands include:
    - "breakpoint set --name main" - Set a breakpoint at main function
    - "run" or "r" - Start the program
    - "continue" or "c" - Continue execution
    - "step" or "s" - Step into next line
    - "next" or "n" - Step over next line
    - "print variable" - Print variable value
    - "backtrace" or "bt" - Show call stack
    
    Args:
        command: The LLDB command to execute (e.g., "breakpoint set --name main", "run", "continue")
        output_filename (optional): The filename to write the output to.
    
    Returns:
        A dictionary containing:
        - "lldb_output": Output from the LLDB command interpreter
        - "program_stdout": Standard output from the debugged program (if any)
        - "error": Error message if the debugger is not initialized
    
    Example:
        run_lldb_command("breakpoint set --name main", "/workspace/project1/lib/lldb_output/output.txt")
        run_lldb_command("run", "/workspace/project1/lib/lldb_output/output.txt")
        run_lldb_command("print myVariable")
    """
    if not output_filename:
        return run_lldb_command_func(command)
    else:
        try :
            with open(output_filename, "w") as f:
                return run_lldb_command_func(command)
        except Exception as e:
            return {"error": str(e)}

@mcp.tool()
@log_tool_call
def get_debugger_status() -> dict:
    """
    Get the current status of the LLDB debugger session.
    
    This tool provides information about whether the debugger is initialized,
    what target is being debugged, and the current process state.
    
    Returns:
        A dictionary containing:
        - "initialized": Boolean indicating if debugger is initialized
        - "filename": Path to the target executable (if initialized)
        - "arch": Target architecture (if initialized)
        - "process_state": Current state of the process (e.g., "running", "stopped", "exited")
        - "process_id": Process ID if a process exists
    
    Example:
        get_debugger_status()
    """
    global debugger_state
    
    if not debugger_state["debugger"]:
        return {
            "initialized": False,
            "filename": None,
            "arch": None,
            "process_state": "No debugger initialized"
        }
    
    status = {
        "initialized": True,
        "filename": debugger_state["filename"],
        "arch": debugger_state["arch"],
        "process_state": "No process",
        "process_id": None
    }
    
    target = debugger_state["target"]
    if target and target.IsValid():
        process = target.GetProcess()
        if process and process.IsValid():
            state = process.GetState()
            state_names = {
                lldb.eStateInvalid: "invalid",
                lldb.eStateUnloaded: "unloaded",
                lldb.eStateConnected: "connected",
                lldb.eStateAttaching: "attaching",
                lldb.eStateLaunching: "launching",
                lldb.eStateStopped: "stopped",
                lldb.eStateRunning: "running",
                lldb.eStateStepping: "stepping",
                lldb.eStateCrashed: "crashed",
                lldb.eStateDetached: "detached",
                lldb.eStateExited: "exited",
                lldb.eStateSuspended: "suspended"
            }
            status["process_state"] = state_names.get(state, "unknown")
            status["process_id"] = process.GetProcessID()
    
    return status


@mcp.tool()
@log_tool_call
def terminate_debugger() -> str:
    """
    Terminate the current LLDB debugger session and clean up resources.
    
    This tool properly shuts down the debugger, terminates any running processes,
    and releases all associated resources. Should be called when debugging is complete.
    
    Returns:
        A confirmation message indicating the debugger has been terminated.
    
    Example:
        terminate_debugger()
    """
    global debugger_state
    
    if debugger_state["debugger"]:
        lldb.SBDebugger.Terminate()
        debugger_state["debugger"] = None
        debugger_state["interpreter"] = None
        debugger_state["target"] = None
        debugger_state["filename"] = None
        debugger_state["arch"] = None
        return "LLDB debugger session terminated successfully."
    else:
        return "No active debugger session to terminate."


@mcp.tool()
@log_tool_call
def set_breakpoint(location: str, condition: str = "") -> dict:
    """
    Set a breakpoint in the target program.
    
    This is a convenience tool that wraps the LLDB breakpoint command.
    Breakpoints can be set by function name, file:line, or address.
    
    Args:
        location: The breakpoint location. Can be:
                  - Function name: "main" or "MyClass::myMethod"
                  - File and line: "main.cpp:42"
                  - Address: "0x100000f00"
        condition: Optional condition for the breakpoint (e.g., "x > 10")
    
    Returns:
        A dictionary containing:
        - "success": Boolean indicating if breakpoint was set
        - "message": Description of the result
        - "lldb_output": Raw output from LLDB
    
    Example:
        set_breakpoint("main")
        set_breakpoint("utils.cpp:150")
        set_breakpoint("processData", "count > 100")
    """
    global debugger_state
    
    if not debugger_state["interpreter"]:
        return {
            "success": False,
            "message": "LLDB not initialized. Call initialize_debugger() first.",
            "lldb_output": ""
        }
    
    # Build breakpoint command
    if ":" in location:
        # File:line format
        cmd = f"breakpoint set --file {location.split(':')[0]} --line {location.split(':')[1]}"
    elif location.startswith("0x"):
        # Address format
        cmd = f"breakpoint set --address {location}"
    else:
        # Function name format
        cmd = f"breakpoint set --name {location}"
    
    # Add condition if provided
    if condition:
        cmd += f" --condition '{condition}'"
    
    # Execute command
    result = run_lldb_command_func(cmd)
    
    success = "Breakpoint" in result.get("lldb_output", "") and "error" not in result
    
    return {
        "success": success,
        "message": f"Breakpoint set at {location}" if success else "Failed to set breakpoint",
        "lldb_output": result.get("lldb_output", ""),
        "condition": condition if condition else "None"
    }


@mcp.tool()
@log_tool_call
def list_breakpoints() -> dict:
    """
    List all breakpoints currently set in the debugger session.
    
    Returns:
        A dictionary containing:
        - "breakpoints": List of breakpoint information
        - "lldb_output": Raw output from LLDB breakpoint list command
    
    Example:
        list_breakpoints()
    """
    result = run_lldb_command_func("breakpoint list")
    return {
        "lldb_output": result.get("lldb_output", ""),
        "program_stdout": result.get("program_stdout", "")
    }


if __name__ == "__main__":
    # Run the MCP server with SSE transport (HTTP streaming)
    print("Starting LLDB MCP Server on http://0.0.0.0:8000")
    print("SSE endpoint: http://0.0.0.0:8000/sse")
    
    # Use FastMCP's built-in run method with transport parameter
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)

