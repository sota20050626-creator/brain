"""
tiktok_builder.py - TikTok自動スライド生成エージェント
毎日: AI速報を「恐ろしい未来」フォーマットで5枚スライド画像化
テーマ: A=速報系 / B=終末系 / C=機密系 をニュース内容で自動選択
出力: knowledge/tiktok/YYYY-MM-DD/slide_1.png ~ slide_5.png
"""

import json
import os
import re
import random
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

TODAY = datetime.now().strftime("%Y-%m-%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
KNOWLEDGE_DIR = Path("knowledge")
TIKTOK_DIR = KNOWLEDGE_DIR / "tiktok" / TODAY
COST_FILE = KNOWLEDGE_DIR / "cost_log.json"
TIKTOK_DIR.mkdir(parents=True, exist_ok=True)

SONNET_INPUT_PRICE = 3.0 / 1_000_000
SONNET_OUTPUT_PRICE = 15.0 / 1_000_000

FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"
WIDTH, HEIGHT = 1080, 1920

# テーマ判定キーワード
THEME_B_KEYWORDS = ["agi", "人類", "滅亡", "超知能", "シンギュラリティ", "existential", "extinction", "civilization"]
THEME_C_KEYWORDS = ["軍事", "兵器", "監視", "政府", "規制", "安全保障", "military", "weapon", "surveillance", "national security"]


def get_fonts():
    return {
        'large':       ImageFont.truetype(FONT_PATH, 72),
        'medium':      ImageFont.truetype(FONT_PATH, 52),
        'small':       ImageFont.truetype(FONT_PATH, 40),
        'tiny':        ImageFont.truetype(FONT_PATH, 30),
        'num':         ImageFont.truetype(FONT_PATH, 26),
        'swipe_arrow': ImageFont.truetype(FONT_PATH, 60),
        'swipe_label': ImageFont.truetype(FONT_PATH, 36),
    }


def load_cost_log():
    if not COST_FILE.exists():
        return {"monthly": {}, "total_usd": 0}
    with open(COST_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_cost(input_tokens, output_tokens, label):
    cost = input_tokens * SONNET_INPUT_PRICE + output_tokens * SONNET_OUTPUT_PRICE
    log = load_cost_log()
    month = TODAY[:7]
    if month not in log["monthly"]:
        log["monthly"][month] = {"usd": 0, "calls": [], "input_tokens": 0, "output_tokens": 0}
    log["monthly"][month]["usd"] = round(log["monthly"][month]["usd"] + cost, 6)
    log["monthly"][month]["input_tokens"] += input_tokens
    log["monthly"][month]["output_tokens"] += output_tokens
    log["monthly"][month]["calls"].append({
        "date": TODAY, "label": label,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "usd": round(cost, 6)
    })
    log["total_usd"] = round(sum(v["usd"] for v in log["monthly"].values()), 6)
    with open(COST_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return cost


def call_claude(prompt, max_tokens=2000, label="tiktok_api"):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    usage = result.get("usage", {})
    save_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0), label)
    return result["content"][0]["text"]


def load_latest_items():
    items = []
    for date in [TODAY, YESTERDAY]:
        fp = KNOWLEDGE_DIR / "daily" / (date + ".json")
        if not fp.exists():
            continue
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        items.extend(data.get("summarized_items", []))
    return items


def select_theme(news_title, news_summary):
    """ニュース内容からテーマを自動選択"""
    text = (news_title + " " + news_summary).lower()
    if any(kw in text for kw in THEME_C_KEYWORDS):
        return "C"
    if any(kw in text for kw in THEME_B_KEYWORDS):
        return "B"
    return "A"


def generate_tiktok_script(items):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:10]
    items_text = "\n".join([
        "- [重要度" + str(item.get("importance", 5)) + "] " +
        item.get("title_ja", item.get("title", "")) + ": " +
        item.get("summary_ja", "")[:100]
        for item in top_items
    ])

    prompt = """あなたはTikTokで「AIの恐ろしい未来」を発信するアカウントの担当者です。
今日のAIニュースから最もインパクトのあるものを1つ選び、5枚のスライド台本を作ってください。

【今日のAIニュース】
""" + items_text + """

【フォーマット】
スライド1（表紙）: タイトル＋サブテキストで止まらせる
スライド2（事実）: 何が起きたかをシンプルに3行以内
スライド3（解説）: この技術でできることを3行以内
スライド4（恐怖）: 5年後の恐ろしい未来予測を3行以内
スライド5（締め）: 視聴者への問いかけ＋ハッシュタグ3個

【ルール】
- 各スライドのテキストは100文字以内
- 断言系・体言止めで書く
- 嘘はつかない、でも最大限に恐ろしく見せる
- 「速報」「判明」「衝撃」などの言葉を使う

以下のJSON形式のみで返してください：
{
  "news_title": "選んだニュースのタイトル",
  "news_summary": "要約（50字以内）",
  "slides": [
    {"num": 1, "title": "タイトル", "sub": "サブテキスト", "body": ""},
    {"num": 2, "title": "見出し", "sub": "", "body": "本文"},
    {"num": 3, "title": "見出し", "sub": "", "body": "本文"},
    {"num": 4, "title": "見出し", "sub": "", "body": "本文"},
    {"num": 5, "title": "見出し", "sub": "", "body": "本文", "tags": "#AI #人工知能 #未来"}
  ]
}"""

    response = call_claude(prompt, max_tokens=1500, label="tiktok_script")
    try:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if not match:
            return None
        return json.loads(match.group())
    except Exception as e:
        print("  スクリプトパースエラー: " + str(e))
        return None


def wrap_text(draw, text, font, max_width):
    lines = []
    current = ''
    for char in text:
        test = current + char
        bbox = draw.textbbox((0,0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def draw_centered(draw, text, font, color, y, max_width=900, line_height=75):
    if not text:
        return y
    lines = wrap_text(draw, text, font, max_width)
    for line in lines:
        draw.text((WIDTH//2, y), line, font=font, fill=color, anchor='mm')
        y += line_height
    return y


def draw_swipe_hint(draw, fonts, label, color, is_last=False):
    """右中央にスワイプ誘導"""
    x = WIDTH - 45
    y = HEIGHT // 2 - 60
    arrow = '▶' if not is_last else '♻'
    draw.text((x, y), arrow, font=fonts['swipe_arrow'], fill=color, anchor='mm')
    char_y = y + 70
    for char in list(label):
        draw.text((x, char_y), char, font=fonts['swipe_label'], fill=color, anchor='mm')
        char_y += 42


def draw_noise(draw, seed=42):
    random.seed(seed)
    for _ in range(WIDTH * HEIGHT // 20):
        x = random.randint(0, WIDTH-1)
        y = random.randint(0, HEIGHT-1)
        v = random.randint(0, 12)
        draw.point((x, y), fill=(v, v, v))


# ============================================================
# テーマA: ニュース速報系
# ============================================================
def create_slide_theme_a(slide_data, slide_num, total, fonts):
    img = Image.new('RGB', (WIDTH, HEIGHT), (8, 8, 12))
    draw = ImageDraw.Draw(img)

    # グリッド背景
    for x in range(0, WIDTH, 60):
        draw.line([(x,0),(x,HEIGHT)], fill=(18,18,28), width=1)
    for y in range(0, HEIGHT, 60):
        draw.line([(0,y),(WIDTH,y)], fill=(18,18,28), width=1)

    # 上部バー
    draw.rectangle([(0,0),(WIDTH,100)], fill=(180,0,0))
    draw.text((WIDTH//2, 50), '⚡ BREAKING NEWS ⚡', font=fonts['medium'], fill=(255,255,255), anchor='mm')
    draw.rectangle([(0,100),(WIDTH,107)], fill=(255,200,0))

    # 日付・ページ
    draw.text((60, 145), TODAY + '  AI速報', font=fonts['num'], fill=(150,150,150))
    draw.text((WIDTH-80, 145), str(slide_num) + ' / ' + str(total), font=fonts['num'], fill=(100,100,100), anchor='rm')

    if slide_num == 1:
        y = 340
        y = draw_centered(draw, slide_data.get("title",""), fonts['large'], (255,255,255), y)
        draw.rectangle([(80,y+20),(WIDTH-80,y+25)], fill=(200,0,0))
        y += 70
        draw.rectangle([(80,y),(WIDTH-80,y+170)], fill=(20,20,35))
        draw.rectangle([(80,y),(84,y+170)], fill=(200,0,0))
        draw.text((WIDTH//2, y+50), slide_data.get("sub",""), font=fonts['small'], fill=(180,180,180), anchor='mm')
        draw_swipe_hint(draw, fonts, '次へ', (200,0,0))
    else:
        y = 220
        draw.rectangle([(80,y),(WIDTH-80,y+5)], fill=(200,0,0))
        y += 40
        y = draw_centered(draw, slide_data.get("title",""), fonts['medium'], (200,0,0), y, line_height=65)
        y += 30
        draw.rectangle([(80,y),(WIDTH-80,y+3)], fill=(60,60,80))
        y += 50
        y = draw_centered(draw, slide_data.get("body",""), fonts['small'], (220,220,220), y)
        if slide_data.get("tags"):
            draw_centered(draw, slide_data["tags"], fonts['tiny'], (120,120,140), HEIGHT-200)
        is_last = slide_num == total
        draw_swipe_hint(draw, fonts, 'フォロー' if is_last else '次へ', (200,0,0), is_last)

    # 下部バー
    draw.rectangle([(0,HEIGHT-75),(WIDTH,HEIGHT)], fill=(180,0,0))
    draw.text((WIDTH//2, HEIGHT-38), 'AI速報 | 毎日更新', font=fonts['num'], fill=(255,255,255), anchor='mm')

    return img


# ============================================================
# テーマB: 終末・崩壊系
# ============================================================
def create_slide_theme_b(slide_data, slide_num, total, fonts):
    img = Image.new('RGB', (WIDTH, HEIGHT), (3, 3, 3))
    draw = ImageDraw.Draw(img)
    random.seed(slide_num * 10 + 99)

    # ノイズ背景
    for _ in range(WIDTH * HEIGHT // 8):
        x = random.randint(0, WIDTH-1)
        y = random.randint(0, HEIGHT-1)
        brightness = int((y / HEIGHT) * 20)
        v = random.randint(0, brightness)
        draw.point((x, y), fill=(v, int(v*0.3), 0))

    # 亀裂
    cracks = [[(50,0),(180,500),(100,1000)], [(900,200),(800,700),(950,1200)], [(200,1300),(350,1600),(280,1900)]]
    for crack in cracks:
        draw.line(crack, fill=(40,10,0), width=2)

    # 縦ライン
    draw.rectangle([(0,0),(6,HEIGHT)], fill=(120,30,0))
    draw.rectangle([(WIDTH-6,0),(WIDTH,HEIGHT)], fill=(120,30,0))

    # ページ番号
    draw.text((WIDTH-80, 60), str(slide_num) + ' / ' + str(total), font=fonts['num'], fill=(80,40,20), anchor='rm')

    if slide_num == 1:
        y = 180
        draw.text((WIDTH//2, y), '⚠ 警 告 ⚠', font=fonts['medium'], fill=(180,50,0), anchor='mm')
        y += 90
        draw.line([(80,y),(WIDTH-80,y)], fill=(100,30,0), width=2)
        y += 80
        title_lines = wrap_text(draw, slide_data.get("title",""), fonts['large'], 900)
        for line in title_lines:
            draw.text((WIDTH//2+3, y+3), line, font=fonts['large'], fill=(80,20,0), anchor='mm')
            draw.text((WIDTH//2, y), line, font=fonts['large'], fill=(230,220,200), anchor='mm')
            y += 105
        y += 30
        draw.line([(80,y),(WIDTH-80,y)], fill=(150,40,0), width=3)
        y += 60
        draw_centered(draw, slide_data.get("sub",""), fonts['small'], (180,160,140), y)
        draw_swipe_hint(draw, fonts, '次へ', (180,50,0))
    else:
        y = 200
        draw.text((WIDTH//2, y), '⚠', font=fonts['medium'], fill=(180,50,0), anchor='mm')
        y += 80
        y = draw_centered(draw, slide_data.get("title",""), fonts['medium'], (200,80,0), y, line_height=65)
        y += 30
        draw.line([(80,y),(WIDTH-80,y)], fill=(100,30,0), width=2)
        y += 50
        y = draw_centered(draw, slide_data.get("body",""), fonts['small'], (200,180,160), y)
        if slide_data.get("tags"):
            draw_centered(draw, slide_data["tags"], fonts['tiny'], (100,70,60), HEIGHT-200)
        is_last = slide_num == total
        draw_swipe_hint(draw, fonts, 'フォロー' if is_last else '次へ', (180,50,0), is_last)

    return img


# ============================================================
# テーマC: ミリタリー・機密系
# ============================================================
def create_slide_theme_c(slide_data, slide_num, total, fonts):
    img = Image.new('RGB', (WIDTH, HEIGHT), (8, 12, 8))
    draw = ImageDraw.Draw(img)
    random.seed(slide_num * 10 + 77)

    # グリーンノイズ
    for _ in range(WIDTH * HEIGHT // 12):
        x = random.randint(0, WIDTH-1)
        y = random.randint(0, HEIGHT-1)
        v = random.randint(0, 20)
        draw.point((x, y), fill=(0, v, 0))

    # スキャンライン
    for y in range(0, HEIGHT, 4):
        draw.line([(0,y),(WIDTH,y)], fill=(0,0,0), width=1)

    # 上部バー
    draw.rectangle([(0,0),(WIDTH,100)], fill=(0,35,0))
    draw.rectangle([(0,100),(WIDTH,107)], fill=(0,170,0))
    draw.rectangle([(WIDTH//2-240,18),(WIDTH//2+240,82)], outline=(0,180,0), width=3)
    draw.text((WIDTH//2, 50), '🔒 TOP SECRET / CLASSIFIED', font=fonts['num'], fill=(0,210,0), anchor='mm')

    # ページ番号
    draw.text((WIDTH-80, 145), str(slide_num) + ' / ' + str(total), font=fonts['num'], fill=(0,120,0), anchor='rm')
    draw.line([(0,175),(WIDTH,175)], fill=(0,80,0), width=1)

    if slide_num == 1:
        draw.text((60, 210), 'CASE: AI-' + TODAY.replace('-','') + '  STATUS: ACTIVE', font=fonts['num'], fill=(0,140,0))
        y = 320
        draw.rectangle([(80,y-20),(WIDTH-80,y+380)], fill=(5,15,5))
        draw.rectangle([(80,y-20),(84,y+380)], fill=(0,170,0))
        y += 20
        y = draw_centered(draw, slide_data.get("title",""), fonts['large'], (0,220,0), y)
        y += 30
        draw_centered(draw, slide_data.get("sub",""), fonts['small'], (0,160,0), y)
        draw_swipe_hint(draw, fonts, '次へ', (0,180,0))
    else:
        draw.text((60, 210), 'INTEL REPORT  ' + TODAY, font=fonts['num'], fill=(0,140,0))
        y = 280
        draw.rectangle([(80,y),(WIDTH-80,y+4)], fill=(0,150,0))
        y += 40
        y = draw_centered(draw, slide_data.get("title",""), fonts['medium'], (0,210,0), y, line_height=65)
        y += 30
        draw.rectangle([(80,y),(WIDTH-80,y+3)], fill=(0,80,0))
        y += 50
        if slide_data.get("body"):
            body_lines = slide_data["body"].split('\n')
            for line in body_lines:
                if line.strip():
                    draw.text((WIDTH//2, y), '■ ' + line.strip(), font=fonts['tiny'], fill=(170,210,170), anchor='mm')
                    y += 55
        if slide_data.get("tags"):
            draw_centered(draw, slide_data["tags"], fonts['tiny'], (0,120,0), HEIGHT-200)
        is_last = slide_num == total
        draw_swipe_hint(draw, fonts, 'フォロー' if is_last else '次へ', (0,180,0), is_last)

    # 下部バー
    draw.rectangle([(0,HEIGHT-75),(WIDTH,HEIGHT)], fill=(0,35,0))
    draw.rectangle([(0,HEIGHT-75),(WIDTH,HEIGHT-68)], fill=(0,170,0))
    draw.text((WIDTH//2, HEIGHT-38), 'BRAIN INTELLIGENCE | CONFIDENTIAL', font=fonts['num'], fill=(0,170,0), anchor='mm')

    return img


def create_slide(slide_data, slide_num, total, theme, fonts):
    if theme == "B":
        return create_slide_theme_b(slide_data, slide_num, total, fonts)
    elif theme == "C":
        return create_slide_theme_c(slide_data, slide_num, total, fonts)
    else:
        return create_slide_theme_a(slide_data, slide_num, total, fonts)


def save_script_md(script, theme):
    path = TIKTOK_DIR / "script.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# TikTok台本 - " + TODAY + "\n\n")
        f.write("元ニュース: " + script.get("news_title", "") + "\n")
        f.write("使用テーマ: " + {"A":"速報系","B":"終末系","C":"機密系"}.get(theme, theme) + "\n\n")
        f.write("---\n\n")
        for slide in script.get("slides", []):
            f.write("## スライド" + str(slide["num"]) + "\n")
            f.write("**タイトル**: " + slide.get("title","") + "\n\n")
            if slide.get("sub"):
                f.write("**サブ**: " + slide.get("sub","") + "\n\n")
            if slide.get("body"):
                f.write("**本文**:\n" + slide.get("body","") + "\n\n")
            if slide.get("tags"):
                f.write("**タグ**: " + slide.get("tags","") + "\n\n")
            f.write("---\n\n")
    print("  台本MD保存: " + str(path))


def main():
    print("Brain TikTok Builder 起動... [" + TODAY + "]")

    items = load_latest_items()
    if len(items) < 3:
        print("  データ不足のためスキップ")
        return

    print("  " + str(len(items)) + " 件のニュースから台本生成中...")
    script = generate_tiktok_script(items)
    if not script:
        print("  台本生成失敗")
        return

    news_title = script.get("news_title", "")
    news_summary = script.get("news_summary", "")
    theme = select_theme(news_title, news_summary)

    print("  選択ニュース: " + news_title)
    print("  使用テーマ: " + {"A":"速報系","B":"終末系","C":"機密系"}.get(theme, theme))

    save_script_md(script, theme)

    fonts = get_fonts()
    slides = script.get("slides", [])
    print("  スライド画像生成中...")

    for slide in slides:
        num = slide["num"]
        img = create_slide(slide, num, len(slides), theme, fonts)
        path = TIKTOK_DIR / ("slide_" + str(num) + ".png")
        img.save(path, "PNG", quality=95)
        print("  スライド" + str(num) + "保存: " + str(path))

    print("TikTokスライド生成完了!")
    print("保存先: " + str(TIKTOK_DIR))
    print("あとはTikTokにアップするだけ!")


if __name__ == "__main__":
    main()
