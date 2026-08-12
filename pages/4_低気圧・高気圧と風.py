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

import json
import math
import os

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
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
    "風の強さは、その地点での等圧線の混み具合(気圧の傾き)に比例するものとしています。"
    "等圧線は天気図と同じく4hPaごとに引き、20hPaごとに太線にしています"
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

    st.markdown("**表示スタイル**")
    DISPLAY_STYLE_OPTIONS = ["矢印グリッド", "粒子アニメーション", "矢印+粒子アニメーション"]
    if "wind_display_style" not in st.session_state:
        st.session_state.wind_display_style = DISPLAY_STYLE_OPTIONS[0]
    display_style = st.radio(
        "表示スタイル",
        DISPLAY_STYLE_OPTIONS,
        index=DISPLAY_STYLE_OPTIONS.index(st.session_state.wind_display_style),
        key="wind_display_style_radio",
        label_visibility="collapsed",
    )
    st.session_state.wind_display_style = display_style

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
        PressureCenter(x=-0.35, y=-0.3, kind="low",
                        strength_hpa=st.session_state.wind_strength_low, radius=CENTER_RADIUS),
        PressureCenter(x=0.35, y=0.3, kind="high",
                        strength_hpa=st.session_state.wind_strength_high, radius=CENTER_RADIUS),
    ]

max_strength = max(c.strength_hpa for c in centers)

with col_main:
    if display_style == "矢印グリッド":
        fig = go.Figure()

        # ------------------------------------------------------------
        # 等圧線(気圧の偏差の等高線)。天気図の慣習にあわせて、
        # 4hPaごとに細線、20hPaごとに太線を引く。
        # ------------------------------------------------------------
        grid_n = 70
        xs = np.linspace(-1.0, 1.0, grid_n)
        ys = np.linspace(-1.0, 1.0, grid_n)
        z = np.array([[pressure_deviation(x, y, centers) for x in xs] for y in ys])

        LEVEL_STEP = 4.0
        BOLD_STEP = 20.0
        level_max = math.ceil((max_strength + LEVEL_STEP) / LEVEL_STEP) * LEVEL_STEP
        bold_max = math.ceil(level_max / BOLD_STEP) * BOLD_STEP

        # 細線(4hPaごと)
        fig.add_trace(
            go.Contour(
                x=xs, y=ys, z=z,
                contours=dict(coloring="lines", start=-level_max, end=level_max, size=LEVEL_STEP),
                line=dict(width=1.1),
                colorscale=[[0.0, ISOBAR_LOW_COLOR], [0.5, ISOBAR_MID_COLOR], [1.0, ISOBAR_HIGH_COLOR]],
                zmin=-level_max, zmax=level_max,
                showscale=False,
                hoverinfo="skip",
            )
        )
        # 太線(20hPaごと)。色のスケールは細線と揃えて、同じ値なら同じ色になるようにする。
        fig.add_trace(
            go.Contour(
                x=xs, y=ys, z=z,
                contours=dict(coloring="lines", start=-bold_max, end=bold_max, size=BOLD_STEP),
                line=dict(width=2.6),
                colorscale=[[0.0, ISOBAR_LOW_COLOR], [0.5, ISOBAR_MID_COLOR], [1.0, ISOBAR_HIGH_COLOR]],
                zmin=-level_max, zmax=level_max,
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

    else:
        # ------------------------------------------------------------
        # 粒子アニメーション(Windy風)。「矢印+粒子アニメーション」の場合は、
        # 同じCanvas上に静的な矢印グリッドも重ねて描画する。
        # StreamlitやPlotlyの標準機能だとなめらかなアニメーションが難しいため、
        # HTML5 Canvas + JavaScriptをそのまま埋め込んで描画する。
        # 風向風速の計算式(気圧勾配→コリオリ偏向)は wind_vector_at と同じものを
        # JavaScript側に移植しているので、Python側と同じ結果になるはず。
        # ------------------------------------------------------------
        show_arrows_js = "true" if display_style == "矢印+粒子アニメーション" else "false"
        centers_json = json.dumps([
            {"x": c.x, "y": c.y, "kind": c.kind, "strength": c.strength_hpa, "radius": c.radius}
            for c in centers
        ])

        particle_html = f"""
        <canvas id="windCanvas" width="700" height="700"
                style="width:100%; max-width:700px; display:block; margin:0 auto;
                       background:#dceefb; border-radius:8px;"></canvas>
        <script>
        (function() {{
            const centers = {centers_json};
            const deflectionDeg = {CORIOLIS_DEFLECTION_DEG};
            const SHOW_ARROWS = {show_arrows_js};
            const canvas = document.getElementById('windCanvas');
            const ctx = canvas.getContext('2d');
            const W = canvas.width, H = canvas.height;

            const LOW_COLOR = '{LOW_COLOR}';
            const HIGH_COLOR = '{HIGH_COLOR}';
            const PARTICLE_COLOR = '#1f3a52';
            const ARROW_COLOR = '{ARROW_COLOR}';

            function toCanvas(x, y) {{
                return [(x + 1) / 2 * W, (1 - y) / 2 * H];
            }}

            function pressureGradient(x, y) {{
                let gx = 0, gy = 0;
                for (const c of centers) {{
                    const sign = c.kind === 'low' ? -1 : 1;
                    const dx = x - c.x, dy = y - c.y;
                    const r2 = dx * dx + dy * dy;
                    const val = sign * c.strength * Math.exp(-r2 / (2 * c.radius * c.radius));
                    gx += val * (-dx / (c.radius * c.radius));
                    gy += val * (-dy / (c.radius * c.radius));
                }}
                return [gx, gy];
            }}

            function windVectorAt(x, y) {{
                const [gx, gy] = pressureGradient(x, y);
                const gradMag = Math.hypot(gx, gy);
                if (gradMag < 1e-9) return [0, 0, 0];
                const dxDir = -gx / gradMag, dyDir = -gy / gradMag;
                const theta = deflectionDeg * Math.PI / 180;
                const wx = dxDir * Math.cos(theta) + dyDir * Math.sin(theta);
                const wy = -dxDir * Math.sin(theta) + dyDir * Math.cos(theta);
                return [wx, wy, gradMag];
            }}

            function randomPosition() {{
                // 円形の領域内に、面積が一様になるように配置する
                // (半径rを一様乱数にすると中心付近が濃くなってしまうため、sqrt(乱数)を使う)
                let x, y, tooClose;
                do {{
                    const angle = Math.random() * 2 * Math.PI;
                    const r = Math.sqrt(Math.random()) * 0.92;
                    x = r * Math.cos(angle);
                    y = r * Math.sin(angle);
                    tooClose = centers.some(c => Math.hypot(x - c.x, y - c.y) < 0.16);
                }} while (tooClose);
                return [x, y];
            }}

            const PARTICLE_COUNT = SHOW_ARROWS ? 150 : 260;
            const particles = [];
            for (let i = 0; i < PARTICLE_COUNT; i++) {{
                const [x, y] = randomPosition();
                particles.push({{x: x, y: y, age: Math.floor(Math.random() * 120)}});
            }}

            // 粒子の移動に使うのと同じ刻み幅(矢印=流線も、粒子と同じ経路をたどらせるため)
            const STEP_SCALE = 0.00022;
            const MIN_STEP = 0.0012;
            const MAX_STEP = 0.012;

            // ある地点から実際に風向風速の式に従って軌跡をたどり、1本の流線を求める。
            // 低気圧は外側から吸い込まれる向き、高気圧は中心から吹き出す向きにたどることで、
            // 渦を巻きながら中心に近づく・遠ざかる「銀河の腕」のような曲線になる。
            function traceStreamline(startX, startY, maxSteps) {{
                const pts = [[startX, startY]];
                let x = startX, y = startY;
                for (let i = 0; i < maxSteps; i++) {{
                    const result = windVectorAt(x, y);
                    const wx = result[0], wy = result[1], mag = result[2];
                    if (mag < 1e-9) break;
                    let step = mag * STEP_SCALE;
                    step = Math.max(MIN_STEP, Math.min(MAX_STEP, step));
                    x += wx * step;
                    y += wy * step;
                    pts.push([x, y]);
                    if (Math.hypot(x, y) > 1.0) break;
                    const tooClose = centers.some(c => Math.hypot(x - c.x, y - c.y) < 0.06);
                    if (tooClose) break;
                }}
                return pts;
            }}

            const ARM_COUNT = 6;      // ひとつの気圧中心あたりの腕の本数
            const ARM_STEPS = 150;    // 1本の腕をたどるステップ数

            function computeArms() {{
                const arms = [];
                for (const c of centers) {{
                    // 低気圧は外側の点から始めて中心へ吸い込まれる経路を、
                    // 高気圧は中心近くの点から始めて外へ広がる経路をたどる
                    const startRadius = c.kind === 'low' ? 0.85 : 0.10;
                    for (let i = 0; i < ARM_COUNT; i++) {{
                        const angle = (2 * Math.PI * i) / ARM_COUNT;
                        const sx = c.x + startRadius * Math.cos(angle);
                        const sy = c.y + startRadius * Math.sin(angle);
                        const pts = traceStreamline(sx, sy, ARM_STEPS);
                        if (pts.length > 3) arms.push(pts);
                    }}
                }}
                return arms;
            }}
            const arms = SHOW_ARROWS ? computeArms() : [];

            function drawArms() {{
                ctx.save();
                ctx.globalAlpha = 0.5;
                ctx.strokeStyle = ARROW_COLOR;
                ctx.fillStyle = ARROW_COLOR;
                ctx.lineWidth = 1.6;
                ctx.lineJoin = 'round';
                ctx.lineCap = 'round';
                for (const pts of arms) {{
                    ctx.beginPath();
                    const p0 = toCanvas(pts[0][0], pts[0][1]);
                    ctx.moveTo(p0[0], p0[1]);
                    for (let i = 1; i < pts.length; i++) {{
                        const p = toCanvas(pts[i][0], pts[i][1]);
                        ctx.lineTo(p[0], p[1]);
                    }}
                    ctx.stroke();

                    // 曲線の終端に矢じりをつけて、流れの向きを示す
                    const lastIdx = pts.length - 1;
                    const prevIdx = Math.max(0, pts.length - 4);
                    const last = toCanvas(pts[lastIdx][0], pts[lastIdx][1]);
                    const prev = toCanvas(pts[prevIdx][0], pts[prevIdx][1]);
                    const angle = Math.atan2(last[1] - prev[1], last[0] - prev[0]);
                    const headLen = 9;
                    ctx.beginPath();
                    ctx.moveTo(last[0], last[1]);
                    ctx.lineTo(
                        last[0] - headLen * Math.cos(angle - Math.PI / 6),
                        last[1] - headLen * Math.sin(angle - Math.PI / 6)
                    );
                    ctx.lineTo(
                        last[0] - headLen * Math.cos(angle + Math.PI / 6),
                        last[1] - headLen * Math.sin(angle + Math.PI / 6)
                    );
                    ctx.closePath();
                    ctx.fill();
                }}
                ctx.restore();
            }}

            function drawBackground() {{
                const ringScale = W / 2;
                for (const c of centers) {{
                    const [cx, cy] = toCanvas(c.x, c.y);
                    const color = c.kind === 'low' ? LOW_COLOR : HIGH_COLOR;

                    // 気圧偏差 = 強さ * exp(-r^2 / (2*radius^2)) を r について解くことで、
                    // 「気圧差がちょうどLになる半径」を厳密に求める(4hPaごと、20hPaごとに太線)。
                    // ※2つの中心が重なる場所ではこの円は近似になる(実際の等圧線は歪む)。
                    for (let L = 4; L < c.strength; L += 4) {{
                        const ratio = L / c.strength;
                        const r = c.radius * Math.sqrt(-2 * Math.log(ratio));
                        const isBold = (L % 20 === 0);
                        ctx.strokeStyle = color;
                        ctx.globalAlpha = isBold ? 0.75 : 0.4;
                        ctx.lineWidth = isBold ? 2.4 : 1.1;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r * ringScale, 0, Math.PI * 2);
                        ctx.stroke();
                    }}
                    ctx.globalAlpha = 1.0;

                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(cx, cy, 16, 0, Math.PI * 2);
                    ctx.fill();

                    ctx.fillStyle = 'white';
                    ctx.font = 'bold 16px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(c.kind === 'low' ? '低' : '高', cx, cy + 1);
                }}
            }}

            const MAX_AGE = 240;

            function updateParticle(p) {{
                const result = windVectorAt(p.x, p.y);
                const wx = result[0], wy = result[1], mag = result[2];
                let step = mag * STEP_SCALE;
                step = Math.max(MIN_STEP, Math.min(MAX_STEP, step));
                p.x += wx * step;
                p.y += wy * step;
                p.age += 1;

                const outOfBounds = Math.hypot(p.x, p.y) > 1.0;
                const tooClose = centers.some(c => Math.hypot(p.x - c.x, p.y - c.y) < 0.08);
                if (outOfBounds || tooClose || p.age > MAX_AGE) {{
                    const pos = randomPosition();
                    p.x = pos[0];
                    p.y = pos[1];
                    p.age = 0;
                }}
            }}

            function frame() {{
                ctx.fillStyle = 'rgba(220, 238, 251, 0.14)';
                ctx.fillRect(0, 0, W, H);

                drawBackground();
                if (SHOW_ARROWS) {{
                    drawArms();
                }}

                ctx.fillStyle = PARTICLE_COLOR;
                for (const p of particles) {{
                    updateParticle(p);
                    const pos = toCanvas(p.x, p.y);
                    ctx.beginPath();
                    ctx.arc(pos[0], pos[1], 2.2, 0, Math.PI * 2);
                    ctx.fill();
                }}

                requestAnimationFrame(frame);
            }}

            ctx.fillStyle = '#dceefb';
            ctx.fillRect(0, 0, W, H);
            frame();
        }})();
        </script>
        """
        components.html(particle_html, height=650)
        st.caption(
            "点(粒子)が実際の風の流れのように動きます。低気圧のまわりでは反時計回りに"
            "渦を巻きながら中心に吸い込まれ、高気圧のまわりでは時計回りに渦を巻きながら"
            "外側へ広がっていく様子に注目してみましょう。"
        )

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
