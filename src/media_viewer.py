# MIT License
# Copyright (c) 2024 Vortex Contributors
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
        var objectUrl = URL.createObjectURL(jpegBlob);
        img.src = objectUrl;
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
