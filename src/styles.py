# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
CSS styles for Vortex web interface.

This module contains the complete stylesheet for the file browser UI.
The design follows a clean, minimal aesthetic with clear visual hierarchy
and responsive behavior for mobile devices.
"""

CSS_STYLESHEET = """
/* Design System & CSS Variables */

:root {
  /* Color Palette - Science-Backed (Low Visual Fatigue) */
  --bg-color: #E8F4F1;          /* Soft sage - desaturated, minimal eye strain */
  --surface-color: #FFFBF7;      /* Warm off-white - reduces glare vs pure white */
  --surface-alt: #F5F3F0;        /* Warm neutral for secondary surfaces */
  --text-main: #212121;          /* Dark grey - softer than pure black, 4.5:1+ contrast */
  --text-dim: #666666;           /* Mid-grey for secondary text */

  /* Accent Colors - Vibrant but Safe */
  --accent-color: #00796B;       /* Teal - lowest visual fatigue (NIH study) */
  --accent-hover: #004D40;       /* Deep teal for hover states */
  --secondary-accent: #D84315;   /* Burnt orange - use sparingly (10% UI) */
  --error-color: #C62828;        /* Deep red - reserved for errors only */

  /* RGB Values for RGBA */
  --accent-rgb: 0,121,107;
  --secondary-accent-rgb: 216,67,21;
  --error-rgb: 198,40,40;

  /* Borders - Industrial Definition */
  --border-color: #3E3E3E;       /* Charcoal - maintains sharpness without harshness */
  --border-light: #D0D0D0;       /* Softer border for secondary elements */
  --border-width: 1px;

  /* Spacing & Sizing */
  --radius: 8px;

  /* Typography */
  /* Unified font stack for consistent Teenage Engineering-inspired industrial aesthetic.
     IBM Plex Mono provides a clean, technical feel; falls back to system monospace fonts. */
  --font-ui: "IBM Plex Mono", "SF Mono", "Menlo", "Consolas", "Monaco", monospace;
}


/* Reset & Base Styles */

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  transition: border-radius 0.3s ease, border-width 0.3s ease;
}

html,
body {
  height: 100%;
}

html {
  height: -webkit-fill-available;
}

body {
  background-color: var(--bg-color);
  background-image:
    linear-gradient(rgba(0, 0, 0, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.04) 1px, transparent 1px);
  background-size: 20px 20px;
  color: var(--text-main);
  font-family: var(--font-ui);
  min-height: 100vh;
  min-height: -webkit-fill-available;
  display: flex;
  justify-content: center;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overscroll-behavior-y: none;
  overflow-x: hidden;
}

.app-root {
  width: 100%;
  max-width: 1200px;
  padding: 0.75rem;
}


/* Layout Container (Device Shell) */

.device-shell {
  background: var(--surface-color);
  border: var(--border-width) solid var(--border-color);
  border-radius: 12px;
  width: 100%;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
  min-height: 0;
  overflow: hidden;
}

/* Desktop Layout */
@media (min-width: 900px) {
  body {
    align-items: center;
  }

  .app-root {
    padding: 1.5rem;
  }

  .device-shell {
    max-height: calc(100vh - 3rem);
  }
}

/* Mobile Layout */
@media (max-width: 600px) {
  body {
    background-size: 16px 16px;
  }

  .app-root {
    padding: max(0.5rem, env(safe-area-inset-top)) max(0.5rem, env(safe-area-inset-right)) max(0.5rem, env(safe-area-inset-bottom)) max(0.5rem, env(safe-area-inset-left));
  }

  .device-shell {
    border-width: 1px;
    box-shadow: none;
  }
}


/* Header */

.device-header {
  padding: 0.9rem 1rem 0.4rem;
  border-bottom: var(--border-width) solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.device-header h1 {
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 800;
  font-family: var(--font-ui);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.server-stop-btn {
  background: var(--secondary-accent);
  border: 1px solid var(--secondary-accent);
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.device-header p {
  font-size: 0.8rem;
  color: var(--text-dim);
  line-height: 1.4;
  font-family: var(--font-ui);
}


/* Subheader / Path Bar */

.device-subheader {
  padding: 0.4rem 1rem;
  border-bottom: 1px solid var(--border-color);
  font-family: var(--font-ui);
  font-size: 0.7rem;
  color: var(--text-dim);
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  min-width: 0;
}

.device-subheader span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}


/* Main Content Area */

.device-main {
  padding: 0.8rem 1rem 0.8rem;
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  grid-template-areas: "files upload chat";
  column-gap: 1rem;
  row-gap: 0.75rem;
  min-height: 0;
}

.panel-files {
  grid-area: files;
  min-width: 0;
}

.panel-upload {
  grid-area: upload;
  min-width: 0;
}

.panel-chat {
  grid-area: chat;
  min-width: 0;
}

/* Medium screens: Adjust proportions */
@media (max-width: 1200px) and (min-width: 901px) {
  .device-main {
    grid-template-columns: 1.5fr 1fr 1fr;
  }
}

/* Tablet/Mobile: Stack columns */
@media (max-width: 900px) {
  .device-main {
    grid-template-columns: 1fr;
    grid-template-areas: "files" "upload" "chat";
    grid-auto-rows: auto;
  }

  /* Upload panel appears first on mobile */
  .panel-upload {
    order: -1;
    grid-area: upload;
  }
  
  .panel-files {
    order: 0;
    grid-area: files;
  }
  
  .panel-chat {
    order: 1;
    grid-area: chat;
  }
}


/* Panel Component */

.panel {
  border: var(--border-width) solid var(--border-color);
  border-radius: 10px;
  background: #ffffff;
  padding: 0.75rem 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.panel-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 800;
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-width: 0;
}

.panel-title span {
  font-family: var(--font-ui);
  font-size: 0.65rem;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.panel-title span:first-child {
  flex-shrink: 0;
  margin-right: 0.5rem;
}

.path-label {
  font-family: var(--font-ui);
  font-size: 0.7rem;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}


/* File Input & Upload Controls */

.upload-row {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 0.25rem;
}

/* Custom File Input */

.file-input {
  position: relative;
  display: flex;
  align-items: stretch;
  gap: 0.25rem;
  font-family: var(--font-ui);
  font-size: 0.75rem;
  flex: 1;
  min-width: 0;
}

.file-input input[type="file"] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  -webkit-appearance: none;
  font-size: 16px; /* Prevents iOS zoom on focus */
}

.file-button {
  background: var(--accent-color);
  color: #ffffff;
  border: var(--border-width) solid var(--border-color);
  border-radius: 8px;
  padding: 0.4rem;
  text-transform: uppercase;
  font-weight: 600;
  font-size: 0.65rem;
  letter-spacing: 0.2px;
  min-width: 3.5rem;
  text-align: center;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-ui);
  box-shadow: none;
  transition: background 0.05s ease, transform 0.05s ease;
}

.file-button:hover {
  background: var(--accent-hover);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.file-button:active {
  transform: translateY(1px);
  box-shadow: none;
}

.file-button:focus {
  box-shadow: none;
}

.file-button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

.file-name {
  flex: 1;
  padding: 0 0.3rem;
  border: 1px dashed #bbbbbb;
  border-radius: 8px;
  color: var(--text-dim);
  white-space: nowrap;
  font-size: 0.65rem;
  overflow: hidden;
  text-overflow: ellipsis;
  background: #fafafa;
  min-height: 44px;
  display: block;
  line-height: 42px;
  min-width: 0;
}


/* Buttons */

.btn {
  appearance: none;
  -webkit-appearance: none;
  background: #ffffff;
  border: var(--border-width) solid var(--border-color);
  border-radius: 8px;
  color: var(--text-main);
  padding: 0.4rem;
  font-family: var(--font-ui);
  font-size: 0.65rem;
  text-transform: uppercase;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.05s ease, color 0.05s ease, border-color 0.05s ease, transform 0.05s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 3.5rem;
  min-height: 44px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  box-shadow: none;
}

.btn:hover {
  background: var(--accent-color);
  color: #ffffff;
  border-color: var(--accent-color);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.btn:active {
  transform: translateY(1px);
  box-shadow: none;
  background: var(--accent-hover);
  color: #ffffff;
}

.btn:focus {
  box-shadow: none;
}

.btn:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Download All Button */

.btn-download {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  text-align: center;
  font-size: 0.7rem;
  padding: 0.35rem 0.6rem;
  min-height: 36px;
}

/* Mobile Button Adjustments */

@media (max-width: 600px) {
  .upload-row {
    flex-direction: column;
    gap: 0.5rem;
  }

  .file-input {
    flex-direction: column;
    flex: none;
    width: 100%;
  }

  .file-button,
  .file-name {
    width: 100%;
    padding: 0.45rem 0.6rem;
    letter-spacing: 0.1px;
  }

  .upload-row .btn {
    width: 100%;
    flex-shrink: 1;
  }
}


/* File List Table */

.file-list {
  border-top: 1px solid var(--border-color);
  margin-top: 0.4rem;
  padding-top: 0.4rem;
  overflow: auto;
  min-height: 0;
  max-height: 100%;
  -webkit-overflow-scrolling: touch;
  -ms-overflow-style: none;
  scrollbar-width: none;
  transition: opacity 0.15s ease;
}

.file-list.updating {
  opacity: 0.6;
  pointer-events: none;
}

.file-list::-webkit-scrollbar {
  display: none;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
  font-family: var(--font-ui);
  table-layout: fixed;
}

th,
td {
  padding: 0.25rem 0.3rem;
  border-bottom: 1px solid var(--border-light);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

th {
  text-align: left;
  text-transform: uppercase;
  font-size: 0.6rem;
  letter-spacing: 0.5px;
  color: var(--text-dim);
  font-weight: 600;
}

td a {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}


/* Links */

a {
  color: var(--accent-color);
  text-decoration: none;
  font-family: var(--font-ui);
  -webkit-tap-highlight-color: transparent;
}

a:hover {
  color: var(--accent-hover);
  text-decoration: underline;
}

a:active {
  color: var(--accent-hover);
  opacity: 0.8;
}

/* Mobile Table Adjustments */

@media (max-width: 600px) {
  table {
    font-size: 0.7rem;
  }

  th,
  td {
    padding: 0.4rem 0.25rem;
  }

  th {
    font-size: 0.55rem;
  }

  /* Larger touch targets on mobile */
  td a {
    padding: 0.35rem 0;
    min-height: 38px;
    display: flex;
    align-items: center;
  }
}


/* Upload Progress Indicator */

.upload-progress {
  display: none;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.6rem;
}

.upload-progress.active {
  display: flex;
}

.progress-bar-container {
  width: 100%;
  height: 10px;
  background: var(--surface-alt);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  width: 0%;
  background: var(--accent-color);
  border-radius: 8px;
  transition: width 0.15s ease;
}

.progress-text {
  font-family: var(--font-ui);
  font-size: 0.7rem;
  color: var(--text-secondary);
}


/* Error Messages */

.upload-error {
  color: var(--error-color);
  font-family: var(--font-ui);
  font-size: 0.7rem;
  display: none;
  padding: 0.4rem 0.6rem;
  background: #fef2f2;
  border-radius: 8px;
  border: 1px solid var(--error-color);
}

.upload-error.active {
  display: block;
}


/* Chat Panel */

.panel-chat {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 350px;
  max-height: 550px;
}

@media (max-width: 1200px) and (min-width: 901px) {
  .panel-chat {
    min-height: 300px;
    max-height: 450px;
  }
}

@media (max-width: 900px) {
  .panel-chat {
    min-height: 300px;
    max-height: 500px;
  }
}

#chat-status {
  font-size: 0.8rem;
  color: #00cc00;
  animation: pulse 2s infinite;
}

#chat-status.offline {
  color: #cc0000;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Chat Messages - Terminal Log Style */

.chat-messages {
  flex: 1;
  overflow-y: auto;
  border: var(--border-width) solid var(--border-color);
  border-radius: 10px;
  padding: 0.6rem;
  background: var(--surface-color);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-family: var(--font-ui);
  -webkit-overflow-scrolling: touch;
  -ms-overflow-style: none;
  scrollbar-width: none;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.05);
}

.chat-messages::-webkit-scrollbar {
  display: none;
}

/* Chat Message - System Log Entry Style */

.chat-message {
  padding: 0.5rem 0.6rem;
  border-left: 3px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-alt);
  word-wrap: break-word;
  font-family: var(--font-ui);
}

.chat-message-own {
  background: #ffffff;
  border-left-color: var(--accent-color);
  border-left-width: 3px;
}

/* Chat Sender - Terminal Prompt Style */

.chat-sender {
  font-size: 0.65rem;
  font-weight: 800;
  color: var(--text-main);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.3rem;
  font-family: var(--font-ui);
}

.chat-message-own .chat-sender {
  color: var(--accent-color);
}

/* Kick Button - Host Controls */

.kick-button {
  display: inline-block;
  margin-left: 0.5rem;
  padding: 0 0.3rem;
  font-size: 1rem;
  font-weight: bold;
  font-family: var(--font-ui);
  color: var(--error-color);
  background: transparent;
  border: 1px solid var(--error-color);
  border-radius: 6px;
  cursor: pointer;
  line-height: 1;
  transition: background 0.05s ease, color 0.05s ease, transform 0.05s ease;
  box-shadow: none;
}

.kick-button:hover {
  background: var(--error-color);
  color: #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.kick-button:active {
  transform: translateY(1px);
  box-shadow: none;
}

.kick-button:focus {
  box-shadow: none;
}

.kick-button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

/* Chat Disconnected State */

.chat-form input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.chat-form input:disabled::placeholder {
  color: var(--error-color);
}

/* Host Controls Container */

.host-controls {
  display: none;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.btn-manage-devices,
.btn-manage-bans {
  flex: 1;
  padding: 0.4rem;
  font-size: 0.65rem;
  font-weight: 600;
  font-family: var(--font-ui);
  color: var(--text-main);
  background: var(--surface-alt);
  border: var(--border-width) solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: background 0.05s ease, color 0.05s ease, border-color 0.05s ease, transform 0.05s ease;
  box-shadow: none;
}

.btn-manage-devices:hover {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.btn-manage-devices:active {
  transform: translateY(1px);
  box-shadow: none;
}

.btn-manage-devices:focus {
  box-shadow: none;
}

.btn-manage-devices:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

.btn-manage-bans:hover {
  background: var(--error-color);
  border-color: var(--error-color);
  color: #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.btn-manage-bans:active {
  transform: translateY(1px);
  box-shadow: none;
}

.btn-manage-bans:focus {
  box-shadow: none;
}

.btn-manage-bans:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

/* Active Devices Section */

.active-devices-section {
  background: var(--surface-main);
  border: var(--border-width) solid var(--accent-color);
  border-radius: 10px;
  margin-bottom: 0.5rem;
  max-height: 200px;
  overflow-y: auto;
  overflow: hidden;
}

.active-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  background: var(--accent-color);
  color: #ffffff;
  border-bottom: var(--border-width) solid var(--accent-color);
  font-size: 0.65rem;
  font-weight: 800;
  font-family: var(--font-ui);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.active-close {
  background: transparent;
  border: 1px solid #ffffff;
  border-radius: 4px;
  color: #ffffff;
  font-size: 1rem;
  font-weight: bold;
  line-height: 1;
  padding: 0 0.3rem;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: none;
}

.active-close:hover {
  background: #ffffff;
  color: var(--accent-color);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.active-close:active {
  transform: translateY(1px);
  box-shadow: none;
}

.active-close:focus {
  box-shadow: none;
}

.active-close:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

.active-list {
  padding: 0.5rem;
}

.active-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.5rem;
  margin-bottom: 0.3rem;
  background: var(--surface-alt);
  border-left: 3px solid var(--accent-color);
  border-radius: 6px;
  font-family: var(--font-ui);
}

.active-device-name {
  font-size: 0.75rem;
  color: var(--text-main);
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

.active-empty {
  padding: 1rem;
  text-align: center;
  font-size: 0.7rem;
  color: var(--text-dim);
  font-family: var(--font-ui);
}

.kick-button-inline {
  padding: 0.2rem 0.5rem;
  font-size: 0.65rem;
  font-weight: 600;
  font-family: var(--font-ui);
  color: #ffffff;
  background: var(--error-color);
  border: 1px solid var(--error-color);
  border-radius: 6px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  transition: all 0.15s ease;
  box-shadow: none;
}

.kick-button-inline:hover {
  background: color-mix(in srgb, var(--error-color) 70% black);
  border-color: color-mix(in srgb, var(--error-color) 70% black);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.kick-button-inline:active {
  transform: translateY(1px);
  box-shadow: none;
}

.kick-button-inline:focus {
  box-shadow: none;
}

.kick-button-inline:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

/* Banned Devices Section */

.banned-devices-section {
  background: var(--surface-main);
  border: var(--border-width) solid var(--border-color);
  border-radius: 10px;
  margin-bottom: 0.5rem;
  max-height: 200px;
  overflow-y: auto;
  overflow: hidden;
}

.banned-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  background: var(--surface-alt);
  border-bottom: var(--border-width) solid var(--border-color);
  font-size: 0.65rem;
  font-weight: 800;
  font-family: var(--font-ui);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.banned-close {
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-dim);
  font-size: 1rem;
  font-weight: bold;
  line-height: 1;
  padding: 0 0.3rem;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: none;
}

.banned-close:hover {
  background: var(--error-color);
  border-color: var(--error-color);
  color: #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.banned-close:active {
  transform: translateY(1px);
  box-shadow: none;
}

.banned-close:focus {
  box-shadow: none;
}

.banned-close:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

.banned-list {
  padding: 0.5rem;
}

.banned-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.5rem;
  margin-bottom: 0.3rem;
  background: var(--surface-alt);
  border-left: 3px solid var(--error-color);
  border-radius: 6px;
  font-family: var(--font-ui);
}

.banned-device-id {
  font-size: 0.7rem;
  color: var(--text-main);
  font-family: var(--font-mono);
  letter-spacing: 0.3px;
}

.banned-empty {
  padding: 1rem;
  text-align: center;
  font-size: 0.7rem;
  color: var(--text-dim);
  font-family: var(--font-ui);
}

.unkick-button {
  padding: 0.2rem 0.5rem;
  font-size: 0.65rem;
  font-weight: 600;
  font-family: var(--font-ui);
  color: var(--text-main);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  transition: all 0.15s ease;
  box-shadow: none;
}

.unkick-button:hover {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.unkick-button:active {
  transform: translateY(1px);
  box-shadow: none;
}

.unkick-button:focus {
  box-shadow: none;
}

.unkick-button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none;
}

/* Chat Content - Monospace Data */

.chat-content {
  font-family: var(--font-ui);
  font-size: 0.7rem;
  word-wrap: break-word;
  line-height: 1.5;
  color: var(--text-main);
}

.chat-content a {
  color: var(--accent-color);
  text-decoration: none;
  font-family: var(--font-ui);
  border-bottom: 1px solid var(--accent-color);
}

.chat-content a:hover {
  text-decoration: none;
  opacity: 0.8;
}

/* Chat Timestamp - Technical Readout */

.chat-timestamp {
  font-size: 0.65rem;
  font-family: var(--font-ui);
  color: var(--text-dim);
  margin-top: 0.3rem;
  text-align: left;
  letter-spacing: 0.3px;
}

/* Chat Form - Command Line Style */

.chat-form {
  display: flex;
  gap: 0.5rem;
  align-items: stretch;
}

/* Chat Input - Terminal Input Field */

#chat-input {
  flex: 1;
  padding: 0.5rem 0.6rem;
  border: var(--border-width) solid var(--border-color);
  font-family: var(--font-ui);
  font-size: 0.7rem;
  border-radius: 8px;
  background: var(--surface-color);
  color: var(--text-main);
  min-height: 44px;
  letter-spacing: 0.2px;
}

#chat-input::placeholder {
  font-family: var(--font-ui);
  color: var(--text-dim);
  opacity: 1;
}

#chat-input:focus {
  outline: none;
  border-color: var(--accent-color);
  background: #ffffff;
}

.btn-chat {
  min-width: 4rem;
  font-size: 0.65rem;
  font-family: var(--font-ui);
}

@media (max-width: 600px) {
  .chat-form {
    flex-direction: column;
    gap: 0.5rem;
  }
  
  #chat-input {
    font-size: 16px; /* Prevent iOS zoom */
  }
  
  .chat-message {
    max-width: 100%;
  }
}


/* Server Termination Message */

.termination-message {
  grid-column: 1 / -1;
  background: white;
  border: 2px solid var(--secondary-accent);
  border-radius: 16px;
  padding: 3rem;
  text-align: center;
  font-family: var(--font-ui);
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--secondary-accent);
  letter-spacing: 2px;
  box-shadow: 0 8px 24px rgba(var(--secondary-accent-rgb), 0.2);
}

@media (max-width: 600px) {
  .termination-message {
    font-size: 1.2rem;
    padding: 2rem;
  }
}


/* QR Code Container */

.qr-code-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 1rem;
  border-top: 1px solid var(--border-light);
  margin: 1rem auto 0;
  width: 100%;
}

.qr-title {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-dim);
  font-family: var(--font-ui);
  text-align: center;
}

#qr-code {
  border: 1px solid var(--border-light);
  padding: 0.3rem;
  background: #ffffff;
  border-radius: 8px;
  width: max-content;
}

#qr-code img {
  display: block;
  max-width: 100%;
  height: auto;
}

.qr-url {
  font-family: var(--font-ui);
  font-size: 0.6rem;
  color: var(--text-dim);
  word-break: break-all;
  text-align: center;
  max-width: 100%;
  line-height: 1.3;
}

@media (max-width: 900px) {
  .qr-code-container {
    display: none;
  }
}


/* Directory Size Info */

#dir-size-info {
  font-family: var(--font-ui);
  font-size: 0.7rem;
  color: var(--text-dim);
  white-space: nowrap;
}


/* Upload Progress Toast (Host View) */

.upload-toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 280px;
  background: var(--surface-color);
  border: var(--border-width) solid var(--border-color);
  border-radius: 10px;
  padding: 0.75rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  font-family: var(--font-ui);
  opacity: 0;
  transform: translateX(100%);
  transition: opacity 0.3s ease, transform 0.3s ease;
  pointer-events: none;
}

.upload-toast.active {
  opacity: 1;
  transform: translateX(0);
  pointer-events: auto;
}

.upload-toast-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.upload-toast-device {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent-color);
}

.upload-toast-close {
  font-size: 1.2rem;
  cursor: pointer;
  color: var(--text-dim);
  line-height: 1;
  padding: 0 0.25rem;
}

.upload-toast-close:hover {
  color: var(--error-color);
}

.upload-toast-filename {
  font-size: 0.75rem;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 0.5rem;
}

.upload-toast-progress {
  width: 100%;
  height: 8px;
  background: var(--surface-alt);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 0.4rem;
}

.upload-toast-bar {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, var(--accent-color), var(--accent-hover));
  border-radius: 6px;
  transition: width 0.15s ease;
}

.upload-toast-text {
  font-size: 0.65rem;
  color: var(--text-dim);
}

@media (max-width: 600px) {
  .upload-toast {
    bottom: 10px;
    right: 10px;
    left: 10px;
    width: auto;
  }
}


/* Universal Button State Rules - Hardware Aesthetic */
/* Default and active states have no shadow, hover has subtle depth */

button,
input[type="submit"],
input[type="button"],
input[type="reset"],
.btn,
.file-button,
.kick-button,
.kick-button-inline,
.unkick-button,
.btn-manage-devices,
.btn-manage-bans,
.btn-download,
.btn-chat,
.active-close,
.banned-close {
  box-shadow: none !important;
}

button:active,
input[type="submit"]:active,
input[type="button"]:active,
input[type="reset"]:active,
.btn:active,
.file-button:active,
.kick-button:active,
.kick-button-inline:active,
.unkick-button:active,
.btn-manage-devices:active,
.btn-manage-bans:active,
.btn-download:active,
.btn-chat:active,
.active-close:active,
.banned-close:active {
  box-shadow: none !important;
}

button:focus,
input[type="submit"]:focus,
input[type="button"]:focus,
input[type="reset"]:focus,
.btn:focus,
.file-button:focus,
.kick-button:focus,
.kick-button-inline:focus,
.unkick-button:focus,
.btn-manage-devices:focus,
.btn-manage-bans:focus,
.btn-download:focus,
.btn-chat:focus,
.active-close:focus,
.banned-close:focus {
  box-shadow: none !important;
}

/* Only show outline on keyboard focus - no glow */
button:focus-visible,
input[type="submit"]:focus-visible,
input[type="button"]:focus-visible,
input[type="reset"]:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
  box-shadow: none !important;
}
"""
