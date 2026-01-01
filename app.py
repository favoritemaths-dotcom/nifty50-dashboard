import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import math

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(page_title="Nifty 50 Analytics Dashboard", layout="wide")
st.title("📊 Nifty 50 Analytics & Advisory Dashboard")

# -------------------------------------------------
# LOAD NIFTY 50 UNIVERSE
# -------------------------------------------------
@st.cache_data
def load_universe():
    return pd.read_csv("nifty50.csv")

stocks = load_universe()

# -------------------------------------------------
# SESSION STATE (WATCHLIST)
# -------------------------------------------------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

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
# CASH FLOW RED FLAGS (AUDITOR LOGIC)
# -------------------------------------------------
@st.cache_data(ttl=3600)
def get_cashflow_flags(symbol):
    try:
        t = yf.Ticker(symbol)
        cashflow = t.cashflow
        income = t.financials

        if cashflow is None or income is None:
            return ["Cash-flow data unavailable"]

        cfo = cashflow.loc["Total Cash From Operating Activities"].iloc[0]
        net_profit = income.loc["Net Income"].iloc[0]

        flags = []

        if cfo < net_profit:
            flags.append("Operating cash flow is lower than net profit")

        if net_profit != 0:
            cash_conversion = cfo / net_profit
            if cash_conversion < 0.8:
                flags.append("Weak cash conversion (CFO / Net Profit < 0.8)")

        if net_profit > 0 and cfo < 0:
            flags.append("Negative operating cash flow despite positive profit")

        if not flags:
            flags.append("Cash flows broadly support reported profits")

        return flags
    except Exception:
        return ["Cash-flow data unavailable"]

# -------------------------------------------------
# BUILD MASTER TABLE
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

# Add to watchlist
if st.button("⭐ Add to Watchlist"):
    if stock not in st.session_state.watchlist:
        st.session_state.watchlist.append(stock)

# -------------------------------------------------
# PRICE CHART
# -------------------------------------------------
st.subheader("📈 5-Year Price Trend")

hist = yf.download(symbol, period="5y", progress=False)
if not hist.empty:
    fig, ax = plt.subplots()
    ax.plot(hist.index, hist["Close"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.set_title("5-Year Price Trend")
    st.pyplot(fig)

# -------------------------------------------------
# PEER COMPARISON
# -------------------------------------------------
st.subheader("🧑‍🤝‍🧑 Peer Comparison")
peers = df[df["Sector"] == row["Sector"]]
st.dataframe(peers.set_index("Company"), use_container_width=True)

# -------------------------------------------------
# CASH FLOW RED FLAGS DISPLAY
# -------------------------------------------------
st.subheader("💧 Cash Flow Quality Check")

cf_flags = get_cashflow_flags(symbol)
for f in cf_flags:
    if "support" in f.lower():
        st.success(f)
    else:
        st.warning(f)

# -------------------------------------------------
# PORTFOLIO ADVISORY
# -------------------------------------------------
st.subheader("🤖 Personalized Portfolio Advisory")

capital = st.number_input("Capital (₹)", min_value=10000, step=5000)
risk = st.selectbox("Risk Profile", ["Low", "Moderate", "High"])

def build_portfolio(data, risk):
    d = data.dropna(subset=["Price (₹)", "ROE", "Volatility %", "P/E"])
    if risk == "Low":
        d = d[d["Volatility %"] < d["Volatility %"].median()]
    elif risk == "Moderate":
        d = d.sort_values("ROE", ascending=False)
    else:
        d = d.sort_values("3Y CAGR %", ascending=False)
    return d.head(5)

if st.button("Generate Portfolio"):
    pf = build_portfolio(df, risk)
    allocation = capital / len(pf)

    pf = pf.copy()
    pf["Shares to Buy"] = pf["Price (₹)"].apply(
        lambda x: math.floor(allocation / x)
    )
    pf["Actual Invested (₹)"] = pf["Shares to Buy"] * pf["Price (₹)"]

    total_invested = pf["Actual Invested (₹)"].sum()
    cash_left = capital - total_invested

    st.dataframe(
        pf[
            ["Company", "Sector", "Price (₹)", "Shares to Buy", "Actual Invested (₹)"]
        ],
        use_container_width=True
    )

    st.markdown(
        f"""
        **Total Capital:** ₹{capital:,.0f}  
        **Invested:** ₹{total_invested:,.0f}  
        **Cash Left:** ₹{cash_left:,.0f}
        """
    )

    # Allocation Pie
    fig2, ax2 = plt.subplots()
    ax2.pie(pf["Actual Invested (₹)"], labels=pf["Company"], autopct="%1.1f%%")
    ax2.set_title("Portfolio Allocation")
    st.pyplot(fig2)

# -------------------------------------------------
# WATCHLIST
# -------------------------------------------------
st.subheader("⭐ Watchlist")

if st.session_state.watchlist:
    st.write(st.session_state.watchlist)
else:
    st.info("No stocks added yet.")
