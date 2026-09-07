# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：policy_simulation_optimizer (政策多目标仿真与Pareto寻优模块)
功能描述：
1. 构建 2022-2035 动态演化系统动力学模型：模拟省域数字赋能、产业结构转型与碳排放强度的演进轨迹。
2. 多情景前瞻推演：支持“基准情景”、“数字加速”、“政策强化”与“定向协同”多维度政策传导模拟。
3. 政策多目标协同与 Pareto 寻优：基于非劣排序多目标优化算法解算减碳改善与经济增长的最优权衡解集。
4. 欧氏距离折中拐点 (Knee Point) 自动化搜索与 A/B/C/D 四类省域差异化治理清单导出。
5. 提供面向对象的工程级仿真寻优类 PolicySimulationOptimizer，支持参数调整与报表输出。
================================================================================
"""

import os

import numpy as np
import pandas as pd

from model_utils import (
    DATA_DIR,
    FIGURE_DIR,
    SCENARIO_PALETTE,
    SIM_DIR,
    SUPP_FIGURE_DIR,
    choose_knee_point,
    configure_matplotlib,
    ensure_dir,
    load_core_panel,
    mark_pareto_front,
    save_figure_bundle,
    style_axis,
)

EMPIRICAL_BOOK = os.path.join(DATA_DIR, "实证结果_完整回归表.xlsx")
REGION_FILE = os.path.join(DATA_DIR, "实证结果_区域异质性.xlsx")
PROVINCE_FILE = os.path.join(DATA_DIR, "省域异质性_省份斜率.xlsx")
POLICY_SUMMARY_FILE = os.path.join(SIM_DIR, "政策仿真最终结果.xlsx")
PARETO_FILE = os.path.join(SIM_DIR, "多目标优化_前沿对比数据.xlsx")
BOUNDARY_FILE = os.path.join(SIM_DIR, "多目标优化_寻优边界单调性测试.xlsx")
SENSITIVITY_FILE = os.path.join(SIM_DIR, "回弹缩放系数_敏感性分析数据.xlsx")
ROBUST_REPORT_FILE = os.path.join(SIM_DIR, "稳健分布_检验报告.xlsx")
POLICY_ZONE_FILE = os.path.join(SIM_DIR, "政策分型_省份清单.xlsx")
STRATEGY_COMPARE_FILE = os.path.join(SIM_DIR, "策略组合_对比结果.xlsx")


def load_term_info(workbook: str, sheet_name: str, variable: str) -> dict[str, float]:
    df = pd.read_excel(workbook, sheet_name=sheet_name)
    row = df.loc[df["variable"] == variable]
    if row.empty:
        raise KeyError(f"{sheet_name} 缺少系数: {variable}")
    return row.iloc[0].to_dict()


def quantile_bounds(series: pd.Series, lower: float, upper: float) -> tuple[float, float]:
    clean = series.replace([np.inf, -np.inf], np.nan).dropna()
    return float(clean.quantile(lower)), float(clean.quantile(upper))


def _save_figure(fig, *paths: str) -> None:
    save_figure_bundle(fig, *paths)


def maybe_plot_policy_curves(
    scenario_map: dict[str, pd.DataFrame],
    pareto_df: pd.DataFrame,
    optimal_row: pd.Series,
    sensitivity_df: pd.DataFrame,
) -> None:
    try:
        plt = configure_matplotlib()
    except Exception:
        print("matplotlib 不可用，跳过情景图与 Pareto 图。")
        return

    candidate_palette = {
        "统一政策": {"face": "#fde68a", "edge": SCENARIO_PALETTE["统一政策"]},
        "定向协同": {"face": "#99f6e4", "edge": SCENARIO_PALETTE["定向协同"]},
    }
    scenario_order = ["基准情景", "数字加速情景", "统一政策情景", "定向协同情景", "Pareto最优路径"]
    label_offsets = {
        "基准情景": 0.004,
        "数字加速情景": 0.000,
        "统一政策情景": -0.002,
        "定向协同情景": -0.006,
        "Pareto最优路径": 0.004,
    }
    ordered_scenarios = [(name, scenario_map[name]) for name in scenario_order if name in scenario_map]
    y_values = pd.concat([df["Y_pred"].astype(float) for _, df in ordered_scenarios], ignore_index=True)

    fig, ax = plt.subplots(figsize=(10.5, 5.9))
    for name, df in ordered_scenarios:
        color = SCENARIO_PALETTE.get(name, "#475569")
        is_highlight = name in {"定向协同情景", "Pareto最优路径"}
        ax.plot(
            df.index,
            df["Y_pred"],
            marker="o",
            linewidth=3.0 if is_highlight else 2.25,
            markersize=6.5 if is_highlight else 5.5,
            color=color,
            alpha=1.0 if is_highlight else 0.9,
            zorder=4 if is_highlight else 2,
        )
        last_year = int(df.index.max())
        last_value = float(df.loc[last_year, "Y_pred"])
        ax.text(
            last_year + 0.22,
            last_value + label_offsets.get(name, 0.0),
            f"{name.replace('情景', '')} {last_value:.3f}",
            color=color,
            va="center",
            fontsize=9,
            fontweight="bold" if is_highlight else None,
        )

    baseline_2035 = float(scenario_map["基准情景"]["Y_pred"].iloc[-1])
    unified_2035 = float(scenario_map["统一政策情景"]["Y_pred"].iloc[-1])
    targeted_2035 = float(scenario_map["定向协同情景"]["Y_pred"].iloc[-1])
    pareto_2035 = float(scenario_map["Pareto最优路径"]["Y_pred"].iloc[-1])

    y_margin = max((float(y_values.max()) - float(y_values.min())) * 0.12, 0.035)
    ax.set_xlim(int(min(df.index.min() for _, df in ordered_scenarios)) - 0.4, int(max(df.index.max() for _, df in ordered_scenarios)) + 1.1)
    ax.set_ylim(float(y_values.min()) - y_margin, float(y_values.max()) + y_margin)
    ax.set_xticks(list(range(2022, 2036, 2)))
    ax.set_title("2022-2035 碳排放强度情景比较", loc="left", pad=10)
    ax.set_xlabel("年份")
    ax.set_ylabel("碳排放强度预测值")
    style_axis(ax, grid_axis="both")
    ax.text(
        0.02,
        0.92,
        (
            f"2035 年：定向协同较基准下降 {baseline_2035 - targeted_2035:.3f}\n"
            f"较统一政策下降 {unified_2035 - targeted_2035:.3f}，Pareto 路径降至 {pareto_2035:.3f}"
        ),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#0f172a",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.96},
    )
    fig.tight_layout()
    _save_figure(
        fig,
        os.path.join(FIGURE_DIR, "碳排放强度情景预测图.png"),
        os.path.join(SIM_DIR, "碳排放强度情景预测图.png"),
    )
    plt.close(fig)

    frontier_df = pareto_df[pareto_df["Pareto_Flag"]].copy().sort_values(["Y_2035", "Avg_PGDP_Growth"])
    fig, ax = plt.subplots(figsize=(8.8, 5.95))
    for strategy_name, group in pareto_df.groupby("策略类型"):
        style = candidate_palette.get(strategy_name, {"face": "#e2e8f0", "edge": "#94a3b8"})
        ax.scatter(
            group["Y_2035"],
            group["Avg_PGDP_Growth"] * 100.0,
            s=62,
            alpha=0.32,
            facecolor=style["face"],
            edgecolor=style["edge"],
            linewidth=1.0,
            label=f"{strategy_name}候选",
        )
    ax.plot(
        frontier_df["Y_2035"],
        frontier_df["Avg_PGDP_Growth"] * 100.0,
        color="#7c3aed",
        linewidth=2.3,
        alpha=0.95,
    )
    ax.scatter(
        frontier_df["Y_2035"],
        frontier_df["Avg_PGDP_Growth"] * 100.0,
        s=90,
        color="#7c3aed",
        edgecolor="white",
        linewidth=0.8,
        label="Pareto 前沿",
        zorder=3,
    )
    ax.scatter(
        [float(optimal_row["Y_2035"])],
        [float(optimal_row["Avg_PGDP_Growth"]) * 100.0],
        marker="*",
        s=320,
        color="#f59e0b",
        edgecolor="#7c3aed",
        linewidth=0.8,
        label="折中最优点",
        zorder=4,
    )
    ax.annotate(
        (
            f"最优折中：{optimal_row['策略类型']}\n"
            f"数字倍数={float(optimal_row['Digital_Scale']):.1f}，升级倍数={float(optimal_row['Upgrade_Scale']):.1f}\n"
            f"碳强度={float(optimal_row['Y_2035']):.3f}，增长={float(optimal_row['Avg_PGDP_Growth']) * 100.0:.2f}%"
        ),
        xy=(float(optimal_row["Y_2035"]), float(optimal_row["Avg_PGDP_Growth"]) * 100.0),
        xytext=(18, -8),
        textcoords="offset points",
        fontsize=9,
        color="#1f2937",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.94},
        arrowprops={"arrowstyle": "->", "color": "#7c3aed", "lw": 1.2},
    )
    ax.set_title("Pareto 前沿：2035 碳强度与增长权衡", loc="left", pad=10)
    ax.set_xlabel("2035 年碳排放强度（越低越优）")
    ax.set_ylabel("平均人均 GDP 增长率（%）")
    style_axis(ax, grid_axis="both")
    ax.legend(loc="upper right")
    fig.tight_layout()
    _save_figure(
        fig,
        os.path.join(FIGURE_DIR, "多目标优化_帕累托前沿对比图.png"),
        os.path.join(SIM_DIR, "多目标优化_帕累托前沿对比图.png"),
    )
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.3, 5.45))
    x = sensitivity_df["targeted_upgrade_scale_factor"].astype(float)
    sensitivity_map = {
        "基准情景": ("#64748b", "--", "o", 1.8),
        "统一政策": (SCENARIO_PALETTE["统一政策"], "-.", "s", 2.0),
        "定向协同": ("#5eead4", ":", "D", 1.9),
        "敏感性策略": (SCENARIO_PALETTE["定向协同"], "-", "^", 2.8),
    }
    for column, (color, linestyle, marker, linewidth) in sensitivity_map.items():
        ax.plot(
            x,
            sensitivity_df[column].astype(float),
            color=color,
            linestyle=linestyle,
            marker=marker,
            linewidth=linewidth,
            markersize=7,
            label="定向协同（gamma 变化）" if column == "敏感性策略" else column,
        )
    ax.fill_between(
        x,
        sensitivity_df["定向协同"].astype(float),
        sensitivity_df["敏感性策略"].astype(float),
        color="#99f6e4",
        alpha=0.35,
        label="gamma 调整带来的额外改善",
    )
    for x_val, y_val in zip(x, sensitivity_df["敏感性策略"].astype(float)):
        ax.text(x_val, y_val + 0.004, f"{y_val:.3f}", ha="center", va="bottom", fontsize=9, color="#047857")
    y_min = float(sensitivity_df[["基准情景", "统一政策", "定向协同", "敏感性策略"]].min().min())
    y_max = float(sensitivity_df[["基准情景", "统一政策", "定向协同", "敏感性策略"]].max().max())
    margin = max((y_max - y_min) * 0.25, 0.02)
    ax.set_ylim(y_min - margin, y_max + margin)
    ax.set_xticks(x.tolist())
    ax.set_title("回弹缩放系数 gamma 的敏感性分析", loc="left", pad=10)
    ax.set_xlabel("回弹缩放系数 gamma")
    ax.set_ylabel("2035 年碳排放强度")
    style_axis(ax, grid_axis="both")
    best_idx = int(sensitivity_df["敏感性策略"].astype(float).idxmin())
    best_gamma = float(x.iloc[best_idx])
    best_value = float(sensitivity_df["敏感性策略"].iloc[best_idx])
    baseline_value = float(sensitivity_df["基准情景"].iloc[0])
    unified_value = float(sensitivity_df["统一政策"].iloc[0])
    ax.text(
        0.02,
        0.96,
        (
            f"gamma={best_gamma:.1f} 时效果最佳：{best_value:.3f}\n"
            f"较基准改善 {baseline_value - best_value:.3f}，较统一政策改善 {unified_value - best_value:.3f}"
        ),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#0f172a",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.96},
    )
    ax.legend(loc="lower left")
    fig.tight_layout()
    _save_figure(fig, os.path.join(SUPP_FIGURE_DIR, "回弹缩放系数_敏感性分析图.png"))
    plt.close(fig)


def evidence_screen(coef: float, p_value: float, alpha: float = 0.10) -> float:
    return float(coef) if p_value < alpha else 0.0


def moderation_ratio(ci_info: dict[str, float], interaction_info: dict[str, float]) -> float:
    ci_coef = float(ci_info["coef"])
    interaction_coef = float(interaction_info["coef"])
    interaction_p = float(interaction_info["P>|t|"])
    if ci_coef <= 0 or interaction_coef >= 0 or interaction_p >= 0.20:
        return 0.0
    return float(np.clip(-interaction_coef / max(ci_coef, 1e-8), 0.0, 1.8))


def classify_policy_zone(snapshot_df: pd.DataFrame, province_diag_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = snapshot_df.merge(province_diag_df[["province", "CI_std_beta"]], on="province", how="left")
    y_high = float(work["Y"].quantile(0.67))
    upgrade_low = float(work["Upgrade"].quantile(0.33))
    ci_median = float(work["CI"].median())

    def classify(row: pd.Series) -> str:
        if row["Region_3"] in ["东北", "中西部"] and row["Y"] >= y_high:
            return "A_高压约束区"
        if row["Region_3"] in ["东北", "中西部"] and row["Upgrade"] <= upgrade_low:
            return "B_结构补短区"
        if row["Region_3"] == "东部" and row["CI"] >= ci_median:
            return "C_数字引领区"
        return "D_均衡提升区"

    advice_map = {
        "A_高压约束区": "控制数字扩张节奏，优先追加产业升级和能效改造",
        "B_结构补短区": "以产业升级补短板为主，数字投资适度跟进",
        "C_数字引领区": "维持数字投入优势，同时用轻量结构优化压低反弹",
        "D_均衡提升区": "保持温和升级，避免过度激进调整",
    }
    work["政策分型"] = work.apply(classify, axis=1)
    work["建议路径"] = work["政策分型"].map(advice_map)

    summary = (
        work.groupby("政策分型")
        .agg(
            省份数=("province", "count"),
            平均碳强度=("Y", "mean"),
            平均数字赋能=("CI", "mean"),
            平均产业升级=("Upgrade", "mean"),
        )
        .reset_index()
        .sort_values("政策分型")
    )
    summary["政策含义"] = summary["政策分型"].map(advice_map)
    return work.sort_values(["政策分型", "Y"], ascending=[True, False]), summary


def build_offset_maps(
    strategy_type: str,
    digital_scale: float,
    upgrade_scale: float,
    zone_map: dict[str, str],
    digital_step: float,
    upgrade_step: float,
) -> tuple[dict[str, float], dict[str, float]]:
    digital_offsets: dict[str, float] = {}
    upgrade_offsets: dict[str, float] = {}

    for province, zone in zone_map.items():
        if strategy_type == "统一政策":
            digital_offsets[province] = digital_step * digital_scale
            upgrade_offsets[province] = upgrade_step * upgrade_scale
            continue

        if zone == "A_高压约束区":
            digital_offsets[province] = 0.0
            upgrade_offsets[province] = upgrade_step * (1.8 + 1.0 * upgrade_scale)
        elif zone == "B_结构补短区":
            digital_offsets[province] = digital_step * 0.1 * digital_scale
            upgrade_offsets[province] = upgrade_step * (1.0 + 0.8 * upgrade_scale)
        elif zone == "C_数字引领区":
            digital_offsets[province] = digital_step * (0.4 + 0.7 * digital_scale)
            upgrade_offsets[province] = upgrade_step * 0.3 * upgrade_scale
        else:
            digital_offsets[province] = digital_step * 0.2 * digital_scale
            upgrade_offsets[province] = upgrade_step * 0.5 * upgrade_scale

    return digital_offsets, upgrade_offsets


def to_offset_series(offsets: float | dict[str, float], provinces: pd.Series) -> pd.Series:
    if isinstance(offsets, dict):
        return provinces.map(offsets).fillna(0.0).astype(float)
    return pd.Series(float(offsets), index=provinces.index, dtype=float)


print("正在加载基础数据与实证参数...")
ensure_dir(SIM_DIR)
panel = load_core_panel()
panel["Y_change"] = panel.groupby("province")["Y"].diff()
panel["CI_growth"] = panel.groupby("province")["CI"].pct_change()
panel["Upgrade_change"] = panel.groupby("province")["Upgrade"].diff()
panel["PGDP_growth"] = panel.groupby("province")["PGDP"].pct_change()
panel["URB_change"] = panel.groupby("province")["URB"].diff()
panel["OPEN_change"] = panel.groupby("province")["OPEN"].diff()
panel["CI_x_Upgrade"] = panel["CI"] * panel["Upgrade"]

region_df = pd.read_excel(REGION_FILE)
if "政策证据权重" in region_df.columns:
    region_df["纳入仿真CI系数"] = region_df.apply(
        lambda row: max(float(row["CI系数"]), 0.0) * float(row["政策证据权重"]),
        axis=1,
    )
else:
    region_df["纳入仿真CI系数"] = region_df.apply(
        lambda row: evidence_screen(float(row["CI系数"]), float(row["p值"]), alpha=0.10),
        axis=1,
    )
region_beta = region_df.set_index("区域")["纳入仿真CI系数"].to_dict()

main_ci_info = load_term_info(EMPIRICAL_BOOK, "连续主回归", "CI")
moderation_ci_info = load_term_info(EMPIRICAL_BOOK, "协同机制", "CI")
moderation_interaction_info = load_term_info(EMPIRICAL_BOOK, "协同机制", "CI_x_Upgrade")
growth_ci_info = load_term_info(EMPIRICAL_BOOK, "增长方程", "CI")
growth_upgrade_info = load_term_info(EMPIRICAL_BOOK, "增长方程", "Upgrade")

beta_growth_ci = evidence_screen(float(growth_ci_info["coef"]), float(growth_ci_info["P>|t|"]), alpha=0.10)
beta_growth_upgrade = evidence_screen(float(growth_upgrade_info["coef"]), float(growth_upgrade_info["P>|t|"]), alpha=0.10)
upgrade_moderation_ratio = moderation_ratio(moderation_ci_info, moderation_interaction_info)

state_2022 = panel[panel["year"] == 2022].copy()
base_upgrade_map = state_2022.set_index("province")["Upgrade"].to_dict()

y_drift = panel.groupby("province")["Y_change"].median().to_dict()
ci_growth = panel.groupby("province")["CI_growth"].median().replace([np.inf, -np.inf], np.nan).to_dict()
upgrade_drift = panel.groupby("province")["Upgrade_change"].median().to_dict()
pgdp_growth = panel.groupby("province")["PGDP_growth"].median().replace([np.inf, -np.inf], np.nan).to_dict()
urb_drift = panel.groupby("province")["URB_change"].median().to_dict()
open_drift = panel.groupby("province")["OPEN_change"].median().to_dict()

global_y_drift = float(panel["Y_change"].dropna().median())
global_ci_growth = float(panel["CI_growth"].replace([np.inf, -np.inf], np.nan).dropna().median())
global_upgrade_drift = float(panel["Upgrade_change"].dropna().median())
global_pgdp_growth = float(panel["PGDP_growth"].replace([np.inf, -np.inf], np.nan).dropna().median())
global_urb_drift = float(panel["URB_change"].dropna().median())
global_open_drift = float(panel["OPEN_change"].dropna().median())

y_q05, y_q95 = quantile_bounds(panel["Y_change"], 0.05, 0.95)
pgdp_q10, pgdp_q90 = quantile_bounds(panel["PGDP_growth"], 0.10, 0.90)
ci_q05, ci_q95 = quantile_bounds(panel["CI_growth"], 0.05, 0.95)
upgrade_min = float(panel["Upgrade"].quantile(0.01))
upgrade_max = float(panel["Upgrade"].quantile(0.99))
urb_min = float(panel["URB"].quantile(0.01))
urb_max = float(panel["URB"].quantile(0.99))
open_min = float(panel["OPEN"].quantile(0.01))
open_max = float(panel["OPEN"].quantile(0.99))

ci_growth_std = float(panel["CI_growth"].replace([np.inf, -np.inf], np.nan).dropna().std())
upgrade_change_std = float(panel["Upgrade_change"].dropna().std())

digital_step = float(np.clip(ci_growth_std * 0.35, 0.004, 0.018))
upgrade_step = float(np.clip(upgrade_change_std * 0.35, 0.002, 0.012))

province_diag = pd.read_excel(PROVINCE_FILE)
policy_zone_df, policy_zone_summary_df = classify_policy_zone(
    state_2022[["province", "Region_3", "Y", "CI", "Upgrade", "PGDP"]].copy(),
    province_diag,
)
zone_map = policy_zone_df.set_index("province")["政策分型"].to_dict()

with pd.ExcelWriter(POLICY_ZONE_FILE, engine="openpyxl") as writer:
    policy_zone_df.to_excel(writer, sheet_name="省份分型", index=False)
    policy_zone_summary_df.to_excel(writer, sheet_name="分型汇总", index=False)

robust_report = pd.DataFrame(
    {
        "指标": [
            "全国主效应p值",
            "交互抑制项p值",
            "增长方程中Upgrade项p值",
            "纳入仿真的区域数量",
            "高支持区域数量",
            "平均政策证据权重",
            "升级抑制比率",
            "数字情景年度增量步长",
            "产业升级年度调整步长",
            "高压约束区省份数",
            "数字引领区省份数",
        ],
        "数值": [
            float(main_ci_info["P>|t|"]),
            float(moderation_interaction_info["P>|t|"]),
            float(growth_upgrade_info["P>|t|"]),
            int((region_df["纳入仿真CI系数"] != 0).sum()),
            int((region_df.get("政策支持级别", pd.Series(dtype=str)) == "高支持").sum()),
            float(region_df.get("政策证据权重", pd.Series([0.0] * len(region_df))).mean()),
            upgrade_moderation_ratio,
            digital_step,
            upgrade_step,
            int((policy_zone_df["政策分型"] == "A_高压约束区").sum()),
            int((policy_zone_df["政策分型"] == "C_数字引领区").sum()),
        ],
    }
)
robust_report.to_excel(ROBUST_REPORT_FILE, index=False)


def simulate_policy(
    scenario_name: str,
    digital_offset: float | dict[str, float] = 0.0,
    upgrade_offset: float | dict[str, float] = 0.0,
    strategy_type: str = "统一政策",
    end_year: int = 2035,
) -> tuple[pd.DataFrame, dict[str, float]]:
    current = state_2022.copy()
    records = [
        {
            "year": 2022,
            "CI_pred": float(current["CI"].mean()),
            "Y_pred": float(current["Y"].mean()),
            "PGDP_pred": float(current["PGDP"].mean()),
            "Avg_PGDP_Growth": float(global_pgdp_growth),
            "Upgrade_pred": float(current["Upgrade"].mean()),
            "Industry_pred": float((1.0 - current["Upgrade"]).mean()),
            "Effective_Rebound_Coeff": float(current["Region_3"].map(region_beta).fillna(0.0).mean()),
        }
    ]
    yearly_growth = []

    for year in range(2023, end_year + 1):
        prev_ci = current["CI"].copy()
        prev_upgrade = current["Upgrade"].copy()

        annual_ci_growth = np.clip(
            current["province"].map(ci_growth).fillna(global_ci_growth) + to_offset_series(digital_offset, current["province"]),
            ci_q05,
            ci_q95,
        )
        current["CI"] = current["CI"] * (1.0 + annual_ci_growth)

        current["Upgrade"] = np.clip(
            current["Upgrade"]
            + current["province"].map(upgrade_drift).fillna(global_upgrade_drift)
            + to_offset_series(upgrade_offset, current["province"]),
            upgrade_min,
            upgrade_max,
        )
        current["URB"] = np.clip(
            current["URB"] + current["province"].map(urb_drift).fillna(global_urb_drift),
            urb_min,
            urb_max,
        )
        current["OPEN"] = np.clip(
            current["OPEN"] + current["province"].map(open_drift).fillna(global_open_drift),
            open_min,
            open_max,
        )

        ci_delta = current["CI"] - prev_ci
        upgrade_delta = (current["Upgrade"] - prev_upgrade).clip(lower=0.0)
        cumulative_upgrade_gain = (
            current["Upgrade"] - current["province"].map(base_upgrade_map).fillna(current["Upgrade"])
        ).clip(lower=0.0)
        attenuation = (1.0 - upgrade_moderation_ratio * cumulative_upgrade_gain).clip(lower=0.55, upper=1.05)
        regional_beta = current["Region_3"].map(region_beta).fillna(0.0) * attenuation
        baseline_y_change = current["province"].map(y_drift).fillna(global_y_drift)
        modeled_y_change = np.clip(baseline_y_change + regional_beta * ci_delta, y_q05, y_q95)
        current["Y"] = np.clip(current["Y"] + modeled_y_change, 0.05, None)

        baseline_growth = current["province"].map(pgdp_growth).fillna(global_pgdp_growth)
        policy_growth = np.clip(
            baseline_growth + beta_growth_ci * ci_delta + beta_growth_upgrade * upgrade_delta,
            pgdp_q10,
            pgdp_q90,
        )
        current["PGDP"] = current["PGDP"] * (1.0 + policy_growth)
        yearly_growth.append(float(policy_growth.mean()))

        records.append(
            {
                "year": year,
                "CI_pred": float(current["CI"].mean()),
                "Y_pred": float(current["Y"].mean()),
                "PGDP_pred": float(current["PGDP"].mean()),
                "Avg_PGDP_Growth": float(policy_growth.mean()),
                "Upgrade_pred": float(current["Upgrade"].mean()),
                "Industry_pred": float((1.0 - current["Upgrade"]).mean()),
                "Effective_Rebound_Coeff": float(regional_beta.mean()),
            }
        )

    result_df = pd.DataFrame(records).set_index("year")
    metrics = {
        "情景": scenario_name,
        "策略类型": strategy_type,
        "Y_2035": float(result_df.loc[end_year, "Y_pred"]),
        "CI_2035": float(result_df.loc[end_year, "CI_pred"]),
        "Upgrade_2035": float(result_df.loc[end_year, "Upgrade_pred"]),
        "Avg_PGDP_Growth": float(np.mean(yearly_growth)) if yearly_growth else global_pgdp_growth,
        "Digital_Input_Multiplier": (
            float(1.0 + digital_offset)
            if not isinstance(digital_offset, dict)
            else float(1.0 + np.mean(list(digital_offset.values())))
        ),
        "Upgrade_Annual_Shift": (
            float(upgrade_offset)
            if not isinstance(upgrade_offset, dict)
            else float(np.mean(list(upgrade_offset.values())))
        ),
    }
    return result_df, metrics


def build_strategy_candidate_rows() -> tuple[pd.DataFrame, dict[str, tuple[pd.DataFrame, dict[str, float]]]]:
    scenario_cache: dict[str, tuple[pd.DataFrame, dict[str, float]]] = {}
    candidate_rows = []

    baseline_df, baseline_metrics = simulate_policy("基准情景", 0.0, 0.0, "统一政策")
    accel_df, accel_metrics = simulate_policy("数字加速情景", digital_step, 0.0, "统一政策")
    uniform_df, uniform_metrics = simulate_policy(
        "政策强化情景",
        digital_step * 0.25,
        upgrade_step * 2.30,
        "统一政策",
    )

    cfg_digital_scale = float(os.environ.get("DEC_CES_DIGITAL_SCALE", "0.0"))
    cfg_upgrade_scale = float(os.environ.get("DEC_CES_UPGRADE_SCALE", "0.6"))
    targeted_offsets = build_offset_maps(
        "定向协同",
        digital_scale=cfg_digital_scale,
        upgrade_scale=cfg_upgrade_scale,
        zone_map=zone_map,
        digital_step=digital_step,
        upgrade_step=upgrade_step,
    )
    targeted_df, targeted_metrics = simulate_policy(
        "定向协同情景",
        targeted_offsets[0],
        targeted_offsets[1],
        "定向协同",
    )

    scenario_cache["基准情景"] = (baseline_df, baseline_metrics)
    scenario_cache["数字加速情景"] = (accel_df, accel_metrics)
    scenario_cache["政策强化情景"] = (uniform_df, uniform_metrics)
    scenario_cache["定向协同情景"] = (targeted_df, targeted_metrics)

    strategy_grid = []
    for digital_scale in np.linspace(0.0, 1.0, 6):
        for upgrade_scale in np.linspace(0.2, 1.2, 6):
            strategy_grid.append(("统一政策", float(digital_scale), float(upgrade_scale)))
            strategy_grid.append(("定向协同", float(digital_scale), float(upgrade_scale)))

    for strategy_type, digital_scale, upgrade_scale in strategy_grid:
        digital_offsets, upgrade_offsets = build_offset_maps(
            strategy_type=strategy_type,
            digital_scale=digital_scale,
            upgrade_scale=upgrade_scale,
            zone_map=zone_map,
            digital_step=digital_step,
            upgrade_step=upgrade_step,
        )
        result_df, metrics = simulate_policy(
            scenario_name="候选策略",
            digital_offset=digital_offsets,
            upgrade_offset=upgrade_offsets,
            strategy_type=strategy_type,
        )
        candidate_rows.append(
            {
                "策略类型": strategy_type,
                "Digital_Scale": digital_scale,
                "Upgrade_Scale": upgrade_scale,
                "Digital_Input_Multiplier": metrics["Digital_Input_Multiplier"],
                "Upgrade_Annual_Shift": metrics["Upgrade_Annual_Shift"],
                "Y_2035": metrics["Y_2035"],
                "CI_2035": metrics["CI_2035"],
                "Upgrade_2035": metrics["Upgrade_2035"],
                "Avg_PGDP_Growth": metrics["Avg_PGDP_Growth"],
            }
        )

    return pd.DataFrame(candidate_rows), scenario_cache


print("正在模拟核心情景与策略族...")
candidate_df, scenario_cache = build_strategy_candidate_rows()
candidate_df["Pareto_Flag"] = mark_pareto_front(candidate_df, min_col="Y_2035", max_col="Avg_PGDP_Growth")
pareto_df = candidate_df[candidate_df["Pareto_Flag"]].copy().sort_values(["Y_2035", "Avg_PGDP_Growth"], ascending=[True, False])
optimal_row = choose_knee_point(pareto_df, min_col="Y_2035", max_col="Avg_PGDP_Growth")
optimal_offsets = build_offset_maps(
    strategy_type=str(optimal_row["策略类型"]),
    digital_scale=float(optimal_row["Digital_Scale"]),
    upgrade_scale=float(optimal_row["Upgrade_Scale"]),
    zone_map=zone_map,
    digital_step=digital_step,
    upgrade_step=upgrade_step,
)
optimal_df, optimal_metrics = simulate_policy(
    "Pareto最优路径",
    optimal_offsets[0],
    optimal_offsets[1],
    str(optimal_row["策略类型"]),
)
scenario_cache["Pareto最优路径"] = (optimal_df, optimal_metrics)

for scenario_name, (scenario_df, _) in scenario_cache.items():
    scenario_df.to_excel(os.path.join(SIM_DIR, f"{scenario_name}.xlsx"))

candidate_df.to_excel(PARETO_FILE, index=False)

boundary_records = []
for upper in [0.0, 0.2, 0.4, 0.6, 1.0]:
    constrained = candidate_df[candidate_df["Digital_Scale"] <= upper].copy()
    constrained["Pareto_Flag"] = mark_pareto_front(constrained, min_col="Y_2035", max_col="Avg_PGDP_Growth")
    constrained_pareto = constrained[constrained["Pareto_Flag"]].copy()
    best_row = choose_knee_point(constrained_pareto, min_col="Y_2035", max_col="Avg_PGDP_Growth")
    boundary_records.append(
        {
            "Tested_Max_Digital_Scale": float(upper),
            "Optimal_Strategy": str(best_row["策略类型"]),
            "Optimal_Digital_Scale": float(best_row["Digital_Scale"]),
            "Optimal_Upgrade_Scale": float(best_row["Upgrade_Scale"]),
            "Y_2035": float(best_row["Y_2035"]),
            "GDP_Growth": float(best_row["Avg_PGDP_Growth"]),
        }
    )
boundary_df = pd.DataFrame(boundary_records)
boundary_df.to_excel(BOUNDARY_FILE, index=False)

sensitivity_records = []
for factor in [0.5, 0.8, 1.0, 1.2, 1.5]:
    digital_offsets, upgrade_offsets = build_offset_maps(
        strategy_type="定向协同",
        digital_scale=0.0,
        upgrade_scale=float(0.6 * factor),
        zone_map=zone_map,
        digital_step=digital_step,
        upgrade_step=upgrade_step,
    )
    _, metrics = simulate_policy(
        "敏感性测试",
        digital_offsets,
        upgrade_offsets,
        "定向协同",
    )
    sensitivity_records.append(
        {
            "targeted_upgrade_scale_factor": float(factor),
            "基准情景": scenario_cache["基准情景"][1]["Y_2035"],
            "统一政策": scenario_cache["政策强化情景"][1]["Y_2035"],
            "定向协同": scenario_cache["定向协同情景"][1]["Y_2035"],
            "敏感性策略": float(metrics["Y_2035"]),
        }
    )
sensitivity_df = pd.DataFrame(sensitivity_records)
sensitivity_df.to_excel(SENSITIVITY_FILE, index=False)

strategy_compare_df = pd.DataFrame(
    [
        scenario_cache["基准情景"][1],
        scenario_cache["数字加速情景"][1],
        scenario_cache["政策强化情景"][1],
        scenario_cache["定向协同情景"][1],
        optimal_metrics,
    ]
)
strategy_compare_df = strategy_compare_df.rename(
    columns={
        "Y_2035": "2035碳强度预测",
        "CI_2035": "2035数字赋能指数",
        "Upgrade_2035": "2035产业升级指标",
        "Avg_PGDP_Growth": "平均人均GDP增长率",
        "Digital_Input_Multiplier": "数字投入倍数",
        "Upgrade_Annual_Shift": "产业升级增量",
    }
)
baseline_y = float(strategy_compare_df.loc[strategy_compare_df["情景"] == "基准情景", "2035碳强度预测"].iloc[0])
baseline_growth = float(strategy_compare_df.loc[strategy_compare_df["情景"] == "基准情景", "平均人均GDP增长率"].iloc[0])
strategy_compare_df["较基准降碳改善"] = baseline_y - strategy_compare_df["2035碳强度预测"]
strategy_compare_df["较基准增长变化"] = strategy_compare_df["平均人均GDP增长率"] - baseline_growth

strategy_compare_df.to_excel(STRATEGY_COMPARE_FILE, index=False)

summary_df = strategy_compare_df.copy()
summary_df.to_excel(POLICY_SUMMARY_FILE, index=False)

maybe_plot_policy_curves(
    {
        "基准情景": scenario_cache["基准情景"][0],
        "数字加速情景": scenario_cache["数字加速情景"][0],
        "统一政策情景": scenario_cache["政策强化情景"][0],
        "定向协同情景": scenario_cache["定向协同情景"][0],
        "Pareto最优路径": optimal_df,
    },
    candidate_df,
    optimal_row,
    sensitivity_df,
)

print("\n" + "=" * 80)
print("五类核心政策情景推演结果对比 (2035 目标年)")
print("系统演化推演区间: 2022-2035 年")
print("=" * 80)

cols_2035 = [
    "情景",
    "策略类型",
    "2035碳强度预测",
    "较基准降碳改善",
    "平均人均GDP增长率",
    "较基准增长变化",
    "数字投入倍数",
    "产业升级增量",
]
print("\n【2035 目标年核心推演终值对比表】:")
print(summary_df[cols_2035].to_string(index=False))

pareto_summary = {
    "策略类型": str(optimal_row["策略类型"]),
    "Digital Scale": float(optimal_row["Digital_Scale"]),
    "Upgrade Scale": float(optimal_row["Upgrade_Scale"]),
    "2035年碳排放强度 (Y_2035)": round(float(optimal_df.loc[2035, "Y_pred"]), 6),
    "平均人均GDP增长率 (2022-2035)": round(float(optimal_row["Avg_PGDP_Growth"]), 6),
    "最优数字投入倍数": round(float(optimal_row["Digital_Input_Multiplier"]), 5),
    "最优产业升级年调整量": round(float(optimal_row["Upgrade_Annual_Shift"]), 6),
}
print("\nPareto 前沿中最优折中策略 (2035 目标年):")
print(pareto_summary)
print(f"\n政策汇总表已保存: {POLICY_SUMMARY_FILE}")

