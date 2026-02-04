from __future__ import annotations

from typing import Any, Dict, Tuple, Optional

import pandas as pd

from app.schemas import AssessmentResult, BenchmarkMetric, Metric


def _safe_ratio(numerator: float | int, denominator: float | int) -> float | None:
    try:
        if denominator == 0:
            return None
        return float(numerator) / float(denominator)
    except Exception:
        return None


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _industry_benchmarks(industry: Optional[str]) -> Dict[str, Any]:
    """
    Simple, hard-coded benchmark table for a few common SME industries.
    Values are illustrative and can be refined later or moved to DB.
    """
    if not industry:
        return {}

    key = industry.strip().lower()

    table: Dict[str, Dict[str, Any]] = {
        "retail": {"gross_margin_pct": 30.0, "leverage_min": 0.5, "leverage_max": 1.5},
        "manufacturing": {"gross_margin_pct": 25.0, "leverage_min": 0.6, "leverage_max": 1.8},
        "services": {"gross_margin_pct": 40.0, "leverage_min": 0.2, "leverage_max": 1.0},
        "logistics": {"gross_margin_pct": 20.0, "leverage_min": 0.7, "leverage_max": 2.0},
        "agriculture": {"gross_margin_pct": 18.0, "leverage_min": 0.5, "leverage_max": 1.5},
        "e-commerce": {"gross_margin_pct": 35.0, "leverage_min": 0.4, "leverage_max": 1.6},
    }

    # Fallback: treat unknown industries as "general SME"
    default_row = {"gross_margin_pct": 30.0, "leverage_min": 0.4, "leverage_max": 1.6}

    for name, row in table.items():
        if name in key:
            return row
    return default_row


def analyze_financials(
    df: pd.DataFrame,
    industry: Optional[str] = None,
) -> Tuple[AssessmentResult, Dict[str, Any]]:
    """
    Core analytics engine.

    This function expects a tabular dataset with high-level financial columns.
    It is intentionally forgiving and will work with a subset of:

    - revenue / sales
    - cost_of_goods_sold / cogs
    - operating_expenses / opex / expenses
    - current_assets, current_liabilities
    - inventory
    - accounts_receivable
    - total_debt / loans
    """
    df = _normalize_column_names(df)

    stats: Dict[str, Any] = {}

    revenue_cols = [c for c in df.columns if c in {"revenue", "sales", "turnover"}]
    expense_cols = [c for c in df.columns if c in {"expenses", "operating_expenses", "opex"}]

    revenue = float(df[revenue_cols].sum().sum()) if revenue_cols else 0.0
    expenses = float(df[expense_cols].sum().sum()) if expense_cols else 0.0
    profit = revenue - expenses

    stats["revenue_total"] = revenue
    stats["expenses_total"] = expenses
    stats["profit_total"] = profit

    current_assets = df.get("current_assets", pd.Series(dtype=float)).sum()
    current_liabilities = df.get("current_liabilities", pd.Series(dtype=float)).sum()
    inventory = df.get("inventory", pd.Series(dtype=float)).sum()
    total_debt = df.get("total_debt", pd.Series(dtype=float)).sum()

    stats["current_assets"] = float(current_assets)
    stats["current_liabilities"] = float(current_liabilities)
    stats["inventory"] = float(inventory)
    stats["total_debt"] = float(total_debt)

    gross_margin = _safe_ratio(profit, revenue) if revenue else None
    current_ratio = _safe_ratio(current_assets, current_liabilities) if current_liabilities else None
    inventory_turnover = _safe_ratio(expenses, inventory) if inventory else None
    leverage_ratio = _safe_ratio(total_debt, current_assets + inventory) if (current_assets + inventory) else None

    metrics: list[Metric] = [
        Metric(
            key="gross_margin",
            label="Gross Margin",
            value=gross_margin * 100 if gross_margin is not None else None,
            unit="%",
            interpretation="Higher is better; aim for > 30% in many SMEs.",
        ),
        Metric(
            key="current_ratio",
            label="Current Ratio",
            value=current_ratio,
            interpretation="Liquidity; values between 1.2 and 2.0 are often considered healthy.",
        ),
        Metric(
            key="inventory_turnover",
            label="Inventory Turnover",
            value=inventory_turnover,
            interpretation="How many times inventory is sold/used; higher suggests efficient stock management.",
        ),
        Metric(
            key="leverage_ratio",
            label="Leverage Ratio (Debt / Assets+Inventory)",
            value=leverage_ratio,
            interpretation="Debt burden relative to assets; lower values generally indicate lower financial risk.",
        ),
    ]

    score_components = []

    if gross_margin is not None:
        score_components.append(min(max((gross_margin * 100) / 40 * 25, 0), 25))
    if current_ratio is not None:
        if current_ratio < 0.8:
            cr_score = 5
        elif current_ratio < 1.0:
            cr_score = 10
        elif current_ratio < 1.5:
            cr_score = 18
        elif current_ratio < 2.5:
            cr_score = 22
        else:
            cr_score = 20
        score_components.append(cr_score)
    if inventory_turnover is not None:
        score_components.append(min(inventory_turnover * 2, 15))
    if leverage_ratio is not None:
        if leverage_ratio > 2:
            lr_score = 5
        elif leverage_ratio > 1:
            lr_score = 10
        elif leverage_ratio > 0.5:
            lr_score = 15
        else:
            lr_score = 20
        score_components.append(lr_score)

    overall_score = sum(score_components) / len(score_components) if score_components else 50.0

    if overall_score >= 75:
        risk_level = "Low"
    elif overall_score >= 50:
        risk_level = "Medium"
    else:
        risk_level = "High"

    narrative_parts = [
        f"The overall financial health score for this business is {overall_score:.1f}/100, indicating {risk_level.lower()} risk.",
    ]
    if gross_margin is not None:
        narrative_parts.append(
            f"Gross margin is approximately {gross_margin * 100:.1f}%, "
            "which reflects how much profit is retained after direct costs."
        )
    if current_ratio is not None:
        narrative_parts.append(
            f"The current ratio is about {current_ratio:.2f}, representing short-term liquidity."
        )
    if leverage_ratio is not None:
        narrative_parts.append(
            f"Leverage (debt to assets + inventory) stands near {leverage_ratio:.2f}, capturing debt burden."
        )

    narrative = " ".join(narrative_parts)

    benchmarks: list[BenchmarkMetric] = []
    bench_cfg = _industry_benchmarks(industry)

    if bench_cfg:
        # Margin vs industry
        industry_margin = bench_cfg.get("gross_margin_pct")
        bm_status = "ok"
        note = "In line with similar businesses."
        if gross_margin is not None and industry_margin is not None:
            margin_pct = gross_margin * 100
            if margin_pct >= industry_margin + 5:
                bm_status = "good"
                note = "Stronger margin than typical peers."
            elif margin_pct <= industry_margin - 5:
                bm_status = "risk"
                note = "Margin is below typical peers; watch pricing and costs."
        benchmarks.append(
            BenchmarkMetric(
                key="margin_vs_industry",
                label="Your margin vs industry average",
                business_value=gross_margin * 100 if gross_margin is not None else None,
                benchmark_value=industry_margin,
                status=bm_status,
                note=note,
            )
        )

        # Debt level vs typical range
        lev_min = bench_cfg.get("leverage_min")
        lev_max = bench_cfg.get("leverage_max")
        lev_status = "ok"
        lev_note = "Debt level is in a typical range for this industry."
        if leverage_ratio is not None and lev_min is not None and lev_max is not None:
            if leverage_ratio < lev_min:
                lev_status = "good"
                lev_note = "Debt is lower than usual, giving more flexibility."
            elif leverage_ratio > lev_max:
                lev_status = "risk"
                lev_note = "Debt is higher than usual; monitor repayments closely."
        benchmarks.append(
            BenchmarkMetric(
                key="debt_vs_range",
                label="Your debt level vs typical range",
                business_value=leverage_ratio,
                benchmark_value=None,  # range is described in note
                status=lev_status,
                note=lev_note,
            )
        )

    result = AssessmentResult(
        overall_score=overall_score,
        risk_level=risk_level,
        metrics=metrics,
        narrative=narrative,
        raw_stats=stats,
        benchmarks=benchmarks,
    )

    return result, stats

