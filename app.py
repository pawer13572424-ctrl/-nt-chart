import io
import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="NT倍率チャート", page_icon="📈", layout="wide")

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&d1={start}&d2={end}&i=d&apikey={apikey}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; nt-chart/1.0)"}


def get_apikey() -> str:
    try:
        return st.secrets["STOOQ_APIKEY"]
    except Exception:
        return os.environ.get("STOOQ_APIKEY", "")


@st.cache_data(ttl=3600)
def fetch_data(years: int) -> pd.DataFrame:
    apikey = get_apikey()
    end = date.today()
    start = end - timedelta(days=int(years * 365.25))

    def fetch(symbol: str) -> pd.DataFrame:
        url = STOOQ_URL.format(
            symbol=symbol,
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
            apikey=apikey,
        )
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        text = r.text.strip()
        if not text or "apikey" in text.lower():
            raise RuntimeError("APIキーが無効です")
        if text.lower().startswith("no data"):
            raise RuntimeError(f"データなし: {symbol}")
        df = pd.read_csv(io.StringIO(text))
        df.columns = df.columns.str.strip()
        if "Date" not in df.columns or "Close" not in df.columns:
            raise RuntimeError(f"Stooqが想定外の応答を返しました: {text[:200]}")
        df["Date"] = pd.to_datetime(df["Date"])
        return df[["Date", "Close"]].dropna().sort_values("Date")

    nikkei = fetch("^nkx")
    topix = fetch("^tpx")
    merged = nikkei.merge(topix, on="Date", suffixes=("_n", "_t"))
    merged.columns = ["Date", "Nikkei", "TOPIX"]
    merged["NT"] = (merged["Nikkei"] / merged["TOPIX"]).round(4)
    return merged


def build_chart(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.6, 0.4],
        vertical_spacing=0.06,
        subplot_titles=("日経平均 / TOPIX", "NT倍率"),
    )

    # 日経平均（左軸）
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Nikkei"],
        name="日経平均", line=dict(color="#1f77b4", width=1.5),
    ), row=1, col=1)

    # TOPIX（右軸）
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["TOPIX"],
        name="TOPIX", line=dict(color="#ff7f0e", width=1.5),
        yaxis="y2",
    ), row=1, col=1)

    # NT倍率
    nt_mean = df["NT"].mean()
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["NT"],
        name="NT倍率", line=dict(color="#2ca02c", width=1.5),
    ), row=2, col=1)

    # NT平均線
    fig.add_hline(
        y=nt_mean, row=2, col=1,
        line=dict(color="gray", dash="dash", width=1),
        annotation_text=f"平均 {nt_mean:.2f}",
        annotation_position="right",
    )

    fig.update_layout(
        height=620,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=60, t=60, b=10),
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,
        ),
    )
    fig.update_xaxes(rangeslider_visible=False)
    return fig


# ── UI ──────────────────────────────────────────────────────────────────────

st.title("📈 NT倍率チャート")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    years = st.selectbox("期間", [1, 2, 3, 5], index=1, format_func=lambda x: f"過去 {x} 年")
with col3:
    if st.button("🔄 更新"):
        st.cache_data.clear()

try:
    with st.spinner("データ取得中..."):
        df = fetch_data(years)

    st.plotly_chart(build_chart(df), use_container_width=True)

    # 統計
    latest = df.iloc[-1]
    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("最新NT", f"{latest['NT']:.4f}", delta=f"{latest['NT'] - df['NT'].iloc[-2]:.4f}")
    c2.metric("平均NT", f"{df['NT'].mean():.4f}")
    c3.metric("最大NT", f"{df['NT'].max():.4f}")
    c4.metric("最小NT", f"{df['NT'].min():.4f}")
    c5.metric("データ件数", f"{len(df)}日")

    st.caption(f"最終更新: {latest['Date'].strftime('%Y-%m-%d')}  |  出所: Stooq")

except Exception as e:
    st.error(f"データ取得エラー: {e}")
