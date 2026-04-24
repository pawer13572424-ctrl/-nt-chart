import os
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="NT倍率チャート", page_icon="📈", layout="wide")

CSV_PATH = os.path.join(os.path.dirname(__file__), "nt_ratio.csv")


@st.cache_data(ttl=3600)
def load_data(years: int) -> pd.DataFrame:
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError("nt_ratio.csv が見つかりません。ローカルでfetch_nt_data.pyを実行してください。")
    df = pd.read_csv(CSV_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    cutoff = df["Date"].max() - timedelta(days=int(years * 365.25))
    return df[df["Date"] >= cutoff].reset_index(drop=True)


def add_technicals(df: pd.DataFrame, ma_period: int, bb_period: int, bb_sigma: float) -> pd.DataFrame:
    df = df.copy()
    df["MA"] = df["NT"].rolling(ma_period).mean()
    df["BB_mid"] = df["NT"].rolling(bb_period).mean()
    std = df["NT"].rolling(bb_period).std()
    df["BB_upper"] = df["BB_mid"] + bb_sigma * std
    df["BB_lower"] = df["BB_mid"] - bb_sigma * std
    return df


def build_chart(df: pd.DataFrame, show_ma: bool, show_bb: bool) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.45],
        vertical_spacing=0.06,
        subplot_titles=("日経平均 / TOPIX", "NT倍率 + テクニカル"),
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
        name="NT倍率", line=dict(color="#2ca02c", width=1.8),
    ), row=2, col=1)

    # 移動平均
    if show_ma and "MA" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["MA"],
            name=f"移動平均", line=dict(color="#d62728", width=1.2, dash="dot"),
        ), row=2, col=1)

    # ボリンジャーバンド
    if show_bb and "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["BB_upper"],
            name="BB +2σ", line=dict(color="rgba(148,103,189,0.8)", width=1, dash="dash"),
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["BB_mid"],
            name="BB 中心", line=dict(color="rgba(148,103,189,0.5)", width=1),
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["BB_lower"],
            name="BB -2σ", line=dict(color="rgba(148,103,189,0.8)", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(148,103,189,0.07)",
        ), row=2, col=1)

    # 全期間平均線
    fig.add_hline(
        y=nt_mean, row=2, col=1,
        line=dict(color="gray", dash="dash", width=1),
        annotation_text=f"平均 {nt_mean:.2f}",
        annotation_position="right",
    )

    fig.update_layout(
        height=680,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=60, t=60, b=10),
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
    )
    fig.update_xaxes(rangeslider_visible=False)
    return fig


# ── UI ──────────────────────────────────────────────────────────────────────

st.title("📈 NT倍率チャート")

col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
with col1:
    years = st.selectbox("期間", [1, 2, 3, 5], index=1, format_func=lambda x: f"過去 {x} 年")
with col2:
    show_ma = st.checkbox("移動平均", value=True)
    ma_period = st.number_input("MA 期間", min_value=5, max_value=120, value=25, step=5, label_visibility="collapsed") if show_ma else 25
with col3:
    show_bb = st.checkbox("ボリンジャーバンド", value=True)
    bb_period = st.number_input("BB 期間", min_value=5, max_value=120, value=20, step=5, label_visibility="collapsed") if show_bb else 20
with col4:
    if st.button("🔄 更新"):
        st.cache_data.clear()

try:
    with st.spinner("データ読み込み中..."):
        df = load_data(years)

    df = add_technicals(df, ma_period=ma_period, bb_period=bb_period, bb_sigma=2.0)
    st.plotly_chart(build_chart(df, show_ma=show_ma, show_bb=show_bb), use_container_width=True)

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
