# -*- coding: utf-8 -*-
"""
pages/5_乾湿球と湿度表.py

中学2年理科「乾湿球温度計と湿度表」学習用ページ
左:乾球・湿球温度計(水銀柱をドラッグして動かす)
右:湿度表(現在の値の行・列・交点を強調)

湿度表は乾湿計の式
    e = es(湿球) - A * P * (乾球 - 湿球)   湿度 = e / es(乾球) * 100
から作成(A = 0.0008 を使うと一般的な中学校の湿度表とほぼ一致する)。
"""

import json

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="乾湿球と湿度表", layout="wide")

# ---------------------------------------------------------------
# 湿度表の作成(乾球 0〜40℃ を1℃刻み、差 0〜10℃ を0.5℃刻み)
# ---------------------------------------------------------------
PRESSURE_HPA = 1013.25
PSYCHRO_COEF = 0.0008  # 乾湿計定数(1/℃)


def saturation_vapor_pressure_hpa(t_c: float) -> float:
    """Tetens の式による飽和水蒸気圧[hPa]"""
    return 6.1078 * 10 ** (7.5 * t_c / (t_c + 237.3))


def humidity_percent(dry_c: float, wet_c: float) -> int:
    e = saturation_vapor_pressure_hpa(wet_c) - PSYCHRO_COEF * PRESSURE_HPA * (dry_c - wet_c)
    rh = 100.0 * e / saturation_vapor_pressure_hpa(dry_c)
    return max(0, round(rh))


def build_table():
    table = {}
    for dry in range(0, 41):
        row = []
        for k in range(0, 21):  # 差 0.0, 0.5, ... 10.0
            diff = k * 0.5
            row.append(humidity_percent(dry, dry - diff))
        table[dry] = row
    return table


TABLE = build_table()

st.title("乾湿球温度計と湿度表")
st.write(
    "左の温度計の液の先を**ドラッグ**して動かしてみよう。"
    "乾球と湿球の示度の差から、右の湿度表で湿度を読み取ることができます。"
)

HTML = r"""
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family: "Hiragino Sans","Yu Gothic","Meiryo",sans-serif; color:#222; background:transparent; }
  .wrap { display:flex; flex-wrap:wrap; gap:24px; align-items:flex-start; justify-content:center; }
  .left { width:380px; max-width:100%; }
  .right { flex:1; min-width:380px; }
  canvas { touch-action:none; background:#fff; border:1px solid #ccd; border-radius:8px; display:block; width:380px; height:520px; max-width:100%; cursor:ns-resize; }
  .bar { margin-top:8px; display:flex; gap:6px; flex-wrap:wrap; align-items:center; font-size:14px; }
  .bar button { padding:4px 10px; border:1px solid #889; background:#f4f6fb; border-radius:6px; cursor:pointer; font-size:14px; }
  .bar button.on { background:#2d6cdf; color:#fff; border-color:#2d6cdf; }
  .fine { display:flex; gap:6px; margin-top:6px; font-size:13px; justify-content:space-around; }
  .fine button { padding:2px 10px; border:1px solid #889; background:#f4f6fb; border-radius:6px; cursor:pointer; font-size:14px; }
  h3 { margin:0 0 6px 0; font-size:20px; }
  table { border-collapse:collapse; width:100%; background:#fff; color:#222; font-size:20px; text-align:center; }
  th, td { border:1px solid #bbb; padding:7px 4px; }
  th { background:#eceef2; font-weight:600; }
  td.hl-row { background:#fde6e3; }
  td.hl-col { background:#fff3d6; }
  th.hl-col { background:#ffd98a; }
  td.hl-row-head { background:#f3a49c; font-weight:700; }
  td.hit { background:#1b7f3b; color:#fff; font-weight:700; outline:3px solid #1b7f3b; }
  .readout { margin-top:12px; padding:10px 14px; background:#f4f7ff; border:1px solid #c4d0f0; border-radius:8px; font-size:20px; line-height:1.7; color:#222; }
  .readout b { font-size:24px; }
  .ans { color:#1b7f3b; white-space:nowrap; }
  label { cursor:pointer; }
  @media (prefers-color-scheme: dark) {
    body { color:#eee; }
    .bar button, .fine button { color:#222; }
  }
</style></head>
<body>
<div class="wrap">
  <div class="left">
    <canvas id="cv" width="380" height="520"></canvas>
    <div class="fine">
      <span>乾球 <button id="dm">−1</button><button id="dp">+1</button></span>
      <span>湿球 <button id="wm">−0.5</button><button id="wp">+0.5</button></span>
    </div>
    <div class="bar">
      目盛りの範囲:
      <button data-w="0">0〜10℃</button>
      <button data-w="10">10〜20℃</button>
      <button data-w="20">20〜30℃</button>
      <button data-w="30">30〜40℃</button>
    </div>
  </div>
  <div class="right">
    <h3>湿度表</h3>
    <table id="tbl"></table>
    <div class="readout" id="out"></div>
    <div class="bar"><label><input type="checkbox" id="hide"> 湿度を隠す(自分で表を読み取る練習)</label></div>
  </div>
</div>

<script>
const TABLE = __TABLE__;
const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');
const dpr = window.devicePixelRatio || 1;
const CW = 380, CH = 520;
cv.width = CW*dpr; cv.height = CH*dpr; ctx.scale(dpr,dpr);

let winLo = 10;          // 目盛り窓の下端(10℃幅)
let dry = 19, wet = 17;  // 乾球は1℃刻み、湿球は0.5℃刻み
const TOP = 50, BOT = 480;   // 目盛り窓の上端・下端のy座標
const SPAN = 10;
const px = (t) => BOT - (t - winLo) / SPAN * (BOT - TOP);
const val = (y) => winLo + (BOT - y) / (BOT - TOP) * SPAN;
const TUBES = [{x:105, name:'乾球', c:'#c0281c', c2:'#e8756b', tint:'#fde6e3', head:'#f3a49c'},
               {x:285, name:'湿球', c:'#1c5fc0', c2:'#6ba0e8', tint:'#e1ecfb', head:'#9bbdf0'}];
const TUBE_W = 34;

function clampState() {
  const hi = winLo + SPAN;
  dry = Math.min(hi, Math.max(winLo, Math.round(dry)));
  wet = Math.round(wet*2)/2;
  wet = Math.min(dry, Math.max(winLo, wet));
}

function draw() {
  ctx.clearRect(0,0,CW,CH);
  ctx.textBaseline = 'middle';
  TUBES.forEach((tb, i) => {
    const x = tb.x, v = i===0 ? dry : wet;
    // 名前
    ctx.fillStyle = tb.c; ctx.font = 'bold 24px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(tb.name, x, 22);
    // ガラス管
    ctx.fillStyle = '#f7f9fc'; ctx.strokeStyle = '#555'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.rect(x-TUBE_W/2, TOP-12, TUBE_W, BOT-TOP+24); ctx.fill(); ctx.stroke();
    // 水銀(赤色のアルコール柱ではなく、教科書図に合わせて灰〜黒のグラデーション)
    const g = ctx.createLinearGradient(x-8,0,x+8,0);
    g.addColorStop(0,tb.c); g.addColorStop(0.45,tb.c2); g.addColorStop(1,tb.c);
    ctx.fillStyle = g;
    ctx.fillRect(x-8, px(v), 16, BOT+12-px(v));
    // 目盛り
    for (let k=0; k<=SPAN*2; k++) {
      const t = winLo + k/2, y = px(t);
      const isInt = (k%2===0);
      const len = isInt ? 16 : 9;
      ctx.strokeStyle = '#333'; ctx.lineWidth = isInt ? 1.6 : 1;
      // 左右に目盛り
      ctx.beginPath();
      ctx.moveTo(x-TUBE_W/2-len, y); ctx.lineTo(x-TUBE_W/2, y);
      ctx.moveTo(x+TUBE_W/2, y); ctx.lineTo(x+TUBE_W/2+len, y);
      ctx.stroke();
      if (isInt && (k%4===0 || t===winLo || t===winLo+SPAN)) {
        // 5℃ごと・端に数字(教科書の「2 0」「1 0」のように)
      }
      if (isInt) {
        ctx.fillStyle = '#222'; ctx.font = (t%5===0 ? 'bold 17px' : '14px') + ' sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(String(t), x-TUBE_W/2-20, y);
      }
    }
    // 読み取り線と値
    const y = px(v);
    ctx.strokeStyle = tb.c; ctx.lineWidth = 2; ctx.setLineDash([5,4]);
    ctx.beginPath(); ctx.moveTo(x-TUBE_W/2-4, y); ctx.lineTo(x+TUBE_W/2+30, y); ctx.stroke();
    ctx.setLineDash([]);
    // つかみ(三角)
    ctx.fillStyle = tb.c;
    ctx.beginPath(); ctx.moveTo(x+TUBE_W/2+30, y); ctx.lineTo(x+TUBE_W/2+44, y-8); ctx.lineTo(x+TUBE_W/2+44, y+8); ctx.closePath(); ctx.fill();
    ctx.font = 'bold 18px sans-serif';
    ctx.textAlign = i===0 ? 'left' : 'right';
    ctx.fillText(v.toFixed(1)+'℃', i===0 ? x+TUBE_W/2+48 : CW-4, y-16 < TOP-14 ? TOP-14 : y-16);
  });
  // 湿球ガーゼ表示
  ctx.fillStyle = '#555'; ctx.font = '13px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('(球部をぬれたガーゼで包む)', TUBES[1].x, 505);
  ctx.fillText('(ふつうの温度計)', TUBES[0].x, 505);
}

function fmt(n){ return n.toFixed(1); }

function renderTable() {
  const diff = Math.round((dry - wet)*2)/2;
  // 行: 乾球±3(0〜40に収める)
  let r0 = Math.max(0, Math.min(40-6, dry-3));
  const rows = []; for (let r=r0+6; r>=r0; r--) rows.push(r);
  // 列: 差 diff を含む7列(0〜10に収める)
  let c0 = Math.max(0, Math.min(10-3, diff-2.5));
  c0 = Math.round(c0*2)/2;
  const cols = []; for (let k=0;k<7;k++) cols.push(c0 + k*0.5);

  let h = '<tr><th rowspan="2" style="width:22%">乾球の<br>示度<br>〔℃〕</th><th colspan="7">乾球と湿球の示度の差〔℃〕</th></tr><tr>';
  cols.forEach(c => { h += '<th class="'+(c===diff?'hl-col':'')+'">'+fmt(c)+'</th>'; });
  h += '</tr>';
  rows.forEach(r => {
    h += '<tr><td class="'+(r===dry?'hl-row-head':'')+'">'+r+'</td>';
    cols.forEach(c => {
      const v = TABLE[r][Math.round(c*2)];
      let cls = '';
      if (r===dry && c===diff) cls = 'hit';
      else if (r===dry) cls = 'hl-row';
      else if (c===diff) cls = 'hl-col';
      h += '<td class="'+cls+'">'+v+'</td>';
    });
    h += '</tr>';
  });
  document.getElementById('tbl').innerHTML = h;

  const hide = document.getElementById('hide').checked;
  const rh = TABLE[dry][Math.round(diff*2)];
  document.getElementById('out').innerHTML =
    '<span style="color:#c0281c">乾球の示度 <b>'+dry+'℃</b></span>、<span style="color:#1c5fc0">湿球の示度 <b>'+fmt(wet)+'℃</b></span><br>' +
    '示度の差 <b>'+fmt(diff)+'℃</b><br>' +
    '湿度表で「乾球 '+dry+'℃」の行と「差 '+fmt(diff)+'℃」の列が交わるところ → ' +
    (hide ? '<b class="ans">?? %</b>' : '<b class="ans">'+rh+' %</b>');
}

function update() {
  clampState(); draw(); renderTable();
  document.querySelectorAll('.bar button[data-w]').forEach(b => {
    b.classList.toggle('on', Number(b.dataset.w) === winLo);
  });
}

// ドラッグ操作
let drag = null;
function pointerY(e) { const r = cv.getBoundingClientRect(); return (e.clientY - r.top) * (CH / r.height); }
function pointerX(e) { const r = cv.getBoundingClientRect(); return (e.clientX - r.left) * (CW / r.width); }
function apply(which, y) {
  const v = val(y);
  if (which === 0) { dry = Math.round(v); if (wet > dry) wet = dry; }
  else { wet = Math.round(v*2)/2; }
  update();
}
cv.addEventListener('pointerdown', e => {
  drag = pointerX(e) < CW/2 ? 0 : 1;
  cv.setPointerCapture(e.pointerId);
  apply(drag, pointerY(e));
});
cv.addEventListener('pointermove', e => { if (drag !== null) apply(drag, pointerY(e)); });
const endDrag = () => { drag = null; };
cv.addEventListener('pointerup', endDrag);
cv.addEventListener('pointercancel', endDrag);

// ボタン
document.getElementById('dm').onclick = () => { dry -= 1; update(); };
document.getElementById('dp').onclick = () => { dry += 1; update(); };
document.getElementById('wm').onclick = () => { wet -= 0.5; update(); };
document.getElementById('wp').onclick = () => { wet += 0.5; update(); };
document.querySelectorAll('.bar button[data-w]').forEach(b => {
  b.onclick = () => {
    const rel = dry - winLo, relw = wet - winLo;
    winLo = Number(b.dataset.w);
    dry = winLo + rel; wet = winLo + relw;   // 窓の中の同じ位置に移動
    update();
  };
});
document.getElementById('hide').onchange = update;
update();
</script>
</body></html>
"""

components.html(HTML.replace("__TABLE__", json.dumps(TABLE)), height=720)

with st.expander("この湿度表の作り方(先生向け)"):
    st.markdown(
        """
湿度表の値は、乾湿計の式から計算しています。

- 水蒸気圧 e = (湿球温度での飽和水蒸気圧) − A × 気圧 × (乾球 − 湿球)
- 湿度[%] = e ÷ (乾球温度での飽和水蒸気圧) × 100
- 気圧は 1013.25 hPa、乾湿計定数 A は 0.0008/℃ としました。

一般的な中学校の湿度表とは、四捨五入の違いで 1% ずれるマスがわずかにあります。
"""
    )
