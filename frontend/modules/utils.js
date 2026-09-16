/**
 * HealthBuddy AI — Utilities Module
 * String formatting, escaping, toast notifications, modal accessibility helpers.
 */

import { state } from "./state.js";

/** Sleep for given milliseconds */
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Escape HTML characters */
export function esc(t) {
  if (t === null || t === undefined) return "";
  const d = document.createElement("div");
  d.textContent = String(t);
  return d.innerHTML;
}

/** Rich clinical markdown formatting for messages */
export function formatMsg(t) {
  if (!t) return "";

  // 1. Escape raw HTML entities
  let s = String(t)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 2. Fenced code blocks
  s = s.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (_m, _lang, code) => {
    return `<pre class="chat-code-block"><code>${code.trim()}</code></pre>`;
  });

  // 3. Inline code
  s = s.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');

  // 4. Bold text
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // 5. Italic text (careful not to match standalone bullet asterisks)
  s = s.replace(/(^|[^\*])\*([^\*\s][^*]*?[^\*\s]|[^\*\s])\*(?!\*)/g, "$1<em>$2</em>");

  // 6. Clinical metric highlights (e.g. 180/120 mmHg, 100.4°F, 72 bpm)
  s = s.replace(/\b(\d{2,3}\/\d{2,3}\s*(?:mmHg|mm\s*Hg)?)\b/gi, '<span class="clinical-metric-pill">$1</span>');
  s = s.replace(/\b(\d{2,3}(?:\.\d)?\s*°\s*[FC])\b/g, '<span class="clinical-metric-pill">$1</span>');
  s = s.replace(/\b(\d{2,3}\s*(?:bpm|BPM))\b/g, '<span class="clinical-metric-pill">$1</span>');

  // 7. Clinical urgency terms
  s = s.replace(/\b(hypertensive emergency|seek immediate emergency care|call 911|emergency room|immediate medical attention)\b/gi, '<span class="clinical-urgency-badge">$1</span>');

  // 8. Line-by-line block structure (headings, lists, callouts, paragraphs)
  const lines = s.split("\n");
  const out = [];
  let inUl = false;
  let inOl = false;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i].trim();
    if (!raw) {
      if (inUl) { out.push("</ul>"); inUl = false; }
      if (inOl) { out.push("</ol>"); inOl = false; }
      continue;
    }

    // Bullet list item (*, -, •)
    const ulMatch = raw.match(/^[\*\-\•]\s+(.*)/);
    if (ulMatch) {
      if (!inUl) {
        if (inOl) { out.push("</ol>"); inOl = false; }
        out.push('<ul class="chat-bullet-list">');
        inUl = true;
      }
      out.push(`<li>${ulMatch[1]}</li>`);
      continue;
    }

    // Numbered list item (1., 2.)
    const olMatch = raw.match(/^\d+\.\s+(.*)/);
    if (olMatch) {
      if (!inOl) {
        if (inUl) { out.push("</ul>"); inUl = false; }
        out.push('<ol class="chat-numbered-list">');
        inOl = true;
      }
      out.push(`<li>${olMatch[1]}</li>`);
      continue;
    }

    // Close any open list
    if (inUl) { out.push("</ul>"); inUl = false; }
    if (inOl) { out.push("</ol>"); inOl = false; }

    // Headings
    if (raw.startsWith("### ")) {
      out.push(`<h4 class="chat-h4">${raw.slice(4)}</h4>`);
    } else if (raw.startsWith("## ")) {
      out.push(`<h3 class="chat-h3">${raw.slice(3)}</h3>`);
    } else if (raw.startsWith("# ")) {
      out.push(`<h2 class="chat-h2">${raw.slice(2)}</h2>`);
    } else if (raw.startsWith("&gt; ") || raw.startsWith("<strong>Warning:</strong>") || raw.startsWith("<strong>Emergency:</strong>") || raw.startsWith("<strong>Red Flag")) {
      const isDanger = raw.toLowerCase().includes("emergency") || raw.toLowerCase().includes("red flag");
      const calloutClass = isDanger ? "danger" : "warning";
      const icon = isDanger ? "🚨" : "⚠️";
      const cleanText = raw.replace(/^&gt;\s*/, "");
      out.push(`<div class="clinical-callout ${calloutClass}"><span class="callout-icon">${icon}</span><div class="callout-text">${cleanText}</div></div>`);
    } else {
      out.push(`<p class="chat-p">${raw}</p>`);
    }
  }

  if (inUl) out.push("</ul>");
  if (inOl) out.push("</ol>");

  return out.join("");
}

/** Announce message to screen reader live region */
export function announceForScreenReader(message, assertive = false) {
  const liveRegion = document.getElementById("screenReaderLiveRegion");
  if (!liveRegion) return;
  liveRegion.setAttribute("aria-live", assertive ? "assertive" : "polite");
  liveRegion.textContent = "";
  window.requestAnimationFrame(() => {
    liveRegion.textContent = String(message || "");
  });
}

/** Display a toast notification popup */
export function showToast(msg, type = "error", duration = 4000) {
  let t = document.querySelector(".toast");
  if (!t) {
    t = document.createElement("div");
    t.className = "toast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.className = `toast ${type}`;
  announceForScreenReader(msg, type === "error");
  requestAnimationFrame(() => t.classList.add("show"));
  setTimeout(() => t.classList.remove("show"), duration);
}

/** Format relative timestamp (e.g. "just now", "5m ago") */
export function relativeTime(date) {
  if (!(date instanceof Date) || isNaN(date.getTime())) return "";
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 10) return "just now";
  if (diff < 60) return `${diff}s ago`;
  const mins = Math.floor(diff / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return date.toLocaleDateString();
}

/** Parse API error responses */
export function parseApiError(data, fallback = "An error occurred") {
  return data?.error?.message || data?.detail || fallback;
}

/** Parse comma-separated list into trimmed string array */
export function parseCommaSeparatedItems(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

/** Copy text to clipboard with fallback */
export async function copyTextToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {
    // fallback below
  }
  try {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const successful = document.execCommand("copy");
    document.body.removeChild(textArea);
    return successful;
  } catch (_) {
    return false;
  }
}

/** Trap focus within modal while open (Accessibility WCAG) */
export function trapModalTabKey(event, modalEl) {
  if (event.key !== "Tab" || !modalEl) return;
  const focusable = modalEl.querySelectorAll(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  if (!focusable.length) return;

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;

  if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
    return;
  }
  if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

/** Open or close modal with focus restoration */
export function setModalOpenWithFocus(modalEl, isOpen) {
  if (!modalEl) return;
  if (isOpen) {
    state.modalFocusReturnEl = document.activeElement;
    modalEl.classList.remove("hidden");
    modalEl.setAttribute("aria-hidden", "false");
    const firstFocusable = modalEl.querySelector(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (firstFocusable) firstFocusable.focus();
  } else {
    modalEl.classList.add("hidden");
    modalEl.setAttribute("aria-hidden", "true");
    if (state.modalFocusReturnEl && typeof state.modalFocusReturnEl.focus === "function") {
      state.modalFocusReturnEl.focus();
      state.modalFocusReturnEl = null;
    }
  }
}

/** Auto-resize textarea according to its content height */
export function autoResize(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px";
}

/** Scroll chat messages container to bottom */
export function scrollBottom(container) {
  if (!container) return;
  container.scrollTo({
    top: container.scrollHeight,
    behavior: "smooth",
  });
}
