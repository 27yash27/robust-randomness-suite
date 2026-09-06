#!/usr/bin/env python3
"""Run one test at several sample sizes and draw the ECDF curves side by side.

    ./compare_curves.py -t 37 -f mygen.bin -e etalon.bin

Produces one SVG with a panel per sample size. Each panel draws the two
empirical distribution functions the robust test compares: the tested
generator and the same generator XOR-ed with the etalon. Curves that lie on
top of each other mean the test sees nothing; curves that pull apart mean the
test distinguishes the generator from random. The KS p-value is printed above
each panel.

Only the standard library is used.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from robust_test_catalog import TEST_CATALOG

PANEL_W, PANEL_H = 340, 260
MARGIN = 46
COLS = 3


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-t", "--test", type=int, required=True,
                   help="test number (22-41)")
    p.add_argument("-f", "--file", type=Path, required=True,
                   help="the generator file to test")
    p.add_argument("-e", "--etalon", type=Path, required=True,
                   help="the fixed reference file")
    p.add_argument("-o", "--out", type=Path, default=None,
                   help="output SVG (default: curves_t<N>_<generator>.svg)")
    p.add_argument("--rtest", type=Path,
                   default=Path(__file__).resolve().parent.parent / "robust" / "rtest",
                   help="path to the rtest binary")
    p.add_argument("--sizes", type=int, nargs="+", default=None,
                   help="sample sizes to use instead of the catalog defaults")
    p.add_argument("--coord", type=int, default=None,
                   help="which coordinate to plot for multi-value tests")
    p.add_argument("--no-xor", action="store_true",
                   help="compare the two files directly instead of XOR mode")
    return p.parse_args()


def read_values(path):
    vals = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                vals.append(float(line.split()[0]))
    vals.sort()
    return vals


def run_one(rtest, cfg, gen, etal, size, coord, use_xor, workdir):
    """Run rtest once; return (p_value, tested_values, etalon_values)."""
    outdir = workdir / f"p{size}"
    cmd = [str(rtest)]
    if use_xor:
        cmd.append("-x")
    cmd += ["-f", str(gen), "-e", str(etal),
            "-p", str(size), "-q", str(size),
            "-d", str(cfg.dimension), "-n", str(cfg.n_value),
            "-t", str(cfg.test_num), "-r", "1", "-o", str(outdir)]
    if cfg.modifier is not None:
        cmd += ["-m", str(cfg.modifier)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == -11 or proc.returncode == 139:
        raise RuntimeError(
            f"rtest crashed at -p {size}. High-dimension tests overflow the "
            f"stack at large sample sizes; raise the limit with "
            f"'ulimit -s unlimited' (Linux) or 'ulimit -s 65520' (macOS).")
    if proc.returncode != 0:
        raise RuntimeError(f"rtest failed at -p {size}: {proc.stderr.strip()}")
    if "oops" in proc.stdout or "oops" in proc.stderr:
        raise RuntimeError(
            f"ran out of data at -p {size}: both files need to be larger.")

    # Match an optional sign and an optional exponent. A bare [01]\.\d+ pattern
    # silently drops the leading minus of the default kernel's occasional -0.0,
    # turning a very small p-value into a plausible-looking one.
    numbers = re.findall(r"-?\d+\.\d+(?:[eE][-+]?\d+)?", proc.stdout)
    pval = float(numbers[coord]) if coord < len(numbers) else float("nan")

    suffix = f".{coord:04d}"
    tested = read_values(outdir / f"000000.test{suffix}")
    etalon = read_values(outdir / f"000000.etal{suffix}")
    return pval, tested, etalon


def ecdf_path(vals, lo, hi, x0, y0):
    """Step-function polyline points for one sample inside a panel box."""
    span = (hi - lo) or 1.0
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = x0 + (PANEL_W - 2 * 26) * (v - lo) / span
        pts.append((x, y0 - (PANEL_H - 2 * 34) * (i / n)))
        pts.append((x, y0 - (PANEL_H - 2 * 34) * ((i + 1) / n)))
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def build_svg(title, subtitle, panels):
    rows = (len(panels) + COLS - 1) // COLS
    width = MARGIN * 2 + COLS * PANEL_W
    height = MARGIN * 2 + 40 + rows * PANEL_H
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{MARGIN}" y="34" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="19" fill="#111">{title}</text>',
        f'<text x="{MARGIN}" y="56" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="13" fill="#555">{subtitle}</text>',
    ]

    for idx, (size, pval, tested, etalon) in enumerate(panels):
        col, row = idx % COLS, idx // COLS
        px = MARGIN + col * PANEL_W
        py = MARGIN + 40 + row * PANEL_H
        x0, y0 = px + 26, py + PANEL_H - 34

        lo = min(tested[0], etalon[0])
        hi = max(tested[-1], etalon[-1])

        out.append(f'<text x="{px + 26}" y="{py + 16}" '
                   f'font-family="Helvetica,Arial,sans-serif" font-size="13" '
                   f'fill="#111">p = q = {size}</text>')
        colour = "#b00020" if pval == pval and pval < 0.01 else "#333"
        if pval != pval:
            label = "KS p-value unavailable"
        elif pval <= 0.0:
            # A printed zero establishes only that the value fell below what the
            # driver's fixed-decimal output can show. Rounding, cancellation in
            # the default kernel and rational reduction in the GMP kernel are
            # different mechanisms, and none of them proves a bound.
            label = "KS p-value numerically unresolved (printed 0)"
        elif pval >= 1.0:
            label = f"KS p-value {pval:.4g} (at the upper limit)"
        else:
            label = f"KS p-value {pval:.4g}"
        out.append(f'<text x="{px + 26}" y="{py + 32}" '
                   f'font-family="Menlo,monospace" font-size="12" '
                   f'fill="{colour}">{label}</text>')
        out.append(f'<line x1="{x0}" y1="{y0}" x2="{x0 + PANEL_W - 52}" '
                   f'y2="{y0}" stroke="#999" stroke-width="1"/>')
        out.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" '
                   f'y2="{y0 - (PANEL_H - 68)}" stroke="#999" stroke-width="1"/>')
        out.append(f'<polyline fill="none" stroke="#c84c09" stroke-width="1.8" '
                   f'points="{ecdf_path(etalon, lo, hi, x0, y0)}"/>')
        out.append(f'<polyline fill="none" stroke="#1864ab" stroke-width="1.8" '
                   f'points="{ecdf_path(tested, lo, hi, x0, y0)}"/>')
        out.append(f'<text x="{x0}" y="{y0 + 16}" font-family="Menlo,monospace" '
                   f'font-size="10" fill="#777">{lo:.4g}</text>')
        out.append(f'<text x="{x0 + PANEL_W - 96}" y="{y0 + 16}" '
                   f'font-family="Menlo,monospace" font-size="10" '
                   f'fill="#777">{hi:.4g}</text>')

    legend_y = height - 14
    out.append(f'<circle cx="{MARGIN + 4}" cy="{legend_y - 4}" r="4" fill="#1864ab"/>')
    out.append(f'<text x="{MARGIN + 14}" y="{legend_y}" '
               f'font-family="Helvetica,Arial,sans-serif" font-size="12" '
               f'fill="#333">tested generator</text>')
    out.append(f'<circle cx="{MARGIN + 150}" cy="{legend_y - 4}" r="4" fill="#c84c09"/>')
    out.append(f'<text x="{MARGIN + 160}" y="{legend_y}" '
               f'font-family="Helvetica,Arial,sans-serif" font-size="12" '
               f'fill="#333">generator XOR etalon</text>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    args = parse_args()

    if args.test not in TEST_CATALOG:
        sys.exit(f"no catalog entry for test {args.test} "
                 f"(known: {min(TEST_CATALOG)}-{max(TEST_CATALOG)})")
    cfg = TEST_CATALOG[args.test]

    if not args.rtest.exists():
        sys.exit(f"rtest binary not found at {args.rtest} -- run 'make' in robust/ first")
    for f in (args.file, args.etalon):
        if not f.exists():
            sys.exit(f"file not found: {f}")

    sizes = args.sizes if args.sizes else list(cfg.p_values)[:5]
    coord = args.coord if args.coord is not None else cfg.chart_coords[0]
    out_path = args.out or Path(f"curves_t{args.test}_{args.file.stem}.svg")

    workdir = Path(tempfile.mkdtemp(prefix="compare_curves_"))
    panels = []
    try:
        for size in sizes:
            print(f"  test {args.test} at p=q={size} ...", end="", flush=True)
            try:
                pval, tested, etalon = run_one(
                    args.rtest, cfg, args.file, args.etalon,
                    size, coord, not args.no_xor, workdir)
            except RuntimeError as exc:
                print(f" skipped ({exc})")
                continue
            if pval != pval:
                print(" no p-value parsed, skipped")
                continue
            if pval <= 0.0:
                print(f" p-value {pval:.4g} (numerically unresolved: below the "
                      f"driver's printed resolution. -k uses the GMP kernel, "
                      f"which avoids cancellation but does not remove the "
                      f"fixed-decimal output or its own rational reduction.)")
            elif pval >= 1.0:
                print(f" p-value {pval:.4g} (exactly 1; legitimate at tiny "
                      f"sample sizes, otherwise suspect KS underflow)")
            else:
                print(f" p-value {pval:.4g}")
            panels.append((size, pval, tested, etalon))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if not panels:
        sys.exit("no run succeeded -- see the messages above")

    title = f"Test {args.test}: {cfg.title}"
    subtitle = (f"{args.file.name} vs etalon {args.etalon.name}, "
                f"coordinate {coord} of {cfg.dimension}"
                f"{'' if not args.no_xor else ', direct comparison (no XOR)'}")
    out_path.write_text(build_svg(title, subtitle, panels))
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
