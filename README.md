# 飽和水蒸気量・湿度・露点 学習アプリ(試作版)

中学2年理科向けに、気温・飽和水蒸気量・湿度・露点の関係を
スライダーとグラフで直感的に理解できるようにしたWebアプリです。

## ファイル構成

```
humidity_app/
├── app.py                     … Streamlit画面(UI)
├── science_utils.py           … 計算ロジック(UIから独立、他教材でも再利用可能)
├── requirements.txt           … 必要なPythonパッケージ
└── data/
    └── saturation_vapor.csv   … 飽和水蒸気量データ(仮データ、差し替え可能)
```

## Windowsでの起動方法

1. Python(3.9以上を推奨)をインストールしておく
2. コマンドプロンプトまたはPowerShellで、このフォルダ(humidity_app)に移動する

   ```
   cd 保存した場所\humidity_app
   ```

3. 必要なパッケージをインストールする(初回のみ)

   ```
   pip install -r requirements.txt
   ```

4. アプリを起動する

   ```
   streamlit run app.py
   ```

5. 自動的にブラウザが開き、`http://localhost:8501` でアプリが表示されます。
   開かない場合は、表示されたURLを手動でブラウザに入力してください。

6. 終了するときは、コマンドプロンプトの画面で `Ctrl + C` を押します。

## CSVデータの差し替えについて

`data/saturation_vapor.csv` は、現時点では計算式から作った仮の値です。
教科書に準拠した値に差し替える場合は、同じ列名
(`temperature_c`, `saturation_g_m3`)のまま、値だけを書き換えてください。
コード側の修正は不要です。

## 今後の拡張について

`science_utils.py` は画面(Streamlit)から独立しているため、
フェーン現象や放射冷却など、他の教材でも
`load_saturation_table` / `saturation_at` / `dew_point_from_water_amount`
などの関数をそのまま再利用できます。
