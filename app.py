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


def add_technicals(df: pd.DataFrame, ma_period: int, bb_period: int, bb_sigma: float, rsi_period: int) -> pd.DataFrame:
    df = df.copy()

    # 移動平均
    df["MA"] = df["NT"].rolling(ma_period).mean()

    # ボリンジャーバンド
    df["BB_mid"] = df["NT"].rolling(bb_period).mean()
    std = df["NT"].rolling(bb_period).std()
    df["BB_upper"] = df["BB_mid"] + bb_sigma * std
    df["BB_lower"] = df["BB_mid"] - bb_sigma * std

    # Zスコア（BBと同期間）
    df["Zscore"] = (df["NT"] - df["BB_mid"]) / std

    # RSI
    delta = df["NT"].diff()
    gain = delta.clip(lower=0).rolling(rsi_period).mean()
    loss = (-delta.clip(upper=0)).rolling(rsi_period).mean()
    df["RSI"] = 100 - (100 / (1 + gain / loss))

    return df


def build_chart(df: pd.DataFrame, show_ma: bool, show_bb: bool, show_zscore: bool, show_rsi: bool) -> go.Figure:
    # 表示するパネルを動的に決定
    panels = [("nikkei", "日経平均 / TOPIX", 0.32), ("nt", "NT倍率", 0.32)]
    if show_zscore:
        panels.append(("zscore", "Zスコア", 0.18))
    if show_rsi:
        panels.append(("rsi", "RSI", 0.18))

    total_h = sum(h for _, _, h in panels)
    heights = [h / total_h for _, _, h in panels]
    titles = [t for _, t, _ in panels]
    n_rows = len(panels)

    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        row_heights=heights,
        vertical_spacing=0.04,
        subplot_titles=titles,
    )

    row_map = {name: i + 1 for i, (name, _, _) in enumerate(panels)}

    # ── 日経平均 / TOPIX ──
    r = row_map["nikkei"]
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Nikkei"],
        name="日経平均", line=dict(color="#1f77b4", width=1.5),
    ), row=r, col=1)
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["TOPIX"],
        name="TOPIX", line=dict(color="#ff7f0e", width=1.5),
        yaxis=f"y{r * 2}",
    ), row=r, col=1)

    # ── NT倍率 ──
    r = row_map["nt"]
    nt_mean = df["NT"].mean()
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["NT"],
        name="NT倍率", line=dict(color="#2ca02c", width=1.8),
    ), row=r, col=1)

    if show_ma:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["MA"],
            name="移動平均", line=dict(color="#d62728", width=1.2, dash="dot"),
        ), row=r, col=1)

    if show_bb:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["BB_upper"],
            name="BB +2σ", line=dict(color="rgba(148,103,189,0.8)", width=1, dash="dash"),
        ), row=r, col=1)
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["BB_mid"],
            name="BB 中心", line=dict(color="rgba(148,103,189,0.5)", width=1),
        ), row=r, col=1)
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["BB_lower"],
            name="BB -2σ", line=dict(color="rgba(148,103,189,0.8)", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(148,103,189,0.07)",
        ), row=r, col=1)

    fig.add_hline(
        y=nt_mean, row=r, col=1,
        line=dict(color="gray", dash="dash", width=1),
        annotation_text=f"平均 {nt_mean:.2f}",
        annotation_position="right",
    )

    # ── Zスコア ──
    if show_zscore:
        r = row_map["zscore"]
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["Zscore"],
            name="Zスコア", line=dict(color="#8c564b", width=1.4),
            fill="tozeroy", fillcolor="rgba(140,86,75,0.08)",
        ), row=r, col=1)
        for level, color in [(2, "rgba(214,39,40,0.5)"), (-2, "rgba(31,119,180,0.5)"),
                             (1, "rgba(214,39,40,0.25)"), (-1, "rgba(31,119,180,0.25)")]:
            fig.add_hline(y=level, row=r, col=1,
                          line=dict(color=color, dash="dash", width=1),
                          annotation_text=str(level), annotation_position="right")

    # ── RSI ──
    if show_rsi:
        r = row_map["rsi"]
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["RSI"],
            name="RSI", line=dict(color="#e377c2", width=1.4),
        ), row=r, col=1)
        fig.add_hline(y=70, row=r, col=1,
                      line=dict(color="rgba(214,39,40,0.5)", dash="dash", width=1),
                      annotation_text="70", annotation_position="right")
        fig.add_hline(y=30, row=r, col=1,
                      line=dict(color="rgba(31,119,180,0.5)", dash="dash", width=1),
                      annotation_text="30", annotation_position="right")
        fig.add_hrect(y0=30, y1=70, row=r, col=1,
                      fillcolor="rgba(200,200,200,0.08)", line_width=0)

    fig.update_layout(
        height=200 + 200 * n_rows,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=60, t=60, b=10),
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
    )
    fig.update_xaxes(rangeslider_visible=False)
    return fig


# ── UI ──────────────────────────────────────────────────────────────────────

st.title("📈 NT倍率チャート")

with st.expander("⚙️ 表示設定", expanded=True):
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
    with c1:
        years = st.selectbox("期間", [1, 2, 3, 5], index=1, format_func=lambda x: f"過去 {x} 年")
    with c2:
        show_ma = st.checkbox("移動平均", value=True)
        ma_period = st.number_input("MA 期間", min_value=5, max_value=120, value=25, step=5,
                                    label_visibility="collapsed") if show_ma else 25
        show_bb = st.checkbox("ボリンジャーバンド", value=True)
        bb_period = st.number_input("BB 期間", min_value=5, max_value=120, value=20, step=5,
                                    label_visibility="collapsed") if show_bb else 20
    with c3:
        show_zscore = st.checkbox("Zスコア", value=True)
        show_rsi = st.checkbox("RSI", value=True)
        rsi_period = st.number_input("RSI 期間", min_value=5, max_value=30, value=14, step=1,
                                     label_visibility="collapsed") if show_rsi else 14
    with c5:
        st.write("")
        st.write("")
        if st.button("🔄 更新"):
            st.cache_data.clear()

try:
    with st.spinner("データ読み込み中..."):
        df = load_data(years)

    df = add_technicals(df, ma_period=ma_period, bb_period=bb_period, bb_sigma=2.0, rsi_period=rsi_period)
    st.plotly_chart(build_chart(df, show_ma=show_ma, show_bb=show_bb,
                                show_zscore=show_zscore, show_rsi=show_rsi),
                    use_container_width=True)

    latest = df.iloc[-1]
    st.divider()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("最新NT", f"{latest['NT']:.4f}", delta=f"{latest['NT'] - df['NT'].iloc[-2]:.4f}")
    c2.metric("平均NT", f"{df['NT'].mean():.4f}")
    c3.metric("最大NT", f"{df['NT'].max():.4f}")
    c4.metric("最小NT", f"{df['NT'].min():.4f}")
    c5.metric("Zスコア", f"{latest['Zscore']:.2f}" if pd.notna(latest["Zscore"]) else "-")
    c6.metric("RSI", f"{latest['RSI']:.1f}" if pd.notna(latest["RSI"]) else "-")

    st.caption(f"最終更新: {latest['Date'].strftime('%Y-%m-%d')}  |  出所: Stooq")

except Exception as e:
    st.error(f"データ取得エラー: {e}")
