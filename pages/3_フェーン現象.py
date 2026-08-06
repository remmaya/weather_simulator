# -*- coding: utf-8 -*-
"""
pages/3_フェーン現象.py

中学2年理科「フェーン現象シミュレーター」学習用ページ
Streamlit + Plotly

計算ロジックは science_utils.py に分離してあります(雲のできる高さシミュレーターの
雲底計算をそのまま再利用しており、計算処理の重複はありません)。
"""

import math
import os
import streamlit as st
import plotly.graph_objects as go

from science_utils import (
    load_saturation_table,
    get_temperature_range,
    compute_foehn_state,
    DRY_LAPSE_RATE_C_PER_100M,
    DEW_POINT_LAPSE_RATE_C_PER_100M,
    MOIST_LAPSE_RATE_C_PER_100M,
)

# ------------------------------------------------------------
# 基本設定
# ------------------------------------------------------------
st.set_page_config(
    page_title="フェーン現象シミュレーター",
    layout="wide",
)

# このファイルは pages/ の中にあるので、プロジェクト直下(data/がある場所)は1つ上の階層
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "saturation_vapor.csv")

MOUNTAIN_HEIGHT_MIN_M = 500.0
MOUNTAIN_HEIGHT_MAX_M = 3000.0
MOUNTAIN_HEIGHT_DEFAULT_M = 2000.0

SKY_BG_COLOR = "#dceefb"
MOUNTAIN_COLOR = "#7c9473"
MOUNTAIN_LINE_COLOR = "#4f5d43"
GROUND_LINE_COLOR = "#4f5d43"
CLOUD_COLOR = "#f5f7fa"
BASE_LINE_COLOR = "#3f6fae"
PEAK_MARK_COLOR = "#5c4433"
WINDWARD_COLOR = "#1f4e79"   # 風上側(左)のラベル色
LEEWARD_COLOR = "#b23b1f"    # 風下側(右)のラベル色(昇温を意識した暖色)


@st.cache_data
def load_data(path: str):
    return load_saturation_table(path)


df = load_data(CSV_PATH)
t_min, t_max = get_temperature_range(df)

# このページで使う気温スライダーの範囲(教材の仕様として -10〜40℃)。
GROUND_TEMP_MIN = max(-10.0, t_min)
GROUND_TEMP_MAX = min(40.0, t_max)

# ------------------------------------------------------------
# タイトルと説明
# ------------------------------------------------------------
st.title("フェーン現象シミュレーター")
st.markdown(
    "風上側(左)のふもとの気温と湿度、そして山の高さを変えると、"
    "山を越えたあとの風下側(右)のふもとの気温がどう変わるかがわかります。"
    "山の途中で雲ができると、風下側のほうが気温が高くなります。これがフェーン現象です。"
)
st.caption(
    "※このシミュレーターでは、雲ができるまでの上昇は気温が100mにつき"
    f"{DRY_LAPSE_RATE_C_PER_100M:.1f}℃、露点が100mにつき{DEW_POINT_LAPSE_RATE_C_PER_100M:.1f}℃"
    f"下がるものとし、雲ができたあとの上昇は気温が100mにつき{MOIST_LAPSE_RATE_C_PER_100M:.1f}℃"
    "下がるものとして計算しています。山を越えたあとは雲(水滴)が雨として落ちてしまうため、"
    f"山頂から風下側への下降は気温が100mにつき{DRY_LAPSE_RATE_C_PER_100M:.1f}℃上がるものとして"
    "計算しています(実際の大気を精密に再現したものではない、中学校教材用の簡略モデルです)。"
)

# ------------------------------------------------------------
# セッション状態の初期化
# ------------------------------------------------------------
if "foehn_ground_temperature_c" not in st.session_state:
    st.session_state.foehn_ground_temperature_c = 20.0
if "foehn_ground_humidity_percent" not in st.session_state:
    st.session_state.foehn_ground_humidity_percent = 70.0
if "foehn_mountain_height_m" not in st.session_state:
    st.session_state.foehn_mountain_height_m = MOUNTAIN_HEIGHT_DEFAULT_M

# ------------------------------------------------------------
# レイアウト: 左=入力 / 中央=山と雲の図 / 右=数値パネル
# ------------------------------------------------------------
col_input, col_main, col_values = st.columns([1.4, 5, 2.4])

with col_input:
    st.markdown("**山の高さ**")
    mountain_height_m = st.slider(
        "山の高さ [m]",
        min_value=MOUNTAIN_HEIGHT_MIN_M,
        max_value=MOUNTAIN_HEIGHT_MAX_M,
        value=st.session_state.foehn_mountain_height_m,
        step=100.0,
        key="foehn_mountain_height_slider",
    )
    st.session_state.foehn_mountain_height_m = mountain_height_m

    st.markdown("**風上側(左)のふもとの条件**")
    ground_temperature_c = st.slider(
        "気温 [℃]",
        min_value=GROUND_TEMP_MIN,
        max_value=GROUND_TEMP_MAX,
        value=st.session_state.foehn_ground_temperature_c,
        step=0.5,
        key="foehn_ground_temp_slider",
    )
    st.session_state.foehn_ground_temperature_c = ground_temperature_c

    ground_humidity_percent = st.slider(
        "相対湿度 [%]",
        min_value=1.0,
        max_value=100.0,
        value=st.session_state.foehn_ground_humidity_percent,
        step=1.0,
        key="foehn_ground_humidity_slider",
    )
    st.session_state.foehn_ground_humidity_percent = ground_humidity_percent

# ------------------------------------------------------------
# 計算
# ------------------------------------------------------------
state = compute_foehn_state(ground_temperature_c, ground_humidity_percent, mountain_height_m, df)

MAX_DISPLAY_HEIGHT_M = max(3500.0, mountain_height_m * 1.2)
# 気温ラベル用に、y軸の下側(データ座標の負の領域)に少しすき間を確保する
Y_AXIS_MIN = -MAX_DISPLAY_HEIGHT_M * 0.13
LABEL_Y = Y_AXIS_MIN * 0.6

with col_main:
    fig = go.Figure()

    # 空(背景)
    fig.add_shape(
        type="rect", x0=-1.15, x1=1.15, y0=Y_AXIS_MIN, y1=MAX_DISPLAY_HEIGHT_M,
        fillcolor=SKY_BG_COLOR, line=dict(width=0), layer="below",
    )

    # 地面(ふもとが同じ高さでつながっていることを示す線)
    fig.add_shape(
        type="line", x0=-1.1, x1=1.1, y0=0, y1=0,
        line=dict(color=GROUND_LINE_COLOR, width=2),
    )

    # 山(左右対称の三角形)
    fig.add_trace(
        go.Scatter(
            x=[-0.8, 0.0, 0.8, -0.8],
            y=[0, mountain_height_m, 0, 0],
            fill="toself",
            mode="lines",
            line=dict(color=MOUNTAIN_LINE_COLOR, width=2),
            fillcolor=MOUNTAIN_COLOR,
            name="山",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # 雲(できる場合のみ描画)。
    # 雲ができるのは風上側(左)が上昇して露点に達してから山頂までの間だけで、
    # 山頂を越えた風下側(右)は乾いた空気が下降するだけなので、雲は描かない
    # (風上側だけ雲がかかり、風下側は乾いて晴れている、というのがフェーン現象の典型的な絵)。
    if state.cloud_formed:
        base_y = state.cloud_base_height_m
        peak_y = mountain_height_m

        def slope_x(h: float) -> float:
            """高度hにおける、山の左側(風上側)斜面のx座標(三角形の左辺に一致)"""
            return -0.8 * (1.0 - h / mountain_height_m)

        # 雲底から山頂までを、風上側の斜面に沿って描画する。
        # 外側(左・空側)に大きくふくらみつつ、内側(右・山側)にも少し重なることで、
        # 斜面をしっかり覆っているように見せる。雲底・山頂の両端ではふくらみ0にして、
        # 斜面にすっと吸い付くような形にする。
        point_count = 11
        altitudes = [base_y + (peak_y - base_y) * i / (point_count - 1) for i in range(point_count)]
        max_bulge_out = 0.55  # 外側(空側)へのふくらみの最大値
        max_bulge_in = 0.20   # 内側(山側)への食い込みの最大値
        shape_factor = [math.sin(math.pi * i / (point_count - 1)) for i in range(point_count)]
        bulges_out = [max_bulge_out * f for f in shape_factor]
        bulges_in = [max_bulge_in * f for f in shape_factor]
        inner_x = [min(slope_x(h) + b, 0.0) for h, b in zip(altitudes, bulges_in)]
        outer_x = [slope_x(h) - b for h, b in zip(altitudes, bulges_out)]

        polygon_x = inner_x + outer_x[::-1]
        polygon_y = altitudes + altitudes[::-1]

        fig.add_trace(
            go.Scatter(
                x=polygon_x,
                y=polygon_y,
                fill="toself",
                mode="lines",
                line=dict(width=0),
                fillcolor=CLOUD_COLOR,
                name="雲",
                hoverinfo="skip",
                showlegend=False,
            )
        )

        # 外側の縁に、もこもこした質感を出すための円を並べる(両端は0になるので内側の点だけ使う)
        puff_x = outer_x[1:-1]
        puff_y = altitudes[1:-1]
        puff_sizes = [40, 52, 44, 56, 46, 54, 42, 48, 36]
        fig.add_trace(
            go.Scatter(
                x=puff_x,
                y=puff_y,
                mode="markers",
                marker=dict(size=puff_sizes[: len(puff_x)], color=CLOUD_COLOR, opacity=1.0, line=dict(width=0)),
                name="雲",
                hoverinfo="skip",
                showlegend=False,
            )
        )

        # 雲底を示す点線(風上側の斜面のあたりだけに描き、風下側には引かない)
        fig.add_shape(
            type="line", x0=-1.05, x1=slope_x(base_y),
            y0=base_y, y1=base_y,
            line=dict(color=BASE_LINE_COLOR, width=2, dash="dash"),
        )
        fig.add_annotation(
            x=-1.05, y=base_y,
            xref="x", yref="y", xanchor="left",
            text=f"雲底 約{base_y:.0f}m",
            showarrow=False,
            font=dict(size=14, color=BASE_LINE_COLOR),
            bgcolor="rgba(255,255,255,0.9)",
        )

    # 山頂マーク・気温
    fig.add_trace(
        go.Scatter(
            x=[0.0], y=[mountain_height_m],
            mode="markers+text",
            marker=dict(color=PEAK_MARK_COLOR, size=10, symbol="triangle-up"),
            text=[f"山頂 {state.peak_temperature_c:.1f}℃"],
            textposition="top center",
            textfont=dict(size=14, color=PEAK_MARK_COLOR),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # 風上側(左)ふもとのマークとラベル
    fig.add_trace(
        go.Scatter(
            x=[-0.8], y=[0],
            mode="markers",
            marker=dict(color=WINDWARD_COLOR, size=12),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(
        x=-0.8, y=LABEL_Y, xref="x", yref="y",
        text=f"{state.ground_temperature_c:.1f}℃ / {state.ground_relative_humidity_percent:.0f}%",
        showarrow=False,
        font=dict(size=20, color=WINDWARD_COLOR),
        align="center",
    )

    # 風下側(右)ふもとのマークとラベル
    fig.add_trace(
        go.Scatter(
            x=[0.8], y=[0],
            mode="markers",
            marker=dict(color=LEEWARD_COLOR, size=12),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(
        x=0.8, y=LABEL_Y, xref="x", yref="y",
        text=f"{state.leeward_temperature_c:.1f}℃ / {state.leeward_relative_humidity_percent:.0f}%",
        showarrow=False,
        font=dict(size=20, color=LEEWARD_COLOR),
        align="center",
    )

    fig.update_layout(
        xaxis=dict(range=[-1.15, 1.15], visible=False, fixedrange=True),
        yaxis=dict(
            range=[Y_AXIS_MIN, MAX_DISPLAY_HEIGHT_M],
            title="高度 [m]",
            tick0=0,
            dtick=1000,
            fixedrange=True,
        ),
        plot_bgcolor=SKY_BG_COLOR,
        margin=dict(l=60, r=20, t=30, b=20),
        height=560,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------
    # 状態に応じた説明文
    # ------------------------------------------------------------
    if not state.cloud_base_reliable:
        st.warning(
            "風上側の空気が非常に乾燥しているため、この教材の計算モデルで正確な雲底高度を"
            "求められる範囲を超えています。ただし、これほど乾燥していればこの山では雲は"
            "できないと考えてよいでしょう。雲ができないため、風下側の気温は風上側とほぼ同じです。"
        )
    elif not state.cloud_formed:
        st.info(
            f"雲ができる高さ(計算上は約{state.cloud_base_height_m:.0f}m)が、"
            f"この山の高さ({mountain_height_m:.0f}m)より高いため、山を越えても雲はできません。"
            "行きも帰りも同じ割合で気温が変化するため、風下側の気温は風上側とほぼ同じで、"
            "フェーン現象は起こりません。"
        )
    elif state.cloud_base_height_m <= 0.05:
        st.success(
            "風上側のふもとですでに湿度100%です(霧や雲がふもとから発生している状態)。"
            f"山を越えると、風下側の気温は風上側より約{state.temperature_rise_c:.1f}℃高くなります。"
        )
    else:
        st.success(
            f"約{state.cloud_base_height_m:.0f}mで雲ができ始めます。山頂を越えると雲(水滴)は"
            f"雨として落ちてしまうため、風下側では気温が風上側より約{state.temperature_rise_c:.1f}℃"
            "高くなります(フェーン現象)。"
        )

with col_values:
    st.markdown("**風上側(左)のふもと**")
    st.metric("気温", f"{state.ground_temperature_c:.1f} ℃")
    st.metric("湿度", f"{state.ground_relative_humidity_percent:.0f} %")
    if state.dew_point_out_of_range == "low":
        st.metric("露点", f"{t_min:.0f} ℃未満")
    elif state.dew_point_out_of_range == "high":
        st.metric("露点", f"{t_max:.0f} ℃超")
    else:
        st.metric("露点", f"{state.ground_dew_point_c:.1f} ℃")

    st.markdown("**山頂**")
    st.metric("雲ができるか", "できる" if state.cloud_formed else "できない")
    if state.cloud_base_reliable:
        st.metric("雲ができ始める高さ", f"約{state.cloud_base_height_m:.0f} m")
    else:
        st.metric("雲ができ始める高さ", "計算範囲外")
    st.metric("山頂の気温", f"{state.peak_temperature_c:.1f} ℃")

    st.markdown("**風下側(右)のふもと**")
    st.metric(
        "気温",
        f"{state.leeward_temperature_c:.1f} ℃",
        delta=f"{state.temperature_rise_c:+.1f} ℃(風上との差)",
    )
    st.metric(
        "湿度",
        f"{state.leeward_relative_humidity_percent:.0f} %",
        delta=f"{state.leeward_relative_humidity_percent - state.ground_relative_humidity_percent:+.0f} %(風上との差)",
        delta_color="inverse",
    )
