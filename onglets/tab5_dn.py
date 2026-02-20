import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import re
import unicodedata
import plotly.graph_objects as go

# ============================================================
# Helpers généraux
# ============================================================

def df_to_excel_bytes(df: pd.DataFrame, sheet_name="flows") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def _unit_factor_from_KEUR(unit: str) -> float:
    if unit == "KEUR":
        return 1.0
    if unit == "EUR":
        return 1000.0
    if unit == "MEUR":
        return 1.0 / 1000.0
    if unit == "GEUR":
        return 1.0 / 1_000_000.0
    return 1.0


def convert_display_unit_dynamic(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    """
    Convertit valeurs kEUR -> unité demandée sur:
    - colonnes mensuelles M0..Mn
    - M0Nouvelle
    - Prévisions
    """
    out = df.copy()

    if unit == "KEUR":
        factor = 1.0
    elif unit == "EUR":
        factor = 1000.0
    elif unit == "MEUR":
        factor = 1.0 / 1000.0
    elif unit == "GEUR":
        factor = 1.0 / 1_000_000.0
    else:
        factor = 1.0

    m_cols = [c for c in out.columns if re.fullmatch(r"M\d+", str(c))]
    for c in m_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0) * factor

    for c in ["M0", "M0Nouvelle", "Prévision_N1", "Prévision_N2", "Prévision_N3"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0) * factor

    return out


def to_bucket_view_dynamic(df: pd.DataFrame) -> pd.DataFrame:
    """
    Affichage obligatoire en buckets :
    M0, M1..M11, 1Y..10Y (=M12..M120).
    Conserve les colonnes non-M* (métadonnées).
    """
    df = df.copy()
    base_cols = [c for c in df.columns if not re.fullmatch(r"M\d+", str(c))]
    out = df[base_cols].copy()

    out["M0"] = df.get("M0", 0.0)
    for i in range(1, 12):
        out[f"M{i}"] = df.get(f"M{i}", 0.0)
    for y in range(1, 11):
        out[f"{y}Y"] = df.get(f"M{12*y}", 0.0)

    return out


def _norm_label(x) -> str:
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


# ============================================================
# Données / cleaning (tes fonctions existantes)
# ============================================================

CATEGORIES_A_SUPPRIMER = [
    "CAISSE, BANQUES CENTRALES",
    "CREANCES SUR LES ETS DE CREDIT",
    "CREANCES SUR LA CLIENTELE",
    "TITRE D'INVESTISSEMENT",
    "IMMOBILISATIONS",
    "AUTRES",
    "DETTES ENVERS ETS DE CREDIT",
    "CPTES CREDITEURS DE LA CLIENTELE",
    "PROVISIONS",
    "FINANCEMENT",
    "FONDS PROPRES",
]


def clean_pmt(pmt_df: pd.DataFrame) -> pd.DataFrame:
    pmt_df_clean = pmt_df[~pmt_df["Poste du bilan"].isin(CATEGORIES_A_SUPPRIMER)].reset_index(drop=True)
    pmt_df_final = pmt_df_clean.copy()
    counts_total = pmt_df_final["Poste du bilan"].value_counts()
    doublons = counts_total[counts_total > 1].index.tolist()

    counts = {}
    new_poste_bilan = []
    for val in pmt_df_final["Poste du bilan"]:
        if val in doublons:
            counts[val] = counts.get(val, 0) + 1
            new_poste_bilan.append(f"{val} {counts[val]}")
        else:
            new_poste_bilan.append(val)

    pmt_df_final["Poste bilan"] = new_poste_bilan
    return pmt_df_final


def clean_taux(taux_df: pd.DataFrame) -> pd.DataFrame:
    taux_df_clean = taux_df[~taux_df["Poste bilan"].isin(CATEGORIES_A_SUPPRIMER)].reset_index(drop=True)
    taux_df_final = taux_df_clean.copy()
    counts_total = taux_df_final["Poste bilan"].value_counts()
    doublons = counts_total[counts_total > 1].index.tolist()

    counts = {}
    new_poste_bilan = []
    for val in taux_df_final["Poste bilan"]:
        if val in doublons:
            counts[val] = counts.get(val, 0) + 1
            new_poste_bilan.append(f"{val} {counts[val]}")
        else:
            new_poste_bilan.append(val)

    taux_df_final["Poste bilan"] = new_poste_bilan
    return taux_df_final


def clean_runoff(runoff_df: pd.DataFrame) -> pd.DataFrame:
    runoff_df_final = runoff_df.copy()
    counts_total = runoff_df_final["Poste bilan"].value_counts()
    doublons = counts_total[counts_total > 1].index.tolist()

    counts = {}
    new_poste_bilan = []
    for val in runoff_df_final["Poste bilan"]:
        if val in doublons:
            counts[val] = counts.get(val, 0) + 1
            new_poste_bilan.append(f"{val} {counts[val]}")
        else:
            new_poste_bilan.append(val)

    runoff_df_final["Poste bilan"] = new_poste_bilan
    return runoff_df_final


def build_dynamic_fs_projection(runoff_df_final: pd.DataFrame,
                               taux_df_final: pd.DataFrame,
                               pmt_df_final: pd.DataFrame) -> pd.DataFrame:
    merged_df = pd.merge(runoff_df_final, taux_df_final, on="Poste bilan", how="left")
    merged_df = pd.merge(
        merged_df,
        pmt_df_final[["Poste bilan", "M0", "Prévision_N1", "Prévision_N2", "Prévision_N3"]],
        on="Poste bilan",
        how="left",
    )

    for i in range(1, 121):
        merged_df[f"M{i}"] = np.nan

    for col in ["Loi d'écoulement en liquidité", "Durée moyenne (en mois)"]:
        if col in merged_df.columns:
            merged_df = merged_df.drop(columns=[col])

    fs = merged_df.copy()
    if "Catégories Bilan" in fs.columns:
        fs["Catégories Bilan"] = fs["Catégories Bilan"].replace("FONDS PROPRES", "CAPITAUX PROPRES")

    fs["Taux"] = pd.to_numeric(fs.get("Taux", 0.0), errors="coerce").fillna(0.0)
    for c in ["M0", "Prévision_N1", "Prévision_N2", "Prévision_N3"]:
        if c not in fs.columns:
            fs[c] = 0.0
        fs[c] = pd.to_numeric(fs[c], errors="coerce").fillna(0.0)

    return fs


def load_stress_raw() -> pd.DataFrame:
    stress_data = st.session_state["stress_liquidity_df"]
    stress_data.columns = stress_data.iloc[0]
    stress_data = stress_data[1:]
    stress_data = stress_data.reset_index(drop=True)

    records = []
    current_scenario = None

    for i in range(len(stress_data)):
        row = stress_data.iloc[i]
        label = str(row[0]).strip() if not pd.isna(row[0]) else ""
        choc_cell = row[1] if len(row) > 1 else np.nan

        if "Scenario 1" in label:
            current_scenario = "idiosyncratique"
            continue
        elif "Scenario 2" in label:
            current_scenario = "systémique"
            continue
        elif "Scenario 3" in label:
            current_scenario = "combiné"
            continue

        if label.lower() in ("actifs", "passifs"):
            continue

        if current_scenario and not pd.isna(choc_cell):
            shock = _parse_shock_value(choc_cell)
            if abs(shock) < 1e-12:
                continue
            records.append([current_scenario, label, shock])

    return pd.DataFrame(records, columns=["Scenario", "Label", "Choc"])


def parse_liquidity_stress_sheet(stress_df: pd.DataFrame) -> dict:
    if set(["Scenario", "Label", "Choc"]).issubset(stress_df.columns):
        res = {"idiosyncratique": {}, "systémique": {}, "combiné": {}}
        for _, r in stress_df.iterrows():
            sc = str(r["Scenario"]).strip().lower()
            lab = _norm_label(r["Label"])
            choc = float(pd.to_numeric(r["Choc"], errors="coerce") or 0.0)
            if lab and abs(choc) > 1e-12 and sc in res:
                res[sc][lab] = choc
        return res
    return {"idiosyncratique": {}, "systémique": {}, "combiné": {}}


# ============================================================
# Flux CRD
# ============================================================

def _pmt(rate_month, nper, pv):
    if nper <= 0:
        return 0.0
    if abs(rate_month) < 1e-12:
        return pv / nper
    return (rate_month * pv) / (1 - (1 + rate_month) ** (-nper))


def liquidity_flows_team_style(financial_statement: pd.DataFrame):
    fs = financial_statement.copy()

    law_col = "Profil d’écoulement" if "Profil découlement" not in fs.columns else "Profil découlement"
    if "Profil d’écoulement" not in fs.columns and "Profil découlement" not in fs.columns:
        fs["Profil d’écoulement"] = ""
        law_col = "Profil d’écoulement"

    dur_col = "Maturité"
    if "Maturité" not in fs.columns:
        fs["Maturité"] = 0

    rate_col = "Taux"
    if "Taux" not in fs.columns:
        fs["Taux"] = 0.0

    CRD_flow_df = fs.copy()
    Cash_Flow_df = fs.copy()
    Interest_Flow_df = fs.copy()

    CRD_flow_df[dur_col] = pd.to_numeric(CRD_flow_df[dur_col], errors="coerce").fillna(0).astype(int)

    for idx in CRD_flow_df.index:
        M0 = float(pd.to_numeric(CRD_flow_df.at[idx, "M0"], errors="coerce") or 0.0)
        n = int(CRD_flow_df.at[idx, dur_col])
        r = float(pd.to_numeric(CRD_flow_df.at[idx, rate_col], errors="coerce") or 0.0)
        r_m = r / 12.0
        law = str(CRD_flow_df.at[idx, law_col]).strip().lower()

        prev_crd = M0

        for i in range(1, 121):
            col = f"M{i}"

            if n <= 0:
                crd_i = 0.0
            elif "linéaire" in law or "lineaire" in law:
                crd_i = M0 * (n - i) / n if i < n else 0.0
            elif "constant" in law:
                if i < n:
                    annuity = _pmt(r_m, n, M0)
                    crd_i = prev_crd * (1 + r_m) - annuity
                    crd_i = max(crd_i, 0.0)
                else:
                    crd_i = 0.0
            elif "in fine" in law or "ine fine" in law:
                crd_i = M0 if i < n else 0.0
            elif "90%-20%*t" in law:
                crd_i = max(M0 * (0.90 - 0.20 * i), 0.0) if i <= 4 else 0.0
            elif "exp" in law:
                crd_i = M0 * 0.90 * np.exp(-0.20 * i)
            else:
                crd_i = 0.0

            CRD_flow_df.at[idx, col] = crd_i
            Cash_Flow_df.at[idx, col] = (-crd_i + prev_crd) if (n > 0 and i < n) else 0.0
            Interest_Flow_df.at[idx, col] = (prev_crd * r_m) if (n > 0 and i < n) else 0.0
            prev_crd = crd_i

    return CRD_flow_df, Cash_Flow_df, Interest_Flow_df


def dynamic_liquidity_flows_from_crd(CRD_flow_df: pd.DataFrame, horizon: int = 170) -> pd.DataFrame:
    df = CRD_flow_df.copy()
    mois_cols = [f"M{i}" for i in range(1, horizon + 1)]
    for col in mois_cols:
        if col not in df.columns:
            df[col] = 0.0

    nouvelles_annees = {
        "2026": ("Prévision_N1", 12),
        "2027": ("Prévision_N2", 24),
        "2028": ("Prévision_N3", 36),
    }

    if "M0Nouvelle" not in df.columns:
        df["M0Nouvelle"] = 0.0

    all_rows = []

    for _, row in df.iterrows():
        all_rows.append(row.copy())

        maturite = int(pd.to_numeric(row.get("Maturité", 0), errors="coerce") or 0)
        profil = str(row.get("Profil d’écoulement", "")).lower()

        for annee, (prev_col, start_month) in nouvelles_annees.items():
            prev = float(pd.to_numeric(row.get(prev_col, 0.0), errors="coerce") or 0.0)
            crd_depart = float(pd.to_numeric(row.get(f"M{start_month}", 0.0), errors="coerce") or 0.0)
            montant_initial = prev - crd_depart

            new_row = row.copy()
            if "Poste bilan" in new_row.index:
                new_row["Poste bilan"] = f"{row.get('Poste bilan','')} - Nouvelle production {annee}"
            new_row["M0Nouvelle"] = montant_initial
            new_row["Maturité"] = maturite

            new_row[mois_cols] = 0.0
            if start_month <= horizon:
                new_row[f"M{start_month}"] = montant_initial

            crd_restant = montant_initial
            for i in range(maturite):
                mois = start_month + i + 1
                if mois > horizon:
                    break

                if ("lin" in profil) or ("lineaire" in profil) or ("linéaire" in profil) or ("constant" in profil):
                    flux = montant_initial / maturite if maturite > 0 else 0.0
                elif ("in fine" in profil) or ("ine fine" in profil):
                    flux = montant_initial if i == maturite - 1 else 0.0
                elif "90%-20%*t" in profil:
                    pct_prev = 0.9 - 0.2 * i
                    pct_curr = 0.9 - 0.2 * (i + 1)
                    flux = montant_initial * (pct_prev - pct_curr)
                elif "exp" in profil:
                    pct_prev = 0.9 * np.exp(-0.2 * i)
                    pct_curr = 0.9 * np.exp(-0.2 * (i + 1))
                    flux = montant_initial * (pct_prev - pct_curr)
                else:
                    flux = montant_initial / maturite if maturite > 0 else 0.0

                crd_restant = max(crd_restant - flux, 0.0)
                new_row[f"M{mois}"] = crd_restant

            fin = start_month + maturite
            for m in range(fin + 1, horizon + 1):
                new_row[f"M{m}"] = 0.0

            all_rows.append(new_row)

    out = pd.DataFrame(all_rows)

    cols = list(out.columns)
    if "M0Nouvelle" in cols and "M0" in cols:
        cols.insert(cols.index("M0") + 1, cols.pop(cols.index("M0Nouvelle")))
        out = out[cols]

    return out


def apply_dynamic_liquidity_stress(financial_statement: pd.DataFrame,
                                   stress_df: pd.DataFrame,
                                   scenario: str) -> pd.DataFrame:
    fs = financial_statement.copy()
    stress_map = parse_liquidity_stress_sheet(stress_df)

    scenario_key = scenario.strip().lower()
    if scenario_key.startswith("id"):
        scenario_key = "idiosyncratique"
    elif "syst" in scenario_key:
        scenario_key = "systémique"
    else:
        scenario_key = "combiné"

    shocks = stress_map.get(scenario_key, {})

    # sécurise colonnes prévision
    for c in ["Prévision_N1", "Prévision_N2", "Prévision_N3"]:
        if c not in fs.columns:
            fs[c] = 0.0
        fs[c] = pd.to_numeric(fs[c], errors="coerce").fillna(0.0)

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
            fs.at[idx, "Prévision_N1"] *= (1 + shock) ** 1
            fs.at[idx, "Prévision_N2"] *= (1 + shock) ** 2
            fs.at[idx, "Prévision_N3"] *= (1 + shock) ** 3

    CRD_flow_df, _, _ = liquidity_flows_team_style(fs)
    return dynamic_liquidity_flows_from_crd(CRD_flow_df, horizon=170)


# ============================================================
# NOUVELLE MÉTHODE GAP (mensuel -> buckets)
# ============================================================

def dynamic_liquidity_gap_by_year(df: pd.DataFrame, year: str) -> pd.DataFrame:
    df = df.copy()
    df["Bilan"] = df["Bilan"].astype(str).str.strip().str.upper()
    df["Poste bilan"] = df["Poste bilan"].astype(str).str.strip()

    mois_cols = [col for col in df.columns if str(col).startswith("M") and str(col)[1:].isdigit()]
    mois_cols = sorted(mois_cols, key=lambda x: int(str(x)[1:]))

    results = []

    for col in mois_cols:
        if col == "M0":
            temp_df = df[~df["Poste bilan"].str.contains("Nouvelle production", na=False)]
        else:
            temp_df = df[
                (~df["Poste bilan"].str.contains("Nouvelle production", na=False))
                | (df["Poste bilan"].str.contains(f"Nouvelle production {year}", na=False))
            ]

        actifs_df = temp_df[temp_df["Bilan"] == "ACTIF"]
        passifs_df = temp_df[temp_df["Bilan"] == "PASSIF"]

        total_actifs = pd.to_numeric(actifs_df[col], errors="coerce").fillna(0.0).sum()
        total_passifs = pd.to_numeric(passifs_df[col], errors="coerce").fillna(0.0).sum()
        gap = total_passifs - total_actifs

        results.append([col, total_actifs, total_passifs, gap])

    return pd.DataFrame(results, columns=["Mois", "Total Actifs", "Total Passifs", "Gap"])


def dynamic_gap_monthly_to_buckets(gap_monthly_df: pd.DataFrame) -> pd.DataFrame:
    g = gap_monthly_df.copy()
    g["Mois"] = g["Mois"].astype(str)
    gap_map = dict(zip(g["Mois"], pd.to_numeric(g["Gap"], errors="coerce").fillna(0.0)))

    buckets = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]
    values = []

    values.append(float(gap_map.get("M0", 0.0)))
    for i in range(1, 12):
        values.append(float(gap_map.get(f"M{i}", 0.0)))
    for y in range(1, 11):
        values.append(float(gap_map.get(f"M{12*y}", 0.0)))

    return pd.DataFrame({"Bucket": buckets, "Gap": values})


def dynamic_liquidity_gap_bucket_by_year(dynamic_CRD_flow_df: pd.DataFrame, year: str) -> pd.DataFrame:
    monthly = dynamic_liquidity_gap_by_year(dynamic_CRD_flow_df, year)
    return dynamic_gap_monthly_to_buckets(monthly)


# ============================================================
# UI TAB5 (Dynamic Analysis)
# ============================================================

def render_tab5_dynamic():

    if st.session_state.get("runoff_df") is None:
        st.warning("Charge d’abord le fichier Excel dans l’onglet 'Load Data'.")
        return

    st.title("Analyse dynamique")

    BTN = "tab5_"

    # --- Controls
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        unit = st.selectbox("**UNITE**", ["KEUR", "EUR", "MEUR", "GEUR"], index=0, key=f"{BTN}unit")
    with c2:
        source = st.selectbox("**SOURCE**", ["Dynamique", "Stressé"], index=0, key=f"{BTN}source")
    with c3:
        scenario = st.selectbox("**Scénario**", ["idiosyncratique", "systémique", "combiné"], index=0, key=f"{BTN}scenario")
    with c4:
        year = st.selectbox("**Prévision jusqu'à**", ["2026", "2027", "2028"], index=0, key=f"{BTN}year")

    with st.expander("**Boutons**", expanded=True):
        b1, b2, b3 = st.columns([1, 1, 1])
        with b1:
            run_selected = st.button("Projeter", key=f"{BTN}run")
        with b2:
            show_compare = st.button("Comparer Gaps", key=f"{BTN}compare")
        with b3:
            prepare_download = st.button("Exporter", key=f"{BTN}export")

    # --- Compute functions
    def _load_all():
        runoff = st.session_state["runoff_df"]
        runoff = runoff.rename(
            columns={
                "Poste du bilan": "Poste bilan",
                "Loi d'écoulement en liquidité": "Profil d’écoulement",
                "Durée moyenne (en mois)": "Maturité",
                "En liquidité": "Montant",
            }
        )

        taux_df = st.session_state["bilan"]
        taux_df = taux_df.rename(
            columns={
                taux_df.columns[2]: "Poste bilan",
                taux_df.columns[4]: "Taux",
            }
        )
        taux = taux_df[["Poste bilan", "Taux"]]
        pmt = st.session_state["pmt_df"]

        runoff = clean_runoff(runoff)
        taux = clean_taux(taux)
        pmt = clean_pmt(pmt)

        fs = build_dynamic_fs_projection(runoff, taux, pmt)
        stress_raw = load_stress_raw()
        return fs, stress_raw

    def _compute_dynamic():
        fs, _stress = _load_all()
        CRD_flow_df, _, _ = liquidity_flows_team_style(fs)
        dyn = dynamic_liquidity_flows_from_crd(CRD_flow_df, horizon=170)

        st.session_state["dynamic_CRD_flow_df"] = dyn
        st.session_state["dynamic_gap_df"] = dynamic_liquidity_gap_bucket_by_year(dyn, year)

    def _compute_dynamic_stress():
        fs, stress_raw = _load_all()
        stressed_dyn = apply_dynamic_liquidity_stress(fs, stress_raw, scenario)

        st.session_state["stressed_dynamic_CRD_flow_df"] = stressed_dyn
        st.session_state["stressed_dynamic_gap_df"] = dynamic_liquidity_gap_bucket_by_year(stressed_dyn, year)
        st.session_state["last_dynamic_stress_scenario"] = scenario

    # --- Bouton unique : calcule selon SOURCE
    if run_selected:
        if source == "Dynamique":
            _compute_dynamic()
            st.success("Projection dynamique calculée ✅")
        else:
            _compute_dynamic_stress()
            st.success("Projection dynamique stressée calculée ✅")

    # ------------------------------------------------------------
    # Comparer gaps (inchangé : calcule les 2 + plot Plotly joli)
    # ------------------------------------------------------------
    if show_compare:
        _compute_dynamic()
        _compute_dynamic_stress()
        st.success("Dynamique + Stress dynamique calculés ✅")

        factor = _unit_factor_from_KEUR(unit)

        gap_dyn = st.session_state["dynamic_gap_df"].copy()
        gap_str = st.session_state["stressed_dynamic_gap_df"].copy()

        gap_dyn["Gap"] = pd.to_numeric(gap_dyn["Gap"], errors="coerce").fillna(0.0) * factor
        gap_str["Gap"] = pd.to_numeric(gap_str["Gap"], errors="coerce").fillna(0.0) * factor

        BUCKET_ORDER = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]
        gap_dyn["Bucket"] = pd.Categorical(gap_dyn["Bucket"], categories=BUCKET_ORDER, ordered=True)
        gap_str["Bucket"] = pd.Categorical(gap_str["Bucket"], categories=BUCKET_ORDER, ordered=True)
        gap_dyn = gap_dyn.sort_values("Bucket")
        gap_str = gap_str.sort_values("Bucket")

        x = gap_dyn["Bucket"].astype(str).tolist()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=gap_dyn["Gap"].tolist(),
            mode="lines+markers",
            name=f"Gap dynamique (NP {year})",
            line=dict(color="#00C2FF", width=3),
        ))
        fig.add_trace(go.Scatter(
            x=x,
            y=gap_str["Gap"].tolist(),
            mode="lines+markers",
            name=f"Gap stressé ({scenario}) (NP {year})",
            line=dict(color="#FF4D6D", width=3),
        ))
        fig.update_layout(
            title=f"Gap dynamique vs Gap dynamique Stressé — Prévision jusqu'à: {year}",
            xaxis_title="Buckets",
            yaxis_title=f"Gap ({unit})",
            template="plotly_dark",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.subheader("Gaps comparés (Buckets)")
        st.plotly_chart(fig, use_container_width=True)

        gap_compare = pd.DataFrame({
            "Bucket": x,
            f"Gap dynamique (NP {year})": gap_dyn["Gap"].tolist(),
            f"Gap stressé ({scenario}) (NP {year})": gap_str["Gap"].tolist(),
        })
        st.dataframe(gap_compare, use_container_width=True)
        return

    # ------------------------------------------------------------
    # Affichage standard
    # ------------------------------------------------------------
    if st.session_state.get("dynamic_CRD_flow_df") is None and st.session_state.get("stressed_dynamic_CRD_flow_df") is None:
        st.info("Clique sur **Projeter ou Comparer gaps** (Dynamique ou Stressé).")
        return

    if source == "Dynamique":
        df_show = st.session_state.get("dynamic_CRD_flow_df")
        gap_df = st.session_state.get("dynamic_gap_df")
        sheet = f"CRD_Dynamic_Buckets_NP_{year}"
    else:
        df_show = st.session_state.get("stressed_dynamic_CRD_flow_df")
        gap_df = st.session_state.get("stressed_dynamic_gap_df")
        scen = st.session_state.get("last_dynamic_stress_scenario", scenario)
        sheet = f"CRD_Dynamic_Stressed_{scen}_Buckets_NP_{year}"
        if df_show is None:
            st.warning("Tu es en **Stressé** : clique d’abord sur **Projeter**.")
            return

    df_disp = convert_display_unit_dynamic(df_show.copy(), unit)
    df_bucket = to_bucket_view_dynamic(df_disp)

    st.subheader(f"{source} — Vision CRD")
    st.dataframe(df_bucket, use_container_width=True)

    # --- Gap Plotly joli
    st.markdown("### Gap dynamique (Passif − Actif)")
    if gap_df is not None and not gap_df.empty:
        g = gap_df.copy()
        factor = _unit_factor_from_KEUR(unit)
        g["Gap"] = pd.to_numeric(g["Gap"], errors="coerce").fillna(0.0) * factor

        BUCKET_ORDER = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]
        g["Bucket"] = pd.Categorical(g["Bucket"], categories=BUCKET_ORDER, ordered=True)
        g = g.sort_values("Bucket")

        x = g["Bucket"].astype(str).tolist()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=g["Gap"].tolist(),
            mode="lines+markers",
            name=f"Gap ({source}) (NP {year})",
            line=dict(color="#00C2FF", width=3),
        ))
        fig.update_layout(
            title=f"Gap dynamique — {source} — Présision jusqu'à: {year}",
            xaxis_title="Buckets",
            yaxis_title=f"Gap ({unit})",
            template="plotly_dark",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(g, use_container_width=True)

    # --- Export
    if prepare_download:
        xls_bytes = df_to_excel_bytes(df_bucket, sheet_name=sheet)
        st.download_button(
            "Télécharger (Excel)",
            data=xls_bytes,
            file_name=f"{sheet}_{unit}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{BTN}dl"
        )