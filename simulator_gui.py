"""Group 10 interactive demo: create a file, edit it, pick a save method and power cut point.
Needs simulator.py in the same folder. Run: python simulator_gui.py"""
import simulator as sim
METHOD_LABELS = {"Journaled": "journaling", "Direct": "no-journaling"}
BLOCK_CHARS = 6      # characters stored per simulated block
MAX_CHARS = 48       # longest text allowed (8 blocks)
BG = "#101820"
PANEL = "#192630"
FIELD = "#2a3b48"
MUTED = "#a7b6c2"
GREEN = "#62d9b5"
RED = "#ff8585"

def chunk(text):
    return [text[i:i + BLOCK_CHARS] for i in range(0, len(text), BLOCK_CHARS)]

class UserFile:
    """A user's file as blocks. Works with the engine in simulator.py."""
    def __init__(self, old_text, new_text):
        ob, nb = chunk(old_text), chunk(new_text)
        n = max(len(ob), len(nb), 1)
        self.file_id = 0
        self.keys = ["block %d" % (i + 1) for i in range(n)]
        self.old = {k: (ob[i] if i < len(ob) else "") for i, k in enumerate(self.keys)}
        self.new = {k: (nb[i] if i < len(nb) else "") for i, k in enumerate(self.keys)}

def validate_name(raw):
    name = raw.strip()
    if not name:
        return False, "Please type a file name.", ""
    if len(name) > 30:
        return False, "File name is too long (30 characters maximum).", ""
    return True, "", name

def validate_text(text):
    if not text:
        return False, "The file needs some text."
    if len(text) > MAX_CHARS:
        return False, "Text is too long (%d characters maximum)." % MAX_CHARS
    return True, ""

def step_names(method, f):
    """Names of each save step, in the same order the engine runs them."""
    names = []
    if method == "journaling":
        names += ["Write change to journal", "Commit journal"]
    names += ["Write %s" % k for k in f.keys]
    names.append("Update file information")
    if method == "journaling":
        names.append("Clear journal")
    return names

def snapshot(method, f, done):
    """Storage after exactly `done` steps have completed."""
    total = sim.total_steps(method, f)
    st = sim.Storage(f)
    power = sim.Power(done + 1 if done < total else None)
    try:
        sim.pick_solution(method)(st, f, power)
    except sim.PowerCut:
        pass
    return st

def tag(f, key, value):
    if f.old[key] == f.new[key]:
        return "SAME"
    if value == f.new[key]:
        return "NEW"
    if value == f.old[key]:
        return "OLD"
    return "?"

def tiles(f, st):
    return [(st.blocks[k], tag(f, k, st.blocks[k])) for k in f.keys]

def save_outcome(method, f, cut):
    """cut = None for no power cut, else the step the power fails BEFORE."""
    total = sim.total_steps(method, f)
    done = total if cut is None else cut - 1
    st = snapshot(method, f, done)
    after_tiles = tiles(f, st)
    after = sim.verify(st, f)
    action = "-"
    if cut is not None:
        action = sim.recover(st, f) if method == "journaling" else "none available"
    final = sim.verify(st, f)
    return {
        "after_tiles": after_tiles, "final_tiles": tiles(f, st),
        "after": after, "final": final, "action": action,
        "final_text": "".join(st.blocks[k] for k in f.keys),
        "writes": st.data_writes + st.journal_writes,
        "recovery": st.recovery_writes,
    }

def verdict(old_text, new_text, final_text, final):
    """Returns (headline, explanation, is_good)."""
    if final["verified"] and final_text == new_text:
        return ("EDIT SAVED", "The whole edit reached the disk and the file information matches.", True)
    if final["verified"] and final_text == old_text:
        return ("EDIT LOST, ORIGINAL INTACT",
                "The power failed before the save could be committed, so the original file is untouched.", True)
    if final_text == new_text:
        return ("CONTENT COMPLETE, FILE INFO OUT OF DATE",
                "All the data was written but the file information still describes the old version.", False)
    return ("FILE CORRUPTED",
            "Part of the file is new and part is old, so it no longer reads as either version.", False)

def summary_text(rows):
    lines = ["METHOD       VERIFIED  INCOMPLETE  INFO OK  AVG RESTORE  AVG JOURNAL"]
    for label, m in METHOD_LABELS.items():
        sel = [r for r in rows if r["method"] == m]
        n = len(sel)
        lines.append("%-12s %-9s %-11s %-8s %-12.1f %.1f" % (
            label,
            "%d/%d" % (sum(r["verified"] for r in sel), n),
            "%d/%d" % (sum(r["incomplete"] for r in sel), n),
            "%d/%d" % (sum(r["info_accurate"] for r in sel), n),
            sum(r["recovery_writes"] for r in sel) / n,
            sum(r["journal_writes"] for r in sel) / n))
    return "\n".join(lines)

def main():
    import tkinter as tk
    from tkinter import ttk
    reqs, source = sim.load_workload()
    eval_rows = sim.evaluation_rows(sim.make_files(reqs))
    disk = {}                      # file name -> text stored on the simulated disk
    state = {"name": None}
    root = tk.Tk()
    root.title("CrashLab | File Save Simulator")
    root.geometry("840x%d" % min(740, root.winfo_screenheight() - 80))
    root.minsize(780, 560)
    root.configure(bg=BG)
    canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
    scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = tk.Frame(canvas, bg=BG)
    win_id = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
    root.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
    root.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
    root.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
    tk.Label(body, text="CRASHLAB", bg=BG, fg=GREEN, font=("Segoe UI", 10, "bold")).pack(pady=(14, 2))
    tk.Label(body, text="What survives a sudden power cut?", bg=BG, fg="white",
             font=("Segoe UI", 18, "bold")).pack(pady=(0, 10))
    def entry(parent, var, width):
        return tk.Entry(parent, textvariable=var, width=width, bg=FIELD, fg="white",
                        insertbackground="white", relief="flat", font=("Consolas", 10))
    p1 = tk.Frame(body, bg=PANEL, padx=16, pady=10)
    p1.pack(fill="x", padx=24, pady=(0, 8))
    tk.Label(p1, text="1 · CREATE A FILE", bg=PANEL, fg=GREEN,
             font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
    name_var = tk.StringVar(value="notes.txt")
    text_var = tk.StringVar(value="Hello from Group 10!")
    entry(p1, name_var, 16).grid(row=1, column=0, pady=(6, 0), ipady=3)
    entry(p1, text_var, 44).grid(row=1, column=1, padx=8, pady=(6, 0), sticky="ew", ipady=3)
    create_btn = tk.Button(p1, text="Create file", bg=GREEN, fg="#10201c", relief="flat",
                           font=("Segoe UI", 10, "bold"), padx=12, pady=3)
    create_btn.grid(row=1, column=2, pady=(6, 0))
    status1 = tk.Label(p1, text="Type a file name and its text, then create it.", bg=PANEL, fg=MUTED,
                       font=("Segoe UI", 9))
    status1.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
    p1.columnconfigure(1, weight=1)
    p2 = tk.Frame(body, bg=PANEL, padx=16, pady=10)
    p2.pack(fill="x", padx=24, pady=(0, 8))
    tk.Label(p2, text="2 · EDIT THE FILE AND CHOOSE HOW TO SAVE", bg=PANEL, fg=GREEN,
             font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
    edit_var = tk.StringVar(value="")
    entry(p2, edit_var, 60).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 8), ipady=3)
    tk.Label(p2, text="SAVE METHOD", bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).grid(row=2, column=0, sticky="w")
    tk.Label(p2, text="POWER CUT POINT", bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).grid(
        row=2, column=1, sticky="w", padx=12)
    method_box = ttk.Combobox(p2, state="readonly", values=list(METHOD_LABELS), width=14)
    method_box.current(0)
    method_box.grid(row=3, column=0, sticky="w")
    slider = tk.Scale(p2, from_=1, to=2, orient="horizontal", bg=PANEL, fg="white",
                      highlightthickness=0, troughcolor=FIELD, length=300)
    slider.grid(row=3, column=1, sticky="ew", padx=12)
    control_var = tk.BooleanVar(value=False)
    tk.Checkbutton(p2, text="No power cut (control)", variable=control_var, bg=PANEL, fg="white",
                   selectcolor=FIELD, activebackground=PANEL,
                   activeforeground="white").grid(row=4, column=1, sticky="w", padx=12)
    save_btn = tk.Button(p2, text="Save file", bg=GREEN, fg="#10201c", relief="flat",
                         font=("Segoe UI", 10, "bold"), padx=16, pady=6)
    save_btn.grid(row=3, column=2, padx=(4, 0))
    step_label = tk.Label(p2, text="", bg=PANEL, fg=GREEN, font=("Segoe UI", 9, "bold"))
    step_label.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
    status2 = tk.Label(p2, text="", bg=PANEL, fg=RED, font=("Segoe UI", 9))
    status2.grid(row=6, column=0, columnspan=3, sticky="w")
    p2.columnconfigure(1, weight=1)
    result = tk.Label(body, text="READY", bg=BG, fg=GREEN, font=("Segoe UI", 16, "bold"))
    result.pack(pady=(4, 2))
    readback = tk.Label(body, text="", bg=BG, fg="white", font=("Consolas", 10), wraplength=780)
    readback.pack()
    explanation = tk.Label(body, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=780)
    explanation.pack(pady=(2, 6))
    block_area = tk.Frame(body, bg=BG)
    block_area.pack(pady=(2, 4))
    tk.Label(body, text="3 · FOLLOW THE SAVE", bg=BG, fg=GREEN,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=30, pady=(4, 4))
    step_log = tk.Text(body, height=8, bg=PANEL, fg="white", relief="flat",
                       font=("Consolas", 9), padx=12, pady=8, state="disabled")
    step_log.pack(fill="x", padx=24, pady=(0, 6))
    bottom = tk.Frame(body, bg=BG)
    bottom.pack(pady=(0, 6))
    compare_btn = tk.Button(bottom, text="Compare 30 matched trials", bg=FIELD, fg="white",
                            relief="flat", font=("Segoe UI", 9), padx=10, pady=4)
    compare_btn.pack(side="left", padx=6)
    reset_btn = tk.Button(bottom, text="Start over", bg=FIELD, fg="white", relief="flat",
                          font=("Segoe UI", 9), padx=10, pady=4)
    reset_btn.pack(side="left", padx=6)
    tk.Label(body, text="Workload for the comparison: %s. Simulated disk only; no real files are changed." % source,
             bg=BG, fg="#738794", font=("Segoe UI", 8), wraplength=780).pack(pady=(0, 6))
    def current_method():
        return METHOD_LABELS[method_box.get()]
    def draw_blocks(tile_list):
        for w in block_area.winfo_children():
            w.destroy()
        colors = {"NEW": "#1c664f", "OLD": "#354653", "SAME": "#2a3b48", "?": "#7a2e2e"}
        for i, (text, t) in enumerate(tile_list):
            tk.Label(block_area, text='BLOCK %d\n"%s"\n%s' % (i + 1, text, t), bg=colors.get(t, "#354653"),
                     fg="white", font=("Consolas", 9, "bold"), width=9, height=4).pack(side="left", padx=3)
    def add_step(title, message):
        step_log.config(state="normal")
        step_log.insert("end", "%s: %s\n" % (title, message))
        step_log.see("end")
        step_log.config(state="disabled")
    def clear_log():
        step_log.config(state="normal")
        step_log.delete("1.0", "end")
        step_log.config(state="disabled")
    def planned_file():
        name = state["name"]
        if name is None:
            return None
        new_text = edit_var.get()
        if not new_text:
            return None
        return UserFile(disk[name], new_text)
    def refresh_slider(*_):
        f = planned_file()
        if f is None:
            step_label.config(text="Create a file first, then edit its text.")
            return
        names = step_names(current_method(), f)
        slider.config(to=len(names))
        if slider.get() > len(names):
            slider.set(len(names))
        update_label()
    def update_label(*_):
        f = planned_file()
        if f is None:
            return
        names = step_names(current_method(), f)
        k = min(slider.get(), len(names))
        step_label.config(text="Power fails just BEFORE step %d of %d: %s" % (k, len(names), names[k - 1]))
    def show_disk():
        name = state["name"]
        status1.config(text='"%s" on disk reads: "%s"' % (name, disk[name]), fg=MUTED)
    def create_file():
        ok, msg, name = validate_name(name_var.get())
        if not ok:
            status1.config(text=msg, fg=RED)
            return
        ok, msg = validate_text(text_var.get())
        if not ok:
            status1.config(text=msg, fg=RED)
            return
        disk.clear()
        disk[name] = text_var.get()
        state["name"] = name
        edit_var.set(text_var.get())
        clear_log()
        result.config(text="FILE CREATED", fg=GREEN)
        readback.config(text="")
        explanation.config(text="Now change the text below, pick a save method and a power cut point, then save.")
        draw_blocks([(b, "OLD") for b in chunk(disk[name])])
        show_disk()
        status2.config(text="")
        refresh_slider()
    def finish(f, old_text, new_text, r, cut):
        headline, why, good = verdict(old_text, new_text, r["final_text"], r["final"])
        consistent = r["final"]["verified"]
        result.config(text="CONSISTENT" if consistent else "INCONSISTENT", fg=GREEN if consistent else RED)
        readback.config(text='%s\nFile now reads: "%s"' % (headline, r["final_text"]))
        explanation.config(text="%s  (Writes: %d, recovery writes: %d)" % (why, r["writes"], r["recovery"]))
        disk[state["name"]] = r["final_text"]
        show_disk()
        save_btn.config(state="normal")
    def animate(method, f, old_text, new_text, cut, done, limit, names):
        if done < limit:
            add_step("STEP %d" % (done + 1), names[done])
            draw_blocks(tiles(f, snapshot(method, f, done + 1)))
            root.after(600, lambda: animate(method, f, old_text, new_text, cut, done + 1, limit, names))
            return
        r = save_outcome(method, f, cut)
        if cut is None:
            add_step("DONE", "Save completed with no power cut.")
            finish(f, old_text, new_text, r, cut)
            return
        add_step("POWER CUT", "Power failed before step %d (%s)." % (cut, names[cut - 1]))
        draw_blocks(r["after_tiles"])
        def after_cut():
            if method == "journaling":
                add_step("RECOVERY", r["action"].capitalize() + ".")
                draw_blocks(r["final_tiles"])
            else:
                add_step("RECOVERY", "No journal, so nothing to restore from.")
            add_step("VERIFY", r["final"]["label"])
            finish(f, old_text, new_text, r, cut)
        root.after(700, after_cut)
    def save():
        name = state["name"]
        if name is None:
            status2.config(text="Create a file first.")
            return
        new_text = edit_var.get()
        ok, msg = validate_text(new_text)
        if not ok:
            status2.config(text=msg)
            return
        old_text = disk[name]
        if new_text == old_text:
            status2.config(text="Change the text first, so there is something to save.")
            return
        status2.config(text="")
        f = UserFile(old_text, new_text)
        method = current_method()
        names = step_names(method, f)
        cut = None if control_var.get() else min(slider.get(), len(names))
        save_btn.config(state="disabled")
        clear_log()
        result.config(text="SAVING...", fg=GREEN)
        readback.config(text="")
        explanation.config(text="")
        draw_blocks(tiles(f, snapshot(method, f, 0)))
        limit = len(names) if cut is None else cut - 1
        animate(method, f, old_text, new_text, cut, 0, limit, names)
    def compare():
        win = tk.Toplevel(root)
        win.title("30 matched trials")
        win.configure(bg=PANEL)
        tk.Label(win, text="Same files, equivalent cut points, simulated workload", bg=PANEL,
                 fg=GREEN, font=("Segoe UI", 9, "bold")).pack(padx=14, pady=(12, 4))
        tk.Label(win, text=summary_text(eval_rows), bg=PANEL, fg="white", font=("Consolas", 9),
                 justify="left").pack(padx=14, pady=(0, 14))
    def start_over():
        disk.clear()
        state["name"] = None
        edit_var.set("")
        clear_log()
        draw_blocks([])
        result.config(text="READY", fg=GREEN)
        readback.config(text="")
        explanation.config(text="")
        status1.config(text="Type a file name and its text, then create it.", fg=MUTED)
        status2.config(text="")
        step_label.config(text="Create a file first, then edit its text.")
        save_btn.config(state="normal")
    create_btn.config(command=create_file)
    save_btn.config(command=save)
    compare_btn.config(command=compare)
    reset_btn.config(command=start_over)
    slider.config(command=update_label)
    method_box.bind("<<ComboboxSelected>>", refresh_slider)
    edit_var.trace_add("write", refresh_slider)
    refresh_slider()
    root.mainloop()

if __name__ == "__main__":
    main()
