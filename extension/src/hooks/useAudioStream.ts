import { useState, useCallback } from 'react';

export type CaptureMode = 'mic' | 'tab' | 'both';

interface AudioStreamState {
  isRecording: boolean;
  stream: MediaStream | null;
  error: string | null;
}

export function useAudioStream() {
  const [state, setState] = useState<AudioStreamState>({
    isRecording: false,
    stream: null,
    error: null,
  });

  const startRecording = useCallback(async (mode: CaptureMode) => {
    try {
      setState(s => ({ ...s, error: null }));
      let mediaStream: MediaStream;

      const isChromeExtension = typeof chrome !== 'undefined' && chrome.tabCapture;

      if (isChromeExtension) {
        // --- CHROME EXTENSION ENVIRONMENT ---
        if (mode === 'tab') {
          mediaStream = await new Promise((resolve, reject) => {
            chrome.tabCapture.capture({ audio: true, video: false }, (stream) => {
              if (chrome.runtime.lastError || !stream) {
                reject(new Error(chrome.runtime.lastError?.message || 'Failed to capture tab'));
                return;
              }
              resolve(stream);
            });
          });
        } else if (mode === 'mic') {
          mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } else {
          // both: need to merge
          const tabStream = await new Promise<MediaStream>((resolve, reject) => {
            chrome.tabCapture.capture({ audio: true, video: false }, (stream) => {
              if (chrome.runtime.lastError || !stream) {
                reject(new Error(chrome.runtime.lastError?.message || 'Failed to capture tab'));
                return;
              }
              resolve(stream);
            });
          });
          const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          
          // Merge tracks (basic implementation, in reality needs AudioContext for proper mixing)
          mediaStream = new MediaStream([
            ...tabStream.getAudioTracks(),
            ...micStream.getAudioTracks()
          ]);
        }
      } else {
        // --- WEB APP ENVIRONMENT ---
        if (mode === 'tab') {
          mediaStream = await navigator.mediaDevices.getDisplayMedia({
            audio: true,
            video: true // WebRTC requires video to be requested for getDisplayMedia in many browsers
          });
          // Remove video tracks to just keep audio
          mediaStream.getVideoTracks().forEach(track => track.stop());
        } else if (mode === 'mic') {
          mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } else {
          // both
          const displayStream = await navigator.mediaDevices.getDisplayMedia({ audio: true, video: true });
          displayStream.getVideoTracks().forEach(track => track.stop());
          const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          
          mediaStream = new MediaStream([
            ...displayStream.getAudioTracks(),
            ...micStream.getAudioTracks()
          ]);
        }
      }

      setState({
        isRecording: true,
        stream: mediaStream,
        error: null,
      });

      return mediaStream;
    } catch (err: any) {
      console.error("Audio capture failed:", err);
      setState(s => ({ ...s, error: err.message || 'Unknown error occurred' }));
      return null;
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (state.stream) {
      state.stream.getTracks().forEach(track => track.stop());
    }
    setState({
      isRecording: false,
      stream: null,
      error: null,
    });
  }, [state.stream]);

  return {
    ...state,
    startRecording,
    stopRecording
  };
}
