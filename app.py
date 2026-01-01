import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Nifty 50 Dashboard",
    layout="wide"
)

st.title("📊 Nifty 50 Interactive Dashboard")

# -------------------- LOAD DATA --------------------
@st.cache_data
def load_universe():
    return pd.read_csv("nifty50.csv")

stocks = load_universe()

# -------------------- SIDEBAR FILTERS --------------------
st.sidebar.header("🔎 Filters")

sector_filter = st.sidebar.multiselect(
    "Select Sector",
    options=stocks["Sector"].unique()
)

search_text = st.sidebar.text_input("Search Company")

filtered = stocks.copy()

if sector_filter:
    filtered = filtered[filtered["Sector"].isin(sector_filter)]

if search_text:
    filtered = filtered[
        filtered["Company"].str.contains(search_text, case=False)
    ]

# -------------------- FETCH FUNDAMENTALS --------------------
@st.cache_data(ttl=3600)
def fetch_fundamentals(symbol):
    try:
        info = yf.Ticker(symbol).info
        return {
            "Price": info.get("currentPrice"),
            "PE": info.get("trailingPE"),
            "ROE": info.get("returnOnEquity"),
            "MarketCap": info.get("marketCap")
        }
    except Exception:
        return {
            "Price": None,
            "PE": None,
            "ROE": None,
            "MarketCap": None
        }

rows = []
for _, r in filtered.iterrows():
    fundamentals = fetch_fundamentals(r["Symbol"])
    rows.append({
        "Company": r["Company"],
        "Sector": r["Sector"],
        **fundamentals
    })

df = pd.DataFrame(rows)

# -------------------- MAIN TABLE --------------------
st.subheader("📋 Stock Screener")

st.dataframe(
    df,
    use_container_width=True
)

st.download_button(
    "⬇ Download CSV",
    df.to_csv(index=False),
    file_name="nifty_screener.csv"
)

# -------------------- STOCK DRILL DOWN --------------------
st.subheader("🔍 Stock Drill-Down")

if not df.empty:
    selected_company = st.selectbox(
        "Select a stock",
        df["Company"].unique()
    )

    selected_row = df[df["Company"] == selected_company].iloc[0]
    selected_symbol = filtered[
        filtered["Company"] == selected_company
    ]["Symbol"].values[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Price (₹)", selected_row["Price"])
    c2.metric("P/E", selected_row["PE"])
    c3.metric("ROE", selected_row["ROE"])

    # -------------------- PRICE CHART (STABLE VERSION) --------------------
    st.subheader("📈 5Y Price Chart")

    try:
        hist = yf.download(
            selected_symbol,
            period="5y",
            progress=False
        )

        if not hist.empty:
            fig, ax = plt.subplots()
            ax.plot(hist.index, hist["Close"])
            ax.set_xlabel("Date")
            ax.set_ylabel("Price")
            ax.set_title("5 Year Price Trend")
            st.pyplot(fig)
        else:
            st.warning("Price data unavailable.")

    except Exception as e:
        st.error("Error loading price chart.")

else:
    st.warning("No stocks match the selected filters.")
