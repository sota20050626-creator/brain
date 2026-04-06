import json
from datetime import datetime, timedelta
from pathlib import Path

DAILY_DIR = Path("knowledge/daily")
PROPOSALS_DIR = Path("knowledge/proposals")
OUTPUT = Path("dashboard/index.html")
OUTPUT.parent.mkdir(exist_ok=True)


def load_recent(days=7):
    result = []
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        fp = DAILY_DIR / f"{date}.json"
        if fp.exists():
            with open(fp, encoding="utf-8") as f:
                result.append(json.load(f))
    return result


def load_pending_proposals():
    proposals = []
    if PROPOSALS_DIR.exists():
        for fp in sorted(PROPOSALS_DIR.glob("proposal_*.md"), reverse=True)[:3]:
            proposals.append(fp.name)
    return proposals


def build_html(days_data, proposals):
    today_data = days_data[0] if days_data else {}
    today = today_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    digest = today_data.get("digest", "データなし")
    items = today_data.get("summarized_items", [])
    top_tags = today_data.get("top_tags", {})

    tag_html = ""
    for tag, count in list(top_tags.items())[:8]:
        tag_html += f'<span class="tag">{tag} <span class="tag-count">{count}</span></span>'

    cards_html = ""
    for item in items[:20]:
        importance = item.get("importance", 5)
        bar_color = "#00ff88" if importance >= 8 else "#ffaa00" if importance >= 6 else "#666"
        tags_html = ""
        for t in item.get("tags", [])[:3]:
            tags_html += f'<span class="item-tag">{t}</span>'
        url = item.get("url", "")
        title = item.get("title_ja", item.get("title", ""))
        summary = item.get("summary_ja", "")
        source = item.get("source", "")
        cards_html += f"""
        <div class="card" onclick="window.open('{url}','_blank')">
          <div class="card-importance" style="background:{bar_color};width:{importance * 10}%"></div>
          <div class="card-source">{source}</div>
          <div class="card-title">{title}</div>
          <div class="card-summary">{summary}</div>
          <div class="card-tags">{tags_html}</div>
          <div class="card-score">重要度 {importance}/10</div>
        </div>"""

    history_html = ""
    for d in days_data:
        count = len(d.get("summarized_items", []))
        height = min(count * 2, 60)
        date_str = d.get("date", "")
        history_html += f'<div class="hist-bar" style="height:{height}px" title="{date_str} ({count}件)"></div>'

    proposals_html = ""
    for p in proposals:
        proposals_html += f'<div class="proposal-item">📋 {p}</div>'
    if not proposals_html:
        proposals_html = '<div class="proposal-item muted">承認待ちの提案はありません</div>'

    total_items = len(items)
    active_days = len(days_data)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Brain Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Noto+Sans+JP:wght@300;400;700&display=swap');
  :root {{
    --bg: #080c10; --surface: #0d1117; --border: #1e2a38;
    --accent: #00ff88; --accent2: #0088ff; --text: #c9d1d9;
    --muted: #484f58; --warning: #ffaa00;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Noto Sans JP', sans-serif; min-height: 100vh; padding: 24px; }}
  .grid-bg {{ position: fixed; inset: 0; z-index: 0; background-image: linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px); background-size: 40px 40px; opacity: 0.3; }}
  .container {{ position: relative; z-index: 1; max-width: 1200px; margin: 0 auto; }}
  header {{ display: flex; align-items: center; justify-content: space-between; padding-bottom: 24px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }}
  .logo {{ font-family: 'Space Mono', monospace; font-size: 24px; font-weight: 700; color: var(--accent); }}
  .logo span {{ color: var(--text); }}
  .date {{ font-family: 'Space Mono', monospace; font-size: 13px; color: var(--muted); }}
  .main-grid {{ display: grid; grid-template-columns: 1fr 320px; gap: 20px; }}
  .panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
  .panel-title {{ font-family: 'Space Mono', monospace; font-size: 11px; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 16px; }}
  .digest {{ font-size: 14px; line-height: 1.8; color: var(--text); white-space: pre-wrap; }}
  .tags {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .tag {{ background: rgba(0,255,136,0.08); border: 1px solid rgba(0,255,136,0.2); color: var(--accent); font-family: 'Space Mono', monospace; font-size: 11px; padding: 4px 10px; border-radius: 4px; }}
  .tag-count {{ color: var(--muted); }}
  .cards {{ display: flex; flex-direction: column; gap: 12px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px; cursor: pointer; transition: border-color 0.2s; position: relative; overflow: hidden; }}
  .card:hover {{ border-color: var(--accent2); }}
  .card-importance {{ position: absolute; top: 0; left: 0; height: 2px; }}
  .card-source {{ font-family: 'Space Mono', monospace; font-size: 10px; color: var(--muted); margin-bottom: 6px; }}
  .card-title {{ font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 6px; line-height: 1.4; }}
  .card-summary {{ font-size: 13px; color: var(--muted); line-height: 1.6; margin-bottom: 8px; }}
  .card-tags {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .item-tag {{ font-size: 10px; padding: 2px 6px; background: rgba(0,136,255,0.1); border: 1px solid rgba(0,136,255,0.2); color: var(--accent2); border-radius: 3px; }}
  .card-score {{ font-family: 'Space Mono', monospace; font-size: 11px; color: var(--muted); margin-top: 8px; }}
  .history {{ display: flex; align-items: flex-end; gap: 6px; height: 70px; }}
  .hist-bar {{ flex: 1; background: var(--accent2); opacity: 0.6; border-radius: 2px; min-height: 4px; }}
  .proposal-item {{ font-size: 13px; padding: 10px; border: 1px solid var(--border); border-radius: 4px; margin-bottom: 8px; color: var(--warning); font-family: 'Space Mono', monospace; }}
  .muted {{ color: var(--muted) !important; }}
  .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .stat {{ text-align: center; padding: 12px; background: rgba(0,255,136,0.04); border: 1px solid rgba(0,255,136,0.1); border-radius: 6px; }}
  .stat-value {{ font-family: 'Space Mono', monospace; font-size: 24px; font-weight: 700; color: var(--accent); }}
  .stat-label {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}
  .pulse {{ display: inline-block; width: 8px; height: 8px; background: var(--accent); border-radius: 50%; animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.5; transform: scale(0.8); }} }}
</style>
</head>
<body>
<div class="grid-bg"></div>
<div class="container">
  <header>
    <div class="logo">🧠 <span>Brain</span></div>
    <div class="date"><span class="pulse"></span> {today} 自動更新</div>
  </header>
  <div class="main-grid">
    <div class="left">
      <div class="panel">
        <div class="panel-title">// Today's Digest</div>
        <div class="digest">{digest}</div>
      </div>
      <div class="panel">
        <div class="panel-title">// Top Tags</div>
        <div class="tags">{tag_html}</div>
      </div>
      <div class="panel">
        <div class="panel-title">// Articles ({total_items} collected)</div>
        <div class="cards">{cards_html}</div>
      </div>
    </div>
    <div class="right">
      <div class="panel">
        <div class="panel-title">// Stats</div>
        <div class="stat-grid">
          <div class="stat"><div class="stat-value">{total_items}</div><div class="stat-label">Today</div></div>
          <div class="stat"><div class="stat-value">{active_days}</div><div class="stat-label">Days</div></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">// 7-Day Activity</div>
        <div class="history">{history_html}</div>
      </div>
      <div class="panel">
        <div class="panel-title">// Pending Approval</div>
        {proposals_html}
      </div>
    </div>
  </div>
</div>
</body>
</html>"""
    return html


def main():
    print("Brain Dashboard Builder starting...")
    days_data = load_recent(days=7)
    proposals = load_pending_proposals()
    html = build_html(days_data, proposals)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard updated -> {OUTPUT}")


if __name__ == "__main__":
    main()
