# MIT License
# Copyright (c) 2026 Vortex Contributors
# See LICENSE file for full license text.

"""
Media viewer module for Vortex file gateway.

Provides image viewer modal with zoom/pan and video player modal with custom controls.
Both viewers are designed to overlay the existing UI without disrupting grid layout
or audio player persistence.

Performance optimizations:
- GPU-accelerated transforms (translateZ, will-change)
- contain: layout for isolation
- Debounced resize handlers at 60fps
- Lazy conversion for HEIC images via CDN
"""


def get_image_viewer_html() -> str:
    """
    Returns HTML for fullscreen image viewer modal.

    Design principles:
    - Z-index 10001 (above audio modal's 10000)
    - Immediate placeholder while loading
    - Download button with a[download] attribute
    - Navigation arrows for image playlist
    """
    return """
<!-- Image Viewer Modal (z-10001, above audio player) -->
<div id="image-viewer-modal" class="image-viewer-modal" style="display: none;">
  <div class="image-viewer-backdrop"></div>

  <!-- Corner controls -->
  <div class="image-viewer-controls">
    <a id="image-download" class="image-viewer-btn image-download-btn" href="" download aria-label="Download image" title="Download">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
      </svg>
    </a>
    <button id="image-close" class="image-viewer-btn image-close-btn" aria-label="Close viewer" title="Close (ESC)">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  </div>

  <!-- Navigation arrows -->
  <button id="image-prev" class="image-nav-btn image-nav-prev" aria-label="Previous image" title="Previous (←)">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M15 18l-6-6 6-6"/>
    </svg>
  </button>
  <button id="image-next" class="image-nav-btn image-nav-next" aria-label="Next image" title="Next (→)">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M9 18l6-6-6-6"/>
    </svg>
  </button>

  <!-- Image container with zoom/pan -->
  <div id="image-container" class="image-container">
    <img id="image-viewer-img" class="image-viewer-img" alt="" draggable="false">
    <div id="image-loading" class="image-loading" style="display: none;">
      <div class="image-loading-spinner"></div>
      <span class="image-loading-text">Loading...</span>
    </div>
  </div>

  <!-- Image info bar -->
  <div id="image-info" class="image-info-bar">
    <span id="image-filename" class="image-filename"></span>
    <span id="image-counter" class="image-counter"></span>
  </div>
</div>
"""


def get_image_viewer_css() -> str:
    """
    Returns CSS for image viewer with GPU optimization.

    Performance:
    - transform: translateZ(0) for GPU layer
    - will-change: transform, opacity
    - contain: layout for isolation
    """
    return """
/* ========================================
   IMAGE VIEWER MODAL
   ======================================== */

.image-viewer-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 10001;
  contain: layout;
  transform: translateZ(0);
  will-change: opacity;
}

.image-viewer-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.95);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

/* Corner Controls (top-right) */
.image-viewer-controls {
  position: absolute;
  top: 1rem;
  right: 1rem;
  display: flex;
  gap: 0.5rem;
  z-index: 10;
}

.image-viewer-btn {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  text-decoration: none;
}

.image-download-btn {
  background: var(--accent-color);
  border-color: var(--accent-color);
}

.image-download-btn:hover {
  background: var(--accent-hover);
  transform: scale(1.05);
}

.image-close-btn:hover {
  background: var(--error-color);
  border-color: var(--error-color);
  transform: scale(1.05);
}

.image-viewer-btn:active {
  transform: scale(0.95);
}

/* Navigation Arrows */
.image-nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  z-index: 10;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.image-nav-prev {
  left: 1rem;
}

.image-nav-next {
  right: 1rem;
}

.image-nav-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-50%) scale(1.05);
}

.image-nav-btn:active {
  transform: translateY(-50%) scale(0.95);
}

.image-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.image-nav-btn:disabled:hover {
  background: rgba(0, 0, 0, 0.5);
  transform: translateY(-50%);
}

/* Image Container */
.image-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: grab;
}

.image-container.dragging {
  cursor: grabbing;
}

.image-viewer-img {
  max-width: 95vw;
  max-height: 95vh;
  object-fit: contain;
  transform-origin: center center;
  transform: translateZ(0);
  will-change: transform;
  transition: transform 0.1s ease-out;
  user-select: none;
  -webkit-user-select: none;
  -webkit-user-drag: none;
}

.image-viewer-img.zoomed {
  cursor: grab;
  transition: none;
}

.image-viewer-img.panning {
  cursor: grabbing;
}

/* Loading Overlay */
.image-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: white;
  z-index: 5;
}

.image-loading-spinner {
  width: 40px;
  height: 40px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: image-spin 0.8s linear infinite;
}

@keyframes image-spin {
  to { transform: rotate(360deg); }
}

.image-loading-text {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* Info Bar (bottom) */
.image-info-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0.75rem 1rem;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.8) 0%, transparent 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: white;
  font-family: var(--font-ui);
  font-size: 0.8rem;
  z-index: 5;
}

.image-filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}

.image-counter {
  opacity: 0.7;
  font-size: 0.75rem;
}

/* Mobile Adjustments */
@media (max-width: 600px) {
  .image-viewer-controls {
    top: 0.5rem;
    right: 0.5rem;
  }

  .image-viewer-btn {
    width: 36px;
    height: 36px;
  }

  .image-nav-btn {
    width: 40px;
    height: 40px;
  }

  .image-nav-prev {
    left: 0.5rem;
  }

  .image-nav-next {
    right: 0.5rem;
  }

  .image-info-bar {
    padding: 0.5rem;
    font-size: 0.7rem;
  }
}

/* Touch device optimizations */
@media (pointer: coarse) {
  .image-nav-btn {
    width: 52px;
    height: 52px;
  }

  .image-viewer-btn {
    width: 44px;
    height: 44px;
  }
}
"""


def get_image_viewer_js() -> str:
    """
    Returns JavaScript for image viewer with zoom/pan and keyboard navigation.

    Features:
    - Zoom: mouse wheel, pinch gesture
    - Pan: click-drag, touch-drag
    - Keyboard: Arrow keys (prev/next), ESC (close), +/- (zoom)
    - HEIC conversion via heic2any CDN
    """
    return """
/* ========================================
   IMAGE VIEWER MODULE
   ======================================== */

(function() {
  'use strict';

  // Image viewer state
  var state = {
    isOpen: false,
    currentIndex: 0,
    imageList: [],
    scale: 1,
    translateX: 0,
    translateY: 0,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    lastTouchDistance: 0
  };

  // DOM Elements
  var modal, backdrop, img, container, loading, loadingText;
  var downloadBtn, closeBtn, prevBtn, nextBtn;
  var filenameEl, counterEl;

  // HEIC conversion library loaded flag
  var heic2anyLoaded = false;

  // Object URL tracking to prevent memory leaks
  var currentObjectUrl = null;

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', initImageViewer);

  function initImageViewer() {
    modal = document.getElementById('image-viewer-modal');
    if (!modal) return;

    backdrop = modal.querySelector('.image-viewer-backdrop');
    container = document.getElementById('image-container');
    img = document.getElementById('image-viewer-img');
    loading = document.getElementById('image-loading');
    loadingText = modal.querySelector('.image-loading-text');
    downloadBtn = document.getElementById('image-download');
    closeBtn = document.getElementById('image-close');
    prevBtn = document.getElementById('image-prev');
    nextBtn = document.getElementById('image-next');
    filenameEl = document.getElementById('image-filename');
    counterEl = document.getElementById('image-counter');

    // Event listeners
    closeBtn.addEventListener('click', close);
    backdrop.addEventListener('click', close);
    prevBtn.addEventListener('click', showPrev);
    nextBtn.addEventListener('click', showNext);

    // Keyboard navigation
    document.addEventListener('keydown', handleKeydown);

    // Mouse wheel zoom
    container.addEventListener('wheel', handleWheel, { passive: false });

    // Mouse drag pan
    container.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    // Touch gestures
    container.addEventListener('touchstart', handleTouchStart, { passive: false });
    container.addEventListener('touchmove', handleTouchMove, { passive: false });
    container.addEventListener('touchend', handleTouchEnd);

    // Image load events
    img.addEventListener('load', handleImageLoad);
    img.addEventListener('error', handleImageError);

    // Expose to global scope
    window.VortexImageViewer = {
      open: open,
      close: close
    };
  }

  /**
   * Open image viewer with specified image URL.
   * Also builds playlist of images in current directory.
   */
  function open(imageUrl, filename) {
    // Build image list from current file listing
    buildImageList();

    // Find current image in list
    var index = state.imageList.findIndex(function(item) {
      return item.url === imageUrl || item.filename === filename;
    });

    if (index === -1) {
      // Image not in list, add it
      state.imageList = [{ url: imageUrl, filename: filename }];
      index = 0;
    }

    state.currentIndex = index;
    state.isOpen = true;

    // Reset zoom/pan
    resetTransform();

    // Show modal
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';

    // Load image
    loadImage(state.imageList[index]);

    // Update navigation buttons
    updateNavButtons();
  }

  /**
   * Build list of images from current file listing.
   */
  function buildImageList() {
    var imageExts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.bmp', '.svg', '.avif'];
    var links = document.querySelectorAll('.file-list a');
    var list = [];

    links.forEach(function(link) {
      var href = link.getAttribute('href');
      var filename = link.textContent.trim();
      var lower = filename.toLowerCase();

      var isImage = imageExts.some(function(ext) {
        return lower.endsWith(ext);
      });

      if (isImage) {
        list.push({ url: href, filename: filename });
      }
    });

    state.imageList = list;
  }

  /**
   * Load an image, with HEIC conversion if needed.
   */
  function loadImage(item) {
    var url = item.url;
    var filename = item.filename;
    var lower = filename.toLowerCase();

    // Update download button
    downloadBtn.href = url;
    downloadBtn.download = filename;

    // Update info
    filenameEl.textContent = filename;
    updateCounter();

    // Check if HEIC
    if (lower.endsWith('.heic') || lower.endsWith('.heif')) {
      loading.style.display = 'flex';
      loadingText.textContent = 'Converting HEIC...';
      img.style.opacity = '0';
      convertHeic(url);
      return;
    }

    // Standard image
    loading.style.display = 'flex';
    loadingText.textContent = 'Loading...';
    img.style.opacity = '0';
    img.src = url;
  }

  /**
   * Convert HEIC image using heic2any library.
   */
  function convertHeic(url) {
    // Load heic2any from CDN if not loaded
    if (!heic2anyLoaded && typeof heic2any === 'undefined') {
      var script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/heic2any@0.0.4/dist/heic2any.min.js';
      script.onload = function() {
        heic2anyLoaded = true;
        doHeicConversion(url);
      };
      script.onerror = function() {
        handleImageError();
      };
      document.head.appendChild(script);
    } else {
      doHeicConversion(url);
    }
  }

  function doHeicConversion(url) {
    fetch(url)
      .then(function(res) { return res.blob(); })
      .then(function(blob) {
        return heic2any({
          blob: blob,
          toType: 'image/jpeg',
          quality: 0.9
        });
      })
      .then(function(jpegBlob) {
        // Revoke previous object URL to prevent memory leak
        if (currentObjectUrl) {
          URL.revokeObjectURL(currentObjectUrl);
        }
        currentObjectUrl = URL.createObjectURL(jpegBlob);
        img.src = currentObjectUrl;
      })
      .catch(function(err) {
        console.error('HEIC conversion failed:', err);
        handleImageError();
      });
  }

  function handleImageLoad() {
    loading.style.display = 'none';
    img.style.opacity = '1';
  }

  function handleImageError() {
    loading.style.display = 'flex';
    loadingText.textContent = 'Failed to load image';
    img.style.opacity = '0';
  }

  /**
   * Close the image viewer.
   */
  function close() {
    if (!state.isOpen) return;

    state.isOpen = false;
    modal.style.display = 'none';
    document.body.style.overflow = '';
    img.src = '';

    // Revoke object URL to prevent memory leak
    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl);
      currentObjectUrl = null;
    }

    resetTransform();
  }

  /**
   * Show previous image.
   */
  function showPrev() {
    if (state.currentIndex > 0) {
      state.currentIndex--;
      resetTransform();
      loadImage(state.imageList[state.currentIndex]);
      updateNavButtons();
    }
  }

  /**
   * Show next image.
   */
  function showNext() {
    if (state.currentIndex < state.imageList.length - 1) {
      state.currentIndex++;
      resetTransform();
      loadImage(state.imageList[state.currentIndex]);
      updateNavButtons();
    }
  }

  function updateNavButtons() {
    prevBtn.disabled = state.currentIndex === 0;
    nextBtn.disabled = state.currentIndex >= state.imageList.length - 1;
    prevBtn.style.display = state.imageList.length > 1 ? 'flex' : 'none';
    nextBtn.style.display = state.imageList.length > 1 ? 'flex' : 'none';
  }

  function updateCounter() {
    if (state.imageList.length > 1) {
      counterEl.textContent = (state.currentIndex + 1) + ' / ' + state.imageList.length;
    } else {
      counterEl.textContent = '';
    }
  }

  /**
   * Reset zoom and pan to default.
   */
  function resetTransform() {
    state.scale = 1;
    state.translateX = 0;
    state.translateY = 0;
    applyTransform();
    img.classList.remove('zoomed', 'panning');
    container.classList.remove('dragging');
  }

  /**
   * Apply current transform to image.
   */
  function applyTransform() {
    img.style.transform = 'translate3d(' + state.translateX + 'px, ' + state.translateY + 'px, 0) scale(' + state.scale + ')';
  }

  /**
   * Keyboard event handler.
   */
  function handleKeydown(e) {
    if (!state.isOpen) return;

    switch (e.key) {
      case 'Escape':
        close();
        break;
      case 'ArrowLeft':
        showPrev();
        break;
      case 'ArrowRight':
        showNext();
        break;
      case '+':
      case '=':
        zoom(1.25);
        break;
      case '-':
        zoom(0.8);
        break;
      case '0':
        resetTransform();
        break;
    }
  }

  /**
   * Mouse wheel zoom handler.
   */
  function handleWheel(e) {
    if (!state.isOpen) return;
    e.preventDefault();

    var delta = e.deltaY > 0 ? 0.9 : 1.1;
    zoom(delta, e.clientX, e.clientY);
  }

  /**
   * Zoom by factor, optionally around a point.
   */
  function zoom(factor, centerX, centerY) {
    var newScale = Math.max(0.5, Math.min(10, state.scale * factor));

    if (centerX !== undefined && centerY !== undefined) {
      // Zoom around cursor position
      var rect = container.getBoundingClientRect();
      var imgCenterX = rect.width / 2;
      var imgCenterY = rect.height / 2;

      var mouseX = centerX - rect.left - imgCenterX;
      var mouseY = centerY - rect.top - imgCenterY;

      state.translateX = mouseX - (mouseX - state.translateX) * (newScale / state.scale);
      state.translateY = mouseY - (mouseY - state.translateY) * (newScale / state.scale);
    }

    state.scale = newScale;

    if (state.scale > 1) {
      img.classList.add('zoomed');
    } else {
      img.classList.remove('zoomed');
      state.translateX = 0;
      state.translateY = 0;
    }

    applyTransform();
  }

  /**
   * Mouse drag handlers for panning.
   */
  function handleMouseDown(e) {
    if (!state.isOpen || state.scale <= 1) return;
    if (e.button !== 0) return; // Only left click

    state.isDragging = true;
    state.dragStartX = e.clientX - state.translateX;
    state.dragStartY = e.clientY - state.translateY;
    img.classList.add('panning');
    container.classList.add('dragging');
    e.preventDefault();
  }

  function handleMouseMove(e) {
    if (!state.isDragging) return;

    state.translateX = e.clientX - state.dragStartX;
    state.translateY = e.clientY - state.dragStartY;
    applyTransform();
  }

  function handleMouseUp() {
    if (!state.isDragging) return;

    state.isDragging = false;
    img.classList.remove('panning');
    container.classList.remove('dragging');
  }

  /**
   * Touch gesture handlers for pinch zoom and pan.
   */
  function handleTouchStart(e) {
    if (!state.isOpen) return;

    if (e.touches.length === 2) {
      // Pinch zoom start
      state.lastTouchDistance = getTouchDistance(e.touches);
      e.preventDefault();
    } else if (e.touches.length === 1 && state.scale > 1) {
      // Pan start
      state.isDragging = true;
      state.dragStartX = e.touches[0].clientX - state.translateX;
      state.dragStartY = e.touches[0].clientY - state.translateY;
      img.classList.add('panning');
      e.preventDefault();
    }
  }

  function handleTouchMove(e) {
    if (!state.isOpen) return;

    if (e.touches.length === 2) {
      // Pinch zoom
      var distance = getTouchDistance(e.touches);
      var factor = distance / state.lastTouchDistance;
      state.lastTouchDistance = distance;

      var centerX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
      var centerY = (e.touches[0].clientY + e.touches[1].clientY) / 2;

      zoom(factor, centerX, centerY);
      e.preventDefault();
    } else if (e.touches.length === 1 && state.isDragging) {
      // Pan
      state.translateX = e.touches[0].clientX - state.dragStartX;
      state.translateY = e.touches[0].clientY - state.dragStartY;
      applyTransform();
      e.preventDefault();
    }
  }

  function handleTouchEnd() {
    state.isDragging = false;
    state.lastTouchDistance = 0;
    img.classList.remove('panning');
  }

  function getTouchDistance(touches) {
    var dx = touches[0].clientX - touches[1].clientX;
    var dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }
})();
"""


def get_video_player_html() -> str:
    """
    Returns HTML for fullscreen video player modal with custom controls.

    Design principles:
    - Z-index 10001 (same layer as image viewer)
    - Custom controls overlay (no native controls)
    - Download button matching audio player style
    - iOS compatibility with playsinline
    """
    return """
<!-- Video Player Modal (z-10001) -->
<div id="video-player-modal" class="video-player-modal" style="display: none;">
  <div class="video-player-backdrop"></div>

  <!-- Corner controls -->
  <div class="video-player-corner-controls">
    <a id="video-download" class="video-player-btn video-download-btn" href="" download aria-label="Download video" title="Download">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
      </svg>
    </a>
    <button id="video-pip" class="video-player-btn" aria-label="Picture in Picture" title="Picture in Picture">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <rect x="11" y="9" width="9" height="6" rx="1" fill="currentColor"/>
      </svg>
    </button>
    <button id="video-close" class="video-player-btn video-close-btn" aria-label="Close player" title="Close (ESC)">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  </div>

  <!-- Video container -->
  <div id="video-container" class="video-container">
    <video id="video-element" preload="metadata" playsinline></video>

    <!-- Play overlay (click to play) -->
    <div id="video-play-overlay" class="video-play-overlay">
      <div class="video-play-circle">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z"/>
        </svg>
      </div>
    </div>

    <!-- Loading overlay -->
    <div id="video-loading" class="video-loading" style="display: none;">
      <div class="video-loading-spinner"></div>
    </div>
  </div>

  <!-- Custom Controls Bar -->
  <div id="video-controls" class="video-controls">
    <!-- Progress bar -->
    <div class="video-progress-container">
      <input type="range" id="video-progress" class="video-progress-bar" min="0" max="100" value="0" step="0.1">
    </div>

    <!-- Control buttons row -->
    <div class="video-controls-row">
      <!-- Left: play/pause, volume, time -->
      <div class="video-controls-left">
        <button id="video-play-btn" class="video-ctrl-btn" aria-label="Play">
          <svg id="video-play-icon" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z"/>
          </svg>
          <svg id="video-pause-icon" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" style="display: none;">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
          </svg>
        </button>

        <button id="video-mute-btn" class="video-ctrl-btn" aria-label="Mute">
          <svg id="video-volume-icon" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
          </svg>
          <svg id="video-muted-icon" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="display: none;">
            <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
          </svg>
        </button>

        <input type="range" id="video-volume" class="video-volume-slider" min="0" max="100" value="80" step="1">

        <span class="video-time">
          <span id="video-time-current">0:00</span>
          <span class="video-time-sep">/</span>
          <span id="video-time-total">0:00</span>
        </span>
      </div>

      <!-- Right: speed, fullscreen -->
      <div class="video-controls-right">
        <select id="video-speed" class="video-speed-select">
          <option value="0.25">0.25x</option>
          <option value="0.5">0.5x</option>
          <option value="0.75">0.75x</option>
          <option value="1" selected>1x</option>
          <option value="1.25">1.25x</option>
          <option value="1.5">1.5x</option>
          <option value="2">2x</option>
        </select>

        <button id="video-fullscreen-btn" class="video-ctrl-btn" aria-label="Fullscreen">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- File info -->
  <div id="video-info" class="video-info-bar">
    <span id="video-filename" class="video-filename"></span>
  </div>
</div>
"""


def get_video_player_css() -> str:
    """
    Returns CSS for video player matching existing audio player aesthetic.
    """
    return """
/* ========================================
   VIDEO PLAYER MODAL
   ======================================== */

.video-player-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 10001;
  contain: layout;
  display: flex;
  flex-direction: column;
}

.video-player-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.95);
}

/* Corner Controls */
.video-player-corner-controls {
  position: absolute;
  top: 1rem;
  right: 1rem;
  display: flex;
  gap: 0.5rem;
  z-index: 20;
}

.video-player-btn {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  text-decoration: none;
}

.video-download-btn {
  background: var(--accent-color);
  border-color: var(--accent-color);
}

.video-download-btn:hover {
  background: var(--accent-hover);
  transform: scale(1.05);
}

.video-close-btn:hover {
  background: var(--error-color);
  border-color: var(--error-color);
  transform: scale(1.05);
}

.video-player-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.05);
}

/* Video Container */
.video-container {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
}

.video-container video {
  max-width: 100%;
  max-height: calc(100vh - 120px);
  background: #000;
}

/* Play Overlay */
.video-play-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
}

.video-play-overlay.hidden {
  display: none;
}

.video-play-circle {
  width: 80px;
  height: 80px;
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: transform 0.15s ease, background 0.15s ease;
}

.video-play-overlay:hover .video-play-circle {
  transform: scale(1.1);
  background: var(--accent-color);
}

/* Loading */
.video-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 15;
}

.video-loading-spinner {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: video-spin 0.8s linear infinite;
}

@keyframes video-spin {
  to { transform: rotate(360deg); }
}

/* Controls Bar */
.video-controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, rgba(0, 0, 0, 0.7) 70%, transparent 100%);
  padding: 1.5rem 1rem 1rem;
  z-index: 20;
  transition: opacity 0.3s ease;
}

.video-controls.hidden {
  opacity: 0;
  pointer-events: none;
}

/* Progress Bar */
.video-progress-container {
  width: 100%;
  margin-bottom: 0.75rem;
}

.video-progress-bar {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  cursor: pointer;
  transition: height 0.15s ease;
}

.video-progress-bar:hover {
  height: 6px;
}

.video-progress-bar::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  background: var(--accent-color);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
}

.video-progress-bar::-moz-range-thumb {
  width: 14px;
  height: 14px;
  background: var(--accent-color);
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

/* Controls Row */
.video-controls-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.video-controls-left,
.video-controls-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.video-ctrl-btn {
  background: transparent;
  border: none;
  color: white;
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s ease, transform 0.15s ease;
}

.video-ctrl-btn:hover {
  color: var(--accent-color);
  transform: scale(1.1);
}

/* Volume Slider */
.video-volume-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 80px;
  height: 4px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  cursor: pointer;
}

.video-volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  cursor: pointer;
}

.video-volume-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

/* Time Display */
.video-time {
  color: white;
  font-family: var(--font-ui);
  font-size: 0.8rem;
  white-space: nowrap;
}

.video-time-sep {
  margin: 0 0.25rem;
  opacity: 0.6;
}

/* Speed Select */
.video-speed-select {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  color: white;
  font-family: var(--font-ui);
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
}

.video-speed-select:hover {
  background: rgba(255, 255, 255, 0.2);
}

.video-speed-select option {
  background: #1a1a1a;
  color: white;
}

/* Info Bar */
.video-info-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 0.75rem 1rem;
  padding-right: 160px; /* Space for corner controls */
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.7) 0%, transparent 100%);
  z-index: 15;
}

.video-filename {
  color: white;
  font-family: var(--font-ui);
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Mobile Adjustments */
@media (max-width: 600px) {
  .video-player-corner-controls {
    top: 0.5rem;
    right: 0.5rem;
  }

  .video-player-btn {
    width: 36px;
    height: 36px;
  }

  .video-controls {
    padding: 1rem 0.5rem 0.5rem;
  }

  .video-volume-slider {
    display: none;
  }

  .video-time {
    font-size: 0.7rem;
  }

  .video-info-bar {
    padding-right: 120px;
    font-size: 0.8rem;
  }
}
"""


def get_video_player_js() -> str:
    """
    Returns JavaScript for video player with custom controls.

    Features:
    - Custom controls (no native)
    - Keyboard: Space (pause), Arrows (±10s seek), M (mute)
    - Speed: 0.25x to 2x
    - Picture-in-Picture support
    """
    return """
/* ========================================
   VIDEO PLAYER MODULE
   ======================================== */

(function() {
  'use strict';

  // Video player state
  var state = {
    isOpen: false,
    controlsTimeout: null,
    controlsHidden: false
  };

  // DOM Elements
  var modal, backdrop, video, container;
  var playOverlay, loading, controls;
  var downloadBtn, closeBtn, pipBtn, fullscreenBtn;
  var playBtn, playIcon, pauseIcon;
  var muteBtn, volumeIcon, mutedIcon, volumeSlider;
  var progressBar, currentTimeEl, totalTimeEl;
  var speedSelect, filenameEl;

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', initVideoPlayer);

  function initVideoPlayer() {
    modal = document.getElementById('video-player-modal');
    if (!modal) return;

    backdrop = modal.querySelector('.video-player-backdrop');
    container = document.getElementById('video-container');
    video = document.getElementById('video-element');
    playOverlay = document.getElementById('video-play-overlay');
    loading = document.getElementById('video-loading');
    controls = document.getElementById('video-controls');

    downloadBtn = document.getElementById('video-download');
    closeBtn = document.getElementById('video-close');
    pipBtn = document.getElementById('video-pip');
    fullscreenBtn = document.getElementById('video-fullscreen-btn');

    playBtn = document.getElementById('video-play-btn');
    playIcon = document.getElementById('video-play-icon');
    pauseIcon = document.getElementById('video-pause-icon');

    muteBtn = document.getElementById('video-mute-btn');
    volumeIcon = document.getElementById('video-volume-icon');
    mutedIcon = document.getElementById('video-muted-icon');
    volumeSlider = document.getElementById('video-volume');

    progressBar = document.getElementById('video-progress');
    currentTimeEl = document.getElementById('video-time-current');
    totalTimeEl = document.getElementById('video-time-total');

    speedSelect = document.getElementById('video-speed');
    filenameEl = document.getElementById('video-filename');

    // Event listeners
    closeBtn.addEventListener('click', close);
    backdrop.addEventListener('click', close);

    playOverlay.addEventListener('click', togglePlay);
    playBtn.addEventListener('click', togglePlay);
    video.addEventListener('click', togglePlay);

    muteBtn.addEventListener('click', toggleMute);
    volumeSlider.addEventListener('input', handleVolumeChange);

    progressBar.addEventListener('input', handleSeek);

    speedSelect.addEventListener('change', handleSpeedChange);

    if (document.pictureInPictureEnabled) {
      pipBtn.addEventListener('click', togglePiP);
    } else {
      pipBtn.style.display = 'none';
    }

    fullscreenBtn.addEventListener('click', toggleFullscreen);

    // Video events
    video.addEventListener('loadedmetadata', handleMetadata);
    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('waiting', function() { loading.style.display = 'flex'; });
    video.addEventListener('canplay', function() { loading.style.display = 'none'; });
    video.addEventListener('ended', handleEnded);

    // Controls auto-hide
    modal.addEventListener('mousemove', showControls);
    modal.addEventListener('touchstart', showControls);

    // Keyboard navigation
    document.addEventListener('keydown', handleKeydown);

    // Expose to global scope
    window.VortexVideoPlayer = {
      open: open,
      close: close
    };
  }

  /**
   * Open video player with specified video URL.
   */
  function open(videoUrl, filename) {
    state.isOpen = true;

    // Update download button
    downloadBtn.href = videoUrl;
    downloadBtn.download = filename;

    // Update filename
    filenameEl.textContent = filename;

    // Reset UI
    playOverlay.classList.remove('hidden');
    playIcon.style.display = 'block';
    pauseIcon.style.display = 'none';
    progressBar.value = 0;
    currentTimeEl.textContent = '0:00';
    totalTimeEl.textContent = '0:00';
    speedSelect.value = '1';

    // Set video source
    video.src = videoUrl;
    video.volume = volumeSlider.value / 100;

    // Show modal
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    showControls();
  }

  /**
   * Close video player.
   */
  function close() {
    if (!state.isOpen) return;

    state.isOpen = false;
    video.pause();
    video.src = '';

    modal.style.display = 'none';
    document.body.style.overflow = '';

    // Exit PiP if active
    if (document.pictureInPictureElement) {
      document.exitPictureInPicture().catch(function() {});
    }
  }

  /**
   * Toggle play/pause.
   */
  function togglePlay() {
    if (video.paused) {
      video.play();
    } else {
      video.pause();
    }
  }

  function handlePlay() {
    playOverlay.classList.add('hidden');
    playIcon.style.display = 'none';
    pauseIcon.style.display = 'block';
  }

  function handlePause() {
    playIcon.style.display = 'block';
    pauseIcon.style.display = 'none';
  }

  function handleEnded() {
    playOverlay.classList.remove('hidden');
    playIcon.style.display = 'block';
    pauseIcon.style.display = 'none';
    progressBar.value = 100;
  }

  /**
   * Toggle mute.
   */
  function toggleMute() {
    video.muted = !video.muted;
    updateMuteIcon();
  }

  function updateMuteIcon() {
    if (video.muted || video.volume === 0) {
      volumeIcon.style.display = 'none';
      mutedIcon.style.display = 'block';
    } else {
      volumeIcon.style.display = 'block';
      mutedIcon.style.display = 'none';
    }
  }

  function handleVolumeChange() {
    video.volume = volumeSlider.value / 100;
    video.muted = video.volume === 0;
    updateMuteIcon();
  }

  /**
   * Handle metadata loaded.
   */
  function handleMetadata() {
    totalTimeEl.textContent = formatTime(video.duration);
  }

  /**
   * Handle time update.
   */
  function handleTimeUpdate() {
    currentTimeEl.textContent = formatTime(video.currentTime);
    if (video.duration) {
      progressBar.value = (video.currentTime / video.duration) * 100;
    }
  }

  /**
   * Handle seek.
   */
  function handleSeek() {
    if (video.duration) {
      video.currentTime = (progressBar.value / 100) * video.duration;
    }
  }

  /**
   * Handle speed change.
   */
  function handleSpeedChange() {
    video.playbackRate = parseFloat(speedSelect.value);
  }

  /**
   * Toggle Picture-in-Picture.
   */
  function togglePiP() {
    if (document.pictureInPictureElement) {
      document.exitPictureInPicture();
    } else if (document.pictureInPictureEnabled) {
      video.requestPictureInPicture().catch(function(err) {
        console.error('PiP failed:', err);
      });
    }
  }

  /**
   * Toggle fullscreen.
   */
  function toggleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      modal.requestFullscreen().catch(function(err) {
        console.error('Fullscreen failed:', err);
      });
    }
  }

  /**
   * Show controls and auto-hide after delay.
   */
  function showControls() {
    controls.classList.remove('hidden');
    state.controlsHidden = false;

    clearTimeout(state.controlsTimeout);
    if (!video.paused) {
      state.controlsTimeout = setTimeout(hideControls, 3000);
    }
  }

  function hideControls() {
    if (!video.paused && state.isOpen) {
      controls.classList.add('hidden');
      state.controlsHidden = true;
    }
  }

  /**
   * Keyboard handler.
   */
  function handleKeydown(e) {
    if (!state.isOpen) return;

    switch (e.key) {
      case 'Escape':
        close();
        break;
      case ' ':
        e.preventDefault();
        togglePlay();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        video.currentTime = Math.max(0, video.currentTime - 10);
        showControls();
        break;
      case 'ArrowRight':
        e.preventDefault();
        video.currentTime = Math.min(video.duration, video.currentTime + 10);
        showControls();
        break;
      case 'ArrowUp':
        e.preventDefault();
        volumeSlider.value = Math.min(100, parseInt(volumeSlider.value) + 10);
        handleVolumeChange();
        showControls();
        break;
      case 'ArrowDown':
        e.preventDefault();
        volumeSlider.value = Math.max(0, parseInt(volumeSlider.value) - 10);
        handleVolumeChange();
        showControls();
        break;
      case 'm':
      case 'M':
        toggleMute();
        showControls();
        break;
      case 'f':
      case 'F':
        toggleFullscreen();
        break;
    }
  }

  /**
   * Format seconds to MM:SS or H:MM:SS.
   */
  function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds)) return '0:00';

    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = Math.floor(seconds % 60);

    if (h > 0) {
      return h + ':' + m.toString().padStart(2, '0') + ':' + s.toString().padStart(2, '0');
    }
    return m + ':' + s.toString().padStart(2, '0');
  }
})();
"""


def get_pdf_viewer_html() -> str:
    """
    Returns HTML for PDF viewer modal with PDF.js canvas and selectable text rendering.

    Features:
    - Canvas-based rendering with overlaid selectable text layer
    - Page navigation and zoom controls
    - Rectangular text selection tool
    - Selection context menu and accessible toolbar for dual copy actions
    - Live watch toggle with pulsing indicator
    - Scanned PDF (no text layer) status notification
    - Manual clipboard copy fallback dialog
    - Download button
    """
    return """
<!-- PDF Viewer Modal (z-10001, PDF.js rendering with selectable text layer) -->
<div id="pdf-viewer-modal" class="pdf-viewer-modal" style="display: none;">
  <div class="pdf-viewer-backdrop"></div>

  <!-- Header with controls -->
  <div class="pdf-viewer-header">
    <div class="pdf-viewer-title">
      <span id="pdf-filename" class="pdf-filename"></span>
    </div>
    <div class="pdf-viewer-controls">
      <button id="pdf-rect-select" class="pdf-viewer-btn pdf-rect-btn" aria-label="Rectangular text selection" title="Rectangular Selection (R)" aria-pressed="false">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 3">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
        </svg>
      </button>
      <button id="pdf-live-toggle" class="pdf-viewer-btn pdf-live-btn" aria-label="Toggle live watch" title="Live Watch">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12,6 12,12 16,14"/>
        </svg>
      </button>
      <a id="pdf-download" class="pdf-viewer-btn pdf-download-btn" href="" download aria-label="Download PDF" title="Download">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
        </svg>
      </a>
      <button id="pdf-close" class="pdf-viewer-btn pdf-close-btn" aria-label="Close viewer" title="Close (ESC)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- Floating Live Indicator (Independent of HUD) -->
  <div id="pdf-live-container" class="pdf-live-container" style="display: none;">
    <div class="pdf-live-indicator">
      <span class="pdf-live-dot"></span>
      <span class="pdf-live-text">LIVE</span>
    </div>
  </div>

  <!-- Notification Banner for scanned PDFs lacking text layer -->
  <div id="pdf-no-text-banner" class="pdf-no-text-banner" style="display: none;" role="status">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
    <span>Selectable text is unavailable in this document (scanned/raster only)</span>
  </div>

  <!-- Scrollable viewport -->
  <div id="pdf-viewport" class="pdf-viewport" tabindex="0" role="region" aria-label="PDF Document Pages">
    <!-- Multi-page container -->
    <div id="pdf-container" class="pdf-pages-container"></div>

    <div id="pdf-loading" class="pdf-loading">
      <div class="pdf-loading-spinner"></div>
      <span class="pdf-loading-text">Loading PDF...</span>
    </div>
  </div>

  <!-- Footer with page controls -->
  <div class="pdf-viewer-footer">
    <div class="pdf-page-controls">
      <button id="pdf-prev" class="pdf-nav-btn" aria-label="Previous page" title="Previous (←)">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
      </button>
      <span class="pdf-page-info">
        <span id="pdf-page-num">1</span> / <span id="pdf-page-count">1</span>
      </span>
      <button id="pdf-next" class="pdf-nav-btn" aria-label="Next page" title="Next (→)">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 18l6-6-6-6"/>
        </svg>
      </button>
    </div>
    <div class="pdf-zoom-controls">
      <!-- Smart Fit Button -->
      <button id="pdf-fit-toggle" class="pdf-nav-btn" aria-label="Toggle Fit" title="Fit to Width">
        <svg id="icon-fit-width" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 8l4 4-4 4M7 8l-4 4 4 4M21 12H3"/>
        </svg>
        <svg id="icon-fit-page" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: none;">
            <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
        </svg>
      </button>

      <div class="pdf-divider"></div>

      <button id="pdf-zoom-out" class="pdf-nav-btn" aria-label="Zoom out" title="Zoom Out (-)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="8" y1="11" x2="14" y2="11"/>
        </svg>
      </button>
      <span id="pdf-zoom-level" class="pdf-zoom-level">100%</span>
      <button id="pdf-zoom-in" class="pdf-nav-btn" aria-label="Zoom in" title="Zoom In (+)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- Custom Context Menu & Floating Selection Toolbar -->
  <div id="pdf-selection-menu" class="pdf-selection-menu" style="display: none;" role="menu" aria-label="Selection Actions">
    <button id="pdf-copy-btn" class="pdf-menu-item" role="menuitem" tabindex="0">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
      </svg>
      <span>Copy</span>
      <span class="pdf-menu-shortcut">Ctrl+C</span>
    </button>
    <button id="pdf-copy-nolinebreaks-btn" class="pdf-menu-item" role="menuitem" tabindex="0">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 6h16M4 12h16M4 18h7"/>
      </svg>
      <span>Copy without line breaks</span>
    </button>
    <button id="pdf-diag-btn" class="pdf-menu-item" role="menuitem" tabindex="0">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
      </svg>
      <span>Export Diag</span>
      <span class="pdf-menu-shortcut">Ctrl+Shift+D</span>
    </button>
  </div>

  <!-- Manual Copy Fallback Dialog (for HTTP origins or clipboard permission denial) -->
  <div id="pdf-copy-dialog" class="pdf-copy-dialog" style="display: none;" role="dialog" aria-modal="true" aria-labelledby="pdf-copy-dialog-title">
    <div class="pdf-copy-dialog-content">
      <div class="pdf-copy-dialog-header">
        <span id="pdf-copy-dialog-title" class="pdf-copy-dialog-title">Copy Selected Text</span>
        <button id="pdf-copy-dialog-close" class="pdf-dialog-close-btn" aria-label="Close dialog">&times;</button>
      </div>
      <p class="pdf-copy-dialog-desc">Direct clipboard writing is unavailable on this connection. You can copy the text below:</p>
      <textarea id="pdf-copy-dialog-textarea" class="pdf-copy-dialog-textarea" readonly spellcheck="false"></textarea>
      <div class="pdf-copy-dialog-actions">
        <span class="pdf-copy-dialog-hint">Press Ctrl+C (or Cmd+C) to copy</span>
        <button id="pdf-copy-dialog-done" class="pdf-dialog-btn">Done</button>
      </div>
    </div>
  </div>

  <!-- Status Toast for Clipboard / Selection feedback -->
  <div id="pdf-toast" class="pdf-toast" style="display: none;" role="status" aria-live="polite"></div>

  <!-- Touch Selection Handles -->
  <div id="pdf-touch-handle-start" class="pdf-touch-handle pdf-handle-start" style="display: none;" aria-hidden="true">
    <div class="pdf-handle-pin"></div>
  </div>
  <div id="pdf-touch-handle-end" class="pdf-touch-handle pdf-handle-end" style="display: none;" aria-hidden="true">
    <div class="pdf-handle-pin"></div>
  </div>
</div>
"""



def get_pdf_viewer_css() -> str:
    """
    Returns CSS for PDF viewer with Vortex aesthetic and precise Okular-style selection.

    Features:
    - Page wrapper for pixel-perfect canvas and text layer alignment
    - PDF.js 3.11.174 compatible text layer stylesheet
    - Okular-inspired compact blue highlights with crisp character rendering
    - Smooth temporary panning cursor states
    - Rectangular text selection visual overlay
    - Accessible context menu and manual copy dialog
    - Touch handles and mobile responsive rules
    """
    return """
/* ========================================
   PDF VIEWER MODAL
   ======================================== */

.pdf-viewer-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 10001;
  display: flex;
  flex-direction: column;
  font-family: var(--font-ui);
  overflow: hidden;
}

.pdf-viewer-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.95);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

/* Header (Ghost UI) */
.pdf-viewer-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.9) 0%, rgba(0, 0, 0, 0.7) 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  transition: transform 0.3s ease-in-out, opacity 0.3s ease-in-out;
}

/* Footer (Ghost UI) */
.pdf-viewer-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 20;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 2rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, rgba(0, 0, 0, 0.7) 100%);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  transition: transform 0.3s ease-in-out, opacity 0.3s ease-in-out;
}

/* Hidden HUD State */
.pdf-viewer-modal.hud-hidden .pdf-viewer-header {
  transform: translateY(-100%);
  opacity: 0;
  pointer-events: none;
}

.pdf-viewer-modal.hud-hidden .pdf-viewer-footer {
  transform: translateY(100%);
  opacity: 0;
  pointer-events: none;
}

/* Header Content */
.pdf-viewer-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: white;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.85rem;
}

.pdf-filename {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-viewer-controls {
  display: flex;
  gap: 0.5rem;
}

.pdf-viewer-btn {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  text-decoration: none;
}

.pdf-viewer-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
}

.pdf-rect-btn.active {
  background: rgba(61, 174, 233, 0.35);
  border-color: #3daee9;
  color: #3daee9;
}

.pdf-live-btn.active {
  background: rgba(76, 175, 80, 0.3);
  border-color: #4CAF50;
  color: #4CAF50;
}

.pdf-download-btn:hover {
  background: var(--accent-color);
  border-color: var(--accent-color);
}

.pdf-close-btn:hover {
  background: var(--error-color);
  border-color: var(--error-color);
}

/* Live Indicator */
.pdf-live-container {
  position: absolute;
  top: 4.5rem;
  right: 1.5rem;
  z-index: 15;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.pdf-viewer-modal.hud-hidden .pdf-live-container .pdf-live-indicator {
  opacity: 0.5;
}

.pdf-live-indicator {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  background: rgba(10, 10, 10, 0.85);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border: 1px solid rgba(76, 175, 80, 0.5);
  border-radius: 4px;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #4CAF50;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  pointer-events: auto;
  transition: opacity 0.3s ease;
}

.pdf-live-dot {
  width: 8px;
  height: 8px;
  background: #4CAF50;
  border-radius: 50%;
  animation: pdf-pulse 1.5s ease-in-out infinite;
}

@keyframes pdf-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

/* Scanned Document Warning Banner */
.pdf-no-text-banner {
  position: absolute;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 18;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(26, 26, 30, 0.94);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(255, 193, 7, 0.5);
  border-radius: 6px;
  padding: 6px 14px;
  color: #ffc107;
  font-size: 0.78rem;
  font-family: 'IBM Plex Mono', monospace;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}

/* Viewport & Pages */
.pdf-viewport {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: auto;
  background: #1e1e1e;
  display: flex;
  flex-direction: column;
  z-index: 5;
  scroll-behavior: smooth;
  padding-top: 60px;
  padding-bottom: 80px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
  outline: none;
}

.pdf-viewport:focus-visible {
  outline: 2px solid rgba(61, 174, 233, 0.4);
}

.pdf-viewport::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.pdf-viewport::-webkit-scrollbar-track {
  background: transparent;
}

.pdf-viewport::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.pdf-pages-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
  padding: 2rem;
  min-height: 100%;
  width: 100%;
  box-sizing: border-box;
}

/* Page wrapper containing canvas & text layer */
.pdf-page-wrapper {
  position: relative;
  background: white;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  margin: 0 auto;
  transform-origin: center top;
  user-select: none;
  -webkit-user-select: none;
  transition: transform 0.1s ease-out;
}

.pdf-page-canvas {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* PDF.js 3.11.174 Compatible Text Layer */
.textLayer {
  position: absolute;
  text-align: initial;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  opacity: 1;
  line-height: 1;
  -webkit-text-size-adjust: none;
  -moz-text-size-adjust: none;
  text-size-adjust: none;
  forced-color-adjust: none;
  transform-origin: 0 0;
  z-index: 2;
  user-select: none;
  -webkit-user-select: none;
}

.textLayer :is(span, br) {
  color: transparent;
  position: absolute;
  white-space: pre;
  cursor: text;
  transform-origin: 0% 0%;
}

.textLayer span {
  user-select: text;
  -webkit-user-select: text;
}

/* Text layer selection: default transparent for container and structural helpers */
.textLayer::selection {
  background: transparent;
}
.textLayer::-moz-selection {
  background: transparent;
}

.textLayer ::selection {
  background: transparent;
}
.textLayer ::-moz-selection {
  background: transparent;
}

/* Okular-inspired selection style: crisp, compact blue highlight strictly on selectable text spans */
.textLayer span::selection {
  background: rgba(61, 174, 233, 0.42);
  color: transparent;
}
.textLayer span::-moz-selection {
  background: rgba(61, 174, 233, 0.42);
  color: transparent;
}

/* Marked-content structural tags have no dimensions and must not show selection highlights */
.textLayer span.markedContent {
  top: 0;
  height: 0;
}
.textLayer span.markedContent::selection {
  background: transparent;
}
.textLayer span.markedContent::-moz-selection {
  background: transparent;
}

/* Line breaks (br) are structural elements with transparent selection highlight to prevent margin artifacts while retaining clipboard line breaks */
.textLayer br {
  pointer-events: none;
  user-select: text;
  -webkit-user-select: text;
}
.textLayer br::selection {
  background: transparent;
}
.textLayer br::-moz-selection {
  background: transparent;
}

/* Sentinel elements below text content must never trigger visual selection */
.textLayer .endOfContent {
  display: block;
  position: absolute;
  inset: 100% 0 0;
  z-index: -1;
  cursor: default;
  user-select: none;
  -webkit-user-select: none;
}
.textLayer .endOfContent::selection {
  background: transparent;
}
.textLayer .endOfContent::-moz-selection {
  background: transparent;
}

/* Active drag selection: endOfContent expands to top:0 covering entire layer to prevent erratic whitespace jumping */
.pdf-viewport.selecting .textLayer .endOfContent,
.textLayer.selecting .endOfContent {
  top: 0;
}

/* Temporary Space-Drag Panning */
.pdf-viewport.panning-ready {
  cursor: grab !important;
}
.pdf-viewport.panning-ready .textLayer {
  pointer-events: none !important;
}
.pdf-viewport.panning-active {
  cursor: grabbing !important;
  user-select: none !important;
  -webkit-user-select: none !important;
}
.pdf-viewport.panning-active .textLayer {
  pointer-events: none !important;
}

/* Rectangular Selection Tool Mode */
.pdf-viewport.rect-select-active {
  cursor: crosshair !important;
}
.pdf-viewport.rect-select-active .textLayer {
  pointer-events: none !important;
}
.pdf-rect-box {
  position: absolute;
  border: 1.5px dashed #3daee9;
  background: rgba(61, 174, 233, 0.22);
  pointer-events: none;
  z-index: 10;
  box-sizing: border-box;
}

/* Context Menu & Selection Toolbar */
.pdf-selection-menu {
  position: fixed;
  z-index: 30;
  display: flex;
  flex-direction: column;
  background: rgba(22, 22, 26, 0.96);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.55);
  padding: 4px;
  gap: 2px;
  min-width: 220px;
}

.pdf-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #f0f0f0;
  font-size: 0.82rem;
  font-family: var(--font-ui, sans-serif);
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease, color 0.15s ease;
}

.pdf-menu-item:hover, .pdf-menu-item:focus {
  background: rgba(61, 174, 233, 0.3);
  color: #ffffff;
  outline: none;
}

.pdf-menu-shortcut {
  margin-left: auto;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.45);
  font-family: monospace;
}

/* Status Toast */
.pdf-toast {
  position: fixed;
  bottom: 90px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(22, 22, 26, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #ffffff;
  padding: 8px 18px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-family: var(--font-ui, sans-serif);
  z-index: 10005;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  pointer-events: none;
}

/* Manual Copy Fallback Dialog */
.pdf-copy-dialog {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 10006;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
}

.pdf-copy-dialog-content {
  background: #1e1e24;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  width: 90%;
  max-width: 520px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
}

.pdf-copy-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: white;
  font-weight: 600;
  font-size: 0.95rem;
}

.pdf-dialog-close-btn {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0 4px;
}

.pdf-dialog-close-btn:hover { color: white; }

.pdf-copy-dialog-desc {
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.8rem;
  margin: 0;
}

.pdf-copy-dialog-textarea {
  width: 100%;
  height: 140px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: white;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.8rem;
  padding: 8px;
  resize: vertical;
  box-sizing: border-box;
}

.pdf-copy-dialog-textarea:focus {
  outline: 1px solid #3daee9;
  border-color: #3daee9;
}

.pdf-copy-dialog-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pdf-copy-dialog-hint {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
}

.pdf-dialog-btn {
  background: var(--accent-color, #3daee9);
  color: white;
  border: none;
  border-radius: 6px;
  padding: 6px 16px;
  font-size: 0.82rem;
  cursor: pointer;
}

/* Touch Selection Handles */
.pdf-touch-handle {
  position: absolute;
  width: 24px;
  height: 24px;
  z-index: 15;
  pointer-events: auto;
  touch-action: none;
}

.pdf-handle-pin {
  width: 14px;
  height: 14px;
  background: #3daee9;
  border: 2px solid white;
  border-radius: 50%;
  box-shadow: 0 2px 6px rgba(0,0,0,0.4);
  position: absolute;
  top: 5px;
  left: 5px;
}

.pdf-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: white;
  z-index: 20;
  pointer-events: none;
}

.pdf-loading-spinner {
  width: 40px;
  height: 40px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: pdf-spin 0.8s linear infinite;
}

@keyframes pdf-spin {
  to { transform: rotate(360deg); }
}

.pdf-loading-text {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* Footer Controls */
.pdf-page-controls,
.pdf-zoom-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.pdf-divider {
  width: 1px;
  height: 24px;
  background: rgba(255,255,255,0.2);
  margin: 0 0.5rem;
}

.pdf-nav-btn {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pdf-nav-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2);
}

.pdf-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.pdf-page-info,
.pdf-zoom-level {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.8);
  min-width: 70px;
  text-align: center;
}

/* Mobile */
@media (max-width: 600px) {
  .pdf-viewer-header,
  .pdf-viewer-footer {
    padding: 0.5rem;
  }

  .pdf-filename {
    max-width: 120px;
    font-size: 0.75rem;
    display: none;
  }

  .pdf-viewer-btn,
  .pdf-nav-btn {
    width: 32px;
    height: 32px;
  }

  .pdf-viewer-footer {
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .pdf-page-info {
    min-width: 50px;
  }

  .pdf-live-container {
    top: 3.5rem;
    right: 0.5rem;
  }
}
"""



def get_pdf_viewer_js() -> str:
    """
    Returns JavaScript for PDF viewer with PDF.js and precise text selection.

    Features:
    - Multi-page scrollable viewport with page wrapper & text layer
    - Lazy rendering with IntersectionObserver
    - Multi-column reading order detection
    - Character-precision drag selection & Okular styling
    - Triple-click visual-line selection
    - Shift-click selection extension from original anchor
    - Edge auto-scrolling during drag selection
    - Space + drag temporary panning without stealing input focus
    - Rectangular text selection tool
    - Dual copy actions: Copy and Copy without line breaks
    - Context menu and accessible toolbar with honest clipboard handling
    - Touch gesture arbitration (long press, pinch zoom, handles)
    - Full lifecycle management & scanned PDF detection
    """
    return r"""
/* ========================================
   PDF VIEWER MODULE (PDF.js Text Selection)
   ======================================== */

(function() {
  'use strict';

  // PDF.js CDN URLs (v3.11.174)
  var PDFJS_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
  var PDFJS_WORKER_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  // Constants
  var SCALE_STEP = 0.25;
  var MIN_SCALE = 0.5;
  var MAX_SCALE = 4.0;
  var DEFAULT_SCALE = 1.5;
  var MAX_CONCURRENT_RENDERS = 1;
  var BUFFER_PAGES = 1;

  function getDevicePixelRatio() {
    return Math.min((typeof window !== 'undefined' && window.devicePixelRatio) || 1, 2.0);
  }

  // State
  var state = {
    isOpen: false,
    isLive: false,
    pdfUrl: '',
    pdfDoc: null,
    loadingTask: null,
    docGeneration: 0,
    scale: DEFAULT_SCALE,
    pages: [],
    renderTimeout: null,
    scrollThrottleRAF: null,
    observer: null,

    // Concurrency & Virtualization
    renderQueue: [],
    activeRenders: 0,
    visiblePages: new Set(),
    pinnedPages: new Set(),

    // Diagnostics metrics (incrementally maintained without whole-document scanning)
    diagTotalBackingStorePixels: 0,
    diagRetainedCanvases: 0,
    diagMountedTextLayers: 0,
    diagIndexedTextItems: 0,
    diagGeometryCacheEntries: 0,

    // Auto-fit Logic
    fitMode: 'width', // 'width', 'page', 'manual'
    pageOriginalWidth: 0,
    pageOriginalHeight: 0,
    resizeObserver: null,

    // Ghost UI
    hudTimeout: null,

    // Selection State
    selectionAnchor: null, // { node, offset }
    lastPointerPosition: null, // { x, y }
    autoScrollRAF: null,
    autoScrollSpeed: 0,
    isSelecting: false,
    cachedViewportRect: null,
    dragTraceEnabled: false,
    dragTraceBuffer: [],
    dragEventSeq: 0,
    lastDragEventTime: 0,

    // Temporary Panning
    isSpacePressed: false,
    isPanning: false,
    panStartX: 0,
    panStartY: 0,
    panScrollLeft: 0,
    panScrollTop: 0,

    // Rectangular Selection Mode
    rectSelectMode: false,
    rectBox: null, // { pageWrapper, pageNum, startX, startY, currentX, currentY }
    rectEl: null,
    selectedRectText: '',

    // Touch Support
    longPressTimer: null,
    isHandleDragging: false,
    activeHandle: null,
    touchStartPos: null,
    pinchStartDist: 0,
    pinchStartScale: 1.0,

    // Toast Timer
    toastTimer: null
  };

  // DOM Elements
  var BUILD_ID = 'vortex-pdf-20261121.diag7';
  var modal, backdrop, viewport, pagesContainer;
  var loading, loadingText;
  var filenameEl, liveIndicatorContainer, liveIndicator, liveToggle, downloadBtn, closeBtn;
  var prevBtn, nextBtn, pageNumEl, pageCountEl;
  var zoomInBtn, zoomOutBtn, zoomLevelEl;
  var fitToggleBtn, iconFitWidth, iconFitPage;
  var rectSelectBtn, noTextBanner;
  var selectionMenu, copyBtn, copyNoLineBreaksBtn, diagBtn;
  var copyDialog, copyDialogTextarea, copyDialogClose, copyDialogDone;
  var toastEl, handleStart, handleEnd;

  var pdfjsLoaded = false;

  document.addEventListener('DOMContentLoaded', initPdfViewer);

  function initPdfViewer() {
    modal = document.getElementById('pdf-viewer-modal');
    if (!modal) return;
    modal.setAttribute('data-viewer-build', BUILD_ID);
    console.log('[VortexPdfViewer ' + BUILD_ID + '] initialized');

    backdrop = modal.querySelector('.pdf-viewer-backdrop');
    viewport = document.getElementById('pdf-viewport');
    pagesContainer = document.getElementById('pdf-container');
    loading = document.getElementById('pdf-loading');
    loadingText = modal.querySelector('.pdf-loading-text');

    filenameEl = document.getElementById('pdf-filename');
    liveIndicatorContainer = document.getElementById('pdf-live-container');
    liveIndicator = modal.querySelector('.pdf-live-indicator');
    liveToggle = document.getElementById('pdf-live-toggle');
    downloadBtn = document.getElementById('pdf-download');
    closeBtn = document.getElementById('pdf-close');

    prevBtn = document.getElementById('pdf-prev');
    nextBtn = document.getElementById('pdf-next');
    pageNumEl = document.getElementById('pdf-page-num');
    pageCountEl = document.getElementById('pdf-page-count');

    zoomInBtn = document.getElementById('pdf-zoom-in');
    zoomOutBtn = document.getElementById('pdf-zoom-out');
    zoomLevelEl = document.getElementById('pdf-zoom-level');

    fitToggleBtn = document.getElementById('pdf-fit-toggle');
    iconFitWidth = document.getElementById('icon-fit-width');
    iconFitPage = document.getElementById('icon-fit-page');

    rectSelectBtn = document.getElementById('pdf-rect-select');
    noTextBanner = document.getElementById('pdf-no-text-banner');

    selectionMenu = document.getElementById('pdf-selection-menu');
    copyBtn = document.getElementById('pdf-copy-btn');
    copyNoLineBreaksBtn = document.getElementById('pdf-copy-nolinebreaks-btn');
    diagBtn = document.getElementById('pdf-diag-btn');

    copyDialog = document.getElementById('pdf-copy-dialog');
    copyDialogTextarea = document.getElementById('pdf-copy-dialog-textarea');
    copyDialogClose = document.getElementById('pdf-copy-dialog-close');
    copyDialogDone = document.getElementById('pdf-copy-dialog-done');

    toastEl = document.getElementById('pdf-toast');
    handleStart = document.getElementById('pdf-touch-handle-start');
    handleEnd = document.getElementById('pdf-touch-handle-end');

    // Controls listeners
    closeBtn.addEventListener('click', close);
    backdrop.addEventListener('click', close);
    liveToggle.addEventListener('click', toggleLive);

    prevBtn.addEventListener('click', function() { scrollToPage(getCurrentPageNum() - 1); });
    nextBtn.addEventListener('click', function() { scrollToPage(getCurrentPageNum() + 1); });

    zoomInBtn.addEventListener('click', zoomIn);
    zoomOutBtn.addEventListener('click', zoomOut);
    fitToggleBtn.addEventListener('click', toggleFit);

    if (rectSelectBtn) {
      rectSelectBtn.addEventListener('click', function() { toggleRectSelect(); });
    }

    if (copyBtn) {
      copyBtn.addEventListener('click', function(e) {
        e.preventDefault();
        copySelection(false);
      });
    }

    if (copyNoLineBreaksBtn) {
      copyNoLineBreaksBtn.addEventListener('click', function(e) {
        e.preventDefault();
        copySelection(true);
      });
    }

    if (diagBtn) {
      diagBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        exportSelectionDiagnostic();
      });
    }

    if (copyDialogClose) copyDialogClose.addEventListener('click', hideCopyDialog);
    if (copyDialogDone) copyDialogDone.addEventListener('click', hideCopyDialog);

    // Viewport & document events (throttled scroll)
    viewport.addEventListener('scroll', handleViewportScroll);
    viewport.addEventListener('wheel', handleWheel, { passive: false });

    document.addEventListener('keydown', handleKeydown);
    document.addEventListener('keyup', handleKeyup);
    window.addEventListener('blur', handleWindowBlur);
    document.addEventListener('vortex-file-changed', handleFileChanged);

    // Pointer & Mouse interactions
    pagesContainer.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    pagesContainer.addEventListener('contextmenu', handleContextMenu);

    // Touch interactions
    pagesContainer.addEventListener('touchstart', handleTouchStart, { passive: false });
    window.addEventListener('touchmove', handleTouchMove, { passive: false });
    window.addEventListener('touchend', handleTouchEnd, { passive: false });
    window.addEventListener('touchcancel', handleTouchEnd, { passive: false });

    // Document selection change to track anchor & touch handles
    document.addEventListener('selectionchange', handleSelectionChange);

    // Lazy rendering observer
    state.observer = new IntersectionObserver(handleIntersection, {
      root: viewport,
      rootMargin: '200px 0px',
      threshold: 0
    });

    // ResizeObserver for Auto-Fit
    state.resizeObserver = new ResizeObserver(function(entries) {
      if (!state.isOpen || state.fitMode === 'manual') return;
      clearTimeout(state.renderTimeout);
      state.renderTimeout = setTimeout(function() {
        calculateSmartFit();
      }, 100);
    });
    state.resizeObserver.observe(viewport);

    // Ghost UI Listeners
    modal.addEventListener('mousemove', resetHudTimer);
    modal.addEventListener('touchstart', resetHudTimer, { passive: true });
    modal.addEventListener('click', resetHudTimer);

    window.VortexPdfViewer = {
      buildId: BUILD_ID,
      open: open,
      close: close,
      toggleRectSelect: toggleRectSelect,
      copySelection: copySelection,
      processReadingOrder: processReadingOrder,
      normalizeCopyText: normalizeCopyText,
      getDiagnostics: getDiagnostics,
      updateVirtualization: updateVirtualization,
      captureSelectionDiagnostic: captureSelectionDiagnostic,
      exportSelectionDiagnostic: exportSelectionDiagnostic,
      getSelectionDiagnostic: captureSelectionDiagnostic,
      enableDragTrace: function(enable) {
        state.dragTraceEnabled = !!enable;
        if (!state.dragTraceEnabled) {
          state.dragTraceBuffer = [];
        }
        return state.dragTraceEnabled;
      },
      getDragTrace: function() {
        return state.dragTraceBuffer ? state.dragTraceBuffer.slice() : [];
      },
      isDragTraceEnabled: function() {
        return !!state.dragTraceEnabled;
      }
    };
    window.capturePdfSelectionDiagnostic = exportSelectionDiagnostic;
  }

  /* --- Helper: Check if element is an editable control --- */
  function isEditable(el) {
    if (!el) return false;
    var tag = el.tagName;
    return el.isContentEditable || tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
  }

  /* --- Virtualization, Pinning, and Memory Management --- */
  function updatePinnedPages() {
    state.pinnedPages.clear();
    if (!state.isOpen) return;

    var startPage = null;
    var endPage = null;

    if (state.selectionAnchor && state.selectionAnchor.node) {
      var el = state.selectionAnchor.node.nodeType === 1 ? state.selectionAnchor.node : state.selectionAnchor.node.parentElement;
      var wrap = el ? el.closest('.pdf-page-wrapper') : null;
      if (wrap) {
        startPage = parseInt(wrap.getAttribute('data-page-num') || (wrap.dataset && wrap.dataset.pageNum), 10);
      }
    }

    var sel = (typeof window !== 'undefined' && window.getSelection) ? window.getSelection() : null;
    if (sel && sel.rangeCount > 0 && !sel.isCollapsed) {
      try {
        var range = sel.getRangeAt(0);
        var startEl = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
        var endEl = range.endContainer.nodeType === 1 ? range.endContainer : range.endContainer.parentElement;

        var startWrap = startEl ? startEl.closest('.pdf-page-wrapper') : null;
        var endWrap = endEl ? endEl.closest('.pdf-page-wrapper') : null;

        if (startWrap) {
          var sp = parseInt(startWrap.getAttribute('data-page-num') || (startWrap.dataset && startWrap.dataset.pageNum), 10);
          if (startPage === null || sp < startPage) startPage = sp;
        }
        if (endWrap) {
          var ep = parseInt(endWrap.getAttribute('data-page-num') || (endWrap.dataset && endWrap.dataset.pageNum), 10);
          endPage = ep;
        }
      } catch (err) {}
    }

    if (startPage !== null) {
      if (endPage === null) endPage = startPage;
      var minP = Math.min(startPage, endPage);
      var maxP = Math.max(startPage, endPage);
      for (var i = minP; i <= maxP; i++) {
        state.pinnedPages.add(i);
      }
    }
  }

  function getVisibleAndBufferPages() {
    if (!viewport || !state.isOpen || state.pages.length <= 1) return { visible: [], buffer: [] };

    var vTop = viewport.scrollTop || 0;
    var vHeight = viewport.clientHeight || 800;
    var vBottom = vTop + vHeight;
    var visible = [];
    var buffer = [];

    var numPages = state.pages.length - 1;
    var firstVis = -1;
    var lastVis = -1;

    for (var i = 1; i <= numPages; i++) {
      var p = state.pages[i];
      if (!p || !p.wrapper) continue;
      var top = p.wrapper.offsetTop || ((i - 1) * (state.pageOriginalHeight || 792) * state.scale);
      var height = p.wrapper.offsetHeight || ((state.pageOriginalHeight || 792) * state.scale);
      var bottom = top + height;

      if (bottom >= vTop && top <= vBottom) {
        visible.push(i);
        if (firstVis === -1) firstVis = i;
        lastVis = i;
      }
    }

    if (visible.length === 0) {
      firstVis = 1;
      lastVis = 1;
      visible.push(1);
    }

    var bufferStart = Math.max(1, firstVis - BUFFER_PAGES);
    var bufferEnd = Math.min(numPages, lastVis + BUFFER_PAGES);

    for (var j = bufferStart; j <= bufferEnd; j++) {
      buffer.push(j);
    }

    return { visible: visible, buffer: buffer };
  }

  function evictPageCanvas(p) {
    if (!p) return;
    if (p.renderTask && typeof p.renderTask.cancel === 'function') {
      try { p.renderTask.cancel(); } catch (e) {}
      p.renderTask = null;
    }
    if (p.hasCanvasAllocated && p.canvas) {
      var pixels = p.canvas.width * p.canvas.height;
      state.diagTotalBackingStorePixels = Math.max(0, state.diagTotalBackingStorePixels - pixels);
      state.diagRetainedCanvases = Math.max(0, state.diagRetainedCanvases - 1);
      p.canvas.width = 0;
      p.canvas.height = 0;
      p.hasCanvasAllocated = false;
    }
    p.rendered = false;
    p.rendering = false;
  }

  function unmountPageTextLayer(p) {
    if (!p) return;
    if (state.pinnedPages.has(p.pageNum)) return;

    if (p.textRenderTask && typeof p.textRenderTask.cancel === 'function') {
      try { p.textRenderTask.cancel(); } catch (e) {}
      p.textRenderTask = null;
    }
    if (p.textLayerMounted && p.textLayer) {
      p.textLayer.innerHTML = '';
      state.diagMountedTextLayers = Math.max(0, state.diagMountedTextLayers - 1);
      state.diagIndexedTextItems = Math.max(0, state.diagIndexedTextItems - (p.textItemCount || 0));
      p.textLayerMounted = false;
    }
  }

  function updateVirtualization() {
    if (!state.isOpen || !state.pdfDoc) return;

    updatePinnedPages();

    var ranges = getVisibleAndBufferPages();
    var activeSet = new Set(ranges.buffer);

    for (var i = 1; i < state.pages.length; i++) {
      var p = state.pages[i];
      if (!p) continue;
      if (!activeSet.has(i)) {
        evictPageCanvas(p);
        if (!state.pinnedPages.has(i)) {
          unmountPageTextLayer(p);
        }
      }
    }

    ranges.buffer.forEach(function(pageNum) {
      var isVis = ranges.visible.indexOf(pageNum) !== -1;
      var priority = isVis ? 1000 - Math.abs(pageNum - ranges.visible[0]) : 500 - Math.abs(pageNum - ranges.visible[0]);
      queuePageRender(pageNum, priority);
    });
  }

  function queuePageRender(pageNum, priority) {
    var p = state.pages[pageNum];
    if (!p) return;
    if (p.rendering) return; // Prevent duplicate queueing while render is in progress
    if (p.rendered && p.renderedScale === state.scale && p.hasCanvasAllocated) return;

    var existingIdx = -1;
    for (var i = 0; i < state.renderQueue.length; i++) {
      if (state.renderQueue[i].pageNum === pageNum) {
        existingIdx = i;
        break;
      }
    }

    if (existingIdx !== -1) {
      state.renderQueue[existingIdx].priority = priority;
    } else {
      state.renderQueue.push({ pageNum: pageNum, priority: priority });
    }

    state.renderQueue.sort(function(a, b) { return b.priority - a.priority; });
    processRenderQueue();
  }

  function processRenderQueue() {
    if (!state.isOpen || !state.pdfDoc) return;
    if (state.activeRenders >= MAX_CONCURRENT_RENDERS) return;
    if (state.renderQueue.length === 0) return;

    var currentGen = state.docGeneration;
    var job = state.renderQueue.shift();
    var pageNum = job.pageNum;
    var p = state.pages[pageNum];

    if (!p || p.rendering) {
      processRenderQueue();
      return;
    }

    var ranges = getVisibleAndBufferPages();
    var activeSet = new Set(ranges.buffer);
    if (!activeSet.has(pageNum) && !state.pinnedPages.has(pageNum)) {
      processRenderQueue();
      return;
    }

    if (p.rendered && p.renderedScale === state.scale && p.hasCanvasAllocated) {
      processRenderQueue();
      return;
    }

    state.activeRenders++;

    executeRenderPage(pageNum, currentGen).then(function() {
      state.activeRenders = Math.max(0, state.activeRenders - 1);
      if (state.isOpen && currentGen === state.docGeneration) {
        processRenderQueue();
      }
    }).catch(function() {
      state.activeRenders = Math.max(0, state.activeRenders - 1);
      if (state.isOpen && currentGen === state.docGeneration) {
        processRenderQueue();
      }
    });
  }

  function cancelAllActiveRenders() {
    state.pages.forEach(function(p) {
      if (p) {
        if (p.renderTask && typeof p.renderTask.cancel === 'function') {
          try { p.renderTask.cancel(); } catch (e) {}
          p.renderTask = null;
        }
        if (p.textRenderTask && typeof p.textRenderTask.cancel === 'function') {
          try { p.textRenderTask.cancel(); } catch (e) {}
          p.textRenderTask = null;
        }
        p.rendering = false;
      }
    });
    // Note: Do NOT synchronously set state.activeRenders = 0 here.
    // Active renders decrement when their promises reject/settle asynchronously,
    // ensuring concurrency remains bounded throughout cancellation.
  }

  function executeRenderPage(pageNum, generation) {
    var p = state.pages[pageNum];
    if (!p || !state.pdfDoc) return Promise.resolve();

    if (p.renderTask && typeof p.renderTask.cancel === 'function') {
      try { p.renderTask.cancel(); } catch (e) {}
      p.renderTask = null;
    }
    if (p.textRenderTask && typeof p.textRenderTask.cancel === 'function') {
      try { p.textRenderTask.cancel(); } catch (e) {}
      p.textRenderTask = null;
    }

    p.rendering = true;

    return state.pdfDoc.getPage(pageNum).then(function(page) {
      if (!state.isOpen || generation !== state.docGeneration) {
        p.rendering = false;
        return;
      }

      var dpr = getDevicePixelRatio();
      var canvasViewport = page.getViewport({ scale: state.scale * dpr });
      var displayViewport = page.getViewport({ scale: state.scale });

      var canvas = p.canvas;
      var ctx = canvas.getContext('2d');

      var oldPixels = p.hasCanvasAllocated ? (canvas.width * canvas.height) : 0;
      var newWidth = Math.floor(canvasViewport.width);
      var newHeight = Math.floor(canvasViewport.height);
      var newPixels = newWidth * newHeight;

      canvas.width = newWidth;
      canvas.height = newHeight;

      if (!p.hasCanvasAllocated) {
        state.diagRetainedCanvases++;
        p.hasCanvasAllocated = true;
      }
      state.diagTotalBackingStorePixels += (newPixels - oldPixels);

      var cssW = Math.floor(displayViewport.width) + 'px';
      var cssH = Math.floor(displayViewport.height) + 'px';
      canvas.style.width = cssW;
      canvas.style.height = cssH;
      p.wrapper.style.width = cssW;
      p.wrapper.style.height = cssH;

      var renderContext = {
        canvasContext: ctx,
        viewport: canvasViewport
      };

      var renderTask = page.render(renderContext);
      p.renderTask = renderTask;

      return renderTask.promise.then(function() {
        p.renderTask = null;
        if (!state.isOpen || generation !== state.docGeneration) return;
        return renderTextLayerForPage(page, displayViewport, p, generation);
      }).then(function() {
        p.rendering = false;
        if (!state.isOpen || generation !== state.docGeneration) return;
        p.rendered = true;
        p.renderedScale = state.scale;
        checkScannedPdfStatus();
      }).catch(function(err) {
        p.renderTask = null;
        p.rendering = false;
        if (err && err.name === 'RenderingCancelledException') return;
      });
    }).catch(function(err) {
      p.rendering = false;
      if (err && err.name === 'RenderingCancelledException') return;
    });
  }

  function getDiagnostics() {
    var jsHeap = null;
    if (typeof window !== 'undefined' && window.performance && window.performance.memory) {
      jsHeap = {
        usedJSHeapSize: window.performance.memory.usedJSHeapSize,
        totalJSHeapSize: window.performance.memory.totalJSHeapSize,
        jsHeapSizeLimit: window.performance.memory.jsHeapSizeLimit
      };
    }

    var ranges = getVisibleAndBufferPages();

    var retainedDetails = [];
    for (var i = 1; i < state.pages.length; i++) {
      var p = state.pages[i];
      if (p && p.hasCanvasAllocated && p.canvas && p.canvas.width > 0) {
        retainedDetails.push({
          pageNum: i,
          width: p.canvas.width,
          height: p.canvas.height,
          pixels: p.canvas.width * p.canvas.height
        });
      }
    }

    return {
      buildId: BUILD_ID,
      activeRenderJobs: state.activeRenders,
      queuedRenderJobs: state.renderQueue.length,
      retainedCanvases: state.diagRetainedCanvases,
      totalBackingStorePixels: state.diagTotalBackingStorePixels,
      estimatedCanvasMemoryBytes: state.diagTotalBackingStorePixels * 4,
      retainedCanvasDetails: retainedDetails,
      mountedTextLayers: state.diagMountedTextLayers,
      indexedTextItems: state.diagIndexedTextItems,
      pinnedPages: Array.from(state.pinnedPages),
      geometryCacheEntries: state.diagGeometryCacheEntries,
      activeDocuments: state.pdfDoc ? 1 : 0,
      hasActivePdfDocument: state.pdfDoc !== null,
      hasActiveLoadingTask: state.loadingTask !== null,
      inferredActiveWorkers: state.pdfDoc !== null ? 1 : (state.loadingTask !== null ? 1 : 0),
      activeAnimationLoops: (state.autoScrollRAF !== null ? 1 : 0) + (state.scrollThrottleRAF !== null ? 1 : 0),
      currentScale: state.scale,
      devicePixelRatio: getDevicePixelRatio(),
      visiblePages: ranges.visible,
      bufferPages: ranges.buffer,
      totalDocumentPages: state.pages.length > 1 ? (state.pages.length - 1) : 0,
      jsHeap: jsHeap
    };
  }

  /* --- Selection Diagnostic & Layout Introspection --- */

  function describeNode(node) {
    if (!node) return null;
    var desc = {
      nodeType: node.nodeType,
      nodeName: node.nodeName
    };
    if (node.nodeType === 1) {
      desc.tagName = node.tagName;
      desc.className = node.className || '';
      desc.id = node.id || null;
      desc.role = node.getAttribute ? node.getAttribute('role') : null;
      desc.parentTagName = node.parentElement ? node.parentElement.tagName : null;
      desc.parentClassName = node.parentElement ? (node.parentElement.className || '') : null;
    } else if (node.nodeType === 3) {
      desc.length = node.textContent ? node.textContent.length : 0;
      desc.parentTagName = node.parentElement ? node.parentElement.tagName : null;
      desc.parentClassName = node.parentElement ? (node.parentElement.className || '') : null;
      if (node.parentElement && node.parentElement.parentElement) {
        desc.grandparentTagName = node.parentElement.parentElement.tagName;
        desc.grandparentClassName = node.parentElement.parentElement.className || '';
      }
    }
    return desc;
  }

  function rectToObj(r) {
    if (!r) return null;
    return {
      left: Math.round(r.left * 100) / 100,
      top: Math.round(r.top * 100) / 100,
      right: Math.round(r.right * 100) / 100,
      bottom: Math.round(r.bottom * 100) / 100,
      width: Math.round(r.width * 100) / 100,
      height: Math.round(r.height * 100) / 100,
      x: Math.round((r.x !== undefined ? r.x : r.left) * 100) / 100,
      y: Math.round((r.y !== undefined ? r.y : r.top) * 100) / 100
    };
  }

  function findPageWrapper(node) {
    var curr = node;
    while (curr && curr !== document.body) {
      if (curr.classList && curr.classList.contains && curr.classList.contains('pdf-page-wrapper')) {
        return curr;
      }
      curr = curr.parentElement;
    }
    return null;
  }

  function captureSelectionDiagnostic() {
    var sel = window.getSelection ? window.getSelection() : null;
    var dpr = getDevicePixelRatio();
    var diag = {
      buildId: BUILD_ID,
      timestamp: new Date().toISOString(),
      environment: {
        devicePixelRatio: dpr,
        userAgent: (typeof navigator !== 'undefined' && navigator.userAgent) ? navigator.userAgent : 'unknown',
        windowInnerWidth: typeof window !== 'undefined' ? window.innerWidth : 0,
        windowInnerHeight: typeof window !== 'undefined' ? window.innerHeight : 0,
        scale: state.scale,
        fitMode: state.fitMode,
        pdfUrl: state.pdfUrl,
        currentPage: state.currentPage,
        totalDocumentPages: state.pages ? (state.pages.length - 1) : 0,
        viewportScroll: viewport ? {
          scrollTop: viewport.scrollTop,
          scrollLeft: viewport.scrollLeft,
          scrollWidth: viewport.scrollWidth,
          scrollHeight: viewport.scrollHeight,
          clientWidth: viewport.clientWidth,
          clientHeight: viewport.clientHeight
        } : null
      },
      selection: null,
      ranges: [],
      pages: [],
      intersectedNodes: [],
      dragTrace: {
        enabled: !!state.dragTraceEnabled,
        isSelecting: !!state.isSelecting,
        eventCount: state.dragTraceBuffer ? state.dragTraceBuffer.length : 0,
        events: state.dragTraceBuffer ? state.dragTraceBuffer.slice() : []
      }
    };

    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
      diag.selection = {
        status: !sel ? 'no_selection_api' : (sel.rangeCount === 0 ? 'zero_ranges' : 'collapsed'),
        isCollapsed: sel ? (sel.isCollapsed !== undefined ? Boolean(sel.isCollapsed) : true) : true,
        rangeCount: sel ? sel.rangeCount : 0
      };
      return diag;
    }

    diag.selection = {
      status: 'active',
      isCollapsed: sel.isCollapsed,
      rangeCount: sel.rangeCount,
      type: sel.type,
      anchorNode: describeNode(sel.anchorNode),
      anchorOffset: sel.anchorOffset,
      focusNode: describeNode(sel.focusNode),
      focusOffset: sel.focusOffset,
      selectedText: sel.toString ? sel.toString() : '',
      endpointDetails: null
    };

    var targetTextNode = null;
    var fNode = sel.focusNode;
    if (fNode) {
      if (fNode.nodeType === 3) {
        targetTextNode = fNode;
      } else if (fNode.nodeType === 1 && fNode.childNodes && fNode.childNodes.length > 0) {
        var childIdx = Math.max(0, Math.min(sel.focusOffset, fNode.childNodes.length - 1));
        if (fNode.childNodes[childIdx].nodeType === 3) {
          targetTextNode = fNode.childNodes[childIdx];
        }
      }
    }

    if (targetTextNode) {
      var textStr = targetTextNode.textContent || '';
      var fOff = sel.focusOffset;
      var spanEl = (targetTextNode.nodeType === 1) ? targetTextNode : targetTextNode.parentElement;
      var spanRect = (spanEl && spanEl.getBoundingClientRect) ? rectToObj(spanEl.getBoundingClientRect()) : null;
      var spanStyle = null;
      if (spanEl && typeof window !== 'undefined' && window.getComputedStyle) {
        var csSp = window.getComputedStyle(spanEl);
        spanStyle = {
          fontFamily: csSp.fontFamily,
          fontSize: csSp.fontSize,
          transform: csSp.transform,
          transformOrigin: csSp.transformOrigin,
          left: csSp.left,
          top: csSp.top,
          width: csSp.width,
          height: csSp.height
        };
      }

      // Character geometry for up to 6 characters around focus endpoint
      var charGeometry = [];
      var startCharIdx = Math.max(0, fOff - 3);
      var endCharIdx = Math.min(textStr.length, fOff + 3);

      if (typeof document !== 'undefined' && document.createRange) {
        for (var ci = startCharIdx; ci < endCharIdx; ci++) {
          try {
            var charRng = document.createRange();
            charRng.setStart(targetTextNode, ci);
            charRng.setEnd(targetTextNode, ci + 1);
            var cRects = charRng.getClientRects ? charRng.getClientRects() : null;
            var primaryRect = (cRects && cRects.length > 0) ? rectToObj(cRects[0]) : null;
            charGeometry.push({
              index: ci,
              char: textStr.charAt(ci),
              isFocusBoundary: (ci === fOff || ci === fOff - 1),
              clientRect: primaryRect
            });
          } catch (e) {}
        }
      }

      diag.selection.endpointDetails = {
        nodeText: textStr.length > 100 ? (textStr.substring(0, 100) + '...') : textStr,
        fullLength: textStr.length,
        focusOffset: fOff,
        isAtTextEnd: (fOff >= textStr.length),
        characterAtOffset: (fOff < textStr.length) ? textStr.charAt(fOff) : null,
        characterBeforeOffset: (fOff > 0) ? textStr.charAt(fOff - 1) : null,
        spanRect: spanRect,
        spanComputedStyle: spanStyle,
        nearbyCharacterGeometry: charGeometry
      };
    }

    var affectedPages = new Set();

    for (var rIdx = 0; rIdx < sel.rangeCount; rIdx++) {
      var range = sel.getRangeAt(rIdx);
      var bRect = rectToObj(range.getBoundingClientRect ? range.getBoundingClientRect() : null);
      var cRects = [];
      if (range.getClientRects) {
        var domRectList = range.getClientRects();
        for (var cr = 0; cr < domRectList.length; cr++) {
          cRects.push(rectToObj(domRectList[cr]));
        }
      }

      diag.ranges.push({
        rangeIndex: rIdx,
        startContainer: describeNode(range.startContainer),
        startOffset: range.startOffset,
        endContainer: describeNode(range.endContainer),
        endOffset: range.endOffset,
        collapsed: range.collapsed,
        boundingClientRect: bRect,
        clientRects: cRects
      });

      var pStart = findPageWrapper(range.startContainer);
      if (pStart) {
        var numStart = parseInt(pStart.getAttribute('data-page-num') || (pStart.dataset && pStart.dataset.pageNum), 10);
        if (numStart) affectedPages.add(numStart);
      }
      var pEnd = findPageWrapper(range.endContainer);
      if (pEnd) {
        var numEnd = parseInt(pEnd.getAttribute('data-page-num') || (pEnd.dataset && pEnd.dataset.pageNum), 10);
        if (numEnd) affectedPages.add(numEnd);
      }
    }

    if (affectedPages.size === 0 && state.currentPage) {
      affectedPages.add(state.currentPage);
    }

    affectedPages.forEach(function(pageNum) {
      var pState = state.pages ? state.pages[pageNum] : null;
      if (!pState || !pState.wrapper) return;
      var wRect = pState.wrapper.getBoundingClientRect ? rectToObj(pState.wrapper.getBoundingClientRect()) : null;
      var cRect = pState.canvas && pState.canvas.getBoundingClientRect ? rectToObj(pState.canvas.getBoundingClientRect()) : null;
      var tRect = pState.textLayer && pState.textLayer.getBoundingClientRect ? rectToObj(pState.textLayer.getBoundingClientRect()) : null;

      var textLayerStyle = null;
      var textLayerSelectionStyle = null;
      if (pState.textLayer && typeof window !== 'undefined' && window.getComputedStyle) {
        var cs = window.getComputedStyle(pState.textLayer);
        textLayerStyle = {
          position: cs.position,
          transform: cs.transform,
          overflow: cs.overflow,
          userSelect: cs.userSelect,
          webkitUserSelect: cs.webkitUserSelect,
          pointerEvents: cs.pointerEvents,
          width: cs.width,
          height: cs.height,
          left: cs.left,
          top: cs.top
        };
        try {
          var csTLSel = window.getComputedStyle(pState.textLayer, '::selection');
          if (csTLSel) {
            textLayerSelectionStyle = {
              backgroundColor: csTLSel.backgroundColor,
              color: csTLSel.color
            };
          }
        } catch (e) {}
      }

      var wrapperSelectionStyle = null;
      if (pState.wrapper && typeof window !== 'undefined' && window.getComputedStyle) {
        try {
          var csWSel = window.getComputedStyle(pState.wrapper, '::selection');
          if (csWSel) {
            wrapperSelectionStyle = {
              backgroundColor: csWSel.backgroundColor,
              color: csWSel.color
            };
          }
        } catch (e) {}
      }

      diag.pages.push({
        pageNum: pageNum,
        wrapperRect: wRect,
        wrapperSelectionStyle: wrapperSelectionStyle,
        canvasRect: cRect,
        canvasWidth: pState.canvas ? pState.canvas.width : 0,
        canvasHeight: pState.canvas ? pState.canvas.height : 0,
        textLayerRect: tRect,
        textLayerComputedStyle: textLayerStyle,
        textLayerSelectionStyle: textLayerSelectionStyle
      });

      if (pState.textLayer) {
        var children = pState.textLayer.childNodes;
        for (var i = 0; i < children.length; i++) {
          var child = children[i];
          var isIntersected = false;
          var rangeDetails = [];

          for (var ri = 0; ri < sel.rangeCount; ri++) {
            var rng = sel.getRangeAt(ri);
            var intersects = false;
            try {
              if (rng.intersectsNode) {
                intersects = rng.intersectsNode(child);
              } else if (typeof document !== 'undefined' && document.createRange) {
                var testRng = document.createRange();
                testRng.selectNode(child);
                intersects = (rng.compareBoundaryPoints(Range.END_TO_START, testRng) < 0 &&
                              rng.compareBoundaryPoints(Range.START_TO_END, testRng) > 0);
              }
            } catch (e) {
              intersects = false;
            }

            if (intersects) {
              isIntersected = true;
              var isStart = (rng.startContainer === child || (child.contains && child.contains(rng.startContainer)));
              var isEnd = (rng.endContainer === child || (child.contains && child.contains(rng.endContainer)));
              var sOff = 0;
              var eOff = child.textContent ? child.textContent.length : 0;
              if (isStart) {
                sOff = rng.startOffset;
              }
              if (isEnd) {
                eOff = rng.endOffset;
              }
              rangeDetails.push({
                rangeIndex: ri,
                isStart: isStart,
                startOffset: sOff,
                isEnd: isEnd,
                endOffset: eOff
              });
            }
          }

          if (isIntersected) {
            var nodeRect = child.getBoundingClientRect ? rectToObj(child.getBoundingClientRect()) : null;
            var nodeCRects = [];
            if (child.getClientRects) {
              var ncrs = child.getClientRects();
              for (var nci = 0; nci < ncrs.length; nci++) {
                nodeCRects.push(rectToObj(ncrs[nci]));
              }
            }

            var subRangeRects = [];
            if (typeof document !== 'undefined' && document.createRange) {
              var targetTextNode = null;
              if (child.nodeType === 3) {
                targetTextNode = child;
              } else if (child.firstChild && child.firstChild.nodeType === 3) {
                targetTextNode = child.firstChild;
              }
              if (targetTextNode) {
                for (var rd = 0; rd < rangeDetails.length; rd++) {
                  try {
                    var maxLen = targetTextNode.textContent ? targetTextNode.textContent.length : 0;
                    var startChar = Math.max(0, Math.min(rangeDetails[rd].startOffset, maxLen));
                    var endChar = Math.max(startChar, Math.min(rangeDetails[rd].endOffset, maxLen));
                    if (startChar < endChar) {
                      var subRng = document.createRange();
                      subRng.setStart(targetTextNode, startChar);
                      subRng.setEnd(targetTextNode, endChar);
                      var subCRs = subRng.getClientRects();
                      for (var sci = 0; sci < subCRs.length; sci++) {
                        subRangeRects.push(rectToObj(subCRs[sci]));
                      }
                    }
                  } catch (e) {}
                }
              }
            }

            var elemStyle = null;
            var targetEl = (child.nodeType === 1) ? child : child.parentElement;
            if (targetEl && typeof window !== 'undefined' && window.getComputedStyle) {
              var csE = window.getComputedStyle(targetEl);
              elemStyle = {
                position: csE.position,
                left: csE.left,
                top: csE.top,
                width: csE.width,
                height: csE.height,
                transform: csE.transform,
                transformOrigin: csE.transformOrigin,
                display: csE.display,
                visibility: csE.visibility,
                opacity: csE.opacity,
                userSelect: csE.userSelect,
                webkitUserSelect: csE.webkitUserSelect,
                pointerEvents: csE.pointerEvents,
                fontSize: csE.fontSize,
                fontFamily: csE.fontFamily,
                lineHeight: csE.lineHeight,
                whiteSpace: csE.whiteSpace
              };
            }

            var elemSelectionStyle = null;
            if (targetEl && typeof window !== 'undefined' && window.getComputedStyle) {
              try {
                var csElSel = window.getComputedStyle(targetEl, '::selection');
                if (csElSel) {
                  elemSelectionStyle = {
                    backgroundColor: csElSel.backgroundColor,
                    color: csElSel.color
                  };
                }
              } catch (e) {}
            }

            var textPreview = '';
            if (child.textContent) {
              textPreview = child.textContent.length > 80 ? (child.textContent.substring(0, 80) + '...') : child.textContent;
            }

            var attributes = {};
            if (child.attributes) {
              for (var a = 0; a < child.attributes.length; a++) {
                var attr = child.attributes[a];
                attributes[attr.name] = attr.value;
              }
            }

            diag.intersectedNodes.push({
              childIndex: i,
              nodeType: child.nodeType,
              nodeName: child.nodeName,
              className: child.nodeType === 1 ? (child.className || '') : '',
              parentTagName: child.parentElement ? child.parentElement.tagName : null,
              parentClassName: child.parentElement ? (child.parentElement.className || '') : null,
              attributes: attributes,
              textPreview: textPreview,
              rangeEndpoints: rangeDetails,
              boundingClientRect: nodeRect,
              clientRects: nodeCRects,
              subRangeClientRects: subRangeRects,
              computedStyle: elemStyle,
              selectionStyle: elemSelectionStyle
            });
          }
        }
      }
    });

    diag.dragTrace = {
      enabled: !!state.dragTraceEnabled,
      isSelecting: !!state.isSelecting,
      eventCount: state.dragTraceBuffer ? state.dragTraceBuffer.length : 0,
      events: state.dragTraceBuffer ? state.dragTraceBuffer.slice() : []
    };

    return diag;
  }

  function exportSelectionDiagnostic() {
    var diag = captureSelectionDiagnostic();
    var jsonStr = JSON.stringify(diag, null, 2);
    console.log('[Vortex Selection Diagnostic ' + BUILD_ID + ']\n' + jsonStr);
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(jsonStr).then(function() {
        showToast('Selection diagnostic copied to clipboard (' + BUILD_ID + ')');
      }).catch(function() {
        showManualCopyDialog(jsonStr, 'Vortex Selection Diagnostic (' + BUILD_ID + ')');
      });
    } else {
      showManualCopyDialog(jsonStr, 'Vortex Selection Diagnostic (' + BUILD_ID + ')');
    }
    return diag;
  }

  function handleViewportScroll() {
    state.cachedViewportRect = null;
    if (state.scrollThrottleRAF) return;
    state.scrollThrottleRAF = requestAnimationFrame(function() {
      state.scrollThrottleRAF = null;
      updateCurrentPageIndicator();
      updateVirtualization();
    });
  }

  /* --- Ghost UI Logic --- */
  function resetHudTimer(e) {
    if (state.isSelecting) return;
    modal.classList.remove('hud-hidden');
    clearTimeout(state.hudTimeout);
    state.hudTimeout = setTimeout(function() {
      if (state.isOpen && !state.rectSelectMode && selectionMenu.style.display === 'none') {
        modal.classList.add('hud-hidden');
      }
    }, 2500);
  }

  function toggleLive() {
    state.isLive = !state.isLive;
    if (state.isLive) {
      liveToggle.classList.add('active');
      liveIndicatorContainer.style.display = 'block';
      fetch('/api/watch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: state.pdfUrl })
      }).catch(function(err) {
        console.error('Failed to start file watcher:', err);
      });
    } else {
      liveToggle.classList.remove('active');
      liveIndicatorContainer.style.display = 'none';
      fetch('/api/watch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: '' })
      }).catch(function(err) {
        console.error('Failed to stop file watcher:', err);
      });
    }
  }

  function handleFileChanged(e) {
    if (!state.isOpen || !state.isLive) return;
    if (document.visibilityState === 'visible') {
      clearTextSelection();
      loadPdf(state.pdfUrl, true);
    }
  }

  /* --- Smart Fit Logic --- */
  function toggleFit() {
    if (state.fitMode === 'width' || state.fitMode === 'manual') {
      state.fitMode = 'page';
    } else {
      state.fitMode = 'width';
    }
    updateFitIcon();
    calculateSmartFit();
  }

  function updateFitIcon() {
    if (state.fitMode === 'page') {
      iconFitWidth.style.display = 'none';
      iconFitPage.style.display = 'block';
      fitToggleBtn.title = "Fit to Page";
    } else {
      iconFitWidth.style.display = 'block';
      iconFitPage.style.display = 'none';
      fitToggleBtn.title = "Fit to Width";
    }
  }

  function calculateSmartFit() {
    if (state.fitMode === 'manual' || !state.pageOriginalWidth || !state.pageOriginalHeight) return;

    var viewportW = viewport.clientWidth - 40;
    var viewportH = viewport.clientHeight - 40;
    var scale = 1;

    if (state.fitMode === 'width') {
      scale = viewportW / state.pageOriginalWidth;
    } else if (state.fitMode === 'page') {
      var heightScale = viewportH / state.pageOriginalHeight;
      var widthScale = viewportW / state.pageOriginalWidth;
      scale = Math.min(heightScale, widthScale);
    }
    setZoom(scale, true);
  }

  function setZoom(newScale, isAutomated) {
    if (!isAutomated) {
      state.fitMode = 'manual';
      updateFitIcon();
    }

    var oldScale = state.scale;
    state.scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScale));
    updateZoomLevel();

    var ratio = state.scale / oldScale;
    state.pages.forEach(function(p) {
      if (p && p.wrapper) {
        var currentW = parseFloat(p.wrapper.style.width) || (state.pageOriginalWidth * oldScale);
        var currentH = parseFloat(p.wrapper.style.height) || (state.pageOriginalHeight * oldScale);
        var newW = currentW * ratio;
        var newH = currentH * ratio;
        p.wrapper.style.width = newW + 'px';
        p.wrapper.style.height = newH + 'px';
        if (p.canvas) {
          p.canvas.style.width = newW + 'px';
          p.canvas.style.height = newH + 'px';
        }
        if (p.textLayer) {
          p.textLayer.style.width = newW + 'px';
          p.textLayer.style.height = newH + 'px';
          p.textLayer.style.setProperty('--scale-factor', state.scale);
        }
        p.rendered = false;
      }
    });

    cancelAllActiveRenders();
    state.renderQueue = [];

    clearTimeout(state.renderTimeout);
    state.renderTimeout = setTimeout(function() {
      updateVirtualization();
    }, 150);
  }

  function zoomIn() { setZoom(state.scale + SCALE_STEP); }
  function zoomOut() { setZoom(state.scale - SCALE_STEP); }
  function resetZoom() {
    state.fitMode = 'width';
    updateFitIcon();
    calculateSmartFit();
  }

  function updateZoomLevel() {
    zoomLevelEl.textContent = Math.round(state.scale * 100) + '%';
  }

  function loadPdfJs(callback) {
    if (pdfjsLoaded && typeof pdfjsLib !== 'undefined') {
      callback();
      return;
    }
    var script = document.createElement('script');
    script.src = PDFJS_CDN;
    script.onload = function() {
      pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER_CDN;
      pdfjsLoaded = true;
      callback();
    };
    script.onerror = function() {
      console.error('Failed to load PDF.js script from CDN');
      loadingText.textContent = 'Error loading PDF engine';
    };
    document.head.appendChild(script);
  }

  function open(pdfUrl, filename) {
    state.pdfUrl = pdfUrl;
    state.isOpen = true;
    state.fitMode = 'width';
    updateFitIcon();

    filenameEl.textContent = filename || pdfUrl.split('/').pop();
    downloadBtn.href = pdfUrl;
    downloadBtn.download = filename || '';

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Reset UI & Submodes
    toggleRectSelect(false);
    hideSelectionMenu();
    hideCopyDialog();
    if (noTextBanner) noTextBanner.style.display = 'none';
    resetHudTimer();

    showLoading('Loading PDF...');
    loadPdfJs(function() {
      loadPdf(pdfUrl);
    });
  }

  function close() {
    state.isOpen = false;
    modal.style.display = 'none';
    document.body.style.overflow = '';

    // Stop active processes
    finishSelecting();
    stopAutoScroll();
    if (state.scrollThrottleRAF) {
      cancelAnimationFrame(state.scrollThrottleRAF);
      state.scrollThrottleRAF = null;
    }
    clearTextSelection();
    toggleRectSelect(false);
    hideSelectionMenu();
    hideCopyDialog();

    clearTimeout(state.hudTimeout);
    clearTimeout(state.renderTimeout);
    clearTimeout(state.longPressTimer);
    clearTimeout(state.toastTimer);

    state.renderQueue = [];
    cancelAllActiveRenders();

    if (state.observer) state.observer.disconnect();

    state.docGeneration = (state.docGeneration || 0) + 1;

    state.pages.forEach(function(p) {
      if (p && p.canvas) {
        p.canvas.width = 0;
        p.canvas.height = 0;
      }
    });

    if (state.pdfDoc && typeof state.pdfDoc.destroy === 'function') {
      try { state.pdfDoc.destroy(); } catch (e) {}
    }
    state.pdfDoc = null;

    pagesContainer.innerHTML = '';
    state.pages = [];

    state.diagTotalBackingStorePixels = 0;
    state.diagRetainedCanvases = 0;
    state.diagMountedTextLayers = 0;
    state.diagIndexedTextItems = 0;
    state.pinnedPages.clear();
    state.visiblePages.clear();

    if (state.isLive) {
      fetch('/api/watch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: '' })
      }).catch(function(err) {
        console.error('Failed to stop file watcher:', err);
      });
      state.isLive = false;
      liveToggle.classList.remove('active');
      liveIndicatorContainer.style.display = 'none';
    }
  }

  function showLoading(msg) {
    loading.style.display = 'flex';
    loadingText.textContent = msg;
  }

  function hideLoading() {
    loading.style.display = 'none';
  }

  function loadPdf(url, keepScroll) {
    var savedScroll = keepScroll ? viewport.scrollTop : 0;

    state.docGeneration = (state.docGeneration || 0) + 1;
    var currentGen = state.docGeneration;

    cancelAllActiveRenders();
    state.renderQueue = [];

    if (state.pdfDoc && typeof state.pdfDoc.destroy === 'function') {
      try { state.pdfDoc.destroy(); } catch (e) {}
    }
    state.pdfDoc = null;

    state.diagTotalBackingStorePixels = 0;
    state.diagRetainedCanvases = 0;
    state.diagMountedTextLayers = 0;
    state.diagIndexedTextItems = 0;
    state.pinnedPages.clear();
    state.visiblePages.clear();

    pagesContainer.innerHTML = '';
    state.pages = [];
    if (state.observer) state.observer.disconnect();

    var loadingTask = pdfjsLib.getDocument(url + '?t=' + Date.now());

    loadingTask.promise.then(function(pdf) {
      if (!state.isOpen || currentGen !== state.docGeneration) {
        try { pdf.destroy(); } catch (e) {}
        return;
      }

      state.pdfDoc = pdf;
      var numPages = pdf.numPages;
      pageCountEl.textContent = numPages;

      state.pages = [];
      pagesContainer.innerHTML = '';

      pdf.getPage(1).then(function(firstPage) {
        if (!state.isOpen || currentGen !== state.docGeneration) return;

        var baseViewport = firstPage.getViewport({ scale: 1.0 });
        state.pageOriginalWidth = baseViewport.width;
        state.pageOriginalHeight = baseViewport.height;

        for (var i = 1; i <= numPages; i++) {
          var pageWrapper = document.createElement('div');
          pageWrapper.className = 'pdf-page-wrapper';
          pageWrapper.setAttribute('data-page-num', i);
          if (pageWrapper.dataset) pageWrapper.dataset.pageNum = i;
          pageWrapper.style.width = state.pageOriginalWidth + 'px';
          pageWrapper.style.height = state.pageOriginalHeight + 'px';

          var canvas = document.createElement('canvas');
          canvas.className = 'pdf-page-canvas';
          canvas.setAttribute('data-page-num', i);
          if (canvas.dataset) canvas.dataset.pageNum = i;
          canvas.width = 0;
          canvas.height = 0;

          var textLayer = document.createElement('div');
          textLayer.className = 'textLayer';
          textLayer.setAttribute('data-page-num', i);
          if (textLayer.dataset) textLayer.dataset.pageNum = i;

          pageWrapper.appendChild(canvas);
          pageWrapper.appendChild(textLayer);
          pagesContainer.appendChild(pageWrapper);

          if (state.observer) state.observer.observe(pageWrapper);

          state.pages[i] = {
            pageNum: i,
            wrapper: pageWrapper,
            canvas: canvas,
            textLayer: textLayer,
            rendered: false,
            renderedScale: 0,
            hasCanvasAllocated: false,
            textLayerMounted: false,
            renderTask: null,
            textRenderTask: null,
            processedContent: null,
            hasText: null,
            textItemCount: 0
          };
        }

        hideLoading();
        calculateSmartFit();

        if (keepScroll && savedScroll) {
          viewport.scrollTop = savedScroll;
        }

        updateVirtualization();
      });
    }).catch(function(error) {
      if (!state.isOpen || currentGen !== state.docGeneration) return;
      console.error('PDF load error:', error);
      loadingText.textContent = 'Error loading PDF';
    });
  }

  function handleIntersection(entries) {
    if (!state.isOpen) return;
    var changed = false;
    entries.forEach(function(entry) {
      var pageNum = parseInt(entry.target.getAttribute('data-page-num') || (entry.target.dataset && entry.target.dataset.pageNum), 10);
      if (!pageNum) return;
      if (entry.isIntersecting) {
        if (!state.visiblePages.has(pageNum)) {
          state.visiblePages.add(pageNum);
          changed = true;
        }
      } else {
        if (state.visiblePages.has(pageNum)) {
          state.visiblePages.delete(pageNum);
          changed = true;
        }
      }
    });

    if (changed) {
      updateVirtualization();
    }
  }

  function renderPage(pageNum, force) {
    if (!state.isOpen || !state.pdfDoc) return;
    if (force) {
      var p = state.pages[pageNum];
      if (p) p.rendered = false;
    }
    queuePageRender(pageNum, 1000);
  }

  function renderTextLayerForPage(page, displayViewport, pageState, generation) {
    var textLayer = pageState.textLayer;
    textLayer.innerHTML = '';
    textLayer.style.width = displayViewport.width + 'px';
    textLayer.style.height = displayViewport.height + 'px';
    textLayer.style.setProperty('--scale-factor', displayViewport.scale);

    var textPromise = pageState.processedContent
      ? Promise.resolve(pageState.processedContent)
      : page.getTextContent().then(function(textContent) {
          if (!textContent || !textContent.items || textContent.items.length === 0) {
            pageState.hasText = false;
            return null;
          }
          pageState.hasText = true;
          pageState.processedContent = textContent;
          return textContent;
        });

    return textPromise.then(function(processedContent) {
      if (!state.isOpen || generation !== state.docGeneration || !processedContent) {
        return;
      }

      var textDivs = [];
      var renderPromise = null;

      if (typeof pdfjsLib.renderTextLayer === 'function') {
        var task = pdfjsLib.renderTextLayer({
          textContentSource: processedContent,
          textContent: processedContent,
          container: textLayer,
          viewport: displayViewport,
          textDivs: textDivs
        });
        pageState.textRenderTask = task;
        renderPromise = task.promise;
      } else if (pdfjsLib.TextLayer) {
        var textLayerObj = new pdfjsLib.TextLayer({
          textContentSource: processedContent,
          container: textLayer,
          viewport: displayViewport
        });
        pageState.textRenderTask = textLayerObj;
        renderPromise = textLayerObj.render();
      } else {
        renderPromise = Promise.resolve();
      }

      return renderPromise.then(function() {
        pageState.textRenderTask = null;
        if (!pageState.textLayerMounted) {
          pageState.textLayerMounted = true;
          state.diagMountedTextLayers++;
        }
        var count = processedContent.items ? processedContent.items.length : 0;
        state.diagIndexedTextItems += (count - (pageState.textItemCount || 0));
        pageState.textItemCount = count;
      }).catch(function(err) {
        pageState.textRenderTask = null;
        if (err && err.name === 'RenderingCancelledException') return;
      });
    });
  }

  /* --- Column-Aware Reading Order Processor --- */
  function processReadingOrder(textContent, viewport) {
    if (!textContent || !textContent.items || textContent.items.length < 4) {
      return textContent;
    }
    var items = textContent.items.slice();

    var enriched = items.map(function(item, idx) {
      var tx = item.transform ? item.transform[4] : 0;
      var ty = item.transform ? item.transform[5] : 0;
      var w = item.width || 0;
      var h = item.height || (item.transform ? Math.abs(item.transform[0]) : 10);
      return {
        item: item,
        idx: idx,
        x: tx,
        y: ty,
        w: w,
        h: h,
        right: tx + w,
        top: ty + h,
        str: item.str || ''
      };
    });

    var nonEmpty = enriched.filter(function(e) { return e.str.trim().length > 0; });
    if (nonEmpty.length < 4) return textContent;

    var minX = Infinity, maxX = -Infinity;
    nonEmpty.forEach(function(e) {
      if (e.x < minX) minX = e.x;
      if (e.right > maxX) maxX = e.right;
    });

    var totalW = maxX - minX;
    if (totalW <= 50) {
      return sortSingleColumn(textContent, enriched);
    }

    // Check for a vertical gutter between 25% and 75% of page width
    var midStart = minX + totalW * 0.25;
    var midEnd = minX + totalW * 0.75;
    var gutterCandidates = [];
    var step = 4;
    var currentStart = null;

    for (var x = midStart; x <= midEnd; x += step) {
      var hasOverlap = false;
      for (var i = 0; i < nonEmpty.length; i++) {
        var it = nonEmpty[i];
        if (it.w < totalW * 0.75 && it.x < x + step && it.right > x) {
          hasOverlap = true;
          break;
        }
      }
      if (!hasOverlap) {
        if (currentStart === null) currentStart = x;
      } else {
        if (currentStart !== null) {
          var gw = x - currentStart;
          if (gw >= 12) gutterCandidates.push({ start: currentStart, end: x, width: gw });
          currentStart = null;
        }
      }
    }
    if (currentStart !== null) {
      var gw = midEnd - currentStart;
      if (gw >= 12) gutterCandidates.push({ start: currentStart, end: midEnd, width: gw });
    }

    if (gutterCandidates.length === 0) {
      return sortSingleColumn(textContent, enriched);
    }

    gutterCandidates.sort(function(a, b) { return b.width - a.width; });
    var bestGutter = gutterCandidates[0];
    var gutterMid = (bestGutter.start + bestGutter.end) / 2;

    var col1 = [], col2 = [], headers = [], footers = [];
    var colItems = nonEmpty.filter(function(e) { return e.w < totalW * 0.75; });
    var colMinY = Infinity, colMaxY = -Infinity;
    colItems.forEach(function(e) {
      if (e.y < colMinY) colMinY = e.y;
      if (e.y > colMaxY) colMaxY = e.y;
    });

    enriched.forEach(function(e) {
      if (e.w >= totalW * 0.75 || e.y > colMaxY + 12 || e.y < colMinY - 12) {
        if (e.y > (colMinY + colMaxY) / 2) headers.push(e);
        else footers.push(e);
      } else {
        var midX = e.x + e.w / 2;
        if (midX < gutterMid) col1.push(e);
        else col2.push(e);
      }
    });

    if (col1.length < 2 || col2.length < 2) {
      return sortSingleColumn(textContent, enriched);
    }

    function sortGroup(arr) {
      return arr.sort(function(a, b) {
        if (Math.abs(b.y - a.y) > 4) return b.y - a.y;
        return a.x - b.x;
      });
    }

    var resultEnriched = sortGroup(headers).concat(
      sortGroup(col1),
      sortGroup(col2),
      sortGroup(footers)
    );

    return {
      items: resultEnriched.map(function(e) { return e.item; }),
      styles: textContent.styles
    };
  }

  function sortSingleColumn(textContent, enriched) {
    var sorted = enriched.slice().sort(function(a, b) {
      if (Math.abs(b.y - a.y) > 4) return b.y - a.y;
      return a.x - b.x;
    });
    return {
      items: sorted.map(function(e) { return e.item; }),
      styles: textContent.styles
    };
  }

  function checkScannedPdfStatus() {
    if (!state.isOpen) return;
    var allChecked = true;
    var anyText = false;
    for (var i = 1; i < state.pages.length; i++) {
      var p = state.pages[i];
      if (p && p.hasText === true) {
        anyText = true;
        break;
      }
      if (p && p.hasText === null) allChecked = false;
    }
    if (noTextBanner) {
      if (anyText) {
        noTextBanner.style.display = 'none';
      } else if (allChecked && state.pages.length > 1) {
        noTextBanner.style.display = 'flex';
      }
    }
  }

  /* --- Pointer / Mouse Interactions --- */
  function finishSelecting() {
    state.isSelecting = false;
    state.cachedViewportRect = null;
    if (viewport) {
      viewport.classList.remove('selecting');
    }
    if (pagesContainer) {
      var selectingLayers = pagesContainer.querySelectorAll('.textLayer.selecting');
      for (var s = 0; s < selectingLayers.length; s++) {
        selectingLayers[s].classList.remove('selecting');
      }
    }
  }

  function recordDragTraceEvent(type, extra) {
    if (!state.dragTraceEnabled) return;
    var now = typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now();
    var sel = (typeof window !== 'undefined' && window.getSelection) ? window.getSelection() : null;
    var selInfo = null;
    if (sel) {
      selInfo = {
        isCollapsed: sel.isCollapsed,
        rangeCount: sel.rangeCount,
        anchor: sel.anchorNode ? {
          nodeType: sel.anchorNode.nodeType,
          nodeName: sel.anchorNode.nodeName,
          parentTag: sel.anchorNode.parentElement ? sel.anchorNode.parentElement.tagName : null,
          offset: sel.anchorOffset
        } : null,
        focus: sel.focusNode ? {
          nodeType: sel.focusNode.nodeType,
          nodeName: sel.focusNode.nodeName,
          parentTag: sel.focusNode.parentElement ? sel.focusNode.parentElement.tagName : null,
          offset: sel.focusOffset,
          textLength: sel.focusNode.textContent ? sel.focusNode.textContent.length : null,
          isAtEnd: (sel.focusNode.textContent) ? (sel.focusOffset >= sel.focusNode.textContent.length) : false
        } : null
      };
    }

    var deltaMs = state.lastDragEventTime ? Math.round((now - state.lastDragEventTime) * 100) / 100 : 0;
    state.lastDragEventTime = now;

    var entry = {
      seq: ++state.dragEventSeq,
      type: type,
      timestamp: Math.round(now * 100) / 100,
      deltaMs: deltaMs,
      pointer: extra && typeof extra.x === 'number' ? { x: extra.x, y: extra.y } : null,
      selection: selInfo,
      isSelecting: state.isSelecting,
      pinnedCount: state.pinnedPages ? state.pinnedPages.size : 0
    };

    state.dragTraceBuffer.push(entry);
    if (state.dragTraceBuffer.length > 50) {
      state.dragTraceBuffer.shift();
    }
  }

  function handleMouseDown(e) {
    if (!state.isOpen) return;

    // Dismiss selection menu if clicking outside of it
    if (selectionMenu.style.display !== 'none' && !selectionMenu.contains(e.target)) {
      hideSelectionMenu();
    }

    // 1. Temporary Space Panning
    if (state.isSpacePressed && e.button === 0) {
      e.preventDefault();
      state.isPanning = true;
      state.panStartX = e.clientX;
      state.panStartY = e.clientY;
      state.panScrollLeft = viewport.scrollLeft;
      state.panScrollTop = viewport.scrollTop;
      viewport.classList.add('panning-active');
      return;
    }

    // 2. Rectangular Selection Mode
    if (state.rectSelectMode && e.button === 0) {
      e.preventDefault();
      var pageWrapper = e.target.closest('.pdf-page-wrapper');
      if (!pageWrapper) return;

      var pRect = pageWrapper.getBoundingClientRect();
      var startX = e.clientX - pRect.left;
      var startY = e.clientY - pRect.top;

      clearSelectionRect();

      var rectEl = document.createElement('div');
      rectEl.className = 'pdf-rect-box';
      rectEl.style.left = startX + 'px';
      rectEl.style.top = startY + 'px';
      rectEl.style.width = '0px';
      rectEl.style.height = '0px';
      pageWrapper.appendChild(rectEl);

      state.rectEl = rectEl;
      state.rectBox = {
        pageWrapper: pageWrapper,
        startX: startX,
        startY: startY,
        currentX: startX,
        currentY: startY
      };
      return;
    }

    // 3. Shift-Click Selection Extension
    if (e.shiftKey && e.button === 0) {
      var extended = handleShiftClick(e);
      if (extended) {
        e.preventDefault();
        return;
      }
    }

    // 4. Triple-Click Visual-Line Selection
    if (e.detail === 3 && e.button === 0) {
      var span = e.target.closest('.textLayer span');
      if (span) {
        e.preventDefault();
        selectVisualLine(span);
        return;
      }
    }

    // 5. Standard drag selection start
    if (e.button === 0) {
      state.isSelecting = true;
      if (viewport) {
        viewport.classList.add('selecting');
        state.cachedViewportRect = viewport.getBoundingClientRect();
      }
      var targetTextLayer = (e && e.target && e.target.closest) ? e.target.closest('.textLayer') : null;
      if (targetTextLayer) {
        targetTextLayer.classList.add('selecting');
      }
      var caret = getCaretPositionFromPoint(e.clientX, e.clientY);
      if (caret && caret.node) {
        state.selectionAnchor = { node: caret.node, offset: caret.offset };
      } else {
        state.selectionAnchor = null;
      }
      recordDragTraceEvent('mousedown', { x: e.clientX, y: e.clientY });
    }
  }

  function handleMouseMove(e) {
    if (!state.isOpen) return;
    state.lastPointerPosition = { x: e.clientX, y: e.clientY };

    // Panning
    if (state.isPanning) {
      viewport.scrollLeft = state.panScrollLeft - (e.clientX - state.panStartX);
      viewport.scrollTop = state.panScrollTop - (e.clientY - state.panStartY);
      return;
    }

    // Rectangular Selection Drag
    if (state.rectSelectMode && state.rectBox && state.rectEl) {
      var pRect = state.rectBox.pageWrapper.getBoundingClientRect();
      var curX = Math.max(0, Math.min(pRect.width, e.clientX - pRect.left));
      var curY = Math.max(0, Math.min(pRect.height, e.clientY - pRect.top));

      state.rectBox.currentX = curX;
      state.rectBox.currentY = curY;

      var left = Math.min(state.rectBox.startX, curX);
      var top = Math.min(state.rectBox.startY, curY);
      var width = Math.abs(curX - state.rectBox.startX);
      var height = Math.abs(curY - state.rectBox.startY);

      state.rectEl.style.left = left + 'px';
      state.rectEl.style.top = top + 'px';
      state.rectEl.style.width = width + 'px';
      state.rectEl.style.height = height + 'px';
      return;
    }

    // Edge Auto-Scrolling during normal drag selection
    if (e.buttons & 1 && !state.rectSelectMode && !state.isSpacePressed) {
      if (!state.isSelecting) {
        state.isSelecting = true;
        if (viewport) {
          viewport.classList.add('selecting');
          if (!state.cachedViewportRect) state.cachedViewportRect = viewport.getBoundingClientRect();
        }
      }
      checkEdgeAutoScroll(e.clientX, e.clientY);
      recordDragTraceEvent('mousemove', { x: e.clientX, y: e.clientY });
    } else {
      stopAutoScroll();
      if (state.isSelecting && !(e.buttons & 1)) {
        finishSelecting();
      }
    }
  }

  function handleMouseUp(e) {
    if (!state.isOpen) return;

    if (state.isPanning) {
      state.isPanning = false;
      viewport.classList.remove('panning-active');
    }

    stopAutoScroll();

    if (state.isSelecting) {
      recordDragTraceEvent('mouseup', { x: e.clientX, y: e.clientY });
      finishSelecting();
    }

    // Finish Rectangular Selection
    if (state.rectSelectMode && state.rectBox && state.rectEl) {
      var left = Math.min(state.rectBox.startX, state.rectBox.currentX);
      var top = Math.min(state.rectBox.startY, state.rectBox.currentY);
      var width = Math.abs(state.rectBox.currentX - state.rectBox.startX);
      var height = Math.abs(state.rectBox.currentY - state.rectBox.startY);

      if (width > 5 && height > 5) {
        var boxRect = { left: left, top: top, right: left + width, bottom: top + height };
        var text = extractRectText(state.rectBox.pageWrapper, boxRect);
        state.selectedRectText = text;
        if (text) {
          showSelectionMenu(e.clientX, e.clientY);
        }
      }
      state.rectBox = null;
    }
  }

  function handleContextMenu(e) {
    if (!state.isOpen) return;

    // Check if right click occurs within selected text or inside text layer with a selection
    var sel = window.getSelection();
    var selText = sel ? sel.toString() : '';

    if (state.rectSelectMode && state.selectedRectText) {
      e.preventDefault();
      showSelectionMenu(e.clientX, e.clientY);
      return;
    }

    if (selText.trim().length > 0) {
      var textLayer = e.target.closest('.textLayer');
      if (textLayer) {
        e.preventDefault();
        showSelectionMenu(e.clientX, e.clientY);
      }
    }
  }

  /* --- Visual Line Selection (Triple-Click) --- */
  function selectVisualLine(targetNode) {
    var span = targetNode.nodeType === Node.ELEMENT_NODE ? targetNode : targetNode.parentElement;
    if (!span) return;
    var textLayer = span.closest('.textLayer');
    if (!textLayer) return;

    var targetRect = span.getBoundingClientRect();
    var spans = Array.from(textLayer.querySelectorAll('span'));
    var lineSpans = [];
    var spanLefts = [];

    for (var i = 0; i < spans.length; i++) {
      var s = spans[i];
      var r = s.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      var overlap = Math.min(targetRect.bottom, r.bottom) - Math.max(targetRect.top, r.top);
      if (overlap > Math.min(targetRect.height, r.height) * 0.4) {
        lineSpans.push(s);
        spanLefts.push(r.left);
      }
    }

    if (lineSpans.length === 0) lineSpans = [span];

    // Sort using pre-computed left coordinates to prevent reflow thrashing
    var indices = [];
    for (var k = 0; k < lineSpans.length; k++) indices.push(k);
    indices.sort(function(a, b) {
      return (spanLefts[a] || 0) - (spanLefts[b] || 0);
    });

    var sortedLineSpans = [];
    for (var m = 0; m < indices.length; m++) {
      sortedLineSpans.push(lineSpans[indices[m]]);
    }
    lineSpans = sortedLineSpans;

    var firstSpan = lineSpans[0];
    var lastSpan = lineSpans[lineSpans.length - 1];

    var startNode = firstSpan.firstChild || firstSpan;
    var endNode = lastSpan.lastChild || lastSpan;

    var sel = window.getSelection();
    sel.removeAllRanges();
    var range = document.createRange();
    range.setStart(startNode, 0);
    var endOffset = endNode.nodeType === Node.TEXT_NODE ? endNode.textContent.length : endNode.childNodes.length;
    range.setEnd(endNode, endOffset);
    sel.addRange(range);

    state.selectionAnchor = { node: startNode, offset: 0 };
    updatePinnedPages();
  }

  /* --- Shift-Click Selection Extension --- */
  function handleShiftClick(e) {
    if (!state.selectionAnchor || !state.selectionAnchor.node) return false;

    var caret = getCaretPositionFromPoint(e.clientX, e.clientY);
    if (!caret || !caret.node) return false;

    var sel = window.getSelection();
    var extended = false;
    if (typeof sel.setBaseAndExtent === 'function') {
      try {
        sel.setBaseAndExtent(state.selectionAnchor.node, state.selectionAnchor.offset, caret.node, caret.offset);
        extended = true;
      } catch (err) {}
    }

    if (!extended) {
      sel.removeAllRanges();
      var range = document.createRange();
      var pos = state.selectionAnchor.node.compareDocumentPosition(caret.node);
      if (pos & Node.DOCUMENT_POSITION_FOLLOWING || (state.selectionAnchor.node === caret.node && state.selectionAnchor.offset <= caret.offset)) {
        range.setStart(state.selectionAnchor.node, state.selectionAnchor.offset);
        range.setEnd(caret.node, caret.offset);
      } else {
        range.setStart(caret.node, caret.offset);
        range.setEnd(state.selectionAnchor.node, state.selectionAnchor.offset);
      }
      sel.addRange(range);
      extended = true;
    }

    updatePinnedPages();
    return extended;
  }

  function getCaretPositionFromPoint(clientX, clientY) {
    if (document.caretPositionFromPoint) {
      var pos = document.caretPositionFromPoint(clientX, clientY);
      if (pos) return { node: pos.offsetNode, offset: pos.offset };
    } else if (document.caretRangeFromPoint) {
      var range = document.caretRangeFromPoint(clientX, clientY);
      if (range) return { node: range.startContainer, offset: range.startOffset };
    }
    return null;
  }

  /* --- Edge Auto-Scrolling --- */
  function checkEdgeAutoScroll(clientX, clientY) {
    var vRect = state.cachedViewportRect;
    if (!vRect) {
      vRect = viewport.getBoundingClientRect();
      state.cachedViewportRect = vRect;
    }
    var MARGIN = 40;
    var MAX_SPEED = 18;

    var topDist = clientY - vRect.top;
    var bottomDist = vRect.bottom - clientY;

    if (topDist >= -20 && topDist < MARGIN) {
      var ratio = 1 - Math.max(0, topDist) / MARGIN;
      state.autoScrollSpeed = -Math.max(3, Math.round(ratio * MAX_SPEED));
      startAutoScroll();
    } else if (bottomDist >= -20 && bottomDist < MARGIN) {
      var ratio = 1 - Math.max(0, bottomDist) / MARGIN;
      state.autoScrollSpeed = Math.max(3, Math.round(ratio * MAX_SPEED));
      startAutoScroll();
    } else {
      stopAutoScroll();
    }
  }

  function startAutoScroll() {
    if (state.autoScrollRAF) return;
    function step() {
      if (!state.isOpen || state.autoScrollSpeed === 0) {
        stopAutoScroll();
        return;
      }
      viewport.scrollTop += state.autoScrollSpeed;
      if (state.lastPointerPosition) {
        var caret = getCaretPositionFromPoint(state.lastPointerPosition.x, state.lastPointerPosition.y);
        if (caret && caret.node && state.selectionAnchor && state.selectionAnchor.node) {
          var sel = window.getSelection();
          if (typeof sel.setBaseAndExtent === 'function') {
            try {
              sel.setBaseAndExtent(state.selectionAnchor.node, state.selectionAnchor.offset, caret.node, caret.offset);
            } catch (e) {}
          }
        }
      }
      state.autoScrollRAF = requestAnimationFrame(step);
    }
    state.autoScrollRAF = requestAnimationFrame(step);
  }

  function stopAutoScroll() {
    if (state.autoScrollRAF) {
      cancelAnimationFrame(state.autoScrollRAF);
      state.autoScrollRAF = null;
    }
    state.autoScrollSpeed = 0;
  }

  /* --- Rectangular Selection Tool --- */
  function toggleRectSelect(force) {
    var nextState = typeof force === 'boolean' ? force : !state.rectSelectMode;
    state.rectSelectMode = nextState;
    if (rectSelectBtn) {
      rectSelectBtn.classList.toggle('active', nextState);
      rectSelectBtn.setAttribute('aria-pressed', nextState ? 'true' : 'false');
    }
    viewport.classList.toggle('rect-select-active', nextState);

    if (!nextState) {
      clearSelectionRect();
      hideSelectionMenu();
    } else {
      clearTextSelection();
    }
  }

  function clearSelectionRect() {
    if (state.rectEl && state.rectEl.parentNode) {
      state.rectEl.parentNode.removeChild(state.rectEl);
    }
    state.rectEl = null;
    state.rectBox = null;
    state.selectedRectText = '';
  }

  function extractRectText(pageWrapper, boxRect) {
    var spans = Array.from(pageWrapper.querySelectorAll('.textLayer span'));
    var charBoxes = [];

    spans.forEach(function(span) {
      var text = span.textContent;
      if (!text) return;
      var spanLeft = span.offsetLeft;
      var spanTop = span.offsetTop;
      var spanWidth = span.offsetWidth;
      var spanHeight = span.offsetHeight || 14;
      var charCount = text.length;
      var charWidth = charCount > 0 ? (spanWidth / charCount) : 0;

      for (var i = 0; i < charCount; i++) {
        var charLeft = spanLeft + i * charWidth;
        var charRight = charLeft + charWidth;
        var charCenterX = (charLeft + charRight) / 2;
        var charCenterY = spanTop + spanHeight / 2;

        if (charCenterX >= boxRect.left && charCenterX <= boxRect.right &&
            charCenterY >= boxRect.top && charCenterY <= boxRect.bottom) {
          charBoxes.push({
            char: text[i],
            x: charCenterX,
            y: charCenterY,
            height: spanHeight
          });
        }
      }
    });

    if (charBoxes.length === 0) return '';

    charBoxes.sort(function(a, b) { return a.y - b.y; });

    var rows = [];
    var currentRow = [];
    var currentY = null;
    var avgH = 12;

    charBoxes.forEach(function(cb) {
      if (currentY === null) {
        currentY = cb.y;
        currentRow.push(cb);
      } else if (Math.abs(cb.y - currentY) <= (cb.height || avgH) * 0.5) {
        currentRow.push(cb);
      } else {
        rows.push(currentRow);
        currentRow = [cb];
        currentY = cb.y;
      }
    });
    if (currentRow.length > 0) rows.push(currentRow);

    var resultLines = rows.map(function(row) {
      row.sort(function(a, b) { return a.x - b.x; });
      return row.map(function(cb) { return cb.char; }).join('');
    });

    return resultLines.join('\n');
  }

  /* --- Two Copy Actions & Normalization --- */
  function copySelection(normalize) {
    var text = '';
    if (state.rectSelectMode && state.selectedRectText) {
      text = state.selectedRectText;
    } else {
      var sel = window.getSelection();
      text = sel ? sel.toString() : '';
    }

    if (!text || text.length === 0) return;

    if (normalize) {
      text = normalizeCopyText(text);
    }

    writeToClipboard(text);
  }

  function normalizeCopyText(text) {
    if (!text) return '';
    var rawLines = text.split(/\r?\n/);
    var paragraphs = [];
    var currentPara = [];

    function isListItem(line) {
      return /^\s*([•\-\*–—]|\d+[\.\)]|[a-zA-Z][\.\)])\s+/.test(line);
    }

    for (var i = 0; i < rawLines.length; i++) {
      var line = rawLines[i];
      var trimmed = line.trim();

      if (!trimmed) {
        if (currentPara.length > 0) {
          paragraphs.push(joinParaLines(currentPara));
          currentPara = [];
        }
        continue;
      }

      if (isListItem(trimmed)) {
        if (currentPara.length > 0) {
          paragraphs.push(joinParaLines(currentPara));
          currentPara = [];
        }
        currentPara.push(trimmed);
        continue;
      }

      currentPara.push(trimmed);
    }

    if (currentPara.length > 0) {
      paragraphs.push(joinParaLines(currentPara));
    }

    return paragraphs.join('\n\n');
  }

  function joinParaLines(lines) {
    if (!lines || lines.length === 0) return '';
    var result = lines[0];
    for (var i = 1; i < lines.length; i++) {
      result += ' ' + lines[i];
    }
    return result;
  }

  function writeToClipboard(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard');
        hideSelectionMenu();
      }).catch(function(err) {
        fallbackClipboard(text);
      });
    } else {
      fallbackClipboard(text);
    }
  }

  function fallbackClipboard(text) {
    var textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    var success = false;
    try {
      success = document.execCommand('copy');
    } catch (e) {
      success = false;
    }
    document.body.removeChild(textArea);

    if (success) {
      showToast('Copied to clipboard');
      hideSelectionMenu();
    } else {
      showManualCopyDialog(text);
      hideSelectionMenu();
    }
  }

  function showManualCopyDialog(text, title) {
    if (!copyDialog || !copyDialogTextarea) return;
    var titleEl = document.getElementById('pdf-copy-dialog-title');
    if (titleEl) titleEl.textContent = title || 'Copy Selected Text';
    copyDialogTextarea.value = text;
    copyDialog.style.display = 'flex';
    copyDialogTextarea.focus();
    copyDialogTextarea.select();
  }

  function hideCopyDialog() {
    if (copyDialog) copyDialog.style.display = 'none';
  }

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.style.display = 'block';
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(function() {
      toastEl.style.display = 'none';
    }, 2200);
  }

  function showSelectionMenu(clientX, clientY) {
    if (!selectionMenu) return;
    selectionMenu.style.display = 'flex';

    // Position within viewport bounds
    var mWidth = 230;
    var mHeight = 90;
    var posX = Math.min(window.innerWidth - mWidth - 10, Math.max(10, clientX));
    var posY = Math.min(window.innerHeight - mHeight - 10, Math.max(10, clientY - mHeight - 5));

    selectionMenu.style.left = posX + 'px';
    selectionMenu.style.top = posY + 'px';
  }

  function hideSelectionMenu() {
    if (selectionMenu) selectionMenu.style.display = 'none';
  }

  function clearTextSelection() {
    var sel = (typeof window !== 'undefined' && window.getSelection) ? window.getSelection() : null;
    if (sel && typeof sel.removeAllRanges === 'function') {
      try { sel.removeAllRanges(); } catch (e) {}
    }
    state.selectionAnchor = null;
    state.pinnedPages.clear();
    hideSelectionMenu();
    hideTouchHandles();
  }

  /* --- Touch Interactions & Mobile Handles --- */
  function handleTouchStart(e) {
    if (!state.isOpen) return;

    if (e.touches.length === 2) {
      // Pinch to Zoom
      clearTimeout(state.longPressTimer);
      var dx = e.touches[0].clientX - e.touches[1].clientX;
      var dy = e.touches[0].clientY - e.touches[1].clientY;
      state.pinchStartDist = Math.hypot(dx, dy);
      state.pinchStartScale = state.scale;
      return;
    }

    if (e.touches.length === 1) {
      var touch = e.touches[0];
      state.touchStartPos = { x: touch.clientX, y: touch.clientY };

      // Check if touching a selection handle
      if (handleStart && handleStart.contains(e.target)) {
        state.isHandleDragging = true;
        state.activeHandle = 'start';
        e.preventDefault();
        return;
      }
      if (handleEnd && handleEnd.contains(e.target)) {
        state.isHandleDragging = true;
        state.activeHandle = 'end';
        e.preventDefault();
        return;
      }

      // Rectangular Mode Touch
      if (state.rectSelectMode) {
        handleMouseDown({
          button: 0,
          clientX: touch.clientX,
          clientY: touch.clientY,
          target: e.target,
          preventDefault: function() { e.preventDefault(); }
        });
        return;
      }

      // Long press detection for word selection
      clearTimeout(state.longPressTimer);
      state.longPressTimer = setTimeout(function() {
        var span = e.target.closest('.textLayer span');
        if (span) {
          triggerTouchWordSelect(touch.clientX, touch.clientY);
        }
      }, 500);
    }
  }

  function handleTouchMove(e) {
    if (!state.isOpen) return;

    if (e.touches.length === 2 && state.pinchStartDist > 0) {
      e.preventDefault();
      var dx = e.touches[0].clientX - e.touches[1].clientX;
      var dy = e.touches[0].clientY - e.touches[1].clientY;
      var newDist = Math.hypot(dx, dy);
      var ratio = newDist / state.pinchStartDist;
      setZoom(state.pinchStartScale * ratio, false);
      return;
    }

    if (e.touches.length === 1) {
      var touch = e.touches[0];

      // Cancel long press if moved > 8px
      if (state.touchStartPos) {
        var moveDist = Math.hypot(touch.clientX - state.touchStartPos.x, touch.clientY - state.touchStartPos.y);
        if (moveDist > 8) {
          clearTimeout(state.longPressTimer);
        }
      }

      // Handle Dragging
      if (state.isHandleDragging && state.activeHandle) {
        e.preventDefault();
        var caret = getCaretPositionFromPoint(touch.clientX, touch.clientY);
        if (caret && caret.node) {
          var sel = window.getSelection();
          if (sel && sel.rangeCount > 0) {
            var range = sel.getRangeAt(0);
            if (state.activeHandle === 'start') {
              range.setStart(caret.node, caret.offset);
            } else {
              range.setEnd(caret.node, caret.offset);
            }
            updateTouchHandles();
          }
        }
        return;
      }

      // Rectangular Mode Touch Move
      if (state.rectSelectMode && state.rectBox) {
        e.preventDefault();
        handleMouseMove({
          clientX: touch.clientX,
          clientY: touch.clientY
        });
      }
    }
  }

  function handleTouchEnd(e) {
    clearTimeout(state.longPressTimer);
    state.pinchStartDist = 0;
    state.isHandleDragging = false;
    state.activeHandle = null;

    if (state.rectSelectMode && state.rectBox) {
      var touch = e.changedTouches ? e.changedTouches[0] : null;
      var cx = touch ? touch.clientX : 0;
      var cy = touch ? touch.clientY : 0;
      handleMouseUp({ clientX: cx, clientY: cy });
    }
  }

  function triggerTouchWordSelect(clientX, clientY) {
    var caret = getCaretPositionFromPoint(clientX, clientY);
    if (!caret || !caret.node) return;

    var text = caret.node.textContent || '';
    var offset = caret.offset;

    var start = offset;
    while (start > 0 && /\S/.test(text[start - 1])) start--;
    var end = offset;
    while (end < text.length && /\S/.test(text[end])) end++;

    var sel = window.getSelection();
    sel.removeAllRanges();
    var range = document.createRange();
    range.setStart(caret.node, start);
    range.setEnd(caret.node, end);
    sel.addRange(range);

    state.selectionAnchor = { node: caret.node, offset: start };
    updateTouchHandles();
    showSelectionMenu(clientX, clientY);
  }

  function updateTouchHandles() {
    if (!handleStart || !handleEnd) return;
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
      hideTouchHandles();
      return;
    }

    var range = sel.getRangeAt(0);
    var rects = range.getClientRects();
    if (!rects || rects.length === 0) {
      hideTouchHandles();
      return;
    }

    var firstRect = rects[0];
    var lastRect = rects[rects.length - 1];

    handleStart.style.display = 'block';
    handleStart.style.left = (firstRect.left - 10) + 'px';
    handleStart.style.top = (firstRect.top - 20) + 'px';

    handleEnd.style.display = 'block';
    handleEnd.style.left = (lastRect.right - 5) + 'px';
    handleEnd.style.top = (lastRect.bottom) + 'px';
  }

  function hideTouchHandles() {
    if (handleStart) handleStart.style.display = 'none';
    if (handleEnd) handleEnd.style.display = 'none';
  }

  function handleSelectionChange() {
    if (!state.isOpen) return;
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
      hideTouchHandles();
      return;
    }
    if (sel.anchorNode && state.isSelecting) {
      state.selectionAnchor = { node: sel.anchorNode, offset: sel.anchorOffset };
    }
    recordDragTraceEvent('selectionchange', null);
  }

  /* --- Keyboard Shortcuts & Accessibility --- */
  function handleKeydown(e) {
    if (!state.isOpen) return;

    // Do not intercept hotkeys if typing in an input/textarea
    if (isEditable(e.target)) return;

    // Space key: temporary panning
    if (e.code === 'Space' || e.key === ' ') {
      if (!state.isSpacePressed) {
        e.preventDefault();
        state.isSpacePressed = true;
        viewport.classList.add('panning-ready');
      }
      return;
    }

    // Escape behavior: hierarchical dismiss
    if (e.key === 'Escape') {
      if (selectionMenu && selectionMenu.style.display !== 'none') {
        hideSelectionMenu();
        e.stopPropagation();
        return;
      }
      if (copyDialog && copyDialog.style.display !== 'none') {
        hideCopyDialog();
        e.stopPropagation();
        return;
      }
      if (state.rectSelectMode) {
        toggleRectSelect(false);
        e.stopPropagation();
        return;
      }
      close();
      return;
    }

    // Ctrl/Cmd + C: Copy ordinary text
    if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')) {
      var sel = window.getSelection();
      var hasSel = (sel && sel.toString().length > 0) || (state.rectSelectMode && state.selectedRectText);
      if (hasSel) {
        e.preventDefault();
        copySelection(false);
        return;
      }
    }

    // Ctrl/Cmd + Shift + D (or Alt + D): Export selection diagnostic
    if ((e.ctrlKey || e.metaKey) && (e.shiftKey || e.altKey) && (e.key === 'd' || e.key === 'D')) {
      e.preventDefault();
      exportSelectionDiagnostic();
      return;
    }

    // R: Toggle Rectangular Selection
    if (e.key === 'r' || e.key === 'R') {
      if (!e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        toggleRectSelect();
        return;
      }
    }

    // Page navigation & zoom
    if (e.key === 'ArrowLeft' && !e.shiftKey) { scrollToPage(getCurrentPageNum() - 1); }
    if (e.key === 'ArrowRight' && !e.shiftKey) { scrollToPage(getCurrentPageNum() + 1); }
    if (e.key === '+' || e.key === '=') zoomIn();
    if (e.key === '-') zoomOut();
    if (e.key === '0') resetZoom();
  }

  function handleKeyup(e) {
    if (e.code === 'Space' || e.key === ' ') {
      state.isSpacePressed = false;
      state.isPanning = false;
      viewport.classList.remove('panning-ready', 'panning-active');
    }
  }

  function handleWindowBlur() {
    state.isSpacePressed = false;
    state.isPanning = false;
    finishSelecting();
    stopAutoScroll();
    if (viewport) viewport.classList.remove('panning-ready', 'panning-active');
  }

  function handleWheel(e) {
    if (e.ctrlKey) {
      e.preventDefault();
      if (e.deltaY < 0) zoomIn();
      else zoomOut();
    }
  }

  function getCurrentPageNum() {
    return parseInt(pageNumEl.textContent) || 1;
  }

  function updateCurrentPageIndicator() {
    if (!state.isOpen || state.pages.length <= 1) return;
    var vTop = viewport.scrollTop || 0;
    var numPages = state.pages.length - 1;

    for (var i = 1; i <= numPages; i++) {
      var p = state.pages[i];
      if (!p || !p.wrapper) continue;
      var top = p.wrapper.offsetTop || ((i - 1) * (state.pageOriginalHeight || 792) * state.scale);
      var height = p.wrapper.offsetHeight || ((state.pageOriginalHeight || 792) * state.scale);
      if ((top + height) > vTop + 100) {
        pageNumEl.textContent = i;
        break;
      }
    }
  }

  function scrollToPage(num) {
    if (num < 1 || num > state.pages.length - 1) return;
    var w = state.pages[num].wrapper;
    if (w) {
      w.scrollIntoView({ behavior: 'smooth' });
    }
  }

})();
"""

