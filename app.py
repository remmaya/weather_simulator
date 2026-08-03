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
from streamlit_vertical_slider import vertical_slider

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

# グラフの左右の余白(px)。気温スライダーの左右位置をこれに合わせて近似させる。
PLOT_MARGIN_L = 55
PLOT_MARGIN_R = 20


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
# セッション状態の初期化(気温・水の量)
# ------------------------------------------------------------
if "temperature_c" not in st.session_state:
    st.session_state.temperature_c = 20.0
if "initial_water" not in st.session_state:
    st.session_state.initial_water = 15.0

# ------------------------------------------------------------
# レイアウト: 左=水の量スライダー(縦) / 中央=グラフ+気温スライダー / 右=数値パネル
# ------------------------------------------------------------
col_water, col_main, col_values = st.columns([1, 5, 2.2])

with col_water:
    st.markdown("**水の量**")
    initial_water = vertical_slider(
        label="空気1m³に最初に\n含まれていた水の量 [g/m³]",
        key="water_vslider",
        height=340,
        min_value=0.0,
        max_value=float(round(sat_max)),
        step=0.5,
        default_value=st.session_state.initial_water,
        slider_color="#1f77b4",
        track_color="#dddddd",
        thumb_color="#1f4e79",
        value_always_visible=True,
    )
    if initial_water is None:
        initial_water = st.session_state.initial_water
    st.session_state.initial_water = initial_water

with col_main:
    # 表示位置を先に確保しておく(中身は後で埋める)
    graph_slot = st.empty()

    # ------------------------------------------------------------
    # 気温スライダー(グラフのすぐ下に配置。左右の余白をグラフの余白に近づけて位置を合わせる)
    # 表示上はグラフの下だが、値を先に取得してから上の表示・グラフを描画することで、
    # 「スライダーを動かしても1回遅れてグラフが反映される」不具合を防ぐ。
    # ------------------------------------------------------------
    slider_l, slider_mid, slider_r = st.columns([PLOT_MARGIN_L, 1000, PLOT_MARGIN_R])
    with slider_mid:
        # 気温の大きな数値表示(スライダーの現在値表示として、スライダーの真上・同じ幅に配置)
        # ※Streamlit内部のスライダー要素をCSSで直接拡大しようとしたが、
        #   内部のdata-testid名がバージョンによって異なり反映されなかったため、
        #   自前のテキスト表示に一本化している。
        temp_display_slot = st.empty()
        temperature_c = st.slider(
            "気温 [℃](上のグラフの横軸と、だいたい対応しています)",
            min_value=float(t_min),
            max_value=float(t_max),
            value=st.session_state.temperature_c,
            step=0.5,
            key="temp_slider",
        )
    st.session_state.temperature_c = temperature_c

    st.caption(
        "点線の枠は、その気温で入りきる水蒸気の限界(飽和水蒸気量)を表します。"
        "青色は水蒸気として存在している部分、赤色は空気中にいられなくなって結露した水(水蒸気ではない)を表します。"
    )

    # ------------------------------------------------------------
    # 計算(スライダーの最新値を使う)
    # ------------------------------------------------------------
    state = compute_state(temperature_c, initial_water, df)

    temp_display_slot.markdown(
        f"<div style='font-size:1.8rem; font-weight:700; text-align:center;'>"
        f"気温:{temperature_c:.1f} ℃</div>",
        unsafe_allow_html=True,
    )

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

    # 6. 湿度ラベル:棒の高さ(水蒸気量の位置)から、引き出し線でグラフの横に表示。
    #    気温が右寄りのときは左側に、それ以外は右側に出して画面端でのはみ出しを防ぐ。
    label_on_left = temperature_c > t_min + (t_max - t_min) * 0.7
    ax_offset = -90 if label_on_left else 90
    fig.add_annotation(
        x=temperature_c,
        y=state.vapor_g_m3,
        ax=ax_offset,
        ay=0,
        xref="x", yref="y",
        axref="pixel", ayref="pixel",
        text=f"湿度 {state.humidity_percent:.0f}%",
        showarrow=True,
        arrowhead=0,
        arrowcolor=FRAME_COLOR,
        arrowwidth=1,
        font=dict(size=16, color="#1f4e79"),
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=FRAME_COLOR,
        borderwidth=1,
    )

    # 7. 結露ラベル:結露しているときだけ、棒の一番上(水蒸気+結露の合計の高さ)の上に表示
    if state.condensed_g_m3 > 0:
        bar_top = state.vapor_g_m3 + state.condensed_g_m3
        fig.add_annotation(
            x=temperature_c,
            y=bar_top + sat_max * 0.05,
            text=f"結露 {state.condensed_g_m3:.1f} g/m³",
            showarrow=False,
            font=dict(size=14, color=CONDENSED_COLOR),
            bgcolor="rgba(255,255,255,0.9)",
        )

    # 8. 棒の根元(x軸の目盛りの下)に、現在の気温を示すラベルを追加
    fig.add_annotation(
        x=temperature_c,
        y=-0.22,
        xref="x",
        yref="paper",
        text=f"{temperature_c:.1f}℃",
        showarrow=False,
        font=dict(size=14, color=POINT_COLOR),
    )

    fig.update_layout(
        barmode="stack",
        xaxis_title="気温 [℃]",
        yaxis_title="水の量 [g/m³]",
        xaxis=dict(range=[t_min, t_max]),
        yaxis=dict(range=[0, sat_max * 1.2]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=PLOT_MARGIN_L, r=PLOT_MARGIN_R, t=40, b=70),
        height=430,
    )

    graph_slot.plotly_chart(fig, use_container_width=True)

with col_values:
    st.markdown("**現在の値**")
    st.metric("飽和水蒸気量", f"{state.saturation_g_m3:.1f} g/m³")
    st.metric("水蒸気として存在する量", f"{state.vapor_g_m3:.1f} g/m³")
    st.metric("結露した水の量", f"{state.condensed_g_m3:.1f} g/m³")
    st.metric("湿度", f"{state.humidity_percent:.0f} %")

    if state.dew_point_out_of_range == "low":
        st.metric("露点", f"{t_min:.0f} ℃未満")
    elif state.dew_point_out_of_range == "high":
        st.metric("露点", f"{t_max:.0f} ℃超")
    else:
        st.metric("露点", f"{state.dew_point_c:.1f} ℃")

    if state.condensed_g_m3 > 0:
        st.info(
            "設定した水の量が、この気温の飽和水蒸気量を超えています。"
            "超えた分は水蒸気でいられなくなり、結露しています(赤色の部分)。"
        )
