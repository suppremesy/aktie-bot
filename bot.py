import os
import html
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

# ---- Inställningar du kan ändra ----
DAGAR_INNAN_RAPPORT = 3      # påminn om rapport/utdelning så här många dagar innan
RORELSE_PROCENT = 8          # visa bara dagsrörelser större än detta
RSI_KOP = 28                 # under detta = möjligt köpläge
RSI_SALJ = 75                # över detta = möjligt säljläge
MAX_NYHETER = 8              # max antal nyheter per rapport

# Bara nyheter med dessa ord skickas
KEYWORDS = [
    "partnership", "partners with", "agreement", "contract", "acquire",
    "acquisition", "merger", "fda", "approval", "guidance", "offering",
    "lawsuit", "investigation", "collaboration",
]

today = dt.date.today()


def esc(s):
    return html.escape(str(s))


def fmt(d):
    return d.strftime("%d/%m")


def send(text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=30,
    )


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def to_date(x):
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    return None


def short(t):
    return t.replace(".ST", "")


def main():
    rapporter, utdelning, kop, salj, rorelser, kors, nyheter = [], [], [], [], [], [], []

    # Nyhetsfönster: måndag tittar tillbaka över helgen
    dagar_tillbaka = 3 if today.weekday() == 0 else 1

    for t in TICKERS:
        namn = short(t)

        # Rapport och utdelning
        try:
            cal = yf.Ticker(t).calendar or {}
        except Exception:
            cal = {}
        for d in cal.get("Earnings Date", []) or []:
            d = to_date(d)
            if d and 0 <= (d - today).days <= DAGAR_INNAN_RAPPORT:
                rapporter.append((d, f"• <b>{namn}</b>: {fmt(d)} ({(d - today).days} dagar)"))
                break
        ex = to_date(cal.get("Ex-Dividend Date"))
        if ex and 0 <= (ex - today).days <= DAGAR_INNAN_RAPPORT:
            utdelning.append((ex, f"• <b>{namn}</b>: ex-datum {fmt(ex)}"))

        # Signaler
        try:
            close = yf.Ticker(t).history(period="1y")["Close"].dropna()
        except Exception:
            close = None
        if close is not None and len(close) > 60:
            change = (close.iloc[-1] / close.iloc[-2] - 1) * 100
            if abs(change) >= RORELSE_PROCENT:
                pil = "📈" if change > 0 else "📉"
                rorelser.append(f"{pil} <b>{namn}</b> {change:+.1f}%")

            r = rsi(close).iloc[-1]
            if r < RSI_KOP:
                kop.append(f"• <b>{namn}</b> (RSI {r:.0f})")
            elif r > RSI_SALJ:
                salj.append(f"• <b>{namn}</b> (RSI {r:.0f})")

            if len(close) >= 205:
                diff = close.rolling(50).mean() - close.rolling(200).mean()
                rec = diff.iloc[-5:]
                if rec.iloc[0] < 0 < rec.iloc[-1]:
                    kors.append(f"🟢 <b>{namn}</b>: golden cross")
                elif rec.iloc[0] > 0 > rec.iloc[-1]:
                    kors.append(f"🔴 <b>{namn}</b>: death cross")

        # Nyheter (bara amerikanska aktier), max 1 per aktie
        if not t.endswith(".ST") and len(nyheter) < MAX_NYHETER:
            try:
                items = requests.get(
                    "https://finnhub.io/api/v1/company-news",
                    params={"symbol": t,
                            "from": str(today - dt.timedelta(days=dagar_tillbaka)),
                            "to": str(today), "token": FINNHUB_KEY},
                    timeout=30,
                ).json()
            except Exception:
                items = []
            if isinstance(items, list):
                for n in items:
                    head = n.get("headline", "")
                    if any(k in head.lower() for k in KEYWORDS):
                        if len(head) > 90:
                            head = head[:87] + "..."
                        nyheter.append(
                            f"• <b>{namn}</b>: {esc(head)} "
                            f"(<a href=\"{esc(n.get('url', ''))}\">läs</a>)")
                        break

    # Bygg meddelandet i sektioner
    sektioner = []
    if rapporter:
        sektioner.append("📅 <b>Rapporter på gång</b>\n" +
                         "\n".join(x[1] for x in sorted(rapporter)))
    if utdelning:
        sektioner.append("💰 <b>Utdelning</b>\n" + "\n".join(x[1] for x in sorted(utdelning)))
    if rorelser:
        sektioner.append("⚡ <b>Stora rörelser</b>\n" + "\n".join(rorelser))
    if kop:
        sektioner.append("🟢 <b>Möjliga köplägen</b>\n" + "\n".join(kop))
    if salj:
        sektioner.append("🔴 <b>Möjliga säljlägen</b>\n" + "\n".join(salj))
    if kors:
        sektioner.append("📊 <b>Trendskiften</b>\n" + "\n".join(kors))
    if nyheter:
        sektioner.append("📰 <b>Nyheter</b>\n" + "\n".join(nyheter))

    # Skicka inget om det inte finns något relevant
    if not sektioner:
        return

    text = f"📊 <b>Aktierapport {fmt(today)}</b>\n\n" + "\n\n".join(sektioner)
    text += "\n\n<i>Signaler är fingervisningar, inte rådgivning.</i>"
    send(text[:4000])


if __name__ == "__main__":
    main()
