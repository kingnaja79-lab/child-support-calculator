"""
Korea Child Support Calculator (2021 Seoul Family Court guideline table)

This module implements an automated calculator based on:
- "2021 양육비 산정기준표" (standard child support table)
- "2021년 양육비산정기준표 해설서" (commentary / methodology)

Core method (per guideline):
1) Determine standard child support (표준양육비) per child from the cross-table
   of (combined pre-tax monthly income) x (child age bracket).
2) Sum for multiple children.
3) Apply add/sub factors (가산·감산 요소) where appropriate.
4) Determine each parent's share by income proportion.
5) Compute the non-custodial parent's payment = total x non-custodial share.

Notes:
- The guideline explicitly lists add/sub factors but does not provide a single mandatory
  numeric multiplier for most factors (asset situation, residence region, high medical/
  education costs, personal rehabilitation). Therefore, this module exposes these as
  configurable adjustments.

Copyright:
- This code contains numeric values from an official public guideline table. Verify
  applicability in any case; courts may deviate based on circumstances.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple
import math
import argparse
import json

# -----------------------------------------------------------------------------
# Data (extracted from the 2021 guideline table)
# Income brackets are in 만원 (10,000 KRW) of combined pre-tax monthly income.
# Age brackets are in "만 나이" years.
# Each cell has avg/low/high in KRW per month (child 1-person average in a 2-child, 4-person household baseline).
# The last income bracket (>=1200만) has an open-ended high bound (None).
# -----------------------------------------------------------------------------

INCOME_BRACKETS_MW: List[Tuple[int, Optional[int]]] = [
    (0, 199),
    (200, 299),
    (300, 399),
    (400, 499),
    (500, 599),
    (600, 699),
    (700, 799),
    (800, 899),
    (900, 999),
    (1000, 1199),
    (1200, None),
]

AGE_BRACKETS: List[Tuple[int, int, str]] = [
    (0, 2, "0~2세"),
    (3, 5, "3~5세"),
    (6, 8, "6~8세"),
    (9, 11, "9~11세"),
    (12, 14, "12~14세"),
    (15, 18, "15~18세"),
]

# Indexed by age_label -> income_bracket_index
TABLE_2021: Dict[str, List[Dict[str, Optional[int]]]] = {
    "0~2세": [
        {"avg": 621000, "low": 264000, "high": 686000},
        {"avg": 752000, "low": 687000, "high": 848000},
        {"avg": 945000, "low": 849000, "high": 1021000},
        {"avg": 1098000, "low": 1022000, "high": 1171000},
        {"avg": 1245000, "low": 1172000, "high": 1323000},
        {"avg": 1401000, "low": 1324000, "high": 1491000},
        {"avg": 1582000, "low": 1492000, "high": 1685000},
        {"avg": 1789000, "low": 1686000, "high": 1893000},
        {"avg": 1997000, "low": 1894000, "high": 2046000},
        {"avg": 2095000, "low": 2047000, "high": 2151000},
        {"avg": 2207000, "low": 2152000, "high": None},
    ],
    "3~5세": [
        {"avg": 631000, "low": 268000, "high": 695000},
        {"avg": 759000, "low": 696000, "high": 854000},
        {"avg": 949000, "low": 855000, "high": 1031000},
        {"avg": 1113000, "low": 1032000, "high": 1189000},
        {"avg": 1266000, "low": 1190000, "high": 1344000},
        {"avg": 1422000, "low": 1345000, "high": 1510000},
        {"avg": 1598000, "low": 1511000, "high": 1702000},
        {"avg": 1807000, "low": 1703000, "high": 1912000},
        {"avg": 2017000, "low": 1913000, "high": 2066000},
        {"avg": 2116000, "low": 2067000, "high": 2180000},
        {"avg": 2245000, "low": 2181000, "high": None},
    ],
    "6~8세": [
        {"avg": 648000, "low": 272000, "high": 707000},
        {"avg": 767000, "low": 708000, "high": 863000},
        {"avg": 959000, "low": 864000, "high": 1049000},
        {"avg": 1140000, "low": 1050000, "high": 1216000},
        {"avg": 1292000, "low": 1217000, "high": 1385000},
        {"avg": 1479000, "low": 1386000, "high": 1546000},
        {"avg": 1614000, "low": 1547000, "high": 1732000},
        {"avg": 1850000, "low": 1733000, "high": 1957000},
        {"avg": 2065000, "low": 1958000, "high": 2101000},
        {"avg": 2137000, "low": 2102000, "high": 2224000},
        {"avg": 2312000, "low": 2225000, "high": None},
    ],
    "9~11세": [
        {"avg": 667000, "low": 281000, "high": 724000},
        {"avg": 782000, "low": 725000, "high": 885000},
        {"avg": 988000, "low": 886000, "high": 1075000},
        {"avg": 1163000, "low": 1076000, "high": 1240000},
        {"avg": 1318000, "low": 1241000, "high": 1406000},
        {"avg": 1494000, "low": 1407000, "high": 1562000},
        {"avg": 1630000, "low": 1563000, "high": 1758000},
        {"avg": 1887000, "low": 1759000, "high": 2012000},
        {"avg": 2137000, "low": 2013000, "high": 2158000},
        {"avg": 2180000, "low": 2159000, "high": 2292000},
        {"avg": 2405000, "low": 2293000, "high": None},
    ],
    "12~14세": [
        {"avg": 679000, "low": 295000, "high": 734000},
        {"avg": 790000, "low": 735000, "high": 894000},
        {"avg": 998000, "low": 895000, "high": 1139000},
        {"avg": 1280000, "low": 1140000, "high": 1351000},
        {"avg": 1423000, "low": 1352000, "high": 1510000},
        {"avg": 1598000, "low": 1511000, "high": 1654000},
        {"avg": 1711000, "low": 1655000, "high": 1847000},
        {"avg": 1984000, "low": 1848000, "high": 2071000},
        {"avg": 2159000, "low": 2072000, "high": 2191000},
        {"avg": 2223000, "low": 2192000, "high": 2349000},
        {"avg": 2476000, "low": 2350000, "high": None},
    ],
    "15~18세": [
        {"avg": 703000, "low": 319000, "high": 830000},
        {"avg": 957000, "low": 831000, "high": 1092000},
        {"avg": 1227000, "low": 1093000, "high": 1314000},
        {"avg": 1402000, "low": 1315000, "high": 1503000},
        {"avg": 1604000, "low": 1504000, "high": 1699000},
        {"avg": 1794000, "low": 1700000, "high": 1879000},
        {"avg": 1964000, "low": 1880000, "high": 2063000},
        {"avg": 2163000, "low": 2064000, "high": 2204000},
        {"avg": 2246000, "low": 2205000, "high": 2393000},
        {"avg": 2540000, "low": 2394000, "high": 2711000},
        {"avg": 2883000, "low": 2712000, "high": None},
    ],
}

# Child-count multiplier per guideline commentary:
# - baseline is 2 children (multiplier 1.0)
# - 1 child -> 1.065
# - 3+ children -> 0.783
CHILD_COUNT_MULTIPLIERS = {
    1: 1.065,
    2: 1.0,
    3: 0.783,  # for 3 or more
}

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Adjustment:
    """
    Generic adjustment applied to the total standard child support.
    type:
      - "multiplier": multiply total by (1 + value) if is_percent=True else by value
      - "add": add fixed KRW amount
      - "subtract": subtract fixed KRW amount
    """
    name: str
    type: str  # multiplier|add|subtract
    value: float
    is_percent: bool = False
    notes: str = ""

@dataclass(frozen=True)
class Child:
    age: int  # 만 나이

@dataclass(frozen=True)
class CalculationInputs:
    custodial_parent_income_krw: int  # pre-tax monthly
    non_custodial_parent_income_krw: int  # pre-tax monthly
    children: List[Child]
    # Optional: if a parent has 0 income but income should be imputed.
    custodial_imputed_income_krw: Optional[int] = None
    non_custodial_imputed_income_krw: Optional[int] = None
    # Optional adjustments (asset situation, region, high medical/education, rehab, etc.)
    adjustments: List[Adjustment] = None

@dataclass
class ChildCell:
    age_label: str
    income_bracket_mw: Tuple[int, Optional[int]]
    avg_krw: int
    low_krw: int
    high_krw: Optional[int]

@dataclass
class CalculationBreakdown:
    combined_income_krw: int
    combined_income_mw: int
    income_bracket_index: int
    standard_children_cells: List[ChildCell]
    standard_total_krw: int
    child_count_multiplier: float
    adjusted_total_krw: int
    non_custodial_share: float
    non_custodial_payment_krw: int
    applied_adjustments: List[Dict[str, Any]]

# -----------------------------------------------------------------------------
# Core functions
# -----------------------------------------------------------------------------

class Guideline2021:
    @staticmethod
    def age_label_for(age: int) -> str:
        for a_min, a_max, label in AGE_BRACKETS:
            if a_min <= age <= a_max:
                return label
        raise ValueError(f"Child age out of supported range (0~18): {age}")

    @staticmethod
    def income_bracket_index(combined_income_krw: int) -> int:
        mw = combined_income_krw // 10_000
        for idx, (lo, hi) in enumerate(INCOME_BRACKETS_MW):
            if hi is None:
                if mw >= lo:
                    return idx
            else:
                if lo <= mw <= hi:
                    return idx
        # Should be unreachable
        raise ValueError(f"Combined income not in any bracket: {combined_income_krw} KRW")

    @staticmethod
    def cell(age: int, combined_income_krw: int) -> ChildCell:
        label = Guideline2021.age_label_for(age)
        idx = Guideline2021.income_bracket_index(combined_income_krw)
        entry = TABLE_2021[label][idx]
        return ChildCell(
            age_label=label,
            income_bracket_mw=INCOME_BRACKETS_MW[idx],
            avg_krw=int(entry["avg"]),
            low_krw=int(entry["low"]),
            high_krw=None if entry["high"] is None else int(entry["high"]),
        )

    @staticmethod
    def minimum_support_half(age: int) -> int:
        """
        Suggest half of minimum support for situations where a parent has a justifiable
        reason for no current income (e.g., disability/serious illness etc.) but some
        contribution is still considered. The commentary suggests "최저 양육비(하한)의 1/2".
        """
        label = Guideline2021.age_label_for(age)
        low = int(TABLE_2021[label][0]["low"])  # lowest income bracket lower bound
        return low // 2

def _safe_int(x: float) -> int:
    return int(math.floor(x + 0.5))

def calculate_child_support(inputs: CalculationInputs) -> CalculationBreakdown:
    if not inputs.children:
        raise ValueError("At least one child is required.")

    adj = inputs.adjustments or []

    # Income imputation (optional)
    cust_income = inputs.custodial_parent_income_krw
    noncust_income = inputs.non_custodial_parent_income_krw
    if cust_income <= 0 and inputs.custodial_imputed_income_krw is not None:
        cust_income = inputs.custodial_imputed_income_krw
    if noncust_income <= 0 and inputs.non_custodial_imputed_income_krw is not None:
        noncust_income = inputs.non_custodial_imputed_income_krw

    if cust_income < 0 or noncust_income < 0:
        raise ValueError("Income cannot be negative.")

    combined = cust_income + noncust_income
    combined_mw = combined // 10_000
    bracket_idx = Guideline2021.income_bracket_index(combined)

    # Standard support: sum of per-child averages from the table
    cells: List[ChildCell] = []
    standard_total = 0
    for child in inputs.children:
        cell = Guideline2021.cell(child.age, combined)
        cells.append(cell)
        standard_total += cell.avg_krw

    # Child-count multiplier (baseline 2 children)
    n = len(inputs.children)
    if n == 1:
        m = CHILD_COUNT_MULTIPLIERS[1]
    elif n == 2:
        m = CHILD_COUNT_MULTIPLIERS[2]
    else:
        m = CHILD_COUNT_MULTIPLIERS[3]

    adjusted_total = standard_total * m

    # Apply user-provided adjustments
    applied: List[Dict[str, Any]] = []
    for a in adj:
        if a.type == "multiplier":
            if a.is_percent:
                adjusted_total *= (1.0 + a.value)
                applied.append({**asdict(a), "effective_multiplier": 1.0 + a.value})
            else:
                adjusted_total *= a.value
                applied.append({**asdict(a), "effective_multiplier": a.value})
        elif a.type == "add":
            adjusted_total += a.value
            applied.append({**asdict(a), "effective_add_krw": a.value})
        elif a.type == "subtract":
            adjusted_total -= a.value
            applied.append({**asdict(a), "effective_subtract_krw": a.value})
        else:
            raise ValueError(f"Unknown adjustment type: {a.type}")

    adjusted_total = max(0, adjusted_total)

    # Allocation by income proportion (non-custodial share)
    if combined == 0:
        # Degenerate case: both 0. In practice, courts may impute income.
        # Here we return 0 share and 0 payment.
        noncust_share = 0.0
    else:
        noncust_share = noncust_income / combined

    payment = _safe_int(adjusted_total * noncust_share)

    return CalculationBreakdown(
        combined_income_krw=int(combined),
        combined_income_mw=int(combined_mw),
        income_bracket_index=int(bracket_idx),
        standard_children_cells=cells,
        standard_total_krw=int(standard_total),
        child_count_multiplier=float(m),
        adjusted_total_krw=_safe_int(adjusted_total),
        non_custodial_share=float(noncust_share),
        non_custodial_payment_krw=int(payment),
        applied_adjustments=applied,
    )

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _parse_children_ages(s: str) -> List[Child]:
    ages = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        ages.append(Child(age=int(part)))
    if not ages:
        raise ValueError("children_ages must be like: 8 or 8,15")
    return ages

def main() -> None:
    p = argparse.ArgumentParser(description="Korean Child Support Calculator (2021 guideline)")
    p.add_argument("--cust-income", type=int, required=True, help="Custodial parent pre-tax monthly income (KRW)")
    p.add_argument("--noncust-income", type=int, required=True, help="Non-custodial parent pre-tax monthly income (KRW)")
    p.add_argument("--children-ages", type=str, required=True, help="Comma-separated child ages (만 나이), e.g. 8,15")
    p.add_argument("--adj-json", type=str, default=None,
                   help="Optional JSON list of adjustments, e.g. "
                        "'[{\"name\":\"urban\",\"type\":\"multiplier\",\"value\":0.05,\"is_percent\":true}]'")
    args = p.parse_args()

    adjustments = None
    if args.adj_json:
        raw = json.loads(args.adj_json)
        adjustments = [Adjustment(**item) for item in raw]

    inp = CalculationInputs(
        custodial_parent_income_krw=args.cust_income,
        non_custodial_parent_income_krw=args.noncust_income,
        children=_parse_children_ages(args.children_ages),
        adjustments=adjustments,
    )
    out = calculate_child_support(inp)
    print(json.dumps(asdict(out), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
