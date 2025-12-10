import streamlit as st
from data_loader import load_nhl_data

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")

st.title("🏒 NHL 2025-26 Player Stats")

with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. The API might be busy or the season hasn't started.")
else:
    # Sidebar Filters
    st.sidebar.header("Filter Options")

    # Team Filter
    if 'Team' in df.columns:
        unique_teams = sorted(df['Team'].dropna().unique())
        selected_teams = st.sidebar.multiselect("Select Teams", unique_teams, default=unique_teams)
        if selected_teams:
            df = df[df['Team'].isin(selected_teams)]

    # Position Filter
    if 'Pos' in df.columns:
        unique_pos = sorted(df['Pos'].dropna().unique())
        selected_positions = st.sidebar.multiselect("Select Positions", unique_pos, default=unique_pos)
        if selected_positions:
            df = df[df['Pos'].isin(selected_positions)]

    # Metrics
    st.markdown("### Top Performers")
    col1, col2, col3 = st.columns(3)
    
    def get_top(df, col):
        if df.empty or col not in df.columns: return "N/A", 0
        row = df.sort_values(by=col, ascending=False).iloc[0]
        return row['Player'], row[col]

    p_name, p_val = get_top(df, 'Pts')
    g_name, g_val = get_top(df, 'G')
    a_name, a_val = get_top(df, 'A')

    col1.metric("Points Leader", str(p_val), p_name)
    col2.metric("Goals Leader", str(g_val), g_name)
    col3.metric("Assists Leader", str(a_val), a_name)

    # Table
    st.markdown("---")
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)


