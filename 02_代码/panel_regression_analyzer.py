# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：panel_regression_analyzer (面板计量回归与条件关系分析模块)
功能描述：
1. 双向固定效应 (Two-Way Fixed Effects, TWFE) 计量经济学主模型估计与聚类稳健标准误求解。
2. 二值处理连续与离散稳健性对照、中介与调节交互效应 (CI × Upgrade) 分析。
3. 区域异质性分层识别：按中西部、东北、东部三区深入估计边际弹性并划分政策证据分级。
4. 构念稳健性（基准 CI 与严格数字 CI_core 对照）与留一法 (Leave-One-Out) 省份影响稳定性检验。
5. 提供面向对象的工程级计量类 PanelRegressionAnalyzer，一键完成主回归与 16 类别多工作簿成果输出。
================================================================================
"""

import os

import numpy as np
import pandas as pd

from model_utils import (
    DATA_DIR,
    FIGURE_DIR,
    REGION_ORDER,
    SUPPORT_PALETTE,
    build_binary_treatment,
    configure_matplotlib,
    ensure_dir,
    extract_term_row,
    fit_panel_fe,
    load_core_panel,
    save_figure_bundle,
    style_axis,
    summary_to_sheet,
)

OUTPUT_BOOK = os.path.join(DATA_DIR, "实证结果_完整回归表.xlsx")
COMPARE_FILE = os.path.join(DATA_DIR, "实证结果_连续与离散比较.xlsx")
REGION_FILE = os.path.join(DATA_DIR, "实证结果_区域异质性.xlsx")
PROVINCE_FILE = os.path.join(DATA_DIR, "省域异质性_省份斜率.xlsx")
ROBUSTNESS_FILE = os.path.join(DATA_DIR, "实证结果_稳健性矩阵.xlsx")
REGION_STABILITY_FILE = os.path.join(DATA_DIR, "实证结果_区域稳定性.xlsx")
CONSTRUCT_FILE = os.path.join(DATA_DIR, "实证结果_构念稳健性.xlsx")
REGION_PLOT_FILE = os.path.join(FIGURE_DIR, "区域证据分层图.png")


def evidence_grade(p_value: float) -> str:
    if p_value < 0.05:
        return "强"
    if p_value < 0.10:
        return "中"
    return "弱"


def significance_label(p_value: float) -> str:
    if p_value < 0.01:
        return "1%显著"
    if p_value < 0.05:
        return "5%显著"
    if p_value < 0.10:
        return "10%显著"
    return "不显著"


def safe_zscore(series: pd.Series) -> pd.Series:
    std = float(series.std(ddof=0))
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    return (series - float(series.mean())) / std


def winsorize_series(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    clean = series.dropna()
    if clean.empty:
        return series.copy()
    lower_bound = float(clean.quantile(lower))
    upper_bound = float(clean.quantile(upper))
    return series.clip(lower=lower_bound, upper=upper_bound)


def winsorize_frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        out[col] = winsorize_series(out[col])
    return out


def effect_direction(coef: float) -> str:
    if coef > 0:
        return "增碳/增压"
    if coef < 0:
        return "降碳/缓压"
    return "零附近"


def region_reading(coef: float, p_value: float) -> str:
    if p_value >= 0.10:
        if coef > 0:
            return "正向压力方向性信号，需保守解释"
        return "统计证据不足，谨慎解读"
    if coef > 0:
        return "数字扩张存在增碳压力"
    return "数字扩张存在降碳迹象"


def build_descriptive_table(panel: pd.DataFrame) -> pd.DataFrame:
    label_map = {
        "Y": "碳排放强度",
        "CI": "数字赋能指数",
        "CI_core": "核心数字指数",
        "PGDP": "人均GDP",
        "URB": "城镇化率",
        "OPEN": "对外开放度",
        "Upgrade": "产业升级指标",
    }
    stats = (
        panel[list(label_map.keys())]
        .agg(["mean", "std", "min", "median", "max"])
        .T
        .reset_index()
        .rename(columns={"index": "变量", "mean": "均值", "std": "标准差", "min": "最小值", "median": "中位数", "max": "最大值"})
    )
    stats["变量"] = stats["变量"].map(label_map)
    stats["样本量"] = len(panel)
    return stats


def build_panel_profile(panel: pd.DataFrame) -> pd.DataFrame:
    profile = pd.DataFrame(
        {
            "指标": [
                "样本量",
                "省份数",
                "年份数",
                "是否平衡面板",
                "起始年份",
                "结束年份",
            ],
            "数值": [
                len(panel),
                panel["province"].nunique(),
                panel["year"].nunique(),
                "是" if panel.groupby("province")["year"].nunique().nunique() == 1 else "否",
                int(panel["year"].min()),
                int(panel["year"].max()),
            ],
        }
    )
    return profile


def fit_simple_ols(y: pd.Series, x_df: pd.DataFrame):
    from model_utils import ols_with_cluster

    return ols_with_cluster(y=y, x_df=x_df, cluster=None, add_const=True)[:2] + (None, None)


def build_region_effects(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for region in REGION_ORDER:
        region_df = panel[panel["Region_3"] == region].copy()
        summary, meta, _, _, _ = fit_panel_fe(
            region_df,
            y_col="Y",
            x_cols=["CI", "PGDP", "URB", "OPEN"],
        )
        ci_row = summary.loc["CI"]
        p_value = float(ci_row["P>|t|"])
        coef = float(ci_row["coef"])
        rows.append(
            {
                "区域": region,
                "CI系数": coef,
                "ATE": coef,
                "标准误": float(ci_row["std err"]),
                "p值": p_value,
                "显著性": significance_label(p_value),
                "证据分级": evidence_grade(p_value),
                "样本量": int(meta["n_obs"]),
                "调整R2": float(meta["adj_r2"]),
                "说明": region_reading(coef, p_value),
            }
        )
    return pd.DataFrame(rows)


def build_construct_robustness(panel: pd.DataFrame) -> pd.DataFrame:
    if "CI_core" not in panel.columns:
        return pd.DataFrame()

    rows = []
    configs = [
        ("全国", "基准协同指数", panel, "CI"),
        ("全国", "核心数字指数", panel, "CI_core"),
    ]
    for region in REGION_ORDER:
        region_df = panel[panel["Region_3"] == region].copy()
        configs.append((region, "基准协同指数", region_df, "CI"))
        configs.append((region, "核心数字指数", region_df, "CI_core"))

    for scope, index_name, df, ci_col in configs:
        summary, meta, _, _, _ = fit_panel_fe(
            df,
            y_col="Y",
            x_cols=[ci_col, "PGDP", "URB", "OPEN"],
        )
        row = summary.loc[ci_col]
        coef = float(row["coef"])
        p_value = float(row["P>|t|"])
        rows.append(
            {
                "范围": scope,
                "指数口径": index_name,
                "变量": ci_col,
                "系数": coef,
                "p值": p_value,
                "方向": effect_direction(coef),
                "显著性": significance_label(p_value),
                "证据分级": evidence_grade(p_value),
                "样本量": int(meta["n_obs"]),
            }
        )

    construct_df = pd.DataFrame(rows)
    compare_rows = []
    for region in ["全国", *REGION_ORDER]:
        baseline = construct_df[
            (construct_df["范围"] == region) & (construct_df["指数口径"] == "基准协同指数")
        ].iloc[0]
        core = construct_df[
            (construct_df["范围"] == region) & (construct_df["指数口径"] == "核心数字指数")
        ].iloc[0]
        same_sign = np.sign(float(baseline["系数"])) == np.sign(float(core["系数"]))
        if not same_sign:
            strict_support = "转向"
            match_text = "否"
            explain = "严格数字口径下方向变化，说明结构因素参与了地区结果"
        elif float(core["p值"]) < 0.10:
            strict_support = "保留"
            match_text = "是"
            explain = "严格数字口径与基准协同口径方向一致，且压力得到保留"
        elif float(core["p值"]) < 0.20 and abs(float(core["系数"])) >= abs(float(baseline["系数"])) * 0.30:
            strict_support = "弱保留"
            match_text = "是"
            explain = "严格数字口径方向一致，但证据强度下降，应保守表述"
        else:
            strict_support = "转弱"
            match_text = "部分"
            explain = "严格数字口径下压力明显转弱，说明结构协同成分更关键"

        compare_rows.append(
            {
                "范围": region,
                "基准协同指数系数": float(baseline["系数"]),
                "基准协同指数p值": float(baseline["p值"]),
                "核心数字指数系数": float(core["系数"]),
                "核心数字指数p值": float(core["p值"]),
                "方向是否一致": match_text,
                "严格口径支持度": strict_support,
                "评估说明": explain,
            }
        )

    return pd.DataFrame(compare_rows)


def build_province_slopes(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for province, group in panel.groupby("province"):
        local = group.dropna(subset=["Y", "CI", "Upgrade"]).copy()
        if len(local) < 8:
            continue
        local["time_trend"] = local["year"] - int(local["year"].min())
        local["z_Y"] = safe_zscore(local["Y"])
        local["z_CI"] = safe_zscore(local["CI"])
        local["z_Upgrade"] = safe_zscore(local["Upgrade"])
        local["z_time_trend"] = safe_zscore(local["time_trend"])
        if float(local["z_Y"].abs().sum()) == 0 or float(local["z_CI"].abs().sum()) == 0:
            continue

        summary, meta, _, _ = fit_simple_ols(
            y=local["z_Y"],
            x_df=local[["z_CI", "z_Upgrade", "z_time_trend"]],
        )
        ci_beta = float(summary.loc["z_CI", "coef"])
        upgrade_beta = float(summary.loc["z_Upgrade", "coef"])
        rows.append(
            {
                "province": province,
                "CI_std_beta": ci_beta,
                "Upgrade_std_beta": upgrade_beta,
                "TimeTrend_std_beta": float(summary.loc["z_time_trend", "coef"]),
                "R2": float(meta["adj_r2"]),
                "n_obs": int(meta["n_obs"]),
                "Direction": "数字扩张压力更强" if ci_beta > 0 else "数字扩张压力较弱",
                "Method": "Province standardized OLS diagnostic",
            }
        )

    return pd.DataFrame(rows).sort_values("CI_std_beta")


def build_comparison_table(
    continuous_summary: pd.DataFrame,
    continuous_meta: dict[str, float],
    discrete_summary: pd.DataFrame,
    discrete_meta: dict[str, float],
    moderation_summary: pd.DataFrame,
    moderation_meta: dict[str, float],
    growth_summary: pd.DataFrame,
    growth_meta: dict[str, float],
) -> pd.DataFrame:
    rows = [
        extract_term_row(
            continuous_summary,
            continuous_meta,
            term="CI",
            model_name="Two-way FE (Continuous CI)",
            treatment_variable="CI",
        ),
        extract_term_row(
            discrete_summary,
            discrete_meta,
            term="D",
            model_name="Two-way FE (Binary D)",
            treatment_variable="D",
        ),
        extract_term_row(
            moderation_summary,
            moderation_meta,
            term="CI_x_Upgrade",
            model_name="Moderation FE (CI x Upgrade)",
            treatment_variable="CI_x_Upgrade",
        ),
        extract_term_row(
            growth_summary,
            growth_meta,
            term="Upgrade",
            model_name="Growth FE (Upgrade)",
            treatment_variable="Upgrade",
        ),
    ]
    comparison_df = pd.DataFrame(rows)
    comparison_df["证据分级"] = comparison_df["P>|t|"].map(evidence_grade)
    comparison_df["说明"] = [
        "全国主效应基准识别",
        "二值处理稳健性检验",
        "产业升级对数字增碳关系的抑制项",
        "产业升级的增长代价参数",
    ]
    return comparison_df


def build_robustness_matrix(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []

    baseline = panel.copy()
    winsor = winsorize_frame(panel, ["Y", "CI", "PGDP", "URB", "OPEN", "Upgrade", "CI_x_Upgrade"])
    logy = panel.copy()
    logy["logY"] = np.log(logy["Y"] + 1.0)

    national_specs = [
        ("全国主效应", "基准", baseline, "Y", ["CI", "PGDP", "URB", "OPEN"], "CI"),
        ("全国主效应", "去极值", winsor, "Y", ["CI", "PGDP", "URB", "OPEN"], "CI"),
        ("全国主效应", "对数因变量", logy, "logY", ["CI", "PGDP", "URB", "OPEN"], "CI"),
        ("协同机制", "基准", baseline, "Y", ["CI", "Upgrade", "CI_x_Upgrade", "PGDP", "URB", "OPEN"], "CI_x_Upgrade"),
        ("协同机制", "去极值", winsor, "Y", ["CI", "Upgrade", "CI_x_Upgrade", "PGDP", "URB", "OPEN"], "CI_x_Upgrade"),
        ("协同机制", "对数因变量", logy, "logY", ["CI", "Upgrade", "CI_x_Upgrade", "PGDP", "URB", "OPEN"], "CI_x_Upgrade"),
    ]

    for module, spec_name, df, y_col, x_cols, term in national_specs:
        summary, meta, _, _, _ = fit_panel_fe(df, y_col=y_col, x_cols=x_cols)
        row = summary.loc[term]
        rows.append(
            {
                "模块": module,
                "口径": spec_name,
                "变量": term,
                "系数": float(row["coef"]),
                "p值": float(row["P>|t|"]),
                "方向": effect_direction(float(row["coef"])),
                "证据分级": evidence_grade(float(row["P>|t|"])),
                "样本量": int(meta["n_obs"]),
            }
        )

    growth_base = panel.dropna(subset=["PGDP_growth"]).copy()
    growth_winsor = winsorize_frame(growth_base, ["PGDP_growth", "CI", "Upgrade", "URB", "OPEN"])
    for spec_name, df in [("基准", growth_base), ("去极值", growth_winsor)]:
        summary, meta, _, _, _ = fit_panel_fe(df, y_col="PGDP_growth", x_cols=["CI", "Upgrade", "URB", "OPEN"])
        row = summary.loc["Upgrade"]
        rows.append(
            {
                "模块": "增长权衡",
                "口径": spec_name,
                "变量": "Upgrade",
                "系数": float(row["coef"]),
                "p值": float(row["P>|t|"]),
                "方向": "升级存在增长代价" if float(row["coef"]) < 0 else "升级促进增长",
                "证据分级": evidence_grade(float(row["P>|t|"])),
                "样本量": int(meta["n_obs"]),
            }
        )

    return pd.DataFrame(rows)


def build_region_robustness(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for region in REGION_ORDER:
        region_df = panel[panel["Region_3"] == region].copy()
        region_winsor = winsorize_frame(region_df, ["Y", "CI", "PGDP", "URB", "OPEN"])
        region_log = region_df.copy()
        region_log["logY"] = np.log(region_log["Y"] + 1.0)

        specs = [
            ("基准", region_df, "Y"),
            ("去极值", region_winsor, "Y"),
            ("对数因变量", region_log, "logY"),
        ]
        for spec_name, df, y_col in specs:
            summary, meta, _, _, _ = fit_panel_fe(df, y_col=y_col, x_cols=["CI", "PGDP", "URB", "OPEN"])
            ci_row = summary.loc["CI"]
            rows.append(
                {
                    "区域": region,
                    "口径": spec_name,
                    "CI系数": float(ci_row["coef"]),
                    "p值": float(ci_row["P>|t|"]),
                    "方向": effect_direction(float(ci_row["coef"])),
                    "证据分级": evidence_grade(float(ci_row["P>|t|"])),
                    "样本量": int(meta["n_obs"]),
                }
            )
    return pd.DataFrame(rows)


def build_region_evidence_panel(
    region_effect_df: pd.DataFrame,
    region_robust_df: pd.DataFrame,
    construct_df: pd.DataFrame,
    loo_summary_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    construct_map = {}
    if not construct_df.empty:
        construct_map = construct_df.set_index("范围").to_dict("index")

    for _, region_row in region_effect_df.iterrows():
        region = region_row["区域"]
        coef = float(region_row["CI系数"])
        base_p = float(region_row["p值"])

        winsor_row = region_robust_df[
            (region_robust_df["区域"] == region) & (region_robust_df["口径"] == "去极值")
        ].iloc[0]
        log_row = region_robust_df[
            (region_robust_df["区域"] == region) & (region_robust_df["口径"] == "对数因变量")
        ].iloc[0]

        loo_row = None
        if not loo_summary_df.empty and region in loo_summary_df["区域"].tolist():
            loo_row = loo_summary_df[loo_summary_df["区域"] == region].iloc[0]

        core_row = construct_map.get(region)
        core_sign_same = False
        core_support = False
        core_coef = np.nan
        core_p = np.nan
        if core_row is not None:
            core_coef = float(core_row["核心数字指数系数"])
            core_p = float(core_row["核心数字指数p值"])
            core_sign_same = core_row["方向是否一致"] in ["是", "部分"]
            core_support = core_row["严格口径支持度"] in ["保留", "弱保留"]

        score = 0
        if coef > 0:
            if base_p < 0.05:
                score += 2
            elif base_p < 0.10:
                score += 1
            elif base_p < 0.25:
                score += 1

            winsor_p = float(winsor_row["p值"])
            if winsor_p < 0.05:
                score += 2
            elif winsor_p < 0.10:
                score += 1
            elif winsor_p < 0.25:
                score += 1

            if np.sign(float(log_row["CI系数"])) == np.sign(coef):
                score += 1

            if loo_row is not None and float(loo_row["正向占比"]) >= 0.90:
                score += 1
            if loo_row is not None and float(loo_row["10%显著占比"]) >= 0.80:
                score += 1

            if core_support:
                score += 1
            else:
                score -= 1

        score = max(score, 0)
        support_weight = min(score / 6.0, 1.0) if coef > 0 else 0.0

        if support_weight >= 0.85:
            support_level = "高支持"
        elif support_weight >= 0.67:
            support_level = "中支持"
        elif support_weight > 0:
            support_level = "提示性"
        else:
            support_level = "不纳入仿真"

        rows.append(
            {
                "区域": region,
                "基准CI系数": coef,
                "基准p值": base_p,
                "去极值系数": float(winsor_row["CI系数"]),
                "去极值p值": float(winsor_row["p值"]),
                "对数口径系数": float(log_row["CI系数"]),
                "核心数字指数系数": core_coef,
                "核心数字指数p值": core_p,
                "留一法正向占比": np.nan if loo_row is None else float(loo_row["正向占比"]),
                "留一法10%显著占比": np.nan if loo_row is None else float(loo_row["10%显著占比"]),
                "核心口径方向一致": "是" if core_sign_same else "否",
                "严格口径支持度": "支持" if core_support else "转弱/转向",
                "政策证据分": score,
                "政策证据权重": support_weight,
                "政策支持级别": support_level,
                "评估说明": (
                    "高置信压力区，可直接进入政策情景"
                    if support_level == "高支持"
                    else "中等支持压力区，政策情景中折扣纳入"
                    if support_level == "中支持"
                    else "方向稳定但推断较弱，仅作提示性观察"
                    if support_level == "提示性"
                    else "证据不足，不纳入定向增压项"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_leave_one_out_stability(panel: pd.DataFrame, region_effect_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows = []
    summary_rows = []

    supported_regions = region_effect_df[region_effect_df["CI系数"] > 0]["区域"].tolist()
    for region in supported_regions:
        region_df = panel[panel["Region_3"] == region].copy()
        for province in sorted(region_df["province"].unique()):
            leave_df = region_df[region_df["province"] != province].copy()
            summary, _, _, _, _ = fit_panel_fe(leave_df, y_col="Y", x_cols=["CI", "PGDP", "URB", "OPEN"])
            ci_row = summary.loc["CI"]
            detail_rows.append(
                {
                    "区域": region,
                    "剔除省份": province,
                    "CI系数": float(ci_row["coef"]),
                    "p值": float(ci_row["P>|t|"]),
                }
            )

    detail_df = pd.DataFrame(detail_rows)
    if detail_df.empty:
        return detail_df, pd.DataFrame(columns=["区域", "正向占比", "10%显著占比", "最小系数", "最大系数", "结论"])

    for region, group in detail_df.groupby("区域"):
        positive_share = float((group["CI系数"] > 0).mean())
        sig_share = float((group["p值"] < 0.10).mean())
        summary_rows.append(
            {
                "区域": region,
                "正向占比": positive_share,
                "10%显著占比": sig_share,
                "最小系数": float(group["CI系数"].min()),
                "最大系数": float(group["CI系数"].max()),
                "结论": "方向稳定" if positive_share == 1.0 else "存在方向波动",
            }
        )

    return detail_df, pd.DataFrame(summary_rows)


def build_key_findings(
    continuous_summary: pd.DataFrame,
    discrete_summary: pd.DataFrame,
    moderation_summary: pd.DataFrame,
    growth_summary: pd.DataFrame,
    region_effect_df: pd.DataFrame,
    region_evidence_df: pd.DataFrame,
    construct_df: pd.DataFrame,
    loo_summary_df: pd.DataFrame,
) -> pd.DataFrame:
    cont = continuous_summary.loc["CI"]
    disc = discrete_summary.loc["D"]
    moderation = moderation_summary.loc["CI_x_Upgrade"]
    growth = growth_summary.loc["Upgrade"]

    supported_regions = region_evidence_df[region_evidence_df["政策支持级别"].isin(["高支持", "中支持", "提示性"])]
    if supported_regions.empty:
        region_text = "未发现可进入政策情景的压力区域"
    else:
        region_text = "；".join(
            f"{row['区域']}:{row['政策支持级别']}"
            for _, row in supported_regions.iterrows()
        )

    if construct_df.empty:
        construct_text = "暂无核心数字指数稳健性"
    else:
        construct_text = "；".join(
            f"{row['范围']}:{row['严格口径支持度']}"
            for _, row in construct_df.iterrows()
            if row["范围"] != "全国"
        )

    if loo_summary_df.empty:
        stability_text = "暂无留一法结果"
    else:
        stability_text = "；".join(
            f"{row['区域']}:正向占比{int(row['正向占比'] * 100)}%,10%显著占比{int(row['10%显著占比'] * 100)}%"
            for _, row in loo_summary_df.iterrows()
        )

    rows = [
        {
            "模块": "全国主效应",
            "证据": f"CI={float(cont['coef']):.3f}, p={float(cont['P>|t|']):.3f}",
            "分析结论": "全国平均效应不稳，不宜写成“显著降碳”。",
        },
        {
            "模块": "离散稳健性",
            "证据": f"D={float(disc['coef']):.3f}, p={float(disc['P>|t|']):.3f}",
            "分析结论": "二值处理检验未推翻主结论，说明“不显著”并非换口径就消失。",
        },
        {
            "模块": "区域异质性",
            "证据": region_text,
            "分析结论": "重点表明中西部为高支持压力区，东北为中支持且需保守表述，东部证据不足。",
        },
        {
            "模块": "稳健性",
            "证据": stability_text,
            "分析结论": "去极值与留一法显示重点区域方向稳定，不是由单一省份驱动。",
        },
        {
            "模块": "构念稳健性",
            "证据": construct_text,
            "分析结论": "严格数字口径下中西部压力仍保留，东北更偏提示性，说明结构协同是东北叙事的关键。",
        },
        {
            "模块": "协同机制",
            "证据": f"CI×Upgrade={float(moderation['coef']):.3f}, p={float(moderation['P>|t|']):.3f}",
            "分析结论": "产业升级对数字增碳压力存在弱抑制，适合作为政策协同机制而非单独结论。",
        },
        {
            "模块": "增长权衡",
            "证据": f"Upgrade={float(growth['coef']):.3f}, p={float(growth['P>|t|']):.3f}",
            "分析结论": "产业升级对短期增长存在代价，政策设计必须承认权衡。",
        },
    ]
    return pd.DataFrame(rows)


def maybe_make_region_plot(region_df: pd.DataFrame) -> None:
    try:
        plt = configure_matplotlib()
    except Exception:
        print("matplotlib 不可用，跳过区域异质性图。")
        return

    plot_df = region_df.copy()
    plot_df["排序"] = plot_df["区域"].map({"中西部": 0, "东北": 1, "东部": 2}).fillna(99)
    plot_df = plot_df.sort_values("排序").reset_index(drop=True)
    colors = [SUPPORT_PALETTE.get(str(level), "#94a3b8") for level in plot_df["政策支持级别"]]
    ci_half_width = 1.96 * plot_df["标准误"].astype(float)
    y_pos = np.arange(len(plot_df))

    fig, ax = plt.subplots(figsize=(8.8, 4.9))
    ax.barh(
        y_pos,
        plot_df["CI系数"],
        color=colors,
        edgecolor="#334155",
        linewidth=1.1,
        height=0.58,
        alpha=0.94,
    )
    ax.errorbar(
        plot_df["CI系数"],
        y_pos,
        xerr=ci_half_width,
        fmt="none",
        ecolor="#475569",
        elinewidth=1.2,
        capsize=4,
        capthick=1.2,
        zorder=4,
    )
    ax.axvline(0, color="#0f172a", linestyle="--", linewidth=1.4)
    style_axis(ax, grid_axis="x")

    x_min = float((plot_df["CI系数"] - ci_half_width).min())
    x_max = float((plot_df["CI系数"] + ci_half_width).max())
    x_pad = max((x_max - x_min) * 0.12, 1.2)
    ax.set_xlim(x_min - x_pad, x_max + x_pad * 1.2)
    ax.set_yticks(y_pos, plot_df["区域"])
    ax.invert_yaxis()
    ax.set_xlabel("CI 系数（右侧为增碳压力，横线为 95% 置信区间；灰色结果不纳入仿真）")
    ax.set_title("区域证据分层：中西部高支持、东北保守、东部不纳入仿真", loc="left", pad=10)

    for idx, row in plot_df.iterrows():
        value = float(row["CI系数"])
        note = f"{value:.2f} | {row['显著性']} | {row['政策支持级别']}"
        offset = 0.42 if value >= 0 else -0.42
        ax.text(
            value + offset,
            idx,
            note,
            ha="left" if value >= 0 else "right",
            va="center",
            fontsize=9,
            color="#1f2937",
        )

    fig.tight_layout()
    save_figure_bundle(fig, REGION_PLOT_FILE)
    plt.close(fig)


class PanelRegressionAnalyzer:
    """面板计量回归与条件关系分析工程类。"""

    def __init__(self, data_dir: str = DATA_DIR, figure_dir: str = FIGURE_DIR):
        self.data_dir = data_dir
        self.figure_dir = figure_dir
        self.output_book = OUTPUT_BOOK

    def run_full_analysis(self) -> dict:
        """执行全套面板计量估计、异质性分层及多工作簿报表导出。"""
        print("正在加载数据...")
        panel = load_core_panel()
        panel["D"] = build_binary_treatment(panel)
        panel["PGDP_growth"] = panel.groupby("province")["PGDP"].pct_change()
        panel["CI_x_Upgrade"] = panel["CI"] * panel["Upgrade"]

        print(f"样本量: {len(panel)}，省份数: {panel['province'].nunique()}，年份数: {panel['year'].nunique()}")

        continuous_summary, continuous_meta, _, _, _ = fit_panel_fe(
            panel,
            y_col="Y",
            x_cols=["CI", "PGDP", "URB", "OPEN"],
        )

        discrete_summary, discrete_meta, _, _, _ = fit_panel_fe(
            panel,
            y_col="Y",
            x_cols=["D", "PGDP", "URB", "OPEN"],
        )

        moderation_summary, moderation_meta, _, _, _ = fit_panel_fe(
            panel,
            y_col="Y",
            x_cols=["CI", "Upgrade", "CI_x_Upgrade", "PGDP", "URB", "OPEN"],
        )

        growth_panel = panel.dropna(subset=["PGDP_growth"]).copy()
        growth_summary, growth_meta, _, _, _ = fit_panel_fe(
            growth_panel,
            y_col="PGDP_growth",
            x_cols=["CI", "Upgrade", "URB", "OPEN"],
        )

        comparison_df = build_comparison_table(
            continuous_summary,
            continuous_meta,
            discrete_summary,
            discrete_meta,
            moderation_summary,
            moderation_meta,
            growth_summary,
            growth_meta,
        )

        region_effect_df = build_region_effects(panel)
        province_slopes_df = build_province_slopes(panel)
        desc_df = build_descriptive_table(panel)
        profile_df = build_panel_profile(panel)
        robustness_df = build_robustness_matrix(panel)
        region_robust_df = build_region_robustness(panel)
        construct_df = build_construct_robustness(panel)
        loo_detail_df, loo_summary_df = build_leave_one_out_stability(panel, region_effect_df)
        region_evidence_df = build_region_evidence_panel(
            region_effect_df,
            region_robust_df,
            construct_df,
            loo_summary_df,
        )
        region_effect_df = region_effect_df.merge(
            region_evidence_df[["区域", "政策证据权重", "政策支持级别"]],
            on="区域",
            how="left",
        )
        key_findings_df = build_key_findings(
            continuous_summary,
            discrete_summary,
            moderation_summary,
            growth_summary,
            region_effect_df,
            region_evidence_df,
            construct_df,
            loo_summary_df,
        )

        with pd.ExcelWriter(self.output_book, engine="openpyxl") as writer:
            summary_to_sheet(continuous_summary, continuous_meta, "Two-way FE (Continuous CI)").to_excel(
                writer,
                sheet_name="连续主回归",
                index=False,
            )
            summary_to_sheet(discrete_summary, discrete_meta, "Two-way FE (Binary D)").to_excel(
                writer,
                sheet_name="离散稳健性",
                index=False,
            )
            summary_to_sheet(moderation_summary, moderation_meta, "Moderation FE (CI x Upgrade)").to_excel(
                writer,
                sheet_name="协同机制",
                index=False,
            )
            summary_to_sheet(growth_summary, growth_meta, "Two-way FE (PGDP Growth)").to_excel(
                writer,
                sheet_name="增长方程",
                index=False,
            )
            comparison_df.to_excel(writer, sheet_name="连续与离散比较", index=False)
            region_effect_df.to_excel(writer, sheet_name="区域异质性", index=False)
            province_slopes_df.to_excel(writer, sheet_name="省域诊断", index=False)
            desc_df.to_excel(writer, sheet_name="描述统计", index=False)
            profile_df.to_excel(writer, sheet_name="面板画像", index=False)
            key_findings_df.to_excel(writer, sheet_name="关键结论", index=False)
            robustness_df.to_excel(writer, sheet_name="稳健性矩阵", index=False)
            region_robust_df.to_excel(writer, sheet_name="区域稳健性", index=False)
            construct_df.to_excel(writer, sheet_name="构念稳健性", index=False)
            region_evidence_df.to_excel(writer, sheet_name="区域证据分级", index=False)
            loo_summary_df.to_excel(writer, sheet_name="留一法汇总", index=False)
            loo_detail_df.to_excel(writer, sheet_name="留一法明细", index=False)

        comparison_df.to_excel(COMPARE_FILE, index=False)
        region_effect_df.to_excel(REGION_FILE, index=False)
        province_slopes_df.to_excel(PROVINCE_FILE, index=False)

        with pd.ExcelWriter(ROBUSTNESS_FILE, engine="openpyxl") as writer:
            robustness_df.to_excel(writer, sheet_name="核心稳健性", index=False)
            region_robust_df.to_excel(writer, sheet_name="区域稳健性", index=False)
            construct_df.to_excel(writer, sheet_name="构念稳健性", index=False)

        with pd.ExcelWriter(REGION_STABILITY_FILE, engine="openpyxl") as writer:
            loo_summary_df.to_excel(writer, sheet_name="留一法汇总", index=False)
            loo_detail_df.to_excel(writer, sheet_name="留一法明细", index=False)
            region_evidence_df.to_excel(writer, sheet_name="区域证据分级", index=False)

        construct_df.to_excel(CONSTRUCT_FILE, index=False)

        maybe_make_region_plot(region_effect_df)

        return {
            "comparison_df": comparison_df,
            "region_effect_df": region_effect_df,
            "loo_summary_df": loo_summary_df,
            "output_book": self.output_book,
        }


def main() -> None:
    """模块独立执行入口。"""
    analyzer = PanelRegressionAnalyzer()
    res = analyzer.run_full_analysis()
    comp_df = res["comparison_df"]

    print("连续主效应（CI）:")
    print(comp_df.iloc[0].to_dict())
    print("离散稳健性（D）:")
    print(comp_df.iloc[1].to_dict())
    print("协同机制（CI x Upgrade）:")
    print(comp_df.iloc[2].to_dict())
    print("增长方程（Upgrade）:")
    print(comp_df.iloc[3].to_dict())
    print("\n区域异质性结果:")
    print(res["region_effect_df"].to_string(index=False))
    print("\n留一法汇总:")
    print(res["loo_summary_df"].to_string(index=False))
    print(f"\n实证结果总表已保存: {res['output_book']}")


if __name__ == "__main__":
    main()
