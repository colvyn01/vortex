# MIT License
# Copyright (c) 2026 Vortex Contributors
# See LICENSE file for full license text.

"""
Command-line interface for Vortex file gateway.

This module handles argument parsing and process management for starting
and stopping the Vortex server. It provides cross-platform support for
Windows and Unix systems.

By default, ``vortex start`` launches the server in the background with no
visible terminal window.  Use ``vortex start --foreground`` to keep the
terminal attached (useful for debugging).
"""

import argparse
import ipaddress
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Set

from .server import run_server


# Configuration Defaults

DEFAULT_PORT = 8000
DEFAULT_DIR = "."
DEFAULT_MAX_PARALLEL = 4

# Environment variable set in the background child process so it can detect
# that it was spawned by ``_launch_background()`` and should suppress any
# interactive prompts (e.g. "Press Enter to exit…").
_VORTEX_BG_ENV = "_VORTEX_BG"

# Log file for the background server (macOS / Linux). Startup output and any
# errors end up here instead of being discarded.
_LOG_FILE = Path.home() / ".vortex" / "vortex.log"


# PID File Management
# The PID file stores the process ID of a running Vortex server, allowing
# the --stop command to find and terminate it. Location varies by platform.


def _get_pid_file() -> Path:
    """
    Get the path to the PID file.

    On Windows, uses LOCALAPPDATA or TEMP directory.
    On Unix, uses the home directory with a hidden file.

    Returns:
        Path object pointing to the PID file location.
    """
    if sys.platform == "win32":
        # Windows: use LOCALAPPDATA (e.g., C:/Users/Name/AppData/Local)
        # Falls back to TEMP if LOCALAPPDATA is not available
        app_data = os.environ.get("LOCALAPPDATA", os.environ.get("TEMP", "."))
        return Path(app_data) / "vortex.pid"
    else:
        # Unix/Linux/macOS: use home directory with hidden file
        return Path.home() / ".vortex.pid"


def _write_pid_file() -> None:
    """
    Write the current process ID to the PID file.

    This is called when starting the server so that --stop can find it later.
    Errors are silently ignored as PID file is non-critical functionality.
    """
    pid_file = _get_pid_file()
    try:
        pid_file.write_text(str(os.getpid()))
    except OSError:
        pass  # Non-critical if we can't write PID file


def _remove_pid_file() -> None:
    """
    Remove the PID file.

    Called when the server shuts down or when --stop terminates a server.
    """
    pid_file = _get_pid_file()
    try:
        pid_file.unlink(missing_ok=True)
    except OSError:
        pass


def _read_pid_file() -> Optional[int]:
    """
    Read the PID from the PID file.

    Returns:
        The process ID as an integer, or None if the file doesn't exist
        or contains invalid data.
    """
    pid_file = _get_pid_file()
    try:
        if pid_file.exists():
            pid_str = pid_file.read_text().strip()
            return int(pid_str)
    except (OSError, ValueError):
        pass
    return None


# Process Management
# Cross-platform utilities for checking if a process exists and terminating it.


def _is_process_running(pid: int) -> bool:
    """
    Check if a process with the given PID is currently running.

    Uses platform-specific methods:
    - Windows: Opens the process handle using ctypes/kernel32
    - Unix: Sends signal 0 (which doesn't kill but checks existence)

    Args:
        pid: The process ID to check.

    Returns:
        True if the process is running, False otherwise.
    """
    if sys.platform == "win32":
        # Windows: Use ctypes to call kernel32.OpenProcess
        # This is the standard way to check process existence on Windows
        # without requiring additional dependencies like psutil.
        import ctypes

        kernel32 = ctypes.windll.kernel32

        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        # This is the minimum access right needed to query process info
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        # Unix: Signal 0 doesn't actually send a signal, but checks
        # if the process exists and we have permission to signal it
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _terminate_process(pid: int) -> bool:
    """
    Terminate a process by its PID.

    Uses platform-specific methods:
    - Windows: Uses taskkill command with /F (force) flag
    - Unix: Sends SIGTERM signal

    Args:
        pid: The process ID to terminate.

    Returns:
        True if termination was successful, False otherwise.
    """
    if sys.platform == "win32":
        # Windows: Use taskkill command
        # /F = force termination, /PID = specify process ID
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except OSError:
            return False
    else:
        # Unix: Send SIGTERM for graceful shutdown
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False


def _is_background_child() -> bool:
    """Return True if this process was spawned as a background child."""
    return os.environ.get(_VORTEX_BG_ENV) == "1"


def _should_prompt() -> bool:
    """Return True if an interactive "Press Enter" prompt is appropriate."""
    if _is_background_child():
        return False
    return sys.platform == "win32" and sys.stdin and sys.stdin.isatty()


# Network Helpers


def _get_lan_ip() -> Optional[str]:
    """
    Best-effort detection of this machine's LAN IPv4 address.

    Opens a UDP socket towards a non-routable address (no packets are sent)
    and reads the local address the OS selected. This works even when the
    hostname is missing from /etc/hosts, which is common on Arch Linux.

    Returns:
        The LAN IP as a string, or None if it cannot be determined.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return None


# Host Detection
# The web UI shows the stop button and host controls only to the host machine.
# The original check compared the client IP with gethostbyname_ex(hostname),
# which on many Linux systems (e.g. Arch) returns only 127.0.1.1, so a browser
# on the same machine using the LAN IP or hostname.local was treated as a guest.

_LOCAL_ADDR_TTL = 30.0
_local_addr_cache = {"time": 0.0, "addrs": set()}


def _collect_local_addresses() -> Set[str]:
    """Collect IP addresses that belong to this machine."""
    addrs = {"127.0.0.1", "::1"}

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addrs.add(str(info[4][0]).split("%")[0])
    except OSError:
        pass

    lan_ip = _get_lan_ip()
    if lan_ip:
        addrs.add(lan_ip)

    if sys.platform.startswith("linux"):
        try:
            out = subprocess.run(
                ["ip", "-o", "addr", "show"],
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout
            for match in re.finditer(r"inet6?\s+([0-9a-fA-F:.]+)/", out):
                addrs.add(match.group(1))
        except (OSError, subprocess.SubprocessError):
            pass

    return addrs


def _local_addresses() -> Set[str]:
    """Return this machine's addresses, cached briefly for performance."""
    now = time.time()
    if now - _local_addr_cache["time"] > _LOCAL_ADDR_TTL or not _local_addr_cache["addrs"]:
        _local_addr_cache["addrs"] = _collect_local_addresses()
        _local_addr_cache["time"] = now
    return _local_addr_cache["addrs"]


def _install_host_detection() -> None:
    """
    Replace VortexHandler._is_host with a more robust implementation.

    A client counts as the host when its IP is loopback or matches any
    address assigned to this machine.
    """
    try:
        from . import server as server_module

        handler_cls = server_module.VortexHandler
    except (ImportError, AttributeError):
        return

    def _is_host(self) -> bool:
        client_ip = str(self.client_address[0]).split("%")[0]
        if client_ip.lower().startswith("::ffff:"):
            client_ip = client_ip[7:]

        try:
            if ipaddress.ip_address(client_ip).is_loopback:
                return True
        except ValueError:
            return False

        return client_ip in _local_addresses()

    handler_cls._is_host = _is_host


def _print_startup_info(args: argparse.Namespace, proc: subprocess.Popen) -> None:
    """
    Print the background server's startup output (macOS / Linux).

    Shows the server's own startup lines (active notice, served directory,
    share URL, plus any token / HTTPS notices) without the extra noise.
    If the child process dies, the log output is printed instead.
    """
    marker = "Share this on your network"
    content = ""
    for _ in range(30):  # up to ~3 seconds
        try:
            content = _LOG_FILE.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        if marker in content or proc.poll() is not None:
            break
        time.sleep(0.1)

    if proc.poll() is not None:
        print("Error: Vortex server exited unexpectedly. Log output:")
        print(content.strip() or "(log is empty)")
        print(f"Full log: {_LOG_FILE}")
        return

    skip = ("Max concurrent connections", "Press Ctrl+C")
    lines = [
        line.rstrip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith(skip)
    ]
    if lines:
        print("\n".join(lines))


# Background Launch
# Re-spawns the server as a fully detached subprocess with no console window.


def _launch_background(args: argparse.Namespace) -> None:
    """
    Launch the Vortex server as a detached background process.

    Constructs a command equivalent to ``vortex start --foreground <flags>``
    and spawns it as a fully detached subprocess.  The child writes the PID
    file; the parent polls for it (up to 5 s) before printing a confirmation
    and exiting.

    Platform behaviour:
    - **Windows**: ``CREATE_NO_WINDOW | DETACHED_PROCESS``; prefers
      ``pythonw.exe`` so no console is allocated at all.
    - **macOS / Linux**: ``start_new_session=True`` with stdout/stderr
      written to ``~/.vortex/vortex.log``; the startup output is echoed
      by the parent.
    """
    # Remove any stale PID file so we can detect the child's write
    _remove_pid_file()

    # Build the child command: python -m src start --foreground <flags>
    cmd = [sys.executable, "-m", "src", "start", "--foreground"]

    if args.port != DEFAULT_PORT:
        cmd += ["--port", str(args.port)]
    if args.dir != DEFAULT_DIR:
        cmd += ["--dir", args.dir]
    if args.https:
        cmd.append("--https")
    if args.secure:
        cmd.append("--secure")
    if args.new_token:
        cmd.append("--new-token")
    if args.mode != "auto":
        cmd += ["--mode", args.mode]
    if args.max_parallel != DEFAULT_MAX_PARALLEL:
        cmd += ["--max-parallel", str(args.max_parallel)]

    # Mark the child so it knows it is backgrounded
    child_env = os.environ.copy()
    child_env[_VORTEX_BG_ENV] = "1"

    log_enabled = False

    if sys.platform == "win32":
        # On Windows prefer pythonw.exe to suppress console entirely
        python_dir = Path(sys.executable).parent
        pythonw = python_dir / "pythonw.exe"
        if pythonw.exists():
            cmd[0] = str(pythonw)

        # CREATE_NO_WINDOW (0x08000000) prevents a new console window.
        # DETACHED_PROCESS (0x00000008) detaches from the parent console.
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        proc = subprocess.Popen(
            cmd,
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    else:
        # Unix: start a new session so the child survives terminal close.
        # Output goes to a log file (not /dev/null) so errors are visible.
        child_env["PYTHONUNBUFFERED"] = "1"
        try:
            _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            log_handle = open(_LOG_FILE, "w", encoding="utf-8")
            log_enabled = True
        except OSError:
            log_handle = open(os.devnull, "w")
        proc = subprocess.Popen(
            cmd,
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=log_handle,
            start_new_session=True,
        )
        log_handle.close()  # child keeps its own copy of the descriptor

    # Wait for the child to write the PID file (up to 5 seconds)
    pid = None
    for _ in range(50):
        time.sleep(0.1)
        # Check the child hasn't crashed
        if proc.poll() is not None:
            print("Error: Vortex server failed to start.")
            if log_enabled:
                try:
                    print(_LOG_FILE.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
            sys.exit(1)
        pid = _read_pid_file()
        if pid is not None:
            break

    if pid is not None:
        print(f"Vortex server started in background (PID {pid}).")
    else:
        print(f"Vortex server launched (PID {proc.pid}), but PID file was not written.")

    if log_enabled:
        _print_startup_info(args, proc)


# Argument Parser


def _create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the command-line argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="vortex",
        description="Vortex - Fast, cross-platform file transfer over local Wi-Fi",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # START command
    start_parser = subparsers.add_parser("start", help="Start the Vortex server")
    start_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port (default: {DEFAULT_PORT})",
    )
    start_parser.add_argument(
        "--dir",
        default=DEFAULT_DIR,
        help="Directory to share (default: current)",
    )
    start_parser.add_argument(
        "--https",
        action="store_true",
        help="Enable HTTPS",
    )
    start_parser.add_argument(
        "--secure",
        action="store_true",
        help="Enable token authentication",
    )
    start_parser.add_argument(
        "--new-token",
        action="store_true",
        help="Generate new token",
    )
    start_parser.add_argument(
        "--mode",
        choices=["auto", "localhost", "lan"],
        default="auto",
        help="Address mode",
    )
    start_parser.add_argument(
        "--max-parallel",
        type=int,
        default=DEFAULT_MAX_PARALLEL,
        help="Max parallel uploads",
    )
    start_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in the foreground with terminal attached (default: background)",
    )

    # STOP command
    subparsers.add_parser("stop", help="Stop the running Vortex server")

    return parser


# Main Entry Point


def main() -> None:
    """
    Parse command-line arguments and execute the appropriate action.

    This is the main entry point for the ``vortex`` command.
    """
    parser = _create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        if _should_prompt():
            input("\nPress Enter to exit...")
        return

    # Handle stop command
    if args.command == "stop":
        pid = _read_pid_file()

        if pid is None:
            print("No running Vortex server found.")
            if _should_prompt():
                input("\nPress Enter to exit...")
            return

        if not _is_process_running(pid):
            print(f"Vortex server (PID {pid}) is not running.")
            _remove_pid_file()
            if _should_prompt():
                input("\nPress Enter to exit...")
            return

        print(f"Stopping Vortex server (PID {pid})...")
        if _terminate_process(pid):
            _remove_pid_file()
            print("Vortex deactivated.")
        else:
            print("Failed to stop Vortex server.")
        if _should_prompt():
            input("\nPress Enter to exit...")
        return

    # Handle start command
    if args.command == "start":
        # Check if already running
        existing_pid = _read_pid_file()
        if existing_pid and _is_process_running(existing_pid):
            print(f"Vortex is already running (PID {existing_pid}).")
            print("Use 'vortex stop' to stop it first.")
            if _should_prompt():
                input("\nPress Enter to exit...")
            return

        # Background launch (default) — re-spawn as a detached child
        if not args.foreground and not _is_background_child():
            _launch_background(args)
            return

        # Foreground / background-child: run the server in this process
        _write_pid_file()
        _install_host_detection()
        try:
            run_server(
                args.dir,
                args.port,
                args.max_parallel,
                args.mode,
                use_https=args.https,
                use_token_auth=args.secure,
                regenerate_token=args.new_token,
            )
        finally:
            _remove_pid_file()
            if _should_prompt():
                input("\nPress Enter to exit...")
        return
