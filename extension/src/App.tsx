import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useAudioStream } from './hooks/useAudioStream';
import type { CaptureMode } from './hooks/useAudioStream';

const ICON = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
    <line x1="12" y1="19" x2="12" y2="23"></line>
    <line x1="8" y1="23" x2="16" y2="23"></line>
  </svg>
);

function App() {
  const { isRecording, startRecording, stopRecording, updateSettings, error } = useAudioStream();
  const [mode, setMode] = useState<CaptureMode>('both');
  const [srcLang, setSrcLang] = useState('auto');
  const [tgtLang, setTgtLang] = useState('id');
  const [tts, setTts] = useState(true);
  const [vmic, setVmic] = useState(false);

  // Load persisted settings from background service worker on mount.
  useEffect(() => {
    chrome.runtime.sendMessage({ action: "GET_STATUS" }, (resp) => {
      const s = resp?.userSettings;
      if (!s) return;
      setMode(s.capture_mode || 'both');
      setSrcLang(s.spoken_lang === 'id' ? 'id' : 'auto');
      setTgtLang(s.target_lang || 'id');
      setTts(s.tts_enabled !== false);
      setVmic(s.virtual_mic_enabled === true);
    });
  }, []);

  // Push setting changes to the background worker.
  useEffect(() => {
    updateSettings({
      capture_mode: mode,
      spoken_lang: srcLang === 'auto' ? 'en' : srcLang,
      target_lang: tgtLang,
      tts_enabled: tts,
      virtual_mic_enabled: vmic,
    });
  }, [mode, srcLang, tgtLang, tts, vmic, updateSettings]);

  const toggleTranslation = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      const settings = {
        capture_mode: mode,
        spoken_lang: srcLang === 'auto' ? 'en' : srcLang,
        target_lang: tgtLang,
        tts_enabled: tts,
        virtual_mic_enabled: vmic,
      };
      await startRecording(mode, settings);
    }
  };

  return (
    <div className="w-[320px] bg-white text-neutral-900 font-sans select-none">
      {/* Header */}
      <header className="flex items-center gap-3 px-5 py-4 border-b border-neutral-200">
        <div className="w-8 h-8 bg-neutral-900 text-white rounded-md flex items-center justify-center shrink-0">
          {ICON}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-[13px] font-semibold tracking-tight leading-tight">Translator</h3>
          <span className="text-[11px] text-neutral-500">Speech-to-Speech · EN ⇄ ID</span>
        </div>
        <div
          className={`w-2 h-2 rounded-full shrink-0 transition-colors ${isRecording ? 'bg-neutral-900 animate-pulse' : 'bg-neutral-300'}`}
        />
      </header>

      <div className="px-5 py-4 space-y-4">
        {/* Error */}
        {error && (
          <div className="px-3 py-2 border border-neutral-300 bg-neutral-50 rounded text-[11px] text-neutral-600">
            {error}
          </div>
        )}

        {/* Mode */}
        <div>
          <Label className="text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-400 mb-1.5 block">Mode Capture</Label>
          <Select value={mode} onValueChange={(val) => val && setMode(val as CaptureMode)}>
            <SelectTrigger className="w-full bg-transparent border-neutral-300 text-[13px] h-9 rounded-md focus:ring-neutral-400">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-white border-neutral-200 text-neutral-900">
              <SelectItem value="both">Mic + Tab</SelectItem>
              <SelectItem value="mic">Mikrofon</SelectItem>
              <SelectItem value="tab">Audio Tab</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Source / Target */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-400 mb-1.5 block">Dari</Label>
            <Select value={srcLang} onValueChange={(v) => v != null && setSrcLang(v)}>
              <SelectTrigger className="w-full bg-transparent border-neutral-300 text-[13px] h-9 rounded-md focus:ring-neutral-400">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white border-neutral-200 text-neutral-900">
                <SelectItem value="auto">Auto</SelectItem>
                <SelectItem value="id">Indonesia</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-400 mb-1.5 block">Ke</Label>
            <Select value={tgtLang} onValueChange={(v) => v != null && setTgtLang(v)}>
              <SelectTrigger className="w-full bg-transparent border-neutral-300 text-[13px] h-9 rounded-md focus:ring-neutral-400">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white border-neutral-200 text-neutral-900">
                <SelectItem value="id">Indonesia</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Toggles */}
        <div className="pt-2 border-t border-neutral-200 space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="tts" className="text-[13px] text-neutral-700 font-normal">Audio TTS</Label>
            <Checkbox
              id="tts"
              checked={tts}
              onCheckedChange={(c) => setTts(!!c)}
              className="border-neutral-300 data-[state=checked]:bg-neutral-900 data-[state=checked]:border-neutral-900 data-[state=checked]:text-white rounded-[3px]"
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="vmic" className="text-[13px] text-neutral-700 font-normal">Virtual Mic</Label>
            <Checkbox
              id="vmic"
              checked={vmic}
              onCheckedChange={(c) => setVmic(!!c)}
              className="border-neutral-300 data-[state=checked]:bg-neutral-900 data-[state=checked]:border-neutral-900 data-[state=checked]:text-white rounded-[3px]"
            />
          </div>
        </div>
      </div>

      {/* Footer / CTA */}
      <footer className="px-5 pb-5">
        <Button
          onClick={toggleTranslation}
          className={`w-full h-10 rounded-md text-[13px] font-semibold transition-colors border ${
            isRecording
              ? 'bg-white text-neutral-900 border-neutral-900 hover:bg-neutral-100'
              : 'bg-neutral-900 text-white border-neutral-900 hover:bg-neutral-700'
          }`}
        >
          {isRecording ? 'Stop' : 'Start'}
        </Button>
        <p className="mt-3 text-center text-[10px] text-neutral-400">
          {isRecording ? 'Menerjemahkan · dengarkan audio keluar' : 'Siap menerjemahkan'}
        </p>
      </footer>
    </div>
  )
}

export default App
