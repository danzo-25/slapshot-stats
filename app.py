import streamlit as st
from data_loader import load_nhl_data

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")

st.title("🏒 NHL 2024-25 Player Stats")

# 1. Load Data
with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. The season might not have started or the API is down.")
else:
    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Filter Options")

    # Team Filter
    all_teams = sorted(df['Team'].unique())
    selected_teams = st.sidebar.multiselect("Select Teams", all_teams, default=all_teams)

    # Position Filter
    all_positions = sorted(df['Pos'].unique())
    selected_positions = st.sidebar.multiselect("Select Positions", all_positions, default=all_positions)

    # --- APPLY FILTERS ---
    filtered_df = df[
        (df['Team'].isin(selected_teams)) &
        (df['Pos'].isin(selected_positions))
    ]

    # --- DISPLAY METRICS ---
    st.markdown("### Top Performers")
    col1, col2, col3 = st.columns(3)
    
    # Helper to safely get top player
    def get_top_player(dataframe, column):
        if dataframe.empty: return "N/A", 0
        top = dataframe.sort_values(by=column, ascending=False).iloc[0]
        return top['Player'], top[column]

    top_pts_name, top_pts_val = get_top_player(filtered_df, 'Pts')
    top_g_name, top_g_val = get_top_player(filtered_df, 'G')
    top_a_name, top_a_val = get_top_player(filtered_df, 'A')

    col1.metric(label="Points Leader", value=str(top_pts_val), delta=top_pts_name)
    col2.metric(label="Goals Leader", value=str(top_g_val), delta=top_g_name)
    col3.metric(label="Assists Leader", value=str(top_a_val), delta=top_a_name)

    # --- MAIN TABLE ---
    st.markdown("---")
    st.subheader("Player Stats Table")
    
    # Use st.dataframe which allows clicking column headers to sort!
    st.dataframe(
        filtered_df, 
        use_container_width=True, 
        hide_index=True,
        height=600
    )

    st.markdown(f"*Showing {len(filtered_df)} players*")
