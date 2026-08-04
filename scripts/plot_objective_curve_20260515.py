#!/usr/bin/env python3
"""
plot_objective_curve_20260515.py

Built 2026-05-15 for the "Adaptive (p, q) sweeps" section of the CiE note.

Reads a single per-(generator, test) history.json produced by the max-p sweep
script and plots `objective` vs probed `p` on a log-y axis. Annotates the
threshold (1e-10), the file-ceiling probe (max_p), and the strongest-signal
probe (best_p / best_obj). Stdlib only, emits SVG.

The intended use is to show, in a single figure, the "peak in the middle,
degrades at the file ceiling" behavior observed for several tests in the
32-41 batch -- e.g. SHA-1 on t37 (NIST Runs) where obj reaches floating-point
underflow at p in [40, 1920] but degrades to obj=0.247 at the file ceiling
p=2499. Reporting only the ceiling value would have hidden a real claim.

Usage:
  python3 plot_objective_curve_20260515.py \
      <campaign>/sweeps/<gen>/t<NN>/history.json \
      --out chart.svg \
      --title "SHA-1 t37 (NIST Runs) -- no-xor"

The script also accepts --threshold (default 1e-10) and --ymin (default 1e-17)
for axis tuning.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

WIDTH = 1100
HEIGHT = 650
MARGIN_L = 90
MARGIN_R = 60
MARGIN_T = 80
MARGIN_B = 70


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("history_json", type=Path, help="Path to history.json produced by max-p sweep")
    p.add_argument("--out", type=Path, default=Path("objective_curve.svg"))
    p.add_argument("--title", default="Objective vs p for a single (gen, test) cell")
    p.add_argument("--threshold", type=float, default=1e-10)
    p.add_argument("--ymin", type=float, default=1e-17)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    with args.history_json.open() as f:
        history = json.load(f)
    probes = [r for r in history if r.get("status") == "ok"
              and isinstance(r.get("objective"), (int, float))
              and r["objective"] > 0]
    if not probes:
        print(f"No ok probes in {args.history_json}")
        return 1

    probes_sorted = sorted(probes, key=lambda r: r["p"])
    xs = [r["p"] for r in probes_sorted]
    ys = [max(r["objective"], args.ymin) for r in probes_sorted]
    x_min, x_max = min(xs), max(xs)
    y_log_min = math.log10(args.ymin)
    y_log_max = 0.0  # log10(1.0)

    max_p = max(xs)
    best_record = min(probes_sorted, key=lambda r: r["objective"])
    best_p = best_record["p"]
    best_obj = max(best_record["objective"], args.ymin)
    final_record = next(r for r in probes_sorted if r["p"] == max_p)
    final_obj = max(final_record["objective"], args.ymin)
    thr = args.threshold

    def sx(x: float) -> float:
        if x_max == x_min:
            return MARGIN_L + (WIDTH - MARGIN_L - MARGIN_R) / 2
        return MARGIN_L + (WIDTH - MARGIN_L - MARGIN_R) * (x - x_min) / (x_max - x_min)

    def sy(y: float) -> float:
        ly = math.log10(max(y, args.ymin))
        frac = (ly - y_log_min) / (y_log_max - y_log_min)
        return MARGIN_T + (HEIGHT - MARGIN_T - MARGIN_B) * (1 - frac)

    # Build polyline of probe points
    line_pts = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in zip(xs, ys))

    # Build axis ticks: log decades for y, ~6 evenly-spaced for x
    y_ticks = []
    yt = int(math.floor(y_log_min))
    while yt <= 0:
        y_ticks.append(10.0 ** yt)
        yt += 2  # every 2 decades to avoid clutter
    x_n_ticks = 6
    x_step = max(1, (x_max - x_min) // x_n_ticks)
    x_ticks = list(range(x_min, x_max + 1, x_step))
    # Add x_max as a tick only if it's not crowding the previous tick
    if x_ticks[-1] != x_max:
        if x_max - x_ticks[-1] >= 0.4 * x_step:
            x_ticks.append(x_max)
        else:
            x_ticks[-1] = x_max  # replace nearby tick with the exact ceiling value

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">')
    parts.append(f'<rect width="100%" height="100%" fill="#f6f4ef"/>')
    parts.append(f'<text x="{MARGIN_L}" y="40" font-family="Menlo, Monaco, monospace" font-size="22" fill="#111">{args.title}</text>')
    parts.append(f'<text x="{MARGIN_L}" y="62" font-family="Menlo, Monaco, monospace" font-size="13" fill="#444">'
                 f'history: {args.history_json.name} ({len(probes_sorted)} probes)</text>')

    # Axes
    parts.append(f'<line x1="{MARGIN_L}" y1="{HEIGHT - MARGIN_B}" x2="{WIDTH - MARGIN_R}" y2="{HEIGHT - MARGIN_B}" stroke="#444" stroke-width="1.5"/>')
    parts.append(f'<line x1="{MARGIN_L}" y1="{MARGIN_T}" x2="{MARGIN_L}" y2="{HEIGHT - MARGIN_B}" stroke="#444" stroke-width="1.5"/>')

    # Y ticks (log scale)
    for v in y_ticks:
        ypx = sy(v)
        parts.append(f'<line x1="{MARGIN_L - 5}" y1="{ypx:.2f}" x2="{MARGIN_L}" y2="{ypx:.2f}" stroke="#444" stroke-width="1"/>')
        label = "1" if v == 1.0 else f"1e{int(math.log10(v))}"
        parts.append(f'<text x="{MARGIN_L - 10}" y="{ypx + 4:.2f}" text-anchor="end" font-family="Menlo, Monaco, monospace" font-size="12" fill="#444">{label}</text>')
        # grid line
        parts.append(f'<line x1="{MARGIN_L}" y1="{ypx:.2f}" x2="{WIDTH - MARGIN_R}" y2="{ypx:.2f}" stroke="#ddd" stroke-width="0.5"/>')

    # X ticks
    for v in x_ticks:
        xpx = sx(v)
        parts.append(f'<line x1="{xpx:.2f}" y1="{HEIGHT - MARGIN_B}" x2="{xpx:.2f}" y2="{HEIGHT - MARGIN_B + 5}" stroke="#444" stroke-width="1"/>')
        parts.append(f'<text x="{xpx:.2f}" y="{HEIGHT - MARGIN_B + 20}" text-anchor="middle" font-family="Menlo, Monaco, monospace" font-size="12" fill="#444">{v}</text>')

    # Axis labels
    parts.append(f'<text x="{(WIDTH - MARGIN_R + MARGIN_L) / 2}" y="{HEIGHT - 18}" text-anchor="middle" font-family="Menlo, Monaco, monospace" font-size="14" fill="#222">probe p (= q)</text>')
    parts.append(f'<text x="20" y="{(HEIGHT - MARGIN_B + MARGIN_T) / 2}" font-family="Menlo, Monaco, monospace" font-size="14" fill="#222" transform="rotate(-90 20 {(HEIGHT - MARGIN_B + MARGIN_T) / 2})" text-anchor="middle">KS objective (log scale)</text>')

    # Threshold line at thr
    thr_y = sy(thr)
    parts.append(f'<line x1="{MARGIN_L}" y1="{thr_y:.2f}" x2="{WIDTH - MARGIN_R}" y2="{thr_y:.2f}" stroke="#c84c09" stroke-width="2" stroke-dasharray="6,4"/>')
    parts.append(f'<text x="{WIDTH - MARGIN_R - 4}" y="{thr_y - 6:.2f}" text-anchor="end" font-family="Menlo, Monaco, monospace" font-size="12" fill="#c84c09">threshold = {thr:g}</text>')

    # Vertical guide at max_p (file ceiling)
    mx = sx(max_p)
    parts.append(f'<line x1="{mx:.2f}" y1="{MARGIN_T}" x2="{mx:.2f}" y2="{HEIGHT - MARGIN_B}" stroke="#888" stroke-width="1" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="{mx - 6:.2f}" y="{MARGIN_T + 16}" text-anchor="end" font-family="Menlo, Monaco, monospace" font-size="12" fill="#666">file ceiling p={max_p}</text>')

    # Data line + points
    parts.append(f'<polyline fill="none" stroke="#1864ab" stroke-width="2.5" points="{line_pts}"/>')
    for x, y in zip(xs, ys):
        parts.append(f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="4" fill="#1864ab"/>')

    # Mark best_p (peak signal)
    bx, by = sx(best_p), sy(best_obj)
    parts.append(f'<circle cx="{bx:.2f}" cy="{by:.2f}" r="7" fill="none" stroke="#2f9e44" stroke-width="3"/>')
    parts.append(f'<text x="{bx + 12:.2f}" y="{by - 8:.2f}" font-family="Menlo, Monaco, monospace" font-size="13" fill="#2f9e44">peak: p={best_p}, obj={best_obj:.3g}</text>')

    # Mark final_p (file ceiling probe)
    fx, fy = sx(max_p), sy(final_obj)
    parts.append(f'<circle cx="{fx:.2f}" cy="{fy:.2f}" r="7" fill="none" stroke="#c84c09" stroke-width="3"/>')
    # Position annotation: if the ceiling probe is near the right edge,
    # place text LEFT of the circle and BELOW it to avoid colliding with
    # the upper "file ceiling p=..." guide label.
    near_right = (WIDTH - MARGIN_R - fx) < 250
    label_x = fx - 12 if near_right else fx + 12
    label_anchor = "end" if near_right else "start"
    label_y = fy + 28 if near_right else fy - 12
    parts.append(f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="{label_anchor}" font-family="Menlo, Monaco, monospace" font-size="13" fill="#c84c09">ceiling: p={max_p}, obj={final_obj:.3g}</text>')

    parts.append('</svg>')
    args.out.write_text("\n".join(parts), encoding="utf-8")
    print(args.out)

    # Also print a one-line summary for the user
    print(f"  probes={len(probes_sorted)}, best p={best_p} obj={best_obj:.3g}, ceiling p={max_p} obj={final_obj:.3g}, threshold={thr:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
