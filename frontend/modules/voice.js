/**
 * HealthBuddy AI — Voice Input Module
 * Speech-to-Text integration via Web Speech API.
 */

import { state } from "./state.js";
import { showToast, autoResize } from "./utils.js";

export function initVoiceInput() {
  const micBtn = document.getElementById("micBtn") || document.getElementById("voiceBtn");
  const inputEl = document.getElementById("messageInput") || document.getElementById("chatInput");
  if (!micBtn || !inputEl) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.addEventListener("click", () => {
      showToast("🎙️ Voice input requires Chrome, Edge, or Safari browser.", "warning", 4000);
    });
    return;
  }

  let recognition = null;

  micBtn.addEventListener("click", () => {
    if (state.isRecording) {
      recognition?.stop();
      return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    let finalTranscript = "";

    recognition.onstart = () => {
      state.isRecording = true;
      micBtn.classList.add("recording");
      micBtn.title = "Click to stop recording";
      showToast("🎙️ Listening… speak now", "info", 3000);
    };

    recognition.onresult = (e) => {
      let interim = "";
      finalTranscript = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalTranscript += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      inputEl.value = (finalTranscript || interim).trim();
      autoResize(inputEl);
      const sendButton = document.getElementById("sendButton");
      if (sendButton) sendButton.disabled = !inputEl.value.trim();
    };

    recognition.onerror = (e) => {
      state.isRecording = false;
      micBtn.classList.remove("recording");
      micBtn.title = "Voice input";
      if (e.error === "not-allowed") {
        showToast("🚫 Microphone permission denied. Enable it in browser settings.", "error", 5000);
      } else if (e.error !== "no-speech") {
        showToast(`Voice error: ${e.error}`, "warning", 3000);
      }
    };

    recognition.onend = () => {
      state.isRecording = false;
      micBtn.classList.remove("recording");
      micBtn.title = "Voice input";
      if (finalTranscript.trim()) {
        showToast("✅ Transcribed! Press Enter to send.", "success", 2500);
        inputEl.focus();
      }
    };

    recognition.start();
  });
}
