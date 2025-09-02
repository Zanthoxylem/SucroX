import os, sys, csv, json, datetime
from pathlib import Path
from collections import defaultdict
import pandas as pd

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QUrl, QFileSystemWatcher
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGridLayout, QTableWidget, QTableWidgetItem,
    QFileDialog, QCheckBox, QMessageBox, QButtonGroup, QListWidget,
    QListWidgetItem, QDialog, QComboBox, QLineEdit, QScrollArea
)
from PyQt5.QtGui import QDesktopServices

# -------------------- UI constants --------------------
APP_FONT = QFont("Open Sans", 14)
TITLE_FONT = QFont("Open Sans", 28, QFont.Bold)
GREEN = "#01915A"
BG = "#e9f3f0"
BTN = "#01915A"
BTN_HOVER = "#188f62"
CARD = "#ffffff"
HEADER = "#cfe5e0"
BORDER = "#d7e7e2"

PALETTE = [
    ("Sunny Yellow", "#FFEB3B"),
    ("Soft Green",   "#C8E6C9"),
    ("Sky Blue",     "#BBDEFB"),
    ("Lavender",     "#E1BEE7"),
    ("Peach",        "#FFE0B2"),
    ("Rose",         "#FFCDD2"),
    ("Grey",         "#CFD8DC"),
]

# -------------------- Date & paths --------------------
date = datetime.date.today()
julian_date = date.toordinal() - datetime.date(date.year, 1, 1).toordinal() + 1

SCRIPT_PATH = Path(__file__).resolve()
PARENT_DIR = SCRIPT_PATH.parent.parent  # parent.parent per your requirement
os.chdir(str(PARENT_DIR))

GROUPS_PATH = PARENT_DIR / "column_groups.json"
PATHS_PATH  = PARENT_DIR / "paths.json"
RULES_PATH  = PARENT_DIR / "rules.json"

GROUPS_DEFAULT = {}
PATHS_DEFAULT = {
    "photoperiod": str(PARENT_DIR / "Photoperiod_Pos_2025.csv"),
    "crossingdataset": str(PARENT_DIR / "ZT_CrossingDataset.csv"),
    "gv": str(PARENT_DIR / "ZT_GVs_1.4.csv"),
    "amat": str(PARENT_DIR / "AMAT_25.csv"),
}
RULES_DEFAULT = {
    "females_per_male": 1,
    "males_per_female": 1,
    "hidden_columns": [],
    # {"name":"...", "logic":"AND"/"OR", "clauses":[{"column":"KINSHIP","op":">=","value":"0.15"}], "color":"#FFEB3B"}
    "highlight_rules": [],
    # NEW: mapping of original CSV header -> alternative display name used in Crosses for the Day
    "display_names": {}
}

# -------------------- util functions --------------------
def ensure_dirs():
    for rel in ["tassle_survey_data", "Tassles", "Combinations",
                "Crosses for the day", "Photoperiod_Pos", "CrossingDataset"]:
        (PARENT_DIR / rel).mkdir(parents=True, exist_ok=True)

def read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return json.loads(json.dumps(default))

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_paths():
    paths = read_json(PATHS_PATH, PATHS_DEFAULT)
    def _first_existing(cands):
        for c in cands:
            if not c:
                continue
            p = Path(c)
            if p.exists():
                return str(p)
        return cands[0] if cands else ""
    paths["photoperiod"] = _first_existing([
        paths.get("photoperiod",""), str(PARENT_DIR / "Photoperiod_Pos_2025.csv"),
        str(PARENT_DIR / "Photoperiod_Pos" / "Photoperiod_Pos_2025.csv")
    ])
    paths["crossingdataset"] = _first_existing([
        paths.get("crossingdataset",""), str(PARENT_DIR / "ZT_CrossingDataset.csv"),
        str(PARENT_DIR / "CrossingDataset" / "ZT_CrossingDataset.csv")
    ])
    paths["gv"] = _first_existing([paths.get("gv",""), str(PARENT_DIR / "ZT_GVs_1.4.csv")])
    paths["amat"] = _first_existing([paths.get("amat",""), str(PARENT_DIR / "AMAT_25.csv")])
    write_json(PATHS_PATH, paths)
    return paths

def get_rules():
    return read_json(RULES_PATH, RULES_DEFAULT)

def save_rules(d):
    write_json(RULES_PATH, d)

def julian_csv(prefix):
    mapping = {
        "tassel_survey_data": PARENT_DIR / "tassle_survey_data" / f"tassel_survey_data_{julian_date}.csv",
        "tassles": PARENT_DIR / "Tassles" / f"Tassles_{julian_date}.csv",
        "combinations": PARENT_DIR / "Combinations" / f"Combinations_{julian_date}.csv",
        "possible_crossings": PARENT_DIR / "Crosses for the day" / f"Possible_crossings_{julian_date}.csv",
        "allocated": PARENT_DIR / "Crosses for the day" / f"allocated_{julian_date}.csv",
    }
    return mapping[prefix]

def load_groups():
    if GROUPS_PATH.exists():
        try:
            return json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return GROUPS_DEFAULT.copy()

def save_groups(groups):
    write_json(GROUPS_PATH, groups)

def build_key_maps(pp_path: Path):
    """Map between NUMVAR, AVARIETY, STDVARIETY using Photoperiod_Pos_2025."""
    maps = {
        "AV_to_STD": {},
        "AV_to_NUM": {},
        "STD_to_NUM": {},
        "NUM_to_STD": {},
        "NUM_to_AV": {},
    }
    if not pp_path or not pp_path.exists():
        return maps
    df = pd.read_csv(pp_path, dtype=str).fillna("")
    cols = {c.upper().strip(): c for c in df.columns}
    a = cols.get("AVARIETY"); s = cols.get("STDVARIETY"); n = cols.get("NUMVAR")
    if not (a and s and n):
        return maps
    for av, sd, num in zip(df[a].astype(str), df[s].astype(str), df[n].astype(str)):
        av = av.strip(); sd = sd.strip(); num = num.strip()
        if not av and not sd and not num:
            continue
        if av and sd: maps["AV_to_STD"][av] = sd
        if av and num: maps["AV_to_NUM"][av] = num
        if sd and num: maps["STD_to_NUM"][sd] = num
        if num and sd: maps["NUM_to_STD"][num] = sd
        if num and av: maps["NUM_to_AV"][num] = av
    return maps

def safe_upper_strip(s):
    return str(s or "").strip().upper()

# -------------------- Tassel Survey Tab --------------------
class TasselSurveyTab(QWidget):
    def __init__(self, switch_to_matrix_callback=None, parent=None):
        super().__init__(parent)
        self.switch_to_matrix_callback = switch_to_matrix_callback
        self.setFont(APP_FONT)
        self.setStyleSheet(f"""
            QWidget {{ background: {BG}; }}
            QLabel {{ color: {GREEN}; }}
            QPushButton {{
                background: {BTN}; color: white; border-radius: 6px; padding: 8px 14px;
            }}
            QPushButton:hover {{ background: #188f62; }}

            /* --- Make only the background change when selected; keep text visible --- */
            QToolButton {{
                background: #e0ebe8;
                color: #0f2a22;                  /* keep dark text by default */
                border: 1px solid #015c3a;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 15px;
                min-width: 40px;
                min-height: 36px;
            }}
            QToolButton:hover {{
                background: #cde5d9;
            }}
            QToolButton:checked {{
                background: #01915A;             /* turns green when selected */
                color: #0f2a22;                  /* keep dark text so it never "disappears" */
                border: 2px solid #015c3a;
            }}
            /* Optional: keep same look even while hovering in checked state */
            QToolButton:checked:hover {{
                background: #01915A;
                color: #0f2a22;
            }}
        """)


        ensure_dirs()
        self.paths = get_paths()

        root = QVBoxLayout(self)

        title = QLabel("Tassel Survey")
        title.setFont(TITLE_FONT); title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("margin: 4px 0 10px 0;")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        def make_row():
            row = QHBoxLayout(); row.setSpacing(2); row.setContentsMargins(0,0,0,0); return row

        def make_btn(text):
            b = QtWidgets.QToolButton()
            b.setText(str(text))
            b.setCheckable(True)
            b.setAutoRaise(False)                 # important on Windows so checked state paints
            b.setMinimumSize(40, 36)
            b.setStyleSheet("""
                QToolButton {
                    background: #e0ebe8;
                    color: #0f2a22;
                    border: 1px solid #015c3a;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-weight: bold;
                    font-size: 15px;
                }
                QToolButton:hover {
                    background: #cde5d9;
                }
                QToolButton:checked {
                    background: #01915A;        /* bright green when selected */
                    color: white;               /* keep text readable */
                    border: 2px solid #015c3a;
                }
                QToolButton:checked:hover {
                    background: #01915A;
                    color: white;
                }
                QToolButton:pressed {
                    padding-top: 9px;           /* tiny press feedback */
                    padding-bottom: 7px;
                }
            """)
            return b


        # Bay
        lab = QLabel("Bay (1-6):"); lab.setStyleSheet("font-weight:600;")
        grid.addWidget(lab, 0, 0, Qt.AlignLeft)
        self.bay_group = QButtonGroup(self); self.bay_group.setExclusive(True)
        row = make_row()
        for i in range(1,7):
            b = make_btn(i)
            if i==1: b.setChecked(True)
            self.bay_group.addButton(b,i); row.addWidget(b)
        w=QWidget(); w.setLayout(row); grid.addWidget(w,0,1)

        # Cart
        lab = QLabel("Cart (A,B,C):"); lab.setStyleSheet("font-weight:600;")
        grid.addWidget(lab, 1, 0, Qt.AlignLeft)
        self.cart_group = QButtonGroup(self); self.cart_group.setExclusive(True)
        row = make_row()
        for j,labtxt in enumerate(["A","B","C"]):
            b = make_btn(labtxt)
            if j==0: b.setChecked(True)
            self.cart_group.addButton(b,j); row.addWidget(b)
        w=QWidget(); w.setLayout(row); grid.addWidget(w,1,1)

        # Bucket (CAN)
        lab = QLabel("Bucket (1-18):"); lab.setStyleSheet("font-weight:600;")
        grid.addWidget(lab, 2, 0, Qt.AlignLeft)
        self.bucket_group = QButtonGroup(self); self.bucket_group.setExclusive(True)
        row = make_row()
        for k in range(1,19):
            b = make_btn(k)
            if k==1: b.setChecked(True)
            self.bucket_group.addButton(b,k); row.addWidget(b)
        w=QWidget(); w.setLayout(row); grid.addWidget(w,2,1)

        # #Tas
        lab = QLabel("#Tas:"); lab.setStyleSheet("font-weight:600;")
        grid.addWidget(lab, 3, 0, Qt.AlignLeft)
        self.tas_group = QButtonGroup(self); self.tas_group.setExclusive(True)
        row = make_row()
        for n in range(1,11):
            b = make_btn(n)
            if n==1: b.setChecked(True)
            self.tas_group.addButton(b,n); row.addWidget(b)
        w=QWidget(); w.setLayout(row); grid.addWidget(w,3,1)

        # Pollen
        lab = QLabel("Pollen Rating:"); lab.setStyleSheet("font-weight:600;")
        grid.addWidget(lab, 4, 0, Qt.AlignLeft)
        self.pollen_group = QButtonGroup(self); self.pollen_group.setExclusive(True)
        row = make_row()
        for n in range(1,11):
            b = make_btn(n)
            if n==1: b.setChecked(True)
            self.pollen_group.addButton(b,n); row.addWidget(b)
        w=QWidget(); w.setLayout(row); grid.addWidget(w,4,1)

        grid_card = QWidget(); grid_card.setLayout(grid)
        grid_card.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:12px;")
        root.addWidget(grid_card)

        # Buttons
        btns = QHBoxLayout()
        self.btn_submit = QPushButton("Submit")
        self.btn_generate = QPushButton("Determine Crosses for the Day")
        self.btn_match = QPushButton("Match Crossings")
        self.btn_open_matrix = QPushButton("Open Crosses for the Day")
        self.btn_open_matrix.clicked.connect(self.open_matrix_tab)
        for b in [self.btn_submit, self.btn_generate, self.btn_match, self.btn_open_matrix]:
            btns.addWidget(b)
        root.addLayout(btns)

        self.preview = QLabel("")
        self.preview.setStyleSheet("color:#0f7f5a; font-size:16px; padding:6px 4px;")
        root.addWidget(self.preview)

        self.status = QLabel("")
        root.addWidget(self.status)

        # Badges for today's entries by sex
        badges = QHBoxLayout()
        self.badge_female = QLabel("♀ 0")
        self.badge_male = QLabel("♂ 0")
        self.badge_female.setStyleSheet("background:#ffe6f2; color:#b30059; border:1px solid #b30059; border-radius:8px; padding:4px 8px; font-weight:bold;")
        self.badge_male.setStyleSheet("background:#e6f0ff; color:#003d99; border:1px solid #003d99; border-radius:8px; padding:4px 8px; font-weight:bold;")
        badges.addWidget(self.badge_female); badges.addWidget(self.badge_male); badges.addStretch(1)
        root.addLayout(badges)

        # signals
        self.bay_group.buttonClicked.connect(self.update_preview)
        self.cart_group.buttonClicked.connect(self.update_preview)
        self.bucket_group.buttonClicked.connect(self.update_preview)
        self.tas_group.buttonClicked.connect(self.update_preview)
        self.pollen_group.buttonClicked.connect(self.update_preview)
        self.btn_submit.clicked.connect(self.submit_entry)
        self.btn_generate.clicked.connect(self.generate_combos)
        self.btn_match.clicked.connect(self.match_crossings)

        self.update_preview()
        self._refresh_entry_counts()

    def open_matrix_tab(self):
        if callable(self.switch_to_matrix_callback):
            self.switch_to_matrix_callback()

    def _refresh_entry_counts(self):
        total = male = female = 0
        try:
            in_file = julian_csv("tassel_survey_data")
            if in_file.exists():
                with open(in_file, newline="", encoding="utf-8") as f:
                    r = csv.DictReader(f)
                    for row in r:
                        total += 1
                        sx = (row.get("Sex","") or "").lower()
                        if sx == "male": male += 1
                        elif sx == "female": female += 1
        except Exception:
            pass
        self.badge_male.setText(f"♂ {male}")
        self.badge_female.setText(f"♀ {female}")

    def _current(self):
        bay = self.bay_group.checkedButton().text()
        cart = self.cart_group.checkedButton().text()
        bucket = self.bucket_group.checkedButton().text()
        tas = int(self.tas_group.checkedId())
        pollen = int(self.pollen_group.checkedId())
        return bay, cart, bucket, tas, pollen

    def lookup_variety(self, bay, cart, can):
        pp = Path(get_paths()["photoperiod"])
        if not pp or not pp.exists():
            return ("No file","No file")
        with open(pp, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if str(row.get("BAY")).strip()==str(bay) and str(row.get("CART")).strip()==str(cart) and str(row.get("CAN")).strip()==str(can):
                    av=row.get("AVARIETY") or row.get("avariety") or ""
                    std=row.get("STDVARIETY") or av
                    return str(av).strip(), str(std).strip()
        return ("No match","No match")

    @staticmethod
    def pollen_to_sex(p):
        if 1<=p<=4: return "male"
        if 5<=p<=10: return "female"
        return "unknown"

    def update_preview(self):
        bay, cart, can, tas, pollen = self._current()
        av,std=self.lookup_variety(bay,cart,can); sex = self.pollen_to_sex(pollen)
        self.preview.setText(f"Variety: {av}  |  STDVariety: {std}  |  Bay {bay} Cart {cart} Can {can}  |  #Tas {tas}  |  Pollen {pollen} ({sex})")

    def submit_entry(self):
        ensure_dirs()
        bay, cart, can, tas, pollen = self._current()
        av,std=self.lookup_variety(bay,cart,can); sex = self.pollen_to_sex(pollen)
        out=julian_csv("tassel_survey_data")
        is_new=not out.exists()
        with open(out,"a",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            if is_new: w.writerow(["AVARIETY","STDVARIETY","Can","Cart","Bay","#Tas","Pollen Rating","Sex"])
            w.writerow([av,std,can,cart,bay,tas,pollen,sex])
        self.status.setText(f"Saved {av}/{std} • Bay {bay} {cart} Can {can} • #Tas {tas} • Pollen {pollen} ({sex})")
        self._refresh_entry_counts()
        self.update_preview()

    def generate_combos(self):
        ensure_dirs()
        in_file = julian_csv("tassel_survey_data")
        if not in_file.exists():
            QMessageBox.warning(self,"Missing data","No tassel survey CSV for today yet.")
            return

        data = list(csv.DictReader(open(in_file, newline="", encoding="utf-8")))
        male_avar, female_avar = defaultdict(int), defaultdict(int)

        kmap = build_key_maps(Path(get_paths()["photoperiod"]))
        av_to_std = kmap["AV_to_STD"]; av_to_num = kmap["AV_to_NUM"]

        for row in data:
            avar = (row.get("AVARIETY", "") or "").strip()
            sex = (row.get("Sex", "") or "").lower()
            try:
                tas = int(row.get("#Tas", "0"))
            except Exception:
                tas = 0

            if sex == "female":
                female_avar[avar] += tas
            elif sex == "male":
                male_avar[avar] += tas

        combos = []
        for f_av in female_avar.keys():
            for m_av in male_avar.keys():
                f_std = av_to_std.get(f_av, f_av)
                m_std = av_to_std.get(m_av, m_av)
                f_num = av_to_num.get(f_av, f_av)
                m_num = av_to_num.get(m_av, m_av)
                combos.append((f_av, m_av, f_std, m_std, f_num, m_num))

        df = pd.DataFrame(combos, columns=["FEMALE_AVAR", "MALE_AVAR", "FEMALE_STD", "MALE_STD", "FEMALE_NUMVAR", "MALE_NUMVAR"]).drop_duplicates()
        df.to_csv(julian_csv("combinations"), index=False)

        # Totals by STD
        female_std = defaultdict(int); male_std = defaultdict(int)
        for av, cnt in female_avar.items():
            female_std[av_to_std.get(av, av)] += cnt
        for av, cnt in male_avar.items():
            male_std[av_to_std.get(av, av)] += cnt
        all_std = set(list(male_std.keys()) + list(female_std.keys()))
        tassles_df = pd.DataFrame({
            "STDVARIETY": list(all_std),
            "MALE TASSLES": [male_std.get(v, 0) for v in all_std],
            "FEMALE TASSLES": [female_std.get(v, 0) for v in all_std],
        })
        tassles_df.to_csv(julian_csv("tassles"), index=False)
        self.status.setText("Generated combinations and tassel totals.")

    def match_crossings(self):
        ensure_dirs()
        combos_path = julian_csv("combinations")
        if not combos_path.exists():
            QMessageBox.warning(self,"Missing combos","Generate combinations first.")
            return

        combos = pd.read_csv(combos_path, dtype=str).fillna("")
        combos.columns = [safe_upper_strip(c) for c in combos.columns]
        for c in ["FEMALE_AVAR","MALE_AVAR","FEMALE_STD","MALE_STD","FEMALE_NUMVAR","MALE_NUMVAR"]:
            if c not in combos.columns: combos[c] = ""
            combos[c] = combos[c].astype(str).str.strip()
        out_df = combos.copy()

        # GV traits by NUMVAR (GV.VARIETY)
        gv_attached = False
        gv_path = Path(get_paths()["gv"])
        if gv_path.exists():
            try:
                gv = pd.read_csv(gv_path, dtype=str).fillna("")
                gv.columns = [safe_upper_strip(c) for c in gv.columns]
                if "VARIETY" in gv.columns:
                    gf = gv.rename(columns={"VARIETY": "JOIN_KEY"}).copy()
                    out_df = out_df.merge(gf, left_on="FEMALE_NUMVAR", right_on="JOIN_KEY", how="left")
                    f_cols = [c for c in gf.columns if c != "JOIN_KEY"]
                    out_df.rename(columns={c: f"FEMALE_{c}" for c in f_cols}, inplace=True)
                    out_df.drop(columns=["JOIN_KEY"], inplace=True, errors="ignore")

                    gm = gv.rename(columns={"VARIETY": "JOIN_KEY"}).copy()
                    out_df = out_df.merge(gm, left_on="MALE_NUMVAR", right_on="JOIN_KEY", how="left")
                    m_cols = [c for c in gm.columns if c != "JOIN_KEY"]
                    out_df.rename(columns={c: f"MALE_{c}" for c in m_cols}, inplace=True)
                    out_df.drop(columns=["JOIN_KEY"], inplace=True, errors="ignore")
                    gv_attached = True
            except Exception:
                pass

        # Per-parent CrossingDataset traits (female excludes ^M; male excludes ^F)
        cd_attached = False
        cd_path = Path(get_paths()["crossingdataset"])
        if cd_path.exists():
            try:
                cdf = pd.read_csv(cd_path, dtype=str).fillna("")
                cdf.columns = [safe_upper_strip(c) for c in cdf.columns]
                has_f = "FVARIETY" in cdf.columns
                has_m = "MVARIETY" in cdf.columns

                if has_f:
                    fem_cols = [c for c in cdf.columns if not c.startswith("M")]
                    fem_tbl = cdf[fem_cols].copy().groupby("FVARIETY", as_index=False).first()
                    rename_f = {c: (f"FEMALE_CD_{c}" if c != "FVARIETY" else c) for c in fem_tbl.columns}
                    fem_tbl.rename(columns=rename_f, inplace=True)
                    out_df = out_df.merge(fem_tbl, left_on="FEMALE_NUMVAR", right_on="FVARIETY", how="left")

                if has_m:
                    mal_cols = [c for c in cdf.columns if not c.startswith("F")]
                    mal_tbl = cdf[mal_cols].copy().groupby("MVARIETY", as_index=False).first()
                    rename_m = {c: (f"MALE_CD_{c}" if c != "MVARIETY" else c) for c in mal_tbl.columns}
                    mal_tbl.rename(columns=rename_m, inplace=True)
                    out_df = out_df.merge(mal_tbl, left_on="MALE_NUMVAR", right_on="MVARIETY", how="left")

                cd_attached = has_f or has_m
            except Exception:
                pass

        # % of GV baseline 2001299
        if gv_attached:
            try:
                gv_raw = pd.read_csv(gv_path, dtype=str).fillna("")
                gv_raw.columns = [safe_upper_strip(c) for c in gv_raw.columns]
                base_rows = gv_raw[gv_raw["VARIETY"].astype(str).str.strip() == "2001299"]
                if not base_rows.empty:
                    base = base_rows.iloc[0]
                    trait_cols = [c for c in gv_raw.columns if c != "VARIETY"]
                    for c in trait_cols:
                        b = pd.to_numeric(pd.Series([base.get(c)]*len(out_df)), errors="coerce")
                        fv = pd.to_numeric(out_df.get(f"FEMALE_{c}", pd.Series([], dtype=float)), errors="coerce")
                        mv = pd.to_numeric(out_df.get(f"MALE_{c}", pd.Series([], dtype=float)), errors="coerce")
                        out_df[f"FEMALE_{c}_PCT_2001299"] = (fv / b * 100.0).round(3)
                        out_df[f"MALE_{c}_PCT_2001299"]   = (mv / b * 100.0).round(3)
            except Exception:
                pass

        # Kinship via STD intersection
        kin_attached = False
        amat_path = Path(get_paths()["amat"])
        if amat_path.exists():
            try:
                amx = pd.read_csv(amat_path, index_col=0, dtype=str)
                amx.index = amx.index.astype(str).str.strip()
                amx.columns = amx.columns.astype(str).str.strip()
                vals = []
                for _, r in out_df.iterrows():
                    fstd = str(r.get("FEMALE_STD","")).strip()
                    mstd = str(r.get("MALE_STD","")).strip()
                    v = ""
                    if fstd in amx.index and mstd in amx.columns:
                        v = amx.loc[fstd, mstd]
                    elif mstd in amx.index and fstd in amx.columns:
                        v = amx.loc[mstd, fstd]
                    vals.append(v)
                out_df["KINSHIP"] = vals
                kin_attached = True
            except Exception:
                pass

        out_path = julian_csv("possible_crossings")
        out_df.to_csv(out_path, index=False, encoding="utf-8")
        self.status.setText(
            f"Saved {len(out_df)} rows → {out_path.name} | GV:{'Y' if gv_attached else 'N'} "
            f"| Per-parent CD:{'Y' if cd_attached else 'N'} | Kinship:{'Y' if kin_attached else 'N'}"
        )
        self.open_matrix_tab()

# -------------------- Group Config Dialog --------------------
class GroupConfigDialog(QDialog):
    def __init__(self, headers, groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Column Groups")
        self.resize(900, 620)
        self.headers = headers
        self.groups = groups
        layout = QVBoxLayout(self)

        hl = QLabel("Select columns and assign them to groups (for quick views).")
        hl.setStyleSheet("font-weight:600;")
        layout.addWidget(hl)

        mid = QHBoxLayout()
        self.list = QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        for idx, name in enumerate(self.headers):
            it = QListWidgetItem(f"{idx}: {name}")
            it.setData(Qt.UserRole, idx)
            self.list.addItem(it)
        self.list.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER};")
        mid.addWidget(self.list, 2)

        right = QVBoxLayout()
        self.group_combo = QComboBox()
        self.group_combo.addItems(list(self.groups.keys()))
        right.addWidget(QLabel("Assign selected to group:"))
        right.addWidget(self.group_combo)
        self.assign_btn = QPushButton("Assign →")
        right.addWidget(self.assign_btn)
        self.clear_btn = QPushButton("Remove selected from current group")
        right.addWidget(self.clear_btn)
        self.mapping = QListWidget()
        self.mapping.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER};")
        right.addWidget(QLabel("Current mapping:"))
        right.addWidget(self.mapping, 1)
        mid.addLayout(right, 3)

        layout.addLayout(mid)
        bot = QHBoxLayout()
        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        bot.addStretch(1); bot.addWidget(save); bot.addWidget(cancel)
        layout.addLayout(bot)

        self.assign_btn.clicked.connect(self.assign_selected)
        self.clear_btn.clicked.connect(self.remove_selected_from_group)
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self._refresh()

    def _refresh(self):
        self.mapping.clear()
        for g, cols in self.groups.items():
            self.mapping.addItem(f"{g}: [{', '.join(str(i) for i in sorted(set(cols)))}]")

    def assign_selected(self):
        grp = self.group_combo.currentText()
        idxs = [it.data(Qt.UserRole) for it in self.list.selectedItems()]
        self.groups.setdefault(grp, [])
        self.groups[grp].extend(idxs)
        self._refresh()

    def remove_selected_from_group(self):
        grp = self.group_combo.currentText()
        idxs = [it.data(Qt.UserRole) for it in self.list.selectedItems()]
        if grp in self.groups:
            self.groups[grp] = [i for i in self.groups[grp] if i not in idxs]
        self._refresh()

    def get_groups(self):
        return self.groups

# -------------------- Crosses for the Day (MatrixTab) --------------------
class MatrixTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(APP_FONT)
        self.setStyleSheet(f"""
            QWidget {{ background: {BG}; }}
            QLabel {{ color: {GREEN}; }}
            QPushButton {{
                background: {BTN}; color: white; border-radius: 10px; padding: 10px 16px;
            }}
            QPushButton:hover {{ background: {BTN_HOVER}; }}
            QHeaderView::section {{ background: {HEADER}; padding: 6px; border: none; }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget {{ background: {CARD}; border: 1px solid {BORDER}; gridline-color:{BORDER}; }}
        """)
        self.group_cols = load_groups()  # { group_name: [col_idx_from_csv] }
        self.headers_all = []            # displayed labels
        self.header_keys = []            # original keys incl. "Export"
        self.display_names = {}          # header -> display label
        self.tassel_counts = {}
        self._suspend_selection_updates = False

        lay = QVBoxLayout(self)

        t = QLabel("Crosses for the Day")
        t.setFont(TITLE_FONT)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("margin: 4px 0 10px 0;")
        lay.addWidget(t)

        # Group button bar (toggleable)
        self.group_btns_container = QWidget()
        self.group_btns_layout = QHBoxLayout(self.group_btns_container)
        self.group_btns_layout.setContentsMargins(0,0,0,0)
        self.group_btns_layout.setSpacing(8)

        self.btn_show_all = QPushButton("Show All")
        self.btn_show_none = QPushButton("Hide All (Core Only)")
        self.btn_show_all.clicked.connect(self.show_all_columns)
        self.btn_show_none.clicked.connect(self.hide_all_columns)

        self.group_btns_layout.addWidget(self.btn_show_all)
        self.group_btns_layout.addWidget(self.btn_show_none)
        self.group_btns_layout.addStretch(1)
        lay.addWidget(self.group_btns_container)

        # Availability panel
        avail_box = QHBoxLayout()
        avail_label = QLabel("Availability (live, rule-adjusted):")
        avail_label.setStyleSheet("font-weight:bold; padding: 4px 0;")
        avail_box.addWidget(avail_label)

        self.avail_table = QTableWidget()
        self.avail_table.setColumnCount(3)
        self.avail_table.setHorizontalHeaderLabels(["STDVARIETY", "Sex", "Flowers remaining"])
        self.avail_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.avail_table.setMaximumHeight(240)
        self.avail_table.horizontalHeader().setStretchLastSection(True)
        self.avail_table.verticalHeader().setDefaultSectionSize(28)
        avail_box.addWidget(self.avail_table)
        lay.addLayout(avail_box)

        # Table + controls
        self.table = QTableWidget()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(28)
        lay.addWidget(self.table)

        ctrl = QHBoxLayout()
        self.btn_reload = QPushButton("Reload Today's Crosses")
        self.btn_export = QPushButton("Export Selected Rows (Guarded)")
        for b in [self.btn_reload,self.btn_export]:
            ctrl.addWidget(b)
        ctrl.addStretch(1)
        lay.addLayout(ctrl)

        self.btn_reload.clicked.connect(self.load_all)
        self.btn_export.clicked.connect(self.export_selected_guarded)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_table)
        self.table.itemChanged.connect(self._on_table_item_changed)

        # Watch groups file for live updates to buttons
        try:
            self._watcher = QFileSystemWatcher(self)
            self._watcher.addPath(str(GROUPS_PATH))
            self._watcher.fileChanged.connect(self._on_groups_file_changed)
        except Exception:
            self._watcher = None

        self._active_group_btns = {}  # name -> button
        self._active_group = None     # currently applied group name or None

        self.refresh_group_buttons()
        self.load_all()

    # ---- header/display-name helpers ----
    def _load_display_names(self):
        try:
            self.display_names = get_rules().get("display_names", {}) or {}
        except Exception:
            self.display_names = {}

    def _col_idx(self, original_key: str, default=None):
        try:
            return self.header_keys.index(original_key)
        except ValueError:
            return default

    # Availability & rules
    def _load_tassel_counts(self):
        self.tassel_counts = {}
        tass = julian_csv("tassles")
        if not tass.exists():
            return
        df = pd.read_csv(tass)
        for _, r in df.iterrows():
            var = str(r.get("STDVARIETY","")).strip()
            try:
                m = int(r.get("MALE TASSLES",0))
                f = int(r.get("FEMALE TASSLES",0))
            except Exception:
                m,f = 0,0
            self.tassel_counts[var] = {"male": m, "female": f}

    def _load_rules_pair(self):
        r = get_rules()
        try:
            fpm = int(r.get("females_per_male", 1))
        except Exception:
            fpm = 1
        try:
            mpf = int(r.get("males_per_female", 1))
        except Exception:
            mpf = 1
        return max(1, fpm), max(1, mpf)

    def _current_checked_rows(self):
        fstd_idx = self._col_idx("FEMALE_STD")
        mstd_idx = self._col_idx("MALE_STD")
        if fstd_idx is None or mstd_idx is None:
            return []
        pairs = []
        for i in range(self.table.rowCount()):
            it = self.table.item(i,0)
            if it and it.checkState()==Qt.Checked:
                fstd = self.table.item(i, fstd_idx).text() if self.table.item(i, fstd_idx) else ""
                mstd = self.table.item(i, mstd_idx).text() if self.table.item(i, mstd_idx) else ""
                pairs.append((fstd.strip(), mstd.strip()))
        return pairs

    def _compute_capacities(self):
        """Compute remaining capacities after allocated + pending (checked) rows."""
        self._load_tassel_counts()
        females_per_male, males_per_female = self._load_rules_pair()

        capacities = {}
        for var, d in self.tassel_counts.items():
            m_tas = int(d.get("male",0))
            f_tas = int(d.get("female",0))
            capacities[var] = {
                "male_cap":   m_tas * females_per_male,
                "female_cap": f_tas * males_per_female
            }

        # subtract already allocated crosses
        alloc_path = julian_csv("allocated")
        if alloc_path.exists():
            try:
                df_a = pd.read_csv(alloc_path)
                for _,r in df_a.iterrows():
                    fstd = str(r.get("FEMALE","")).strip()
                    mstd = str(r.get("MALE","")).strip()
                    if fstd in capacities:
                        capacities[fstd]["female_cap"] = max(0, capacities[fstd]["female_cap"] - 1)
                    if mstd in capacities:
                        capacities[mstd]["male_cap"] = max(0, capacities[mstd]["male_cap"] - 1)
            except Exception:
                pass

        # subtract pending (checked but not exported yet)
        for fstd, mstd in self._current_checked_rows():
            if fstd in capacities:
                capacities[fstd]["female_cap"] = max(0, capacities[fstd]["female_cap"] - 1)
            if mstd in capacities:
                capacities[mstd]["male_cap"] = max(0, capacities[mstd]["male_cap"] - 1)

        return capacities

    def _render_availability(self, capacities):
        """Render availability into simplified table: [STDVARIETY | Male | Flowers remaining]"""
        rows = []
        for var, d in capacities.items():
            rows.append((var, True,  d["male_cap"]))
            rows.append((var, False, d["female_cap"]))
        rows.sort(key=lambda x: (x[0], not x[1]))  # variety, then male first

        self.avail_table.setRowCount(len(rows))
        for i, (var, is_male, rem) in enumerate(rows):
            self.avail_table.setItem(i, 0, QTableWidgetItem(var))
            self.avail_table.setItem(i, 1, QTableWidgetItem("MALE" if is_male else "FEMALE"))
            rem_it = QTableWidgetItem(str(rem))
            if rem <= 0: rem_it.setBackground(QColor("#ffd6d6"))
            self.avail_table.setItem(i, 2, rem_it)
        self.avail_table.resizeColumnsToContents()

    def _apply_row_filtering(self, capacities):
        fstd_idx = self._col_idx("FEMALE_STD")
        mstd_idx = self._col_idx("MALE_STD")
        if fstd_idx is None or mstd_idx is None:
            return
        checked_rows = set(i for i in range(self.table.rowCount()) if self.table.item(i,0) and self.table.item(i,0).checkState()==Qt.Checked)
        for i in range(self.table.rowCount()):
            if i in checked_rows:
                self.table.setRowHidden(i, False)
                continue
            fstd = self.table.item(i, fstd_idx).text() if self.table.item(i, fstd_idx) else ""
            mstd = self.table.item(i, mstd_idx).text() if self.table.item(i, mstd_idx) else ""
            f_ok = capacities.get(fstd,{"female_cap":0}).get("female_cap",0) > 0
            m_ok = capacities.get(mstd,{"male_cap":0}).get("male_cap",0) > 0
            self.table.setRowHidden(i, not (f_ok and m_ok))

    def _live_refresh(self):
        capacities = self._compute_capacities()
        self._render_availability(capacities)
        self._apply_row_filtering(capacities)
        self.apply_highlights()

    # Load & table helpers
    def load_all(self):
        poss = julian_csv("possible_crossings")
        if not poss.exists():
            self.info("Missing Possible_crossings CSV. Use the Tassel Survey tab first.")
            self.table.setRowCount(0); self.table.setColumnCount(0)
            return

        self._load_display_names()
        with open(poss, newline='', encoding='utf-8') as f:
            r = csv.reader(f)
            headers = next(r)
            rows = list(r)

        # Keep the canonical/original keys (include Export first)
        self.header_keys = ["Export"] + headers

        # Use display names for UI only
        shown = ["Export"] + [self.display_names.get(h, h) for h in headers]
        self.headers_all = shown
        self.populate_table_display(headers, shown, rows)

        # Persistent hidden columns by original header names
        try:
            hidden_keys = set(get_rules().get("hidden_columns", []))
            if hidden_keys:
                key_to_idx = {k: i for i, k in enumerate(self.header_keys)}
                for k in hidden_keys:
                    idx = key_to_idx.get(k)
                    if idx is not None:
                        self.table.setColumnHidden(idx, True)
        except Exception:
            pass

        self._live_refresh()

    def populate_table_display(self, original_headers, shown_headers, rows):
        self.table.clear()
        col_count = len(shown_headers)
        self.table.setColumnCount(col_count)
        self.table.setHorizontalHeaderLabels(shown_headers)
        self.table.setRowCount(0)
        for i, row in enumerate(rows):
            self.table.insertRow(i)
            # Export checkbox in col 0
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, chk)
            # remaining columns map 1:1 to CSV headers (offset +1)
            for j, val in enumerate(row, start=1):
                self.table.setItem(i, j, QTableWidgetItem(val))
        self.table.resizeColumnsToContents()

    def sort_table(self, column_index):
        self.table.sortItems(column_index, self.table.horizontalHeader().sortIndicatorOrder())

    def info(self,msg):
        QMessageBox.information(self,"Info",msg)

    # Group button bar
    def refresh_group_buttons(self):
        while self.group_btns_layout.count() > 3:
            item = self.group_btns_layout.takeAt(2)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.group_cols = load_groups()
        self._active_group_btns.clear()
        for name in self.group_cols.keys():
            btn = QtWidgets.QToolButton()
            btn.setText(name)
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.clicked.connect(lambda checked, n=name, b=btn: self._on_group_button_toggled(n, b, checked))
            btn.setStyleSheet(f"QToolButton {{ background:{CARD}; color:#1b1b1b; border:1px solid {BORDER}; padding:8px 12px; border-radius:10px; }}"
                              f"QToolButton:checked {{ background:{BTN}; color:white; }}")
            self.group_btns_layout.insertWidget(self.group_btns_layout.count()-1, btn)
            self._active_group_btns[name] = btn

    def _on_groups_file_changed(self, _path):
        self.refresh_group_buttons()

    def _on_group_button_toggled(self, name, btn, checked):
        if checked:
            for other_name, other_btn in self._active_group_btns.items():
                if other_btn is not btn:
                    other_btn.setChecked(False)
            self._active_group = name
            self.show_only_group(name)
        else:
            self._active_group = None
            self.show_all_columns()

    def core_columns(self):
        want = {"Export", "FEMALE_AVAR", "MALE_AVAR", "FEMALE_STD", "MALE_STD", "KINSHIP"}
        idxs = set()
        for i, key in enumerate(self.header_keys):
            if key in want:
                idxs.add(i)
        return idxs

    def show_only_group(self, group_name: str):
        cols = self.group_cols.get(group_name, [])
        visible = {0}  # always keep Export
        visible |= {c+1 for c in cols if 0 <= c < (self.table.columnCount()-1)}
        visible |= self.core_columns()
        for c in range(self.table.columnCount()):
            self.table.setColumnHidden(c, c not in visible)

    def show_all_columns(self):
        for c in range(self.table.columnCount()):
            self.table.setColumnHidden(c, False)

    def hide_all_columns(self):
        core = self.core_columns() | {0}
        for c in range(self.table.columnCount()):
            self.table.setColumnHidden(c, c not in core)

    # Export guarded (rule-aware)
    def export_selected_guarded(self):
        capacities = self._compute_capacities()
        remaining = dict((k, {"male_cap": v["male_cap"], "female_cap": v["female_cap"]})
                         for k, v in capacities.items())

        selected_rows = [i for i in range(self.table.rowCount())
                         if self.table.item(i,0) and self.table.item(i,0).checkState()==Qt.Checked]
        if not selected_rows:
            QMessageBox.information(self,"No selection","Check the 'Export' box on one or more rows first.")
            return

        # Build header list from original keys (skip "Export")
        headers = self.header_keys[1:]
        fstd_idx = self._col_idx("FEMALE_STD")
        mstd_idx = self._col_idx("MALE_STD")
        if fstd_idx is None or mstd_idx is None:
            QMessageBox.warning(self, "Missing columns", "FEMALE_STD / MALE_STD not found.")
            return

        export_rows, skipped = [], []
        for r in selected_rows:
            female_std = self.table.item(r,fstd_idx).text() if self.table.item(r,fstd_idx) else ""
            male_std   = self.table.item(r,mstd_idx).text() if self.table.item(r,mstd_idx) else ""

            f_ok = remaining.get(female_std,{"female_cap":0}).get("female_cap",0) > 0
            m_ok = remaining.get(male_std,{"male_cap":0}).get("male_cap",0) > 0

            if f_ok and m_ok:
                remaining[female_std]["female_cap"] -= 1
                remaining[male_std]["male_cap"] -= 1
                row_vals=[self.table.item(r,j).text() if self.table.item(r,j) else "" for j in range(1, self.table.columnCount())]
                export_rows.append((r,row_vals,female_std,male_std))
            else:
                reason=[]
                if not f_ok: reason.append(f"female '{female_std}' has 0 remaining")
                if not m_ok: reason.append(f"male '{male_std}' has 0 remaining (rule-adjusted)")
                skipped.append((r,"; ".join(reason)))

        if not export_rows:
            QMessageBox.warning(self,"Insufficient availability","None of the selected rows fit remaining availability.")
            return

        path,_ = QFileDialog.getSaveFileName(self,"Export CSV","","CSV Files (*.csv)")
        if not path:
            return
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            w.writerow(headers)
            for _,row_vals,_,_ in export_rows:
                w.writerow(row_vals)

        alloc_path = julian_csv("allocated")
        df_append = pd.DataFrame([{"FEMALE":f,"MALE":m} for _,_,f,m in export_rows])
        if alloc_path.exists():
            df_out = pd.concat([pd.read_csv(alloc_path), df_append], ignore_index=True)
        else:
            df_out = df_append
        df_out.to_csv(alloc_path, index=False)

        self._suspend_selection_updates = True
        try:
            for r,_,_,_ in export_rows:
                it=self.table.item(r,0)
                if it: it.setCheckState(Qt.Unchecked)
        finally:
            self._suspend_selection_updates = False

        self._live_refresh()

        if skipped:
            msg="\n".join([f"Row {r+1}: {reason}" for r,reason in skipped])
            QMessageBox.information(self,"Export complete (with skips)",f"Exported {len(export_rows)} rows.\nSkipped {len(skipped)} due to availability:\n{msg}")
        else:
            QMessageBox.information(self,"Export complete",f"Exported {len(export_rows)} rows.")

    def _on_table_item_changed(self, item):
        if self._suspend_selection_updates:
            return
        if item and item.column()==0 and item.flags() & Qt.ItemIsUserCheckable:
            self._live_refresh()

    # Highlighting engine
    def _value_matches(self, cell_text: str, op: str, target: str) -> bool:
        t = (cell_text or "").strip()
        v = (target or "").strip()
        def to_float(x):
            try:
                return float(str(x).replace(",",""))
            except Exception:
                return None
        if op in (">",">=","<","<=","==","!="):
            a = to_float(t); b = to_float(v)
            if a is not None and b is not None:
                if op == ">":  return a >  b
                if op == ">=": return a >= b
                if op == "<":  return a <  b
                if op == "<=": return a <= b
                if op == "==": return a == b
                if op == "!=": return a != b
            if op == "==": return t == v
            if op == "!=": return t != v

            return False
        elif op == "contains":
            return v.lower() in t.lower()
        elif op == "not contains":
            return v.lower() not in t.lower()
        return False

    def apply_highlights(self):
        rules = get_rules()
        hrules = rules.get("highlight_rules", [])
        if not hrules:
            return
        headers = { key: i for i, key in enumerate(self.header_keys) }  # original key -> index
        for row in range(self.table.rowCount()):
            for rule in hrules:
                color = rule.get("color", "#FFEB3B")
                logic = (rule.get("logic","AND") or "AND").upper()
                clauses = rule.get("clauses", [])
                results = []
                for c in clauses:
                    colname = c.get("column","")
                    op = c.get("op","")
                    val = c.get("value","")
                    idx = headers.get(colname)
                    if idx is None:
                        results.append(False)
                        continue
                    it = self.table.item(row, idx)
                    txt = it.text() if it else ""
                    results.append(self._value_matches(txt, op, val))
                ok = (all(results) if logic == "AND" else any(results)) if results else False
                if ok:
                    qcol = QColor(color)
                    for col in range(self.table.columnCount()):
                        it = self.table.item(row, col)
                        if it:
                            it.setBackground(qcol)

# -------------------- Settings Tab (scrollable) --------------------
class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(APP_FONT)

        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget(); scroll.setWidget(content)
        v = QVBoxLayout(content)

        head = QLabel("Settings")
        head.setFont(TITLE_FONT); head.setAlignment(Qt.AlignCenter)
        v.addWidget(head)

        card = QWidget(); card_lay = QVBoxLayout(card)
        card.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:12px;")
        v.addWidget(card)

        card_lay.addWidget(QLabel("Variable Groupings (persist across runs)"))
        self.groups = load_groups()

        top = QHBoxLayout()
        self.group_list = QListWidget()
        self.group_list.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER};")
        for g in self.groups.keys():
            self.group_list.addItem(g)
        top.addWidget(self.group_list, 2)

        right = QVBoxLayout()
        self.btn_add = QPushButton("Add Group")
        self.btn_rename = QPushButton("Rename Group")
        self.btn_delete = QPushButton("Delete Group")
        self.btn_open = QPushButton("Open Group Window")
        self.btn_edit = QPushButton("Edit Columns in Group")
        for b in [self.btn_add, self.btn_rename, self.btn_delete, self.btn_open, self.btn_edit]:
            right.addWidget(b)
        right.addSpacing(8)

        # Data Sources
        right.addWidget(QLabel("Data Sources (persisted in paths.json)"))
        self.paths = get_paths()

        # read possible headers (from today's Possible_crossings) once
        def _read_possible_headers():
            poss = julian_csv("possible_crossings")
            if not poss.exists():
                return []
            with open(poss, newline="", encoding="utf-8") as f:
                r = csv.reader(f)
                try:
                    headers = next(r)
                except StopIteration:
                    return []
            return headers

        self._possible_headers = _read_possible_headers()
        self.rules = get_rules()
        self.display_names = self.rules.get("display_names", {}) or {}

        self.pp_edit = QLineEdit(self.paths.get("photoperiod",""))
        self.cd_edit = QLineEdit(self.paths.get("crossingdataset",""))
        self.gv_edit = QLineEdit(self.paths.get("gv",""))
        self.am_edit = QLineEdit(self.paths.get("amat",""))

        def row(label, edit, button_text, key):
            h = QHBoxLayout()
            h.addWidget(QLabel(label))
            h.addWidget(edit)
            b = QPushButton(button_text)
            def pick():
                path, _ = QFileDialog.getOpenFileName(self, f"Select {label}", "", "CSV Files (*.csv);;All Files (*.*)")
                if path:
                    edit.setText(path)
                    self.paths[key] = path
                    write_json(PATHS_PATH, self.paths)
            b.clicked.connect(pick)
            h.addWidget(b)
            return h

        right.addLayout(row("Photoperiod_Pos_2025.csv", self.pp_edit, "Browse...", "photoperiod"))
        right.addLayout(row("ZT_CrossingDataset.csv", self.cd_edit, "Browse...", "crossingdataset"))
        right.addLayout(row("ZT_GVs_1.4.csv", self.gv_edit, "Browse...", "gv"))
        right.addLayout(row("AMAT_25.csv", self.am_edit, "Browse...", "amat"))

        # Crossing Rules
        right.addSpacing(10)
        right.addWidget(QLabel("Crossing Rules"))
        rule_row1 = QHBoxLayout()
        self.rule_fpm = QtWidgets.QSpinBox(); self.rule_fpm.setRange(1, 20)
        self.rule_fpm.setValue(int(self.rules.get("females_per_male", 1)))
        rule_row1.addWidget(QLabel("Females per 1 male tassel:"))
        rule_row1.addWidget(self.rule_fpm)
        right.addLayout(rule_row1)

        rule_row2 = QHBoxLayout()
        self.rule_mpf = QtWidgets.QSpinBox(); self.rule_mpf.setRange(1, 20)
        self.rule_mpf.setValue(int(self.rules.get("males_per_female", 1)))
        rule_row2.addWidget(QLabel("Males per 1 female tassel:"))
        rule_row2.addWidget(self.rule_mpf)
        right.addLayout(rule_row2)

        btn_save_rule = QPushButton("Save Rules")
        def _save_rule():
            self.rules["females_per_male"] = int(self.rule_fpm.value())
            self.rules["males_per_female"] = int(self.rule_mpf.value())
            save_rules(self.rules)
            QMessageBox.information(self, "Saved", "Crossing rules updated.")
        btn_save_rule.clicked.connect(_save_rule)
        right.addWidget(btn_save_rule)

        # Persistent Hidden Columns (multi-select)
        right.addSpacing(10)
        right.addWidget(QLabel("Persistently Hidden Columns"))
        hint = QLabel("Select columns to start hidden (original header names).")
        hint.setStyleSheet("color:#555; font-size:12px;")
        right.addWidget(hint)

        self.hidden_cols_list = QListWidget()
        self.hidden_cols_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.hidden_cols_list.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER};")
        for h in self._possible_headers:
            shown = f"{h} — (Display: {self.display_names.get(h, h)})"
            it = QListWidgetItem(shown)
            it.setData(Qt.UserRole, h)  # store original key
            self.hidden_cols_list.addItem(it)
        # preselect any previously hidden
        for i in range(self.hidden_cols_list.count()):
            it = self.hidden_cols_list.item(i)
            if it.data(Qt.UserRole) in set(self.rules.get("hidden_columns", [])):
                it.setSelected(True)

        right.addWidget(self.hidden_cols_list)
        btn_save_hidden = QPushButton("Save Hidden Columns")
        def _save_hidden():
            names = [self.hidden_cols_list.item(i).data(Qt.UserRole)
                     for i in range(self.hidden_cols_list.count())
                     if self.hidden_cols_list.item(i).isSelected()]
            self.rules["hidden_columns"] = names
            save_rules(self.rules)
            QMessageBox.information(self, "Saved", "Hidden columns updated.")
        btn_save_hidden.clicked.connect(_save_hidden)
        right.addWidget(btn_save_hidden)

        # Conditional Highlighting
        right.addSpacing(10)
        right.addWidget(QLabel("Conditional Highlighting"))
        self.hl_list = QListWidget()
        self.hl_list.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER};")
        for rule in self.rules.get("highlight_rules", []):
            self.hl_list.addItem(rule.get("name","(unnamed rule)"))
        right.addWidget(self.hl_list)

        hl_form = QVBoxLayout()
        hl_row1 = QHBoxLayout()
        self.hl_name = QLineEdit(); self.hl_name.setPlaceholderText("Rule name")
        hl_row1.addWidget(QLabel("Name:")); hl_row1.addWidget(self.hl_name)
        hl_form.addLayout(hl_row1)

        self.clauses = []
        clause_row = QHBoxLayout()

        # Column combobox (original keys, shows display names)
        self.cl_col = QComboBox()
        for h in self._possible_headers:
            label = f"{h} — (Display: {self.display_names.get(h, h)})"
            self.cl_col.addItem(label, h)
        self.cl_op  = QComboBox(); self.cl_op.addItems(["==","!=",">",">=","<","<=","contains","not contains"])
        self.cl_val = QLineEdit(); self.cl_val.setPlaceholderText("Value (e.g., 0.15)")
        btn_add_clause = QPushButton("Add Clause")
        def _add_clause():
            c = self.cl_col.currentData()  # original header key
            o = self.cl_op.currentText().strip()
            v = self.cl_val.text().strip()
            if not c or not o:
                QMessageBox.warning(self, "Missing", "Column and operator are required.")
                return
            self.clauses.append({"column": c, "op": o, "value": v})
            QMessageBox.information(self, "Added", f"Clause: {c} {o} {v}")
            self.cl_val.clear()
        btn_add_clause.clicked.connect(_add_clause)

        clause_row.addWidget(QLabel("Column:")); clause_row.addWidget(self.cl_col)
        clause_row.addWidget(QLabel("Op:")); clause_row.addWidget(self.cl_op)
        clause_row.addWidget(QLabel("Value:")); clause_row.addWidget(self.cl_val)
        clause_row.addWidget(btn_add_clause)
        hl_form.addLayout(clause_row)

        hl_row2 = QHBoxLayout()
        self.hl_logic = QComboBox(); self.hl_logic.addItems(["AND","OR"])
        hl_row2.addWidget(QLabel("Combine clauses with:"))
        hl_row2.addWidget(self.hl_logic)

        self.hl_color = QComboBox()
        for label, color in PALETTE:
            self.hl_color.addItem(label, color)
        hl_row2.addWidget(QLabel("Color:"))
        hl_row2.addWidget(self.hl_color)
        hl_form.addLayout(hl_row2)

        btn_save_rule = QPushButton("Save Highlight Rule")
        def _save_hl_rule():
            name = self.hl_name.text().strip() or f"Rule {len(self.rules.get('highlight_rules',[]))+1}"
            logic = self.hl_logic.currentText().strip()
            if not self.clauses:
                QMessageBox.warning(self, "Missing", "Add at least one clause.")
                return
            rule = {"name": name, "logic": logic, "clauses": list(self.clauses), "color": self.hl_color.currentData()}
            rules = get_rules()
            arr = rules.get("highlight_rules", [])
            arr.append(rule)
            rules["highlight_rules"] = arr
            save_rules(rules)
            self.rules = rules
            self.hl_list.addItem(name)
            self.clauses.clear(); self.hl_name.clear()
            QMessageBox.information(self, "Saved", "Highlight rule saved.")
        btn_save_rule.clicked.connect(_save_hl_rule)
        hl_form.addWidget(btn_save_rule)

        btn_delete_rule = QPushButton("Delete Selected Rule")
        def _del_rule():
            row = self.hl_list.currentRow()
            if row < 0: return
            rules = get_rules()
            arr = rules.get("highlight_rules", [])
            if 0 <= row < len(arr):
                arr.pop(row)
                rules["highlight_rules"] = arr
                save_rules(rules)
                self.rules = rules
                self.hl_list.takeItem(row)
        btn_delete_rule.clicked.connect(_del_rule)
        hl_form.addWidget(btn_delete_rule)

        right.addLayout(hl_form)

        # Display Names editor
        right.addSpacing(12)
        right.addWidget(QLabel("Column Display Names (used in Crosses for the Day)"))
        dn_hint = QLabel("Leave blank to use original header. Saved to rules.json → display_names.")
        dn_hint.setStyleSheet("color:#555; font-size:12px;")
        right.addWidget(dn_hint)

        self.display_name_edits = {}

        dn_card = QWidget()
        dn_grid = QGridLayout(dn_card)
        dn_grid.setColumnStretch(1, 1)
        right.addWidget(dn_card)

        def _populate_display_names():
            poss_headers = self._possible_headers or []
            for row, h in enumerate(poss_headers):
                lab = QLabel(h)
                edit = QLineEdit(self.display_names.get(h, ""))
                self.display_name_edits[h] = edit
                dn_grid.addWidget(lab, row, 0)
                dn_grid.addWidget(edit, row, 1)

        _populate_display_names()

        btn_save_display_names = QPushButton("Save Display Names")
        def _save_display_names():
            mapping = {}
            for h, edit in self.display_name_edits.items():
                val = edit.text().strip()
                if val and val != h:
                    mapping[h] = val
            rules = get_rules()
            prior = rules.get("display_names", {}) or {}
            # remove cleared ones
            for k in list(prior.keys()):
                if k in self.display_name_edits and not self.display_name_edits[k].text().strip():
                    prior.pop(k, None)
            prior.update(mapping)
            rules["display_names"] = prior
            save_rules(rules)
            self.rules = rules
            self.display_names = prior
            QMessageBox.information(self, "Saved", "Display names updated. Reload Crosses tab to see them.")
        btn_save_display_names.clicked.connect(_save_display_names)
        right.addWidget(btn_save_display_names)

        right.addStretch(1)

        top.addLayout(right, 3)
        card_lay.addLayout(top)

        # wire buttons
        self.btn_add.clicked.connect(self.add_group)
        self.btn_rename.clicked.connect(self.rename_group)
        self.btn_delete.clicked.connect(self.delete_group)
        self.btn_open.clicked.connect(self.open_group_window)
        self.btn_edit.clicked.connect(self.edit_group_columns)

    def refresh(self):
        self.group_list.clear()
        for g in self.groups.keys():
            self.group_list.addItem(g)

    def add_group(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Group", "Group name:")
        if not ok or not name:
            return
        if name in self.groups:
            QMessageBox.warning(self, "Exists", "A group with that name already exists.")
            return
        self.groups[name] = []
        save_groups(self.groups)
        self.refresh()

    def rename_group(self):
        it = self.group_list.currentItem()
        if not it:
            return
        old = it.text()
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename Group", "New name:", text=old)
        if not ok or not new:
            return
        if new in self.groups and new != old:
            QMessageBox.warning(self, "Exists", "A group with that name already exists.")
            return
        self.groups[new] = self.groups.pop(old)
        save_groups(self.groups)
        self.refresh()

    def delete_group(self):
        it = self.group_list.currentItem()
        if not it:
            return
        name = it.text()
        if QMessageBox.question(self, "Confirm", f"Delete group '{name}'?", QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            self.groups.pop(name, None)
            save_groups(self.groups)
            self.refresh()

    def open_group_window(self):
        it = self.group_list.currentItem()
        if not it:
            return
        name = it.text()
        cols = self.groups.get(name, [])
        if not cols:
            QMessageBox.information(self, "Empty", "No columns assigned yet. Use 'Edit Columns in Group'.")
            return
        w = GroupWindow(name, cols, self)
        w.show()

    def edit_group_columns(self):
        poss = julian_csv("possible_crossings")
        if not poss.exists():
            QMessageBox.information(self, "No data", "No Possible_crossings file yet.")
            return
        with open(poss, newline="", encoding="utf-8") as f:
            r = csv.reader(f); headers = next(r)
        it = self.group_list.currentItem()
        if not it:
            return
        name = it.text()
        cols = self.groups.get(name, [])
        dlg = GroupConfigDialog(headers, {name: cols}, self)
        if dlg.exec_()==QDialog.Accepted:
            out = dlg.get_groups()
            self.groups[name] = out.get(name, [])
            save_groups(self.groups)
            self.refresh()

# -------------------- Group quick view window --------------------
class GroupWindow(QWidget):
    def __init__(self, group_name, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"View: {group_name}")
        v = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER};")
        v.addWidget(self.table)
        self.group_name = group_name
        self.columns = columns
        self.reload()

    def reload(self):
        poss = julian_csv("possible_crossings")
        self.table.clear()
        if not poss.exists():
            self.table.setRowCount(0); self.table.setColumnCount(0)
            return
        with open(poss, newline="", encoding="utf-8") as f:
            r = csv.reader(f); headers = next(r); rows = list(r)
        wanted = [c for c in self.columns if 0 <= c < len(headers)]
        sub_headers = [headers[i] for i in wanted]
        self.table.setColumnCount(len(sub_headers))
        self.table.setHorizontalHeaderLabels(sub_headers)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, col_idx in enumerate(wanted):
                val = row[col_idx] if col_idx < len(row) else ""
                self.table.setItem(i, j, QtWidgets.QTableWidgetItem(val))
        self.table.resizeColumnsToContents()

# -------------------- Main Window --------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SucroX")
        self.setFont(APP_FONT)
        self.setWindowIcon(QIcon())
        w=QWidget()
        self.setCentralWidget(w)
        lay=QVBoxLayout(w)
        header = QLabel("SucroX")
        header.setFont(QFont("Open Sans", 40, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        lay.addWidget(header)
        sub = QLabel(f"Julian Date: {julian_date}")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color:{GREEN};")
        lay.addWidget(sub)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { padding:10px 16px; }")
        lay.addWidget(self.tabs)
        self.matrix_tab = MatrixTab()
        self.tassel_tab = TasselSurveyTab(switch_to_matrix_callback=self.goto_matrix)
        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.tassel_tab,"Tassel Survey")
        self.tabs.addTab(self.matrix_tab,"Crosses for the Day")
        self.tabs.addTab(self.settings_tab,"Settings")
        self.resize(1380,900)

    def goto_matrix(self):
        self.tabs.setCurrentWidget(self.matrix_tab)

# -------------------- main --------------------
def main():
    if '--check' in sys.argv:
        paths = get_paths()
        required = [
            ('Photoperiod_Pos_2025.csv', paths.get('photoperiod','')),
            ('AMAT_25.csv', paths.get('amat','')),
            ('ZT_CrossingDataset.csv', paths.get('crossingdataset','')),
            ('ZT_GVs_1.4.csv', paths.get('gv','')),
        ]
        missing = [name for name, p in required if not p or not Path(p).exists()]
        if missing:
            print('Missing:', ', '.join(missing)); sys.exit(1)
        print('All good!'); sys.exit(0)
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        print('No DISPLAY detected. Run this app on a machine with a GUI.'); sys.exit(0)
    ensure_dirs()
    app = QApplication(sys.argv)
    app.setFont(APP_FONT)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
