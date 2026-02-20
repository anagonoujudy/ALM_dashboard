import streamlit as st
import streamlit.components.v1 as components
from ui.theme import apply_theme
from ui.state import init_state

from onglets.tab1_load_data import render as render_tab1
from onglets.tab3_liquidity import render3 as render_tab3
from onglets.tab4_rate import render4 as render_tab4
from onglets.tab_kpi import render_tab2_kpi as render_tab2
from onglets.tab5_dn import render_tab5_dynamic as render_tab5
from onglets.tab55_qv import render_quickly_view as render_qv

st.set_page_config(page_title="ALM Dashboard", layout="wide")
apply_theme()
init_state()

tab1, tab2, tab3, tab5, tab55, tab4 = st.tabs(
    ["Load Data", "KPI and Risk", "Static Analysis", "Dynamic Analysis","Quickly View","Rate Analysis"]
)

with tab1:
    render_tab1()
with tab2:
    render_tab2()
with tab3:
    render_tab3()
with tab5:
    render_tab5()
with tab55:
    render_qv()
with tab4:
    render_tab4()
