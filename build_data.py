import os, json, datetime as dt

# Återanvänder listan och inställningarna från bot.py (inga nycklar behövs här)
for k in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "FINNHUB_KEY"):
    os.environ.setdefault(k, "x")
import yfinance as yf
from bot import TICKERS, rsi, to_date, RSI_KOP, RSI_SALJ

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
today = dt.date.today()
stocks = []

for t in TICKERS:
    try:
        tk = yf.Ticker(t)
        close = tk.history(period="1y")["Close"].dropna()
        if len(close) < 20:
            continue
        price = float(close.iloc[-1])
        change = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
        r = float(rsi(close).iloc[-1])
        trend = None
        if len(close) >= 200:
            trend = "upp" if close.rolling(50).mean().iloc[-1] > close.rolling(200).mean().iloc[-1] else "ner"
        signal = "kop" if r < RSI_KOP else "salj" if r > RSI_SALJ else "none"
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
            "price": round(price, 2), "change": round(change, 2), "rsi": round(r),
            "trend": trend, "signal": signal,
            "earn": str(earn) if earn else None,
            "earn_days": (earn - today).days if earn else None,
            "ex": str(ex) if ex else None,
        })
    except Exception as e:
        print("Hoppade över", t, e)

os.makedirs("site", exist_ok=True)
with open("site/data.json", "w") as f:
    json.dump({"updated": dt.datetime.utcnow().isoformat() + "Z", "stocks": stocks}, f)
print(len(stocks), "aktier sparade")
