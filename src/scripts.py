# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
JavaScript for Vortex web interface.

This module contains the client-side JavaScript that handles file selection
display and parallel multi-file uploads with progress tracking.
"""

JS_UPLOAD_HANDLER = """
document.addEventListener('DOMContentLoaded', function() {
	// Configuration

	// Maximum number of simultaneous upload connections.
	// 6 connections utilize full browser capacity for maximum throughput.
	var MAX_PARALLEL = 6;


	// Server Stop Button
	// Handle server shutdown request (host only).

	var stopBtn = document.getElementById('server-stop-btn');
	if (stopBtn) {
		stopBtn.addEventListener('click', function() {
			if (confirm('Stop the Vortex server?')) {
				fetch('/api/stop-server', { method: 'POST' })
					.then(function(response) {
						return response.json();
					})
					.then(function(data) {
						if (data.success) {
							showTerminationMessage();
						} else {
							alert(data.error || 'Failed to stop server');
						}
					})
					.catch(function(err) {
						console.error('Error stopping server:', err);
					});
			}
		});
	}


	// Poll server status every 500ms
	function checkServerStatus() {
		fetch('/api/server-status')
			.then(function(response) {
				return response.json();
			})
			.then(function(data) {
				if (data.terminating) {
					showTerminationMessage();
				} else {
					setTimeout(checkServerStatus, 500);
				}
			})
			.catch(function() {
				// Server already stopped - ignore errors
			});
	}

	function showTerminationMessage() {
		// Abort all active uploads if any
		try {
			globalAbortAllUploads();
		} catch (e) {
			// Ignore errors if upload form not initialized
		}

		// Stop audio player using proper dismissal method
		if (window.VortexAudioPlayer && typeof window.VortexAudioPlayer.dismiss === 'function') {
			window.VortexAudioPlayer.dismiss();
		}

		// Hide stop button
		var stopBtn = document.getElementById('server-stop-btn');
		if (stopBtn) {
			stopBtn.style.display = 'none';
		}

		// Remove all main content
		var deviceMain = document.querySelector('.device-main');
		if (deviceMain) {
			deviceMain.innerHTML = '<div class="termination-message">SERVER TERMINATED</div>';
		}
	}

	// Start polling on page load
	checkServerStatus();


	// File Input Display
	// Update the filename display when user selects files.

	var fileInputs = document.querySelectorAll('.file-input input[type="file"]');

	fileInputs.forEach(function(input) {
		input.addEventListener('change', function() {
			var label = input.closest('.file-input');
			if (!label) return;

			var nameSpan = label.querySelector('.file-name');
			if (!nameSpan) return;

			if (input.files && input.files.length > 0) {
				if (input.files.length > 10) {
					// Large selection: show processing indicator, yield to UI thread
					nameSpan.textContent = 'Processing ' + input.files.length + ' files...';
					setTimeout(function() {
						nameSpan.textContent = input.files.length + ' files selected';
					}, 50);
				} else if (input.files.length === 1) {
					nameSpan.textContent = input.files[0].name;
				} else {
					nameSpan.textContent = input.files.length + ' files selected';
				}
			} else {
				nameSpan.textContent = 'No file selected';
			}
		});
	});


	// Parallel Multi-File Upload
	// Handles uploading multiple files simultaneously with aggregate progress.

	var uploadForm = document.querySelector('form[enctype="multipart/form-data"]');
	
	// Global upload tracking for abortion capability
	var globalFileProgress = {};
	var globalAbortAllUploads = function() {
		for (var key in globalFileProgress) {
			var uploadData = globalFileProgress[key];
			if (uploadData && uploadData.xhr) {
				try {
					uploadData.xhr.abort();
				} catch (e) {
					// Ignore abort errors
				}
			}
		}
		globalFileProgress = {};
	};

	if (uploadForm) {
		uploadForm.addEventListener('submit', function(e) {
			e.preventDefault();

			var fileInput = uploadForm.querySelector('input[type="file"]');
			if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
				return;
			}

			// --- Initialize Upload State ---

			var files = Array.from(fileInput.files);
			var totalFiles = files.length;
			var totalBytes = files.reduce(function(sum, f) { return sum + f.size; }, 0);
			var uploadedBytes = 0;
			var completedFiles = 0;
			var failedFiles = [];
			var activeUploads = 0;
			var fileIndex = 0;

			// --- Get UI Elements ---

			var progressContainer = document.querySelector('.upload-progress');
			var progressBar = document.querySelector('.progress-bar');
			var progressText = document.querySelector('.progress-text');
			var uploadError = document.querySelector('.upload-error');
			var submitBtn = uploadForm.querySelector('button[type="submit"]');

			// Show progress UI, hide errors, disable submit
			if (progressContainer) progressContainer.classList.add('active');
			if (uploadError) {
				uploadError.classList.remove('active');
				uploadError.textContent = '';
			}
			if (submitBtn) submitBtn.disabled = true;

			// Track bytes uploaded per file for accurate progress calculation
			// Store both progress and XHR objects for abortion capability
			var fileProgress = globalFileProgress;

			// --- Abort All Uploads Function ---
			// Called when server is terminating to cancel all in-progress uploads

			function abortAllUploads() {
				globalAbortAllUploads();
			}

			// --- Progress Update Function ---

			function updateProgress() {
				var currentUploaded = uploadedBytes;
				for (var key in fileProgress) {
					var uploadData = fileProgress[key];
					if (uploadData) {
						currentUploaded += uploadData.bytes || 0;
					}
				}
				var percent = totalBytes > 0
					? Math.round((currentUploaded / totalBytes) * 100)
					: 0;

				if (progressBar) {
					progressBar.style.width = percent + '%';
				}
				if (progressText) {
					progressText.textContent =
						formatSize(currentUploaded) + ' / ' + formatSize(totalBytes) +
						' (' + percent + '%) - ' + completedFiles + '/' + totalFiles + ' files';
				}
			}

			// --- Upload Queue Manager ---
			// Starts uploads up to MAX_PARALLEL at a time.

			function uploadNext() {
				while (activeUploads < MAX_PARALLEL && fileIndex < files.length) {
					uploadFile(files[fileIndex], fileIndex);
					fileIndex++;
				}
			}

			// --- Single File Upload Function ---

			function uploadFile(file, idx) {
				activeUploads++;
				fileProgress[idx] = { bytes: 0, xhr: null };

				var formData = new FormData();
				formData.append('file', file);

				var xhr = new XMLHttpRequest();
				
				// Store XHR reference for potential abortion
				fileProgress[idx].xhr = xhr;

				// Track upload progress for this file
				xhr.upload.addEventListener('progress', function(e) {
					if (e.lengthComputable) {
						fileProgress[idx].bytes = e.loaded;
						updateProgress();
					}
				});

				// Handle upload completion
				xhr.addEventListener('load', function() {
					activeUploads--;
					delete fileProgress[idx];

					if (xhr.status === 503) {
						// Server is shutting down
						abortAllUploads();
						showTerminationMessage();
						return;
					}

					if (xhr.status >= 200 && xhr.status < 400) {
						completedFiles++;
						uploadedBytes += file.size;
					} else {
						failedFiles.push(file.name);
					}

					updateProgress();

					// Start next upload or handle completion
					if (fileIndex < files.length) {
						uploadNext();
					} else if (activeUploads === 0) {
						handleAllComplete();
					}
				});

				// Handle network errors
				xhr.addEventListener('error', function() {
					activeUploads--;
					delete fileProgress[idx];
					failedFiles.push(file.name);

					if (fileIndex < files.length) {
						uploadNext();
					} else if (activeUploads === 0) {
						handleAllComplete();
					}
				});

				// Handle abort events
				xhr.addEventListener('abort', function() {
					activeUploads--;
					delete fileProgress[idx];
				});

				xhr.open('POST', window.location.pathname, true);
				xhr.send(formData);
			}

			// --- Completion Handler ---

			function handleAllComplete() {
				if (failedFiles.length === 0) {
					// All uploads succeeded - update file list via AJAX to preserve audio player
					refreshFileList();

					// Auto-refresh file list after 1 second to show new file
					setTimeout(() => {
						location.reload();
					}, 1000);
				} else {
					// Some uploads failed - show error
					if (uploadError) {
						uploadError.textContent = 'Failed: ' + failedFiles.join(', ');
						uploadError.classList.add('active');
					}

					if (completedFiles > 0) {
						// Some succeeded - refresh after brief delay
						setTimeout(function() { refreshFileList(); }, 2000);
					} else {
						// All failed - reset UI for retry
						if (progressContainer) progressContainer.classList.remove('active');
						if (submitBtn) submitBtn.disabled = false;
					}
				}
			}

			/**
			 * Refresh file list without page reload (preserves audio player state).
			 * Uses same pattern as navigateToDirectory().
			 */
			function refreshFileList() {
				var fileList = document.querySelector('.file-list');
				if (!fileList) {
					// Fallback to full page reload if file list not found
					window.location.reload();
					return;
				}

				// Add loading state
				fileList.classList.add('updating');

				fetch(window.location.pathname, {
					headers: {
						'X-Requested-With': 'XMLHttpRequest'
					}
				})
					.then(function(response) {
						if (!response.ok) throw new Error('Refresh failed');
						return response.text();
					})
					.then(function(html) {
						var parser = new DOMParser();
						var doc = parser.parseFromString(html, 'text/html');

						// Update file listing
						var newFileList = doc.querySelector('.file-list');
						var currentFileList = document.querySelector('.file-list');
						if (newFileList && currentFileList) {
							currentFileList.innerHTML = newFileList.innerHTML;
							currentFileList.classList.remove('updating');
						}

						// Update path display
						var newSubheader = doc.querySelector('.device-subheader');
						var currentSubheader = document.querySelector('.device-subheader');
						if (newSubheader && currentSubheader) {
							currentSubheader.innerHTML = newSubheader.innerHTML;
						}

						// Update session data (for chat context)
						var newSessionData = doc.querySelector('#session-data');
						var currentSessionData = document.querySelector('#session-data');
						if (newSessionData && currentSessionData) {
							currentSessionData.dataset.baseDir = newSessionData.dataset.baseDir;
						}

						// Update Download All button href if present
						var downloadBtn = document.querySelector('.btn-download');
						var newDownloadBtn = doc.querySelector('.btn-download');
						if (downloadBtn && newDownloadBtn) {
							downloadBtn.href = newDownloadBtn.href;
						} else if (downloadBtn && !newDownloadBtn) {
							downloadBtn.style.display = 'none';
						} else if (!downloadBtn && newDownloadBtn) {
							// Insert Download All button if it appeared
							var panel = document.querySelector('.panel-files');
							if (panel) {
								var panelTitle = panel.querySelector('.panel-title');
								if (panelTitle && panelTitle.nextSibling) {
									panel.insertBefore(newDownloadBtn, panelTitle.nextSibling);
								}
							}
						}

						// Refresh directory size
						if (typeof fetchDirectorySize === 'function') {
							fetchDirectorySize();
						}

						// Audio player remains untouched - no DOM manipulation
						// Mini-player continues playing seamlessly

						// Reset upload UI
						if (progressContainer) progressContainer.classList.remove('active');
						if (submitBtn) submitBtn.disabled = false;
					})
					.catch(function(error) {
						console.error('File list refresh failed:', error);
						fileList.classList.remove('updating');
						// Fallback to full page reload
						window.location.reload();
					});
			}

			// --- Start Upload ---
			uploadNext();
		});
	}


	// Utility Functions

	/**
	 * Format bytes as human-readable string (e.g., "1.5 MB").
	 */
	function formatSize(bytes) {
		var units = ['B', 'KB', 'MB', 'GB', 'TB'];
		var i = 0;
		while (bytes >= 1024 && i < units.length - 1) {
			bytes /= 1024;
			i++;
		}
		return bytes.toFixed(1) + ' ' + units[i];
	}


	// Chat and Real-Time Features
	// Cross-device chat with polling, QR code generation, and directory size display

	var sessionData = document.getElementById('session-data');
	if (!sessionData) return;

	var sessionId = sessionData.getAttribute('data-session-id');
	var baseDir = sessionData.getAttribute('data-base-dir');

	if (!sessionId) return;

	// Chat State
	var lastMessageId = null;
	var eventSource = null;
	var deviceIdentity = generateDeviceIdentity();
	var SENDER_NAME = deviceIdentity.device_name;
	var DEVICE_ID = deviceIdentity.device_id;
	var isKicked = false;
	var isHost = false;

	// UI Elements
	var chatMessages = document.getElementById('chat-messages');
	var chatForm = document.getElementById('chat-form');
	var chatInput = document.getElementById('chat-input');
	var chatStatus = document.getElementById('chat-status');
	var dirSizeInfo = document.getElementById('dir-size-info');
	var qrContainer = document.getElementById('qr-container');
	var qrCode = document.getElementById('qr-code');
	var qrUrlText = document.getElementById('qr-url-text');

	// Initialize Features
	initializeChat();
	initializeQRCode();
	fetchDirectorySize();

	/**
	 * Generate or retrieve persistent device identity.
	 * Returns: {device_name: string, device_id: string}
	 */
	function generateDeviceIdentity() {
		// Check if identity already exists in localStorage
		var storedDeviceId = localStorage.getItem('device_id');
		var storedDeviceName = localStorage.getItem('device_name');

		if (storedDeviceId && storedDeviceName) {
			// Ensure cookie is set
			document.cookie = 'device_id=' + storedDeviceId + '; path=/; max-age=31536000';
			return {
				device_id: storedDeviceId,
				device_name: storedDeviceName
			};
		}

		// Generate new identity
		var deviceType = detectDeviceType();
		var randomId = Math.random().toString(36).substr(2, 3).toUpperCase();
		var deviceName = deviceType + '-' + randomId;
		var deviceId = generateUUID();

		// Store in localStorage for persistence
		localStorage.setItem('device_id', deviceId);
		localStorage.setItem('device_name', deviceName);

		// Also set as cookie for server-side access
		document.cookie = 'device_id=' + deviceId + '; path=/; max-age=31536000'; // 1 year

		return {
			device_id: deviceId,
			device_name: deviceName
		};
	}

	/**
	 * Detect device type from user agent.
	 * Returns: iPhone, Android, Windows, Mac, Linux, or Unknown
	 */
	function detectDeviceType() {
		var ua = navigator.userAgent;

		if (/iPhone/i.test(ua)) return 'iPhone';
		if (/iPad/i.test(ua)) return 'iPad';
		if (/Android/i.test(ua)) return 'Android';
		if (/Windows/i.test(ua)) return 'Windows';
		if (/Macintosh/i.test(ua)) return 'Mac';
		if (/Linux/i.test(ua)) return 'Linux';

		return 'Unknown';
	}

	/**
	 * Generate a UUID v4.
	 */
	function generateUUID() {
		return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
			var r = Math.random() * 16 | 0;
			var v = c === 'x' ? r : (r & 0x3 | 0x8);
			return v.toString(16);
		});
	}

	/**
	 * Check if current client is the host.
	 */
	function checkHostStatus() {
		fetch('/api/host-status', {
			headers: {
				'X-Device-ID': DEVICE_ID
			}
		})
			.then(function(response) {
				if (!response.ok) throw new Error('Host check failed');
				return response.json();
			})
			.then(function(data) {
				isHost = data.is_host || false;
				if (isHost) {
					var hostControls = document.getElementById('host-controls');
					if (hostControls) {
						hostControls.style.display = 'flex';
					}
					initializeBannedDevicesUI();
					
					// Show stop button for host only
					var stopBtn = document.getElementById('server-stop-btn');
					if (stopBtn) {
						stopBtn.style.display = 'flex';
					}
				}
			})
			.catch(function(error) {
				console.error('Host status check failed:', error);
				isHost = false;
			});
	}

	/**
	 * Kick a device by device_id (host only).
	 */
	function kickDevice(deviceId, deviceName) {
		if (!isHost) {
			alert('Only the host can kick users.');
			return;
		}

		if (!confirm('Kick ' + deviceName + '?')) {
			return;
		}

		fetch('/api/kick', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'X-Device-ID': DEVICE_ID
			},
			body: JSON.stringify({ device_id: deviceId })
		})
			.then(function(response) {
				if (!response.ok) throw new Error('Kick failed');
				return response.json();
			})
			.then(function(data) {
				console.log('Device kicked:', deviceName);
			})
			.catch(function(error) {
				alert('Failed to kick device: ' + error.message);
			});
	}

	/**
	 * Unkick a device by device_id (host only).
	 */
	function unkickDevice(deviceId) {
		fetch('/api/unkick', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'X-Device-ID': DEVICE_ID
			},
			body: JSON.stringify({ device_id: deviceId })
		})
			.then(function(response) {
				if (!response.ok) throw new Error('Unkick failed');
				return response.json();
			})
			.then(function(data) {
				console.log('Device unbanned');
				loadBannedDevices();
			})
			.catch(function(error) {
				alert('Failed to unkick device: ' + error.message);
			});
	}

	/**
	 * Load and display banned devices (host only).
	 */
	function loadBannedDevices() {
		if (!isHost) return;

		fetch('/api/banned-devices', {
			headers: {
				'X-Device-ID': DEVICE_ID
			}
		})
			.then(function(response) {
				if (!response.ok) throw new Error('Failed to load banned devices');
				return response.json();
			})
			.then(function(data) {
				var bannedList = document.getElementById('banned-list');
				if (!bannedList) return;

				bannedList.innerHTML = '';

				if (data.banned_devices.length === 0) {
					bannedList.innerHTML = '<div class="banned-empty">No kicked devices</div>';
					return;
				}

				data.banned_devices.forEach(function(deviceId) {
					var item = document.createElement('div');
					item.className = 'banned-item';

					var idSpan = document.createElement('span');
					idSpan.className = 'banned-device-id';
					idSpan.textContent = deviceId.substring(0, 8) + '...';
					idSpan.title = deviceId;

					var unkickBtn = document.createElement('button');
					unkickBtn.className = 'unkick-button';
					unkickBtn.textContent = 'Unkick';
					unkickBtn.onclick = function() {
						unkickDevice(deviceId);
					};

					item.appendChild(idSpan);
					item.appendChild(unkickBtn);
					bannedList.appendChild(item);
				});
			})
			.catch(function(error) {
				console.error('Failed to load banned devices:', error);
			});
	}

	/**
	 * Load and display active devices (host only).
	 */
	function loadActiveDevices() {
		if (!isHost) return;

		fetch('/api/active-devices?session=' + encodeURIComponent(sessionId), {
			headers: {
				'X-Device-ID': DEVICE_ID
			}
		})
			.then(function(response) {
				if (!response.ok) throw new Error('Failed to load active devices');
				return response.json();
			})
			.then(function(data) {
				var activeList = document.getElementById('active-list');
				if (!activeList) return;

				activeList.innerHTML = '';

				if (data.active_devices.length === 0) {
					activeList.innerHTML = '<div class="active-empty">No active devices</div>';
					return;
				}

				data.active_devices.forEach(function(device) {
					var item = document.createElement('div');
					item.className = 'active-item';

					var nameSpan = document.createElement('span');
					nameSpan.className = 'active-device-name';
					nameSpan.textContent = device.device_name;

					var kickBtn = document.createElement('button');
					kickBtn.className = 'kick-button-inline';
					kickBtn.textContent = 'Kick';
					kickBtn.onclick = function() {
						kickDevice(device.device_id, device.device_name);
						setTimeout(loadActiveDevices, 500);
					};

					item.appendChild(nameSpan);
					item.appendChild(kickBtn);
					activeList.appendChild(item);
				});
			})
			.catch(function(error) {
				console.error('Failed to load active devices:', error);
			});
	}

	/**
	 * Initialize devices management UI (host only).
	 */
	function initializeBannedDevicesUI() {
		var manageActiveBtn = document.getElementById('manage-active-btn');
		var manageBansBtn = document.getElementById('manage-bans-btn');
		var activeSection = document.getElementById('active-section');
		var bannedSection = document.getElementById('banned-section');
		var activeClose = document.getElementById('active-close');
		var bannedClose = document.getElementById('banned-close');

		var activeRefreshInterval = null;

		if (manageActiveBtn && activeSection && activeClose) {
			manageActiveBtn.addEventListener('click', function() {
				activeSection.style.display = 'block';
				bannedSection.style.display = 'none';
				loadActiveDevices();
				// Auto-refresh active devices every 3 seconds
				if (activeRefreshInterval) clearInterval(activeRefreshInterval);
				activeRefreshInterval = setInterval(loadActiveDevices, 3000);
			});

			activeClose.addEventListener('click', function() {
				activeSection.style.display = 'none';
				if (activeRefreshInterval) {
					clearInterval(activeRefreshInterval);
					activeRefreshInterval = null;
				}
			});
		}

		if (manageBansBtn && bannedSection && bannedClose) {
			manageBansBtn.addEventListener('click', function() {
				bannedSection.style.display = 'block';
				activeSection.style.display = 'none';
				if (activeRefreshInterval) {
					clearInterval(activeRefreshInterval);
					activeRefreshInterval = null;
				}
				loadBannedDevices();
			});

			bannedClose.addEventListener('click', function() {
				bannedSection.style.display = 'none';
			});
		}
	}

	/**
	 * Initialize chat with Server-Sent Events for real-time updates.
	 */
	function initializeChat() {
		if (!chatMessages || !chatForm || !chatInput) return;

		// Start SSE connection for real-time messages
		connectEventSource();

		// Check if this client is the host
		checkHostStatus();

		// Handle message sending
		chatForm.addEventListener('submit', function(e) {
			e.preventDefault();

			var content = chatInput.value.trim();
			if (!content) return;

			var submitBtn = chatForm.querySelector('button[type=\"submit\"]');
			if (submitBtn) submitBtn.disabled = true;

			// Check if kicked
			if (isKicked) {
				return;
			}

			// Send message to server
			fetch('/api/messages', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-Device-ID': DEVICE_ID,
					'X-Device-Name': SENDER_NAME
				},
				body: JSON.stringify({
					session_id: sessionId,
					sender: SENDER_NAME,
					device_id: DEVICE_ID,
					content: content
				})
			})
			.then(function(response) {
				if (response.status === 403) {
					// Device has been kicked
					handleKicked();
					throw new Error('Device banned');
				}
				if (!response.ok) throw new Error('Send failed');
				return response.json();
			})
			.then(function(data) {
				chatInput.value = '';
				if (submitBtn) submitBtn.disabled = false;
				// Message will appear via SSE
			})
			.catch(function(error) {
				console.error('Failed to send message:', error);
				if (submitBtn) submitBtn.disabled = false;
			});
		});

		// Cleanup on page unload
		window.addEventListener('beforeunload', function() {
			if (eventSource) {
				eventSource.close();
				eventSource = null;
			}
		});
	}

	/**
	 * Connect to SSE endpoint for real-time message updates.
	 */
	function connectEventSource() {
		if (eventSource) {
			eventSource.close();
		}

		var url = '/api/events?session=' + encodeURIComponent(sessionId);
		eventSource = new EventSource(url);

		eventSource.onmessage = function(event) {
			try {
				var message = JSON.parse(event.data);
				
				// Check for server termination message
				if (message.type === 'server_terminating') {
					showTerminationMessage();
					if (eventSource) {
						eventSource.close();
						eventSource = null;
					}
					return;
				}
				
				renderMessage(message);
				
				// Update connection status
				if (chatStatus) {
					chatStatus.style.color = '#00cc00';
					chatStatus.classList.remove('offline');
				}
			} catch (error) {
				console.error('Failed to parse SSE message:', error);
			}
		};

		eventSource.onerror = function(error) {
			console.error('SSE connection error:', error);
			
			// Update connection status
			if (chatStatus) {
				chatStatus.style.color = '#cc0000';
				chatStatus.classList.add('offline');
			}

			// Close and attempt reconnect after delay
			eventSource.close();
			eventSource = null;
			
			if (!isKicked) {
				setTimeout(connectEventSource, 5000);
			}
		};

		eventSource.onopen = function() {
			if (chatStatus) {
				chatStatus.style.color = '#00cc00';
				chatStatus.classList.remove('offline');
			}
		};
	}

	/**
	 * Handle device being kicked.
	 */
	function handleKicked() {
		isKicked = true;
		
		// Stop SSE connection
		if (eventSource) {
			eventSource.close();
			eventSource = null;
		}

		if (chatInput) {
			chatInput.disabled = true;
			chatInput.placeholder = '/// CONNECTION TERMINATED ///';
			chatInput.style.color = '#C62828';
			chatInput.style.borderColor = '#C62828';
		}
		if (chatStatus) {
			chatStatus.style.color = '#C62828';
		}

		// Show blocked message
		setTimeout(function() {
			alert('You have been removed from this server by the host.');
		}, 500);
	}

	/**
	 * Render a chat message to the UI.
	 */
	function renderMessage(message) {
		if (!chatMessages) return;

		var messageDiv = document.createElement('div');
		messageDiv.className = 'chat-message';
		
		// Check by device_id for accurate identity matching
		var isOwnMessage = message.device_id && message.device_id === DEVICE_ID;
		if (isOwnMessage) {
			messageDiv.classList.add('chat-message-own');
		}

		var senderDiv = document.createElement('div');
		senderDiv.className = 'chat-sender';
		senderDiv.textContent = message.sender;

		// Add kick button if host and not own message
		if (isHost && !isOwnMessage && message.device_id) {
			var kickBtn = document.createElement('button');
			kickBtn.className = 'kick-button';
			kickBtn.textContent = '×';
			kickBtn.title = 'Kick ' + message.sender;
			kickBtn.onclick = function() {
				kickDevice(message.device_id, message.sender);
			};
			senderDiv.appendChild(kickBtn);
		}

		var contentDiv = document.createElement('div');
		contentDiv.className = 'chat-content';
		
		// Sanitize and linkify content
		var sanitized = escapeHtml(message.content);
		var linkified = linkifyUrls(sanitized);
		contentDiv.innerHTML = linkified;

		var timeDiv = document.createElement('div');
		timeDiv.className = 'chat-timestamp';
		timeDiv.textContent = formatTime(message.timestamp);

		messageDiv.appendChild(senderDiv);
		messageDiv.appendChild(contentDiv);
		messageDiv.appendChild(timeDiv);

		chatMessages.appendChild(messageDiv);
		chatMessages.scrollTop = chatMessages.scrollHeight;
	}

	/**
	 * Escape HTML to prevent XSS.
	 */
	function escapeHtml(text) {
		var div = document.createElement('div');
		div.textContent = text;
		return div.innerHTML;
	}

	/**
	 * Convert URLs in text to clickable links.
	 */
	function linkifyUrls(text) {
		var urlRegex = /(https?:\\/\\/[^\\s]+)/g;
		return text.replace(urlRegex, function(url) {
			return '<a href=\"' + url + '\" target=\"_blank\" rel=\"noopener noreferrer\">' + url + '</a>';
		});
	}

	/**
	 * Format Unix timestamp to HH:MM.
	 */
	function formatTime(timestamp) {
		var date = new Date(timestamp * 1000);
		var hours = date.getHours().toString().padStart(2, '0');
		var minutes = date.getMinutes().toString().padStart(2, '0');
		return hours + ':' + minutes;
	}

	/**
	 * Initialize QR code generation (desktop only).
	 */
	function initializeQRCode() {
		if (!qrContainer || !qrCode || !qrUrlText) return;

		// Skip on mobile/tablet
		if (window.innerWidth < 900) return;

		// Wait for QRCode library to load
		if (typeof QRCode === 'undefined') {
			setTimeout(initializeQRCode, 100);
			return;
		}

		var currentUrl = window.location.href;
		
		// Generate QR code with smaller size for calm aesthetic
		new QRCode(qrCode, {
			text: currentUrl,
			width: 96,
			height: 96
		});

		// Display URL text
		qrUrlText.textContent = currentUrl;
	}

	/**
	 * Fetch directory size information.
	 */
	function fetchDirectorySize() {
		if (!dirSizeInfo) return;

		fetch('/api/directory-size?session=' + encodeURIComponent(sessionId), {
			headers: {
				'X-Device-ID': DEVICE_ID
			}
		})
			.then(function(response) {
				if (!response.ok) throw new Error('Fetch failed');
				return response.json();
			})
			.then(function(data) {
				if (data.size) {
					dirSizeInfo.textContent = 'Total: ' + data.size.total_formatted + 
						' (' + data.size.file_count + ' files)';
				}
			})
			.catch(function(error) {
				dirSizeInfo.textContent = 'Size unavailable';
			});
	}

	/**
	 * Directory Navigation Without Page Reload
	 * Intercepts directory link clicks to maintain audio player state.
	 */
	(function initDirectoryNavigation() {
		// Helper to check if a filename is an audio file
		function isAudioFile(filename) {
			var audioExts = ['.mp3', '.m4a', '.aac', '.flac', '.wav', '.ogg', '.opus', '.wma'];
			var lower = filename.toLowerCase();
			return audioExts.some(function(ext) {
				return lower.endsWith(ext);
			});
		}

		// Helper to check if a filename is an image file
		function isImageFile(filename) {
			var imageExts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.bmp', '.svg', '.avif', '.tiff', '.tif'];
			var lower = filename.toLowerCase();
			return imageExts.some(function(ext) {
				return lower.endsWith(ext);
			});
		}

		// Helper to check if a filename is a video file
		function isVideoFile(filename) {
			var videoExts = ['.mp4', '.webm', '.mov', '.mkv', '.avi', '.m4v', '.ogv', '.3gp', '.wmv'];
			var lower = filename.toLowerCase();
			return videoExts.some(function(ext) {
				return lower.endsWith(ext);
			});
		}

		// Intercept directory link clicks
		document.addEventListener('click', function(e) {
			var target = e.target.closest('a');
			if (!target) return;

			var href = target.getAttribute('href');
			if (!href) return;

			var filename = target.textContent.trim();

			// Skip if:
			// - Audio file (handled by audio player)
			// - Download action
			// - External link
			// - Parent directory (..)
			if (isAudioFile(filename) || href.includes('?download') || href.startsWith('http')) {
				return;
			}

			// Handle image files - open in image viewer
			if (isImageFile(filename)) {
				e.preventDefault();
				e.stopPropagation();
				if (window.VortexImageViewer && typeof window.VortexImageViewer.open === 'function') {
					window.VortexImageViewer.open(href, filename);
				}
				return;
			}

			// Handle video files - open in video player
			if (isVideoFile(filename)) {
				e.preventDefault();
				e.stopPropagation();
				if (window.VortexVideoPlayer && typeof window.VortexVideoPlayer.open === 'function') {
					window.VortexVideoPlayer.open(href, filename);
				}
				return;
			}

			// Check if it's a directory link (ends with / or is parent directory)
			var isDirectory = href.endsWith('/') || filename === '[..]';
			if (!isDirectory) {
				// Check if it has a file extension
				var hasExtension = /\.[a-z0-9]+$/i.test(href.replace(/\/$/, ''));
				if (hasExtension) return; // Let file downloads proceed normally
			}

			// Intercept directory navigation
			e.preventDefault();
			e.stopPropagation();
			navigateToDirectory(href);
		});

		/**
		 * Navigate to a directory without full page reload.
		 */
		function navigateToDirectory(path) {
			var fileList = document.querySelector('.file-list');
			if (!fileList) {
				// Fallback to full page load if file list not found
				window.location.href = path;
				return;
			}

			// Add loading state
			fileList.classList.add('updating');

			fetch(path, {
				headers: {
					'X-Requested-With': 'XMLHttpRequest'
				}
			})
				.then(function(response) {
					if (!response.ok) throw new Error('Navigation failed');
					return response.text();
				})
				.then(function(html) {
					var parser = new DOMParser();
					var doc = parser.parseFromString(html, 'text/html');

					// Update file listing
					var newFileList = doc.querySelector('.file-list');
					var currentFileList = document.querySelector('.file-list');
					if (newFileList && currentFileList) {
						currentFileList.innerHTML = newFileList.innerHTML;
						currentFileList.classList.remove('updating');
					}

					// Update path display
					var newSubheader = doc.querySelector('.device-subheader');
					var currentSubheader = document.querySelector('.device-subheader');
					if (newSubheader && currentSubheader) {
						currentSubheader.innerHTML = newSubheader.innerHTML;
					}

					// Update session data (for chat context)
					var newSessionData = doc.querySelector('#session-data');
					var currentSessionData = document.querySelector('#session-data');
					if (newSessionData && currentSessionData) {
						currentSessionData.dataset.baseDir = newSessionData.dataset.baseDir;
					}

					// Update page title
					var newTitle = doc.querySelector('title');
					if (newTitle) {
						document.title = newTitle.textContent;
					}

					// Update URL without reload
					window.history.pushState({ path: path }, '', path);

					// Update Download All button href if present
					var downloadBtn = document.querySelector('.btn-download');
					var newDownloadBtn = doc.querySelector('.btn-download');
					if (downloadBtn && newDownloadBtn) {
						downloadBtn.href = newDownloadBtn.href;
					} else if (downloadBtn && !newDownloadBtn) {
						downloadBtn.style.display = 'none';
					} else if (!downloadBtn && newDownloadBtn) {
						// Insert Download All button if it appeared
						var panel = document.querySelector('.panel-files');
						if (panel) {
							var panelTitle = panel.querySelector('.panel-title');
							if (panelTitle && panelTitle.nextSibling) {
								panel.insertBefore(newDownloadBtn, panelTitle.nextSibling);
							}
						}
					}

					// Update upload form action to current path
					var uploadForm = document.querySelector('.panel-upload form');
					if (uploadForm) {
						uploadForm.action = path;
					}

					// Refresh directory size
					fetchDirectorySize();

					// Audio player remains untouched - no DOM manipulation
					// Mini-player continues playing seamlessly
				})
				.catch(function(error) {
					console.error('Directory navigation failed:', error);
					fileList.classList.remove('updating');
					// Fallback to full page load
					window.location.href = path;
				});
		}

		// Handle browser back/forward buttons
		window.addEventListener('popstate', function(e) {
			if (e.state && e.state.path) {
				navigateToDirectory(e.state.path);
			} else {
				window.location.reload();
			}
		});

		// Set initial state for back button
		window.history.replaceState({ path: window.location.pathname }, '');
	})();
});
"""
