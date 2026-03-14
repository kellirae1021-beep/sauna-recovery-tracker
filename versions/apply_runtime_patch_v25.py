from pathlib import Path
import sys

index = Path("index.html")
if not index.exists():
    print("index.html not found")
    sys.exit(1)

html = index.read_text(encoding="utf-8")

def remove_block(text, start_marker, end_marker):
    if start_marker in text and end_marker in text:
        start = text.index(start_marker)
        end = text.index(end_marker) + len(end_marker)
        return text[:start] + text[end:]
    return text

start_marker = "<!-- V25_RUNTIME_PATCH_START -->"
end_marker = "<!-- V25_RUNTIME_PATCH_END -->"

patch = r"""
<!-- V25_RUNTIME_PATCH_START -->
<style>
  .entry-type-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
  .entry-type-btn{border:1px solid var(--border);border-radius:999px;padding:8px 12px;background:#fff;cursor:pointer}
  .entry-type-btn.active{background:var(--plum);color:#fff;border-color:var(--plum)}
  .field-error{display:none;color:#b00020;font-size:12px;margin-top:4px}
  .field-invalid input,.field-invalid textarea,.field-invalid select{border-color:#d44 !important;background:#fff7f7}
  .field-invalid .field-error{display:block}
  .sauna-status{border:1px solid var(--border);border-radius:14px;padding:14px;background:#fcfafc;display:grid;gap:8px}
  .sauna-status-main{font-size:26px;font-weight:700;line-height:1.1}
  .sauna-status-sub{font-size:13px;color:var(--muted)}
</style>

<script>
(function () {
  const FIELD_RULES = {
    sleepSelf: {min:1,max:10,label:"Use 1–10"},
    energy: {min:1,max:10,label:"Use 1–10"},
    stress: {min:1,max:10,label:"Use 1–10"},
    muscleSoreness: {min:1,max:10,label:"Use 1–10"},
    jointSoreness: {min:1,max:10,label:"Use 1–10"},
    jointStiffness: {min:1,max:10,label:"Use 1–10"},
    sleepScore: {min:0,max:100,label:"Use 0–100"},
    hrv: {min:1,max:200,label:"Use a realistic HRV"},
    restingHr: {min:30,max:120,label:"Use 30–120"},
    bodyBattery: {min:0,max:100,label:"Use 0–100"},
    respiration: {min:5,max:30,label:"Use 5–30"},
    pulseOx: {min:70,max:100,label:"Use 70–100"},
    saunaMinutes: {min:1,max:120,label:"Use 1–120"},
  };

  const TYPE_FIELDS = {
    morning: ["sleepScore","hrv","restingHr","bodyBattery","respiration","pulseOx","energy","stress","muscleSoreness","jointSoreness","jointStiffness","notes"],
    bedtime: ["energy","stress","muscleSoreness","jointSoreness","jointStiffness","notes"],
    sauna: ["saunaMinutes","redLightUsed","notes"]
  };

  function waitForApp() {
    if (typeof renderAll !== "function" || typeof getFormData !== "function") {
      setTimeout(waitForApp, 150);
      return;
    }

    const versionEl = document.querySelector(".version");
    if (versionEl && /version v\d+/i.test(versionEl.textContent)) {
      versionEl.textContent = "version v25";
    }

    installEntryTypeUI();
    installValidationUI();
    wrapFormData();
    wrapTodayRender();
    wrapHistoryRender();
    patchExistingEntries();
    bindFormValidation();

    setTimeout(() => {
      try { renderAll(); } catch (e) { console.error("renderAll failed in v25 patch", e); }
    }, 50);
  }

  function patchExistingEntries() {
    if (!Array.isArray(window.entries)) return;
    let changed = false;
    window.entries = window.entries.map(e => {
      if (!e.entryType) {
        changed = true;
        let entryType = "morning";
        if (e.timeOfDay === "post_sauna") entryType = "bedtime";
        if (e.saunaMinutes !== "" && e.saunaMinutes != null) entryType = "sauna";
        return {...e, entryType};
      }
      return e;
    });
    if (changed && typeof saveEntries === "function") saveEntries();
  }

  function installEntryTypeUI() {
    const form = document.getElementById("entryForm");
    if (!form || document.getElementById("entryTypeBar")) return;

    const bar = document.createElement("div");
    bar.id = "entryTypeBar";
    bar.className = "entry-type-bar";
    bar.innerHTML = `
      <button type="button" class="entry-type-btn active" data-entry-type="morning">Morning</button>
      <button type="button" class="entry-type-btn" data-entry-type="bedtime">Bedtime</button>
      <button type="button" class="entry-type-btn" data-entry-type="sauna">Sauna</button>
    `;
    form.insertBefore(bar, form.firstChild);

    bar.querySelectorAll(".entry-type-btn").forEach(btn => {
      btn.addEventListener("click", () => setEntryType(btn.dataset.entryType));
    });

    const timeSel = document.getElementById("timeOfDay");
    if (timeSel) {
      const wrap = timeSel.closest("div");
      if (wrap) wrap.style.display = "none";
    }
    setEntryType("morning");
  }

  function installValidationUI() {
    Object.keys(FIELD_RULES).forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const wrap = el.closest("div");
      if (!wrap || wrap.querySelector(".field-error")) return;
      const err = document.createElement("div");
      err.className = "field-error";
      err.textContent = FIELD_RULES[id].label;
      wrap.appendChild(err);
    });
  }

  function setEntryType(type) {
    window.currentEntryType = type;
    document.querySelectorAll(".entry-type-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.entryType === type);
    });

    const allowed = new Set(TYPE_FIELDS[type] || []);
    const all = ["saunaMinutes","sleepScore","sleepSelf","hrv","restingHr","bodyBattery","respiration","pulseOx","energy","stress","muscleSoreness","jointSoreness","jointStiffness","notes","redLightUsed"];

    all.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      let wrap = el.closest("div");
      if (id === "redLightUsed") wrap = el.closest(".switch-row");
      if (!wrap) return;
      wrap.style.display = allowed.has(id) ? "" : "none";
    });

    if (type !== "sauna") {
      const sauna = document.getElementById("saunaMinutes");
      const red = document.getElementById("redLightUsed");
      if (sauna) sauna.value = "";
      if (red) red.checked = false;
    }
  }

  function validateField(id) {
    const el = document.getElementById(id);
    const rule = FIELD_RULES[id];
    if (!el || !rule) return true;
    const wrap = el.closest("div");
    if (!wrap) return true;

    if (wrap.style.display === "none") {
      wrap.classList.remove("field-invalid");
      return true;
    }

    const value = el.value;
    if (value === "") {
      wrap.classList.remove("field-invalid");
      return true;
    }

    const n = Number(value);
    const ok = !Number.isNaN(n) && n >= rule.min && n <= rule.max;
    wrap.classList.toggle("field-invalid", !ok);
    return ok;
  }

  function validateForm() {
    const ids = Object.keys(FIELD_RULES);
    let ok = true;
    ids.forEach(id => { if (!validateField(id)) ok = false; });

    const saveBtn = document.querySelector('#entryForm button[type="submit"]');
    if (saveBtn) saveBtn.disabled = !ok;
    return ok;
  }

  function bindFormValidation() {
    Object.keys(FIELD_RULES).forEach(id => {
      const el = document.getElementById(id);
      if (!el || el.dataset.v25Bound) return;
      el.addEventListener("input", () => validateForm());
      el.addEventListener("blur", () => validateForm());
      el.dataset.v25Bound = "1";
    });

    const form = document.getElementById("entryForm");
    if (form && !form.dataset.v25SubmitBound) {
      form.addEventListener("submit", (e) => {
        if (!validateForm()) {
          e.preventDefault();
          alert("Fix highlighted fields before saving.");
        }
      }, true);
      form.dataset.v25SubmitBound = "1";
    }
  }

  function wrapFormData() {
    if (window.__v25WrappedGetFormData) return;
    const original = getFormData;
    window.getFormData = function () {
      const data = original();
      data.entryType = window.currentEntryType || "morning";
      if (data.entryType === "morning") data.timeOfDay = "morning";
      if (data.entryType === "bedtime") data.timeOfDay = "post_sauna";
      if (data.entryType === "sauna") data.timeOfDay = "other";
      return data;
    };
    window.__v25WrappedGetFormData = true;
  }

  function saunaEntryForToday() {
    if (!Array.isArray(window.entries)) return null;
    const today = new Date().toISOString().slice(0,10);
    return window.entries.find(e => e.date === today && e.entryType === "sauna") || null;
  }

  function morningEntryForToday() {
    if (!Array.isArray(window.entries)) return null;
    const today = new Date().toISOString().slice(0,10);
    return window.entries.find(e => e.date === today && e.entryType === "morning") || null;
  }

  function bedtimeEntryForToday() {
    if (!Array.isArray(window.entries)) return null;
    const today = new Date().toISOString().slice(0,10);
    return window.entries.find(e => e.date === today && e.entryType === "bedtime") || null;
  }

  function wrapTodayRender() {
    if (window.__v25WrappedRenderToday) return;
    const original = renderToday;
    window.renderToday = function () {
      original();
      injectSaunaStatus();
      stripSubjectiveBadges();
      renameTodayCards();
    };
    window.__v25WrappedRenderToday = true;
  }

  function renameTodayCards() {
    const cols = document.querySelectorAll(".today-slot h4");
    cols.forEach(h => {
      if (h.textContent.includes("Night")) h.textContent = "Bedtime";
    });
  }

  function injectSaunaStatus() {
    const todayGrid = document.querySelector(".today-grid");
    if (!todayGrid) return;
    let box = document.getElementById("saunaTodayBox");
    if (!box) {
      box = document.createElement("div");
      box.id = "saunaTodayBox";
      box.className = "sauna-status";
      todayGrid.insertBefore(box, todayGrid.children[1] || null);
    }

    const sauna = saunaEntryForToday();
    if (!sauna) {
      box.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
          <h4>Sauna Today</h4>
          <button type="button" onclick="openCreateForSauna()">Add</button>
        </div>
        <div class="sauna-status-main">No session</div>
        <div class="sauna-status-sub">No sauna entry logged for today.</div>
      `;
    } else {
      box.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
          <h4>Sauna Today</h4>
          <button type="button" onclick="startEdit('${sauna.id}')">Edit</button>
        </div>
        <div class="sauna-status-main">${sauna.saunaMinutes || "—"} min</div>
        <div class="sauna-status-sub">Red light: ${sauna.redLightUsed ? "Yes" : "No"}</div>
        ${sauna.notes ? `<div class="today-note">${escapeHtml(sauna.notes)}</div>` : ""}
      `;
    }
  }

  window.openCreateForSauna = function () {
    resetForm();
    setEntryType("sauna");
    openModal("entryModal");
  };

  function stripSubjectiveBadges() {
    document.querySelectorAll(".secondary-metric").forEach(card => {
      const label = card.querySelector(".secondary-head span")?.textContent?.trim() || "";
      if (["Energy","Stress","Joint stiffness"].includes(label)) {
        const badge = card.querySelector(".delta");
        if (badge) badge.remove();
      }
    });
  }

  function wrapHistoryRender() {
    if (window.__v25WrappedRenderHistory) return;
    const original = renderHistory;
    window.renderHistory = function () {
      original();
      document.querySelectorAll(".history-item").forEach(item => {
        const txt = item.querySelector(".history-date");
        if (!txt) return;
        if (txt.textContent.includes("post sauna")) txt.textContent = txt.textContent.replace("post sauna", "bedtime");
      });
    };
    window.__v25WrappedRenderHistory = true;
  }

  const originalResetForm = window.resetForm;
  window.resetForm = function () {
    originalResetForm();
    setEntryType("morning");
    validateForm();
  };

  const originalStartEdit = window.startEdit;
  window.startEdit = function (id) {
    originalStartEdit(id);
    const entry = window.entries.find(e => e.id === id);
    setEntryType(entry?.entryType || (entry?.timeOfDay === "post_sauna" ? "bedtime" : (entry?.saunaMinutes !== "" && entry?.saunaMinutes != null ? "sauna" : "morning")));
    validateForm();
  };

  waitForApp();
})();
</script>
<!-- V25_RUNTIME_PATCH_END -->
"""

html = remove_block(html, start_marker, end_marker)

if "</body>" not in html:
    print("Could not find </body> in index.html")
    sys.exit(1)

html = html.replace("</body>", patch + "\n</body>")
index.write_text(html, encoding="utf-8")

print("Applied runtime patch v25 to index.html")