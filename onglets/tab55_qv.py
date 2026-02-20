import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ============================================================
# IMPORTS MOTEUR (à adapter à ton projet)
# ============================================================
# - Tab3 (statique + stress statique + gap statique)
from onglets.tab3_liquidity import (
    build_empty_fs_projection,
    liquidity_flows,
    apply_liquidity_stress,
    liquidity_gap_from_flow_df,
    _unit_factor_from_KEUR,
)

# - Tab5 (dynamique + stress dynamique + gap dynamique par année en buckets)
from onglets.tab5_dn import (
    clean_runoff,
    clean_taux,
    clean_pmt,
    build_dynamic_fs_projection,
    load_stress_raw,
    liquidity_flows_team_style,
    dynamic_liquidity_flows_from_crd,
    apply_dynamic_liquidity_stress,
    dynamic_liquidity_gap_bucket_by_year,  # <- ta nouvelle méthode (mensuel->buckets) déjà intégrée
)

# ============================================================
# CONSTANTES
# ============================================================

BUCKET_ORDER = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]


# ============================================================
# HELPERS QUICKLY VIEW
# ============================================================

def _gap_df_to_bucket_series(gap_df: pd.DataFrame) -> pd.Series:
    """
    Accepte un df de gap en buckets (Bucket/Gap) et retourne une série indexée sur BUCKET_ORDER.
    Si df vide ou mal formé -> renvoie des zéros.
    """
    if gap_df is None or getattr(gap_df, "empty", True):
        return pd.Series([0.0] * len(BUCKET_ORDER), index=BUCKET_ORDER)

    df = gap_df.copy()

    # fallback si jamais c'est "Mois" au lieu de "Bucket"
    if "Bucket" not in df.columns and "Mois" in df.columns:
        df = df.rename(columns={"Mois": "Bucket"})

    if "Bucket" not in df.columns or "Gap" not in df.columns:
        return pd.Series([0.0] * len(BUCKET_ORDER), index=BUCKET_ORDER)

    df["Bucket"] = df["Bucket"].astype(str)
    df["Gap"] = pd.to_numeric(df["Gap"], errors="coerce").fillna(0.0)

    df = df[df["Bucket"].isin(BUCKET_ORDER)].copy()
    df["Bucket"] = pd.Categorical(df["Bucket"], categories=BUCKET_ORDER, ordered=True)
    df = df.sort_values("Bucket")

    s = pd.Series(df["Gap"].values, index=df["Bucket"].astype(str).values)
    return s.reindex(BUCKET_ORDER).fillna(0.0)


def _ensure_required_data_for_static() -> bool:
    """Vérifie les prérequis statiques."""
    return st.session_state.get("runoff_df") is not None


def _ensure_required_data_for_static_stress() -> bool:
    """Vérifie les prérequis stress statique."""
    return st.session_state.get("runoff_df") is not None and st.session_state.get("stress_liquidity_df") is not None


def _ensure_required_data_for_dynamic() -> bool:
    """Vérifie les prérequis dynamiques."""
    return (
        st.session_state.get("runoff_df") is not None
        and st.session_state.get("bilan") is not None
        and st.session_state.get("pmt_df") is not None
        and st.session_state.get("stress_liquidity_df") is not None
    )


def _compute_gap_static_base() -> pd.DataFrame | None:
    """Calcule gap statique (CRD) en buckets."""
    if not _ensure_required_data_for_static():
        return None

    empty_fs = build_empty_fs_projection(st.session_state["runoff_df"])
    CRD_flow_df, _, _ = liquidity_flows(empty_fs)

    # (optionnel) sauvegarde si tu veux
    st.session_state["CRD_flow_df"] = CRD_flow_df

    return liquidity_gap_from_flow_df(CRD_flow_df)


def _compute_gap_static_stress(scenario: str) -> pd.DataFrame | None:
    """Calcule gap statique stressé (CRD) en buckets pour 1 scénario."""
    if not _ensure_required_data_for_static_stress():
        return None

    empty_fs = build_empty_fs_projection(st.session_state["runoff_df"])
    CRD_flow_df, _, _ = liquidity_flows(empty_fs)

    apply_liquidity_stress(CRD_flow_df, st.session_state["stress_liquidity_df"], scenario)

    stress_crd = st.session_state.get("Stress_CRD_flow_df")
    if stress_crd is None:
        # apply_liquidity_stress doit normalement produire cette clé
        return None

    return liquidity_gap_from_flow_df(stress_crd)


def _load_all_dynamic() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """
    Reprend la logique de Tab5 pour construire fs + stress_raw
    (sans UI, uniquement data wrangling)
    """
    if not _ensure_required_data_for_dynamic():
        return None, None

    runoff = st.session_state["runoff_df"].copy()
    runoff = runoff.rename(
        columns={
            "Poste du bilan": "Poste bilan",
            "Loi d'écoulement en liquidité": "Profil d’écoulement",
            "Durée moyenne (en mois)": "Maturité",
            "En liquidité": "Montant",
        }
    )

    taux_df = st.session_state["bilan"].copy()
    taux_df = taux_df.rename(columns={taux_df.columns[2]: "Poste bilan", taux_df.columns[4]: "Taux"})
    taux = taux_df[["Poste bilan", "Taux"]]

    pmt = st.session_state["pmt_df"].copy()

    runoff = clean_runoff(runoff)
    taux = clean_taux(taux)
    pmt = clean_pmt(pmt)

    fs = build_dynamic_fs_projection(runoff, taux, pmt)
    stress_raw = load_stress_raw()  # lit st.session_state["stress_liquidity_df"]
    return fs, stress_raw


def _compute_gap_dynamic_base(year: str) -> pd.DataFrame | None:
    """Calcule gap dynamique (NP=year) en buckets."""
    fs, _stress_raw = _load_all_dynamic()
    if fs is None:
        return None

    CRD_flow_df, _, _ = liquidity_flows_team_style(fs)
    dyn = dynamic_liquidity_flows_from_crd(CRD_flow_df, horizon=170)

    # Ta nouvelle méthode -> buckets
    return dynamic_liquidity_gap_bucket_by_year(dyn, year)


def _compute_gap_dynamic_stress(scenario: str, year: str) -> pd.DataFrame | None:
    """Calcule gap dynamique stressé (NP=year) en buckets."""
    fs, stress_raw = _load_all_dynamic()
    if fs is None or stress_raw is None:
        return None

    stressed_dyn = apply_dynamic_liquidity_stress(fs, stress_raw, scenario)
    return dynamic_liquidity_gap_bucket_by_year(stressed_dyn, year)


def _clear_quickly_cache(prefix: str = "quickly_gap_") -> None:
    """Supprime toutes les clés session_state relatives aux gaps quickly view."""
    keys_to_del = [k for k in st.session_state.keys() if str(k).startswith(prefix)]
    for k in keys_to_del:
        del st.session_state[k]


# ============================================================
# UI : ONGLET QUICKLY VIEW
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

def render_quickly_view():
    # ============== Prérequis ==============
    if st.session_state.get("runoff_df") is None:
        st.warning("Charge d’abord le fichier Excel dans l’onglet 'Load Data'.")
        return

    # Pour les courbes dynamiques (et stress dynamiques), il faut bilan + pmt
    # On ne bloque pas l'onglet : on avertit seulement si tu essaies d'ajouter une courbe qui en dépend.
    has_dynamic_inputs = (
        st.session_state.get("bilan") is not None
        and st.session_state.get("pmt_df") is not None
        and st.session_state.get("stress_liquidity_df") is not None
    )
    has_static_stress_inputs = st.session_state.get("stress_liquidity_df") is not None

    st.title("Quickly View")

    BTN = "qv_"

    # ============== Constantes ==============
    BUCKET_ORDER = ["M0"] + [f"M{i}" for i in range(1, 12)] + [f"{y}Y" for y in range(1, 11)]
    STRESS_COLORS = ["#00C2FF", "#FF4D6D", "#FFD166", "#06D6A0", "#A78BFA", "#FF8FAB", "#F97316", "#22C55E"]

    CURVES = [
        "Gap statique",
        "Gap dynamique",
        "Gap statique stressée idiosyncratique",
        "Gap statique stressée systémique",
        "Gap statique stressée combiné",
        "Gap dynamique stressé idiosyncratique",
        "Gap dynamique stressé systémique",
        "Gap dynamique stressé combiné",
    ]

    # ============== Controls ==============
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        unit = st.selectbox("Unité", ["KEUR", "EUR", "MEUR", "GEUR"], index=0, key=f"{BTN}unit")
    with c2:
        year = st.selectbox("Prévision jusqu'à", ["2026", "2027", "2028"], index=0, key=f"{BTN}year")
    with c3:
        curve_to_add = st.selectbox("Courbe à afficher / ajouter", CURVES, index=0, key=f"{BTN}curve")

    # ============== Boutons (style render4) ==============
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        show_curve = st.button("Visualiser Gap", key=f"{BTN}show")
    with b2:
        add_curve = st.button("Ajouter courbe", key=f"{BTN}add")
    with b3:
        reset_curve = st.button("Reset graphe", key=f"{BTN}reset")

    # ============== session_state fig + compteur ==============
    if "qv_fig" not in st.session_state:
        st.session_state["qv_fig"] = None
    if "qv_curve_count" not in st.session_state:
        st.session_state["qv_curve_count"] = 0

    if reset_curve:
        st.session_state["qv_fig"] = None
        st.session_state["qv_curve_count"] = 0

    # ============== Helpers internes ==============
    def _gap_df_to_bucket_series(gap_df: pd.DataFrame) -> pd.Series:
        """gap_df attendu : colonnes Bucket + Gap (déjà en buckets)."""
        if gap_df is None or gap_df.empty:
            return pd.Series([0.0] * len(BUCKET_ORDER), index=BUCKET_ORDER)

        g = gap_df.copy()
        if "Bucket" not in g.columns and "Mois" in g.columns:
            g = g.rename(columns={"Mois": "Bucket"})

        g["Bucket"] = g["Bucket"].astype(str)
        g["Gap"] = pd.to_numeric(g["Gap"], errors="coerce").fillna(0.0)

        g = g[g["Bucket"].isin(BUCKET_ORDER)].copy()
        g["Bucket"] = pd.Categorical(g["Bucket"], categories=BUCKET_ORDER, ordered=True)
        g = g.sort_values("Bucket")

        s = pd.Series(g["Gap"].values, index=g["Bucket"].astype(str).values)
        return s.reindex(BUCKET_ORDER).fillna(0.0)

    def _load_all_dynamic():
        """
        Reprend la logique Tab5 : construit fs + stress_raw à partir des session_state.
        """
        runoff = st.session_state["runoff_df"].copy()
        runoff = runoff.rename(
            columns={
                "Poste du bilan": "Poste bilan",
                "Loi d'écoulement en liquidité": "Profil d’écoulement",
                "Durée moyenne (en mois)": "Maturité",
                "En liquidité": "Montant",
            }
        )

        taux_df = st.session_state["bilan"].copy()
        taux_df = taux_df.rename(columns={taux_df.columns[2]: "Poste bilan", taux_df.columns[4]: "Taux"})
        taux = taux_df[["Poste bilan", "Taux"]]

        pmt = st.session_state["pmt_df"].copy()

        runoff_c = clean_runoff(runoff)
        taux_c = clean_taux(taux)
        pmt_c = clean_pmt(pmt)

        fs = build_dynamic_fs_projection(runoff_c, taux_c, pmt_c)
        stress_raw = load_stress_raw()  # lit st.session_state["stress_liquidity_df"]
        return fs, stress_raw

    def _compute_gap(curve_name: str) -> pd.DataFrame | None:
        """
        Retourne un gap_df en BUCKETS avec colonnes ['Bucket','Gap'].
        Cache en session_state pour éviter recalcul.
        """
        cache_key = f"{BTN}gap_cache::{curve_name}::{year}"
        if cache_key in st.session_state:
            return st.session_state[cache_key]

        # --- STATIQUE
        if curve_name == "Gap statique":
            empty_fs = build_empty_fs_projection(st.session_state["runoff_df"])
            CRD, _, _ = liquidity_flows(empty_fs)
            gap = liquidity_gap_from_flow_df(CRD)
            st.session_state[cache_key] = gap
            return gap

        # --- STATIQUE STRESSÉ (3 scénarios)
        if curve_name.startswith("Gap statique stressée"):
            if not has_static_stress_inputs:
                return None
            if "idiosyncratique" in curve_name:
                scen = "idiosyncratique"
            elif "systémique" in curve_name:
                scen = "systémique"
            else:
                scen = "combiné"

            empty_fs = build_empty_fs_projection(st.session_state["runoff_df"])
            CRD, _, _ = liquidity_flows(empty_fs)
            apply_liquidity_stress(CRD, st.session_state["stress_liquidity_df"], scen)

            stress_crd = st.session_state.get("Stress_CRD_flow_df")
            if stress_crd is None:
                return None
            gap = liquidity_gap_from_flow_df(stress_crd)
            st.session_state[cache_key] = gap
            return gap

        # --- DYNAMIQUE
        if curve_name == "Gap dynamique":
            if not has_dynamic_inputs:
                return None
            fs, _stress_raw = _load_all_dynamic()
            CRD, _, _ = liquidity_flows_team_style(fs)
            dyn = dynamic_liquidity_flows_from_crd(CRD, horizon=170)
            gap = dynamic_liquidity_gap_bucket_by_year(dyn, year)
            st.session_state[cache_key] = gap
            return gap

        # --- DYNAMIQUE STRESSÉ (3 scénarios)
        if curve_name.startswith("Gap dynamique stressé"):
            if not has_dynamic_inputs:
                return None
            if "idiosyncratique" in curve_name:
                scen = "idiosyncratique"
            elif "systémique" in curve_name:
                scen = "systémique"
            else:
                scen = "combiné"

            fs, stress_raw = _load_all_dynamic()
            stressed_dyn = apply_dynamic_liquidity_stress(fs, stress_raw, scen)
            gap = dynamic_liquidity_gap_bucket_by_year(stressed_dyn, year)
            st.session_state[cache_key] = gap
            return gap

        return None

    def _add_curve_to_fig(curve_name: str, fig: go.Figure):
        gap_df = _compute_gap(curve_name)
        if gap_df is None:
            # message propre selon dépendances
            if "dynamique" in curve_name.lower() and not has_dynamic_inputs:
                st.warning("Données dynamiques manquantes : il faut **bilan**, **pmt_df** et **stress_liquidity_df**.")
            elif "stressée" in curve_name.lower() and not has_static_stress_inputs:
                st.warning("Données de stress liquidité manquantes : il faut **stress_liquidity_df**.")
            else:
                st.warning("Impossible de calculer la courbe (données manquantes ou format inattendu).")
            return

        factor = _unit_factor_from_KEUR(unit)
        s = _gap_df_to_bucket_series(gap_df) * factor

        color = STRESS_COLORS[st.session_state["qv_curve_count"] % len(STRESS_COLORS)]
        st.session_state["qv_curve_count"] += 1

        # Nom plus lisible sur légende
        display_name = curve_name
        if curve_name == "Gap dynamique":
            display_name = f"Gap dynamique (Prévision jusqu'à {year})"
        if curve_name.startswith("Gap dynamique stressé"):
            display_name = f"{curve_name} (NP {year})"

        fig.add_trace(go.Scatter(
            x=BUCKET_ORDER,
            y=s.values.tolist(),
            mode="lines+markers",
            name=display_name,
            line=dict(color=color, width=3),
        ))

    # ============== 1) Afficher (base) ==============
    if show_curve:
        fig = go.Figure()
        _add_curve_to_fig(curve_to_add, fig)

        fig.update_layout(
            title=f"Gaps — unité {unit}",
            xaxis_title="Bucket",
            yaxis_title=f"Gap ({unit})",
            template="plotly_dark",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=20, r=20, t=60, b=20),
        )
        # ligne 0 (utile sur gap)
        fig.add_hline(y=0)

        st.session_state["qv_fig"] = fig

    # ============== 2) Ajouter courbe ==============
    if add_curve:
        if st.session_state.get("qv_fig") is None:
            st.warning("Clique d’abord sur **Visualiser Gap**.")
        else:
            fig = st.session_state["qv_fig"]
            _add_curve_to_fig(curve_to_add, fig)
            st.session_state["qv_fig"] = fig

    # ============== 3) Affichage du graphe unique + tableau ==============
    if st.session_state.get("qv_fig") is not None:
        st.plotly_chart(st.session_state["qv_fig"], use_container_width=True)

        # Table comparative des courbes présentes (reconstruit depuis les traces)
        # (On refait une table simple à partir des traces : bucket + colonnes)
        fig = st.session_state["qv_fig"]
        table = pd.DataFrame({"Bucket": BUCKET_ORDER})
        for tr in fig.data:
            # chaque trace a x,y
            if hasattr(tr, "name") and hasattr(tr, "y") and tr.y is not None:
                table[str(tr.name)] = list(tr.y)

        st.dataframe(table, use_container_width=True)