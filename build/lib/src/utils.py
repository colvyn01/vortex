# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
Utility functions for Vortex.

This module provides helper functions for file handling, security validation,
MIME type detection, HTTP header parsing, and other common operations.
"""

import os
import re
from hashlib import md5
from pathlib import Path
from typing import Optional, Tuple

from .constants import CONTENT_TYPE_OCTET, MIME_TYPES

# Filename Sanitization

# Characters that are invalid in Windows filenames: \ / : * ? " < > |
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing characters invalid on Windows.

    This ensures uploaded files can be saved on any filesystem without
    issues. Leading/trailing spaces and dots are also stripped.

    Args:
        filename: The original filename from the upload.

    Returns:
        A sanitized filename safe for all major filesystems.
        Returns "uploaded_file" if the result would be empty.
    """
    # Replace invalid characters with underscore
    sanitized = INVALID_FILENAME_CHARS.sub("_", filename)

    # Remove leading/trailing spaces and dots (problematic on Windows)
    sanitized = sanitized.strip(" .")

    # Fallback if filename is empty after sanitization
    if not sanitized:
        sanitized = "uploaded_file"

    return sanitized


# Path Security


def is_path_safe(path: Path, base_directory: Path) -> bool:
    """
    Check if a path is safely contained within the base directory.

    This prevents directory traversal attacks where malicious requests
    attempt to access files outside the served directory using sequences
    like "../" or absolute paths.

    Args:
        path: The path to validate (will be resolved to absolute).
        base_directory: The root directory that should contain the path.

    Returns:
        True if the path is safely within base_directory, False otherwise.
    """
    try:
        # Resolve both paths to absolute, resolving any symlinks
        resolved_path = path.resolve()
        resolved_base = base_directory.resolve()

        # Check if the resolved path starts with the base directory
        return resolved_path.is_relative_to(resolved_base)
    except (OSError, ValueError):
        # Any error in path resolution means it's not safe
        return False


# MIME Type Detection


def get_mime_type(file_path: str) -> str:
    """
    Get the MIME type for a file based on its extension.

    Uses a comprehensive mapping of common file extensions. Falls back
    to application/octet-stream for unknown extensions.

    Args:
        file_path: Path to the file (only extension is used).

    Returns:
        MIME type string (e.g., "video/mp4", "image/png").
    """
    ext = os.path.splitext(file_path)[1].lower()
    return MIME_TYPES.get(ext, CONTENT_TYPE_OCTET)


# HTTP Header Utilities


def generate_etag(file_path: str, file_stat: os.stat_result) -> str:
    """
    Generate an ETag for HTTP caching validation.

    The ETag is computed from the file path, size, and modification time.
    This allows browsers to efficiently check if their cached version
    is still valid without downloading the entire file.

    Args:
        file_path: Path to the file.
        file_stat: Result of os.stat() on the file.

    Returns:
        ETag string in quotes (e.g., '"abc123def456"').
    """
    etag_data = f"{file_path}:{file_stat.st_size}:{file_stat.st_mtime}"
    return f'"{md5(etag_data.encode()).hexdigest()}"'


def parse_range_header(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """
    Parse an HTTP Range header for partial content requests.

    Supports single-range requests only. Used for video/audio seeking
    and resumable downloads.

    Supported formats:
        - "bytes=0-1023"  : Bytes 0 through 1023 (inclusive)
        - "bytes=500-"    : From byte 500 to end of file
        - "bytes=-500"    : Last 500 bytes of file

    Args:
        range_header: The Range header value (e.g., "bytes=0-1023").
        file_size: Total size of the file in bytes.

    Returns:
        Tuple of (start, end) byte positions (inclusive), or None if
        the range is invalid or unsupported (e.g., multi-range).
    """
    # Range header must start with "bytes="
    if not range_header.startswith("bytes="):
        return None

    range_spec = range_header[6:].strip()

    # Multi-range requests are not supported
    if "," in range_spec:
        return None

    try:
        if range_spec.startswith("-"):
            # Suffix range: "-500" means last 500 bytes
            suffix_length = int(range_spec[1:])
            if suffix_length <= 0:
                return None
            start = max(0, file_size - suffix_length)
            end = file_size - 1

        elif range_spec.endswith("-"):
            # Open-ended range: "500-" means from byte 500 to end
            start = int(range_spec[:-1])
            end = file_size - 1

        else:
            # Explicit range: "0-1023"
            parts = range_spec.split("-")
            if len(parts) != 2:
                return None
            start = int(parts[0])
            end = int(parts[1])

        # Validate range bounds
        if start < 0 or end < start or start >= file_size:
            return None

        # Clamp end to file size (handle oversized range requests gracefully)
        end = min(end, file_size - 1)

        return (start, end)

    except ValueError:
        # Invalid integer in range specification
        return None
