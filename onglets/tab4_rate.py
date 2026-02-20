import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.graph_objects as go
import re


# =========================
# Constantes Buckets
# =========================
BUCKET_LABELS = [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]
BUCKET_MONTHS = list(range(1, 12)) + [12 * y for y in range(1, 11)]  # 1..11, 12..120 step 12
STRESS_COLORS = [
    "#FF4D6D", "#FFD166", "#06D6A0", "#A78BFA", "#F97316",
    "#22C55E", "#38BDF8", "#F43F5E", "#EAB308", "#14B8A6"
]

def _pmt(rate_month, nper, pv):
    if nper <= 0:
        return 0.0
    if abs(rate_month) < 1e-12:
        return pv / nper
    return (rate_month * pv) / (1 - (1 + rate_month) ** (-nper))



def zc_to_buckets(actuarial_zc_rate: pd.DataFrame) -> pd.DataFrame:
    """Convertit la courbe mensuelle (1..120) en buckets M1..M11 + 1Y..10Y."""
    base = dict(zip(actuarial_zc_rate["month"], actuarial_zc_rate["zc_rate"]))
    return pd.DataFrame({
        "Bucket": BUCKET_LABELS,
        "month": BUCKET_MONTHS,
        "rate": [float(base.get(m, np.nan)) for m in BUCKET_MONTHS]
    })


# =========================
# Utils
# =========================
def convert_display_unit(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    df = df.copy()
    m_cols = ["M0"] + [f"M{i}" for i in range(1, 121) if f"M{i}" in df.columns]

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

    for c in m_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0) * factor
    return df


def _reorder_m_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    base_cols = [c for c in df.columns if not str(c).startswith("M")]
    m_cols = ["M0"] + [f"M{i}" for i in range(1, 121) if f"M{i}" in df.columns]
    ordered = [c for c in base_cols if c in df.columns] + [c for c in m_cols if c in df.columns]
    for c in df.columns:
        if c not in ordered:
            ordered.append(c)
    return df[ordered]


def df_to_excel_bytes(df: pd.DataFrame, sheet_name="rate") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


# =========================
# Build empty projection
# =========================
def build_empty_fs_projection(runoff_df: pd.DataFrame) -> pd.DataFrame:
    df = runoff_df.copy()

    if "Loi d'écoulement en taux" in df.columns:
        df = df.drop(columns=["Loi d'écoulement en taux"])

    if "Montant (en k€)" in df.columns:
        df = df.rename(columns={"Montant (en k€)": "M0"})

    if "Taux d'intérèt moyen" in df.columns and "Taux d'intérêt moyen" not in df.columns:
        df = df.rename(columns={"Taux d'intérèt moyen": "Taux d'intérêt moyen"})

    for i in range(1, 121):
        df[f"M{i}"] = np.nan

    return _reorder_m_cols(df)

def to_bucket_view(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    base_cols = [c for c in df.columns if not str(c).startswith("M")]
    out = df[base_cols].copy()

    out["M0"] = df.get("M0", 0.0)
    for i in range(1, 12):
        out[f"M{i}"] = df.get(f"M{i}", 0.0)
    for y in range(1, 11):
        out[f"{y}Y"] = df.get(f"M{12*y}", 0.0)

    return out
# =========================
# Fixed rate flows
# =========================
# def Fixed_rate_flows(financial_statement: pd.DataFrame) -> pd.DataFrame:
#     df = financial_statement.copy()

#     if "M0" not in df.columns:
#         raise ValueError("Colonne 'M0' manquante.")
#     if "Durée moyenne (en mois)" not in df.columns:
#         raise ValueError("Colonne 'Durée moyenne (en mois)' manquante.")
#     if "Taux d'intérêt moyen" not in df.columns:
#         df["Taux d'intérêt moyen"] = 0.0

#     prof_col = None
#     for c in ["Profil d’écoulement en taux", "Profil d'écoulement en taux", "Profil taux"]:
#         if c in df.columns:
#             prof_col = c
#             break

#     if prof_col is None:
#         df["Loi d'écoulement en taux"] = "in fine"
#     else:
#         df["Loi d'écoulement en taux"] = (
#             df[prof_col].astype(str)
#             .str.strip()
#             .str.lower()
#             .replace({"ine fine": "in fine", "lineaire": "linéaire"})
#         )

#     for i in range(len(df)):
#         profile = str(df.loc[i, "Loi d'écoulement en taux"]).lower().strip()

#         m0_raw = pd.to_numeric(df.loc[i, "M0"], errors="coerce")
#         dur_raw = pd.to_numeric(df.loc[i, "Durée moyenne (en mois)"], errors="coerce")
#         r_raw = pd.to_numeric(df.loc[i, "Taux d'intérêt moyen"], errors="coerce")

#         M0 = float(0.0 if pd.isna(m0_raw) else m0_raw)
#         maturity = int(0 if pd.isna(dur_raw) else dur_raw)
#         rate_annual = float(0.0 if pd.isna(r_raw) else r_raw)



#         r = rate_annual / 12.0

#         if maturity <= 0:
#             for m in range(1, 121):
#                 df.loc[i, f"M{m}"] = 0.0
#             continue

#         if profile == "in fine":
#             for m in range(1, 121):
#                 df.loc[i, f"M{m}"] = M0 if m < maturity else 0.0

#         elif profile == "linéaire":
#             for m in range(1, 121):
#                 if m <= maturity:
#                     CRD = M0 * (1 - m / maturity)
#                     df.loc[i, f"M{m}"] = max(CRD, 0.0)
#                 else:
#                     df.loc[i, f"M{m}"] = 0.0

#         elif profile == "constant":
#             CRD = M0
#             if abs(r) < 1e-12:
#                 C = M0 / maturity
#             else:
#                 C = (r * M0) / (1 - (1 + r) ** (-maturity))

#             for m in range(1, 121):
#                 if m <= maturity:
#                     CRD = CRD * (1 + r) - C
#                     if abs(CRD) < 1e-8:
#                         CRD = 0.0
#                     df.loc[i, f"M{m}"] = max(CRD, 0.0)
#                 else:
#                     df.loc[i, f"M{m}"] = 0.0
#         else:
#             for m in range(1, 121):
#                 df.loc[i, f"M{m}"] = 0.0

#     return df

def Fixed_rate_flows(financial_statement: pd.DataFrame)-> pd.DataFrame:
    CRD_flow_df = financial_statement.copy()

    law_col = "Loi d'écoulement en liquidité"
    dur_col = "Durée moyenne (en mois)"
    rate_col = "Taux d'intérêt moyen"

    CRD_flow_df[dur_col] = pd.to_numeric(CRD_flow_df[dur_col], errors="coerce").fillna(0).astype(int)

    for idx in CRD_flow_df.index:
        M0 = float(pd.to_numeric(CRD_flow_df.at[idx, "M0"], errors="coerce") or 0.0)
        n = int(CRD_flow_df.at[idx, dur_col])
        r = float(CRD_flow_df.at[idx, rate_col]) if rate_col in CRD_flow_df.columns else 0.0
        r_m = r / 12.0
        law = str(CRD_flow_df.at[idx, law_col]).strip().lower() if law_col in CRD_flow_df.columns else ""

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

            else:
                crd_i = 0.0

            CRD_flow_df.at[idx, col] = crd_i

            prev_crd = crd_i

    return _reorder_m_cols(CRD_flow_df)
# =========================
# ZC interpolation
# =========================
def Interpolate_ZC_Rate(zc_data_df: pd.DataFrame) -> pd.DataFrame:
    df = zc_data_df.copy()
    df.columns = df.columns.astype(str).str.strip()
    if "Maturité" not in df.columns:
        raise ValueError("Colonne 'Maturité' manquante dans zc_df.")
    if "Zero Coupon" not in df.columns:
        raise ValueError("Colonne 'Zero Coupon' manquante dans zc_df.")

    def to_months(x):
        s = str(x).strip().lower()
        s = s.replace("ans", "an").replace("année", "an").replace("annee", "an")
        m = re.match(r"^\s*(\d+)\s*(y|an|a|mois|m)\s*$", s)
        if m:
            n = int(m.group(1))
            u = m.group(2)
            if u in ("mois", "m"):
                return n
            return n * 12
        m2 = re.match(r"^\s*(\d+)\s+(an|a|mois)\s*$", s)
        if m2:
            n = int(m2.group(1))
            u = m2.group(2)
            return n if u == "mois" else n * 12
        raise ValueError(f"Maturité non reconnue: {x}")

    df["maturity_month"] = df["Maturité"].apply(to_months)
    df["Zero Coupon"] = pd.to_numeric(df["Zero Coupon"], errors="coerce")

    df = df.dropna(subset=["maturity_month", "Zero Coupon"]).sort_values("maturity_month")
    if df.empty:
        raise ValueError("zc_df ne contient pas de points valides.")

    results = []
    months_known = df["maturity_month"].values

    for m in range(1, 121):
        if m in months_known:
            r = float(df.loc[df["maturity_month"] == m, "Zero Coupon"].values[0])
        else:
            lower_part = df[df["maturity_month"] < m]
            upper_part = df[df["maturity_month"] > m]
            if lower_part.empty or upper_part.empty:
                r = float(df.iloc[0]["Zero Coupon"]) if lower_part.empty else float(df.iloc[-1]["Zero Coupon"])
            else:
                lower = lower_part.iloc[-1]
                upper = upper_part.iloc[0]
                m1, r1 = float(lower["maturity_month"]), float(lower["Zero Coupon"])
                m2, r2 = float(upper["maturity_month"]), float(upper["Zero Coupon"])
                r = r1 + ((m - m1) / (m2 - m1)) * (r2 - r1)

        DF = 1 / ((1 + r) ** (m / 12))
        results.append({"month": m, "zc_rate": r, "discount_factor": DF})

    return pd.DataFrame(results)


# =========================
# Fixed rate gap
# =========================

def fixed_rate_gap(flow_df: pd.DataFrame) -> pd.DataFrame:
    bdf = to_bucket_view(flow_df)
    bucket_cols = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]

    if "Bilan" not in bdf.columns:
        return pd.DataFrame({"Bucket": bucket_cols, "GAP (Passif - Actif)": [0.0] * len(bucket_cols)})

    # Exclure Capitaux propres si colonne dispo
    mask_exclude = pd.Series(False, index=bdf.index)
    if "Poste du bilan" in bdf.columns:
        mask_exclude |= bdf["Poste du bilan"].astype(str).str.strip().str.lower().eq("capitaux propres")
    if "Catégories Bilan" in bdf.columns:
        mask_exclude |= bdf["Catégories Bilan"].astype(str).str.strip().str.lower().eq("capitaux propres")

    bdf = bdf.loc[~mask_exclude].copy()

    side = bdf["Bilan"].astype(str).str.strip().str.upper()

    actifs = bdf.loc[side == "ACTIF", bucket_cols].sum(axis=0)
    passifs = bdf.loc[side == "PASSIF", bucket_cols].sum(axis=0)

    gap = passifs - actifs

    return pd.DataFrame({
        "Bucket": bucket_cols,
        "GAP (Passif - Actif)": gap.values
    })



# =========================
# Stress rate apply (interleaved)
# =========================
def apply_rate_stress_interleaved(stress_rate_df: pd.DataFrame, zc_rate: pd.DataFrame) -> pd.DataFrame:
    base_rates = dict(zip(zc_rate["month"], zc_rate["zc_rate"]))

    meta_cols = list(stress_rate_df.columns[:3])
    shock_cols = list(stress_rate_df.columns[3:123])  # 120 mois

    rows = []
    for _, row in stress_rate_df.iterrows():
        scenario_name = str(row[meta_cols[2]])
        rate_row = {"Scenario": scenario_name}
        df_row = {"Scenario": scenario_name + "_DF"}

        for m in range(1, 121):
            shock = float(pd.to_numeric(row[shock_cols[m-1]], errors="coerce") or 0.0)
            base_rate = float(base_rates.get(m, 0.0))
            stressed_rate = base_rate + shock
            stressed_df = 1 / ((1 + stressed_rate) ** (m / 12))

            rate_row[f"M{m}"] = stressed_rate
            df_row[f"M{m}"] = stressed_df

        rows.append(rate_row)
        rows.append(df_row)

    return pd.DataFrame(rows)


# =========================
# TAB 4 - Rate Analysis
# =========================
def render4():
    if st.session_state.get("runoff_df") is None:
        st.warning("Charge d’abord le fichier Excel dans l’onglet 'Load Data'.")
        return
    if st.session_state.get("stress_rate_df") is None:
        st.warning("Il manque la feuille **Stress test de taux** dans le chargement (onglet 1).")
        return
    if st.session_state.get("zc_data_df") is None:
        st.warning("Il manque la feuille **Courbe des taux** dans le chargement (onglet 1).")
        return
  
    runoff_df = st.session_state["runoff_df"]
    stress_df = st.session_state["stress_rate_df"]

    # --- Nettoyage zc_df (drop 1ère ligne, 2e devient header, drop dernière col)
    zc_df = st.session_state["zc_data_df"].copy()

    # 1) supprimer complètement les headers existants
    zc_df.columns = range(zc_df.shape[1])

    # 2) utiliser la première ligne comme header
    zc_df.columns = zc_df.iloc[0]

    # 3) supprimer cette ligne devenue header
    zc_df = zc_df.iloc[1:].reset_index(drop=True)

    # 4) supprimer la dernière colonne
    zc_df = zc_df.iloc[:, :-1]

    # 5) nettoyer noms colonnes
    zc_df.columns = zc_df.columns.astype(str).str.strip()


    # --- Courbe ZC mensuelle + matrice stress (mensuel)
    actuarial_zc_rate = Interpolate_ZC_Rate(zc_df)
    stress_matrix = apply_rate_stress_interleaved(stress_df, actuarial_zc_rate)

    st.title("Rate curve  ")

    c1, c2 = st.columns([1, 1])
    with c1:
        unit = st.selectbox("Unité ", ["KEUR", "EUR", "MEUR", "GEUR"], index=0)
    with c2:
        scenario = st.selectbox(
            "Scénario",
            ["+200BPS", "-200BPS", "Short_up", "Short_down", "Steepener", "Flattener"],
            index=0
        )

    # --- Boutons
    b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
    with b1:
        show_curve = st.button("Afficher courbe ZC (buckets)")
    with b2:
        add_stress_curve = st.button("Ajouter courbe ZC stressée")
    with b3:
        reset_curve = st.button("Reset graphe")
    with b4:
        show_static_gaps = st.button("Visionner GAP taux fixé")

    # --- Prépare données base en buckets
    base_bucket_df = zc_to_buckets(actuarial_zc_rate)

    if "zc_fig" not in st.session_state:
        st.session_state["zc_fig"] = None
    if "zc_stress_count" not in st.session_state:
        st.session_state["zc_stress_count"] = 0

    if reset_curve:
        st.session_state["zc_fig"] = None
        st.session_state["zc_stress_count"] = 0


    # 1) Graphe base (buckets)
    if show_curve:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=base_bucket_df["Bucket"],
            y=base_bucket_df["rate"],
            mode="lines+markers",
            name="ZC base",
            line=dict(color="#00C2FF", width=3),
        ))
        fig.update_layout(
            title="Courbe Zero-Coupon (Buckets)",
            xaxis_title="Bucket",
            yaxis_title="Taux",
            template="plotly_dark"
        )
        st.session_state["zc_fig"] = fig

    # 2) Ajout courbe stressée sur le même graphe (buckets)
    if add_stress_curve:
        if st.session_state.get("zc_fig") is None:
            st.warning("Clique d’abord sur **Afficher courbe ZC (buckets)**.")
        else:
            row_rate = stress_matrix[stress_matrix["Scenario"].astype(str) == scenario]
            if row_rate.empty:
                st.warning("Scénario introuvable dans la matrice de stress.")
            else:
                # mensuel -> bucket
                stress_month = {m: float(row_rate.iloc[0][f"M{m}"]) for m in range(1, 121)}
                stress_bucket_rates = [stress_month.get(m, np.nan) for m in BUCKET_MONTHS]

                color = STRESS_COLORS[st.session_state["zc_stress_count"] % len(STRESS_COLORS)]
                st.session_state["zc_stress_count"] += 1

                fig = st.session_state["zc_fig"]
                fig.add_trace(go.Scatter(
                    x=BUCKET_LABELS,
                    y=stress_bucket_rates,
                    mode="lines+markers",
                    name=f"ZC stressée ({scenario})",
                    line=dict(color=color, width=3),
                ))
                st.session_state["zc_fig"] = fig

    # 3) Affichage du graphe unique (base + stress)
    if st.session_state.get("zc_fig") is not None:
        st.plotly_chart(st.session_state["zc_fig"], use_container_width=True)

        # tableau buckets (base) pour contrôle
        st.dataframe(base_bucket_df, use_container_width=True)

    # 4) GAP taux fixé (par buckets)
    if show_static_gaps:
        empty_fs_static = build_empty_fs_projection(runoff_df)
        CRD_rate_flow_df = Fixed_rate_flows(empty_fs_static)
        CRD_rate_flow_df = convert_display_unit(CRD_rate_flow_df, unit)

        gap_df = fixed_rate_gap(CRD_rate_flow_df)

        fig_gap = go.Figure()
        fig_gap.add_trace(go.Scatter(
            x=gap_df["Bucket"],
            y=gap_df["GAP (Passif - Actif)"],
            mode="lines+markers",
            name="GAP taux fixé",
            line=dict(color="#00C2FF", width=3),
        ))
        fig_gap.add_hline(y=0)

        fig_gap.update_layout(
            title="Courbe du GAP en taux fixé (Buckets)",
            xaxis_title="Bucket",
            yaxis_title=f"GAP ({unit})",
            template="plotly_dark"
        )

        st.plotly_chart(fig_gap, use_container_width=True)
        st.dataframe(gap_df, use_container_width=True)
