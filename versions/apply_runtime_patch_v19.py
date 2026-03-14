from pathlib import Path
import sys

index = Path("index.html")
if not index.exists():
    print("index.html not found")
    sys.exit(1)

html = index.read_text(encoding="utf-8")

patch = r"""
<!-- V19_RUNTIME_PATCH_START -->
<script>
(function () {
  function waitForApp() {
    if (typeof renderCharts !== "function") {
      setTimeout(waitForApp, 150);
      return;
    }

    // Set version label if present
    const versionEl = document.querySelector(".version");
    if (versionEl && versionEl.textContent.includes("v18")) {
      versionEl.textContent = "version v19";
    }

    // Keep baseline label as Last 90d
    const status = document.getElementById("garminStatus");
    if (status) status.textContent = "Last 90d";

    // Remove/hide old topbar filter if present
    const oldFilter = document.getElementById("rangeFilter");
    if (oldFilter) {
      const maybeWrapper = oldFilter.closest("div");
      if (maybeWrapper) {
        maybeWrapper.style.display = "none";
      } else {
        oldFilter.style.display = "none";
      }
    }

    // Insert chart-local filter next to Primary recovery
    const primaryTitle = Array.from(document.querySelectorAll(".chart-title"))
      .find(el => el.textContent.trim() === "Primary recovery");

    if (primaryTitle && !document.getElementById("rangeFilterLocal")) {
      const row = document.createElement("div");
      row.style.display = "flex";
      row.style.justifyContent = "space-between";
      row.style.alignItems = "center";
      row.style.gap = "10px";
      row.style.flexWrap = "wrap";
      row.style.marginBottom = "4px";

      const titleClone = primaryTitle.cloneNode(true);

      const filterWrap = document.createElement("div");
      filterWrap.style.display = "flex";
      filterWrap.style.alignItems = "center";
      filterWrap.style.gap = "6px";

      const label = document.createElement("label");
      label.textContent = "Range";
      label.setAttribute("for", "rangeFilterLocal");
      label.style.fontSize = "12px";
      label.style.color = "var(--muted)";

      const select = document.createElement("select");
      select.id = "rangeFilterLocal";
      select.style.width = "auto";
      select.style.padding = "6px 10px";
      select.style.borderRadius = "999px";
      select.innerHTML = `
        <option value="28">4 weeks</option>
        <option value="90">90 days</option>
        <option value="180">6 months</option>
        <option value="365">12 months</option>
        <option value="all">All</option>
      `;

      // sync with app state if present
      if (typeof chartRange !== "undefined") {
        select.value = String(chartRange);
      } else {
        select.value = "28";
      }

      select.addEventListener("change", () => {
        if (typeof chartRange !== "undefined") {
          chartRange = select.value;
        }
        renderCharts();
        setTimeout(postProcessCharts, 30);
      });

      filterWrap.appendChild(label);
      filterWrap.appendChild(select);
      row.appendChild(titleClone);
      row.appendChild(filterWrap);

      primaryTitle.replaceWith(row);
    }

    // Wrap renderCharts so post-processing always runs
    if (!window.__v19WrappedRenderCharts) {
      const originalRenderCharts = renderCharts;
      renderCharts = function () {
        originalRenderCharts();
        setTimeout(postProcessCharts, 20);
      };
      window.__v19WrappedRenderCharts = true;
    }

    // Initial post-process
    setTimeout(postProcessCharts, 30);
  }

  function getTickStep() {
    if (typeof chartRange === "undefined") return 4;
    if (String(chartRange) === "28") return 4;
    if (String(chartRange) === "90") return 10;
    if (String(chartRange) === "180") return 20;
    if (String(chartRange) === "365") return 40;
    if (String(chartRange) === "all") return 90;
    return 4;
  }

  function postProcessCharts() {
    const step = getTickStep();
    const svgs = document.querySelectorAll(".chart-svg");

    svgs.forEach(svg => {
      const texts = Array.from(svg.querySelectorAll("text"));

      // Hide crowded x-axis labels: bottom labels are the ones near the bottom of the SVG
      const bottomTexts = texts.filter(t => {
        const y = Number(t.getAttribute("y") || 0);
        return y >= 260;
      });

      const byX = new Map();
      bottomTexts.forEach(t => {
        const x = t.getAttribute("x");
        if (!byX.has(x)) byX.set(x, []);
        byX.get(x).push(t);
      });

      const groups = Array.from(byX.entries())
        .sort((a, b) => Number(a[0]) - Number(b[0]));

      groups.forEach(([_, nodes], i) => {
        const keep = (i % step === 0) || i === groups.length - 1;
        nodes.forEach(node => {
          node.style.display = keep ? "" : "none";
        });
      });

      // Lighten historical/background lines slightly
      const paths = Array.from(svg.querySelectorAll("path"));
      paths.forEach(p => {
        const opacity = p.getAttribute("opacity");
        if (opacity && Number(opacity) < 1) {
          p.setAttribute("opacity", "0.18");
        }
      });
    });
  }

  waitForApp();
})();
</script>
<!-- V19_RUNTIME_PATCH_END -->
"""

start_marker = "<!-- V19_RUNTIME_PATCH_START -->"
end_marker = "<!-- V19_RUNTIME_PATCH_END -->"

if start_marker in html and end_marker in html:
    start = html.index(start_marker)
    end = html.index(end_marker) + len(end_marker)
    html = html[:start] + html[end:]

if "</body>" not in html:
    print("Could not find </body> in index.html")
    sys.exit(1)

html = html.replace("</body>", patch + "\n</body>")
index.write_text(html, encoding="utf-8")

print("Applied runtime patch v19 to index.html")