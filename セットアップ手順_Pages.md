# 理論株価サイト（GitHub Pages）セットアップ手順

## 完成イメージ

`https://あなたのユーザー名.github.io/nikkei-site/` にアクセスすると、
その日の日経平均・PER・EPSと、PER11倍～21倍の理論株価一覧が表示されます。
現在の日経平均がどのPER水準にいるかも朱色のマーカーで一目で分かります。

毎日18時ごろに自動更新。スマホからもそのまま見られます。

## セットアップ手順（初回のみ）

### 1. リポジトリ作成
1. GitHubにログイン → 右上「+」→「New repository」
2. Repository name: `nikkei-site`（何でもOK）
3. **Public を選択**（※無料プランのGitHub PagesはPublicのみ。
   表示されるのは公開データの計算結果だけなので問題ありません）
4. 「Create repository」

### 2. ファイルをアップロード
以下の構成でアップロードします：

```
nikkei-site/
├── build_site.py           ← サイト生成スクリプト
├── requirements.txt
├── index.html              ← サンプル（初回表示用。以降は自動で上書きされます）
└── .github/
    └── workflows/
        └── update.yml      ← 毎日実行の設定
```

※`.github/workflows/` の階層が崩れると自動実行されません。

### 3. GitHub Pages を有効化
1. リポジトリの「Settings」→ 左メニュー「Pages」
2. Source: 「Deploy from a branch」
3. Branch: `main` / フォルダ `/ (root)` を選択して「Save」
4. 数分待つと上部にURLが表示されます
   → `https://ユーザー名.github.io/nikkei-site/`

### 4. 動作テスト
1. 「Actions」タブ →「理論株価サイト 毎日更新」を選択
2. 「Run workflow」で手動実行
3. 緑のチェック✓が付いたら、数分後にサイトのURLを開いて
   最新データに更新されていることを確認

### 5. 以降は放置でOK
毎日18時ごろに自動でデータ取得→ページ更新されます。
ブックマークやスマホのホーム画面に追加しておくと便利です。

## よくある質問

**Q. 更新時刻がずれる**
GitHubの混雑状況により、18:00〜18:40ごろの間で変動します。

**Q. 60日更新が止まるとメールが来た**
リポジトリに変化がない期間が続くとGitHubがスケジュールを一時停止します。
メール内の「再有効化」リンクを押せば再開します。

**Q. サイトのデザインやPERの範囲を変えたい**
build_site.py の PER_MIN / PER_MAX や HTML_TEMPLATE 部分を編集してください。
