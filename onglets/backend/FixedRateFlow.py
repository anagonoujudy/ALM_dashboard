import pandas as pd 
import numpy as np


MONTHS = list(range(1, 121))
M_COLS = [f"M{m}" for m in MONTHS]
CF_COLS = [f"CF_{m}" for m in MONTHS]

def _normalize_profiles(df: pd.DataFrame, col: str) -> pd.Series:
    return (
        df[col].astype(str).str.strip().str.lower()
        .replace({"ine fine": "in fine", "lineaire": "linéaire"})
    )


def build_rate_projection(bilan_df: pd.DataFrame, runoff_df: pd.DataFrame) -> pd.DataFrame:
    df = runoff_df.copy()
    df = df.rename(columns={
        "Catégories Bilan": "Categorie",
        "Durée moyenne (en mois)": "Maturité",
    })

    required = [
        "Bilan",
        "Categorie",
        "Poste du bilan",
        "Montant (en k€)",
        "Taux d'intérèt moyen",
        "Loi d'écoulement en taux",
        "Maturité",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Colonnes manquantes dans runoff_df: {missing}")

    df = df[required].copy()

    df["Montant (en k€)"] = pd.to_numeric(df["Montant (en k€)"], errors="coerce").fillna(0.0)
    df["Taux d'intérèt moyen"] = pd.to_numeric(df["Taux d'intérèt moyen"], errors="coerce").fillna(0.0)
    df["Maturité"] = pd.to_numeric(df["Maturité"], errors="coerce").fillna(0).astype(int)

    proj = df[[
        "Bilan", "Categorie", "Poste du bilan",
        "Taux d'intérèt moyen", "Loi d'écoulement en taux", "Maturité"
    ]].copy()

    proj["M0"] = df["Montant (en k€)"]
    months_matrix = pd.DataFrame(np.zeros((len(proj), 120)), columns=M_COLS)
    proj = pd.concat([proj, months_matrix], axis=1)

    proj["Loi d'écoulement en taux"] = _normalize_profiles(proj, "Loi d'écoulement en taux")
    return proj


def Fixed_rate_flows(financial_statement: pd.DataFrame) -> pd.DataFrame:
    df = financial_statement.copy()

    for i in range(len(df)):
        M0 = float(df.loc[i, "M0"])
        maturity = int(df.loc[i, "Maturité"])
        rate_annual = float(df.loc[i, "Taux d'intérèt moyen"])
        profile = str(df.loc[i, "Loi d'écoulement en taux"]).strip().lower()

        r = rate_annual / 12.0

        if maturity <= 0:
            df.loc[i, M_COLS] = 0.0
            continue

        if profile == "in fine":
            for m in MONTHS:
                df.loc[i, f"M{m}"] = M0 if m < maturity else 0.0

        elif profile == "linéaire":
            for m in MONTHS:
                if m <= maturity:
                    crd = M0 * (1 - m / maturity)
                    df.loc[i, f"M{m}"] = max(crd, 0.0)
                else:
                    df.loc[i, f"M{m}"] = 0.0

        elif profile == "constant":
            crd = M0
            if r == 0:
                C = M0 / maturity
            else:
                C = (r * M0) / (1 - (1 + r) ** (-maturity))

            for m in MONTHS:
                if m <= maturity:
                    crd = crd * (1 + r) - C
                    if abs(crd) < 1e-8:
                        crd = 0.0
                    df.loc[i, f"M{m}"] = max(crd, 0.0)
                else:
                    df.loc[i, f"M{m}"] = 0.0
        else:
            df.loc[i, M_COLS] = 0.0

    return df
