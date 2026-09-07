# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：data_quality_checker (数据完整性审计与质量体检模块)
功能描述：
1. 原始数据源全量体检：全面审计 9 份基础源表年份跨度、省份对齐、缺失值及非数值项分布。
2. 平衡面板清洗核查：跟踪省份样本准入准出逻辑，审计孤立尖峰 (Isolated Spikes) 留痕插值修正。
3. 全链条数据一致性审计：比对基准 CI 测算、双向 FE 回归模型与动态政策仿真多情景预测终值的一致性。
4. 交付文件时间戳审计：校验各工作簿更新时序与文件可加载完整性，输出 JSON 格式系统体检报告。
================================================================================
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from model_utils import find_project_root, get_raw_data_dir, list_input_files_metadata, repair_isolated_spikes


CODE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(find_project_root())
RAW_DATA_DIR = Path(get_raw_data_dir())
ROOT = PROJECT_DIR / "04_核心结果"
SIM_DIR = ROOT / "simulation_results"
YEARS_TARGET = list(range(2011, 2023))

SOURCE_FILES = [
    "省份等级的灯光值_平均值.xlsx",
    "数字经济指数_2011_2022.xlsx",
    "能源消费量_万吨标煤.xlsx",
    "产业结构高级化_第二产业占比.xlsx",
    "碳排放量_万吨.xlsx",
    "碳排放强度_万吨亿元GDP.xlsx",
    "人均GDP.xlsx",
    "城镇化率_2000_2022.xlsx",
    "对外开放程度_2000_2022.xlsx",
]

SCENARIO_FILES = [
    "基准情景.xlsx",
    "数字加速情景.xlsx",
    "政策强化情景.xlsx",
    "定向协同情景.xlsx",
    "Pareto最优路径.xlsx",
]

def normalize_province(value: object) -> str:
    text = str(value)
    for token in ["省", "市", "自治区", "维吾尔", "回族", "壮族", "特别行政区"]:
        text = text.replace(token, "")
    return text


def read_source_panel(filepath: Path, value_name: str) -> pd.DataFrame:
    df = pd.read_excel(filepath, index_col=0)
    year_cols: list[object] = []
    for col in df.columns:
        try:
            year = int(col)
        except (TypeError, ValueError):
            continue
        if year in YEARS_TARGET:
            year_cols.append(col)

    panel = df[year_cols].copy()
    panel.index.name = "province"
    panel.columns = [int(col) for col in panel.columns]
    long_df = panel.stack().reset_index()
    long_df.columns = ["province", "year", value_name]
    long_df["province"] = long_df["province"].map(normalize_province)
    return long_df


def to_jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def add_issue(issues: list[str], text: str) -> None:
    if text not in issues:
        issues.append(text)


def check_sources(report: dict[str, object], issues: list[str]) -> dict[str, set[str]]:
    province_sets: dict[str, set[str]] = {}

    for filename in SOURCE_FILES:
        path = RAW_DATA_DIR / filename
        xls = pd.ExcelFile(path)
        df = pd.read_excel(path, index_col=0)

        year_cols: list[object] = []
        for col in df.columns:
            try:
                year = int(col)
            except (TypeError, ValueError):
                continue
            if year in YEARS_TARGET:
                year_cols.append(col)

        wide = df[year_cols].copy()
        provinces = [normalize_province(index) for index in wide.index]
        province_sets[filename] = set(provinces)

        numeric_series = pd.to_numeric(wide.stack(), errors="coerce") if not wide.empty else pd.Series(dtype=float)
        total_non_na = int(wide.stack().shape[0]) if not wide.empty else 0
        numeric_non_na = int(numeric_series.notna().sum())
        non_numeric_non_na = total_non_na - numeric_non_na

        source_info = {
            "sheets": xls.sheet_names,
            "rows": int(wide.shape[0]),
            "year_cols_2011_2022": [int(col) for col in year_cols],
            "year_count": len(year_cols),
            "province_count": len(provinces),
            "duplicate_province_names": int(pd.Series(provinces).duplicated().sum()),
            "missing_cells": int(wide.isna().sum().sum()),
            "non_numeric_non_na_cells": int(non_numeric_non_na),
            "min_value": None if numeric_series.empty else float(numeric_series.min()),
            "max_value": None if numeric_series.empty else float(numeric_series.max()),
        }
        report["source_checks"][filename] = source_info

        if len(year_cols) != 12:
            add_issue(issues, f"{filename}: 2011-2022 年份列数量为 {len(year_cols)}，不是 12")
        if source_info["duplicate_province_names"]:
            add_issue(issues, f"{filename}: 存在重复省份名 {source_info['duplicate_province_names']} 个")
        if source_info["missing_cells"]:
            add_issue(issues, f"{filename}: 存在缺失单元格 {source_info['missing_cells']} 个")
        if source_info["non_numeric_non_na_cells"]:
            add_issue(issues, f"{filename}: 存在非数值且非空单元格 {source_info['non_numeric_non_na_cells']} 个")

    baseline_name = SOURCE_FILES[0]
    baseline_provinces = province_sets[baseline_name]
    for filename, provinces in province_sets.items():
        delta = sorted((provinces - baseline_provinces) | (baseline_provinces - provinces))
        if delta:
            add_issue(issues, f"{filename}: 省份集合与 {baseline_name} 不一致，差异样本 {delta[:10]}")

    # 自定义扩展输入文件体检
    report["custom_sources_checks"] = {}
    for meta in list_input_files_metadata(str(RAW_DATA_DIR)):
        if meta.get("is_custom"):
            c_fname = meta["file"]
            c_path = RAW_DATA_DIR / c_fname
            if c_path.exists():
                try:
                    c_df = pd.read_excel(c_path)
                    report["custom_sources_checks"][c_fname] = {
                        "status": "✓ 正常已接入",
                        "rows": int(c_df.shape[0]),
                        "cols": int(c_df.shape[1]),
                        "missing_cells": int(c_df.isna().sum().sum()),
                        "role": meta.get("role", "自定义扩展"),
                    }
                except Exception as e:
                    report["custom_sources_checks"][c_fname] = {
                        "status": "✗ 读取失败",
                        "error": str(e),
                    }
                    add_issue(issues, f"自定义文件 {c_fname} 校验异常: {e}")

    return province_sets


def check_panel_merge(report: dict[str, object], issues: list[str]) -> pd.DataFrame:
    tech = read_source_panel(RAW_DATA_DIR / "数字经济指数_2011_2022.xlsx", "Tech")
    ntl = read_source_panel(RAW_DATA_DIR / "省份等级的灯光值_平均值.xlsx", "NTL")
    energy = read_source_panel(RAW_DATA_DIR / "能源消费量_万吨标煤.xlsx", "Energy")
    industry = read_source_panel(RAW_DATA_DIR / "产业结构高级化_第二产业占比.xlsx", "Industry")
    y = read_source_panel(RAW_DATA_DIR / "碳排放强度_万吨亿元GDP.xlsx", "Y")
    pgdp = read_source_panel(RAW_DATA_DIR / "人均GDP.xlsx", "PGDP")
    urb = read_source_panel(RAW_DATA_DIR / "城镇化率_2000_2022.xlsx", "URB")
    open_df = read_source_panel(RAW_DATA_DIR / "对外开放程度_2000_2022.xlsx", "OPEN")

    index_panel_raw = tech.merge(ntl, on=["province", "year"]).merge(energy, on=["province", "year"]).merge(
        industry,
        on=["province", "year"],
    )
    index_panel = index_panel_raw.dropna(subset=["Tech", "NTL", "Energy", "Industry"]).copy()
    full_panel_raw = (
        index_panel_raw.merge(y, on=["province", "year"])
        .merge(pgdp, on=["province", "year"])
        .merge(urb, on=["province", "year"])
        .merge(open_df, on=["province", "year"])
    )
    full_panel = full_panel_raw.dropna(subset=["Tech", "NTL", "Energy", "Industry", "Y", "PGDP", "URB", "OPEN"]).copy()
    full_panel, anomaly_df = repair_isolated_spikes(full_panel, "Y")
    anomaly_path = ROOT / "数据异常修正记录.xlsx"
    try:
        anomaly_df.to_excel(anomaly_path, index=False)
    except PermissionError:
        fallback_path = anomaly_path.with_name(f"{anomaly_path.stem}_刷新副本{anomaly_path.suffix}")
        anomaly_df.to_excel(fallback_path, index=False)
        report["anomaly_record_fallback"] = str(fallback_path)

    report["panel_merge"] = {
        "index_panel_rows_raw": int(index_panel_raw.shape[0]),
        "index_panel_rows_model_ready": int(index_panel.shape[0]),
        "full_panel_rows_raw": int(full_panel_raw.shape[0]),
        "full_panel_rows_model_ready": int(full_panel.shape[0]),
        "province_count": int(full_panel["province"].nunique()),
        "year_count": int(full_panel["year"].nunique()),
        "duplicate_province_year": int(full_panel.duplicated(["province", "year"]).sum()),
        "any_missing": bool(full_panel.isna().any().any()),
        "excluded_provinces_after_dropna": sorted(set(full_panel_raw["province"]) - set(full_panel["province"])),
        "isolated_spike_repairs": anomaly_df.to_dict(orient="records"),
    }

    if full_panel.shape[0] != 360:
        add_issue(issues, f"合并后的 full panel 行数为 {full_panel.shape[0]}，不是 360")
    if report["panel_merge"]["duplicate_province_year"]:
        add_issue(issues, "full panel 存在重复的 province-year")
    if report["panel_merge"]["any_missing"]:
        add_issue(issues, "full panel 合并后仍存在缺失值")
    excluded = report["panel_merge"]["excluded_provinces_after_dropna"]
    if excluded:
        add_issue(issues, f"原始源表经缺失清洗后排除了省份 {excluded}；当前模型样本按 30 省处理")
    if not anomaly_df.empty:
        add_issue(issues, f"建模面板按预设规则修正了 {len(anomaly_df)} 个孤立尖峰，详见 数据异常修正记录.xlsx")

    return full_panel


def check_derived_outputs(report: dict[str, object], issues: list[str]) -> None:
    required_files = [
        ROOT / "数字赋能指数_测算结果.xlsx",
        ROOT / "熵权法_权重汇总.xlsx",
        ROOT / "实证结果_连续与离散比较.xlsx",
        ROOT / "实证结果_区域异质性.xlsx",
        ROOT / "实证结果_构念稳健性.xlsx",
        ROOT / "实证结果_完整回归表.xlsx",
    ]
    if not all(p.exists() for p in required_files):
        report["derived_checks"] = {
            "status": "pending_generation",
            "note": "衍生计算文件待后续流水线阶段解算生成",
            "weight_sum_by_index": {},
        }
        return

    ci = pd.read_excel(ROOT / "数字赋能指数_测算结果.xlsx")
    weights = pd.read_excel(ROOT / "熵权法_权重汇总.xlsx")
    compare = pd.read_excel(ROOT / "实证结果_连续与离散比较.xlsx")
    region = pd.read_excel(ROOT / "实证结果_区域异质性.xlsx")
    construct = pd.read_excel(ROOT / "实证结果_构念稳健性.xlsx")
    full_book = pd.ExcelFile(ROOT / "实证结果_完整回归表.xlsx")

    report["derived_checks"] = {
        "ci_rows": int(ci.shape[0]),
        "ci_duplicate_province_year": int(ci.duplicated(["province", "year"]).sum()),
        "ci_missing": int(ci[["CI", "CI_core"]].isna().sum().sum()),
        "ci_range": {
            "CI_min": float(ci["CI"].min()),
            "CI_max": float(ci["CI"].max()),
            "CI_core_min": float(ci["CI_core"].min()),
            "CI_core_max": float(ci["CI_core"].max()),
        },
        "weight_sum_by_index": weights.groupby("指数方案")["权重"].sum().round(8).to_dict(),
        "compare_models": compare[["Treatment_Variable", "coef", "P>|t|"]].to_dict(orient="records"),
        "region_levels": region[["区域", "CI系数", "p值", "政策证据权重", "政策支持级别"]].to_dict(
            orient="records",
        ),
        "construct_rows": construct.to_dict(orient="records"),
        "full_book_sheets": full_book.sheet_names,
    }

    if ci.shape[0] != 360:
        add_issue(issues, f"数字赋能指数_测算结果.xlsx 行数为 {ci.shape[0]}，不是 360")
    if ci.duplicated(["province", "year"]).sum():
        add_issue(issues, "数字赋能指数_测算结果.xlsx 存在重复的省份-年份组合")
    if ci[["CI", "CI_core"]].isna().sum().sum() > 0:
        add_issue(issues, "数字赋能指数_测算结果.xlsx 包含缺失值")

    for index_name, weight_sum in report["derived_checks"]["weight_sum_by_index"].items():
        if abs(weight_sum - 1.0) > 1e-6:
            add_issue(issues, f"{index_name} 权重和为 {weight_sum}，不是 1")

def check_simulation_outputs(report: dict[str, object], issues: list[str]) -> None:
    required_sim_files = [SIM_DIR / filename for filename in SCENARIO_FILES] + [
        SIM_DIR / "政策仿真最终结果.xlsx",
        SIM_DIR / "策略组合_对比结果.xlsx",
        SIM_DIR / "政策分型_省份清单.xlsx",
    ]
    if not all(p.exists() for p in required_sim_files):
        report["sim_checks"] = {
            "status": "pending_generation",
            "note": "政策多目标仿真文件待第 4 阶段执行生成",
        }
        return

    sim_checks: dict[str, object] = {}
    scenarios = {filename: pd.read_excel(SIM_DIR / filename) for filename in SCENARIO_FILES}
    summary = pd.read_excel(SIM_DIR / "政策仿真最终结果.xlsx")
    strategy = pd.read_excel(SIM_DIR / "策略组合_对比结果.xlsx")
    policy_zone = pd.read_excel(SIM_DIR / "政策分型_省份清单.xlsx", sheet_name="省份分型")
    policy_zone_summary = pd.read_excel(SIM_DIR / "政策分型_省份清单.xlsx", sheet_name="分型汇总")

    for filename, df in scenarios.items():
        sim_checks[filename] = {
            "rows": int(df.shape[0]),
            "year_min": int(df["year"].min()),
            "year_max": int(df["year"].max()),
            "year_unique": int(df["year"].nunique()),
            "missing_cells": int(df.isna().sum().sum()),
        }
        if sim_checks[filename]["rows"] != 14:
            add_issue(issues, f"{filename}: 情景表行数为 {sim_checks[filename]['rows']}，不是 14")
        if sim_checks[filename]["year_min"] != 2022 or sim_checks[filename]["year_max"] != 2035:
            add_issue(issues, f"{filename}: 年份区间不是 2022-2035")
        if sim_checks[filename]["year_unique"] != 14:
            add_issue(issues, f"{filename}: 年份数量为 {sim_checks[filename]['year_unique']}，不是 14")
        if sim_checks[filename]["missing_cells"]:
            add_issue(issues, f"{filename}: 存在缺失单元格 {sim_checks[filename]['missing_cells']} 个")

    summary_map = {row["情景"]: float(row["2035碳强度预测"]) for _, row in summary.iterrows()}
    for filename, df in scenarios.items():
        scene_name = filename.replace(".xlsx", "")
        y_2035 = float(df.loc[df["year"] == 2035, "Y_pred"].iloc[0])
        if scene_name in summary_map and abs(summary_map[scene_name] - y_2035) > 1e-9:
            add_issue(issues, f"政策汇总表与 {scene_name} 情景文件的 2035 碳强度不一致")

    key_cols = ["情景", "策略类型", "2035碳强度预测", "平均人均GDP增长率"]
    if not summary[key_cols].equals(strategy[key_cols]):
        add_issue(issues, "政策仿真最终结果.xlsx 与 策略组合_对比结果.xlsx 的关键列不一致")

    zone_total = int(policy_zone.shape[0])
    zone_summary_total = int(policy_zone_summary["省份数"].sum())
    sim_checks["policy_zone"] = {
        "province_rows": zone_total,
        "summary_total": zone_summary_total,
        "types": sorted(policy_zone["政策分型"].unique().tolist()),
    }
    if zone_total != 30:
        add_issue(issues, f"政策分型_省份清单.xlsx 省份分型行数为 {zone_total}，不是 30")
    if zone_summary_total != 30:
        add_issue(issues, f"政策分型_省份清单.xlsx 分型汇总省份数合计为 {zone_summary_total}，不是 30")

    report["sim_checks"] = sim_checks


def check_stale_files(report: dict[str, object], issues: list[str]) -> None:
    summary_file = ROOT / "综合评估与仿真分析汇总表.xlsx"
    pipeline_outputs = [
        ROOT / "数字赋能指数_测算结果.xlsx",
        ROOT / "实证结果_完整回归表.xlsx",
        SIM_DIR / "政策仿真最终结果.xlsx",
        summary_file,
    ]
    existing_outputs = [path.stat().st_mtime for path in pipeline_outputs if path.exists()]
    if not existing_outputs:
        report["stale_files"] = []
        return
    latest_pipeline_time = max(existing_outputs)

    stale_candidates = []
    for path in sorted(SIM_DIR.glob("*.xlsx")):
        if path.name in {
            "基准情景.xlsx",
            "数字加速情景.xlsx",
            "政策强化情景.xlsx",
            "定向协同情景.xlsx",
            "Pareto最优路径.xlsx",
            "政策仿真最终结果.xlsx",
            "策略组合_对比结果.xlsx",
            "政策分型_省份清单.xlsx",
            "回弹缩放系数_敏感性分析数据.xlsx",
            "多目标优化_前沿对比数据.xlsx",
            "多目标优化_寻优边界单调性测试.xlsx",
            "稳健分布_检验报告.xlsx",
        }:
            continue
        if path.stat().st_mtime < latest_pipeline_time:
            stale_candidates.append(path.name)

    report["stale_files"] = stale_candidates
    if stale_candidates:
        add_issue(issues, f"发现 {len(stale_candidates)} 个较旧的历史数据文件：{stale_candidates}")


def check_workbook_loadability(report: dict[str, object], issues: list[str]) -> None:
    workbook_status: list[dict[str, object]] = []
    for base_dir in [ROOT, SIM_DIR]:
        for path in sorted(base_dir.glob("*.xlsx")):
            try:
                xls = pd.ExcelFile(path)
                workbook_status.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "sheet_count": len(xls.sheet_names),
                        "status": "ok",
                    },
                )
            except Exception as exc:
                workbook_status.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "sheet_count": None,
                        "status": f"error: {exc}",
                    },
                )
                add_issue(issues, f"工作簿无法打开: {path.name} -> {exc}")
    report["workbook_loadability"] = workbook_status


def main() -> None:
    issues: list[str] = []
    report: dict[str, object] = {
        "source_checks": {},
        "panel_merge": {},
        "derived_checks": {},
        "sim_checks": {},
        "stale_files": [],
    }

    check_sources(report, issues)
    check_panel_merge(report, issues)
    check_derived_outputs(report, issues)
    check_simulation_outputs(report, issues)
    check_stale_files(report, issues)
    check_workbook_loadability(report, issues)

    report["issues"] = issues
    report_path = ROOT / "data_integrity_report.json"
    report_path.write_text(json.dumps(to_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== SOURCE SUMMARY ===")
    for filename, info in report["source_checks"].items():
        print(filename, json.dumps(to_jsonable(info), ensure_ascii=False))

    print("\n=== PANEL MERGE ===")
    print(json.dumps(to_jsonable(report["panel_merge"]), ensure_ascii=False))

    print("\n=== DERIVED SNAPSHOT ===")
    derived_snapshot = {
        "ci_rows": report["derived_checks"].get("ci_rows", "待后续生成"),
        "weight_sum_by_index": report["derived_checks"].get("weight_sum_by_index", {}),
        "full_book_sheets": report["derived_checks"].get("full_book_sheets", []),
    }
    print(json.dumps(to_jsonable(derived_snapshot), ensure_ascii=False))

    print("\n=== SIM SNAPSHOT ===")
    print(json.dumps(to_jsonable(report["sim_checks"]), ensure_ascii=False))

    print("\n=== ISSUES ===")
    if issues:
        for issue in issues:
            print("-", issue)
    else:
        print("No blocking data integrity issues found.")

    print(f"\n完整质量审计报告已写入: {report_path}")


if __name__ == "__main__":
    main()
