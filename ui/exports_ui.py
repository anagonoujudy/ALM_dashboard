import io
import pandas as pd
import streamlit as st

def build_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Crée un Excel multi-feuilles en mémoire."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            if df is None:
                continue
            # sécurité: si ce n'est pas un df, on skip
            if not hasattr(df, "to_excel"):
                continue
            df.to_excel(writer, sheet_name=str(name)[:31], index=False)
    buffer.seek(0)
    return buffer.read()

def export_button(label: str, sheets: dict[str, pd.DataFrame], filename: str):
    """Affiche un bouton de téléchargement si on a au moins 1 feuille."""
    if not sheets or all(df is None for df in sheets.values()):
        st.info("Rien à exporter pour le moment.")
        return

    xlsx_bytes = build_excel_bytes(sheets)
    st.download_button(
        label=label,
        data=xlsx_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
