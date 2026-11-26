"""Group 10 file-save power-cut simulator: journaling vs no-journaling (simulated data only).
Run: python simulator.py. Optional trace_sample.csv columns: time,op,block_id,size,offset."""
import csv
import os
import random
TRACE_FILE = "trace_sample.csv"
FILE_BLOCKS = 5      # blocks per simulated file save
ITERATIONS = 30      # evaluation iterations (from our evaluation plan)
SEED = 2026          # fixed seed so results are repeatable
METHODS = ("no-journaling", "journaling")

class PowerCut(Exception):
    pass

def synthetic_workload(n=200, seed=SEED):
    """Fallback workload. This is SIMULATED data, not a real trace."""
    rng = random.Random(seed)
    reqs, t = [], 0.0
    for _ in range(n):
        t += rng.random() * 0.01
        reqs.append({
            "time": round(t, 4),
            "op": "write" if rng.random() < 0.7 else "read",
            "block_id": rng.randint(1000, 1999),
            "size": rng.choice([512, 1024, 4096]),
            "offset": rng.randint(0, 255) * 512,
        })
    return reqs

def is_write(op):
    return op in ("write", "w", "put", "set")

def load_workload():
    """Use trace_sample.csv if present and valid, otherwise synthetic data."""
    if os.path.exists(TRACE_FILE):
        try:
            reqs = []
            with open(TRACE_FILE, newline="") as f:
                for row in csv.DictReader(f):
                    reqs.append({
                        "time": float(row["time"]),
                        "op": row["op"].strip().lower(),
                        "block_id": int(row["block_id"]),
                        "size": int(row["size"]),
                        "offset": int(row["offset"]),
                    })
            if sum(1 for r in reqs if is_write(r["op"])) >= FILE_BLOCKS:
                return reqs, "trace file (" + TRACE_FILE + ")"
            print("Trace file has too few write requests. Using synthetic data.")
        except (KeyError, ValueError):
            print("Trace file columns/values not valid. Using synthetic data.")
    return synthetic_workload(), "SYNTHETIC (simulated) workload"

def analyse_workload(reqs, source):
    writes = [r for r in reqs if is_write(r["op"])]
    print("\n--- Workload analysis ---")
    print("Source           :", source)
    print("Total requests   :", len(reqs))
    print("Write requests   :", len(writes))
    print("Distinct blocks  :", len(set(r["block_id"] for r in reqs)))
    if reqs:
        avg = sum(r["size"] for r in reqs) / len(reqs)
        span = reqs[-1]["time"] - reqs[0]["time"]
        print("Average size     : %.0f bytes" % avg)
        print("Time span        : %.3f" % span)
    print("First 3 requests :")
    for r in reqs[:3]:
        print("  ", r)

class SimFile:
    """One file save = FILE_BLOCKS block writes taken from the workload."""
    def __init__(self, file_id, reqs):
        self.file_id = file_id
        self.keys, self.old, self.new = [], {}, {}
        for r in reqs:
            key = "%d:%d" % (r["block_id"], r["offset"])
            if key in self.old:
                continue
            self.keys.append(key)
            self.old[key] = "OLD|%s|%d" % (key, r["size"])
            self.new[key] = "NEW|%s|%d" % (key, r["size"])

def make_files(reqs):
    writes = [r for r in reqs if is_write(r["op"])]
    files = []
    for i in range(0, len(writes) - FILE_BLOCKS + 1, FILE_BLOCKS):
        files.append(SimFile(len(files) + 1, writes[i:i + FILE_BLOCKS]))
    return files

class Power:
    """Counts steps. If cut_at = k, power fails just BEFORE step k happens."""
    def __init__(self, cut_at=None):
        self.cut_at = cut_at
        self.step = 0
    def tick(self):
        self.step += 1
        if self.cut_at is not None and self.step == self.cut_at:
            raise PowerCut()

class Storage:
    def __init__(self, f):
        self.blocks = dict(f.old)   # data blocks on the simulated disk
        self.meta = "OLD"           # file information log (recorded version)
        self.journal = None         # {"blocks": {...}, "committed": bool}
        self.data_writes = 0
        self.journal_writes = 0
        self.recovery_writes = 0
    def write_block(self, key, value, power, kind="data"):
        power.tick()
        self.blocks[key] = value
        if kind == "recovery":
            self.recovery_writes += 1
        else:
            self.data_writes += 1
    def write_meta(self, version, power, kind="data"):
        power.tick()
        self.meta = version
        if kind == "recovery":
            self.recovery_writes += 1
        else:
            self.data_writes += 1
    def write_journal(self, blocks, power):
        power.tick()
        self.journal = {"blocks": dict(blocks), "committed": False}
        self.journal_writes += len(blocks)   # a copy of every block
    def commit_journal(self, power):
        power.tick()
        self.journal["committed"] = True
        self.journal_writes += 1
    def clear_journal(self, power):
        power.tick()
        self.journal = None
        self.journal_writes += 1

def save_direct(st, f, power):
    """No-journaling: overwrite blocks in place, then update file info."""
    for k in f.keys:
        st.write_block(k, f.new[k], power)
    st.write_meta("NEW", power)

def save_journal(st, f, power):
    """Journaling (redo log): log + commit first, then apply, then clear."""
    st.write_journal(f.new, power)
    st.commit_journal(power)
    for k in f.keys:
        st.write_block(k, f.new[k], power)
    st.write_meta("NEW", power)
    st.clear_journal(power)
SOLUTIONS = {"no-journaling": save_direct, "journaling": save_journal}

def pick_solution(name):
    return SOLUTIONS[name]

def recover(st, f):
    """Runs on 'restart'. Only journaling has anything to recover from."""
    if st.journal is None:
        return "no journal to use"
    if st.journal["committed"]:
        p = Power()  # no power cut during recovery
        for k, v in st.journal["blocks"].items():
            st.write_block(k, v, p, "recovery")
        st.write_meta("NEW", p, "recovery")
        st.journal = None
        return "replayed committed journal"
    st.journal = None
    return "discarded uncommitted journal"

def verify(st, f):
    olds = sum(1 for k in f.keys if st.blocks[k] == f.old[k])
    news = sum(1 for k in f.keys if st.blocks[k] == f.new[k])
    n = len(f.keys)
    if olds == n:
        content = "OLD"
    elif news == n:
        content = "NEW"
    else:
        content = "MIXED"
    info_ok = content != "MIXED" and st.meta == content
    if content == "MIXED":
        label = "INCOMPLETE (mixed blocks)"
    elif not info_ok:
        label = "INCONSISTENT (file info wrong)"
    elif content == "OLD":
        label = "OLD (intact)"
    else:
        label = "NEW (complete)"
    return {
        "label": label,
        "verified": info_ok,
        "incomplete": content == "MIXED",
        "info_accurate": info_ok,
    }

def run_trial(method, f, cut_at=None):
    st = Storage(f)
    power = Power(cut_at)
    cut = False
    try:
        pick_solution(method)(st, f, power)
    except PowerCut:
        cut = True
    after = verify(st, f)
    action = "-"
    if cut and method == "journaling":
        action = recover(st, f)
    elif cut:
        action = "none available"
    final = verify(st, f)
    return {
        "method": method, "cut_at": cut_at, "power_cut": cut,
        "steps": power.step, "after": after, "final": final,
        "action": action, "data_writes": st.data_writes,
        "journal_writes": st.journal_writes,
        "recovery_writes": st.recovery_writes,
    }

def total_steps(method, f):
    return run_trial(method, f, None)["steps"]

def ask_int(prompt, lo, hi):
    while True:
        s = input(prompt).strip()
        if s.isdigit() and lo <= int(s) <= hi:
            return int(s)
        print("Please enter a number from %d to %d." % (lo, hi))

def action_single(files):
    f = files[0]
    print("\n1. no-journaling   2. journaling")
    method = METHODS[ask_int("Choose method (1-2): ", 1, 2) - 1]
    n = total_steps(method, f)
    print("A full save of file #%d (%d blocks) has %d steps." % (f.file_id, len(f.keys), n))
    cut = ask_int("Cut the power before which step? (1-%d): " % n, 1, n)
    r = run_trial(method, f, cut)
    print("\n--- Result ---")
    print("Method               :", method)
    print("Power cut before step:", cut)
    print("State after cut      :", r["after"]["label"])
    print("Recovery action      :", r["action"])
    print("Final state          :", r["final"]["label"])
    print("Recovery writes      :", r["recovery_writes"])

def action_control(files):
    print("\n--- Control test: NO power cut (averaged over %d files) ---" % len(files))
    totals = {}
    for m in METHODS:
        w = j = 0
        ok = 0
        for f in files:
            r = run_trial(m, f, None)
            w += r["data_writes"]
            j += r["journal_writes"]
            ok += 1 if r["final"]["label"] == "NEW (complete)" else 0
        totals[m] = (w / len(files), j / len(files), ok)
        print("%-14s saved OK: %d/%d | data writes/save: %.1f | journal writes/save: %.1f"
              % (m, ok, len(files), w / len(files), j / len(files)))
    base = totals["no-journaling"][0]
    extra = totals["journaling"][1]
    if base:
        print("Write overhead of journaling: +%.1f writes per save (+%.0f%%)"
              % (extra, 100.0 * extra / base))

def action_all_cuts(files):
    f = files[0]
    rows = []
    print("\nAll cut points for file #%d" % f.file_id)
    print("%-14s%-5s%-31s%-30s%s" % ("method", "cut", "state after cut", "recovery action", "final state"))
    print("-" * 110)
    for m in METHODS:
        for cut in range(1, total_steps(m, f) + 1):
            r = run_trial(m, f, cut)
            rows.append([m, cut, r["after"]["label"], r["action"], r["final"]["label"]])
            print("%-14s%-5d%-31s%-30s%s" % tuple(rows[-1]))
    with open("results_all_cuts.csv", "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["method", "cut_step", "state_after_cut", "recovery_action", "final_state"])
        w.writerows(rows)
    print("\nSaved to results_all_cuts.csv")

def evaluation_rows(files):
    """Run the matched iterations and return one row per method per iteration."""
    rng = random.Random(SEED)
    rows = []
    for i in range(ITERATIONS):
        f = files[i % len(files)]
        frac = rng.random()  # same relative cut location for both methods
        for m in METHODS:
            total = total_steps(m, f)
            cut = 1 + min(total - 1, int(frac * total))
            r = run_trial(m, f, cut)
            rows.append({
                "iteration": i + 1, "file": f.file_id, "method": m,
                "cut_percent": round(100 * cut / total),
                "final_state": r["final"]["label"],
                "verified": r["final"]["verified"],
                "incomplete": r["final"]["incomplete"],
                "info_accurate": r["final"]["info_accurate"],
                "recovery_writes": r["recovery_writes"],
                "journal_writes": r["journal_writes"],
            })
    return rows

def action_evaluation(files):
    rows = evaluation_rows(files)
    cols = ["iteration", "file", "method", "cut_percent", "final_state", "verified",
            "incomplete", "info_accurate", "recovery_writes", "journal_writes"]
    with open("results_evaluation.csv", "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("\n--- Evaluation: %d iterations, identical files and equivalent cut points ---" % ITERATIONS)
    print("%-14s%-10s%-12s%-14s%-12s%s" % ("method", "verified", "incomplete", "info-accurate", "restore-wr", "journal-wr"))
    print("-" * 74)
    for m in METHODS:
        sel = [r for r in rows if r["method"] == m]
        n = len(sel)
        print("%-14s%-10s%-12s%-14s%-12.1f%.1f" % (
            m,
            "%d/%d" % (sum(r["verified"] for r in sel), n),
            "%d/%d" % (sum(r["incomplete"] for r in sel), n),
            "%d/%d" % (sum(r["info_accurate"] for r in sel), n),
            sum(r["recovery_writes"] for r in sel) / n,
            sum(r["journal_writes"] for r in sel) / n))
    print("\nverified      = file is fully OLD or fully NEW and file info matches")
    print("incomplete    = file has a mix of old and new blocks")
    print("restore-wr    = average writes needed during recovery")
    print("journal-wr    = average extra writes caused by journaling")
    print("\nSaved to results_evaluation.csv")

def menu():
    reqs, source = load_workload()
    files = make_files(reqs)
    print("=" * 56)
    print(" Group 10 - File-Save Power-Cut Simulator")
    print(" Workload:", source)
    print(" (all results are simulated)")
    print("=" * 56)
    while True:
        print("\n1. Analyse workload")
        print("2. Test one power cut (choose method and step)")
        print("3. Control test (no power cut)")
        print("4. Try every cut point on one file (saves CSV)")
        print("5. Run %d-iteration evaluation (saves CSV)" % ITERATIONS)
        print("6. Exit")
        c = input("Choose an option (1-6): ").strip()
        if c == "1":
            analyse_workload(reqs, source)
        elif c == "2":
            action_single(files)
        elif c == "3":
            action_control(files)
        elif c == "4":
            action_all_cuts(files)
        elif c == "5":
            action_evaluation(files)
        elif c == "6":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1 to 6.")

if __name__ == "__main__":
    menu()
