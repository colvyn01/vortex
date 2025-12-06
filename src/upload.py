# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
File upload handling for Vortex.

This module implements multipart form data parsing with streaming support
for memory-efficient handling of large file uploads. Files are streamed
directly to disk rather than being buffered entirely in memory.
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from io import BufferedIOBase
from typing import Optional, Union

from .constants import CHUNK_SIZE, ENCODING, MAX_HEADER_SIZE
from .utils import sanitize_filename


# Upload Result


@dataclass
class UploadResult:
    """
    Result of a file upload operation.

    Attributes:
        success: True if the upload completed successfully.
        error_message: Description of the error if success is False.
    """

    success: bool
    error_message: Optional[str] = None


# Multipart Parsing


def extract_boundary(content_type: str) -> Optional[str]:
    """
    Extract the multipart boundary string from a Content-Type header.

    The boundary is used to separate different parts in a multipart
    form submission.

    Args:
        content_type: The Content-Type header value.

    Returns:
        The boundary string, or None if not found.
    """
    match = re.search(r"boundary=(.+)", content_type)
    if not match:
        return None

    boundary = match.group(1).strip()

    # Remove surrounding quotes if present
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]

    return boundary


def parse_multipart_streaming(
    rfile: Union[BufferedIOBase, "SocketIO"],  # type: ignore[name-defined]
    content_length: int,
    boundary: str,
    base_directory: str,
    upload_id: Optional[str] = None,
    termination_check: Optional[callable] = None,
) -> UploadResult:
    """
    Parse multipart form data using streaming to handle large files.

    This function reads the upload in chunks and writes directly to disk,
    avoiding the need to buffer the entire file in memory. This allows
    uploads of arbitrarily large files without memory issues.

    The parsing works by:
    1. Finding the multipart boundary that separates form fields
    2. Extracting the filename from the Content-Disposition header
    3. Streaming file data to a temporary file
    4. Moving the temp file to the final destination on success

    Args:
        rfile: The request input stream (socket file object).
        content_length: Total bytes to read from the stream.
        boundary: The multipart boundary string.
        base_directory: Directory where uploaded files will be saved.
        upload_id: Optional unique identifier for tracking this upload.
        termination_check: Optional callable that returns True if upload should abort.

    Returns:
        UploadResult indicating success or failure with error message.
    """
    boundary_bytes = ("--" + boundary).encode(ENCODING)
    remaining = content_length

    # Phase 1: Find the first boundary
    # Read until we encounter the boundary that starts the file part.

    header_buffer = b""
    while remaining > 0 and boundary_bytes not in header_buffer:
        to_read = min(1024, remaining)
        chunk = rfile.read(to_read)
        if not chunk:
            break
        remaining -= len(chunk)
        header_buffer += chunk

        # Prevent memory exhaustion from malformed requests
        if len(header_buffer) > MAX_HEADER_SIZE:
            return UploadResult(success=False, error_message="Headers too large")

    # Phase 2: Parse headers after boundary
    # Extract Content-Disposition to get the filename.

    boundary_pos = header_buffer.find(boundary_bytes)
    if boundary_pos == -1:
        return UploadResult(success=False, error_message="No boundary found")

    # Skip past boundary and CRLF to reach headers
    header_start = boundary_pos + len(boundary_bytes)
    header_buffer = header_buffer[header_start:].lstrip(b"\r\n")

    # Read until we hit the double CRLF separating headers from body
    while b"\r\n\r\n" not in header_buffer and remaining > 0:
        to_read = min(1024, remaining)
        chunk = rfile.read(to_read)
        if not chunk:
            break
        remaining -= len(chunk)
        header_buffer += chunk

        if len(header_buffer) > MAX_HEADER_SIZE:
            return UploadResult(success=False, error_message="Headers too large")

    if b"\r\n\r\n" not in header_buffer:
        return UploadResult(success=False, error_message="Malformed multipart data")

    headers_block, file_data_start = header_buffer.split(b"\r\n\r\n", 1)
    headers_text = headers_block.decode(ENCODING, "replace")

    # Verify this is the file field we expect
    if 'name="file"' not in headers_text:
        return UploadResult(success=False, error_message="No file field found")

    # Extract filename from Content-Disposition header
    filename_match = re.search(r'filename="([^"]+)"', headers_text)
    if not filename_match:
        return UploadResult(success=False, error_message="No filename in upload")

    filename = os.path.basename(filename_match.group(1))
    filename = sanitize_filename(filename)
    if not filename:
        return UploadResult(success=False, error_message="Empty filename")

    # Resolve filename conflicts by appending counter if file exists
    dest_path = os.path.join(base_directory, filename)
    
    if os.path.exists(dest_path):
        # Separate filename and extension
        name_without_ext, ext = os.path.splitext(filename)
        counter = 1
        
        # Incrementally append counter until we find a unique filename
        while os.path.exists(dest_path):
            new_filename = f"{name_without_ext} ({counter}){ext}"
            dest_path = os.path.join(base_directory, new_filename)
            counter += 1
            
            # Safety check to prevent infinite loops
            if counter > 9999:
                return UploadResult(success=False, error_message="Too many duplicate files")

    # Phase 3: Stream file data to temporary file
    # Write to temp file first, then move to destination atomically.
    # This prevents partial/corrupt files if the upload is interrupted.

    temp_fd = None
    temp_path = None

    try:
        temp_fd, temp_path = tempfile.mkstemp(dir=base_directory, prefix=".upload_")

        # Track this upload if upload_id is provided
        if upload_id:
            try:
                # Import here to avoid circular dependency
                from . import server
                with server._active_uploads_lock:
                    server._active_uploads[upload_id] = temp_path
            except (ImportError, AttributeError):
                pass  # Server module not available or lock not initialized

        with os.fdopen(temp_fd, "wb") as temp_file:
            temp_fd = None  # fdopen takes ownership of the file descriptor

            # Check if the entire file was in the initial buffer
            boundary_pos = file_data_start.find(boundary_bytes)
            if boundary_pos != -1:
                # Small file: everything fit in the header buffer
                file_data = file_data_start[:boundary_pos]
                if file_data.endswith(b"\r\n"):
                    file_data = file_data[:-2]
                temp_file.write(file_data)
            else:
                # Large file: need to stream the rest
                # Use optimized buffer for boundary detection
                boundary_len = len(boundary_bytes)
                
                # Write initial safe data
                if len(file_data_start) > boundary_len + 2:
                    safe_len = len(file_data_start) - boundary_len - 2
                    temp_file.write(file_data_start[:safe_len])
                    buffer = file_data_start[safe_len:]
                else:
                    buffer = file_data_start

                # Stream remaining data with optimized chunked reads
                while remaining > 0:
                    # Check if server is terminating
                    if termination_check and termination_check():
                        return UploadResult(success=False, error_message="Upload aborted: server shutting down")
                    
                    to_read = min(CHUNK_SIZE, remaining)
                    chunk = rfile.read(to_read)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    
                    # Append to buffer and check for boundary
                    buffer += chunk
                    boundary_pos = buffer.find(boundary_bytes)
                    
                    if boundary_pos != -1:
                        # Found boundary - write final data
                        data_to_write = buffer[:boundary_pos]
                        if data_to_write.endswith(b"\r\n"):
                            data_to_write = data_to_write[:-2]
                        temp_file.write(data_to_write)
                        break
                    
                    # Write all but potential boundary overlap
                    if len(buffer) > boundary_len + 2:
                        safe_len = len(buffer) - boundary_len - 2
                        temp_file.write(buffer[:safe_len])
                        buffer = buffer[safe_len:]
                else:
                    # No boundary found - write remaining buffer
                    if buffer:
                        if buffer.endswith(b"\r\n"):
                            buffer = buffer[:-2]
                        if buffer.endswith(b"--"):
                            buffer = buffer[:-2]
                        temp_file.write(buffer)

        # Phase 4: Move temp file to final destination
        # Atomic rename to final destination.

        os.rename(temp_path, dest_path)
        temp_path = None  # Successfully moved

        return UploadResult(success=True)

    except OSError as e:
        return UploadResult(success=False, error_message=f"Failed to save file: {e}")

    finally:
        # Clean up temp file if it still exists (upload failed)
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
