# 重量計算スクリプト (Mass) for Rhino — v4

> **Overview (EN):** A RhinoPython script for Rhino for Mac that computes the **mass/weight (kg)** of selected closed solids, polysurfaces, meshes, extrusions, block instances, and SubD objects — or from a directly entered volume. It uses RhinoCommon's `VolumeMassProperties.Compute()` so its volume matches Rhino's native `Volume` command, recursively expands block instances (applying `InstanceXform`), splits disjoint Brep shells for per-piece counting, and ships with 13+ preset material densities (steel, aluminum, stainless, brass, copper, concrete, and several woods). Install it, bind it to a Rhino alias (`Mass`), select geometry, pick a material, and read the weight. Useful for makers, fabricators, and educators who need a fast on-model weight estimate. **v2 remembers your last-used material** (saved to `~/.rhino_weight_calc_settings.json`) and pre-selects it next time, so repeated runs on the same material are one click faster. **Status: stable (v4 engine + v2 material memory). Results are estimates — not for structural/safety decisions.**

選択した **閉じたソリッド／ポリサーフェス／メッシュ／Extrusion／Block Instance／SubD** の体積、または **直接入力した体積** から **重量 (kg)** を算出する Rhino 用 Python スクリプトです。
体積取得は Rhino 標準 `Volume` コマンドと一致させる方針に揃えるため、`rhinoscriptsyntax.SurfaceVolume()` ではなく **RhinoCommon の `Rhino.Geometry.VolumeMassProperties.Compute()`** を直接使用しています。Block Instance は `InstanceXform` を適用したうえで `InstanceDefinition` 内のジオメトリを再帰的に展開し、Brep は `SplitDisjointPieces()` で disjoint な solid に分割して個別計数します。

Rhino for Mac の `RunPythonScript` で動作することを想定しています。UI は日本語化されています。

---

## 0. v4 の変更点

| 機能 | v3 | v4 |
|---|---|---|
| Block Instance | フィルタで除外 (`ExplodeBlock` 必須) | **`InstanceXform` 適用のうえ定義内を再帰展開して合算** |
| Brep の複数 solid shell | 単一 Brep として 1 件カウント | **`SplitDisjointPieces` で分割し個別計数** |
| 計数表示 | 「選択 N 個」のみ | **「入力オブジェクト数」と「体積計算ジオメトリ数」を分離** |
| 体積表示 | m³ のみ | **モデル単位の Raw volume と m³ を併記** |
| ログ | 表示なし | **各ピースの id / kind / raw / success / block-child フラグを出力** |
| 対応ジオメトリ | Surface / Polysurface / Mesh / Extrusion / SubD | **+ InstanceReferenceGeometry (Block)** |

---

## 0.5. v2 の変更点（材料の記憶 / Remembered material）

連続して同じ素材（steel / stainless / aluminum など）を扱う制作現場向けに、**前回選択した素材を記憶**して 2 回目以降の操作を短縮します。

- **記憶する内容**: 確定した素材の英名（例 `Steel`）を 1 件だけ保存します。
- **次回の挙動**: 素材選択ダイアログで前回素材が**既定候補として事前選択**され、プロンプトに `素材を選択してください (前回: Steel)` のように併記されます。そのまま OK（Enter / デフォルト選択）すれば前回素材を再利用、別の素材を選べばその素材で上書き保存します。
- **設定ファイルの場所**: `~/.rhino_weight_calc_settings.json`
  ```json
  {
    "last_material": "Steel"
  }
  ```
- **設定のリセット方法**: `~/.rhino_weight_calc_settings.json` を削除すると初期状態（毎回先頭素材が既定）に戻ります。
- **フォールバック（壊れない設計）**: 設定ファイルが無い／壊れている／保存名が現在の素材リストに無い場合は、エラーで止めずに**従来どおりの素材選択**になります。
- **依存**: Python 標準ライブラリ `json` / `os` のみ。外部ライブラリ不要。体積取得・密度データ・重量計算ロジック（v4）は不変更で、v1 互換です。

---

## 0.6. v3 の変更点（材料費の概算 / Cost estimation）

重量に加えて**概算材料費**を出力します。各素材に単価 `price_per_kg`（通貨は `CURRENCY`、既定 `JPY`）を持たせ、`概算材料費 = 重量(kg) × price_per_kg` を計算します。

- 出力に `material` / `density` / `volume` / `weight` / `price_per_kg` / `estimated_material_cost` を含めます。
- **単価未設定（`price_per_kg = None`）の素材でも重量計算は動作**し、材料費は `-`（未算出）になります。木材は重量単価での流通が一般的でないため既定で未設定です。
- 通貨は `weight_calc.py` 冒頭の `CURRENCY` 定数で一括変更できます（将来の多通貨化を想定）。
- ⚠️ **`price_per_kg` は編集前提のプレースホルダ概算値**です。市況・調達先で大きく変動するため、正確な見積りには各自の実調達価格に置き換えてください。本ツールの材料費はあくまで**概算**であり、確定見積りではありません。

---

## 1. ファイル

| ファイル | 用途 |
|---|---|
| `weight_calc.py` | 本体スクリプト |
| `README.md` | この説明書 |

保存先（想定）:

```
/Users/<you>/Documents/RhinoScripts/weight_calc.py
/Users/<you>/Documents/RhinoScripts/README.md
```

---

## 2. 使い方

### 2.1 選択オブジェクトから計算する場合（基本）

1. Rhino で **閉じたソリッド／閉じたメッシュ／Block** を 1 つ以上選択する（事前選択可）。
2. コマンド欄に `Mass` と入力して Enter（Alias 登録後）。
3. 素材選択ダイアログから素材を選ぶ。
4. 体積（Raw / m³）と重量（kg）がコマンド履歴と MessageBox に表示される。

> ⚠️ **Alias 名に `Weight` は使わないでください。**
> Rhino には標準コマンド `Weight`（NURBS 制御点のウェイト編集）が既に存在し、Alias 名を `Weight` にすると標準コマンドが起動してしまいます。本スクリプトでは Alias 名を **`Mass`** に統一しています。

### 2.2 体積を直接入力する場合（モデル無しで試算）

1. オブジェクトを **何も選択していない状態** でコマンド欄に `Mass` と入力。
2. 入力方法ダイアログで「**体積を直接入力 (m³)**」を選択。
3. 体積を **m³** で入力（例：1 リットル = `0.001`、100mm 立方 = `0.001`、1m 立方 = `1.0`）。
4. 素材を選んで結果を確認。

> 直接入力時はモデル単位の影響を受けません。常に **m³** で入力してください。

### 2.3 出力例

```
----- 重量計算 (Mass) -----
入力オブジェクト数: 2
体積計算ジオメトリ数: 32
素材: 鋼 (Steel)
密度: 7850 kg/m3
モデル単位: mm
Raw volume: 73901980 mm3
Volume: 0.07390198 m3
Weight: 580.13 kg
失敗: 0
```

`体積計算ジオメトリ数` は「Block 展開後 / Brep 分割後に VolumeMassProperties.Compute() が成功したピース数」です。Rhino 標準 `Volume` コマンドが「N 個のソリッド」と表示する N と一致するように設計されています。

### 2.4 計算ログ

コマンド履歴（F2）には、各ピースの内訳が以下の形式で出力されます。

```
----- 計算ログ -----
  1 [OK  ] id=a1b2c3d4 kind=Brep raw=2310936.875 [block-child] [block:Bracket (16個)] -> piece 1/4
  2 [OK  ] id=a1b2c3d4 kind=Brep raw=950123.250  [block-child] [block:Bracket (16個)] -> piece 2/4
  ...
 32 [OK  ] id=...      kind=Brep raw=...
```

- `id` … RhinoObject の GUID 先頭 8 文字
- `kind` … 元ジオメトリの型名（`Brep` / `Mesh` / `Extrusion` / `SubD` / `InstanceReferenceGeometry` など）
- `raw` … モデル単位での体積（成功時のみ）
- `[block-child]` … ブロック定義から展開されたピース
- `piece i/N` … 単一 Brep を `SplitDisjointPieces` で分割した結果の i 番目

### 2.5 素材と密度

#### 金属・無機材料

| 表示名 | 英名 | 密度 [kg/m³] |
|---|---|---:|
| 鋼           | Steel    | 7850 |
| アルミ       | Aluminum | 2700 |
| ステンレス   | SUS      | 7930 |
| コンクリート | Concrete | 2400 |
| 真鍮         | Brass    | 8500 |
| 銅           | Copper   | 8960 |

#### 木材（気乾密度の代表値）

| 表示名 | 英名 | 密度 [kg/m³] |
|---|---|---:|
| 杉       | Cedar    | 380 |
| 桧       | Hinoki   | 410 |
| 松       | Pine     | 510 |
| 樫       | Oak      | 750 |
| 集成材   | Glulam   | 450 |
| 合板     | Plywood  | 600 |
| MDF      | MDF      | 750 |

> **木材の密度は樹種・含水率で大きく変動します。** 表の値は気乾状態の一般的な代表値で、誤差 ±20% 程度を想定してください。設計値が必要な場合は使用する木材の実測値か JAS / 樹種別の規格値を確認してください。素材を追加・調整したい場合は `weight_calc.py` の `MATERIALS` リストを編集してください。

---

## 3. Alias 登録方法

Rhino → **環境設定 (Preferences)** → **エイリアス (Aliases)** を開き、以下の 1 行を登録します。

| 名前 | コマンドマクロ |
|---|---|
| `Mass` | `! _-RunPythonScript "/Users/<you>/Documents/RhinoScripts/weight_calc.py"` |

ポイント:

- 先頭の `!` は実行中コマンドをキャンセルしてから新しいコマンドを開始する記号。
- `_-RunPythonScript` の `_` は英語コマンド指定、`-` はダイアログを抑制してスクリプトモードで起動する記号。
- パスは必ずダブルクォートで囲む。

### Alias 名に関する注意（重要）

- **`Weight` は Rhino 標準コマンド**（NURBS 制御点のウェイト編集）と衝突するため Alias 名に使わないでください。
- 本スクリプトでは **`Mass`** を推奨名としています（Rhino 標準コマンドにありません）。
- 別名にしたい場合は `Density` / `WeightCalc` / `KgCalc` 等、既存コマンドと被らない名前を選んでください。

---

## 4. Rhino でのテスト方法

### 4.1 基本動作（Box ソリッド）

| ケース | モデル単位 | 形状 | 素材 | 期待値 |
|---|---|---|---|---:|
| A | mm | `Box` で 1000 × 1000 × 1000 | 鋼 (Steel) | **約 7850 kg** |
| B | mm | `Box` で 100 × 100 × 100   | 鋼 (Steel) | **約 7.85 kg** |
| C | m  | `Box` で 1.0 × 1.0 × 1.0   | 鋼 (Steel) | **約 7850 kg** |
| D | cm | `Box` で 100 × 100 × 100   | 鋼 (Steel) | **約 7850 kg** |
| E | mm | `Box` で 1000 × 1000 × 1000 | 杉 (Cedar) | **約 380 kg** |

手順例（ケース A）:

1. `Units` コマンドでモデル単位を **Millimeters** に設定。
2. `Box` コマンドで対角に `0,0,0` と `1000,1000,1000` を入力。
3. その立方体を選択した状態で `Mass` を実行。
4. 素材選択ダイアログで `鋼` を選択。
5. 出力に `Weight: 7850.00 kg` 付近が表示されればOK。

### 4.2 閉じた Mesh

1. ケース A と同じ Box を作成。
2. `Mesh` コマンドでメッシュ化（デフォルト設定で可）。元の Brep は削除。
3. Mesh を選択して `Mass` → `鋼`。
4. 同じく **約 7850 kg** が出ること（メッシュ近似のため小さな誤差あり）。

### 4.3 体積を直接入力

1. **何も選択していない状態** で `Mass` を実行。
2. 入力方法ダイアログで「**体積を直接入力 (m³)**」を選ぶ。
3. 体積に `1.0` を入力 → `鋼` で `Weight: 7850.00 kg`。
4. 体積に `0.001`（=1 リットル相当）を入力 → `鋼` で `Weight: 7.85 kg`。

### 4.4 Block Instance（v4 新機能）

1. 任意の閉じた Brep を作成し、`Block` コマンドで Block 化（名前: 例 `unit`）。
2. `Insert` で同じブロックを複数配置（任意の位置・回転・スケールで可）。
3. 配置した Block Instance を **そのまま** 選択（`ExplodeBlock` 不要）。
4. `Mass` を実行 → 配置数 × 単位体積分の重量が出ること。
5. コマンド履歴の計算ログに `[block-child]` 印付きでピースが列挙されることを確認。

### 4.5 Brep の複数 solid shell

1. 2 つの離れた閉じた Brep を `Join` で結合（Rhino 上は 1 オブジェクトの polysurface だが内部には 2 つの shell）。
2. `Mass` を実行。
3. 「入力オブジェクト数: 1 / 体積計算ジオメトリ数: 2」が表示され、両 shell の体積合計で重量が出ること。

### 4.6 複数選択 / 失敗カウント

1. 閉じた Box を 2 個、開いたサーフェスを 1 個まとめて選択。
2. `Mass` → 任意の素材。
3. 出力に `体積計算ジオメトリ数: 2 / 失敗: 1` のように分かれて表示されること。

### 4.7 異常系

- **モデル単位が inches / feet 等の未対応**かつ Select モード → 警告して停止。直接入力モードは利用可能。
- **対象を 1 つも選択せずキャンセル** → 静かに終了。
- **全てが体積取得不能** → 「有効な体積を取得できませんでした」と表示。
- **体積に 0 や負値を入力** → 警告して終了。

---

## 5. Rhino 標準 `Volume` コマンドとの照合（重要）

v4 の目的は **Rhino 標準 `Volume` コマンドと同じ体積をベースに重量を算出する** ことです。次の手順で一致を検証してください。

### 5.1 手順

1. 対象オブジェクト（Block / 多数 solid を含む Brep / 通常の Brep / Mesh）を選択する。
2. Rhino で `Volume` コマンドを実行し、コマンド履歴に出る次の値を控える。
   - **累積体積**（モデル単位、例: `7.390198e+07 立方ミリメートル`）
   - **ソリッド数**（例: `32 個のソリッド`）
3. **同じ選択** で `Mass` を実行する。
4. 計算ログと最終表示で以下を確認する。
   - `Raw volume` が `Volume` の累積体積と一致する（モデル単位）
   - `体積計算ジオメトリ数` が `Volume` のソリッド数と一致する
   - `Volume` の値が m³ 換算と一致する
   - `Weight` が `Volume × 密度` と一致する

### 5.2 数値例（mm モデル、鋼 Steel）

| 項目 | 期待値 |
|---|---|
| Rhino `Volume` の累積体積 | `7.390198e+07 mm³` |
| `Mass` の `Raw volume` | `73901980 mm3`（= `7.390198e+07 mm³`） |
| `Mass` の `Volume` | `0.07390198 m3` |
| `Mass` の `Weight`（鋼 7850 kg/m³） | **約 580.13 kg** |
| Rhino `Volume` のソリッド数 | `32` |
| `Mass` の `体積計算ジオメトリ数` | `32` |

### 5.3 一致しない場合のチェックリスト

| 症状 | 確認ポイント |
|---|---|
| `体積計算ジオメトリ数` が `Volume` のソリッド数より少ない | 計算ログを見て `FAIL` 行の `kind` / `note` を確認。Block 内に開いた Brep / Mesh が含まれていないか。InstanceDefinition の参照解決に失敗していないか。 |
| `Raw volume` が `Volume` の累積体積と桁違いに違う | モデル単位設定が `Volume` 実行時と `Mass` 実行時で同じか。スクリプトの `SUPPORTED_UNITS` に該当する単位か。 |
| 数 % ずれる | 対象に Mesh が含まれていないか（Mesh は近似ジオメトリ）。Brep の `SplitDisjointPieces` 失敗で 1 ピースとしてまとめ計算されていないか。 |
| Block 内の体積が出ない | ログに `[block:<name> (N個)]` が出ているか。`N=0` の場合はブロック定義が空（参照のみで実体無し）。 |

---

## 6. 注意点

### 6.1 体積取得まわり

- **閉じていないサーフェス／開いたメッシュ** では `VolumeMassProperties.Compute()` が `None` を返します。Rhino の `What` または `Volume` コマンドで閉じているか事前確認してください。
- **負値の扱い**: 法線方向が反転していると `Compute()` の Volume が負値になることがあります。本スクリプトは Rhino 標準 `Volume` コマンドと同様、`abs()` を取って正値として扱います。
- **Extrusion / SubD** は内部で Brep に変換してから計算します。
- **Block Instance** は `InstanceXform` を適用して定義内のジオメトリを再帰展開します。Scale を含む xform でも、Brep / Mesh の体積はスケール後に再計算されるため正しく合算されます。
- **Brep の複数 solid shell** は `SplitDisjointPieces` で分割します。失敗した場合（例: 完全に閉じていない Brep）は元の Brep をそのまま 1 ピースとして渡します。

### 6.2 モデリングと実重量

- **角パイプ／丸パイプを「外形だけの中実モデル」で作っている場合**、内部の空洞が考慮されず実重量より重く出ます。中空モデル（ブール差で内部をくり抜いたソリッド）にしてください。
- **塗装・溶接・公差**は考慮されません。実物比で 1〜3% の誤差は想定してください。
- **Mesh は頂点密度が低いと体積誤差が増えます。** 精密計算は Brep を推奨。
- **木材は密度のばらつきが大きい**（樹種・部位・含水率で ±20% 程度変動）ため、本ツールの結果は **概算** として扱ってください。

### 6.3 単位

- モデル単位は `rs.UnitSystem()` で判定し、長さ → m 換算は `rs.UnitScale(4)` で動的取得しています（固定係数より環境差に強い）。
- 対応単位は **mm (=2) / cm (=3) / m (=4)** のみ。インチ等は警告して停止します（直接入力モードは影響を受けません）。

### 6.4 日本語表示

- 素材名と UI メッセージは日本語表示です。`rs.ListBox` は OS 標準ダイアログのため日本語表示が安定します。
- 万一日本語が表示崩れする環境（古い Rhino for Mac 等）では、`weight_calc.py` の `MATERIALS` リストの日本語名を英名（タプル 3 番目の要素）に書き換えれば回避できます。

---

## 7. トラブルシューティング

| 症状 | 対処 |
|---|---|
| 「対応していないモデル単位です」と出る | `Units` で mm / cm / m のいずれかに変更、または直接入力モードを使う |
| `Mass` と入力すると別のコマンドが起動 | Alias が `Mass` で正しく登録されているか確認。`Weight` で登録すると標準コマンドが優先される |
| MessageBox が出ない | コマンド履歴（F2 で表示）に同じ内容が出ているか確認 |
| Mesh で `失敗` にカウントされる | `MeshRepair` / `FillMeshHoles` で閉じているか確認 |
| Block の重量が 0 になる | コマンド履歴のログで `[block:<name> (0個)]` になっていないか確認。InstanceDefinition が空の場合は実ジオメトリを追加する |
| 重量がパイプ類で過大 | `Volume` コマンドで体積を確認し、中空ソリッドになっているか確認 |
| 重量が想定の 1000 倍 / 1/1000 倍 | モデル単位設定と実寸が合っているか確認（例: mm モデルに m スケールでインポートしていないか） |
| `Volume` と `Mass` で値が一致しない | §5.3 のチェックリストを順に確認 |
| 木材の値が現実と合わない | 樹種・含水率で密度は大きく変わる。`MATERIALS` リストの密度値を実測値に置換 |

---

## 8. インストール (Installation)

1. 本リポジトリの `weight_calc.py` を任意の場所に保存する（例: `~/Documents/RhinoScripts/`）。
2. §3 の手順で Rhino に Alias `Mass` を登録する。Alias マクロ内のパスは保存先に合わせて書き換える。

## 9. 利用文脈 (Use cases)

実制作・教育の現場で「モデル段階の概算重量」を素早く得るために使えます。

- **公共彫刻・大型立体 (public sculpture)**: 据付前にブロンズ・ステンレス・鋼材の重量を概算し、台座の耐荷重・吊り上げ・運搬計画・輸送コストの検討材料にする。Block Instance の再帰展開により、繰り返し要素を持つ構成物でも一括で見積もれる。
- **金属制作・ファブリケーション (metal fabrication)**: 鋼・アルミ・ステンレス・真鍮・銅の密度プリセットで、溶接前の材料重量・歩留まり・見積りの一次概算に使う。中空形状は中実モデルとの差に注意（§6.2）。
- **教育現場 (education)**: 体積×密度＝質量の関係や、モデル単位の扱い、Rhino 標準 `Volume` との照合（§5）を学ぶ教材として。素材ごとの密度差（金属と木材で 1 桁以上違う）を体感させる演習に向く。

> いずれの用途でも本ツールの出力は**概算**です。木材は ±20% 程度ばらつき、塗装・溶接・公差・中空モデリング差は反映されません。構造・安全に関わる判断には実測値・規格値と専門家の検証を用いてください（§11 参照）。

## 10. 状態 (Status)

安定版 (v4)。Rhino for Mac の `RunPythonScript` 環境で動作確認済み。

## 11. ライセンス / 免責 (License & Disclaimer)

MIT License — [LICENSE](LICENSE) を参照。

本ツールは設計・検討用の**概算**重量を算出するものです。木材密度のばらつき（±20% 程度）、塗装・溶接・公差・中空形状のモデリング差により実重量と乖離し得ます（§6 参照）。**構造設計・安全性判断には使用しないでください。**正式な設計値が必要な場合は実測値・規格値に基づき専門家が検証してください。Rhinoceros / RhinoCommon は Robert McNeel & Associates の製品であり、本プロジェクトとは無関係の独立したスクリプトです。

## 12. 開発コンテキスト (Development context)

個人による Rhino 作業効率化のための RhinoPython スクリプトです。
