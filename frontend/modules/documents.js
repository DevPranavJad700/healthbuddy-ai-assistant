/**
 * HealthBuddy AI — Documents Module
 * RAG Document upload, progress tracking, rich document listing, search, category filtering,
 * interactive document viewer modal, and AI query integration.
 */

import { API, DOC_AVATAR_SVG } from "./config.js";
import { state } from "./state.js";
import { esc, showToast } from "./utils.js";
import { authHeaders } from "./auth.js";

// Module state
let allDocuments = [];
let activeCategory = "all";
let searchQuery = "";
let currentViewedDoc = null;

// Category mapping helper
export function getDocCategory(filename) {
  const fn = (filename || "").toLowerCase();
  if (fn.includes("cardio") || fn.includes("hypertens")) return { id: "cardio", label: "Cardiovascular", color: "var(--accent-teal, #14b8a6)" };
  if (fn.includes("diabet") || fn.includes("endocrin") || fn.includes("thyroid") || fn.includes("nutrit")) return { id: "metabolic", label: "Metabolic & Endocrine", color: "var(--accent-orange, #f59e0b)" };
  if (fn.includes("neuro") || fn.includes("headache") || fn.includes("mental") || fn.includes("sleep")) return { id: "neuro", label: "Neurology & Brain", color: "var(--accent-purple, #8b5cf6)" };
  if (fn.includes("renal") || fn.includes("nephro") || fn.includes("kidney")) return { id: "renal", label: "Renal & Nephrology", color: "var(--accent-cyan, #06b6d4)" };
  if (fn.includes("respirat") || fn.includes("pulmon") || fn.includes("asthma")) return { id: "respiratory", label: "Pulmonology", color: "var(--accent-blue, #3b82f6)" };
  if (fn.includes("prevent") || fn.includes("screen") || fn.includes("diagnost") || fn.includes("geriatric") || fn.includes("pediatric") || fn.includes("women")) return { id: "screenings", label: "Preventive Care", color: "var(--accent-emerald, #10b981)" };
  if (fn.includes("allerg") || fn.includes("anaph") || fn.includes("infect") || fn.includes("protocol") || fn.includes("validat")) return { id: "emergency", label: "Emergency & Safety", color: "var(--accent-red, #ef4444)" };
  if (fn.includes("derm")) return { id: "derm", label: "Dermatology", color: "var(--accent-pink, #ec4899)" };
  if (fn.includes("gastro")) return { id: "gastro", label: "Gastroenterology", color: "var(--accent-amber, #d97706)" };
  if (fn.includes("musculo") || fn.includes("joint")) return { id: "musculo", label: "Musculoskeletal", color: "var(--accent-indigo, #6366f1)" };
  if (fn.includes("hemato") || fn.includes("blood")) return { id: "hemato", label: "Hematology", color: "var(--accent-rose, #f43f5e)" };
  if (fn.includes("ophthal") || fn.includes("eye")) return { id: "ophthal", label: "Ophthalmology", color: "var(--accent-sky, #0ea5e9)" };
  return { id: "general", label: "Clinical Reference", color: "var(--text-muted, #94a3b8)" };
}

// Format raw filename into a human-friendly title
export function formatDocTitle(filename) {
  if (!filename) return "Clinical Document";
  let base = filename.replace(/\.(txt|pdf|md)$/i, "");
  base = base.replace(/_clinical$/i, "");
  return base
    .split(/[_-\s]+/)
    .map((word) => {
      const lower = word.toLowerCase();
      if (lower === "v1" || lower === "v2" || lower === "v3") return word.toUpperCase();
      if (lower === "quickref") return "Quick Reference";
      if (lower === "espanol") return "Español";
      if (lower === "hindi") return "Hindi";
      if (lower === "type2") return "Type 2";
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

export async function uploadFile(file) {
  const allowed = [".pdf", ".txt", ".md"];
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showToast("Use PDF, TXT, or MD files.", "error");
    return;
  }

  const uploadProgress = document.getElementById("uploadProgress");
  const progressFill = document.getElementById("progressFill");
  const progressText = document.getElementById("progressText");
  const fileInput = document.getElementById("fileInput");

  if (uploadProgress) uploadProgress.classList.add("active");
  if (progressFill) progressFill.style.width = "0%";
  if (progressText) progressText.textContent = `Uploading ${file.name}...`;

  let prog = 0;
  const iv = setInterval(() => {
    prog = Math.min(prog + Math.random() * 15, 90);
    if (progressFill) progressFill.style.width = `${prog}%`;
  }, 200);

  try {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(API.uploadDocument, {
      method: "POST",
      headers: authHeaders(),
      body: fd,
    });
    clearInterval(iv);

    if (r.ok) {
      const data = await r.json();
      if (progressFill) progressFill.style.width = "100%";
      if (progressText) {
        progressText.textContent = `✓ Processed ${data.num_chunks} chunks`;
      }
      showToast(`Uploaded ${file.name}`, "success");
      await loadDocuments();
    } else {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.detail || "Upload failed");
    }
  } catch (err) {
    clearInterval(iv);
    if (progressFill) progressFill.style.width = "0%";
    if (progressText) progressText.textContent = `✗ ${err.message}`;
    showToast(err.message, "error");
  } finally {
    if (fileInput) fileInput.value = "";
    setTimeout(() => {
      if (uploadProgress) uploadProgress.classList.remove("active");
    }, 3000);
  }
}

export async function loadDocuments() {
  try {
    const r = await fetch(API.documents, { headers: authHeaders() });
    if (!r.ok) {
      state.docCount = 0;
      updateStatsCounters(0, 0);
      if (typeof window.updateOnboardingChecklist === "function") {
        window.updateOnboardingChecklist();
      }
      return;
    }
    const data = await r.json();
    allDocuments = Array.isArray(data.documents) ? data.documents : [];
    const totalChunks = data.total_chunks || allDocuments.reduce((acc, d) => acc + (d.num_chunks || 0), 0);
    state.docCount = allDocuments.length;
    
    updateStatsCounters(allDocuments.length, totalChunks);

    if (typeof window.updateOnboardingChecklist === "function") {
      window.updateOnboardingChecklist();
    }

    applyFilterAndRender();
  } catch (_) {
    state.docCount = 0;
    updateStatsCounters(0, 0);
    if (typeof window.updateOnboardingChecklist === "function") {
      window.updateOnboardingChecklist();
    }
  }
}

function updateStatsCounters(docCount, chunkCount) {
  const countEl = document.getElementById("docStatsCount");
  const chunksEl = document.getElementById("docStatsChunks");
  if (countEl) countEl.textContent = docCount;
  if (chunksEl) chunksEl.textContent = chunkCount;
}

export function applyFilterAndRender() {
  let filtered = allDocuments;

  if (activeCategory && activeCategory !== "all") {
    filtered = filtered.filter((d) => {
      const cat = getDocCategory(d.filename);
      return cat.id === activeCategory;
    });
  }

  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase().trim();
    filtered = filtered.filter((d) => {
      const title = formatDocTitle(d.filename).toLowerCase();
      const fn = (d.filename || "").toLowerCase();
      const cat = getDocCategory(d.filename).label.toLowerCase();
      return title.includes(q) || fn.includes(q) || cat.includes(q);
    });
  }

  renderDocs(filtered);
}

export function renderDocs(docs) {
  const documentList = document.getElementById("documentList");
  if (!documentList) return;

  if (!docs || docs.length === 0) {
    if (searchQuery || activeCategory !== "all") {
      documentList.innerHTML = `<div class="empty-state-card doc-empty-filtered">
        <p>No documents match your filter</p>
        <button class="empty-action-btn" type="button" onclick="window.resetDocFilters()">Reset Filters</button>
      </div>`;
    } else {
      documentList.innerHTML = `<div class="empty-state-card">
        <p>No documents in knowledge base</p>
        <button class="empty-action-btn" type="button" onclick="document.getElementById('fileInput')?.click()">Upload Document</button>
      </div>`;
    }
    return;
  }

  documentList.innerHTML = docs
    .map((d) => {
      const cat = getDocCategory(d.filename);
      const title = formatDocTitle(d.filename);
      const isSystemDoc = d.filename && !d.filename.startsWith("upload_");

      return `
        <div class="document-item" data-doc-id="${esc(d.doc_id)}" onclick="window.openDocViewer('${esc(d.doc_id)}')">
          <div class="doc-icon" style="background: rgba(99, 102, 241, 0.12); color: ${cat.color};">
            ${DOC_AVATAR_SVG}
          </div>
          <div class="doc-info">
            <div class="doc-title-row">
              <span class="doc-name" title="${esc(title)}">${esc(title)}</span>
              <span class="doc-cat-tag" style="border-color: ${cat.color}40; color: ${cat.color};">${cat.label}</span>
            </div>
            <div class="doc-meta-row">
              <span class="doc-meta">${d.num_chunks} chunks indexed</span>
              <span class="doc-view-hint">Click to read →</span>
            </div>
          </div>
          ${
            !isSystemDoc
              ? `<button class="doc-delete" onclick="event.stopPropagation(); window.deleteDoc('${esc(d.doc_id)}')" title="Delete">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>`
              : ""
          }
        </div>`;
    })
    .join("");
}

export async function openDocViewer(docId) {
  const modal = document.getElementById("docViewerModal");
  const titleEl = document.getElementById("docViewerTitle");
  const catBadgeEl = document.getElementById("docViewerCatBadge");
  const metaEl = document.getElementById("docViewerMeta");
  const bodyEl = document.getElementById("docViewerBody");

  if (!modal || !bodyEl) return;

  const doc = allDocuments.find((d) => d.doc_id === docId) || { doc_id: docId, filename: docId, num_chunks: "?" };
  currentViewedDoc = doc;

  const title = formatDocTitle(doc.filename);
  const cat = getDocCategory(doc.filename);

  if (titleEl) titleEl.textContent = title;
  if (catBadgeEl) {
    catBadgeEl.textContent = cat.label;
    catBadgeEl.style.borderColor = `${cat.color}60`;
    catBadgeEl.style.color = cat.color;
  }
  if (metaEl) metaEl.textContent = `${doc.num_chunks} chunks indexed · Clinical Evidence`;

  bodyEl.innerHTML = `
    <div class="doc-viewer-spinner">
      <div class="spinner-ring"></div>
      <p>Loading clinical content for <strong>${esc(title)}</strong>...</p>
    </div>`;

  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");

  try {
    const r = await fetch(`${API.documents}/${docId}`, { headers: authHeaders() });
    if (!r.ok) {
      throw new Error(`Failed to load document (Status: ${r.status})`);
    }
    const data = await r.json();
    renderDocContent(bodyEl, data.content || "No text content found for this document.");
  } catch (err) {
    bodyEl.innerHTML = `
      <div class="doc-viewer-error">
        <p>⚠️ Unable to fetch document text: ${esc(err.message)}</p>
        <button class="empty-action-btn" type="button" onclick="window.openDocViewer('${esc(docId)}')">Retry</button>
      </div>`;
  }
}

function renderDocContent(container, rawText) {
  if (!rawText || !rawText.trim()) {
    container.innerHTML = `<p class="doc-text-empty">Document contains no readable text content.</p>`;
    return;
  }

  // Parse structured clinical text sections
  const lines = rawText.split("\n");
  let html = `<div class="doc-content-article">`;
  let inList = false;

  for (let line of lines) {
    const trimmed = line.trim();

    if (!trimmed) {
      if (inList) {
        html += `</ul>`;
        inList = false;
      }
      continue;
    }

    // Top-level document banner: === ... ===
    if (trimmed.startsWith("===") && trimmed.endsWith("===")) {
      if (inList) { html += `</ul>`; inList = false; }
      const clean = trimmed.replace(/^=+\s*|\s*=+$/g, "");
      html += `<div class="doc-article-banner"><h2>${esc(clean)}</h2></div>`;
      continue;
    }

    // Major sections: e.g. "1. OVERVIEW...", "2. CHRONIC KIDNEY..."
    if (/^[0-9]+\.\s+[A-Z\s&/()-]+$/.test(trimmed)) {
      if (inList) { html += `</ul>`; inList = false; }
      html += `<h3 class="doc-section-h3">${esc(trimmed)}</h3>`;
      continue;
    }

    // Subsection headings: e.g. "A. Microcytic Anemia", "Deep Vein Thrombosis (DVT):"
    if (/^[A-Z]\.\s+/.test(trimmed) || (trimmed.endsWith(":") && trimmed.length < 80 && !trimmed.includes("http"))) {
      if (inList) { html += `</ul>`; inList = false; }
      html += `<h4 class="doc-section-h4">${esc(trimmed)}</h4>`;
      continue;
    }

    // Red flag / warning callout lines
    if (trimmed.toLowerCase().includes("red flag") || trimmed.toLowerCase().includes("emergency") || trimmed.toLowerCase().includes("critical rule") || trimmed.toLowerCase().includes("immediate action")) {
      if (inList) { html += `</ul>`; inList = false; }
      html += `<div class="doc-callout-warning"><strong>⚠️ Clinical Alert:</strong> ${esc(trimmed)}</div>`;
      continue;
    }

    // Bullets: -, *, •
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("• ")) {
      if (!inList) {
        html += `<ul class="doc-bullet-list">`;
        inList = true;
      }
      const bulletText = trimmed.replace(/^[-*•]\s+/, "");
      html += `<li>${formatInlineText(bulletText)}</li>`;
      continue;
    }

    // Numbered sub-items
    if (/^[0-9]+\.\s+/.test(trimmed)) {
      if (inList) { html += `</ul>`; inList = false; }
      html += `<p class="doc-step-item"><strong>${esc(trimmed.slice(0, 3))}</strong> ${formatInlineText(trimmed.slice(3))}</p>`;
      continue;
    }

    // Standard paragraph
    if (inList) { html += `</ul>`; inList = false; }
    html += `<p class="doc-paragraph">${formatInlineText(trimmed)}</p>`;
  }

  if (inList) {
    html += `</ul>`;
  }

  html += `</div>`;
  container.innerHTML = html;
}

function formatInlineText(text) {
  // Bold formatting: **text**
  let s = esc(text);
  s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*(.*?)\*/g, "<em>$1</em>");
  return s;
}

export function closeDocViewer() {
  const modal = document.getElementById("docViewerModal");
  if (modal) {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }
}

export function askAiAboutDoc() {
  if (!currentViewedDoc) return;
  const title = formatDocTitle(currentViewedDoc.filename);
  closeDocViewer();

  // Switch to Chat Tab
  const chatTabBtn = document.getElementById("chatTabBtn") || document.querySelector('[data-tab="chat-tab"]');
  if (chatTabBtn) chatTabBtn.click();

  // Populate message input
  const msgInput = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendButton");
  if (msgInput) {
    msgInput.value = `Can you summarize the key clinical recommendations, diagnostic criteria, and emergency red flags from the ${title} guide?`;
    msgInput.focus();
    if (sendBtn) sendBtn.disabled = false;
  }
}

export async function deleteDoc(id) {
  try {
    const r = await fetch(`${API.documents}/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!r.ok) throw new Error("Failed to delete document");
    showToast("Document removed", "success");
    await loadDocuments();
  } catch (_) {
    showToast("Failed to delete", "error");
  }
}

export function resetDocFilters() {
  activeCategory = "all";
  searchQuery = "";
  const input = document.getElementById("docSearchInput");
  const clearBtn = document.getElementById("docSearchClearBtn");
  if (input) input.value = "";
  if (clearBtn) clearBtn.classList.add("hidden");

  const pills = document.querySelectorAll("#docCategoryPills .doc-pill");
  pills.forEach((p) => {
    p.classList.toggle("active", p.dataset.cat === "all");
  });

  applyFilterAndRender();
}

// Bind UI listeners once DOM is loaded
export function initDocumentsListeners() {
  // Search input
  const searchInput = document.getElementById("docSearchInput");
  const clearBtn = document.getElementById("docSearchClearBtn");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value;
      if (clearBtn) {
        clearBtn.classList.toggle("hidden", !searchQuery);
      }
      applyFilterAndRender();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      searchQuery = "";
      clearBtn.classList.add("hidden");
      applyFilterAndRender();
      if (searchInput) searchInput.focus();
    });
  }

  // Category Pills
  const categoryPillsContainer = document.getElementById("docCategoryPills");
  if (categoryPillsContainer) {
    categoryPillsContainer.addEventListener("click", (e) => {
      const btn = e.target.closest(".doc-pill");
      if (!btn) return;
      const cat = btn.dataset.cat || "all";
      activeCategory = cat;

      categoryPillsContainer.querySelectorAll(".doc-pill").forEach((p) => {
        p.classList.toggle("active", p === btn);
      });

      applyFilterAndRender();
    });
  }

  // Modal close buttons
  const closeBtn = document.getElementById("closeDocViewerBtn");
  const closeFooterBtn = document.getElementById("docViewerCloseBtn");
  const modal = document.getElementById("docViewerModal");
  const askAiBtn = document.getElementById("docViewerAskAiBtn");

  if (closeBtn) closeBtn.addEventListener("click", closeDocViewer);
  if (closeFooterBtn) closeFooterBtn.addEventListener("click", closeDocViewer);
  if (askAiBtn) askAiBtn.addEventListener("click", askAiAboutDoc);

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeDocViewer();
    });
  }

  // Escape key to dismiss
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
      closeDocViewer();
    }
  });
}

// Expose globals for onclick attributes
window.openDocViewer = openDocViewer;
window.closeDocViewer = closeDocViewer;
window.deleteDoc = deleteDoc;
window.resetDocFilters = resetDocFilters;

// Auto-initialize if DOM already loaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDocumentsListeners);
} else {
  initDocumentsListeners();
}
