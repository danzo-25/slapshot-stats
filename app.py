import streamlit as st
from data_loader import load_nhl_data

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")

st.title("🏒 NHL 2025-26 Player Stats")

with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. The API might be busy or the season hasn't started.")
else:
    # --- FILTERS ---
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

    # --- METRICS ---
    st.markdown("### Top Performers")
    col1, col2, col3, col4 = st.columns(4)
    
    def get_top(dataframe, col):
        if dataframe.empty or col not in dataframe.columns: return "N/A", 0
        row = dataframe.sort_values(by=col, ascending=False).iloc[0]
        return row['Player'], row[col]

    p_name, p_val = get_top(df, 'Pts')
    g_name, g_val = get_top(df, 'G')
    a_name, a_val = get_top(df, 'A')
    gwg_name, gwg_val = get_top(df, 'GWG')

    col1.metric("Points Leader", str(p_val), p_name)
    col2.metric("Goals Leader", str(g_val), g_name)
    col3.metric("Assists Leader", str(a_val), a_name)
    col4.metric("GWG Leader", str(gwg_val), gwg_name)

    # --- MAIN TABLE WITH TOOLTIPS ---
    st.markdown("---")
    st.subheader("Player Stats Table")
    
    # This dictionary defines the tooltips and formatting for each column
    column_config = {
        "Player": st.column_config.TextColumn("Player", pinned=True),
        "Team": st.column_config.TextColumn("Team", help="Team Abbreviation"),
        "Pos": st.column_config.TextColumn("Pos", help="Position"),
        "GP": st.column_config.NumberColumn("GP", help="Games Played"),
        "G": st.column_config.NumberColumn("G", help="Goals"),
        "A": st.column_config.NumberColumn("A", help="Assists"),
        "Pts": st.column_config.NumberColumn("Pts", help="Points (Goals + Assists)"),
        "+/-": st.column_config.NumberColumn("+/-", help="Plus/Minus Rating"),
        "PIM": st.column_config.NumberColumn("PIM", help="Penalty Minutes"),
        "PPP": st.column_config.NumberColumn("PPP", help="Power Play Points"),
        "PPG": st.column_config.NumberColumn("PPG", help="Power Play Goals"),
        "SHP": st.column_config.NumberColumn("SHP", help="Shorthanded Points"),
        "GWG": st.column_config.NumberColumn("GWG", help="Game Winning Goals"),
        "SOG": st.column_config.NumberColumn("SOG", help="Shots on Goal"),
        "Sh%": st.column_config.NumberColumn("Sh%", help="Shooting Percentage (Goals / Shots)", format="%.1f%%"),
        "FO%": st.column_config.NumberColumn("FO%", help="Faceoff Win Percentage", format="%.1f%%"),
        "TOI": st.column_config.TextColumn("TOI", help="Time On Ice Per Game (Minutes:Seconds)")
    }

    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        height=600,
        column_config=column_config
    )


