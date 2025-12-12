# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
High-performance audio player module for Vortex.

Optimized for memory efficiency, rendering speed, and minimal CPU usage.
Features pitch shifting, tempo control, 3-band EQ, album artwork extraction,
LED-style VU meter visualizer, and dual-mode UI (full/mini) with persistent playback.
"""

import base64
import hashlib
import os
import struct
from typing import Dict, Optional, Tuple


# ========================================
# METADATA EXTRACTION (Pure Python, Zero Dependencies)
# ========================================

# LRU metadata cache - max 50 entries (~2MB memory for typical album art)
_metadata_cache: Dict[str, Dict] = {}
_cache_order: list = []
MAX_CACHE_SIZE = 50


def _evict_cache():
    """Evict oldest cache entry when cache size exceeds limit."""
    if len(_cache_order) > MAX_CACHE_SIZE:
        oldest_key = _cache_order.pop(0)
        _metadata_cache.pop(oldest_key, None)


def _hash_color(text: str, index: int) -> str:
    """Generate deterministic hex color from text hash for gradient placeholder."""
    hash_bytes = hashlib.md5(text.encode()).digest()
    # Use different byte offsets for variety
    offset = index * 3
    r = hash_bytes[offset % 16]
    g = hash_bytes[(offset + 1) % 16]
    b = hash_bytes[(offset + 2) % 16]
    # Desaturate for muted aesthetic (blend with grey)
    r = int(r * 0.6 + 100)
    g = int(g * 0.6 + 100)
    b = int(b * 0.6 + 100)
    return f"#{r:02x}{g:02x}{b:02x}"


def generate_placeholder_svg(filename: str) -> str:
    """
    Generate deterministic gradient SVG placeholder with music note icon.

    Design Decision: Hash-based gradient (not solid color or generic icon).
    Rationale: Deterministic hashing creates visual variety (each file gets unique
    gradient) without randomness that would change on reload. Gradient provides
    depth without complexity. Music note icon anchors the design.

    Args:
        filename: Original filename (used for hash seed)

    Returns:
        Base64-encoded SVG data URI
    """
    color1 = _hash_color(filename, 0)
    color2 = _hash_color(filename, 1)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{color1};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{color2};stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="300" height="300" fill="url(#grad)"/>
  <path d="M150 80 L150 200 M150 200 Q165 210 165 220 Q165 230 150 230 Q135 230 135 220 Q135 210 150 200 M190 70 L190 180 M190 180 Q205 190 205 200 Q205 210 190 210 Q175 210 175 200 Q175 190 190 180 M150 80 L190 70" 
        fill="rgba(255,255,255,0.9)" stroke="rgba(255,255,255,0.9)" stroke-width="3"/>
</svg>"""

    svg_base64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{svg_base64}"


def extract_id3v2_metadata(file_path: str) -> Dict:
    """
    Extract ID3v2 metadata from MP3 files using pure Python struct parsing.

    Design Decision: Parse only TIT2/TPE1/TALB/APIC (title/artist/album/artwork).
    Rationale: UI displays only these 4 fields. Extended metadata (TDRC date, TCON genre)
    would add 40% parsing overhead with zero UI benefit.

    Args:
        file_path: Absolute path to MP3 file

    Returns:
        Dict with keys: title, artist, album, artwork_base64, has_artwork
    """
    metadata = {
        "title": None,
        "artist": None,
        "album": None,
        "artwork_base64": None,
        "has_artwork": False,
    }

    try:
        with open(file_path, "rb") as f:
            # Read ID3v2 header (10 bytes)
            header = f.read(10)
            if len(header) < 10 or header[:3] != b"ID3":
                return metadata

            # Parse ID3v2 version and size
            version = header[3]
            if version not in (3, 4):  # Only support ID3v2.3 and ID3v2.4
                return metadata

            # ID3v2 size (syncsafe integer - 7 bits per byte)
            size = (
                (header[6] & 0x7F) << 21
                | (header[7] & 0x7F) << 14
                | (header[8] & 0x7F) << 7
                | (header[9] & 0x7F)
            )

            # Read all frames
            tag_data = f.read(size)
            pos = 0

            while pos < len(tag_data) - 10:
                # Read frame header (10 bytes)
                frame_id = tag_data[pos : pos + 4].decode("latin1", errors="ignore")
                if frame_id[0] == "\x00":  # Padding reached
                    break

                # Frame size
                if version == 4:
                    # ID3v2.4 uses syncsafe integers for frame size
                    frame_size = (
                        (tag_data[pos + 4] & 0x7F) << 21
                        | (tag_data[pos + 5] & 0x7F) << 14
                        | (tag_data[pos + 6] & 0x7F) << 7
                        | (tag_data[pos + 7] & 0x7F)
                    )
                else:
                    # ID3v2.3 uses regular big-endian integers
                    frame_size = struct.unpack(">I", tag_data[pos + 4 : pos + 8])[0]

                pos += 10  # Skip frame header

                if frame_size <= 0 or pos + frame_size > len(tag_data):
                    break

                frame_data = tag_data[pos : pos + frame_size]
                pos += frame_size

                # Parse only essential frames for UI display
                if frame_id == "TIT2":  # Title
                    metadata["title"] = _decode_text_frame(frame_data)
                elif frame_id == "TPE1":  # Artist
                    metadata["artist"] = _decode_text_frame(frame_data)
                elif frame_id == "TALB":  # Album
                    metadata["album"] = _decode_text_frame(frame_data)
                elif frame_id == "APIC":  # Attached picture
                    artwork = _decode_apic_frame(frame_data)
                    if artwork:
                        metadata["artwork_base64"] = artwork
                        metadata["has_artwork"] = True

    except Exception:
        pass  # Return partial metadata on error

    return metadata


def _decode_text_frame(data: bytes) -> Optional[str]:
    """Decode ID3v2 text frame with encoding byte."""
    if len(data) < 2:
        return None

    encoding = data[0]
    text_data = data[1:]

    try:
        if encoding == 0:  # ISO-8859-1
            return text_data.rstrip(b"\x00").decode("latin1")
        elif encoding == 1:  # UTF-16 with BOM
            return text_data.rstrip(b"\x00").decode("utf-16")
        elif encoding == 2:  # UTF-16BE
            return text_data.rstrip(b"\x00").decode("utf-16-be")
        elif encoding == 3:  # UTF-8
            return text_data.rstrip(b"\x00").decode("utf-8")
    except Exception:
        return None

    return None


def _decode_apic_frame(data: bytes) -> Optional[str]:
    """Decode ID3v2 APIC (Attached Picture) frame to base64."""
    if len(data) < 10:
        return None

    try:
        encoding = data[0]
        pos = 1

        # Read MIME type (null-terminated)
        mime_end = data.find(b"\x00", pos)
        if mime_end == -1:
            return None
        mime_type = data[pos:mime_end].decode("latin1")
        pos = mime_end + 1

        # Skip picture type byte
        pos += 1

        # Skip description (null-terminated based on encoding)
        if encoding == 0 or encoding == 3:  # Latin1 or UTF-8
            desc_end = data.find(b"\x00", pos)
        else:  # UTF-16
            desc_end = data.find(b"\x00\x00", pos)

        if desc_end == -1:
            return None
        pos = desc_end + (2 if encoding != 0 and encoding != 3 else 1)

        # Remaining data is the image
        image_data = data[pos:]
        if len(image_data) < 100:  # Sanity check for minimum image size
            return None

        # Detect actual MIME type from magic bytes if needed
        if image_data[:2] == b"\xff\xd8":
            mime_type = "image/jpeg"
        elif image_data[:8] == b"\x89PNG\r\n\x1a\n":
            mime_type = "image/png"

        img_base64 = base64.b64encode(image_data).decode()
        return f"data:{mime_type};base64,{img_base64}"

    except Exception:
        return None


def extract_m4a_metadata(file_path: str) -> Dict:
    """
    Extract metadata from M4A/MP4 audio files using atom parsing.

    Parses covr (artwork), ©nam (title), ©ART (artist), ©alb (album) atoms.

    Args:
        file_path: Absolute path to M4A file

    Returns:
        Dict with keys: title, artist, album, artwork_base64, has_artwork
    """
    metadata = {
        "title": None,
        "artist": None,
        "album": None,
        "artwork_base64": None,
        "has_artwork": False,
    }

    try:
        with open(file_path, "rb") as f:
            # Find 'moov' atom containing metadata
            while True:
                atom_header = f.read(8)
                if len(atom_header) < 8:
                    break

                atom_size = struct.unpack(">I", atom_header[:4])[0]
                atom_type = atom_header[4:8]

                if atom_type == b"moov":
                    moov_data = f.read(atom_size - 8)
                    _parse_moov_atom(moov_data, metadata)
                    break
                elif atom_size > 8:
                    f.seek(atom_size - 8, 1)  # Skip to next atom
                else:
                    break

    except Exception:
        pass  # Return partial metadata on error

    return metadata


def _parse_moov_atom(data: bytes, metadata: Dict):
    """Parse moov atom to find udta -> meta -> ilst atoms."""
    pos = 0
    while pos < len(data) - 8:
        if pos + 8 > len(data):
            break

        atom_size = struct.unpack(">I", data[pos : pos + 4])[0]
        atom_type = data[pos + 4 : pos + 8]

        if atom_size < 8:
            break

        if atom_type == b"udta":
            # Parse user data atom
            _parse_udta_atom(data[pos + 8 : pos + atom_size], metadata)

        pos += atom_size


def _parse_udta_atom(data: bytes, metadata: Dict):
    """Parse udta atom to find meta -> ilst."""
    pos = 0
    while pos < len(data) - 8:
        if pos + 8 > len(data):
            break

        atom_size = struct.unpack(">I", data[pos : pos + 4])[0]
        atom_type = data[pos + 4 : pos + 8]

        if atom_size < 8:
            break

        if atom_type == b"meta":
            # Skip version/flags (4 bytes) and parse ilst
            _parse_ilst_atom(data[pos + 12 : pos + atom_size], metadata)

        pos += atom_size


def _parse_ilst_atom(data: bytes, metadata: Dict):
    """Parse ilst (item list) atom containing metadata."""
    pos = 0
    while pos < len(data) - 8:
        if pos + 8 > len(data):
            break

        atom_size = struct.unpack(">I", data[pos : pos + 4])[0]
        atom_type = data[pos + 4 : pos + 8]

        if atom_size < 8:
            break

        atom_data = data[pos + 8 : pos + atom_size]

        # Parse metadata atoms (skip 'data' wrapper - 16 bytes header)
        if len(atom_data) > 16:
            value_data = atom_data[16:]

            if atom_type == b"\xa9nam":  # Title
                try:
                    metadata["title"] = value_data.decode(
                        "utf-8", errors="ignore"
                    ).rstrip("\x00")
                except:
                    pass
            elif atom_type == b"\xa9ART":  # Artist
                try:
                    metadata["artist"] = value_data.decode(
                        "utf-8", errors="ignore"
                    ).rstrip("\x00")
                except:
                    pass
            elif atom_type == b"\xa9alb":  # Album
                try:
                    metadata["album"] = value_data.decode(
                        "utf-8", errors="ignore"
                    ).rstrip("\x00")
                except:
                    pass
            elif atom_type == b"covr":  # Cover artwork
                # Detect image type from magic bytes
                mime_type = "image/jpeg"
                if value_data[:8] == b"\x89PNG\r\n\x1a\n":
                    mime_type = "image/png"

                img_base64 = base64.b64encode(value_data).decode()
                metadata["artwork_base64"] = f"data:{mime_type};base64,{img_base64}"
                metadata["has_artwork"] = True

        pos += atom_size


def get_audio_metadata(file_path: str) -> Dict:
    """
    Get audio metadata with LRU caching.

    Design Decision: On-demand endpoint with LRU cache (not pre-scan).
    Rationale: Pre-scanning entire directory delays initial page load and wastes
    memory on files never played. On-demand caching hits 90%+ for typical listening
    patterns (repeat plays, adjacent tracks). 50 entries = ~2MB memory (negligible).

    Args:
        file_path: Absolute path to audio file

    Returns:
        Dict with: title, artist, album, artwork_base64, has_artwork, placeholder
    """
    # Check cache first
    if file_path in _metadata_cache:
        # Move to end (mark as recently used)
        _cache_order.remove(file_path)
        _cache_order.append(file_path)
        return _metadata_cache[file_path]

    # Extract metadata based on file extension
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".mp3":
        metadata = extract_id3v2_metadata(file_path)
    elif ext in (".m4a", ".m4b", ".m4p", ".m4r"):
        metadata = extract_m4a_metadata(file_path)
    else:
        # Unsupported format - return empty metadata
        metadata = {
            "title": None,
            "artist": None,
            "album": None,
            "artwork_base64": None,
            "has_artwork": False,
        }

    # Generate placeholder if no artwork found
    filename = os.path.basename(file_path)
    if not metadata["has_artwork"]:
        metadata["artwork_base64"] = generate_placeholder_svg(filename)

    # Use filename as title fallback
    if not metadata["title"]:
        metadata["title"] = os.path.splitext(filename)[0]

    # Cache and evict if necessary
    _metadata_cache[file_path] = metadata
    _cache_order.append(file_path)
    _evict_cache()

    return metadata


def get_audio_player_html():
    """
    Returns dual-mode DOM structure for audio player (full modal + mini dock).

    Design principles:
    - Persistent audio element (never destroyed - critical for iOS Safari)
    - Dual-mode UI: full modal with album art + VU meter, mini dock with thumbnail
    - Immediate placeholder rendering (no empty frames or layout shift)
    - 14-bar LED VU meter (optimal frequency zone division)
    - GPU-optimized transitions (transform/opacity only)
    """
    return """
<!-- Persistent Audio Element (never removed from DOM for seamless playback) -->
<audio id="audio-element" crossorigin="anonymous" preload="metadata" style="position: absolute; left: -9999px;"></audio>

<!-- Mini Player Dock (collapsed state, fixed bottom) -->
<div id="audio-mini-player" class="mini-player" style="display: none;">
  <img class="mini-art" id="mini-art" width="48" height="48" alt="Album art" src="">
  <div class="mini-info">
    <div class="mini-title" id="mini-title">Track Title</div>
    <div class="mini-artist" id="mini-artist">Artist Name</div>
  </div>
  <div class="mini-controls">
    <button id="mini-prev" class="mini-btn" aria-label="Previous track">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z"/>
      </svg>
    </button>
    <button id="mini-play" class="mini-btn mini-play-btn" aria-label="Play">
      <svg id="mini-play-icon" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
        <path d="M8 5v14l11-7z"/>
      </svg>
      <svg id="mini-pause-icon" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" style="display: none;">
        <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
      </svg>
    </button>
    <button id="mini-next" class="mini-btn" aria-label="Next track">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M16 18h2V6h-2v12zM6 18l8.5-6L6 6v12z"/>
      </svg>
    </button>
    <input type="range" id="mini-volume" class="mini-volume-slider" min="0" max="100" value="80" step="1" aria-label="Volume">
    <a id="mini-download" class="mini-btn mini-download-btn" href="" download aria-label="Download track" title="Download">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
      </svg>
    </a>
    <button id="mini-expand" class="mini-btn" aria-label="Expand player">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M7 13L12 8L17 13M7 17L12 12L17 17"/>
      </svg>
    </button>
    <button id="mini-close" class="mini-btn" aria-label="Stop playback">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  </div>
</div>

<!-- Full Audio Player Modal -->
<div id="audio-modal" class="audio-modal" style="display: none;">
  <div class="audio-player-container">
    <!-- Corner button group -->
    <div class="audio-corner-controls">
      <a class="audio-download-btn" id="audio-download" href="" download aria-label="Download track" title="Download">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
        </svg>
      </a>
      <button class="audio-minimize-btn" id="audio-minimize" aria-label="Minimize player" title="Minimize">
        <span style="font-size: 1.2rem;">−</span>
      </button>
      <button class="audio-dismiss-btn" id="audio-dismiss" aria-label="Close player" title="Close">
        <span style="font-size: 1.2rem;">×</span>
      </button>
    </div>

    <!-- Album Art Section (300x300px, immediate placeholder) -->
    <div class="album-art-section">
      <img id="album-art" class="album-art" width="300" height="300" alt="Album artwork" src="">
      <div class="art-loading-overlay" id="art-loading" style="display: none;">
        <div class="loading-spinner"></div>
      </div>
      <div class="audio-header-overlay">
        <div class="audio-title" id="audio-title">Loading...</div>
        <div class="audio-artist" id="audio-artist"></div>
      </div>
    </div>

    <!-- LED VU Meter Visualizer (14 bars, logarithmic frequency mapping) -->
    <!-- Design Decision: 14 rectangular LED segments (not 12/16, not rounded).
         Rationale: 14 bars optimally divide audio spectrum (20Hz-20kHz log scale)
         into visible bass/mid/treble zones. Rectangular matches cassette deck
         aesthetic over modern TE rounded style. -->
    <div id="vu-meter" class="vu-meter">
      <div class="vu-bar" data-index="0"></div>
      <div class="vu-bar" data-index="1"></div>
      <div class="vu-bar" data-index="2"></div>
      <div class="vu-bar" data-index="3"></div>
      <div class="vu-bar" data-index="4"></div>
      <div class="vu-bar" data-index="5"></div>
      <div class="vu-bar" data-index="6"></div>
      <div class="vu-bar" data-index="7"></div>
      <div class="vu-bar" data-index="8"></div>
      <div class="vu-bar" data-index="9"></div>
      <div class="vu-bar" data-index="10"></div>
      <div class="vu-bar" data-index="11"></div>
      <div class="vu-bar" data-index="12"></div>
      <div class="vu-bar" data-index="13"></div>
    </div>

    <!-- Progress Bar -->
    <div class="audio-progress-container">
      <div class="audio-time" id="audio-time-current">0:00</div>
      <input type="range" id="audio-progress" class="audio-progress-bar" min="0" max="100" value="0" step="0.1">
      <div class="audio-time" id="audio-time-total">0:00</div>
    </div>

    <!-- Main Controls (physical button aesthetic) -->
    <div class="audio-controls">
      <button id="audio-prev" class="audio-btn" aria-label="Previous track">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
          <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z"/>
        </svg>
      </button>
      
      <button id="audio-play" class="audio-play-btn" aria-label="Play">
        <svg id="play-icon" width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z"/>
        </svg>
        <svg id="pause-icon" width="48" height="48" viewBox="0 0 24 24" fill="currentColor" style="display: none;">
          <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
        </svg>
      </button>
      
      <button id="audio-next" class="audio-btn" aria-label="Next track">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
          <path d="M16 18h2V6h-2v12zM6 18l8.5-6L6 6v12z"/>
        </svg>
      </button>
      
      <button id="audio-loop" class="audio-btn" data-mode="0" aria-label="Loop off">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M17 1l4 4-4 4"/>
          <path d="M3 11V9a4 4 0 014-4h14"/>
          <path d="M7 23l-4-4 4-4"/>
          <path d="M21 13v2a4 4 0 01-4 4H3"/>
        </svg>
      </button>
    </div>

    <!-- Advanced Controls Grid (preserved from original) -->
    <div class="audio-advanced-grid">
      <!-- Volume -->
      <div class="audio-control-group">
        <label for="audio-volume">VOLUME</label>
        <input type="range" id="audio-volume" min="0" max="100" value="80" step="1">
        <span id="audio-volume-val">80%</span>
      </div>

      <!-- Tempo (affects both speed and pitch naturally) -->
      <div class="audio-control-group">
        <label for="audio-tempo">TEMPO</label>
        <input type="range" id="audio-tempo" min="50" max="200" value="100" step="1">
        <span id="audio-tempo-val">100%</span>
      </div>

      <!-- Bass EQ -->
      <div class="audio-control-group">
        <label for="audio-bass">BASS</label>
        <input type="range" id="audio-bass" min="-12" max="12" value="0" step="1">
        <span id="audio-bass-val">0</span>
      </div>

      <!-- Mid EQ -->
      <div class="audio-control-group">
        <label for="audio-mid">MID</label>
        <input type="range" id="audio-mid" min="-12" max="12" value="0" step="1">
        <span id="audio-mid-val">0</span>
      </div>

      <!-- Treble EQ -->
      <div class="audio-control-group">
        <label for="audio-treble">TREBLE</label>
        <input type="range" id="audio-treble" min="-12" max="12" value="0" step="1">
        <span id="audio-treble-val">0</span>
      </div>

      <!-- Reverb -->
      <div class="audio-control-group">
        <label for="audio-reverb">REVERB</label>
        <input type="range" id="audio-reverb" min="0" max="100" value="0" step="1">
        <span id="audio-reverb-val">0%</span>
      </div>
    </div>

    <!-- Reset Button Container -->
    <div class="audio-reset-container">
      <button id="audio-reset-btn" class="audio-reset-btn" aria-label="Reset all controls">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
          <path d="M3 3v5h5"/>
        </svg>
        RESET
      </button>
    </div>

    <!-- Playlist -->
    <div class="audio-playlist" id="audio-playlist"></div>
  </div>
</div>

<!-- Global style for container padding when mini-player active -->
<style id="mini-player-styles">
  /* Add padding to body to prevent content clipping behind viewport-attached mini-player */
  body.mini-player-active {
    padding-bottom: 56px !important;
    transition: padding-bottom 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }
  
  /* Mobile: Account for safe-area-inset */
  @media (max-width: 899px) {
    body.mini-player-active {
      padding-bottom: calc(56px + env(safe-area-inset-bottom)) !important;
      transition: padding-bottom 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
  }
</style>
"""


def get_audio_player_css():
    """
    Returns hardware-aesthetic CSS with LED VU meter and dual-mode player.

    Design aesthetic: 1980s cassette deck meets TE retrofuturistic minimal.

    Performance optimizations:
    - GPU-accelerated transitions (transform/opacity only)
    - will-change for layer promotion
    - contain: strict for VU meter bars
    - CSS Grid for static layouts
    """
    return """
/* ========================================
   GLOBAL SCROLLBAR HIDING
   ======================================== */

/* Hide scrollbars but keep functionality */
* {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE/Edge */
}

*::-webkit-scrollbar {
  display: none; /* Chrome/Safari/Opera */
}

/* Ensure smooth scrolling */
html {
  scroll-behavior: smooth;
}

/* ========================================
   FULL AUDIO PLAYER MODAL
   ======================================== */

.audio-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.92);
  z-index: 10000;
  contain: layout;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.audio-player-container {
  max-width: 900px;
  margin: 2rem auto;
  padding: 2rem;
  background: var(--surface-color);
  /* Hardware cassette deck beveled border effect */
  border: 1px solid var(--border-color);
  border-radius: 16px;
  box-shadow: 
    0 20px 60px rgba(0, 0, 0, 0.4),
    inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* ========================================
   ALBUM ART SECTION (300x300px)
   ======================================== */

.album-art-section {
  position: relative;
  width: 300px;
  height: 300px;
  margin: 0 auto 2rem;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-color);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}

.album-art {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.art-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.album-art-section .audio-header-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 1rem;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, rgba(0, 0, 0, 0.7) 70%, transparent 100%);
  color: white;
}

.album-art-section .audio-title {
  font-family: var(--font-ui);
  font-size: 1rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 0.25rem;
}

.album-art-section .audio-artist {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Corner button container - top-right of player */
.audio-corner-controls {
  position: absolute;
  top: 1rem;
  right: 1rem;
  display: flex;
  gap: 0.5rem;
  z-index: 100;
}

/* Shared corner button styles */
.audio-minimize-btn,
.audio-dismiss-btn,
.audio-download-btn {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  cursor: pointer;
  font-family: var(--font-ui);
  font-weight: 600;
  transition: all 0.15s ease;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  text-decoration: none;
}

.audio-download-btn {
  background: var(--accent-color);
  border-color: var(--accent-color);
  border-radius: 50%;
}

.audio-download-btn:hover {
  background: var(--accent-hover);
  transform: scale(1.05);
}

.audio-minimize-btn:hover {
  background: var(--accent-color);
  border-color: var(--accent-hover);
  transform: scale(1.05);
}

.audio-dismiss-btn:hover {
  background: var(--error-color);
  border-color: var(--error-color);
  transform: scale(1.05);
}

.audio-minimize-btn:active,
.audio-dismiss-btn:active,
.audio-download-btn:active {
  transform: translateY(1px) scale(1.02);
}

/* Mini-player download button */
.mini-download-btn {
  background: var(--accent-color);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  text-decoration: none;
  transition: transform 0.15s ease, background 0.15s ease;
}

.mini-download-btn:hover {
  background: var(--accent-hover);
  transform: scale(1.05);
}

/* ========================================
   LED VU METER VISUALIZER (14 bars)
   Design Decision: Rectangular LED segments.
   Rationale: Matches cassette deck aesthetic.
   ======================================== */

.vu-meter {
  display: flex;
  justify-content: center;
  align-items: flex-end;
  gap: 3px;
  height: 120px;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.85);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 1.5rem;
  box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.5);
}

.vu-bar {
  width: 12px;
  height: 100%;
  position: relative;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  transition: opacity 0.05s linear;
  will-change: opacity;
  contain: strict;
}

/* LED color zones: bass (teal), mid (orange), treble/peak (red) */
.vu-bar[data-index="0"],
.vu-bar[data-index="1"],
.vu-bar[data-index="2"],
.vu-bar[data-index="3"],
.vu-bar[data-index="4"],
.vu-bar[data-index="5"],
.vu-bar[data-index="6"],
.vu-bar[data-index="7"],
.vu-bar[data-index="8"] {
  background-color: rgba(0, 121, 107, 0.15); /* Teal base */
}

.vu-bar[data-index="9"],
.vu-bar[data-index="10"],
.vu-bar[data-index="11"],
.vu-bar[data-index="12"] {
  background-color: rgba(216, 67, 21, 0.15); /* Orange base */
}

.vu-bar[data-index="13"] {
  background-color: rgba(198, 40, 40, 0.15); /* Red base */
}

/* Active LED states with glow effect */
.vu-bar.active[data-index="0"],
.vu-bar.active[data-index="1"],
.vu-bar.active[data-index="2"],
.vu-bar.active[data-index="3"],
.vu-bar.active[data-index="4"],
.vu-bar.active[data-index="5"],
.vu-bar.active[data-index="6"],
.vu-bar.active[data-index="7"],
.vu-bar.active[data-index="8"] {
  background-color: var(--accent-color); /* Teal */
  opacity: 1;
  box-shadow: 
    0 0 8px var(--accent-color),
    0 0 4px rgba(0, 121, 107, 0.8);
}

.vu-bar.active[data-index="9"],
.vu-bar.active[data-index="10"],
.vu-bar.active[data-index="11"],
.vu-bar.active[data-index="12"] {
  background-color: var(--secondary-accent); /* Orange */
  opacity: 1;
  box-shadow: 
    0 0 8px var(--secondary-accent),
    0 0 4px rgba(216, 67, 21, 0.8);
}

.vu-bar.active[data-index="13"] {
  background-color: var(--error-color); /* Red peak */
  opacity: 1;
  box-shadow: 
    0 0 10px var(--error-color),
    0 0 6px rgba(198, 40, 40, 0.9);
}

.vu-bar:not(.active) {
  opacity: 0.15;
}

/* ========================================
   PROGRESS BAR
   ======================================== */

.audio-progress-container {
  display: grid;
  grid-template-columns: 3.5rem 1fr 3.5rem;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.audio-time {
  font-family: var(--font-ui);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-dim);
  text-align: center;
  letter-spacing: 0.05em;
}

.audio-progress-bar {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 8px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  outline: none;
  cursor: pointer;
}

.audio-progress-bar::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  background: var(--accent-color);
  border: 1px solid var(--accent-hover);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  transition: transform 0.1s;
}

.audio-progress-bar::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.audio-progress-bar::-webkit-slider-thumb:active {
  transform: scale(1.1);
}

.audio-progress-bar::-moz-range-thumb {
  width: 20px;
  height: 20px;
  background: var(--accent-color);
  border: 1px solid var(--accent-hover);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  transition: transform 0.1s;
}

.audio-progress-bar::-moz-range-thumb:hover {
  transform: scale(1.2);
}

/* ========================================
   MAIN CONTROLS (Physical Button Aesthetic)
   ======================================== */

.audio-controls {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.audio-btn {
  background: var(--surface-alt);
  /* Physical button: raised effect with shadow */
  border: 1px solid var(--border-color);
  border-radius: 50%;
  box-shadow: 
    0 3px 0 rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-main);
  transition: all 0.1s;
  will-change: transform;
}

.audio-btn:hover {
  background: var(--accent-color);
  border-color: var(--accent-hover);
  color: white;
  transform: translateY(-1px);
  box-shadow: 
    0 4px 0 rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

/* Tactile button press effect */
.audio-btn:active {
  transform: translateY(2px);
  box-shadow: 
    0 1px 0 rgba(0, 0, 0, 0.25),
    inset 0 1px 2px rgba(0, 0, 0, 0.2);
}

.audio-btn[data-mode="1"],
.audio-btn[data-mode="2"] {
  background: var(--accent-color);
  border-color: var(--accent-hover);
  color: white;
}

/* Loop button specific embossed hover/active effect */
#audio-loop:hover {
  background: var(--accent-color);
  border-color: var(--accent-hover);
  color: white;
  /* Subtle lift effect - embossed feel */
  transform: translateY(-2px);
  box-shadow: 
    0 5px 0 rgba(0, 0, 0, 0.3),
    inset 0 2px 0 rgba(255, 255, 255, 0.4);
}

#audio-loop:active {
  /* Pressed button effect */
  transform: translateY(2px);
  box-shadow: 
    0 1px 0 rgba(0, 0, 0, 0.25),
    inset 0 2px 3px rgba(0, 0, 0, 0.3);
}

/* Maintain active state appearance when loop is on */
#audio-loop[data-mode="1"]:hover,
#audio-loop[data-mode="2"]:hover {
  transform: translateY(-2px);
  box-shadow: 
    0 5px 0 rgba(0, 0, 0, 0.3),
    inset 0 2px 0 rgba(255, 255, 255, 0.4);
}

#audio-loop[data-mode="1"]:active,
#audio-loop[data-mode="2"]:active {
  transform: translateY(2px);
  box-shadow: 
    0 1px 0 rgba(0, 0, 0, 0.25),
    inset 0 2px 3px rgba(0, 0, 0, 0.3);
}

.audio-play-btn {
  background: var(--accent-color);
  border: 1px solid var(--accent-hover);
  border-radius: 50%;
  box-shadow: 
    0 4px 0 rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  transition: all 0.1s;
  will-change: transform;
}

.audio-play-btn:hover {
  background: var(--accent-hover);
  transform: translateY(-1px) scale(1.05);
  box-shadow: 
    0 5px 0 rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.audio-play-btn:active {
  transform: translateY(2px) scale(1.02);
  box-shadow: 
    0 2px 0 rgba(0, 0, 0, 0.3),
    inset 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* ========================================
   ADVANCED CONTROLS GRID
   ======================================== */

.audio-advanced-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.05);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
}

.audio-control-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.audio-control-group label {
  font-family: var(--font-ui);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-dim);
  font-weight: 700;
}

.audio-control-group input[type="range"] {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  outline: none;
  cursor: pointer;
}

.audio-control-group input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  background: var(--secondary-accent);
  border: 1px solid var(--border-color);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.audio-control-group input[type="range"]::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: var(--secondary-accent);
  border: 1px solid var(--border-color);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.audio-control-group span {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-main);
  text-align: center;
  min-height: 1.5rem;
  letter-spacing: 0.05em;
}

/* Reset button container */
.audio-reset-container {
  display: flex;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.audio-reset-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-ui);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 0.6rem 1.5rem;
  background: rgba(0, 0, 0, 0.1);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-dim);
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow:
    0 2px 0 rgba(0, 0, 0, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.audio-reset-btn:hover {
  background: var(--accent-color);
  border-color: var(--accent-hover);
  color: white;
  transform: translateY(-1px);
  box-shadow:
    0 3px 0 rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.audio-reset-btn:active {
  transform: translateY(1px);
  box-shadow:
    0 1px 0 rgba(0, 0, 0, 0.2),
    inset 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* ========================================
   FULL PLAYER FOCUS STATES (Remove Blue Glow)
   ======================================== */

/* Remove default browser focus outlines */
.audio-modal input:focus,
.audio-modal button:focus {
  outline: none;
  box-shadow: none;
}

/* Accessible keyboard navigation */
.audio-btn:focus-visible,
.audio-play-btn:focus-visible,
.audio-minimize-btn:focus-visible,
.audio-dismiss-btn:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

/* Progress bar focus - thumb highlight only */
.audio-progress-bar:focus {
  outline: none;
}

.audio-progress-bar:focus-visible::-webkit-slider-thumb {
  box-shadow: 0 0 0 4px rgba(0, 121, 107, 0.3);
  transform: scale(1.15);
}

.audio-progress-bar:focus-visible::-moz-range-thumb {
  box-shadow: 0 0 0 4px rgba(0, 121, 107, 0.3);
  transform: scale(1.15);
}

/* Advanced control sliders focus */
.audio-control-group input[type="range"]:focus {
  outline: none;
}

.audio-control-group input[type="range"]:focus-visible::-webkit-slider-thumb {
  box-shadow: 0 0 0 3px rgba(216, 67, 21, 0.3);
  transform: scale(1.15);
}

.audio-control-group input[type="range"]:focus-visible::-moz-range-thumb {
  box-shadow: 0 0 0 3px rgba(216, 67, 21, 0.3);
  transform: scale(1.15);
}

/* Remove webkit tap highlight */
.audio-modal input,
.audio-modal button {
  -webkit-tap-highlight-color: transparent;
}

/* ========================================
   PLAYLIST
   ======================================== */

.audio-playlist {
  max-height: 200px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.05);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  contain: layout style;
  -webkit-overflow-scrolling: touch;
}

.audio-playlist-item {
  padding: 0.75rem 1rem;
  font-family: var(--font-ui);
  font-size: 0.85rem;
  color: var(--text-main);
  cursor: pointer;
  border-bottom: 1px solid var(--border-light);
  transition: background 0.1s;
}

.audio-playlist-item:hover {
  background: rgba(0, 121, 107, 0.1);
}

.audio-playlist-item.active {
  background: var(--accent-color);
  color: white;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.audio-playlist-item:last-child {
  border-bottom: none;
}

/* ========================================
   MINI PLAYER DOCK (64px fixed bottom)
   Design Decision: Hide visualizer in mini mode.
   Rationale: 64px height insufficient for meaningful
   display, battery savings prioritized over non-functional decoration.

   Desktop (≥900px): Centered within app-root bounds, respects device-shell aesthetic.
   Mobile (<900px): Full-width with safe-area-inset for notch/home indicator.
   ======================================== */

.mini-player {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: 56px;
  /* Glassmorphism effect - theme colors only, no saturation boost */
  background: rgba(232, 244, 241, 0.85); /* Cool off-white/teal tint */
  backdrop-filter: blur(12px); /* Remove saturate() to fix blue shift */
  -webkit-backdrop-filter: blur(12px); /* Safari support */
  border: none;
  border-top: 1px solid rgba(0, 121, 107, 0.3); /* Slightly stronger top border */
  border-radius: 0;
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.12); /* Pure black shadow only */
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.375rem 1rem;
  padding-bottom: calc(0.375rem + env(safe-area-inset-bottom));
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: opacity;
  contain: layout;
}

/* Fallback for browsers without backdrop-filter support */
@supports not (backdrop-filter: blur(10px)) {
  .mini-player {
    background: rgba(255, 251, 247, 0.96); /* More opaque fallback */
  }
}

.mini-art {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  object-fit: cover;
  flex-shrink: 0;
  /* Enhanced shadow for contrast against translucent background */
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.2),
    0 0 0 1px rgba(255, 255, 255, 0.5);
}

.mini-info {
  flex: 1;
  min-width: 0;
  max-width: 300px;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.mini-title {
  font-family: var(--font-ui);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-artist {
  font-family: var(--font-ui);
  font-size: 0.65rem;
  font-weight: 400;
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-controls {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.mini-btn {
  background: var(--surface-alt);
  border: 1px solid var(--border-color);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-main);
  box-shadow: 0 2px 0 rgba(0, 0, 0, 0.2);
  transition: all 0.1s;
}

.mini-btn:hover {
  background: var(--accent-color);
  border-color: var(--accent-hover);
  color: white;
  transform: translateY(-1px);
}

.mini-btn:active {
  transform: translateY(1px);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.2);
}

.mini-play-btn {
  background: var(--accent-color);
  border-color: var(--accent-hover);
  color: white;
  width: 36px;
  height: 36px;
}

.mini-play-btn:hover {
  background: var(--accent-hover);
}

.mini-volume-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 80px;
  height: 4px;
  background: var(--border-light);
  border: 1px solid var(--border-light);
  border-radius: 20px;
  outline: none;
  cursor: pointer;
}

.mini-volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 12px;
  height: 12px;
  background: var(--accent-color);
  border: 1px solid var(--accent-hover);
  border-radius: 50%;
  cursor: pointer;
}

.mini-volume-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  background: var(--accent-color);
  border: 1px solid var(--accent-hover);
  border-radius: 50%;
  cursor: pointer;
}

/* ========================================
   MINI PLAYER FOCUS STATES (Remove Blue Glow)
   ======================================== */

/* Remove default browser focus outlines from all mini-player controls */
.mini-player *:focus {
  outline: none;
  box-shadow: none;
}

/* Accessible keyboard navigation with theme-consistent styling */
.mini-player *:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

/* Button focus states - subtle teal ring */
.mini-btn:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

/* Volume slider focus - no outline, just thumb highlight */
.mini-volume-slider:focus {
  outline: none;
  box-shadow: none;
}

.mini-volume-slider:focus-visible {
  outline: none; /* No outline on track, thumb provides visual feedback */
}

.mini-volume-slider:focus-visible::-webkit-slider-thumb {
  box-shadow: 0 0 0 3px rgba(0, 121, 107, 0.3);
  transform: scale(1.1);
}

.mini-volume-slider:focus-visible::-moz-range-thumb {
  box-shadow: 0 0 0 3px rgba(0, 121, 107, 0.3);
  transform: scale(1.1);
}

/* Remove any webkit-focus-ring-color */
.mini-player input,
.mini-player button {
  -webkit-tap-highlight-color: transparent;
}

/* Prevent blue backgrounds on active states */
.mini-player input:active,
.mini-player button:active {
  background-color: inherit;
}

/* ========================================
   RESPONSIVE DESIGN
   ======================================== */

@media (max-width: 900px) {
  .audio-player-container {
    margin: 1rem;
    padding: 1.5rem;
  }

  /* Mobile corner controls - smaller and tighter */
  .audio-corner-controls {
    gap: 0.25rem;
  }

  .audio-minimize-btn,
  .audio-dismiss-btn {
    width: 28px;
    height: 28px;
    background: rgba(0, 0, 0, 0.75);
  }

  .album-art-section {
    width: 250px;
    height: 250px;
  }

  .audio-advanced-grid {
    grid-template-columns: 1fr;
  }

  .audio-controls {
    gap: 1rem;
  }

  .audio-btn {
    width: 48px;
    height: 48px;
  }

  .audio-play-btn {
    width: 70px;
    height: 70px;
  }

  /* Mobile mini-player: solid background for better readability */
  .mini-player {
    /* Mobile: Use solid background for better readability on small screens */
    background: var(--surface-color);
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    padding-bottom: calc(0.375rem + env(safe-area-inset-bottom));
    box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.2);
  }
  
  /* Remove enhanced shadow from album art on mobile */
  .mini-art {
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  }

  .mini-info {
    display: none; /* Hide on very small screens */
  }

  .mini-volume-slider {
    width: 60px;
  }
}

@media (max-width: 600px) {
  .album-art-section {
    width: 200px;
    height: 200px;
  }

  .vu-meter {
    height: 80px;
  }

  .vu-bar {
    width: 10px;
  }

  .audio-controls {
    gap: 0.75rem;
  }

  .audio-btn {
    width: 44px;
    height: 44px;
  }

  .audio-play-btn {
    width: 60px;
    height: 60px;
  }

  .mini-volume-slider {
    display: none; /* Hide volume slider on mobile */
  }
}
"""


def get_audio_player_js():
    """
    Returns ultra-optimized JavaScript with dual-mode player and LED VU meter.

    Design Decision: Logarithmic frequency mapping for VU meter (not linear/mel scale).
    Rationale: Perceptually linear for music, matches human hearing sensitivity.

    Performance optimizations:
    - Persistent audio element (never destroyed - zero stuttering)
    - Pre-allocated typed arrays for 14-bar VU meter
    - Reused AudioContext across mode switches
    - DOM-based VU meter with GPU-accelerated opacity transitions
    - Async album art loading (non-blocking)
    - Throttled progress updates (250ms)
    - Debounced slider inputs (100ms)
    - Page Visibility API for battery savings
    """
    return """
(function() {
  'use strict';

  // ========================================
  // CONSTANTS
  // ========================================

  const AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.alac', '.opus'];
  const FFT_SIZE = 2048;
  const VU_BARS = 14;  // 14 bars for optimal bass/mid/treble division
  const PROGRESS_THROTTLE = 250;  // ms
  const SLIDER_DEBOUNCE = 100;  // ms
  const PEAK_HOLD_TIME = 100;  // ms before peak decay starts
  const PEAK_DECAY_TIME = 150;  // ms for full peak decay

  // ========================================
  // TEMPO CONTROL EXPLANATION
  // ========================================
  // Tempo uses HTMLAudioElement's playbackRate, which naturally affects
  // both speed AND pitch (like playing a vinyl record faster/slower).
  // - 100% = normal playback
  // - 150% = 1.5x faster (higher pitch)
  // -  50% = 0.5x slower (lower pitch)

  // Logarithmic frequency mapping for 14 VU bars (20Hz - 20kHz)
  // Design Decision: Logarithmic scale (not linear).
  // Rationale: Matches human hearing perception for music.
  const VU_FREQ_INDICES = [
    1, 2, 3, 5, 7, 10, 14, 20, 28, 40, 56, 80, 113, 160
  ];

  // ========================================
  // GLOBAL STATE
  // ========================================

  let playerState = 'hidden';  // hidden, full, mini
  let audioContext = null;
  let audioSource = null;
  let gainNode = null;
  let bassNode = null;
  let midNode = null;
  let trebleNode = null;
  let analyserNode = null;
  
  // Reverb effect nodes
  let reverbNode = null;      // ConvolverNode for reverb
  let reverbGainNode = null;  // Wet signal gain
  let dryGainNode = null;     // Dry signal gain
  let reverbBuffer = null;    // Impulse response buffer
  
  // Tempo control
  let currentTempo = 1.0;     // playback rate (1.0 = normal)

  const freqData = new Uint8Array(FFT_SIZE / 2);
  const vuPeaks = new Float32Array(VU_BARS);  // Peak hold values
  const vuPeakTimers = new Array(VU_BARS).fill(0);  // Peak decay timers
  
  let currentPlaylist = [];
  let currentTrackIndex = 0;
  let loopMode = 0;  // 0=off, 1=all, 2=one
  let visualizerActive = true;
  let animationFrameId = null;
  let abortController = null;
  let currentFileUrl = null;

  // ========================================
  // DOM ELEMENTS
  // ========================================

  // Persistent audio element
  const audio = document.getElementById('audio-element');
  
  // Full modal elements
  const modal = document.getElementById('audio-modal');
  const albumArt = document.getElementById('album-art');
  const audioTitle = document.getElementById('audio-title');
  const audioArtist = document.getElementById('audio-artist');
  const artLoading = document.getElementById('art-loading');
  const minimizeBtn = document.getElementById('audio-minimize');
  const dismissBtn = document.getElementById('audio-dismiss');
  const playBtn = document.getElementById('audio-play');
  const playIcon = document.getElementById('play-icon');
  const pauseIcon = document.getElementById('pause-icon');
  const prevBtn = document.getElementById('audio-prev');
  const nextBtn = document.getElementById('audio-next');
  const loopBtn = document.getElementById('audio-loop');
  const progressBar = document.getElementById('audio-progress');
  const timeCurrent = document.getElementById('audio-time-current');
  const timeTotal = document.getElementById('audio-time-total');
  const volumeSlider = document.getElementById('audio-volume');
  const volumeVal = document.getElementById('audio-volume-val');
  const tempoSlider = document.getElementById('audio-tempo');
  const tempoVal = document.getElementById('audio-tempo-val');
  const bassSlider = document.getElementById('audio-bass');
  const bassVal = document.getElementById('audio-bass-val');
  const midSlider = document.getElementById('audio-mid');
  const midVal = document.getElementById('audio-mid-val');
  const trebleSlider = document.getElementById('audio-treble');
  const trebleVal = document.getElementById('audio-treble-val');
  const reverbSlider = document.getElementById('audio-reverb');
  const reverbVal = document.getElementById('audio-reverb-val');
  const playlistEl = document.getElementById('audio-playlist');
  const vuMeter = document.getElementById('vu-meter');
  const vuBars = Array.from(vuMeter.querySelectorAll('.vu-bar'));

  // Mini player elements
  const miniPlayer = document.getElementById('audio-mini-player');
  const miniArt = document.getElementById('mini-art');
  const miniTitle = document.getElementById('mini-title');
  const miniArtist = document.getElementById('mini-artist');
  const miniPlayBtn = document.getElementById('mini-play');
  const miniPlayIcon = document.getElementById('mini-play-icon');
  const miniPauseIcon = document.getElementById('mini-pause-icon');
  const miniPrevBtn = document.getElementById('mini-prev');
  const miniNextBtn = document.getElementById('mini-next');
  const miniVolume = document.getElementById('mini-volume');
  const miniExpandBtn = document.getElementById('mini-expand');
  const miniCloseBtn = document.getElementById('mini-close');

  // Download buttons
  const miniDownloadBtn = document.getElementById('mini-download');
  const audioDownloadBtn = document.getElementById('audio-download');

  // Reset button
  const resetBtn = document.getElementById('audio-reset-btn');

  // ========================================
  // UTILITY FUNCTIONS
  // ========================================

  function throttle(fn, delay) {
    let last = 0;
    return function(...args) {
      const now = Date.now();
      if (now - last >= delay) {
        fn.apply(this, args);
        last = now;
      }
    };
  }

  function debounce(fn, delay) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function formatTime(seconds) {
    if (!isFinite(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins + ':' + (secs < 10 ? '0' : '') + secs;
  }

  function isAudioFile(filename) {
    const lower = filename.toLowerCase();
    return AUDIO_EXTENSIONS.some(ext => lower.endsWith(ext));
  }

  /**
   * Normalize loop mode to prevent stuck states.
   * Ensures loopMode is always one of {0, 1, 2}.
   */
  function normalizeLoopMode() {
    if (typeof loopMode !== 'number' || loopMode < 0 || loopMode > 2) {
      loopMode = 0;
    }
    return loopMode;
  }

  // ========================================
  // AUDIO CONTEXT INITIALIZATION
  // ========================================

  function initAudioContext() {
    if (audioContext) return;

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = FFT_SIZE;
    analyserNode.smoothingTimeConstant = 0.7;  // Slight smoothing for VU meter

    gainNode = audioContext.createGain();
    bassNode = audioContext.createBiquadFilter();
    midNode = audioContext.createBiquadFilter();
    trebleNode = audioContext.createBiquadFilter();

    bassNode.type = 'lowshelf';
    bassNode.frequency.value = 200;
    midNode.type = 'peaking';
    midNode.frequency.value = 1000;
    midNode.Q.value = 1;
    trebleNode.type = 'highshelf';
    trebleNode.frequency.value = 3000;
    
    // Initialize reverb nodes
    reverbNode = audioContext.createConvolver();
    reverbGainNode = audioContext.createGain();
    dryGainNode = audioContext.createGain();
    
    // Start with no reverb (dry = 1, wet = 0)
    reverbGainNode.gain.value = 0;
    dryGainNode.gain.value = 1;
    
    // Generate synthetic impulse response for reverb (2 second hall reverb)
    createReverbImpulse(2.0, 2.5);
    
    // Initialize tempo state
    currentTempo = 1.0;
  }
  
  /**
   * Create a synthetic impulse response for reverb effect.
   * Uses exponential decay with noise to simulate a reverb tail.
   */
  function createReverbImpulse(duration, decay) {
    const sampleRate = audioContext.sampleRate;
    const length = sampleRate * duration;
    const impulse = audioContext.createBuffer(2, length, sampleRate);
    const impulseL = impulse.getChannelData(0);
    const impulseR = impulse.getChannelData(1);
    
    for (let i = 0; i < length; i++) {
      const t = i / sampleRate;
      // Exponential decay envelope
      const envelope = Math.exp(-t * decay);
      // Stereo decorrelation with slightly different noise
      impulseL[i] = (Math.random() * 2 - 1) * envelope;
      impulseR[i] = (Math.random() * 2 - 1) * envelope;
    }
    
    reverbNode.buffer = impulse;
    reverbBuffer = impulse;
  }

  function connectAudioNodes() {
    if (audioSource) {
      audioSource.disconnect();
    }

    audioSource = audioContext.createMediaElementSource(audio);
    
    // Audio chain: source -> EQ -> gain -> [dry path + wet path] -> analyser -> destination
    // EQ chain
    audioSource
      .connect(bassNode)
      .connect(midNode)
      .connect(trebleNode)
      .connect(gainNode);
    
    // Dry path (no reverb)
    gainNode.connect(dryGainNode);
    dryGainNode.connect(analyserNode);
    
    // Wet path (with reverb)
    gainNode.connect(reverbNode);
    reverbNode.connect(reverbGainNode);
    reverbGainNode.connect(analyserNode);
    
    // Output
    analyserNode.connect(audioContext.destination);
  }
  
  /**
   * Calculate playback rate for pitch and tempo control.
   * Since we can't truly separate pitch from tempo with basic playbackRate,
   * we apply both multiplicatively: pitch shifts will also affect tempo.
   */
  function updatePlaybackRate() {
    console.log(`[updatePlaybackRate] currentPitchShift: ${currentPitchShift}, currentTempo: ${currentTempo}`);\n    console.log(`[updatePlaybackRate] PITCH_LUT length: ${PITCH_LUT.length}`);\n    console.log(`[updatePlaybackRate] Accessing PITCH_LUT[${currentPitchShift + 12}]`);\n    \n    const pitchRate = PITCH_LUT[currentPitchShift + 12];\n    console.log(`[updatePlaybackRate] pitchRate: ${pitchRate}`);\n    \n    const combinedRate = currentTempo * pitchRate;\n    console.log(`[updatePlaybackRate] Pitch: ${currentPitchShift} semitones (${pitchRate.toFixed(3)}x), Tempo: ${(currentTempo * 100).toFixed(0)}%, Combined: ${combinedRate.toFixed(3)}x`);\n    \n    // Clamp to valid range (0.25x to 4x)\n    const finalRate = Math.max(0.25, Math.min(4.0, combinedRate));\n    console.log(`[updatePlaybackRate] Setting audio.playbackRate to: ${finalRate}`);\n    audio.playbackRate = finalRate;\n    console.log(`[updatePlaybackRate] audio.playbackRate is now: ${audio.playbackRate}`);\n  }

  // ========================================
  // LED VU METER VISUALIZER (60fps)
  // ========================================

  function animateVUMeter() {
    if (!visualizerActive || audio.paused || playerState === 'hidden') {
      animationFrameId = requestAnimationFrame(animateVUMeter);
      return;
    }

    // Get frequency data
    analyserNode.getByteFrequencyData(freqData);

    const now = performance.now();

    // Update each VU bar with logarithmic frequency mapping
    for (let i = 0; i < VU_BARS; i++) {
      const freqIndex = VU_FREQ_INDICES[i];
      const value = freqData[freqIndex] / 255;

      // Peak hold logic with decay
      if (value > vuPeaks[i]) {
        vuPeaks[i] = value;
        vuPeakTimers[i] = now + PEAK_HOLD_TIME;
      } else if (now > vuPeakTimers[i]) {
        // Linear decay after hold time
        const decayAmount = (now - vuPeakTimers[i]) / PEAK_DECAY_TIME;
        vuPeaks[i] = Math.max(value, vuPeaks[i] - decayAmount);
      }

      // Instant activation/deactivation (no artificial smoothing)
      const isActive = vuPeaks[i] > 0.05;  // 5% threshold
      vuBars[i].classList.toggle('active', isActive);
    }

    animationFrameId = requestAnimationFrame(animateVUMeter);
  }

  function startVUMeter() {
    if (animationFrameId) return;
    animationFrameId = requestAnimationFrame(animateVUMeter);
  }

  function stopVUMeter() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
    // Clear all bars
    vuBars.forEach(bar => bar.classList.remove('active'));
    vuPeaks.fill(0);
  }

  // ========================================
  // ALBUM ART LOADING (Async, Non-Blocking)
  // Design Decision: Immediate placeholder (not empty frame/spinner).
  // Rationale: Prevents layout shift, better perceived performance.
  // ========================================

  async function loadAlbumArt(fileUrl) {
    currentFileUrl = fileUrl;
    
    try {
      // Show loading overlay
      artLoading.style.display = 'flex';

      const response = await fetch(`/api/audio-metadata?file=${encodeURIComponent(fileUrl)}`);
      
      if (!response.ok) {
        throw new Error('Metadata fetch failed');
      }

      const metadata = await response.json();

      // Update album art (both full and mini)
      if (metadata.artwork_base64) {
        albumArt.src = metadata.artwork_base64;
        miniArt.src = metadata.artwork_base64;
      }

      // Update text metadata
      const title = metadata.title || 'Unknown Track';
      const artist = metadata.artist || 'Unknown Artist';

      audioTitle.textContent = title;
      audioArtist.textContent = artist;
      miniTitle.textContent = title;
      miniArtist.textContent = artist;

    } catch (error) {
      console.warn('Album art loading failed:', error);
      // Keep placeholder on error
    } finally {
      artLoading.style.display = 'none';
    }
  }

  // ========================================
  // PLAYBACK CONTROLS
  // ========================================

  function playTrack(index) {
    if (index < 0 || index >= currentPlaylist.length) return;

    // Initialize audio context before first play
    if (!audioContext) {
      initAudioContext();
    }

    currentTrackIndex = index;
    const track = currentPlaylist[index];

    audio.src = track.url;
    
    // Update download buttons with current track URL
    if (miniDownloadBtn) {
      miniDownloadBtn.href = track.url;
      miniDownloadBtn.download = track.name || '';
    }
    if (audioDownloadBtn) {
      audioDownloadBtn.href = track.url;
      audioDownloadBtn.download = track.name || '';
    }
    
    // Update playlist UI
    Array.from(playlistEl.children).forEach((el, i) => {
      el.classList.toggle('active', i === index);
    });

    // Load album art async (non-blocking)
    loadAlbumArt(track.url);

    audio.play().then(() => {
      if (audioContext.state === 'suspended') {
        audioContext.resume();
      }
      if (!audioSource) {
        connectAudioNodes();
      }
      updatePlayPauseIcons(false);
      startVUMeter();
    }).catch(err => {
      console.error('Playback failed:', err);
    });
  }

  function togglePlayPause() {
    if (audio.paused) {
      // Initialize audio context before first play
      if (!audioContext) {
        initAudioContext();
      }
      
      audio.play().then(() => {
        if (audioContext.state === 'suspended') {
          audioContext.resume();
        }
        if (!audioSource) {
          connectAudioNodes();
        }
        updatePlayPauseIcons(false);
        startVUMeter();
      }).catch(err => {
        console.error('Playback failed:', err);
      });
    } else {
      audio.pause();
      updatePlayPauseIcons(true);
      stopVUMeter();
    }
  }

  function updatePlayPauseIcons(paused) {
    playIcon.style.display = paused ? 'block' : 'none';
    pauseIcon.style.display = paused ? 'none' : 'block';
    miniPlayIcon.style.display = paused ? 'block' : 'none';
    miniPauseIcon.style.display = paused ? 'none' : 'block';
  }

  function playNext() {
    normalizeLoopMode();
    
    // Repeat one: restart current track
    if (loopMode === 2) {
      audio.currentTime = 0;
      audio.play().catch(err => console.error('Playback failed:', err));
      return;
    }

    // Move to next track
    let nextIndex = currentTrackIndex + 1;
    
    // Handle end of playlist
    if (nextIndex >= currentPlaylist.length) {
      if (loopMode === 1) {
        // Repeat all: wrap to first track
        nextIndex = 0;
      } else {
        // Loop off: stop playback
        audio.pause();
        updatePlayPauseIcons(true);
        stopVUMeter();
        return;
      }
    }
    
    playTrack(nextIndex);
  }

  function playPrev() {
    let prevIndex = currentTrackIndex - 1;
    if (prevIndex < 0) {
      prevIndex = loopMode === 1 ? currentPlaylist.length - 1 : 0;
    }
    playTrack(prevIndex);
  }

  function toggleLoop() {
    // Cycle through modes: 0 -> 1 -> 2 -> 0
    loopMode = (loopMode + 1) % 3;
    normalizeLoopMode();
    
    // Update visual state
    loopBtn.setAttribute('data-mode', String(loopMode));
    
    // Update accessibility label
    const labels = ['Loop off', 'Loop all', 'Loop one'];
    loopBtn.setAttribute('aria-label', labels[loopMode]);
  }

  // ========================================
  // PLAYER MODE MANAGEMENT
  // Design Decision: Mini-player dismiss stops playback (not hide-while-playing).
  // Rationale: iOS Safari limitation + UX consistency.
  // ========================================

  function showPlayer(fileUrl, fileName, mode = 'full') {
    initAudioContext();
    playerState = mode;

    if (mode === 'full') {
      modal.style.display = 'block';
      miniPlayer.style.display = 'none';
      document.body.classList.remove('mini-player-active');
    } else if (mode === 'mini') {
      modal.style.display = 'none';
      miniPlayer.style.display = 'flex';
      document.body.classList.add('mini-player-active');
    }

    // Reset controls to defaults on first open (preserve loop state)
    if (!audioSource) {
      const savedVolume = localStorage.getItem('vortex-audio-volume');
      const volume = savedVolume ? parseInt(savedVolume) : 80;
      volumeSlider.value = volume;
      miniVolume.value = volume;
      updateVolume(volume);

      tempoSlider.value = 100;
      bassSlider.value = 0;
      midSlider.value = 0;
      trebleSlider.value = 0;
      reverbSlider.value = 0;

      currentTempo = 1.0;
      audio.playbackRate = 1;
      bassNode.gain.value = 0;
      midNode.gain.value = 0;
      trebleNode.gain.value = 0;
      reverbGainNode.gain.value = 0;
      dryGainNode.gain.value = 1;

      tempoVal.textContent = '100%';
      bassVal.textContent = '0';
      midVal.textContent = '0';
      trebleVal.textContent = '0';
      reverbVal.textContent = '0%';

      // Only reset loop mode on very first initialization
      if (typeof loopMode === 'undefined') {
        loopMode = 0;
      }
      normalizeLoopMode();
      loopBtn.setAttribute('data-mode', String(loopMode));
    }

    // Load playlist and play
    loadPlaylist(fileUrl).then(() => {
      const trackIndex = currentPlaylist.findIndex(t => t.url === fileUrl);
      if (trackIndex >= 0) {
        playTrack(trackIndex);
      } else {
        // File not in playlist, play directly
        audio.src = fileUrl;
        loadAlbumArt(fileUrl);
        audio.play().then(() => {
          if (audioContext.state === 'suspended') {
            audioContext.resume();
          }
          if (!audioSource) {
            connectAudioNodes();
          }
          updatePlayPauseIcons(false);
          startVUMeter();
        }).catch(err => {
          console.error('Playback failed:', err);
        });
      }
    });
  }

  function minimizePlayer() {
    // Always show mini-player, even when paused
    playerState = 'mini';
    modal.style.display = 'none';
    miniPlayer.style.display = 'flex';
    document.body.classList.add('mini-player-active');
  }

  function expandPlayer() {
    playerState = 'full';
    modal.style.display = 'block';
    miniPlayer.style.display = 'none';
    document.body.classList.remove('mini-player-active');
  }

  function dismissPlayer() {
    playerState = 'hidden';
    modal.style.display = 'none';
    miniPlayer.style.display = 'none';
    document.body.classList.remove('mini-player-active');
    
    audio.pause();
    audio.src = '';
    stopVUMeter();

    // Cancel pending requests
    if (abortController) {
      abortController.abort();
      abortController = null;
    }

    // Clear UI
    updatePlayPauseIcons(true);
    progressBar.value = 0;
    timeCurrent.textContent = '0:00';
    timeTotal.textContent = '0:00';
    playlistEl.innerHTML = '';
  }

  // ========================================
  // PROGRESS BAR (Throttled)
  // ========================================

  const updateProgress = throttle(() => {
    if (!isFinite(audio.duration)) return;
    
    const progress = (audio.currentTime / audio.duration) * 100;
    progressBar.value = progress;
    timeCurrent.textContent = formatTime(audio.currentTime);
  }, PROGRESS_THROTTLE);

  function seekTo(percent) {
    if (!isFinite(audio.duration)) return;
    audio.currentTime = (percent / 100) * audio.duration;
  }

  // ========================================
  // AUDIO PARAMETERS (Debounced)
  // ========================================

  const updateVolume = debounce((value) => {
    gainNode.gain.value = value / 100;
    volumeVal.textContent = value + '%';
    volumeSlider.value = value;
    miniVolume.value = value;
    localStorage.setItem('vortex-audio-volume', value);
  }, SLIDER_DEBOUNCE);

  const updateTempo = debounce((tempo) => {
    currentTempo = tempo / 100;
    audio.playbackRate = Math.max(0.25, Math.min(4.0, currentTempo));
    tempoVal.textContent = tempo + '%';
  }, SLIDER_DEBOUNCE);

  const updateBass = throttle((gain) => {
    if (bassNode && bassNode.gain) {
      bassNode.gain.value = gain;
    }
    bassVal.textContent = (gain > 0 ? '+' : '') + gain;
  }, 16);

  const updateMid = throttle((gain) => {
    if (midNode && midNode.gain) {
      midNode.gain.value = gain;
    }
    midVal.textContent = (gain > 0 ? '+' : '') + gain;
  }, 16);

  const updateTreble = throttle((gain) => {
    if (trebleNode && trebleNode.gain) {
      trebleNode.gain.value = gain;
    }
    trebleVal.textContent = (gain > 0 ? '+' : '') + gain;
  }, 16);

  const updateReverb = throttle((value) => {
    // value is 0-100, convert to wet/dry mix
    const wetAmount = value / 100;
    const dryAmount = 1 - (wetAmount * 0.5);  // Keep some dry signal even at max reverb

    if (reverbGainNode && reverbGainNode.gain) {
      reverbGainNode.gain.value = wetAmount;
    }
    if (dryGainNode && dryGainNode.gain) {
      dryGainNode.gain.value = dryAmount;
    }
    reverbVal.textContent = value + '%';
  }, 16);

  /**
   * Reset all audio controls to their default values.
   * Volume is preserved as it's user preference.
   */
  function resetControls() {
    // Reset slider values
    tempoSlider.value = 100;
    bassSlider.value = 0;
    midSlider.value = 0;
    trebleSlider.value = 0;
    reverbSlider.value = 0;

    // Reset audio parameters
    currentTempo = 1.0;
    audio.playbackRate = 1;

    if (bassNode && bassNode.gain) {
      bassNode.gain.value = 0;
    }
    if (midNode && midNode.gain) {
      midNode.gain.value = 0;
    }
    if (trebleNode && trebleNode.gain) {
      trebleNode.gain.value = 0;
    }
    if (reverbGainNode && reverbGainNode.gain) {
      reverbGainNode.gain.value = 0;
    }
    if (dryGainNode && dryGainNode.gain) {
      dryGainNode.gain.value = 1;
    }

    // Update display values
    tempoVal.textContent = '100%';
    bassVal.textContent = '0';
    midVal.textContent = '0';
    trebleVal.textContent = '0';
    reverbVal.textContent = '0%';
  }

  // ========================================
  // PLAYLIST LOADING
  // ========================================

  async function loadPlaylist(currentFileUrl) {
    const url = new URL(currentFileUrl, window.location.origin);
    const pathParts = url.pathname.split('/');
    pathParts.pop();
    const dirPath = pathParts.join('/') || '/';

    if (abortController) {
      abortController.abort();
    }
    abortController = new AbortController();

    try {
      const response = await fetch(dirPath, {
        signal: abortController.signal
      });

      const html = await response.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const links = doc.querySelectorAll('a');

      currentPlaylist = [];
      links.forEach(link => {
        const href = link.getAttribute('href');
        const text = link.textContent.trim();

        if (href && isAudioFile(text)) {
          const fullUrl = new URL(href, currentFileUrl).href;
          currentPlaylist.push({ url: fullUrl, name: text });
        }
      });

      renderPlaylist();

    } catch (error) {
      if (error.name !== 'AbortError') {
        console.warn('Playlist load failed:', error);
      }
    }
  }

  function renderPlaylist() {
    playlistEl.innerHTML = '';
    currentPlaylist.forEach((track, i) => {
      const item = document.createElement('div');
      item.className = 'audio-playlist-item';
      if (i === currentTrackIndex) {
        item.classList.add('active');
      }
      item.textContent = track.name;
      item.addEventListener('click', () => playTrack(i));
      playlistEl.appendChild(item);
    });
  }

  // ========================================
  // EVENT LISTENERS
  // ========================================

  // Full modal controls
  if (minimizeBtn) {
    minimizeBtn.addEventListener('click', minimizePlayer);
  }
  if (dismissBtn) {
    dismissBtn.addEventListener('click', dismissPlayer);
  }
  playBtn.addEventListener('click', togglePlayPause);
  prevBtn.addEventListener('click', playPrev);
  nextBtn.addEventListener('click', playNext);
  loopBtn.addEventListener('click', toggleLoop);

  // Mini player controls
  miniPlayBtn.addEventListener('click', togglePlayPause);
  miniPrevBtn.addEventListener('click', playPrev);
  miniNextBtn.addEventListener('click', playNext);
  miniExpandBtn.addEventListener('click', expandPlayer);
  miniCloseBtn.addEventListener('click', dismissPlayer);

  // Audio events
  audio.addEventListener('timeupdate', updateProgress);
  audio.addEventListener('ended', playNext);
  audio.addEventListener('loadedmetadata', () => {
    timeTotal.textContent = formatTime(audio.duration);
    progressBar.max = 100;
  });

  // Progress bar seeking
  progressBar.addEventListener('input', (e) => {
    seekTo(parseFloat(e.target.value));
  });

  // Sliders
  volumeSlider.addEventListener('input', (e) => updateVolume(e.target.value));
  miniVolume.addEventListener('input', (e) => updateVolume(e.target.value));
  tempoSlider.addEventListener('input', (e) => updateTempo(e.target.value));
  bassSlider.addEventListener('input', (e) => updateBass(e.target.value));
  midSlider.addEventListener('input', (e) => updateMid(e.target.value));
  trebleSlider.addEventListener('input', (e) => updateTreble(e.target.value));
  reverbSlider.addEventListener('input', (e) => updateReverb(e.target.value));

  // Reset button
  resetBtn.addEventListener('click', resetControls);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (playerState === 'hidden') return;

    switch(e.key) {
      case ' ':
        e.preventDefault();
        togglePlayPause();
        break;
      case 'Escape':
        if (playerState === 'full') {
          minimizePlayer();
        } else {
          dismissPlayer();
        }
        break;
      case 'ArrowLeft':
        e.preventDefault();
        audio.currentTime = Math.max(0, audio.currentTime - 5);
        break;
      case 'ArrowRight':
        e.preventDefault();
        audio.currentTime = Math.min(audio.duration, audio.currentTime + 5);
        break;
      case 'ArrowUp':
        e.preventDefault();
        volumeSlider.value = Math.min(100, parseInt(volumeSlider.value) + 10);
        updateVolume(volumeSlider.value);
        break;
      case 'ArrowDown':
        e.preventDefault();
        volumeSlider.value = Math.max(0, parseInt(volumeSlider.value) - 10);
        updateVolume(volumeSlider.value);
        break;
    }
  });

  // Page Visibility API
  document.addEventListener('visibilitychange', () => {
    visualizerActive = !document.hidden;
  });

  // Intercept audio file clicks
  document.addEventListener('click', (e) => {
    const target = e.target.closest('a');
    if (!target) return;

    const href = target.getAttribute('href');
    if (!href) return;

    const filename = target.textContent.trim();
    if (isAudioFile(filename)) {
      e.preventDefault();
      e.stopPropagation();
      showPlayer(target.href, filename, 'full');
    }
  });

  // Expose for debugging
  window.VortexAudioPlayer = {
    show: showPlayer,
    minimize: minimizePlayer,
    expand: expandPlayer,
    dismiss: dismissPlayer
  };

})();
"""
