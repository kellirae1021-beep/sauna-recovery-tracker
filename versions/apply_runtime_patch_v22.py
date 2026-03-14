from pathlib import Path
import sys

index = Path("index.html")
if not index.exists():
    print("index.html not found")
    sys.exit(1)

html = index.read_text(encoding="utf-8")

start_marker = "<!-- V22_RUNTIME_PATCH_START -->"
end_marker = "<!-- V22_RUNTIME_PATCH_END -->"

patch = r"""
<!-- V22_RUNTIME_PATCH_START -->
<style>
  .chart-tooltip{
    position:fixed;
    z-index:9999;
    pointer-events:none;
    background:#221b29;
    color:#fff;
    border-radius:10px;
    padding:8px 10px;
    font-size:12px;
    line-height:1.3;
    box-shadow:0 8px 20px rgba(34,27,41,.25);
    display:none;
    max-width:220px;
  }
  .chart-tooltip .tt-label{
    font-weight:700;
    margin-bottom:2px;
  }
  .legend-item.is-dimmed{
    opacity:.35;
  }
</style>

<script>
(function () {
  function waitForApp() {
    if (typeof renderCharts !== "function") {
      setTimeout(waitForApp, 150);
      return;
    }

    const versionEl = document.querySelector(".version");
    if (versionEl && /version v\d+/i.test(versionEl.textContent)) {
      versionEl.textContent = "version v22";
    }

    installTooltip();
    wrapRenderCharts();

    setTimeout(() => {
      try {
        renderCharts();
      } catch (e) {
        console.error("renderCharts failed in v22 patch", e);
      }
      setTimeout(postProcessCharts, 50);
    }, 50);
  }

  function installTooltip() {
    if (document.getElementById("chartTooltip")) return;
    const div = document.createElement("div");
    div.id = "chartTooltip";
    div.className = "chart-tooltip";
    document.body.appendChild(div);
  }

  function showTooltip(x, y, label, date, value) {
    const tt = document.getElementById("chartTooltip");
    if (!tt) return;
    tt.innerHTML = `
      <div class="tt-label">${label}</div>
      <div>${date}</div>
      <div>Value: ${value}</div>
    `;
    tt.style.display = "block";
    tt.style.left = (x + 14) + "px";
    tt.style.top = (y + 14) + "px";
  }

  function hideTooltip() {
    const tt = document.getElementById("chartTooltip");
    if (!tt) return;
    tt.style.display = "none";
  }

  function wrapRenderCharts() {
    if (window.__v22WrappedRenderCharts) return;

    const originalRenderCharts = renderCharts;
    renderCharts = function () {
      originalRenderCharts();
      setTimeout(postProcessCharts, 50);
    };

    window.__v22WrappedRenderCharts = true;
  }

  function postProcessCharts() {
    fixSubjectiveChartClipping();
    improveSupplementalChart();
  }

  function fixSubjectiveChartClipping() {
    const subjective = document.getElementById("subjectiveChart");
    if (!subjective) return;

    const points = Array.from(subjective.querySelectorAll("circle"));
    points.forEach(pt => {
      const cy = Number(pt.getAttribute("cy") || 0);
      if (cy < 0) pt.setAttribute("cy", "0");
    });

    const texts = Array.from(subjective.querySelectorAll("text"));
    texts.forEach(t => {
      const y = Number(t.getAttribute("y") || 0);
      const text = (t.textContent || "").trim();
      const numeric = Number(text);

      if (!Number.isNaN(numeric) && numeric > 10) {
        t.style.display = "none";
      }
      if (y < 8) {
        t.setAttribute("y", "12");
      }
    });

    const paths = Array.from(subjective.querySelectorAll("path"));
    paths.forEach(p => {
      const d = p.getAttribute("d");
      if (!d) return;
      const cleaned = d.replace(/(-?\d+(\.\d+)?) (-?\d+(\.\d+)?)/g, (m, x, y) => {
        const yy = Math.max(0, Math.min(238, Number(y)));
        return `${x} ${yy}`;
      });
      p.setAttribute("d", cleaned);
    });
  }

  function improveSupplementalChart() {
    const svg = document.getElementById("supplementalChart");
    if (!svg) return;

    const lines = Array.from(svg.querySelectorAll("path"));
    const circles = Array.from(svg.querySelectorAll("circle"));

    if (lines.length < 3) return;

    // Distinct visual styles
    const seriesStyles = [
      { label: "Body Battery", dash: "", width: "3", color: "#c06a98" },
      { label: "Respiration", dash: "2 5", width: "3", color: "#8f79a8" },
      { label: "Pulse Ox", dash: "10 5", width: "3", color: "#d8647d" },
    ];

    // Apply styles to the three visible/manual series (usually the later paths)
    const targetLines = lines.slice(-3);
    targetLines.forEach((line, i) => {
      const style = seriesStyles[i];
      line.setAttribute("stroke", style.color);
      line.setAttribute("stroke-width", style.width);
      if (style.dash) line.setAttribute("stroke-dasharray", style.dash);
      else line.removeAttribute("stroke-dasharray");
      line.dataset.seriesLabel = style.label;
      line.style.cursor = "pointer";
    });

    // Better legend
    const section = svg.closest(".card, .chart-box, div");
    const chartBlock = svg.closest("div");
    const legend = svg.parentElement.parentElement.querySelector(".legend");
    if (legend) {
      const items = Array.from(legend.querySelectorAll(".legend-item"));
      items.forEach((item, i) => {
        const swatch = item.querySelector(".swatch");
        if (swatch && seriesStyles[i]) {
          swatch.style.background = seriesStyles[i].color;
          swatch.style.border = "1px solid rgba(0,0,0,.06)";
        }
        item.dataset.seriesLabel = seriesStyles[i] ? seriesStyles[i].label : "";
      });

      items.forEach((item, i) => {
        item.onmouseenter = () => highlightSeries(i);
        item.onmouseleave = () => clearHighlight();
        item.style.cursor = "pointer";
      });
    }

    // Rebind points to nearest series color order
    const visiblePoints = circles.filter(c => {
      const fill = c.getAttribute("fill") || "";
      return fill && fill !== "none";
    });

    const groupedByColor = {};
    visiblePoints.forEach(c => {
      const fill = c.getAttribute("fill");
      if (!groupedByColor[fill]) groupedByColor[fill] = [];
      groupedByColor[fill].push(c);
    });

    const pointGroups = Object.values(groupedByColor).sort((a,b)=>a.length-b.length).slice(-3);
    pointGroups.forEach((group, i) => {
      const style = seriesStyles[i];
      group.forEach(pt => {
        pt.setAttribute("fill", style.color);
        pt.dataset.seriesLabel = style.label;
        pt.style.cursor = "pointer";
      });
    });

    // Right-edge labels
    Array.from(svg.querySelectorAll(".v22-end-label")).forEach(n => n.remove());

    pointGroups.forEach((group, i) => {
      const style = seriesStyles[i];
      const sorted = group
        .map(pt => ({
          x: Number(pt.getAttribute("cx") || 0),
          y: Number(pt.getAttribute("cy") || 0),
          value: pt.getAttribute("data-value") || "",
          node: pt,
        }))
        .sort((a,b)=>a.x-b.x);

      const last = sorted[sorted.length - 1];
      if (!last) return;

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "v22-end-label");
      label.setAttribute("x", String(Math.min(885, last.x + 12)));
      label.setAttribute("y", String(last.y - 6));
      label.setAttribute("font-size", "12");
      label.setAttribute("fill", style.color);
      label.textContent = style.label;
      svg.appendChild(label);
    });

    // Hover behavior
    targetLines.forEach((line, i) => {
      line.onmouseenter = (e) => highlightSeries(i);
      line.onmouseleave = clearHighlight;
      line.onclick = () => highlightSeries(i, true);
    });

    pointGroups.forEach((group, i) => {
      const style = seriesStyles[i];
      group.forEach(pt => {
        pt.onmouseenter = (e) => {
          highlightSeries(i);
          const x = e.clientX || 0;
          const y = e.clientY || 0;
          const value = pt.getAttribute("data-value") || "";
          const date = findNearestDateLabel(svg, Number(pt.getAttribute("cx") || 0));
          showTooltip(x, y, style.label, date, value || "—");
        };
        pt.onmouseleave = () => {
          clearHighlight();
          hideTooltip();
        };
      });
    });

    function highlightSeries(activeIndex, sticky) {
      targetLines.forEach((line, idx) => {
        line.setAttribute("opacity", idx === activeIndex ? "1" : "0.12");
      });

      pointGroups.forEach((group, idx) => {
        group.forEach(pt => {
          pt.setAttribute("opacity", idx === activeIndex ? "1" : "0.12");
          const r = idx === activeIndex ? 5 : 3.5;
          pt.setAttribute("r", String(r));
        });
      });

      const legend = svg.parentElement.parentElement.querySelector(".legend");
      if (legend) {
        Array.from(legend.querySelectorAll(".legend-item")).forEach((item, idx) => {
          item.classList.toggle("is-dimmed", idx !== activeIndex);
        });
      }

      Array.from(svg.querySelectorAll(".v22-end-label")).forEach((label, idx) => {
        label.setAttribute("opacity", idx === activeIndex ? "1" : "0.18");
      });
    }

    function clearHighlight() {
      targetLines.forEach(line => line.setAttribute("opacity", "1"));
      pointGroups.forEach(group => {
        group.forEach(pt => {
          pt.setAttribute("opacity", "1");
          pt.setAttribute("r", "3.5");
        });
      });

      const legend = svg.parentElement.parentElement.querySelector(".legend");
      if (legend) {
        Array.from(legend.querySelectorAll(".legend-item")).forEach(item => {
          item.classList.remove("is-dimmed");
        });
      }

      Array.from(svg.querySelectorAll(".v22-end-label")).forEach(label => {
        label.setAttribute("opacity", "1");
      });

      hideTooltip();
    }

    function findNearestDateLabel(svgEl, targetX) {
      const labels = Array.from(svgEl.querySelectorAll("text")).filter(t => {
        const y = Number(t.getAttribute("y") || 0);
        return y >= 250;
      });

      const grouped = new Map();
      labels.forEach(t => {
        const x = Number(t.getAttribute("x") || 0);
        if (!grouped.has(x)) grouped.set(x, []);
        grouped.get(x).push((t.textContent || "").trim());
      });

      let bestX = null;
      let bestDiff = Infinity;
      for (const x of grouped.keys()) {
        const diff = Math.abs(x - targetX);
        if (diff < bestDiff) {
          bestDiff = diff;
          bestX = x;
        }
      }

      if (bestX == null) return "";
      return grouped.get(bestX).join(" ");
    }
  }

  waitForApp();
})();
</script>
<!-- V22_RUNTIME_PATCH_END -->
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

print("Applied runtime patch v22 to index.html")