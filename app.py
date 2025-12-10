import streamlit as st
import pandas as pd
from data_loader import load_nhl_data, get_player_game_log

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")
st.title("🏒 NHL 2025-26 Fantasy Tool")

# --- LOAD DATA ---
with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. API might be down.")
else:
    # --- TABS ---
    tab1, tab2 = st.tabs(["📊 Summary & Trends", "⚔️ My Fantasy Team"])

    # Define Config (Hidden ID column)
    column_config = {
        "ID": st.column_config.NumberColumn("ID", hidden=True), # Hide ID from user
        "Player": st.column_config.TextColumn("Player", pinned=True),
        "Team": st.column_config.TextColumn("Team", help="Team"),
        "Pos": st.column_config.TextColumn("Pos", help="Position"),
        "GP": st.column_config.NumberColumn("GP", help="Games Played"),
        "G": st.column_config.NumberColumn("G", help="Goals"),
        "A": st.column_config.NumberColumn("A", help="Assists"),
        "Pts": st.column_config.NumberColumn("Pts", help="Points"),
        "W": st.column_config.NumberColumn("W", help="Wins"),
        "SV%": st.column_config.NumberColumn("SV%", help="Save %", format="%.3f"),
        "GAA": st.column_config.NumberColumn("GAA", help="GAA", format="%.2f"),
        "TOI": st.column_config.TextColumn("TOI", help="Time On Ice")
    }

    # ==========================================
    # TAB 1: SUMMARY & TRENDS
    # ==========================================
    with tab1:
        # --- SECTION A: TREND VISUALIZER ---
        st.header("📈 Breakout Detector")
        st.info("Select a player to see if they are heating up (Rolling 5-Game Average).")

        # 1. Player Selector
        # Create a list of "Player Name (Team)" for the dropdown
        player_options = df.sort_values('Pts', ascending=False)
        player_dict = dict(zip(player_options['Player'], player_options['ID']))
        
        selected_player_name = st.selectbox("Select Player to Analyze:", player_options['Player'].unique())

        if selected_player_name:
            # 2. Fetch Logs
            pid = player_dict[selected_player_name]
            with st.spinner(f"Fetching game log for {selected_player_name}..."):
                game_log = get_player_game_log(pid)
            
            if not game_log.empty:
                # 3. Process Data for Graph
                # We want "Points" over time.
                # Use .rolling(window=5).mean() to smooth out the noise and show the trend
                game_log['Rolling Points (Last 5)'] = game_log['points'].rolling(window=5, min_periods=1).mean()
                
                # Create a simple chart dataframe
                chart_data = game_log[['gameDate', 'points', 'Rolling Points (Last 5)']].set_index('gameDate')
                
                # 4. Plot
                st.line_chart(chart_data, color=["#d3d3d3", "#ff4b4b"]) 
                # Grey = Actual Daily Points, Red = The Trend Line (Rolling Avg)
                
                st.caption("Grey Line: Daily Points | Red Line: 5-Game Rolling Average (The Trend)")
            else:
                st.warning("No game log data available for this player.")

        st.divider()

        # --- SECTION B: LEAGUE TABLE ---
        st.subheader("League Summary Table")
        
        with st.expander("Filter Options"):
            c1, c2 = st.columns(2)
            with c1:
                teams = sorted(df['Team'].unique())
                sel_teams = st.multiselect("Team", teams, default=teams)
            with c2:
                pos = sorted(df['Pos'].unique())
                sel_pos = st.multiselect("Position", pos, default=pos)

        filt_df = df[df['Team'].isin(sel_teams) & df['Pos'].isin(sel_pos)]
        st.dataframe(filt_df, use_container_width=True, hide_index=True, height=500, column_config=column_config)

    # ==========================================
    # TAB 2: MY FANTASY TEAM
    # ==========================================
    with tab2:
        st.header("⚔️ My Roster")
        
        col_up, _ = st.columns([1, 2])
        with col_up:
            uploaded_file = st.file_uploader("📂 Load Saved Roster", type=["csv"])
        
        default_roster = []
        if uploaded_file:
            try:
                udf = pd.read_csv(uploaded_file)
                if "Player" in udf.columns: default_roster = [p for p in udf["Player"] if p in df['Player'].values]
            except: pass

        my_team = st.multiselect("Search Players:", df['Player'].unique(), default=default_roster)

        if my_team:
            team_df = df[df['Player'].isin(my_team)]
            
            # Download
            st.download_button("💾 Save Roster", team_df[['Player']].to_csv(index=False), "roster.csv", "text/csv")
            
            # Totals
            st.markdown("### Team Totals")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Goals", int(team_df['G'].sum()))
            c2.metric("Points", int(team_df['Pts'].sum()))
            c3.metric("Goalie Wins", int(team_df['W'].sum()))
            c4.metric("Goalie SO", int(team_df['SO'].sum()))
            
            st.dataframe(team_df, use_container_width=True, hide_index=True, column_config=column_config)



