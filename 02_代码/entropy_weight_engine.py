# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：entropy_weight_engine (多维指标赋权与综合指数测算引擎)
功能描述：
1. 实现客观赋权数学模型：基于香农信息熵 (Shannon Information Entropy) 计算各子指标离散度与信息效用价值。
2. 双构念指数解算：测算涵盖技术、活跃度、能效与结构转型的“基准协同指数 (CI)”与聚焦技术能力的“核心数字指数 (CI_core)”。
3. 极差标准化与下限对数平滑处理，有效消除量纲与绝对极值对赋权结果的扰动。
4. 提供面向对象的工程级计算类 EntropyWeightEngine，支持独立配置、批量测算与全套 Excel 成果导出。
================================================================================
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

from model_utils import DATA_DIR, ensure_dir, export_evaluation_txt_report, raw_data_path, result_path


RESULT_FILE = result_path("数字赋能指数_测算结果.xlsx")
CORE_RESULT_FILE = result_path("核心数字指数_测算结果.xlsx")
WEIGHT_FILE = result_path("熵权法_权重汇总.xlsx")
INDEX_COMPARE_FILE = result_path("指标构建_稳健性对比.xlsx")
DEFAULT_YEARS = range(2011, 2023)


def minmax(series: pd.Series) -> pd.Series:
    """对序列执行 0-1 极差标准化处理。

    Args:
        series: 原始浮点型数据序列。

    Returns:
        pd.Series: 标准化至 [0, 1] 区间的数据序列。
    """
    series_float = series.astype(float)
    series_min = series_float.min()
    series_max = series_float.max()
    if pd.isna(series_min) or pd.isna(series_max) or series_max == series_min:
        return pd.Series(np.zeros(len(series_float)), index=series.index, dtype=float)
    return (series_float - series_min) / (series_max - series_min)


def read_panel(
    filepath: str,
    value_name: str,
    year_range: Iterable[int] = DEFAULT_YEARS,
) -> pd.DataFrame:
    """读取宽表格式的省级面板 Excel 文件并转换为长表格式。

    Args:
        filepath: Excel 文件绝对路径。
        value_name: 指标变量名称。
        year_range: 有效年份迭代区间。

    Returns:
        pd.DataFrame: 包含 province, year 与指标列的长表 DataFrame。
    """
    df = pd.read_excel(filepath, index_col=0)
    year_set = set(int(y) for y in year_range)
    year_cols: List[Any] = []
    for col in df.columns:
        try:
            year = int(col)
        except (TypeError, ValueError):
            continue
        if year in year_set:
            year_cols.append(col)

    panel = df[year_cols].copy()
    panel.index.name = "province"
    panel.columns = [int(col) for col in panel.columns]

    long_df = panel.stack().reset_index()
    long_df.columns = ["province", "year", value_name]
    long_df["province"] = long_df["province"].astype(str).str.replace(
        "省|市|自治区|维吾尔|回族|壮族|特别行政区",
        "",
        regex=True,
    )
    long_df["year"] = long_df["year"].astype(int)
    return long_df


def calc_entropy_weights(norm_df: pd.DataFrame, eps: float = 1e-10) -> Dict[str, float]:
    """基于客观信息熵理论计算各特征维度的相对权重。

    Args:
        norm_df: 已经归一化/极差标准化后的指标特征矩阵。
        eps: 避免 log(0) 的极小数值平滑项。

    Returns:
        Dict[str, float]: 各列特征指标对应的客观信息熵权重字典。
    """
    weights: Dict[str, float] = {}
    m = len(norm_df)
    k = 1.0 / np.log(m)

    redundancy: Dict[str, float] = {}
    for col in norm_df.columns:
        p = (norm_df[col] + eps) / (norm_df[col] + eps).sum()
        entropy = float(-k * (p * np.log(p)).sum())
        redundancy[col] = 1.0 - entropy

    denom = sum(redundancy.values())
    for col, value in redundancy.items():
        weights[col] = value / denom if denom else 0.0
    return weights


def build_entropy_index(
    base_panel: pd.DataFrame,
    feature_defs: Sequence[Tuple[str, pd.Series, str, str]],
    index_col: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """根据特征定义列表计算客观熵权并合成加权综合指数。

    Args:
        base_panel: 基础面板数据集。
        feature_defs: 特征元组列表 [(特征名, 原始序列, 经济含义, 平滑标识)]。
        index_col: 合成指数的目标列名（如 CI 或 CI_core）。

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 合成指数后的面板与权重汇总记录。
    """
    work = base_panel.copy()
    norm_cols: List[str] = []
    weight_rows: List[Dict[str, Any]] = []

    for feature_name, raw_series, meaning, smooth_flag in feature_defs:
        work[feature_name] = raw_series.astype(float)
        norm_col = f"{feature_name}_norm"
        work[norm_col] = minmax(work[feature_name])
        norm_cols.append(norm_col)
        weight_rows.append(
            {
                "指数方案": index_col,
                "指标": feature_name,
                "经济学含义": meaning,
                "是否需要对数平滑": smooth_flag,
            }
        )

    weights = calc_entropy_weights(work[norm_cols])
    work[index_col] = 0.0
    for norm_col in norm_cols:
        feature_name = norm_col.replace("_norm", "")
        weight = weights[norm_col]
        work[index_col] = work[index_col] + weight * work[norm_col]
        for row in weight_rows:
            if row["指标"] == feature_name:
                row["权重"] = weight
                break

    return work, pd.DataFrame(weight_rows)


class EntropyWeightEngine:
    """多维指标赋权与综合指数测算工程类。

    封装香农信息熵权重矩阵解算、指标标准化与多构念指数生成的核心管道。
    """

    def __init__(self, years: Iterable[int] = DEFAULT_YEARS):
        """初始化测算引擎并配置研究年份区间。"""
        self.years = list(years)
        self.panel: pd.DataFrame | None = None
        self.base_weight_df: pd.DataFrame | None = None
        self.core_weight_df: pd.DataFrame | None = None
        self.compare_df: pd.DataFrame | None = None

    def load_raw_indicators(self) -> pd.DataFrame:
        """加载原始灯光、数字经济、能源与产业结构四大基础表并合并清洗。"""
        ntl = read_panel(raw_data_path("省份等级的灯光值_平均值.xlsx"), "NTL", self.years)
        tech = read_panel(raw_data_path("数字经济指数_2011_2022.xlsx"), "Tech", self.years)
        energy = read_panel(raw_data_path("能源消费量_万吨标煤.xlsx"), "Energy", self.years)
        industry = read_panel(raw_data_path("产业结构高级化_第二产业占比.xlsx"), "Industry", self.years)

        panel = (
            tech.merge(ntl, on=["province", "year"], how="inner")
            .merge(energy, on=["province", "year"], how="inner")
            .merge(industry, on=["province", "year"], how="inner")
        )
        panel.dropna(subset=["Tech", "NTL", "Energy", "Industry"], inplace=True)
        panel = panel[panel["year"].between(min(self.years), max(self.years))].copy()
        panel.sort_values(["province", "year"], inplace=True)
        panel.reset_index(drop=True, inplace=True)
        self.panel = panel
        return self.panel

    def compute_indices(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """测算基准协同指数 CI 与核心数字指数 CI_core 并对比秩相关系数。"""
        if self.panel is None:
            self.load_raw_indicators()
        assert self.panel is not None

        # 基线对照
        old_raw = (self.panel["NTL"] * self.panel["Tech"]) / self.panel["Energy"]
        self.panel["CI_old_proxy"] = np.log(old_raw / old_raw.min())

        base_feature_defs = [
            ("X1_Tech", np.log(self.panel["Tech"] + 1.0), "代表数字赋能技术能力", "是"),
            ("X2_NTL", np.log(self.panel["NTL"] + 1.0), "代表经济活动数字化活跃度", "是"),
            ("X3_EnergyEff", np.log(1.0 / self.panel["Energy"] + 1e-8), "代表低碳用能效率", "是"),
            ("X4_Upgrade", 1.0 - self.panel["Industry"], "代表产业结构高级化", "否"),
        ]
        self.panel, self.base_weight_df = build_entropy_index(self.panel, base_feature_defs, "CI")

        core_feature_defs = [
            ("C1_Tech", np.log(self.panel["Tech"] + 1.0), "核心数字技术能力", "是"),
            ("C2_NTL", np.log(self.panel["NTL"] + 1.0), "核心数字活跃度代理", "是"),
        ]
        self.panel, self.core_weight_df = build_entropy_index(self.panel, core_feature_defs, "CI_core")

        spearman_like = self.panel["CI_old_proxy"].rank(method="average").corr(
            self.panel["CI"].rank(method="average"),
            method="pearson",
        )
        base_core_corr = self.panel["CI"].rank(method="average").corr(
            self.panel["CI_core"].rank(method="average"),
            method="pearson",
        )

        self.compare_df = pd.DataFrame(
            [
                {
                    "比较项": "CI 与基线代理排序相关",
                    "数值": spearman_like,
                    "含义": "检验重构方案的一致性与稳定性",
                },
                {
                    "比较项": "CI 与 CI_core 排序相关",
                    "数值": base_core_corr,
                    "含义": "衡量协同口径与严格数字口径之间的一致性",
                },
                {
                    "比较项": "CI 均值",
                    "数值": float(self.panel["CI"].mean()),
                    "含义": "基准协同指数样本均值",
                },
                {
                    "比较项": "CI_core 均值",
                    "数值": float(self.panel["CI_core"].mean()),
                    "含义": "核心数字指数样本均值",
                },
            ]
        )
        return self.panel, self.base_weight_df, self.core_weight_df

    def export_results(self) -> None:
        """导出全套指标测算报表、权重汇总及口径对比分析表。"""
        if self.panel is None or self.base_weight_df is None or self.core_weight_df is None:
            self.compute_indices()
        assert self.panel is not None
        assert self.base_weight_df is not None
        assert self.core_weight_df is not None
        assert self.compare_df is not None

        ensure_dir(DATA_DIR)

        result_cols = [
            "province",
            "year",
            "NTL",
            "Tech",
            "Energy",
            "Industry",
            "CI",
            "CI_core",
        ]
        feature_cols = [
            "X1_Tech",
            "X1_Tech_norm",
            "X2_NTL",
            "X2_NTL_norm",
            "X3_EnergyEff",
            "X3_EnergyEff_norm",
            "X4_Upgrade",
            "X4_Upgrade_norm",
            "C1_Tech",
            "C1_Tech_norm",
            "C2_NTL",
            "C2_NTL_norm",
        ]
        self.panel[result_cols + feature_cols].to_excel(RESULT_FILE, index=False)
        self.panel[["province", "year", "Tech", "NTL", "C1_Tech", "C1_Tech_norm", "C2_NTL", "C2_NTL_norm", "CI_core"]].to_excel(
            CORE_RESULT_FILE,
            index=False,
        )

        weight_df = pd.concat([self.base_weight_df, self.core_weight_df], ignore_index=True)
        weight_df.to_excel(WEIGHT_FILE, index=False)

        with pd.ExcelWriter(INDEX_COMPARE_FILE, engine="openpyxl") as writer:
            self.compare_df.to_excel(writer, sheet_name="口径对比", index=False)
            self.base_weight_df.to_excel(writer, sheet_name="基准协同指数权重", index=False)
            self.core_weight_df.to_excel(writer, sheet_name="核心数字指数权重", index=False)

        export_evaluation_txt_report()
        print(f"指标测算完成，已输出：{RESULT_FILE} 及评价体系测算结果.txt")


def main() -> None:
    """模块独立执行入口。"""
    engine = EntropyWeightEngine()
    engine.load_raw_indicators()
    engine.compute_indices()

    assert engine.panel is not None
    assert engine.compare_df is not None
    assert engine.base_weight_df is not None
    assert engine.core_weight_df is not None

    spearman_like = engine.compare_df.loc[engine.compare_df["比较项"] == "CI 与基线代理排序相关", "数值"].iloc[0]
    base_core_corr = engine.compare_df.loc[engine.compare_df["比较项"] == "CI 与 CI_core 排序相关", "数值"].iloc[0]

    print("【1. 指标构建对比】")
    print("基准协同指数 CI 使用 4 个子指标：Tech / NTL / EnergyEff / Upgrade")
    print("核心数字指数 CI_core 使用 2 个子指标：Tech / NTL")
    print("\n【2. 基准协同指数与旧版代理排序相关】")
    print(f"CI vs old proxy (Spearman-like) = {spearman_like:.4f}")
    print("\n【3. 基准协同指数与核心数字指数排序相关】")
    print(f"CI vs CI_core (Spearman-like) = {base_core_corr:.4f}")

    print("\n【4. 基准协同指数权重】")
    print(engine.base_weight_df[["指标", "权重"]].to_string(index=False))
    print("\n【5. 核心数字指数权重】")
    print(engine.core_weight_df[["指标", "权重"]].to_string(index=False))

    engine.export_results()


if __name__ == "__main__":
    main()
