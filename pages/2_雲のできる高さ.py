# -*- coding: utf-8 -*-
"""
pages/2_雲のできる高さ.py

中学2年理科「雲のできる高さシミュレーター」学習用ページ
Streamlit + Plotly

計算ロジックは science_utils.py に分離してあります(既存の飽和水蒸気量・
湿度・露点アプリと同じモジュールを再利用しており、計算処理の重複はありません)。
"""

import os
import streamlit as st
import plotly.graph_objects as go

from science_utils import (
    load_saturation_table,
    get_temperature_range,
    compute_cloud_state,
    DRY_LAPSE_RATE_C_PER_100M,
    DEW_POINT_LAPSE_RATE_C_PER_100M,
)

# ------------------------------------------------------------
# 基本設定
# ------------------------------------------------------------
st.set_page_config(
    page_title="雲のできる高さシミュレーター",
    layout="wide",
)

# このファイルは pages/ の中にあるので、プロジェクト直下(data/がある場所)は1つ上の階層
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "saturation_vapor.csv")

MOUNTAIN_HEIGHT_M = 3000.0      # 山の高さ
MAX_DISPLAY_HEIGHT_M = 5000.0   # グラフの縦軸の表示上限(山より高い空も見せるため)

SKY_BG_COLOR = "#dceefb"
MOUNTAIN_COLOR = "#7c9473"
MOUNTAIN_LINE_COLOR = "#4f5d43"
CLOUD_COLOR = "#f5f7fa"
BASE_LINE_COLOR = "#3f6fae"
PEAK_MARK_COLOR = "#5c4433"


@st.cache_data
def load_data(path: str):
    return load_saturation_table(path)


df = load_data(CSV_PATH)
t_min, t_max = get_temperature_range(df)

# このページで実際に使う気温スライダーの範囲(教材の仕様として -10〜40℃)。
# CSVデータ自体は -20〜40℃ まであるが、露点計算のためだけに使う。
GROUND_TEMP_MIN = max(-10.0, t_min)
GROUND_TEMP_MAX = min(40.0, t_max)

# ------------------------------------------------------------
# タイトルと説明
# ------------------------------------------------------------
st.title("雲のできる高さシミュレーター")
st.markdown(
    "地上の気温と湿度を変えると、山を登るにつれて気温が下がり、"
    "どの高さで雲ができ始めるかが変わります。スライダーを動かして調べてみましょう。"
)
st.caption(
    f"※このシミュレーターでは、上昇する空気の気温は100mにつき{DRY_LAPSE_RATE_C_PER_100M:.1f}℃、"
    f"露点は100mにつき{DEW_POINT_LAPSE_RATE_C_PER_100M:.1f}℃下がるものとして計算しています"
    "(実際の大気を精密に再現したものではない、中学校教材用の簡略モデルです)。"
)

# ------------------------------------------------------------
# セッション状態の初期化
# ------------------------------------------------------------
if "ground_temperature_c" not in st.session_state:
    st.session_state.ground_temperature_c = 20.0
if "ground_humidity_percent" not in st.session_state:
    st.session_state.ground_humidity_percent = 60.0

# ------------------------------------------------------------
# レイアウト: 左=入力 / 中央=山と雲の図 / 右=数値パネル
# ------------------------------------------------------------
col_input, col_main, col_values = st.columns([1.4, 5, 2.2])

with col_input:
    st.markdown("**地上の条件**")
    ground_temperature_c = st.slider(
        "地上の気温 [℃]",
        min_value=GROUND_TEMP_MIN,
        max_value=GROUND_TEMP_MAX,
        value=st.session_state.ground_temperature_c,
        step=0.5,
        key="ground_temp_slider",
    )
    st.session_state.ground_temperature_c = ground_temperature_c

    ground_humidity_percent = st.slider(
        "地上の相対湿度 [%]",
        min_value=1.0,
        max_value=100.0,
        value=st.session_state.ground_humidity_percent,
        step=1.0,
        key="ground_humidity_slider",
    )
    st.session_state.ground_humidity_percent = ground_humidity_percent

# ------------------------------------------------------------
# 計算
# ------------------------------------------------------------
state = compute_cloud_state(ground_temperature_c, ground_humidity_percent, df)

is_saturated_at_ground = state.cloud_base_height_m <= 0.05
in_mountain = state.cloud_base_reliable and 0.05 < state.cloud_base_height_m <= MOUNTAIN_HEIGHT_M
above_mountain_visible = (
    state.cloud_base_reliable
    and MOUNTAIN_HEIGHT_M < state.cloud_base_height_m <= MAX_DISPLAY_HEIGHT_M
)
above_display_range = state.cloud_base_reliable and state.cloud_base_height_m > MAX_DISPLAY_HEIGHT_M
out_of_model_range = not state.cloud_base_reliable

with col_main:
    fig = go.Figure()

    # 空(背景)
    fig.add_shape(
        type="rect", x0=-1, x1=1, y0=0, y1=MAX_DISPLAY_HEIGHT_M,
        fillcolor=SKY_BG_COLOR, line=dict(width=0), layer="below",
    )

    # 山(左右対称の三角形)
    fig.add_trace(
        go.Scatter(
            x=[-0.8, 0.0, 0.8, -0.8],
            y=[0, MOUNTAIN_HEIGHT_M, 0, 0],
            fill="toself",
            mode="lines",
            line=dict(color=MOUNTAIN_LINE_COLOR, width=2),
            fillcolor=MOUNTAIN_COLOR,
            name="山",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # 山頂マーク
    fig.add_trace(
        go.Scatter(
            x=[0.0], y=[MOUNTAIN_HEIGHT_M],
            mode="markers+text",
            marker=dict(color=PEAK_MARK_COLOR, size=10, symbol="triangle-up"),
            text=["山頂"],
            textposition="top center",
            textfont=dict(size=13, color=PEAK_MARK_COLOR),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # 雲(表示できる場合のみ描画)
    show_cloud = in_mountain or above_mountain_visible
    if show_cloud:
        base_y = state.cloud_base_height_m
        band_top = min(base_y + 1200.0, MAX_DISPLAY_HEIGHT_M)

        # 雲がその高さより上に広がっている様子を、帯として表現
        fig.add_trace(
            go.Scatter(
                x=[-0.9, 0.9, 0.9, -0.9],
                y=[base_y, base_y, band_top, band_top],
                fill="toself",
                mode="lines",
                line=dict(width=0),
                fillcolor=CLOUD_COLOR,
                name="雲が広がる範囲",
                hoverinfo="skip",
                showlegend=False,
            )
        )

        # 雲底を示す水平の点線
        fig.add_shape(
            type="line", x0=-0.95, x1=0.95, y0=base_y, y1=base_y,
            line=dict(color=BASE_LINE_COLOR, width=2, dash="dash"),
        )

        # 雲の輪郭:長方形の上下の縁に、枠線なしの円を並べて「もこもこ」させる
        puff_count = 9
        puff_x = [-0.92 + 1.84 * i / (puff_count - 1) for i in range(puff_count)]
        bottom_puff_sizes = [55, 68, 58, 74, 62, 76, 60, 70, 54]
        top_puff_sizes = [48, 64, 76, 58, 80, 56, 74, 62, 50]

        fig.add_trace(
            go.Scatter(
                x=puff_x + puff_x,
                y=[base_y] * puff_count + [band_top] * puff_count,
                mode="markers",
                marker=dict(
                    size=bottom_puff_sizes + top_puff_sizes,
                    color=CLOUD_COLOR,
                    line=dict(width=0),
                ),
                name="雲",
                hoverinfo="skip",
                showlegend=False,
            )
        )

        # 雲底高度のラベル
        fig.add_annotation(
            x=0.97, y=base_y,
            xref="x", yref="y",
            xanchor="left",
            text=f"雲底 約{base_y:.0f}m",
            showarrow=False,
            font=dict(size=16, color=BASE_LINE_COLOR),
            bgcolor="rgba(255,255,255,0.9)",
        )

    fig.update_layout(
        xaxis=dict(range=[-1.15, 1.35], visible=False, fixedrange=True),
        yaxis=dict(
            range=[0, MAX_DISPLAY_HEIGHT_M],
            title="高度 [m]",
            tick0=0,
            dtick=1000,
            fixedrange=True,
        ),
        plot_bgcolor=SKY_BG_COLOR,
        margin=dict(l=60, r=20, t=20, b=20),
        height=560,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------
    # 状態に応じた説明文
    # ------------------------------------------------------------
    if is_saturated_at_ground:
        st.info("地上ですでに湿度100%です。雲底高度は0mです。")
    elif in_mountain:
        st.success(f"約{state.cloud_base_height_m:.0f}mで気温が露点に達します。")
    elif above_mountain_visible:
        st.warning(
            f"この{MOUNTAIN_HEIGHT_M:.0f}mの山を上昇しても雲はできません"
            f"(雲ができるのは山の上空、約{state.cloud_base_height_m:.0f}m付近です)。"
        )
    elif above_display_range:
        st.warning(
            f"この{MOUNTAIN_HEIGHT_M:.0f}mの山を上昇しても雲はできません"
            f"(計算上、雲ができるのは約{state.cloud_base_height_m:.0f}mで、"
            f"このグラフの表示範囲({MAX_DISPLAY_HEIGHT_M:.0f}m)よりも高い場所です)。"
        )
    else:
        st.warning(
            f"この{MOUNTAIN_HEIGHT_M:.0f}mの山を上昇しても雲はできません"
            "(地上の空気が非常に乾燥しているため、この教材の計算モデルで"
            "正確な高さを求められる範囲を超えています)。"
        )

with col_values:
    st.markdown("**現在の値**")
    st.metric("地上の気温", f"{state.ground_temperature_c:.1f} ℃")
    st.metric("地上の湿度", f"{state.ground_relative_humidity_percent:.0f} %")
    st.metric("地上の飽和水蒸気量", f"{state.ground_saturation_g_m3:.1f} g/m³")
    st.metric("実際の水蒸気量", f"{state.ground_vapor_g_m3:.2f} g/m³")

    if state.dew_point_out_of_range == "low":
        st.metric("露点", f"{t_min:.0f} ℃未満")
    elif state.dew_point_out_of_range == "high":
        st.metric("露点", f"{t_max:.0f} ℃超")
    else:
        st.metric("露点", f"{state.ground_dew_point_c:.1f} ℃")

    if state.cloud_base_reliable:
        st.metric("気温と露点の差", f"{state.temp_dew_diff_c:.1f} ℃")
        st.metric("雲のでき始める高さ", f"約{state.cloud_base_height_m:.0f} m")
        st.metric("その高さでの気温", f"{state.temperature_at_cloud_base_c:.1f} ℃")
    else:
        st.metric("気温と露点の差", "計算範囲外")
        st.metric("雲のでき始める高さ", "計算範囲外")
