import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import math
from datetime import datetime

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(page_title="Nifty 50 Analytics Dashboard", layout="wide")
st.title("📊 Nifty 50 Analytics & Advisory Dashboard")

# -------------------------------------------------
# LOAD UNIVERSE
# -------------------------------------------------
@st.cache_data
def load_universe():
    return pd.read_csv("nifty50.csv")

stocks = load_universe()

# -------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------
st.sidebar.header("🔎 Filters")

sector_filter = st.sidebar.multiselect(
    "Sector",
    sorted(stocks["Sector"].unique())
)

search_text = st.sidebar.text_input("Search Company")

filtered = stocks.copy()
if sector_filter:
    filtered = filtered[filtered["Sector"].isin(sector_filter)]
if search_text:
    filtered = filtered[
        filtered["Company"].str.contains(search_text, case=False)
    ]

# -------------------------------------------------
# METRICS ENGINE
# -------------------------------------------------
@st.cache_data(ttl=3600)
def get_metrics(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        hist = t.history(period="3y")

        price = info.get("currentPrice")
        pe = info.get("trailingPE")
        roe = info.get("returnOnEquity")

        r1y, cagr3, vol = None, None, None

        if not hist.empty:
            if len(hist) > 252:
                r1y = (hist["Close"].iloc[-1] / hist["Close"].iloc[-252] - 1) * 100
            if len(hist) > 756:
                cagr3 = ((hist["Close"].iloc[-1] / hist["Close"].iloc[0]) ** (1/3) - 1) * 100
            vol = hist["Close"].pct_change().std() * (252 ** 0.5) * 100

        return price, pe, roe, r1y, cagr3, vol
    except Exception:
        return None, None, None, None, None, None

# -------------------------------------------------
# ROBUST CASH FLOW CHECK (FIXED)
# -------------------------------------------------
@st.cache_data(ttl=3600)
def get_cashflow_flags(symbol):
    try:
        t = yf.Ticker(symbol)
        cf = t.cashflow
        inc = t.financials

        if cf is None or inc is None or cf.empty or inc.empty:
            return ["Cash-flow data not published by source"]

        # Possible row names (Yahoo is inconsistent)
        cfo_rows = [
            "Total Cash From Operating Activities",
            "Operating Cash Flow",
            "Net Cash Provided by Operating Activities"
        ]

        cfo = None
        for r in cfo_rows:
            if r in cf.index:
                cfo = cf.loc[r].iloc[0]
                break

        if cfo is None:
            return ["Operating cash-flow not reported"]

        if "Net Income" not in inc.index:
            return ["Net income data unavailable"]

        net_profit = inc.loc["Net Income"].iloc[0]

        flags = []

        if cfo < net_profit:
            flags.append("Operating cash flow is lower than net profit")

        if net_profit != 0:
            ratio = cfo / net_profit
            if ratio < 0.8:
                flags.append("Weak cash conversion (CFO / Net Profit < 0.8)")

        if net_profit > 0 and cfo < 0:
            flags.append("Negative operating cash flow despite positive profit")

        if not flags:
            flags.append("Cash flows broadly support reported profits")

        return flags

    except Exception:
        return ["Cash-flow data not available"]

# -------------------------------------------------
# NEWS ENGINE (IMPROVED)
# -------------------------------------------------
@st.cache_data(ttl=900)
def get_stock_news(symbol):
    try:
        n = yf.Ticker(symbol).news
        return [x for x in n if x.get("title")]
    except Exception:
        return []

def classify_sentiment(title):
    title = title.lower()

    positive = ["profit", "growth", "order", "approval", "record", "expansion"]
    negative = ["loss", "penalty", "fraud", "probe", "downgrade", "decline"]

    if any(w in title for w in positive):
        return "🟢 Positive"
    if any(w in title for w in negative):
        return "🔴 Caution"
    return "🟡 Neutral"

# -------------------------------------------------
# BUILD SCREENER
# -------------------------------------------------
rows = []
for _, r in filtered.iterrows():
    price, pe, roe, r1y, c3y, vol = get_metrics(r["Symbol"])
    rows.append({
        "Company": r["Company"],
        "Sector": r["Sector"],
        "Price (₹)": price,
        "P/E": pe,
        "ROE": roe,
        "1Y Return %": r1y,
        "3Y CAGR %": c3y,
        "Volatility %": vol
    })

df = pd.DataFrame(rows)

# -------------------------------------------------
# SCREENER
# -------------------------------------------------
st.subheader("📋 Nifty 50 Screener")
st.dataframe(df, use_container_width=True)

# -------------------------------------------------
# STOCK VIEW
# -------------------------------------------------
st.subheader("🔍 Stock Drill-Down")

stock = st.selectbox("Select Stock", df["Company"])
row = df[df["Company"] == stock].iloc[0]
symbol = filtered[filtered["Company"] == stock]["Symbol"].values[0]

c1, c2, c3 = st.columns(3)
c1.metric("Price (₹)", row["Price (₹)"])
c2.metric("P/E", row["P/E"])
c3.metric("ROE", row["ROE"])

# -------------------------------------------------
# PRICE CHART
# -------------------------------------------------
st.subheader("📈 5-Year Price Trend")
hist = yf.download(symbol, period="5y", progress=False)
if not hist.empty:
    fig, ax = plt.subplots()
    ax.plot(hist.index, hist["Close"])
    st.pyplot(fig)

# -------------------------------------------------
# CASH FLOW DISPLAY
# -------------------------------------------------
st.subheader("💧 Cash Flow Quality Check")
for f in get_cashflow_flags(symbol):
    if "support" in f.lower():
        st.success(f)
    else:
        st.warning(f)

# -------------------------------------------------
# NEWS DISPLAY
# -------------------------------------------------
st.subheader("📰 Latest News & Events")

news = get_stock_news(symbol)

if not news:
    st.info("No recent news available from public sources.")
else:
    for n in news[:8]:
        title = n["title"]
        link = n.get("link", "")
        ts = n.get("providerPublishTime")
        time_str = datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M") if ts else ""

        st.markdown(
            f"""
            **[{title}]({link})**  
            *{time_str}*  
            Sentiment: {classify_sentiment(title)}
            ---
            """
    )
