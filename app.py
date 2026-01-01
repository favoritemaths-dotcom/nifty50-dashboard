import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Nifty 50 Dashboard",
    layout="wide"
)

st.title("📊 Nifty 50 Interactive Dashboard")

# ---------------- LOAD UNIVERSE ----------------
@st.cache_data
def load_universe():
    return pd.read_csv("nifty50.csv")

stocks = load_universe()

# ---------------- SIDEBAR FILTERS ----------------
st.sidebar.header("🔎 Filters")

sector_filter = st.sidebar.multiselect(
    "Select Sector",
    options=sorted(stocks["Sector"].unique())
)

search_text = st.sidebar.text_input("Search Company")

filtered = stocks.copy()

if sector_filter:
    filtered = filtered[filtered["Sector"].isin(sector_filter)]

if search_text:
    filtered = filtered[
        filtered["Company"].str.contains(search_text, case=False)
    ]

# ---------------- METRICS ENGINE ----------------
@st.cache_data(ttl=3600)
def get_metrics(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="3y")

        price = info.get("currentPrice")
        pe = info.get("trailingPE")
        roe = info.get("returnOnEquity")

        one_year_return = None
        three_year_cagr = None
        volatility = None

        if hist is not None and not hist.empty:
            if len(hist) > 252:
                one_year_return = (
                    (hist["Close"].iloc[-1] / hist["Close"].iloc[-252]) - 1
                ) * 100

            if len(hist) > 756:
                three_year_cagr = (
                    (hist["Close"].iloc[-1] / hist["Close"].iloc[0]) ** (1 / 3) - 1
                ) * 100

            volatility = (
                hist["Close"]
                .pct_change()
                .std() * (252 ** 0.5) * 100
            )

        return price, pe, roe, one_year_return, three_year_cagr, volatility

    except Exception:
        return None, None, None, None, None, None

# ---------------- BUILD SCREENER TABLE ----------------
rows = []

for _, r in filtered.iterrows():
    price, pe, roe, ret1y, cagr3y, vol = get_metrics(r["Symbol"])
    rows.append({
        "Company": r["Company"],
        "Sector": r["Sector"],
        "Price (₹)": price,
        "P/E": pe,
        "ROE": roe,
        "1Y Return %": ret1y,
        "3Y CAGR %": cagr3y,
        "Volatility %": vol
    })

df = pd.DataFrame(rows)

# ---------------- MAIN TABLE ----------------
st.subheader("📋 Nifty 50 Stock Screener")

st.dataframe(
    df,
    use_container_width=True
)

st.download_button(
    "⬇ Download CSV",
    df.to_csv(index=False),
    file_name="nifty50_screener.csv"
)

# ---------------- STOCK DRILL-DOWN ----------------
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
    c1.metric("Price (₹)", selected_row["Price (₹)"])
    c2.metric("P/E", selected_row["P/E"])
    c3.metric("ROE", selected_row["ROE"])

    # ---------------- PRICE CHART ----------------
    st.subheader("📈 5-Year Price Chart")

    try:
        hist = yf.download(
            selected_symbol,
            period="5y",
            progress=False
        )

        if hist is not None and not hist.empty:
            fig, ax = plt.subplots()
            ax.plot(hist.index, hist["Close"])
            ax.set_xlabel("Date")
            ax.set_ylabel("Price")
            ax.set_title("5-Year Price Trend")
            st.pyplot(fig)
        else:
            st.warning("Price data unavailable.")

    except Exception:
        st.error("Unable to load price chart.")

else:
    st.warning("No stocks match the selected filters.")
