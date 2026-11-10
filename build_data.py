import os, json, time, datetime as dt
import requests

# Återanvänder listan och inställningarna från bot.py
for k in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "FINNHUB_KEY"):
    os.environ.setdefault(k, "x")
import yfinance as yf
from bot import TICKERS, rsi, to_date, RSI_KOP, RSI_SALJ, KEYWORDS

FKEY = os.environ["FINNHUB_KEY"]
today = dt.date.today()

NAMES = {
    "AMD": "Advanced Micro Devices", "AMZN": "Amazon", "AAPL": "Apple",
    "AMAT": "Applied Materials", "ACHR": "Archer Aviation", "ARM": "Arm Holdings",
    "ASTS": "AST SpaceMobile", "CRWV": "CoreWeave", "GLW": "Corning",
    "GDC": "GD Culture Group", "ISRG": "Intuitive Surgical", "JOBY": "Joby Aviation",
    "LRCX": "Lam Research", "MRVL": "Marvell", "MU": "Micron", "MSFT": "Microsoft",
    "MINEST.ST": "Minesto", "NIO": "NIO", "NVDA": "NVIDIA", "ORCL": "Oracle",
    "PONY": "Pony AI", "RDW": "Redwire", "RR": "Richtech Robotics",
    "RGTI": "Rigetti Computing", "RKLB": "Rocket Lab", "SERV": "Serve Robotics",
    "SILEX.ST": "Silex Microsystems", "SOUN": "SoundHound AI", "TTWO": "Take-Two",
    "TSLA": "Tesla", "VRT": "Vertiv", "VER.ST": "Verve Group", "XPEV": "XPeng",
}

# Tech-aktier att söka bland (de du redan äger sorteras bort automatiskt)
CANDIDATES = {
    "COHR": "Coherent", "AVGO": "Broadcom", "TSM": "TSMC", "ASML": "ASML",
    "PLTR": "Palantir", "CRWD": "CrowdStrike", "NOW": "ServiceNow", "SNOW": "Snowflake",
    "PANW": "Palo Alto Networks", "NET": "Cloudflare", "DDOG": "Datadog", "ANET": "Arista Networks",
    "QCOM": "Qualcomm", "INTC": "Intel", "SMCI": "Super Micro", "DELL": "Dell",
    "ON": "ON Semiconductor", "TXN": "Texas Instruments", "ADBE": "Adobe", "CRM": "Salesforce",
    "SHOP": "Shopify", "META": "Meta", "GOOGL": "Alphabet", "NFLX": "Netflix",
    "APP": "AppLovin", "MDB": "MongoDB", "ZS": "Zscaler", "TEAM": "Atlassian",
    "IONQ": "IonQ", "LITE": "Lumentum", "CIEN": "Ciena", "ALAB": "Astera Labs",
    "CLS": "Celestica", "KLAC": "KLA", "SNPS": "Synopsys", "CDNS": "Cadence",
    "MPWR": "Monolithic Power", "AMKR": "Amkor", "FTNT": "Fortinet", "UBER": "Uber",
}
STRONG = ["partnership", "partners with", "partner with", "collaboration",
          "agreement", "contract", "acquire", "acquisition", "merger"]


def get_news(t):
    """Viktigaste nyheten senaste 7 dagarna (nyckelordsträff först, annars senaste)."""
    try:
        items = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": t, "from": str(today - dt.timedelta(days=7)),
                    "to": str(today), "token": FKEY}, timeout=30).json()
    except Exception:
        items = []
    time.sleep(1.0)  # gratisplanen tillåter ca 60 anrop/minut
    if not isinstance(items, list):
        return None
    items = [i for i in items if i.get("headline")]
    if not items:
        return None
    items.sort(key=lambda i: i.get("datetime", 0), reverse=True)
    hot = [i for i in items if any(k in i["headline"].lower() for k in KEYWORDS)]
    n = (hot or items)[0]
    summ = (n.get("summary") or "").strip()
    if len(summ) > 280:
        summ = summ[:280].rsplit(" ", 1)[0] + "…"
    return {"h": n["headline"][:140], "s": summ, "u": n.get("url", ""),
            "src": n.get("source", ""), "dt": n.get("datetime", 0), "hot": bool(hot)}


def partnership(news):
    return bool(news) and any(k in (news["h"] + " " + news["s"]).lower() for k in STRONG)


def close_series(t):
    c = yf.Ticker(t).history(period="1y")["Close"].dropna()
    return c if len(c) >= 60 else None


# ---------- Dina aktier ----------
stocks = []
for t in TICKERS:
    try:
        tk = yf.Ticker(t)
        close = close_series(t)
        if close is None:
            continue
        r = float(rsi(close).iloc[-1])
        cal = tk.calendar or {}
        earn = None
        for d in cal.get("Earnings Date", []) or []:
            d = to_date(d)
            if d and d >= today:
                earn = d
                break
        ex = to_date(cal.get("Ex-Dividend Date"))
        if ex and ex < today:
            ex = None
        stocks.append({
            "t": t.replace(".ST", ""), "name": NAMES.get(t, t),
            "cur": "SEK" if t.endswith(".ST") else "USD",
            "price": round(float(close.iloc[-1]), 2),
            "change": round(float((close.iloc[-1] / close.iloc[-2] - 1) * 100), 2),
            "rsi": round(r),
            "signal": "kop" if r < RSI_KOP else "salj" if r > RSI_SALJ else "none",
            "earn": str(earn) if earn else None,
            "earn_days": (earn - today).days if earn else None,
            "ex": str(ex) if ex else None,
            "news": None if t.endswith(".ST") else get_news(t),
        })
    except Exception as e:
        print("Hoppade över", t, e)

# ---------- Upptäck nya aktier ----------
cands = []
for t, name in CANDIDATES.items():
    if t in TICKERS:
        continue
    try:
        tk = yf.Ticker(t)
        close = close_series(t)
        info = tk.info or {}
        if close is None or not info:
            continue
        price = float(close.iloc[-1])
        dip = (1 - price / float(close.max())) * 100
        r = float(rsi(close).iloc[-1])
        target = info.get("targetMeanPrice")
        n = info.get("numberOfAnalystOpinions") or 0
        rec = info.get("recommendationMean")
        upside = (target / price - 1) * 100 if target else None
        if upside is None or n < 8 or upside < 8 or (rec and rec > 3.0):
            continue
        s, why = 0, []
        s += 3 if upside >= 30 else 2 if upside >= 15 else 1
        why.append(f"Riktkurs {upside:+.0f}% (snitt ${target:.0f}, {n} analytiker)")
        if rec and rec <= 2.0:
            s += 2
            why.append("Analytikerna: starkt köp")
        elif rec and rec <= 2.5:
            s += 1
            why.append("Analytikerna: köp")
        if dip >= 25:
            s += 2
        elif dip >= 15:
            s += 1
        if dip >= 10:
            why.append(f"{dip:.0f}% under 52-veckorstoppen")
        if r < 35:
            s += 2
        elif r < 45:
            s += 1
        if r < 45:
            why.append(f"RSI {r:.0f} (nedtryckt)")
        cands.append({
            "t": t, "name": name, "price": round(price, 2),
            "change": round(float((close.iloc[-1] / close.iloc[-2] - 1) * 100), 2),
            "rsi": round(r), "upside": round(upside), "dip": round(dip),
            "score": s, "why": why, "news": None, "_dip_ok": dip >= 15 or r < 40,
        })
        time.sleep(0.3)
    except Exception as e:
        print("Hoppade över kandidat", t, e)

cands.sort(key=lambda c: -c["score"])
for c in cands[:10]:                       # nyheter bara för de bästa
    c["news"] = get_news(c["t"])
    if partnership(c["news"]):
        c["score"] += 1
        c["why"].append("Aktuellt partnerskap/avtal i nyheterna")

picks = []
for c in sorted(cands, key=lambda c: -c["score"]):
    ok = c.pop("_dip_ok")
    if c["score"] >= 8 and ok:
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
        h = yf.Ticker(sym).history(period="5d")["Close"].dropna()
        market.append({"n": nm, "c": round(float((h.iloc[-1] / h.iloc[-2] - 1) * 100), 2)})
    except Exception:
        pass

os.makedirs("site", exist_ok=True)
with open("site/data.json", "w") as f:
    json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(),
               "stocks": stocks, "picks": picks, "market": market}, f)
print(len(stocks), "aktier,", len(picks), "rekommendationer")
