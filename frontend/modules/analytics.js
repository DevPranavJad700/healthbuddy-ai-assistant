/**
 * HealthBuddy AI — Analytics & Clinician Review Queue Module
 * Chart.js powered operational dashboard and clinician review management.
 */

import { API, API_BASE, CHAT_ICON_SVG } from "./config.js";
import { state } from "./state.js";
import { esc, showToast } from "./utils.js";
import { authHeaders, attemptTokenRefresh } from "./auth.js";

let _chartInstances = {};

export function destroyChart(id) {
  if (_chartInstances[id]) {
    _chartInstances[id].destroy();
    delete _chartInstances[id];
  }
}

export async function loadDashboard() {
  const dash = document.getElementById("analyticsDashboard");
  if (!dash) return;

  dash.innerHTML = `
    <div class="analytics-skeleton">
      <div class="skel-card"></div><div class="skel-card"></div>
      <div class="skel-card"></div><div class="skel-card"></div>
      <div class="skel-card"></div><div class="skel-card"></div>
    </div>
    <div class="skel-chart"></div>
    <div class="skel-chart" style="height:120px;margin-top:10px;"></div>`;

  try {
    const r = await fetch(API_BASE + "/analytics/dashboard", {
      headers: authHeaders(),
    });

    if (r.status === 401 || r.status === 403) {
      if (r.status === 401 && (await attemptTokenRefresh())) {
        return loadDashboard();
      }
      const msg =
        r.status === 401
          ? "Sign in as admin to view analytics."
          : "Admin access required to view analytics.";
      dash.innerHTML = `<div class="session-loading" style="color:var(--text-muted)">${msg}</div>`;
      return;
    }

    if (!r.ok) {
      const errorData = await r.json().catch(() => ({}));
      throw new Error(errorData.detail || "Cannot load analytics");
    }

    const data = await r.json();
    const runtime = data.runtime_counters || {};

    const stats = [
      { v: data.total_chats, label: "Total Queries", icon: "💬" },
      {
        v: `${(Number(data.avg_response_time_ms || 0) / 1000).toFixed(2)}s`,
        label: "Avg Response",
        icon: "⚡",
      },
      { v: data.emergency_detections, label: "Emergencies", icon: "🚨" },
      { v: data.safety_flags, label: "Safety Blocks", icon: "🛡️" },
      {
        v: `${Number(data.chat_error_rate_pct || 0).toFixed(1)}%`,
        label: "Error Rate",
        icon: "❌",
      },
      {
        v: `${Number(data.helpful_rate_pct || 0).toFixed(1)}%`,
        label: "Helpful Rate",
        icon: "👍",
      },
      {
        v: Number(data.pending_clinician_reviews || 0),
        label: "Pending Reviews",
        icon: "🩺",
      },
      {
        v: `$${Number(data.usage_cost_today_usd || 0).toFixed(4)}`,
        label: "Cost Today",
        icon: "💰",
      },
    ];

    let html = `<div class="analytics-grid">`;
    stats.forEach((s) => {
      html += `<div class="stat-card"><div class="stat-icon">${s.icon}</div><div class="stat-value">${s.v}</div><div class="stat-label">${s.label}</div></div>`;
    });
    html += `</div>
      <div class="chart-section">
        <div class="chart-header">📈 Query Trend (Last 7 Days)</div>
        <div class="chart-wrap"><canvas id="queryTrendChart"></canvas></div>
      </div>
      <div class="chart-section" style="margin-top:12px;">
        <div class="chart-header">⚡ Performance Metrics</div>
        <div class="chart-wrap" style="height:140px;"><canvas id="responseBreakChart"></canvas></div>
      </div>
      <div class="chart-header" style="margin-top:12px;">🕐 Recent Queries</div>
      <div class="recent-queries">`;

    if (data.recent_questions && data.recent_questions.length > 0) {
      data.recent_questions.forEach((q) => {
        html += `<div class="query-item">${CHAT_ICON_SVG} ${esc(q)}</div>`;
      });
    } else {
      html += `<p style="font-size:0.7rem;color:var(--text-muted);">No queries yet.</p>`;
    }
    html += `</div>`;
    dash.innerHTML = html;

    // Check if Chart.js is loaded
    if (typeof Chart === "undefined") return;

    // Line Chart
    destroyChart("queryTrend");
    const trendCtx = document.getElementById("queryTrendChart");
    if (trendCtx) {
      const days = data.daily_stats || [];
      const labels = days.map((d) => (d.date ? d.date.slice(5) : "—"));
      const counts = days.map((d) => d.queries || 0);
      _chartInstances["queryTrend"] = new Chart(trendCtx, {
        type: "line",
        data: {
          labels: labels.length ? labels : ["No data"],
          datasets: [
            {
              label: "Queries",
              data: counts.length ? counts : [0],
              borderColor: "#6c63ff",
              backgroundColor: "rgba(108,99,255,0.15)",
              fill: true,
              tension: 0.4,
              pointBackgroundColor: "#6c63ff",
              pointRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              ticks: { color: "#8b8fa8", font: { size: 10 } },
              grid: { color: "rgba(255,255,255,0.05)" },
            },
            y: {
              ticks: { color: "#8b8fa8", font: { size: 10 } },
              grid: { color: "rgba(255,255,255,0.05)" },
              beginAtZero: true,
            },
          },
        },
      });
    }

    // Performance Bar Chart
    destroyChart("responseBreak");
    const breakCtx = document.getElementById("responseBreakChart");
    if (breakCtx) {
      _chartInstances["responseBreak"] = new Chart(breakCtx, {
        type: "bar",
        data: {
          labels: [
            "Avg Response (ms)",
            "Emergencies",
            "Safety Flags",
            "Failures",
          ],
          datasets: [
            {
              data: [
                Number(data.avg_response_time_ms || 0).toFixed(0),
                data.emergency_detections || 0,
                data.safety_flags || 0,
                runtime.provider_failures || 0,
              ],
              backgroundColor: ["#6c63ff", "#ff6b6b", "#ffa94d", "#868e96"],
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              ticks: { color: "#8b8fa8", font: { size: 10 } },
              grid: { display: false },
            },
            y: {
              ticks: { color: "#8b8fa8", font: { size: 10 } },
              grid: { color: "rgba(255,255,255,0.05)" },
              beginAtZero: true,
            },
          },
        },
      });
    }
  } catch (e) {
    console.error("Analytics Error:", e);
    dash.innerHTML = `<div class="session-loading" style="color:var(--danger)">Error: ${e.message}</div>`;
  }
}

export async function refreshQueueSummaryCounts() {
  const pCount = document.getElementById("queuePendingCount");
  const rCount = document.getElementById("queueReviewedCount");
  const sCount = document.getElementById("queueResolvedCount");
  if (!pCount || !rCount || !sCount) return;

  const statuses = ["pending", "reviewed", "resolved"];
  try {
    const results = await Promise.all(
      statuses.map(async (status) => {
        const r = await fetch(
          `${API.clinicianQueue}?status=${encodeURIComponent(status)}`,
          { headers: authHeaders() }
        );
        if (!r.ok) throw new Error(String(r.status));
        const data = await r.json().catch(() => ({}));
        return [status, Number(data.count || 0)];
      })
    );

    state.queueCounts = Object.fromEntries(results);
    pCount.textContent = String(state.queueCounts.pending || 0);
    rCount.textContent = String(state.queueCounts.reviewed || 0);
    sCount.textContent = String(state.queueCounts.resolved || 0);
    if (typeof window.updateOnboardingChecklist === "function") {
      window.updateOnboardingChecklist();
    }
  } catch (_) {
    pCount.textContent = "-";
    rCount.textContent = "-";
    sCount.textContent = "-";
  }
}

export async function loadClinicianQueue() {
  const container = document.getElementById("clinicianQueue");
  if (!container) return;

  const statusFilter = document.getElementById("reviewStatusFilter");
  const sortFilter = document.getElementById("reviewSortFilter");
  const searchInput = document.getElementById("reviewSearchInput");

  const status = statusFilter?.value || "pending";
  const sortMode = sortFilter?.value || "newest";
  const searchQuery = (searchInput?.value || "").trim().toLowerCase();

  container.innerHTML = `<div class="session-loading">Loading clinician queue...</div>`;

  try {
    const r = await fetch(
      `${API.clinicianQueue}?status=${encodeURIComponent(status)}`,
      { headers: authHeaders() }
    );
    if (r.status === 401 || r.status === 403) {
      if (r.status === 401 && (await attemptTokenRefresh())) {
        return loadClinicianQueue();
      }
      container.innerHTML = `<p style="font-size:0.72rem;color:var(--text-muted)">Admin token required to view clinician queue.</p>`;
      return;
    }
    if (!r.ok) throw new Error("Could not load queue");
    const data = await r.json();
    await refreshQueueSummaryCounts();

    const rawItems = Array.isArray(data.items) ? data.items : [];
    const filtered = rawItems
      .filter((item) => {
        if (!searchQuery) return true;
        const haystack = `${item.session_id || ""} ${item.question || ""} ${item.response || ""} ${item.reviewer_notes || ""}`.toLowerCase();
        return haystack.includes(searchQuery);
      })
      .sort((a, b) => {
        const tA = new Date(a.created_at || 0).getTime();
        const tB = new Date(b.created_at || 0).getTime();
        return sortMode === "oldest" ? tA - tB : tB - tA;
      });

    if (!filtered.length) {
      container.innerHTML = `<p style="font-size:0.72rem;color:var(--text-muted)">No ${esc(status)} items.</p>`;
      return;
    }

    container.innerHTML = filtered
      .map(
        (it) => `<div class="review-item">
          <div class="review-item-head">
            <span class="review-id">#${it.id}</span>
            <span class="review-status ${esc(it.status)}">${esc(it.status)}</span>
          </div>
          <div class="goal-meta">Session ${esc(it.session_id || "n/a")} • Created ${new Date(it.created_at).toLocaleString()}</div>
          <div class="goal-text">Q: ${esc(it.question)}</div>
          <div class="goal-meta">A: ${esc(it.response)}</div>
          ${it.reviewer_notes ? `<div class="review-notes">Notes: ${esc(it.reviewer_notes)}</div>` : ""}
          <div class="review-actions">
            <button class="feedback-btn" onclick="window.updateReview(${it.id}, 'reviewed')" ${it.status === "reviewed" ? "disabled" : ""}>Mark Reviewed</button>
            <button class="feedback-btn" onclick="window.updateReview(${it.id}, 'resolved')" ${it.status === "resolved" ? "disabled" : ""}>Mark Resolved</button>
          </div>
        </div>`
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<p style="font-size:0.72rem;color:var(--danger)">${esc(err.message || "Error loading queue")}</p>`;
  }
}

export async function updateReview(id, status) {
  const reviewerNotes = prompt("Reviewer notes (optional):", "") || "";
  try {
    const r = await fetch(`${API.clinicianQueue}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ status, reviewer_notes: reviewerNotes }),
    });
    if (r.status === 401 && (await attemptTokenRefresh())) {
      return updateReview(id, status);
    }
    if (!r.ok) throw new Error("Failed to update review");
    showToast(`Review ${status}`, "success");
    await loadClinicianQueue();
  } catch (err) {
    showToast(err.message || "Update failed", "error");
  }
}
