from pathlib import Path
import re
import sys

INDEX = Path("index.html")

if not INDEX.exists():
    print("Could not find index.html in this folder.", flush=True)
    sys.exit(1)

html = INDEX.read_text(encoding="utf-8")
original = html

def must_replace(pattern: str, repl: str, desc: str, flags=re.S):
    global html
    print(f"Trying: {desc}", flush=True)
    new_html, count = re.subn(pattern, repl, html, count=1, flags=flags)
    if count != 1:
        print(f"FAILED: {desc}", flush=True)
        sys.exit(1)
    html = new_html
    print(f"OK: {desc}", flush=True)

must_replace(
    r"version v17",
    "version v18",
    "version label"
)

must_replace(
    r'(<div class="status-banner" id="garminStatus">)(.*?)(</div>)',
    r'\1Last 90d\3',
    "garmin status banner"
)

must_replace(
    r'(<div class="card topbar">\s*<div class="tabs">)',
    """<div class="card topbar">
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <label for="rangeFilter" style="font-size:12px;font-weight:600;margin:0">Charts</label>
      <select id="rangeFilter" style="width:auto;padding:8px 12px;border-radius:999px">
        <option value="28">Last 4 weeks</option>
        <option value="90">Last 90 days</option>
        <option value="180">Last 6 months</option>
        <option value="365">Last 12 months</option>
        <option value="all">All history</option>
      </select>
    </div>
    <div class="tabs">""",
    "chart filter control"
)

must_replace(
    r"(let garminHistory = \[\];)",
    r"""\1
let chartRange = '28';""",
    "chartRange variable"
)

html = html.replace(
    "document.getElementById('garminStatus').textContent = `Garmin history loaded: ${garminHistory.length} days`;",
    "document.getElementById('garminStatus').textContent = 'Last 90d';"
)

html = html.replace(
    "document.getElementById('garminStatus').textContent = 'No Garmin history file loaded yet';",
    "document.getElementById('garminStatus').textContent = 'Last 90d';"
)

must_replace(
    r"""const cutoff = new Date\(latestDate \+ 'T12:00:00'\);\s*
  cutoff\.setDate\(cutoff\.getDate\(\) - 365\);\s*
  const recent = garminHistory\.filter\(r => new Date\(r\.date \+ 'T12:00:00'\) >= cutoff\);""",
    """const cutoff = new Date(latestDate + 'T12:00:00');
  cutoff.setDate(cutoff.getDate() - 90);
  const recent = garminHistory.filter(r => new Date(r.date + 'T12:00:00') >= cutoff);""",
    "baseline window"
)

html = html.replace("{label:'Sleep (365d)', value:'—'},", "{label:'Sleep (90d)', value:'—'},")
html = html.replace("{label:'Sleep (365d)', value: baselineValues.sleepScore ?? '—'},", "{label:'Sleep (90d)', value: baselineValues.sleepScore ?? '—'},")

must_replace(
    r"""function renderHistoryGroups\(entry\)\{.*?const groups = \[\['Primary', primary\],\['Supplemental', supplemental\],\['Subjective', subjective\],\['Session', session\]\]\.filter\(\(\[,items\]\) => items.length\);\s*return groups\.map\(\(\[label, items\]\) => `<div><div class="history-note" style="margin-bottom:4px">\$\{label\}</div><div class="history-metrics">\$\{items\.map\(\(\[k,v\]\) => `<div class="metric">\$\{k\} \$\{v\}</div>`\)\.join\(''\)\}</div></div>`\)\.join\(''\);\s*\}""",
    """function renderHistoryGroups(entry){
  const primary = [['😴 Sleep', entry.sleepScore],['📉 HRV', entry.hrv],['❤️ RHR', entry.restingHr]].filter(([,v]) => !isBlank(v));
  const supplemental = [['🔋 Body Battery', entry.bodyBattery],['🫁 Resp', entry.respiration],['🩸 Pulse Ox', entry.pulseOx]].filter(([,v]) => !isBlank(v));
  const subjective = [['🛌 Self Sleep', entry.sleepSelf],['⚡ Energy', entry.energy],['🧠 Stress', entry.stress],['🦴 Joint Stiff', entry.jointStiffness]].filter(([,v]) => !isBlank(v));
  const session = [['🔥 Sauna', entry.saunaMinutes === '' ? '' : entry.saunaMinutes + 'm'],['🔴 Red light', entry.redLightUsed ? 'Yes' : '']].filter(([,v]) => !isBlank(v));
  const flat = [...primary, ...supplemental, ...subjective, ...session];
  return `<div class="history-metrics">${flat.map(([k,v]) => `<div class="metric">${k} ${v}</div>`).join('')}</div>`;
}""",
    "renderHistoryGroups"
)

html = html.replace(
    '<div style="display:grid;gap:8px;margin-top:6px">${renderHistoryGroups(entry)}</div>',
    '<div style="margin-top:6px">${renderHistoryGroups(entry)}</div>'
)

must_replace(
    r"function dateLabelParts\(value\)\{",
    """function filterRowsByRange(rows){
  if(chartRange === 'all' || !rows.length) return rows;
  const latest = rows.reduce((m,r)=> r.date > m ? r.date : m, rows[0].date);
  const cutoff = new Date(latest.split('-').slice(0,3).join('-') + 'T12:00:00');
  cutoff.setDate(cutoff.getDate() - Number(chartRange));
  return rows.filter(r => new Date(r.date.split('-').slice(0,3).join('-') + 'T12:00:00') >= cutoff);
}
function dateLabelParts(value){""",
    "filterRowsByRange helper"
)

must_replace(
    r"""const mergedMap = new Map\(\);\s*
  datasets\.forEach\(ds=> ds\.data\.forEach\(row => mergedMap\.set\(row\.date, true\)\)\);""",
    """const filteredSets = datasets.map(ds => ({...ds, data: filterRowsByRange(ds.data)}));
  const mergedMap = new Map();
  filteredSets.forEach(ds=> ds.data.forEach(row => mergedMap.set(row.date, true)));""",
    "drawChart filteredSets"
)

html = html.replace("datasets.forEach(s=>{", "filteredSets.forEach(s=>{", 1)

must_replace(
    r"""document\.getElementById\('ingestDate'\)\.addEventListener\('change',e=>\{ ingestDraft\.date = e\.target\.value; \}\);""",
    """document.getElementById('ingestDate').addEventListener('change',e=>{ ingestDraft.date = e.target.value; });
document.getElementById('rangeFilter').addEventListener('change',e=>{ chartRange = e.target.value; renderCharts(); });""",
    "range filter listener"
)

if html == original:
    print("No changes were made.", flush=True)
    sys.exit(1)

INDEX.write_text(html, encoding="utf-8")
print("Updated index.html to v18.", flush=True)
