import os, json, time, datetime as dt
import requests
for k in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "FINNHUB_KEY"):
    os.environ.setdefault(k, "x")
import yfinance as yf
from bot import TICKERS, rsi, to_date, RSI_KOP, RSI_SALJ, KEYWORDS, TOKEN, CHAT_ID

FKEY = os.environ["FINNHUB_KEY"]
today = dt.date.today()

NAMES = {
    "AMD": "Advanced Micro Devices", "AMZN": "Amazon", "AAPL": "Apple", "AMAT": "Applied Materials",
    "ACHR": "Archer Aviation", "ARM": "Arm Holdings", "ASTS": "AST SpaceMobile", "CRWV": "CoreWeave",
    "GLW": "Corning", "GDC": "GD Culture Group", "ISRG": "Intuitive Surgical", "JOBY": "Joby Aviation",
    "LRCX": "Lam Research", "MRVL": "Marvell", "MU": "Micron", "MSFT": "Microsoft", "MINEST.ST": "Minesto",
    "NIO": "NIO", "NVDA": "NVIDIA", "ORCL": "Oracle", "PONY": "Pony AI", "RDW": "Redwire",
    "RR": "Richtech Robotics", "RGTI": "Rigetti Computing", "RKLB": "Rocket Lab", "SERV": "Serve Robotics",
    "SILEX.ST": "Silex Microsystems", "SOUN": "SoundHound AI", "TTWO": "Take-Two", "TSLA": "Tesla",
    "VRT": "Vertiv", "VER.ST": "Verve Group", "XPEV": "XPeng",
}
THEMES = {
    "AI & chip": ["AMD", "NVDA", "MU", "MRVL", "AMAT", "LRCX", "ARM"],
    "Datacenter & moln": ["CRWV", "VRT", "GLW", "ORCL", "MSFT", "AMZN"],
    "Mobilitet & flyg": ["TSLA", "NIO", "XPEV", "PONY", "ACHR", "JOBY"],
    "Rymd": ["ASTS", "RKLB", "RDW"],
    "Robotar & AI-appar": ["SERV", "RR", "SOUN"],
    "Kvant": ["RGTI"],
}
THEME_OF = {t: th for th, ts in THEMES.items() for t in ts}

# Fler datum kan läggas till här (datum, text)
MACRO = [("2026-12-09", "FOMC – USA:s räntebesked")]

C = """COHR Coherent|AVGO Broadcom|TSM TSMC|ASML ASML|PLTR Palantir|CRWD CrowdStrike|NOW ServiceNow|SNOW Snowflake|PANW Palo Alto|NET Cloudflare|DDOG Datadog|ANET Arista|QCOM Qualcomm|INTC Intel|SMCI Super Micro|DELL Dell|ON ON Semi|TXN Texas Instruments|ADBE Adobe|CRM Salesforce|SHOP Shopify|META Meta|GOOGL Alphabet|NFLX Netflix|APP AppLovin|MDB MongoDB|ZS Zscaler|TEAM Atlassian|IONQ IonQ|LITE Lumentum|CIEN Ciena|ALAB Astera Labs|CLS Celestica|KLAC KLA|SNPS Synopsys|CDNS Cadence|MPWR Monolithic Power|AMKR Amkor|FTNT Fortinet|UBER Uber|ADI Analog Devices|NXPI NXP|MCHP Microchip|TER Teradyne|ONTO Onto Innovation|CSCO Cisco|HPE HPE|NTAP NetApp|WDC Western Digital|STX Seagate|PSTG Pure Storage|OKTA Okta|S SentinelOne|INTU Intuit|WDAY Workday|ADSK Autodesk|HUBS HubSpot|TTD Trade Desk|DASH DoorDash|SPOT Spotify|COIN Coinbase|HOOD Robinhood|CRDO Credo|FN Fabrinet|CAMT Camtek|QBTS D-Wave|IOT Samsara|DOCN DigitalOcean|ESTC Elastic|GTLB GitLab|PATH UiPath"""
CANDIDATES = dict(x.split(" ", 1) for x in C.split("|"))
STRONG = ["partnership", "partners with", "partner with", "collaboration", "agreement", "contract", "acquire", "acquisition", "merger"]


def get_news(t):
    try:
        items = requests.get("https://finnhub.io/api/v1/company-news", params={
            "symbol": t, "from": str(today - dt.timedelta(days=7)), "to": str(today), "token": FKEY}, timeout=30).json()
    except Exception:
        items = []
    time.sleep(1.0)
    items = [i for i in items if isinstance(items, list) and i.get("headline")] if isinstance(items, list) else []
    if not items:
        return None
    items.sort(key=lambda i: i.get("datetime", 0), reverse=True)
    hot = [i for i in items if any(k in i["headline"].lower() for k in KEYWORDS)]
    n = (hot or items)[0]
    s = (n.get("summary") or "").strip()
    if len(s) > 280:
        s = s[:280].rsplit(" ", 1)[0] + "…"
    return {"h": n["headline"][:140], "s": s, "u": n.get("url", ""), "src": n.get("source", ""),
            "dt": n.get("datetime", 0), "hot": bool(hot)}


def closes(t, period="1y"):
    c = yf.Ticker(t).history(period=period)["Close"].dropna()
    return c if len(c) >= 60 else None


def pct(c, n):
    return round(float((c.iloc[-1] / c.iloc[-1 - n] - 1) * 100), 2) if len(c) > n else None


def extras(tk):
    e = {"beat": None, "up": 0, "down": 0}
    try:
        s = tk.earnings_dates["Surprise(%)"].dropna().head(4)
        if len(s):
            e["beat"] = f"{int((s > 0).sum())}/{len(s)}"
    except Exception:
        pass
    try:
        ug = tk.upgrades_downgrades
        idx = ug.index.tz_localize(None) if getattr(ug.index, "tz", None) else ug.index
        r = ug[idx >= dt.datetime.now() - dt.timedelta(days=30)]
        e["up"], e["down"] = int((r["Action"] == "up").sum()), int((r["Action"] == "down").sum())
    except Exception:
        pass
    return e


def base(t, close):
    return {"price": round(float(close.iloc[-1]), 2), "change": pct(close, 1), "rsi": round(float(rsi(close).iloc[-1])),
            "spark": [round(float(x), 2) for x in close.iloc[-30:]], "w": pct(close, 5), "m1": pct(close, 21), "m3": pct(close, 63)}


# ---------- Dina aktier ----------
stocks = []
for t in TICKERS:
    try:
        tk = yf.Ticker(t)
        close = closes(t)
        if close is None:
            continue
        b = base(t, close)
        cal = tk.calendar or {}
        earn = next((d for d in (to_date(x) for x in cal.get("Earnings Date", []) or []) if d and d >= today), None)
        ex = to_date(cal.get("Ex-Dividend Date"))
        ex = ex if ex and ex >= today else None
        r = b["rsi"]
        b.update({"t": t.replace(".ST", ""), "name": NAMES.get(t, t), "cur": "SEK" if t.endswith(".ST") else "USD",
                  "signal": "kop" if r < RSI_KOP else "salj" if r > RSI_SALJ else "none",
                  "earn": str(earn) if earn else None, "earn_days": (earn - today).days if earn else None,
                  "ex": str(ex) if ex else None, "theme": THEME_OF.get(t, "Övrigt"), "ext": extras(tk),
                  "news": None if t.endswith(".ST") else get_news(t)})
        stocks.append(b)
    except Exception as e:
        print("Hoppade över", t, e)

# ---------- Upptäck ----------
cands = []
for t, name in CANDIDATES.items():
    if t in TICKERS:
        continue
    try:
        tk = yf.Ticker(t)
        close = closes(t)
        info = tk.info or {}
        if close is None or not info:
            continue
        b = base(t, close)
        price = b["price"]
        dip = (1 - price / float(close.max())) * 100
        r = b["rsi"]
        target, n, rec = info.get("targetMeanPrice"), info.get("numberOfAnalystOpinions") or 0, info.get("recommendationMean")
        up = (target / price - 1) * 100 if target else None
        if up is None or n < 8 or up < 8 or (rec and rec > 3.0):
            continue
        s = 3 if up >= 30 else 2 if up >= 15 else 1
        why = [f"Riktkurs {up:+.0f}% (snitt ${target:.0f}, {n} analytiker)"]
        if rec and rec <= 2.0:
            s += 2; why.append("Analytikerna: starkt köp")
        elif rec and rec <= 2.5:
            s += 1; why.append("Analytikerna: köp")
        s += 2 if dip >= 25 else 1 if dip >= 15 else 0
        if dip >= 10:
            why.append(f"{dip:.0f}% under 52-veckorstoppen")
        s += 2 if r < 35 else 1 if r < 45 else 0
        if r < 45:
            why.append(f"RSI {r} (nedtryckt)")
        g, om, fpe, de = info.get("revenueGrowth"), info.get("operatingMargins"), info.get("forwardPE"), info.get("debtToEquity")
        if g is not None and g >= 0.2:
            s += 1; why.append(f"Omsättning {g*100:+.0f}% y/y")
        if om is not None and om > 0.15:
            s += 1; why.append(f"Rörelsemarginal {om*100:.0f}%")
        elif om is not None and om < 0:
            s -= 1; why.append("Går med förlust")
        if fpe and 0 < fpe <= 35:
            s += 1; why.append(f"Fwd P/E {fpe:.0f}")
        elif fpe and fpe > 90:
            s -= 1
        if de and de > 250:
            s -= 1
        b.update({"t": t, "name": name, "upside": round(up), "dip": round(dip), "score": s, "why": why,
                  "news": None, "ext": None, "warn": False, "_ok": dip >= 15 or r < 40})
        cands.append(b)
        time.sleep(0.3)
    except Exception as e:
        print("Hoppade över kandidat", t, e)

cands.sort(key=lambda c: -c["score"])
for c in cands[:12]:                    # extra data bara för de bästa
    tk = yf.Ticker(c["t"])
    c["ext"] = extras(tk)
    net = c["ext"]["up"] - c["ext"]["down"]
    if net >= 2:
        c["score"] += 1; c["why"].append(f"Analytiker höjer ({c['ext']['up']} upp/{c['ext']['down']} ner, 30 d)")
    elif net <= -2:
        c["score"] -= 1; c["why"].append(f"Analytiker sänker ({c['ext']['up']} upp/{c['ext']['down']} ner, 30 d)")
    try:
        e = next((d for d in (to_date(x) for x in (tk.calendar or {}).get("Earnings Date", []) or []) if d and d >= today), None)
        if e and (e - today).days <= 7:
            c["warn"] = True; c["why"].append(f"⚠️ Rapport om {(e - today).days} dagar – risktid att köpa")
    except Exception:
        pass
    c["news"] = get_news(c["t"])
    if c["news"] and any(k in (c["news"]["h"] + " " + c["news"]["s"]).lower() for k in STRONG):
        c["score"] += 1; c["why"].append("Aktuellt partnerskap/avtal i nyheterna")

picks = []
for c in sorted(cands, key=lambda c: -c["score"]):
    ok, warn = c.pop("_ok"), c.pop("warn")
    if c["score"] >= 9 and ok and not warn:
        c["color"] = "green"
    elif c["score"] >= 6:
        c["color"] = "yellow"
    elif c["score"] >= 4:
        c["color"] = "blue"
    else:
        continue
    picks.append(c)
    if len(picks) == 5:
        break

# ---------- Marknad ----------
market = []
for sym, nm in (("^IXIC", "Nasdaq"), ("^GSPC", "S&P 500")):
    try:
        h = yf.Ticker(sym).history(period="2y")["Close"].dropna()
        market.append({"n": nm, "c": pct(h, 1), "w": pct(h, 5), "m1": pct(h, 21), "m3": pct(h, 63)})
    except Exception:
        pass

# ---------- Facit (backtest) ----------
HF = "history.json"
hist = json.load(open(HF)) if os.path.exists(HF) else []
last = {}
for e in hist:
    last[e["t"]] = max(last.get(e["t"], "0"), e["d"])
new_green = []
for p in picks:
    if p["t"] not in last or (today - dt.date.fromisoformat(last[p["t"]])).days > 30:
        hist.append({"d": str(today), "t": p["t"], "c": p["color"], "p": p["price"]})
        if p["color"] == "green":
            new_green.append(p)
hist = hist[-600:]
json.dump(hist, open(HF, "w"))

cache = {}
def series(t):
    if t not in cache:
        try:
            cache[t] = yf.Ticker(t).history(period="2y")["Close"].dropna()
        except Exception:
            cache[t] = None
    return cache[t]
def at(s, d):
    x = s[s.index.date >= d]
    return float(x.iloc[0]) if len(x) else None

facit = []
bench = series("^IXIC")
for col in ("green", "yellow", "blue"):
    for h in (30, 90):
        rows = []
        for e in (x for x in hist if x["c"] == col):
            d0 = dt.date.fromisoformat(e["d"]); d1 = d0 + dt.timedelta(days=h)
            s = series(e["t"])
            if d1 > today or s is None or bench is None:
                continue
            p1, b0, b1 = at(s, d1), at(bench, d0), at(bench, d1)
            if p1 and b0 and b1:
                rows.append((p1 / e["p"] - 1, (p1 / e["p"]) - (b1 / b0)))
        if rows:
            facit.append({"c": col, "h": h, "n": len(rows), "avg": round(sum(r[0] for r in rows) / len(rows) * 100, 1),
                          "exc": round(sum(r[1] for r in rows) / len(rows) * 100, 1),
                          "hit": round(sum(r[1] > 0 for r in rows) / len(rows) * 100)})

# ---------- Larm vid nytt starkt köpläge ----------
if TOKEN != "x":
    for p in new_green:
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "parse_mode": "HTML",
                "text": f"🟢 <b>Nytt starkt köpläge: {p['t']}</b> ({p['name']})\n" + "\n".join("• " + w for w in p["why"][:4])}, timeout=30)
        except Exception:
            pass

os.makedirs("site", exist_ok=True)
json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "stocks": stocks, "picks": picks, "market": market,
           "macro": [{"d": d, "n": n} for d, n in MACRO if d >= str(today)], "facit": facit}, open("site/data.json", "w"))
print(len(stocks), "aktier,", len(picks), "rekommendationer")
