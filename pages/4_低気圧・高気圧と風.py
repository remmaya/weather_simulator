# -*- coding: utf-8 -*-
"""
pages/4_低気圧・高気圧と風.py

中学2年理科「低気圧・高気圧のまわりの風シミュレーター」学習用ページ
Streamlit + Plotly

計算ロジックは science_utils.py に分離してあります。
第一段階として、以下の3つの定番パターンを扱う(自由配置は将来の拡張):
  ・低気圧のみ
  ・高気圧のみ
  ・低気圧と高気圧(両方)
"""

import math
import os

import numpy as np
import streamlit as st
import plotly.graph_objects as go

from science_utils import (
    PressureCenter,
    pressure_deviation,
    wind_vector_at,
    CORIOLIS_DEFLECTION_DEG,
)

# ------------------------------------------------------------
# 基本設定
# ------------------------------------------------------------
st.set_page_config(
    page_title="低気圧・高気圧のまわりの風",
    layout="wide",
)

LOW_COLOR = "#c0392b"    # 低気圧(赤系。天気図の慣習にあわせる)
HIGH_COLOR = "#1f4e79"   # 高気圧(青系)
ARROW_COLOR = "#333333"
ISOBAR_LOW_COLOR = "#c0392b"
ISOBAR_HIGH_COLOR = "#1f4e79"
ISOBAR_MID_COLOR = "#aaaaaa"

PRESET_OPTIONS = ["低気圧のみ", "高気圧のみ", "低気圧と高気圧"]
CENTER_RADIUS = 0.5  # 気圧配置の広がりのスケール(共通)

# ------------------------------------------------------------
# タイトルと説明
# ------------------------------------------------------------
st.title("低気圧・高気圧のまわりの風シミュレーター")
st.markdown(
    "風は気圧の高いところから低いところへ向かって吹こうとしますが、地球の自転の影響で、"
    "まっすぐには吹かず少し向きがそれます。その結果、北半球では**低気圧のまわりは反時計回りに"
    "風が吹き込み**、**高気圧のまわりは時計回りに風が吹き出し**ます。"
    "気圧配置のパターンや強さを変えて、風のようすがどう変わるか調べてみましょう。"
)
st.caption(
    "※このシミュレーターでは、気圧が下がる方向(等圧線にほぼ直角な向き)から、"
    f"時計回りに{CORIOLIS_DEFLECTION_DEG:.0f}°だけそれた向きに風が吹くものとして計算しています。"
    "風の強さは、その地点での等圧線の混み具合(気圧の傾き)に比例するものとしています"
    "(実際の大気の複雑な動きを精密に再現したものではない、中学校教材用の簡略モデルです)。"
)

# ------------------------------------------------------------
# セッション状態の初期化
# ------------------------------------------------------------
if "wind_preset" not in st.session_state:
    st.session_state.wind_preset = PRESET_OPTIONS[0]
if "wind_strength_single" not in st.session_state:
    st.session_state.wind_strength_single = 20.0
if "wind_strength_low" not in st.session_state:
    st.session_state.wind_strength_low = 20.0
if "wind_strength_high" not in st.session_state:
    st.session_state.wind_strength_high = 20.0

# ------------------------------------------------------------
# レイアウト: 左=入力 / 中央=気圧配置と風の図 / 右=読み方の説明
# ------------------------------------------------------------
col_input, col_main, col_values = st.columns([1.4, 5, 2.2])

with col_input:
    st.markdown("**気圧配置のパターン**")
    preset = st.radio(
        "パターンを選ぶ",
        PRESET_OPTIONS,
        index=PRESET_OPTIONS.index(st.session_state.wind_preset),
        key="wind_preset_radio",
        label_visibility="collapsed",
    )
    st.session_state.wind_preset = preset

    st.markdown("**気圧の強さ(周囲との気圧差)**")
    if preset == "低気圧と高気圧":
        strength_low = st.slider(
            "低気圧の強さ [hPa]", min_value=4.0, max_value=40.0,
            value=st.session_state.wind_strength_low, step=4.0,
            key="wind_low_slider",
        )
        st.session_state.wind_strength_low = strength_low

        strength_high = st.slider(
            "高気圧の強さ [hPa]", min_value=4.0, max_value=40.0,
            value=st.session_state.wind_strength_high, step=4.0,
            key="wind_high_slider",
        )
        st.session_state.wind_strength_high = strength_high
    else:
        strength_single = st.slider(
            "気圧差 [hPa]", min_value=4.0, max_value=40.0,
            value=st.session_state.wind_strength_single, step=4.0,
            key="wind_single_slider",
        )
        st.session_state.wind_strength_single = strength_single

# ------------------------------------------------------------
# 気圧中心の設定
# ------------------------------------------------------------
if preset == "低気圧のみ":
    centers = [
        PressureCenter(x=0.0, y=0.0, kind="low",
                        strength_hpa=st.session_state.wind_strength_single, radius=CENTER_RADIUS)
    ]
elif preset == "高気圧のみ":
    centers = [
        PressureCenter(x=0.0, y=0.0, kind="high",
                        strength_hpa=st.session_state.wind_strength_single, radius=CENTER_RADIUS)
    ]
else:
    centers = [
        PressureCenter(x=-0.4, y=0.0, kind="low",
                        strength_hpa=st.session_state.wind_strength_low, radius=CENTER_RADIUS),
        PressureCenter(x=0.4, y=0.0, kind="high",
                        strength_hpa=st.session_state.wind_strength_high, radius=CENTER_RADIUS),
    ]

max_strength = max(c.strength_hpa for c in centers)

with col_main:
    fig = go.Figure()

    # ------------------------------------------------------------
    # 等圧線(気圧の偏差の等高線)
    # ------------------------------------------------------------
    grid_n = 70
    xs = np.linspace(-1.0, 1.0, grid_n)
    ys = np.linspace(-1.0, 1.0, grid_n)
    z = np.array([[pressure_deviation(x, y, centers) for x in xs] for y in ys])

    fig.add_trace(
        go.Contour(
            x=xs, y=ys, z=z,
            contours=dict(
                coloring="lines",
                start=-max_strength - 2.0,
                end=max_strength + 2.0,
                size=4.0,
            ),
            line=dict(width=1.3),
            colorscale=[[0.0, ISOBAR_LOW_COLOR], [0.5, ISOBAR_MID_COLOR], [1.0, ISOBAR_HIGH_COLOR]],
            zmin=-max_strength - 2.0,
            zmax=max_strength + 2.0,
            showscale=False,
            hoverinfo="skip",
        )
    )

    # ------------------------------------------------------------
    # 風向風速の矢印グリッド
    # ------------------------------------------------------------
    grid_pts = np.linspace(-0.9, 0.9, 9)
    arrow_data = []
    for gx in grid_pts:
        for gy in grid_pts:
            # 気圧中心に近すぎる点は、無風域・特異点を避けるためスキップする
            too_close = any(math.hypot(gx - c.x, gy - c.y) < 0.16 for c in centers)
            if too_close:
                continue
            wx, wy, mag = wind_vector_at(float(gx), float(gy), centers)
            if mag < 1e-9:
                continue
            arrow_data.append((gx, gy, wx, wy, mag))

    if arrow_data:
        max_mag = max(a[4] for a in arrow_data)
        for gx, gy, wx, wy, mag in arrow_data:
            length = 0.05 + 0.13 * (mag / max_mag)
            fig.add_annotation(
                x=gx + wx * length, y=gy + wy * length,
                ax=gx, ay=gy,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowsize=1.0, arrowwidth=2.2,
                arrowcolor=ARROW_COLOR,
            )

    # ------------------------------------------------------------
    # 気圧中心のマーク
    # ------------------------------------------------------------
    for c in centers:
        label = "低" if c.kind == "low" else "高"
        color = LOW_COLOR if c.kind == "low" else HIGH_COLOR
        fig.add_trace(
            go.Scatter(
                x=[c.x], y=[c.y],
                mode="markers+text",
                marker=dict(size=30, color=color),
                text=[label],
                textfont=dict(size=20, color="white"),
                textposition="middle center",
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        xaxis=dict(range=[-1.05, 1.05], visible=False, fixedrange=True, scaleanchor="y"),
        yaxis=dict(range=[-1.05, 1.05], visible=False, fixedrange=True),
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
        height=560,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

with col_values:
    st.markdown("**図の読み方**")
    st.markdown(
        "- 色のついた線: 等圧線(気圧が同じところを結んだ線)。"
        "線が混み合っているところほど風が強い\n"
        "- 矢印: その地点での風向き(矢印が長いほど風が強い)"
    )

    st.markdown("**このパターンでわかること**")
    if preset == "低気圧のみ":
        st.info(
            "低気圧のまわりでは、風は反時計回りに渦を巻きながら中心に向かって吹き込みます。"
            "低気圧の中心付近では上昇気流が生じ、雲ができやすく天気が悪くなります。"
        )
    elif preset == "高気圧のみ":
        st.info(
            "高気圧のまわりでは、風は時計回りに渦を巻きながら中心から外側へ吹き出します。"
            "高気圧の中心付近では下降気流が生じ、雲ができにくく晴れやすくなります。"
        )
    else:
        st.info(
            "低気圧と高気圧が並ぶと、高気圧側から低気圧側に向かって全体的に風が吹きます。"
            "それぞれの中心付近では、低気圧は反時計回り、高気圧は時計回りの渦も同時に見られます。"
        )
