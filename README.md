# 🌱 SucroX – Sugarcane Crossing Assistant

SucroX is a PyQt5 desktop application that helps sugarcane breeders manage tassel surveys, generate crossing combinations, enforce crossing rules, and keep track of daily crosses.  
It integrates **phenotypic datasets** (Photoperiod, CrossingDataset, GV traits, Kinship/AMAT) into a single streamlined workflow.

---

## ✨ Features

- **Tassel Survey**
  - Record flowering varieties by **Bay / Cart / Can**, with tassel counts and pollen ratings.
  - Auto-classify sex (male vs female) from pollen rating.
  - Save daily tassel surveys into dated CSVs.

- **Cross Combination Generator**
  - Automatically combine all male × female varieties recorded today.
  - Output `Combinations_*.csv` and tassel totals by variety.

- **Crosses for the Day**
  - View all possible crosses enriched with:
    - STD variety IDs
    - GV trait values (and % relative to baseline 2001299)
    - Kinship values from AMAT matrix
    - CrossingDataset info
  - Apply **crossing rules** (max females per male tassel, max males per female tassel).
  - Live availability tracking (remaining capacity).
  - Export selected crosses (guarded by availability).
  - Persistent column settings:
    - **Display names**
    - **Visible/hidden toggle**
    - **Drag-and-drop reordering**
    - **Conditional highlighting** (e.g., KINSHIP < 0.15 → yellow highlight).
    - **Column groups** for quick views.

- **Settings**
  - Manage file paths for Photoperiod, CrossingDataset, GV, and AMAT datasets.
  - Configure crossing rules.
  - Define highlight rules (with AND/OR logic).
  - Set persistent hidden columns and display names.
  - Reorder columns by drag-and-drop.
  - Create and manage column groups.

---

## 📂 Project Structure

When you first run the app, SucroX creates the following folders in the parent directory:

```
Crosses for the day/
Combinations/
Tassles/
tassle_survey_data/
Photoperiod_Pos/
CrossingDataset/
```

And JSON config files:

- `paths.json` → where your datasets are stored
- `rules.json` → crossing rules, hidden columns, highlights, display names
- `column_groups.json` → column group definitions

---

## ⚙️ Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/<yourname>/SucroX.git
   cd SucroX
   ```

2. **Set up environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

## ▶️ Running

From the repo root:

```bash
python Scripts/SucroX_2025.py
```

- On first launch, go to **Settings** → point the app to your CSV datasets (Photoperiod, CrossingDataset, GV, AMAT).
- If today’s `Possible_crossings_*.csv` doesn’t exist, generate it via the **Tassel Survey** tab.

Optional quick check (verifies paths):
```bash
python Scripts/SucroX_2025.py --check
```

---

## 📊 Input Datasets

SucroX integrates with these files (CSV format):

- `Photoperiod_Pos_2025.csv` → mapping AVARIETY ↔ STDVARIETY ↔ NUMVAR.
- `ZT_CrossingDataset.csv` → per-parent notes.
- `ZT_GVs_1.4.csv` → GV trait values by VARIETY.
- `AMAT_25.csv` → kinship matrix.

---

## 🖼️ Screenshots (to add)

- Tassel survey entry screen  
- Crosses for the Day matrix with highlights and hidden columns  
- Settings tab (highlight rules + drag-drop ordering)  

---

## 🛠️ Development

To bundle as a single `.exe` for Windows, install [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --noconfirm --name SucroX --windowed Scripts/SucroX_2025.py
```

The binary will be created in `dist/SucroX/`.

---

## 📜 License

[MIT License](LICENSE) — feel free to use and adapt.

---

## 🙌 Acknowledgments

SucroX is being developed as part of sugarcane breeding research at LSU.  
Special thanks to the breeding team for real-world feedback.
