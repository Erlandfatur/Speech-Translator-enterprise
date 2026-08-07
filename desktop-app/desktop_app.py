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

# ---- Design tokens (WCAG AA compliant, monochrome, editorial) ----
# Contrast vs CARD(#FFF): INK 15.9:1, TEXT 12.6:1, MUTE 7.6:1, FAINT 4.6:1
INK       = "#1A1A1A"   # primary text / solid accent (AA ✓)
TEXT      = "#383838"   # body copy
MUTE      = "#5A5A5A"   # secondary / labels (AA ✓)
FAINT     = "#707070"   # tertiary / helper (AA ✓)
BG        = "#F4F4F2"   # window background (warm off-white)
CARD      = "#FFFFFF"   # cards / inputs
LINE      = "#D8D8D6"   # hairline borders (decorative, not text)
ACTIVE    = "#111111"   # pressed / hover accent
DOT_IDLE  = "#C9C9C9"
DOT_ACTIVE = INK
FOCUS     = "#1A1A1A"
ERROR     = "#8C2F2F"   # error text on white = 7.0:1 (AA ✓), no neon red

FONT_HEAD  = ("Georgia", 17)             # serif wordmark — elegant
FONT_SUB   = ("Segoe UI", 8)             # small caps subtitle
FONT_TITLE = ("Segoe UI", 9, "bold")     # section headers
FONT_BODY  = ("Segoe UI", 10)            # labels / inputs
FONT_CAPS  = ("Segoe UI", 7, "bold")
PAD_X = 28                                # consistent page gutter
PAD_Y = 14                                # vertical rhythm (8pt-ish grid)


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

    def _style(self):
        style = self.ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=CARD, background=CARD,
                        foreground=INK, arrowcolor=MUTE,
                        bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
                        padding=7, font=FONT_BODY)
        style.map("TCombobox",
                  fieldbackground=[("readonly", CARD)],
                  bordercolor=[("focus", FOCUS)],
                  lightcolor=[("focus", FOCUS)], darkcolor=[("focus", FOCUS)])
        self.root.option_add("*TCombobox*TEntry.selectBackground", INK)
        self.root.option_add("*TCombobox*TEntry.selectForeground", CARD)

    def _build_ui(self):
        tk, ttk = self.tk, self.ttk
        self._style()
        self.root.title("Speech Translator")
        self.root.geometry("820x640")
        self.root.configure(bg=BG)
        self.root.minsize(720, 580)

        # ---------------- Masthead ----------------
        mast = tk.Frame(self.root, bg=CARD)
        mast.pack(fill="x")
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")

        inner = tk.Frame(mast, bg=CARD)
        inner.pack(fill="x", padx=PAD_X, pady=16)
        left = tk.Frame(inner, bg=CARD)
        left.pack(side="left")
        tk.Label(left, text="Speech Translator", bg=CARD, fg=INK,
                 font=FONT_HEAD).pack(anchor="w")
        tk.Label(left, text="REAL-TIME SPEECH-TO-SPEECH TRANSLATION", bg=CARD, fg=FAINT,
                 font=FONT_SUB).pack(anchor="w", pady=(2, 0))

        right = tk.Frame(inner, bg=CARD)
        right.pack(side="right")
        self.dot = tk.Label(right, text="●", bg=CARD, fg=DOT_IDLE, font=("Segoe UI", 10))
        self.dot.pack(side="left", padx=(0, 6))
        self.status = tk.Label(right, text="Idle", bg=CARD, fg=MUTE,
                               font=("Segoe UI", 9, "bold"))
        self.status.pack(side="left")

        # ---------------- Body (gutter + sections) ----------------
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=PAD_X, pady=PAD_Y)

        self._section_label(body, "Perangkat Audio")
        dev = tk.Frame(body, bg=CARD, highlightthickness=1,
                       highlightbackground=LINE, highlightcolor=LINE)
        dev.pack(fill="x", pady=(6, 0))
        dev_inner = tk.Frame(dev, bg=CARD, padx=18, pady=6)
        dev_inner.pack(fill="x")

        self.var_mic = tk.StringVar()
        self._field(dev_inner, 0, "Mikrofon (Anda)",
                    self._combo(dev_inner, self.var_mic, [n for _, n in self.devices["mics"]]))
        self.var_loop = tk.StringVar()
        self._field(dev_inner, 1, "System audio (Lawan)",
                    self._combo(dev_inner, self.var_loop, [n for _, n in self.devices["loopbacks"]]))
        self.var_tts = tk.StringVar()
        self._field(dev_inner, 2, "Output terjemahan",
                    self._combo(dev_inner, self.var_tts, [n for _, n in self.devices["speakers"]]))
        dev_inner.columnconfigure(1, weight=1)

        self._section_label(body, "Bahasa", top=14)
        lang = tk.Frame(body, bg=CARD, highlightthickness=1,
                        highlightbackground=LINE, highlightcolor=LINE)
        lang.pack(fill="x", pady=(6, 0))
        lang_inner = tk.Frame(lang, bg=CARD, padx=18, pady=6)
        lang_inner.pack(fill="x")
        self.var_src = tk.StringVar(value="en")
        self._field(lang_inner, 0, "Bahasa asal",
                    self._combo(lang_inner, self.var_src, ["en", "id"]))
        self.var_tgt = tk.StringVar(value="id")
        self._field(lang_inner, 1, "Bahasa target",
                    self._combo(lang_inner, self.var_tgt, ["id", "en"]))
        lang_inner.columnconfigure(1, weight=1)

        self._section_label(body, "Kunci API", top=14)
        keys = tk.Frame(body, bg=CARD, highlightthickness=1,
                        highlightbackground=LINE, highlightcolor=LINE)
        keys.pack(fill="x", pady=(6, 0))
        keys_inner = tk.Frame(keys, bg=CARD, padx=18, pady=6)
        keys_inner.pack(fill="x")
        self.var_groq = tk.StringVar()
        self._field(keys_inner, 0, "Groq (wajib)",
                    self._entry(keys_inner, self.var_groq))
        self.var_gemini = tk.StringVar()
        self._field(keys_inner, 1, "Gemini (opsional)",
                    self._entry(keys_inner, self.var_gemini))
        keys_inner.columnconfigure(1, weight=1)
        tk.Label(keys, text="Kunci hanya disimpan di memori & tidak pernah ditulis ke disk.",
                 bg=CARD, fg=FAINT, font=("Segoe UI", 8), padx=18, pady=(0, 8)).pack(anchor="w")

        # ---------------- Primary action ----------------
        self.btn = tk.Button(body, text="Mulai", command=self.toggle,
                             bg=INK, fg=CARD, activebackground=ACTIVE, activeforeground=CARD,
                             relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                             padx=10, pady=9, cursor="hand2", highlightthickness=0)
        self.btn.pack(fill="x", pady=(14, 0))

        # ---------------- Transcripts ----------------
        subs = tk.Frame(body, bg=BG)
        subs.pack(fill="both", expand=True, pady=(14, 0))
        self.mic_card, self.mic_label = self._sub_card(subs, "Anda", accent=INK)
        self.tab_card, self.tab_label = self._sub_card(subs, "Lawan bicara", accent=INK)

        # Pre-select sensible defaults.
        if self.devices["mics"]:
            self.var_mic.set(self.devices["mics"][0][1])
        if self.devices["loopbacks"]:
            self.var_loop.set(self.devices["loopbacks"][0][1])
        if self.devices["speakers"]:
            self.var_tts.set(self.devices["speakers"][0][1])

    # ---- Layout helpers ----
    def _section_label(self, parent, text, top=0):
        self.tk.Label(parent, text=text.upper(), bg=BG, fg=MUTE,
                      font=FONT_TITLE).pack(anchor="w", pady=(top, 0))

    def _field(self, parent, row, label, widget):
        tk = self.tk
        tk.Label(parent, text=label, width=22, anchor="w", bg=CARD, fg=TEXT,
                 font=FONT_BODY).grid(row=row, column=0, sticky="w", pady=5)
        widget.grid(row=row, column=1, sticky="ew", pady=5)

    def _combo(self, parent, var, items):
        cb = self.ttk.Combobox(parent, textvariable=var, values=items,
                               state="readonly", font=FONT_BODY)
        return cb

    def _entry(self, parent, var):
        e = self.tk.Entry(parent, textvariable=var, show="*",
                          relief="flat", bd=0, highlightthickness=1,
                          highlightbackground=LINE, highlightcolor=FOCUS,
                          bg=CARD, fg=INK, insertbackground=INK, font=FONT_BODY)
        return e

    def _sub_card(self, parent, caption, accent):
        tk = self.tk
        card = tk.Frame(parent, bg=CARD, highlightthickness=1,
                        highlightbackground=LINE, highlightcolor=LINE)
        card.pack(fill="both", expand=True, pady=3)

        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="both", expand=True, padx=18, pady=12)

        head = tk.Frame(inner, bg=CARD)
        head.pack(fill="x")
        bar = tk.Frame(head, bg=accent, width=3)
        bar.pack(side="left", fill="y")
        tk.Label(head, text=caption.upper(), bg=CARD, fg=MUTE,
                 font=FONT_CAPS).pack(side="left", padx=(8, 0))

        body = tk.Label(inner, text="—", anchor="w", justify="left",
                        bg=CARD, fg=TEXT, font=("Segoe UI", 12),
                        wraplength=700, pady=(8, 0))
        body.pack(fill="both", expand=True)
        return card, body

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
            self.status.configure(text="Perlu Groq key", fg=ERROR)
            self.dot.configure(fg=DOT_IDLE)
            return
        mic_idx = self._index_of(self.devices["mics"], self.var_mic.get())
        loop_idx = self._index_of(self.devices["loopbacks"], self.var_loop.get())
        self._stop.clear()
        self.running = True
        self.btn.configure(text="Stop")
        self.status.configure(text="Menerjemahkan", fg=INK)
        self.dot.configure(fg=DOT_ACTIVE)

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
        self.btn.configure(text="Mulai")
        self.status.configure(text="Berhenti", fg=MUTE)
        self.dot.configure(fg=DOT_IDLE)

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
