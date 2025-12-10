# rpw_processing.py
import pandas as pd
import re
from typing import Dict, Any


def extract_metadata_from_filename(filename: str) -> Dict[str, Any]:
    """Parse group, timepoint, adsorbent, sample from the file name."""
    name = filename.lower()

    # timepoint like 24h, 48 h, 72h, etc.
    m_time = re.search(r"(\d+)\s*h", name)
    timepoint = f"{m_time.group(1)}h" if m_time else None

    # adsorbent
    if "char" in name:
        adsorbent = "char"
    elif "dvb" in name:
        adsorbent = "dvb"
    else:
        adsorbent = None

    # sample number (e.g. -char-1, -dvb-3)
    m_sample = re.search(r"-(char|dvb)-(\d+)", name)
    sample = int(m_sample.group(2)) if m_sample else None

    # group
    if "healthy" in name and "infested" not in name:
        group = "healthy+masa" if "masa" in name else "healthy"
    elif "infested" in name:
        group = "infested+masa" if "masa" in name else "infested"
    else:
        group = None

    return {
        "group": group,
        "timepoint": timepoint,
        "adsorbent": adsorbent,
        "sample": sample,
        "source_file": filename,
    }


# NEW: helper to extract the LibRes sheet from a multi-sheet Excel file
def load_libres_sheet(file_obj, filename: str) -> pd.DataFrame:
    """
    Load the 'LibRes' subsheet from a raw GC–MS Excel file.

    - Uses xlrd for .xls, default engine for .xlsx.
    - Finds the sheet named 'LibRes' (case-insensitive).
    - Uses Excel row 9 (0-based index 8) as the header row.
    """
    fname = filename.lower()
    if fname.endswith(".xls"):
        engine = "xlrd"
    else:
        engine = None  # let pandas choose (openpyxl for .xlsx)

    # open workbook
    xls = pd.ExcelFile(file_obj, engine=engine)

    # find LibRes sheet
    libres_name = None
    for s in xls.sheet_names:
        if s.lower() == "libres":
            libres_name = s
            break

    if libres_name is None:
        raise ValueError(f"No 'LibRes' sheet found in file. Sheets: {xls.sheet_names}")

    # 👉 Row 9 in Excel = index 8 in pandas → header=8
    df_raw = pd.read_excel(xls, sheet_name=libres_name, header=8)

    return df_raw


def extract_top_hits(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    From a LibRes-style sheet:
    - forward-fill compound ID column
    - for each compound, keep the row with max Quality.
    """
    df = df_raw.copy()

    # ---- detect compound column robustly ----
    # Try to find any column whose name contains "compound"
    compound_candidates = [
        c for c in df.columns if "compound" in str(c).lower()
    ]
    if not compound_candidates:
        raise KeyError(
            f"No compound column found. Available columns: {list(df.columns)}"
        )
    col_compound = compound_candidates[0]  # e.g. "Compound" or "Compound number (#)"

    # Quality column (this one really is called "Quality" in your sheet)
    col_quality = "Quality"

    # drop completely empty rows
    df = df.dropna(how="all")

    # forward fill compound IDs
    df["compound_id"] = df[col_compound].ffill()

    # drop rows where compound is still NaN (header/footer)
    df = df.dropna(subset=["compound_id"])

    # choose row with max Quality per compound
    idx = df.groupby("compound_id")[col_quality].idxmax()
    top = df.loc[idx].sort_values("compound_id").reset_index(drop=True)

    return top


def clean_rpw_file(file_obj, filename: str) -> pd.DataFrame:
    """
    High-level function:
    - read LibRes subsheet from the raw Excel file
    - take top hit per compound
    - rename columns nicely
    - attach metadata from filename.
    """
    # 👉 pass filename into load_libres_sheet
    df_raw = load_libres_sheet(file_obj, filename)

    df_hits = extract_top_hits(df_raw)

    rename_map = {
    # support both possible header names for the first column
    "Compound number (#)": "compound_number",
    "Compound": "compound_number",

    "RT (min)": "rt_min",
    "Scan number (#)": "scan_number",
    "Scan numb": "scan_number",          # in case your header is truncated
    "Area (Ab*s)": "area_abs",
    "Baseline Heigth (Ab)": "baseline_height",
    "Baseline H": "baseline_height",     # fallback
    "Absolute Heigth (Ab)": "absolute_height",
    "Absolute H": "absolute_height",     # fallback
    "Peak Width 50% (min)": "peak_width_50",
    "Peak Widt": "peak_width_50",        # fallback
    "Hit Number": "hit_number",
    "Hit Numbe": "hit_number",           # fallback
    "Hit Name": "hit_name",
    "Quality": "quality",
    "Mol Weight (amu)": "mol_weight_amu",
    "CAS Number": "cas_number",
    "Library": "library",
    "Entry Number": "entry_number",
    "Entry Numb": "entry_number",        # fallback
}

    df_hits = df_hits.rename(columns=rename_map)

    meta = extract_metadata_from_filename(filename)
    for key, val in meta.items():
        df_hits[key] = val

    return df_hits
