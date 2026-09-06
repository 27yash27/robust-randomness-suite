#!/usr/bin/env python3
"""Generate generator files from a patched NIST STS tree.

    python3 generate_nist_inputs.py --sts /path/to/sts-2.1.2 \
        --out ./inputs --size-mb 100 --generators 1 7 9

Drives the patched `assess` binary once per generator, in an isolated working
directory, and records what it did. Nothing outside that directory is touched
and no process the script did not start is signalled.

Each generator is produced by a single `assess` invocation whose C loop walks
all the streams, which is what the original campaign did. Do not split it into
one process per chunk: that would restart the generator and change the bytes.
"""

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# STS menu number -> (name, identifier used in the 2026-05 campaign)
GENERATORS = {
    1: ("Linear_Congruential", "g04_linear_congruential_1gb"),
    2: ("Quadratic_Congruential_I", "g08_quadratic_congruential_i"),
    3: ("Quadratic_Congruential_II", "g07_quadratic_congruential_ii"),
    4: ("Cubic_Congruential", "g02_cubic_congruential_1gb"),
    5: ("XOR", "g09_xor_1gb"),
    6: ("Modular_Exponentiation", "g06_modular_exponentiation_1gb"),
    7: ("Blum-Blum-Shub", "g01_blum_blum_shub"),
    8: ("Micali-Schnorr", "g05_micali_schnorr_1gb"),
    9: ("G_Using_SHA-1", "g03_g_using_sha"),
}

CHUNK_BITS = 1_000_000          # one megabit per stream, as in the campaign
OUTPUT_NAME = "bad_generator_output.bin"


def sha256(path, limit=None):
    h = hashlib.sha256()
    read = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            if limit is not None and read + len(chunk) > limit:
                chunk = chunk[: limit - read]
            h.update(chunk)
            read += len(chunk)
            if limit is not None and read >= limit:
                break
    return h.hexdigest()


def tool_version(*cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:
        return "unknown"


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sts", type=Path, required=True,
                    help="patched NIST STS tree containing a built ./assess")
    ap.add_argument("--out", type=Path, required=True,
                    help="output directory; must not already exist")
    ap.add_argument("--size-mb", type=int, required=True,
                    help="size of each generated file in MB (campaign used 100 and 1000)")
    ap.add_argument("--generators", nargs="+", type=int,
                    default=sorted(GENERATORS),
                    help="STS menu numbers to generate (default: all nine)")
    ap.add_argument("--expect-exit", type=int, nargs="+", default=[0, 1],
                    metavar="CODE",
                    help="exit codes to accept from assess (default: 0 and 1; "
                         "the patched build is observed to exit 1 on success)")
    ap.add_argument("--keep-workspaces", action="store_true",
                    help="keep the per-generator STS copies for inspection")
    ap.add_argument("--force", action="store_true",
                    help="allow an existing output directory")
    return ap.parse_args()


def main():
    a = parse_args()
    a.expect_exit = set(a.expect_exit)
    sts = a.sts.resolve()
    assess = sts / "assess"
    if not assess.is_file() or not os.access(assess, os.X_OK):
        sys.exit(f"no executable assess in {sts}. Build it there first (see the guide).")
    for g in a.generators:
        if g not in GENERATORS:
            sys.exit(f"unknown generator {g}; valid values are {sorted(GENERATORS)}")

    out = a.out.resolve()
    if out.exists() and not a.force:
        sys.exit(f"{out} already exists; choose a new directory or pass --force")
    out.mkdir(parents=True, exist_ok=True)
    logs = out / "logs"
    logs.mkdir(exist_ok=True)

    expected_bytes = a.size_mb * 1_000_000
    streams = (expected_bytes * 8) // CHUNK_BITS
    if streams * CHUNK_BITS != expected_bytes * 8:
        sys.exit(f"--size-mb {a.size_mb} is not a whole number of "
                 f"{CHUNK_BITS}-bit streams")

    workspaces = out / "workspaces"
    workspaces.mkdir(exist_ok=True)

    print(f"STS      : {sts} (copied per run, never written to)")
    print(f"output   : {out}")
    print(f"each file: {expected_bytes:,} bytes, {streams} streams of {CHUNK_BITS} bits\n")

    rows, failures = [], 0
    for g in a.generators:
        name, campaign_id = GENERATORS[g]
        target = out / f"bad_{name}_{a.size_mb}MB.bin"

        # assess writes its output and its experiment logs into its own working
        # directory, so give each generator a private copy of the tree. The
        # caller's STS tree is never modified and two runs cannot collide.
        workspace = workspaces / f"gen{g}_{name}"
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(sts, workspace, symlinks=True)
        scratch = workspace / OUTPUT_NAME
        if scratch.exists():
            scratch.unlink()

        stdin_recipe = f"{g}\n1\n0\n{streams}\n"
        cmd = [str(workspace / "assess"), str(CHUNK_BITS)]
        print(f"generator {g}: {name} ...", end="", flush=True)
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=workspace, input=stdin_recipe, text=True,
                              capture_output=True)
        elapsed = round(time.time() - t0, 1)
        (logs / f"gen{g}_{name}.stdout").write_text(proc.stdout)
        (logs / f"gen{g}_{name}.stderr").write_text(proc.stderr)

        # The patched assess is observed to exit 1 on a fully successful
        # generation on the builds tested here. That specific code is therefore
        # accepted, along with 0; anything else, including a signal, is a
        # failure even if the file looks right. Override with --expect-exit if
        # your build differs.
        problem = ""
        if proc.returncode not in a.expect_exit:
            problem = (f"assess exited {proc.returncode}; expected one of "
                       f"{sorted(a.expect_exit)}")
        elif "Statistical Testing Complete" not in proc.stdout:
            problem = (f"assess did not reach its completion marker "
                       f"(exit {proc.returncode})")
        elif not scratch.is_file():
            problem = "no output file produced"
        else:
            actual = scratch.stat().st_size
            if actual != expected_bytes:
                problem = f"expected {expected_bytes} bytes, got {actual}"

        digest = size = ""
        if not problem:
            shutil.move(str(scratch), str(target))
            size = target.stat().st_size
            digest = sha256(target)
            print(f" ok  {elapsed}s  {digest[:16]}...")
        else:
            # keep whatever was produced, next to its logs, for diagnosis
            if scratch.exists():
                shutil.move(str(scratch), str(out / f"FAILED_{target.name}"))
            failures += 1
            print(f" FAILED: {problem}")

        rows.append({
            "sts_selector": g, "generator": name, "campaign_identifier": campaign_id,
            "file": target.name if not problem else "",
            "size_bytes": size, "sha256": digest,
            "streams": streams, "chunk_bits": CHUNK_BITS,
            "stdin_recipe": stdin_recipe.replace("\n", "\\n"),
            "command": json.dumps(cmd), "returncode": proc.returncode,
            "elapsed_s": elapsed, "problem": problem,
        })

    if not a.keep_workspaces:
        shutil.rmtree(workspaces, ignore_errors=True)

    with (out / "generated_manifest.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    (out / "provenance.json").write_text(json.dumps({
        "sts_tree": str(sts),
        "assess_sha256": sha256(assess),
        "size_mb": a.size_mb,
        "expected_bytes": expected_bytes,
        "streams_per_file": streams,
        "chunk_bits": CHUNK_BITS,
        "bit_packing": "eight bits per output byte, first bit in the most "
                       "significant position (packed_byte = (packed_byte << 1) | "
                       "bit); a partial final byte is left-shifted so its padding "
                       "sits in the low bits. This is the writer's convention and "
                       "is separate from how rtest later reads 32-bit integers. "
                       "See src/utilities.c and NIST_STS_Modifications_Guide.md.",
        "compiler_on_path": tool_version("gcc", "--version"),
        "openssl_on_path": tool_version("openssl", "version"),
        "note": "compiler_on_path and openssl_on_path describe the tools found "
                "now, not necessarily those used to build the assess binary "
                "recorded above by hash.",
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }, indent=2) + "\n")

    print(f"\nmanifest: {out / 'generated_manifest.csv'}")
    if failures:
        print(f"{failures} of {len(a.generators)} generators failed.")
        return 1
    print(f"all {len(a.generators)} generators produced the expected {expected_bytes:,} bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
