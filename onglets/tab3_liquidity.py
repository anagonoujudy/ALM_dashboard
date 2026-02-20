import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.graph_objects as go

from onglets.backend.Static_and_stress_flow import *
# =========================
# Helpers
# =========================
def _pmt(rate_month, nper, pv):
    if nper <= 0:
        return 0.0
    if abs(rate_month) < 1e-12:
        return pv / nper
    return (rate_month * pv) / (1 - (1 + rate_month) ** (-nper))


def _reorder_m_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    base_cols = [c for c in df.columns if not str(c).startswith("M")]
    m_cols = ["M0"] + [f"M{i}" for i in range(1, 121) if f"M{i}" in df.columns]
    ordered = [c for c in base_cols if c in df.columns] + [c for c in m_cols if c in df.columns]
    for c in df.columns:
        if c not in ordered:
            ordered.append(c)
    return df[ordered]


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


def df_to_excel_bytes(df: pd.DataFrame, sheet_name="flows") -> bytes:
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


# =========================
# Liquidity flows (3 views)
# =========================
def liquidity_flows(financial_statement: pd.DataFrame):
    CRD_flow_df = financial_statement.copy()
    Cash_Flow_df = financial_statement.copy()
    Interest_Flow_df = financial_statement.copy()

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

            elif "90%-20%*t" in law:
                crd_i = max(M0 * (0.90 - 0.20 * i), 0.0) if i <= 4 else 0.0

            elif "exp" in law:
                crd_i = M0 * 0.90 * np.exp(-0.20 * i)

            else:
                crd_i = 0.0

            CRD_flow_df.at[idx, col] = crd_i

            cash_i = (-crd_i + prev_crd) if (n > 0 and i < n) else 0.0
            Cash_Flow_df.at[idx, col] = cash_i

            int_i = (prev_crd * r_m) if (n > 0 and i < n) else 0.0
            Interest_Flow_df.at[idx, col] = int_i

            prev_crd = crd_i

    return _reorder_m_cols(CRD_flow_df), _reorder_m_cols(Cash_Flow_df), _reorder_m_cols(Interest_Flow_df)


# =========================
# Gap
# =========================
def liquidity_gap_from_flow_df(flow_df: pd.DataFrame) -> pd.DataFrame:
    bdf = to_bucket_view(flow_df)
    bucket_cols = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]

    if "Bilan" not in bdf.columns:
        return pd.DataFrame({"Bucket": bucket_cols, "Gap": [0.0] * len(bucket_cols)})

    side = bdf["Bilan"].astype(str).str.strip().str.upper()

    if "Poste du bilan" in bdf.columns:
        mask_exclude_equity = bdf["Poste du bilan"].astype(str).str.strip().str.lower().eq("capitaux propres")
    else:
        mask_exclude_equity = pd.Series(False, index=bdf.index)

    bdf_gap = bdf.loc[~mask_exclude_equity].copy()
    side_gap = side.loc[~mask_exclude_equity]

    actifs = bdf_gap.loc[side_gap == "ACTIF", bucket_cols].sum(axis=0)
    passifs = bdf_gap.loc[side_gap == "PASSIF", bucket_cols].sum(axis=0)

    gap = passifs - actifs
    return pd.DataFrame({"Bucket": bucket_cols, "Gap": gap.values})


# =========================
# TAB3 UI (no sidebar)
# =========================
def render3():
    if st.session_state.get("runoff_df") is None:
        st.warning("Charge d’abord le fichier Excel dans l’onglet 'Load Data'.")
        return
    if st.session_state.get("stress_liquidity_df") is None:
        st.warning("Il manque la feuille **Stress test de liquidité**.")
        return

    runoff_df = st.session_state["runoff_df"]
    stress_df = st.session_state["stress_liquidity_df"]

    st.title("Analyse Statique")

    BTN = "tab3_"

    c1, c2, c3, c4 = st.columns(4)
    unit = c1.selectbox("**Unité**", ["KEUR", "EUR", "MEUR", "GEUR"], index=0)
    source = c2.selectbox("**Source**", ["Statique", "Stressé"], index=0)
    scenario = c3.selectbox("**Scénario**", ["idiosyncratique", "systémique", "combiné"], index=0)
    view = c4.selectbox("**Vue**", ["Vision CRD", " ", ""], index=0)

    st.session_state["unit_out"] = unit

    # ================= Helpers =================

    def run_static():
        empty_fs = build_empty_fs_projection(runoff_df)
        CRD, CASH, INT = liquidity_flows(empty_fs)

        st.session_state["CRD_flow_df"] = CRD
        st.session_state["Cash_Flow_df"] = CASH
        st.session_state["Interest_Flow_df"] = INT

    def run_stress(scen):
        empty_fs = build_empty_fs_projection(runoff_df)
        CRD, CASH, INT = liquidity_flows(empty_fs)
        apply_liquidity_stress(CRD, stress_df, scen)
        st.session_state["last_stress_scenario"] = scen

    # ================= Boutons =================

    with st.expander("Boutons", expanded=True):
        b1, b2, b3 = st.columns(3)
        run_selected = b1.button("Projeter", key=f"{BTN}run")
        show_gaps = b2.button("Comparer Gaps", key=f"{BTN}gaps")
        prepare_download = b3.button("Exporter", key=f"{BTN}export")

    # ================= Calcul principal =================

    if run_selected:
        if source == "Statique":
            run_static()
            st.success("Projection statique calculée ✅")
        else:
            run_stress(scenario)
            st.success("Projection stressée calculée ✅")

    # =====================================================
    # Visionner Gaps (mode dédié)
    # =====================================================
    if show_gaps:
        run_static()
        run_stress(scenario)

        st.subheader("Écoulement Statique")
        df_stat = to_bucket_view(convert_display_unit(st.session_state["CRD_flow_df"], unit))
        st.dataframe(df_stat, use_container_width=True)

        st.subheader(f"Écoulement Stressé ({scenario})")
        df_str = to_bucket_view(convert_display_unit(st.session_state["Stress_CRD_flow_df"], unit))
        st.dataframe(df_str, use_container_width=True)

        BUCKET_ORDER = [f"M{i}" for i in range(12)] + [f"{y}Y" for y in range(1, 11)]
        factor = _unit_factor_from_KEUR(unit)

        gap_static = liquidity_gap_from_flow_df(st.session_state["CRD_flow_df"])
        gap_static["Gap"] *= factor
        gap_static = gap_static[gap_static["Bucket"].isin(BUCKET_ORDER)]

        gap_stress = liquidity_gap_from_flow_df(st.session_state["Stress_CRD_flow_df"])
        gap_stress["Gap"] *= factor
        gap_stress = gap_stress[gap_stress["Bucket"].isin(BUCKET_ORDER)]

        x = gap_static["Bucket"].astype(str).tolist()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x, y=gap_static["Gap"],
            mode="lines+markers",
            name="Gap statique",
            line=dict(color="#00C2FF", width=3)
        ))
        fig.add_trace(go.Scatter(
            x=x, y=gap_stress["Gap"],
            mode="lines+markers",
            name=f"Gap stressé ({scenario})",
            line=dict(color="#FF4D6D", width=3)
        ))

        fig.update_layout(
            title=f"Gap de liquidité Statique vs Stressé ({scenario})",
            xaxis_title="Buckets",
            yaxis_title=f"Gap ({unit})",
            template="plotly_dark",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=20, r=20, t=60, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(pd.DataFrame({
            "Bucket": gap_static["Bucket"],
            "Gap statique": gap_static["Gap"],
            f"Gap stressé ({scenario})": gap_stress["Gap"]
        }), use_container_width=True)

        return

    # =====================================================
    # Affichage standard
    # =====================================================
    if source == "Statique":
        mapper = {
            "Vision CRD": ("CRD_flow_df", "CRD_Statique"),
            "Vision Cash Flow": ("Cash_Flow_df", "CashFlow_Statique"),
            "Vision Intérêts": ("Interest_Flow_df", "Interets_Statique"),
        }
    else:
        mapper = {
            "Vision CRD": ("Stress_CRD_flow_df", "CRD_Stresse"),
            "Vision Cash Flow": ("Stress_Cash_Flow_df", "CashFlow_Stresse"),
            "Vision Intérêts": ("Stress_Interest_Flow_df", "Interets_Stresse"),
        }

    key_df, sheet = mapper[view]
    df_show = st.session_state.get(key_df)

    if df_show is None:
        st.info("Clique sur **Projeter ou Comparer Gaps**.")
        return

    df_disp = to_bucket_view(convert_display_unit(df_show.copy(), unit))
    st.subheader(f"Ecoulement {source} — {view}")
    st.dataframe(df_disp, use_container_width=True)

    # ================= Gap Plotly (même style que Visionner Gaps) =================

    factor = _unit_factor_from_KEUR(unit)
    BUCKET_ORDER = [f"M{i}" for i in range(12)] + [f"{y}Y" for y in range(1, 11)]

    gap_static = None
    gap_stress = None

    if st.session_state.get("CRD_flow_df") is not None:
        gap_static = liquidity_gap_from_flow_df(st.session_state["CRD_flow_df"])
        gap_static["Gap"] *= factor
        gap_static = gap_static[gap_static["Bucket"].isin(BUCKET_ORDER)]

    if st.session_state.get("Stress_CRD_flow_df") is not None:
        gap_stress = liquidity_gap_from_flow_df(st.session_state["Stress_CRD_flow_df"])
        gap_stress["Gap"] *= factor
        gap_stress = gap_stress[gap_stress["Bucket"].isin(BUCKET_ORDER)]

    scen = st.session_state.get("last_stress_scenario", scenario)

    fig = go.Figure()

    if gap_static is not None:
        fig.add_trace(go.Scatter(
            x=gap_static["Bucket"],
            y=gap_static["Gap"],
            mode="lines+markers",
            name="Gap statique",
            line=dict(color="#00C2FF", width=3)
        ))

    if gap_stress is not None:
        fig.add_trace(go.Scatter(
            x=gap_stress["Bucket"],
            y=gap_stress["Gap"],
            mode="lines+markers",
            name=f"Gap stressé ({scen})",
            line=dict(color="#FF4D6D", width=3)
        ))

    if len(fig.data) > 0:
        fig.update_layout(
            title=f"Gap de liquidité — Statique vs Stressé ({scen})",
            xaxis_title="Buckets",
            yaxis_title=f"Gap ({unit})",
            template="plotly_dark",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=20, r=20, t=60, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)

        if gap_static is not None and gap_stress is not None:
            st.dataframe(pd.DataFrame({
                "Bucket": gap_static["Bucket"],
                "Gap statique": gap_static["Gap"],
                f"Gap stressé ({scen})": gap_stress["Gap"]
            }), use_container_width=True)

    # ================= Export =================

    if prepare_download:
        xls = df_to_excel_bytes(df_disp, sheet)
        st.download_button(
            "Télécharger Excel",
            data=xls,
            file_name=f"{sheet}_{unit}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{BTN}dl"
        )