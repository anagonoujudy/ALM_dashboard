import pandas as pd

UNIT_FACTORS = {
    "EUR": 1.0,
    "KEUR": 1e3,
    "MEUR": 1e6,
    "GEUR": 1e9,
}

def scale_amount(x, unit_out: str):
    """Convertit un montant (supposé en EUR) vers l'unité d'affichage."""
    f = UNIT_FACTORS.get(unit_out, 1e3)
    return x / f

def format_number(x, decimals=2):
    try:
        return f"{float(x):,.{decimals}f}".replace(",", " ").replace(".", ",")
    except Exception:
        return str(x)

def ratios_dict_to_df(ratios: dict) -> pd.DataFrame:
    """Transforme {'ratio_key': value} en DataFrame affichable/exportable."""
    if ratios is None:
        return pd.DataFrame(columns=["Ratio", "Valeur"])
    return pd.DataFrame(
        [{"Ratio": k, "Valeur": v} for k, v in ratios.items()]
    )

def require_loaded_excel():
    """Petit helper logique: renvoie True si OK, sinon False."""
    import streamlit as st
    if not st.session_state.get("excel_loaded", False):
        st.warning("Charge d'abord le fichier Excel dans l’onglet 1.")
        return False
    return True