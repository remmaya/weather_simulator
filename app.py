# -*- coding: utf-8 -*-
"""
app.py

中学2年理科「飽和水蒸気量・湿度・露点」学習用Webアプリ
Streamlit + Plotly

計算ロジックは science_utils.py に分離してあります。
飽和水蒸気量のデータは data/saturation_vapor.csv から読み込みます(仮データ)。
"""

import os
import streamlit as st
import plotly.graph_objects as go

from science_utils import (
    load_saturation_table,
    get_temperature_range,
    compute_state,
)

# ------------------------------------------------------------
# 基本設定
# ------------------------------------------------------------
st.set_page_config(
    page_title="飽和水蒸気量と湿度・露点",
    layout="wide",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "data", "saturation_vapor.csv")

VAPOR_COLOR = "#1f77b4"        # 水蒸気(青)
CONDENSED_COLOR = "#e45756"    # 結露した水(赤系)
CURVE_COLOR = "#2c3e50"        # 飽和水蒸気量の曲線
FRAME_COLOR = "#888888"        # 外枠(容器)
POINT_COLOR = "#f2a900"        # 現在の状態を示す点

BAR_WIDTH = 1.4  # 気温の棒の幅[℃]


@st.cache_data
def load_data(path: str):
    return load_saturation_table(path)


df = load_data(CSV_PATH)
t_min, t_max = get_temperature_range(df)
sat_max = float(df["saturation_g_m3"].max())

# ------------------------------------------------------------
# タイトルと説明
# ------------------------------------------------------------
st.title("飽和水蒸気量と湿度・露点")
st.markdown(
    "気温を変えると、空気が含むことができる水蒸気の量(飽和水蒸気量)が変わります。"
    "スライダーを動かして、湿度や露点がどう変化するか調べてみましょう。"
)

# ------------------------------------------------------------
# 入力(スライダー)
# ------------------------------------------------------------
col_input1, col_input2 = st.columns(2)

with col_input1:
    temperature_c = st.slider(
        "気温 [℃]",
        min_value=float(t_min),
        max_value=float(t_max),
        value=20.0,
        step=0.5,
    )

with col_input2:
    initial_water = st.slider(
        "空気1m³に最初に含まれていた水の量 [g/m³]",
        min_value=0.0,
        max_value=float(round(sat_max)),
        value=15.0,
        step=0.5,
    )

# ------------------------------------------------------------
# 計算
# ------------------------------------------------------------
state = compute_state(temperature_c, initial_water, df)

# ------------------------------------------------------------
# グラフ
# ------------------------------------------------------------
fig = go.Figure()

# 1. 飽和水蒸気量の曲線
fig.add_trace(
    go.Scatter(
        x=df["temperature_c"],
        y=df["saturation_g_m3"],
        mode="lines",
        name="飽和水蒸気量の曲線",
        line=dict(color=CURVE_COLOR, width=3),
        hovertemplate="気温 %{x}℃ ・ 飽和水蒸気量 %{y:.1f} g/m³<extra></extra>",
    )
)

# 2. 現在も水蒸気として存在する部分(棒・下側)
fig.add_trace(
    go.Bar(
        x=[temperature_c],
        y=[state.vapor_g_m3],
        width=BAR_WIDTH,
        name="水蒸気として存在する部分",
        marker_color=VAPOR_COLOR,
        hovertemplate="水蒸気 %{y:.1f} g/m³<extra></extra>",
    )
)

# 3. 結露した部分(棒・水蒸気の上に積み上げ)※水蒸気ではないことを凡例名で明示
if state.condensed_g_m3 > 0:
    fig.add_trace(
        go.Bar(
            x=[temperature_c],
            y=[state.condensed_g_m3],
            base=[state.vapor_g_m3],
            width=BAR_WIDTH,
            name="結露した水(水蒸気ではない)",
            marker_color=CONDENSED_COLOR,
            hovertemplate="結露した水 %{y:.1f} g/m³<extra></extra>",
        )
    )

# 4. 外枠(その気温での飽和水蒸気量を表す枠)
fig.add_shape(
    type="rect",
    x0=temperature_c - BAR_WIDTH / 2,
    x1=temperature_c + BAR_WIDTH / 2,
    y0=0,
    y1=state.saturation_g_m3,
    line=dict(color=FRAME_COLOR, width=2, dash="dash"),
    fillcolor="rgba(0,0,0,0)",
)
# 凡例用のダミートレース(shapeは凡例に出ないため)
fig.add_trace(
    go.Scatter(
        x=[None], y=[None],
        mode="lines",
        line=dict(color=FRAME_COLOR, width=2, dash="dash"),
        name="飽和水蒸気量の枠(その気温で入る限界)",
    )
)

# 5. 現在の状態を示す点
fig.add_trace(
    go.Scatter(
        x=[temperature_c],
        y=[state.vapor_g_m3],
        mode="markers",
        name="現在の状態",
        marker=dict(color=POINT_COLOR, size=14, symbol="diamond",
                     line=dict(color="black", width=1)),
        hovertemplate="現在の状態<extra></extra>",
    )
)

fig.update_layout(
    barmode="stack",
    xaxis_title="気温 [℃]",
    yaxis_title="水の量 [g/m³]",
    xaxis=dict(range=[t_min, t_max]),
    yaxis=dict(range=[0, sat_max * 1.1]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=10, r=10, t=40, b=10),
    height=480,
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "点線の枠は、その気温で入りきる水蒸気の限界(飽和水蒸気量)を表します。"
    "青色は水蒸気として存在している部分、赤色は空気中にいられなくなって結露した水(水蒸気ではない)を表します。"
)

# ------------------------------------------------------------
# 数値表示
# ------------------------------------------------------------
st.subheader("現在の値")

c1, c2, c3 = st.columns(3)
c1.metric("気温", f"{state.temperature_c:.1f} ℃")
c2.metric("飽和水蒸気量", f"{state.saturation_g_m3:.1f} g/m³")
c3.metric("水蒸気として存在する量", f"{state.vapor_g_m3:.1f} g/m³")

c4, c5, c6 = st.columns(3)
c4.metric("結露した水の量", f"{state.condensed_g_m3:.1f} g/m³")
c5.metric("湿度", f"{state.humidity_percent:.0f} %")
c6.metric("露点", f"{state.dew_point_c:.1f} ℃")

if state.condensed_g_m3 > 0:
    st.info(
        "設定した水の量が、この気温の飽和水蒸気量を超えています。"
        "超えた分は水蒸気でいられなくなり、結露しています(赤色の部分)。"
    )
