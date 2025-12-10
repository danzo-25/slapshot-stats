import streamlit as st
import streamlit as st
import pandas as pd
import altair as alt
from data_loader import load_nhl_data, get_player_game_log, load_schedule, load_weekly_leaders, get_weekly_schedule_matrix

st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")
st.title("🏒 NHL 2025-26 Dashboard")

# --- SESSION STATE ---
if 'my_roster' not in st.session_state:
    st.session_state.my_roster = []

# --- CSS ---
st.markdown("""
<style>
    .game-card { background-color: #262730; border: 1px solid #41444e; border-radius: 8px; padding: 5px; text-align: center; margin: 0 auto 5px auto; max-width: 100%; box-shadow: 1px 1px 3px rgba(0,0,0,0.2); }
    .team-row { display: flex; justify-content: center; align-items: center; gap: 5px; }
    .team-info { display: flex; flex-direction: column; align-items: center; }
    .team-logo { width: 55px; height: 55px; object-fit: contain; margin-bottom: 2px; }
    .team-name { font-weight: 900; font-size: 1em; margin-top: -2px; }
    .vs-text { font-size: 1em; font-weight: bold; color: #888; padding-top: 5px; }
    .game-time { margin-top: 5px; font-weight: bold; color: #FF4B4B; font-size: 0.9em; border-top: 1px solid #41444e; padding-top: 2px; }
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
        # 1. SCHEDULE
        st.header("📅 Today's Games")
        schedule = load_schedule()
        if not schedule:
            st.info("No games scheduled for today.")
        else:
            cols_per_row = 5
            for i in range(0, len(schedule), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
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

        # 2. STRENGTH OF SCHEDULE (SOS)
        st.header("💪 Strength of Schedule (Weekly View)")
        st.caption("Green = Easy Matchup (You are favored). Red = Hard Matchup (Opponent is favored).")
        
        with st.spinner("Calculating matchup difficulty..."):
            sos_matrix, standings = get_weekly_schedule_matrix()
        
        if not sos_matrix.empty and standings:
            # --- COLOR LOGIC ---
            def color_sos(val, my_team_abbr):
                """
                val: The cell value (e.g. "vs TOR" or "")
                my_team_abbr: The row index (e.g. "EDM")
                """
                if not val or val == "":
                    return 'background-color: #262730' # Grey for no game
                
                # Extract Opponent Name ("vs TOR" -> "TOR")
                opp_abbr = val.split(" ")[1] 
                
                # Get Points % (Strength)
                my_str = standings.get(my_team_abbr, 0.5)
                opp_str = standings.get(opp_abbr, 0.5)
                
                # Calculate Advantage
                # Positive = I am stronger (Green)
                # Negative = Opponent is stronger (Red)
                diff = my_str - opp_str
                
                # Gradient Logic (Hex Codes)
                # Thresholds: +/- 0.15 is a massive gap
                if diff > 0.15: return 'background-color: #1b5e20; color: white'  # Deep Green
                elif diff > 0.05: return 'background-color: #2e7d32; color: white' # Medium Green
                elif diff > 0.00: return 'background-color: #4caf50; color: black' # Light Green
                elif diff > -0.05: return 'background-color: #fbc02d; color: black' # Yellow/Even
                elif diff > -0.15: return 'background-color: #c62828; color: white' # Medium Red
                else: return 'background-color: #b71c1c; color: white'            # Deep Red

            # Apply Style row by row
            # We iterate through the dataframe and apply the style function
            def apply_style(df):
                return df.style.apply(lambda row: [color_sos(val, row.name) for val in row], axis=1)

            styled_sos = apply_style(sos_matrix)
            
            # Display
            st.dataframe(styled_sos, use_container_width=True, height=600)
        else:
            st.info("Strength of Schedule data unavailable.")

        st.divider()

        # 3. WEEKLY CHARTS
        st.header("🔥 Hot This Week")
        with st.spinner("Loading weekly trends..."):
            df_weekly = load_weekly_leaders()
        
        if not df_weekly.empty:
            def make_mini_chart(data, x_col, y_col, color, title):
                sorted_data = data.sort_values(y_col, ascending=False).head(5)
                chart = alt.Chart(sorted_data).mark_bar(cornerRadiusEnd=4).encode(
                    x=alt.X(f'{y_col}:Q', title=None), 
                    y=alt.Y(f'{x_col}:N', sort='-x', title=None), 
                    color=alt.value(color), tooltip=[x_col, y_col]
                ).properties(title=title, height=200)
                text = chart.mark_text(align='left', dx=2).encode(text=f'{y_col}:Q')
                return (chart + text)

            c1, c2 = st.columns(2)
            with c1: st.altair_chart(make_mini_chart(df_weekly, 'Player', 'G', '#ff4b4b', 'Top Goal Scorers'), use_container_width=True)
            with c2: st.altair_chart(make_mini_chart(df_weekly, 'Player', 'Pts', '#0083b8', 'Top Points Leaders'), use_container_width=True)

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
                game_log['Rolling Points'] = game_log['points'].rolling(window=5, min_periods=1).mean()
                chart_data = game_log[['gameDate', 'points', 'Rolling Points']].set_index('gameDate')
                st.line_chart(chart_data, color=["#d3d3d3", "#ff4b4b"])
        
        st.divider()
        st.subheader("League Summary Table")
        
        with st.expander("⚙️ Fantasy Point Settings", expanded=False):
            c_s1, c_s2, c_s3, c_s4, c_s5, c_s6 = st.columns(6)
            c_g1, c_g2, c_g3, c_g4, c_g5, c_g6 = st.columns(6)
            val_G = c_s1.number_input("Goals", value=2.0)
            val_A = c_s2.number_input("Assists", value=1.0)
            val_PPP = c_s3.number_input("PPP", value=0.5)
            val_SHP = c_s4.number_input("SHP", value=0.5)
            val_SOG = c_s5.number_input("SOG", value=0.1)
            val_Hit = c_s6.number_input("Hits", value=0.1)
            val_BkS = c_g1.number_input("Blocks", value=0.5)
            val_W = c_g2.number_input("Wins", value=4.0)
            val_GA = c_g3.number_input("GA", value=-2.0)
            val_Svs = c_g4.number_input("Saves", value=0.2)
            val_SO = c_g5.number_input("Shutouts", value=3.0)
            val_OTL = c_g6.number_input("OTL", value=1.0)

        df['FP'] = (
            (df['G'] * val_G) + (df['A'] * val_A) + (df['PPP'] * val_PPP) + 
            (df['SHP'] * val_SHP) + (df['SOG'] * val_SOG) + (df['Hits'] * val_Hit) + 
            (df['BkS'] * val_BkS) + (df['W'] * val_W) + (df['GA'] * val_GA) + 
            (df['Svs'] * val_Svs) + (df['SO'] * val_SO) + (df['OTL'] * val_OTL)
        ).round(1)

        cols = ['ID', 'Player', 'Team', 'Pos', 'FP'] + [c for c in df.columns if c not in ['ID', 'Player', 'Team', 'Pos', 'FP', 'PosType']]
        df = df[cols]

        column_config = {
            "ID": None,
            "Player": st.column_config.TextColumn("Player", pinned=True),
            "FP": st.column_config.NumberColumn("FP", format="%.1f"),
            "Team": st.column_config.TextColumn("Team"),
            "Pos": st.column_config.TextColumn("Pos"),
            "GP": st.column_config.NumberColumn("GP", format="%.0f"),
            "G": st.column_config.NumberColumn("G", format="%.0f"),
            "A": st.column_config.NumberColumn("A", format="%.0f"),
            "Pts": st.column_config.NumberColumn("Pts", format="%.0f"),
            "PPP": st.column_config.NumberColumn("PPP", format="%.0f"),
            "SHP": st.column_config.NumberColumn("SHP", format="%.0f"),
            "SOG": st.column_config.NumberColumn("SOG", format="%.0f"),
            "Hits": st.column_config.NumberColumn("Hits", format="%.0f"),
            "BkS": st.column_config.NumberColumn("BkS", format="%.0f"),
            "W": st.column_config.NumberColumn("W", format="%.0f"),
            "GA": st.column_config.NumberColumn("GA", format="%.0f"),
            "Svs": st.column_config.NumberColumn("Svs", format="%.0f"),
            "SO": st.column_config.NumberColumn("SO", format="%.0f"),
            "SAT%": st.column_config.NumberColumn("SAT%", format="%.1f%%"),
            "USAT%": st.column_config.NumberColumn("USAT%", format="%.1f%%"),
            "SV%": st.column_config.NumberColumn("SV%", format="%.3f"),
            "GAA": st.column_config.NumberColumn("GAA", format="%.2f"),
            "GSAA": st.column_config.NumberColumn("GSAA", format="%.2f"),
            "TOI": st.column_config.TextColumn("TOI")
        }

        with st.expander("Filter Options"):
            c1, c2 = st.columns(2)
            teams = sorted(df['Team'].unique())
            sel_teams = c1.multiselect("Team", teams, default=teams)
            pos = sorted(df['Pos'].unique())
            sel_pos = c2.multiselect("Position", pos, default=pos)

        filt_df = df.copy()
        if sel_teams: filt_df = filt_df[filt_df['Team'].isin(sel_teams)]
        if sel_pos: filt_df = filt_df[filt_df['Pos'].isin(sel_pos)]

        def highlight_my_team(row):
            return ['background-color: #574d28'] * len(row) if row['Player'] in st.session_state.my_roster else [''] * len(row)

        styled_df = filt_df.style.apply(highlight_my_team, axis=1)
        
        # Apply formatting
        whole_num_cols = ['GP', 'G', 'A', 'Pts', 'PPP', 'SHP', 'SOG', 'Hits', 'BkS', 'W', 'GA', 'Svs', 'SO', 'OTL']
        valid_whole = [c for c in whole_num_cols if c in filt_df.columns]
        styled_df = styled_df.format("{:.0f}", subset=valid_whole)
        styled_df = styled_df.format("{:.1f}", subset=['FP'])
        styled_df = styled_df.format("{:.2f}", subset=['GAA', 'GSAA'])
        styled_df = styled_df.format("{:.3f}", subset=['SV%'])

        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600, column_config=column_config)

    # ================= TAB 3: FANTASY =================
    with tab_fantasy:
        st.header("⚔️ My Roster")
        col_up, _ = st.columns([1, 2])
        uploaded_file = col_up.file_uploader("📂 Load Saved Roster", type=["csv"])
        if uploaded_file:
            try:
                udf = pd.read_csv(uploaded_file)
                if "Player" in udf.columns: 
                    st.session_state.my_roster = [p for p in udf["Player"] if p in df['Player'].values]
            except: pass

        selected_players = st.multiselect("Search Players:", df['Player'].unique(), default=st.session_state.my_roster)
        st.session_state.my_roster = selected_players

        if selected_players:
            team_df = df[df['Player'].isin(selected_players)]
            st.download_button("💾 Save Roster", team_df[['Player']].to_csv(index=False), "roster.csv", "text/csv")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Goals", int(team_df['G'].sum()))
            c2.metric("Points", int(team_df['Pts'].sum()))
            c3.metric("Total FP", f"{team_df['FP'].sum():,.1f}")
            c4.metric("Goalie Wins", int(team_df['W'].sum()))
            
            styled_team = team_df.style.format("{:.0f}", subset=[c for c in whole_num_cols if c in team_df.columns])
            styled_team = styled_team.format("{:.1f}", subset=['FP'])
            st.dataframe(styled_team, use_container_width=True, hide_index=True, column_config=column_config)
