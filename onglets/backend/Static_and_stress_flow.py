import pandas as pd
import numpy as np 
import streamlit as st
import unicodedata
import re
# =========================
# Stress parsing + apply (CORRIGÉ)
# =========================
def _norm_label(x) -> str:
    """Normalise pour matcher: lower + trim + espaces + sans accents."""
    if x is None:
        return ""
    try:
        if isinstance(x, float) and np.isnan(x):
            return ""
    except Exception:
        pass

    s = str(x).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return s


def _parse_shock_value(x) -> float:
    """Accepte -0.15, '5%', '0,05', NaN, etc."""
    if x is None:
        return 0.0
    try:
        if isinstance(x, float) and np.isnan(x):
            return 0.0
    except Exception:
        pass

    s = str(x).strip().lower()
    if s in ("", "none", "nan", "null", "-"):
        return 0.0

    s = s.replace(" ", "").replace(",", ".")
    is_pct = "%" in s
    s = s.replace("%", "")

    try:
        v = float(s)
    except ValueError:
        return 0.0

    return v / 100.0 if is_pct else v


def parse_liquidity_stress_sheet(stress_df: pd.DataFrame) -> dict:
    """
    Parse la feuille stress sous forme Excel (blocs Scenario 1/2/3, Actifs/Passifs, vides/NaN).
    Retour:
      {
        "idiosyncratique": {label_norm: choc_float, ...},
        "systémique": {..},
        "combiné": {..}
      }
    """
    df = stress_df.copy()
    cols = list(df.columns)
    if len(cols) < 2:
        return {"idiosyncratique": {}, "systémique": {}, "combiné": {}}

    label_col = cols[0]

    choc_col = None
    for c in cols:
        if str(c).strip().lower() == "choc":
            choc_col = c
            break
    if choc_col is None:
        choc_col = cols[1]  # fallback

    res = {"idiosyncratique": {}, "systémique": {}, "combiné": {}}
    current = None

    def _scenario_from_label(x) -> str | None:
        t = _norm_label(x)
        if "scenario 1" in t:
            return "idiosyncratique"
        if "scenario 2" in t:
            return "systémique"
        if "scenario 3" in t:
            return "combiné"
        return None

    for _, row in df.iterrows():
        raw_label = row.get(label_col, None)
        sc = _scenario_from_label(raw_label)
        if sc is not None:
            current = sc
            continue

        if current is None:
            continue

        label = _norm_label(raw_label)

        # ignorer titres / vides
        if label in ("", "actifs", "passifs", "choc"):
            continue

        shock = _parse_shock_value(row.get(choc_col, None))
        if abs(shock) < 1e-12:
            continue

        res[current][label] = float(shock)

    return res


def apply_liquidity_stress(static_flow: pd.DataFrame, stress_df: pd.DataFrame, scenario: str):
    """
    Respecte TA règle:
    - on cherche match sur 'Catégories Bilan' OU 'Poste du bilan'
    - si match, on applique: M0_i = M0_i + choc(label)*M0_i
    - puis projection liquidity_flows()
    """
    fs = static_flow.copy()  # ✅ on reçoit déjà empty_fs (projetable)

    stress_map = parse_liquidity_stress_sheet(stress_df)

    scenario_key = scenario.strip().lower()
    if scenario_key.startswith("id"):
        scenario_key = "idiosyncratique"
    elif "syst" in scenario_key:
        scenario_key = "systémique"
    else:
        scenario_key = "combiné"

    shocks = stress_map.get(scenario_key, {})  # {label_norm: choc_float}

    col_cat = "Catégories Bilan"
    col_poste = "Poste du bilan"

    for idx in fs.index:
        cat = _norm_label(fs.at[idx, col_cat]) if col_cat in fs.columns else ""
        poste = _norm_label(fs.at[idx, col_poste]) if col_poste in fs.columns else ""

        shock = None
        if cat and cat in shocks:
            shock = shocks[cat]
        elif poste and poste in shocks:
            shock = shocks[poste]

        if shock is not None:
            for j in range(1,121):
                m0 = float(pd.to_numeric(fs.at[idx, f"M{j}"], errors="coerce") or 0.0)
                fs.at[idx, f"M{j}"] = m0*(1+shock)**(j/12)# ✅ EXACTEMENT ta formule
    #Stress_CRD_flow_df, Stress_Cash_Flow_df, Stress_Interest_Flow_df = liquidity_flows(fs)
    Stress_CRD_flow_df = fs
    st.session_state["Stress_CRD_flow_df"] = Stress_CRD_flow_df
    # st.session_state["Stress_Cash_Flow_df"] = Stress_Cash_Flow_df
    # st.session_state["Stress_Interest_Flow_df"] = Stress_Interest_Flow_df
    st.session_state["last_stress_scenario"] = scenario

    return Stress_CRD_flow_df
