import os
import subprocess
import sys
import threading
import time
from datetime import datetime

# Path to your NIST STS software
nist_dir = "<project-root>/sts-2.1.2"


def pre_run_cleanup():
    """Kill stale assess/generator processes and remove leftover output files.

    Prevents the bug where multiple processes append to bad_generator_output.bin
    simultaneously, producing files larger than expected.
    """
    print("=== Pre-run cleanup ===")
    my_pid = os.getpid()
    killed = []

    # Find and kill stale assess and generator script processes
    try:
        ps = subprocess.run(["ps", "-axo", "pid,command"], capture_output=True, text=True)
        for line in ps.stdout.splitlines()[1:]:
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue
            pid_str, cmd = parts
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            if pid == my_pid:
                continue
            if "./assess" in cmd or "/assess " in cmd or cmd.endswith("/assess"):
                try:
                    os.kill(pid, 9)
                    killed.append(f"assess (pid {pid})")
                except ProcessLookupError:
                    pass
            elif ("nist_test_generator_both.py" in cmd or "generate_nist_data.py" in cmd) \
                    and "grep" not in cmd:
                try:
                    os.kill(pid, 9)
                    killed.append(f"generator script (pid {pid})")
                except ProcessLookupError:
                    pass
    except Exception as e:
        print(f"  Warning: could not scan processes: {e}")

    if killed:
        print(f"  Killed stale processes: {', '.join(killed)}")
    else:
        print("  No stale assess/generator processes found.")

    # Remove leftover output file
    leftover = os.path.join(nist_dir, "bad_generator_output.bin")
    if os.path.exists(leftover):
        size = os.path.getsize(leftover)
        os.remove(leftover)
        print(f"  Removed stale bad_generator_output.bin ({size:,} bytes)")
    else:
        print("  No stale bad_generator_output.bin to remove.")

    print()


pre_run_cleanup()

# Chunk size per assess call: 1 Megabit = 125 KB per iteration
# Tests are now skipped in the C code (return early in nist_test_suite),
# so each iteration is very fast — just generation + bit-packing.
chunk_size_bits = "1000000"

# --- INTERACTIVE PROMPT ---
print("=== NIST STS Bad Generator Data Creator ===")
print("Choose the file size you want to generate:")
print(" 1. 100MB (800,000,000 bits) — 800 iterations per generator")
print(" 2. 1GB   (8,000,000,000 bits) — 8000 iterations per generator")

choice = input("\nEnter 1 or 2: ").strip()

if choice == "1":
    total_bits = 800_000_000
    size_label = "100MB"
elif choice == "2":
    total_bits = 8_000_000_000
    size_label = "1GB"
else:
    print("Invalid choice. Exiting script.")
    sys.exit()

chunk_bits = int(chunk_size_bits)
num_iterations = total_bits // chunk_bits

# All 9 built-in NIST generators
generators = {
    1: "Linear_Congruential",
    2: "Quadratic_Congruential_I",
    3: "Quadratic_Congruential_II",
    4: "Cubic_Congruential",
    5: "XOR",
    6: "Modular_Exponentiation",
    7: "Blum-Blum-Shub",
    8: "Micali-Schnorr",
    9: "G_Using_SHA-1"
}

os.chdir(nist_dir)
run_timestamp = datetime.now().strftime("%Y%m%d_%H%M")
output_dir = f"../My-RNGs-Tests/NIST_Bad_Generators_{run_timestamp}"
os.makedirs(output_dir, exist_ok=True)
print(f"Output folder for this run: {output_dir}")

expected_size = total_bits // 8
num_streams = num_iterations  # one stream per chunk

print(f"\nStarting NIST STS Data Generation for {size_label} files...")
print(f"Chunk size: {chunk_bits:,} bits | Streams per generator: {num_streams}")
print(f"(Single ./assess call per generator — C code loops through all streams.)\n")


def progress_poller(stop_event, expected, start_ticks, label):
    """Background thread: every 10s, print current file size + ETA."""
    while not stop_event.wait(10):
        if not os.path.exists("bad_generator_output.bin"):
            continue
        size = os.path.getsize("bad_generator_output.bin")
        elapsed = time.time() - start_ticks
        pct = (size / expected * 100) if expected else 0
        if size > 0 and pct > 0:
            eta = elapsed * (100 - pct) / pct
            print(f"  [{label}] {size:,} / {expected:,} bytes ({pct:.1f}%) — "
                  f"{elapsed:.0f}s elapsed, ~{eta:.0f}s remaining", flush=True)
        else:
            print(f"  [{label}] {size:,} bytes — {elapsed:.0f}s elapsed", flush=True)


for gen_id, gen_name in generators.items():

    # CLEANUP: Delete old appended file before starting a new generator
    if os.path.exists("bad_generator_output.bin"):
        os.remove("bad_generator_output.bin")

    # --- START TIMER & TIMESTAMP ---
    start_time = datetime.now()
    start_ticks = time.time()
    print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] Started generating {size_label} data for {gen_name}...")

    # Single ./assess call: C code loops through all `num_streams` internally,
    # calling the bit-packing routine once per stream. This avoids per-call
    # subprocess setup overhead and (critically) prevents any other process
    # from interleaving writes into bad_generator_output.bin.
    simulated_input = f"{gen_id}\n1\n0\n{num_streams}\n"

    # Background thread for periodic progress updates (every 10s)
    stop_event = threading.Event()
    poller = threading.Thread(
        target=progress_poller,
        args=(stop_event, expected_size, start_ticks, gen_name),
        daemon=True,
    )
    poller.start()

    try:
        subprocess.run(
            ["./assess", chunk_size_bits],
            input=simulated_input,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"  Error running assess for {gen_name}: {e}")
        stop_event.set()
        poller.join(timeout=1)
        continue

    stop_event.set()
    poller.join(timeout=1)

    # --- END TIMER & TIMESTAMP ---
    end_time = datetime.now()
    end_ticks = time.time()

    elapsed_seconds = end_ticks - start_ticks
    elapsed_minutes = elapsed_seconds / 60

    print(f"[{end_time.strftime('%Y-%m-%d %H:%M:%S')}] Finished generating data for {gen_name}.")
    print(f"--> Time taken: {elapsed_minutes:.2f} minutes ({elapsed_seconds:.2f} seconds).")

    # RENAME & SAVE
    if os.path.exists("bad_generator_output.bin"):
        new_filename = os.path.join(output_dir, f"bad_{gen_name}_{size_label}.bin")

        if os.path.exists(new_filename):
            os.remove(new_filename)

        os.rename("bad_generator_output.bin", new_filename)
        print(f"--> Success! Saved to {new_filename}")

        # --- HEXDUMP VERIFICATION ---
        with open(new_filename, "rb") as f:
            sample = f.read(64)

        file_size = os.path.getsize(new_filename)
        unique_bytes = set(sample)

        if unique_bytes <= {0x00, 0x01}:
            print(f"    [WARN] File appears to contain unpacked 0x00/0x01 patterns — "
                  f"C routine may not be packing bits correctly.")
        else:
            print(f"    [VERIFIED] Hexdump looks good — {len(unique_bytes)} distinct byte values "
                  f"in first 64 bytes (packed binary confirmed).")

        hex_preview = " ".join(f"{b:02x}" for b in sample[:16])
        print(f"    First 16 bytes: {hex_preview}")
        print(f"    Total file size: {file_size:,} bytes (expected {expected_size:,} bytes)")

        if file_size == expected_size:
            print(f"    [SIZE OK] File size matches expected {size_label}.\n")
        else:
            print(f"    [SIZE MISMATCH] Expected {expected_size:,} but got {file_size:,} bytes.\n")
    else:
        print(f"--> Error: Output was not created for {gen_name}.\n")

print("All generators have been successfully processed!")
