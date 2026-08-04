#!/usr/bin/env python3

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


TEST_CONFIGS = {
    22: {
        "script": "run_rtest_t22_sweep.py",
        "p_values": [3, 4, 5],
        "dir_template": "t22_p{p:03d}",
        "chart_coords": [0, 30],
        "summary_kind": "triple",
        "title": "Test 22: DNA",
        "note": "",
    },
    23: {
        "script": "run_rtest_t23_sweep.py",
        "p_values": [100, 150, 200, 250, 300],
        "dir_template": "t23_p{p:04d}",
        "chart_coords": [0],
        "chart_only": [100, 150],
        "summary_kind": "single",
        "title": "Test 23: Count the 1s in a Stream of Bytes",
        "note": "The zeros at p=q=200, 250, and 300 are EOF artifacts, not valid p-values.",
    },
    24: {
        "script": "run_rtest_t24_sweep.py",
        "p_values": [10, 20, 30, 40, 50],
        "dir_template": "t24_p{p:03d}",
        "chart_coords": [0, 3],
        "chart_only": [10, 20, 30, 40],
        "summary_kind": "triple",
        "title": "Test 24: Count the 1s for Specific Bytes",
        "note": "",
    },
    25: {
        "script": "run_rtest_t25_sweep.py",
        "p_values": [10, 20, 30, 40, 50],
        "dir_template": "t25_p{p:03d}",
        "chart_coords": [0],
        "summary_kind": "single",
        "title": "Test 25: Parking",
        "note": "",
    },
    26: {
        "script": "run_rtest_t26_sweep.py",
        "p_values": [2, 3, 4, 5, 6],
        "dir_template": "t26_p{p:03d}",
        "chart_coords": [0],
        "summary_kind": "single",
        "title": "Test 26: Squeeze",
        "note": "",
    },
}


HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    @page {{
      size: portrait;
      margin: 0.6in 0.8in;
    }}

    :root {{
      --ink: #111111;
      --muted: #4a4a4a;
      --line: #cfcfcf;
      --soft: #f4f4f4;
    }}

    * {{
      box-sizing: border-box;
    }}

    html, body {{
      margin: 0;
      padding: 0;
      color: var(--ink);
      background: #ffffff;
      font-family: Georgia, "Times New Roman", serif;
    }}

    body {{
      font-size: 12.5pt;
      line-height: 1.4;
    }}

    h1, h2, h3, p {{
      margin: 0;
    }}

    .page {{
      min-height: calc(100vh - 1.2in);
      display: flex;
      flex-direction: column;
      page-break-after: always;
      break-after: page;
      padding: 0.05in 0.08in;
    }}

    .page:last-child {{
      page-break-after: auto;
      break-after: auto;
    }}

    .title-page {{
      justify-content: center;
      gap: 0.2in;
    }}

    .title-page h1 {{
      font-size: 24pt;
      line-height: 1.1;
    }}

    .subtitle {{
      color: var(--muted);
      max-width: 6.5in;
      font-size: 13pt;
    }}

    .chip {{
      display: inline-block;
      margin-top: 0.1in;
      padding: 0.08in 0.14in;
      border: 1px solid var(--line);
      background: var(--soft);
      font-size: 10.5pt;
    }}

    .section-head {{
      margin-bottom: 0.18in;
      padding-bottom: 0.08in;
      border-bottom: 1px solid var(--line);
    }}

    .section-head h2 {{
      font-size: 19pt;
      margin-bottom: 0.05in;
    }}

    .section-head p {{
      color: var(--muted);
      font-size: 11.5pt;
    }}

    .panel {{
      border: 1px solid var(--line);
      padding: 0.14in;
      background: #fff;
      margin-bottom: 0.18in;
    }}

    .panel h3 {{
      font-size: 13.5pt;
      margin-bottom: 0.08in;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 0.12in;
      font-size: 11pt;
    }}

    th, td {{
      border: 1px solid var(--line);
      padding: 0.085in 0.11in;
      text-align: left;
      vertical-align: top;
    }}

    th {{
      background: var(--soft);
      font-weight: 700;
    }}

    .small {{
      font-size: 10.5pt;
      color: var(--muted);
    }}

    .chart-page {{
      gap: 0.14in;
    }}

    .chart-meta {{
      display: flex;
      justify-content: space-between;
      gap: 0.2in;
      align-items: baseline;
      border-bottom: 1px solid var(--line);
      padding-bottom: 0.08in;
    }}

    .chart-meta h2 {{
      font-size: 17pt;
    }}

    .chart-meta .small {{
      text-align: right;
      max-width: 2.8in;
    }}

    .chart-frame {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      padding: 0.08in;
      overflow: hidden;
    }}

    .chart-frame object {{
      width: 100%;
      height: calc(100vh - 2.8in);
    }}

    code {{
      font-family: "Courier New", Courier, monospace;
      font-size: 0.95em;
    }}
  </style>
</head>
<body>
"""


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent.parent
    default_results_root = repo_root / "My-robust-Test-Results"
    parser = argparse.ArgumentParser(
        description="Run tests 22-26 on one or more NIST bad generators and build print HTML reports."
    )
    parser.add_argument(
        "--tested",
        nargs="+",
        type=Path,
        required=True,
        help="One or more tested .bin files",
    )
    parser.add_argument(
        "--etalon",
        default=Path.home() / "Downloads" / "etal.bin",
        type=Path,
        help="Path to etalon file",
    )
    parser.add_argument(
        "--repo-root",
        default=repo_root,
        type=Path,
        help="Repository root",
    )
    parser.add_argument(
        "--prefix-tag",
        default="",
        help="Optional short tag appended to output prefixes, e.g. v2",
    )
    return parser.parse_args()


def run_command(cmd: list[str], workdir: Path) -> None:
    result = subprocess.run(cmd, cwd=workdir, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")


def read_summary(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="ascii", newline="") as f:
        return list(csv.DictReader(f))


def render_summary_table(test_num: int, rows: list[dict[str, str]]) -> str:
    cfg = TEST_CONFIGS[test_num]
    if cfg["summary_kind"] == "triple":
        body_rows = []
        for row in rows:
            body_rows.append(
                f"<tr><td>{row['p']}</td><td>{row['returncode']}</td><td>{row['min']}</td><td>{row['median']}</td><td>{row['max']}</td></tr>"
            )
        note_html = ""
        if cfg.get("note"):
            note_html = f'<p class="small" style="margin-top:0.12in;">{cfg["note"]}</p>'
        return f"""
    <div class="panel">
      <h3>{cfg['title']}</h3>
      <table>
        <thead>
          <tr><th>p=q</th><th>Return</th><th>Min</th><th>Median</th><th>Max</th></tr>
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
      {note_html}
    </div>
"""
    body_rows = []
    for row in rows:
        pvalue = row.get("pvalue", "")
        extra = ""
        if row["returncode"] != "0":
            extra = "EOF / parse failure"
            pvalue = ""
        body_rows.append(
            f"<tr><td>{row['p']}</td><td>{row['returncode']}</td><td>{pvalue or extra}</td><td>{pvalue or ''}</td><td>{pvalue or ''}</td></tr>"
        )
    note_html = ""
    if cfg.get("note"):
        note_html = f'<p class="small" style="margin-top:0.12in;">{cfg["note"]}</p>'
    return f"""
    <div class="panel">
      <h3>{cfg['title']}</h3>
      <table>
        <thead>
          <tr><th>p=q</th><th>Return</th><th>Min</th><th>Median</th><th>Max</th></tr>
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
      {note_html}
    </div>
"""


def render_chart_pages(prefixes: dict[int, str], output_name: str) -> str:
    pages: list[str] = []
    for test_num, cfg in TEST_CONFIGS.items():
        p_values = cfg.get("chart_only", cfg["p_values"])
        for p in p_values:
            run_dir = prefixes[test_num] / cfg["dir_template"].format(p=p)
            for coord in cfg["chart_coords"]:
                svg_name = f"coord{coord:04d}.svg"
                svg_path = run_dir / svg_name
                if not svg_path.is_file():
                    continue
                label = (
                    f"Test {test_num}, p=q={p}"
                    if len(cfg["chart_coords"]) == 1
                    else f"Test {test_num}, p=q={p}, Coordinate {coord}"
                )
                rel_path = f"{prefixes[test_num].name}/{run_dir.name}/{svg_name}"
                pages.append(
                    f'<section class="page chart-page"><div class="chart-meta"><h2>{label}</h2>'
                    f'<p class="small">{output_name} chart page.</p></div>'
                    f'<div class="chart-frame"><object data="{rel_path}" type="image/svg+xml"></object></div></section>'
                )
    return "\n".join(pages)


def sanitize_report_name(stem: str) -> str:
    stem = re.sub(r"^\d+\.", "", stem)
    stem = stem.replace("_100MB", "")
    stem = stem.replace("bad_", "")
    stem = stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return stem


def short_prefix(bin_path: Path, tag: str) -> str:
    match = re.match(r"(\d+)\.", bin_path.name)
    if not match:
        raise ValueError(f"Could not extract numeric prefix from {bin_path.name}")
    prefix = f"n{match.group(1)}"
    if tag:
        prefix += tag
    return prefix


def build_report(repo_root: Path, tested: Path, prefixes: dict[int, Path]) -> Path:
    results_root = repo_root / "My-robust-Test-Results" / "legacy" / "suite_runs"
    report_slug = sanitize_report_name(tested.stem)
    report_path = results_root / f"{report_slug}_tests_22_26_print.html"
    title = f"{tested.name}: Tests 22 to 26"
    summary_sections = []
    for test_num in sorted(TEST_CONFIGS):
        summary_sections.append(render_summary_table(test_num, read_summary(prefixes[test_num] / "summary.csv")))
    folder_list = ", ".join(f"<code>My-robust-Test-Results/{prefix.name}</code>" for prefix in prefixes.values())
    html = (
        HTML_HEAD.format(title=title)
        + f"""
  <section class="page title-page">
    <h1>{tested.name}: Tests 22 to 26</h1>
    <p class="subtitle">
      Print-optimized report for <code>{tested}</code> against
      <code>~/Downloads/etal.bin</code> in XOR mode. This report covers tests 22, 23, 24, 25, and 26.
    </p>
    <div class="chip">
      Sweep folders: {folder_list}
    </div>
  </section>

  <section class="page">
    <div class="section-head">
      <h2>Summary</h2>
      <p>Compact sweep tables for this generator before the chart pages.</p>
    </div>
    {''.join(summary_sections)}
  </section>
"""
        + render_chart_pages(prefixes, tested.name)
        + "\n</body>\n</html>\n"
    )
    report_path.write_text(html, encoding="ascii")
    return report_path


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    results_root = repo_root / "My-robust-Test-Results"
    etalon = args.etalon.expanduser().resolve()
    my_tests_dir = repo_root / "My-RNGs-Testers" / "scripts"
    plot_script = my_tests_dir / "plot_distribs_svg.py"

    if not etalon.is_file():
        print(f"Etalon file not found: {etalon}", file=sys.stderr)
        return 1

    results_root.mkdir(parents=True, exist_ok=True)

    for tested_path in args.tested:
        tested = tested_path.expanduser().resolve()
        if not tested.is_file():
            print(f"Tested file not found: {tested}", file=sys.stderr)
            return 1

        prefix = short_prefix(tested, args.prefix_tag)
        prefixes = {test_num: results_root / f"{prefix}_{test_num}" for test_num in TEST_CONFIGS}

        for test_num, cfg in TEST_CONFIGS.items():
            cmd = [
                "python3",
                str(my_tests_dir / cfg["script"]),
                "--tested",
                str(tested),
                "--output-root",
                str(prefixes[test_num]),
                "--p-values",
                *[str(p) for p in cfg["p_values"]],
                "--xor",
                "--keep-going",
            ]
            run_command(cmd, repo_root)

        for test_num, cfg in TEST_CONFIGS.items():
            p_values = cfg.get("chart_only", cfg["p_values"])
            for p in p_values:
                run_dir = prefixes[test_num] / cfg["dir_template"].format(p=p)
                for coord in cfg["chart_coords"]:
                    etal_file = run_dir / f"000000.etal.{coord:04d}"
                    test_file = run_dir / f"000000.test.{coord:04d}"
                    out_file = run_dir / f"coord{coord:04d}.svg"
                    if not etal_file.is_file() or not test_file.is_file():
                        continue
                    title = (
                        f"Test {test_num} {sanitize_report_name(tested.stem)} p=q={p}"
                        if len(cfg["chart_coords"]) == 1
                        else f"Test {test_num} {sanitize_report_name(tested.stem)} p=q={p} coord={coord}"
                    )
                    cmd = [
                        "python3",
                        str(plot_script),
                        str(etal_file),
                        str(test_file),
                        "--out",
                        str(out_file),
                        "--title",
                        title,
                    ]
                    run_command(cmd, repo_root)

        report_path = build_report(repo_root, tested, prefixes)
        print(report_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
