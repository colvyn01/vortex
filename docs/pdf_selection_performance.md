# Vortex PDF Viewer: Text Selection & Bounded Performance Architecture

## Overview

This document records the architectural design, implementation details, test procedures, and verification status for the PDF viewer text selection and resource management in Vortex.

An earlier implementation of PDF.js text selection caused severe system memory and swap exhaustion on Linux desktop environments. The current architecture addresses this through bounded render concurrency, viewport canvas virtualization with backing-store eviction, cross-page selection pinning, and lifecycle teardown.

---

## 1. Implemented Selection & Copy Interactions

The PDF viewer is integrated into Vortex via [`src/media_viewer.py`](file:///home/colvyn/Documents/Projects/vortex/src/media_viewer.py) and rendered in the web client via [`src/ui.py`](file:///home/colvyn/Documents/Projects/vortex/src/ui.py).

* **Multi-Page Viewport & Text Layer**:
  * Pages are mounted inside `.pdf-page-wrapper` containers with absolute-positioned `.textLayer` elements overlaid on `.pdf-page-canvas` elements.
  * Uses PDF.js standard transparent text overlays with custom Okular-inspired selection styling (`rgba(61, 174, 233, 0.42)`).
* **Precise Text Selection**:
  * Forward and backward pointer drag selection using `document.caretPositionFromPoint` / `document.caretRangeFromPoint`.
  * Double-click word selection and triple-click visual line selection (`selectVisualLine`) with batched layout queries to eliminate reflow.
  * Shift-click selection extension from the original anchor node.
  * Viewport edge auto-scrolling during drag operations.
* **Reading-Order Normalization (`processReadingOrder`)**:
  * Multi-column detection groups text spans into column blocks before sorting vertically, avoiding interleaving between adjacent text columns.
  * Results are cached per page generation to avoid repeated layout parsing.
* **Space-Drag Temporary Panning**:
  * Holding `Space` switches the cursor to `grab` and enables drag-panning without losing focus or initiating text selection.
* **Rectangular Text Selection**:
  * Toggleable crosshair mode (`R` shortcut or toolbar button).
  * Extracts text whose character bounding box centers fall within the drawn rectangle.
* **Two Copy Actions**:
  * **Ordinary Copy**: Copies selected text with standard line normalization.
  * **Copy without line breaks**: Joins wrapped lines within paragraphs with a single space while preserving distinct paragraph breaks, list items, hyphens, and headers/footers.
  * **Selection Invariant**: Copying preserves the active DOM selection and does not collapse or clear it.
* **Touch & Mobile Support**:
  * Distinguishes single-touch scrolling from long-press selection handle placement (`pdf-touch-handle-start`, `pdf-touch-handle-end`) and pinch zooming.

---

## 2. Bounded-Rendering and Resource Management Design

To prevent resource exhaustion when opening multi-page or high-resolution PDFs:

1. **Strictly Bounded Concurrency (`MAX_CONCURRENT_RENDERS = 1`)**:
   * Only one page render task executes at any given time.
   * Render concurrency is tracked asynchronously: `state.activeRenders` decrements strictly when the render promise settles (`.then()` / `.catch()`), preventing race conditions during cancellation.
   * Duplicate requests in `state.renderQueue` are deduplicated before dispatch.
2. **Viewport Virtualization & Canvas Eviction**:
   * Only visible pages plus an adjacent buffer window (`BUFFER_PAGES = 1`) retain active backing-store canvases.
   * When a page scrolls out of the retention window, `evictPageCanvas()` resets `canvas.width = 0; canvas.height = 0;` to trigger backing-store memory release.
3. **Cross-Page Selection Pinning (`updatePinnedPages`)**:
   * When an active user selection spans multiple pages, those pages are pinned into `state.pinnedPages`.
   * Pinned pages keep their `.textLayer` mounted in the DOM during scrolling so the browser selection range does not collapse, while their heavy backing-store canvases remain subject to eviction.
   * Pinned pages are released as soon as the selection is cleared.
4. **DevicePixelRatio Clamping**:
   * Capped via `Math.min(window.devicePixelRatio || 1, 2.0)` to prevent excessive backing-store allocation on high-DPI (e.g., 3x–4x) displays.
5. **Lifecycle Teardown & Generation Tokens**:
   * `state.generation` tokens prevent stale asynchronous renders from attaching to the DOM after page eviction or re-scale.
   * On `close()` or document replacement:
     * In-flight network/worker tasks are aborted via `state.loadingTask.destroy()`.
     * Active PDF.js document instances are destroyed via `state.pdfDoc.destroy()`.
     * All queues, intervals, and observers are disconnected.
6. **Diagnostics API (`getDiagnostics`)**:
   * Exposes `window.VortexPdfViewer.getDiagnostics()` to monitor `retainedCanvases`, `totalBackingStorePixels`, `activeRenderJobs`, `mountedTextLayers`, `pinnedPages`, and `hasActivePdfDocument`.

---

## 3. Verification & Test Execution

### Automated Test Suites

1. **Python Unit Tests**:
   Verifies HTML/CSS/JS structural integrity, UI module exports, PDF test fixture headers, and harness configuration:
   ```bash
   python3 -m unittest discover tests
   ```
2. **Node.js Logic Tests**:
   Verifies reading-order algorithms, copy normalization, rectangular text containment, escape key hierarchy, concurrency bounding, selection pinning, and lifecycle destruction:
   ```bash
   node --test tests/test_pdf_selection_logic.js
   ```

### Browser Test Harness

The browser test harness embeds the actual application viewer components and runs automated checks across baseline, load, idle, scroll, selection, zoom, and teardown phases:

* **Generate/Update Harness**:
  ```bash
  python3 tests/generate_browser_perf_test.py
  ```
* **Run Harness**:
  1. Start the server from repository root:
     ```bash
     python3 -m src.cli start --foreground --port 8000
     ```
  2. Open in browser:
     ```text
     http://localhost:8000/tests/browser_perf_test.html
     ```
  3. Run the automated benchmarks (3-page initial test, 20-page extended test, or 50-page stress benchmark) and export diagnostic JSON.

---

## 4. Verification Status & Constraints

* **User Verification (Brave Desktop)**:
  * Manually verified on Arch Linux / KDE Plasma (Wayland) on an Intel Core i5-1334U with 31 GiB RAM using the original multi-page PDF document that previously exhausted system memory.
  * The user confirmed that the viewer and Brave remained responsive throughout interaction.
  * Text selection and copying produced satisfactory results.
  * The automated browser harness completed successful test runs on 3-, 20-, and 50-page fixtures.
* **Measurement Disclaimers**:
  * Improved responsiveness and stability were observed qualitatively during user testing. Post-fix system-wide quantitative resource metrics (e.g., continuous batch `top` CPU/RSS/swap logs) were not recorded.
  * In-browser JavaScript (`performance.memory`) measures only the V8 JS heap; it cannot inspect browser process RSS, GPU/GEM shared memory, or kernel swap pages.
* **Scope Limits & Unverified Environments**:
  * Testing has been validated exclusively in Brave desktop on Linux.
  * Other desktop browsers (Firefox, Safari, standard Chromium) remain unverified.
  * Real mobile devices (iOS Safari, Android Chrome/Firefox) and touch gesture handling have not been validated on physical hardware.
  * Complete feature parity with native desktop PDF viewers (such as Okular) is not claimed.
