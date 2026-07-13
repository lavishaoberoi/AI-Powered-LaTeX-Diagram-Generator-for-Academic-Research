/**
 * DiagramAI — Frontend Application
 * IBM Watsonx.ai + Granite | Academic LaTeX Diagram Generator
 */

"use strict";

// ═══════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════
const State = {
  currentDiagramId:  null,
  currentLatexCode:  "",
  currentVersion:    0,
  zoomLevel:         1.0,
  isLoading:         false,
  isDraggingResizer: false,
  uploadedSketchFile: null,
  history:           [],
};

// ═══════════════════════════════════════════════════════════════════════
// DOM REFERENCES
// ═══════════════════════════════════════════════════════════════════════
const $ = id => document.getElementById(id);

const DOM = {
  chatContainer:      $("chatContainer"),
  chatInput:          $("chatInput"),
  sendBtn:            $("sendBtn"),
  autoCompile:        $("autoCompile"),
  diagramTypeHint:    $("diagramTypeHint"),
  styleProfile:       $("styleProfile"),
  themeToggle:        $("themeToggle"),
  historyToggle:      $("historyToggle"),
  historyCount:       $("historyCount"),
  historySidebar:     $("historySidebar"),
  historyOverlay:     $("historyOverlay"),
  historyList:        $("historyList"),
  historySearch:      $("historySearch"),
  closeHistory:       $("closeHistory"),
  clearHistoryBtn:    $("clearHistoryBtn"),
  panelLeft:          $("panelLeft"),
  panelResizer:       $("panelResizer"),
  previewArea:        $("previewArea"),
  previewPlaceholder: $("previewPlaceholder"),
  previewImageWrap:   $("previewImageWrap"),
  previewImage:       $("previewImage"),
  previewStatus:      $("previewStatus"),
  compileErrorPanel:  $("compileErrorPanel"),
  errorLog:           $("errorLog"),
  autoFixBtn:         $("autoFixBtn"),
  exportBtn:          $("exportBtn"),
  exportTex:          $("exportTex"),
  exportPdf:          $("exportPdf"),
  exportPng:          $("exportPng"),
  zoomIn:             $("zoomIn"),
  zoomOut:            $("zoomOut"),
  zoomReset:          $("zoomReset"),
  zoomContainer:      $("zoomContainer"),
  explanationPanel:   $("explanationPanel"),
  explanationToggle:  $("explanationToggle"),
  explanationBody:    $("explanationBody"),
  loadingOverlay:     $("loadingOverlay"),
  loadingMsg:         $("loadingMsg"),
  toastContainer:     $("toastContainer"),
  // Editor tab
  editorValidate:     $("editorValidate"),
  editorCompile:      $("editorCompile"),
  editorOptimize:     $("editorOptimize"),
  editorCopy:         $("editorCopy"),
  validationPanel:    $("validationPanel"),
  optimizationPanel:  $("optimizationPanel"),
  codeEditorEl:       $("codeEditor"),
  // Sketch tab
  dropZone:           $("dropZone"),
  sketchFile:         $("sketchFile"),
  sketchPreview:      $("sketchPreview"),
  sketchImg:          $("sketchImg"),
  clearSketch:        $("clearSketch"),
  sketchDescription:  $("sketchDescription"),
  interpretSketch:    $("interpretSketch"),
};

// ═══════════════════════════════════════════════════════════════════════
// CODEMIRROR SETUP
// ═══════════════════════════════════════════════════════════════════════
let editor;

function initEditor() {
  const isDark = document.documentElement.dataset.theme === "dark";
  editor = CodeMirror(DOM.codeEditorEl, {
    mode:             "stex",
    theme:            isDark ? "dracula" : "eclipse",
    lineNumbers:      true,
    matchBrackets:    true,
    autoCloseBrackets: true,
    lineWrapping:     false,
    tabSize:          2,
    indentWithTabs:   false,
    extraKeys: {
      "Ctrl-Enter":  () => compileEditorCode(),
      "Cmd-Enter":   () => compileEditorCode(),
    },
  });

  // Sync editor content to state on change
  editor.on("change", () => {
    State.currentLatexCode = editor.getValue();
  });

  // Set initial size
  setTimeout(() => editor.refresh(), 100);
}

function setEditorCode(code) {
  if (!editor) return;
  editor.setValue(code || "");
  editor.clearHistory();
  State.currentLatexCode = code || "";
}

function getEditorCode() {
  return editor ? editor.getValue() : State.currentLatexCode;
}

// ═══════════════════════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════════════════════
function initTheme() {
  const saved = localStorage.getItem("diagramai-theme") || "light";
  applyTheme(saved);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("diagramai-theme", theme);
  const icon = DOM.themeToggle.querySelector("i");
  icon.className = theme === "dark" ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
  if (editor) {
    editor.setOption("theme", theme === "dark" ? "dracula" : "eclipse");
  }
}

DOM.themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
});

// ═══════════════════════════════════════════════════════════════════════
// LOADING
// ═══════════════════════════════════════════════════════════════════════
function showLoading(msg = "Generating diagram...") {
  State.isLoading = true;
  DOM.loadingMsg.textContent = msg;
  DOM.loadingOverlay.classList.remove("d-none");
  DOM.sendBtn.disabled = true;
}

function hideLoading() {
  State.isLoading = false;
  DOM.loadingOverlay.classList.add("d-none");
  DOM.sendBtn.disabled = false;
}

// ═══════════════════════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════════
function toast(message, type = "info", duration = 4000) {
  const id = "toast-" + Date.now();
  const icons = { success: "bi-check-circle-fill", error: "bi-exclamation-triangle-fill", info: "bi-info-circle-fill", warning: "bi-exclamation-circle-fill" };
  const colors = { success: "#16a34a", error: "#dc2626", info: "#3b82d4", warning: "#d97706" };
  const el = document.createElement("div");
  el.className = "toast show align-items-center";
  el.id = id;
  el.style.cssText = `border-left: 4px solid ${colors[type]}; background: var(--bg); color: var(--text); min-width: 260px;`;
  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body d-flex align-items-center gap-2">
        <i class="bi ${icons[type]}" style="color:${colors[type]}"></i>
        <span style="font-size:13px">${message}</span>
      </div>
      <button type="button" class="btn-close btn-close-sm me-2 m-auto" onclick="this.closest('.toast').remove()"></button>
    </div>`;
  DOM.toastContainer.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ═══════════════════════════════════════════════════════════════════════
// CHAT MESSAGES
// ═══════════════════════════════════════════════════════════════════════
function timeNow() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function addUserMessage(text) {
  const el = document.createElement("div");
  el.className = "chat-message user-message";
  el.innerHTML = `
    <div class="msg-avatar"><i class="bi bi-person-fill"></i></div>
    <div class="msg-body">
      <div class="msg-header">You <span class="msg-time">${timeNow()}</span></div>
      <div class="msg-text">${escapeHtml(text)}</div>
    </div>`;
  DOM.chatContainer.appendChild(el);
  scrollChat();
}

function addTypingIndicator() {
  const el = document.createElement("div");
  el.className = "chat-message assistant-message";
  el.id = "typingIndicator";
  el.innerHTML = `
    <div class="msg-avatar"><i class="bi bi-cpu-fill"></i></div>
    <div class="msg-body">
      <div class="msg-header">DiagramAI <span class="msg-time">${timeNow()}</span></div>
      <div class="msg-text">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    </div>`;
  DOM.chatContainer.appendChild(el);
  scrollChat();
  return el;
}

function removeTypingIndicator() {
  const el = $("typingIndicator");
  if (el) el.remove();
}

function addAssistantMessage(content, latexCode = null, diagramId = null, version = null, compiled = false) {
  const el = document.createElement("div");
  el.className = "chat-message assistant-message";

  let codeBlock = "";
  if (latexCode) {
    const preview = latexCode.substring(0, 500);
    const truncated = latexCode.length > 500;
    codeBlock = `
      <div class="msg-code">
        <div class="msg-code-header">
          <span><i class="bi bi-code-slash me-1"></i>TikZ Code ${version ? `— v${version}` : ""}</span>
          <div class="d-flex gap-1">
            <button class="btn btn-xs btn-outline-secondary" onclick="loadCodeToEditor(\`${escapeForAttr(latexCode)}\`)">
              <i class="bi bi-pencil-square me-1"></i>Edit
            </button>
            ${compiled ? `<span class="badge" style="background:#dcfce7;color:#166534;font-size:10px"><i class="bi bi-check2 me-1"></i>Compiled</span>` : `<span class="badge" style="background:#fee2e2;color:#dc2626;font-size:10px"><i class="bi bi-x me-1"></i>Error</span>`}
          </div>
        </div>
        <code>${escapeHtml(preview)}${truncated ? "\n... (truncated — see editor)" : ""}</code>
      </div>`;
  }

  el.innerHTML = `
    <div class="msg-avatar"><i class="bi bi-cpu-fill"></i></div>
    <div class="msg-body">
      <div class="msg-header">DiagramAI <span class="msg-time">${timeNow()}</span></div>
      <div class="msg-text">
        <p>${content}</p>
        ${codeBlock}
      </div>
    </div>`;
  DOM.chatContainer.appendChild(el);
  scrollChat();
}

function scrollChat() {
  DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
}

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escapeForAttr(str) {
  return str.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$/g, "\\$");
}

// ═══════════════════════════════════════════════════════════════════════
// PREVIEW PANEL
// ═══════════════════════════════════════════════════════════════════════
function setPreviewStatus(status, text) {
  const icons = { idle: "bi-circle-fill", loading: "bi-arrow-repeat", ok: "bi-check-circle-fill", error: "bi-x-circle-fill" };
  DOM.previewStatus.className = `status-badge status-${status}`;
  DOM.previewStatus.innerHTML = `<i class="bi ${icons[status]} me-1"></i>${text}`;
}

function showPreviewImage(base64Png) {
  DOM.previewPlaceholder.classList.add("d-none");
  DOM.compileErrorPanel.classList.add("d-none");
  DOM.previewImageWrap.classList.remove("d-none");
  DOM.previewImage.src = "data:image/png;base64," + base64Png;
  setPreviewStatus("ok", "Compiled");
  DOM.exportBtn.disabled = false;
}

function showPreviewError(errorLog) {
  DOM.previewPlaceholder.classList.add("d-none");
  DOM.previewImageWrap.classList.add("d-none");
  DOM.compileErrorPanel.classList.remove("d-none");
  DOM.errorLog.textContent = errorLog || "Unknown compilation error.";
  setPreviewStatus("error", "Error");
}

function showExplanation(explanation) {
  if (!explanation || explanation === "No explanation provided.") return;
  const formatted = explanation
    .split("\n")
    .filter(l => l.trim())
    .map(l => `<p>${escapeHtml(l)}</p>`)
    .join("");
  DOM.explanationBody.innerHTML = formatted;
  DOM.explanationPanel.classList.remove("collapsed");
}

function loadCodeToEditor(code) {
  setEditorCode(code);
  // Switch to editor tab
  const editorTab = document.querySelector('[data-bs-target="#tabEditor"]');
  if (editorTab) bootstrap.Tab.getOrCreateInstance(editorTab).show();
}

// ═══════════════════════════════════════════════════════════════════════
// API CALLS
// ═══════════════════════════════════════════════════════════════════════
async function apiPost(endpoint, body) {
  const resp = await fetch(endpoint, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
  return data;
}

async function apiFetch(endpoint) {
  const resp = await fetch(endpoint);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
  return data;
}

// ═══════════════════════════════════════════════════════════════════════
// GENERATE DIAGRAM
// ═══════════════════════════════════════════════════════════════════════
async function handleSend() {
  const text = DOM.chatInput.value.trim();
  if (!text || State.isLoading) return;

  const hasExistingCode = !!State.currentLatexCode;
  const isRefinement = hasExistingCode && looksLikeRefinement(text);

  DOM.chatInput.value = "";
  addUserMessage(text);
  const indicator = addTypingIndicator();
  showLoading(isRefinement ? "Refining diagram..." : "Generating diagram...");
  setPreviewStatus("loading", "Generating...");

  try {
    let data;
    if (isRefinement) {
      data = await apiPost("/api/refine", {
        current_code:       State.currentLatexCode,
        refinement_request: text,
        style_profile:      DOM.styleProfile.value,
        diagram_type:       DOM.diagramTypeHint.value || undefined,
        auto_compile:       DOM.autoCompile.checked,
      });
    } else {
      data = await apiPost("/api/generate", {
        description:   text,
        style_profile: DOM.styleProfile.value,
        diagram_type:  DOM.diagramTypeHint.value || undefined,
        auto_compile:  DOM.autoCompile.checked,
      });
    }

    removeTypingIndicator();
    handleDiagramResponse(data, text, isRefinement);
  } catch (err) {
    removeTypingIndicator();
    hideLoading();
    setPreviewStatus("error", "Failed");
    addAssistantMessage(`❌ Error: ${err.message}. Please check your IBM Cloud credentials and try again.`);
    toast(err.message, "error");
  }
}

function looksLikeRefinement(text) {
  const refinementKeywords = [
    "make", "change", "add", "remove", "increase", "decrease",
    "move", "rotate", "color", "colour", "curved", "dashed",
    "bold", "larger", "smaller", "horizontal", "vertical",
    "label", "rename", "fix", "update", "modify", "adjust",
    "show", "hide", "resize", "recolor", "recolour", "now",
  ];
  const lower = text.toLowerCase();
  return refinementKeywords.some(kw => lower.startsWith(kw) || lower.includes(" " + kw + " "));
}

function handleDiagramResponse(data, prompt, isRefinement) {
  State.currentDiagramId = data.diagram_id;
  State.currentVersion   = data.version;
  State.currentLatexCode = data.latex_code;

  // Update editor
  setEditorCode(data.latex_code);

  // Chat message
  const action = isRefinement ? "refined" : "generated";
  const typeLabel = (data.diagram_type || "diagram").replace(/_/g, " ");
  const compiled  = data.compiled;
  const msg = compiled
    ? `✅ I've ${action} your <strong>${typeLabel}</strong> (v${data.version}). The diagram compiled successfully!`
    : `⚠️ I've ${action} your <strong>${typeLabel}</strong> (v${data.version}). There was a compilation issue — check the error panel.`;

  addAssistantMessage(msg, data.latex_code, data.diagram_id, data.version, compiled);

  // Preview
  if (data.png_base64) {
    showPreviewImage(data.png_base64);
  } else if (data.error_log) {
    showPreviewError(data.error_log);
  }

  // Explanation
  if (data.explanation) {
    showExplanation(data.explanation);
  }

  // Syntax issues
  if (data.issues && data.issues.length > 0) {
    toast("Syntax issues detected — check validation panel", "warning");
  }

  // Update export links
  updateExportLinks(data.diagram_id);

  hideLoading();
  loadHistory();
}

// ═══════════════════════════════════════════════════════════════════════
// EDITOR ACTIONS
// ═══════════════════════════════════════════════════════════════════════
async function compileEditorCode() {
  const code = getEditorCode();
  if (!code.trim()) { toast("Editor is empty", "warning"); return; }

  showLoading("Compiling...");
  setPreviewStatus("loading", "Compiling...");

  try {
    const data = await apiPost("/api/compile", { latex_code: code });

    if (data.compiled && data.png_base64) {
      showPreviewImage(data.png_base64);
      toast("Compiled successfully!", "success");
    } else {
      showPreviewError(data.error_log || "Compilation failed.");
      toast("Compilation failed", "error");
    }

    if (data.issues && data.issues.length > 0) {
      DOM.validationPanel.classList.remove("d-none");
      DOM.validationPanel.className = "validation-panel has-errors";
      DOM.validationPanel.innerHTML = `<strong>⚠️ Issues:</strong><ul class="mb-0 mt-1">${data.issues.map(i => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`;
    }
  } catch (err) {
    toast(err.message, "error");
  } finally {
    hideLoading();
  }
}

DOM.editorValidate.addEventListener("click", async () => {
  const code = getEditorCode();
  if (!code.trim()) { toast("Editor is empty", "warning"); return; }
  try {
    const data = await apiPost("/api/compile", { latex_code: code });
    DOM.validationPanel.classList.remove("d-none");
    if (data.issues && data.issues.length > 0) {
      DOM.validationPanel.className = "validation-panel has-errors";
      DOM.validationPanel.innerHTML = `<strong>⚠️ Issues found:</strong><ul class="mb-0 mt-1">${data.issues.map(i => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`;
    } else {
      DOM.validationPanel.className = "validation-panel has-ok";
      DOM.validationPanel.innerHTML = "<strong>✅ No syntax issues detected.</strong>";
    }
  } catch (err) {
    toast(err.message, "error");
  }
});

DOM.editorCompile.addEventListener("click", compileEditorCode);

DOM.editorOptimize.addEventListener("click", async () => {
  const code = getEditorCode();
  if (!code.trim()) { toast("Editor is empty", "warning"); return; }
  showLoading("Getting AI optimization suggestions...");
  try {
    const data = await apiPost("/api/optimize", {
      latex_code:    code,
      style_profile: DOM.styleProfile.value,
    });
    DOM.optimizationPanel.classList.remove("d-none");
    const suggestionsHtml = data.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join("");
    DOM.optimizationPanel.innerHTML = `
      <strong>💡 Optimization Suggestions:</strong>
      <ul class="mb-2 mt-1">${suggestionsHtml}</ul>
      ${data.improved_code ? `<button class="btn btn-xs btn-outline-primary" id="applyOptimization">Apply Improved Code</button>` : ""}`;

    const applyBtn = $("applyOptimization");
    if (applyBtn && data.improved_code) {
      applyBtn.addEventListener("click", () => {
        setEditorCode(data.improved_code);
        DOM.optimizationPanel.classList.add("d-none");
        toast("Improved code applied!", "success");
      });
    }
  } catch (err) {
    toast(err.message, "error");
  } finally {
    hideLoading();
  }
});

DOM.editorCopy.addEventListener("click", () => {
  const code = getEditorCode();
  navigator.clipboard.writeText(code).then(() => toast("Code copied to clipboard!", "success"));
});

// ═══════════════════════════════════════════════════════════════════════
// AUTO-FIX
// ═══════════════════════════════════════════════════════════════════════
DOM.autoFixBtn.addEventListener("click", async () => {
  const errorLog = DOM.errorLog.textContent;
  const code = getEditorCode() || State.currentLatexCode;
  if (!code || !errorLog) return;

  showLoading("Auto-fixing errors with AI...");
  try {
    const data = await apiPost("/api/refine", {
      current_code:       code,
      refinement_request: `Fix these LaTeX compilation errors:\n${errorLog}`,
      style_profile:      DOM.styleProfile.value,
      auto_compile:       true,
    });
    State.currentLatexCode = data.latex_code;
    setEditorCode(data.latex_code);
    if (data.png_base64) {
      showPreviewImage(data.png_base64);
      toast("Errors fixed and recompiled!", "success");
    } else if (data.error_log) {
      showPreviewError(data.error_log);
      toast("Some errors remain — check error panel", "warning");
    }
  } catch (err) {
    toast(err.message, "error");
  } finally {
    hideLoading();
  }
});

// ═══════════════════════════════════════════════════════════════════════
// SKETCH UPLOAD
// ═══════════════════════════════════════════════════════════════════════
function setupSketchUpload() {
  DOM.dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    DOM.dropZone.classList.add("drag-over");
  });
  DOM.dropZone.addEventListener("dragleave", () => DOM.dropZone.classList.remove("drag-over"));
  DOM.dropZone.addEventListener("drop", e => {
    e.preventDefault();
    DOM.dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) loadSketchFile(file);
  });
  DOM.dropZone.addEventListener("click", () => DOM.sketchFile.click());
  DOM.sketchFile.addEventListener("change", e => {
    const file = e.target.files[0];
    if (file) loadSketchFile(file);
  });
  DOM.clearSketch.addEventListener("click", () => {
    State.uploadedSketchFile = null;
    DOM.sketchPreview.classList.add("d-none");
    DOM.interpretSketch.disabled = true;
    DOM.sketchFile.value = "";
  });

  DOM.interpretSketch.addEventListener("click", async () => {
    if (!State.uploadedSketchFile) return;
    showLoading("Interpreting sketch...");
    const formData = new FormData();
    formData.append("sketch", State.uploadedSketchFile);
    formData.append("description", DOM.sketchDescription.value);
    formData.append("style_profile", DOM.styleProfile.value);

    try {
      const resp = await fetch("/api/sketch", { method: "POST", body: formData });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Sketch interpretation failed");
      handleDiagramResponse(data, `[sketch] ${DOM.sketchDescription.value}`, false);
      // Switch to chat tab
      const chatTab = document.querySelector('[data-bs-target="#tabChat"]');
      if (chatTab) bootstrap.Tab.getOrCreateInstance(chatTab).show();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      hideLoading();
    }
  });
}

function loadSketchFile(file) {
  if (!file.type.startsWith("image/")) { toast("Please upload an image file", "warning"); return; }
  State.uploadedSketchFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    DOM.sketchImg.src = e.target.result;
    DOM.sketchPreview.classList.remove("d-none");
    DOM.interpretSketch.disabled = false;
  };
  reader.readAsDataURL(file);
}

// ═══════════════════════════════════════════════════════════════════════
// ZOOM
// ═══════════════════════════════════════════════════════════════════════
function applyZoom(level) {
  State.zoomLevel = Math.max(0.3, Math.min(3.0, level));
  DOM.zoomContainer.style.transform = `scale(${State.zoomLevel})`;
}

DOM.zoomIn.addEventListener("click",    () => applyZoom(State.zoomLevel + 0.2));
DOM.zoomOut.addEventListener("click",   () => applyZoom(State.zoomLevel - 0.2));
DOM.zoomReset.addEventListener("click", () => applyZoom(1.0));

// Mouse-wheel zoom on preview
DOM.previewArea.addEventListener("wheel", e => {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    applyZoom(State.zoomLevel + (e.deltaY < 0 ? 0.1 : -0.1));
  }
}, { passive: false });

// ═══════════════════════════════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════════════════════════════
function updateExportLinks(diagramId) {
  DOM.exportTex.href = `/api/download/tex/${diagramId}`;
  DOM.exportPdf.href = `/api/download/pdf/${diagramId}`;
  DOM.exportPng.href = `/api/download/png/${diagramId}`;
  DOM.exportBtn.disabled = false;
}

// Prevent default for non-download links while disabled
[DOM.exportTex, DOM.exportPdf, DOM.exportPng].forEach(el => {
  el.addEventListener("click", e => {
    if (DOM.exportBtn.disabled || !State.currentDiagramId) {
      e.preventDefault();
      toast("Generate a diagram first", "warning");
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════
// PANEL RESIZER
// ═══════════════════════════════════════════════════════════════════════
function setupResizer() {
  let startX, startWidth;

  DOM.panelResizer.addEventListener("mousedown", e => {
    State.isDraggingResizer = true;
    startX = e.clientX;
    startWidth = DOM.panelLeft.offsetWidth;
    DOM.panelResizer.classList.add("dragging");
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  });

  document.addEventListener("mousemove", e => {
    if (!State.isDraggingResizer) return;
    const delta = e.clientX - startX;
    const newWidth = Math.max(300, Math.min(startWidth + delta, window.innerWidth * 0.70));
    DOM.panelLeft.style.width = newWidth + "px";
    if (editor) editor.refresh();
  });

  document.addEventListener("mouseup", () => {
    if (State.isDraggingResizer) {
      State.isDraggingResizer = false;
      DOM.panelResizer.classList.remove("dragging");
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════
// HISTORY
// ═══════════════════════════════════════════════════════════════════════
async function loadHistory() {
  try {
    const data = await apiFetch("/api/history");
    State.history = data.history || [];
    renderHistory(State.history);
    const count = State.history.length;
    DOM.historyCount.textContent = count;
    DOM.historyCount.classList.toggle("show", count > 0);
  } catch (e) {
    // silently fail
  }
}

function renderHistory(items) {
  if (!items || items.length === 0) {
    DOM.historyList.innerHTML = '<p class="text-muted text-center small pt-4">No diagrams yet. Generate one to get started!</p>';
    return;
  }
  DOM.historyList.innerHTML = items.map(item => {
    const date = new Date(item.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    const typeLabel = (item.diagram_type || "diagram").replace(/_/g, " ");
    const prompt = item.prompt ? item.prompt.substring(0, 60) + (item.prompt.length > 60 ? "…" : "") : "No description";
    return `
      <div class="history-item" data-id="${item.id}">
        <span class="h-type">${escapeHtml(typeLabel)}</span>
        <div class="h-prompt">${escapeHtml(prompt)}</div>
        <div class="h-meta">v${item.version} &nbsp;·&nbsp; ${date}</div>
        <button class="h-delete" onclick="deleteHistoryItem(event, '${item.id}')" title="Delete">
          <i class="bi bi-trash"></i>
        </button>
      </div>`;
  }).join("");

  // Click to load
  DOM.historyList.querySelectorAll(".history-item").forEach(el => {
    el.addEventListener("click", () => loadHistoryItem(el.dataset.id));
  });
}

async function loadHistoryItem(id) {
  try {
    const data = await apiFetch(`/api/history/${id}`);
    State.currentDiagramId = data.id;
    State.currentVersion   = data.version;
    State.currentLatexCode = data.latex_code;
    setEditorCode(data.latex_code);
    if (data.png_base64) showPreviewImage(data.png_base64);
    if (data.explanation) showExplanation(data.explanation);
    updateExportLinks(data.id);
    closeHistorySidebar();
    toast(`Loaded v${data.version}`, "info");
  } catch (err) {
    toast(err.message, "error");
  }
}

async function deleteHistoryItem(event, id) {
  event.stopPropagation();
  try {
    await fetch(`/api/history/${id}`, { method: "DELETE" });
    loadHistory();
    toast("Deleted", "info");
  } catch (err) {
    toast(err.message, "error");
  }
}

DOM.clearHistoryBtn.addEventListener("click", async () => {
  if (!confirm("Clear all diagram history?")) return;
  try {
    await fetch("/api/history", { method: "DELETE" });
    loadHistory();
    toast("History cleared", "info");
  } catch (err) {
    toast(err.message, "error");
  }
});

DOM.historySearch.addEventListener("input", () => {
  const q = DOM.historySearch.value.toLowerCase();
  const filtered = q ? State.history.filter(h => (h.prompt || "").toLowerCase().includes(q) || (h.diagram_type || "").toLowerCase().includes(q)) : State.history;
  renderHistory(filtered);
});

// ═══════════════════════════════════════════════════════════════════════
// HISTORY SIDEBAR TOGGLE
// ═══════════════════════════════════════════════════════════════════════
function openHistorySidebar()  {
  DOM.historySidebar.classList.add("open");
  DOM.historyOverlay.classList.remove("d-none");
}

function closeHistorySidebar() {
  DOM.historySidebar.classList.remove("open");
  DOM.historyOverlay.classList.add("d-none");
}

DOM.historyToggle.addEventListener("click",  openHistorySidebar);
DOM.closeHistory.addEventListener("click",   closeHistorySidebar);
DOM.historyOverlay.addEventListener("click", closeHistorySidebar);

// ═══════════════════════════════════════════════════════════════════════
// EXPLANATION TOGGLE
// ═══════════════════════════════════════════════════════════════════════
DOM.explanationToggle.addEventListener("click", () => {
  DOM.explanationPanel.classList.toggle("collapsed");
});

// ═══════════════════════════════════════════════════════════════════════
// EXAMPLE PROMPTS
// ═══════════════════════════════════════════════════════════════════════
document.addEventListener("click", e => {
  const link = e.target.closest(".example-link");
  if (link) {
    e.preventDefault();
    DOM.chatInput.value = link.dataset.prompt;
    DOM.chatInput.focus();
  }
});

// ═══════════════════════════════════════════════════════════════════════
// KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════════════════
DOM.chatInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

DOM.sendBtn.addEventListener("click", handleSend);

// Global shortcuts
document.addEventListener("keydown", e => {
  // Ctrl/Cmd+K → focus chat
  if ((e.ctrlKey || e.metaKey) && e.key === "k") {
    e.preventDefault();
    DOM.chatInput.focus();
    const chatTab = document.querySelector('[data-bs-target="#tabChat"]');
    if (chatTab) bootstrap.Tab.getOrCreateInstance(chatTab).show();
  }
  // Escape → close sidebar
  if (e.key === "Escape") closeHistorySidebar();
});

// ═══════════════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initEditor();
  setupResizer();
  setupSketchUpload();
  loadHistory();

  // Auto-resize textarea
  DOM.chatInput.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 150) + "px";
  });
});

// Expose for inline handlers
window.loadCodeToEditor = loadCodeToEditor;
window.deleteHistoryItem = deleteHistoryItem;
