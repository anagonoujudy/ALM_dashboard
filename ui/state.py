import streamlit as st

def init_state():
    defaults = {
        # global UI
        "unit_out": "KEUR",
        "excel_loaded": False,
        "active_tab": "Load Data",

        # raw inputs
        "runoff_df": None,
        "pmt_df": None,
        "zc_data_df": None,

        # ✅ utilisés dans tab3
        "stress_liquidity_df": None,

        "zc_fig": None,
        "zc_stress_count": 0,
        "actuarial_zc_rate": None,
        "stress_matrix": None,
        "rate_flow_df": None,


        # results (tab3)
        "CRD_flow_df": None,
        "Cash_Flow_df": None,
        "Interest_Flow_df": None,

        "Stress_CRD_flow_df": None,
        "Stress_Cash_Flow_df": None,
        "Stress_Interest_Flow_df": None,
        "last_stress_scenario": "idiosyncratique",

        # other tabs (si besoin)
        "stress_rate_df": None,

        # structured statement + ratios
        "statement": None,
        "balance_sheet_ratios": None,
        "liquidity_ratios": None,
        "funding_ratios": None,

        # results containers (dicts)
        "liq_static": {},
        "liq_dynamic": {},
        "rate_results": {},
        "metrics_results": {},

        # UI selections (legacy)
        "selected_sheet": None,
        "liq_profile": "Liquidité",
        "liq_scenario": "idiosyncratique",
        "rate_scenario": None,
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_results():
    st.session_state["statement"] = None
    st.session_state["balance_sheet_ratios"] = None
    st.session_state["liquidity_ratios"] = None
    st.session_state["funding_ratios"] = None
    st.session_state["liq_static"] = {}
    st.session_state["liq_dynamic"] = {}
    st.session_state["rate_results"] = {}
    st.session_state["metrics_results"] = {}

    # (optionnel) reset tab3 calculs
    st.session_state["CRD_flow_df"] = None
    st.session_state["Cash_Flow_df"] = None
    st.session_state["Interest_Flow_df"] = None
    st.session_state["Stress_CRD_flow_df"] = None
    st.session_state["Stress_Cash_Flow_df"] = None
    st.session_state["Stress_Interest_Flow_df"] = None

    st.session_state["rate_flow_df"] = None
    st.session_state["Stress_rate_flow_df"] = None

