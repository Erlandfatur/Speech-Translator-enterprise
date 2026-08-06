import React, { useState } from 'react';
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
import { useAudioStream, CaptureMode } from './hooks/useAudioStream';

function App() {
  const { isRecording, startRecording, stopRecording, error } = useAudioStream();
  const [mode, setMode] = useState<CaptureMode>('both');

  const toggleTranslation = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording(mode);
    }
  };

  return (
    <div className="w-[320px] p-5 bg-black text-white font-sans">
      <div className="flex items-center gap-3 mb-5 pb-4 border-b border-neutral-800">
        <div className="w-8 h-8 bg-white text-black rounded-md flex items-center justify-center font-bold">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </div>
        <div>
          <h3 className="m-0 text-sm font-semibold tracking-tight">Translator</h3>
          <span className="text-[11px] text-neutral-400">Universal Enterprise</span>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-2 bg-red-900/50 border border-red-500 rounded text-xs text-red-200">
          Error: {error}
        </div>
      )}

      <div className="mb-4">
        <Label className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 mb-2 block">Mode Perekaman</Label>
        <Select value={mode} onValueChange={(val: CaptureMode) => setMode(val)}>
          <SelectTrigger className="w-full bg-neutral-900 border-neutral-800 text-sm h-10 focus:ring-white">
            <SelectValue placeholder="Pilih mode" />
          </SelectTrigger>
          <SelectContent className="bg-neutral-900 border-neutral-800 text-white">
            <SelectItem value="both">Keduanya (Mic & Tab)</SelectItem>
            <SelectItem value="mic">Hanya Mikrofon</SelectItem>
            <SelectItem value="tab">Hanya Audio Tab/Sistem</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="mb-4">
        <Label className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 mb-2 block">Bahasa Asal</Label>
        <Select defaultValue="auto">
          <SelectTrigger className="w-full bg-neutral-900 border-neutral-800 text-sm h-10 focus:ring-white">
            <SelectValue placeholder="Pilih bahasa" />
          </SelectTrigger>
          <SelectContent className="bg-neutral-900 border-neutral-800 text-white">
            <SelectItem value="auto">Otodetek (Auto)</SelectItem>
            <SelectItem value="id">Indonesia</SelectItem>
            <SelectItem value="en">English</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="mb-6">
        <Label className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 mb-2 block">Bahasa Tujuan</Label>
        <Select defaultValue="id">
          <SelectTrigger className="w-full bg-neutral-900 border-neutral-800 text-sm h-10 focus:ring-white">
            <SelectValue placeholder="Pilih bahasa" />
          </SelectTrigger>
          <SelectContent className="bg-neutral-900 border-neutral-800 text-white">
            <SelectItem value="id">Indonesia</SelectItem>
            <SelectItem value="en">English</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center justify-between mb-4">
        <Label htmlFor="tts" className="text-xs text-neutral-300 font-medium">Audio TTS & Ducking</Label>
        <Checkbox id="tts" defaultChecked className="border-white data-[state=checked]:bg-white data-[state=checked]:text-black" />
      </div>

      <div className="flex items-center justify-between mb-6">
        <Label htmlFor="vmic" className="text-xs text-neutral-300 font-medium">Virtual Mic Output</Label>
        <Checkbox id="vmic" className="border-white data-[state=checked]:bg-white data-[state=checked]:text-black" />
      </div>

      <Button 
        onClick={toggleTranslation}
        className={`w-full font-semibold h-10 transition-colors ${
          isRecording 
            ? 'bg-red-600 text-white hover:bg-red-700' 
            : 'bg-white text-black hover:bg-neutral-200'
        }`}
      >
        {isRecording ? 'Stop Translation' : 'Start Translation'}
      </Button>
    </div>
  )
}

export default App

