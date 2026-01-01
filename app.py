import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf

st.set_page_config(layout="wide", page_title="Nifty 50 Dashboard")

st.title("📊 Nifty 50 Interactive Analytics Dashboard")

@st.cache_data
def load_data():
    return pd.read_csv("nifty50.csv")

stocks = load_data()

st.sidebar.header("Filters")
sector = st.sidebar.multiselect("Sector", stocks["Sector"].unique())
search = st.sidebar.text_input("Search Company")

df = stocks.copy()
if sector:
    df = df[df["Sector"].isin(sector)]
if search:
    df = df[df["Company"].str.contains(search, case=False)]

data = []
for _, row in df.iterrows():
    stock = yf.Ticker(row["Symbol"])
    info = stock.info
    data.append({
        "Company": row["Company"],
        "Sector": row["Sector"],
        "Price": info.get("currentPrice"),
        "P/E": info.get("trailingPE"),
        "ROE": info.get("returnOnEquity")
    })

final_df = pd.DataFrame(data)
st.subheader("📋 Nifty 50 Screener")
st.dataframe(final_df, use_container_width=True)

stock_name = st.selectbox("Select Stock", final_df["Company"])

selected = final_df[final_df["Company"] == stock_name].iloc[0]
st.metric("Price", selected["Price"])

hist = yf.download(df[df["Company"] == stock_name]["Symbol"].values[0], period="5y")
fig = px.line(hist, y="Close", title="5Y Price Chart")
st.plotly_chart(fig, use_container_width=True)
