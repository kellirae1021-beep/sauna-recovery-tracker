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

start_marker = "<!-- V26_RUNTIME_PATCH_START -->"
end_marker = "<!-- V26_RUNTIME_PATCH_END -->"

patch = r"""
<!-- V26_RUNTIME_PATCH_START -->
<style>
  @media (min-width: 980px) {
    .today-grid.v26-layout {
      grid-template-columns: 1fr 1fr 1fr !important;
      align-items: start;
    }
  }
  .today-grid.v26-layout > * {
    align-self: start;
  }
  .history-group-block {
    display: grid;
    gap: 6px;
    margin-top: 8px;
  }
  .history-group-title {
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .04em;
  }
  .history-group-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>

<script>
(function () {
  function waitForApp() {
    if (typeof renderAll !== "function") {
      setTimeout(waitForApp, 150);
      return;
    }

    const versionEl = document.querySelector(".version");
    if (versionEl && /version v\d+/i.test(versionEl.textContent)) {
      versionEl.textContent = "version v26";
    }

    wrapTodayRender();
    wrapHistoryRender();
    wrapEntryTypeSetter();
    disableBadSupplementalHover();

    setTimeout(() => {
      try { renderAll(); } catch (e) { console.error("renderAll failed in v26 patch", e); }
    }, 50);
  }

  function wrapTodayRender() {
    if (window.__v26WrappedRenderToday) return;
    const original = renderToday;
    window.renderToday = function () {
      original();

      const grid = document.querySelector(".today-grid");
      if (grid) {
        grid.classList.add("v26-layout");

        const morning = findCardByHeading("Morning");
        const sauna = document.getElementById("saunaTodayBox");
        const bedtime = findCardByHeading("Bedtime");

        if (morning && sauna && bedtime) {
          grid.innerHTML = "";
          grid.appendChild(morning);
          grid.appendChild(sauna);
          grid.appendChild(bedtime);
        }
      }
    };
    window.__v26WrappedRenderToday = true;
  }

  function findCardByHeading(text) {
    const cards = Array.from(document.querySelectorAll(".today-slot, .sauna-status"));
    return cards.find(card => {
      const h = card.querySelector("h4");
      return h && h.textContent.trim() === text;
    }) || null;
  }

  function wrapEntryTypeSetter() {
    if (typeof window.setEntryType !== "function" || window.__v26WrappedSetEntryType) return;

    const original = window.setEntryType;
    window.setEntryType = function (type) {
      original(type);
      const modal = document.querySelector("#entryModal .modal");
      if (modal) modal.scrollTop = 0;
    };
    window.__v26WrappedSetEntryType = true;
  }

  function mergeEntries(entries) {
    const map = new Map();

    entries.forEach(entry => {
      const type = entry.entryType || (entry.timeOfDay === "post_sauna" ? "bedtime" : (entry.saunaMinutes !== "" && entry.saunaMinutes != null ? "sauna" : "morning"));
      const key = `${entry.date}__${type}`;

      if (!map.has(key)) {
        map.set(key, {...entry, entryType: type});
        return;
      }

      const existing = map.get(key);
      const merged = {...existing};

      Object.keys(entry).forEach(k => {
        const v = entry[k];
        if (v !== "" && v != null && v !== false) {
          merged[k] = v;
        }
      });

      if (existing.notes && entry.notes && existing.notes !== entry.notes) {
        merged.notes = `${existing.notes} | ${entry.notes}`;
      }

      map.set(key, merged);
    });

    return Array.from(map.values()).sort((a,b)=>b.date.localeCompare(a.date));
  }

  function renderGroupedHistoryMetrics(entry) {
    const recovery = [
      ["😴 Sleep", entry.sleepScore],
      ["📉 HRV", entry.hrv],
      ["❤️ RHR", entry.restingHr],
      ["🔋 Body Battery", entry.bodyBattery],
      ["🫁 Resp", entry.respiration],
      ["🩸 Pulse Ox", entry.pulseOx]
    ].filter(([,v]) => v !== "" && v != null);

    const subjective = [
      ["⚡ Energy", entry.energy],
      ["🧠 Stress", entry.stress],
      ["💪 Muscle", entry.muscleSoreness],
      ["🦴 Joint soreness", entry.jointSoreness],
      ["🪵 Joint stiffness", entry.jointStiffness],
      ["🛌 Self Sleep", entry.sleepSelf]
    ].filter(([,v]) => v !== "" && v != null);

    const session = [
      ["🔥 Sauna", entry.saunaMinutes !== "" && entry.saunaMinutes != null ? `${entry.saunaMinutes}m` : ""],
      ["🔴 Red light", entry.redLightUsed ? "Yes" : ""]
    ].filter(([,v]) => v !== "" && v != null);

    const groups = [
      ["Recovery", recovery],
      ["Subjective", subjective],
      ["Session", session]
    ].filter(([,items]) => items.length);

    return groups.map(([label, items]) => `
      <div class="history-group-block">
        <div class="history-group-title">${label}</div>
        <div class="history-group-metrics">
          ${items.map(([k,v]) => `<div class="metric">${k} ${v}</div>`).join("")}
        </div>
      </div>
    `).join("");
  }

  function wrapHistoryRender() {
    if (window.__v26WrappedRenderHistory) return;
    const original = renderHistory;
    window.renderHistory = function () {
      if (!Array.isArray(window.entries)) {
        original();
        return;
      }

      const holder = document.getElementById("historyList");
      if (!holder) {
        original();
        return;
      }

      const merged = mergeEntries(window.entries);

      if (!merged.length) {
        holder.innerHTML = '<div class="empty">No entries yet.</div>';
        return;
      }

      holder.innerHTML = merged.map(entry => {
        const type = entry.entryType || "morning";
        const typeLabel = type === "post_sauna" ? "bedtime" : type;
        const dateText = typeof longDate === "function" ? longDate(entry.date) : entry.date;
        const note = entry.notes ? `<div class="history-note">${typeof escapeHtml === "function" ? escapeHtml(entry.notes) : entry.notes}</div>` : "";

        return `
          <div class="history-item">
            <div class="history-head">
              <div>
                <div class="history-date">${dateText} · ${typeLabel}</div>
                ${renderGroupedHistoryMetrics(entry)}
              </div>
              <div style="display:flex;gap:6px;flex-wrap:wrap">
                <button onclick="startEdit('${entry.id}')">Edit</button>
              </div>
            </div>
            ${note}
          </div>
        `;
      }).join("");
    };
    window.__v26WrappedRenderHistory = true;
  }

  function disableBadSupplementalHover() {
    if (window.__v26HoverGuard) return;
    window.__v26HoverGuard = true;

    const originalRenderCharts = window.renderCharts;
    if (!originalRenderCharts || window.__v26WrappedRenderCharts) return;

    window.renderCharts = function () {
      originalRenderCharts();
      setTimeout(() => {
        const tt = document.getElementById("chartTooltip");
        const supplemental = document.getElementById("supplementalChart");
        if (!supplemental) return;

        supplemental.querySelectorAll("circle").forEach(pt => {
          pt.onmouseenter = null;
          pt.onmouseleave = null;
        });

        supplemental.addEventListener("mouseenter", hideTooltip, true);
      }, 40);
    };

    function hideTooltip() {
      const tt = document.getElementById("chartTooltip");
      if (tt) tt.style.display = "none";
    }

    window.__v26WrappedRenderCharts = true;
  }

  waitForApp();
})();
</script>
<!-- V26_RUNTIME_PATCH_END -->
"""

html = remove_block(html, start_marker, end_marker)

if "</body>" not in html:
    print("Could not find </body> in index.html")
    sys.exit(1)

html = html.replace("</body>", patch + "\n</body>")
index.write_text(html, encoding="utf-8")

print("Applied runtime patch v26 to index.html")