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

start_marker = "<!-- V24_RUNTIME_PATCH_START -->"
end_marker = "<!-- V24_RUNTIME_PATCH_END -->"

patch = r"""
<!-- V24_RUNTIME_PATCH_START -->
<script>
(function () {
  function waitForApp() {
    if (typeof renderAll !== "function") {
      setTimeout(waitForApp, 150);
      return;
    }

    const versionEl = document.querySelector(".version");
    if (versionEl && /version v\d+/i.test(versionEl.textContent)) {
      versionEl.textContent = "version v24";
    }

    installValidation();
    wrapEntrySubmit();
    sanitizeExistingEntries();

    setTimeout(() => {
      try {
        renderAll();
      } catch (e) {
        console.error("renderAll failed in v24 patch", e);
      }
    }, 40);
  }

  function installValidation() {
    const rules = [
      ["sleepSelf", 1, 10, true],
      ["energy", 1, 10, true],
      ["stress", 1, 10, true],
      ["muscleSoreness", 1, 10, true],
      ["jointSoreness", 1, 10, true],
      ["jointStiffness", 1, 10, true],
      ["sleepScore", 0, 100, false],
      ["hrv", 1, 200, false],
      ["restingHr", 30, 120, false],
      ["bodyBattery", 0, 100, false],
      ["respiration", 5, 30, false],
      ["pulseOx", 70, 100, false],
      ["saunaMinutes", 0, 120, false],
    ];

    rules.forEach(([id, min, max, integerOnly]) => {
      const input = document.getElementById(id);
      if (!input) return;

      input.setAttribute("min", String(min));
      input.setAttribute("max", String(max));
      if (integerOnly) input.setAttribute("step", "1");

      if (!input.dataset.v24Bound) {
        input.addEventListener("blur", () => clampInput(input, min, max, integerOnly));
        input.addEventListener("change", () => clampInput(input, min, max, integerOnly));
        input.dataset.v24Bound = "1";
      }
    });
  }

  function clampInput(input, min, max, integerOnly) {
    if (!input || input.value === "") return;

    let n = Number(input.value);
    if (Number.isNaN(n)) {
      input.value = "";
      return;
    }

    if (integerOnly) n = Math.round(n);
    if (n < min) n = min;
    if (n > max) n = max;

    input.value = integerOnly ? String(Math.round(n)) : String(n);
  }

  function sanitizeEntry(entry) {
    const sanitize = (value, min, max, integerOnly=false) => {
      if (value === "" || value == null) return "";
      let n = Number(value);
      if (Number.isNaN(n)) return "";
      if (integerOnly) n = Math.round(n);
      if (n < min || n > max) return "";
      return integerOnly ? Math.round(n) : n;
    };

    return {
      ...entry,
      sleepSelf: sanitize(entry.sleepSelf, 1, 10, true),
      energy: sanitize(entry.energy, 1, 10, true),
      stress: sanitize(entry.stress, 1, 10, true),
      muscleSoreness: sanitize(entry.muscleSoreness, 1, 10, true),
      jointSoreness: sanitize(entry.jointSoreness, 1, 10, true),
      jointStiffness: sanitize(entry.jointStiffness, 1, 10, true),
      sleepScore: sanitize(entry.sleepScore, 0, 100, true),
      hrv: sanitize(entry.hrv, 1, 200, false),
      restingHr: sanitize(entry.restingHr, 30, 120, false),
      bodyBattery: sanitize(entry.bodyBattery, 0, 100, true),
      respiration: sanitize(entry.respiration, 5, 30, false),
      pulseOx: sanitize(entry.pulseOx, 70, 100, false),
      saunaMinutes: sanitize(entry.saunaMinutes, 0, 120, true),
    };
  }

  function sanitizeExistingEntries() {
    if (!Array.isArray(window.entries)) return;
    window.entries = window.entries.map(sanitizeEntry);

    if (typeof saveEntries === "function") {
      try {
        saveEntries();
      } catch (e) {
        console.error("saveEntries failed during v24 sanitize", e);
      }
    }
  }

  function wrapEntrySubmit() {
    const form = document.getElementById("entryForm");
    if (!form || form.dataset.v24Wrapped) return;

    form.addEventListener("submit", function () {
      setTimeout(() => {
        if (Array.isArray(window.entries)) {
          window.entries = window.entries.map(sanitizeEntry);
          if (typeof saveEntries === "function") {
            try {
              saveEntries();
            } catch (e) {
              console.error("saveEntries failed after submit", e);
            }
          }
          if (typeof renderAll === "function") {
            renderAll();
          }
        }
      }, 0);
    });

    form.dataset.v24Wrapped = "1";
  }

  waitForApp();
})();
</script>
<!-- V24_RUNTIME_PATCH_END -->
"""

html = remove_block(html, start_marker, end_marker)

if "</body>" not in html:
    print("Could not find </body> in index.html")
    sys.exit(1)

html = html.replace("</body>", patch + "\n</body>")
index.write_text(html, encoding="utf-8")

print("Applied runtime patch v24 to index.html")