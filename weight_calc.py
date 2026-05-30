# -*- coding: utf-8 -*-
"""
重量計算スクリプト (v4) for Rhino

選択した閉じたソリッド / ポリサーフェス / メッシュ / Extrusion /
Block Instance / SubD、または直接入力した体積から、素材密度を掛けて
重量 (kg) を算出する。

体積取得は Rhino 標準 Volume コマンドの結果と一致させる方針で、
Rhino.Geometry.VolumeMassProperties.Compute() を直接使用する。

Rhino for Mac の RunPythonScript で動作することを想定。

v2 (材料記憶機能) の変更点:
  - 前回選択した素材をローカル設定ファイル
    (~/.rhino_weight_calc_settings.json) に保存し、次回実行時に
    素材選択ダイアログの既定候補 (default) として復元する。
  - 標準ライブラリ json / os のみ使用。外部ライブラリ非依存。
  - 設定ファイルが無い / 壊れている / 保存名が現在の MATERIALS に
    無い場合は、エラーで止めずに従来どおりの素材選択へフォールバック。
  - 体積取得・密度データ・重量計算ロジック (下記 v4) は不変更。

v4 の主な変更点:
  - Block Instance (InstanceReferenceGeometry) を展開し、定義内の
    Brep/Mesh/Extrusion/SubD に InstanceXform を適用してから合算
  - Brep に複数の disjoint な solid shell が含まれる場合は
    SplitDisjointPieces で分割して個別計数 (Rhino 標準 Volume の
    「N 個のソリッド」と一致させる)
  - モデル単位での Raw volume と m^3 の両方を表示
  - 入力オブジェクト数と「実際に体積計算したジオメトリ数」を分離表示
  - 各ピースの計算ログ (id / kind / raw volume / success / note) を
    コマンド履歴に出力
"""

import json
import os
import time

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino  # RhinoCommon


# --- 素材データ ----------------------------------------------------------
# 各素材は dict:
#   jp           : 表示名 (日本語)
#   en           : 英名 (設定ファイル / UserText 保存キー, ASCII)
#   density      : 密度 (kg/m^3)
#   price_per_kg : 単価 (通貨単位/kg)。None なら材料費は概算しない。
#
# ※ price_per_kg は v3 で追加した「概算用プレースホルダ」です。市況・調達先で
#   大きく変動するため、必ず各自の実調達価格に更新してください。木材は重量単価
#   ではなく材積/枚単位で流通するのが一般的なため、既定では None (材料費は出さ
#   ない) にしています。
CURRENCY = u"JPY"

MATERIALS = [
    # --- 金属・無機 ---
    {"jp": u"鋼",           "en": "Steel",    "density": 7850.0, "price_per_kg": 150.0},
    {"jp": u"アルミ",       "en": "Aluminum", "density": 2700.0, "price_per_kg": 700.0},
    {"jp": u"ステンレス",   "en": "SUS",      "density": 7930.0, "price_per_kg": 1000.0},
    {"jp": u"コンクリート", "en": "Concrete", "density": 2400.0, "price_per_kg": 30.0},
    {"jp": u"真鍮",         "en": "Brass",    "density": 8500.0, "price_per_kg": 1800.0},
    {"jp": u"銅",           "en": "Copper",   "density": 8960.0, "price_per_kg": 2000.0},
    # --- 木材 (気乾密度の代表値。重量単価が一般的でないため price は None) ---
    {"jp": u"杉",           "en": "Cedar",    "density": 380.0,  "price_per_kg": None},
    {"jp": u"桧",           "en": "Hinoki",   "density": 410.0,  "price_per_kg": None},
    {"jp": u"松",           "en": "Pine",     "density": 510.0,  "price_per_kg": None},
    {"jp": u"樫",           "en": "Oak",      "density": 750.0,  "price_per_kg": None},
    {"jp": u"集成材",       "en": "Glulam",   "density": 450.0,  "price_per_kg": None},
    {"jp": u"合板",         "en": "Plywood",  "density": 600.0,  "price_per_kg": None},
    {"jp": u"MDF",          "en": "MDF",      "density": 750.0,  "price_per_kg": None},
]


def material_cost(weight_kg, price_per_kg):
    """概算材料費を返す。price_per_kg が None / 無効なら None。"""
    if price_per_kg is None:
        return None
    try:
        return float(weight_kg) * float(price_per_kg)
    except Exception:
        return None


def fmt_cost(cost):
    """材料費を整形。None は "-"。"""
    if cost is None:
        return u"-"
    return u"{:,.0f} {}".format(cost, CURRENCY)


# --- 設定ファイル (v2: 前回素材の記憶) -----------------------------------
# ユーザーホーム直下に保存。外部ライブラリ非依存 (json / os のみ)。
# 英名 (MATERIALS の 3 番目の要素, ASCII) のみ保存するため、
# 日本語パス・エンコーディングの影響を受けない。
SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), ".rhino_weight_calc_settings.json")


def load_settings():
    """設定ファイル (JSON) を dict で読み込む。
    存在しない / 壊れている / 読み込み失敗時は {} を返す (例外を投げない)。"""
    try:
        f = open(SETTINGS_PATH, "r")
        try:
            data = json.load(f)
        finally:
            f.close()
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def save_settings(settings):
    """設定 dict を JSON で保存する。失敗しても重量計算は止めない。
    成功時 True / 失敗時 False を返す。"""
    try:
        f = open(SETTINGS_PATH, "w")
        try:
            # ensure_ascii=True (既定) でファイルは純 ASCII になり、
            # Mac / 日本語環境でもエンコーディング問題を起こさない。
            json.dump(settings, f, indent=2, sort_keys=True)
        finally:
            f.close()
        return True
    except Exception:
        return False


def _material_by_en(name):
    """英名 (dict["en"]) に一致する素材 dict を返す。見つからなければ None。"""
    if not name:
        return None
    for m in MATERIALS:
        if m["en"] == name:
            return m
    return None


def get_last_material():
    """保存済み last_material (英名) を返す。
    現在の MATERIALS に存在する場合のみ返し、無ければ None。"""
    settings = load_settings()
    name = settings.get("last_material") if isinstance(settings, dict) else None
    if _material_by_en(name) is not None:
        return name
    return None


def save_last_material(material_name):
    """選択された素材の英名を last_material として保存する。
    既存の他キーは保持する。保存失敗は無視する (戻り値で判定可)。"""
    settings = load_settings()
    if not isinstance(settings, dict):
        settings = {}
    settings["last_material"] = material_name
    return save_settings(settings)


# --- Rhino の単位系コード -------------------------------------------------
SUPPORTED_UNITS = {2: "mm", 3: "cm", 4: "m"}
LENGTH_TO_M_FALLBACK = {2: 1.0e-3, 3: 1.0e-2, 4: 1.0}


def get_volume_to_m3_factor():
    """現在のモデル単位の「体積」を m^3 に変換する係数を返す。
    対応外の単位なら (None, unit_code) を返す。"""
    unit_code = rs.UnitSystem()
    if unit_code not in SUPPORTED_UNITS:
        return None, unit_code
    try:
        length_to_m = float(rs.UnitScale(4))
    except Exception:
        length_to_m = LENGTH_TO_M_FALLBACK[unit_code]
    return length_to_m ** 3, unit_code


# --- 入力モード選択 -----------------------------------------------------
def pick_mode():
    items = [u"選択オブジェクトから計算", u"体積を直接入力 (m³)"]
    sel = rs.ListBox(
        items,
        message=u"計算方法を選択してください",
        title=u"重量計算 (Mass)",
        default=items[0],
    )
    if sel is None:
        return None
    return "select" if sel == items[0] else "manual"


def pick_objects():
    """対象は Surface(8) / Polysurface(16) / Mesh(32) / Instance(4096) /
    SubD(262144) / Extrusion(1073741824)."""
    filter_mask = 8 + 16 + 32 + 4096 + 262144 + 1073741824
    return rs.GetObjects(
        message=u"重量計算する閉じたソリッド/メッシュ/ブロックを選択",
        filter=filter_mask,
        group=True,
        preselect=True,
        select=False,
    )


def pick_volume_manual():
    msg = u"体積 (m³) を入力  (例: 1m立方=1.0, 100mm立方=0.001, 1リットル=0.001)"
    v = rs.GetReal(message=msg, number=0.001, minimum=0.0)
    if v is None:
        return None
    if v <= 0.0:
        rs.MessageBox(u"体積は 0 より大きい値を入力してください。", 16, u"重量計算 (Mass)")
        return None
    return v


def _material_label(m):
    """ListBox 用の素材ラベルを組み立てる (密度 + 単価)。"""
    if m["price_per_kg"] is None:
        price = u"単価未設定"
    else:
        price = u"{:,.0f} {}/kg".format(m["price_per_kg"], CURRENCY)
    return u"{}  ({:.0f} kg/m³, {}, {})".format(
        m["jp"], m["density"], m["en"], price)


def pick_material(default_en=None, prompt_extra=None):
    """素材選択ダイアログ。default_en (英名) が現在の MATERIALS にあれば
    その項目を既定候補 (default) として事前選択し、プロンプトに併記する。
    Enter / そのまま OK で既定素材を再利用できる。default_en が None / 不一致
    なら従来どおり先頭を既定にする。prompt_extra はレイヤー名等の補足文。"""
    labels = [_material_label(m) for m in MATERIALS]
    default_label = labels[0]
    message = u"素材を選択してください"
    if prompt_extra:
        message = message + u"  " + prompt_extra
    if default_en is not None:
        for i, m in enumerate(MATERIALS):
            if m["en"] == default_en:
                default_label = labels[i]
                message = message + u"  (既定: {})".format(default_en)
                break
    sel = rs.ListBox(
        labels,
        message=message,
        title=u"重量計算 (Mass)",
        default=default_label,
    )
    if sel is None:
        return None
    return MATERIALS[labels.index(sel)]


# --- ジオメトリ正規化 / 体積計算 -----------------------------------------
def _to_brep_if_possible(geom):
    """VolumeMassProperties.Compute() に渡せる形にジオメトリを正規化する。
    - Brep / Mesh はそのまま返す
    - Extrusion は ToBrep で Brep 化
    - SubD は Brep.CreateFromSubD で Brep 化
    - 単一 Surface は ToBrep で Brep 化
    - InstanceReferenceGeometry や上記以外は None
    """
    if geom is None:
        return None
    if isinstance(geom, Rhino.Geometry.Brep):
        return geom
    if isinstance(geom, Rhino.Geometry.Mesh):
        return geom
    if isinstance(geom, Rhino.Geometry.Extrusion):
        try:
            return geom.ToBrep(False)
        except Exception:
            return None
    SubD = getattr(Rhino.Geometry, "SubD", None)
    if SubD is not None and isinstance(geom, SubD):
        try:
            return Rhino.Geometry.Brep.CreateFromSubD(geom, 0)
        except Exception:
            return None
    if isinstance(geom, Rhino.Geometry.Surface):
        try:
            return geom.ToBrep()
        except Exception:
            return None
    return None


def _split_brep_pieces(brep):
    """Brep を disjoint な solid pieces に分割。失敗時 / 1ピースの時は
    [brep] を返す。Mesh やその他は呼び出し側で扱わないこと。"""
    if brep is None:
        return []
    if not isinstance(brep, Rhino.Geometry.Brep):
        return [brep]
    try:
        pieces = brep.SplitDisjointPieces()
    except Exception:
        pieces = None
    if pieces is None:
        return [brep]
    pieces = list(pieces)
    if len(pieces) == 0:
        return [brep]
    return pieces


def _vmp_volume(geom):
    """VolumeMassProperties.Compute() を呼び、絶対値で返す。失敗時 None。"""
    if geom is None:
        return None
    try:
        vmp = Rhino.Geometry.VolumeMassProperties.Compute(geom)
    except Exception:
        return None
    if vmp is None:
        return None
    try:
        return abs(float(vmp.Volume))
    except Exception:
        return None


def _xform_is_identity(xf):
    try:
        return bool(xf.IsIdentity)
    except Exception:
        try:
            ident = Rhino.Geometry.Transform.Identity
            return xf == ident
        except Exception:
            return False


def _apply_xform(geom, xf):
    """xform を適用したコピーを返す。失敗時は元の geom をそのまま返す。"""
    if geom is None:
        return None
    if _xform_is_identity(xf):
        return geom
    try:
        dup = geom.Duplicate()
    except Exception:
        dup = geom
    try:
        dup.Transform(xf)
    except Exception:
        pass
    return dup


def _short_id(uid):
    s = str(uid)
    return s[:8] if len(s) >= 8 else s


# --- 再帰的ジオメトリ収集 ------------------------------------------------
def collect_computables(rhino_object, xform_accum, label_prefix,
                        results, depth=0, max_depth=16):
    """RhinoObject から計算可能なジオメトリを再帰的に取り出し、
    各ピースについて VolumeMassProperties で体積を計算して results に追加する。

    results 要素 (dict):
      id          : RhinoObject の GUID (str)
      kind        : 元ジオメトリの型名 (str)
      raw_volume  : モデル単位での体積 (float) or None
      success     : 計算成功 (bool)
      depth       : 再帰深さ
      block_child : ブロック子要素か (bool)
      note        : ラベル/補足
    """
    if depth > max_depth:
        return
    if rhino_object is None:
        results.append({
            "id": "?", "kind": "None",
            "raw_volume": None, "success": False,
            "depth": depth, "block_child": depth > 0,
            "note": label_prefix + u"(RhinoObject 取得失敗)",
        })
        return

    geom = getattr(rhino_object, "Geometry", None)
    obj_id = str(getattr(rhino_object, "Id", "?"))

    # --- Block / Instance Reference の展開 ---
    if isinstance(geom, Rhino.Geometry.InstanceReferenceGeometry):
        # top-level の InstanceObject なら属性で取れる
        local_xform = getattr(rhino_object, "InstanceXform", None)
        idef = getattr(rhino_object, "InstanceDefinition", None)
        # nested 用フォールバック (InstanceDefinition.GetObjects() 経由など)
        if idef is None:
            try:
                idef = sc.doc.InstanceDefinitions.FindId(geom.ParentIdefId)
            except Exception:
                idef = None
        if local_xform is None:
            local_xform = getattr(geom, "Xform", None)
        if local_xform is None:
            local_xform = Rhino.Geometry.Transform.Identity

        if idef is None:
            results.append({
                "id": obj_id, "kind": "InstanceReference",
                "raw_volume": None, "success": False,
                "depth": depth, "block_child": depth > 0,
                "note": label_prefix + u"(InstanceDefinition not found)",
            })
            return

        idef_name = getattr(idef, "Name", "?")
        try:
            children = list(idef.GetObjects())
        except Exception:
            children = []

        try:
            combined_xform = xform_accum * local_xform
        except Exception:
            combined_xform = local_xform

        new_prefix = u"{}[block:{} ({}個)]".format(
            label_prefix, idef_name, len(children))
        if len(children) == 0:
            results.append({
                "id": obj_id, "kind": "InstanceReference",
                "raw_volume": 0.0, "success": True,
                "depth": depth, "block_child": depth > 0,
                "note": new_prefix + u" (empty definition)",
            })
            return

        for ch in children:
            collect_computables(ch, combined_xform, new_prefix + u" -> ",
                                results, depth + 1, max_depth)
        return

    # --- 通常ジオメトリ ---
    kind = type(geom).__name__ if geom is not None else "None"
    base = _to_brep_if_possible(geom)

    if base is None:
        results.append({
            "id": obj_id, "kind": kind,
            "raw_volume": None, "success": False,
            "depth": depth, "block_child": depth > 0,
            "note": label_prefix + u"(対象外: " + kind + u")",
        })
        return

    # Brep は disjoint solid pieces に分割、Mesh などはそのまま
    if isinstance(base, Rhino.Geometry.Brep):
        pieces = _split_brep_pieces(base)
    else:
        pieces = [base]

    for idx, piece in enumerate(pieces):
        piece_xf = _apply_xform(piece, xform_accum)
        vol = _vmp_volume(piece_xf)
        if len(pieces) > 1:
            note = u"{}piece {}/{}".format(label_prefix, idx + 1, len(pieces))
        else:
            note = label_prefix
        if vol is None:
            results.append({
                "id": obj_id, "kind": kind,
                "raw_volume": None, "success": False,
                "depth": depth, "block_child": depth > 0,
                "note": note + u" (VolumeMassProperties 失敗)",
            })
        else:
            results.append({
                "id": obj_id, "kind": kind,
                "raw_volume": vol, "success": True,
                "depth": depth, "block_child": depth > 0,
                "note": note,
            })


# --- 表示フォーマット ----------------------------------------------------
def fmt_raw(v):
    """raw volume をモデル単位値として整形 (4 桁小数, 末尾ゼロ除去)."""
    if v is None:
        return "?"
    s = "{:.4f}".format(v)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def fmt_m3(v):
    """m^3 を 8 桁有効精度で整形."""
    if v is None:
        return "?"
    return "{:.8g}".format(v)


# --- v4: オブジェクト別の取得 / 集計 -------------------------------------
def _object_name(oid):
    """オブジェクト名を返す。無ければ "(unnamed)"。"""
    try:
        nm = rs.ObjectName(oid)
    except Exception:
        nm = None
    if nm is None or nm == u"":
        return u"(unnamed)"
    return nm


def _object_layer(oid):
    """オブジェクトのレイヤー名 (フルパス) を返す。失敗時は "(no layer)"。"""
    try:
        ly = rs.ObjectLayer(oid)
    except Exception:
        ly = None
    if ly is None or ly == u"":
        return u"(no layer)"
    return ly


def collect_object_rows(ids):
    """選択された各オブジェクト id について計算可能ジオメトリを収集し、
    1 オブジェクト = 1 行に集計する。
    返り値: (rows, all_results)
      rows: dict のリスト。キー: id / name / layer / native_volume /
            ok (成功ピース数) / fail (失敗ピース数)
      all_results: 全ピースの詳細 (計算ログ用)
    体積取得に失敗したオブジェクトもエラーで止めず、native_volume=0.0 /
    fail>0 の行として残す (呼び出し側で警告表示)。"""
    identity_xform = Rhino.Geometry.Transform.Identity
    rows = []
    all_results = []
    for oid in ids:
        ro = None
        try:
            ro = rs.coercerhinoobject(oid, True, False)
        except Exception:
            ro = None
        if ro is None:
            try:
                ro = sc.doc.Objects.Find(oid)
            except Exception:
                ro = None
        res = []
        collect_computables(ro, identity_xform, u"", res, depth=0)
        all_results.extend(res)
        native = sum((r["raw_volume"] or 0.0) for r in res if r["success"])
        ok = sum(1 for r in res if r["success"])
        fail = sum(1 for r in res if not r["success"])
        rows.append({
            "id": str(oid),
            "name": _object_name(oid),
            "layer": _object_layer(oid),
            "native_volume": native,
            "ok": ok,
            "fail": fail,
        })
    return rows, all_results


# --- v5: CSV 出力 --------------------------------------------------------
CSV_COLUMNS = [
    "object_id", "object_name", "layer", "material", "density",
    "volume", "weight_kg", "price_per_kg", "estimated_cost",
]


def _timestamp():
    """ファイル名用の日時文字列 (YYYYMMDD_HHMMSS)。"""
    try:
        return time.strftime("%Y%m%d_%H%M%S")
    except Exception:
        return "export"


def _csv_field(value):
    """CSV 1 フィールドを安全に整形する (RFC 4180 風)。
    None は空欄。カンマ / 改行 / ダブルクォートを含む場合は引用符で囲む。"""
    if value is None:
        return u""
    s = u"{}".format(value)
    if (u"," in s) or (u"\"" in s) or (u"\n" in s) or (u"\r" in s):
        s = u"\"" + s.replace(u"\"", u"\"\"") + u"\""
    return s


def csv_default_path():
    """既定の保存先パスを返す。~/Desktop があればそこ、無ければ ~。"""
    home = os.path.expanduser("~")
    desktop = os.path.join(home, "Desktop")
    base = desktop if os.path.isdir(desktop) else home
    return os.path.join(base, "rhino_weight_{}.csv".format(_timestamp()))


def build_csv_text(rows, factor):
    """object_rows から CSV 本文 (ヘッダ + 各行) の文字列を組み立てる。"""
    out = [u",".join(_csv_field(c) for c in CSV_COLUMNS)]
    for r in rows:
        vol_m3 = r["native_volume"] * factor
        density = r.get("density")
        weight = vol_m3 * density if density else 0.0
        price = r.get("price_per_kg")
        cost = material_cost(weight, price)
        has_geom = r["ok"] > 0
        cells = [
            r["id"],
            r["name"],
            r["layer"],
            r.get("material_en", u""),
            u"{:.1f}".format(density) if density else u"",
            u"{:.8g}".format(vol_m3) if has_geom else u"",
            u"{:.4f}".format(weight) if has_geom else u"",
            u"" if price is None else u"{:.2f}".format(price),
            u"" if (cost is None or not has_geom) else u"{:.2f}".format(cost),
        ]
        out.append(u",".join(_csv_field(c) for c in cells))
    return u"\n".join(out) + u"\n"


def export_csv(rows, factor, path):
    """CSV を UTF-8 (BOM 付き) で書き出す。成功時 path、失敗時 None を返す。
    BOM は Excel が UTF-8 を正しく開くため。例外は投げない。"""
    try:
        text = build_csv_text(rows, factor)
        f = open(path, "wb")
        try:
            f.write(b"\xef\xbb\xbf")  # UTF-8 BOM
            f.write(text.encode("utf-8"))
        finally:
            f.close()
        return path
    except Exception:
        return None


def maybe_export_csv(rows, factor):
    """ユーザーに CSV 出力の可否と保存先を尋ね、保存する。
    保存できれば path を、スキップ/失敗時は None を返す (計算表示は止めない)。"""
    try:
        yn = rs.MessageBox(
            u"計算結果を CSV に保存しますか?", 4, u"重量計算 (Mass)")
    except Exception:
        yn = None
    # rs.MessageBox の Yes は 6。Yes 以外 / 取得失敗ならスキップ。
    if yn != 6:
        return None

    default_path = csv_default_path()
    path = None
    try:
        path = rs.SaveFileName(
            u"CSV の保存先", u"CSV Files (*.csv)|*.csv||", None,
            os.path.basename(default_path))
    except Exception:
        path = None
    if not path:
        # ダイアログが使えない / キャンセル時はデスクトップ等にフォールバック
        path = default_path
    if not path.lower().endswith(".csv"):
        path = path + ".csv"

    saved = export_csv(rows, factor, path)
    if saved:
        print(u"CSV を保存しました: {}".format(saved))
    else:
        print(u"CSV の保存に失敗しました (計算結果の表示は続行します)。")
    return saved


def _pad(s, width):
    """表示用に文字列を width まで右空白詰め (簡易, 全角は考慮しない)。"""
    s = u"{}".format(s)
    if len(s) < width:
        return s + u" " * (width - len(s))
    return s


def print_object_table(rows, factor, unit_label):
    """オブジェクト別の集計表をコマンドラインに出力する。"""
    print(u"----- オブジェクト別一覧 (per-object) -----")
    header = u"{} {} {} {} {} {} {}".format(
        _pad(u"#", 3), _pad(u"id", 9), _pad(u"name", 16),
        _pad(u"layer", 16), _pad(u"material", 12),
        _pad(u"weight(kg)", 12), u"cost")
    print(header)
    for i, r in enumerate(rows):
        vol_m3 = r["native_volume"] * factor
        weight = vol_m3 * r["density"] if r.get("density") else 0.0
        cost = material_cost(weight, r.get("price_per_kg"))
        flag = u"" if r["fail"] == 0 else u"  [warn: {} skip]".format(r["fail"])
        if r["ok"] == 0:
            wt_str = u"-"
            cost_str = u"-"
            flag = u"  [skip: 体積取得不可]"
        else:
            wt_str = u"{:.2f}".format(weight)
            cost_str = fmt_cost(cost)
        print(u"{} {} {} {} {} {} {}{}".format(
            _pad(i + 1, 3), _pad(_short_id(r["id"]), 9),
            _pad(r["name"], 16), _pad(r["layer"], 16),
            _pad(r.get("material_en", u"-"), 12),
            _pad(wt_str, 12), cost_str, flag))


# --- メイン --------------------------------------------------------------
def main():
    factor, unit_code = get_volume_to_m3_factor()
    unit_supported = factor is not None

    selected_now = rs.SelectedObjects()
    if selected_now:
        mode = "select"
    else:
        mode = pick_mode()
        if mode is None:
            return

    if mode == "select" and not unit_supported:
        msg = (
            u"対応していないモデル単位です (UnitSystem code = {}).\n"
            u"mm / cm / m のいずれかに変更してから再実行してください。\n"
            u"(モデル無しで試算したい場合は「体積を直接入力」モードを使ってください)"
        ).format(unit_code)
        print(msg)
        rs.MessageBox(msg, 16, u"重量計算 (Mass)")
        return

    ids = None
    object_rows = None
    if mode == "select":
        ids = pick_objects()
        if not ids:
            return

        # v4: 1 オブジェクト = 1 行に集計 (詳細ピースは all_results)
        object_rows, all_results = collect_object_rows(ids)

        # --- 計算ログ (全ピース詳細) ---
        print(u"----- 計算ログ -----")
        for i, r in enumerate(all_results):
            tag = u"OK  " if r["success"] else u"FAIL"
            depth_pad = u"  " * r["depth"]
            vol_str = fmt_raw(r["raw_volume"]) if r["success"] else u"-"
            child_tag = u"[block-child] " if r.get("block_child") else u""
            line = u"{:>3d} [{}] {}id={} kind={} raw={} {}{}".format(
                i + 1, tag, depth_pad, _short_id(r["id"]),
                r["kind"], vol_str, child_tag, r.get("note", u""))
            print(line)

        success_results = [r for r in all_results if r["success"]]
        total_native = sum((r["raw_volume"] or 0.0) for r in success_results)
        used = len(success_results)
        failed = sum(1 for r in all_results if not r["success"])

        if used == 0:
            msg = (u"有効な体積を取得できませんでした。\n"
                   u"対象が閉じたソリッド / 閉じたメッシュ / Block か確認してください。")
            print(msg)
            rs.MessageBox(msg, 16, u"重量計算 (Mass)")
            return

        volume_m3 = total_native * factor
        input_count = len(ids)
        geom_count = used
        unit_label = SUPPORTED_UNITS[unit_code]
        raw_unit_label = unit_label + u"3"
    else:
        v_m3 = pick_volume_manual()
        if v_m3 is None:
            return
        volume_m3 = v_m3
        total_native = None
        input_count = 1
        geom_count = 1
        failed = 0
        unit_label = u"-"
        raw_unit_label = u"-"

    # v2: 前回素材を既定候補として復元 (無ければ None で従来動作)
    last_en = get_last_material()
    picked = pick_material(last_en)
    if picked is None:
        return
    material_jp = picked["jp"]
    density = picked["density"]
    material_en = picked["en"]
    price_per_kg = picked["price_per_kg"]

    # v2: 確定した素材を次回用に保存 (失敗しても計算は続行)
    save_last_material(material_en)

    weight_kg = volume_m3 * density
    # v3: 概算材料費 (単価未設定なら None)
    cost = material_cost(weight_kg, price_per_kg)

    # v4: 各オブジェクト行へ素材を割り当て、per-object 表を出力 (select 時)
    if mode == "select" and object_rows is not None:
        for row in object_rows:
            row["material_en"] = material_en
            row["density"] = density
            row["price_per_kg"] = price_per_kg
        print_object_table(object_rows, factor, unit_label)

    # --- 最終結果表示 (合計 / totals) ---
    lines = [u"----- 重量計算 (Mass) -----"]
    if mode == "select":
        lines.append(u"入力オブジェクト数: {}".format(input_count))
        lines.append(u"体積計算ジオメトリ数: {}".format(geom_count))
    else:
        lines.append(u"入力: 直接入力 (m³)")
    lines.append(u"素材: {} ({})".format(material_jp, material_en))
    lines.append(u"密度: {:.0f} kg/m3".format(density))
    if mode == "select":
        lines.append(u"モデル単位: {}".format(unit_label))
        lines.append(u"Raw volume: {} {}".format(
            fmt_raw(total_native), raw_unit_label))
    lines.append(u"Volume: {} m3".format(fmt_m3(volume_m3)))
    lines.append(u"Weight: {:.2f} kg".format(weight_kg))
    # v3: 単価と概算材料費
    if price_per_kg is None:
        lines.append(u"単価 (price_per_kg): 未設定")
    else:
        lines.append(u"単価 (price_per_kg): {:,.0f} {}/kg".format(
            price_per_kg, CURRENCY))
    lines.append(u"概算材料費 (estimated): {}".format(fmt_cost(cost)))
    if mode == "select":
        lines.append(u"失敗: {}".format(failed))

    text = "\n".join(lines)

    for ln in lines:
        print(ln)

    rs.MessageBox(text, 0, u"重量計算 (Mass)")

    # v5: select モードのみ CSV 出力を提案 (失敗しても上記表示は維持)
    if mode == "select" and object_rows is not None:
        maybe_export_csv(object_rows, factor)


if __name__ == "__main__":
    main()
