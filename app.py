import streamlit as st
import pandas as pd
import altair as alt
from data_loader import load_nhl_data, get_player_game_log, load_schedule, get_weekly_hot_players

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")
st.title("🏒 NHL 2025-26 Dashboard")

# CSS for Schedule
st.markdown("""
<style>
    .game-card {
        background-color: #262730;
        border: 1px solid #41444e;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 10px;
        text-align: center;
    }
    .team-row { display: flex; justify-content: center; align-items: center; gap: 15px; }
    .team-info { display: flex; flex-direction: column; align-items: center; width: 80px; }
    .team-logo { width: 60px; height: 60px; object-fit: contain; margin-bottom: 5px; }
    .team-name { font-weight: 900; font-size: 1.1em; }
    .vs-text { font-size: 0.9em; font-weight: bold; color: #aaa; }
    .game-time { margin-top: 8px; font-weight: bold; color: #FF4B4B; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)

with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. API might be down.")
else:
    tab_home, tab_analytics, tab_fantasy = st.tabs(["🏠 Home", "📊 Data & Analytics", "⚔️ My Fantasy Team"])

    # ================= TAB 1: HOME =================
    with tab_home:
        # SCHEDULE
        st.header("📅 Today's Games")
        schedule = load_schedule()
        if not schedule:
            st.info("No games scheduled for today.")
        else:
            for i in range(0, len(schedule), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(schedule):
                        game = schedule[i+j]
                        with cols[j]:
                            st.markdown(f"""
                            <div class="game-card">
                                <div class="team-row">
                                    <div class="team-info">
                                        <img src="{game['away_logo']}" class="team-logo">
                                        <div class="team-name">{game['away']}</div>
                                    </div>
                                    <div class="vs-text">@</div>
                                    <div class="team-info">
                                        <img src="{game['home_logo']}" class="team-logo">
                                        <div class="team-name">{game['home']}</div>
                                    </div>
                                </div>
                                <div class="game-time">{game['time']}</div>
                            </div>
                            """, unsafe_allow_html=True)
        st.divider()

        # WEEKLY CHARTS
        st.header("🔥 Hot This Week (Last 7 Days)")
        st.caption("Tracking top season performers over their last few games.")
        
        with st.spinner("Calculating weekly trends..."):
            df_weekly = get_weekly_hot_players()
        
        if not df_weekly.empty:
            def make_chart(data, x_col, y_col, color, title):
                base = alt.Chart(data).encode(
                    x=alt.X(f'{x_col}:N', axis=alt.Axis(labelAngle=0, title=None)),
                    y=alt.Y(f'{y_col}:Q', axis=None),
                    tooltip=['Player', y_col]
                )
                bars = base.mark_bar(size=30, color=color, cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(y=f'{y_col}:Q')
                text = base.mark_text(align='center', baseline='bottom', dy=-5, fontWeight='bold').encode(text=f'{y_col}:Q')
                return (bars + text).properties(title=title, height=250)

            top_g = df_weekly.sort_values('G', ascending=False).head(5)
            top_pts = df_weekly.sort_values('Pts', ascending=False).head(5)
            top_sog = df_weekly.sort_values('SOG', ascending=False).head(5)
            top_ppp = df_weekly.sort_values('PPP', ascending=False).head(5)

            c1, c2 = st.columns(2)
            with c1: st.altair_chart(make_chart(top_g, 'Player', 'G', '#ff4b4b', 'Top Goal Scorers'), use_container_width=True)
            with c2: st.altair_chart(make_chart(top_pts, 'Player', 'Pts', '#0083b8', 'Top Points Leaders'), use_container_width=True)
            
            c3, c4 = st.columns(2)
            with c3: st.altair_chart(make_chart(top_sog, 'Player', 'SOG', '#ffa600', 'Most Shots on Goal'), use_container_width=True)
            with c4: st.altair_chart(make_chart(top_ppp, 'Player', 'PPP', '#58508d', 'Power Play Points'), use_container_width=True)
        else:
            st.info("No weekly data available. The API might be returning partial data.")

    # ================= TAB 2: ANALYTICS =================
    with tab_analytics:
        st.header("📈 Breakout Detector")
        skater_options = df[df['PosType'] == 'Skater'].sort_values('Pts', ascending=False)
        player_dict = dict(zip(skater_options['Player'], skater_options['ID']))
        selected_player_name = st.selectbox("Select Player:", skater_options['Player'].unique())
        
        if selected_player_name:
            pid = player_dict[selected_player_name]
            game_log = get_player_game_log(pid)
            if not game_log.empty:
                game_log['Rolling Points (Last 5)'] = game_log['points'].rolling(window=5, min_periods=1).mean()
                chart_data = game_log[['gameDate', 'points', 'Rolling Points (Last 5)']].set_index('gameDate')
                st.line_chart(chart_data, color=["#d3d3d3", "#ff4b4b"])
        
        st.divider()
        st.subheader("League Summary")
        
        column_config = {
            "ID": None,
            "Player": st.column_config.TextColumn("Player", pinned=True),
            "Team": st.column_config.TextColumn("Team"),
            "Pos": st.column_config.TextColumn("Pos"),
            "GP": st.column_config.NumberColumn("GP", help="Games Played"),
            "G": st.column_config.NumberColumn("G", help="Goals"),
            "A": st.column_config.NumberColumn("A", help="Assists"),
            "Pts": st.column_config.NumberColumn("Pts", help="Points"),
            "W": st.column_config.NumberColumn("W", help="Wins"),
            "SV%": st.column_config.NumberColumn("SV%", format="%.3f"),
            "GAA": st.column_config.NumberColumn("GAA", format="%.2f"),
            "TOI": st.column_config.TextColumn("TOI")
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

    # ================= TAB 3: FANTASY =================
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
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Goals", int(team_df['G'].sum()))
            c2.metric("Points", int(team_df['Pts'].sum()))
            c3.metric("Goalie Wins", int(team_df['W'].sum()))
            c4.metric("Goalie SO", int(team_df['SO'].sum()))
            
            st.dataframe(team_df, use_container_width=True, hide_index=True, column_config=column_config)






