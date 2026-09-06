#!/usr/bin/env python3
"""
Parallel orchestrator for run_maximal_p_sweep.py.

Round-robin splits the generator set into N groups, launches N independent
sweep processes in parallel (each writing to its own campaign_<gN> folder),
and merges the per-group maximal_p.csv files into a single canonical CSV
when all finish.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def canonical_generator_code(index: int, fname: str) -> str:
    stem = Path(fname).stem.replace("bad_", "").replace("-", "_")
    parts = [piece for piece in re.split(r"[^A-Za-z0-9]+", stem) if piece]
    short = "_".join(parts[:3]).lower()
    return f"g{index:02d}_{short}"[:32]


def main() -> int:
    sweep = Path(__file__).resolve().parent / "run_maximal_p_sweep.py"

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--generator-dir", type=Path, required=True,
                        help="Directory containing the generator .bin files to test")
    parser.add_argument("--etalon", type=Path, required=True,
                        help="Fixed reference file, passed through to run_maximal_p_sweep.py")
    parser.add_argument("--generator-glob", default="*.bin")
    parser.add_argument("--n-groups", type=int, default=3)
    parser.add_argument("--tests", nargs="+", type=int, default=list(range(22, 32)))
    parser.add_argument("--xor", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="merge even if a worker failed; the result is "
                             "labelled incomplete and still exits non-zero")
    parser.add_argument("--ksexact", action="store_true",
                        help="forwarded to each worker; without it the workers use "
                             "the default KS routine, which underflows at large "
                             "sample sizes on some platforms")
    parser.add_argument("--max-p", type=int, default=10_000,
                        help="forwarded to each worker as its sample-size cap")
    parser.add_argument("--results-root", type=Path, default=Path("sweep_results"),
                        help="Where to write results (default: ./sweep_results)")
    args = parser.parse_args()

    gens = sorted(args.generator_dir.glob(args.generator_glob))
    if not gens:
        print(f"No generators in {args.generator_dir}", file=sys.stderr)
        return 1
    print(f"Found {len(gens)} generators in {args.generator_dir}")

    groups: list[list[Path]] = [[] for _ in range(args.n_groups)]
    for i, g in enumerate(gens):
        groups[i % args.n_groups].append(g)

    work_dir = Path(tempfile.mkdtemp(prefix="maxp_parallel_"))
    print(f"Workdir: {work_dir}")
    print(f"Mode: {'XOR' if args.xor else 'NO-XOR'}")
    print(f"Tests: {args.tests}")
    print(f"Campaign tag base: {args.campaign}")
    print()

    procs = []
    log_files = []
    for gi, group in enumerate(groups):
        if not group:
            continue
        gdir = work_dir / f"group_{gi}"
        gdir.mkdir()
        for src in group:
            (gdir / src.name).symlink_to(src.resolve())
        log_path = work_dir / f"group_{gi}.log"
        log_f = open(log_path, "w")
        log_files.append(log_f)
        cmd = [sys.executable, "-u", str(sweep),
               "--campaign", f"{args.campaign}_g{gi}",
               "--generator-dir", str(gdir),
               "--etalon", str(args.etalon.resolve()),
               "--results-root", str(args.results_root.resolve()),
               "--max-p", str(args.max_p),
               "--xor" if args.xor else "--no-xor"]
        if args.ksexact:
            cmd.append("--ksexact")
        cmd += ["--tests"]
        cmd.extend(str(t) for t in args.tests)
        proc = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)
        procs.append((gi, proc, group, log_path))
        print(f"  Group {gi}: PID {proc.pid}  {len(group)} gens  log={log_path}")
        for src in group:
            print(f"    - {src.name}")
        print()

    print(f"Waiting for {len(procs)} parallel sweeps to finish...")
    t0 = time.monotonic()
    statuses: dict[int, int] = {}
    for gi, proc, group, log_path in procs:
        rc = proc.wait()
        statuses[gi] = rc
        elapsed = time.monotonic() - t0
        print(f"  [{elapsed/60:.1f} min] Group {gi} exited rc={rc}")
    for f in log_files:
        f.close()

    failed_groups = [gi for gi, rc in statuses.items() if rc != 0]
    missing_groups: list[int] = []
    # Set now so the merged metadata can reference it; recomputed once the
    # per-group files have actually been read.
    incomplete = bool(failed_groups)
    if failed_groups and not args.allow_incomplete:
        print(f"\nGroups {failed_groups} did not exit cleanly. Their per-group "
              f"directories and logs are left in place for inspection; nothing "
              f"has been merged, because a merged campaign built from an "
              f"incomplete set would look like a complete one.\n"
              f"Re-run those groups, or pass --allow-incomplete to merge what "
              f"succeeded and label the result incomplete.", file=sys.stderr)
        return 1
    if failed_groups:
        print(f"WARNING: groups {failed_groups} did not exit cleanly; "
              f"--allow-incomplete was given, so merging anyway")

    merged_dir = args.results_root / args.campaign
    merged_dir.mkdir(parents=True, exist_ok=True)

    # Track each per-group row as (group_index, group_subcode, file, full_row)
    # so we can re-key the gen_code AND move sweeps/charts trees into the
    # merged campaign with canonical names.
    rows: list[list[str]] = []
    header: list[str] | None = None
    sub_code_to_file: dict[tuple[int, str], str] = {}
    for gi, _, _, _ in procs:
        sub = args.results_root / f"{args.campaign}_g{gi}" / "maximal_p.csv"
        if not sub.exists():
            print(f"WARN: missing {sub}")
            missing_groups.append(gi)
            continue
        with sub.open() as f:
            r = csv.reader(f)
            h = next(r)
            if header is None:
                header = h
            for row in r:
                rows.append(row)
                sub_code_to_file[(gi, row[0])] = row[1]

    if header is None:
        print("ERROR: no group produced output", file=sys.stderr)
        return 1

    rows.sort(key=lambda r: (r[1], int(r[2])))
    file_to_idx: dict[str, int] = {}
    for r in rows:
        if r[1] not in file_to_idx:
            file_to_idx[r[1]] = len(file_to_idx) + 1
    file_to_canonical = {f: canonical_generator_code(i, f) for f, i in file_to_idx.items()}
    for r in rows:
        r[0] = file_to_canonical[r[1]]

    incomplete = bool(failed_groups or missing_groups)

    with (merged_dir / "maximal_p.csv").open("w", newline="", encoding="ascii") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)
    print(f"\nMerged {len(rows)} rows -> {merged_dir / 'maximal_p.csv'}")

    # Move sweeps/<sub_code>/ and charts/<sub_code>/ trees from each per-group
    # campaign into the merged dir, renamed to canonical gen_codes. This way
    # the merged dir layout is identical to a serial run.
    for (gi, sub_code), gen_file in sub_code_to_file.items():
        canonical = file_to_canonical[gen_file]
        for kind in ("sweeps", "charts"):
            src = args.results_root / f"{args.campaign}_g{gi}" / kind / sub_code
            dst = merged_dir / kind / canonical
            if not src.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))

    # Build the canonical generator_manifest.csv (one row per generator file).
    manifest_path = merged_dir / "generator_manifest.csv"
    with manifest_path.open("w", newline="", encoding="ascii") as f:
        w = csv.DictWriter(f, fieldnames=["generator_code", "filename", "path"])
        w.writeheader()
        for fname in sorted(file_to_idx.keys()):
            w.writerow({
                "generator_code": file_to_canonical[fname],
                "filename": fname,
                "path": str((args.generator_dir / fname).resolve()),
            })

    # Synthesize a campaign.json that documents the merged campaign and
    # records the per-group sub-campaigns it was assembled from.
    sub_metas = {}
    for gi, _, _, _ in procs:
        sub_json = args.results_root / f"{args.campaign}_g{gi}" / "campaign.json"
        if sub_json.exists():
            with sub_json.open() as f:
                sub_metas[f"g{gi}"] = json.load(f)
    template = next(iter(sub_metas.values()), {})
    merged_meta = {
        "campaign": args.campaign,
        "generator_dir": str(args.generator_dir.resolve()),
        "generator_glob": args.generator_glob,
        "etalon": template.get("etalon"),
        "rtest": template.get("rtest"),
        "xor": args.xor,
        "max_p_cap": template.get("max_p_cap"),
        "ksexact": args.ksexact,
        "ks_backend": "exact-gmp (-k)" if args.ksexact else "default-psmirnov2x",
        "failed_groups": failed_groups,
        "missing_groups": missing_groups,
        "complete": not incomplete,
        "threshold": template.get("threshold"),
        "charts_enabled": template.get("charts_enabled"),
        "tests": template.get("tests"),
        "elapsed_s": round(time.monotonic() - t0, 1),
        "parallel": {
            "n_groups": args.n_groups,
            "sub_campaigns": list(sub_metas.keys()),
        },
    }
    with (merged_dir / "campaign.json").open("w", encoding="ascii") as f:
        json.dump(merged_meta, f, indent=2)

    # Now that artifacts are moved out of each sub-campaign, remove the
    # (mostly-empty) per-group dirs so the directory tree is identical to a
    # serial-run output. Keep their .log files in the workdir for debugging.
    if incomplete:
        print("Keeping the per-group directories, because this campaign is "
              "incomplete and their metadata is not fully carried into the "
              "merged record.")
    else:
        for gi, _, _, _ in procs:
            sub_dir = args.results_root / f"{args.campaign}_g{gi}"
            if sub_dir.exists():
                shutil.rmtree(sub_dir)

    total = time.monotonic() - t0
    print(f"Wrote {merged_dir / 'maximal_p.csv'}")
    print(f"Wrote {merged_dir / 'generator_manifest.csv'}")
    print(f"Wrote {merged_dir / 'campaign.json'}")
    print(f"Total wall time: {total/60:.1f} min ({total/3600:.2f} hr)")
    if incomplete:
        print(f"\nINCOMPLETE: groups {sorted(set(failed_groups + missing_groups))} "
              f"did not contribute. Do not read this merged campaign as a full one.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
