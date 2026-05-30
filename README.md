# Rhino Weight & Material Estimator (`Mass`)

> **Overview (EN):** A RhinoPython tool for **Rhino for Mac** that grew from a simple weight calculator into a lightweight **weight / material-cost / fabrication-estimate helper** for sculpture, metalwork, furniture/fixtures, and teaching. Select closed solids, polysurfaces, meshes, extrusions, block instances, or SubD (or type a volume) and it computes **mass (kg)** using RhinoCommon's `VolumeMassProperties.Compute()` — matching Rhino's native `Volume` command — then estimates **material cost**, prints a **per-object table**, and can **export CSV**. It remembers your **last-used material**, supports **per-layer material assignments**, and can store material metadata in each object's **Rhino UserText**. No external libraries; settings live in a local JSON file. **Results are estimates — not for structural or safety decisions.**

選択した **閉じたソリッド／ポリサーフェス／メッシュ／Extrusion／Block Instance／SubD** の体積、または **直接入力した体積** から **重量 (kg)** と **概算材料費** を算出する Rhino for Mac 用 RhinoPython ツールです。体積は Rhino 標準 `Volume` コマンドと一致させるため RhinoCommon の `VolumeMassProperties.Compute()` を直接使用します。UI は日本語化されています。

---

## 変更履歴 / What's new (v2–v7)

| 版 | 機能 | 概要 |
|---|---|---|
| v1 | 重量計算 | 体積 → 重量。Block 再帰展開・disjoint solid 分割・モデル単位対応（コア機能） |
| v2 | 材料の記憶 | 前回素材をローカル設定に保存し、次回の既定候補に |
| v3 | 材料費の概算 | 素材に単価 `price_per_kg` を持たせ、概算材料費を出力 |
| v4 | オブジェクト別一覧 | 選択オブジェクトごとに id / 名前 / レイヤー / 重量 / 費用を表形式表示 |
| v5 | CSV 出力 | 計算結果を CSV（UTF-8 BOM）に保存 |
| v6 | レイヤー別材料 | レイヤー名ごとに素材を割り当て、保存・再利用 |
| v7 | UserText メタデータ | 各オブジェクトの UserText (`rwc_*`) に素材情報を読み書き |

> v1 のコア機能（体積→重量）は全版で維持しています。外部ライブラリ非依存・`.format()` 使用で、RhinoPython（IronPython 2.7 / CPython 3）双方を想定しています。

---

## Installation / インストール

1. 本リポジトリの `weight_calc.py` を任意の場所に保存する（例: `~/Documents/RhinoScripts/`）。
2. Rhino → **環境設定 (Preferences)** → **エイリアス (Aliases)** に次の 1 行を登録する（パスは保存先に合わせて書き換える）。

   | 名前 | コマンドマクロ |
   |---|---|
   | `Mass` | `! _-RunPythonScript "/Users/<you>/Documents/RhinoScripts/weight_calc.py"` |

   - `!` は実行中コマンドをキャンセルする記号、`_-RunPythonScript` の `_` は英語コマンド指定、`-` はダイアログ抑制。パスは必ずダブルクォートで囲む。

> ⚠️ **Alias 名に `Weight` は使わないでください。** Rhino 標準コマンド `Weight`（NURBS 制御点編集）と衝突します。本ツールは **`Mass`** を推奨名にしています（別名なら `Density` / `WeightCalc` 等、既存コマンドと被らない名前を）。

---

## Usage / 使い方

### 選択オブジェクトから計算（基本）

1. **閉じたソリッド／閉じたメッシュ／Block** を 1 つ以上選択（事前選択可）。
2. コマンド欄に `Mass` と入力して Enter。
3. 素材を選ぶ（前回素材・レイヤー材料・UserText がある場合は自動適用、後述）。
4. コマンドラインに**オブジェクト別一覧**と**合計**、`MessageBox` に合計が表示される。任意で CSV 保存・UserText 書き込みを尋ねられる。

### 体積を直接入力（モデル無しで試算）

1. **何も選択していない状態**で `Mass` を実行。
2. 「**体積を直接入力 (m³)**」を選択し、体積を m³ で入力（例: 1m 立方=`1.0`、100mm 立方=`0.001`）。
3. 素材を選んで結果を確認（直接入力モードはモデル単位の影響を受けません）。

### 出力例（オブジェクト別一覧 + 合計）

```
----- オブジェクト別一覧 (per-object) -----
#   id        name             layer            material     weight(kg)   cost
1   abcd1234  枠材A             steel_frame      Steel        580.13       87,019 JPY
2   ef567890  (unnamed)        wood             Cedar        4.56         -
3   99999999  open_srf         misc             Steel        -            -  [skip: 体積取得不可]
----- 重量計算 合計 (totals) -----
入力オブジェクト数: 3
体積計算ジオメトリ数: 33
使用素材: Steel, Cedar
Weight (合計): 584.69 kg
概算材料費 (合計): 87,019 JPY
失敗: 1
```

`体積計算ジオメトリ数` は Block 展開後 / Brep 分割後に体積計算が成功したピース数で、Rhino 標準 `Volume` の「N 個のソリッド」と一致するよう設計しています。各ピースの内訳はコマンド履歴（F2）の `----- 計算ログ -----` に `id / kind / raw / [block-child] / piece i/N` 形式で出力されます。

---

## Current Status / 現在の状態

**安定版**。Rhino for Mac の `RunPythonScript` 環境で動作確認済み。v1 のコア（体積→重量）に v2–v7 の機能を非破壊で積み上げた構成です。

---

## Materials / 素材と密度・単価

素材は `weight_calc.py` 冒頭の `MATERIALS`（`jp` / `en` / `density` / `price_per_kg`）で定義します。追加・調整は同リストを編集してください。

| 表示名 | 英名 | 密度 [kg/m³] | 既定単価 `price_per_kg` |
|---|---|---:|---:|
| 鋼 | Steel | 7850 | 150 |
| アルミ | Aluminum | 2700 | 700 |
| ステンレス | SUS | 7930 | 1000 |
| コンクリート | Concrete | 2400 | 30 |
| 真鍮 | Brass | 8500 | 1800 |
| 銅 | Copper | 8960 | 2000 |
| 杉 | Cedar | 380 | 未設定 |
| 桧 | Hinoki | 410 | 未設定 |
| 松 | Pine | 510 | 未設定 |
| 樫 | Oak | 750 | 未設定 |
| 集成材 | Glulam | 450 | 未設定 |
| 合板 | Plywood | 600 | 未設定 |
| MDF | MDF | 750 | 未設定 |

> **木材の密度は樹種・含水率で ±20% 程度変動**します。表は気乾状態の代表値です。木材の単価は重量単価での流通が一般的でないため既定で「未設定」（材料費は算出しません）。

---

## Cost Estimation / 材料費の概算

`概算材料費 = 重量(kg) × price_per_kg` を計算し、`material` / `density` / `volume` / `weight` / `price_per_kg` / `estimated_material_cost` を出力します。

- 単価未設定（`price_per_kg = None`）の素材でも**重量計算は動作**し、材料費は `-` になります。
- 通貨は `weight_calc.py` 冒頭の `CURRENCY` 定数（既定 `JPY`）で一括変更できます。
- ⚠️ **`price_per_kg` は編集前提のプレースホルダ概算値**です。市況・調達先で大きく変動するため、正確な見積りには実調達価格に置き換えてください。本ツールの費用は**概算**であり確定見積りではありません。

---

## CSV Export / CSV 出力

選択モードの結果を CSV に保存できます（Excel / Google Sheets / 見積書・制作メモ用）。表示後に保存可否と保存先を尋ねます。

- **列**: `object_id, object_name, layer, material, density, volume, weight_kg, price_per_kg, estimated_cost`（`volume` は m³）。
- **保存先**: ダイアログで選択。キャンセル / 不可時は**デスクトップ**（無ければホーム）へフォールバック。ファイル名 `rhino_weight_YYYYMMDD_HHMMSS.csv`。
- **文字コード**: UTF-8（BOM 付き）。Excel で日本語が文字化けしません。
- CSV 保存に失敗しても**計算結果の表示は止まりません**。

```csv
object_id,object_name,layer,material,density,volume,weight_kg,price_per_kg,estimated_cost
abcd1234-...,枠材A,steel_frame,Steel,7850.0,0.0739,580.1300,150.00,87019.50
ef567890-...,(unnamed),wood,Cedar,380.0,0.012,4.5600,,
```

---

## Layer Material Settings / レイヤー別材料設定

大きなモデルで毎回素材を選ばずに済むよう、**Rhino のレイヤー名ごとに素材を割り当て**られます。割り当てはローカル設定に保存され、次回も再利用されます。

- レイヤーに素材が設定済みなら**優先**（プロンプトなし）。未設定なら前回素材を既定にしたプロンプトで 1 回だけ選択し、当該レイヤーへ保存します。
- 合計はレイヤー別に異なる素材を考慮して**行ごとに集計**します。
- 設定ファイル例:

```json
{
  "last_material": "Steel",
  "layer_materials": {
    "steel_frame": "Steel",
    "aluminum_cover": "Aluminum",
    "stainless_parts": "SUS"
  }
}
```

---

## Rhino UserText Metadata / UserText メタデータ

材料情報を**各オブジェクト自身**（Rhino の UserText: キー・バリュー属性）に保存できます。ファイルを共有・再オープンしても材料が保持されます。

- 書き込むキー: `rwc_material` / `rwc_density` / `rwc_price_per_kg`（**`rwc_` プレフィックスのみ。他の UserText には一切触れません**）。
- **素材の優先順位**: ① オブジェクトの UserText → ② レイヤー材料設定 → ③ 前回素材 → ④ ユーザー選択。
- 既知素材（`MATERIALS`）を `rwc_material` に持てば、未指定の `rwc_density` / `rwc_price_per_kg` は素材表の値で補完。独自素材名でも `rwc_density` があれば計算可能。
- 計算後、**確認ダイアログで Yes のときのみ**選択オブジェクトへ書き込みます。
- 削除: 補助関数 `clear_rwc_usertext(object_id)` は対象オブジェクトの `rwc_` キーのみ削除します（他属性は残す）。

---

## Rhino 標準 `Volume` コマンドとの照合

本ツールは **Rhino 標準 `Volume` と同じ体積をベース**に重量を算出します。検証手順:

1. 対象を選択し `Volume` を実行 → **累積体積**（モデル単位）と**ソリッド数**を控える。
2. **同じ選択**で `Mass` を実行し、`Raw volume`＝累積体積、`体積計算ジオメトリ数`＝ソリッド数、`Volume`＝m³ 換算、`Weight`＝体積×密度 を確認。

数値例（mm モデル・鋼 7850 kg/m³）: 累積体積 `7.390198e+07 mm³` → `Volume 0.07390198 m3` → `Weight 約 580.13 kg`、ソリッド数 `32`＝`体積計算ジオメトリ数 32`。

一致しない場合は、Mesh の混在（近似）、`SplitDisjointPieces` 失敗、モデル単位の不一致、Block 内の開いた Brep / 空 InstanceDefinition を確認してください。

---

## Limitations / 制限・注意点

- **閉じていないサーフェス／開いたメッシュ**は体積が取得できず（`None`）、スキップ扱いになります（処理は止めません）。
- **負値**（法線反転）は `abs()` で正値として扱います（Rhino 標準 `Volume` と同様）。
- **中実モデルのパイプ類**は空洞が考慮されず過大になります。中空ソリッドにしてください。**塗装・溶接・公差**は非考慮（実物比 1〜3% 程度の誤差を想定）。**Mesh** は頂点密度が低いと誤差増。
- 対応モデル単位は **mm / cm / m** のみ（インチ等は select モードで警告停止、直接入力は影響なし）。
- **木材は ±20% 程度の密度ばらつき**。結果は**概算**として扱ってください。
- 素材名・UI は日本語表示（`rs.ListBox` を使用）。表示崩れ時は `MATERIALS` の日本語名を英名に書き換えて回避できます。
- per-object 一覧 / CSV / UserText 書き込みは**選択モード**の機能です（直接入力モードは単一結果のみ）。

---

## Reset Settings / 設定のリセット

- **ローカル設定**（前回素材・レイヤー材料）: `~/.rhino_weight_calc_settings.json` を削除すると初期状態に戻ります。ファイルが無い／壊れている／保存名が現在の素材リストに無い場合は、エラーで止めず通常選択にフォールバックします。
- **オブジェクトの材料メタデータ**: `clear_rwc_usertext(object_id)` で `rwc_` キーのみ削除（他属性は保持）。

---

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| 「対応していないモデル単位です」 | `Units` で mm / cm / m に変更、または直接入力モードを使う |
| `Mass` で別コマンドが起動 | Alias が `Mass` で登録されているか確認（`Weight` は標準コマンド優先） |
| `MessageBox` が出ない | コマンド履歴（F2）に同内容が出ているか確認 |
| Mesh が「失敗」になる | `MeshRepair` / `FillMeshHoles` で閉じているか確認 |
| Block の重量が 0 | ログで `[block:<name> (0個)]` を確認（空定義なら実ジオメトリを追加） |
| 重量がパイプ類で過大 | 中空ソリッドになっているか `Volume` で確認 |
| 重量が 1000 倍 / 1/1000 倍 | モデル単位と実寸の整合を確認 |
| 材料費が出ない | その素材は `price_per_kg` 未設定（`MATERIALS` を編集） |

---

## 利用文脈 / Use cases

- **公共彫刻・大型立体**: 据付前にブロンズ・ステンレス・鋼材の重量を概算し、台座の耐荷重・吊り上げ・運搬・輸送コストの検討に。Block の再帰展開で繰り返し要素も一括見積り。
- **金属制作・什器制作 (fabrication)**: 鋼・アルミ・ステンレス等の密度・単価プリセットで、材料重量・歩留まり・一次見積りに。レイヤー別材料で部材ごとの素材を一括管理。
- **教育現場**: 体積×密度＝質量、モデル単位の扱い、`Volume` との照合を学ぶ教材に。素材ごとの密度差（金属と木材で 1 桁以上）を体感する演習向き。

---

## License & Disclaimer / ライセンス・免責

MIT License — [LICENSE](LICENSE) を参照。

本ツールは設計・検討用の**概算**重量・材料費を算出するものです。木材密度のばらつき、塗装・溶接・公差・中空モデリング差、単価の市況変動により実値と乖離し得ます。**構造設計・安全性判断・確定見積りには使用しないでください。**正式値が必要な場合は実測値・規格値・実調達価格に基づき専門家が検証してください。Rhinoceros / RhinoCommon は Robert McNeel & Associates の製品であり、本プロジェクトとは無関係の独立したスクリプトです。

---

## 開発コンテキスト / Development context

個人による Rhino 作業効率化（彫刻・金属/什器制作・教育）のための RhinoPython ツールです。商用提供を前提としません。
