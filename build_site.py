# -*- coding: utf-8 -*-
"""
日経平均 理論株価サイト 自動生成スクリプト（GitHub Pages用）
================================================================
nikkei225jp.com/data/per.php から最新データを取得し、
PER11倍～21倍の理論株価を表示する index.html を生成します。
GitHub Actions から毎日実行される想定です。
"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta
from string import Template

import requests
from bs4 import BeautifulSoup

URL = "https://nikkei225jp.com/data/per.php"
BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_HTML = os.path.join(BASE, "index.html")
PER_MIN = 11
PER_MAX = 21

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ja,en;q=0.9",
}

JST = timezone(timedelta(hours=9))


def to_float(text):
    if text is None:
        return None
    t = text.replace(",", "").replace("+", "").replace("%", "").strip()
    if t in ("", "-", "—"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def fetch_latest():
    """最新の営業日データを1件返す"""
    res = requests.get(URL, headers=HEADERS, timeout=30)
    res.raise_for_status()
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    records = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or not date_pattern.match(cells[0]):
            continue
        if len(cells) < 8:
            continue
        rec = {
            "date":   cells[0],
            "nikkei": to_float(cells[1]),
            "change": to_float(cells[2]),
            "per":    to_float(cells[4]),
            "pbr":    to_float(cells[5]),
            "eps":    to_float(cells[6]),
            "bps":    to_float(cells[7]),
        }
        if rec["nikkei"] and rec["eps"]:
            records.append(rec)

    if not records:
        raise RuntimeError("データを取得できませんでした（表の構造変更の可能性）")

    records.sort(key=lambda r: r["date"], reverse=True)
    return records[0]


HTML_TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>日経平均 理論株価 | $date</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@700;900&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#20242c;        /* 墨 */
    --ink-soft:#5a6272;
    --paper:#ffffff;
    --panel:#f2f4f7;      /* 薄鼠 */
    --rule:#d8dce3;
    --indigo:#2b4a6f;     /* 藍 */
    --vermilion:#c9432b;  /* 朱：現在位置のみに使用 */
    --num:'Noto Sans JP',sans-serif;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    font-family:'Noto Sans JP',sans-serif;
    background:var(--paper);color:var(--ink);
    line-height:1.6;
    -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:720px;margin:0 auto;padding:0 20px 64px}

  /* 題字 */
  header{border-bottom:3px double var(--ink);padding:28px 0 16px;margin-bottom:8px}
  h1{
    font-family:'Zen Old Mincho',serif;font-weight:900;
    font-size:clamp(26px,6vw,38px);letter-spacing:.06em;
  }
  .dateline{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px;margin-top:6px}
  .dateline .d{font-size:15px;font-weight:700;letter-spacing:.05em}
  .dateline .u{font-size:12px;color:var(--ink-soft)}

  /* 現況 */
  .stats{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--rule);border-radius:6px;overflow:hidden;margin:20px 0 28px}
  .stat{padding:12px 8px;text-align:center;background:var(--panel)}
  .stat+.stat{border-left:1px solid var(--rule)}
  .stat .l{font-size:11px;color:var(--ink-soft);letter-spacing:.08em}
  .stat .v{font-size:clamp(15px,3.4vw,20px);font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
  .stat .v.up{color:var(--vermilion)}
  .stat .v.down{color:var(--indigo)}

  /* 理論株価はしご */
  h2{font-family:'Zen Old Mincho',serif;font-size:18px;font-weight:700;letter-spacing:.1em;margin-bottom:4px}
  .note{font-size:12px;color:var(--ink-soft);margin-bottom:14px}
  table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
  th{
    font-size:12px;font-weight:500;color:var(--ink-soft);letter-spacing:.08em;
    text-align:right;padding:6px 10px;border-bottom:2px solid var(--ink)
  }
  th:first-child{text-align:left}
  td{padding:10px;border-bottom:1px solid var(--rule);text-align:right;font-size:16px}
  td:first-child{text-align:left;font-weight:700;letter-spacing:.04em}
  td.price{font-weight:700;font-size:17px}
  td.diff{font-size:13px;color:var(--ink-soft)}
  tr.above td{color:var(--ink)}
  tr.below td{color:var(--ink-soft)}

  /* 現在値マーカー行 */
  tr.now td{
    border-top:2px solid var(--vermilion);
    border-bottom:2px solid var(--vermilion);
    background:#fdf3f1;color:var(--vermilion);
    font-size:14px;padding:7px 10px;font-weight:700
  }
  tr.now td:first-child::before{content:"▶ ";font-size:11px}

  footer{margin-top:36px;padding-top:14px;border-top:1px solid var(--rule);font-size:11px;color:var(--ink-soft)}
  footer a{color:var(--indigo)}
  @media (max-width:480px){
    td{padding:9px 6px;font-size:15px}
    td.price{font-size:16px}
    th{padding:6px}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>日経平均 理論株価</h1>
    <div class="dateline">
      <span class="d">$date_jp 現在</span>
      <span class="u">毎日18時ごろ自動更新 ｜ 更新: $updated</span>
    </div>
  </header>

  <div class="stats">
    <div class="stat"><div class="l">日経平均</div><div class="v $chg_class">$nikkei</div></div>
    <div class="stat"><div class="l">前日比</div><div class="v $chg_class">$change</div></div>
    <div class="stat"><div class="l">PER</div><div class="v">$per 倍</div></div>
    <div class="stat"><div class="l">EPS</div><div class="v">$eps</div></div>
  </div>

  <h2>PER別 理論株価</h2>
  <p class="note">理論株価 ＝ EPS $eps 円 × PER倍率。朱色の線が現在の日経平均の位置です。</p>

  <table>
    <thead>
      <tr><th>PER</th><th>理論株価</th><th>現在値との差</th></tr>
    </thead>
    <tbody>
$rows
    </tbody>
  </table>

  <footer>
    データ出所: <a href="https://nikkei225jp.com/data/per.php" target="_blank" rel="noopener">nikkei225jp.com</a>（加重平均ベース）。
    本ページは個人利用目的の自動生成であり、投資判断はご自身の責任でお願いします。
  </footer>
</div>
</body>
</html>
""")


def build_html(rec):
    eps = rec["eps"]
    nikkei = rec["nikkei"]
    per_now = rec["per"] or (nikkei / eps)

    # PER21→11の降順で行を作り、現在値の位置にマーカー行を挿入
    rows = []
    marker_inserted = False
    for p in range(PER_MAX, PER_MIN - 1, -1):
        price = eps * p
        # 現在PERがこの行と次の行の間にあればマーカーを挿入
        if (not marker_inserted) and per_now >= p:
            rows.append(
                f'      <tr class="now"><td>現在 {per_now:.2f}倍</td>'
                f'<td class="price">¥{nikkei:,.0f}</td><td class="diff">―</td></tr>'
            )
            marker_inserted = True
        diff = price - nikkei
        pct = diff / nikkei * 100
        cls = "above" if price > nikkei else "below"
        sign = "+" if diff >= 0 else ""
        rows.append(
            f'      <tr class="{cls}"><td>{p}倍</td>'
            f'<td class="price">¥{price:,.0f}</td>'
            f'<td class="diff">{sign}{diff:,.0f}円（{sign}{pct:.1f}%）</td></tr>'
        )
    if not marker_inserted:
        rows.append(
            f'      <tr class="now"><td>現在 {per_now:.2f}倍</td>'
            f'<td class="price">¥{nikkei:,.0f}</td><td class="diff">―</td></tr>'
        )

    d = datetime.strptime(rec["date"], "%Y-%m-%d")
    weekday = "月火水木金土日"[d.weekday()]
    change = rec["change"]
    if change is None:
        change_str, chg_class = "―", ""
    else:
        change_str = f"{'+' if change >= 0 else ''}{change:,.2f}"
        chg_class = "up" if change >= 0 else "down"

    return HTML_TEMPLATE.substitute(
        date=rec["date"],
        date_jp=f"{d.year}年{d.month}月{d.day}日（{weekday}）",
        updated=datetime.now(JST).strftime("%m/%d %H:%M JST"),
        nikkei=f"{nikkei:,.2f}",
        change=change_str,
        chg_class=chg_class,
        per=f"{per_now:.2f}",
        eps=f"{eps:,.2f}",
        rows="\n".join(rows),
    )


def main():
    try:
        rec = fetch_latest()
        print(f"取得成功: {rec['date']} 日経平均 {rec['nikkei']:,.2f} / EPS {rec['eps']:,.2f}")
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

    html = build_html(rec)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 生成完了: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
