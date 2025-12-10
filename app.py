import streamlit as st
from data_loader import load_nhl_data

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")

st.title("🏒 NHL 2024-25 Player Stats")

# 1. Load Data
with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

# 2. Check if Data Loaded
if df.empty:
    st.warning("No data found. The API might be busy or the season hasn't started.")
else:
    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Filter Options")

    # Team Filter (Safety Check: ensure column exists and drop N/As)
    if 'Team' in df.columns:
        all_teams = sorted(df['Team'].dropna().unique())
        selected_teams = st.sidebar.multiselect("Select Teams", all_teams, default=all_teams)
    else:
        selected_teams = []

    # Position Filter
    if 'Pos' in df.columns:
        all_positions = sorted(df['Pos'].dropna().unique())
        selected_positions = st.sidebar.multiselect("Select Positions", all_positions, default=all_positions)
    else:
        selected_positions = []

    # --- APPLY FILTERS ---
    # Only filter if the user made a selection, otherwise show all
    if selected_teams and 'Team' in df.columns:
        df = df[df['Team'].isin(selected_teams)]
    
    if selected_positions and 'Pos' in df.columns:
        df = df[df['Pos'].isin(selected_positions)]

    # --- DISPLAY METRICS ---
    st.markdown("### Top Performers")
    col1, col2, col3 = st.columns(3)
    
    def get_top_player(dataframe, column):
        if dataframe.empty or column not in dataframe.columns:
            return "N/A", 0
        top = dataframe.sort_values(by=column, ascending=False).iloc[0]
        return top['Player'], top[column]

    top_pts_name, top_pts_val = get_top_player(df, 'Pts')
    top_g_name, top_g_val = get_top_player(df, 'G')
    top_a_name, top_a_val = get_top_player(df, 'A')

    col1.metric(label="Points Leader", value=str(top_pts_val), delta=top_pts_name)
    col2.metric(label="Goals Leader", value=str(top_g_val), delta=top_g_name)
    col3.metric(label="Assists Leader", value=str(top_a_val), delta=top_a_name)

    # --- MAIN TABLE ---
    st.markdown("---")
    st.subheader("Player Stats Table")
    
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        height=600
    )

    st.markdown(f"*Showing {len(df)} players*")

