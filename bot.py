import os
import datetime as dt
import requests
import yfinance as yf

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FINNHUB_KEY = os.environ["FINNHUB_KEY"]

# Dina aktier. Svenska aktier slutar på .ST
TICKERS = [
    "AMD", "AMZN", "AAPL", "AMAT", "ACHR", "ARM", "ASTS", "CRWV", "GLW",
    "GDC", "ISRG", "JOBY", "LRCX", "MRVL", "MU", "MSFT", "MINEST.ST",
    "NIO", "NVDA", "ORCL", "PONY", "RDW", "RR", "RGTI", "RKLB", "SERV",
    "SILEX.ST", "SOUN", "TTWO", "TSLA", "VRT", "VER.ST", "XPEV",
]

# Nyheter som innehåller dessa ord skickas till dig
KEYWORDS = [
    "partner", "partnership", "agreement", "contract", "acquire",
    "acquisition", "merger", "fda", "approval", "guidance", "upgrade",
    "downgrade", "offering", "lawsuit", "investigation", "order",
    "collaboration", "deal", "launch",
]

today = dt.date.today()


def send(text):
    # Telegram tillåter max ca 4000 tecken per meddelande
    for i in range(0, len(text), 3800):
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text[i:i + 3800],
                  "disable_web_page_preview": True},
            timeout=30,
        )


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def to_date(x):
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    return None


def check_dates(t):
    """Rapportdatum och utdelning inom 7 dagar."""
    out = []
    try:
        cal = yf.Ticker(t).calendar or {}
    except Exception:
        return out
    for d in cal.get("Earnings Date", []) or []:
        d = to_date(d)
        if d and 0 <= (d - today).days <= 7:
            out.append(f"📅 Rapport om {(d - today).days} dagar ({d})")
            break
    ex = to_date(cal.get("Ex-Dividend Date"))
    if ex and 0 <= (ex - today).days <= 7:
        out.append(f"💰 Utdelning (ex-datum) om {(ex - today).days} dagar ({ex})")
    return out


def check_signals(t):
    """RSI, glidande medelvärden och stora rörelser."""
    out = []
    try:
        close = yf.Ticker(t).history(period="1y")["Close"].dropna()
    except Exception:
        return out
    if len(close) < 60:
        return out

    change = (close.iloc[-1] / close.iloc[-2] - 1) * 100
    if abs(change) >= 7:
        pil = "🚀" if change > 0 else "🔻"
        out.append(f"{pil} Rörelse senaste dagen: {change:+.1f}%")

    r = rsi(close).iloc[-1]
    if r < 30:
        out.append(f"🟢 Signal: RSI {r:.0f} (översåld, möjligt köpläge)")
    elif r > 70:
        out.append(f"🔴 Signal: RSI {r:.0f} (överköpt, möjligt säljläge)")

    if len(close) >= 205:
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        diff = ma50 - ma200
        recent = diff.iloc[-5:]
        if recent.iloc[0] < 0 < recent.iloc[-1]:
            out.append("🟢 Signal: Golden cross (50d korsade över 200d)")
        elif recent.iloc[0] > 0 > recent.iloc[-1]:
            out.append("🔴 Signal: Death cross (50d korsade under 200d)")
    return out


def check_news(t):
    """Nyheter om partnerskap, avtal m.m. (endast amerikanska aktier)."""
    if t.endswith(".ST"):
        return []
    out = []
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": t, "from": str(today - dt.timedelta(days=1)),
                    "to": str(today), "token": FINNHUB_KEY},
            timeout=30,
        )
        items = r.json()
    except Exception:
        return out
    if not isinstance(items, list):
        return out
    seen = set()
    for n in items:
        head = n.get("headline", "")
        if head in seen:
            continue
        if any(k in head.lower() for k in KEYWORDS):
            seen.add(head)
            out.append(f"📰 {head}\n{n.get('url', '')}")
        if len(out) >= 2:
            break
    return out


def main():
    lines = []
    for t in TICKERS:
        items = check_dates(t) + check_signals(t) + check_news(t)
        if items:
            lines.append(f"━━ {t} ━━\n" + "\n".join(items))

    header = f"📊 Aktierapport {today}\n\n"
    if lines:
        send(header + "\n\n".join(lines) +
             "\n\n⚠️ Signaler är en fingervisning, inte finansiell rådgivning.")
    else:
        send(header + "Inga viktiga händelser idag. ✅")


if __name__ == "__main__":
    main()
