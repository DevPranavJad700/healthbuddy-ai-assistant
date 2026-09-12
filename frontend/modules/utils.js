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

/** Basic markdown formatting for messages */
export function formatMsg(t) {
  if (!t) return "";
  return t
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
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
