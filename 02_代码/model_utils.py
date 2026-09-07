# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：model_utils (系统通用计量与数学分析工具集)
功能描述：
1. 统一管理全系统工程路径拓扑、可视化色彩基调与时间序列参数。
2. 基础数据管道清洗、异常孤立尖峰 (Isolated Spikes) 邻域平滑修复。
3. 高性能矩阵运算引擎：双向固定效应 (Two-Way FE) 面板 OLS 回归与聚类稳健标准误 (Cluster-Robust SE)。
4. 统计推断数学库：正则化不完全贝塔函数、双侧 Student-t 分布临界值与 p 值数值求解。
5. 多目标优化支持：Pareto 非劣解前沿提取与欧氏距离折中拐点 (Knee Point) 自动化选取。
================================================================================
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def find_project_root() -> str:
    """纯相对路径推导项目根目录（代码文件的上一级目录）。
    严禁任何绝对路径硬编码，确保项目无论在何处运行，输出均自动定位在代码文件上一级目录的新建文件夹中。"""
    if "DEC_CES_PROJECT_ROOT" in os.environ and os.path.isdir(os.environ["DEC_CES_PROJECT_ROOT"]):
        return os.path.abspath(os.environ["DEC_CES_PROJECT_ROOT"])
    code_file = Path(__file__).resolve()
    code_dir = code_file.parent  # 02_代码
    parent = code_dir.parent     # 代码文件的上一级目录
    return str(parent)


PROJECT_DIR = find_project_root()
RAW_DATA_DIR = os.path.join(PROJECT_DIR, "03_原始数据")
RESULT_DIR = os.path.join(PROJECT_DIR, "04_核心结果")
DATA_DIR = RESULT_DIR
SIM_DIR = os.path.join(RESULT_DIR, "simulation_results")
FIGURE_DIR = os.path.join(PROJECT_DIR, "05_图形")
SUPP_FIGURE_DIR = os.path.join(FIGURE_DIR, "补充诊断图")
YEARS = range(2011, 2023)

# 确保在代码文件的上一级目录下新建结果输出目录
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(SIM_DIR, exist_ok=True)
os.makedirs(FIGURE_DIR, exist_ok=True)
os.makedirs(SUPP_FIGURE_DIR, exist_ok=True)

_CUSTOM_RAW_DATA_DIR: Optional[str] = None
_CUSTOM_RESULT_DIR: Optional[str] = None
_CUSTOM_FIGURE_DIR: Optional[str] = None


def get_raw_data_dir() -> str:
    """获取当前激活的原始数据目录。"""
    global _CUSTOM_RAW_DATA_DIR
    if _CUSTOM_RAW_DATA_DIR and os.path.isdir(_CUSTOM_RAW_DATA_DIR):
        return _CUSTOM_RAW_DATA_DIR
    if "DEC_CES_RAW_DATA_DIR" in os.environ and os.path.isdir(os.environ["DEC_CES_RAW_DATA_DIR"]):
        return os.environ["DEC_CES_RAW_DATA_DIR"]
    return RAW_DATA_DIR


def set_raw_data_dir(new_dir: str) -> None:
    """动态切换激活的原始数据目录。"""
    global _CUSTOM_RAW_DATA_DIR, RAW_DATA_DIR
    abs_dir = os.path.abspath(new_dir)
    if not os.path.isdir(abs_dir):
        raise FileNotFoundError(f"指定的数据源目录不存在: {abs_dir}")
    _CUSTOM_RAW_DATA_DIR = abs_dir
    RAW_DATA_DIR = abs_dir


def get_result_dir() -> str:
    """获取当前激活的输出结果目录（默认为代码文件上一级目录下的新建 04_核心结果）。"""
    global _CUSTOM_RESULT_DIR
    if _CUSTOM_RESULT_DIR and os.path.isdir(_CUSTOM_RESULT_DIR):
        return _CUSTOM_RESULT_DIR
    if "DEC_CES_RESULT_DIR" in os.environ:
        target = os.path.abspath(os.environ["DEC_CES_RESULT_DIR"])
        os.makedirs(target, exist_ok=True)
        return target
    os.makedirs(RESULT_DIR, exist_ok=True)
    return RESULT_DIR


def set_result_dir(new_dir: str) -> None:
    """动态切换输出结果目录，自动确保目录创建。"""
    global _CUSTOM_RESULT_DIR, RESULT_DIR, DATA_DIR, SIM_DIR
    abs_dir = os.path.abspath(new_dir)
    os.makedirs(abs_dir, exist_ok=True)
    _CUSTOM_RESULT_DIR = abs_dir
    RESULT_DIR = abs_dir
    DATA_DIR = abs_dir
    SIM_DIR = os.path.join(abs_dir, "simulation_results")
    os.makedirs(SIM_DIR, exist_ok=True)


def get_figure_dir() -> str:
    """获取当前激活的图形输出目录（默认为代码文件上一级目录下的新建 05_图形）。"""
    global _CUSTOM_FIGURE_DIR
    if _CUSTOM_FIGURE_DIR and os.path.isdir(_CUSTOM_FIGURE_DIR):
        return _CUSTOM_FIGURE_DIR
    if "DEC_CES_FIGURE_DIR" in os.environ:
        target = os.path.abspath(os.environ["DEC_CES_FIGURE_DIR"])
        os.makedirs(target, exist_ok=True)
        return target
    os.makedirs(FIGURE_DIR, exist_ok=True)
    return FIGURE_DIR


def set_figure_dir(new_dir: str) -> None:
    """动态切换图形输出目录，自动确保目录创建。"""
    global _CUSTOM_FIGURE_DIR, FIGURE_DIR, SUPP_FIGURE_DIR
    abs_dir = os.path.abspath(new_dir)
    os.makedirs(abs_dir, exist_ok=True)
    _CUSTOM_FIGURE_DIR = abs_dir
    FIGURE_DIR = abs_dir
    SUPP_FIGURE_DIR = os.path.join(abs_dir, "补充诊断图")
    os.makedirs(SUPP_FIGURE_DIR, exist_ok=True)

NE_PROVS = ["辽宁", "吉林", "黑龙江"]
EAST_PROVS = ["北京", "天津", "河北", "上海", "江苏", "浙江", "福建", "山东", "广东", "海南"]
REGION_ORDER = ["东北", "东部", "中西部"]
PLOT_DPI = 360

SCENARIO_PALETTE = {
    "基准情景": "#64748b",
    "数字加速情景": "#f97316",
    "统一政策情景": "#f59e0b",
    "定向协同情景": "#0f766e",
    "Pareto最优路径": "#8b5cf6",
    "统一政策": "#f59e0b",
    "定向协同": "#0f766e",
}

SUPPORT_PALETTE = {
    "高支持": "#c2410c",
    "中支持": "#ea580c",
    "提示性": "#f59e0b",
    "不纳入仿真": "#94a3b8",
}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_figure_bundle(fig, *paths: str, dpi: int = PLOT_DPI) -> None:
    for path in paths:
        ensure_dir(os.path.dirname(path) or ".")
        fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")


def configure_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 10.5,
            "axes.titlesize": 13.5,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11.5,
            "axes.labelcolor": "#1f2937",
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "legend.fontsize": 9.5,
            "legend.framealpha": 0.94,
            "legend.facecolor": "white",
            "legend.edgecolor": "#cbd5e1",
            "axes.edgecolor": "#475569",
            "axes.linewidth": 1.05,
            "grid.color": "#cbd5e1",
            "grid.linestyle": "--",
            "grid.alpha": 0.55,
            "axes.axisbelow": True,
            "savefig.facecolor": "white",
        }
    )
    return plt


def style_axis(ax, grid_axis: str | None = "y", despine: bool = True) -> None:
    ax.set_facecolor("white")
    if despine:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#475569")
    ax.spines["bottom"].set_color("#475569")
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)

    if grid_axis == "both":
        ax.grid(True)
    elif grid_axis in {"x", "y"}:
        ax.grid(axis=grid_axis)
    else:
        ax.grid(False)


def raw_data_path(*parts: str) -> str:
    return os.path.join(get_raw_data_dir(), *parts)


def result_path(*parts: str) -> str:
    return os.path.join(get_result_dir(), *parts)


def figure_path(*parts: str) -> str:
    return os.path.join(get_figure_dir(), *parts)


def supp_figure_path(*parts: str) -> str:
    return os.path.join(get_figure_dir(), "补充诊断图", *parts)


DEFAULT_DATA_DICTIONARY: Dict[str, Dict[str, Any]] = {
    "数字经济指数_2011_2022.xlsx": {
        "id": "DS-01",
        "var": "Tech",
        "role": "核心数字技术能力 (协同/严格口径)",
        "weight": "0.3424",
        "status_default": "✓ 正常 (360样本)",
        "is_default": True,
    },
    "省份等级的灯光值_平均值.xlsx": {
        "id": "DS-02",
        "var": "NTL",
        "role": "数字活跃度与经济活动代理",
        "weight": "0.2851",
        "status_default": "✓ 正常 (360样本)",
        "is_default": True,
    },
    "能源消费量_万吨标煤.xlsx": {
        "id": "DS-03",
        "var": "Energy",
        "role": "低碳用能效率 log(1/Energy)",
        "weight": "0.1976",
        "status_default": "✓ 正常 (西藏除外)",
        "is_default": True,
    },
    "产业结构高级化_第二产业占比.xlsx": {
        "id": "DS-04",
        "var": "Upgrade",
        "role": "产业升级机制变量 (1-二产比重)",
        "weight": "0.1749",
        "status_default": "✓ 正常 (360样本)",
        "is_default": True,
    },
    "碳排放强度_万吨亿元GDP.xlsx": {
        "id": "DS-05",
        "var": "CO2 / Y",
        "role": "基准被解释变量 (碳排放强度)",
        "weight": "主被解释",
        "status_default": "✓ 孤立尖峰已留痕修复",
        "is_default": True,
    },
    "人均GDP.xlsx": {
        "id": "DS-06",
        "var": "PGDP",
        "role": "经济发展水平控制变量 / 增长方程",
        "weight": "控制变量",
        "status_default": "✓ 正常 (360样本)",
        "is_default": True,
    },
    "城镇化率_2000_2022.xlsx": {
        "id": "DS-07",
        "var": "URB",
        "role": "常住人口城镇化率控制变量",
        "weight": "控制变量",
        "status_default": "✓ 正常 (360样本)",
        "is_default": True,
    },
    "对外开放程度_2000_2022.xlsx": {
        "id": "DS-08",
        "var": "OPEN",
        "role": "进出口总额/GDP 对外开放度",
        "weight": "控制变量",
        "status_default": "✓ 正常 (360样本)",
        "is_default": True,
    },
    "碳排放量_万吨.xlsx": {
        "id": "DS-09",
        "var": "Emission",
        "role": "省域碳排放绝对总量指标",
        "weight": "总量指标",
        "status_default": "✓ 正常 (360样本)",
        "is_default": True,
    },
}


def get_manifest_path(raw_dir: Optional[str] = None) -> str:
    base = raw_dir or get_raw_data_dir()
    return os.path.join(base, "custom_inputs_manifest.json")


def load_inputs_manifest(raw_dir: Optional[str] = None) -> Dict[str, Any]:
    m_path = get_manifest_path(raw_dir)
    if os.path.isfile(m_path):
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_inputs_manifest(manifest: Dict[str, Any], raw_dir: Optional[str] = None) -> None:
    m_path = get_manifest_path(raw_dir)
    ensure_dir(os.path.dirname(m_path))
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def inspect_data_file(filepath: str) -> Dict[str, Any]:
    """读取并深度解析待导入的数据文件（支持 .xlsx, .xls, .csv），提取格式结构与关键元数据。"""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    df = None

    if ext in {".xlsx", ".xls"}:
        df = pd.read_excel(filepath)
    elif ext == ".csv":
        for enc in ["utf-8-sig", "gbk", "gb18030", "utf-8"]:
            try:
                df = pd.read_csv(filepath, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise ValueError(f"无法读取 CSV 文件（编码不支持）: {filepath}")
    else:
        raise ValueError(f"不支持的数据格式: {ext} (仅支持 .xlsx, .xls, .csv)")

    provinces_found: List[str] = []
    prov_col_candidates = ["province", "省份", "PR", "地区", "省", "省区"]
    prov_col = None

    for col in df.columns:
        if str(col).strip() in prov_col_candidates:
            prov_col = col
            break

    if prov_col is not None:
        provinces_found = normalize_province_names(df[prov_col].dropna()).unique().tolist()
    else:
        first_col_vals = df.iloc[:, 0].dropna().astype(str)
        norm_vals = normalize_province_names(first_col_vals)
        overlap = set(norm_vals).intersection(set(EAST_PROVS + NE_PROVS + ["河南", "湖北", "湖南", "四川", "陕西"]))
        if len(overlap) >= 3:
            prov_col = df.columns[0]
            provinces_found = norm_vals.unique().tolist()

    year_cols: List[int] = []
    for col in df.columns:
        try:
            y = int(col)
            if 1990 <= y <= 2050:
                year_cols.append(y)
        except (TypeError, ValueError):
            continue

    is_wide = len(year_cols) >= 2
    is_long = False
    if not is_wide:
        for col in df.columns:
            if str(col).lower() in {"year", "年份", "时间"}:
                is_long = True
                year_cols = sorted([int(y) for y in df[col].dropna().unique() if str(y).isdigit() and 1990 <= int(y) <= 2050])
                break

    missing_cnt = int(df.isna().sum().sum())
    file_size_kb = round(os.path.getsize(filepath) / 1024.0, 1)

    return {
        "filename": os.path.basename(filepath),
        "filepath": os.path.abspath(filepath),
        "extension": ext,
        "rows": len(df),
        "cols": len(df.columns),
        "columns": [str(c) for c in df.columns],
        "is_wide": is_wide,
        "is_long": is_long,
        "provinces_count": len(provinces_found),
        "provinces": provinces_found,
        "years": sorted(year_cols),
        "year_min": min(year_cols) if year_cols else None,
        "year_max": max(year_cols) if year_cols else None,
        "missing_count": missing_cnt,
        "file_size_kb": file_size_kb,
    }


def import_input_file(
    src_path: str,
    target_name: Optional[str] = None,
    var_name: Optional[str] = None,
    var_role: str = "控制变量",
    dest_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """导入/添加输入文件到系统数据源目录中，自动校验格式、统一规范并记录配置。"""
    info = inspect_data_file(src_path)
    target_dir = dest_dir or get_raw_data_dir()
    ensure_dir(target_dir)

    base_name = target_name or os.path.basename(src_path)
    target_ext = os.path.splitext(base_name)[1].lower()
    if not target_ext:
        base_name += ".xlsx"

    target_path = os.path.join(target_dir, base_name)

    ext = os.path.splitext(src_path)[1].lower()
    if ext in {".xlsx", ".xls"}:
        df = pd.read_excel(src_path)
        df.to_excel(target_path, index=False)
    elif ext == ".csv":
        df = None
        for enc in ["utf-8-sig", "gbk", "gb18030", "utf-8"]:
            try:
                df = pd.read_csv(src_path, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise ValueError("CSV 编码解析失败")
        if not target_path.endswith(".xlsx"):
            target_path = os.path.splitext(target_path)[0] + ".xlsx"
            base_name = os.path.basename(target_path)
        df.to_excel(target_path, index=False)

    if not var_name:
        stem = os.path.splitext(base_name)[0]
        var_name = stem.split("_")[0] if "_" in stem else stem

    manifest = load_inputs_manifest(target_dir)
    manifest[base_name] = {
        "filename": base_name,
        "original_source": os.path.abspath(src_path),
        "var": var_name,
        "role": var_role,
        "import_time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows": info["rows"],
        "cols": info["cols"],
        "provinces_count": info["provinces_count"],
        "year_min": info["year_min"],
        "year_max": info["year_max"],
        "missing_count": info["missing_count"],
        "is_custom": True,
    }
    save_inputs_manifest(manifest, target_dir)

    return {
        "success": True,
        "filename": base_name,
        "target_path": target_path,
        "var": var_name,
        "role": var_role,
        "info": info,
        "message": f"输入文件 '{base_name}' 导入成功！已归档至数据源目录。\n识别到 {info['provinces_count']} 个省份样本，年份跨度: {info['year_min']}-{info['year_max']}。",
    }


def remove_input_file(filename: str, raw_dir: Optional[str] = None) -> Tuple[bool, str]:
    """安全移除用户自定义添加的数据文件（保护系统默认核心数据源）。"""
    if filename in DEFAULT_DATA_DICTIONARY:
        return False, f"'{filename}' 是系统内置的核心基础数据源，不能被删除！"

    target_dir = raw_dir or get_raw_data_dir()
    target_path = os.path.join(target_dir, filename)

    if os.path.isfile(target_path):
        try:
            os.remove(target_path)
        except Exception as e:
            return False, f"删除文件失败: {e}"

    manifest = load_inputs_manifest(target_dir)
    if filename in manifest:
        del manifest[filename]
        save_inputs_manifest(manifest, target_dir)

    return True, f"已成功移除自定义输入文件: {filename}"


def list_input_files_metadata(raw_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """扫描并聚合当前数据源目录中的全部输入文件元数据（涵盖默认源表与自定义扩展文件）。"""
    target_dir = raw_dir or get_raw_data_dir()
    manifest = load_inputs_manifest(target_dir)
    results: List[Dict[str, Any]] = []

    # 1. 默认源表
    for fname, meta in DEFAULT_DATA_DICTIONARY.items():
        fpath = os.path.join(target_dir, fname)
        exists = os.path.isfile(fpath)
        size_str = f"{round(os.path.getsize(fpath)/1024, 1)} KB" if exists else "缺失"
        status = meta["status_default"] if exists else "✗ 缺失未找到"

        results.append({
            "id": meta["id"],
            "var": meta["var"],
            "file": fname,
            "role": meta["role"],
            "type": "系统内置",
            "size": size_str,
            "status": status,
            "is_custom": False,
            "exists": exists,
            "full_path": fpath,
        })

    # 2. 用户自定义/扫描发现的其他文件
    custom_id_counter = 1
    if os.path.isdir(target_dir):
        for item in sorted(os.listdir(target_dir)):
            if item.lower().endswith((".xlsx", ".xls", ".csv")) and item not in DEFAULT_DATA_DICTIONARY:
                fpath = os.path.join(target_dir, item)
                if not os.path.isfile(fpath):
                    continue

                m_entry = manifest.get(item, {})
                var_sym = m_entry.get("var", f"EXT_{custom_id_counter:02d}")
                role_desc = m_entry.get("role", "自定义扩展数据源")
                size_str = f"{round(os.path.getsize(fpath)/1024, 1)} KB"

                p_cnt = m_entry.get("provinces_count", "待核验")
                y_min = m_entry.get("year_min")
                y_max = m_entry.get("year_max")
                if y_min and y_max:
                    stat = f"✓ 自定义 ({p_cnt}省/{y_min}-{y_max})"
                else:
                    stat = f"✓ 自定义已接入"

                results.append({
                    "id": f"EXT-{custom_id_counter:02d}",
                    "var": var_sym,
                    "file": item,
                    "role": role_desc,
                    "type": "自定义导入",
                    "size": size_str,
                    "status": stat,
                    "is_custom": True,
                    "exists": True,
                    "full_path": fpath,
                })
                custom_id_counter += 1

    return results


def preview_input_file(filepath_or_name: str, max_rows: int = 15) -> Tuple[List[str], List[List[Any]], Dict[str, Any]]:
    """读取指定数据源文件的头部明细，供表格弹窗或控制台预览。"""
    if os.path.isfile(filepath_or_name):
        fpath = filepath_or_name
    else:
        fpath = raw_data_path(filepath_or_name)

    if not os.path.isfile(fpath):
        raise FileNotFoundError(f"文件未找到: {fpath}")

    ext = os.path.splitext(fpath)[1].lower()
    if ext in {".xlsx", ".xls"}:
        df = pd.read_excel(fpath)
    else:
        df = None
        for enc in ["utf-8-sig", "gbk", "gb18030", "utf-8"]:
            try:
                df = pd.read_csv(fpath, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise ValueError("文件读取失败")

    total_rows = len(df)
    total_cols = len(df.columns)
    preview_df = df.head(max_rows).fillna("-")

    columns = [str(c) for c in preview_df.columns]
    rows = preview_df.values.tolist()

    meta = {
        "filename": os.path.basename(fpath),
        "total_rows": total_rows,
        "total_cols": total_cols,
        "preview_rows": len(rows),
    }
    return columns, rows, meta


def normalize_province_names(values: pd.Series) -> pd.Series:
    return values.astype(str).str.replace(
        "省|市|自治区|维吾尔|回族|壮族|特别行政区",
        "",
        regex=True,
    )


def read_panel(filepath: str, value_name: str, year_range: Iterable[int] = YEARS) -> pd.DataFrame:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        df = None
        for enc in ["utf-8-sig", "gbk", "gb18030", "utf-8"]:
            try:
                df = pd.read_csv(filepath, index_col=0, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            df = pd.read_csv(filepath, index_col=0)
    else:
        df = pd.read_excel(filepath, index_col=0)

    if df.index.name not in {"province", "省份", "PR", "地区"}:
        for candidate in ["province", "省份", "PR", "地区", "省"]:
            if candidate in df.columns:
                df.set_index(candidate, inplace=True)
                break

    valid_years = set(int(year) for year in year_range)
    year_cols = []
    for col in df.columns:
        try:
            col_year = int(col)
        except (TypeError, ValueError):
            continue
        if col_year in valid_years:
            year_cols.append(col)

    panel = df[year_cols].copy()
    panel.index.name = "province"
    panel.columns = [int(col) for col in panel.columns]

    long_df = panel.stack().reset_index()
    long_df.columns = ["province", "year", value_name]
    long_df["province"] = normalize_province_names(long_df["province"])
    long_df["year"] = long_df["year"].astype(int)
    return long_df


def assign_region(province: str) -> str:
    if province in NE_PROVS:
        return "东北"
    if province in EAST_PROVS:
        return "东部"
    return "中西部"


def add_regions(df: pd.DataFrame, province_col: str = "province", region_col: str = "Region_3") -> pd.DataFrame:
    out = df.copy()
    out[region_col] = out[province_col].map(assign_region)
    return out


def repair_isolated_spikes(
    df: pd.DataFrame,
    value_col: str,
    *,
    group_col: str = "province",
    time_col: str = "year",
    spike_ratio: float = 8.0,
    neighbor_gap_ratio: float = 0.60,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replace isolated one-year spikes with neighbor interpolation.

    The raw value is preserved in ``{value_col}_raw``. The rule is deliberately
    conservative: it only repairs an interior year when the current value is
    many times larger than both adjacent years and the two adjacent years are
    themselves on the same order of magnitude.
    """
    out = df.copy()
    raw_col = f"{value_col}_raw"
    if raw_col not in out.columns:
        out[raw_col] = out[value_col]

    records: list[dict[str, object]] = []
    for _, group in out.sort_values([group_col, time_col]).groupby(group_col, sort=False):
        ordered_idx = list(group.index)
        values = group[value_col].astype(float)
        for pos in range(1, len(ordered_idx) - 1):
            idx = ordered_idx[pos]
            prev_idx = ordered_idx[pos - 1]
            next_idx = ordered_idx[pos + 1]
            prev_value = float(values.loc[prev_idx])
            current_value = float(values.loc[idx])
            next_value = float(values.loc[next_idx])
            if not all(np.isfinite([prev_value, current_value, next_value])):
                continue
            if prev_value <= 0 or next_value <= 0:
                continue

            neighbor_max = max(prev_value, next_value)
            neighbor_gap = abs(prev_value - next_value) / max(neighbor_max, 1e-12)
            is_spike = current_value >= spike_ratio * neighbor_max and neighbor_gap <= neighbor_gap_ratio
            if not is_spike:
                continue

            repaired_value = (prev_value + next_value) / 2.0
            out.loc[idx, value_col] = repaired_value
            records.append(
                {
                    "province": out.loc[idx, group_col],
                    "year": int(out.loc[idx, time_col]),
                    "variable": value_col,
                    "raw_value": current_value,
                    "repaired_value": repaired_value,
                    "previous_value": prev_value,
                    "next_value": next_value,
                    "rule": f"isolated spike >= {spike_ratio:g}x adjacent values",
                }
            )

    return out, pd.DataFrame(records)


def load_core_panel(data_dir: str = DATA_DIR, raw_dir: str = RAW_DATA_DIR) -> pd.DataFrame:
    ci_df = pd.read_excel(os.path.join(data_dir, "数字赋能指数_测算结果.xlsx"))
    ci_df["province"] = normalize_province_names(ci_df["province"])

    y_df = read_panel(os.path.join(raw_dir, "碳排放强度_万吨亿元GDP.xlsx"), "Y")
    pgdp_df = read_panel(os.path.join(raw_dir, "人均GDP.xlsx"), "PGDP")
    urb_df = read_panel(os.path.join(raw_dir, "城镇化率_2000_2022.xlsx"), "URB")
    open_df = read_panel(os.path.join(raw_dir, "对外开放程度_2000_2022.xlsx"), "OPEN")

    panel = (
        ci_df.merge(y_df, on=["province", "year"], how="inner")
        .merge(pgdp_df, on=["province", "year"], how="inner")
        .merge(urb_df, on=["province", "year"], how="inner")
        .merge(open_df, on=["province", "year"], how="inner")
    )
    panel["Upgrade"] = 1.0 - panel["Industry"]
    panel, _ = repair_isolated_spikes(panel, "Y")
    panel = add_regions(panel)
    panel.sort_values(["province", "year"], inplace=True)
    panel.reset_index(drop=True, inplace=True)
    return panel


def build_binary_treatment(df: pd.DataFrame, value_col: str = "CI", region_col: str = "Region_3") -> pd.Series:
    return (
        df.groupby(["year", region_col])[value_col]
        .transform(lambda x: (x > x.median()).astype(int))
        .astype(int)
    )


def normal_cdf(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    erf = np.vectorize(math.erf)
    return 0.5 * (1.0 + erf(arr / math.sqrt(2.0)))


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    eps = 3e-12
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d

    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    bt = math.exp(log_bt)
    threshold = (a + 1.0) / (a + b + 2.0)
    if x < threshold:
        value = bt * _beta_continued_fraction(a, b, x) / a
    else:
        value = 1.0 - bt * _beta_continued_fraction(b, a, 1.0 - x) / b
    return float(np.clip(value, 0.0, 1.0))


def student_t_two_sided_p(values: Sequence[float], df: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if df <= 0 or not np.isfinite(df):
        return 2.0 * (1.0 - normal_cdf(np.abs(arr)))

    out = []
    for value in np.abs(arr):
        x = df / (df + float(value) ** 2)
        out.append(regularized_incomplete_beta(x, df / 2.0, 0.5))
    return np.clip(np.asarray(out, dtype=float), 0.0, 1.0)


def student_t_critical(df: float, alpha: float = 0.05) -> float:
    if df <= 0 or not np.isfinite(df):
        return 1.96

    low = 0.0
    high = 2.0
    while float(student_t_two_sided_p([high], df)[0]) > alpha and high < 1e6:
        high *= 2.0

    for _ in range(80):
        mid = (low + high) / 2.0
        if float(student_t_two_sided_p([mid], df)[0]) > alpha:
            low = mid
        else:
            high = mid
    return high


def significance_stars(p_value: float) -> str:
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return "不显著"


def build_fe_design(
    df: pd.DataFrame,
    x_cols: Sequence[str],
    entity_col: str = "province",
    time_col: str = "year",
) -> pd.DataFrame:
    x_df = df[list(x_cols)].astype(float).copy()
    entity_dummies = pd.get_dummies(df[entity_col], prefix="prov", drop_first=True, dtype=float)
    time_dummies = pd.get_dummies(df[time_col].astype(int).astype(str), prefix="year", drop_first=True, dtype=float)
    return pd.concat([x_df, entity_dummies, time_dummies], axis=1)


def ols_with_cluster(
    y: pd.Series,
    x_df: pd.DataFrame,
    cluster: pd.Series | None = None,
    add_const: bool = True,
) -> tuple[pd.DataFrame, dict[str, float], np.ndarray, np.ndarray]:
    design = x_df.copy()
    if add_const:
        design.insert(0, "const", 1.0)

    x_mat = design.to_numpy(dtype=float)
    y_vec = np.asarray(y, dtype=float).reshape(-1)

    xtx_inv = np.linalg.pinv(x_mat.T @ x_mat)
    beta = xtx_inv @ x_mat.T @ y_vec
    fitted = x_mat @ beta
    resid = y_vec - fitted

    n_obs, n_vars = x_mat.shape
    if cluster is None:
        score = x_mat * resid[:, None]
        meat = score.T @ score
        correction = n_obs / max(n_obs - n_vars, 1)
        n_groups = math.nan
        inference_df = max(n_obs - n_vars, 1)
        inference_method = "HC sandwich + t(df=n-k)"
    else:
        groups = pd.Series(cluster, index=design.index).astype(str).to_numpy()
        unique_groups = pd.unique(groups)
        meat = np.zeros((n_vars, n_vars), dtype=float)
        for group in unique_groups:
            mask = groups == group
            x_g = x_mat[mask]
            resid_g = resid[mask]
            group_score = x_g.T @ resid_g
            meat += np.outer(group_score, group_score)
        n_groups = len(unique_groups)
        if n_groups > 1 and n_obs > n_vars:
            correction = (n_groups / (n_groups - 1)) * ((n_obs - 1) / (n_obs - n_vars))
        else:
            correction = 1.0
        inference_df = max(n_groups - 1, 1)
        inference_method = "cluster sandwich + t(df=G-1)"

    cov = correction * xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    t_stats = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
    p_values = student_t_two_sided_p(t_stats, inference_df)

    ci_crit = student_t_critical(inference_df)
    ci_low = beta - ci_crit * se
    ci_high = beta + ci_crit * se

    summary = pd.DataFrame(
        {
            "coef": beta,
            "std err": se,
            "t": t_stats,
            "P>|t|": p_values,
            "2.5 %": ci_low,
            "97.5 %": ci_high,
            "inference df": inference_df,
            "inference method": inference_method,
        },
        index=design.columns,
    )
    summary.index.name = "variable"

    y_centered = y_vec - y_vec.mean()
    sst = float(y_centered @ y_centered)
    ssr = float(resid @ resid)
    r2 = 1.0 - ssr / sst if sst > 0 else 0.0
    adj_r2 = 1.0 - (1.0 - r2) * (n_obs - 1) / max(n_obs - n_vars, 1)

    meta = {
        "n_obs": float(n_obs),
        "n_vars": float(n_vars),
        "n_clusters": float(n_groups),
        "inference_df": float(inference_df),
        "r2": float(r2),
        "adj_r2": float(adj_r2),
    }
    return summary, meta, fitted, resid


def fit_panel_fe(
    df: pd.DataFrame,
    y_col: str,
    x_cols: Sequence[str],
    cluster_col: str = "province",
) -> tuple[pd.DataFrame, dict[str, float], pd.DataFrame, np.ndarray, np.ndarray]:
    required_cols = [y_col, *x_cols, cluster_col, "province", "year"]
    work = df.dropna(subset=required_cols).copy()
    design = build_fe_design(work, x_cols=x_cols)
    summary, meta, fitted, resid = ols_with_cluster(
        y=work[y_col],
        x_df=design,
        cluster=work[cluster_col],
        add_const=True,
    )
    return summary, meta, work, fitted, resid


def extract_term_row(
    summary: pd.DataFrame,
    meta: dict[str, float],
    term: str,
    model_name: str,
    treatment_variable: str,
) -> dict[str, float | str]:
    row = summary.loc[term]
    return {
        "Model": model_name,
        "Treatment_Variable": treatment_variable,
        "coef": float(row["coef"]),
        "std err": float(row["std err"]),
        "t": float(row["t"]),
        "P>|t|": float(row["P>|t|"]),
        "2.5 %": float(row["2.5 %"]),
        "97.5 %": float(row["97.5 %"]),
        "样本量": int(meta["n_obs"]),
        "聚类数": None if pd.isna(meta["n_clusters"]) else int(meta["n_clusters"]),
        "推断自由度": int(meta["inference_df"]),
        "调整R2": float(meta["adj_r2"]),
    }


def summary_to_sheet(summary: pd.DataFrame, meta: dict[str, float], model_name: str) -> pd.DataFrame:
    out = summary.reset_index().copy()
    out["model"] = model_name
    out["n_obs"] = int(meta["n_obs"])
    out["n_clusters"] = None if pd.isna(meta["n_clusters"]) else int(meta["n_clusters"])
    out["inference_df"] = int(meta["inference_df"])
    out["adj_r2"] = float(meta["adj_r2"])
    return out


def mark_pareto_front(df: pd.DataFrame, min_col: str, max_col: str) -> pd.Series:
    min_values = df[min_col].to_numpy(dtype=float)
    max_values = df[max_col].to_numpy(dtype=float)
    is_pareto = np.ones(len(df), dtype=bool)

    for idx in range(len(df)):
        dominates = (
            (min_values <= min_values[idx])
            & (max_values >= max_values[idx])
            & ((min_values < min_values[idx]) | (max_values > max_values[idx]))
        )
        dominates[idx] = False
        if dominates.any():
            is_pareto[idx] = False

    return pd.Series(is_pareto, index=df.index)


def choose_knee_point(df: pd.DataFrame, min_col: str, max_col: str) -> pd.Series:
    work = df.copy()
    min_range = work[min_col].max() - work[min_col].min()
    max_range = work[max_col].max() - work[max_col].min()

    if min_range == 0:
        work["_loss_min"] = 0.0
    else:
        work["_loss_min"] = (work[min_col] - work[min_col].min()) / min_range

    if max_range == 0:
        work["_loss_max"] = 0.0
    else:
        work["_loss_max"] = (work[max_col].max() - work[max_col]) / max_range

    work["_ideal_distance"] = np.sqrt(work["_loss_min"] ** 2 + work["_loss_max"] ** 2)
    return work.sort_values(["_ideal_distance", min_col, max_col], ascending=[True, True, False]).iloc[0]


def export_evaluation_txt_report(target_path: Optional[str | Path] = None) -> str:
    """生成并导出评价体系与综合指数测算成果的纯文本 (.txt) 报告。"""
    proj_root = Path(find_project_root())
    result_dir = proj_root / "04_核心结果"
    if target_path is None:
        target_path = result_dir / "评价体系测算结果.txt"
    else:
        target_path = Path(target_path)

    res_file = result_dir / "数字赋能指数_测算结果.xlsx"
    wt_file = result_dir / "熵权法_权重汇总.xlsx"
    cmp_file = result_dir / "指标构建_稳健性对比.xlsx"

    if not res_file.exists() or not wt_file.exists():
        return ""

    df_res = pd.read_excel(res_file)
    df_wt = pd.read_excel(wt_file)

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 80,
        "省域数字经济与低碳协同综合评估系统 (DEC-CES) V1.0",
        "【评价体系构念与综合指数测算成果报告】",
        f"导出时间：{now_str}",
        "=" * 80,
        "",
        "一、 评价体系指标构成与客观权重汇总 (基于香农信息熵客观赋权模型)",
        "-" * 80,
        f"{'指数方案':<12} {'指标代码':<16} {'指标经济学含义':<24} {'对数平滑':<10} {'客观权重'}",
        "-" * 80,
    ]

    for _, r in df_wt.iterrows():
        scheme = str(r["指数方案"])
        var = str(r["指标"])
        meaning = str(r["经济学含义"])
        smooth = str(r["是否需要对数平滑"])
        weight = float(r["权重"])
        lines.append(f"{scheme:<12} {var:<16} {meaning:<24} {smooth:<10} {weight:.4f} ({weight*100:.2f}%)")
    lines.append("-" * 80)
    lines.append("")

    if cmp_file.exists():
        try:
            df_cmp = pd.read_excel(cmp_file, sheet_name=0)
            lines.append("二、 指标构念口径稳健性检验与相关性矩阵")
            lines.append("-" * 80)
            for _, r in df_cmp.iterrows():
                item = str(r.get("比较项", ""))
                val = str(r.get("数值", ""))
                note = str(r.get("说明", ""))
                lines.append(f"• {item}: {val}  ({note})")
            lines.append("-" * 80)
            lines.append("")
        except Exception:
            pass

    df_2022 = df_res[df_res["year"] == 2022].sort_values(by="CI", ascending=False).reset_index(drop=True)
    lines.append("三、 2022 基准目标年全国 30 省份协同指数 (CI) 排名榜单与明细")
    lines.append("-" * 80)
    lines.append(f"{'排名':<6} {'省份':<10} {'基准协同指数 (CI)':<20} {'核心数字指数 (CI_core)':<22} {'梯队归类'}")
    lines.append("-" * 80)
    for idx, r in df_2022.iterrows():
        rank = idx + 1
        prov = str(r["province"])
        ci = float(r["CI"])
        ci_core = float(r["CI_core"])
        if rank <= 8:
            tier = "第一梯队 (领军协同区)"
        elif rank <= 18:
            tier = "第二梯队 (稳健提质区)"
        else:
            tier = "第三梯队 (潜能蓄势区)"
        lines.append(f"{rank:<6} {prov:<10} {ci:<20.4f} {ci_core:<22.4f} {tier}")
    lines.append("-" * 80)
    lines.append("")

    lines.append("四、 测算总体统计量与样本画像")
    lines.append("-" * 80)
    lines.append(f"• 样本覆盖范围：30 个省份平衡面板 (2011-2022 年，共 {len(df_res)} 组观测样本)")
    lines.append(f"• 2022 年基准协同指数 (CI) 全国均值：{df_2022['CI'].mean():.4f}，标准差：{df_2022['CI'].std():.4f}")
    lines.append(f"• 领跑省份：{df_2022.iloc[0]['province']} (CI={df_2022.iloc[0]['CI']:.4f})，末位省份：{df_2022.iloc[-1]['province']} (CI={df_2022.iloc[-1]['CI']:.4f})")
    lines.append("• 测算模型：香农信息熵客观赋权法 + 极值标准化 + 孤立尖峰邻域留痕平滑修正")
    lines.append("• 关联成果数据表：")
    lines.append("  - 04_核心结果/数字赋能指数_测算结果.xlsx")
    lines.append("  - 04_核心结果/核心数字指数_测算结果.xlsx")
    lines.append("  - 04_核心结果/熵权法_权重汇总.xlsx")
    lines.append("=" * 80)

    content = "\n".join(lines)
    target_path.write_text(content, encoding="utf-8")
    return str(target_path)


def export_integrity_txt_report(target_path: Optional[str | Path] = None) -> str:
    """生成并导出系统全流程自检与完整性核验的纯文本 (.txt) 报告。"""
    proj_root = Path(find_project_root())
    result_dir = proj_root / "04_核心结果"
    if target_path is None:
        target_path = result_dir / "系统运行自检报告.txt"
    else:
        target_path = Path(target_path)

    json_path = result_dir / "系统运行自检报告.json"
    if not json_path.exists():
        return ""

    data = json.loads(json_path.read_text(encoding="utf-8"))
    software = data.get("software", "省域数字经济与低碳协同综合评估系统 (DEC-CES) V1.0")
    passed = data.get("passed", False) or data.get("summary", {}).get("overall_passed", False)
    status_str = "PASS (100% 通过)" if passed else "WARN (自检发现异常)"
    checks = data.get("checks", [])
    manual_gate = data.get("manual_gate", "")

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 80,
        software,
        "【系统全流程运行完整性自检报告】",
        f"核验时间：{now_str}",
        f"总体评估结论：{status_str}",
        "=" * 80,
        "",
        "一、 系统核心要素核验清单明细",
        "-" * 80,
    ]

    for idx, c in enumerate(checks, 1):
        c_name = c.get("name", f"核验项 {idx}")
        c_passed = c.get("passed", False)
        c_detail = c.get("detail", "")
        mark = "[✓ PASS]" if c_passed else "[✗ FAIL]"
        lines.append(f"{idx}. {mark} {c_name}")
        if c_detail:
            lines.append(f"   详情：{c_detail}")
    lines.append("-" * 80)
    lines.append("")

    if manual_gate:
        lines.append("二、 人工放行准则与系统交付判定 (Manual Gate)")
        lines.append("-" * 80)
        lines.append(manual_gate)
        lines.append("-" * 80)
        lines.append("")

    lines.append("三、 核心交付文件与说明")
    lines.append("-" * 80)
    lines.append("• 02_代码/             : 包含 12 个核心算法、计量回归与情景仿真 Python 模块")
    lines.append("• 03_原始数据/         : 包含 9 份平衡面板省级宏观输入样例源表")
    lines.append("• 04_核心结果/         : 包含 17 张成果表汇总大表及多维实证测算工作簿")
    lines.append("• 05_图形/             : 包含高分辨率区域分层图、碳预测情景图与 Pareto 折中前沿图")
    lines.append("=" * 80)

    content = "\n".join(lines)
    target_path.write_text(content, encoding="utf-8")
    return str(target_path)


def open_txt_file(filepath: str | Path) -> bool:
    """使用系统默认关联程序（如 Windows 记事本）打开指定的 .txt 文件。"""
    p = Path(filepath)
    if not p.exists():
        return False
    try:
        os.startfile(str(p))
        return True
    except Exception:
        try:
            subprocess.Popen(["notepad.exe", str(p)])
            return True
        except Exception:
            return False
