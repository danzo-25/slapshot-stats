import streamlit as st
import pandas as pd
from data_loader import load_nhl_data, get_player_game_log, load_schedule, load_weekly_leaders

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")
st.title("🏒 NHL 2025-26 Dashboard")

# --- LOAD MAIN DATA ---
# We load the big dataset once to use across tabs
with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. API might be down.")
else:
    # --- TABS ---
    tab_home, tab_analytics, tab_fantasy = st.tabs(["🏠 Home", "📊 Data & Analytics", "⚔️ My Fantasy Team"])

    # ==========================================
    # TAB 1: HOME (Schedule + Weekly Trends)
    # ==========================================
    with tab_home:
        # --- SECTION A: TODAY'S SCHEDULE ---
        st.header("📅 Today's Games")
        
        schedule = load_schedule()
        
        if not schedule:
            st.info("No games scheduled for today.")
        else:
            # Create rows of 3 games each
            for i in range(0, len(schedule), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(schedule):
                        game = schedule[i+j]
                        with cols[j]:
                            with st.container(border=True):
                                c1, c2, c3 = st.columns([1, 0.5, 1])
                                with c1:
                                    st.image(game['away_logo'], width=50)
                                    st.caption(game['away'])
                                with c2:
                                    st.markdown(f"**VS**")
                                with c3:
                                    st.image(game['home_logo'], width=50)
                                    st.caption(game['home'])
                                st.markdown(f"<div style='text-align: center; font-weight: bold;'>{game['time']}</div>", unsafe_allow_html=True)

        st.divider()

        # --- SECTION B: HOT THIS WEEK ---
        st.header("🔥 Hot This Week (Last 7 Days)")
        
        with st.spinner("Loading weekly trends..."):
            df_weekly = load_weekly_leaders()
        
        if not df_weekly.empty:
            # Top 4 Charts
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Top Goal Scorers")
                top_g = df_weekly.sort_values('G', ascending=False).head(5)
                st.bar_chart(top_g.set_index('Player')['G'], color="#ff4b4b")

            with c2:
                st.subheader("Top Points Leaders")
                top_pts = df_weekly.sort_values('Pts', ascending=False).head(5)
                st.bar_chart(top_pts.set_index('Player')['Pts'], color="#0083b8")
            
            c3, c4 = st.columns(2)
            
            with c3:
                st.subheader("Most Shots on Goal")
                top_sog = df_weekly.sort_values('SOG', ascending=False).head(5)
                st.bar_chart(top_sog.set_index('Player')['SOG'], color="#ffa600")

            with c4:
                st.subheader("Power Play Points")
                top_ppp = df_weekly.sort_values('PPP', ascending=False).head(5)
                st.bar_chart(top_ppp.set_index('Player')['PPP'], color="#58508d")

        else:
            st.info("No weekly data available yet.")


    # ==========================================
    # TAB 2: DATA & ANALYTICS (Old Summary Tab)
    # ==========================================
    with tab_analytics:
        st.header("📈 Breakout Detector")
        st.info("Select a player to see if they are heating up (Rolling 5-Game Average).")

        # 1. Player Selector
        skater_options = df[df['PosType'] == 'Skater'].sort_values('Pts', ascending=False)
        player_dict = dict(zip(skater_options['Player'], skater_options['ID']))
        
        selected_player_name = st.selectbox("Select Player to Analyze:", skater_options['Player'].unique())

        if selected_player_name:
            pid = player_dict[selected_player_name]
            with st.spinner(f"Fetching game log for {selected_player_name}..."):
                game_log = get_player_game_log(pid)
            
            if not game_log.empty:
                game_log['Rolling Points (Last 5)'] = game_log['points'].rolling(window=5, min_periods=1).mean()
                chart_data = game_log[['gameDate', 'points', 'Rolling Points (Last 5)']].set_index('gameDate')
                
                st.line_chart(chart_data, color=["#d3d3d3", "#ff4b4b"]) 
                st.caption("Grey: Daily Points | Red: Trend Line (5-Game Avg)")
            else:
                st.warning("No game log data available for this player.")

        st.divider()

        st.subheader("League Summary Table")
        
        column_config = {
            "ID": None,
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

        with st.expander("Filter Options"):
            c1, c2 = st.columns(2)
            with c1:
                teams = sorted(df['Team'].unique())
                sel_teams = st.multiselect("Team", teams, default=teams)
            with c2:
                pos = sorted(df['Pos'].unique())
                sel_pos = st.multiselect("Position", pos, default=pos)

        filt_df = df.copy()
        if sel_teams: filt_df = filt_df[filt_df['Team'].isin(sel_teams)]
        if sel_pos: filt_df = filt_df[filt_df['Pos'].isin(sel_pos)]
        
        st.dataframe(filt_df, use_container_width=True, hide_index=True, height=500, column_config=column_config)

    # ==========================================
    # TAB 3: MY FANTASY TEAM
    # ==========================================
    with tab_fantasy:
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
            st.download_button("💾 Save Roster", team_df[['Player']].to_csv(index=False), "roster.csv", "text/csv")
            
            st.markdown("### Team Totals")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Goals", int(team_df['G'].sum()))
            c2.metric("Points", int(team_df['Pts'].sum()))
            c3.metric("Goalie Wins", int(team_df['W'].sum()))
            c4.metric("Goalie SO", int(team_df['SO'].sum()))
            
            # Reuse column config from above
            st.dataframe(team_df, use_container_width=True, hide_index=True, column_config=column_config)







