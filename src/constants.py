# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
Constants and configuration values for Vortex.

This module centralizes all magic numbers, configuration defaults, and
static mappings used throughout the application. Keeping constants in
one place makes the codebase easier to configure and maintain.
"""

# Encoding

ENCODING = "utf-8"

# Content Types

CONTENT_TYPE_HTML = "text/html; charset=utf-8"
CONTENT_TYPE_MULTIPART = "multipart/form-data"
CONTENT_TYPE_OCTET = "application/octet-stream"
CONTENT_TYPE_ZIP = "application/zip"

# Network Defaults

FALLBACK_IP = "127.0.0.1"
DNS_SERVERS = [
    ("8.8.8.8", 53),
    ("1.1.1.1", 53),
]  # Used to detect local IP via UDP socket trick

# Streaming Configuration

# Chunk size for streaming file reads/writes.
# 1MB optimized for modern networks to reduce I/O syscall overhead.
CHUNK_SIZE = 256 * 1024  # Optimized for concurrency

# Maximum size for multipart form headers before rejecting request.
# Prevents memory exhaustion from malformed or malicious requests.
MAX_HEADER_SIZE = 8 * 1024

# Thread Pool Configuration

# Maximum concurrent connections the server will handle.
# Prevents resource exhaustion under high load.
MAX_WORKERS = 100

# MIME Type Mapping
# Comprehensive mapping of file extensions to MIME types.
# Organized by category for maintainability.

MIME_TYPES = {
    # Video Formats
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".ogv": "video/ogg",
    ".3gp": "video/3gpp",
    ".3g2": "video/3gpp2",
    ".ts": "video/mp2t",
    ".m2ts": "video/mp2t",
    ".mts": "video/mp2t",
    ".vob": "video/dvd",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
    # Audio Formats
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".m4b": "audio/mp4",  # Audiobook
    ".m4p": "audio/mp4",  # Protected audio
    ".m4r": "audio/mp4",  # Ringtone
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/opus",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".wma": "audio/x-ms-wma",
    ".aiff": "audio/aiff",
    ".aif": "audio/aiff",
    ".aifc": "audio/aiff",  # Compressed AIFF
    ".caf": "audio/x-caf",  # Core Audio Format
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    ".weba": "audio/webm",
    ".mka": "audio/x-matroska",
    # Image Formats
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".heic": "image/heic",  # Apple photo format
    ".heif": "image/heif",  # Apple photo format
    ".heics": "image/heic-sequence",  # Apple photo sequence
    ".avif": "image/avif",
    ".raw": "image/raw",
    ".cr2": "image/x-canon-cr2",  # Canon RAW
    ".nef": "image/x-nikon-nef",  # Nikon RAW
    ".arw": "image/x-sony-arw",  # Sony RAW
    ".dng": "image/dng",  # Adobe Digital Negative / ProRAW
    # Document Formats
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".txt": "text/plain",
    ".rtf": "application/rtf",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".md": "text/markdown",
    # Archive Formats
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".xz": "application/x-xz",
    # Streaming Playlist Formats
    ".m3u": "audio/x-mpegurl",
    ".m3u8": "application/vnd.apple.mpegurl",
    ".pls": "audio/x-scpls",
    # Font Formats
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    # Other Common Formats
    ".apk": "application/vnd.android.package-archive",
    ".exe": "application/x-msdownload",
    ".dmg": "application/x-apple-diskimage",
    ".iso": "application/x-iso9660-image",
    ".torrent": "application/x-bittorrent",
}
