// Background Service Worker for Real-time Speech Translator Extension
let socket = null;
let activeTabId = null;
let isTranslating = false;
let userSettings = {
  capture_mode: "both",
  user_id: "user-" + Math.floor(Math.random() * 1000),
  spoken_lang: "en",
  target_lang: "id",
  tts_enabled: true,
  virtual_mic_enabled: false,
  ws_token: "",
  ducking_level: 0.2
};

// Load saved settings from Chrome Storage
chrome.storage.local.get(["userSettings"], (result) => {
  if (result.userSettings) {
    userSettings = { ...userSettings, ...result.userSettings };
  }
});

// WebSocket Ping Heartbeat to prevent Chrome / Uvicorn inactivity disconnects
setInterval(() => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "ping" }));
  }
}, 10000);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "START_TRANSLATION") {
    activeTabId = request.tabId;
    startTranslation(activeTabId, request.tabStreamId, sendResponse);
    return true;
  } else if (request.action === "STOP_TRANSLATION") {
    stopTranslation();
    sendResponse({ status: "stopped" });
  } else if (request.action === "UPDATE_SETTINGS") {
    userSettings = { ...userSettings, ...request.settings };
    chrome.storage.local.set({ userSettings });
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: "config",
        config: {
          capture_mode: userSettings.capture_mode,
          spoken_lang: userSettings.spoken_lang,
          target_lang: userSettings.target_lang,
          tts_enabled: userSettings.tts_enabled,
          virtual_mic_enabled: userSettings.virtual_mic_enabled === true
        }
      }));
    }
    sendResponse({ status: "updated", settings: userSettings });
  } else if (request.action === "GET_STATUS") {
    sendResponse({ isTranslating, userSettings });
  } else if (request.action === "REAL_AUDIO_CHUNK_MIC") {
    if (socket && socket.readyState === WebSocket.OPEN && request.audio_b64) {
      socket.send(JSON.stringify({ type: "audio_chunk_mic", audio_b64: request.audio_b64 }));
    }
  } else if (request.action === "REAL_AUDIO_CHUNK_TAB") {
    if (socket && socket.readyState === WebSocket.OPEN && request.audio_b64) {
      socket.send(JSON.stringify({ type: "audio_chunk_tab", audio_b64: request.audio_b64 }));
    }
  }
});

async function setupOffscreenDocument(path) {
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT'],
    documentUrls: [chrome.runtime.getURL(path)]
  });
  if (existingContexts.length > 0) {
    await chrome.offscreen.closeDocument();
  }
  await chrome.offscreen.createDocument({
    url: path,
    reasons: ['USER_MEDIA'],
    justification: 'Recording microphone and tab audio for real-time speech translation'
  });
}

function startTranslation(tabId, tabStreamId, sendResponse) {
  if (isTranslating) {
    sendResponse({ status: "already_running" });
    return;
  }
  connectAndStart(tabId, tabStreamId, sendResponse);
}

function connectAndStart(tabId, tabStreamId, sendResponse) {
  let hasResponded = false;
  const token = (userSettings.ws_token || "").trim();
  const wsUrl = `ws://localhost:8000/ws/translate?user_id=${encodeURIComponent(userSettings.user_id)}${token ? `&token=${encodeURIComponent(token)}` : ""}`;
  console.log("Connecting WebSocket to:", wsUrl);

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = async () => {
      try {
        console.log("WebSocket connected to AI Server.");
        isTranslating = true;

        socket.send(JSON.stringify({
          type: "config",
          config: {
            capture_mode: userSettings.capture_mode,
            spoken_lang: userSettings.spoken_lang,
            target_lang: userSettings.target_lang,
            tts_enabled: userSettings.tts_enabled,
            virtual_mic_enabled: userSettings.virtual_mic_enabled === true
          }
        }));

        await setupOffscreenDocument('offscreen.html');
        let hasRespondedObj = { get value() { return hasResponded; }, set value(v) { hasResponded = v; } };
        startOffscreenRecording(tabStreamId, sendResponse, tabId, hasRespondedObj);

        if (activeTabId) {
          try {
            await chrome.scripting.insertCSS({ target: { tabId: activeTabId }, files: ["content.css"] }).catch(() => {});
            await chrome.scripting.executeScript({ target: { tabId: activeTabId }, files: ["content.js"] }).catch(() => {});
          } catch (e) {}
          chrome.tabs.sendMessage(activeTabId, { action: "TRANSLATION_STARTED" }).catch(() => {});
        }

      } catch (err) {
        console.error("Error in onopen:", err);
        stopTranslation();
        if (!hasResponded) {
          hasResponded = true;
          sendResponse({ status: "error", message: err.message });
        }
      }
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("WS Received Payload:", data);

      if (data.type === "translation_result") {
        if (activeTabId) {
          chrome.tabs.sendMessage(activeTabId, {
            action: "SHOW_SUBTITLE",
            text: data.translated_text,
            original: data.original_text,
            type: data.source === "mic" ? "OWN" : "PEER",
            lang: data.source === "mic" ? data.tgt_lang : data.src_lang,
            latency: data.latency_ms
          });

          if (data.audio_b64) {
            playTtsWithDucking(activeTabId, data.audio_b64, data.source);
          }
        }
      }
    };

    socket.onerror = (err) => {
      console.error("WebSocket Error:", err);
      stopTranslation();
      if (!hasResponded) {
        hasResponded = true;
        sendResponse({ status: "error", message: "WebSocket connection failed" });
      }
    };

    socket.onclose = () => {
      console.log("WebSocket connection closed.");
      stopTranslation();
      if (!hasResponded) {
        hasResponded = true;
        sendResponse({ status: "error", message: "WebSocket closed before connecting" });
      }
    };

  } catch (err) {
    console.error("Failed to connect WebSocket:", err);
    if (!hasResponded) {
      hasResponded = true;
      sendResponse({ status: "error", message: err.message });
    }
  }
}

function startOffscreenRecording(tabStreamId, sendResponse, tabId, hasRespondedObj) {
  chrome.runtime.sendMessage({
    action: 'START_RECORDING',
    capture_mode: userSettings.capture_mode,
    tabStreamId: tabStreamId
  }, (resp) => {
    if (chrome.runtime.lastError) {
      console.error("Failed to start recording:", chrome.runtime.lastError);
      stopTranslation();
      if (!hasRespondedObj.value) {
        hasRespondedObj.value = true;
        sendResponse({ status: "error", message: "Failed to start offscreen recording" });
      }
      return;
    }
    chrome.tabs.sendMessage(tabId, { action: "TRANSLATION_STARTED", settings: userSettings }, () => {
      const err = chrome.runtime.lastError;
    });
    if (!hasRespondedObj.value) {
      hasRespondedObj.value = true;
      sendResponse({ status: "started" });
    }
  });
}

function stopTranslation() {
  isTranslating = false;
  if (socket) {
    socket.close();
    socket = null;
  }
  chrome.runtime.sendMessage({ action: 'STOP_RECORDING' });
  if (activeTabId) {
    chrome.tabs.sendMessage(activeTabId, { action: "TRANSLATION_STOPPED" });
    activeTabId = null;
  }
}

function playTtsWithDucking(tabId, audioB64, source) {
  chrome.tabs.sendMessage(tabId, {
    action: "PLAY_TTS_AUDIO",
    audio_b64: audioB64,
    ducking_level: userSettings.ducking_level,
    source: source
  });
}
