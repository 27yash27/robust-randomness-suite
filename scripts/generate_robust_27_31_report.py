#!/usr/bin/env python3

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


def _find_anchor(start: Path, anchor: str) -> Path:
    """Walk up from `start` looking for a directory containing a sibling named
    `anchor`. Returns the path to the anchor itself."""
    for parent in [start.resolve(), *start.resolve().parents]:
        candidate = parent / anchor
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not locate '{anchor}' walking up from {start}"
    )


# `updated-rtest-main` is a sibling of this project under "0-Shen Research/".
# Walk up until we find it instead of hardcoding a username/path.
MAIN_FOLDER = _find_anchor(Path(__file__).parent, "updated-rtest-main")
CAMPAIGNS = MAIN_FOLDER / "My-robust-Test-Results" / "campaigns"
REPORTS = MAIN_FOLDER / "My-robust-Test-Results" / "reports"

BASELINE_100 = CAMPAIGNS / "nist_100mb_27_31_20260412"
EXTENDED_1G = CAMPAIGNS / "nist_1gb_extended_27_31_20260412"

TEST_ORDER = ["27", "28", "29", "30", "31"]
TEST_TITLES = {
    "27": "OPERM5",
    "28": "Craps",
    "29": "DAB DCT",
    "30": "DAB Filtering",
    "31": "Linear Complexity",
}
TEST_SWEEP_100 = {
    "27": "5, 10, 15, 20, 24",
    "28": "5, 10, 15",
    "29": "5, 10, 20, 30, 40, 50",
    "30": "5, 10, 20, 30, 40, 50",
    "31": "5, 10, 20, 30, 40, 50",
}
TEST_SWEEP_1G = {
    "27": "5, 10, 15, 20, 24, 30, 40, 50, 75, 100, 150, 200",
    "28": "5, 10, 15, 20, 30, 40, 50, 75, 100",
    "29": "5, 10, 20, 30, 40, 50, 75, 100, 150, 200",
    "30": "5, 10, 20, 30, 40, 50, 75, 100, 150, 200",
    "31": "5, 10, 20, 30, 40, 50, 75, 100, 150, 200",
}
GENERATOR_ORDER = [
    ("linear_congruential", "[1] Linear Congruential"),
    ("quadratic_congruential_i", "[2] Quadratic Congruential I"),
    ("quadratic_congruential_ii", "[3] Quadratic Congruential II"),
    ("cubic_congruential", "[4] Cubic Congruential"),
    ("xor", "[5] XOR"),
    ("modular_exponentiation", "[6] Modular Exponentiation"),
    ("blum_blum_shub", "[7] Blum-Blum-Shub"),
    ("micali_schnorr", "[8] Micali-Schnorr"),
    ("g_using_sha", "[9] G Using SHA-1"),
]
GENERATOR_RANK = {key: idx for idx, (key, _) in enumerate(GENERATOR_ORDER)}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="ascii") as f:
        return list(csv.DictReader(f))


def fmt_obj(value: str | float) -> str:
    x = float(value)
    if abs(x) < 5e-16:
        x = 0.0
    return f"{x:.6g}"


def generator_family_key(filename: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", filename.lower())
    for key, _label in sorted(GENERATOR_ORDER, key=lambda item: len(item[0]), reverse=True):
        if key in name:
            return key
    raise ValueError(f"unknown generator family for {filename}")


def generator_label(filename: str) -> str:
    family = generator_family_key(filename)
    for key, label in GENERATOR_ORDER:
        if key == family:
            return label
    raise ValueError(f"missing label for {filename}")


def summarize_hits(rows: list[dict[str, str]]) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for test_num in TEST_ORDER:
        sub = [row for row in rows if row["test_num"] == test_num]
        out[test_num] = (
            sum(float(row["objective"]) < 0.05 for row in sub),
            sum(float(row["objective"]) < 0.01 for row in sub),
        )
    return out


def load_extended_rows() -> list[dict[str, str]]:
    return read_csv(EXTENDED_1G / "optimal_p_merged.csv")


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return (row["generator_file"], row["test_num"])


def build_extended_summary_map(rows: list[dict[str, str]]) -> dict[tuple[str, str], Path]:
    out: dict[tuple[str, str], Path] = {}
    for row in rows:
        rel = Path(row["summary_csv"])
        if rel.parts and rel.parts[0] == "sweeps":
            out[row_key(row)] = EXTENDED_1G / rel
        else:
            out[row_key(row)] = CAMPAIGNS / rel
    return out


def build_baseline_summary_map(rows: list[dict[str, str]]) -> dict[tuple[str, str], Path]:
    return {row_key(row): BASELINE_100 / row["summary_csv"] for row in rows}


def neighbor_ps_from_summary(summary_csv: Path, best_p: str) -> list[str]:
    rows = read_csv(summary_csv)
    p_values = [row["p"] for row in rows if row["status"] == "ok"]
    idx = p_values.index(best_p)
    out = [best_p]
    if idx > 0:
        out.insert(0, p_values[idx - 1])
    if idx + 1 < len(p_values):
        out.append(p_values[idx + 1])
    return out


def chart_links_for_row(
    row: dict[str, str],
    summary_map: dict[tuple[str, str], Path],
    campaign_root: Path | None = None,
) -> list[Path]:
    key = row_key(row)
    summary_csv = summary_map[key]
    best_p = row["best_p"]
    chart_ps = neighbor_ps_from_summary(summary_csv, best_p)

    if campaign_root is None:
        rel = summary_csv.relative_to(CAMPAIGNS)
        campaign_root = CAMPAIGNS / rel.parts[0]
        summary_rel = Path(*rel.parts[1:])
    else:
        summary_rel = summary_csv.relative_to(campaign_root)

    test_dir = summary_rel.parent
    if test_dir.parts and test_dir.parts[0] == "sweeps":
        chart_rel = Path(*test_dir.parts[1:])
    else:
        chart_rel = test_dir.relative_to("sweeps")
    chart_dir = campaign_root / "charts" / chart_rel
    links: list[Path] = []
    for p in chart_ps:
        for svg in sorted(chart_dir.glob(f"p{int(p):03d}_c*.svg")):
            links.append(svg)
    return links


def make_test_table(rows: list[dict[str, str]], test_num: str) -> str:
    sub = sorted(
        (row for row in rows if row["test_num"] == test_num),
        key=lambda row: GENERATOR_RANK[generator_family_key(row["generator_file"])],
    )
    lines = [
        "| Generator | Best p=q | Best KS p-value |",
        "|---|---:|---:|",
    ]
    for row in sub:
        lines.append(
            f"| {generator_label(row['generator_file'])} | {row['best_p']} | {fmt_obj(row['objective'])} |"
        )
    return "\n".join(lines)


def make_paired_parameter_tables(
    baseline_rows: list[dict[str, str]],
    extended_rows: list[dict[str, str]],
) -> str:
    baseline_by = {
        (generator_family_key(row["generator_file"]), row["test_num"]): row for row in baseline_rows
    }
    extended_by = {
        (generator_family_key(row["generator_file"]), row["test_num"]): row for row in extended_rows
    }

    lines: list[str] = []
    for test_num in TEST_ORDER:
        lines.append(f"### Test {test_num}: {TEST_TITLES[test_num]}")
        lines.append("")
        lines.append("| Generator | 100MB Best p=q | 100MB Best KS p-value | 1GB Best p=q | 1GB Best KS p-value |")
        lines.append("|---|---:|---:|---:|---:|")
        for family, label in GENERATOR_ORDER:
            brow = baseline_by[(family, test_num)]
            erow = extended_by[(family, test_num)]
            lines.append(
                f"| {label} | {brow['best_p']} | {fmt_obj(brow['objective'])} | {erow['best_p']} | {fmt_obj(erow['objective'])} |"
            )
        lines.append("")
    return "\n".join(lines)


def strongest_rows(rows: list[dict[str, str]], test_num: str, n: int = 3) -> list[dict[str, str]]:
    sub = [row for row in rows if row["test_num"] == test_num]
    return sorted(sub, key=lambda row: float(row["objective"]))[:n]


def best_coord_for_row(
    row: dict[str, str],
    summary_map: dict[tuple[str, str], Path],
    ) -> int:
    summary_csv = summary_map[row_key(row)]
    best_p = row["best_p"]
    rows = read_csv(summary_csv)
    match = None
    for item in rows:
        if item["status"] == "ok" and item["p"] == best_p:
            match = item
            break
    if match is None:
        return 0
    values = [float(v) for v in match["values"].split()] if match["values"].strip() else []
    if not values:
        return 0
    best_idx = min(range(len(values)), key=lambda idx: values[idx])
    return best_idx


def chart_path_for_best_row(
    row: dict[str, str],
    summary_map: dict[tuple[str, str], Path],
) -> Path:
    summary_csv = summary_map[row_key(row)]
    rel = summary_csv.relative_to(CAMPAIGNS)
    campaign_root = CAMPAIGNS / rel.parts[0]
    summary_rel = Path(*rel.parts[1:])
    test_dir = summary_rel.parent
    chart_rel = Path(*test_dir.parts[1:]) if test_dir.parts[0] == "sweeps" else test_dir.relative_to("sweeps")
    chart_dir = campaign_root / "charts" / chart_rel
    coord = best_coord_for_row(row, summary_map)
    return chart_dir / f"p{int(row['best_p']):03d}_c{coord:04d}.svg"


def make_paired_chart_section(
    baseline_rows: list[dict[str, str]],
    extended_rows: list[dict[str, str]],
    baseline_summary_map: dict[tuple[str, str], Path],
    extended_summary_map: dict[tuple[str, str], Path],
) -> str:
    baseline_by = {
        (generator_family_key(row["generator_file"]), row["test_num"]): row for row in baseline_rows
    }
    extended_by = {
        (generator_family_key(row["generator_file"]), row["test_num"]): row for row in extended_rows
    }

    lines = ["## Charts", ""]
    lines.append(
        "The figures below retain only the settled best chart for each generator/test pair. "
        "Each row compares the 100MB baseline result against the 1GB extended result at the final settled `p=q` values."
    )
    lines.append("")
    lines.append(
        "For multi-coordinate tests such as Craps, the displayed chart is the coordinate that produced the lowest KS p-value at the settled `p=q`."
    )
    lines.append("")

    for family, label in GENERATOR_ORDER:
        lines.append(f"### {label}")
        lines.append("")
        lines.append("| Test | 100MB Baseline | 1GB Extended |")
        lines.append("|---|---|---|")
        for test_num in TEST_ORDER:
            brow = baseline_by[(family, test_num)]
            erow = extended_by[(family, test_num)]
            bchart = chart_path_for_best_row(brow, baseline_summary_map)
            echart = chart_path_for_best_row(erow, extended_summary_map)
            bcell = (
                f"`p=q={brow['best_p']}`, KS `{fmt_obj(brow['objective'])}`<br>"
                f"![](<{bchart.as_posix()}>)"
            )
            ecell = (
                f"`p=q={erow['best_p']}`, KS `{fmt_obj(erow['objective'])}`<br>"
                f"![](<{echart.as_posix()}>)"
            )
            lines.append(f"| t{test_num} {TEST_TITLES[test_num]} | {bcell} | {ecell} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)

    baseline_rows = read_csv(BASELINE_100 / "optimal_p.csv")
    extended_rows = load_extended_rows()
    comparison_rows = read_csv(EXTENDED_1G / "comparison_vs_baseline.csv")

    baseline_summary_map = build_baseline_summary_map(baseline_rows)
    extended_summary_map = build_extended_summary_map(extended_rows)

    baseline_hits = summarize_hits(baseline_rows)
    extended_hits = summarize_hits(extended_rows)

    changed_counts: dict[str, int] = defaultdict(int)
    for row in comparison_rows:
        if row["changed"] == "1":
            changed_counts[row["test_num"]] += 1

    lines: list[str] = []
    lines.append("# Robust Tests 27-31 on NIST Bad Generators")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(f"Main folder: `{MAIN_FOLDER}`")
    lines.append("")
    lines.append("This report summarizes the robust-test campaigns for tests 27-31 against the NIST bad-generator binaries in two regimes:")
    lines.append("- 100MB baseline sweep")
    lines.append("- 1GB extended sweep with larger `p=q` ranges")
    lines.append("")
    lines.append("The goal was to identify the most effective operating region for each test, compare 100MB and 1GB behavior, and retain the chart set needed for paper figures.")
    lines.append("")
    lines.append("Lower KS p-values indicate stronger separation in the 2-sample KS framework.")
    lines.append("")
    lines.append("## Tests")
    lines.append("")
    lines.append("- `t27 OPERM5`: overlapping 5-permutations")
    lines.append("- `t28 Craps`: simulated craps outcomes and game-length statistics")
    lines.append("- `t29 DAB DCT`: low-frequency DCT-energy statistic")
    lines.append("- `t30 DAB Filtering`: filtered block-energy statistic")
    lines.append("- `t31 Linear Complexity`: Berlekamp-Massey block complexity statistic")
    lines.append("")
    lines.append("## Sweep Design")
    lines.append("")
    lines.append("The numbers listed after each test name are the `p=q` sweep values used in the robust 2-sample KS framework. For example, `t27 OPERM5: 5, 10, 15, 20, 24` means the test was run at `-p 5 -q 5`, then `-p 10 -q 10`, and so on. Here, `p` is the number of tested-sample statistics and `q` is the number of etalon-sample statistics compared by the KS test. In this study we kept `p` and `q` equal, so these lists define the sample-count grid explored for each test.")
    lines.append("")
    lines.append("### 100MB Baseline")
    lines.append("")
    for test_num in TEST_ORDER:
        lines.append(f"- `t{test_num} {TEST_TITLES[test_num]}`: `{TEST_SWEEP_100[test_num]}`")
    lines.append("")
    lines.append("### 1GB Extended")
    lines.append("")
    for test_num in TEST_ORDER:
        lines.append(f"- `t{test_num} {TEST_TITLES[test_num]}`: `{TEST_SWEEP_1G[test_num]}`")
    lines.append("")
    lines.append("## High-Level Findings")
    lines.append("")
    lines.append("Definitions used in the summary table:")
    lines.append("- `100MB hits < 0.05`")
    lines.append("  How many of the 9 generators gave a best KS p-value below `0.05` in the 100MB campaign. Example: `3/9` means that test showed a reasonably strong signal on 3 of the 9 generators.")
    lines.append("- `1GB extended hits < 0.05`")
    lines.append("  The same count, but using the larger 1GB sweep with the expanded `p=q` range.")
    lines.append("- `Changed best point in 1GB extension`")
    lines.append("  How often the best settled `p=q` moved when we allowed the larger 1GB sweep. Example: `7/9` means that for 7 of the 9 generators, the best-performing `p=q` in the 1GB extended run was different from the one chosen in the original smaller sweep.")
    lines.append("")
    lines.append("| Test | 100MB hits < 0.05 | 1GB extended hits < 0.05 | Changed best point in 1GB extension |")
    lines.append("|---|---:|---:|---:|")
    for test_num in TEST_ORDER:
        lines.append(
            f"| t{test_num} {TEST_TITLES[test_num]} | {baseline_hits[test_num][0]}/9 | {extended_hits[test_num][0]}/9 | {changed_counts[test_num]}/9 |"
        )
    lines.append("")
    lines.append("Key conclusions from the sweep comparison:")
    lines.append("- `t29 DAB DCT` remained the strongest overall test and improved from 4/9 to 5/9 generators below 0.05 under the extended 1GB sweep.")
    lines.append("- `t28 Craps` benefited the most from larger 1GB sweep ranges: the best `p=q` changed for all 9 generators, and its hit count improved from 2/9 to 3/9.")
    lines.append("- `t27 OPERM5` also benefited materially from the larger sweep, with best `p=q` changing for 7/9 generators.")
    lines.append("- `t30 DAB Filtering` and `t31 Linear Complexity` were comparatively stable and remained weaker on this generator set.")
    lines.append("")
    lines.append("### Test Best Performance")
    lines.append("")
    lines.append("For each test, the entries below list the top few generator/test combinations with:")
    lines.append("- the generator name")
    lines.append("- the settled best `p=q`")
    lines.append("- the lowest best KS p-value achieved")
    lines.append("")
    for test_num in TEST_ORDER:
        lines.append(f"- `t{test_num} {TEST_TITLES[test_num]}`:")
        for row in strongest_rows(extended_rows, test_num):
            lines.append(
                f"  {generator_label(row['generator_file'])} at `p=q={row['best_p']}` with best KS p-value `{fmt_obj(row['objective'])}`"
            )
    lines.append("")
    lines.append("## Final Settled Parameters")
    lines.append("")
    lines.append("In the tables below, `Best KS p-value` is the final KS value used to judge the strength of separation at the settled `p=q` setting. Lower values indicate stronger evidence that the tested generator differs from the etalon distribution. For multi-coordinate tests such as Craps, the reported value is the smallest KS p-value among the reported coordinates, since that is the value used to select the settled sweep point.")
    lines.append("")
    lines.append(make_paired_parameter_tables(baseline_rows, extended_rows))
    lines.append("")
    lines.append(make_paired_chart_section(baseline_rows, extended_rows, baseline_summary_map, extended_summary_map))
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append("Across tests 27-31, the clearest overall performer was `t29 DAB DCT`, which delivered the strongest and broadest discrimination on the NIST bad-generator set. `t27 OPERM5` became more useful once the 1GB files allowed higher `p=q` values, and `t28 Craps` showed the most obvious dependence on broader sweep ranges. In contrast, `t30 DAB Filtering` and `t31 Linear Complexity` were comparatively specialized, with their strongest response concentrated mainly on the XOR family.")
    lines.append("")
    lines.append("For paper presentation, the most defensible emphasis is:")
    lines.append("- `t29 DAB DCT` as the primary new test among 27-31")
    lines.append("- `t27 OPERM5` as a secondary test whose performance improves when larger files permit broader `p=q` exploration")
    lines.append("- `t28 Craps` as a useful complementary test, especially once the sweep range is extended")
    lines.append("")
    lines.append("The final settled parameter set should therefore be taken from the 100MB baseline tables for the 100MB data regime, and from the 1GB extended tables for the 1GB regime.")
    lines.append("")

    report_path = REPORTS / "robust_27_31_nist_summary_report_20260412.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
