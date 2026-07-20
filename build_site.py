# -*- coding: utf-8 -*-
"""
日経平均 理論株価サイト 自動生成スクリプト v3
================================================================
【v3の変更点】
nikkei225jp.com が海外サーバーからのアクセスを遮断(403)したため、
一次データ源を日経公式「日経平均プロフィル」の日次サマリーに変更。
  https://indexes.nikkei.co.jp/nkave/archives/summary
公式が取得できない場合のみ、旧ソース(daily2.json)にフォールバック。

EPS = 日経平均終値 ÷ PER(加重平均) で算出（従来と同じ計算方法）。
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from string import Template

import requests
from bs4 import BeautifulSoup

OFFICIAL_URL = "https://indexes.nikkei.co.jp/nkave/archives/summary"
FALLBACK_URL = "https://nikkei225jp.com/_data/_nfsDATA/DAY/daily2.json"
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

NUM = r"[+\-−▲]?\d{1,3}(?:,\d{3})*(?:\.\d+)?"


def parse_num(s):
    """カンマ・全角マイナス・▲を処理して数値化"""
    if s is None:
        return None
    t = (s.replace(",", "").replace("−", "-").replace("▲", "-")
          .replace("+", "").strip())
    try:
        return float(t)
    except ValueError:
        return None


# ---------------------------------------------------------------
# 一次ソース: 日経平均プロフィル（公式）
# ---------------------------------------------------------------
def fetch_official():
    res = requests.get(OFFICIAL_URL, headers=HEADERS, timeout=30)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    # 日付「2026年7月17日(金)」
    m_date = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if not m_date:
        raise RuntimeError("公式: 日付が見つかりません")
    y, mo, dd = map(int, m_date.groups())
    date_str = f"{y:04d}-{mo:02d}-{dd:02d}"

    # 日付以降のテキストを対象に解析
    t = text[m_date.end():]

    # 「日経平均株価 64,141.12 -4.03% -2,694.42」の並びを探す
    m_px = re.search(
        r"日経平均株価\s*(" + NUM + r")\s*(" + NUM + r")%\s*(" + NUM + r")", t)
    if m_px:
        nikkei = parse_num(m_px.group(1))
        change = parse_num(m_px.group(3))
    else:
        # 並びが違う場合: 日経平均株価の直後の数値だけ拾う
        m_px2 = re.search(r"日経平均株価\s*(" + NUM + r")", t)
        if not m_px2:
            raise RuntimeError("公式: 日経平均終値が見つかりません")
        nikkei = parse_num(m_px2.group(1))
        change = None

    # PER(加重平均)「株価収益率(PER) 加重平均 17.42倍」
    m_per = re.search(
        r"株価収益率\s*\(?PER\)?.{0,80}?加重平均\s*(" + NUM + r")\s*倍",
        t, re.DOTALL)
    if not m_per:
        raise RuntimeError("公式: PER(加重平均)が見つかりません")
    per = parse_num(m_per.group(1))

    # PBR(加重平均)（任意）
    m_pbr = re.search(
        r"株価純資産倍率\s*\(?PBR\)?.{0,80}?加重平均\s*(" + NUM + r")\s*倍",
        t, re.DOTALL)
    pbr = parse_num(m_pbr.group(1)) if m_pbr else None

    if not (nikkei and per and nikkei > 0 and per > 0):
        raise RuntimeError("公式: 数値の解析に失敗しました")

    return {
        "date": date_str,
        "nikkei": nikkei,
        "change": change,
        "per": per,
        "pbr": pbr,
        "eps": nikkei / per,
        "bps": (nikkei / pbr) if pbr else None,
        "source": "日経平均プロフィル（公式）",
    }


# ---------------------------------------------------------------
# フォールバック: 旧ソース daily2.json
# ---------------------------------------------------------------
COL_TIME, COL_N225, COL_PER, COL_PBR = 0, 1, 12, 13


def num_pos(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def fetch_fallback():
    h = dict(HEADERS)
    h["Referer"] = "https://nikkei225jp.com/data/per.php"
    res = requests.get(FALLBACK_URL, headers=h, timeout=30)
    res.raise_for_status()
    text = res.text.strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise RuntimeError("フォールバック: 形式が想定外です")
    body = text[start:end + 1]
    body = re.sub(r",\s*(?=,)", ",null", body)
    body = re.sub(r"\[\s*,", "[null,", body)
    body = re.sub(r",\s*\]", ",null]", body)
    data = json.loads(body)

    valid = []
    for row in data:
        if not isinstance(row, list) or len(row) <= COL_PBR:
            continue
        t, n225 = row[COL_TIME], num_pos(row[COL_N225])
        per, pbr = num_pos(row[COL_PER]), num_pos(row[COL_PBR])
        if t and n225 and per:
            valid.append({"t": t, "nikkei": n225, "per": per, "pbr": pbr})
    if not valid:
        raise RuntimeError("フォールバック: 有効データなし")
    valid.sort(key=lambda r: r["t"])
    latest, prev = valid[-1], (valid[-2] if len(valid) >= 2 else None)
    d = datetime.fromtimestamp(latest["t"] / 1000, tz=timezone.utc) + timedelta(hours=9)
    return {
        "date": d.strftime("%Y-%m-%d"),
        "nikkei": latest["nikkei"],
        "change": (latest["nikkei"] - prev["nikkei"]) if prev else None,
        "per": latest["per"],
        "pbr": latest["pbr"],
        "eps": latest["nikkei"] / latest["per"],
        "bps": (latest["nikkei"] / latest["pbr"]) if latest["pbr"] else None,
        "source": "nikkei225jp.com",
    }


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
    --ink:#20242c;
    --ink-soft:#5a6272;
    --paper:#ffffff;
    --panel:#f2f4f7;
    --rule:#d8dce3;
    --indigo:#2b4a6f;
    --vermilion:#c9432b;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    font-family:'Noto Sans JP',sans-serif;
    background:var(--paper);color:var(--ink);
    line-height:1.6;
    -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:720px;margin:0 auto;padding:0 20px 64px}

  header{border-bottom:3px double var(--ink);padding:28px 0 16px;margin-bottom:8px}
  h1{
    font-family:'Zen Old Mincho',serif;font-weight:900;
    font-size:clamp(26px,6vw,38px);letter-spacing:.06em;
  }
  .dateline{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px;margin-top:6px}
  .dateline .d{font-size:15px;font-weight:700;letter-spacing:.05em}
  .dateline .u{font-size:12px;color:var(--ink-soft)}

  .stats{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--rule);border-radius:6px;overflow:hidden;margin:20px 0 28px}
  .stat{padding:12px 8px;text-align:center;background:var(--panel)}
  .stat+.stat{border-left:1px solid var(--rule)}
  .stat .l{font-size:11px;color:var(--ink-soft);letter-spacing:.08em}
  .stat .v{font-size:clamp(15px,3.4vw,20px);font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
  .stat .v.up{color:var(--vermilion)}
  .stat .v.down{color:var(--indigo)}

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
  <p class="note">理論株価 ＝ EPS $eps 円 × PER倍率（加重平均ベース）。朱色の線が現在の日経平均の位置です。</p>

  <table>
    <thead>
      <tr><th>PER</th><th>理論株価</th><th>現在値との差</th></tr>
    </thead>
    <tbody>
$rows
    </tbody>
  </table>

  <footer>
    データ出所: $source。EPSは「日経平均÷PER(加重平均)」で算出。
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

    rows = []
    marker_inserted = False
    for p in range(PER_MAX, PER_MIN - 1, -1):
        price = eps * p
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

    src = rec.get("source", "")
    if "公式" in src or "プロフィル" in src:
        source_html = ('<a href="https://indexes.nikkei.co.jp/nkave/archives/summary" '
                       'target="_blank" rel="noopener">日経平均プロフィル</a>')
    else:
        source_html = ('<a href="https://nikkei225jp.com/data/per.php" '
                       'target="_blank" rel="noopener">nikkei225jp.com</a>')

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
        source=source_html,
    )


def main():
    rec = None
    errors = []
    for name, fn in (("公式", fetch_official), ("フォールバック", fetch_fallback)):
        try:
            rec = fn()
            print(f"[{name}] 取得成功: {rec['date']} "
                  f"日経平均 {rec['nikkei']:,.2f} / PER {rec['per']:.2f} / "
                  f"EPS {rec['eps']:,.2f}")
            break
        except Exception as e:
            errors.append(f"[{name}] {e}")
            print(f"[{name}] 失敗: {e}")

    if rec is None:
        print("エラー: すべてのデータ源で取得に失敗しました")
        for e in errors:
            print("  " + e)
        sys.exit(1)

    html = build_html(rec)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 生成完了: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
