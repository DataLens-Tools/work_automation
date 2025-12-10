# app.py
import streamlit as st
import pandas as pd

from rpw_processing import clean_rpw_file

st.set_page_config(page_title="RPW VOC Automation", layout="wide")

st.title("🌴 RPW Volatile Data Automation – MVP")

st.markdown(
    """
Upload one or more **raw GC–MS Excel files** from any timepoint  
(24 h, 48 h, 72 h, …; charcoal or DVB).

Each file should be the original export that contains multiple subsheets  
(e.g. *IntRes*, *LibRes*, *QRes*, *CalCurve*).  
The app will automatically extract the **LibRes** sheet and then:

- take the **top-quality hit per compound**
- attach metadata from the file name (group, timepoint, adsorbent, sample)
- combine everything into one clean table you can download.
"""
)

uploaded_files = st.file_uploader(
    "Upload Excel files (.xls / .xlsx)", type=["xls", "xlsx"], accept_multiple_files=True
)

if uploaded_files:
    all_tables = []

    for f in uploaded_files:
        st.write(f"Processing: **{f.name}**")
        try:
            df_clean = clean_rpw_file(f, f.name)
            all_tables.append(df_clean)
        except Exception as e:
            st.error(f"❌ Error processing {f.name}: {e}")

    if all_tables:
        df_all = pd.concat(all_tables, ignore_index=True)

        st.subheader("Combined Cleaned Data")
        st.dataframe(df_all, use_container_width=True)

        # quick summary by timepoint / group / adsorbent
        with st.expander("Summary by timepoint / group / adsorbent"):
            summary = (
                df_all.groupby(["timepoint", "group", "adsorbent"])
                .size()
                .reset_index(name="n_compounds")
                .sort_values(["timepoint", "group", "adsorbent"])
            )
            st.dataframe(summary, use_container_width=True)

        # download button
        csv_bytes = df_all.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Download combined CSV",
            csv_bytes,
            file_name="rpw_clean_combined.csv",
            mime="text/csv",
        )
    else:
        st.warning("No valid files were processed. Please check your uploads.")
else:
    st.info("Upload at least one Excel file to begin.")
