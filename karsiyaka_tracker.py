#!/usr/bin/env python3
"""Karşıyaka Basketbol takip programı (BSL 2026-27).

TBF sayfasından puan durumu + maç sonuçlarını çeker, Karşıyaka'ya ait
istatistikleri hesaplar ve grafikli tek dosyalık bir HTML raporu üretir.
Sadece standart kütüphane kullanır (Playwright opsiyonel yedek).

Kullanım:
  python karsiyaka_tracker.py                  # siteden çek, docs/index.html üret
  python karsiyaka_tracker.py --html sayfa.html  # kaydedilmiş sayfadan üret
  python karsiyaka_tracker.py --dump           # bulunan tabloları tables_dump.json'a yaz
  python karsiyaka_tracker.py --demo           # SAHTE veriyle arayüzü dene
"""
import argparse, json, re, sys, urllib.request, datetime as dt
from html import escape
from html.parser import HTMLParser
from pathlib import Path

# ---------------------------------------------------------------- AYARLAR
TEAM = "karsiyaka"  # normalize edilmiş takım adı (ş,ı,ğ... -> ascii)
# TBF'de puan durumu / fikstür ayrı sayfalardaysa buraya ekleyin:
URLS = ["https://www.tbf.org.tr/ligler/bsl-2026-2027"]
OUT = Path("docs/index.html")
HISTORY = Path("docs/history.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---------------------------------------------------------------- YARDIMCI
_TR = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissggUUoOcC".replace("U", "u").replace("O", "o")
                    .replace("C", "c"))
def norm(s):
    return re.sub(r"\s+", " ", s.translate(_TR).lower()).strip()

SCORE = re.compile(r"^\s*(\d{1,3})\s*[-–:]\s*(\d{1,3})\s*$")
DATE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._t, self._r, self._c = [], None, None, None
    def handle_starttag(self, tag, a):
        if tag == "table": self._t = []
        elif tag == "tr" and self._t is not None: self._r = []
        elif tag in ("td", "th") and self._r is not None: self._c = []
    def handle_data(self, d):
        if self._c is not None: self._c.append(d)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._c is not None:
            self._r.append(re.sub(r"\s+", " ", "".join(self._c)).strip()); self._c = None
        elif tag == "tr" and self._r is not None:
            if any(self._r): self._t.append(self._r)
            self._r = None
        elif tag == "table" and self._t is not None:
            if self._t: self.tables.append(self._t)
            self._t = None

def parse_tables(html):
    p = TableParser(); p.feed(html); return p.tables

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"[uyarı] düz istek başarısız ({e}); Playwright deneniyor...", file=sys.stderr)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(user_agent=UA)
            pg.goto(url, wait_until="networkidle", timeout=60000)
            html = pg.content(); b.close(); return html
    except Exception as e:
        sys.exit(f"Sayfa alınamadı: {e}\nÇözüm: sayfayı tarayıcıda 'Farklı kaydet' ile kaydedip --html ile verin.")

# ---------------------------------------------------------------- AYRIŞTIRMA
def find_standings(tables):
    """Başlığında 'takım' geçen ve sayısal sütunları olan tabloyu bulur."""
    for t in tables:
        hdr = [norm(c) for c in t[0]]
        if any("takim" in h for h in hdr) and len(hdr) >= 5:
            def idx(*names):
                for n in names:
                    for i, h in enumerate(hdr):
                        if h == n: return i
                return None
            ti = next(i for i, h in enumerate(hdr) if "takim" in h)
            m = dict(team=ti, played=idx("o", "oynanan", "maç", "mac"), won=idx("g", "galibiyet"),
                     lost=idx("m", "maglubiyet"), pf=idx("as", "atilan"), pa=idx("ys", "yenilen"),
                     pts=idx("p", "puan"))
            rows = []
            for r in t[1:]:
                if len(r) <= ti: continue
                g = lambda k: (int(re.sub(r"\D", "", r[m[k]]) or 0)
                               if m[k] is not None and m[k] < len(r) else 0)
                rows.append(dict(team=r[ti], played=g("played"), won=g("won"), lost=g("lost"),
                                 pf=g("pf"), pa=g("pa"), pts=g("pts")))
            if rows:
                for i, r in enumerate(rows, 1): r["rank"] = i
                return rows
    return []

def parse_matches(tables):
    """Skor deseni içeren (veya takım adı + tarih içeren) satırlardan maçları çıkarır."""
    out, seen = [], set()
    for t in tables:
        for r in t:
            if not any(TEAM in norm(c) for c in r): continue
            score = next((SCORE.match(c) for c in r if SCORE.match(c)), None)
            date = next((DATE.search(c) for c in r if DATE.search(c)), None)
            names = [c for c in r if len(c) > 2 and not SCORE.match(c) and not DATE.search(c)
                     and not re.fullmatch(r"[\d:.\s/-]+", c) and norm(c) not in ("oynandi", "tbf")]
            teams = [c for c in names if len(c) < 45][:2]
            if len(teams) < 2: continue
            d = dt.date(int(date[3]), int(date[2]), int(date[1])) if date else None
            key = (d, teams[0], teams[1])
            if key in seen: continue
            seen.add(key)
            hs, as_ = (int(score[1]), int(score[2])) if score else (None, None)
            out.append(dict(date=d.isoformat() if d else "", home=teams[0], away=teams[1], hs=hs, as_=as_))
    out.sort(key=lambda m: m["date"] or "9999")
    return out

# ---------------------------------------------------------------- İSTATİSTİK
def analyse(matches):
    played, upcoming = [], []
    for m in matches:
        home = TEAM in norm(m["home"])
        if m["hs"] is None: upcoming.append(m); continue
        pf, pa = (m["hs"], m["as_"]) if home else (m["as_"], m["hs"])
        played.append(dict(m, home_game=home, pf=pf, pa=pa, win=pf > pa,
                           opp=m["away"] if home else m["home"]))
    n = len(played)
    def avg(xs): return round(sum(xs) / len(xs), 1) if xs else 0
    st = dict(n=n, wins=sum(p["win"] for p in played), losses=sum(not p["win"] for p in played),
              avg_pf=avg([p["pf"] for p in played]), avg_pa=avg([p["pa"] for p in played]),
              best=max(played, key=lambda p: p["pf"] - p["pa"], default=None),
              worst=min(played, key=lambda p: p["pf"] - p["pa"], default=None))
    for side, key in ((True, "home"), (False, "away")):
        g = [p for p in played if p["home_game"] == side]
        st[key] = dict(n=len(g), wins=sum(p["win"] for p in g), avg_pf=avg([p["pf"] for p in g]),
                       avg_pa=avg([p["pa"] for p in g]))
    streak = 0
    for p in reversed(played):
        if streak == 0 or p["win"] == (streak > 0): streak += 1 if p["win"] else -1
        else: break
    st["streak"] = streak
    return played, upcoming, st

# ---------------------------------------------------------------- GRAFİKLER (SVG)
C_MAIN, C_OK, C_BAD, C_MUTE = "#d4a017", "#2e9e5b", "#d64545", "#8a8f98"

def svg_bars(rows):
    if not rows: return ""
    mx = max(r["pts"] for r in rows) or 1
    h = 22 * len(rows) + 10
    s = [f'<svg viewBox="0 0 640 {h}" class="chart" role="img" aria-label="Puan durumu">']
    for i, r in enumerate(rows):
        y = 5 + i * 22; w = 380 * r["pts"] / mx; me = TEAM in norm(r["team"])
        s.append(f'<text x="0" y="{y+14}" class="t{" me" if me else ""}">{r["rank"]}. {escape(r["team"][:22])}</text>'
                 f'<rect x="190" y="{y+2}" width="{w:.0f}" height="16" rx="3" fill="{C_MAIN if me else C_MUTE}" opacity="{1 if me else .45}"/>'
                 f'<text x="{196+w:.0f}" y="{y+14}" class="t">{r["pts"]}</text>')
    return "".join(s) + "</svg>"

def svg_lines(played):
    if len(played) < 2: return "<p class='mute'>Çizgi grafik için en az 2 maç gerekli.</p>"
    W, H, L, B = 640, 220, 34, 24
    vals = [p["pf"] for p in played] + [p["pa"] for p in played]
    lo, hi = min(vals) - 5, max(vals) + 5
    X = lambda i: L + (W - L - 10) * i / (len(played) - 1)
    Y = lambda v: 10 + (H - B - 10) * (1 - (v - lo) / (hi - lo))
    s = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Maç başı sayılar">']
    for v in range(int(lo // 10 * 10 + 10), int(hi), 10):
        s.append(f'<line x1="{L}" x2="{W-10}" y1="{Y(v):.0f}" y2="{Y(v):.0f}" class="grid"/><text x="0" y="{Y(v)+4:.0f}" class="t">{v}</text>')
    for key, col in (("pf", C_MAIN), ("pa", C_MUTE)):
        pts = " ".join(f"{X(i):.0f},{Y(p[key]):.0f}" for i, p in enumerate(played))
        s.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.5"/>')
        s += [f'<circle cx="{X(i):.0f}" cy="{Y(p[key]):.0f}" r="3.5" fill="{col}"><title>{escape(p["opp"])}: {p["pf"]}-{p["pa"]}</title></circle>' for i, p in enumerate(played)]
    s.append(f'<circle cx="{L+6}" cy="{H-8}" r="5" fill="{C_MAIN}"/><text x="{L+16}" y="{H-4}" class="t">Attığı</text>'
             f'<circle cx="{L+86}" cy="{H-8}" r="5" fill="{C_MUTE}"/><text x="{L+96}" y="{H-4}" class="t">Yediği</text>')
    return "".join(s) + "</svg>"

def svg_margins(played):
    if not played: return ""
    W = 640; bw = min(40, (W - 20) / len(played) - 4); mx = max(abs(p["pf"] - p["pa"]) for p in played) or 1
    s = [f'<svg viewBox="0 0 {W} 180" class="chart" role="img" aria-label="Fark">', f'<line x1="0" x2="{W}" y1="90" y2="90" class="grid"/>']
    for i, p in enumerate(played):
        d = p["pf"] - p["pa"]; h = 75 * abs(d) / mx; x = 10 + i * (bw + 4)
        s.append(f'<rect x="{x:.0f}" y="{90-h if d>0 else 90}" width="{bw:.0f}" height="{h:.0f}" fill="{C_OK if d>0 else C_BAD}" rx="2"><title>{escape(p["opp"])} {d:+d}</title></rect>')
    return "".join(s) + "</svg>"

# ---------------------------------------------------------------- HTML
CSS = """:root{--bg:#fff;--fg:#1c1e21;--card:#f5f5f2;--mute:#6b7078;--line:#ddd}
@media(prefers-color-scheme:dark){:root{--bg:#15171a;--fg:#e8e8e6;--card:#1f2226;--mute:#9aa0a8;--line:#33373d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:auto;padding:max(24px,env(safe-area-inset-top)) 16px 60px}h1{margin:0}h2{margin:32px 0 10px;font-size:18px}
.card{background:var(--card);border-radius:10px;padding:14px 16px;margin:10px 0;overflow-x:auto}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
.kpi b{display:block;font-size:24px}.kpi span,.mute{color:var(--mute);font-size:13px}
table{border-collapse:collapse;width:100%}th,td{padding:6px 8px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
tr.me{background:rgba(212,160,23,.18);font-weight:600}.W{color:#2e9e5b;font-weight:700}.L{color:#d64545;font-weight:700}
.chart{width:100%;height:auto}.chart .t{font-size:12px;fill:var(--fg)}.chart .t.me{font-weight:700}.chart .grid{stroke:var(--line)}
.form span{display:inline-block;width:26px;height:26px;line-height:26px;text-align:center;border-radius:50%;color:#fff;margin-right:4px;font-size:12px}"""

def render(standings, played, upcoming, st, demo, updated):
    me = next((r for r in standings if TEAM in norm(r["team"])), None)
    k = lambda v, l: f'<div class="card kpi"><b>{v}</b><span>{l}</span></div>'
    form = "".join(f'<span style="background:{C_OK if p["win"] else C_BAD}" title="{escape(p["opp"])} {p["pf"]}-{p["pa"]}">{"G" if p["win"] else "M"}</span>' for p in played[-8:])
    stk = st["streak"]; stk_t = f'{abs(stk)} {"galibiyet" if stk > 0 else "mağlubiyet"}' if stk else "-"
    sd = lambda d: f'{d["wins"]}G-{d["n"]-d["wins"]}M · {d["avg_pf"]}–{d["avg_pa"]}'
    rows_s = "".join(f'<tr class="{"me" if TEAM in norm(r["team"]) else ""}"><td>{r["rank"]}</td><td>{escape(r["team"])}</td><td>{r["played"]}</td><td>{r["won"]}</td><td>{r["lost"]}</td><td>{r["pf"]}</td><td>{r["pa"]}</td><td>{r["pf"]-r["pa"]:+d}</td><td><b>{r["pts"]}</b></td></tr>' for r in standings)
    rows_m = "".join(f'<tr><td>{p["date"]}</td><td>{"İç" if p["home_game"] else "Dep"}</td><td>{escape(p["opp"])}</td><td>{p["pf"]}–{p["pa"]}</td><td class="{"W" if p["win"] else "L"}">{"G" if p["win"] else "M"}</td></tr>' for p in reversed(played))
    rows_u = "".join(f'<tr><td>{m["date"]}</td><td>{escape(m["home"])}</td><td>{escape(m["away"])}</td></tr>' for m in upcoming[:6])
    best = st["best"]; worst = st["worst"]
    extra = (f'<p>En farklı galibiyet: <b>{best["pf"]}–{best["pa"]}</b> ({escape(best["opp"])})<br>'
             f'En ağır sonuç: <b>{worst["pf"]}–{worst["pa"]}</b> ({escape(worst["opp"])})</p>') if best else ""
    banner = '<div class="card" style="border-left:4px solid #d64545"><b>DEMO:</b> Aşağıdaki veriler sahtedir.</div>' if demo else ""
    return f"""<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Karşıyaka Basketbol – BSL 2026-27</title><link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icon-180.png"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Karşıyaka"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="theme-color" content="#d4a017"><style>{CSS}</style><main>
<h1>Karşıyaka Basketbol</h1><div class="mute">BSL 2026-27 · Kaynak: tbf.org.tr · Güncelleme: {updated}</div>{banner}
<div class="kpis">{k(f'{me["rank"]}.' if me else '-', 'Sıra')}{k(f'{st["wins"]}G / {st["losses"]}M', 'Galibiyet / Mağlubiyet')}{k(st["avg_pf"], 'Attığı sayı ort.')}{k(st["avg_pa"], 'Yediği sayı ort.')}{k(f'{st["avg_pf"]-st["avg_pa"]:+.1f}', 'Fark ort.')}{k(stk_t, 'Seri')}</div>
<h2>Son form</h2><div class="card form">{form or '<span class="mute">Henüz maç yok</span>'}</div>
<h2>Puan durumu</h2><div class="card"><table><tr><th>#</th><th>Takım</th><th>O</th><th>G</th><th>M</th><th>AS</th><th>YS</th><th>AV</th><th>P</th></tr>{rows_s}</table></div>
<div class="card">{svg_bars(standings)}</div>
<h2>Maç başı sayılar</h2><div class="card">{svg_lines(played)}</div>
<h2>Maç farkı</h2><div class="card">{svg_margins(played)}<div class="mute">Yeşil: galibiyet farkı · Kırmızı: mağlubiyet farkı</div></div>
<h2>İstatistikler</h2><div class="card">İç saha: <b>{sd(st["home"])}</b><br>Deplasman: <b>{sd(st["away"])}</b><div class="mute">G-M · attığı–yediği ortalama</div>{extra}</div>
<h2>Oynanan maçlar</h2><div class="card"><table><tr><th>Tarih</th><th></th><th>Rakip</th><th>Skor</th><th></th></tr>{rows_m}</table></div>
<h2>Sıradaki maçlar</h2><div class="card">{f'<table><tr><th>Tarih</th><th>Ev sahibi</th><th>Deplasman</th></tr>{rows_u}</table>' if rows_u else '<span class="mute">Fikstürde bekleyen maç bulunamadı.</span>'}</div>
</main></html>"""

# ---------------------------------------------------------------- DEMO
def demo_data():
    teams = ["Fenerbahçe Beko", "Anadolu Efes", "Pınar Karşıyaka", "Bahçeşehir Koleji", "Tofaş", "Mersin Spor"]
    standings = [dict(rank=i + 1, team=t, played=4, won=4 - i // 2, lost=i // 2, pf=330 - i * 6, pa=300 + i * 4, pts=8 - i // 2 * 1 - (i % 2 and 0)) for i, t in enumerate(teams)]
    sc = [(88, 80, True), (79, 84, False), (95, 90, True), (84, 77, False)]
    ms = [dict(date=f"2026-10-{4 + 7*i:02d}", home="Pınar Karşıyaka" if h else o, away=o if h else "Pınar Karşıyaka",
               hs=a if h else b, as_=b if h else a) for i, ((a, b, h), o) in enumerate(zip(sc, teams[3:] + teams[:1]))]
    ms.append(dict(date="2026-11-01", home="Pınar Karşıyaka", away="Anadolu Efes", hs=None, as_=None))
    return standings, ms

# ---------------------------------------------------------------- iOS DOSYALARI
def png(size, path):
    import zlib, struct
    bg, fg = (21, 23, 26), (212, 160, 23)
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            dx, dy = x - size / 2, y - size / 2; r = (dx * dx + dy * dy) ** .5
            ball = r < size * .34 and (r > size * .31 or abs(dx) < size * .012 or abs(dy) < size * .012
                                        or abs(r - size * .2) < size * .01 and dx * dy < 0)
            rows += bytes(fg if ball else bg)
    ck = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    data = b"\x89PNG\r\n\x1a\n" + ck(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) \
        + ck(b"IDAT", zlib.compress(bytes(rows), 9)) + ck(b"IEND", b"")
    Path(path).write_bytes(data)

def write_assets(out_dir, standings, played, upcoming, st, updated):
    out_dir.mkdir(parents=True, exist_ok=True)
    png(180, out_dir / "icon-180.png"); png(512, out_dir / "icon-512.png")
    (out_dir / "manifest.webmanifest").write_text(json.dumps(dict(
        name="Karşıyaka Basketbol", short_name="Karşıyaka", start_url="./", display="standalone",
        background_color="#15171a", theme_color="#d4a017",
        icons=[dict(src="icon-180.png", sizes="180x180", type="image/png"),
               dict(src="icon-512.png", sizes="512x512", type="image/png")]), ensure_ascii=False))
    me = next((r for r in standings if TEAM in norm(r["team"])), None)
    last = played[-1] if played else None; nxt = upcoming[0] if upcoming else None
    (out_dir / "data.json").write_text(json.dumps(dict(
        updated=updated, rank=me["rank"] if me else None, points=me["pts"] if me else None,
        wins=st["wins"], losses=st["losses"], avg_pf=st["avg_pf"], avg_pa=st["avg_pa"], streak=st["streak"],
        form=["G" if p["win"] else "M" for p in played[-5:]],
        last=dict(opp=last["opp"], pf=last["pf"], pa=last["pa"], win=last["win"], home=last["home_game"], date=last["date"]) if last else None,
        next=dict(home=nxt["home"], away=nxt["away"], date=nxt["date"]) if nxt else None,
        top=[dict(rank=r["rank"], team=r["team"], pts=r["pts"]) for r in standings[:8]]), ensure_ascii=False, indent=1))

# ---------------------------------------------------------------- ANA AKIŞ
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="kaydedilmiş sayfa(lar)", nargs="*")
    ap.add_argument("--dump", action="store_true"); ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.demo:
        standings, matches = demo_data()
    else:
        pages = [Path(p).read_text(encoding="utf-8", errors="replace") for p in a.html] if a.html else [fetch(u) for u in URLS]
        tables = [t for pg in pages for t in parse_tables(pg)]
        if a.dump:
            Path("tables_dump.json").write_text(json.dumps(tables, ensure_ascii=False, indent=1)); print(f"{len(tables)} tablo -> tables_dump.json")
        standings, matches = find_standings(tables), parse_matches(tables)
        if not standings and not matches:
            sys.exit("Tablo bulunamadı. --dump ile sayfa yapısını inceleyin (JS ile yükleniyor olabilir).")
    played, upcoming, st = analyse(matches)
    updated = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(standings, played, upcoming, st, a.demo, updated), encoding="utf-8")
    write_assets(out.parent, standings, played, upcoming, st, updated)
    if not a.demo:  # haftalık geçmiş kaydı
        hist = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
        me = next((r for r in standings if TEAM in norm(r["team"])), {})
        hist.append(dict(date=dt.date.today().isoformat(), rank=me.get("rank"), pts=me.get("pts"), played=st["n"]))
        HISTORY.write_text(json.dumps(hist[-60:], ensure_ascii=False))
    print(f"Tamam: {out}  ({st['n']} oynanan, {len(upcoming)} bekleyen maç, {len(standings)} takım)")

if __name__ == "__main__":
    main()
