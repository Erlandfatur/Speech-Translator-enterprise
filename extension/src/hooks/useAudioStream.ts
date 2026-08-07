import { useState, useCallback, useEffect } from 'react';

export type CaptureMode = 'mic' | 'tab' | 'both';

interface AudioStreamState {
  isRecording: boolean;
  error: string | null;
}

// Messages routed to the Background Service Worker, which owns the
// WebSocket + offscreen capture (MV3 requires this indirection).
export function useAudioStream() {
  const [state, setState] = useState<AudioStreamState>({
    isRecording: false,
    error: null,
  });

  const startRecording = useCallback(async (mode: CaptureMode, settings?: Record<string, unknown>) => {
    try {
      setState(s => ({ ...s, error: null }));

      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) {
        throw new Error('Tidak ada tab aktif. Buka tab rapat/YouTube lalu coba lagi.');
      }

      // Capture tab audio requires a streamId obtained inside the user click
      // gesture (MV3). For mic-only mode we don't need it.
      let tabStreamId: string | null = null;
      if (mode === 'tab' || mode === 'both') {
        tabStreamId = await new Promise<string | null>((resolve) => {
          chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id! }, (streamId) => {
            if (chrome.runtime.lastError || !streamId) {
              console.warn("tabCapture streamId notice:", chrome.runtime.lastError?.message);
              resolve(null);
              return;
            }
            resolve(streamId);
          });
        });
      }

      // Persist latest settings (incl. ws_token) to the background BEFORE
      // opening the WebSocket, so the token is guaranteed to be present.
      if (settings) {
        await chrome.runtime.sendMessage({ action: "UPDATE_SETTINGS", settings });
      }

      const response = await chrome.runtime.sendMessage({
        action: "START_TRANSLATION",
        tabId: tab.id,
        tabStreamId,
        capture_mode: mode,
      });

      if (response?.status === "started" || response?.status === "already_running") {
        setState({ isRecording: true, error: null });
        return true;
      }

      throw new Error(response?.message || 'Gagal memulai terjemahan.');
    } catch (err: any) {
      console.error("Audio capture failed:", err);
      setState(s => ({ ...s, error: err.message || 'Unknown error occurred' }));
      return false;
    }
  }, []);

  const stopRecording = useCallback(() => {
    chrome.runtime.sendMessage({ action: "STOP_TRANSLATION" });
    setState({ isRecording: false, error: null });
  }, []);

  // On mount, sync with the background worker so the popup reflects the
  // current state (keeps "Stop" shown if translation is already running).
  useEffect(() => {
    chrome.runtime.sendMessage({ action: "GET_STATUS" }, (resp) => {
      if (resp && resp.isTranslating) {
        setState({ isRecording: true, error: null });
      }
    });
  }, []);

  const updateSettings = useCallback((settings: Record<string, unknown>) => {
    chrome.runtime.sendMessage({ action: "UPDATE_SETTINGS", settings });
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
    updateSettings,
  };
}
