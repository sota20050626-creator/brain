import os
import requests

TYPEFULLY_API_KEY = os.environ["TYPEFULLY_API_KEY"]

def create_draft(content: str, schedule_date: str = None):
    """
    Typefullyに下書きを作成・予約投稿する
    schedule_date: "2026-04-18T07:00:00Z" のような形式
    """
    headers = {
        "X-API-KEY": f"Bearer {TYPEFULLY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "content": content,
        "threadify": False,
        "share": False,
    }
    
    if schedule_date:
        payload["schedule-date"] = schedule_date
    
    response = requests.post(
        "https://api.typefully.com/v1/drafts/",
        headers=headers,
        json=payload
    )
    
    return response.json()
