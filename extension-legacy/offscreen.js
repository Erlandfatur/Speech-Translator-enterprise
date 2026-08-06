// Offscreen document for capturing mic and tab audio streams
// This runs in an isolated offscreen page - variables are safe here

let streams = {};
let audioCtxs = {};
let processors = {};
let isTtsPlaying = false;
let ttsSafetyTimeout = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'START_RECORDING') {
    isTtsPlaying = false;
    startRecording(message.capture_mode, message.tabStreamId)
      .then(() => sendResponse({ status: 'started' }))
      .catch((err) => {
        console.error("startRecording error:", err);
        sendResponse({ status: 'error', message: err.message });
      });
    return true; // async response
  }

  if (message.action === 'STOP_RECORDING') {
    stopRecording();
    sendResponse({ status: 'stopped' });
    return;
  }

  if (message.action === 'PAUSE_MIC_CAPTURE' || message.action === 'PAUSE_AUDIO_CAPTURE') {
    isTtsPlaying = true;
    if (streams['mic']) {
      streams['mic'].getAudioTracks().forEach(t => t.enabled = false);
    }
    if (ttsSafetyTimeout) clearTimeout(ttsSafetyTimeout);
    ttsSafetyTimeout = setTimeout(() => {
      isTtsPlaying = false;
      if (streams['mic']) streams['mic'].getAudioTracks().forEach(t => t.enabled = true);
    }, 3000);
    return;
  }

  if (message.action === 'RESUME_MIC_CAPTURE' || message.action === 'RESUME_AUDIO_CAPTURE') {
    isTtsPlaying = false;
    if (ttsSafetyTimeout) clearTimeout(ttsSafetyTimeout);
    if (streams['mic']) streams['mic'].getAudioTracks().forEach(t => t.enabled = true);
    return;
  }
});

async function startRecording(captureMode, tabStreamId) {
  stopRecording(); // Clean up any previous streams first

  if (captureMode === 'mic' || captureMode === 'both') {
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      setupAudioStream(micStream, 'mic', 'REAL_AUDIO_CHUNK_MIC');
      console.log("[offscreen] Mic stream ready.");
    } catch (e) {
      console.error("[offscreen] Mic capture failed:", e);
    }
  }

  if ((captureMode === 'tab' || captureMode === 'both') && tabStreamId) {
    try {
      const tabStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          mandatory: {
            chromeMediaSource: 'tab',
            chromeMediaSourceId: tabStreamId
          }
        },
        video: false
      });
      console.log("[offscreen] Tab stream ready:", tabStream.getAudioTracks());
      setupAudioStream(tabStream, 'tab', 'REAL_AUDIO_CHUNK_TAB');
    } catch (e) {
      console.error("[offscreen] Tab capture failed:", e);
    }
  }
}

function setupAudioStream(stream, id, actionName) {
  streams[id] = stream;

  const audioCtx = new AudioContext({ sampleRate: 16000 });
  audioCtxs[id] = audioCtx;

  // Immediately resume if suspended
  if (audioCtx.state === 'suspended') audioCtx.resume();

  const source = audioCtx.createMediaStreamSource(stream);
  const processor = audioCtx.createScriptProcessor(4096, 1, 1);
  processors[id] = processor;

  processor.onaudioprocess = (e) => {
    // Keep AudioContext alive
    if (audioCtx.state === 'suspended') audioCtx.resume();

    const float32 = e.inputBuffer.getChannelData(0);
    const output32 = e.outputBuffer.getChannelData(0);
    for (let i = 0; i < float32.length; i++) output32[i] = float32[i];

    // Only block MIC during TTS to prevent echo. Tab audio is NEVER blocked.
    if (id === 'mic' && isTtsPlaying) return;

    // Convert Float32 PCM → Int16 → Base64
    const int16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    const b64 = btoa(String.fromCharCode(...new Uint8Array(int16.buffer)));

    chrome.runtime.sendMessage({ action: actionName, audio_b64: b64 }, () => {
      // Swallow any lastError (e.g. background not ready yet)
      void chrome.runtime.lastError;
    });
  };

  // Connect source -> processor -> gainNode -> destination
  // gainNode value is near-zero (not 0) to prevent Web Audio's silence optimization (which skips processing upstream nodes if gain is exactly 0).
  const gainNode = audioCtx.createGain();
  if (id === 'tab') {
    gainNode.gain.value = 0.00001; // Inaudible, but prevents zero-optimization
  } else {
    gainNode.gain.value = 0.00001; 
  }
  
  source.connect(processor);
  processor.connect(gainNode);
  gainNode.connect(audioCtx.destination);
}

function stopRecording() {
  for (const id in processors) {
    try { processors[id].disconnect(); } catch (_) {}
  }
  processors = {};

  for (const id in audioCtxs) {
    try { audioCtxs[id].close(); } catch (_) {}
  }
  audioCtxs = {};

  for (const id in streams) {
    try { streams[id].getTracks().forEach(t => t.stop()); } catch (_) {}
  }
  streams = {};

  // Remove all audio elements we added
  document.querySelectorAll('audio').forEach(el => el.remove());
}
