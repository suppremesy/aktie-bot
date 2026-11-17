import os, sys, json, time, datetime as dt, requests
for k in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "FINNHUB_KEY"):
    os.environ.setdefault(k, "x")
import yfinance as yf
from bot import TICKERS, rsi, RSI_KOP, RSI_SALJ, KEYWORDS, send

# ---- Inställningar ----
RORELSE = 8                     # larma vid dagsrörelse på minst så här många procent
PRISLARM = {}                   # exempel: {"NVDA": {"over": 200, "under": 150}}
SF = "alerts_state.json"
now = dt.datetime.now(dt.timezone.utc)
today = str(now.date())


def alerts():
    st = json.load(open(SF)) if os.path.exists(SF) else {}
    sent, zone = st.get("sent", {}), st.get("zone", {})
    sent = {k: v for k, v in sent.items() if v >= str(now.date() - dt.timedelta(days=7))}
    out = []
    for t in TICKERS:
        nm = t.replace(".ST", "")
        try:
            c = yf.Ticker(t).history(period="1y")["Close"].dropna()
        except Exception:
            continue
        if len(c) < 60:
            continue
        price, ch, r = float(c.iloc[-1]), float((c.iloc[-1] / c.iloc[-2] - 1) * 100), float(rsi(c).iloc[-1])
        k = f"move:{t}:{today}:{ch > 0}"
        if abs(ch) >= RORELSE and k not in sent:
            sent[k] = today; out.append(f"{'🚀' if ch > 0 else '🔻'} <b>{nm}</b> {ch:+.1f}% idag")
        z = "kop" if r < RSI_KOP else "salj" if r > RSI_SALJ else "none"
        if z != "none" and zone.get(t) != z:
            out.append(f"{'🟢' if z == 'kop' else '🔴'} <b>{nm}</b> {'möjligt köpläge' if z == 'kop' else 'möjligt säljläge'} (RSI {r:.0f})")
        zone[t] = z
        for kind, lvl in (PRISLARM.get(nm, {}) or {}).items():
            k = f"lvl:{nm}:{kind}:{lvl}:{today}"
            if k not in sent and ((kind == "over" and price >= lvl) or (kind == "under" and price <= lvl)):
                sent[k] = today; out.append(f"🎯 <b>{nm}</b> {'över' if kind == 'over' else 'under'} {lvl} (nu {price:.2f})")
        if not t.endswith(".ST") and os.environ["FINNHUB_KEY"] != "x":
            try:
                items = requests.get("https://finnhub.io/api/v1/company-news", params={
                    "symbol": t, "from": str(now.date() - dt.timedelta(days=1)), "to": today, "token": os.environ["FINNHUB_KEY"]}, timeout=30).json()
            except Exception:
                items = []
            time.sleep(1.0)
            for n in items if isinstance(items, list) else []:
                h, u = n.get("headline", ""), n.get("url", "")
                if n.get("datetime", 0) >= now.timestamp() - 3 * 3600 and u not in sent and any(x in h.lower() for x in KEYWORDS):
                    sent[u] = today; out.append(f"📰 <b>{nm}</b>: {h[:110]} (<a href=\"{u}\">läs</a>)"); break
    if out:
        send("🔔 <b>Aktielarm</b>\n\n" + "\n".join(out[:12]))
    json.dump({"sent": sent, "zone": zone}, open(SF, "w"))


def weekly():
    repo = os.environ.get("GITHUB_REPOSITORY", "/").split("/")
    d = requests.get(f"https://{repo[0].lower()}.github.io/{repo[1]}/data.json", timeout=30).json()
    S = [s for s in d["stocks"] if s.get("w") is not None]
    avg = sum(s["w"] for s in S) / len(S)
    nq = next((m for m in d["market"] if m["n"] == "Nasdaq"), {})
    S.sort(key=lambda s: -s["w"])
    l = ["📅 <b>Veckosammanfattning</b>", "",
         f"Portföljen (snitt): <b>{avg:+.1f}%</b>" + (f" · Nasdaq {nq['w']:+.1f}%" if nq.get("w") is not None else ""),
         "Bäst: " + ", ".join(f"{s['t']} {s['w']:+.0f}%" for s in S[:3]),
         "Sämst: " + ", ".join(f"{s['t']} {s['w']:+.0f}%" for s in S[-3:])]
    rep = sorted((s for s in d["stocks"] if s.get("earn_days") is not None and s["earn_days"] <= 7), key=lambda s: s["earn_days"])
    if rep:
        l += ["", "📅 Rapporter kommande vecka: " + ", ".join(f"{s['t']} ({s['earn'][8:]}/{s['earn'][5:7]})" for s in rep)]
    mac = [m for m in d.get("macro", []) if m["d"] <= str(now.date() + dt.timedelta(days=7))]
    if mac:
        l += ["", "🏛️ " + ", ".join(f"{m['n']} ({m['d'][8:]}/{m['d'][5:7]})" for m in mac)]
    if d["picks"]:
        l += ["", "🔍 Toppval: " + ", ".join(f"{p['t']} (riktkurs {p['upside']:+d}%)" for p in d["picks"][:3])]
    send("\n".join(l))


weekly() if len(sys.argv) > 1 and sys.argv[1] == "weekly" else alerts()
