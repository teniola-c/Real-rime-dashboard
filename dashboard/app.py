# app.py — Nova/Neumorphic UI • Markets • Weather • Football
# -----------------------------------------------------------
# Features
# - TradingView embeds for stocks/crypto
# - Realtime crypto tiles via Binance WS (REST fallback)
# - Weather now + past (Meteostat) + 5-day forecast (OWM)
# - Football (football-data.org): today, standings, scorers
# - Pastel/neo-morphic UI with gradient hero, soft cards, KPI tiles

import os, json, time, threading, queue, requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
from websocket import WebSocketApp
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime as _dt, date as _date, timedelta as _timedelta
from meteostat import Daily, Point

# ---------------- Env ----------------
dotenv_path = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=dotenv_path, override=True)
OWM_KEY = os.getenv("OWM_API_KEY", "")
FD_TOKEN = os.getenv("FOOTBALL_DATA_TOKEN", "")
DEFAULT_CITIES = os.getenv("DEFAULT_CITIES", "Toronto,CA;Lagos,NG;London,GB")

# ---------------- Page ----------------
st.set_page_config(page_title="Markets • Weather • Football", layout="wide")

# ---------------- Theme / CSS ----------------
ACCENT = "#7c3aed"  # purple
GRAD_L = "#eef2ff"  # light indigo
GRAD_R = "#e9fdf6"  # mint

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
html, body, [class*="css"] {{ font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji","Segoe UI Emoji"; }}

:root {{
  --accent: {ACCENT};
  --muted: #6b7280;
  --bg: #f6f7fb;
  --card: #ffffff;
  --shadow1: 0 10px 20px rgba(28, 28, 40, .06);
  --shadow2: inset 0 1px 0 rgba(255,255,255,.35);
}}

body {{
  background: radial-gradient(1200px 600px at 20% -10%, {GRAD_L} 0%, transparent 50%),
              radial-gradient(1200px 700px at 100% 0%, {GRAD_R} 0%, transparent 50%),
              var(--bg);
}}

div.block-container {{ padding-top: .8rem; max-width: 1320px; }}

.hero {{
  background: linear-gradient(135deg, #ffffffaa 0%, #ffffff80 100%);
  border: 1px solid #e8ecf4;
  border-radius: 20px;
  padding: 18px 20px;
  box-shadow: var(--shadow1);
  backdrop-filter: blur(6px);
}}

.badge {{
  display:inline-flex; align-items:center; gap:8px;
  padding:6px 10px; border-radius: 999px;
  background:#f5f3ff; color:#5b21b6; border:1px solid #ede9fe;
  font-weight:600; font-size:12px;
}}
.badge span {{
  display:inline-flex; align-items:center; justify-content:center;
  width:22px;height:22px;border-radius:8px;background:var(--accent);color:#fff;font-weight:800;
}}

.top-tabs .stTabs [data-baseweb="tab"] button {{
  gap:8px; border-radius:12px !important;
  background:#ffffffcc; border:1px solid #eef2f7;
}}
.top-tabs .stTabs [data-baseweb="tab-highlight"] {{
  background: linear-gradient(180deg, #fff 0%, #f6f7fb 100%);
  border-radius:12px;
}}

.card {{
  background: var(--card);
  border: 1px solid #eef2f7;
  border-radius: 18px;
  padding: 14px 16px;
  box-shadow: var(--shadow1), var(--shadow2);
}}

.kpi {{
  background: var(--card);
  border: 1px solid #eef2f7;
  border-radius: 16px; padding: 12px 14px;
  box-shadow: var(--shadow1);
}}
.kpi .label {{ color: var(--muted); font-size:12px; }}
.kpi .row {{ display:flex; align-items:center; gap:10px; }}
.kpi .value {{ font-size:22px; font-weight:800; }}
.kpi .delta {{ font-weight:700; font-size:12px; color:#16a34a; }}
.kpi.down .delta {{ color:#dc2626; }}

.caption-muted {{ color: var(--muted); font-size:12px; }}

.sidebar .sidebar-title {{
  font-weight:800; letter-spacing:.2px; margin-bottom:.4rem;
}}

[data-testid="stMetricValue"] {{ font-weight:800; }}
[data-testid="stDataFrame"] table {{ font-size: 13px; }}

.spark .js-plotly-plot .plotly .modebar{{ display:none; }}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- Plotly palette ----------------
pio.templates["nova_light"] = pio.templates["plotly_white"]
pio.templates["nova_light"].layout.update(
    colorway=[ACCENT, "#0ea5e9", "#22c55e", "#f59e0b", "#64748b"],
    font=dict(family="Inter"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
pio.templates.default = "nova_light"

# ---------------- Sidebar (refined) ----------------
with st.sidebar:
    st.markdown('<div class="sidebar">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">⚙️ Controls</div>', unsafe_allow_html=True)

    stock_choices  = ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:NVDA", "NASDAQ:GOOGL", "NASDAQ:AMZN", "NASDAQ:TSLA"]
    crypto_choices = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT", "BINANCE:BNBUSDT"]
    stock_symbol  = st.selectbox("Stock (TradingView)", stock_choices, index=0)
    crypto_symbol = st.selectbox("Crypto (TradingView)", crypto_choices, index=0)

    tile_stocks = st.multiselect(
        "Stock tiles",
        [s.split(":")[1] for s in stock_choices],
        default=["AAPL", "MSFT", "NVDA"]
    )
    tile_crypto = st.multiselect(
        "Crypto tiles",
        [c.split(":")[1].lower() for c in crypto_choices],
        default=["btcusdt", "ethusdt"]
    )

    PRESET_LOCATIONS = [
        "Toronto,CA","Lagos,NG","London,GB","New York,US","Abuja,NG",
        "Accra,GH","Nairobi,KE","Delhi,IN","Sydney,AU","Johannesburg,ZA"
    ]
    defaults = [c.strip() for c in DEFAULT_CITIES.split(";") if c.strip()]
    safe_defaults = [d for d in defaults if d in PRESET_LOCATIONS][:3] or None

    unit = st.radio("Weather units", ["metric (°C)", "imperial (°F)"], horizontal=True, key="wx_units")
    selected_locations = st.multiselect("Weather locations", PRESET_LOCATIONS, default=safe_defaults)
    custom_loc = st.text_input("Add custom location (City,CountryCode)")
    if custom_loc.strip() and custom_loc not in selected_locations:
        selected_locations.append(custom_loc.strip())

    refresh = st.slider("Stocks refresh (sec)", 10, 120, 30, 5)
    alert_cfg = st.text_area("Price alerts JSON", '{"AAPL": 240.0, "BTCUSDT": 70000}')
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Hero ----------------
st.markdown(
    """
<div class="hero">
  <div style="display:flex; align-items:center; gap:12px;">
    <div class="badge"><span>MWF</span> Markets • Weather • Football</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------- Helpers ----------------
def tv_embed(symbol: str, height=520, interval="60", theme="light", chart_type="1"):
    html = f"""
    <div class="card" style="padding:0;">
      <iframe
        src="https://s.tradingview.com/widgetembed/?symbol={symbol}&interval={interval}&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme={theme}&style={chart_type}&locale=en"
        width="100%" height="{height}" frameborder="0" allowtransparency="true" scrolling="no"></iframe>
    </div>
    """
    components.html(html, height=height+2)

def sparkline(series):
    if len(series) < 2:
        return None
    fig = px.line(pd.DataFrame({"v": series}))
    fig.update_traces(line=dict(width=2), hovertemplate=None)
    fig.update_layout(
        height=56, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        hovermode=False,
    )
    return fig

def plot_chart(fig, key: str):
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)

# Weather helpers
@st.cache_data(ttl=300)
def get_weather(city, unit="metric"):
    if not OWM_KEY:
        return {"error": "Set OWM_API_KEY in .env"}
    u = "metric" if "metric" in unit else "imperial"
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": OWM_KEY, "units": u},
            timeout=8,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=24*3600)
def owm_geocode(city_country: str):
    if not OWM_KEY:
        return None, None, city_country
    try:
        raw = city_country.strip()
        parts = [p.strip() for p in raw.split(",")]
        city = parts[0] if parts else raw
        cc = parts[1] if len(parts) > 1 else ""
        cc_map = {"UK": "GB", "GBR": "GB", "USA": "US"}
        cc = cc_map.get(cc.upper(), cc) if cc else cc

        url = "https://api.openweathermap.org/geo/1.0/direct"
        q = f"{city},{cc}" if cc else city
        data = requests.get(url, params={"q": q, "limit": 1, "appid": OWM_KEY}, timeout=8).json()
        if not data and cc:
            data = requests.get(url, params={"q": city, "limit": 1, "appid": OWM_KEY}, timeout=8).json()
        if data:
            name = f'{data[0].get("name", city)}{", " + data[0].get("country","") if data[0].get("country") else ""}'
            return data[0]["lat"], data[0]["lon"], name
    except Exception:
        pass
    return None, None, city_country

@st.cache_data(ttl=12*3600)
def wx_history_daily(city_country: str, days_back: int = 7, units: str = "metric"):
    lat, lon, resolved = owm_geocode(city_country)
    if lat is None or lon is None:
        return {"error": "geocode_failed", "name": resolved}
    try:
        p = Point(lat, lon)
        end_d: _date = _date.today()
        start_d: _date = end_d - _timedelta(days=days_back)
        start_dt = _dt.combine(start_d, _dt.min.time())
        end_dt   = _dt.combine(end_d,   _dt.min.time())
        df = Daily(p, start_dt, end_dt).fetch()
        if df is None or df.empty:
            return {"name": resolved, "rows": []}
        if "imperial" in units:
            df["tmin"] = df["tmin"] * 9/5 + 32
            df["tmax"] = df["tmax"] * 9/5 + 32
        rows = []
        for d, r in df.iterrows():
            rows.append({
                "date": pd.Timestamp(d).date().isoformat(),
                "low": float(r.tmin) if pd.notna(r.tmin) else None,
                "high": float(r.tmax) if pd.notna(r.tmax) else None,
                "prcp": float(r.prcp) if "prcp" in df.columns and pd.notna(r.prcp) else 0.0
            })
        return {"name": resolved, "rows": rows}
    except Exception as e:
        return {"error": str(e), "name": resolved}

@st.cache_data(ttl=30*60)
def wx_forecast_daily(city_country: str, units: str = "metric"):
    lat, lon, resolved = owm_geocode(city_country)
    if lat is None or lon is None:
        return {"error": "geocode_failed", "name": resolved}
    try:
        u = "metric" if "metric" in units else "imperial"
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"lat": lat, "lon": lon, "appid": OWM_KEY, "units": u},
            timeout=10
        )
        lst = r.json().get("list", [])
        day = {}
        for item in lst:
            d = pd.to_datetime(item["dt"], unit="s").date()
            t = float(item["main"]["temp"])
            rmm = 0.0
            if "rain" in item and isinstance(item["rain"], dict):
                rmm = float(item["rain"].get("3h", 0.0))
            if d not in day:
                day[d] = {"low": t, "high": t, "prcp": rmm}
            else:
                day[d]["low"] = min(day[d]["low"], t)
                day[d]["high"] = max(day[d]["high"], t)
                day[d]["prcp"] += rmm
        rows = [{"date": d.isoformat(), "low": v["low"], "high": v["high"], "prcp": v["prcp"]}
                for d, v in sorted(day.items())][:5]
        return {"name": resolved, "rows": rows}
    except Exception as e:
        return {"error": str(e), "name": resolved}

def plot_band_hi_lo(title: str, rows: list):
    if not rows: return None
    df = pd.DataFrame(rows)
    df["avg"] = (df["low"] + df["high"]) / 2.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["low"], mode="lines", name="Low"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["high"], mode="lines", name="High", fill="tonexty"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["avg"], mode="lines", name="Avg",
                             line=dict(width=1, dash="dot")))
    fig.update_layout(title=title, margin=dict(l=10, r=10, t=36, b=0), height=260, legend_title="")
    return fig

def plot_precip_bars(title: str, rows: list):
    if not rows: return None
    df = pd.DataFrame(rows)
    if "prcp" not in df.columns: return None
    fig = px.bar(df, x="date", y="prcp", title=title)
    fig.update_layout(margin=dict(l=10, r=10, t=36, b=0), height=220, yaxis_title="mm", xaxis_title="")
    return fig

# ----- Stocks (yfinance) -----
@st.cache_data(ttl=60)
def fetch_stock(ticker):
    if ticker.upper().endswith("USDT"):
        return None
    for period, interval in [("1d", "1m"), ("5d", "5m"), ("1mo", "1d")]:
        try:
            df = yf.download(tickers=ticker, period=period, interval=interval,
                             progress=False, auto_adjust=False)
            if df is None or df.empty or "Close" not in df.columns:
                continue
            df = df.reset_index()
            last = float(df["Close"].iloc[-1]); prev = float(df["Close"].iloc[0])
            return {
                "last": last,
                "pct": (last - prev) / prev * 100 if prev else 0.0,
                "high": float(df["High"].max()),
                "low": float(df["Low"].min()),
                "spark": df["Close"].tail(60).tolist()
            }
        except Exception:
            continue
    return None

# ----- Crypto WS -----
crypto_q = queue.Queue()
def on_msg(ws, msg):
    import json as _json
    d = _json.loads(msg)
    p = float(d.get("p") or d.get("c") or d.get("price"))
    s = d.get("s") or d.get("stream","").split("@")[0].upper()
    crypto_q.put((s, p, time.time()))

def start_crypto_ws(symbols):
    if not symbols: return
    streams = "/".join([f"{s}@trade" for s in symbols])
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    ws = WebSocketApp(url, on_message=on_msg)
    ws.run_forever()

def binance_rest_price(symbol_upper: str):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol_upper}"
        r = requests.get(url, timeout=6); r.raise_for_status()
        return float(r.json()["price"])
    except Exception:
        return None

if "ws_started" not in st.session_state:
    syms = [s.strip().lower() for s in tile_crypto if s.strip()]
    threading.Thread(target=start_crypto_ws, args=(syms,), daemon=True).start()
    st.session_state.ws_started = True

if "crypto_prices" not in st.session_state:
    st.session_state.crypto_prices = {}
while not crypto_q.empty():
    s, p, t = crypto_q.get()
    key = s.lower()
    hist = st.session_state.crypto_prices.get(key, {"last": p, "hist": []})
    hist["last"] = p
    hist["hist"] = (hist["hist"] + [p])[-120:]
    st.session_state.crypto_prices[key] = hist

# ----- Football (football-data.org) -----
FD_BASE = "https://api.football-data.org/v4"
FD_LEAGUES = {
    "Premier League (ENG)": "PL",
    "La Liga (ESP)": "PD",
    "Serie A (ITA)": "SA",
    "Bundesliga (GER)": "BL1",
    "Ligue 1 (FRA)": "FL1",
}

def fd_get(path, params=None, timeout=10):
    headers = {"X-Auth-Token": FD_TOKEN} if FD_TOKEN else {}
    try:
        r = requests.get(f"{FD_BASE}/{path}", headers=headers, params=params or {}, timeout=timeout)
    except Exception as e:
        return {"error": f"network: {e}"}
    try:
        return r.json()
    except Exception:
        return {"error": "bad_json", "status": r.status_code, "preview": (r.text or "")[:200]}

@st.cache_data(ttl=600)
def fd_standings(code: str): return fd_get(f"competitions/{code}/standings")

@st.cache_data(ttl=120)
def fd_matches_today(code: str):
    today = pd.Timestamp.utcnow().date().isoformat()
    return fd_get(f"competitions/{code}/matches", params={"dateFrom": today, "dateTo": today})

@st.cache_data(ttl=600)
def fd_scorers(code: str): return fd_get(f"competitions/{code}/scorers")

# ---------------- Tabs (with pill look) ----------------
st.markdown('<div class="top-tabs">', unsafe_allow_html=True)
tab_markets, tab_weather, tab_football = st.tabs(["📈 Markets", "⛅ Weather", "⚽ Football"])
st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Markets ----------------
with tab_markets:
    st.markdown(
        f"""
        <div style="display:flex;gap:8px;align-items:center;margin:10px 0 6px 2px;">
          <span class="badge"><span>📈</span> Markets</span>
          <span class="caption-muted">Auto-refresh: {refresh}s</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Stock Chart (TradingView)")
    tv_embed(stock_symbol, height=520, interval="60", theme="light", chart_type="1")

    st.subheader("Crypto Chart (TradingView)")
    tv_embed(crypto_symbol, height=520, interval="15", theme="light", chart_type="1")

    st.markdown("### KPI Tiles")
    left, right = st.columns([1.6, 1])

    with left:
        st.write("**Stocks**")
        if not tile_stocks:
            st.info("Pick tickers in the sidebar.")
        else:
            cols = st.columns(min(4, len(tile_stocks)))
            for i, tkr in enumerate(tile_stocks):
                data = fetch_stock(tkr)
                with cols[i % len(cols)]:
                    if not data:
                        st.markdown(f'<div class="kpi"><div class="label">{tkr}</div><div class="caption-muted">no data</div></div>', unsafe_allow_html=True)
                        continue
                    delta = f"{data['pct']:+.2f}%"
                    cls = "kpi down" if data['pct'] < 0 else "kpi"
                    st.markdown(
                        f"""
                        <div class="{cls}">
                          <div class="label">{tkr}</div>
                          <div class="row">
                            <div class="value">{data['last']:.2f}</div>
                            <div class="delta">{delta}</div>
                          </div>
                          <div class="caption-muted">H:{data['high']:.2f} • L:{data['low']:.2f}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    fig = sparkline(data["spark"])
                    if fig: plot_chart(fig, key=f"spark-stock-{tkr}")

    with right:
        st.write("**Crypto (realtime)**")
        if not tile_crypto:
            st.info("Add crypto pairs in the sidebar.")
        else:
            # bootstrap if WS blocked
            if not st.session_state.crypto_prices:
                for s in tile_crypto:
                    p = binance_rest_price(s.upper())
                    if p is not None:
                        st.session_state.crypto_prices[s] = {"last": p, "hist": [p]}
            for sym in tile_crypto:
                pack = st.session_state.crypto_prices.get(sym.lower())
                st.markdown('<div class="kpi">', unsafe_allow_html=True)
                if not pack:
                    st.markdown(f"<div class='label'>{sym.upper()}</div><div class='caption-muted'>no data</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='label'>{sym.upper()}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='row'><div class='value'>{pack['last']:.2f}</div></div>", unsafe_allow_html=True)
                    fig = sparkline(pack.get("hist", [])[-60:])
                    if fig: plot_chart(fig, key=f"spark-crypto-{sym.lower()}")
                st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Weather ----------------
with tab_weather:
    st.markdown(
        '<div class="badge"><span>⛅</span> Weather</div>',
        unsafe_allow_html=True,
    )
    st.write("**Now • Past 7 days • Next 5 days**")
    if not selected_locations:
        st.info("Select locations in the sidebar.")
    else:
        cols = st.columns(1 if len(selected_locations) == 1 else 2)
        for i, loc in enumerate(selected_locations):
            with cols[i % len(cols)]:
                st.markdown('<div class="card">', unsafe_allow_html=True)

                current = get_weather(loc, st.session_state.get("wx_units", "metric"))
                if isinstance(current, dict) and current.get("cod") == 200:
                    w0 = current["weather"][0]
                    icon = w0.get("icon")
                    main = w0.get("main"); desc = w0.get("description")
                    temp = current["main"]["temp"]; feels = current["main"]["feels_like"]
                    st.markdown(
                        f"""
                        <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
                          {'<img src="https://openweathermap.org/img/wn/'+icon+'@2x.png" width="48">' if icon else ''}
                          <div>
                            <div style="font-weight:700">{loc} — Now</div>
                            <div class="caption-muted">{main.title()} • {desc}</div>
                          </div>
                          <div style="margin-left:auto;font-weight:800;font-size:20px;">{temp:.1f}°</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif isinstance(current, dict) and "error" in current:
                    st.error(f"{loc}: {current['error']}")
                else:
                    st.warning(f"{loc}: current conditions unavailable")

                hist = wx_history_daily(loc, days_back=7, units=st.session_state.get("wx_units","metric"))
                if isinstance(hist, dict) and "error" in hist:
                    st.warning(f"Past 7 days: {hist['error']}")
                else:
                    rows_h = hist.get("rows", [])
                    fig_band = plot_band_hi_lo("Past 7 days — High/Low", rows_h)
                    if fig_band: plot_chart(fig_band, key=f"wx-band-hist-{i}-{loc}")
                    fig_pr = plot_precip_bars("Past 7 days — Precipitation (mm)", rows_h)
                    if fig_pr: plot_chart(fig_pr, key=f"wx-prcp-hist-{i}-{loc}")
                    elif not rows_h: st.info("No historical data.")

                fc = wx_forecast_daily(loc, units=st.session_state.get("wx_units","metric"))
                if isinstance(fc, dict) and "error" in fc:
                    st.warning(f"Forecast: {fc['error']}")
                else:
                    rows_f = fc.get("rows", [])
                    fig_band_f = plot_band_hi_lo("Next 5 days — High/Low", rows_f)
                    if fig_band_f: plot_chart(fig_band_f, key=f"wx-band-fc-{i}-{loc}")
                    fig_pr_f = plot_precip_bars("Next 5 days — Precipitation (mm)", rows_f)
                    if fig_pr_f: plot_chart(fig_pr_f, key=f"wx-prcp-fc-{i}-{loc}")
                    elif not rows_f: st.info("No forecast available.")
                st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Football ----------------
with tab_football:
    st.markdown('<div class="badge"><span>⚽</span> Football</div>', unsafe_allow_html=True)
    st.write("**Today • Standings • Top Scorers**")
    if not FD_TOKEN:
        st.warning("Add FOOTBALL_DATA_TOKEN to your .env to enable this tab.")
    else:
        colA, colB = st.columns([1, 1])
        with colA:
            league_name = st.selectbox("Competition", list(FD_LEAGUES.keys()), index=0)
            code = FD_LEAGUES[league_name]
        with colB:
            pass

        subtab1, subtab2, subtab3 = st.tabs(["Today", "Standings", "Top Scorers"])

        with subtab1:
            data = fd_matches_today(code)
            if "error" in data: st.warning(f"Matches error: {data['error']}")
            else:
                matches = data.get("matches") or []
                if not matches:
                    st.info("No matches today.")
                else:
                    rows = []
                    for m in matches:
                        score = m.get("score") or {}
                        full = score.get("fullTime") or {}
                        rows.append({
                            "Kickoff (UTC)": m.get("utcDate"),
                            "Home": (m.get("homeTeam") or {}).get("name"),
                            "Away": (m.get("awayTeam") or {}).get("name"),
                            "Score": f"{'' if full.get('home') is None else full.get('home')} - {'' if full.get('away') is None else full.get('away')}",
                            "Status": m.get("status"),
                            "Competition": (m.get("competition") or {}).get("name"),
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with subtab2:
            st_data = fd_standings(code)
            if "error" in st_data: st.warning(f"Standings error: {st_data['error']}")
            else:
                tabs = st_data.get("standings") or []
                if not tabs:
                    st.info("Standings not available.")
                else:
                    table = tabs[0].get("table") or []
                    rows = []
                    for t in table:
                        rows.append({
                            "Pos": t.get("position"),
                            "Team": (t.get("team") or {}).get("name"),
                            "P": t.get("playedGames"),
                            "W": t.get("won"),
                            "D": t.get("draw"),
                            "L": t.get("lost"),
                            "GF": t.get("goalsFor"),
                            "GA": t.get("goalsAgainst"),
                            "Pts": t.get("points"),
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with subtab3:
            scorers = fd_scorers(code)
            if "error" in scorers: st.warning(f"Scorers error: {scorers['error']}")
            else:
                arr = scorers.get("scorers") or []
                if not arr: st.info("Top scorers not available.")
                else:
                    rows = []
                    for s_ in arr:
                        rows.append({
                            "Player": (s_.get("player") or {}).get("name"),
                            "Team": (s_.get("team") or {}).get("name"),
                            "Goals": s_.get("goals"),
                            "Assists": s_.get("assists"),
                            "Apps": s_.get("playedMatches") or s_.get("appearances"),
                        })
                    df = pd.DataFrame(rows).sort_values(["Goals","Assists"], ascending=False, na_position="last")
                    st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------- Alerts ----------------
try:
    alerts = json.loads(alert_cfg) if alert_cfg.strip() else {}
except Exception:
    alerts = {}
    st.sidebar.error("Invalid JSON for alerts")

def hit_alert(symbol, price, target):
    key = (symbol, "alerted", target)
    if not st.session_state.get(key):
        st.toast(f"🔔 {symbol} crossed {target:.2f} (now {price:.2f})", icon="⚡")
        st.session_state[key] = True

for tkr in tile_stocks:
    if tkr in alerts:
        dat = fetch_stock(tkr)
        if dat and dat["last"] >= float(alerts[tkr]):
            hit_alert(tkr, dat["last"], float(alerts[tkr]))

for sym, pack in st.session_state.crypto_prices.items():
    key = sym.upper()
    if key in alerts and pack["last"] >= float(alerts[key]):
        hit_alert(key, pack["last"], float(alerts[key]))

# ---------------- Auto-refresh ----------------
if st.session_state.get("last_refresh") and time.time() - st.session_state["last_refresh"] > refresh:
    st.rerun()
st.session_state["last_refresh"] = time.time()
