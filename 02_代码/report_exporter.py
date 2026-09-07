# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：report_exporter (综合评估指标与多维数据报表导出模块)
功能描述：
1. 自动化多源成果汇聚：系统化提取指标测算、主效应计量、区域异质性分层及多情景仿真预测数据。
2. 生成交付级汇总工作簿：整合输出“表0_核心结论”至“表16_结果时间戳”共 17 个标准化工作表。
3. 自动化数值一致性与数据时间戳审计：校验终端预测值与各情景明细表的微差偏差，确保数据绝对可追溯。
4. 提供面向对象的工程级报表导出类 ComprehensiveReportExporter，支持模块调用与独立执行。
================================================================================
"""

from __future__ import annotations

from datetime import datetime
import os
import shutil
from typing import Any, Dict, List, Optional

import pandas as pd

from model_utils import DATA_DIR, SIM_DIR, ensure_dir


OUTPUT_FILE = os.path.join(DATA_DIR, "综合评估与仿真分析汇总表.xlsx")
POLICY_SUMMARY_FILE = os.path.join(SIM_DIR, "政策仿真最终结果.xlsx")
EMPIRICAL_BOOK = os.path.join(DATA_DIR, "实证结果_完整回归表.xlsx")
POLICY_ZONE_FILE = os.path.join(SIM_DIR, "政策分型_省份清单.xlsx")
STRATEGY_COMPARE_FILE = os.path.join(SIM_DIR, "策略组合_对比结果.xlsx")
CONSTRUCT_FILE = os.path.join(DATA_DIR, "实证结果_构念稳健性.xlsx")


def read_excel_if_exists(path: str) -> Optional[pd.DataFrame]:
    """若指定路径的 Excel 文件存在则安全读取，否则返回 None。"""
    return pd.read_excel(path) if os.path.exists(path) else None


def read_sheet_if_exists(path: str, sheet_name: str) -> Optional[pd.DataFrame]:
    """若指定路径的 Excel 文件及其子表存在则安全读取，否则返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        return pd.read_excel(path, sheet_name=sheet_name)
    except Exception:
        return None


def get_mtime(path: str) -> Optional[str]:
    """获取文件最后修改时间的格式化字符串。"""
    if not os.path.exists(path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")


def scenario_value(df: pd.DataFrame | None, year: int, value_col: str = "Y_pred") -> Optional[float]:
    """提取特定情景预测表在目标年份的预测数值。"""
    if df is None or "year" not in df.columns or value_col not in df.columns:
        return None
    matched = df[df["year"] == year]
    if matched.empty:
        return None
    return float(matched[value_col].iloc[0])


def pick_existing_column(df: pd.DataFrame | None, candidates: List[str]) -> Optional[str]:
    """从候选列名列表中选取 DataFrame 中首个存在的字段。"""
    if df is None:
        return None
    for column in candidates:
        if column in df.columns:
            return column
    return None


def build_scenario_terminal_table() -> pd.DataFrame:
    """构建基准、加速、统一政策、定向协同及 Pareto 最优五大情景的终端数值对比表。"""
    scenario_map = {
        "基准情景": read_excel_if_exists(os.path.join(SIM_DIR, "基准情景.xlsx")),
        "数字加速情景": read_excel_if_exists(os.path.join(SIM_DIR, "数字加速情景.xlsx")),
        "政策强化情景": read_excel_if_exists(os.path.join(SIM_DIR, "政策强化情景.xlsx")),
        "定向协同情景": read_excel_if_exists(os.path.join(SIM_DIR, "定向协同情景.xlsx")),
        "Pareto最优路径": read_excel_if_exists(os.path.join(SIM_DIR, "Pareto最优路径.xlsx")),
    }

    rows: List[Dict[str, Any]] = []
    for year in [2022, 2035]:
        row: Dict[str, Any] = {"年份": year}
        for scenario_name, df in scenario_map.items():
            row[f"{scenario_name}_碳强度"] = scenario_value(df, year)
        rows.append(row)
    return pd.DataFrame(rows)


def build_policy_summary() -> pd.DataFrame:
    """构建或加载政策仿真综合汇总数据表。"""
    summary_df = read_excel_if_exists(POLICY_SUMMARY_FILE)
    if summary_df is not None and not summary_df.empty:
        return summary_df

    strategy_compare = read_excel_if_exists(STRATEGY_COMPARE_FILE)
    if strategy_compare is not None and not strategy_compare.empty:
        strategy_compare.to_excel(POLICY_SUMMARY_FILE, index=False)
        return strategy_compare

    return pd.DataFrame()


def build_nsga_table(policy_summary_df: pd.DataFrame) -> pd.DataFrame:
    """提取 Pareto 最优前沿拐点 (Knee Point) 政策筛选推荐决策表。"""
    if policy_summary_df is None or policy_summary_df.empty:
        return pd.DataFrame(columns=["指标名称", "数值", "含义"])

    nsga_row = policy_summary_df[policy_summary_df["情景"].isin(["Pareto最优路径", "NSGA-II最优路径"])]
    if nsga_row.empty:
        return pd.DataFrame(columns=["指标名称", "数值", "含义"])

    row = nsga_row.iloc[0]
    return pd.DataFrame(
        {
            "指标名称": ["最优策略类型", "最优数字投入倍数", "最优产业升级增量", "2035年预期碳排放强度"],
            "数值": [
                row.get("策略类型"),
                row.get("数字投入倍数"),
                row.get("产业升级增量"),
                row.get("2035碳强度预测"),
            ],
            "含义": [
                "Pareto 前沿折中解所属策略族",
                "Pareto 前沿折中解对应的数字投入倍数",
                "Pareto 前沿折中解对应的产业升级增量",
                "最优政策路径下的终值预测",
            ],
        }
    )


def build_consistency_sheet(policy_summary_df: pd.DataFrame) -> pd.DataFrame:
    """自动化比对汇总表与情景推演独立工作簿之间的终端数值一致性。"""
    checks: List[Dict[str, Any]] = []
    scenario_file_map = {
        "基准情景": "基准情景.xlsx",
        "数字加速情景": "数字加速情景.xlsx",
        "政策强化情景": "政策强化情景.xlsx",
        "定向协同情景": "定向协同情景.xlsx",
        "Pareto最优路径": "Pareto最优路径.xlsx",
    }

    for scenario_name, filename in scenario_file_map.items():
        df = read_excel_if_exists(os.path.join(SIM_DIR, filename))
        summary_value = None
        if policy_summary_df is not None and not policy_summary_df.empty and "情景" in policy_summary_df.columns:
            matched = policy_summary_df[policy_summary_df["情景"] == scenario_name]
            if not matched.empty:
                summary_value = float(matched["2035碳强度预测"].iloc[0])
        scenario_terminal = scenario_value(df, 2035)
        delta = None
        if summary_value is not None and scenario_terminal is not None:
            delta = summary_value - scenario_terminal

        checks.append(
            {
                "校验项": scenario_name,
                "汇总表_2035碳强度": summary_value,
                "情景文件_2035碳强度": scenario_terminal,
                "差值": delta,
                "是否一致": "是" if delta is not None and abs(delta) < 1e-9 else "否",
            }
        )

    return pd.DataFrame(checks)


def build_metadata_sheet() -> pd.DataFrame:
    """采集所有核心成果文件的物理存在性与修改时间戳凭据。"""
    tracked_files = [
        os.path.join(DATA_DIR, "熵权法_权重汇总.xlsx"),
        os.path.join(DATA_DIR, "实证结果_连续与离散比较.xlsx"),
        os.path.join(DATA_DIR, "实证结果_区域异质性.xlsx"),
        os.path.join(DATA_DIR, "实证结果_完整回归表.xlsx"),
        os.path.join(DATA_DIR, "实证结果_稳健性矩阵.xlsx"),
        os.path.join(DATA_DIR, "实证结果_区域稳定性.xlsx"),
        os.path.join(DATA_DIR, "实证结果_构念稳健性.xlsx"),
        os.path.join(DATA_DIR, "省域异质性_省份斜率.xlsx"),
        os.path.join(SIM_DIR, "基准情景.xlsx"),
        os.path.join(SIM_DIR, "数字加速情景.xlsx"),
        os.path.join(SIM_DIR, "政策强化情景.xlsx"),
        os.path.join(SIM_DIR, "定向协同情景.xlsx"),
        os.path.join(SIM_DIR, "Pareto最优路径.xlsx"),
        os.path.join(SIM_DIR, "政策仿真最终结果.xlsx"),
        os.path.join(SIM_DIR, "多目标优化_前沿对比数据.xlsx"),
        os.path.join(SIM_DIR, "多目标优化_寻优边界单调性测试.xlsx"),
        os.path.join(SIM_DIR, "政策分型_省份清单.xlsx"),
        os.path.join(SIM_DIR, "策略组合_对比结果.xlsx"),
    ]

    rows: List[Dict[str, Any]] = []
    for path in tracked_files:
        rows.append(
            {
                "文件": os.path.basename(path),
                "是否存在": "是" if os.path.exists(path) else "否",
                "最后修改时间": get_mtime(path),
            }
        )
    return pd.DataFrame(rows)


class ComprehensiveReportExporter:
    """多维数据与综合评估报表导出工程类。"""

    def __init__(self, data_dir: str = DATA_DIR, sim_dir: str = SIM_DIR):
        self.data_dir = data_dir
        self.sim_dir = sim_dir
        self.output_file = OUTPUT_FILE

    def export_master_workbook(self) -> str:
        """执行全量报表聚合并输出包含表0至表16的多工作表 Excel。"""
        ensure_dir(self.data_dir)
        pol_summary_df = build_policy_summary()

        with pd.ExcelWriter(self.output_file, engine="openpyxl") as writer:
            key_findings = read_sheet_if_exists(EMPIRICAL_BOOK, "关键结论")
            if key_findings is not None:
                key_findings.to_excel(writer, sheet_name="表0_核心结论", index=False)

            ci_weights = read_excel_if_exists(os.path.join(self.data_dir, "熵权法_权重汇总.xlsx"))
            if ci_weights is not None:
                ci_weights.to_excel(writer, sheet_name="表1_CI构建权重", index=False)

            province_diag = read_excel_if_exists(os.path.join(self.data_dir, "省域异质性_省份斜率.xlsx"))
            if province_diag is not None:
                province_diag.to_excel(writer, sheet_name="表2_省域异质性补充诊断", index=False)

            comp_df = read_excel_if_exists(os.path.join(self.data_dir, "实证结果_连续与离散比较.xlsx"))
            region_df = read_excel_if_exists(os.path.join(self.data_dir, "实证结果_区域异质性.xlsx"))

            if comp_df is not None:
                rename_dict = {
                    "coef": "效应估计值",
                    "std err": "标准误",
                    "t": "T统计量",
                    "P>|t|": "P值",
                    "2.5 %": "置信区间下界(2.5%)",
                    "97.5 %": "置信区间上界(97.5%)",
                }
                comp_df = comp_df.rename(columns=rename_dict)
                comp_df.to_excel(writer, sheet_name="表3_实证识别结果", startrow=0, index=False)

                if region_df is not None:
                    worksheet = writer.sheets["表3_实证识别结果"]
                    worksheet.cell(row=len(comp_df) + 3, column=1, value="区域异质性连续效应：")
                    region_df.to_excel(writer, sheet_name="表3_实证识别结果", startrow=len(comp_df) + 4, index=False)

            robust_df = read_sheet_if_exists(EMPIRICAL_BOOK, "稳健性矩阵")
            if robust_df is not None:
                robust_df.to_excel(writer, sheet_name="表4_稳健性矩阵", index=False)

            region_robust_df = read_sheet_if_exists(EMPIRICAL_BOOK, "区域稳健性")
            if region_robust_df is not None:
                region_robust_df.to_excel(writer, sheet_name="表5_区域稳健性", index=False)

            construct_df = read_sheet_if_exists(EMPIRICAL_BOOK, "构念稳健性")
            if construct_df is None:
                construct_df = read_excel_if_exists(CONSTRUCT_FILE)
            if construct_df is not None:
                construct_df.to_excel(writer, sheet_name="表6_构念稳健性", index=False)

            loo_summary_df = read_sheet_if_exists(EMPIRICAL_BOOK, "留一法汇总")
            if loo_summary_df is not None:
                loo_summary_df.to_excel(writer, sheet_name="表7_留一法稳定性", index=False)

            region_evidence_df = read_sheet_if_exists(EMPIRICAL_BOOK, "区域证据分级")
            if region_evidence_df is not None:
                region_evidence_df.to_excel(writer, sheet_name="表8_区域证据分级", index=False)

            build_scenario_terminal_table().to_excel(writer, sheet_name="表9_情景预测终值对比", index=False)
            if pol_summary_df is not None and not pol_summary_df.empty:
                pol_summary_df.to_excel(writer, sheet_name="表10_政策仿真最终结果", index=False)
                build_nsga_table(pol_summary_df).to_excel(writer, sheet_name="表11_政策筛选最优解", index=False)

            strategy_compare_df = read_excel_if_exists(STRATEGY_COMPARE_FILE)
            if strategy_compare_df is not None:
                strategy_compare_df.to_excel(writer, sheet_name="表12_策略组合对比", index=False)

            zone_summary_df = read_sheet_if_exists(POLICY_ZONE_FILE, "分型汇总")
            if zone_summary_df is not None:
                zone_summary_df.to_excel(writer, sheet_name="表13_政策分型汇总", index=False)

            zone_detail_df = read_sheet_if_exists(POLICY_ZONE_FILE, "省份分型")
            if zone_detail_df is not None:
                zone_detail_df.to_excel(writer, sheet_name="表14_省份分型明细", index=False)

            build_consistency_sheet(pol_summary_df).to_excel(writer, sheet_name="表15_结果一致性校验", index=False)
            build_metadata_sheet().to_excel(writer, sheet_name="表16_结果时间戳", index=False)

        return self.output_file


def main() -> None:
    """模块独立执行入口。"""
    exporter = ComprehensiveReportExporter()
    output_path = exporter.export_master_workbook()
    print(f"Summary tables successfully aggregated to: {output_path}")


if __name__ == "__main__":
    main()
