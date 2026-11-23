"use strict";

const state = { cases: [], selectedCaseId: null, selectedCase: null, metrics: null, jobId: null, jobPoll: null, entities: [] };
const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
function labelOf(value) {
  return String(value || "Field").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function formatPct(value) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? "N/A" : `${(Number(value) * 100).toFixed(1)}%`;
}
function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => node.classList.remove("visible"), 3200);
}
function setApiStatus(ok, message) {
  $("api-status").classList.toggle("offline", !ok);
  $("api-status").innerHTML = `<span class="status-dot"></span>${esc(message)}`;
}
async function api(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error(payload?.error || `Request failed (${response.status})`);
  return payload;
}

async function initialize() {
  bindEvents();
  try {
    const [health, metrics] = await Promise.all([api("/api/health"), api("/api/metrics")]);
    state.metrics = metrics;
    setApiStatus(true, "API connected");
    renderHealth(health);
    await refreshCases();
  } catch (error) {
    setApiStatus(false, "API unavailable");
    showEmptyState(`Could not connect to the local API: ${error.message}. Start the server with python src/serve.py.`);
  }
}

function bindEvents() {
  $("refresh-cases").addEventListener("click", refreshCases);
  $("empty-refresh").addEventListener("click", refreshCases);
  $("case-search").addEventListener("input", renderCaseList);
  $("process-case").addEventListener("click", startPipeline);
  $("close-job").addEventListener("click", closeJobModal);
  $("entity-search").addEventListener("input", () => renderEntities(state.entities));
  document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tab)));
}

function renderHealth(health) {
  const parts = ["Local server" ];
  if (health.whisper_cli_available && health.whisper_model_available) parts.push("Whisper ready");
  else parts.push("transcription setup required");
  $("api-status").title = `Python ${health.python_version}; ${parts.join("; ")}`;
}

async function refreshCases() {
  try {
    const [result, metrics] = await Promise.all([api("/api/cases"), api("/api/metrics")]);
    state.metrics = metrics;
    state.cases = result.cases || [];
    $("case-count").textContent = `${state.cases.length} ${state.cases.length === 1 ? "case" : "cases"} available`;
    renderCaseList();
    if (!state.cases.length) {
      state.selectedCaseId = null;
      showEmptyState();
      return;
    }
    hideEmptyState();
    if (!state.selectedCaseId || !state.cases.some((item) => item.id === state.selectedCaseId)) {
      await selectCase(state.cases[0].id);
    } else {
      await selectCase(state.selectedCaseId);
    }
  } catch (error) {
    toast(error.message);
  }
}

function renderCaseList() {
  const query = $("case-search").value.trim().toLowerCase();
  const list = state.cases.filter((item) => `${item.label} ${item.id}`.toLowerCase().includes(query));
  $("case-list").innerHTML = list.length ? list.map((item) => `
    <button class="case-item ${item.id === state.selectedCaseId ? "selected" : ""}" type="button" data-case-id="${esc(item.id)}">
      <span class="case-item-avatar">${esc(item.id.slice(-2))}</span>
      <span class="case-item-copy"><strong>${esc(item.label)}</strong><small>${item.age ? `${esc(item.age)} yrs` : "Age not reported"}${item.sex ? ` · ${esc(item.sex)}` : ""}</small><small class="case-item-status"><i class="mini-dot ${item.ready ? "ready" : "pending"}"></i>${item.ready ? "Form generated" : "Transcript available"}</small></span>
      <span class="case-chevron">›</span>
    </button>`).join("") : `<div class="list-empty">No cases match this search.</div>`;
  $("case-list").querySelectorAll("[data-case-id]").forEach((button) => button.addEventListener("click", () => selectCase(button.dataset.caseId)));
}

function showEmptyState(message) {
  $("case-workspace").classList.add("hidden");
  $("empty-state").classList.remove("hidden");
  if (message) $("empty-state").querySelector("p").textContent = message;
  $("process-case").disabled = true;
}
function hideEmptyState() {
  $("empty-state").classList.add("hidden");
  $("case-workspace").classList.remove("hidden");
}

async function selectCase(caseId) {
  try {
    const result = await api(`/api/cases/${encodeURIComponent(caseId)}`);
    state.selectedCaseId = caseId;
    state.selectedCase = result;
    renderCaseList();
    renderCase(result);
    $("process-case").disabled = !(state.cases.find((item) => item.id === caseId)?.can_process);
  } catch (error) {
    toast(error.message);
  }
}

function renderCase(item) {
  const form = item.form || {};
  const demo = form.demographics || {};
  const summary = item.summary || {};
  $("case-title").textContent = item.label || item.id;
  $("case-avatar").textContent = (item.label || "C").replace(/\D/g, "").slice(-2) || "C";
  $("case-subtitle").textContent = [summary.age ? `${summary.age} years` : "Age not reported", summary.sex || "Sex not reported", "Identifiers redacted in dashboard"].join(" · ");
  $("case-updated").textContent = item.updated_at ? `Updated ${new Date(item.updated_at).toLocaleString()}` : "No generated form yet";
  $("stat-entities").textContent = summary.entity_count ?? 0;
  $("stat-grounded").textContent = summary.ontology_grounded_count ?? 0;
  $("stat-relations").textContent = summary.relation_count ?? 0;
  $("stat-audio").textContent = item.audio_available ? "Available" : "Not found";
  $("audio-caption").textContent = item.audio_available ? "Source audio is streamed from the local project folder." : "No local audio file found for this case.";
  const audio = $("audio-player");
  if (item.audio_available) {
    audio.src = `/api/cases/${encodeURIComponent(item.id)}/audio`;
    audio.classList.remove("audio-disabled");
  } else {
    audio.removeAttribute("src");
    audio.load();
    audio.classList.add("audio-disabled");
  }
  $("export-json").href = `/api/cases/${encodeURIComponent(item.id)}/export?format=json`;
  $("export-md").href = `/api/cases/${encodeURIComponent(item.id)}/export?format=md`;
  renderForm(form);
  renderTranscripts(item.transcripts || {});
  state.entities = item.entities || [];
  renderEntities(state.entities);
  renderRelations(item.relations || []);
  renderEvaluation(state.metrics);
  activateTab("overview");
}

function statusPill(assertion) {
  const status = String(assertion || "UNKNOWN").toUpperCase();
  const cls = ["PRESENT", "ABSENT", "POSSIBLE", "UNKNOWN"].includes(status) ? status.toLowerCase() : "unknown";
  return `<span class="status-pill status-${cls}">${esc(status)}</span>`;
}
function fieldValue(value) {
  if (value === null || value === undefined || value === "") return `<span class="value-muted">Not reported</span>`;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value !== "object") return esc(value);
  if (value.assertion) {
    const detail = value.details || value.evidence || value.cancer_type || "";
    return `${statusPill(value.assertion)}${detail ? `<span class="field-detail">${esc(detail)}</span>` : ""}`;
  }
  const parts = Object.entries(value).filter(([key, val]) => val !== null && val !== undefined && val !== "" && !["source_question"].includes(key));
  if (!parts.length) return `<span class="value-muted">Not reported</span>`;
  return parts.map(([key, val]) => `<span class="field-detail"><b>${esc(labelOf(key))}:</b> ${esc(typeof val === "object" ? JSON.stringify(val) : val)}</span>`).join("");
}

function renderForm(form) {
  const sections = [
    ["demographics", "Patient profile", "Identity fields are redacted in this prototype view."],
    ["clinical_indicators", "Clinical indicators", "Measurements are shown only when extracted from the source."],
    ["history", "Medical and family history", "Assertion states preserve explicit negatives and unknown answers."],
    ["risk_factors", "Lifestyle and risk factors", "Extracted responses from the consultation."],
    ["general_cancer_symptoms", "General cancer symptoms", "Screening responses; UNKNOWN is not equivalent to ABSENT."],
    ["oral_cancer_screening", "Oral cancer screening", "Screening responses; UNKNOWN is not equivalent to ABSENT."],
  ];
  $("form-sections").innerHTML = sections.map(([key, title, description]) => {
    const obj = form[key] || {};
    const rows = Object.entries(obj).map(([field, value]) => `<div class="form-field"><span class="field-label">${esc(labelOf(field))}</span><div class="field-value">${fieldValue(value)}</div></div>`).join("");
    return `<article class="form-card"><div class="form-card-head"><div><h3>${esc(title)}</h3><p>${esc(description)}</p></div><span class="field-count">${Object.keys(obj).length} fields</span></div><div class="form-field-grid">${rows || `<p class="value-muted">No data available.</p>`}</div></article>`;
  }).join("");

  const evidence = form.extraction_evidence || {};
  const evidenceEntries = Object.entries(evidence);
  $("evidence-count").textContent = `${evidenceEntries.length} fields`;
  $("evidence-list").innerHTML = evidenceEntries.length ? evidenceEntries.map(([key, source]) => `
    <article class="evidence-item"><strong>${esc(labelOf(key.split(".").pop()))}</strong><div><span>Question</span><p>${esc(source?.question || "No matched question")}</p></div><div><span>Answer / evidence</span><p>${esc(source?.answer || source?.evidence || "No answer evidence")}</p></div></article>`).join("") : `<p class="value-muted">No extraction evidence map is available in this form.</p>`;
}

function segmentText(segment) {
  if (typeof segment === "string") return segment;
  return segment?.text || segment?.content || "";
}
function renderTranscriptList(segments, emptyText) {
  if (!Array.isArray(segments) || !segments.length) return `<div class="transcript-empty">${esc(emptyText)}</div>`;
  return segments.map((segment) => {
    const text = segmentText(segment);
    const start = segment?.start;
    const timestamp = Number.isFinite(Number(start)) ? `<time>${Math.floor(Number(start) / 60).toString().padStart(2, "0")}:${Math.floor(Number(start) % 60).toString().padStart(2, "0")}</time>` : "";
    return `<div class="transcript-line">${timestamp}<p>${esc(text)}</p></div>`;
  }).join("");
}
function renderTranscripts(transcripts) {
  $("transcript-hi").innerHTML = renderTranscriptList(transcripts.hi, "Hindi transcript is not available for this case.");
  $("transcript-en").innerHTML = renderTranscriptList(transcripts.en, "English translation is not available for this case.");
}

function renderEntities(entities) {
  const query = $("entity-search").value.trim().toLowerCase();
  const filtered = entities.filter((entity) => [entity.span, entity.entity_type, entity.assertion, entity.ontology_grounding?.preferred_term].join(" ").toLowerCase().includes(query));
  $("entity-rows").innerHTML = filtered.length ? filtered.map((entity) => {
    const onto = entity.ontology_grounding || {};
    const concept = onto.concept_id ? `${onto.ontology || "Concept"}: ${onto.concept_id}${onto.preferred_term ? ` · ${onto.preferred_term}` : ""}` : "Not mapped";
    return `<tr><td class="entity-span">${esc(entity.span)}</td><td>${esc(labelOf(entity.entity_type))}</td><td>${statusPill(entity.assertion)}</td><td>${esc(concept)}</td><td class="mono">${esc(onto.cui || "—")}</td></tr>`;
  }).join("") : `<tr><td colspan="5" class="table-empty">No entities match this filter.</td></tr>`;
}

function renderRelations(relations) {
  $("relation-grid").innerHTML = relations.length ? relations.map((relation) => `
    <article class="relation-card"><div class="relation-head"><span class="tag tag-soft">${esc(labelOf(relation.relation_type))}</span>${statusPill(relation.assertion)}</div><div class="relation-flow"><strong>${esc(relation.head?.span || "Unknown source")}</strong><span>→</span><strong>${esc(relation.tail?.span || relation.tail?.assertion || "Unknown target")}</strong></div><p>Source: ${esc(relation.head?.type || "—")} · Target: ${esc(relation.tail?.type || "Assertion")}</p></article>`).join("") : `<div class="blank-card">No clinical relations were extracted for this consultation.</div>`;
}

function renderEvaluation(metrics) {
  if (!metrics?.available) {
    $("evaluation-content").innerHTML = `<div class="blank-card">${esc(metrics?.message || "M4 evaluation summary is not available yet.")}</div>`;
    return;
  }
  const support = metrics.gold_class_support || {};
  const classes = ["PRESENT", "ABSENT", "POSSIBLE", "UNKNOWN"];
  const rows = classes.map((name) => {
    const item = metrics.per_class?.[name] || {};
    return `<tr><td>${statusPill(name)}</td><td>${esc(support[name] ?? item.support ?? 0)}</td><td>${esc(item.predicted_count ?? 0)}</td><td>${formatPct(item.precision)}</td><td>${formatPct(item.recall)}</td><td>${formatPct(item.f1)}</td></tr>`;
  }).join("");
  $("evaluation-content").innerHTML = `
    <div class="evaluation-warning"><strong>Interpretation warning</strong><p>${esc(metrics.scope_warning)}</p></div>
    <div class="evaluation-stats">
      <article class="metric-card"><span>Exact four-state agreement</span><strong>${formatPct(metrics.exact_accuracy)}</strong><small>${esc(metrics.correct_fields ?? "—")} of ${esc(metrics.scorable_fields ?? "—")} fields</small></article>
      <article class="metric-card"><span>Prediction coverage</span><strong>${formatPct(metrics.prediction_coverage)}</strong><small>Non-UNKNOWN predictions</small></article>
      <article class="metric-card"><span>Selective accuracy</span><strong>${formatPct(metrics.selective_accuracy)}</strong><small>Among non-abstained predictions</small></article>
      <article class="metric-card"><span>Abstentions</span><strong>${esc(metrics.abstentions ?? "—")}</strong><small>UNKNOWN predictions</small></article>
    </div>
    <div class="table-wrap"><table><thead><tr><th>Class</th><th>Reference support</th><th>Predicted</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="evaluation-note"><strong>NER evaluation:</strong> ${metrics.ner_available ? "Available from completed human annotations." : `Not available. ${esc(metrics.ner_reason || "Independent human annotations have not been completed.")}`}</div>
    <div class="evaluation-note"><strong>Matched case pairs:</strong> ${esc(metrics.matched_case_count ?? "Not reported")} · Metrics are a small preliminary benchmark, not a clinical performance claim.</div>`;
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const active = panel.id === `tab-${name}`;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
}

async function startPipeline() {
  if (!state.selectedCaseId || state.jobId) return;
  try {
    const result = await api(`/api/cases/${encodeURIComponent(state.selectedCaseId)}/process`, { method: "POST" });
    state.jobId = result.id;
    $("job-title").textContent = `Processing ${state.selectedCaseId.replace("-", " ")}`;
    $("job-status").textContent = "Queued";
    $("job-message").textContent = result.message;
    $("job-progress").style.width = "12%";
    $("job-log").textContent = "Pipeline started. This may take longer when speech recognition is required.";
    $("close-job").disabled = true;
    $("job-modal").classList.remove("hidden");
    $("process-case").disabled = true;
    state.jobPoll = window.setInterval(pollJob, 1100);
  } catch (error) {
    toast(error.message);
  }
}

async function pollJob() {
  try {
    const job = await api(`/api/jobs/${encodeURIComponent(state.jobId)}`);
    $("job-status").textContent = labelOf(job.status);
    $("job-message").textContent = job.message || "Working…";
    $("job-progress").style.width = job.status === "completed" ? "100%" : job.status === "failed" ? "100%" : "68%";
    $("job-log").textContent = job.log || "Pipeline is still running…";
    if (["completed", "failed"].includes(job.status)) {
      window.clearInterval(state.jobPoll);
      state.jobPoll = null;
      state.jobId = null;
      $("close-job").disabled = false;
      $("job-progress").classList.toggle("failed", job.status === "failed");
      $("process-case").disabled = false;
      if (job.status === "completed") {
        toast("Pipeline completed. Refreshing this case…");
        await refreshCases();
      } else {
        toast("Pipeline failed. Review the execution log.");
      }
    }
  } catch (error) {
    window.clearInterval(state.jobPoll);
    state.jobPoll = null;
    state.jobId = null;
    $("close-job").disabled = false;
    toast(error.message);
  }
}

function closeJobModal() {
  if (state.jobPoll) return;
  $("job-modal").classList.add("hidden");
  $("job-progress").classList.remove("failed");
}

document.addEventListener("DOMContentLoaded", initialize);
