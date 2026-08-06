document.addEventListener("DOMContentLoaded", () => {
  const captureModeSelect = document.getElementById("capture-mode");
  const spokenLangSelect = document.getElementById("spoken-lang");
  const targetLangSelect = document.getElementById("target-lang");
  const ttsToggle = document.getElementById("tts-toggle");
  const virtualMicToggle = document.getElementById("virtual-mic-toggle");
  const audioOutputSelect = document.getElementById("audio-output-select");
  const groqApiKeyInput = document.getElementById("groq-api-key");
  const geminiApiKeyInput = document.getElementById("gemini-api-key");
  const toggleBtn = document.getElementById("toggle-btn");

  let isTranslating = false;

  // Enumerate audio output devices (Speakers, Headphones, VB-Cable, DELL, etc.)
  async function populateAudioOutputs(selectedDeviceId) {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const outputs = devices.filter(d => d.kind === "audiooutput");
      audioOutputSelect.innerHTML = '<option value="default">Default Speaker System</option>';
      outputs.forEach(d => {
        if (d.deviceId !== "default") {
          const opt = document.createElement("option");
          opt.value = d.deviceId;
          opt.textContent = d.label || `Perangkat Audio Output (${d.deviceId.slice(0, 8)}...)`;
          audioOutputSelect.appendChild(opt);
        }
      });
      if (selectedDeviceId) audioOutputSelect.value = selectedDeviceId;
    } catch (e) {
      console.warn("Could not enumerate audio outputs:", e);
    }
  }

  // Fetch current status and settings from Background Service Worker
  chrome.runtime.sendMessage({ action: "GET_STATUS" }, (response) => {
    if (response) {
      isTranslating = response.isTranslating;
      updateBtnState();

      if (response.userSettings) {
        captureModeSelect.value = response.userSettings.capture_mode || "both";
        spokenLangSelect.value = response.userSettings.spoken_lang || "en";
        targetLangSelect.value = response.userSettings.target_lang || "id";
        ttsToggle.checked = response.userSettings.tts_enabled !== false;
        virtualMicToggle.checked = response.userSettings.virtual_mic_enabled === true;
        groqApiKeyInput.value = response.userSettings.groq_api_key || "";
        geminiApiKeyInput.value = response.userSettings.gemini_api_key || "";
        populateAudioOutputs(response.userSettings.audio_output_device || "default");
      } else {
        populateAudioOutputs("default");
      }
    } else {
      populateAudioOutputs("default");
    }
  });

  // Save changes on input change
  function saveSettings() {
    const settings = {
      capture_mode: captureModeSelect.value,
      spoken_lang: spokenLangSelect.value,
      target_lang: targetLangSelect.value,
      tts_enabled: ttsToggle.checked,
      virtual_mic_enabled: virtualMicToggle.checked,
      audio_output_device: audioOutputSelect.value,
      groq_api_key: groqApiKeyInput.value.trim(),
      gemini_api_key: geminiApiKeyInput.value.trim()
    };

    chrome.runtime.sendMessage({ action: "UPDATE_SETTINGS", settings });
  }

  spokenLangSelect.addEventListener("change", saveSettings);
  targetLangSelect.addEventListener("change", saveSettings);
  ttsToggle.addEventListener("change", saveSettings);
  virtualMicToggle.addEventListener("change", saveSettings);
  audioOutputSelect.addEventListener("change", saveSettings);
  captureModeSelect.addEventListener("change", saveSettings);

  groqApiKeyInput.addEventListener("input", saveSettings);
  geminiApiKeyInput.addEventListener("input", saveSettings);



  // Toggle Start / Stop Translation
  toggleBtn.addEventListener("click", () => {
    saveSettings();

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;
      const activeTab = tabs[0];

      const handleStartResp = (resp) => {
        if (chrome.runtime.lastError || !resp || resp.status === "error") {
          console.error("Translation start failed:", chrome.runtime.lastError || (resp && resp.message));
          alert("Gagal memulai. Pastikan server AI berjalan dan halaman YouTube direfresh.");
          isTranslating = false;
          updateBtnState();
          return;
        }
        if (resp.status === "started" || resp.status === "already_running") {
          isTranslating = true;
          updateBtnState();
        }
      };

      if (!isTranslating) {
        if (captureModeSelect.value === 'tab' || captureModeSelect.value === 'both') {
          // MUST getMediaStreamId inside user click gesture to preserve Chrome permissions
          chrome.tabCapture.getMediaStreamId({ targetTabId: activeTab.id }, (streamId) => {
            let tabStreamId = streamId;
            if (chrome.runtime.lastError) {
              console.warn("tabCapture streamId notice:", chrome.runtime.lastError.message);
              tabStreamId = null;
            }
            chrome.runtime.sendMessage({
              action: "START_TRANSLATION",
              tabId: activeTab.id,
              tabStreamId: tabStreamId
            }, handleStartResp);
          });
        } else {
          chrome.runtime.sendMessage({
            action: "START_TRANSLATION",
            tabId: activeTab.id,
            tabStreamId: null
          }, handleStartResp);
        }
      } else {
        chrome.runtime.sendMessage({ action: "STOP_TRANSLATION" }, () => {
          isTranslating = false;
          updateBtnState();
        });
      }
    });
  });


  function updateBtnState() {
    if (isTranslating) {
      toggleBtn.innerText = "Hentikan Penerjemahan";
      toggleBtn.className = "st-btn st-btn-danger";
    } else {
      toggleBtn.innerText = "Mulai Penerjemahan";
      toggleBtn.className = "st-btn st-btn-primary";
    }
  }
});
