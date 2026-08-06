// Content Script – injected into YouTube / Meet / Teams tabs
// Guard: only execute once per page load, even if injected multiple times
if (!window.__speechTranslatorInitialized) {
  window.__speechTranslatorInitialized = true;

  // ──────────────────────────────────────────────────────────────────
  // State
  // ──────────────────────────────────────────────────────────────────
  let overlayContainer = null;
  let transcriptList   = null;
  let statusIndicator  = null;
  let isMinimized      = false;
  let transcriptCount  = 0;

  // ──────────────────────────────────────────────────────────────────
  // Build the overlay UI
  // ──────────────────────────────────────────────────────────────────
  function initOverlayUI() {
    if (document.getElementById('speech-translator-overlay')) return;

    overlayContainer = document.createElement('div');
    overlayContainer.id        = 'speech-translator-overlay';
    overlayContainer.className = 'st-overlay-container';

    overlayContainer.innerHTML = `
      <div class="st-header">
        <div class="st-brand">
          <span class="st-dot"></span>
          <span class="st-title">Live Speech &amp; Translation Log</span>
        </div>
        <div class="st-controls">
          <span class="st-platform-badge" id="st-platform-badge">Detecting...</span>
          <button id="st-btn-clear"  class="st-icon-btn" title="Hapus Riwayat">🗑️</button>
          <button id="st-btn-toggle" class="st-icon-btn" title="Minimize/Expand">➖</button>
        </div>
      </div>
      <div class="st-body-content" id="st-body-content">
        <div class="st-transcript-list" id="st-transcript-list">
          <div class="st-placeholder" id="st-placeholder">
            <p>🎙️ Bicara di mikrofon Anda atau dengarkan pembicara rapat...</p>
            <small>Transkrip &amp; Terjemahan real-time akan muncul secara otomatis di sini.</small>
          </div>
        </div>
      </div>
      <div class="st-footer">
        <span id="st-latency-badge" class="st-badge">Latency: -- ms</span>
        <span class="st-count-badge" id="st-count-badge">0 Percakapan</span>
      </div>
    `;

    document.body.appendChild(overlayContainer);
    transcriptList  = document.getElementById('st-transcript-list');
    statusIndicator = overlayContainer.querySelector('.st-dot');

    document.getElementById('st-btn-clear').addEventListener('click', () => {
      if (!transcriptList) return;
      transcriptList.innerHTML = `
        <div class="st-placeholder" id="st-placeholder">
          <p>🎙️ Riwayat dibersihkan. Menunggu suara baru...</p>
        </div>`;
      transcriptCount = 0;
      updateCountBadge();
    });

    document.getElementById('st-btn-toggle').addEventListener('click', () => {
      const bodyContent = document.getElementById('st-body-content');
      const toggleBtn   = document.getElementById('st-btn-toggle');
      isMinimized = !isMinimized;
      if (isMinimized) {
        bodyContent.style.display = 'none';
        toggleBtn.innerText = '➕';
        overlayContainer.classList.add('minimized');
      } else {
        bodyContent.style.display = 'block';
        toggleBtn.innerText = '➖';
        overlayContainer.classList.remove('minimized');
      }
    });

    // Platform badge
    const host  = window.location.hostname;
    const badge = document.getElementById('st-platform-badge');
    if      (host.includes('teams'))        { badge.innerText = 'MS Teams';    badge.classList.add('st-teams');   }
    else if (host.includes('meet.google'))  { badge.innerText = 'Google Meet'; badge.classList.add('st-gmeet');   }
    else if (host.includes('zoom'))         { badge.innerText = 'Zoom Web';    badge.classList.add('st-zoom');    }
    else if (host.includes('youtube'))      { badge.innerText = 'YouTube';     badge.classList.add('st-youtube'); }
    else                                     { badge.innerText = 'Web Meeting'; }
  }

  function updateCountBadge() {
    const badge = document.getElementById('st-count-badge');
    if (badge) badge.innerText = `${transcriptCount} Percakapan`;
  }

  // ──────────────────────────────────────────────────────────────────
  // Messages from Background Service Worker
  // ──────────────────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'TRANSLATION_STARTED') {
      initOverlayUI();
      if (overlayContainer)  overlayContainer.style.display = 'block';
      if (statusIndicator)   statusIndicator.classList.add('active');
    }
    else if (request.action === 'TRANSLATION_STOPPED') {
      if (statusIndicator) statusIndicator.classList.remove('active');
    }
    else if (request.action === 'SHOW_SUBTITLE') {
      displaySubtitle(request);
    }
    else if (request.action === 'PLAY_TTS_AUDIO') {
      playAudioWithDucking(request.audio_b64, request.ducking_level, request.source);
    }
  });

  // ──────────────────────────────────────────────────────────────────
  // Subtitle card renderer
  // ──────────────────────────────────────────────────────────────────
  function displaySubtitle(data) {
    if (!transcriptList) initOverlayUI();
    if (overlayContainer)  overlayContainer.style.display = 'block';
    if (statusIndicator)   statusIndicator.classList.add('active');

    const placeholder = document.getElementById('st-placeholder');
    if (placeholder) placeholder.remove();

    const isPeer       = data.type === 'PEER';
    const borderClass  = isPeer ? 'st-card-peer' : 'st-card-own';
    const speakerLabel = isPeer ? '🔊 Lawan Bicara (Media)' : '🎙️ Suara Anda (Mic)';
    const timeStr      = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    const card = document.createElement('div');
    card.className = `st-transcript-card ${borderClass}`;
    card.innerHTML = `
      <div class="st-card-header">
        <span class="st-speaker-tag">${speakerLabel}</span>
        <span class="st-card-meta">${(data.lang || '').toUpperCase()} · ${timeStr} · ${data.latency || 0}ms</span>
      </div>
      <div class="st-card-body">
        <div class="st-translated-text">${data.text}</div>
        ${data.original ? `<div class="st-original-text">Asli: "${data.original}"</div>` : ''}
      </div>`;

    transcriptList.appendChild(card);
    transcriptCount++;
    updateCountBadge();

    while (transcriptList.children.length > 50) {
      transcriptList.removeChild(transcriptList.firstChild);
    }
    transcriptList.scrollTop = transcriptList.scrollHeight;

    if (data.latency) {
      const latBadge = document.getElementById('st-latency-badge');
      if (latBadge) latBadge.innerText = `Latency: ${data.latency} ms`;
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // TTS playback with volume ducking
  // ──────────────────────────────────────────────────────────────────
  function playAudioWithDucking(audioB64, duckingLevel, source) {
    if (!audioB64) return;

    const mediaElements = document.querySelectorAll('audio, video');
    mediaElements.forEach(el => {
      if (el.dataset.origVolume === undefined) el.dataset.origVolume = el.volume;
      el.volume = Math.max(0, (parseFloat(el.dataset.origVolume) || 1.0) * (duckingLevel || 0.2));
    });

    const audio = new Audio('data:audio/wav;base64,' + audioB64);

    // Route to selected output device if supported
    chrome.storage.local.get(['userSettings'], (res) => {
      const devId = res && res.userSettings && res.userSettings.audio_output_device;
      if (devId && devId !== 'default' && typeof audio.setSinkId === 'function') {
        audio.setSinkId(devId).catch(err => console.warn('setSinkId failed:', err));
      }
    });

    chrome.runtime.sendMessage({ action: 'PAUSE_AUDIO_CAPTURE' });

    const restoreVolume = () => {
      chrome.runtime.sendMessage({ action: 'RESUME_AUDIO_CAPTURE' });
      mediaElements.forEach(el => {
        if (el.dataset.origVolume !== undefined) el.volume = parseFloat(el.dataset.origVolume);
      });
    };

    audio.onended = restoreVolume;
    audio.onerror = () => { console.warn('TTS audio error'); restoreVolume(); };
    audio.play().catch(err => { console.warn('TTS play blocked:', err); restoreVolume(); });
  }

  // ──────────────────────────────────────────────────────────────────
  // Auto-restore overlay if session already running when page loads
  // ──────────────────────────────────────────────────────────────────
  chrome.runtime.sendMessage({ action: 'GET_STATUS' }, (response) => {
    if (response && response.isTranslating) initOverlayUI();
  });
}
