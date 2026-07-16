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
    dew_point_c: float            # 露点 [℃]


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


def dew_point_from_water_amount(water_g_m3: float, df: pd.DataFrame) -> float:
    """
    「空気中の水蒸気量」から露点(気温を下げて湿度100%になる気温)を求める。

    飽和水蒸気量は気温に対して単調に増加するテーブルであることを利用し、
    (saturation_g_m3 -> temperature_c) の対応を逆に補間して露点を求める。
    水の量が表の最大飽和水蒸気量を超える場合は、表の最高気温を返す。
    水の量が表の最小飽和水蒸気量を下回る場合は、表の最低気温を返す。
    """
    sat_min = float(df["saturation_g_m3"].iloc[0])
    sat_max = float(df["saturation_g_m3"].iloc[-1])
    w = min(max(water_g_m3, sat_min), sat_max)
    # saturation_g_m3 は temperature_c に対して単調増加である前提
    return float(np.interp(w, df["saturation_g_m3"], df["temperature_c"]))


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

    dew_point = dew_point_from_water_amount(initial_water_g_m3, df)

    return MoistureState(
        temperature_c=temperature_c,
        initial_water_g_m3=initial_water_g_m3,
        saturation_g_m3=sat,
        vapor_g_m3=vapor,
        condensed_g_m3=condensed,
        humidity_percent=humidity,
        dew_point_c=dew_point,
    )
