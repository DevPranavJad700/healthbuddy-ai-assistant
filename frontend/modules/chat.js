/**
 * HealthBuddy AI — Chat Module
 * SSE streaming, message rendering, explainability, feedback, and session history.
 */

import {
  API,
  API_BASE,
  USER_AVATAR_SVG,
  BOT_AVATAR_SVG,
  LOCAL_HISTORY_KEY,
  MESSAGE_DRAFT_KEY,
} from "./config.js";

import { state, getAuthToken } from "./state.js";

import {
  esc,
  formatMsg,
  showToast,
  announceForScreenReader,
  sleep,
  parseApiError,
  scrollBottom,
  autoResize,
} from "./utils.js";

import {
  authHeaders,
  attemptTokenRefresh,
  clearAuthToken,
  openConsentCenterWithContext,
  loadConsentCenterState,
} from "./auth.js";

export function readLocalHistory() {
  try {
    const raw = localStorage.getItem(LOCAL_HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

export function writeLocalHistory(sessions) {
  const trimmed = sessions.slice(0, 20).map((session) => ({
    ...session,
    messages: Array.isArray(session.messages)
      ? session.messages.slice(-40)
      : [],
  }));
  localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(trimmed));
}

export function saveLocalConversation(sessionId, userMessage, botData) {
  const now = new Date().toISOString();
  const sessions = readLocalHistory();
  let session = sessions.find((item) => item.session_id === sessionId);

  if (!session) {
    session = {
      session_id: sessionId,
      title: userMessage.slice(0, 40),
      timestamp: now,
      messages: [],
    };
    sessions.unshift(session);
  }

  session.title = session.title || userMessage.slice(0, 40);
  session.timestamp = botData.timestamp || now;
  session.messages.push({ role: "user", content: userMessage, timestamp: now });
  session.messages.push({
    role: "assistant",
    content: botData.response,
    timestamp: botData.timestamp || now,
    sources: botData.sources || [],
    emergency: botData.emergency_alert || null,
    confidence: botData.confidence_note || null,
    prompt_used: botData.prompt_used || null,
    triage_level: botData.triage_level || null,
    triage_rule_id: botData.triage_rule_id || null,
    triage_ruleset_version: botData.triage_ruleset_version || null,
    urgency_explanation:
      botData.urgency_explanation || botData.triage_reason || null,
    next_actions: Array.isArray(botData.next_actions) ? botData.next_actions : [],
    citation_quality: botData.citation_quality || null,
    escalation_action: botData.escalation_action || null,
  });

  writeLocalHistory(sessions);
  state.hasChatHistory = sessions.length > 0;
  if (typeof window.updateOnboardingChecklist === "function") {
    window.updateOnboardingChecklist();
  }
}

export function deleteLocalConversation(sessionId) {
  const sessions = readLocalHistory().filter(
    (session) => session.session_id !== sessionId
  );
  writeLocalHistory(sessions);
  state.hasChatHistory = sessions.length > 0;
  if (typeof window.updateOnboardingChecklist === "function") {
    window.updateOnboardingChecklist();
  }
}

export function showTyping() {
  const messagesList = document.getElementById("messagesList");
  const d = document.createElement("div");
  d.className = "message bot";
  d.innerHTML = `<div class="message-avatar">${BOT_AVATAR_SVG}</div><div class="message-content"><div class="message-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div></div>`;
  if (messagesList) messagesList.appendChild(d);
  scrollBottom(document.getElementById("messagesContainer"));
  announceForScreenReader("Assistant is generating a response.");
  return d;
}

function normalizeTriageLevel(value) {
  const raw = String(value || "self_care").toLowerCase();
  if (raw === "self-care") return "self_care";
  if (raw.includes("urgent")) return "urgent";
  if (raw.includes("emergency")) return "emergency";
  return "self_care";
}

function renderSourceTransparencyPanel(sources = [], citationQuality = null) {
  if (!Array.isArray(sources) || sources.length === 0) return "";
  const panelId = `source-panel-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  const quality = citationQuality
    ? `<span class="source-quality-tag">${esc(citationQuality)}</span>`
    : "";

  const cards = sources
    .slice(0, 5)
    .map((s) => {
      const guidelineBits = [s.guideline_ref, s.source_version]
        .filter(Boolean)
        .join(" • ");
      const confidence = Number.isFinite(Number(s.relevance))
        ? `${Math.round(Number(s.relevance) * 100)}%`
        : Number.isFinite(Number(s.score))
        ? `${Math.round(Number(s.score) * 100)}%`
        : "n/a";
      return `<div class="source-transparency-item">
        <div class="source-transparency-head">
          <strong>${esc(s.source || "Knowledge Source")}</strong>
          <span class="source-confidence">Confidence: ${esc(confidence)}</span>
        </div>
        ${guidelineBits ? `<div class="source-guideline">${esc(guidelineBits)}</div>` : ""}
        <div class="source-preview">${esc(s.content || "No excerpt returned")}</div>
      </div>`;
    })
    .join("");

  return `<details class="source-transparency-panel" id="${panelId}">
    <summary>Source transparency ${quality}</summary>
    ${cards}
    <p class="source-coverage-note">What this does not cover: this answer may not include your complete history, labs, or a physical exam. Seek clinician review for diagnosis-critical decisions.</p>
  </details>`;
}

function renderTrustCard(trustData = {}, sessionId = null) {
  const triageLevel = normalizeTriageLevel(trustData.triage_level);
  const triageLabel = triageLevel.replace("_", " ");
  const explanation =
    trustData.urgency_explanation ||
    "This urgency level is based on symptom risk cues, known safety policies, and available clinical guidance.";
  const actions = Array.isArray(trustData.next_actions)
    ? trustData.next_actions
    : [];
  const actionList = actions.length
    ? `<ul class="trust-next-actions">${actions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>`
    : '<p class="trust-next-actions-empty">No structured next actions were returned.</p>';

  const immediateCare =
    triageLevel === "emergency"
      ? "Seek immediate emergency care now if severe chest pain, breathing distress, confusion, fainting, seizure, or uncontrolled bleeding is present."
      : triageLevel === "urgent"
      ? "Seek same-day care if symptoms worsen quickly, new red flags appear, or hydration/fever control fails."
      : "Escalate to urgent care if symptoms persist, intensify, or new red flags develop.";

  const handoffBtn =
    sessionId && (triageLevel === "emergency" || trustData.escalation_action)
      ? `<button class="fallback-action-btn" type="button" data-fallback-action="request-review">Request clinician handoff</button>`
      : "";

  return `<section class="trust-card trust-${esc(triageLevel)}">
    <div class="trust-card-head">
      <span class="trust-level-pill">Triage: ${esc(triageLabel)}</span>
      ${trustData.triage_ruleset_version ? `<span class="trust-rule-tag">Ruleset ${esc(trustData.triage_ruleset_version)}</span>` : ""}
    </div>
    <p class="trust-urgency-text">${esc(explanation)}</p>
    ${actionList}
    <p class="trust-threshold"><strong>When to seek immediate care:</strong> ${esc(immediateCare)}</p>
    ${handoffBtn}
  </section>`;
}

export function wireFeedbackBox(feedbackBox) {
  if (!feedbackBox) return;
  feedbackBox.addEventListener("click", async (event) => {
    const btn = event.target.closest("button");
    if (!btn) return;

    const sessionId = feedbackBox.dataset.sessionId;
    if (!sessionId) return;

    if (btn.dataset.review === "true") {
      const session = readLocalHistory().find((s) => s.session_id === sessionId);
      const lastUserQuestion =
        session?.messages
          ?.slice()
          .reverse()
          .find((m) => m.role === "user")?.content || "Question not available";

      const optionalNote = window.prompt(
        "Optional note for clinician handoff (medications, timeline, or major concern):",
        ""
      );

      try {
        const response = decodeURIComponent(feedbackBox.dataset.response || "");
        const composedQuestion = optionalNote
          ? `${lastUserQuestion}\n\n[Escalation note]\n${optionalNote}`
          : lastUserQuestion;
        const r = await fetch(API.clinicianReviewRequest, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            session_id: sessionId,
            question: composedQuestion,
            response,
          }),
        });
        if (!r.ok) throw new Error("Could not request review");
        const data = await r.json().catch(() => ({}));
        showToast("Clinician review requested", "success");
        btn.disabled = true;
      } catch (err) {
        showToast(err.message || "Review request failed", "error");
      }
      return;
    }

    const helpful = btn.dataset.helpful === "true";
    try {
      const r = await fetch(API.chatFeedback, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          session_id: sessionId,
          helpful,
          rating: helpful ? 5 : 2,
          resolved: helpful,
        }),
      });
      if (!r.ok) throw new Error("Feedback failed");
      feedbackBox.querySelectorAll("button").forEach((b) => (b.disabled = true));
      showToast("Feedback submitted", "success");
    } catch (err) {
      showToast(err.message || "Feedback failed", "error");
    }
  });
}

function ensureFeedbackControlsAfterStream(sessionId, responseText) {
  const sid = sessionId || state.currentSessionId || "default_session";
  const messagesList = document.getElementById("messagesList");
  if (!messagesList) return false;
  const lastBotMsg = messagesList.querySelector(".message.bot:last-child .message-content");
  if (!lastBotMsg) return false;

  let feedbackBox = lastBotMsg.querySelector(".feedback-box");
  if (feedbackBox) return true;

  const encodedResponse = encodeURIComponent(String(responseText || "").slice(0, 1200));
  const wrapper = document.createElement("div");
  wrapper.className = "stream-feedback-fallback";
  wrapper.innerHTML = `<div class="feedback-box" data-session-id="${esc(sid)}" data-response="${encodedResponse}">
      <span class="feedback-label">Was this helpful?</span>
      <button class="feedback-btn" type="button" data-helpful="true">👍</button>
      <button class="feedback-btn" type="button" data-helpful="false">👎</button>
      <button class="feedback-btn" type="button" data-review="true">Review</button>
    </div>`;
  lastBotMsg.appendChild(wrapper);
  feedbackBox = wrapper.querySelector(".feedback-box");
  wireFeedbackBox(feedbackBox);
  return Boolean(feedbackBox);
}

export async function appendMessage(
  role,
  content,
  sources = [],
  emergency = null,
  confidence = null,
  prompt_used = null,
  stream = true,
  parseMarkdown = true,
  trustData = null,
  fallbackState = null
) {
  const messagesList = document.getElementById("messagesList");
  const messagesContainer = document.getElementById("messagesContainer");
  if (!messagesList) return;

  const div = document.createElement("div");
  div.className = `message ${role}`;
  const time = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  const avatar = role === "user" ? USER_AVATAR_SVG : BOT_AVATAR_SVG;
  const previewContent = content;

  let extra = "";
  if (emergency) {
    extra += `<div class="emergency-alert">${formatMsg(emergency)}</div>`;
  }

  // Explainability Box
  if (role === "bot") {
    const explainId = "explain-" + Date.now() + Math.floor(Math.random() * 1000);
    let explainHtml = `<div class="explain-box">
            <button class="explain-toggle" onclick="document.getElementById('${explainId}').classList.toggle('hidden')">
                🧠 Why this answer?
            </button>
            <div id="${explainId}" class="explain-content hidden">`;

    let contentHtml = "";
    if (sources && sources.length > 0) {
      contentHtml += `<div class="explain-section-title">Retrieved Chunks</div>`;
      contentHtml += sources
        .map(
          (s) =>
            `<div class="source-card"><span class="source-name">${esc(s.source)}</span>${s.page !== null ? ` <span class="source-page">Page ${s.page + 1}</span>` : ""}<span class="source-preview">${esc(s.content)}</span></div>`
        )
        .join("");
    }
    if (prompt_used) {
      contentHtml += `<div class="explain-section-title">Prompt Used</div>
                      <pre class="prompt-preview">${esc(prompt_used)}</pre>`;
    }
    if (!contentHtml) {
      contentHtml = `<p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0; padding-top: 5px;">No explainability parameters returned by the backend logic.</p>`;
    }
    explainHtml += contentHtml + `</div></div>`;
    extra += explainHtml;
  }

  if (role === "bot" && trustData) {
    extra += renderTrustCard(trustData, state.currentSessionId || null);
  }

  if (role === "bot" && Array.isArray(sources) && sources.length > 0) {
    extra += renderSourceTransparencyPanel(
      sources,
      trustData?.citation_quality || null
    );
  }

  if (confidence && role === "bot") {
    extra += `<div class="confidence-note">ℹ️ ${esc(confidence)}</div>`;
  }

  if (role === "bot" && state.currentSessionId) {
    const encodedResponse = encodeURIComponent(content.slice(0, 1200));
    extra += `<div class="feedback-box" data-session-id="${esc(state.currentSessionId)}" data-response="${encodedResponse}">
      <span class="feedback-label">Was this helpful?</span>
      <button class="feedback-btn" type="button" data-helpful="true">👍</button>
      <button class="feedback-btn" type="button" data-helpful="false">👎</button>
      <button class="feedback-btn" type="button" data-review="true">Review</button>
    </div>`;
  }

  div.innerHTML = `<div class="message-avatar">${avatar}</div><div class="message-content"><div class="message-bubble"></div>${extra}<div class="message-time">${time}</div></div>`;
  messagesList.appendChild(div);

  const feedbackBox = div.querySelector(".feedback-box");
  if (feedbackBox) {
    wireFeedbackBox(feedbackBox);
  }

  // Copy button
  if (role === "bot") {
    const bubble = div.querySelector(".message-bubble");
    if (bubble) {
      const copyBtn = document.createElement("button");
      copyBtn.className = "msg-copy-btn";
      copyBtn.setAttribute("type", "button");
      copyBtn.setAttribute("aria-label", "Copy response");
      copyBtn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`;
      copyBtn.addEventListener("click", () => {
        const text = bubble.innerText || bubble.textContent || "";
        navigator.clipboard.writeText(text.replace("Copy", "").trim()).then(() => {
          copyBtn.textContent = "✓ Copied!";
          copyBtn.classList.add("copied");
          setTimeout(() => {
            copyBtn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`;
            copyBtn.classList.remove("copied");
          }, 2000);
        }).catch(() => {});
      });
      bubble.appendChild(copyBtn);
    }
  }

  scrollBottom(messagesContainer);

  const bubble = div.querySelector(".message-bubble");
  if (role === "bot" && stream) {
    const words = content.split(" ");
    let currentText = "";
    for (let i = 0; i < words.length; i++) {
      currentText += words[i] + " ";
      bubble.innerHTML = parseMarkdown ? formatMsg(currentText) : currentText;
      scrollBottom(messagesContainer);
      await sleep(35);
    }
  } else {
    bubble.innerHTML = parseMarkdown ? formatMsg(previewContent) : previewContent;
  }

  const announcementText =
    role === "user"
      ? `You said: ${String(previewContent || "").slice(0, 120)}`
      : `Assistant response received: ${String(previewContent || "").slice(0, 160)}`;
  announceForScreenReader(announcementText);
}

export async function sendMessage(msgOverride = null) {
  const messageInput = document.getElementById("messageInput");
  const sendButton = document.getElementById("sendButton");
  const welcomeScreen = document.getElementById("welcomeScreen");
  const messagesList = document.getElementById("messagesList");
  const messagesContainer = document.getElementById("messagesContainer");

  const msg = (msgOverride !== null ? msgOverride : messageInput?.value || "").trim();
  if (!msg || state.isLoading) return;

  let sendAsGuest = false;

  if (welcomeScreen) welcomeScreen.classList.add("hidden");
  appendMessage("user", msg);
  if (messageInput) {
    messageInput.value = "";
    messageInput.disabled = true;
    localStorage.removeItem(MESSAGE_DRAFT_KEY);
    autoResize(messageInput);
  }
  if (sendButton) sendButton.disabled = true;

  const typing = showTyping();
  state.isLoading = true;

  try {
    const payload = {
      message: msg,
      use_rag: true,
      temperature: 0.7,
      preferred_language: state.uiLanguage || "en",
    };
    if (state.currentSessionId) {
      payload.session_id = state.currentSessionId;
    }

    let r = await fetch(API.chatStream, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(sendAsGuest ? {} : authHeaders()),
      },
      body: JSON.stringify(payload),
    });

    if (!r.ok && r.status === 403 && !sendAsGuest) {
      sendAsGuest = true;
      r = await fetch(API.chatStream, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }

    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      const enrichedError = new Error(parseApiError(err, `Server error: ${r.status}`));
      enrichedError.httpStatus = r.status;
      throw enrichedError;
    }

    typing.remove();

    // Create streaming placeholder
    const botMsgDiv = document.createElement("div");
    botMsgDiv.className = "message bot";
    const time = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    botMsgDiv.innerHTML = `<div class="message-content">
      <div class="avatar-container">${BOT_AVATAR_SVG}</div>
      <div class="message-body">
        <div class="message-header"><span class="message-role">HealthBuddy</span><span class="message-time">${time}</span></div>
        <div class="message-text streaming"></div>
      </div>
    </div>`;
    messagesList.appendChild(botMsgDiv);
    scrollBottom(messagesContainer);
    const textContainer = botMsgDiv.querySelector(".message-text");

    const reader = r.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let done = false;
    let fullText = "";
    let finalData = {};
    let emergencyAlert = null;
    let sources = [];
    let sseBuffer = "";
    let streamComplete = false;

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        sseBuffer += decoder.decode(value, { stream: true });
        const blocks = sseBuffer.split("\n\n");
        sseBuffer = blocks.pop() || "";

        for (const block of blocks) {
          if (!block.trim()) continue;
          let eventName = "message";
          const dataLines = [];
          const lines = block.split("\n");

          for (const rawLine of lines) {
            const line = rawLine.trimEnd();
            if (!line) continue;
            if (line.startsWith("event:")) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice(5).trimStart());
            }
          }

          const dataStr = dataLines.join("\n");
          if (eventName === "token") {
            try {
              const token = JSON.parse(dataStr);
              fullText += token;
              textContainer.innerHTML = formatMsg(fullText);
              scrollBottom(messagesContainer);
            } catch (_) {}
          } else if (eventName === "emergency") {
            emergencyAlert = dataStr;
          } else if (eventName === "sources") {
            try {
              sources = JSON.parse(dataStr);
            } catch (_) {}
          } else if (eventName === "done") {
            streamComplete = true;
            try {
              finalData = JSON.parse(dataStr);
            } catch (_) {}
          } else if (eventName === "error") {
            showToast(dataStr || "Streaming error", "error");
          }
        }
      }
    }

    textContainer.classList.remove("streaming");

    const data = {
      session_id: finalData.session_id || null,
      response: finalData.full_response || fullText,
      sources: sources,
      emergency_alert: emergencyAlert,
      confidence_note: null,
      prompt_used: null,
      triage_level: finalData.triage_level || "self_care",
      triage_rule_id: finalData.triage_rule_id,
      triage_ruleset_version: finalData.triage_ruleset_version,
      urgency_explanation: finalData.triage_reason,
      next_actions: [],
      citation_quality: "medium",
      escalation_action: finalData.escalation_action,
    };

    if (!state.currentSessionId && data.session_id) {
      state.currentSessionId = data.session_id;
    }

    saveLocalConversation(
      state.currentSessionId || data.session_id || "default",
      msg,
      data
    );
    loadSessions();

    // Morph streaming div into formatted message
    botMsgDiv.style.transition = "opacity 0.15s ease";
    botMsgDiv.style.opacity = "0";
    await sleep(150);

    const tempContainer = document.createElement("div");
    tempContainer.style.display = "none";
    document.body.appendChild(tempContainer);

    const savedList = messagesList;
    // Format message into temp
    const oldAppend = messagesList;
    tempContainer.innerHTML = "";
    
    // Transplant formatted message
    await appendMessage(
      "bot",
      data.response,
      data.sources,
      data.emergency_alert,
      data.confidence_note,
      data.prompt_used,
      false,
      true,
      {
        triage_level: data.triage_level,
        triage_rule_id: data.triage_rule_id,
        triage_ruleset_version: data.triage_ruleset_version,
        urgency_explanation: data.urgency_explanation,
        next_actions: data.next_actions,
        citation_quality: data.citation_quality,
        escalation_action: data.escalation_action,
      }
    );

    // The appended message is in messagesList; remove botMsgDiv
    botMsgDiv.remove();
    tempContainer.remove();

    ensureFeedbackControlsAfterStream(
      state.currentSessionId || data.session_id,
      data.response
    );

    window.dispatchEvent(
      new CustomEvent("healthbuddy:chat-stream-complete", {
        detail: {
          sessionId: state.currentSessionId || data.session_id,
          response: data.response,
        },
      })
    );
  } catch (err) {
    typing.remove();
    showToast(err.message || "Message failed", "error");
  } finally {
    state.isLoading = false;
    if (messageInput) {
      messageInput.disabled = false;
      messageInput.focus();
    }
  }
}

export async function clearChat() {
  if (state.currentSessionId) {
    try {
      await fetch(`${API_BASE}/chat/sessions/${state.currentSessionId}`, {
        method: "DELETE",
      });
    } catch (_) {}
    deleteLocalConversation(state.currentSessionId);
  }
  startNewChat();
  loadSessions();
}

export function startNewChat() {
  state.currentSessionId = null;
  const messagesList = document.getElementById("messagesList");
  const welcomeScreen = document.getElementById("welcomeScreen");
  if (messagesList) messagesList.innerHTML = "";
  if (welcomeScreen) welcomeScreen.classList.remove("hidden");
}

export async function loadSessions() {
  const sessionList = document.getElementById("sessionList");
  if (!sessionList) return;
  const sessions = readLocalHistory();
  state.hasChatHistory = sessions.length > 0;

  if (!sessions || sessions.length === 0) {
    sessionList.innerHTML = '<div class="empty-state-card"><p>No conversation history yet</p></div>';
    return;
  }

  sessionList.innerHTML = sessions
    .map(
      (s) => `
        <div class="document-item history-item" style="cursor:pointer" onclick="window.loadSession('${s.session_id}')">
            <div class="doc-icon">${USER_AVATAR_SVG}</div>
            <div class="doc-info">
                <div class="doc-name" title="${esc(s.title)}">${esc(s.title)}</div>
                <div class="doc-meta" style="font-size: 0.65rem;">${new Date(s.timestamp).toLocaleDateString()}</div>
            </div>
            <button class="export-history-btn" title="Download conversation" onclick="window.exportSession(event, '${s.session_id}')">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>
            <button class="delete-history-btn" title="Delete conversation" onclick="window.deleteHistorySession(event, '${s.session_id}')">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        </div>`
    )
    .join("");
}

export async function loadSession(sessionId) {
  state.currentSessionId = sessionId;
  const welcomeScreen = document.getElementById("welcomeScreen");
  const messagesList = document.getElementById("messagesList");
  if (welcomeScreen) welcomeScreen.classList.add("hidden");
  if (messagesList) messagesList.innerHTML = "";

  try {
    const sessions = readLocalHistory();
    const session = sessions.find((item) => item.session_id === sessionId);
    if (!session) throw new Error("Session not found in local history");

    for (const msg of session.messages) {
      const role = msg.role === "assistant" ? "bot" : "user";
      await appendMessage(
        role,
        msg.content,
        msg.sources || [],
        msg.emergency || null,
        msg.confidence || null,
        msg.prompt_used || null,
        false,
        true,
        {
          triage_level: msg.triage_level || null,
          triage_rule_id: msg.triage_rule_id || null,
          triage_ruleset_version: msg.triage_ruleset_version || null,
          urgency_explanation: msg.urgency_explanation || null,
          next_actions: Array.isArray(msg.next_actions) ? msg.next_actions : [],
          citation_quality: msg.citation_quality || null,
          escalation_action: msg.escalation_action || null,
        }
      );
    }
  } catch (err) {
    showToast(err.message, "error");
    startNewChat();
  }
}

export async function deleteHistorySession(event, sessionId) {
  event?.stopPropagation();
  if (!confirm("Delete this conversation from history?")) return;

  if (state.currentSessionId === sessionId) {
    startNewChat();
  }

  try {
    await fetch(`${API_BASE}/chat/sessions/${sessionId}`, { method: "DELETE" });
  } catch (_) {}

  deleteLocalConversation(sessionId);
  loadSessions();
  showToast("Conversation deleted", "success");
}

export function exportSession(event, sessionId) {
  event?.stopPropagation();
  try {
    const sessions = readLocalHistory();
    const session = sessions.find((s) => s.session_id === sessionId);
    if (!session || !session.messages || session.messages.length === 0) {
      showToast("No messages to export.", "error");
      return;
    }

    const lines = [
      "=".repeat(60),
      `HealthBuddy AI — Chat Export`,
      `Session: ${sessionId}`,
      `Date: ${new Date(session.timestamp).toLocaleString()}`,
      "=".repeat(60),
      "",
    ];

    for (const msg of session.messages) {
      const role = msg.role === "assistant" ? "HealthBuddy" : "You";
      const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : "";
      lines.push(`[${role}]${time ? " " + time : ""}`);
      lines.push(msg.content || "");
      lines.push("");
    }

    lines.push("-".repeat(60));
    lines.push("Disclaimer: This export is for informational purposes only.");
    lines.push("Always consult a qualified healthcare professional.");
    lines.push("-".repeat(60));

    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `healthbuddy-chat-${sessionId}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Chat exported successfully!", "success");
  } catch (err) {
    showToast("Failed to export chat.", "error");
  }
}

export async function loadChatHistory() {
  const sessionList = document.getElementById("sessionList");
  const gate = document.getElementById("historySignInGate");
  const emptyEl = document.getElementById("historyEmpty");
  const loadingEl = document.getElementById("historyLoading");
  if (!sessionList) return;

  const token = getAuthToken();
  if (!token) {
    if (gate) gate.classList.remove("hidden");
    if (loadingEl) loadingEl.classList.add("hidden");
    return;
  }
  if (gate) gate.classList.add("hidden");
  if (emptyEl) emptyEl.classList.add("hidden");
  if (loadingEl) loadingEl.classList.remove("hidden");

  try {
    const r = await fetch(API.chatSessions, { headers: authHeaders() });
    if (r.status === 401 && (await attemptTokenRefresh())) return loadChatHistory();
    if (!r.ok) throw new Error("Could not load history");
    const data = await r.json();
    const sessions = Array.isArray(data.sessions) ? data.sessions : [];

    if (loadingEl) loadingEl.classList.add("hidden");

    if (!sessions.length) {
      if (emptyEl) emptyEl.classList.remove("hidden");
      return;
    }

    sessionList.innerHTML = sessions
      .map((s) => {
        const icon = s.emergency_detected ? "🚨" : "💬";
        const cls = s.emergency_detected ? "session-card emergency" : "session-card";
        return `<div class="${cls}" data-session="${esc(s.session_id)}" onclick="window.loadSession('${s.session_id}')">
          <div class="session-card-icon">${icon}</div>
          <div class="session-card-body">
            <div class="session-card-preview">${esc(s.preview)}</div>
            <div class="session-card-meta">
              <span>${s.last_active ? new Date(s.last_active).toLocaleDateString() : ""}</span>
              <span class="session-card-badge">${s.message_count} msg${s.message_count !== 1 ? "s" : ""}</span>
            </div>
          </div>
        </div>`;
      })
      .join("");
  } catch (err) {
    if (loadingEl) loadingEl.classList.add("hidden");
    sessionList.innerHTML = `<p style="font-size:0.72rem;color:var(--danger);padding:8px">Could not load history. Try again later.</p>`;
  }
}
