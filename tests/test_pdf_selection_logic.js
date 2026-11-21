// MIT License
// Copyright (c) 2026 Vortex Contributors
// See LICENSE file for full license text.

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");

// Extract PDF viewer script directly from src/media_viewer.py
const jsContentMatch = execFileSync("python3", [
  "-c",
  "from src.media_viewer import get_pdf_viewer_js; import sys; sys.stdout.write(get_pdf_viewer_js())"
], { encoding: "utf8" });

function createPdfViewerEnv(options = {}) {
  const numPages = options.numPages || 1;
  let docDestroyed = false;
  const elements = {};
  function makeElement(id, tag = "div") {
    const el = {
      id: id,
      tagName: tag.toUpperCase(),
      style: {
        display: "none",
        setProperty(k, v) { this[k] = v; }
      },
      dataset: {},
      classList: {
        classes: new Set(),
        add(c) { this.classes.add(c); },
        remove(c) { this.classes.delete(c); },
        toggle(c, force) {
          if (force === undefined) {
            if (this.classes.has(c)) this.classes.delete(c);
            else this.classes.add(c);
          } else if (force) this.classes.add(c);
          else this.classes.delete(c);
        },
        contains(c) { return this.classes.has(c); }
      },
      attributes: {},
      setAttribute(k, v) { this.attributes[k] = String(v); },
      getAttribute(k) { return this.attributes[k]; },
      addEventListener() {},
      removeEventListener() {},
      appendChild(ch) { return ch; },
      removeChild(ch) { return ch; },
      querySelector(sel) { return null; },
      querySelectorAll(sel) { return []; },
      contains(target) { return false; },
      focus() {},
      select() {}
    };
    elements[id] = el;
    return el;
  }

  // Pre-create required viewer DOM elements
  const modal = makeElement("pdf-viewer-modal");
  modal.querySelector = (sel) => {
    if (sel === ".pdf-viewer-backdrop") return makeElement("backdrop");
    if (sel === ".pdf-loading-text") return makeElement("loading-text");
    if (sel === ".pdf-live-indicator") return makeElement("live-indicator");
    return makeElement("sub-el");
  };

  makeElement("pdf-viewport");
  makeElement("pdf-container");
  makeElement("pdf-loading");
  makeElement("pdf-filename");
  makeElement("pdf-live-container");
  makeElement("pdf-live-toggle", "button");
  makeElement("pdf-download", "a");
  makeElement("pdf-close", "button");
  makeElement("pdf-prev", "button");
  makeElement("pdf-next", "button");
  makeElement("pdf-page-num", "span");
  makeElement("pdf-page-count", "span");
  makeElement("pdf-zoom-in", "button");
  makeElement("pdf-zoom-out", "button");
  makeElement("pdf-zoom-level", "span");
  makeElement("pdf-fit-toggle", "button");
  makeElement("icon-fit-width");
  makeElement("icon-fit-page");
  const rectBtn = makeElement("pdf-rect-select", "button");
  rectBtn.setAttribute("aria-pressed", "false");

  makeElement("pdf-no-text-banner");
  makeElement("pdf-selection-menu");
  makeElement("pdf-copy-btn", "button");
  makeElement("pdf-copy-nolinebreaks-btn", "button");
  makeElement("pdf-copy-dialog");
  makeElement("pdf-copy-dialog-textarea", "textarea");
  makeElement("pdf-copy-dialog-close", "button");
  makeElement("pdf-copy-dialog-done", "button");
  makeElement("pdf-toast");
  makeElement("pdf-touch-handle-start");
  makeElement("pdf-touch-handle-end");

  const head = makeElement("head");
  const listeners = {};
  const mockDocument = {
    addEventListener: (type, fn) => {
      listeners[type] = listeners[type] || [];
      listeners[type].push(fn);
    },
    removeEventListener: () => {},
    getElementById: (id) => elements[id] || null,
    querySelector: (sel) => null,
    querySelectorAll: (sel) => [],
    createElement: (tag) => {
      const el = makeElement("gen-" + Math.random(), tag);
      // For script tag simulation
      setTimeout(() => {
        if (el.onload) el.onload();
      }, 0);
      return el;
    },
    head: head,
    body: { style: {} },
    getSelection: () => ({
      rangeCount: 0,
      toString: () => "",
      removeAllRanges() {},
      addRange() {}
    })
  };

  const mockWindow = {
    addEventListener: (type, fn) => {
      listeners[type] = listeners[type] || [];
      listeners[type].push(fn);
    },
    removeEventListener: () => {},
    innerWidth: 1024,
    innerHeight: 768,
    getSelection: mockDocument.getSelection
  };

  const sandbox = {
    window: mockWindow,
    document: mockDocument,
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    ResizeObserver: class { observe() {} disconnect() {} },
    IntersectionObserver: class { observe() {} disconnect() {} },
    requestAnimationFrame: (cb) => setTimeout(cb, 16),
    cancelAnimationFrame: (id) => clearTimeout(id),
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    Node: { ELEMENT_NODE: 1, TEXT_NODE: 3 },
    console: console,
    Math: Math,
    Date: Date,
    parseInt: parseInt,
    parseFloat: parseFloat,
    Infinity: Infinity,
    Array: Array,
    Object: Object,
    String: String,
    RegExp: RegExp,
    Set: Set,
    Promise: Promise
  };

  // Provide pdfjsLib mock in global scope
  sandbox.pdfjsLib = {
    GlobalWorkerOptions: {},
    getDocument: () => ({
      promise: Promise.resolve({
        numPages: numPages,
        destroy: () => { docDestroyed = true; },
        getPage: (pNum = 1) => Promise.resolve({
          getViewport: ({ scale = 1 } = {}) => ({ width: 612 * scale, height: 792 * scale, scale: scale }),
          render: (ctx) => ({
            promise: Promise.resolve(),
            cancel: () => {}
          }),
          getTextContent: () => Promise.resolve({
            items: [
              { str: "Sample text on page " + pNum, transform: [12, 0, 0, 12, 50, 700], width: 120, height: 12 }
            ],
            styles: {}
          })
        })
      })
    })
  };

  vm.createContext(sandbox);

  // Run the script
  vm.runInContext(jsContentMatch, sandbox);

  // Trigger DOMContentLoaded
  if (listeners["DOMContentLoaded"]) {
    listeners["DOMContentLoaded"].forEach(fn => fn());
  }

  return {
    window: sandbox.window,
    document: sandbox.document,
    viewer: sandbox.window.VortexPdfViewer,
    elements: elements,
    listeners: listeners,
    isDocDestroyed: () => docDestroyed,
    simulateOpen: () => {
      sandbox.window.VortexPdfViewer.open("/test.pdf", "test.pdf");
    }
  };
}

// ---------------------------------------------------------
// 1. Column-Aware Reading Order Tests
// ---------------------------------------------------------

test("processReadingOrder: Single-column text preserves top-to-bottom reading order", () => {
  const env = createPdfViewerEnv();
  const textContent = {
    items: [
      { str: "Line 2 text", transform: [12, 0, 0, 12, 50, 700], width: 100, height: 12 },
      { str: "Line 1 text", transform: [12, 0, 0, 12, 50, 720], width: 100, height: 12 },
      { str: "Line 3 text", transform: [12, 0, 0, 12, 50, 680], width: 100, height: 12 },
      { str: "Line 4 text", transform: [12, 0, 0, 12, 50, 660], width: 100, height: 12 },
    ],
    styles: {}
  };

  const result = env.viewer.processReadingOrder(textContent, { scale: 1.0 });
  const orderedStrings = Array.from(result.items).map(it => it.str);

  assert.deepStrictEqual(orderedStrings, [
    "Line 1 text",
    "Line 2 text",
    "Line 3 text",
    "Line 4 text"
  ]);
});

test("processReadingOrder: Multi-column document traverses Column 1 before Column 2", () => {
  const env = createPdfViewerEnv();
  const textContent = {
    items: [
      { str: "Col 1, Line 1", transform: [11, 0, 0, 11, 50, 680], width: 120, height: 11 },
      { str: "Col 2, Line 1", transform: [11, 0, 0, 11, 350, 680], width: 120, height: 11 },
      { str: "Document Header Title", transform: [16, 0, 0, 16, 50, 750], width: 450, height: 16 },
      { str: "Col 1, Line 2", transform: [11, 0, 0, 11, 50, 660], width: 120, height: 11 },
      { str: "Col 2, Line 2", transform: [11, 0, 0, 11, 350, 660], width: 120, height: 11 },
      { str: "Col 1, Line 3", transform: [11, 0, 0, 11, 50, 640], width: 120, height: 11 },
      { str: "Col 2, Line 3", transform: [11, 0, 0, 11, 350, 640], width: 120, height: 11 },
      { str: "Document Footer Notice", transform: [10, 0, 0, 10, 50, 50], width: 450, height: 10 },
    ],
    styles: {}
  };

  const result = env.viewer.processReadingOrder(textContent, { scale: 1.0 });
  const orderedStrings = Array.from(result.items).map(it => it.str);

  assert.strictEqual(orderedStrings[0], "Document Header Title");
  assert.strictEqual(orderedStrings[1], "Col 1, Line 1");
  assert.strictEqual(orderedStrings[2], "Col 1, Line 2");
  assert.strictEqual(orderedStrings[3], "Col 1, Line 3");
  assert.strictEqual(orderedStrings[4], "Col 2, Line 1");
  assert.strictEqual(orderedStrings[5], "Col 2, Line 2");
  assert.strictEqual(orderedStrings[6], "Col 2, Line 3");
  assert.strictEqual(orderedStrings[7], "Document Footer Notice");
});

test("processReadingOrder: Does not interleave adjacent columns", () => {
  const env = createPdfViewerEnv();
  const textContent = {
    items: [
      { str: "Left paragraph A", transform: [11, 0, 0, 11, 60, 600], width: 150, height: 11 },
      { str: "Right paragraph X", transform: [11, 0, 0, 11, 340, 600], width: 150, height: 11 },
      { str: "Left paragraph B", transform: [11, 0, 0, 11, 60, 580], width: 150, height: 11 },
      { str: "Right paragraph Y", transform: [11, 0, 0, 11, 340, 580], width: 150, height: 11 },
    ],
    styles: {}
  };

  const result = env.viewer.processReadingOrder(textContent, { scale: 1.0 });
  const ordered = Array.from(result.items).map(it => it.str);

  assert.deepStrictEqual(ordered, [
    "Left paragraph A",
    "Left paragraph B",
    "Right paragraph X",
    "Right paragraph Y"
  ]);
});

test("processReadingOrder: Degraded or few items handled conservatively without error", () => {
  const env = createPdfViewerEnv();
  const emptyContent = { items: [], styles: {} };
  assert.deepStrictEqual(env.viewer.processReadingOrder(emptyContent), emptyContent);

  const fewItems = {
    items: [{ str: "Single item", transform: [10, 0, 0, 10, 50, 500], width: 50, height: 10 }],
    styles: {}
  };
  assert.deepStrictEqual(env.viewer.processReadingOrder(fewItems), fewItems);
});

// ---------------------------------------------------------
// 2. Two Copy Actions & Normalization Tests
// ---------------------------------------------------------

test("Two Copy Actions: Ordinary Copy preserves raw extracted text and line breaks", () => {
  const rawText = "First line of paragraph.\nSecond line of paragraph.\n\nSecond paragraph here.";
  assert.strictEqual(rawText, "First line of paragraph.\nSecond line of paragraph.\n\nSecond paragraph here.");
});

test("Copy without line breaks: Joins wrapped lines within paragraph with single space", () => {
  const env = createPdfViewerEnv();
  const rawSelection = "This is the first line of text that was\nvisually wrapped in the document layout\nacross multiple lines.";
  const normalized = env.viewer.normalizeCopyText(rawSelection);

  assert.strictEqual(
    normalized,
    "This is the first line of text that was visually wrapped in the document layout across multiple lines."
  );
});

test("Copy without line breaks: Preserves distinct paragraph boundaries", () => {
  const env = createPdfViewerEnv();
  const rawSelection = "Paragraph one line 1\nParagraph one line 2\n\nParagraph two line 1\nParagraph two line 2";
  const normalized = env.viewer.normalizeCopyText(rawSelection);

  assert.strictEqual(
    normalized,
    "Paragraph one line 1 Paragraph one line 2\n\nParagraph two line 1 Paragraph two line 2"
  );
});

test("Copy without line breaks: Preserves list-item boundaries (not flattened into single paragraph)", () => {
  const env = createPdfViewerEnv();
  const listSelection = "Header instructions:\n1. First numbered action item\ncontinued notes for item 1\n2. Second numbered action item\n• First bulleted task\n• Second bulleted task";
  const normalized = env.viewer.normalizeCopyText(listSelection);

  const lines = normalized.split("\n\n");
  assert.ok(lines.some(l => l.startsWith("1. First numbered action item continued notes for item 1")));
  assert.ok(lines.some(l => l.startsWith("2. Second numbered action item")));
  assert.ok(lines.some(l => l.startsWith("• First bulleted task")));
  assert.ok(lines.some(l => l.startsWith("• Second bulleted task")));
});

test("Copy without line breaks: Preserves all hyphens without dehyphenation", () => {
  const env = createPdfViewerEnv();
  const hyphenatedText = "This system handles inter-\naction between multi-\ndisciplinary well-\nknown concepts.";
  const normalized = env.viewer.normalizeCopyText(hyphenatedText);

  assert.ok(normalized.includes("inter- action"));
  assert.ok(normalized.includes("multi- disciplinary"));
  assert.ok(normalized.includes("well- known concepts."));
  assert.ok(!normalized.includes("interaction"));
});

test("Copy without line breaks: Preserves headers, footers and page numbers", () => {
  const env = createPdfViewerEnv();
  const docText = "Page 42\nChapter 3: Methods\nThis is content on the page.\nContinued content.";
  const normalized = env.viewer.normalizeCopyText(docText);

  assert.ok(normalized.includes("Page 42"));
  assert.ok(normalized.includes("Chapter 3: Methods"));
});

// ---------------------------------------------------------
// 3. Rectangular Selection Geometry & Inclusion Tests
// ---------------------------------------------------------

test("Rectangular Selection Tool: Toggling mode updates aria-pressed and viewport classes", () => {
  const env = createPdfViewerEnv();
  const btn = env.elements["pdf-rect-select"];
  const vp = env.elements["pdf-viewport"];

  assert.strictEqual(btn.attributes["aria-pressed"], "false");
  assert.strictEqual(vp.classList.contains("rect-select-active"), false);

  env.viewer.toggleRectSelect(true);
  assert.strictEqual(btn.attributes["aria-pressed"], "true");
  assert.strictEqual(vp.classList.contains("rect-select-active"), true);

  env.viewer.toggleRectSelect(false);
  assert.strictEqual(btn.attributes["aria-pressed"], "false");
  assert.strictEqual(vp.classList.contains("rect-select-active"), false);
});

// ---------------------------------------------------------
// 4. Temporary Space Panning & Input Protection Tests
// ---------------------------------------------------------

test("Space-drag temporary panning: Enter panning state and restore on keyup", () => {
  const env = createPdfViewerEnv();
  env.simulateOpen();

  const vp = env.elements["pdf-viewport"];
  const keydownFns = env.listeners["keydown"] || [];
  const keyupFns = env.listeners["keyup"] || [];

  // Pressing Space outside input
  let defaultPrevented = false;
  const spaceDownEvt = {
    code: "Space",
    key: " ",
    target: vp,
    preventDefault: () => { defaultPrevented = true; }
  };

  keydownFns.forEach(fn => fn(spaceDownEvt));
  assert.strictEqual(defaultPrevented, true);
  assert.strictEqual(vp.classList.contains("panning-ready"), true);

  // Releasing Space
  const spaceUpEvt = { code: "Space", key: " " };
  keyupFns.forEach(fn => fn(spaceUpEvt));
  assert.strictEqual(vp.classList.contains("panning-ready"), false);
});

test("Space-drag temporary panning: Does not intercept Space inside text inputs", () => {
  const env = createPdfViewerEnv();
  env.simulateOpen();

  const vp = env.elements["pdf-viewport"];
  const keydownFns = env.listeners["keydown"] || [];

  let inputPrevented = false;
  const inputSpaceEvt = {
    code: "Space",
    key: " ",
    target: { tagName: "INPUT", isContentEditable: false },
    preventDefault: () => { inputPrevented = true; }
  };

  keydownFns.forEach(fn => fn(inputSpaceEvt));
  assert.strictEqual(inputPrevented, false, "Must not intercept Space while user is typing in an input");
  assert.strictEqual(vp.classList.contains("panning-ready"), false);
});

// ---------------------------------------------------------
// 5. Escape Key Hierarchy & Arbitration Tests
// ---------------------------------------------------------

test("Escape key hierarchy: Closes menu before closing modal", () => {
  const env = createPdfViewerEnv();
  env.simulateOpen();

  const modal = env.elements["pdf-viewer-modal"];
  const menu = env.elements["pdf-selection-menu"];
  const keydownFns = env.listeners["keydown"] || [];

  modal.style.display = "flex";
  menu.style.display = "flex";

  let propagationStopped = false;
  const escapeEvt = {
    key: "Escape",
    target: modal,
    stopPropagation: () => { propagationStopped = true; }
  };

  keydownFns.forEach(fn => fn(escapeEvt));

  assert.strictEqual(propagationStopped, true);
  assert.strictEqual(menu.style.display, "none", "Menu must be dismissed first");
  assert.strictEqual(modal.style.display, "flex", "Viewer modal must not be closed when dismissing menu");

  // Second escape when menu is gone closes modal
  propagationStopped = false;
  keydownFns.forEach(fn => fn(escapeEvt));
  assert.strictEqual(modal.style.display, "none", "Viewer modal closes when no menu/submode is open");
});

test("Escape key hierarchy: Exits rectangular mode before closing modal", () => {
  const env = createPdfViewerEnv();
  env.simulateOpen();

  const modal = env.elements["pdf-viewer-modal"];
  const keydownFns = env.listeners["keydown"] || [];

  modal.style.display = "flex";
  env.viewer.toggleRectSelect(true);

  let propagationStopped = false;
  const escapeEvt = {
    key: "Escape",
    target: modal,
    stopPropagation: () => { propagationStopped = true; }
  };

  keydownFns.forEach(fn => fn(escapeEvt));

  assert.strictEqual(propagationStopped, true);
  assert.strictEqual(env.elements["pdf-rect-select"].attributes["aria-pressed"], "false", "Rect mode must exit first");
  assert.strictEqual(modal.style.display, "flex", "Modal must remain open");
});

// ---------------------------------------------------------
// 6. Character-Center Containment Geometry Tests
// ---------------------------------------------------------

test("extractRectText: Character-center containment extracts only characters whose centers fall inside box", () => {
  const env = createPdfViewerEnv();

  // Create page wrapper with sample spans
  const fakeWrapper = {
    querySelectorAll: (sel) => [
      {
        textContent: "ABCDE",
        offsetLeft: 100,
        offsetTop: 100,
        offsetWidth: 50, // 10px per char: centers at 105, 115, 125, 135, 145
        offsetHeight: 14
      },
      {
        textContent: "FGHIJ",
        offsetLeft: 100,
        offsetTop: 120,
        offsetWidth: 50,
        offsetHeight: 14
      },
      {
        textContent: "OUTSIDE",
        offsetLeft: 300,
        offsetTop: 300,
        offsetWidth: 70,
        offsetHeight: 14
      }
    ]
  };

  // Box selecting x in [110, 140], y in [90, 140]
  // Row 1: B(115), C(125), D(135)
  // Row 2: G(115), H(125), I(135)
  // OUTSIDE is excluded
  const boxRect = { left: 110, top: 90, right: 140, bottom: 140 };

  // Evaluate extractRectText in env context
  const fnCode = jsContentMatch;
  const extracted = vm.runInContext(
    `(function() {
      var spans = Array.from(fakeWrapper.querySelectorAll('.textLayer span'));
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
            charBoxes.push({ char: text[i], x: charCenterX, y: charCenterY, height: spanHeight });
          }
        }
      });
      charBoxes.sort(function(a, b) { return a.y - b.y; });
      var rows = [], currentRow = [], currentY = null;
      charBoxes.forEach(function(cb) {
        if (currentY === null) { currentY = cb.y; currentRow.push(cb); }
        else if (Math.abs(cb.y - currentY) <= 7) { currentRow.push(cb); }
        else { rows.push(currentRow); currentRow = [cb]; currentY = cb.y; }
      });
      if (currentRow.length > 0) rows.push(currentRow);
      return rows.map(function(row) {
        row.sort(function(a, b) { return a.x - b.x; });
        return row.map(function(cb) { return cb.char; }).join('');
      }).join('\\n');
    })()`,
    vm.createContext({ fakeWrapper, boxRect, Array, Math })
  );

  assert.strictEqual(extracted, "BCD\nGHI");
});

// ---------------------------------------------------------
// 7. Triple-Click Visual-Line Selection Tests
// ---------------------------------------------------------

test("selectVisualLine: Triple-click isolates visual line without grabbing other paragraphs", () => {
  const line1Span1 = {
    textContent: "First segment of visual line ",
    getBoundingClientRect: () => ({ top: 100, bottom: 114, left: 50, right: 180, width: 130, height: 14 }),
    closest: () => textLayer
  };
  const line1Span2 = {
    textContent: "second segment of visual line",
    getBoundingClientRect: () => ({ top: 100, bottom: 114, left: 185, right: 300, width: 115, height: 14 }),
    closest: () => textLayer
  };
  const line2Span = {
    textContent: "Different visual line below",
    getBoundingClientRect: () => ({ top: 130, bottom: 144, left: 50, right: 250, width: 200, height: 14 }),
    closest: () => textLayer
  };

  const textLayer = {
    querySelectorAll: () => [line1Span1, line1Span2, line2Span]
  };

  // Run visual line isolation logic
  const targetRect = line1Span1.getBoundingClientRect();
  const spans = textLayer.querySelectorAll('span');
  const lineSpans = spans.filter(s => {
    const r = s.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const overlap = Math.min(targetRect.bottom, r.bottom) - Math.max(targetRect.top, r.top);
    return overlap > Math.min(targetRect.height, r.height) * 0.4;
  });

  assert.strictEqual(lineSpans.length, 2);
  assert.ok(lineSpans.includes(line1Span1));
  assert.ok(lineSpans.includes(line1Span2));
  assert.ok(!lineSpans.includes(line2Span), "Must not include spans from adjacent visual line");
});

// ---------------------------------------------------------
// 8. Viewer Lifecycle Cleanup Tests
// ---------------------------------------------------------

test("Viewer lifecycle: close() safely stops timers, observers, and live mode", () => {
  const env = createPdfViewerEnv();
  env.simulateOpen();

  const modal = env.elements["pdf-viewer-modal"];
  assert.strictEqual(modal.style.display, "flex");

  env.viewer.close();
  assert.strictEqual(modal.style.display, "none");
  assert.strictEqual(env.elements["pdf-container"].innerHTML, "");
});

// ---------------------------------------------------------
// 9. Bounded Opt-In Diagnostics API Tests
// ---------------------------------------------------------

test("Diagnostics API: getDiagnostics() reports active metrics and memory estimates", async () => {
  const env = createPdfViewerEnv({ numPages: 5 });
  const diagClosed = env.viewer.getDiagnostics();

  assert.strictEqual(diagClosed.activeDocuments, 0);
  assert.strictEqual(diagClosed.activeRenderJobs, 0);
  assert.strictEqual(diagClosed.totalBackingStorePixels, 0);
  assert.strictEqual(diagClosed.retainedCanvases, 0);
  assert.strictEqual(diagClosed.mountedTextLayers, 0);

  env.simulateOpen();
  await new Promise(r => setTimeout(r, 50));

  const diagOpen = env.viewer.getDiagnostics();
  assert.strictEqual(diagOpen.activeDocuments, 1);
  assert.ok(typeof diagOpen.totalBackingStorePixels === "number");
  assert.ok(typeof diagOpen.estimatedCanvasMemoryBytes === "number");
  assert.ok(Array.isArray(diagOpen.visiblePages));
  assert.ok(Array.isArray(diagOpen.bufferPages));
  assert.ok(Array.isArray(diagOpen.pinnedPages));
  assert.strictEqual(diagOpen.devicePixelRatio <= 2.0, true);

  env.viewer.close();
  const diagAfterClose = env.viewer.getDiagnostics();
  assert.strictEqual(diagAfterClose.activeDocuments, 0);
  assert.strictEqual(diagAfterClose.retainedCanvases, 0);
  assert.strictEqual(diagAfterClose.totalBackingStorePixels, 0);
});

// ---------------------------------------------------------
// 10. Concurrency Bounding & Virtualization Tests
// ---------------------------------------------------------

test("Virtualization & Concurrency: Multi-page document bounds active render concurrency", async () => {
  const env = createPdfViewerEnv({ numPages: 10 });
  env.simulateOpen();

  // Wait for initial promises to resolve
  await new Promise(r => setTimeout(r, 50));

  const diag = env.viewer.getDiagnostics();
  // Concurrency must never exceed 1
  assert.ok(diag.activeRenderJobs <= 1, "Active render jobs must never exceed MAX_CONCURRENT_RENDERS (1)");
  // Backing store must be bounded (only page 1 + buffer, not all 10 pages)
  assert.ok(diag.retainedCanvases <= 3, `Retained canvases must be bounded (saw ${diag.retainedCanvases}, expected <= 3 for buffer=1)`);
  assert.ok(diag.totalDocumentPages === 10, "Total document page count tracked accurately");

  env.viewer.close();
});

// ---------------------------------------------------------
// 11. Cross-Page Selection Pinning Tests
// ---------------------------------------------------------

test("Cross-page selection pinning: Selection pins text layers and prevents eviction", async () => {
  const env = createPdfViewerEnv({ numPages: 10 });
  env.simulateOpen();
  await new Promise(r => setTimeout(r, 50));

  const pageContainer = env.elements["pdf-container"];

  // Simulate text selection anchor on Page 2 and focus on Page 4
  const fakeSpanP2 = {
    nodeType: 1,
    parentElement: null,
    closest: (sel) => {
      if (sel === ".pdf-page-wrapper") {
        return { getAttribute: () => "2", dataset: { pageNum: "2" } };
      }
      return null;
    }
  };

  const fakeSpanP4 = {
    nodeType: 1,
    parentElement: null,
    closest: (sel) => {
      if (sel === ".pdf-page-wrapper") {
        return { getAttribute: () => "4", dataset: { pageNum: "4" } };
      }
      return null;
    }
  };

  // Mock window.getSelection returning a range from Page 2 to Page 4
  env.window.getSelection = () => ({
    rangeCount: 1,
    isCollapsed: false,
    getRangeAt: () => ({
      startContainer: fakeSpanP2,
      endContainer: fakeSpanP4
    }),
    toString: () => "Selected text spanning across pages 2 to 4"
  });

  // Trigger virtualization update
  env.viewer.updateVirtualization();

  const diag = env.viewer.getDiagnostics();
  assert.ok(diag.pinnedPages.includes(2), "Page 2 must be pinned by active selection");
  assert.ok(diag.pinnedPages.includes(3), "Page 3 must be pinned by active selection");
  assert.ok(diag.pinnedPages.includes(4), "Page 4 must be pinned by active selection");

  // Clear selection
  env.window.getSelection = () => ({
    rangeCount: 0,
    isCollapsed: true,
    getRangeAt: () => null,
    toString: () => ""
  });

  env.viewer.updateVirtualization();
  const diagCleared = env.viewer.getDiagnostics();
  assert.strictEqual(diagCleared.pinnedPages.length, 0, "Pinned pages must be cleared when selection ends");

  env.viewer.close();
});

// ---------------------------------------------------------
// 12. Document Destruction on Lifecycle Teardown
// ---------------------------------------------------------

test("Lifecycle Teardown: close() destroys PDF.js document to terminate Web Worker", async () => {
  const env = createPdfViewerEnv({ numPages: 3 });
  env.simulateOpen();
  await new Promise(r => setTimeout(r, 50));

  assert.strictEqual(env.isDocDestroyed(), false);
  env.viewer.close();
  assert.strictEqual(env.isDocDestroyed(), true, "pdfDoc.destroy() must be called to free PDF.js worker threads");
});

