/**
 * HealthBuddy AI — Documents Module
 * RAG Document upload, progress tracking, document listing, and deletion.
 */

import { API, DOC_AVATAR_SVG } from "./config.js";
import { state } from "./state.js";
import { esc, showToast } from "./utils.js";
import { authHeaders } from "./auth.js";

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
      if (typeof window.updateOnboardingChecklist === "function") {
        window.updateOnboardingChecklist();
      }
      return;
    }
    const data = await r.json();
    renderDocs(data.documents);
  } catch (_) {
    state.docCount = 0;
    if (typeof window.updateOnboardingChecklist === "function") {
      window.updateOnboardingChecklist();
    }
  }
}

export function renderDocs(docs) {
  const documentList = document.getElementById("documentList");
  if (!documentList) return;

  state.docCount = Array.isArray(docs) ? docs.length : 0;
  if (typeof window.updateOnboardingChecklist === "function") {
    window.updateOnboardingChecklist();
  }

  if (!docs || docs.length === 0) {
    documentList.innerHTML = `<div class="empty-state-card">
      <p>No documents uploaded</p>
      <button class="empty-action-btn" type="button" onclick="document.getElementById('fileInput')?.click()">Upload document</button>
    </div>`;
    return;
  }

  documentList.innerHTML = docs
    .map(
      (d) => `
        <div class="document-item">
          <div class="doc-icon">${DOC_AVATAR_SVG}</div>
          <div class="doc-info">
            <div class="doc-name" title="${esc(d.filename)}">${esc(d.filename)}</div>
            <div class="doc-meta">${d.num_chunks} chunks</div>
          </div>
          <button class="doc-delete" onclick="window.deleteDoc('${d.doc_id}')" title="Delete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>`
    )
    .join("");
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
