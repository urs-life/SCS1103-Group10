# File-Save Power-Cut Simulator (Group 10, SCS 1103)

Compares **journaling** and **no-journaling** file saves when the power fails mid-save.
All results are **simulated**: no real files or hardware are affected, and the simulator does not measure real-world data loss.

## What you need
- Python 3.9 or newer (tkinter is included with a normal Python install; it is only needed for the window demo)
- `simulator.py` and `simulator_gui.py` in the same folder

## Quick start
```
python simulator.py        # text menu: tests and results
python simulator_gui.py    # window demo
```

## Text menu (`simulator.py`)
| Option | What it does |
|---|---|
| 1 | Shows a summary of the workload being used |
| 2 | Tests one power cut: choose a method, then the step where the power fails |
| 3 | Control test with no power cut; shows the extra writes journaling costs |
| 4 | Tries every cut point on one file and saves `results_all_cuts.csv` |
| 5 | Runs 30 matched iterations and saves `results_evaluation.csv` |
| 6 | Exit |

## Window demo (`simulator_gui.py`)
1. **Create a file:** type a file name and some text, then click **Create file**.
2. **Edit and save:** change the text, pick **Journaled** or **Direct**, drag the slider to choose where the power fails (or tick *No power cut*), then click **Save file**.
3. **Read the result:** the window shows **CONSISTENT** or **INCONSISTENT**, what the file now reads, and the save steps. Scroll down to see the full step log.
4. **Compare 30 matched trials** shows the summary table. **Start over** resets the demo.

## Reading the results
- **Verified:** the file is fully old or fully new, and its file information matches.
- **Incomplete:** the file is a mix of old and new blocks.
- **Info OK:** the recorded file information matches the file contents.
- **Restore / journal writes:** average extra writes needed for recovery and for journaling.

Expected pattern: journaling verifies every file at the cost of extra writes; direct saving avoids the extra writes but cannot recover from a cut.

## Workload data
By default the simulator uses a clearly labelled **synthetic** workload. To use a real trace sample, save it as `trace_sample.csv` in the same folder with the header `time,op,block_id,size,offset`, and record its source link and licence in the group report.
