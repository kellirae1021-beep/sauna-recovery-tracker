from pathlib import Path
import re
import sys

INDEX = Path("index.html")

if not INDEX.exists():
    print("index.html not found")
    sys.exit(1)

html = INDEX.read_text(encoding="utf-8")

def replace_once(pattern, repl, label, flags=re.S):
    global html
    new_html, count = re.subn(pattern, repl, html, count=1, flags=flags)
    if count != 1:
        print(f"FAILED: {label}")
        sys.exit(1)
    html = new_html
    print(f"OK: {label}")

# 1) Remove the old topbar chart filter block if present
html = re.sub(
    r'\s*<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">\s*<label[^>]*>Charts</label>\s*<select id="rangeFilter"[\s\S]*?</select>\s*</div>',
    "",
    html,
    count=1,
    flags=re.S,
)

# 2) Add filter next to Primary recovery title
replace_once(
    r'<div class="chart-title">Primary recovery</div>',
    """<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">
          <div class="chart-title">Primary recovery</div>
          <div style="display:flex;align-items:center;gap:6px">
            <label for="rangeFilter" style="font-size:12px;color:var(--muted)">Range</label>
            <select id="rangeFilter" style="width:auto;padding:6px 10px;border-radius:999px">
              <option value="28">4 weeks</option>
              <option value="90">90 days</option>
              <option value="180">6 months</option>
              <option value="365">12 months</option>
              <option value="all">All</option>
            </select>
          </div>
        </div>""",
    "move range filter into chart header",
)

# 3) Add helper function for x-axis label spacing before dateLabelParts
replace_once(
    r'function dateLabelParts\(value\)\s*\{',
    """function getTickSpacing() {
  if (chartRange === '28') return 4;
  if (chartRange === '90') return 10;
  if (chartRange === '180') return 20;
  if (chartRange === '365') return 40;
  if (chartRange === 'all') return 90;
  return 4;
}

function dateLabelParts(value) {""",
    "insert tick spacing helper",
)

# 4) Thin x-axis labels by wrapping the date label loop
replace_once(
    r'data\.forEach\(\(d,i\)\s*=>\s*\{',
    """const tickSpacing = getTickSpacing();
  data.forEach((d,i) => {
    if (i % tickSpacing !== 0 && i !== data.length - 1) return;""",
    "thin x-axis labels",
)

# 5) Lighten historical Garmin lines
html = html.replace("opacity:.35", "opacity:.22")

INDEX.write_text(html, encoding="utf-8")
print("Upgrade complete → v19 chart improvements applied.")