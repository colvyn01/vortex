const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const { execFileSync } = require("node:child_process");

// Extract actual implementation functions directly from src/scripts.py
const scriptContent = fs.readFileSync("src/scripts.py", "utf8");
const fullScriptContent = execFileSync("python3", ["-W", "ignore", "-c", "from src.scripts import JS_UPLOAD_HANDLER; import sys; sys.stdout.write(JS_UPLOAD_HANDLER)"], { encoding: "utf8" });

const sizeFnMatch = scriptContent.match(/function fetchDirectorySize\(targetPath\) {[\s\S]*?\n\t}/);
const navFnMatch = scriptContent.match(/function navigateToDirectory\(path, pushHistory\) {[\s\S]*?\n\t}/);

if (!sizeFnMatch || !navFnMatch) {
    throw new Error("Failed to extract functions from src/scripts.py");
}

const sizeFnCode = `var currentSizeRequestId = 0;\n${sizeFnMatch[0]}`;
const navFnCode = `var currentNavId = 0;\n${navFnMatch[0]}`;

function createEnvironment(initialPath = "/") {
    let elements = {};
    let historyStack = [];

    const env = {
        sessionId: "sess-123",
        DEVICE_ID: "dev-456",
        window: {
            location: {
                pathname: initialPath,
                href: `http://localhost:8000${initialPath}`,
            },
            history: {
                pushState: (state, title, url) => {
                    historyStack.push({ action: "push", state, url });
                    env.window.location.pathname = url;
                    env.window.location.href = `http://localhost:8000${url}`;
                },
                replaceState: (state, title, url) => {
                    historyStack.push({ action: "replace", state, url });
                },
            },
        },
        document: {
            getElementById: (id) => elements[id] || null,
            querySelector: (sel) => elements[sel] || null,
        },
        historyStack,
        setElement: (id, el) => {
            elements[id] = el;
        },
    };

    // DOMParser simulation for navigateToDirectory
    global.DOMParser = class {
        parseFromString(html) {
            return {
                querySelector: (sel) => {
                    if (sel === ".file-list") {
                        return { innerHTML: `<div>files for ${html}</div>` };
                    }
                    if (sel === ".device-subheader") {
                        const newSubheader = {
                            innerHTML: `<span>${html}</span><span id="dir-size-info">Calculating size...</span>`,
                        };
                        return newSubheader;
                    }
                    if (sel === "#session-data") {
                        return { dataset: { baseDir: html } };
                    }
                    if (sel === "title") {
                        return { textContent: `Title for ${html}` };
                    }
                    return null;
                },
            };
        }
    };

    return env;
}

test("1. fetchDirectorySize updates current element and sends correct pathname", async () => {
    const env = createEnvironment("/my%20folder/");
    let label = { textContent: "Calculating size..." };
    env.setElement("dir-size-info", label);

    let requestedUrl = null;
    let requestedHeaders = null;
    const mockFetch = async (url, opts) => {
        requestedUrl = url;
        requestedHeaders = opts.headers;
        return {
            ok: true,
            json: async () => ({
                size: {
                    total_bytes: 512,
                    total_formatted: "512.0 B",
                    file_count: 3,
                },
            }),
        };
    };

    const runScript = new Function(
        "sessionId", "DEVICE_ID", "window", "document", "fetch",
        `${sizeFnCode}; return fetchDirectorySize;`
    );

    const fetchDirectorySize = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    await fetchDirectorySize();

    assert.ok(requestedUrl.includes("path=%2Fmy%2520folder%2F"), "Path must be URL-encoded in query param");
    assert.strictEqual(requestedHeaders["X-Device-ID"], "dev-456");
    assert.strictEqual(label.textContent, "Total: 512.0 B (3 files)");
});

test("2. Stale size response discarded after newer request", async () => {
    const env = createEnvironment("/folderA/");
    let label = { textContent: "Calculating size..." };
    env.setElement("dir-size-info", label);

    let resolveReq1;
    let resolveReq2;

    const mockFetch = (url) => {
        if (url.includes("folderA")) {
            return new Promise((res) => {
                resolveReq1 = () => res({
                    ok: true,
                    json: async () => ({
                        size: { total_formatted: "100.0 KB", file_count: 1 },
                    }),
                });
            });
        } else {
            return new Promise((res) => {
                resolveReq2 = () => res({
                    ok: true,
                    json: async () => ({
                        size: { total_formatted: "20.0 KB", file_count: 5 },
                    }),
                });
            });
        }
    };

    const runScript = new Function(
        "sessionId", "DEVICE_ID", "window", "document", "fetch",
        `${sizeFnCode}; return fetchDirectorySize;`
    );

    const fetchDirectorySize = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    // Request 1 initiated for folderA
    fetchDirectorySize("/folderA/");

    // Navigation occurs to folderB
    env.window.location.pathname = "/folderB/";
    env.window.location.href = "http://localhost:8000/folderB/";

    // Request 2 initiated for folderB
    fetchDirectorySize("/folderB/");

    // Request 2 finishes first
    resolveReq2();
    await new Promise((r) => setTimeout(r, 10));
    assert.strictEqual(label.textContent, "Total: 20.0 KB (5 files)");

    // Request 1 finishes later
    resolveReq1();
    await new Promise((r) => setTimeout(r, 10));

    // Must NOT be overwritten by folderA's result
    assert.strictEqual(label.textContent, "Total: 20.0 KB (5 files)");
});

test("3. Leaving folder and returning to same path discards stale request", async () => {
    const env = createEnvironment("/sub/");

    // Label 1 for first visit to /sub/
    let label1 = { textContent: "Calculating size..." };
    env.setElement("dir-size-info", label1);

    let resolveReq1;
    let resolveReq3;

    let reqCount = 0;
    const mockFetch = (url) => {
        reqCount++;
        const currentCount = reqCount;
        return new Promise((res) => {
            if (currentCount === 1) {
                resolveReq1 = () => res({
                    ok: true,
                    json: async () => ({
                        size: { total_formatted: "Old Size", file_count: 1 },
                    }),
                });
            } else if (currentCount === 2) {
                // /other/ request
                res({
                    ok: true,
                    json: async () => ({
                        size: { total_formatted: "Other Size", file_count: 2 },
                    }),
                });
            } else if (currentCount === 3) {
                resolveReq3 = () => res({
                    ok: true,
                    json: async () => ({
                        size: { total_formatted: "New Size", file_count: 9 },
                    }),
                });
            }
        });
    };

    const runScript = new Function(
        "sessionId", "DEVICE_ID", "window", "document", "fetch",
        `${sizeFnCode}; return fetchDirectorySize;`
    );

    const fetchDirectorySize = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    // 1. Visit /sub/, request 1 sent
    fetchDirectorySize("/sub/");

    // 2. Navigate away to /other/, subheader replaced
    let label2 = { textContent: "Calculating size..." };
    env.setElement("dir-size-info", label2);
    env.window.location.pathname = "/other/";
    env.window.location.href = "http://localhost:8000/other/";
    fetchDirectorySize("/other/");
    await new Promise((r) => setTimeout(r, 10));

    // 3. Navigate back to /sub/, subheader replaced again with label 3
    let label3 = { textContent: "Calculating size..." };
    env.setElement("dir-size-info", label3);
    env.window.location.pathname = "/sub/";
    env.window.location.href = "http://localhost:8000/sub/";
    fetchDirectorySize("/sub/");

    // Now request 1 finally resolves
    resolveReq1();
    await new Promise((r) => setTimeout(r, 10));

    // Stale request 1 must NOT update label3 (or detached label1)
    assert.strictEqual(label3.textContent, "Calculating size...");

    // Request 3 resolves
    resolveReq3();
    await new Promise((r) => setTimeout(r, 10));
    assert.strictEqual(label3.textContent, "Total: New Size (9 files)");
});

test("4. Error and malformed size response updates label to 'Size unavailable'", async () => {
    const env = createEnvironment("/");
    let label = { textContent: "Calculating size..." };
    env.setElement("dir-size-info", label);

    // Test HTTP 500 error
    let mockFetch = async () => ({
        ok: false,
        status: 500,
    });

    let runScript = new Function(
        "sessionId", "DEVICE_ID", "window", "document", "fetch",
        `${sizeFnCode}; return fetchDirectorySize;`
    );

    let fetchDirectorySize = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    await fetchDirectorySize();
    assert.strictEqual(label.textContent, "Size unavailable");

    // Test malformed response (missing size property)
    label.textContent = "Calculating size...";
    mockFetch = async () => ({
        ok: true,
        json: async () => ({ error: "something went wrong" }),
    });
    fetchDirectorySize = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    await fetchDirectorySize();
    assert.strictEqual(label.textContent, "Size unavailable");
});

test("5. Overlapping navigation requests: latest request wins, stale response ignored", async () => {
    const env = createEnvironment("/");
    const fileList = {
        innerHTML: "original",
        classList: { add: () => {}, remove: () => {} },
    };
    const subheader = { innerHTML: "original subheader" };
    const sessionData = { dataset: { baseDir: "/" } };
    env.setElement(".file-list", fileList);
    env.setElement(".device-subheader", subheader);
    env.setElement("#session-data", sessionData);

    let resolveNav1;
    let resolveNav2;

    const mockFetch = (url) => {
        if (url.includes("slow")) {
            return new Promise((res) => {
                resolveNav1 = () => res({
                    ok: true,
                    text: async () => "html-slow",
                });
            });
        } else {
            return new Promise((res) => {
                resolveNav2 = () => res({
                    ok: true,
                    text: async () => "html-fast",
                });
            });
        }
    };

    const combinedCode = `
        ${sizeFnCode}
        ${navFnCode}
        return navigateToDirectory;
    `;

    const runScript = new Function(
        "sessionId", "DEVICE_ID", "window", "document", "fetch",
        combinedCode
    );

    const navigateToDirectory = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    // Nav 1 (slow) started
    navigateToDirectory("/slow/");

    // Nav 2 (fast) started
    navigateToDirectory("/fast/");

    // Nav 2 completes first
    resolveNav2();
    await new Promise((r) => setTimeout(r, 10));

    assert.strictEqual(env.window.location.pathname, "/fast/");
    assert.ok(fileList.innerHTML.includes("html-fast"));

    // Nav 1 completes later
    resolveNav1();
    await new Promise((r) => setTimeout(r, 10));

    // Stale Nav 1 must NOT overwrite Nav 2
    assert.strictEqual(env.window.location.pathname, "/fast/");
    assert.ok(fileList.innerHTML.includes("html-fast"));
});

test("6. Failed older navigation does not redirect after newer navigation succeeds", async () => {
    const env = createEnvironment("/");
    const fileList = {
        innerHTML: "original",
        classList: { add: () => {}, remove: () => {} },
    };
    const subheader = { innerHTML: "original" };
    env.setElement(".file-list", fileList);
    env.setElement(".device-subheader", subheader);

    let rejectNav1;
    let resolveNav2;

    const mockFetch = (url) => {
        if (url.includes("bad")) {
            return new Promise((_, rej) => {
                rejectNav1 = () => rej(new Error("Network failed"));
            });
        } else {
            return new Promise((res) => {
                resolveNav2 = () => res({
                    ok: true,
                    text: async () => "html-good",
                });
            });
        }
    };

    const combinedCode = `
        ${sizeFnCode}
        ${navFnCode}
        return navigateToDirectory;
    `;

    const runScript = new Function(
        "sessionId", "DEVICE_ID", "window", "document", "fetch",
        combinedCode
    );

    const navigateToDirectory = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    // Nav 1 (bad) starts
    navigateToDirectory("/bad/");

    // Nav 2 (good) starts
    navigateToDirectory("/good/");

    // Nav 2 completes
    resolveNav2();
    await new Promise((r) => setTimeout(r, 10));
    assert.strictEqual(env.window.location.pathname, "/good/");

    // Nav 1 fails
    rejectNav1();
    await new Promise((r) => setTimeout(r, 10));

    // Window must NOT redirect to /bad/
    assert.strictEqual(env.window.location.pathname, "/good/");
    assert.strictEqual(env.window.location.href, "http://localhost:8000/good/");
});

test("7. Popstate navigation does not call history.pushState", async () => {
    const env = createEnvironment("/folder/");
    const fileList = {
        innerHTML: "original",
        classList: { add: () => {}, remove: () => {} },
    };
    const subheader = { innerHTML: "original" };
    env.setElement(".file-list", fileList);
    env.setElement(".device-subheader", subheader);

    const mockFetch = async () => ({
        ok: true,
        text: async () => "html-root",
    });

    const combinedCode = `
        ${sizeFnCode}
        ${navFnCode}
        return navigateToDirectory;
    `;

    const runScript = new Function(
        "sessionId", "DEVICE_ID", "window", "document", "fetch",
        combinedCode
    );

    const navigateToDirectory = runScript(
        env.sessionId, env.DEVICE_ID, env.window, env.document, mockFetch
    );

    // Popstate triggers navigateToDirectory("/", false)
    navigateToDirectory("/", false);
    await new Promise((r) => setTimeout(r, 10));

    // Verify pushState was NOT called
    const pushes = env.historyStack.filter((h) => h.action === "push");
    assert.strictEqual(pushes.length, 0, "pushState should not be called on popstate navigation");
    assert.ok(fileList.innerHTML.includes("html-root"), "DOM was updated for popstate destination");
});

// --- Startup Sequence Regression Tests ---

class MockQRCode {
    constructor(el, options) {
        this.el = el;
        this.options = options;
        el.children = el.children || [];
        el.children.push({
            tagName: "CANVAS",
            options,
        });
        MockQRCode.instances.push(this);
    }
}
MockQRCode.instances = [];
MockQRCode.CorrectLevel = { M: 0 };

function createStartupEnvironment({ pathname = "/", mockFetch, innerWidth = 800, hidden = false, theme = "light" } = {}) {
    const docListeners = {};
    const winListeners = {};
    const elements = {};

    const makeElement = (props = {}) => {
        const elListeners = {};
        let _innerHTML = props.innerHTML || "";
        let _children = props.children ? [...props.children] : [];
        let _textContent = props.textContent !== undefined ? props.textContent : "";
        const attrs = { ...(props.attrs || {}) };
        const el = {
            addEventListener: (ev, fn) => {
                elListeners[ev] = elListeners[ev] || [];
                elListeners[ev].push(fn);
            },
            get listeners() { return elListeners; },
            querySelector: (sel) => elements[sel] || null,
            querySelectorAll: () => [],
            setAttribute: (k, v) => { attrs[k] = String(v); },
            getAttribute: (k) => (attrs[k] !== undefined ? attrs[k] : null),
            closest: (sel) => null,
            classList: { add: () => {}, remove: () => {} },
            style: {},
            get textContent() { return _textContent; },
            set textContent(val) { _textContent = val; },
            get children() { return _children; },
            set children(val) { _children = val; },
            get innerHTML() { return _innerHTML; },
            set innerHTML(val) {
                _innerHTML = val;
                if (val === "") _children = [];
            },
            ...props,
        };
        return el;
    };

    const dirSizeLabel = makeElement({ textContent: "Calculating size..." });
    elements["session-data"] = makeElement({
        getAttribute: (attr) => (attr === "data-session-id" ? "sess-startup" : "/mock/base"),
        dataset: { baseDir: "/mock/base" },
    });
    elements["dir-size-info"] = dirSizeLabel;
    elements["server-stop-btn"] = makeElement();
    elements["stop-modal-overlay"] = makeElement();
    elements["stop-modal-cancel"] = makeElement();
    elements["stop-modal-confirm"] = makeElement();
    elements["theme-toggle"] = makeElement();
    elements["chat-messages"] = makeElement();
    elements["chat-form"] = makeElement({ querySelector: () => null });
    elements["chat-input"] = makeElement({ value: "" });
    elements["chat-status"] = makeElement();
    elements["qr-container"] = makeElement();
    elements["qr-code"] = makeElement();
    elements["qr-url-text"] = makeElement();
    elements[".device-main"] = makeElement();
    elements[".file-list"] = makeElement({ innerHTML: "files" });
    elements[".device-subheader"] = makeElement({ innerHTML: "subheader" });
    elements["document-element"] = makeElement({ attrs: { "data-theme": theme } });

    const doc = {
        documentElement: elements["document-element"],
        getElementById: (id) => elements[id] || null,
        querySelector: (sel) => elements[sel] || null,
        querySelectorAll: () => [],
        addEventListener: (ev, fn) => {
            docListeners[ev] = docListeners[ev] || [];
            docListeners[ev].push(fn);
        },
        cookie: "",
        hidden,
    };

    const mqlListeners = [];
    const win = {
        location: { pathname, href: `http://localhost:8000${pathname}` },
        history: {
            pushState: (state, title, url) => {
                win.location.pathname = url;
                win.location.href = `http://localhost:8000${url}`;
            },
            replaceState: () => {},
        },
        matchMedia: (query) => ({
            get matches() {
                if (query && query.includes("max-width: 900px")) {
                    return win.innerWidth <= 900;
                }
                return false;
            },
            addEventListener: (ev, fn) => {
                mqlListeners.push(fn);
            },
            removeEventListener: () => {},
            addListener: (fn) => {
                mqlListeners.push(fn);
            },
            removeListener: () => {},
        }),
        getComputedStyle: () => ({
            getPropertyValue: (prop) => {
                const currentTheme = elements["document-element"].getAttribute("data-theme") || theme;
                if (prop === "--text-main") {
                    return currentTheme === "dark" ? "#E0E0E0" : "#263238";
                }
                if (prop === "--surface-main") {
                    return currentTheme === "dark" ? "#1e252b" : "#ffffff";
                }
                return "";
            },
        }),
        addEventListener: (ev, fn) => {
            winListeners[ev] = winListeners[ev] || [];
            winListeners[ev].push(fn);
        },
        innerWidth,
    };

    const storage = {
        getItem: (k) => (k === "theme" ? theme : null),
        setItem: () => {},
    };

    const fetchImpl = async (url, opts) => {
        if (url.includes("/api/server-status")) {
            // Stop polling immediately in tests
            throw new Error("server status offline in test");
        }
        if (typeof mockFetch === "function") {
            return mockFetch(url, opts);
        }
        return { ok: true, json: async () => ({}) };
    };

    const runner = new Function(
        "document", "window", "localStorage", "fetch", "EventSource",
        fullScriptContent
    );
    runner(doc, win, storage, fetchImpl, class { close() {} });

    const triggerDOMContentLoaded = () => {
        for (const fn of (docListeners["DOMContentLoaded"] || [])) {
            fn();
        }
    };

    const triggerWinEvent = (ev) => {
        for (const fn of (winListeners[ev] || [])) {
            fn();
        }
        if (ev === "resize") {
            for (const fn of mqlListeners) {
                fn();
            }
        }
    };

    const triggerDocEvent = (ev) => {
        for (const fn of (docListeners[ev] || [])) {
            fn();
        }
    };

    return {
        doc,
        win,
        storage,
        elements,
        dirSizeLabel,
        listeners: docListeners,
        winListeners,
        triggerDOMContentLoaded,
        triggerWinEvent,
        triggerDocEvent,
    };
}

test("8. Startup sequence: Fresh load at '/' requests root size and updates label without navigation", async () => {
    let sizeRequestedUrl = null;
    let resolveSizeFetch = null;

    const mockFetch = (url) => {
        if (url.includes("/api/directory-size")) {
            sizeRequestedUrl = url;
            return new Promise((res) => {
                resolveSizeFetch = () => res({
                    ok: true,
                    json: async () => ({
                        size: { total_formatted: "10.0 MB", file_count: 42 },
                    }),
                });
            });
        }
        return Promise.resolve({ ok: true, json: async () => ({}) });
    };

    const env = createStartupEnvironment({ pathname: "/", mockFetch });
    env.triggerDOMContentLoaded();

    assert.ok(sizeRequestedUrl, "fetchDirectorySize must be called during DOMContentLoaded");
    assert.ok(sizeRequestedUrl.includes("path=%2F"), "Target path must be '/'");
    assert.strictEqual(env.dirSizeLabel.textContent, "Calculating size...");

    resolveSizeFetch();
    await new Promise((r) => setTimeout(r, 15));

    assert.strictEqual(env.dirSizeLabel.textContent, "Total: 10.0 MB (42 files)");
});

test("9. Startup sequence: Fresh load directly at subdirectory URL fetches and displays subdirectory size", async () => {
    let sizeRequestedUrl = null;
    const mockFetch = async (url) => {
        if (url.includes("/api/directory-size")) {
            sizeRequestedUrl = url;
            return {
                ok: true,
                json: async () => ({
                    size: { total_formatted: "350.0 KB", file_count: 4 },
                }),
            };
        }
        return { ok: true, json: async () => ({}) };
    };

    const env = createStartupEnvironment({ pathname: "/projects/vortex/", mockFetch });
    env.triggerDOMContentLoaded();

    await new Promise((r) => setTimeout(r, 15));

    assert.ok(sizeRequestedUrl.includes("path=%2Fprojects%2Fvortex%2F"), "Target path must be '/projects/vortex/'");
    assert.strictEqual(env.dirSizeLabel.textContent, "Total: 350.0 KB (4 files)");
});

test("10. Startup sequence: Fresh document/startup cycle representing full page refresh works reliably", async () => {
    // 1st cycle: Initial page load
    const mockFetch1 = async (url) => {
        if (url.includes("/api/directory-size")) {
            return {
                ok: true,
                json: async () => ({
                    size: { total_formatted: "1.0 MB", file_count: 5 },
                }),
            };
        }
        return { ok: true, json: async () => ({}) };
    };

    const env1 = createStartupEnvironment({ pathname: "/", mockFetch: mockFetch1 });
    env1.triggerDOMContentLoaded();
    await new Promise((r) => setTimeout(r, 15));
    assert.strictEqual(env1.dirSizeLabel.textContent, "Total: 1.0 MB (5 files)");

    // 2nd cycle: Full page refresh (fresh document, fresh window, clean state)
    let refreshSizeUrl = null;
    let resolveRefresh = null;
    const mockFetch2 = (url) => {
        if (url.includes("/api/directory-size")) {
            refreshSizeUrl = url;
            return new Promise((res) => {
                resolveRefresh = () => res({
                    ok: true,
                    json: async () => ({
                        size: { total_formatted: "2.0 MB", file_count: 10 },
                    }),
                });
            });
        }
        return Promise.resolve({ ok: true, json: async () => ({}) });
    };

    const env2 = createStartupEnvironment({ pathname: "/", mockFetch: mockFetch2 });
    env2.triggerDOMContentLoaded();

    assert.ok(refreshSizeUrl, "Refresh cycle must trigger size fetch");
    assert.strictEqual(env2.dirSizeLabel.textContent, "Calculating size...");

    resolveRefresh();
    await new Promise((r) => setTimeout(r, 15));

    // Confirm that counter hoisting/reset regression does not discard the first response on refresh
    assert.strictEqual(env2.dirSizeLabel.textContent, "Total: 2.0 MB (10 files)");
});

test("11. Startup sequence: Stale initial size request discarded if user navigates during startup", async () => {
    let resolveStartupFetch = null;
    let resolveNavSizeFetch = null;
    let reqCount = 0;

    const mockFetch = (url) => {
        if (url.includes("/api/directory-size")) {
            reqCount++;
            const current = reqCount;
            return new Promise((res) => {
                if (current === 1) {
                    resolveStartupFetch = () => res({
                        ok: true,
                        json: async () => ({
                            size: { total_formatted: "Root Size", file_count: 100 },
                        }),
                    });
                } else if (current === 2) {
                    resolveNavSizeFetch = () => res({
                        ok: true,
                        json: async () => ({
                            size: { total_formatted: "Sub Size", file_count: 5 },
                        }),
                    });
                }
            });
        }
        if (url === "/sub/") {
            return Promise.resolve({
                ok: true,
                text: async () => "<div><div class='file-list'>new files</div><div class='device-subheader'><span id='dir-size-info'>Calculating size...</span></div></div>",
            });
        }
        return Promise.resolve({ ok: true, json: async () => ({}) });
    };

    const env = createStartupEnvironment({ pathname: "/", mockFetch });
    env.triggerDOMContentLoaded();
    assert.strictEqual(reqCount, 1, "Initial size request dispatched");

    // Before startup fetch finishes, navigate to /sub/
    const linkTarget = {
        closest: (sel) => (sel === "a" ? {
            getAttribute: (attr) => (attr === "href" ? "/sub/" : null),
            textContent: "sub/",
        } : null),
    };
    const clickHandler = env.listeners["click"] ? env.listeners["click"][0] : null;
    assert.ok(clickHandler, "Click listener registered on document");

    clickHandler({
        target: linkTarget,
        preventDefault: () => {},
        stopPropagation: () => {},
    });

    await new Promise((r) => setTimeout(r, 15));
    assert.strictEqual(reqCount, 2, "Second size request dispatched for navigation");

    // Resolve startup request 1 (stale)
    resolveStartupFetch();
    await new Promise((r) => setTimeout(r, 15));

    // Stale initial request must NOT overwrite label
    const currentLabel = env.elements["dir-size-info"];
    assert.notStrictEqual(currentLabel.textContent, "Total: Root Size (100 files)");

    // Resolve navigation request 2 (fresh)
    resolveNavSizeFetch();
    await new Promise((r) => setTimeout(r, 15));
    assert.strictEqual(currentLabel.textContent, "Total: Sub Size (5 files)");
});

// --- Directory Sorting Behavioral Tests ---

function createSortingTestEnvironment(initialRowDefs) {
    const docListeners = {};
    const winListeners = {};
    const elements = {};

    const makeElement = (tag, attrs = {}, children = []) => {
        const elListeners = {};
        const el = {
            tagName: tag.toUpperCase(),
            getAttribute: (attr) => (attr in attrs ? attrs[attr] : null),
            setAttribute: (attr, val) => { attrs[attr] = String(val); },
            removeAttribute: (attr) => { delete attrs[attr]; },
            classList: {
                add: (c) => {
                    const current = (attrs["class"] || "").split(/\s+/).filter(Boolean);
                    if (!current.includes(c)) current.push(c);
                    attrs["class"] = current.join(" ");
                },
                remove: (c) => {
                    const current = (attrs["class"] || "").split(/\s+/).filter(Boolean);
                    attrs["class"] = current.filter((x) => x !== c).join(" ");
                },
                contains: (c) => (attrs["class"] ? attrs["class"].split(/\s+/).includes(c) : false),
            },
            style: {},
            focus: () => {},
            get className() { return attrs["class"] || ""; },
            set className(v) { attrs["class"] = String(v); },
            textContent: "",
            children: [...children],
            listeners: elListeners,
            addEventListener: (ev, fn) => {
                elListeners[ev] = elListeners[ev] || [];
                elListeners[ev].push(fn);
            },
            appendChild: (child) => {
                child.parentNode = el;
                const idx = el.children.indexOf(child);
                if (idx !== -1) el.children.splice(idx, 1);
                el.children.push(child);
            },
            remove: () => {
                if (el.parentNode && el.parentNode.removeChild) {
                    el.parentNode.removeChild(el);
                }
            },
            querySelector: (sel) => null,
            querySelectorAll: (sel) => [],
            closest: (sel) => {
                if (sel === ".sort-header-btn") {
                    if (attrs["class"] && attrs["class"].includes("sort-header-btn")) return el;
                    return null;
                }
                if (sel === "a") {
                    if (tag.toLowerCase() === "a") return el;
                    return null;
                }
                return null;
            },
        };
        return el;
    };

    const makeRow = (def) => {
        const attrs = {};
        if (def.isParent) attrs["data-parent"] = "1";
        if (def.name !== undefined) attrs["data-name"] = def.name;
        if (def.isDir) attrs["data-isdir"] = "1";
        else if (!def.isParent) attrs["data-isdir"] = "0";
        if (def.size !== undefined && def.size !== null) attrs["data-size"] = String(def.size);
        if (def.mtime !== undefined && def.mtime !== null) attrs["data-mtime"] = String(def.mtime);
        return makeElement("tr", attrs);
    };

    const tbody = {
        tagName: "TBODY",
        children: initialRowDefs.map(makeRow),
        querySelector: (sel) => {
            if (sel === ".no-matches-row") {
                return tbody.children.find((c) => c.classList && c.classList.contains("no-matches-row")) || null;
            }
            return null;
        },
        querySelectorAll: (sel) => {
            if (sel === "tr") return tbody.children.slice();
            return [];
        },
        appendChild: (row) => {
            row.parentNode = tbody;
            const idx = tbody.children.indexOf(row);
            if (idx !== -1) tbody.children.splice(idx, 1);
            tbody.children.push(row);
        },
        removeChild: (child) => {
            const idx = tbody.children.indexOf(child);
            if (idx !== -1) tbody.children.splice(idx, 1);
        },
    };

    const makeTh = (sortField, labelText, defaultSort = "none") => {
        const btnAttrs = { "class": "sort-header-btn", "data-sort": sortField };
        const btn = makeElement("button", btnAttrs);

        const labelSpan = makeElement("span");
        labelSpan.textContent = labelText;

        const iconSpan = makeElement("span", { "class": "sort-icon" });
        iconSpan.textContent = defaultSort === "ascending" ? "▲" : (defaultSort === "descending" ? "▼" : "");

        btn.children = [labelSpan, iconSpan];
        btn.querySelector = (sel) => (sel === ".sort-icon" ? iconSpan : null);

        const thAttrs = { "class": `col-${sortField}`, "aria-sort": defaultSort };
        const th = makeElement("th", thAttrs, [btn]);
        th.querySelector = (sel) => {
            if (sel === ".sort-header-btn") return btn;
            if (sel === ".sort-icon") return iconSpan;
            return null;
        };
        return { th, btn, iconSpan };
    };

    const nameCol = makeTh("name", "Name", "ascending");
    const mtimeCol = makeTh("mtime", "Last modified", "none");
    const sizeCol = makeTh("size", "Size", "none");

    const thead = makeElement("thead");
    const table = {
        tagName: "TABLE",
        querySelector: (sel) => {
            if (sel === "tbody") return tbody;
            if (sel === "thead") return thead;
            return null;
        },
        querySelectorAll: (sel) => {
            if (sel === "th" || sel === "th[data-sort], th") return [nameCol.th, mtimeCol.th, sizeCol.th];
            if (sel === "tr") return tbody.children.slice();
            return [];
        },
    };

    const fileList = {
        tagName: "DIV",
        querySelector: (sel) => (sel === "table" ? table : null),
        classList: { add: () => {}, remove: () => {} },
    };

    const searchInput = makeElement("input", { id: "file-search-input", "class": "file-search-input" });
    searchInput.value = "";
    const searchClear = makeElement("button", { id: "file-search-clear", "class": "file-search-clear" });
    searchClear.style = { display: "none" };

    elements[".file-list"] = fileList;
    elements["dir-size-info"] = makeElement("span", {}, []);
    elements["session-data"] = makeElement("div", { "data-session-id": "sess-sort", "data-base-dir": "/base" });
    elements["file-search-input"] = searchInput;
    elements["file-search-clear"] = searchClear;

    const doc = {
        documentElement: makeElement("html"),
        createElement: (tag) => makeElement(tag),
        getElementById: (id) => elements[id] || null,
        querySelector: (sel) => elements[sel] || null,
        querySelectorAll: (sel) => (sel === "th" ? [nameCol.th, mtimeCol.th, sizeCol.th] : []),
        addEventListener: (ev, fn) => {
            docListeners[ev] = docListeners[ev] || [];
            docListeners[ev].push(fn);
        },
    };

    const win = {
        location: { pathname: "/", href: "http://localhost:8000/" },
        history: { pushState: () => {}, replaceState: () => {} },
        matchMedia: () => ({ matches: false }),
        addEventListener: (ev, fn) => {
            winListeners[ev] = winListeners[ev] || [];
            winListeners[ev].push(fn);
        },
        innerWidth: 800,
    };

    const runner = new Function(
        "document", "window", "localStorage", "fetch", "EventSource",
        fullScriptContent
    );
    const fetchImpl = async (url) => {
        if (url && url.includes("/api/server-status")) {
            throw new Error("server status offline in test");
        }
        return { ok: true, json: async () => ({}) };
    };
    runner(doc, win, { getItem: () => null, setItem: () => {} }, fetchImpl, class { close() {} });

    // Trigger DOMContentLoaded
    for (const fn of (docListeners["DOMContentLoaded"] || [])) {
        fn();
    }

    const clickSort = (field) => {
        let btn = null;
        if (field === "name") btn = nameCol.btn;
        if (field === "mtime") btn = mtimeCol.btn;
        if (field === "size") btn = sizeCol.btn;
        for (const handler of (docListeners["click"] || [])) {
            handler({
                target: btn,
                preventDefault: () => {},
                stopPropagation: () => {},
            });
        }
    };

    const getRowNames = () => {
        return tbody.children.map((r) => {
            if (r.getAttribute("data-parent") === "1") return "[..]";
            return r.getAttribute("data-name");
        });
    };

    const typeSearch = (query) => {
        searchInput.value = query;
        for (const fn of (searchInput.listeners["input"] || [])) {
            fn();
        }
    };

    const pressSearchKey = (key) => {
        for (const fn of (searchInput.listeners["keydown"] || [])) {
            fn({ key });
        }
    };

    const clickClearSearch = () => {
        for (const fn of (searchClear.listeners["click"] || [])) {
            fn();
        }
    };

    const getVisibleRowNames = () => {
        return tbody.children
            .filter((r) => r.style.display !== "none")
            .map((r) => {
                if (r.getAttribute("data-parent") === "1") return "[..]";
                if (r.getAttribute("data-no-matches") === "1") return "__NO_MATCHES__";
                return r.getAttribute("data-name");
            });
    };

    return {
        table,
        tbody,
        nameCol,
        mtimeCol,
        sizeCol,
        searchInput,
        searchClear,
        clickSort,
        typeSearch,
        pressSearchKey,
        clickClearSearch,
        getRowNames,
        getVisibleRowNames,
        win,
        doc,
        listeners: docListeners,
    };
}

test("12. Sorting: Default sort is Name ascending, [..] is first, folders above files", () => {
    const rows = [
        { name: "zebra.txt", isDir: false, size: 100, mtime: 1000 },
        { name: "Photos", isDir: true, mtime: 2000 },
        { isParent: true },
        { name: "alpha.txt", isDir: false, size: 200, mtime: 3000 },
        { name: "Docs", isDir: true, mtime: 1500 },
    ];
    const env = createSortingTestEnvironment(rows);

    // Default: [..] first, folders Docs & Photos A-Z, files alpha.txt & zebra.txt A-Z
    const names = env.getRowNames();
    assert.deepStrictEqual(names, ["[..]", "Docs", "Photos", "alpha.txt", "zebra.txt"]);
    assert.strictEqual(env.nameCol.th.getAttribute("aria-sort"), "ascending");
    assert.strictEqual(env.nameCol.iconSpan.textContent, "▲");
    assert.strictEqual(env.mtimeCol.th.getAttribute("aria-sort"), "none");
    assert.strictEqual(env.sizeCol.th.getAttribute("aria-sort"), "none");
});

test("13. Sorting: Toggling direction toggles Name between asc and desc", () => {
    const rows = [
        { isParent: true },
        { name: "b_folder", isDir: true },
        { name: "a_folder", isDir: true },
        { name: "1_file.txt", isDir: false },
        { name: "2_file.txt", isDir: false },
    ];
    const env = createSortingTestEnvironment(rows);

    // Initial: A-Z
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "a_folder", "b_folder", "1_file.txt", "2_file.txt"]);

    // Click Name -> desc
    env.clickSort("name");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "b_folder", "a_folder", "2_file.txt", "1_file.txt"]);
    assert.strictEqual(env.nameCol.th.getAttribute("aria-sort"), "descending");
    assert.strictEqual(env.nameCol.iconSpan.textContent, "▼");

    // Click Name again -> asc
    env.clickSort("name");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "a_folder", "b_folder", "1_file.txt", "2_file.txt"]);
    assert.strictEqual(env.nameCol.th.getAttribute("aria-sort"), "ascending");
    assert.strictEqual(env.nameCol.iconSpan.textContent, "▲");
});

test("14. Sorting: Switching to Last modified defaults to newest first (desc), clicking again toggles to asc", () => {
    const rows = [
        { isParent: true },
        { name: "old_dir", isDir: true, mtime: 100 },
        { name: "new_dir", isDir: true, mtime: 500 },
        { name: "old_file.txt", isDir: false, mtime: 150 },
        { name: "new_file.txt", isDir: false, mtime: 900 },
    ];
    const env = createSortingTestEnvironment(rows);

    // Click Last modified -> newly selected column defaults to desc (newest first)
    env.clickSort("mtime");
    assert.strictEqual(env.mtimeCol.th.getAttribute("aria-sort"), "descending");
    assert.strictEqual(env.mtimeCol.iconSpan.textContent, "▼");
    assert.strictEqual(env.nameCol.th.getAttribute("aria-sort"), "none");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "new_dir", "old_dir", "new_file.txt", "old_file.txt"]);

    // Click Last modified again -> toggles to asc (oldest first)
    env.clickSort("mtime");
    assert.strictEqual(env.mtimeCol.th.getAttribute("aria-sort"), "ascending");
    assert.strictEqual(env.mtimeCol.iconSpan.textContent, "▲");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "old_dir", "new_dir", "old_file.txt", "new_file.txt"]);
});

test("15. Sorting: Switching to Size defaults to largest first (desc), clicking again toggles to asc", () => {
    const rows = [
        { isParent: true },
        { name: "folder1", isDir: true },
        { name: "small.txt", isDir: false, size: 50 },
        { name: "huge.txt", isDir: false, size: 1000000 },
        { name: "med.txt", isDir: false, size: 5000 },
    ];
    const env = createSortingTestEnvironment(rows);

    // Click Size -> newly selected column defaults to desc (largest first)
    env.clickSort("size");
    assert.strictEqual(env.sizeCol.th.getAttribute("aria-sort"), "descending");
    assert.strictEqual(env.sizeCol.iconSpan.textContent, "▼");
    assert.strictEqual(env.nameCol.th.getAttribute("aria-sort"), "none");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "folder1", "huge.txt", "med.txt", "small.txt"]);

    // Click Size again -> toggles to asc (smallest first)
    env.clickSort("size");
    assert.strictEqual(env.sizeCol.th.getAttribute("aria-sort"), "ascending");
    assert.strictEqual(env.sizeCol.iconSpan.textContent, "▲");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "folder1", "small.txt", "med.txt", "huge.txt"]);
});

test("16. Sorting: Numeric byte count sorting works properly (not alphabetical string sort)", () => {
    // "1000" is alphabetically smaller than "20", but numerically 1000 > 20
    const rows = [
        { isParent: true },
        { name: "item_20.txt", isDir: false, size: 20 },
        { name: "item_1000.txt", isDir: false, size: 1000 },
        { name: "item_5.txt", isDir: false, size: 5 },
    ];
    const env = createSortingTestEnvironment(rows);

    // Size desc -> 1000, 20, 5
    env.clickSort("size");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "item_1000.txt", "item_20.txt", "item_5.txt"]);

    // Size asc -> 5, 20, 1000
    env.clickSort("size");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "item_5.txt", "item_20.txt", "item_1000.txt"]);
});

test("17. Sorting: Equal size and mtime values use stable filename tie-breaker", () => {
    const rows = [
        { isParent: true },
        { name: "c_same.txt", isDir: false, size: 100, mtime: 500 },
        { name: "a_same.txt", isDir: false, size: 100, mtime: 500 },
        { name: "b_same.txt", isDir: false, size: 100, mtime: 500 },
    ];
    const env = createSortingTestEnvironment(rows);

    // Under Size desc, tie-breaker produces a_same, b_same, c_same
    env.clickSort("size");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "a_same.txt", "b_same.txt", "c_same.txt"]);

    // Under Mtime desc, tie-breaker produces a_same, b_same, c_same
    env.clickSort("mtime");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "a_same.txt", "b_same.txt", "c_same.txt"]);
});

test("18. Sorting: Unavailable size metadata placed at end (not treated as 0 bytes)", () => {
    const rows = [
        { isParent: true },
        { name: "zero_byte.txt", isDir: false, size: 0 },
        { name: "normal.txt", isDir: false, size: 100 },
        { name: "unknown_size.txt", isDir: false, size: "" }, // stat failed
    ];
    const env = createSortingTestEnvironment(rows);

    // In Size desc: normal (100) -> zero_byte (0) -> unknown_size (at end)
    env.clickSort("size");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "normal.txt", "zero_byte.txt", "unknown_size.txt"]);

    // In Size asc: zero_byte (0) -> normal (100) -> unknown_size (at end)
    env.clickSort("size");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "zero_byte.txt", "normal.txt", "unknown_size.txt"]);
});

test("19. Sorting: Unavailable timestamp metadata placed at end (not treated as epoch 0)", () => {
    const rows = [
        { isParent: true },
        { name: "epoch_file.txt", isDir: false, mtime: 0 },
        { name: "recent_file.txt", isDir: false, mtime: 1700000000 },
        { name: "unknown_mtime.txt", isDir: false, mtime: "" }, // stat failed
    ];
    const env = createSortingTestEnvironment(rows);

    // In Mtime desc: recent -> epoch -> unknown
    env.clickSort("mtime");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "recent_file.txt", "epoch_file.txt", "unknown_mtime.txt"]);

    // In Mtime asc: epoch -> recent -> unknown
    env.clickSort("mtime");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "epoch_file.txt", "recent_file.txt", "unknown_mtime.txt"]);
});

test("20. Sorting: Size sort keeps folders name-sorted A-Z above size-sorted files", () => {
    const rows = [
        { isParent: true },
        { name: "z_dir", isDir: true },
        { name: "a_dir", isDir: true },
        { name: "file_huge.txt", isDir: false, size: 999999 },
        { name: "file_tiny.txt", isDir: false, size: 10 },
    ];
    const env = createSortingTestEnvironment(rows);

    // Size desc: folders stay name-sorted A-Z (a_dir, z_dir) above files sorted by size desc
    env.clickSort("size");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "a_dir", "z_dir", "file_huge.txt", "file_tiny.txt"]);

    // Size asc: folders still stay name-sorted A-Z above files sorted by size asc
    env.clickSort("size");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "a_dir", "z_dir", "file_tiny.txt", "file_huge.txt"]);
});

test("21. Sorting: Preserves sort state after navigation and DOM replacement", () => {
    const rowsInitial = [
        { isParent: true },
        { name: "file_b.txt", isDir: false, size: 200 },
        { name: "file_a.txt", isDir: false, size: 100 },
    ];
    const env = createSortingTestEnvironment(rowsInitial);

    // Set sort to Size asc
    env.clickSort("size"); // desc
    env.clickSort("size"); // asc
    assert.strictEqual(env.sizeCol.th.getAttribute("aria-sort"), "ascending");
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "file_a.txt", "file_b.txt"]);

    // Simulate navigation/upload refresh: new rows loaded into tbody in server order
    // (e.g. server default Name asc: file_1 (900), file_2 (50))
    const makeRow = (def) => {
        const attrs = {};
        if (def.isParent) attrs["data-parent"] = "1";
        if (def.name !== undefined) attrs["data-name"] = def.name;
        if (def.isDir) attrs["data-isdir"] = "1";
        else if (!def.isParent) attrs["data-isdir"] = "0";
        if (def.size !== undefined) attrs["data-size"] = String(def.size);
        const el = {
            getAttribute: (a) => attrs[a] || null,
            setAttribute: (a, v) => { attrs[a] = String(v); },
            style: {},
        };
        return el;
    };
    const newRows = [
        makeRow({ isParent: true }),
        makeRow({ name: "file_1.txt", isDir: false, size: 900 }),
        makeRow({ name: "file_2.txt", isDir: false, size: 50 }),
    ];
    env.tbody.children = newRows;

    // Apply sorting (as navigateToDirectory or refreshFileList does)
    env.win.VortexSort.apply();

    // Verify sort state (Size asc) was preserved and applied to new rows
    assert.deepStrictEqual(env.getRowNames(), ["[..]", "file_2.txt", "file_1.txt"]);
    assert.strictEqual(env.sizeCol.th.getAttribute("aria-sort"), "ascending");
});

// --- Search Behavioral Tests ---

test("22. Search: Case-insensitive filtering of files and folders", () => {
    const rows = [
        { isParent: true },
        { name: "Documents", isDir: true },
        { name: "Photos", isDir: true },
        { name: "doc_summary.pdf", isDir: false },
        { name: "notes.txt", isDir: false },
    ];
    const env = createSortingTestEnvironment(rows);

    // Initial: all items visible
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "Documents", "Photos", "doc_summary.pdf", "notes.txt"]);

    // Type "doc" (case-insensitive) -> matches "Documents" and "doc_summary.pdf"
    env.typeSearch("doc");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "Documents", "doc_summary.pdf"]);
    assert.strictEqual(env.searchClear.style.display, "");

    // Match folder with trailing slash: "photos/"
    env.typeSearch("photos/");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "Photos"]);
});

test("23. Search: Literal special characters match literally without regex interpretation", () => {
    const rows = [
        { isParent: true },
        { name: "report (final).pdf", isDir: false },
        { name: "report 1.pdf", isDir: false },
        { name: "archive.v1.0.tar.gz", isDir: false },
        { name: "star*file.txt", isDir: false },
        { name: "[draft] notes.txt", isDir: false },
    ];
    const env = createSortingTestEnvironment(rows);

    // Search "(final)" -> parentheses are literal characters, not regex capture groups
    env.typeSearch("(final)");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "report (final).pdf"]);

    // Search "[draft]" -> brackets are literal characters, not regex character classes
    env.typeSearch("[draft]");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "[draft] notes.txt"]);

    // Search "*" -> literal asterisk, not regex quantifier
    env.typeSearch("*");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "star*file.txt"]);

    // Search ".tar.gz" -> literal dots, not any-character wildcards
    env.typeSearch(".tar.gz");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "archive.v1.0.tar.gz"]);
});

test("24. Search: Zero matches displays 'No matching files or folders' placeholder", () => {
    const rows = [
        { isParent: true },
        { name: "alpha.txt", isDir: false },
        { name: "beta.txt", isDir: false },
    ];
    const env = createSortingTestEnvironment(rows);

    // Search for nonexistent term
    env.typeSearch("nonexistent_term");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "__NO_MATCHES__"]);

    const noMatchesEl = env.tbody.children.find((c) => c.getAttribute("data-no-matches") === "1");
    assert.ok(noMatchesEl, "No matches row is rendered");
    assert.strictEqual(noMatchesEl.children[0].textContent, "No matching files or folders");

    // Clearing query removes no-matches row and restores all rows
    env.typeSearch("");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "alpha.txt", "beta.txt"]);
    const noMatchesAfter = env.tbody.children.find((c) => c.getAttribute("data-no-matches") === "1");
    assert.strictEqual(noMatchesAfter, undefined);
});

test("25. Search: Clear button and Escape key restore full listing and focus", () => {
    const rows = [
        { isParent: true },
        { name: "cat.png", isDir: false },
        { name: "dog.png", isDir: false },
    ];
    const env = createSortingTestEnvironment(rows);

    // Filter by "cat"
    env.typeSearch("cat");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "cat.png"]);
    assert.strictEqual(env.searchClear.style.display, "");

    // Click clear button
    env.clickClearSearch();
    assert.strictEqual(env.searchInput.value, "");
    assert.strictEqual(env.searchClear.style.display, "none");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "cat.png", "dog.png"]);

    // Filter by "dog" and press Escape
    env.typeSearch("dog");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "dog.png"]);
    env.pressSearchKey("Escape");
    assert.strictEqual(env.searchInput.value, "");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "cat.png", "dog.png"]);
});

test("26. Search: Sorting applies to filtered results", () => {
    const rows = [
        { isParent: true },
        { name: "project_small.zip", isDir: false, size: 50 },
        { name: "project_huge.zip", isDir: false, size: 50000 },
        { name: "project_med.zip", isDir: false, size: 500 },
        { name: "unrelated.txt", isDir: false, size: 10 },
    ];
    const env = createSortingTestEnvironment(rows);

    // Search "project" -> 3 matching files
    env.typeSearch("project");
    // Default sort is Name asc
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "project_huge.zip", "project_med.zip", "project_small.zip"]);

    // Click Size sort -> desc (largest first)
    env.clickSort("size");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "project_huge.zip", "project_med.zip", "project_small.zip"]);

    // Click Size sort again -> asc (smallest first)
    env.clickSort("size");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "project_small.zip", "project_med.zip", "project_huge.zip"]);

    // Non-matching file remains hidden
    const unrelatedRow = env.tbody.children.find((r) => r.getAttribute("data-name") === "unrelated.txt");
    assert.strictEqual(unrelatedRow.style.display, "none");
});

test("27. Search: Directory navigation clears the search query", async () => {
    const rows = [
        { isParent: true },
        { name: "sub", isDir: true },
        { name: "file.txt", isDir: false },
    ];
    let navFetchUrl = null;
    const mockFetch = async (url) => {
        navFetchUrl = url;
        if (url === "/sub/") {
            return {
                ok: true,
                text: async () => `
                    <div class="file-list">
                        <table>
                            <thead>
                                <tr>
                                    <th scope="col" class="col-name" aria-sort="ascending"><button type="button" class="sort-header-btn" data-sort="name"><span>Name</span><span class="sort-icon">▲</span></button></th>
                                    <th scope="col" class="col-mtime" aria-sort="none"><button type="button" class="sort-header-btn" data-sort="mtime"><span>Last modified</span><span class="sort-icon"></span></button></th>
                                    <th scope="col" class="col-size" aria-sort="none"><button type="button" class="sort-header-btn" data-sort="size"><span>Size</span><span class="sort-icon"></span></button></th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr data-parent="1"><td><a href="../">[..]</a></td><td></td><td></td></tr>
                                <tr data-name="sub_file.txt" data-isdir="0" data-size="100"><td><a href="sub_file.txt">sub_file.txt</a></td><td></td><td>100 B</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div class="device-subheader"><span>/sub/</span><span id="dir-size-info">Calculating size...</span></div>
                    <div id="session-data" data-base-dir="/base" data-session-id="sess-1"></div>
                `,
            };
        }
        return { ok: true, json: async () => ({}) };
    };

    const env = createStartupEnvironment({ pathname: "/", mockFetch });
    env.triggerDOMContentLoaded();

    // Set search query in window.VortexSearch
    env.win.VortexSearch.setQuery("test-filter");
    assert.strictEqual(env.win.VortexSearch.getQuery(), "test-filter");

    // Click directory link to navigate to /sub/
    const linkTarget = {
        closest: (sel) => (sel === "a" ? {
            getAttribute: (attr) => (attr === "href" ? "/sub/" : null),
            textContent: "sub/",
        } : null),
    };
    const clickHandler = env.listeners["click"][0];
    clickHandler({
        target: linkTarget,
        preventDefault: () => {},
        stopPropagation: () => {},
    });

    await new Promise((r) => setTimeout(r, 20));

    // Verify search query was cleared on directory change
    assert.strictEqual(env.win.VortexSearch.getQuery(), "");
});

test("28. Search: Upload refresh within same directory preserves search query and re-applies filter", () => {
    const rows = [
        { isParent: true },
        { name: "log1.txt", isDir: false },
        { name: "image.png", isDir: false },
    ];
    const env = createSortingTestEnvironment(rows);

    // Active search filter: "log"
    env.typeSearch("log");
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "log1.txt"]);

    // Simulate an upload refresh in the same directory:
    // New row "log2.txt" added to newly fetched table rows
    const makeRow = (def) => {
        const attrs = {};
        if (def.isParent) attrs["data-parent"] = "1";
        if (def.name !== undefined) attrs["data-name"] = def.name;
        if (def.isDir) attrs["data-isdir"] = "1";
        else if (!def.isParent) attrs["data-isdir"] = "0";
        const el = {
            getAttribute: (a) => attrs[a] || null,
            setAttribute: (a, v) => { attrs[a] = String(v); },
            style: {},
        };
        return el;
    };
    const newRows = [
        makeRow({ isParent: true }),
        makeRow({ name: "image.png", isDir: false }),
        makeRow({ name: "log1.txt", isDir: false }),
        makeRow({ name: "log2.txt", isDir: false }),
    ];
    env.tbody.children = newRows;

    // Refresh re-applies sorting and filtering without clearing query
    env.win.VortexSort.apply();
    env.win.VortexSearch.apply();

    // Query is preserved
    assert.strictEqual(env.win.VortexSearch.getQuery(), "log");
    // Visible rows include [..] and the two matching log files; image.png is hidden
    assert.deepStrictEqual(env.getVisibleRowNames(), ["[..]", "log1.txt", "log2.txt"]);
});

// --- QR Code Initialization and Responsive Regression Tests ---

test("29. QR code: Initial wide-window loading generates QR and sets URL", () => {
    MockQRCode.instances = [];
    global.QRCode = MockQRCode;
    try {
        const env = createStartupEnvironment({ pathname: "/folder/", innerWidth: 1200 });
        env.triggerDOMContentLoaded();

        const qrText = env.elements["qr-url-text"];
        const qrEl = env.elements["qr-code"];

        assert.strictEqual(qrText.textContent, "http://localhost:8000/folder/");
        assert.strictEqual(qrEl.children.length, 1);
        assert.strictEqual(qrEl.children[0].options.text, "http://localhost:8000/folder/");
        assert.strictEqual(qrEl.children[0].options.colorDark, "#263238");
    } finally {
        delete global.QRCode;
    }
});

test("30. QR code: Initial narrow loading followed by widening initializes QR code", () => {
    MockQRCode.instances = [];
    global.QRCode = MockQRCode;
    try {
        const env = createStartupEnvironment({ pathname: "/", innerWidth: 800 });
        env.triggerDOMContentLoaded();

        const qrText = env.elements["qr-url-text"];
        const qrEl = env.elements["qr-code"];

        // Must be uninitialized when narrow
        assert.strictEqual(qrText.textContent, "");
        assert.strictEqual(qrEl.children.length, 0);

        // Window widens to desktop
        env.win.innerWidth = 1024;
        env.triggerWinEvent("resize");

        assert.strictEqual(qrText.textContent, "http://localhost:8000/");
        assert.strictEqual(qrEl.children.length, 1);
        assert.strictEqual(qrEl.children[0].options.text, "http://localhost:8000/");
    } finally {
        delete global.QRCode;
    }
});

test("31. QR code: Responsive breakpoint boundary behavior (900px mobile vs 901px desktop)", () => {
    MockQRCode.instances = [];
    global.QRCode = MockQRCode;
    try {
        // Startup exactly at 900px (mobile boundary)
        const env = createStartupEnvironment({ pathname: "/", innerWidth: 900 });
        env.triggerDOMContentLoaded();

        const qrText = env.elements["qr-url-text"];
        const qrEl = env.elements["qr-code"];

        assert.strictEqual(qrText.textContent, "");
        assert.strictEqual(qrEl.children.length, 0);

        // Resize below boundary: 899px
        env.win.innerWidth = 899;
        env.triggerWinEvent("resize");
        assert.strictEqual(qrText.textContent, "");
        assert.strictEqual(qrEl.children.length, 0);

        // Resize back to 900px
        env.win.innerWidth = 900;
        env.triggerWinEvent("resize");
        assert.strictEqual(qrText.textContent, "");
        assert.strictEqual(qrEl.children.length, 0);

        // Cross boundary to 901px (desktop)
        env.win.innerWidth = 901;
        env.triggerWinEvent("resize");
        assert.strictEqual(qrText.textContent, "http://localhost:8000/");
        assert.strictEqual(qrEl.children.length, 1);
    } finally {
        delete global.QRCode;
    }
});

test("32. QR code: Repeated narrow/wide transitions are idempotent without duplicate QR output", () => {
    MockQRCode.instances = [];
    global.QRCode = MockQRCode;
    try {
        const env = createStartupEnvironment({ pathname: "/", innerWidth: 1200 });
        env.triggerDOMContentLoaded();

        const qrEl = env.elements["qr-code"];
        assert.strictEqual(qrEl.children.length, 1);
        assert.strictEqual(MockQRCode.instances.length, 1);

        // Resize repeatedly between narrow and wide
        const widths = [800, 1200, 750, 1050, 600, 1400];
        for (const w of widths) {
            env.win.innerWidth = w;
            env.triggerWinEvent("resize");
            if (w > 900) {
                // Must keep single QR output without duplicate canvas elements or extra instances
                assert.strictEqual(qrEl.children.length, 1);
                assert.strictEqual(MockQRCode.instances.length, 1);
            }
        }
    } finally {
        delete global.QRCode;
    }
});

test("33. QR code: Hidden/minimized startup followed by restore initializes QR code", () => {
    MockQRCode.instances = [];
    global.QRCode = MockQRCode;
    try {
        const env = createStartupEnvironment({ pathname: "/restore-test/", innerWidth: 1200, hidden: true });
        env.triggerDOMContentLoaded();

        const qrText = env.elements["qr-url-text"];
        const qrEl = env.elements["qr-code"];

        // Startup while hidden: skipped
        assert.strictEqual(qrText.textContent, "");
        assert.strictEqual(qrEl.children.length, 0);

        // Document restored/visible
        env.doc.hidden = false;
        env.triggerDocEvent("visibilitychange");

        assert.strictEqual(qrText.textContent, "http://localhost:8000/restore-test/");
        assert.strictEqual(qrEl.children.length, 1);
        assert.strictEqual(qrEl.children[0].options.text, "http://localhost:8000/restore-test/");
    } finally {
        delete global.QRCode;
    }
});

test("34. QR code: Delayed library availability renders QR when ready without refresh or indefinite polling", async () => {
    MockQRCode.instances = [];
    delete global.QRCode;

    const env = createStartupEnvironment({ pathname: "/delayed/", innerWidth: 1200 });
    env.triggerDOMContentLoaded();

    const qrText = env.elements["qr-url-text"];
    const qrEl = env.elements["qr-code"];

    // URL is shown immediately even if QR library is delayed
    assert.strictEqual(qrText.textContent, "http://localhost:8000/delayed/");
    assert.strictEqual(qrEl.children.length, 0);

    // Simulate library loaded later
    global.QRCode = MockQRCode;

    // Wait for the retry loop to pick up the ready library
    await new Promise((r) => setTimeout(r, 250));

    assert.strictEqual(qrEl.children.length, 1);
    assert.strictEqual(qrEl.children[0].options.text, "http://localhost:8000/delayed/");
    delete global.QRCode;
});

test("35. QR code: Theme switching after becoming visible updates QR colors", () => {
    MockQRCode.instances = [];
    global.QRCode = MockQRCode;
    try {
        const env = createStartupEnvironment({ pathname: "/", innerWidth: 1200, theme: "light" });
        env.triggerDOMContentLoaded();

        const qrEl = env.elements["qr-code"];
        assert.strictEqual(qrEl.children.length, 1);
        assert.strictEqual(qrEl.children[0].options.colorDark, "#263238");

        // Click theme toggle to switch to dark
        const toggleBtn = env.elements["theme-toggle"];
        const clickFn = toggleBtn.listeners["click"][0];
        clickFn();

        assert.strictEqual(env.elements["document-element"].getAttribute("data-theme"), "dark");
        assert.strictEqual(qrEl.children.length, 1);
        assert.strictEqual(qrEl.children[0].options.colorDark, "#E0E0E0");

        // Click theme toggle to switch back to light
        clickFn();
        assert.strictEqual(env.elements["document-element"].getAttribute("data-theme"), "light");
        assert.strictEqual(qrEl.children.length, 1);
        assert.strictEqual(qrEl.children[0].options.colorDark, "#263238");
    } finally {
        delete global.QRCode;
    }
});
