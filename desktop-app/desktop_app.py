"""
Speech Translator — Self-contained Desktop App (BYOK)

A standalone Windows GUI app that captures microphone + system loopback, runs
speech-to-speech translation in-process using the user's OWN AI API keys
(Bring-Your-Own-Key), and plays translated voice + shows subtitles.

No Python runtime or local server needed once packaged as an .exe.

Usage (source):
    pip install -r requirements-app.txt
    python desktop_app.py

Build EXE:
    build_app.bat     (PyInstaller onefile -> dist/SpeechTranslator.exe)
"""
import os
import sys
import tempfile
import threading
import logging

# Allow importing the shared AI pipeline modules from ../server
_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.abspath(os.path.join(_HERE, "..", "server"))
if _SERVER not in sys.path:
    sys.path.insert(0, _SERVER)

import numpy as np
import soundcard as sc
import soundfile as sf

from pipeline.stt import FasterWhisperSTT
from pipeline.nmt import GeminiTranslator
from pipeline.edge_tts_engine import EdgeTTSEngine

RATE = 16000
MIC_FLUSH_BYTES = int(RATE * 2 * 1.5)          # 1.5s min mic buffer
TAB_FLUSH_BYTES = int(RATE * 2 * 4.0)          # 4s fixed loopback window
SILENCE_FRAMES = int(RATE / 2048 * 0.6)        # ~0.6s of silence to flush
RMS_SPEECH = 0.0008                            # min energy to count as speech
BUFFER_MAX_BYTES = int(RATE * 2 * 8.0)         # hard cap 8s

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("DesktopTranslator")


def list_devices() -> dict:
    return {
        "speakers": [(i, s.name) for i, s in enumerate(sc.all_speakers())],
        "mics": [(i, m.name) for i, m in enumerate(sc.all_microphones())],
        "loopbacks": [(i, m.name) for i, m in enumerate(sc.all_microphones(include_loopback=True))],
    }


class TranslatorApp:
    """Tkinter GUI + capture + STT->NMT->TTS pipeline."""

    def __init__(self, root, tk, ttk, devices):
        self.root = root
        self.tk = tk
        self.ttk = ttk
        self.devices = devices
        self.running = False
        self._stop = threading.Event()
        self._buffers = {"mic": bytearray(), "tab": bytearray()}
        self._silence = {"mic": 0, "tab": 0}
        self._last_text = {"mic": "", "tab": ""}
        self._lock = threading.Lock()

        # AI engines (lightweight, cloud-based).
        self.stt = FasterWhisperSTT()
        self.nmt = GeminiTranslator()
        self.tts = EdgeTTSEngine()

        self._build_ui()

    def _build_ui(self):
        tk, ttk = self.tk, self.ttk
        self.root.title("Speech Translator — Desktop (BYOK)")
        self.root.geometry("780x580")
        self.root.configure(bg="#111111")

        tk.Label(self.root, text="Speech Translator — Desktop (BYOK)",
                 bg="#1b1b1b", fg="#ffffff", font=("Segoe UI", 14, "bold"),
                 padx=12, pady=10, anchor="w").pack(fill="x")

        form = tk.Frame(self.root, bg="#1e1e1e", padx=12, pady=8)
        form.pack(fill="x")

        self.var_mic = tk.StringVar()
        self._row(form, "Mikrofon (Anda)",
                  self._combo(form, self.var_mic, [n for _, n in self.devices["mics"]]))

        self.var_loop = tk.StringVar()
        self._row(form, "System audio (Lawan)",
                  self._combo(form, self.var_loop, [n for _, n in self.devices["loopbacks"]]))

        self.var_tts = tk.StringVar()
        self._row(form, "Output Suara Terjemahan",
                  self._combo(form, self.var_tts, [n for _, n in self.devices["speakers"]]))

        self.var_src = tk.StringVar(value="en")
        self._row(form, "Bahasa Asal", self._combo(form, self.var_src, ["en", "id"]))

        self.var_tgt = tk.StringVar(value="id")
        self._row(form, "Bahasa Terjemahan", self._combo(form, self.var_tgt, ["id", "en"]))

        self.var_groq = tk.StringVar()
        self._row(form, "Groq API Key (BYOK)",
                  tk.Entry(form, textvariable=self.var_groq, show="*",
                           bg="#2a2a2a", fg="#ffffff", insertbackground="#ffffff"))

        self.var_gemini = tk.StringVar()
        self._row(form, "Gemini API Key (opsional)",
                  tk.Entry(form, textvariable=self.var_gemini, show="*",
                           bg="#2a2a2a", fg="#ffffff", insertbackground="#ffffff"))

        btns = tk.Frame(self.root, bg="#1e1e1e", pady=6)
        btns.pack(fill="x")
        self.btn = tk.Button(btns, text="Start", command=self.toggle, bg="#3a3a3a", fg="#ffffff",
                             activebackground="#555555", activeforeground="#ffffff",
                             font=("Segoe UI", 10, "bold"), padx=20)
        self.btn.pack(side="left", padx=12)
        self.status = tk.Label(btns, text="Idle", bg="#1e1e1e", fg="#4f8ef7", font=("Segoe UI", 9))
        self.status.pack(side="left", padx=10)

        subs = tk.Frame(self.root, bg="#111111", padx=12, pady=8)
        subs.pack(fill="both", expand=True)

        self.mic_label = tk.Label(subs, text="SUARA ANDA (MIC)", anchor="w", justify="left",
                                  bg="#181818", fg="#4f8ef7", font=("Segoe UI", 10, "bold"),
                                  wraplength=700, padx=10, pady=8)
        self.mic_label.pack(fill="x", pady=3)
        self.tab_label = tk.Label(subs, text="LAWAN BICARA (SYSTEM)", anchor="w", justify="left",
                                  bg="#181818", fg="#3ddc84", font=("Segoe UI", 10, "bold"),
                                  wraplength=700, padx=10, pady=8)
        self.tab_label.pack(fill="x", pady=3)

        # Pre-select sensible defaults.
        if self.devices["mics"]:
            self.var_mic.set(self.devices["mics"][0][1])
        if self.devices["loopbacks"]:
            self.var_loop.set(self.devices["loopbacks"][0][1])
        if self.devices["speakers"]:
            self.var_tts.set(self.devices["speakers"][0][1])

    def _row(self, parent, label, widget):
        r = self.tk.Frame(parent, bg="#1e1e1e")
        r.pack(fill="x", pady=2)
        self.tk.Label(r, text=label, width=22, anchor="w", bg="#1e1e1e", fg="#cccccc",
                      font=("Segoe UI", 9)).pack(side="left")
        widget.pack(side="left", fill="x", expand=True)

    def _combo(self, parent, var, items):
        cb = self.ttk.Combobox(parent, textvariable=var, values=items, state="readonly")
        return cb

    # ---------- Capture ----------
    def _capture_loop(self, rec, key, flush_bytes):
        while not self._stop.is_set():
            try:
                data = rec.record(numframes=2048)
            except Exception as e:
                print(f"[{key}] capture error: {e}")
                continue
            if data.size == 0:
                continue
            mono = data.mean(axis=1) if data.ndim > 1 else data
            sr = int(getattr(rec, "samplerate", RATE) or RATE)
            factor = max(1, sr // RATE)
            if factor > 1:
                mono = mono[::factor]
            mono = np.clip(mono, -1.0, 1.0)
            int16 = (mono * 32767).astype(np.int16)

            rms = float(np.sqrt(np.mean(mono.astype(np.float32) ** 2)))
            is_speech = rms >= RMS_SPEECH

            with self._lock:
                buf = self._buffers[key]
                if is_speech:
                    buf.extend(int16.tobytes())
                    self._silence[key] = 0
                elif len(buf) > 0:
                    buf.extend(int16.tobytes())
                    self._silence[key] += 1

                flush = False
                if len(buf) >= BUFFER_MAX_BYTES:
                    flush = True
                elif key == "tab" and len(buf) >= flush_bytes:
                    flush = True
                elif len(buf) >= MIC_FLUSH_BYTES and self._silence[key] >= SILENCE_FRAMES:
                    flush = True

                if flush and len(buf) > 0:
                    pcm = bytes(buf)
                    buf.clear()
                    self._silence[key] = 0
                else:
                    pcm = b""
            if pcm:
                self._process(key, pcm)

    # ---------- Pipeline ----------
    def _process(self, key, pcm):
        def work():
            try:
                src_lang = self.var_src.get() or "en"
                tgt_lang = self.var_tgt.get() or "id"
                groq_key = (self.var_groq.get() or "").strip() or None
                gemini_key = (self.var_gemini.get() or "").strip() or None

                original, _ = self.stt.transcribe_chunk(pcm, RATE, src_lang, groq_key)
                clean = original.strip()
                if not clean or clean in [".", "..", "..."]:
                    return
                if self._last_text.get(key) and clean.lower() == self._last_text[key].lower():
                    return
                self._last_text[key] = clean

                translated, _ = self.nmt.translate(original, src_lang, tgt_lang, groq_key, gemini_key)

                label = self.mic_label if key == "mic" else self.tab_label
                label.configure(text=f"【{clean}】\n→ {translated}")

                if translated.strip():
                    audio, _ = self.tts.synthesize(translated, tgt_lang)
                    if audio:
                        self._play(audio)
            except Exception as e:
                print(f"[pipeline error] {e}")
        threading.Thread(target=work, daemon=True).start()

    def _play(self, audio_bytes):
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                path = f.name
            try:
                data, sr = sf.read(path)
            finally:
                os.remove(path)
            if data.size == 0:
                return
            if data.ndim == 1:
                data = np.stack([data, data], axis=1)
            idx = self._tts_index()
            spk = sc.all_speakers()[idx]
            with spk.player(samplerate=sr, channels=2) as sp:
                sp.play(data)
        except Exception as e:
            print(f"[tts error] {e}")

    def _tts_index(self):
        name = self.var_tts.get()
        for i, n in self.devices["speakers"]:
            if n == name:
                return i
        return 0

    # ---------- Control ----------
    def toggle(self):
        self.stop() if self.running else self.start()

    def start(self):
        if not (self.var_groq.get() or "").strip():
            self.status.configure(text="Groq API key diperlukan (BYOK)", fg="#ff6b6b")
            return
        mic_idx = self._index_of(self.devices["mics"], self.var_mic.get())
        loop_idx = self._index_of(self.devices["loopbacks"], self.var_loop.get())
        self._stop.clear()
        self.running = True
        self.btn.configure(text="Stop")
        self.status.configure(text="Running…", fg="#3ddc84")

        mics = sc.all_microphones()
        loops = sc.all_microphones(include_loopback=True)

        def src_runner(s, key, fb):
            try:
                with s.recorder(samplerate=RATE, channels=1, blocksize=2048) as rec:
                    self._capture_loop(rec, key, fb)
            except Exception as e:
                print(f"[{key}] recorder: {e}")

        threads = []
        if mic_idx is not None and mic_idx < len(mics):
            t = threading.Thread(target=src_runner, args=(mics[mic_idx], "mic", MIC_FLUSH_BYTES), daemon=True)
            t.start(); threads.append(t)
        if loop_idx is not None and loop_idx < len(loops):
            t = threading.Thread(target=src_runner, args=(loops[loop_idx], "tab", TAB_FLUSH_BYTES), daemon=True)
            t.start(); threads.append(t)
        for t in threads:
            t.join()  # blocks this thread until stop

    def stop(self):
        self.running = False
        self._stop.set()
        self.btn.configure(text="Start")
        self.status.configure(text="Stopped", fg="#4f8ef7")

    def _index_of(self, items, name):
        for i, n in items:
            if n == name:
                return i
        return None


def main():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    devices = list_devices()
    app = TranslatorApp(root, tk, ttk, devices)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
