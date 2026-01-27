# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
Vortex - Simple local file gateway.

A zero-configuration file sharing server for local networks. Vortex provides
an easy way to share files between devices on the same Wi-Fi network through
a clean web interface.

Features:
    - No configuration required - just run and share
    - Upload and download files from any device with a browser
    - Streaming transfers for memory-efficient handling of large files
    - HTTP Range support for media seeking and resumable downloads
    - Cross-platform: Windows, macOS, Linux

Quick Start:
    $ vortex --start                    # Start server in current directory
    $ vortex --start --dir ~/Downloads  # Share a specific directory
    $ vortex --stop                     # Stop the running server

Example:
    >>> from src import run_server
    >>> run_server("/path/to/share", port=8000)
"""

# Public API
# These are the main entry points for using Vortex programmatically.

from .cli import main
from .server import PooledHTTPServer, VortexHandler, get_local_ip, run_server
from .ui import format_size, render_directory_listing, render_layout
from .utils import get_mime_type, is_path_safe

__all__ = [
    # CLI entry point
    "main",
    # Server components
    "run_server",
    "VortexHandler",
    "PooledHTTPServer",
    "get_local_ip",
    # UI rendering
    "render_directory_listing",
    "render_layout",
    # Utilities
    "format_size",
    "get_mime_type",
    "is_path_safe",
]

__version__ = "1.0.0"
