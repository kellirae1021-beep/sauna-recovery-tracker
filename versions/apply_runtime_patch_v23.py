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

# Remove v22 completely
html = remove_block(html, "<!-- V22_RUNTIME_PATCH_START -->", "<!-- V22_RUNTIME_PATCH_END -->")

start_marker = "<!-- V23_RUNTIME_PATCH_START -->"
end_marker = "<!-- V23_RUNTIME_PATCH_END -->"

patch = r"""
<!-- V23_RUNTIME_PATCH_START -->
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
      versionEl.textContent = "version v23";
    }

    installTooltip();
    wrapRenderCharts();

    setTimeout(() => {
      try {
        renderCharts();
      } catch (e) {
        console.error("renderCharts failed in v23 patch", e);
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
      <div style="font-weight:700;margin-bottom:2px">${label}</div>
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
    if (window.__v23WrappedRenderCharts) return;

    const originalRenderCharts = renderCharts;
    renderCharts = function () {
      originalRenderCharts();
      setTimeout(postProcessCharts, 50);
    };

    window.__v23WrappedRenderCharts = true;
  }

  function postProcessCharts() {
    enforceSubjectiveChartBounds();
    attachHoverToAllCharts();
  }

  function enforceSubjectiveChartBounds() {
    const svg = document.getElementById("subjectiveChart");
    if (!svg) return;

    // Hide any numeric value labels above 10 for this chart
    Array.from(svg.querySelectorAll("text")).forEach(t => {
      const text = (t.textContent || "").trim();
      const num = Number(text);
      if (!Number.isNaN(num) && num > 10) {
        t.style.display = "none";
      }
    });
  }

  function attachHoverToAllCharts() {
    bindChartHover("primaryChart", ["Sleep", "HRV", "RHR"]);
    bindChartHover("supplementalChart", ["Body Battery", "Respiration", "Pulse Ox"]);
    bindChartHover("subjectiveChart", ["Energy", "Stress", "Avg soreness", "Self Sleep", "Joint Stiffness"]);
  }

  function bindChartHover(svgId, labels) {
    const svg = document.getElementById(svgId);
    if (!svg) return;

    const circles = Array.from(svg.querySelectorAll("circle"));
    if (!circles.length) return;

    // Group by fill color, preserving on-screen order
    const colorGroups = new Map();
    circles.forEach(c => {
      const fill = c.getAttribute("fill") || "";
      if (!fill || fill === "none") return;
      if (!colorGroups.has(fill)) colorGroups.set(fill, []);
      colorGroups.get(fill).push(c);
    });

    const groups = Array.from(colorGroups.values()).sort((a, b) => {
      const ax = Math.min(...a.map(n => Number(n.getAttribute("cx") || 0)));
      const bx = Math.min(...b.map(n => Number(n.getAttribute("cx") || 0)));
      return ax - bx;
    });

    groups.forEach((group, i) => {
      const label = labels[i] || `Series ${i+1}`;

      group.forEach(pt => {
        pt.style.cursor = "pointer";

        pt.onmouseenter = (e) => {
          const value = findNearestValueLabel(svg, pt) || "—";
          const date = findNearestDateLabel(svg, Number(pt.getAttribute("cx") || 0)) || "";
          showTooltip(e.clientX || 0, e.clientY || 0, label, date, value);
          pt.setAttribute("r", "5");
        };

        pt.onmouseleave = () => {
          hideTooltip();
          pt.setAttribute("r", "3.5");
        };
      });
    });
  }

  function findNearestValueLabel(svg, point) {
    const px = Number(point.getAttribute("cx") || 0);
    const py = Number(point.getAttribute("cy") || 0);

    const texts = Array.from(svg.querySelectorAll("text")).filter(t => {
      const txt = (t.textContent || "").trim();
      if (!txt) return false;
      const num = Number(txt);
      if (Number.isNaN(num)) return false;
      const ty = Number(t.getAttribute("y") || 0);
      return ty < 250;
    });

    let best = null;
    let bestScore = Infinity;

    texts.forEach(t => {
      const tx = Number(t.getAttribute("x") || 0);
      const ty = Number(t.getAttribute("y") || 0);
      const dx = Math.abs(tx - px);
      const dy = Math.abs((ty + 8) - py);
      const score = dx + dy * 2;
      if (score < bestScore) {
        bestScore = score;
        best = t;
      }
    });

    return best ? best.textContent.trim() : "";
  }

  function findNearestDateLabel(svg, targetX) {
    const labels = Array.from(svg.querySelectorAll("text")).filter(t => {
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

  waitForApp();
})();
</script>
<!-- V23_RUNTIME_PATCH_END -->
"""

html = remove_block(html, start_marker, end_marker)

if "</body>" not in html:
    print("Could not find </body> in index.html")
    sys.exit(1)

html = html.replace("</body>", patch + "\n</body>")
index.write_text(html, encoding="utf-8")

print("Applied runtime patch v23 to index.html")
