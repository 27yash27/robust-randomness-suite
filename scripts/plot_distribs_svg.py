#!/usr/bin/env python3

import argparse
from pathlib import Path


WIDTH = 1000
HEIGHT = 700
MARGIN = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draw distribs-style empirical CDF step graphs as an SVG."
    )
    parser.add_argument("etal_file", type=Path, help="Path to the .etal.* file")
    parser.add_argument("test_file", type=Path, help="Path to the .test.* file")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("distribs.svg"),
        help="Output SVG path",
    )
    parser.add_argument(
        "--title",
        default="Distribs-style ECDF comparison",
        help="SVG title",
    )
    return parser.parse_args()


def read_values(path: Path) -> list[float]:
    values: list[float] = []
    with path.open("r", encoding="ascii") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            values.append(float(stripped.split()[0]))
    if len(values) < 2:
        raise ValueError(f"Need at least 2 values in {path}")
    values.sort()
    return values


def sx(x: float, min_x: float, max_x: float) -> float:
    span = max_x - min_x
    if span == 0:
        return MARGIN + (WIDTH - 2 * MARGIN) / 2
    return MARGIN + (WIDTH - 2 * MARGIN) * (x - min_x) / span


def sy(y: float) -> float:
    return HEIGHT - MARGIN - (HEIGHT - 2 * MARGIN) * y


def step_path(values: list[float], min_x: float, max_x: float) -> str:
    n = len(values)
    pts: list[tuple[float, float]] = []
    for i, value in enumerate(values):
        if i > 0:
            pts.append((sx(values[i - 1], min_x, max_x), sy(i / n)))
            pts.append((sx(value, min_x, max_x), sy(i / n)))
        pts.append((sx(value, min_x, max_x), sy(i / n)))
        pts.append((sx(value, min_x, max_x), sy((i + 1) / n)))
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)


def main() -> int:
    args = parse_args()
    etal_path = args.etal_file.expanduser().resolve()
    test_path = args.test_file.expanduser().resolve()
    out_path = args.out.expanduser().resolve()

    etal = read_values(etal_path)
    test = read_values(test_path)
    min_x = min(etal[0], test[0])
    max_x = max(etal[-1], test[-1])

    etal_path_svg = step_path(etal, min_x, max_x)
    test_path_svg = step_path(test, min_x, max_x)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <rect width="100%" height="100%" fill="#f6f4ef" />
  <text x="{MARGIN}" y="34" font-family="Menlo, Monaco, monospace" font-size="22" fill="#1b1b1b">{args.title}</text>
  <text x="{MARGIN}" y="58" font-family="Menlo, Monaco, monospace" font-size="14" fill="#444">etal: {etal_path.name}</text>
  <text x="{MARGIN}" y="78" font-family="Menlo, Monaco, monospace" font-size="14" fill="#444">test: {test_path.name}</text>

  <line x1="{MARGIN}" y1="{HEIGHT - MARGIN}" x2="{WIDTH - MARGIN}" y2="{HEIGHT - MARGIN}" stroke="#444" stroke-width="1.5"/>
  <line x1="{MARGIN}" y1="{MARGIN}" x2="{MARGIN}" y2="{HEIGHT - MARGIN}" stroke="#444" stroke-width="1.5"/>

  <text x="{MARGIN}" y="{HEIGHT - MARGIN + 24}" font-family="Menlo, Monaco, monospace" font-size="12" fill="#444">{min_x:.6g}</text>
  <text x="{WIDTH - MARGIN - 70}" y="{HEIGHT - MARGIN + 24}" font-family="Menlo, Monaco, monospace" font-size="12" fill="#444">{max_x:.6g}</text>
  <text x="{MARGIN - 34}" y="{MARGIN + 4}" font-family="Menlo, Monaco, monospace" font-size="12" fill="#444">1.0</text>
  <text x="{MARGIN - 34}" y="{HEIGHT - MARGIN + 4}" font-family="Menlo, Monaco, monospace" font-size="12" fill="#444">0.0</text>

  <polyline fill="none" stroke="#c84c09" stroke-width="2.5" points="{etal_path_svg}" />
  <polyline fill="none" stroke="#1864ab" stroke-width="2.5" points="{test_path_svg}" />

  <circle cx="{WIDTH - 180}" cy="42" r="5" fill="#c84c09"/>
  <text x="{WIDTH - 168}" y="46" font-family="Menlo, Monaco, monospace" font-size="12" fill="#333">etal</text>
  <circle cx="{WIDTH - 110}" cy="42" r="5" fill="#1864ab"/>
  <text x="{WIDTH - 98}" y="46" font-family="Menlo, Monaco, monospace" font-size="12" fill="#333">test</text>
</svg>
"""
    out_path.write_text(svg, encoding="ascii")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
