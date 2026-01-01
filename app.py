import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import math
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import re

# =================================================
# CONFIG
# =================================================
st.set_page_config(page_title="Nifty 50 Advisory Dashboard", layout="wide")
st.title("📊 Nifty 50 – Personal Investment Advisory")

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
use_ai = st.sidebar.checkbox("🤖 Enable AI News Deep Dive", value=False)

if use_ai and not OPENAI_KEY:
    st.sidebar.warning("AI enabled but OpenAI key not found")

# =================================================
# LOAD UNIVERSE
# =================================================
@st.cache_data
def load_universe():
    return pd.read_csv("nifty50.csv")

stocks = load_universe()

# =================================================
# SIDEBAR FILTERS
# =================================================
st.sidebar.header("🔎 Filters")
sector_filter = st.sidebar.multiselect("Sector", sorted(stocks["Sector"].unique()))
search = st.sidebar.text_input("Search Company")

filtered = stocks.copy()
if sector_filter:
    filtered = filtered[filtered["Sector"].isin(sector_filter)]
if search:
    filtered = filtered[filtered["Company"].str.contains(search, case=False)]

# =================================================
# METRICS ENGINE
# =================================================
@st.cache_data(ttl=3600)
def get_metrics(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        hist = t.history(period="3y")

        price = info.get("currentPrice")
        pe = info.get("trailingPE")
        roe = info.get("returnOnEquity")

        vol = None
        if not hist.empty:
            vol = hist["Close"].pct_change().std() * (252 ** 0.5) * 100

        return price, pe, roe, vol
    except Exception:
        return None, None, None, None

# =================================================
# GOOGLE NEWS (RSS)
# =================================================
@st.cache_data(ttl=900)
def fetch_google_news(company):
    query = f"{company} NSE stock"
    url = (
        "https://news.google.com/rss/search?q="
        + requests.utils.quote(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    try:
        r = requests.get(url, timeout=10)
        root = ET.fromstring(r.content)

        items = []
        for item in root.findall(".//item")[:5]:
            title = item.findtext("title")
            link = item.findtext("link")
            if title and link:
                items.append({"title": title, "link": link})
        return items
    except Exception:
        return []

# =================================================
# ARTICLE EXTRACTION (SAFE)
# =================================================
def extract_article_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        text = re.sub("<[^<]+?>", "", r.text)
        text = re.sub(r"\s+", " ", text)
        return text[:4000]
    except Exception:
        return None

# =================================================
# AI NEWS DEEP DIVE (SAFE)
# =================================================
def ai_news_deep_dive(company, headline, article_text):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)

        context = article_text if article_text else headline

        prompt = f"""
You are an equity research analyst.

Company: {company}

News content:
{context}

Task:
- Explain what happened
- Why it matters (or not)
- Risks or positives
- NO buy/sell advice
- NO price prediction

Limit to 5 bullet points.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=250
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return "AI summary unavailable."

# =================================================
# BUILD SCREENER
# =================================================
rows = []
for _, r in filtered.iterrows():
    price, pe, roe, vol = get_metrics(r["Symbol"])
    rows.append({
        "Company": r["Company"],
        "Sector": r["Sector"],
        "Price": price,
        "P/E": pe,
        "ROE": roe,
        "Volatility %": vol
    })

df = pd.DataFrame(rows)

st.subheader("📋 Nifty 50 Screener")
st.dataframe(df, use_container_width=True)

# =================================================
# STOCK DEEP DIVE
# =================================================
st.subheader("🔍 Stock Deep Dive")

stock = st.selectbox("Select Stock", df["Company"])
symbol = filtered[filtered["Company"] == stock]["Symbol"].values[0]
price, pe, roe, vol = get_metrics(symbol)

c1, c2, c3 = st.columns(3)
c1.metric("Price", price)
c2.metric("P/E", pe)
c3.metric("ROE", roe)

# =================================================
# PRICE CHART
# =================================================
hist = yf.download(symbol, period="5y", progress=False)
if not hist.empty:
    fig, ax = plt.subplots()
    ax.plot(hist.index, hist["Close"])
    ax.set_title("5Y Price Trend")
    st.pyplot(fig)

# =================================================
# NEWS DEEP DIVE
# =================================================
st.subheader("📰 News Deep Dive")

news_items = fetch_google_news(stock)

if not news_items:
    st.info("No recent news found.")
else:
    for n in news_items:
        st.markdown(f"**{n['title']}**")
        st.markdown(f"[Read source]({n['link']})")

        if use_ai and OPENAI_KEY:
            with st.spinner("AI analyzing article..."):
                article_text = extract_article_text(n["link"])
                summary = ai_news_deep_dive(stock, n["title"], article_text)
            st.info(summary)

        st.markdown("---")

# =================================================
# PORTFOLIO ADVISORY (RESTORED)
# =================================================
st.subheader("💼 Portfolio Advisory")

capital = st.number_input("Investment Capital (₹)", min_value=50000, step=10000)
risk = st.selectbox("Risk Profile", ["Low", "Moderate", "High"])

if st.button("Generate Portfolio"):
    eligible = df.dropna()

    if eligible.empty:
        st.warning("Insufficient data to generate portfolio.")
        st.stop()

    if risk == "Low":
        eligible = eligible.sort_values("Volatility %")
    elif risk == "High":
        eligible = eligible.sort_values("ROE", ascending=False)

    pf = eligible.head(5)

    allocation = capital / len(pf)

    pf = pf.copy()
    pf["Shares"] = pf["Price"].apply(lambda x: math.floor(allocation / x))
    pf["Investment (₹)"] = pf["Shares"] * pf["Price"]

    total_invested = pf["Investment (₹)"].sum()
    cash_left = capital - total_invested

    st.dataframe(
        pf[["Company", "Price", "Shares", "Investment (₹)"]],
        use_container_width=True
    )

    st.markdown(
        f"""
        **Total Capital:** ₹{capital:,.0f}  
        **Invested:** ₹{total_invested:,.0f}  
        **Cash Left:** ₹{cash_left:,.0f}
        """
    )
