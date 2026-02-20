import streamlit as st
import pandas as pd

from ui.state import reset_results

REQUIRED_SHEETS = {
    "Bilan au 31_12_2025": "bilan",
    "Loi découlement": "runoff_df",
    "Plan Moyen Terme (PMT)": "pmt_df",
    "Courbe des taux": "zc_data_df",
    "Stress test de liquidité": "stress_liquidity_df",
    "stress test de taux": "stress_rate_df",
}

def render():
    st.title("Bienvenue sur ALM Dashboard FOJUMMA ")
    st.header("Chargement des données")
    st.markdown("##### Importez le fichier Excel")
    uploaded = st.file_uploader("",type=["xlsx"],label_visibility="collapsed")
    #uploaded = st.file_uploader("Importez le fichier Excel", type=["xlsx"])

    if uploaded is None:
        st.info("Attention : les noms des sheets ne doivent pas contenir des caractères spéciaux comme '")
        return

    # Reset des résultats si on recharge un fichier
    reset_results()

    # Lecture des feuilles
    loaded = {}
    missing = []

    for sheet_name, key in REQUIRED_SHEETS.items():
        try:
            df = pd.read_excel(uploaded, sheet_name=sheet_name)
            if sheet_name == "Plan Moyen Terme (PMT)":
                for c in df.columns:
                    if c != "Poste du bilan":
                       df[c] = pd.to_numeric(df[c], errors="coerce")
                    else:
                        continue
            loaded[sheet_name] = df
            st.session_state[key] = df

        except Exception:
            missing.append(sheet_name)
            st.session_state[key] = None

    # Status global
    if missing:
        st.session_state["excel_loaded"] = False
        st.error("Certaines feuilles obligatoires sont manquantes ou illisibles :")
        for s in missing:
            st.write(f"- {s}")
        return
    else:
        st.session_state["excel_loaded"] = True
        st.success("Toutes les feuilles ont été chargées avec succès ✅")

    # Infos rapides
    with st.expander("Voir un résumé des feuilles chargées"):
        for sheet_name, key in REQUIRED_SHEETS.items():
            df = st.session_state[key]
            st.write(f"✅ {sheet_name} — {df.shape[0]} lignes × {df.shape[1]} colonnes")

    # Exploration feuille
    st.subheader("Explorer une feuille")
    st.markdown("##### Choisir une feuille")
    choice = st.selectbox("", list(REQUIRED_SHEETS.keys()),label_visibility="collapsed")
    df_choice = st.session_state[REQUIRED_SHEETS[choice]]

    st.dataframe(df_choice, use_container_width=True)
