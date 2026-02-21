import pandas as pd
import numpy as np
import streamlit as st

def Build_statement_data(pmt_df: pd.DataFrame) -> dict:
    pmt_df = pmt_df.copy().reset_index(drop=True).iloc[:, :2]
    pmt_df.columns = ["Poste du bilan", "M0"]
    pmt_df["Montant"] = pd.to_numeric(pmt_df["M0"], errors="coerce").fillna(0.0)

    def m(idx):
        return float(pmt_df.loc[idx, "Montant"]) if idx < len(pmt_df) else 0.0

    return {
        "ACTIF": {
            "CAISSE, BANQUES CENTRALES": {"Caisse": m(1), "Compte courant BDF": m(2)},
            "CREANCES SUR LES ETS DE CREDIT": {"A vue": m(4), "A terme": m(5)},
            "CREANCES SUR LA CLIENTELE": {
                "Créances commerciales": m(7),
                "Autres concours à la clientèle": m(8),
                "Comptes ordinaires débiteurs": m(9),
            },
            "TITRE D'INVESTISSEMENT": {"Investissements financiers": m(10)},
            "IMMOBILISATIONS": {"Immobilisations corporelles et incorporelles": m(11)},
            "AUTRES": {"Autres actifs": m(12)},
        },
        "PASSIF": {
            "DETTES ENVERS ETS DE CREDIT": {"A vue": m(15), "A terme": m(16)},
            "CPTES CREDITEURS DE LA CLIENTELE": {"A vue": m(18), "A terme": m(19)},
            "FINANCEMENT": {"Financement LT": m(22)},
            "PROVISIONS": {"Provisions pour risques et charges": m(21)},
            "AUTRES": {"Autres passifs": m(20)},
            "FONDS PROPRES": {
                "FRBG": m(24),
                "Capital souscrit": m(25),
                "Prime d'émission": m(26),
                "Réserves": m(27),
                "Report à nouveau": m(28),
                "Résultat de l'exercice": m(29),
                "Dividende": m(30),
            },
        },
    }


def _total_categorie(statement, cote, categorie):
    return sum(statement[cote][categorie].values())


def _total_cote(statement, cote):
    return sum(sum(postes.values()) for postes in statement[cote].values())

# ============================================================
# 1) FORMATTING UI
# ============================================================
def _fmt_amount(x, unit="KEUR"):
    x = 0.0 if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)
    if unit == "EUR":
        return f"{x*1000.0:,.0f} €"
    if unit == "MEUR":
        return f"{x/1000.0:,.2f} M€"
    if unit == "GEUR":
        return f"{x/1_000_000.0:,.3f} G€"
    return f"{x:,.0f} k€"

# def _unit_factor_from_KEUR(unit: str) -> float:
#     if unit == "KEUR":
#         return 1.0
#     if unit == "EUR":
#         return 1000.0
#     if unit == "MEUR":
#         return 1.0 / 1000.0
#     if unit == "GEUR":
#         return 1.0 / 1_000_000.0
#     return 1.0


def _fmt_pct(x):
    try:
        return f"{100*float(x):.2f}%"
    except Exception:
        return "—"


def _dict_to_df(d: dict, col_name="Valeur"):
    return pd.DataFrame({"Indicateur": list(d.keys()), col_name: list(d.values())})


def _ratio_table(d: dict, title: str):
    df = _dict_to_df(d, "Ratio")
    df["Ratio"] = df["Ratio"].apply(_fmt_pct)
    st.subheader(title)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _kpi_from_statement(statement: dict) -> dict:
    total_actif = _total_cote(statement, "ACTIF")
    total_passif = _total_cote(statement, "PASSIF")
    fonds_propres = sum(statement["PASSIF"].get("FONDS PROPRES", {}).values())
    caisse_bc = sum(statement["ACTIF"].get("CAISSE, BANQUES CENTRALES", {}).values())
    inv_fin = statement["ACTIF"].get("TITRE D'INVESTISSEMENT", {}).get("Investissements financiers", 0.0)
    hqla = caisse_bc + inv_fin
    depots = sum(statement["PASSIF"].get("CPTES CREDITEURS DE LA CLIENTELE", {}).values())

    return {
        "Total Actif": total_actif,
        "Total Passif": total_passif,
        "Fonds propres (Tier1 proxy)": fonds_propres,
        "HQLA": hqla,
        "Dépôts clientèle": depots,
    }

