import streamlit as st

# Palette inspirée du thème "dashboard dark" de tes screenshots
COLORS = {
    "bg": "#0B1220",          # fond global (bleu nuit)
    "panel": "#0F1A2B",       # panneaux / sidebar
    "card": "#121F33",        # cartes KPI
    "card_2": "#0E1828",      # cartes secondaires
    "text": "#E6EDF7",        # texte principal
    "muted": "#9FB0C7",       # texte secondaire
    "border": "rgba(255,255,255,0.10)",
    "accent": "#2DD4BF",      # turquoise
    "accent2": "#60A5FA",     # bleu clair
    "navy": "#1E3A8A",        # bleu marine (tabs)
    "danger": "#F87171",
    "success": "#34D399",
}

def apply_theme():
    st.markdown(
        f"""
        <style>
        /* ---------- Global ---------- */
        html, body, [class*="css"] {{
            font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
        }}
        .stApp {{
            background: {COLORS["muted"]};
            color: {COLORS["bg"]}; /* ✅ AVANT: accent2 -> maintenant texte principal bien lisible */
        }}

        /* ---------- Hide Streamlit top bar (white header) ---------- */
        header[data-testid="stHeader"] {{
            display: none;
        }}

        /* ---------- Main container spacing ---------- */
        .block-container {{
            padding-top: 1rem;
            padding-bottom: 2.2rem;
        }}

        /* ---------- Sidebar (comme avant) ---------- */
        [data-testid="stSidebar"] {{
            background: {COLORS["panel"]};
            border-right: 1px solid {COLORS["border"]};
        }}
        [data-testid="stSidebar"] * {{
            color: {COLORS["text"]};
        }}
        [data-testid="stSidebar"] .stMarkdown p {{
            color: {COLORS["text"]};
        }}

        /* ---------- Headings ---------- */
        h1, h2, h3, h4 {{
            color: {COLORS["navy"]};
            letter-spacing: 0.2px;
        }}

        /* ---------- Buttons ---------- */
        .stButton > button {{
            background: linear-gradient(135deg, {COLORS["accent"]}, {COLORS["accent2"]});
            color: #07101A;
            border: 0;
            border-radius: 12px;
            padding: 0.55rem 0.9rem;
            font-weight: 700;
            box-shadow: 0 10px 22px rgba(0,0,0,0.25);
            transition: transform 0.05s ease-in-out;
        }}
        .stButton > button:hover {{
            transform: translateY(-1px);
            filter: brightness(1.02);
        }}
        .stButton > button:active {{
            transform: translateY(0px);
        }}

        /* ---------- Inputs ---------- */
        .stTextInput > div > div,
        .stSelectbox > div > div,
        .stNumberInput > div > div,
        .stDateInput > div > div {{
            background: {COLORS["card_2"]} !important;
            border: 1px solid {COLORS["border"]} !important;
            border-radius: 12px !important;
            color: {COLORS["text"]} !important;
        }}
        .stSlider > div > div {{
            color: {COLORS["navy"]};
        }}

        /* ---------- Dataframe / Tables ---------- */
        .stDataFrame {{
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid {COLORS["border"]};
            background: {COLORS["card_2"]};
        }}

        /* ---------- Alerts ---------- */
        [data-testid="stAlert"] {{
            border-radius: 14px;
            border: 1px solid {COLORS["border"]};
            background: {COLORS["card_2"]};
            color: {COLORS["text"]};
        }}

        /* ---------- KPI Cards (custom) ---------- */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
        }}
        @media (max-width: 1100px) {{
            .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        @media (max-width: 700px) {{
            .kpi-grid {{ grid-template-columns: repeat(1, minmax(0, 1fr)); }}
        }}
        .kpi-card {{
            background: {COLORS["card"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 16px;
            padding: 14px 16px;
            box-shadow: 0 16px 30px rgba(0,0,0,0.25);
        }}
        .kpi-title {{
            margin: 0;
            font-size: 0.85rem;
            color: {COLORS["navy"]};
        }}
        .kpi-value {{
            margin: 6px 0 0 0;
            font-size: 1.45rem;
            font-weight: 800;
            color: {COLORS["bg"]};
        }}
        .kpi-foot {{
            margin: 6px 0 0 0;
            font-size: 0.78rem;
            color: {COLORS["navy"]};
        }}
        .pill {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            border: 1px solid {COLORS["border"]};
            background: rgba(45,212,191,0.10);
            color: {COLORS["accent"]};
            font-size: 0.75rem;
            font-weight: 700;
            margin-left: 6px;
        }}

        /* ✅ NEW: Native Streamlit metrics (st.metric) = flashy */
        [data-testid="stMetricValue"] {{
            color: {COLORS["navy"]} !important;   /* turquoise qui tape à l'œil */
            font-size: 2rem !important;
            font-weight: 900 !important;
        }}
        [data-testid="stMetricLabel"] {{
            color: {COLORS["bg"]} !important;
            font-size: 1.3rem !important;
            font-weight: 800 !important;
        }}

        /* ---------- TOP TABS (st.tabs) ---------- */
        button[data-baseweb="tab"] {{
            background: transparent !important;
            padding-top: 14px !important;
            padding-bottom: 14px !important;
        }}

        button[data-baseweb="tab"] * {{
            font-size: 1.25rem !important;
            font-weight: 800 !important;
            color: {COLORS["bg"]} !important;   /* bleue marine */
        }}

        button[data-baseweb="tab"][aria-selected="true"] * {{
            color: {COLORS["danger"]} !important; /* actif */
        }}

        div[data-baseweb="tab-highlight"] {{
            background-color: {COLORS["danger"]} !important;
            height: 4px !important;
        }}

        div[data-baseweb="tab-list"] {{
            gap: 32px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

def kpi_card(title: str, value: str, subtitle: str = "", pill: str | None = None):
    pill_html = f'<span class="pill">{pill}</span>' if pill else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <p class="kpi-title">{title}{pill_html}</p>
            <p class="kpi-value">{value}</p>
            <p class="kpi-foot">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def kpi_grid_open():
    st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)

def kpi_grid_close():
    st.markdown('</div>', unsafe_allow_html=True)
