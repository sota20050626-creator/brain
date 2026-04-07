import json
from datetime import datetime, timedelta
from pathlib import Path

DAILY_DIR = Path("knowledge/daily")
PROPOSALS_DIR = Path("knowledge/proposals")
KNOWLEDGE_FILE = Path("knowledge/knowledge_base.json")
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


def load_knowledge_base():
    if not KNOWLEDGE_FILE.exists():
        return {"entries": [], "days_covered": 0, "total_articles": 0}
    with open(KNOWLEDGE_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_pending_proposals():
    proposals = []
    if PROPOSALS_DIR.exists():
        for fp in sorted(PROPOSALS_DIR.glob("proposal_*.md"), reverse=True)[:3]:
            proposals.append(fp.name)
    return proposals


def build_html(days_data, proposals, knowledge):
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
        bar_color = "#00ff88" if importance >= 8 else "#ffaa00" if importance >= 6 else "#444"
        tags_html = ""
        for t in item.get("tags", [])[:3]:
            tags_html += f'<span class="item-tag">{t}</span>'
        url = item.get("url", "")
        title = item.get("title_ja", item.get("title", ""))
        summary = item.get("summary_ja", "")
        source = item.get("source", "")
        cards_html += (
            '<div class="card" onclick="window.open(\'' + url + '\',\'_blank\')">'
            '<div class="card-bar" style="background:' + bar_color + '"></div>'
            '<div class="card-source">' + source + '</div>'
            '<div class="card-title">' + title + '</div>'
            '<div class="card-summary">' + summary + '</div>'
            '<div class="card-tags">' + tags_html + '</div>'
            '<div class="card-score">重要度 ' + str(importance) + '/10</div>'
            '</div>'
        )

    history_html = ""
    for d in days_data:
        count = len(d.get("summarized_items", []))
        height = min(count * 3, 60)
        date_str = d.get("date", "")
        history_html += f'<div class="hist-bar" style="height:{height}px" title="{date_str} ({count}件)"></div>'

    proposals_html = ""
    for p in proposals:
        proposals_html += f'<div class="proposal-item">📋 {p}</div>'
    if not proposals_html:
        proposals_html = '<div class="proposal-item muted">承認待ちの提案はありません</div>'

    kb_days = knowledge.get("days_covered", 0)
    kb_articles = knowledge.get("total_articles", 0)
    total_items = len(items)
    active_days = len(days_data)
    kb_entries_json = json.dumps(knowledge.get("entries", []), ensure_ascii=False)

    with open("/home/claude/Brain/agents/template.html", encoding="utf-8") as f:
        template = f.read()

    html = (template
        .replace("{{TODAY}}", today)
        .replace("{{DIGEST}}", digest)
        .replace("{{TAG_HTML}}", tag_html)
        .replace("{{CARDS_HTML}}", cards_html)
        .replace("{{TOTAL_ITEMS}}", str(total_items))
        .replace("{{ACTIVE_DAYS}}", str(active_days))
        .replace("{{KB_DAYS}}", str(kb_days))
        .replace("{{KB_ARTICLES}}", str(kb_articles))
        .replace("{{HISTORY_HTML}}", history_html)
        .replace("{{PROPOSALS_HTML}}", proposals_html)
        .replace("{{KB_ENTRIES_JSON}}", kb_entries_json)
    )

    return html


def main():
    print("Brain Dashboard Builder starting...")
    days_data = load_recent(days=7)
    proposals = load_pending_proposals()
    knowledge = load_knowledge_base()
    html = build_html(days_data, proposals, knowledge)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard updated -> {OUTPUT}")


if __name__ == "__main__":
    main()
