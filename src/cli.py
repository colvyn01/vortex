# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
Command-line interface for Vortex file gateway.

This module handles argument parsing and process management for starting
and stopping the Vortex server. It provides cross-platform support for
Windows and Unix systems.
"""

import argparse
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from .server import run_server


# Configuration Defaults

DEFAULT_PORT = 8000
DEFAULT_DIR = "."
DEFAULT_MAX_PARALLEL = 4


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
        import subprocess

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

    # STOP command
    subparsers.add_parser("stop", help="Stop the running Vortex server")

    return parser


# Main Entry Point


def main() -> None:
    """
    Parse command-line arguments and execute the appropriate action.

    This is the main entry point for the `vortex` command.
    """
    parser = _create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        # Keep CMD open on Windows
        if sys.platform == "win32" and sys.stdin and sys.stdin.isatty():
            input("\nPress Enter to exit...")
        return

    # Handle stop command
    if args.command == "stop":
        pid = _read_pid_file()

        if pid is None:
            print("No running Vortex server found.")
            # Keep CMD open on Windows
            if sys.platform == "win32" and sys.stdin and sys.stdin.isatty():
                input("\nPress Enter to exit...")
            return

        if not _is_process_running(pid):
            print(f"Vortex server (PID {pid}) is not running.")
            _remove_pid_file()
            # Keep CMD open on Windows
            if sys.platform == "win32" and sys.stdin and sys.stdin.isatty():
                input("\nPress Enter to exit...")
            return

        print(f"Stopping Vortex server (PID {pid})...")
        if _terminate_process(pid):
            _remove_pid_file()
            print("Vortex deactivated.")
        else:
            print("Failed to stop Vortex server.")
        # Keep CMD open on Windows
        if sys.platform == "win32" and sys.stdin and sys.stdin.isatty():
            input("\nPress Enter to exit...")
        return

    # Handle start command
    if args.command == "start":
        # Check if already running
        existing_pid = _read_pid_file()
        if existing_pid and _is_process_running(existing_pid):
            print(f"Vortex is already running (PID {existing_pid}).")
            print("Use 'vortex stop' to stop it first.")
            # Keep CMD open on Windows
            if sys.platform == "win32" and sys.stdin and sys.stdin.isatty():
                input("\nPress Enter to exit...")
            return

        # Write PID file and start server
        _write_pid_file()
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
            # Keep CMD open on Windows
            if sys.platform == "win32" and sys.stdin and sys.stdin.isatty():
                input("\nPress Enter to exit...")
        return

