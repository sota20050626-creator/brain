# 🧠 Brain - 自律型AI情報収集・成長システム

毎日自動でAI情報を収集・要約し、週次でビジネスアイデアと改善案を提案する自律型エージェントシステム。

## アーキテクチャ

```
毎日AM6時 (JST)
  └── GitHub Actions 自動起動
        ├── collector.py    → Reddit / HackerNews / ArXiv から収集
        ├── summarizer.py   → Claude APIで日本語要約・重要度スコアリング
        ├── cleaner.py      → 30日以上のrawデータを自動削除
        └── dashboard_builder.py → dashboard/index.html を更新

毎週月曜AM6時 (JST) - 追加で実行
        └── growth.py       → トレンド分析 + ビジネスアイデア + 改善提案
                              → knowledge/proposals/ に承認待ちファイルを生成
```

## セットアップ（5分で完了）

### 1. このリポジトリをGitHubにpush

```bash
git init
git add -A
git commit -m "🧠 Brain initial setup"
git remote add origin https://github.com/YOUR_USERNAME/Brain.git
git push -u origin main
```

### 2. GitHub Secrets を設定

GitHubリポジトリの Settings → Secrets and variables → Actions で以下を追加：

| Secret名 | 値 | 取得先 |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | https://console.anthropic.com |
| `REDDIT_CLIENT_ID` | アプリのclient_id | https://www.reddit.com/prefs/apps |
| `REDDIT_CLIENT_SECRET` | アプリのsecret | 同上 |

### 3. Reddit APIの取得（無料）

1. https://www.reddit.com/prefs/apps にアクセス
2. "create another app" をクリック
3. typeは "script" を選択
4. `redirect uri` は `http://localhost:8080` でOK
5. 作成後に表示される `client_id`（アプリ名の下の文字列）と `secret` をコピー

### 4. GitHub Pages を有効化（ダッシュボード公開）

Settings → Pages → Source: Deploy from branch → Branch: main → /dashboard

これで `https://YOUR_USERNAME.github.io/Brain/` でダッシュボードが見れます。

### 5. 手動で初回実行

Actions タブ → "Brain Daily Update" → "Run workflow" で即座にテスト実行できます。

## 承認フロー

週次の成長エージェントが `knowledge/proposals/proposal_YYYY-MM-DD.md` を生成します。

- 内容を確認
- 承認する場合: `proposal_YYYY-MM-DD.json` の `status` を `"approved"` に変更してpush
- 却下する場合: `status` を `"rejected"` に変更し `approval_notes` に理由を記入

## コスト試算

| サービス | コスト |
|---|---|
| Claude API (Sonnet) | ~$5〜15/月 |
| Reddit API | 無料 |
| HackerNews API | 無料 |
| ArXiv API | 無料 |
| GitHub Actions | 無料 |
| **合計** | **~$5〜15/月** |

## ファイル構成

```
Brain/
├── .github/workflows/daily.yml  # 自動実行スケジュール
├── agents/
│   ├── collector.py             # 情報収集
│   ├── summarizer.py            # Claude APIで要約
│   ├── growth.py                # 週次成長エージェント
│   ├── cleaner.py               # 古いデータ削除
│   └── dashboard_builder.py    # HTML生成
├── knowledge/
│   ├── daily/                   # 日別データ (JSON)
│   └── proposals/               # 週次提案（承認待ち）
├── dashboard/
│   └── index.html               # ダッシュボード（自動更新）
├── requirements.txt
└── README.md
```
