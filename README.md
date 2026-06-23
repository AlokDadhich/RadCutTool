# RadCutTool — Radiation Pattern Analyzer

Desktop app for GRASP `.grd` antenna radiation pattern files.  
Python translation of the MATLAB `RadCutTool` (Multi-Frequency Edition).

---

## Key Behaviours

- On file load, reads the **actual angular extent** of the grid and uses it everywhere:
  - Theta-cut quick-add buttons rebuilt with grid-aware values
  - Adding a theta cut outside the grid range shows a clear warning
  - Axis limits match the real grid extent (no blank padding)
- Phi cuts / Theta cuts / Both modes with sub-tab switching
- Overlay and Individual plot tabs
- Export PNG (overlay or per-cut)
- Multi-frequency block support

---

## Run Locally (Mac / Linux / Windows with Python)

```bash
pip install -r requirements.txt
python main.py
```

---

## Build Windows `.exe` via GitHub Actions

### One-time setup (5 minutes)

**Step 1** — Create a GitHub account at https://github.com  
**Step 2** — Create a new **public** repository named `RadCutTool`  
**Step 3** — Upload all files (keep `.github/workflows/build.yml` and `RadCutTool.spec`)  
**Step 4** — Click the **Actions** tab → watch "Build Windows EXE" run (~3-5 min)  
**Step 5** — Download **RadCutTool-Windows** artifact → unzip → get `RadCutTool.exe`

Every push to `main` auto-rebuilds the EXE.

---

## Use on Windows (no install needed)

1. Copy `RadCutTool.exe` to Windows PC (USB etc.)
2. Double-click — no Python, no internet, no install required

---

## Project Structure

```
RadCutTool/
├── main.py                  ← entry point
├── RadCutTool.spec          ← PyInstaller build config
├── requirements.txt         ← Python dependencies
├── .github/
│   └── workflows/
│       └── build.yml        ← GitHub Actions build script
├── parser/
│   └── grd_parser.py        ← reads .grd files (matches MATLAB parseGrdAll)
├── engine/
│   └── cut_engine.py        ← phi/theta cut interpolation (interp2 fix applied)
├── ui/
│   └── main_window.py       ← full GUI (tkinter + matplotlib)
└── utils/
    └── __init__.py
```
