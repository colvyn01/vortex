#!/usr/bin/env python3
# MIT License
# Copyright (c) 2026 Vortex Contributors
# See LICENSE file for full license text.

"""
Generator script for tests/browser_perf_test.html.

Constructs the performance benchmark harness by embedding the real
Vortex PDF viewer HTML, CSS, and JS components directly from src.media_viewer.
This guarantees the benchmark always tests the actual application implementation.
"""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.media_viewer import (
    get_pdf_viewer_html,
    get_pdf_viewer_css,
    get_pdf_viewer_js,
)

def build_harness_html() -> str:
    viewer_html = get_pdf_viewer_html()
    viewer_css = get_pdf_viewer_css()
    viewer_js = get_pdf_viewer_js()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vortex PDF Performance & Resource Verification</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
  
  <!-- PDF.js CDN (Matches src/media_viewer.py) -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>

  <!-- Real Application PDF Viewer Styles -->
  <style>
{viewer_css}
  </style>

  <!-- Test Harness Dashboard Styles -->
  <style>
    :root {{
      --bg: #0f141c;
      --card-bg: #1a2230;
      --border: #2a364a;
      --accent: #3daee9;
      --text: #e2e8f0;
      --text-muted: #8899ac;
      --success: #2ecc71;
      --danger: #e74c3c;
      --warning: #f39c12;
    }}
    body {{
      font-family: 'IBM Plex Sans', -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 1.5rem;
    }}
    h1 {{
      margin-top: 0;
      font-size: 1.4rem;
      color: #fff;
    }}
    .harness-panel {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      margin-bottom: 1.5rem;
    }}
    .controls-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
      margin-bottom: 1rem;
    }}
    .btn {{
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 4px;
      padding: 0.5rem 1rem;
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s ease, opacity 0.15s ease;
    }}
    .btn:hover {{ background: #2980b9; }}
    .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .btn-stop {{ background: var(--danger); font-weight: 600; }}
    .btn-stop:hover {{ background: #c0392b; }}
    .btn-secondary {{ background: #4a5568; }}
    .btn-secondary:hover {{ background: #3b4453; }}
    .btn-export {{ background: #27ae60; }}
    .btn-export:hover {{ background: #219653; }}
    
    .status-badge {{
      display: inline-block;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
    }}
    .status-pass {{ background: rgba(46, 204, 113, 0.2); color: var(--success); }}
    .status-fail {{ background: rgba(231, 76, 60, 0.2); color: var(--danger); }}
    .status-running {{ background: rgba(61, 174, 233, 0.2); color: var(--accent); }}
    .status-pending {{ background: rgba(136, 153, 172, 0.2); color: var(--text-muted); }}

    .disclaimer-box {{
      background: rgba(243, 156, 18, 0.1);
      border-left: 3px solid var(--warning);
      padding: 0.75rem 1rem;
      margin-bottom: 1rem;
      font-size: 0.8rem;
      line-height: 1.4;
      color: #fce4b8;
    }}
    .disclaimer-box strong {{ color: #fff; }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 0.5rem;
      font-size: 0.8rem;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: 0.45rem 0.65rem;
      text-align: left;
    }}
    th {{
      background: rgba(0, 0, 0, 0.25);
      color: var(--text-muted);
      font-weight: 600;
    }}
    td.mono {{
      font-family: 'IBM Plex Mono', monospace;
    }}
    #console-log {{
      background: #090d13;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.75rem;
      height: 160px;
      overflow-y: auto;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.75rem;
      color: #a0aec0;
      margin-top: 1rem;
      white-space: pre-wrap;
    }}

    /* Floating Benchmark HUD Overlay when Modal is Open */
    #benchmark-hud-overlay {{
      position: fixed;
      top: 12px;
      right: 12px;
      z-index: 10005;
      width: 480px;
      max-width: 90vw;
      background: rgba(15, 20, 28, 0.95);
      border: 1px solid var(--accent);
      border-radius: 8px;
      padding: 12px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.85);
      display: none;
      font-size: 0.8rem;
    }}
    #benchmark-hud-overlay.active {{
      display: block;
    }}
    .hud-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 4px;
    }}
    .hud-title {{
      font-weight: 600;
      color: var(--accent);
    }}
  </style>
</head>
<body>

  <!-- FLOATING BENCHMARK HUD (VISIBLE WHILE PDF VIEWER MODAL IS OPEN) -->
  <div id="benchmark-hud-overlay">
    <div class="hud-header">
      <span class="hud-title">Vortex Performance HUD</span>
      <button id="btn-hud-stop" class="btn btn-stop" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;">Stop / Abort</button>
    </div>
    <div id="hud-status" style="margin-bottom: 6px; color: #fff;">Status: <span id="hud-phase-name">Idle</span></div>
    <div id="hud-metrics" class="mono" style="font-size: 0.72rem; color: #a0aec0; line-height: 1.4;">
      Canvases: - | RAM: - | Active: - | Pinned: -
    </div>
  </div>

  <h1>Vortex PDF Performance & Resource Verification</h1>
  <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: -0.25rem; margin-bottom: 1rem;">
    Verification harness embedded with real Vortex viewer components (HTML, CSS, JS).
    &bull; Loaded Viewer Build: <span id="harness-build-id" class="mono" style="color: var(--accent); font-weight: 600;">detecting...</span>
  </p>

  <div class="disclaimer-box">
    <strong>Telemetry Disclaimers & Attribution Notes:</strong><br>
    - <strong>JS Heap:</strong> Sampled from Chromium <code>performance.memory</code> (JS V8 heap only). Does <em>not</em> reflect browser process RSS, GPU/GEM buffers, or OS swap.<br>
    - <strong>Canvas Memory:</strong> Calculated exact backing-store allocation: &Sigma;(width &times; height &times; 4 bytes).<br>
    - <strong>Host CPU &amp; Swap:</strong> Browser JavaScript cannot measure system-wide CPU or swap. Monitor host impact via <code>top</code>, <code>htop</code>, or Brave Task Manager (<code>Shift+Esc</code>).
  </div>

  <div class="harness-panel">
    <div class="controls-row">
      <!-- Conservative Initial Test (Recommended) -->
      <button id="btn-run-small" class="btn">1. Run Initial Test (3-Page PDF)</button>
      <!-- Extended Tests -->
      <button id="btn-run-20" class="btn btn-secondary">2. Extended Test (20 Pages)</button>
      <button id="btn-run-50" class="btn btn-secondary">3. Full Stress (50 Pages)</button>
      <!-- Control Buttons -->
      <button id="btn-stop" class="btn btn-stop" disabled>Stop / Cancel</button>
      <button id="btn-open-manual" class="btn btn-secondary">Open 3-Page</button>
      <button id="btn-open-lists" class="btn btn-secondary">Open Lists Fixture</button>
      <button id="btn-open-resume" class="btn btn-secondary">Open Résumé Fixture</button>
      <button id="btn-close-manual" class="btn btn-secondary">Close Viewer</button>
      <!-- Export -->
      <button id="btn-toggle-trace" class="btn btn-secondary">Toggle Drag Trace (Off)</button>
      <button id="btn-capture-diag" class="btn btn-export">Capture Diag</button>
      <button id="btn-export-json" class="btn btn-export">Export JSON</button>
      <button id="btn-export-log" class="btn btn-secondary">Export Log</button>
    </div>

    <div id="diag-container" style="display: none; margin-top: 1rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <strong style="color: var(--accent); font-size: 0.85rem;">Selection Diagnostic JSON:</strong>
        <button id="btn-close-diag-view" class="btn btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">Hide</button>
      </div>
      <pre id="diag-display" style="max-height: 250px; overflow: auto; background: #0a0e14; border: 1px solid #2a364a; padding: 10px; border-radius: 6px; font-size: 0.72rem; color: #64d2ff;"></pre>
    </div>

    <table id="results-table">
      <thead>
        <tr>
          <th>Test Phase</th>
          <th>Canvases</th>
          <th>Backing-Store Pixels</th>
          <th>Est. Canvas RAM</th>
          <th>Mounted TextLayers</th>
          <th>JS Heap (V8)</th>
          <th>Active/Queued Renders</th>
          <th>Outcome</th>
        </tr>
      </thead>
      <tbody>
        <tr id="row-init">
          <td>1. Baseline Closed</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td><span class="status-badge status-pending">Pending</span></td>
        </tr>
        <tr id="row-load">
          <td>2. Document Load</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td><span class="status-badge status-pending">Pending</span></td>
        </tr>
        <tr id="row-idle">
          <td>3. Post-Load Idle</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td><span class="status-badge status-pending">Pending</span></td>
        </tr>
        <tr id="row-scroll">
          <td>4. Scroll Virtualization & Eviction</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td><span class="status-badge status-pending">Pending</span></td>
        </tr>
        <tr id="row-select">
          <td>5. Cross-Page Selection Pinning</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td><span class="status-badge status-pending">Pending</span></td>
        </tr>
        <tr id="row-zoom">
          <td>6. Zoom Scaling</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td><span class="status-badge status-pending">Pending</span></td>
        </tr>
        <tr id="row-teardown">
          <td>7. Close Teardown & Lifecycle</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td class="mono">-</td>
          <td><span class="status-badge status-pending">Pending</span></td>
        </tr>
      </tbody>
    </table>

    <div id="console-log">Ready. Start with '1. Run Initial Test (3-Page PDF)'.</div>
  </div>

  <!-- REAL APPLICATION VIEWER MODAL MARKUP -->
{viewer_html}

  <!-- REAL APPLICATION VIEWER JAVASCRIPT -->
  <script>
{viewer_js}
  </script>

  <!-- BENCHMARK HARNESS LOGIC -->
  <script>
    var isAborted = false;
    var activeBenchmarkRunning = false;
    var currentTimeoutId = null;
    var collectedDiagnostics = [];
    var logHistory = [];

    function log(msg) {{
      var el = document.getElementById('console-log');
      var time = new Date().toISOString().split('T')[1].slice(0, 8);
      var line = `[${{time}}] ${{msg}}`;
      logHistory.push(line);
      el.textContent += line + '\\n';
      el.scrollTop = el.scrollHeight;
      console.log(line);
    }}

    function updateHud(phaseName, diag) {{
      var hud = document.getElementById('benchmark-hud-overlay');
      var nameEl = document.getElementById('hud-phase-name');
      var metricsEl = document.getElementById('hud-metrics');
      if (activeBenchmarkRunning) {{
        hud.classList.add('active');
        nameEl.textContent = phaseName || 'Running';
        if (diag) {{
          var mb = (diag.estimatedCanvasMemoryBytes / (1024 * 1024)).toFixed(1);
          metricsEl.textContent = `Canvases: ${{diag.retainedCanvases}} | RAM: ${{mb}} MB | Active Renders: ${{diag.activeRenderJobs}} | Pinned: ${{diag.pinnedPages.length}}`;
        }}
      }} else {{
        hud.classList.remove('active');
      }}
    }}

    function updateRow(rowId, diag, passed, note) {{
      var row = document.getElementById(rowId);
      if (!row) return;
      var cells = row.getElementsByTagName('td');
      if (diag) {{
        cells[1].textContent = diag.retainedCanvases;
        cells[2].textContent = (diag.totalBackingStorePixels / 1e6).toFixed(2) + ' MP';
        cells[3].textContent = (diag.estimatedCanvasMemoryBytes / (1024 * 1024)).toFixed(1) + ' MB';
        cells[4].textContent = diag.mountedTextLayers + (diag.pinnedPages.length > 0 ? ` (${{diag.pinnedPages.length}} pinned)` : '');
        cells[5].textContent = diag.jsHeap ? (diag.jsHeap.usedJSHeapSize / (1024 * 1024)).toFixed(1) + ' MB' : 'N/A';
        cells[6].textContent = `${{diag.activeRenderJobs}} / ${{diag.queuedRenderJobs}}`;
      }}
      var badge = cells[7].querySelector('.status-badge');
      if (passed === true) {{
        badge.className = 'status-badge status-pass';
        badge.textContent = 'PASS';
      }} else if (passed === false) {{
        badge.className = 'status-badge status-fail';
        badge.textContent = note || 'FAIL';
      }} else if (passed === 'SKIPPED') {{
        badge.className = 'status-badge status-pending';
        badge.textContent = 'SKIPPED';
      }} else {{
        badge.className = 'status-badge status-running';
        badge.textContent = 'RUNNING...';
      }}
    }}

    async function sleep(ms) {{
      return new Promise(resolve => setTimeout(resolve, ms));
    }}

    async function waitForCondition(conditionFn, timeoutMs, intervalMs) {{
      intervalMs = intervalMs || 50;
      var start = Date.now();
      while (Date.now() - start < timeoutMs) {{
        if (isAborted) throw new Error('Benchmark aborted by user');
        if (conditionFn()) return true;
        await sleep(intervalMs);
      }}
      throw new Error(`Condition timed out after ${{timeoutMs}}ms`);
    }}

    function resetTable() {{
      var rows = ['row-init', 'row-load', 'row-idle', 'row-scroll', 'row-select', 'row-zoom', 'row-teardown'];
      rows.forEach(r => {{
        var row = document.getElementById(r);
        if (row) {{
          var cells = row.getElementsByTagName('td');
          for (var i = 1; i <= 6; i++) cells[i].textContent = '-';
          var badge = cells[7].querySelector('.status-badge');
          badge.className = 'status-badge status-pending';
          badge.textContent = 'PENDING';
        }}
      }});
    }}

    function setControlsState(running) {{
      activeBenchmarkRunning = running;
      document.getElementById('btn-run-small').disabled = running;
      document.getElementById('btn-run-20').disabled = running;
      document.getElementById('btn-run-50').disabled = running;
      document.getElementById('btn-stop').disabled = !running;
      document.getElementById('btn-hud-stop').disabled = !running;
      if (!running) {{
        document.getElementById('benchmark-hud-overlay').classList.remove('active');
      }}
    }}

    function stopBenchmark() {{
      if (!activeBenchmarkRunning) return;
      isAborted = true;
      log('STOP REQUESTED: Aborting test and cleaning up viewer immediately...');
      if (window.VortexPdfViewer) {{
        try {{ window.VortexPdfViewer.close(); }} catch(e) {{}}
      }}
      setControlsState(false);
      log('Test aborted. Viewer closed and resources cleaned up.');
    }}

    async function runBenchmarkWorkload(pdfUrl, filename, totalExpectedPages, isStressTest) {{
      if (activeBenchmarkRunning) return;
      resetTable();
      isAborted = false;
      setControlsState(true);
      collectedDiagnostics = [];

      var viewer = window.VortexPdfViewer;
      if (!viewer) {{
        log('CRITICAL ERROR: window.VortexPdfViewer is not defined!');
        setControlsState(false);
        return;
      }}

      var runPhase = async function(phaseName, rowId, timeoutMs, phaseFn) {{
        if (isAborted) {{
          updateRow(rowId, null, 'SKIPPED');
          return false;
        }}
        updateRow(rowId, null, null);
        updateHud(phaseName, viewer.getDiagnostics());
        log(`--> Starting Phase: ${{phaseName}}`);

        var phaseTimer = null;
        var timeoutPromise = new Promise((_, reject) => {{
          phaseTimer = setTimeout(() => reject(new Error(`Phase '${{phaseName}}' timed out after ${{timeoutMs}}ms`)), timeoutMs);
        }});

        try {{
          await Promise.race([phaseFn(), timeoutPromise]);
          clearTimeout(phaseTimer);
          var diag = viewer.getDiagnostics();
          collectedDiagnostics.push({{ phase: phaseName, timestamp: new Date().toISOString(), diag: diag }});
          updateHud(phaseName, diag);
          return true;
        }} catch(err) {{
          clearTimeout(phaseTimer);
          var errDiag = viewer.getDiagnostics();
          collectedDiagnostics.push({{ phase: phaseName, timestamp: new Date().toISOString(), diag: errDiag, error: err.message }});
          updateRow(rowId, errDiag, false, err.message);
          log(`FAIL in ${{phaseName}}: ${{err.message}}`);
          stopBenchmark();
          return false;
        }}
      }};

      try {{
        // Phase 1: Baseline Closed
        var p1 = await runPhase('1. Baseline Closed', 'row-init', 3000, async () => {{
          viewer.close();
          await sleep(100);
          var diag = viewer.getDiagnostics();
          var ok = diag.activeDocuments === 0 && diag.retainedCanvases === 0 && diag.totalBackingStorePixels === 0 && !diag.hasActivePdfDocument;
          updateRow('row-init', diag, ok, ok ? null : 'Leaked initial baseline');
          if (!ok) throw new Error(`Baseline not empty: canvases=${{diag.retainedCanvases}}, docs=${{diag.activeDocuments}}`);
          log(`Phase 1 Baseline Clean: Retained canvases = 0, Active docs = 0. PASS.`);
        }});
        if (!p1) return;

        // Phase 2: Document Load
        var p2 = await runPhase('2. Document Load', 'row-load', 12000, async () => {{
          log(`Opening ${{filename}} (${{totalExpectedPages}} pages)...`);
          viewer.open(pdfUrl, filename);
          
          // Wait for document to load
          await waitForCondition(() => {{
            var d = viewer.getDiagnostics();
            return d.hasActivePdfDocument && d.totalDocumentPages === totalExpectedPages;
          }}, 8000);

          // Wait for initial visible page render to finish
          await waitForCondition(() => viewer.getDiagnostics().activeRenderJobs === 0, 8000);

          var diag = viewer.getDiagnostics();
          // Concurrency check: activeRenderJobs must be <= 1
          // Bounded canvases: visible + 1 buffer page <= 3 (or 4 if partially visible)
          var okCanvases = diag.retainedCanvases <= 3;
          var okConcurrency = diag.activeRenderJobs <= 1;
          var ok = okCanvases && okConcurrency && diag.totalDocumentPages === totalExpectedPages;
          updateRow('row-load', diag, ok, ok ? null : `Retained: ${{diag.retainedCanvases}} (expected <= 3)`);
          if (!ok) throw new Error(`Load bounds violated: retainedCanvases=${{diag.retainedCanvases}}, activeJobs=${{diag.activeRenderJobs}}`);
          log(`Phase 2 Load Verified: Pages=${{diag.totalDocumentPages}}, Retained canvases=${{diag.retainedCanvases}} <= 3. PASS.`);
        }});
        if (!p2) return;

        // Phase 3: Post-Load Idle
        var p3 = await runPhase('3. Post-Load Idle', 'row-idle', 4000, async () => {{
          await sleep(500);
          var diag = viewer.getDiagnostics();
          var ok = diag.activeRenderJobs === 0 && diag.queuedRenderJobs === 0;
          updateRow('row-idle', diag, ok, ok ? null : 'Active jobs running during idle');
          if (!ok) throw new Error(`Idle work detected: active=${{diag.activeRenderJobs}}, queued=${{diag.queuedRenderJobs}}`);
          log(`Phase 3 Idle Verified: 0 active and 0 queued jobs. PASS.`);
        }});
        if (!p3) return;

        // Phase 4: Scroll Virtualization & Canvas Eviction
        var p4 = await runPhase('4. Scroll Virtualization', 'row-scroll', 10000, async () => {{
          var vp = document.getElementById('pdf-viewport');
          if (!vp) throw new Error('pdf-viewport element missing');

          log('Scrolling viewport to test lazy rendering and offscreen canvas eviction...');
          if (totalExpectedPages > 1) {{
            // Scroll down
            vp.scrollTop = vp.scrollHeight;
            viewer.updateVirtualization();
            await waitForCondition(() => viewer.getDiagnostics().activeRenderJobs === 0, 6000);
          }}

          var diag = viewer.getDiagnostics();
          // Critical check: Canvas count must remain bounded (<= 4)
          var ok = diag.retainedCanvases <= 4;
          updateRow('row-scroll', diag, ok, ok ? null : `Canvases=${{diag.retainedCanvases}} > 4`);
          if (!ok) throw new Error(`Canvas eviction failed: retainedCanvases=${{diag.retainedCanvases}}`);
          log(`Phase 4 Scroll Eviction Verified: Retained canvases=${{diag.retainedCanvases}} <= 4. PASS.`);
        }});
        if (!p4) return;

        // Phase 5: Cross-Page Selection Pinning
        var p5 = await runPhase('5. Selection Pinning', 'row-select', 10000, async () => {{
          log('Testing selection pinning and preservation during scroll...');
          var vp = document.getElementById('pdf-viewport');
          var pageWrappers = document.querySelectorAll('.pdf-page-wrapper');
          var sel = window.getSelection();

          if (pageWrappers.length >= 2 && sel) {{
            var pStart = pageWrappers[0];
            var pEnd = pageWrappers[1];
            var r = document.createRange();
            r.setStart(pStart.querySelector('.textLayer') || pStart, 0);
            r.setEnd(pEnd.querySelector('.textLayer') || pEnd, 0);
            sel.removeAllRanges();
            sel.addRange(r);

            viewer.updateVirtualization();
            var diagSelect = viewer.getDiagnostics();
            if (diagSelect.pinnedPages.length < 2) {{
              throw new Error(`Pages failed to pin: pinnedPages=[${{diagSelect.pinnedPages.join(',')}}]`);
            }}
            log(`Selection active: pinnedPages=[${{diagSelect.pinnedPages.join(',')}}]`);

            // Scroll away
            if (vp) vp.scrollTop = vp.scrollHeight;
            viewer.updateVirtualization();
            var diagScrolled = viewer.getDiagnostics();

            // Verify pinned pages remained mounted despite being scrolled away
            var stayPinned = diagSelect.pinnedPages.every(p => diagScrolled.pinnedPages.includes(p));
            if (!stayPinned) throw new Error('Pinned pages were unpinned during scroll');

            // Clear selection
            sel.removeAllRanges();
            viewer.updateVirtualization();
            var diagCleared = viewer.getDiagnostics();
            var unpinned = diagCleared.pinnedPages.length === 0;
            if (!unpinned) throw new Error('Pinned pages not released after selection clear');

            updateRow('row-select', diagCleared, true);
            log(`Phase 5 Selection Pinning Verified: Pinning & unpinning work correctly. PASS.`);
          }} else {{
            updateRow('row-select', viewer.getDiagnostics(), true, 'Single page tested');
            log(`Phase 5 Selection Pinning: Single page document, skipped multi-page span. PASS.`);
          }}
        }});
        if (!p5) return;

        // Phase 6: Zoom Scaling (Bounded Concurrency & Scaling)
        var p6 = await runPhase('6. Zoom Scaling', 'row-zoom', 8000, async () => {{
          log('Testing zoom scaling bounded concurrency (0.75x -> 1.5x -> 1.0x)...');
          var zoomInBtn = document.getElementById('pdf-zoom-in');
          var zoomOutBtn = document.getElementById('pdf-zoom-out');

          if (zoomOutBtn) zoomOutBtn.click();
          await sleep(200);
          if (zoomInBtn) zoomInBtn.click();
          await sleep(200);

          await waitForCondition(() => viewer.getDiagnostics().activeRenderJobs === 0, 5000);
          var diag = viewer.getDiagnostics();
          var ok = diag.retainedCanvases <= 4 && diag.activeRenderJobs <= 1;
          updateRow('row-zoom', diag, ok, ok ? null : 'Unbounded zoom canvases');
          if (!ok) throw new Error(`Zoom test failed: retainedCanvases=${{diag.retainedCanvases}}`);
          log(`Phase 6 Zoom Scaling Verified: Retained canvases=${{diag.retainedCanvases}} <= 4. PASS.`);
        }});
        if (!p6) return;

        // Phase 7: Close Teardown & Lifecycle
        var p7 = await runPhase('7. Close Teardown', 'row-teardown', 5000, async () => {{
          log('Closing viewer and verifying full asynchronous resource teardown...');
          viewer.close();
          await sleep(300);

          var diag = viewer.getDiagnostics();
          var ok = (
            diag.activeDocuments === 0 &&
            diag.hasActivePdfDocument === false &&
            diag.hasActiveLoadingTask === false &&
            diag.retainedCanvases === 0 &&
            diag.totalBackingStorePixels === 0 &&
            diag.mountedTextLayers === 0 &&
            diag.pinnedPages.length === 0
          );
          updateRow('row-teardown', diag, ok, ok ? null : 'Resources leaked on close');
          if (!ok) throw new Error(`Teardown leak: canvases=${{diag.retainedCanvases}}, docs=${{diag.activeDocuments}}`);
          log(`Phase 7 Teardown Verified: 0 canvases, 0 documents, 0 mounted text layers. PASS.`);
        }});
        if (!p7) return;

        log('==================================================');
        log('*** ALL PERFORMANCE VERIFICATION PHASES PASSED! ***');
        log('==================================================');
      }} catch(err) {{
        log(`Unexpected test suite error: ${{err.message}}`);
      }} finally {{
        setControlsState(false);
      }}
    }}

    // Export Handlers
    function exportResultsJson() {{
      var exportData = {{
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        devicePixelRatio: window.devicePixelRatio || 1,
        windowSize: {{ width: window.innerWidth, height: window.innerHeight }},
        diagnosticsHistory: collectedDiagnostics,
        logHistory: logHistory
      }};
      var blob = new Blob([JSON.stringify(exportData, null, 2)], {{ type: 'application/json' }});
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = `vortex-pdf-diag-${{new Date().toISOString().replace(/[:.]/g, '-')}}.json`;
      a.click();
      URL.revokeObjectURL(url);
      log('Exported diagnostic results to JSON.');
    }}

    function exportLogText() {{
      var blob = new Blob([logHistory.join('\\n')], {{ type: 'text/plain' }});
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = `vortex-pdf-log-${{new Date().toISOString().replace(/[:.]/g, '-')}}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      log('Exported log history to text file.');
    }}

    // Button Listeners
    document.getElementById('btn-run-small').addEventListener('click', () => {{
      runBenchmarkWorkload('/tests/fixtures/pdf/multipage.pdf', 'multipage.pdf', 3, false);
    }});
    document.getElementById('btn-run-20').addEventListener('click', () => {{
      runBenchmarkWorkload('/tests/fixtures/pdf/multipage_20.pdf', 'multipage_20.pdf', 20, false);
    }});
    document.getElementById('btn-run-50').addEventListener('click', () => {{
      runBenchmarkWorkload('/tests/fixtures/pdf/multipage_50.pdf', 'multipage_50.pdf', 50, true);
    }});

    document.getElementById('btn-stop').addEventListener('click', stopBenchmark);
    document.getElementById('btn-hud-stop').addEventListener('click', stopBenchmark);

    document.getElementById('btn-open-manual').addEventListener('click', () => {{
      window.VortexPdfViewer.open('/tests/fixtures/pdf/multipage.pdf', 'multipage.pdf');
    }});
    document.getElementById('btn-open-lists').addEventListener('click', () => {{
      window.VortexPdfViewer.open('/tests/fixtures/pdf/lists.pdf', 'lists.pdf');
    }});
    document.getElementById('btn-open-resume').addEventListener('click', () => {{
      window.VortexPdfViewer.open('/tests/fixtures/pdf/resume.pdf', 'resume.pdf');
    }});
    document.getElementById('btn-close-manual').addEventListener('click', () => {{
      window.VortexPdfViewer.close();
    }});

    var toggleTraceBtn = document.getElementById('btn-toggle-trace');
    if (toggleTraceBtn) {{
      toggleTraceBtn.addEventListener('click', function() {{
        if (window.VortexPdfViewer && window.VortexPdfViewer.enableDragTrace) {{
          var isEnabled = window.VortexPdfViewer.isDragTraceEnabled();
          var newState = window.VortexPdfViewer.enableDragTrace(!isEnabled);
          this.textContent = 'Toggle Drag Trace (' + (newState ? 'ON' : 'Off') + ')';
          log('Real-time drag trace ' + (newState ? 'ENABLED (recording up to 50 drag events)' : 'DISABLED'));
        }}
      }});
    }}

    document.getElementById('btn-capture-diag').addEventListener('click', () => {{
      if (window.VortexPdfViewer && window.VortexPdfViewer.exportSelectionDiagnostic) {{
        var d = window.VortexPdfViewer.exportSelectionDiagnostic();
        var cont = document.getElementById('diag-container');
        var box = document.getElementById('diag-display');
        if (cont && box) {{
          cont.style.display = 'block';
          box.textContent = JSON.stringify(d, null, 2);
        }}
      }}
    }});
    document.getElementById('btn-close-diag-view').addEventListener('click', () => {{
      var cont = document.getElementById('diag-container');
      if (cont) cont.style.display = 'none';
    }});

    // Update loaded build id badge
    function updateHarnessBuildBadge() {{
      var badge = document.getElementById('harness-build-id');
      if (badge && window.VortexPdfViewer && window.VortexPdfViewer.buildId) {{
        badge.textContent = window.VortexPdfViewer.buildId;
      }}
    }}
    document.addEventListener('DOMContentLoaded', updateHarnessBuildBadge);
    setTimeout(updateHarnessBuildBadge, 150);

    document.getElementById('btn-export-json').addEventListener('click', exportResultsJson);
    document.getElementById('btn-export-log').addEventListener('click', exportLogText);
  </script>
</body>
</html>
"""

def main():
    repo_root = Path(__file__).resolve().parent.parent
    target_path = repo_root / "tests" / "browser_perf_test.html"
    content = build_harness_html()
    target_path.write_text(content, encoding="utf-8")
    print(f"Generated {target_path} ({len(content)} bytes)")

if __name__ == "__main__":
    main()
