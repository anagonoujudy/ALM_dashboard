import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from onglets.backend.statement_analysis import Build_statement_data, _fmt_amount, _ratio_table, _kpi_from_statement, _fmt_pct, _total_categorie, _total_cote, _dict_to_df
from onglets.backend.FixedRateFlow import *

# ============================================================
# CONSTANTES (ALM)
# ============================================================
POSTES_NON_SENSIBLES = [
    "Immobilisations corporelles et incorporelles",
    "Capital souscrit",
    "Prime d'émission",
    "Réserves",
    "Report à nouveau",
    "Résultat de l'exercice",
    "Dividende",
    "FRBG",
]

MONTHS = list(range(1, 121))
M_COLS = [f"M{m}" for m in MONTHS]
CF_COLS = [f"CF_{m}" for m in MONTHS]

def analyze_balance_sheet_structure(statement):
    total_actif = _total_cote(statement, "ACTIF")
    total_passif = _total_cote(statement, "PASSIF")

    return {
        "Créances ETS  de Crédit / Total Actif": _total_categorie(statement, "ACTIF", "CREANCES SUR LES ETS DE CREDIT") / total_actif if total_actif else 0.0,
        "Créances sur la clientèle / Total Actif": _total_categorie(statement, "ACTIF", "CREANCES SUR LA CLIENTELE") / total_actif if total_actif else 0.0,
        "Investissements financiers/ Total Actif": _total_categorie(statement, "ACTIF", "TITRE D'INVESTISSEMENT") / total_actif if total_actif else 0.0,
        "Dépôts Clientèles / Total Passif": _total_categorie(statement, "PASSIF", "CPTES CREDITEURS DE LA CLIENTELE") / total_passif if total_passif else 0.0,
        "Dettes envers ETS  de crédit / Total Passif": _total_categorie(statement, "PASSIF", "DETTES ENVERS ETS DE CREDIT") / total_passif if total_passif else 0.0,
        "Financement LT / Total Passif": _total_categorie(statement, "PASSIF", "FINANCEMENT") / total_passif if total_passif else 0.0,
    }


def analyze_liquidity_position(statement):
    total_actif = _total_cote(statement, "ACTIF")
    total_passif = _total_cote(statement, "PASSIF")

    creances_clientele = _total_categorie(statement, "ACTIF", "CREANCES SUR LA CLIENTELE")
    caisse_bc = _total_categorie(statement, "ACTIF", "CAISSE, BANQUES CENTRALES")
    inv_fin = statement["ACTIF"]["TITRE D'INVESTISSEMENT"]["Investissements financiers"]
    hqla = caisse_bc + inv_fin

    depots = _total_categorie(statement, "PASSIF", "CPTES CREDITEURS DE LA CLIENTELE")
    dettes_ets_vue = statement["PASSIF"]["DETTES ENVERS ETS DE CREDIT"]["A vue"]
    depots_vue = statement["PASSIF"]["CPTES CREDITEURS DE LA CLIENTELE"]["A vue"]
    dav_eibv = dettes_ets_vue + depots_vue

    fonds_propres = _total_categorie(statement, "PASSIF", "FONDS PROPRES")

    return {
        "Créances sur la clientèle / Dépôts Clientèles ": creances_clientele / depots if depots else 0.0,
        "HQLA / Total Actif": hqla / total_actif if total_actif else 0.0,
        "HQLA / Dépôts Clientèles": hqla / depots if depots else 0.0,
        "HQLA / (DAV + Interbancaire vue)": hqla / dav_eibv if dav_eibv else 0.0,
        "Fonds propres / Total Passif": fonds_propres / total_passif if total_passif else 0.0,
    }


def analyze_funding_structure(statement):
    total_passif = _total_cote(statement, "PASSIF")
    dettes_ets_credit = _total_categorie(statement, "PASSIF", "DETTES ENVERS ETS DE CREDIT")

    depots_total = _total_categorie(statement, "PASSIF", "CPTES CREDITEURS DE LA CLIENTELE")
    depots_terme = statement["PASSIF"]["CPTES CREDITEURS DE LA CLIENTELE"]["A terme"]
    depots_vue = statement["PASSIF"]["CPTES CREDITEURS DE LA CLIENTELE"]["A vue"]

    return {
        "Dettes envers ETS  de crédit / Total Passif": dettes_ets_credit / total_passif if total_passif else 0.0,
        "DAT/ Dépôts Clientèles ": depots_terme / depots_total if depots_total else 0.0,
        "DAV / Dépôts Clientèles ": depots_vue / depots_total if depots_total else 0.0,
    }




# ============================================================
# BUCKET VIEW + GAP (pour affichage)
# ============================================================
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


def fixed_rate_gap(rate_flow_df: pd.DataFrame) -> pd.DataFrame:
    bdf = to_bucket_view(rate_flow_df)
    bucket_cols = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]

    if "Bilan" not in bdf.columns:
        return pd.DataFrame({"Bucket": bucket_cols, "GAP (Passif - Actif)": [0.0] * len(bucket_cols)})

    mask_exclude = pd.Series(False, index=bdf.index)
    if "Poste du bilan" in bdf.columns:
        mask_exclude |= bdf["Poste du bilan"].astype(str).str.strip().str.lower().eq("capitaux propres")
    if "Categorie" in bdf.columns:
        mask_exclude |= bdf["Categorie"].astype(str).str.strip().str.lower().eq("capitaux propres")

    bdf = bdf.loc[~mask_exclude].copy()

    side = bdf["Bilan"].astype(str).str.strip().str.upper()
    actifs = bdf.loc[side == "ACTIF", bucket_cols].sum(axis=0)
    passifs = bdf.loc[side == "PASSIF", bucket_cols].sum(axis=0)

    gap = passifs - actifs
    return pd.DataFrame({"Bucket": bucket_cols, "GAP (Passif - Actif)": gap.values})


# ============================================================
# ✅ GAP MENSUEL COMPLET (M1..M120) POUR SENSIBILITÉ MNI
# ============================================================
def fixed_rate_gap_monthly(rate_flow_df: pd.DataFrame) -> pd.DataFrame:
    """
    GAP mensuel complet : Bucket = M1..M120
    """
    df = rate_flow_df.copy()
    side = df["Bilan"].astype(str).str.strip().str.upper()

    rows = []
    for m in range(1, 121):
        col = f"M{m}"
        actif = float(df.loc[side == "ACTIF", col].sum())
        passif = float(df.loc[side == "PASSIF", col].sum())
        rows.append({"Bucket": col, "GAP (Passif - Actif)": passif - actif})

    return pd.DataFrame(rows)


# ============================================================
# 3) ZC + STRESS (on calcule ZC mais on ne l'affiche pas)
# ============================================================
def Interpolate_ZC_Rate(zc_data_df: pd.DataFrame) -> pd.DataFrame:
    def to_months(x):
        x = str(x).lower().strip()
        n = int(x.split()[0])
        if "mois" in x:
            return n
        if "an" in x:
            return n * 12
        raise ValueError(f"Maturité non reconnue : {x}")

    zc = zc_data_df.copy()
    zc.columns = range(zc.shape[1])
    zc.columns = zc.iloc[0]
    zc = zc.iloc[1:].reset_index(drop=True)
    zc = zc.iloc[:, :-1]
    zc.columns = zc.columns.astype(str).str.strip()

    zc["maturity_month"] = zc["Maturité"].apply(to_months)
    zc = zc.sort_values("maturity_month")

    results = []
    for m in MONTHS:
        if m in zc["maturity_month"].values:
            r = float(zc.loc[zc["maturity_month"] == m, "Zero Coupon"].values[0])
        else:
            lower = zc[zc["maturity_month"] < m].iloc[-1]
            upper = zc[zc["maturity_month"] > m].iloc[0]
            m1, r1 = float(lower["maturity_month"]), float(lower["Zero Coupon"])
            m2, r2 = float(upper["maturity_month"]), float(upper["Zero Coupon"])
            r = r1 + ((m - m1) / (m2 - m1)) * (r2 - r1)

        DF = 1 / ((1 + r) ** (m / 12))
        results.append({"month": m, "zc_rate": r, "discount_factor": DF})

    return pd.DataFrame(results)


def apply_rate_stress_interleaved(stress_rate_df: pd.DataFrame, zc_rate: pd.DataFrame) -> pd.DataFrame:
    base_rates = dict(zip(zc_rate["month"], zc_rate["zc_rate"]))
    meta_cols = stress_rate_df.columns[:3]
    shock_cols = stress_rate_df.columns[3:123]  # 120 mois

    rows = []
    for _, row in stress_rate_df.iterrows():
        scenario_name = row[meta_cols[2]]

        rate_row = {"Scenario": scenario_name}
        df_row = {"Scenario": scenario_name + "_DF"}

        for m in MONTHS:
            shock = float(row[shock_cols[m-1]])
            base = float(base_rates[m])
            stressed_rate = base + shock
            stressed_df = 1 / ((1 + stressed_rate) ** (m / 12))

            rate_row[f"M{m}"] = stressed_rate
            df_row[f"M{m}"] = stressed_df

        rows.append(rate_row)
        rows.append(df_row)

    return pd.DataFrame(rows)


# ============================================================
# 4) CASH FLOWS + VAN / EVE / MNI
# ============================================================
def compute_cash_flows(rate_flow_df: pd.DataFrame) -> pd.DataFrame:
    df = rate_flow_df.copy()
    monthly_rate = df["Taux d'intérèt moyen"] / 12.0

    cf_dict = {}
    for m in MONTHS:
        prev = "M0" if m == 1 else f"M{m-1}"
        curr = f"M{m}"
        cap = df[prev] - df[curr]
        interest = monthly_rate * df[prev]
        cf_dict[f"CF_{m}"] = cap + interest

    return pd.concat([df, pd.DataFrame(cf_dict)], axis=1)


def compute_van_alm(rate_flow_df: pd.DataFrame, actuarial_zc_rate: pd.DataFrame) -> pd.DataFrame:
    df_cf = compute_cash_flows(rate_flow_df)
    df_dict = dict(zip(actuarial_zc_rate["month"], actuarial_zc_rate["discount_factor"]))

    rows = []
    for m in MONTHS:
        df_m = float(df_dict[m])
        actif = float(df_cf[df_cf["Bilan"] == "ACTIF"][f"CF_{m}"].sum())
        passif = float(df_cf[df_cf["Bilan"] == "PASSIF"][f"CF_{m}"].sum())
        rows.append({"Month": m, "VAN centrale": (actif - passif) * df_m})

    van_df = pd.DataFrame(rows)
    van_ct = van_df.loc[van_df["Month"].between(1, 12), "VAN centrale"].sum()
    van_mt = van_df.loc[van_df["Month"].between(13, 60), "VAN centrale"].sum()
    van_lt = van_df.loc[van_df["Month"].between(61, 120), "VAN centrale"].sum()

    summary = pd.DataFrame({
        "Month": ["VAN Court Terme (1-12)", "VAN Moyen Terme (13-60)", "VAN Long Terme (61-120)"],
        "VAN centrale": [van_ct, van_mt, van_lt],
    })
    return pd.concat([van_df, summary], ignore_index=True)


def compute_van_stress(rate_flow_df: pd.DataFrame, stress_matrix: pd.DataFrame) -> pd.DataFrame:
    df_cf = compute_cash_flows(rate_flow_df)
    df_only = stress_matrix[stress_matrix["Scenario"].astype(str).str.endswith("_DF")].copy()

    results = []
    for _, row in df_only.iterrows():
        scenario = str(row["Scenario"]).replace("_DF", "")
        df_dict = {m: float(row.get(f"M{m}", 0.0)) for m in MONTHS}

        van_month = []
        for m in MONTHS:
            actif = float(df_cf[df_cf["Bilan"] == "ACTIF"][f"CF_{m}"].sum())
            passif = float(df_cf[df_cf["Bilan"] == "PASSIF"][f"CF_{m}"].sum())
            van_month.append((actif - passif) * df_dict[m])

        results.append({
            "Scenario": scenario,
            "VAN_Stressee_CT": sum(van_month[0:12]),
            "VAN_Stressee_MT": sum(van_month[12:60]),
            "VAN_Stressee_LT": sum(van_month[60:120]),
            **{f"M{m}": van_month[m-1] for m in MONTHS}
        })

    return pd.DataFrame(results)


def compute_eve_centrale(df_cf_eve: pd.DataFrame, actuarial_zc_rate: pd.DataFrame) -> pd.DataFrame:
    df_dict = dict(zip(actuarial_zc_rate["month"], actuarial_zc_rate["discount_factor"]))

    rows = []
    for m in MONTHS:
        df_m = float(df_dict[m])
        actif = float(df_cf_eve[df_cf_eve["Bilan"] == "ACTIF"][f"CF_{m}"].sum())
        passif = float(df_cf_eve[df_cf_eve["Bilan"] == "PASSIF"][f"CF_{m}"].sum())
        rows.append({"Month": m, "EVE centrale": (actif - passif) * df_m})

    eve_df = pd.DataFrame(rows)
    eve_ct = eve_df.loc[eve_df["Month"].between(1, 12), "EVE centrale"].sum()
    eve_mt = eve_df.loc[eve_df["Month"].between(13, 60), "EVE centrale"].sum()
    eve_lt = eve_df.loc[eve_df["Month"].between(61, 120), "EVE centrale"].sum()

    summary = pd.DataFrame({
        "Month": ["EVE Court Terme (1-12)", "EVE Moyen Terme (13-60)", "EVE Long Terme (61-120)"],
        "EVE centrale": [eve_ct, eve_mt, eve_lt],
    })
    return pd.concat([eve_df, summary], ignore_index=True)


def compute_eve_stress(rate_flow_df: pd.DataFrame, stress_matrix: pd.DataFrame, postes_non_sensibles: list) -> pd.DataFrame:
    df_cf = compute_cash_flows(rate_flow_df)

    df_cf_eve = df_cf.copy()
    if "Poste du bilan" in df_cf_eve.columns:
        mask = df_cf_eve["Poste du bilan"].isin(postes_non_sensibles)
        for m in MONTHS:
            df_cf_eve.loc[mask, f"CF_{m}"] = 0.0

    results = []
    for i in range(0, len(stress_matrix), 2):
        scenario = str(stress_matrix.iloc[i]["Scenario"])
        df_row = stress_matrix.iloc[i + 1]

        eve_month = []
        for m in MONTHS:
            df_m = float(df_row.get(f"M{m}", 0.0))
            actif = float(df_cf_eve[df_cf_eve["Bilan"] == "ACTIF"][f"CF_{m}"].sum())
            passif = float(df_cf_eve[df_cf_eve["Bilan"] == "PASSIF"][f"CF_{m}"].sum())
            eve_month.append((actif - passif) * df_m)

        results.append({
            "Scenario": scenario,
            "EVE_Stressee_CT": sum(eve_month[0:12]),
            "EVE_Stressee_MT": sum(eve_month[12:60]),
            "EVE_Stressee_LT": sum(eve_month[60:120]),
        })

    return pd.DataFrame(results)


def compute_mni_stock(rate_flow_df: pd.DataFrame, horizon=120) -> pd.DataFrame:
    df = rate_flow_df.copy()
    out = []

    for m in range(1, horizon + 1):
        prev = f"M{m-1}"
        df["Interest"] = df[prev] * df["Taux d'intérèt moyen"] / 12.0

        i_actif = float(df[df["Bilan"] == "ACTIF"]["Interest"].sum())
        i_passif = float(df[df["Bilan"] == "PASSIF"]["Interest"].sum())

        out.append({"Month": m, "MNI_stock": i_actif - i_passif})

    mni_df = pd.DataFrame(out)
    mni_ct = mni_df.loc[mni_df["Month"].between(1, 12), "MNI_stock"].sum()
    mni_mt = mni_df.loc[mni_df["Month"].between(13, 60), "MNI_stock"].sum()
    mni_lt = mni_df.loc[mni_df["Month"].between(61, 120), "MNI_stock"].sum()

    summary = pd.DataFrame({
        "Month": ["MNI Court Terme (1-12)", "MNI Moyen Terme (13-60)", "MNI Long Terme (61-120)"],
        "MNI_stock": [mni_ct, mni_mt, mni_lt]
    })
    return pd.concat([mni_df, summary], ignore_index=True)


# ============================================================
# ✅ SENSIBILITÉ MNI (FIXÉE) : utilise GAP mensuel M1..M120
# ============================================================
def compute_mni_sensitivity_full(rate_flow_df: pd.DataFrame, stress_rates_only: pd.DataFrame):
    gap_m = fixed_rate_gap_monthly(rate_flow_df)  # M1..M120
    gap_map = dict(zip(gap_m["Bucket"], gap_m["GAP (Passif - Actif)"]))

    bucket_rows = []
    summary_rows = []

    for _, row in stress_rates_only.iterrows():
        scenario = str(row["Scenario"])
        data = []

        for m in range(1, 121):
            bucket_label = f"M{m}"
            gap_val = float(gap_map.get(bucket_label, 0.0))
            shock = float(row.get(bucket_label, 0.0))
            sensi = gap_val * shock / 12.0
            data.append({"Scenario": scenario, "Month": m, "Sensi_MNI": sensi})

        tmp = pd.DataFrame(data)
        s_ct = float(tmp.loc[tmp["Month"].between(1, 12), "Sensi_MNI"].sum())
        s_mt = float(tmp.loc[tmp["Month"].between(13, 60), "Sensi_MNI"].sum())
        s_lt = float(tmp.loc[tmp["Month"].between(61, 120), "Sensi_MNI"].sum())

        bucket_rows.append(tmp)
        summary_rows.append({
            "Scenario": scenario,
            "Sensi_MNI_CT": s_ct,
            "Sensi_MNI_MT": s_mt,
            "Sensi_MNI_LT": s_lt,
            "Sensi_MNI_Totale": s_ct + s_mt + s_lt
        })

    return pd.concat(bucket_rows, ignore_index=True), pd.DataFrame(summary_rows)


# ============================================================
# ✅ PLOTS : uniquement en buckets (GAP + MNI sur la même ligne)
# ============================================================
def series_to_bucket_df(values_by_month: pd.Series, value_name: str) -> pd.DataFrame:
    rows = []
    for m in range(1, 12):
        rows.append({"Bucket": f"M{m}", value_name: float(values_by_month.loc[m])})
    for y in range(1, 11):
        m = 12 * y
        rows.append({"Bucket": f"{y}Y", value_name: float(values_by_month.loc[m])})
    return pd.DataFrame(rows)


def _plot_bucket_line(df: pd.DataFrame, y_col: str, title: str, ytitle: str):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Bucket"], y=df[y_col], mode="lines+markers", name=y_col))
    fig.add_hline(y=0)
    fig.update_layout(title=title, xaxis_title="Buckets", yaxis_title=ytitle, height=420)
    return fig


# ============================================================
# 6) RENDER (TAB KPI)
# ============================================================
def render_tab2_kpi():

    if st.session_state.get("pmt_df") is None:
        st.warning("Charge d’abord le fichier Excel (PMT requis).")
        return
    st.title("KPI & Risk Dashboard")
    #unit = st.selectbox("Unité d'affichage", ["KEUR", "EUR", "MEUR", "GEUR"], index=0, key="kpi_unit")
    
    st.markdown("##### Unité d'affichage")
    c1, c2, c3 = st.columns(3)
    unit = c1.selectbox("", ["KEUR","EUR"], label_visibility="collapsed")
    # ==========================================================
    # A) KPI Bilan (PMT)
    # ==========================================================
    pmt_df = st.session_state["pmt_df"]
    statement = Build_statement_data(pmt_df)

    bs_ratios = analyze_balance_sheet_structure(statement)
    liq_ratios = analyze_liquidity_position(statement)
    fund_ratios = analyze_funding_structure(statement)
    kpi = _kpi_from_statement(statement)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("**Total Actif**", _fmt_amount(kpi["Total Actif"], unit))
    c2.metric("**Total Passif**", _fmt_amount(kpi["Total Passif"], unit))
    c3.metric("**Fonds propres**", _fmt_amount(kpi["Fonds propres (Tier1 proxy)"], unit))
    c4.metric("**HQLA**", _fmt_amount(kpi["HQLA"], unit))
    c5.metric("**Dépôts clientèle**", _fmt_amount(kpi["Dépôts clientèle"], unit))

    st.markdown("---")
    colA, colB, colC = st.columns(3)
    with colA:
        _ratio_table(bs_ratios, "Structure de la banque")
    with colB:
        _ratio_table(liq_ratios, "Liquidité à priori")
    with colC:
        _ratio_table(fund_ratios, "Financement de la banque")

    # st.subheader("Financement (ratios)")
    # df_fund = _dict_to_df(fund_ratios, "Ratio")
    # df_fund["Ratio"] = df_fund["Ratio"].apply(_fmt_pct)
    # st.dataframe(df_fund, use_container_width=True, hide_index=True)

    # ==========================================================
    # B) Risque de taux : GAP, VAN, EVE, MNI & SOT
    # ==========================================================
    st.markdown("---")
    st.subheader("Risque de taux: GAP, VAN, EVE, MNI & SOT")

    missing = []
    if st.session_state.get("runoff_df") is None: missing.append("runoff_df")
    if st.session_state.get("zc_data_df") is None: missing.append("zc_data_df")
    if st.session_state.get("stress_rate_df") is None: missing.append("stress_rate_df")
    if st.session_state.get("bilan") is None: missing.append("bilan")

    if missing:
        st.info("Données manquantes : " + ", ".join(missing) + " (onglet Load Data).")
        return

    #runoff_df = st.session_state["runoff_df"]
    runoff_df = st.session_state["runoff_df"] = st.session_state["runoff_df"].loc[~st.session_state["runoff_df"]["Poste du bilan"].astype(str).str.lower().str.strip().eq("capitaux propres")].reset_index(drop=True)

    bilan_df = st.session_state["bilan"]          # conservé (même si runoff suffit)
    stress_df = st.session_state["stress_rate_df"]
    zc_df = st.session_state["zc_data_df"].copy()

    # --- Projection taux fixe
    proj = build_rate_projection(bilan_df, runoff_df)
    rate_flow_df = Fixed_rate_flows(proj)

    # --- Contrôle équilibre (affichage)
    sum_actif = rate_flow_df[rate_flow_df["Bilan"] == "ACTIF"]["M0"].sum()
    sum_passif = rate_flow_df[rate_flow_df["Bilan"] == "PASSIF"]["M0"].sum()
    ecart = sum_actif - sum_passif

    c1, c2, c3 = st.columns(3)
    # c1.metric("M0 Actif", _fmt_amount(sum_actif, unit))
    # c2.metric("M0 Passif", _fmt_amount(sum_passif, unit))
    c1.metric("**Écart (Actif - Passif)**", _fmt_amount(ecart, unit))

    # ==========================================================
    # ✅ GAP + MNI SUR LA MÊME LIGNE (EN BUCKETS)
    # ==========================================================
    gap_df = fixed_rate_gap(rate_flow_df)

    mni_stock_df = compute_mni_stock(rate_flow_df, horizon=120)
    mni_curve = mni_stock_df[mni_stock_df["Month"].apply(lambda x: isinstance(x, int))].copy()
    mni_series = mni_curve.set_index("Month")["MNI_stock"]
    mni_bucket_df = series_to_bucket_df(mni_series, "MNI_stock")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            _plot_bucket_line(
                gap_df[gap_df["Bucket"] != "M0"].copy(),
                "GAP (Passif - Actif)",
                "GAP en taux fixe",
                "GAP"
            ),
            use_container_width=True
        )
    with right:
        st.plotly_chart(
            _plot_bucket_line(
                mni_bucket_df,
                "MNI_stock",
                "MNI du stock",
                "MNI"
            ),
            use_container_width=True
        )

    # ==========================================================
    # ZC (interpolation) : calcul OK, mais on ne plot pas
    # ==========================================================
    actuarial_zc_rate = Interpolate_ZC_Rate(zc_df)

    # --- Stress matrix (taux + DF)
    stress_matrix = apply_rate_stress_interleaved(stress_df, actuarial_zc_rate)
    stress_rates_only = stress_matrix[~stress_matrix["Scenario"].astype(str).str.endswith("_DF")].copy()

    # ==========================================================
    # VAN
    # ==========================================================
    van_central = compute_van_alm(rate_flow_df, actuarial_zc_rate)
    van_ct = van_central.loc[van_central["Month"] == "VAN Court Terme (1-12)", "VAN centrale"].values[0]
    van_mt = van_central.loc[van_central["Month"] == "VAN Moyen Terme (13-60)", "VAN centrale"].values[0]
    van_lt = van_central.loc[van_central["Month"] == "VAN Long Terme (61-120)", "VAN centrale"].values[0]

    van_stress = compute_van_stress(rate_flow_df, stress_matrix)
    van_stress["Sensibilité_CT"] = van_stress["VAN_Stressee_CT"] - van_ct
    van_stress["Sensibilité_MT"] = van_stress["VAN_Stressee_MT"] - van_mt
    van_stress["Sensibilité_LT"] = van_stress["VAN_Stressee_LT"] - van_lt

    st.markdown("### VAN (Earnings Value / NPV)")
    c1, c2, c3 = st.columns(3)
    c1.metric("**VAN centrale CT**", _fmt_amount(van_ct, unit))
    c2.metric("**VAN centrale MT**", _fmt_amount(van_mt, unit))
    c3.metric("**VAN centrale LT**", _fmt_amount(van_lt, unit))

    st.write("**Sensibilités VAN (stress vs central)**")
    st.dataframe(
        van_stress[["Scenario", "Sensibilité_CT", "Sensibilité_MT", "Sensibilité_LT"]],
        use_container_width=True,
        hide_index=True
    )

    # ==========================================================
    # EVE
    # ==========================================================
    df_cf = compute_cash_flows(rate_flow_df)
    df_cf_eve = df_cf.copy()
    if "Poste du bilan" in df_cf_eve.columns:
        mask = df_cf_eve["Poste du bilan"].isin(POSTES_NON_SENSIBLES)
        for m in MONTHS:
            df_cf_eve.loc[mask, f"CF_{m}"] = 0.0

    eve_central = compute_eve_centrale(df_cf_eve, actuarial_zc_rate)
    eve_ct = eve_central.loc[eve_central["Month"] == "EVE Court Terme (1-12)", "EVE centrale"].values[0]
    eve_mt = eve_central.loc[eve_central["Month"] == "EVE Moyen Terme (13-60)", "EVE centrale"].values[0]
    eve_lt = eve_central.loc[eve_central["Month"] == "EVE Long Terme (61-120)", "EVE centrale"].values[0]

    eve_stress = compute_eve_stress(rate_flow_df, stress_matrix, POSTES_NON_SENSIBLES)
    eve_stress["Sensi_EVE_Totale"] = (
        (eve_stress["EVE_Stressee_CT"] - eve_ct) +
        (eve_stress["EVE_Stressee_MT"] - eve_mt) +
        (eve_stress["EVE_Stressee_LT"] - eve_lt)
    )

    tier1 = float(rate_flow_df.loc[rate_flow_df["Categorie"] == "FONDS PROPRES", "M0"].sum())
    min_sensi_eve = float(eve_stress["Sensi_EVE_Totale"].min()) if not eve_stress.empty else 0.0
    sot_eve = (min_sensi_eve / tier1) if tier1 else 0.0

    st.markdown("### EVE (Economic Value of Equity)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("**EVE centrale CT**", _fmt_amount(eve_ct, unit))
    c2.metric("**EVE centrale MT**", _fmt_amount(eve_mt, unit))
    c3.metric("**EVE centrale LT**", _fmt_amount(eve_lt, unit))
    c4.metric("**Tier 1 (proxy)**", _fmt_amount(tier1, unit))
    c5.metric("**SOT EVE (min)**", _fmt_pct(sot_eve))

    if abs(sot_eve) <= 0.15:
        st.success("✅ Conforme : SOT EVE ≤ 15%")
    else:
        st.warning("⚠️ Non conforme : dépassement du seuil 15%")

    st.write("**Résultats EVE stress (CT/MT/LT)**")
    st.dataframe(
        eve_stress[["Scenario", "EVE_Stressee_CT", "EVE_Stressee_MT", "EVE_Stressee_LT", "Sensi_EVE_Totale"]],
        use_container_width=True,
        hide_index=True
    )

    # ==========================================================
    # MNI : agrégats + SOT MNI
    # ==========================================================
    st.markdown("### Sensibilités MNI (stress) & SOT MNI")

    mni_bucket_df_full, mni_summary_df = compute_mni_sensitivity_full(rate_flow_df, stress_rates_only)

    min_sensi_mni = float(mni_summary_df["Sensi_MNI_Totale"].min()) if not mni_summary_df.empty else 0.0
    sot_mni = (min_sensi_mni / tier1) if tier1 else 0.0

    c1, c2 = st.columns(2)
    c1.metric("Sensi MNI minimale", _fmt_amount(min_sensi_mni, unit))
    c2.metric("SOT MNI (min)", _fmt_pct(sot_mni))

    if abs(sot_mni) <= 0.05:
        st.success("✅ Conforme : SOT MNI ≤ 5%")
    else:
        st.warning("⚠️ Non conforme : dépassement du seuil 5%")

    st.write("**Sensibilités MNI par scénario (agrégats)**")
    st.dataframe(mni_summary_df, use_container_width=True, hide_index=True)
