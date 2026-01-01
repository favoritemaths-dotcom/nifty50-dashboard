import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import math
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(page_title="Nifty 50 Analytics Dashboard", layout="wide")
st.title("📊 Nifty 50 Analytics & Advisory Dashboard")

# -------------------------------------------------
# AI CONFIG
# -------------------------------------------------
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

use_ai = st.sidebar.checkbox("🤖 Enable AI News Summary", value=False)

if use_ai and not OPENAI_KEY:
    st.sidebar.warning("AI enabled but API key not found")

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
# GOOGLE NEWS RSS
# -------------------------------------------------
@st.cache_data(ttl=900)
def fetch_google_news(company):
    query = f"{company} NSE stock"
    url = (
        "https://news.google.com/rss/search?q="
        + requests.utils.quote(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)

        items = []
        for item in root.findall(".//item")[:8]:
            title = item.findtext("title")
            link = item.findtext("link")
            pub_date = item.findtext("pubDate")

            if pub_date:
                pub_date = datetime.strptime(
                    pub_date, "%a, %d %b %Y %H:%M:%S %Z"
                ).strftime("%d %b %Y, %H:%M")

            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "date": pub_date
                })

        return items
    except Exception:
        return []

# -------------------------------------------------
# AI SUMMARIZATION
# -------------------------------------------------
def ai_summarize(title, company):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)

        prompt = f"""
Summarize the following news headline for a long-term equity investor.
Do not give buy/sell advice.

Company: {company}
Headline: {title}

Explain:
- What happened
- Why it matters (or not)
In 2–3 lines.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=120
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return "AI summary unavailable."

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
# STOCK DRILL-DOWN
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
# NEWS & AI SUMMARY
# -------------------------------------------------
st.subheader("📰 Latest News & Events")

news_items = fetch_google_news(stock)

if not news_items:
    st.info("No recent news found.")
else:
    for n in news_items:
        st.markdown(
            f"""
            **[{n['title']}]({n['link']})**  
            *{n['date']}*
            """
        )

        if use_ai and OPENAI_KEY:
            with st.spinner("AI summarizing..."):
                summary = ai_summarize(n["title"], stock)
            st.markdown(f"> 🤖 **AI Insight:** {summary}")

        st.markdown("---")
