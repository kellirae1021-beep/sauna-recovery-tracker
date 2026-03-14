from pathlib import Path
import sys

index = Path("index.html")
if not index.exists():
    print("index.html not found")
    sys.exit(1)

html = index.read_text(encoding="utf-8")

start_marker = "<!-- V21_RUNTIME_PATCH_START -->"
end_marker = "<!-- V21_RUNTIME_PATCH_END -->"

patch = r"""
<!-- V21_RUNTIME_PATCH_START -->
<script>
(function () {
  function waitForApp() {
    if (typeof renderAll !== "function") {
      setTimeout(waitForApp, 150);
      return;
    }

    const versionEl = document.querySelector(".version");
    if (versionEl && /version v\d+/i.test(versionEl.textContent)) {
      versionEl.textContent = "version v21";
    }

    installSmarterDisplay();
    wrapRenderAll();

    setTimeout(() => {
      try {
        renderAll();
      } catch (e) {
        console.error("renderAll failed in v21 patch", e);
      }
    }, 40);
  }

  function wrapRenderAll() {
    if (window.__v21WrappedRenderAll) return;

    const originalRenderAll = renderAll;
    renderAll = function () {
      originalRenderAll();
      setTimeout(postProcessDisplay, 30);
    };

    window.__v21WrappedRenderAll = true;
  }

  function installSmarterDisplay() {
    window.__v21RoundDisplay = function(value, mode) {
      if (value == null || value === "" || Number.isNaN(Number(value))) return "—";
      const n = Number(value);

      if (mode === "int") return String(Math.round(n));
      if (mode === "bpm") return `${Math.round(n)} bpm`;
      if (mode === "pct") return `${Math.round(n)}%`;
      if (mode === "one") return (Math.round(n * 10) / 10).toFixed(1).replace(/\.0$/, "");
      return String(n);
    };

    window.__v21DeltaChip = function(kind, value, baseline) {
      const neutral = '<span class="delta neutral">—</span>';

      if (value == null || value === "" || Number.isNaN(Number(value))) return neutral;

      const v = Number(value);

      if (kind === "range") {
        if (!baseline || baseline.low == null || baseline.high == null) return neutral;
        const low = Number(baseline.low);
        const high = Number(baseline.high);
        if (v >= low && v <= high) return '<span class="delta good">in range</span>';
        if (v < low) return '<span class="delta bad">below range</span>';
        return '<span class="delta bad">above range</span>';
      }

      if (baseline == null || baseline === "" || Number.isNaN(Number(baseline))) return neutral;

      const b = Number(baseline);
      const diff = v - b;
      const absDiff = Math.abs(diff);

      if (kind === "higher_better") {
        const threshold = getThreshold(kind, b);
        if (absDiff < threshold) return '<span class="delta neutral">near base</span>';
        return diff > 0
          ? '<span class="delta good">above base</span>'
          : '<span class="delta bad">below base</span>';
      }

      if (kind === "lower_better") {
        const threshold = getThreshold(kind, b);
        if (absDiff < threshold) return '<span class="delta neutral">near base</span>';
        return diff < 0
          ? '<span class="delta good">below base</span>'
          : '<span class="delta bad">above base</span>';
      }

      return neutral;
    };

    function getThreshold(kind, baseline) {
      if (kind === "higher_better" || kind === "lower_better") {
        if (baseline <= 10) return 0.6;      // subjective scales
        if (baseline <= 25) return 1.0;      // respiration-ish
        if (baseline <= 60) return 2.0;      // HRV / smaller physiological values
        return 3.0;                          // sleep, body battery, pulse ox
      }
      return 1.0;
    }
  }

  function postProcessDisplay() {
    roundBaselineCards();
    replaceTodayBadgeText();
    tightenChartSubtext();
  }

  function roundBaselineCards() {
    const cards = Array.from(document.querySelectorAll("#baselineCards .baseline"));
    cards.forEach(card => {
      const labelEl = card.childNodes[0];
      const valueEl = card.querySelector("b");
      if (!valueEl) return;

      const label = (labelEl?.textContent || card.textContent || "").trim();

      if (/Sleep/i.test(label)) {
        valueEl.textContent = roundFromText(valueEl.textContent, "int");
      } else if (/Resting HR/i.test(label)) {
        valueEl.textContent = roundFromText(valueEl.textContent, "bpm");
      } else if (/HRV range/i.test(label)) {
        valueEl.textContent = roundRangeText(valueEl.textContent);
      } else if (/SpO2/i.test(label)) {
        valueEl.textContent = roundFromText(valueEl.textContent, "pct");
      } else if (/Body Battery/i.test(label)) {
        valueEl.textContent = roundFromText(valueEl.textContent, "int");
      }
    });
  }

  function roundFromText(text, mode) {
    const m = String(text).match(/-?\d+(\.\d+)?/);
    if (!m) return text;
    const n = Number(m[0]);
    if (mode === "int") return String(Math.round(n));
    if (mode === "bpm") return `${Math.round(n)} bpm`;
    if (mode === "pct") return `${Math.round(n)}%`;
    return text;
  }

  function roundRangeText(text) {
    const nums = String(text).match(/-?\d+(\.\d+)?/g);
    if (!nums || nums.length < 2) return text;
    return `${Math.round(Number(nums[0]))}–${Math.round(Number(nums[1]))}`;
  }

  function replaceTodayBadgeText() {
    if (typeof window.deltaChip !== "function") return;

    window.deltaChip = function(kind, value, baseline) {
      return window.__v21DeltaChip(kind, value, baseline);
    };

    if (typeof window.formatVal === "function") {
      const originalFormatVal = window.formatVal;
      if (!window.__v21WrappedFormatVal) {
        window.formatVal = function(v) {
          return originalFormatVal(v);
        };
        window.__v21WrappedFormatVal = true;
      }
    }
  }

  function tightenChartSubtext() {
    const subs = Array.from(document.querySelectorAll(".chart-sub"));
    subs.forEach(el => {
      if (/Baselines use the last 365 days/i.test(el.textContent)) {
        el.textContent = "Manual entries overlaid on Garmin history. Baselines use the last 90 days.";
      }
    });
  }

  waitForApp();
})();
</script>
<!-- V21_RUNTIME_PATCH_END -->
"""

if start_marker in html and end_marker in html:
    start = html.index(start_marker)
    end = html.index(end_marker) + len(end_marker)
    html = html[:start] + html[end:]

if "</body>" not in html:
    print("Could not find </body> in index.html")
    sys.exit(1)

html = html.replace("</body>", patch + "\n</body>")
index.write_text(html, encoding="utf-8")

print("Applied runtime patch v21 to index.html")