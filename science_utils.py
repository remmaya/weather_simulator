# -*- coding: utf-8 -*-
"""
science_utils.py

気温と水蒸気量に関する計算ロジックをまとめたモジュール。

・Streamlit(UI)には依存しない
・飽和水蒸気量はCSVファイルの値を補間して求める(物理式の近似計算は使わない)
・将来、フェーン現象や放射冷却の教材でも計算部分を再利用できるように、
  「表を読み込む」「表を引く」処理だけを独立させてある

CSVファイルの形式:
    temperature_c,saturation_g_m3
    0.0,4.85
    0.5,5.02
    ...
"""

from dataclasses import dataclass
import math
import pandas as pd
import numpy as np


@dataclass
class MoistureState:
    """ある気温・ある水蒸気量における状態をまとめて表すクラス"""
    temperature_c: float          # 気温 [℃]
    initial_water_g_m3: float     # 最初に含まれていた水の量 [g/m3]
    saturation_g_m3: float        # その気温での飽和水蒸気量 [g/m3]
    vapor_g_m3: float             # 現在、水蒸気として存在する量 [g/m3]
    condensed_g_m3: float         # 結露した水の量 [g/m3]
    humidity_percent: float       # 湿度 [%](100%が上限)
    dew_point_c: float            # 露点 [℃](表の範囲外の場合は端の値にクリップ済み)
    dew_point_out_of_range: str   # "low" / "high" / "" のいずれか(表の範囲外かどうか)


def load_saturation_table(csv_path: str) -> pd.DataFrame:
    """
    飽和水蒸気量テーブル(CSV)を読み込む。

    列名は temperature_c, saturation_g_m3 を想定。
    気温の昇順に並んでいることを前提とする。
    """
    df = pd.read_csv(csv_path)
    df = df.sort_values("temperature_c").reset_index(drop=True)
    return df


def get_temperature_range(df: pd.DataFrame):
    """テーブルに含まれる気温の最小値・最大値を返す"""
    return float(df["temperature_c"].min()), float(df["temperature_c"].max())


def saturation_at(temperature_c: float, df: pd.DataFrame) -> float:
    """
    指定した気温における飽和水蒸気量を、CSVデータの直線補間で求める。

    物理式(テテンス式など)は使わず、あくまで表の値を補間する。
    表の範囲外の気温が渡された場合は、範囲の端の値でクリップする。
    """
    t_min, t_max = get_temperature_range(df)
    t = min(max(temperature_c, t_min), t_max)
    return float(np.interp(t, df["temperature_c"], df["saturation_g_m3"]))


def dew_point_from_water_amount(water_g_m3: float, df: pd.DataFrame):
    """
    「空気中の水蒸気量」から露点(気温を下げて湿度100%になる気温)を求める。

    飽和水蒸気量は気温に対して単調に増加するテーブルであることを利用し、
    (saturation_g_m3 -> temperature_c) の対応を逆に補間して露点を求める。

    戻り値は (露点[℃], 範囲外フラグ) のタプル。
    範囲外フラグは、水の量が表の最小飽和水蒸気量を下回る場合 "low"、
    表の最大飽和水蒸気量を超える場合 "high"、範囲内なら "" となる。
    範囲外の場合、露点の値自体は表の端の気温にクリップした近似値を返す
    (表示側で「範囲外」であることを明示するために使う)。
    """
    sat_min = float(df["saturation_g_m3"].iloc[0])
    sat_max = float(df["saturation_g_m3"].iloc[-1])
    t_min, t_max = get_temperature_range(df)

    if water_g_m3 < sat_min:
        out_of_range = "low"
    elif water_g_m3 > sat_max:
        out_of_range = "high"
    else:
        out_of_range = ""

    w = min(max(water_g_m3, sat_min), sat_max)
    # saturation_g_m3 は temperature_c に対して単調増加である前提
    dew_point = float(np.interp(w, df["saturation_g_m3"], df["temperature_c"]))
    return dew_point, out_of_range


def compute_state(temperature_c: float, initial_water_g_m3: float, df: pd.DataFrame) -> MoistureState:
    """
    気温と最初の水の量から、現在の状態(水蒸気量・結露量・湿度・露点)をまとめて計算する。
    """
    sat = saturation_at(temperature_c, df)

    vapor = min(initial_water_g_m3, sat)
    condensed = max(0.0, initial_water_g_m3 - sat)

    if sat > 0:
        humidity = min(100.0, (vapor / sat) * 100.0)
    else:
        humidity = 0.0

    dew_point, dew_point_out_of_range = dew_point_from_water_amount(initial_water_g_m3, df)

    return MoistureState(
        temperature_c=temperature_c,
        initial_water_g_m3=initial_water_g_m3,
        saturation_g_m3=sat,
        vapor_g_m3=vapor,
        condensed_g_m3=condensed,
        humidity_percent=humidity,
        dew_point_c=dew_point,
        dew_point_out_of_range=dew_point_out_of_range,
    )


# ==============================================================
# 雲のできる高さシミュレーター用の計算処理
# ここから下は「気温・湿度・露点・雲底高度」に関する処理。
# 上の処理(飽和水蒸気量・湿度・露点アプリ用)は変更していない。
# 将来のフェーン現象アプリでも、この下のブロックをそのまま再利用できるようにしてある。
# ==============================================================

# 教材用の簡略モデルの定数(中学校向けの近似値)。
# コード中に直接埋め込まず、ここで一括管理することで、
# 教材上の設定を変更しやすくしている。
DRY_LAPSE_RATE_C_PER_100M = 1.0        # 上昇する未飽和空気の気温低下 [℃/100m]
DEW_POINT_LAPSE_RATE_C_PER_100M = 0.2  # 上昇中の露点の低下 [℃/100m]


@dataclass
class CloudState:
    """地上の気温・湿度から求めた、雲のでき始める高さに関する状態をまとめて表すクラス"""
    ground_temperature_c: float            # 地上の気温 [℃]
    ground_relative_humidity_percent: float  # 地上の相対湿度 [%]
    ground_saturation_g_m3: float          # 地上の飽和水蒸気量 [g/m3]
    ground_vapor_g_m3: float               # 地上の実際の水蒸気量 [g/m3]
    ground_dew_point_c: float              # 地上の露点 [℃](範囲外の場合はクリップ済み参考値)
    dew_point_out_of_range: str            # "low" / "high" / "" (地上の露点がCSV範囲外かどうか)
    temp_dew_diff_c: float                 # 地上の気温と露点の差 [℃]
    cloud_base_height_m: float             # 雲底高度の計算値 [m]
    cloud_base_reliable: bool              # 上の計算値が信頼できるか(範囲外のときは False)
    temperature_at_cloud_base_c: float     # 雲ができ始める高度での気温 [℃]


def water_amount_from_relative_humidity(
    temperature_c: float, relative_humidity_percent: float, df: pd.DataFrame
) -> float:
    """
    気温と相対湿度から、実際に含まれている水蒸気量を求める。

    実際の水蒸気量 = その気温での飽和水蒸気量 × 相対湿度 ÷ 100
    (saturation_at を内部で使うだけで、飽和水蒸気量の計算自体は重複実装しない)
    """
    sat = saturation_at(temperature_c, df)
    rh = min(max(relative_humidity_percent, 0.0), 100.0)
    return sat * rh / 100.0


def temperature_at_altitude(
    ground_temperature_c: float,
    altitude_m: float,
    lapse_rate_c_per_100m: float = DRY_LAPSE_RATE_C_PER_100M,
) -> float:
    """
    地上の気温から、指定した高度での気温を求める(教材用の簡略な線形モデル)。
    """
    return ground_temperature_c - lapse_rate_c_per_100m * altitude_m / 100.0


def dew_point_at_altitude(
    ground_dew_point_c: float,
    altitude_m: float,
    lapse_rate_c_per_100m: float = DEW_POINT_LAPSE_RATE_C_PER_100M,
) -> float:
    """
    地上の露点から、指定した高度での露点を求める(教材用の簡略な線形モデル)。
    """
    return ground_dew_point_c - lapse_rate_c_per_100m * altitude_m / 100.0


def cloud_base_height(
    ground_temperature_c: float,
    ground_dew_point_c: float,
    dry_lapse_rate_c_per_100m: float = DRY_LAPSE_RATE_C_PER_100M,
    dew_point_lapse_rate_c_per_100m: float = DEW_POINT_LAPSE_RATE_C_PER_100M,
) -> float:
    """
    地上の気温と露点から、雲ができ始める高さ(雲底高度)を求める。

    上昇する空気の気温は100mにつき dry_lapse_rate_c_per_100m ℃、
    露点は100mにつき dew_point_lapse_rate_c_per_100m ℃ 下がるものとし、
    両者が一致する(気温 = 露点になる)高さを雲底高度とする。

    地上ですでに気温 <= 露点(湿度100%以上)の場合は 0m を返す。
    """
    diff = ground_temperature_c - ground_dew_point_c
    if diff <= 0:
        return 0.0

    rate_diff = dry_lapse_rate_c_per_100m - dew_point_lapse_rate_c_per_100m
    if rate_diff <= 0:
        # 気温減率が露点低下率以下だと、上昇しても気温と露点が絶対に一致しない
        # (教材の前提が崩れているので、実装ミスとして早期に気づけるようにする)
        raise ValueError(
            "dry_lapse_rate_c_per_100m は dew_point_lapse_rate_c_per_100m より大きい必要があります"
        )

    return diff / rate_diff * 100.0


def compute_cloud_state(
    ground_temperature_c: float,
    ground_relative_humidity_percent: float,
    df: pd.DataFrame,
) -> CloudState:
    """
    地上の気温・相対湿度から、雲のでき始める高さに関する状態をまとめて計算する。

    重要:地上の空気が極端に乾燥している場合、理論上の露点がCSVデータの
    気温範囲(下限)を下回ることがある。この場合 dew_point_out_of_range が
    "low" になり、cloud_base_reliable は False になる。
    これは「表の下限の気温を仮の露点として使った、誤りうる参考値」であることを示す。
    実際にはさらに露点が低い(=雲がさらに高い所でしかできない、または全くできない)
    可能性があるため、cloud_base_reliable が False のときは、
    cloud_base_height_m の値をそのまま「雲ができる高さ」として画面に表示してはいけない。
    """
    sat = saturation_at(ground_temperature_c, df)
    vapor = water_amount_from_relative_humidity(ground_temperature_c, ground_relative_humidity_percent, df)
    dew_point, out_of_range = dew_point_from_water_amount(vapor, df)

    diff = ground_temperature_c - dew_point
    height = cloud_base_height(ground_temperature_c, dew_point)
    reliable = (out_of_range == "")
    temp_at_base = temperature_at_altitude(ground_temperature_c, height)

    return CloudState(
        ground_temperature_c=ground_temperature_c,
        ground_relative_humidity_percent=ground_relative_humidity_percent,
        ground_saturation_g_m3=sat,
        ground_vapor_g_m3=vapor,
        ground_dew_point_c=dew_point,
        dew_point_out_of_range=out_of_range,
        temp_dew_diff_c=diff,
        cloud_base_height_m=height,
        cloud_base_reliable=reliable,
        temperature_at_cloud_base_c=temp_at_base,
    )


# ==============================================================
# フェーン現象シミュレーター用の計算処理
# 「雲のできる高さ」で使った雲底計算(cloud_base_height など)をそのまま再利用し、
# それに「雲底から山頂までの上昇」「山頂から反対側のふもとまでの下降」を
# 付け加えることでフェーン現象を再現する。
#
# 中学校向けの簡略モデルの考え方:
#   1. 風上側のふもとから雲底高度までは、乾燥断熱減率(気温)・露点減率(露点)で上昇する
#      (雲のできる高さシミュレーターと全く同じ計算)。
#   2. 雲底高度が山頂より低ければ、そこから山頂までは雲(飽和した空気)として、
#      湿潤断熱減率で気温が下がりながら上昇する。山頂の空気は湿度100%とみなす。
#   3. 雲底高度が山頂より高い場合(=雲ができない)は、山頂まで乾燥断熱減率のまま上昇する。
#   4. 山を越えると雲(水滴)は雨として落ちてしまうので、山頂から風下側のふもとまでは、
#      山頂での水蒸気量を保ったまま、乾燥断熱減率で気温が上がりながら下降する。
#
# この結果、雲ができた場合は風下側のふもとの気温が風上側より高くなる
# (=フェーン現象)。雲ができなかった場合は、行きと帰りが同じ乾燥断熱減率になるため、
# 風下側の気温は風上側と同じに戻り、気温差は生まれない。
# ==============================================================

MOIST_LAPSE_RATE_C_PER_100M = 0.5  # 雲ができた後(飽和した空気)が上昇するときの気温低下 [℃/100m]


@dataclass
class FoehnState:
    """フェーン現象シミュレーターの計算結果をまとめて表すクラス"""
    # 風上側(左)のふもとの状態
    ground_temperature_c: float
    ground_relative_humidity_percent: float
    ground_saturation_g_m3: float
    ground_vapor_g_m3: float
    ground_dew_point_c: float
    dew_point_out_of_range: str  # "low" / "high" / "" (風上側の露点がCSV範囲外かどうか)

    mountain_height_m: float

    # 山頂・雲に関する状態
    cloud_base_height_m: float  # 雲ができ始める高さの計算値 [m](雲ができない場合は参考値)
    cloud_base_reliable: bool   # 雲底の計算値そのものが信頼できるか(範囲外なら False)
    cloud_formed: bool          # この山の高さで実際に雲ができるか

    peak_temperature_c: float   # 山頂の気温 [℃]
    peak_vapor_g_m3: float      # 山頂の水蒸気量 [g/m3](雲ができた場合は飽和水蒸気量と一致)

    # 風下側(右)のふもとの状態
    leeward_temperature_c: float
    leeward_saturation_g_m3: float
    leeward_vapor_g_m3: float
    leeward_relative_humidity_percent: float

    temperature_rise_c: float  # 風下側の気温 - 風上側の気温(フェーン現象による昇温)[℃]


def compute_foehn_state(
    ground_temperature_c: float,
    ground_relative_humidity_percent: float,
    mountain_height_m: float,
    df: pd.DataFrame,
) -> FoehnState:
    """
    風上側(左)のふもとの気温・湿度と山の高さから、フェーン現象の計算結果をまとめて求める。

    地上の空気が乾燥しすぎていて露点がCSVデータの範囲外になる場合
    (cloud_base_reliable = False)は、雲底高度そのものは求められないが、
    実際にはさらに雲ができにくいはずなので、この山の高さでは
    「雲はできない」ものとして扱う(cloud_formed = False)。
    """
    sat = saturation_at(ground_temperature_c, df)
    vapor = water_amount_from_relative_humidity(
        ground_temperature_c, ground_relative_humidity_percent, df
    )
    dew_point, out_of_range = dew_point_from_water_amount(vapor, df)
    cloud_base_reliable = (out_of_range == "")

    if cloud_base_reliable:
        cloud_base = cloud_base_height(ground_temperature_c, dew_point)
    else:
        # 範囲外(非常に乾燥している)ときは、山頂より確実に高いものとして扱い、
        # 「雲ができない」判定にそろえる(値自体は参考値であり画面には表示しない)。
        cloud_base = mountain_height_m + 1.0

    cloud_formed = cloud_base_reliable and cloud_base <= mountain_height_m

    if cloud_formed:
        # 風上側のふもと → 雲底: 乾燥断熱減率で上昇
        temp_at_cloud_base = temperature_at_altitude(ground_temperature_c, cloud_base)
        # 雲底 → 山頂: 湿潤断熱減率で上昇(空気は飽和したまま)
        remaining_height = mountain_height_m - cloud_base
        peak_temperature_c = (
            temp_at_cloud_base - MOIST_LAPSE_RATE_C_PER_100M * remaining_height / 100.0
        )
        # 山頂の空気は飽和しているとみなすので、水蒸気量はその気温での飽和水蒸気量に等しい
        peak_vapor_g_m3 = saturation_at(peak_temperature_c, df)
    else:
        # 雲ができないので、山頂まで乾燥断熱減率のまま上昇。水蒸気量は変化しない。
        peak_temperature_c = temperature_at_altitude(ground_temperature_c, mountain_height_m)
        peak_vapor_g_m3 = vapor

    # 山頂 → 風下側のふもと: 雲(水滴)は雨として落ちているので、
    # 山頂での水蒸気量を保ったまま、乾燥断熱減率で気温が上がりながら下降する。
    leeward_temperature_c = peak_temperature_c + DRY_LAPSE_RATE_C_PER_100M * mountain_height_m / 100.0
    leeward_saturation_g_m3 = saturation_at(leeward_temperature_c, df)
    leeward_vapor_g_m3 = min(peak_vapor_g_m3, leeward_saturation_g_m3)

    if leeward_saturation_g_m3 > 0:
        leeward_relative_humidity_percent = min(
            100.0, leeward_vapor_g_m3 / leeward_saturation_g_m3 * 100.0
        )
    else:
        leeward_relative_humidity_percent = 0.0

    temperature_rise_c = leeward_temperature_c - ground_temperature_c

    return FoehnState(
        ground_temperature_c=ground_temperature_c,
        ground_relative_humidity_percent=ground_relative_humidity_percent,
        ground_saturation_g_m3=sat,
        ground_vapor_g_m3=vapor,
        ground_dew_point_c=dew_point,
        dew_point_out_of_range=out_of_range,
        mountain_height_m=mountain_height_m,
        cloud_base_height_m=cloud_base,
        cloud_base_reliable=cloud_base_reliable,
        cloud_formed=cloud_formed,
        peak_temperature_c=peak_temperature_c,
        peak_vapor_g_m3=peak_vapor_g_m3,
        leeward_temperature_c=leeward_temperature_c,
        leeward_saturation_g_m3=leeward_saturation_g_m3,
        leeward_vapor_g_m3=leeward_vapor_g_m3,
        leeward_relative_humidity_percent=leeward_relative_humidity_percent,
        temperature_rise_c=temperature_rise_c,
    )


# ==============================================================
# 低気圧・高気圧のまわりの風シミュレーター用の計算処理
#
# 中学校向けの簡略モデルの考え方:
#   ・気圧配置は、低気圧・高気圧のそれぞれの中心を中心とした
#     なだらかな気圧の山・谷(ガウス分布)を重ね合わせて表現する。
#   ・風は「気圧が下がる方向」(気圧配置の最も急な下り坂の向き、
#     等圧線にほぼ直角な向き)に吹こうとするが、地球の自転の影響で
#     まっすぐには吹かず、その向きから時計回りに一定の角度だけそれる
#     (北半球の場合。これにより、低気圧のまわりは反時計回りに吹き込み、
#     高気圧のまわりは時計回りに吹き出す、という結果になる)。
#   ・風の強さは、その地点での気圧の傾き(等圧線の混み具合)に比例する
#     ものとする。
# ==============================================================

CORIOLIS_DEFLECTION_DEG = 30.0  # 教材用の簡略値:等圧線に直角な向きからのずれ角[度]


@dataclass
class PressureCenter:
    """低気圧・高気圧ひとつぶんの気圧配置を表すクラス"""
    x: float             # 中心のx座標
    y: float              # 中心のy座標
    kind: str             # "low"(低気圧) または "high"(高気圧)
    strength_hpa: float   # 周囲との気圧差[hPa](大きいほど等圧線が混み合う)
    radius: float = 0.5   # 気圧配置の広がりのスケール


def pressure_deviation(x: float, y: float, centers) -> float:
    """
    指定した地点における、周囲(基準気圧)からの気圧の偏差を求める。
    複数の低気圧・高気圧がある場合は、それぞれの寄与を単純に足し合わせる。
    """
    total = 0.0
    for c in centers:
        sign = -1.0 if c.kind == "low" else 1.0
        dx, dy = x - c.x, y - c.y
        r2 = dx * dx + dy * dy
        total += sign * c.strength_hpa * math.exp(-r2 / (2.0 * c.radius ** 2))
    return total


def pressure_gradient(x: float, y: float, centers):
    """
    指定した地点における気圧の勾配(x方向・y方向の傾き)を、解析的に求める。
    pressure_deviation をxとyでそれぞれ偏微分した式に対応する。
    """
    gx = gy = 0.0
    for c in centers:
        sign = -1.0 if c.kind == "low" else 1.0
        dx, dy = x - c.x, y - c.y
        r2 = dx * dx + dy * dy
        val = sign * c.strength_hpa * math.exp(-r2 / (2.0 * c.radius ** 2))
        gx += val * (-dx / c.radius ** 2)
        gy += val * (-dy / c.radius ** 2)
    return gx, gy


def wind_vector_at(x: float, y: float, centers, deflection_deg: float = CORIOLIS_DEFLECTION_DEG):
    """
    指定した地点における風向(単位ベクトル)と、風の強さの目安を求める。

    戻り値は (風向のx成分, 風向のy成分, 風の強さの目安) のタプル。
    風の強さの目安は気圧勾配の大きさそのもの(相対的な比較にのみ使う値)。
    気圧勾配がほぼ0(無風とみなせる点)の場合は (0.0, 0.0, 0.0) を返す。
    """
    gx, gy = pressure_gradient(x, y, centers)
    grad_mag = math.hypot(gx, gy)
    if grad_mag < 1e-9:
        return 0.0, 0.0, 0.0

    # 気圧が下がる方向(高圧側から低圧側へ向かう向き)の単位ベクトル
    dx_dir, dy_dir = -gx / grad_mag, -gy / grad_mag

    # そこから時計回りに deflection_deg だけ回転させる
    # (北半球でのコリオリの力による偏向を、模式的に一定角度のずれとして表現)
    theta = math.radians(deflection_deg)
    wx = dx_dir * math.cos(theta) + dy_dir * math.sin(theta)
    wy = -dx_dir * math.sin(theta) + dy_dir * math.cos(theta)

    return wx, wy, grad_mag
