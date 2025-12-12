# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
UI rendering module for Vortex file gateway.

This module provides HTML template rendering for the directory listing
and file upload interface. It generates a responsive, mobile-friendly
web UI for browsing and uploading files.
"""

import html
import os
from pathlib import Path
from typing import List
from urllib.parse import unquote

from .scripts import JS_UPLOAD_HANDLER
from .styles import CSS_STYLESHEET
from .audio_player import (
    get_audio_player_html,
    get_audio_player_css,
    get_audio_player_js,
)
from .media_viewer import (
    get_image_viewer_html,
    get_image_viewer_css,
    get_image_viewer_js,
    get_video_player_html,
    get_video_player_css,
    get_video_player_js,
)

# Pre-generate combined resources (once at module load for performance)
_AUDIO_PLAYER_CSS = get_audio_player_css()
_MEDIA_VIEWER_CSS = get_image_viewer_css() + "\n" + get_video_player_css()
_COMPLETE_STYLESHEET = (
    CSS_STYLESHEET + "\n\n" + _AUDIO_PLAYER_CSS + "\n\n" + _MEDIA_VIEWER_CSS
)

_AUDIO_PLAYER_JS = get_audio_player_js()
_MEDIA_VIEWER_JS = get_image_viewer_js() + "\n" + get_video_player_js()
_COMPLETE_SCRIPTS = (
    JS_UPLOAD_HANDLER + "\n\n" + _AUDIO_PLAYER_JS + "\n\n" + _MEDIA_VIEWER_JS
)

_AUDIO_PLAYER_HTML = get_audio_player_html()
_MEDIA_VIEWER_HTML = get_image_viewer_html() + get_video_player_html()


# Size Formatting

# Units for human-readable file sizes
_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")
_SIZE_THRESHOLD = 1024.0


def format_size(size_bytes: int) -> str:
    """
    Format a file size in bytes to a human-readable string.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Human-readable size string (e.g., "1.5 MB", "256 KB").
    """
    size = float(size_bytes)
    for unit in _SIZE_UNITS[:-1]:
        if size < _SIZE_THRESHOLD:
            return f"{size:3.1f} {unit}"
        size /= _SIZE_THRESHOLD
    return f"{size:.1f} {_SIZE_UNITS[-1]}"


# HTML Layout


def render_layout(title: str, body_html: str) -> str:
    """
    Render the main HTML layout with header, body content, and footer.

    This is the outer shell of the web interface, providing consistent
    styling and structure across all pages.

    Args:
        title: Page title for the browser tab.
        body_html: HTML content to insert into the main body area.

    Returns:
        Complete HTML document as a string.
    """
    escaped_title = html.escape(title)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="format-detection" content="telephone=no">
<meta name="theme-color" content="#e8e4e0">
<title>{escaped_title}</title>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<style>{_COMPLETE_STYLESHEET}</style>
</head>
<body>
  <div class="app-root">
    <div class="device-shell">
      <header class="device-header">
        <h1>
          <span>Vortex</span>
          <div class="header-controls">
            <button id="theme-toggle" class="theme-toggle" aria-label="Toggle dark mode" title="Toggle dark mode">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
            </button>
            <button id="server-stop-btn" class="server-stop-btn" aria-label="Stop server" title="Stop server" style="display: none;">×</button>
          </div>
        </h1>
        <p>Local file gateway</p>
      </header>
      {body_html}
    </div>
  </div>
<script>{_COMPLETE_SCRIPTS}</script>
</body>
</html>
"""


# Directory Listing


def _build_file_table_rows(real_path: Path, base_directory: str) -> List[str]:
    """
    Build HTML table rows for directory entries.

    Creates a table row for each file and subdirectory, including
    a parent directory link ("..") when not at the root.

    Args:
        real_path: Path to the directory being listed.
        base_directory: Root directory being served.

    Returns:
        List of HTML table row strings.
    """
    rows: List[str] = []

    # Add parent directory link if not at root
    rel = os.path.relpath(real_path, base_directory)
    if rel != ".":
        rows.append('<tr><td><a href="../">[..]</a></td><td></td></tr>')

    # Sort entries case-insensitively
    try:
        entries = sorted(real_path.iterdir(), key=lambda p: p.name.lower())
    except (OSError, PermissionError):
        # Cannot read directory - return what we have
        return rows

    for entry in entries:
        try:
            is_dir = entry.is_dir()
            name = entry.name + ("/" if is_dir else "")
            escaped_name = html.escape(name)

            if is_dir:
                size = "-"
            else:
                try:
                    size = format_size(entry.stat().st_size)
                except (OSError, PermissionError):
                    size = "?"  # Cannot stat file

            rows.append(
                f'<tr><td><a href="{escaped_name}">{escaped_name}</a></td>'
                f"<td>{size}</td></tr>"
            )
        except (OSError, PermissionError):
            # Skip entries we cannot access
            continue

    return rows


def render_directory_listing(
    base_directory: str,
    fs_path: str,
    request_path: str,
    session_id: str,
) -> str:
    """
    Build the complete HTML page for a directory listing.

    Includes the upload panel and file table with all entries
    in the specified directory.

    Args:
        base_directory: Root directory being served.
        fs_path: Filesystem path to the current directory.
        request_path: URL path from the HTTP request.
        session_id: Chat session identifier.

    Returns:
        Complete HTML page for the directory listing.
    """
    real_path = Path(fs_path)
    display_path = html.escape(unquote(request_path))
    base_name = html.escape(os.path.basename(base_directory) or "/")

    # Build file table rows
    rows = _build_file_table_rows(real_path, base_directory)

    # Count files (not directories) for Download All button
    file_count = 0
    try:
        for entry in real_path.iterdir():
            try:
                if entry.is_file():
                    file_count += 1
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass

    # Build the file table HTML
    table_html = (
        "<table>"
        "<thead><tr><th>Name</th><th>Size</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )

    # Download All button (only shown if there are files)
    download_btn = ""
    if file_count > 0:
        download_btn = (
            f'<a class="btn btn-download" href="?download=zip">'
            f"Download All ({file_count})</a>"
        )

    # Subheader shows current path and base directory
    subheader = f"""
      <div id="session-data" data-session-id="{html.escape(session_id)}" data-base-dir="{html.escape(str(base_directory))}" style="display: none;"></div>
      <div class="device-subheader">
        <span>Serving: {html.escape(str(base_directory))}</span>
        <span>{display_path}</span>
        <span id="dir-size-info">Calculating size...</span>
      </div>
    """

    # Main content with upload panel, file list, and chat
    main_content = f"""
    <main class="device-main">
      <section class="panel panel-files">
        <div class="panel-title">
          <span>Files</span>
        </div>
        {download_btn}
        <div class="file-list">
          {table_html}
        </div>
      </section>
      <section class="panel panel-upload">
        <div class="panel-title">
          <span>Upload</span>
        </div>
        <p class="path-label">Select file(s) to upload</p>
        <form method="post" enctype="multipart/form-data">
          <div class="upload-row">
            <label class="file-input">
              <input type="file" name="file" multiple required>
              <span class="file-button">Files</span>
              <span class="file-name">None</span>
            </label>
            <button class="btn" type="submit">Send</button>
          </div>
          <div class="upload-progress">
            <div class="progress-bar-container">
              <div class="progress-bar"></div>
            </div>
            <span class="progress-text">Uploading...</span>
          </div>
          <div class="upload-error"></div>
        </form>
        <div class="qr-code-container" id="qr-container">
          <div class="qr-title">Scan to Connect</div>
          <div id="qr-code"></div>
          <div class="qr-url" id="qr-url-text"></div>
        </div>
      </section>
      <section class="panel panel-chat">
        <div class="panel-title">
          <span>Chat</span>
          <span id="chat-status">●</span>
        </div>
        <div class="active-devices-section" id="active-section" style="display: none;">
          <div class="active-header">
            <span>Active Devices</span>
            <button class="active-close" id="active-close">×</button>
          </div>
          <div class="active-list" id="active-list"></div>
        </div>
        <div class="banned-devices-section" id="banned-section" style="display: none;">
          <div class="banned-header">
            <span>Kicked Devices</span>
            <button class="banned-close" id="banned-close">×</button>
          </div>
          <div class="banned-list" id="banned-list"></div>
        </div>
        <div class="chat-messages" id="chat-messages"></div>
        <form class="chat-form" id="chat-form">
          <input type="text" id="chat-input" placeholder="Type message..." maxlength="1000" autocomplete="off">
          <button type="submit" class="btn btn-chat">Send</button>
        </form>
        <div class="host-controls" id="host-controls" style="display: none;">
          <button class="btn-manage-devices" id="manage-active-btn">Active Devices</button>
          <button class="btn-manage-bans" id="manage-bans-btn">Kicked Devices</button>
        </div>
      </section>
    </main>
    """

    # Inject audio player and media viewer modals after device-shell
    body_with_modals = (
        subheader
        + main_content
        + "\n    </div>\n    "
        + _AUDIO_PLAYER_HTML
        + "\n    "
        + _MEDIA_VIEWER_HTML
        + '\n    <div class="dummy-wrapper">'
    )

    return render_layout("Vortex", body_with_modals)
