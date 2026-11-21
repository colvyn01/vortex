# MIT License
# Copyright (c) 2026 Vortex Contributors
# See LICENSE file for full license text.

import unittest
from pathlib import Path
from src.media_viewer import (
    get_pdf_viewer_html,
    get_pdf_viewer_css,
    get_pdf_viewer_js,
)
from src.ui import (
    _MEDIA_VIEWER_HTML,
    _MEDIA_VIEWER_CSS,
    _MEDIA_VIEWER_JS,
)

class TestPdfViewerComponents(unittest.TestCase):
    """Unit tests for PDF viewer HTML, CSS, and JS structure and integration."""

    def test_pdf_viewer_html_structure(self):
        html = get_pdf_viewer_html()
        
        # Modal and Viewport
        self.assertIn('id="pdf-viewer-modal"', html)
        self.assertIn('id="pdf-viewport"', html)
        self.assertIn('id="pdf-container"', html)
        self.assertIn('tabindex="0"', html)
        self.assertIn('role="region"', html)
        self.assertIn('aria-label="PDF Document Pages"', html)

        # Controls
        self.assertIn('id="pdf-rect-select"', html)
        self.assertIn('title="Rectangular Selection (R)"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn('id="pdf-live-toggle"', html)
        self.assertIn('id="pdf-download"', html)
        self.assertIn('id="pdf-close"', html)

        # Scanned PDF banner
        self.assertIn('id="pdf-no-text-banner"', html)
        self.assertIn('role="status"', html)

        # Selection Context Menu / Toolbar
        self.assertIn('id="pdf-selection-menu"', html)
        self.assertIn('role="menu"', html)
        self.assertIn('id="pdf-copy-btn"', html)
        self.assertIn('id="pdf-copy-nolinebreaks-btn"', html)

        # Manual Copy Fallback Dialog
        self.assertIn('id="pdf-copy-dialog"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('id="pdf-copy-dialog-textarea"', html)
        self.assertIn('id="pdf-copy-dialog-close"', html)
        self.assertIn('id="pdf-copy-dialog-done"', html)

        # Feedback & Touch
        self.assertIn('id="pdf-toast"', html)
        self.assertIn('id="pdf-touch-handle-start"', html)
        self.assertIn('id="pdf-touch-handle-end"', html)

    def test_pdf_viewer_css_selection_and_textlayer(self):
        css = get_pdf_viewer_css()

        # Page wrapper & canvas
        self.assertIn('.pdf-page-wrapper', css)
        self.assertIn('user-select: text;', css)
        self.assertIn('-webkit-user-select: text;', css)
        self.assertIn('.pdf-page-canvas', css)
        self.assertIn('pointer-events: none;', css)

        # PDF.js 3.11.174 compliant text layer
        self.assertIn('.textLayer', css)
        self.assertIn('position: absolute;', css)
        self.assertIn('transform-origin: 0 0;', css)
        self.assertIn('forced-color-adjust: none;', css)
        self.assertIn('.textLayer :is(span, br)', css)
        self.assertIn('color: transparent;', css)

        # Okular-inspired selection style
        self.assertIn('.textLayer ::selection', css)
        self.assertIn('rgba(61, 174, 233, 0.42)', css)
        self.assertIn('.textLayer ::-moz-selection', css)

        # Space Panning states
        self.assertIn('.pdf-viewport.panning-ready', css)
        self.assertIn('cursor: grab !important;', css)
        self.assertIn('.pdf-viewport.panning-active', css)
        self.assertIn('cursor: grabbing !important;', css)

        # Rectangular selection styles
        self.assertIn('.pdf-viewport.rect-select-active', css)
        self.assertIn('cursor: crosshair !important;', css)
        self.assertIn('.pdf-rect-box', css)
        self.assertIn('border: 1.5px dashed #3daee9;', css)

        # Selection menu, toast, copy dialog, touch handles
        self.assertIn('.pdf-selection-menu', css)
        self.assertIn('.pdf-menu-item', css)
        self.assertIn('.pdf-toast', css)
        self.assertIn('.pdf-copy-dialog', css)
        self.assertIn('.pdf-touch-handle', css)

    def test_pdf_viewer_js_api_and_version(self):
        js = get_pdf_viewer_js()

        # PDF.js version 3.11.174
        self.assertIn('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js', js)
        self.assertIn('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js', js)

        # Global object and exported functions
        self.assertIn('window.VortexPdfViewer =', js)
        self.assertIn('open: open,', js)
        self.assertIn('close: close,', js)
        self.assertIn('toggleRectSelect: toggleRectSelect,', js)
        self.assertIn('copySelection: copySelection,', js)
        self.assertIn('processReadingOrder: processReadingOrder,', js)
        self.assertIn('normalizeCopyText: normalizeCopyText', js)
        self.assertIn('getDiagnostics: getDiagnostics', js)
        self.assertIn('updateVirtualization: updateVirtualization', js)

        # Performance, virtualization, and bounded concurrency
        self.assertIn('MAX_CONCURRENT_RENDERS = 1', js)
        self.assertIn('BUFFER_PAGES = 1', js)
        self.assertIn('getDevicePixelRatio', js)
        self.assertIn('updatePinnedPages', js)
        self.assertIn('evictPageCanvas', js)
        self.assertIn('unmountPageTextLayer', js)
        self.assertIn('cancelAllActiveRenders', js)

        # Key interactions
        self.assertIn('selectVisualLine', js)
        self.assertIn('handleShiftClick', js)
        self.assertIn('checkEdgeAutoScroll', js)
        self.assertIn('extractRectText', js)
        self.assertIn('normalizeCopyText', js)
        self.assertIn('isEditable', js)

    def test_ui_integration(self):
        """Verify media viewer components are properly exported and wired into ui.py"""
        self.assertIn('id="pdf-viewer-modal"', _MEDIA_VIEWER_HTML)
        self.assertIn('id="pdf-rect-select"', _MEDIA_VIEWER_HTML)
        self.assertIn('.pdf-page-wrapper', _MEDIA_VIEWER_CSS)
        self.assertIn('.textLayer ::selection', _MEDIA_VIEWER_CSS)
        self.assertIn('VortexPdfViewer', _MEDIA_VIEWER_JS)

    def test_pdf_fixtures_exist(self):
        """Ensure all required PDF test fixtures were generated and have valid headers."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "pdf"
        required = [
            "single_column.pdf",
            "two_column.pdf",
            "lists.pdf",
            "hyphenated.pdf",
            "multipage.pdf",
            "multipage_20.pdf",
            "multipage_50.pdf",
            "scanned_textless.pdf",
        ]
        for name in required:
            f = fixtures_dir / name
            self.assertTrue(f.exists(), f"Missing fixture {name}")
            data = f.read_bytes()
            self.assertTrue(data.startswith(b"%PDF-1.4"), f"Invalid PDF header in {name}")
            self.assertTrue(data.rstrip().endswith(b"%%EOF"), f"Invalid PDF EOF in {name}")

    def test_browser_perf_test_harness_structure(self):
        """Verify tests/browser_perf_test.html embeds real viewer components and has required harness controls."""
        harness_path = Path(__file__).parent / "browser_perf_test.html"
        self.assertTrue(harness_path.exists(), "tests/browser_perf_test.html must exist")
        content = harness_path.read_text(encoding="utf-8")

        # 1. Tests real application viewer components
        self.assertIn('id="pdf-viewer-modal"', content)
        self.assertIn('id="pdf-viewport"', content)
        self.assertIn('.textLayer', content)
        self.assertIn('window.VortexPdfViewer =', content)
        self.assertIn('MAX_CONCURRENT_RENDERS = 1', content)

        # 2. Obtains diagnostics
        self.assertIn('viewer.getDiagnostics()', content)
        self.assertIn('retainedCanvases', content)
        self.assertIn('totalBackingStorePixels', content)
        self.assertIn('activeRenderJobs', content)

        # 3. Detects failure and asserts bounds
        self.assertIn('diag.retainedCanvases <= 3', content)
        self.assertIn('diag.activeRenderJobs <= 1', content)
        self.assertIn('status-fail', content)

        # 4. CPU/memory disclaimers and honest measurements
        self.assertIn('performance.memory', content)
        self.assertIn('Telemetry Disclaimers', content)
        self.assertIn('JS Heap (V8)', content)

        # 5. Export timestamped results
        self.assertIn('exportResultsJson', content)
        self.assertIn('exportLogText', content)
        self.assertIn('application/json', content)

        # 6. Stop / Cancel controls
        self.assertIn('stopBenchmark', content)
        self.assertIn('btn-stop', content)
        self.assertIn('btn-hud-stop', content)

        # 7. Timeouts abort workload
        self.assertIn('Promise.race', content)
        self.assertIn('timed out after', content)

if __name__ == '__main__':
    unittest.main()
