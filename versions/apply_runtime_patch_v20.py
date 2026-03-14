from pathlib import Path
import sys

index = Path("index.html")
if not index.exists():
    print("index.html not found")
    sys.exit(1)

html = index.read_text(encoding="utf-8")

start_marker = "<!-- V20_RUNTIME_PATCH_START -->"
end_marker = "<!-- V20_RUNTIME_PATCH_END -->"

patch = r"""
<!-- V20_RUNTIME_PATCH_START -->
<script>
(function () {
  function waitForApp() {
    if (typeof renderCharts !== "function") {
      setTimeout(waitForApp, 150);
      return;
    }

    const versionEl = document.querySelector(".version");
    if (versionEl && /version v\d+/i.test(versionEl.textContent)) {
      versionEl.textContent = "version v20";
    }

    const status = document.getElementById("garminStatus");
    if (status) status.textContent = "Last 90d";

    installRangeOptions();
    wrapRenderCharts();

    if (typeof chartRange !== "undefined") {
      chartRange = "7";
    }

    syncRangeControls("7");

    setTimeout(() => {
      try {
        renderCharts();
      } catch (e) {
        console.error("renderCharts failed in v20 patch", e);
      }
      setTimeout(postProcessCharts, 40);
    }, 40);
  }

  function installRangeOptions() {
    const selects = Array.from(document.querySelectorAll("select"))
      .filter(s => s.id === "rangeFilter" || s.id === "rangeFilterLocal");

    selects.forEach(select => {
      if (!select.querySelector('option[value="7"]')) {
        const opt = document.createElement("option");
        opt.value = "7";
        opt.textContent = "7 days";
        select.insertBefore(opt, select.firstChild);
      }

      select.value = "7";

      if (!select.dataset.v20Bound) {
        select.addEventListener("change", () => {
          const val = select.value;
          if (typeof chartRange !== "undefined") {
            chartRange = val;
          }
          syncRangeControls(val, select);
          renderCharts();
          setTimeout(postProcessCharts, 40);
        });
        select.dataset.v20Bound = "1";
      }
    });
  }

  function syncRangeControls(value, source) {
    const selects = Array.from(document.querySelectorAll("select"))
      .filter(s => s.id === "rangeFilter" || s.id === "rangeFilterLocal");

    selects.forEach(select => {
      if (select !== source) {
        select.value = value;
      }
    });
  }

  function wrapRenderCharts() {
    if (window.__v20WrappedRenderCharts) return;

    const originalRenderCharts = renderCharts;
    renderCharts = function () {
      originalRenderCharts();
      setTimeout(postProcessCharts, 40);
    };

    window.__v20WrappedRenderCharts = true;
  }

  function getTickStep() {
    const value = typeof chartRange === "undefined" ? "7" : String(chartRange);
    if (value === "7") return 1;
    if (value === "28") return 7;
    if (value === "90") return 14;
    if (value === "180") return 21;
    if (value === "365") return 30;
    if (value === "all") return 90;
    return 7;
  }

  function postProcessCharts() {
    const step = getTickStep();
    const svgs = document.querySelectorAll(".chart-svg");

    svgs.forEach(svg => {
      const texts = Array.from(svg.querySelectorAll("text"));

      const bottomTexts = texts.filter(t => {
        const y = Number(t.getAttribute("y") || 0);
        return y >= 250;
      });

      const byX = new Map();
      bottomTexts.forEach(t => {
        const x = t.getAttribute("x");
        if (!byX.has(x)) byX.set(x, []);
        byX.get(x).push(t);
      });

      const groups = Array.from(byX.entries()).sort((a, b) => Number(a[0]) - Number(b[0]));

      groups.forEach(([_, nodes], i) => {
        const keep = (i % step === 0) || i === groups.length - 1;
        nodes.forEach(node => {
          node.style.display = keep ? "" : "none";
        });
      });

      const paths = Array.from(svg.querySelectorAll("path"));
      paths.forEach(p => {
        const opacity = p.getAttribute("opacity");
        if (opacity && Number(opacity) < 1) {
          p.setAttribute("opacity", "0.14");
        }
      });
    });
  }

  waitForApp();
})();
</script>
<!-- V20_RUNTIME_PATCH_END -->
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

print("Applied runtime patch v20 to index.html")