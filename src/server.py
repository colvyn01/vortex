# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
HTTP server implementation for Vortex file gateway.

This module provides the core HTTP server functionality including:
- Thread pool-based server for concurrent connection handling
- Request handler with streaming file transfers
- HTTP Range request support for media seeking
- Directory ZIP download capability
- Security hardening (path traversal protection, security headers, HTTPS)
"""

import io
import html
import json
import os
import queue
import socket
import ssl
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from hashlib import md5
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlparse

from .constants import (
    CHUNK_SIZE,
    CONTENT_TYPE_HTML,
    CONTENT_TYPE_MULTIPART,
    CONTENT_TYPE_ZIP,
    DNS_SERVERS,
    ENCODING,
    FALLBACK_IP,
    MAX_WORKERS,
)
from .ui import render_directory_listing
from .upload import UploadResult, extract_boundary, parse_multipart_streaming
from .audio_player import get_audio_metadata
from .utils import generate_etag, get_mime_type, is_path_safe, parse_range_header

if TYPE_CHECKING:
    from .security import SecurityManager


# Chat Session Storage
# In-memory storage for cross-device chat messages

_chat_sessions: Dict[str, List[Dict[str, Any]]] = {}
MAX_MESSAGES_PER_SESSION = 100
MESSAGE_RETENTION_SECONDS = 3600  # 1 hour

# SSE (Server-Sent Events) Infrastructure
# Real-time message delivery without polling

_sse_queues: Dict[str, List[queue.Queue]] = {}  # session_id -> list of client queues
_sse_lock = threading.Lock()

# Chat Rate Limiter
# Dedicated rate limiter for chat endpoints to prevent flooding

_chat_rate_limiter = None  # Initialized in run_server

# Banned Devices Storage
# Persistent storage for kicked device IDs

_banned_devices: set = set()
_BANNED_DEVICES_FILE = Path.home() / ".vortex" / "banned_devices.json"

# Active Devices Tracking
# Track all devices currently connected to the server

_active_devices: Dict[str, Dict[str, Any]] = {}
# Key: device_id, Value: {device_name: str, last_seen: float, session_id: str}

# Directory Size Cache
# Caches directory size calculations to avoid expensive recomputation

_size_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
SIZE_CACHE_DURATION = 30  # seconds

# Server Configuration (for host detection)
_server_display_address: Optional[str] = None

# Server Termination State
# Track when server is shutting down to notify clients
_server_terminating: bool = False

# Active Uploads Tracking
# Track all in-progress uploads for graceful shutdown
_active_uploads: Dict[str, str] = {}  # {upload_id: temp_file_path}
_active_uploads_lock = threading.Lock()


# Chat Helper Functions


def _load_banned_devices() -> None:
    """
    Load banned device IDs from persistent storage.

    Loads from ~/.vortex/banned_devices.json if it exists.
    Silently ignores errors if file doesn't exist or is invalid.
    """
    global _banned_devices
    try:
        if _BANNED_DEVICES_FILE.exists():
            with open(_BANNED_DEVICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    _banned_devices = set(data)
    except (OSError, json.JSONDecodeError):
        pass


def _save_banned_devices() -> None:
    """
    Save banned device IDs to persistent storage.

    Saves to ~/.vortex/banned_devices.json.
    Creates directory if it doesn't exist.
    """
    try:
        _BANNED_DEVICES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_BANNED_DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(list(_banned_devices), f)
    except OSError:
        pass  # Non-critical if we can't persist


def _register_active_device(device_id: str, device_name: str, session_id: str) -> None:
    """
    Register or update an active device.

    Args:
        device_id: Unique device identifier.
        device_name: Human-readable device name.
        session_id: Current session identifier.
    """
    _active_devices[device_id] = {
        "device_name": device_name,
        "device_id": device_id,
        "last_seen": time.time(),
        "session_id": session_id,
    }


def _get_active_devices(session_id: str) -> List[Dict[str, Any]]:
    """
    Get list of active devices for a session.

    Filters out devices inactive for more than 60 seconds.

    Args:
        session_id: Session identifier.

    Returns:
        List of active device dictionaries.
    """
    now = time.time()
    cutoff = now - 60  # 60 second timeout

    # Clean up stale devices
    stale_devices = [
        did for did, info in _active_devices.items() if info["last_seen"] < cutoff
    ]
    for did in stale_devices:
        del _active_devices[did]

    # Return active devices for this session
    return [
        info for info in _active_devices.values() if info["session_id"] == session_id
    ]


def _get_session_id(directory_path: str) -> str:
    """
    Generate a stable session ID from directory path.

    Args:
        directory_path: Absolute path to the directory being served.

    Returns:
        MD5 hash of the directory path as session identifier.
    """
    return md5(directory_path.encode()).hexdigest()[:16]


def _cleanup_old_messages(session_id: str) -> None:
    """
    Remove old messages from a chat session.

    Removes messages older than MESSAGE_RETENTION_SECONDS and
    trims to MAX_MESSAGES_PER_SESSION.

    Args:
        session_id: Session identifier to clean up.
    """
    if session_id not in _chat_sessions:
        return

    now = time.time()
    messages = _chat_sessions[session_id]

    # Remove expired messages
    messages[:] = [
        msg for msg in messages if now - msg["timestamp"] < MESSAGE_RETENTION_SECONDS
    ]

    # Trim to maximum count
    if len(messages) > MAX_MESSAGES_PER_SESSION:
        messages[:] = messages[-MAX_MESSAGES_PER_SESSION:]


def _add_message(
    session_id: str, sender: str, content: str, device_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a message to a chat session.

    Args:
        session_id: Session identifier.
        sender: Name/ID of the message sender.
        content: Message text content.
        device_id: Optional unique device identifier.

    Returns:
        The created message dictionary.
    """
    if session_id not in _chat_sessions:
        _chat_sessions[session_id] = []

    # XSS Prevention: Escape all user-provided content
    message = {
        "id": str(uuid.uuid4()),
        "sender": html.escape(sender),
        "content": html.escape(content),
        "timestamp": time.time(),
        "type": "text",
    }

    # Add device_id if provided (also escape it)
    if device_id:
        message["device_id"] = html.escape(device_id)

    _chat_sessions[session_id].append(message)
    _cleanup_old_messages(session_id)

    # Broadcast to SSE clients
    _broadcast_message_to_sse(session_id, message)

    return message


def _broadcast_message_to_sse(session_id: str, message: Dict[str, Any]) -> None:
    """
    Broadcast a new message to all SSE clients for a session.

    Args:
        session_id: Session identifier.
        message: Message dictionary to broadcast.
    """
    with _sse_lock:
        if session_id not in _sse_queues:
            return

        # Send message to all connected clients for this session
        dead_queues = []
        for client_queue in _sse_queues[session_id]:
            try:
                client_queue.put_nowait(message)
            except queue.Full:
                # Queue full, mark for removal
                dead_queues.append(client_queue)

        # Remove dead queues
        for dq in dead_queues:
            _sse_queues[session_id].remove(dq)


def _register_sse_client(session_id: str, client_queue: queue.Queue) -> None:
    """
    Register a new SSE client for a session.

    Args:
        session_id: Session identifier.
        client_queue: Queue for sending messages to this client.
    """
    with _sse_lock:
        if session_id not in _sse_queues:
            _sse_queues[session_id] = []
        _sse_queues[session_id].append(client_queue)


def _unregister_sse_client(session_id: str, client_queue: queue.Queue) -> None:
    """
    Unregister an SSE client.

    Args:
        session_id: Session identifier.
        client_queue: Queue to remove.
    """
    with _sse_lock:
        if session_id in _sse_queues and client_queue in _sse_queues[session_id]:
            _sse_queues[session_id].remove(client_queue)
            if not _sse_queues[session_id]:
                del _sse_queues[session_id]


def _broadcast_upload_progress(
    session_id: str,
    device_name: str,
    filename: str,
    bytes_uploaded: int,
    total_bytes: int,
    upload_path: str,
) -> None:
    """
    Broadcast upload progress to all SSE clients.

    Args:
            session_id: Session identifier.
            device_name: Name of the uploading device.
            filename: Name of the file being uploaded.
            bytes_uploaded: Number of bytes uploaded so far.
            total_bytes: Total size of the upload.
            upload_path: URL path where file is being uploaded.
    """
    percent = int((bytes_uploaded / total_bytes * 100)) if total_bytes > 0 else 0
    message = {
        "type": "upload_progress",
        "device_name": device_name,
        "filename": filename,
        "bytes_uploaded": bytes_uploaded,
        "total_bytes": total_bytes,
        "percent": percent,
        "upload_path": upload_path,
        "timestamp": time.time(),
    }
    _broadcast_message_to_sse(session_id, message)


def _broadcast_upload_complete(
    session_id: str,
    device_name: str,
    filename: str,
    upload_path: str,
) -> None:
    """
    Broadcast upload completion to all SSE clients.

    Args:
            session_id: Session identifier.
            device_name: Name of the uploading device.
            filename: Name of the uploaded file.
            upload_path: URL path where file was uploaded.
    """
    message = {
        "type": "upload_complete",
        "device_name": device_name,
        "filename": filename,
        "upload_path": upload_path,
        "timestamp": time.time(),
    }
    _broadcast_message_to_sse(session_id, message)


def _get_messages(
    session_id: str, since_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get messages from a chat session.

    Args:
        session_id: Session identifier.
        since_id: Optional message ID to get messages after.

    Returns:
        List of message dictionaries.
    """
    if session_id not in _chat_sessions:
        return []

    _cleanup_old_messages(session_id)
    messages = _chat_sessions[session_id]

    if since_id:
        # Find the index of since_id and return messages after it
        for i, msg in enumerate(messages):
            if msg["id"] == since_id:
                return messages[i + 1 :]
        # If since_id not found, return all recent messages
        return messages

    return messages


# Directory Size Helper


def _calculate_directory_size(directory_path: str) -> Dict[str, Any]:
    """
    Calculate total size of a directory.

    Walks the directory tree and sums file sizes. Caches result
    for SIZE_CACHE_DURATION to avoid expensive recalculation.

    Args:
        directory_path: Path to directory to calculate.

    Returns:
        Dictionary with size information.
    """
    # Check cache first
    now = time.time()
    if directory_path in _size_cache:
        cached_time, cached_data = _size_cache[directory_path]
        if now - cached_time < SIZE_CACHE_DURATION:
            return cached_data

    # Import format_size from ui module
    from .ui import format_size

    total_bytes = 0
    file_count = 0
    folder_count = 0

    try:
        dir_path = Path(directory_path)
        for entry in dir_path.rglob("*"):
            try:
                if entry.is_file():
                    total_bytes += entry.stat().st_size
                    file_count += 1
                elif entry.is_dir():
                    folder_count += 1
            except (OSError, PermissionError):
                # Skip inaccessible files
                continue
    except (OSError, PermissionError):
        pass

    result = {
        "total_bytes": total_bytes,
        "total_formatted": format_size(total_bytes),
        "file_count": file_count,
        "folder_count": folder_count,
    }

    # Cache the result
    _size_cache[directory_path] = (now, result)

    return result


# Thread Pool Server


class PooledHTTPServer(HTTPServer):
    """
    HTTP server using a thread pool for controlled concurrency.

    Uses ThreadPoolExecutor to limit maximum concurrent connections,
    preventing resource exhaustion under high load while maintaining
    high throughput for file transfers.

    Attributes:
        executor: Thread pool for handling requests.
        allow_reuse_address: Enables socket reuse to avoid bind errors.
    """

    def __init__(
        self,
        server_address: Tuple[str, int],
        RequestHandlerClass: Callable[..., SimpleHTTPRequestHandler],
        max_workers: int = MAX_WORKERS,
    ) -> None:
        """
        Initialize the pooled HTTP server.

        Args:
            server_address: Tuple of (host, port) to bind to.
            RequestHandlerClass: Handler class for processing requests.
            max_workers: Maximum concurrent connections (default: 100).
        """
        super().__init__(server_address, RequestHandlerClass)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.allow_reuse_address = True
        self._shutdown_flag = False

    def process_request(
        self, request: socket.socket, client_address: Tuple[str, int]
    ) -> None:
        """Submit request to thread pool instead of blocking."""
        if not self._shutdown_flag:
            self.executor.submit(self._process_request_thread, request, client_address)

    def _process_request_thread(
        self, request: socket.socket, client_address: Tuple[str, int]
    ) -> None:
        """Process a single request in a thread pool worker."""
        try:
            self.finish_request(request, client_address)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            # Client disconnected - normal behavior, no logging needed
            pass
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

    def handle_error(
        self, request: socket.socket, client_address: Tuple[str, int]
    ) -> None:
        """Silently handle errors for cleaner output."""
        pass

    def shutdown(self) -> None:
        """Shutdown the server and thread pool."""
        self._shutdown_flag = True
        super().shutdown()

    def server_close(self) -> None:
        """Clean up the thread pool when server closes."""
        self._shutdown_flag = True
        super().server_close()
        self.executor.shutdown(wait=False, cancel_futures=True)


# HTTP Request Handler


class VortexHandler(SimpleHTTPRequestHandler):
    """
    HTTP request handler for serving files and accepting uploads.

    Features:
        - HTTP Range requests for media seeking and download resumption
        - Chunked file streaming for memory-efficient large transfers
        - Comprehensive MIME type detection
        - Proper caching headers (ETag, Last-Modified, Cache-Control)
        - Security headers (X-Content-Type-Options, X-Frame-Options, CSP)
        - Path traversal protection
        - Rate limiting and optional authentication
        - Robust error handling for network and filesystem errors

    Attributes:
        base_directory: Root directory being served (absolute path).
        protocol_version: HTTP/1.1 for persistent connections.
        security_manager: Optional security manager for auth/rate limiting.
        is_https: Whether connection is using HTTPS.
    """

    base_directory: str
    protocol_version = "HTTP/1.1"
    security_manager: Optional["SecurityManager"] = None
    is_https: bool = False

    def __init__(
        self,
        *args: Any,
        directory: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the request handler.

        Args:
            directory: Directory to serve. Defaults to current directory.
        """
        if directory is None:
            directory = os.getcwd()
        self.base_directory = os.path.abspath(directory)
        super().__init__(*args, directory=directory, **kwargs)

    def setup(self) -> None:
        """Set up the connection with optimized socket options."""
        super().setup()
        try:
            # Increase socket buffer sizes for better throughput
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 512 * 1024)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512 * 1024)
            # Disable Nagle's algorithm for lower latency
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except (OSError, AttributeError):
            pass  # Not all systems support these options

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging for cleaner output."""
        pass

    # Security Helpers

    def _send_security_headers(self) -> None:
        """Send security headers to prevent common attacks."""
        if self.security_manager:
            # Use comprehensive security headers from security manager
            for header, value in self.security_manager.get_security_headers(
                self.is_https
            ).items():
                self.send_header(header, value)
        else:
            # Fallback: basic security headers
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")

    def _is_host(self) -> bool:
        """
        Check if the current request is from the host device.

        Host is identified as:
        - Request from localhost (127.0.0.1 or ::1)
        - Request from the server's own display address

        Returns:
            True if request is from host, False otherwise.
        """
        client_ip = self.client_address[0]

        # Check localhost
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return True

        # Check if matches server's display address
        if _server_display_address and client_ip == _server_display_address:
            return True

        return False

    def _check_device_ban(self) -> bool:
        """
        Check if the requesting device is banned.

        Extracts device_id from X-Device-ID header or device_id cookie.
        If device is banned, sends 403 and returns False.
        Also registers active devices for tracking.

        Returns:
            True if request is allowed, False if device is banned.
        """
        # Get device_id from custom header or cookie
        device_id = self.headers.get("X-Device-ID")
        device_name = self.headers.get("X-Device-Name", "Unknown")

        if not device_id:
            # Try to get from cookie
            cookie_header = self.headers.get("Cookie", "")
            for cookie in cookie_header.split(";"):
                cookie = cookie.strip()
                if cookie.startswith("device_id="):
                    device_id = cookie.split("=", 1)[1]
                    break

        # Register active device if we have device info (do this for ALL devices including host)
        if device_id:
            # Extract session_id from path
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)
            session_id = query_params.get("session", [""])[0]

            if session_id:
                _register_active_device(device_id, device_name, session_id)

        # Skip ban check for host (but device was already registered above)
        if self._is_host():
            return True

        # Check if device is banned
        if device_id and device_id in _banned_devices:
            self._send_error_safe(403, "Access denied: Device has been removed")
            return False

        return True

    def _validate_security(self) -> bool:
        """
        Validate request against security manager.

        Returns:
            True if request is allowed, False if blocked (error sent).
        """
        if not self.security_manager:
            return True

        # Get token from query string or header
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        token = None

        # Check query string first
        if "token" in query_params:
            token = query_params["token"][0]
        # Then check Authorization header
        elif auth_header := self.headers.get("Authorization"):
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        # Validate request
        client_ip = self.client_address[0]
        allowed, message, status_code = self.security_manager.validate_request(
            client_ip, token
        )

        if not allowed:
            self._send_error_safe(status_code, message)
            return False

        return True

    def _is_request_path_safe(self, path: str) -> bool:
        """
        Validate that a request path is safely within base_directory.

        Prevents directory traversal attacks using "../" or symlinks.

        Args:
            path: The filesystem path to validate.

        Returns:
            True if the path is safe, False otherwise.
        """
        return is_path_safe(Path(path), Path(self.base_directory))

    # Response Helpers

    def _send_html(self, content: str, status: int = 200) -> None:
        """Send an HTML response with proper headers."""
        encoded = content.encode(ENCODING, "surrogateescape")
        self.send_response(status)
        self.send_header("Content-Type", CONTENT_TYPE_HTML)
        self.send_header("Content-Length", str(len(encoded)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        """Send a JSON response with proper headers."""
        json_str = json.dumps(data, ensure_ascii=False)
        encoded = json_str.encode(ENCODING)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def _parse_json_body(self) -> Optional[Dict[str, Any]]:
        """Parse JSON from request body."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return None
            body = self.rfile.read(length).decode(ENCODING)
            return json.loads(body)
        except (ValueError, json.JSONDecodeError):
            return None

    def _send_error_safe(self, code: int, message: str) -> None:
        """Send error response, catching any connection errors."""
        try:
            self.send_error(code, message)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    # ZIP Download Handler

    def _handle_zip_download(self, dir_path: str, include_body: bool = True) -> None:
        """
        Handle a request to download directory contents as a ZIP file.

        Creates an in-memory ZIP archive of all files in the directory
        (not recursive) and streams it to the client.

        Args:
            dir_path: Path to the directory to zip.
            include_body: Whether to include body (False for HEAD requests).
        """
        directory = Path(dir_path)
        dir_name = directory.name or "download"
        zip_filename = f"{dir_name}.zip"

        # Build ZIP in memory to determine size for Content-Length
        zip_buffer = io.BytesIO()

        try:
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for entry in directory.iterdir():
                    try:
                        if entry.is_file():
                            zf.write(entry, entry.name)
                    except (OSError, PermissionError):
                        continue
        except Exception as e:
            self._send_error_safe(500, f"Failed to create ZIP: {e}")
            return

        zip_size = zip_buffer.tell()
        zip_buffer.seek(0)

        if zip_size == 0:
            self._send_error_safe(404, "No files to download")
            return

        # Send response
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_ZIP)
        self.send_header("Content-Length", str(zip_size))
        self.send_header(
            "Content-Disposition", f'attachment; filename="{zip_filename}"'
        )
        self.send_header("Cache-Control", "no-cache")
        self._send_security_headers()
        self.end_headers()

        # Stream ZIP content
        if include_body:
            try:
                while True:
                    chunk = zip_buffer.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    # File Streaming

    def _stream_file(self, file_path: str, start: int, end: int) -> bool:
        """
        Stream a file range to the client in chunks.

        Args:
            file_path: Path to the file to stream.
            start: Starting byte position.
            end: Ending byte position (inclusive).

        Returns:
            True if streaming completed successfully, False otherwise.
        """
        bytes_to_send = end - start + 1

        try:
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = bytes_to_send

                while remaining > 0:
                    chunk_size = min(CHUNK_SIZE, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return False
        except OSError:
            return False

    # API Endpoints

    def _handle_api_messages_get(self, query_params: Dict[str, List[str]]) -> None:
        """Handle GET /api/messages - retrieve chat messages."""
        session_id = query_params.get("session", [""])[0]
        since_id = query_params.get("since", [""])[0] or None

        if not session_id:
            self._send_json({"error": "Missing session parameter"}, 400)
            return

        messages = _get_messages(session_id, since_id)
        self._send_json({"messages": messages, "session_id": session_id})

    def _handle_api_events_sse(self, query_params: Dict[str, List[str]]) -> None:
        """
        Handle GET /api/events - Server-Sent Events endpoint for real-time messages.

        Keeps connection open and streams new messages as they arrive.
        """
        session_id = query_params.get("session", [""])[0]

        if not session_id:
            self._send_error_safe(400, "Missing session parameter")
            return

        # Register device from query params (EventSource can't send custom headers)
        device_id = query_params.get("device_id", [""])[0]
        device_name = query_params.get("device_name", ["Unknown"])[0]
        if device_id and session_id:
            _register_active_device(device_id, device_name, session_id)

        # Create queue for this client
        client_queue: queue.Queue = queue.Queue(maxsize=50)
        _register_sse_client(session_id, client_queue)

        try:
            # Send SSE headers
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._send_security_headers()
            self.end_headers()

            # Send initial heartbeat
            self.wfile.write(b": heartbeat\n\n")
            self.wfile.flush()

            # Send existing messages as initial data
            existing_messages = _get_messages(session_id)
            if existing_messages:
                for msg in existing_messages:
                    event_data = f"data: {json.dumps(msg)}\n\n"
                    self.wfile.write(event_data.encode(ENCODING))
                self.wfile.flush()

            # Keep connection alive and send new messages
            while True:
                try:
                    # Wait for new message with timeout for heartbeat
                    message = client_queue.get(timeout=30)

                    # Send message as SSE event
                    event_data = f"data: {json.dumps(message)}\n\n"
                    self.wfile.write(event_data.encode(ENCODING))
                    self.wfile.flush()

                except queue.Empty:
                    # Send heartbeat to keep connection alive
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            # Client disconnected
            pass
        finally:
            # Clean up
            _unregister_sse_client(session_id, client_queue)

    def _handle_api_messages_post(self) -> None:
        """Handle POST /api/messages - send a chat message."""
        # Apply chat-specific rate limiting
        if _chat_rate_limiter:
            client_ip = self.client_address[0]
            if not _chat_rate_limiter.check(client_ip):
                self._send_json({"error": "Too many messages. Please slow down."}, 429)
                return

        data = self._parse_json_body()

        if not data:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        session_id = data.get("session_id")
        sender = data.get("sender", "")
        content = data.get("content", "")
        device_id = data.get("device_id")

        if not session_id or not sender or not content:
            self._send_json({"error": "Missing required fields"}, 400)
            return

        # Register active device
        if device_id and sender:
            _register_active_device(device_id, sender, session_id)

        # Check if device is banned
        if device_id and device_id in _banned_devices:
            self._send_json({"error": "Device banned"}, 403)
            return

        # Validate content length
        if len(content) > 1000:
            self._send_json({"error": "Message too long (max 1000 chars)"}, 400)
            return

        # Note: _add_message now applies html.escape() to all fields
        message = _add_message(session_id, sender, content, device_id)
        self._send_json({"message": message, "status": "ok"})

    def _handle_api_directory_size(self, query_params: Dict[str, List[str]]) -> None:
        """Handle GET /api/directory-size - get directory size info."""
        session_id = query_params.get("session", [""])[0]

        if not session_id:
            self._send_json({"error": "Missing session parameter"}, 400)
            return

        size_info = _calculate_directory_size(self.base_directory)
        self._send_json({"size": size_info, "cached_at": time.time()})

    def _handle_api_host_status(self) -> None:
        """Handle GET /api/host-status - check if current device is the host."""
        is_host = self._is_host()
        self._send_json({"is_host": is_host})

    def _handle_api_audio_metadata(self, query_params: Dict[str, List[str]]) -> None:
        """
        Handle GET /api/audio-metadata - extract audio file metadata.

        Returns JSON with title, artist, album, and base64-encoded artwork.
        Supports MP3 (ID3v2) and M4A (MP4 atoms) formats.
        """
        # Get file parameter
        file_param = query_params.get("file")
        if not file_param or len(file_param) == 0:
            self._send_json({"error": "Missing file parameter"}, 400)
            return

        # Decode URL-encoded file path
        file_url = file_param[0]

        # Parse URL to get path
        try:
            parsed = urlparse(file_url)
            file_path = unquote(parsed.path)

            # Translate to filesystem path
            full_path = self.translate_path(file_path)

            # Security: Validate path is within base directory
            if not self._is_request_path_safe(full_path):
                self._send_json({"error": "Access denied"}, 403)
                return

            # Check if file exists
            if not os.path.isfile(full_path):
                self._send_json({"error": "File not found"}, 404)
                return

            # Extract metadata using audio_player module
            metadata = get_audio_metadata(full_path)

            # Send metadata as JSON
            self._send_json(metadata)

        except Exception as e:
            self._send_json({"error": f"Metadata extraction failed: {str(e)}"}, 500)

    def _handle_api_kick_post(self) -> None:
        """Handle POST /api/kick - ban a device (host only)."""
        # Verify host privileges
        if not self._is_host():
            self._send_json({"error": "Unauthorized: Host access required"}, 403)
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0 or content_length > 10000:
                self._send_json({"error": "Invalid request size"}, 400)
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        device_id = data.get("device_id")

        if not device_id:
            self._send_json({"error": "Missing device_id"}, 400)
            return

        # Add to banned set and persist
        _banned_devices.add(device_id)
        _save_banned_devices()

        # Broadcast kick event to all SSE clients so kicked device terminates immediately
        kick_message = {
            "type": "device_kicked",
            "device_id": device_id,
            "timestamp": time.time(),
        }
        with _sse_lock:
            for session_id in _sse_queues:
                for client_queue in _sse_queues[session_id]:
                    try:
                        client_queue.put_nowait(kick_message)
                    except queue.Full:
                        pass

        self._send_json({"status": "ok", "message": "Device banned successfully"})

    def _handle_api_unkick_post(self) -> None:
        """Handle POST /api/unkick - unban a device (host only)."""
        # Verify host privileges
        if not self._is_host():
            self._send_json({"error": "Unauthorized: Host access required"}, 403)
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0 or content_length > 10000:
                self._send_json({"error": "Invalid request size"}, 400)
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        device_id = data.get("device_id")

        if not device_id:
            self._send_json({"error": "Missing device_id"}, 400)
            return

        # Remove from banned set and persist
        _banned_devices.discard(device_id)
        _save_banned_devices()

        self._send_json({"status": "ok", "message": "Device unbanned successfully"})

    def _handle_api_stop_server_post(self) -> None:
        """
        Handle POST /api/stop-server - Stop the Vortex server.

        Only the host can stop the server.

        Response:
            {"success": true, "message": "Server stopping..."}
        """
        # Only host can stop the server
        if not self._is_host():
            self._send_json({"error": "Only the host can stop the server"}, 403)
            return

        # Set global terminating flag to prevent new uploads
        global _server_terminating, _active_uploads
        _server_terminating = True

        # Delete all partial upload files
        with _active_uploads_lock:
            for upload_id, temp_path in list(_active_uploads.items()):
                try:
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                except OSError:
                    pass  # File may not exist yet or already deleted
            _active_uploads.clear()

        # Broadcast termination message to all SSE clients
        with _sse_lock:
            for session_id in _sse_queues:
                termination_msg = {
                    "type": "server_terminating",
                    "message": "Server is shutting down",
                    "timestamp": time.time(),
                }
                for client_queue in _sse_queues[session_id]:
                    try:
                        client_queue.put_nowait(termination_msg)
                    except queue.Full:
                        pass

        # Send success response first
        self._send_json({"success": True, "message": "Server terminating"})

        # Shutdown after 3 seconds (time for clients to receive SSE message)
        def delayed_shutdown():
            time.sleep(3.0)
            os._exit(0)

        threading.Thread(target=delayed_shutdown, daemon=True).start()

    def _handle_api_banned_devices_get(self) -> None:
        """Handle GET /api/banned-devices - list all banned devices (host only)."""
        # Verify host privileges
        if not self._is_host():
            self._send_json({"error": "Unauthorized: Host access required"}, 403)
            return

        # Return list of banned device IDs
        self._send_json(
            {"banned_devices": list(_banned_devices), "count": len(_banned_devices)}
        )

    def _handle_api_active_devices_get(
        self, query_params: Dict[str, List[str]]
    ) -> None:
        """Handle GET /api/active-devices - list all active devices (host only)."""
        # Verify host privileges
        if not self._is_host():
            self._send_json({"error": "Unauthorized: Host access required"}, 403)
            return

        session_id = query_params.get("session", [""])[0]

        if not session_id:
            self._send_json({"error": "Missing session parameter"}, 400)
            return

        active_devices = _get_active_devices(session_id)
        self._send_json(
            {"active_devices": active_devices, "count": len(active_devices)}
        )

    # HTTP Method Handlers

    def do_HEAD(self) -> None:
        """Handle HEAD requests (same as GET but without body)."""
        self._handle_get_or_head(include_body=False)

    def do_GET(self) -> None:
        """
        Handle GET requests for directory listings and file downloads.

        Supports HTTP Range requests for media seeking and download resumption.
        Uses chunked streaming for memory-efficient large file transfers.
        """
        self._handle_get_or_head(include_body=True)

    def _handle_get_or_head(self, include_body: bool = True) -> None:
        """Common handler for GET and HEAD requests."""
        # Security validation (rate limiting and token auth)
        if not self._validate_security():
            return

        # Check if device is banned
        if not self._check_device_ban():
            return

        # Parse URL for query parameters
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        clean_path = unquote(parsed.path)

        # API Endpoints
        if clean_path == "/api/server-status":
            global _server_terminating
            self._send_json({"terminating": _server_terminating})
            return
        elif clean_path == "/api/messages":
            self._handle_api_messages_get(query_params)
            return
        elif clean_path == "/api/events":
            self._handle_api_events_sse(query_params)
            return
        elif clean_path == "/api/directory-size":
            self._handle_api_directory_size(query_params)
            return
        elif clean_path == "/api/host-status":
            self._handle_api_host_status()
            return
        elif clean_path == "/api/banned-devices":
            self._handle_api_banned_devices_get()
            return
        elif clean_path == "/api/active-devices":
            self._handle_api_active_devices_get(query_params)
            return
        elif clean_path == "/api/audio-metadata":
            self._handle_api_audio_metadata(query_params)
            return

        path = self.translate_path(parsed.path)

        # Security: Validate path is within base directory
        if not self._is_request_path_safe(path):
            self._send_error_safe(403, "Access denied")
            return

        # Directory Handling
        if os.path.isdir(path):
            # ZIP download request
            if query_params.get("download") == ["zip"]:
                self._handle_zip_download(path, include_body)
                return

            # Regular directory listing
            try:
                session_id = _get_session_id(self.base_directory)
                html_page = render_directory_listing(
                    self.base_directory, path, parsed.path, session_id
                )
                self._send_html(html_page)
            except (OSError, PermissionError) as e:
                self._send_error_safe(403, f"Cannot access directory: {e}")
            return

        # File Not Found
        if not os.path.isfile(path):
            self._send_error_safe(404, "File not found")
            return

        # File Handling
        try:
            file_stat = os.stat(path)
            file_size = file_stat.st_size
        except OSError as e:
            self._send_error_safe(403, f"Cannot access file: {e}")
            return

        # Generate response headers
        mime_type = get_mime_type(path)
        etag = generate_etag(path, file_stat)
        last_modified = formatdate(file_stat.st_mtime, usegmt=True)
        filename = os.path.basename(path)

        # Check If-None-Match for caching (304 Not Modified)
        if_none_match = self.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            self.send_response(304)
            self.end_headers()
            return

        # Range Request Handling
        range_header = self.headers.get("Range")

        if range_header:
            byte_range = parse_range_header(range_header, file_size)

            if byte_range is None:
                # Invalid range - send 416 Range Not Satisfiable
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            start, end = byte_range
            content_length = end - start + 1

            # Send 206 Partial Content
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        else:
            # Full file request
            start, end = 0, file_size - 1
            content_length = file_size
            self.send_response(200)

        # Send Headers
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", last_modified)
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self._send_security_headers()
        self.end_headers()

        # Stream file content (skip for HEAD requests)
        if include_body and content_length > 0:
            self._stream_file(path, start, end)

    def do_POST(self) -> None:
        """
        Handle POST requests for file uploads via multipart/form-data.

        Uses streaming to handle large files without loading them entirely
        into memory. This allows uploading files of any size smoothly.
        """
        # Check if server is terminating - reject new uploads
        global _server_terminating
        if _server_terminating:
            self._send_error_safe(503, "Server is shutting down")
            return

        # Security validation (rate limiting and token auth)
        if not self._validate_security():
            return

        # Check if device is banned
        if not self._check_device_ban():
            return

        # Parse URL path
        parsed = urlparse(self.path)
        clean_path = unquote(parsed.path)

        # API Endpoints
        if clean_path == "/api/messages":
            self._handle_api_messages_post()
            return
        elif clean_path == "/api/kick":
            self._handle_api_kick_post()
            return
        elif clean_path == "/api/unkick":
            self._handle_api_unkick_post()
            return
        elif clean_path == "/api/stop-server":
            self._handle_api_stop_server_post()
            return

        content_type = self.headers.get("Content-Type", "")

        if CONTENT_TYPE_MULTIPART not in content_type:
            self._send_error_safe(400, "Expected multipart/form-data")
            return

        boundary = extract_boundary(content_type)
        if not boundary:
            self._send_error_safe(400, "No multipart boundary found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_error_safe(400, "Missing or invalid Content-Length")
            return

        if length <= 0:
            self._send_error_safe(400, "Invalid Content-Length")
            return

        # Determine upload target directory from request path
        target_path = self.translate_path(parsed.path)

        # Security: Validate upload path is within base directory
        if not self._is_request_path_safe(target_path):
            self._send_error_safe(403, "Access denied")
            return

        # Ensure target is a directory
        if not os.path.isdir(target_path):
            self._send_error_safe(400, "Upload target must be a directory")
            return

        # Generate unique upload ID and register this upload
        upload_id = str(uuid.uuid4())

        # Get device info for progress notifications
        device_name = self.headers.get("X-Device-Name", "Unknown Device")
        device_id = self.headers.get("X-Device-ID")
        if not device_id:
            # Try to get from cookie
            cookie_header = self.headers.get("Cookie", "")
            for cookie in cookie_header.split(";"):
                cookie = cookie.strip()
                if cookie.startswith("device_id="):
                    device_id = cookie.split("=", 1)[1]
                    break

        # Get session ID for SSE broadcast
        session_id = _get_session_id(self.base_directory)

        # Create progress callback for SSE broadcast
        def progress_callback(
            bytes_uploaded: int, total_bytes: int, filename: str
        ) -> None:
            _broadcast_upload_progress(
                session_id=session_id,
                device_name=device_name,
                filename=filename,
                bytes_uploaded=bytes_uploaded,
                total_bytes=total_bytes,
                upload_path=clean_path,
            )

        # Stream upload to disk with termination checking and progress broadcast
        try:
            result: UploadResult = parse_multipart_streaming(
                self.rfile,
                length,
                boundary,
                target_path,
                upload_id=upload_id,
                termination_check=lambda: _server_terminating,
                progress_callback=progress_callback,
            )
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Clean up upload tracking on connection error
            with _active_uploads_lock:
                _active_uploads.pop(upload_id, None)
            return

        # Remove from active uploads tracking
        with _active_uploads_lock:
            _active_uploads.pop(upload_id, None)

        if not result.success:
            self._send_error_safe(400, result.error_message or "Upload failed")
            return

        # Broadcast upload completion via SSE
        if result.filename:
            _broadcast_upload_complete(
                session_id=session_id,
                device_name=device_name,
                filename=result.filename,
                upload_path=clean_path,
            )

        # Redirect back to current directory after successful upload
        try:
            self.send_response(303)
            self.send_header("Location", clean_path)
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


# Network Utilities


def get_local_ip(mode: str = "auto") -> Tuple[str, str]:
    """
    Detect the appropriate server address based on mode.

    Args:
        mode: Address detection mode.
            - 'auto': Intelligent detection (try LAN, fallback to localhost)
            - 'localhost': Force localhost only (127.0.0.1)
            - 'lan': Force LAN detection (fail if no LAN found)

    Returns:
        Tuple of (bind_address, display_address).
        bind_address is always '0.0.0.0' for accepting connections.
        display_address is the user-facing IP for sharing.
    """
    bind_address = "0.0.0.0"

    if mode == "localhost":
        return bind_address, "localhost"

    # Try UDP socket trick with multiple DNS servers
    for dns_server in DNS_SERVERS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.0)
            sock.connect(dns_server)
            ip = sock.getsockname()[0]
            sock.close()
            # Skip IPv6 addresses (contain ':')
            if ":" not in ip and not ip.startswith("127."):
                return bind_address, ip
        except OSError:
            continue

    # Fallback: try gethostname + gethostbyname
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ":" not in ip and not ip.startswith("127."):
            return bind_address, ip
    except OSError:
        pass

    # Final fallback
    if mode == "lan":
        # LAN mode requires a LAN IP - fail if not found
        raise RuntimeError("No LAN IP address found. Check your network connection.")

    return bind_address, FALLBACK_IP


# Server Entry Point


def run_server(
    directory: str,
    port: int,
    max_parallel: int = 4,
    address_mode: str = "auto",
    use_https: bool = False,
    use_token_auth: bool = False,
    regenerate_token: bool = False,
) -> None:
    """
    Start the Vortex HTTP server.

    Args:
        directory: Path to the directory to serve.
        port: Port number to listen on.
        max_parallel: Max parallel uploads hint for browser (unused server-side).
        address_mode: Address detection mode ('auto', 'localhost', 'lan').
        use_https: Enable HTTPS with self-signed certificate.
        use_token_auth: Require token authentication for all requests.
        regenerate_token: Generate a new authentication token.

    The server uses a thread pool to handle multiple concurrent connections
    efficiently, with limits to prevent resource exhaustion.
    """
    resolved_directory = str(Path(directory).resolve())

    # Load banned devices from persistent storage
    _load_banned_devices()

    # Initialize chat rate limiter (30 messages per minute per IP)
    global _chat_rate_limiter
    from .security import _RateLimiter

    _chat_rate_limiter = _RateLimiter(threshold=30, window_seconds=60)

    # Initialize security manager if any security features are enabled
    security_manager = None
    if use_https or use_token_auth:
        from .security import SecurityManager

        security_manager = SecurityManager(
            enable_auth=use_token_auth,
        )

        # Regenerate token if requested
        if regenerate_token:
            security_manager.regenerate_token()

        # Configure handler class with security settings
        VortexHandler.security_manager = security_manager
        VortexHandler.is_https = use_https

    def handler_factory(*args: Any, **kwargs: Any) -> VortexHandler:
        return VortexHandler(*args, directory=resolved_directory, **kwargs)

    bind_address, display_address = get_local_ip(address_mode)

    # Set global display address for host detection
    global _server_display_address
    _server_display_address = display_address

    server_address = (bind_address, port)
    httpd = PooledHTTPServer(server_address, handler_factory, max_workers=MAX_WORKERS)

    # Wrap socket with SSL if HTTPS is enabled
    if use_https and security_manager:
        ssl_context = security_manager.get_ssl_context()
        if ssl_context:
            httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)
            protocol = "https"
        else:
            print("Warning: Failed to create SSL context, falling back to HTTP")
            protocol = "http"
    else:
        protocol = "http"

    print("Vortex active")
    print(f"Serving directory: {resolved_directory}")
    print(f"Share this on your network: {protocol}://{display_address}:{port}/")
    print(f"Max concurrent connections: {MAX_WORKERS}")

    # Display security information
    if security_manager:
        if use_token_auth:
            token = security_manager.get_token()
            print(f"\n🔐 Token authentication ENABLED")
            print(
                f"   Access URL: {protocol}://{display_address}:{port}/?token={token}"
            )
            print(f"   Token: {token}")
        if use_https:
            print(f"\n🔒 HTTPS ENABLED (self-signed certificate)")
            print("   Browsers may show a security warning - this is expected.")

    print("\nPress Ctrl+C to stop.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nVortex deactivated.")
        # Clear class-level security settings
        VortexHandler.security_manager = None
        VortexHandler.is_https = False
        httpd.shutdown()
        httpd.server_close()
