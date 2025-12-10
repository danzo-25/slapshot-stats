import streamlit as st
import pandas as pd
import altair as alt
import re
from datetime import datetime, timedelta
from data_loader import load_nhl_data, get_player_game_log, load_schedule, load_weekly_leaders, get_weekly_schedule_matrix, load_nhl_news, fetch_espn_roster_data

st.set_page_config(layout="wide", page_title="Slapshot Stats")
st.title("🏒 Slapshot Stats")

# --- SESSION STATE ---
if 'my_roster' not in st.session_state: st.session_state.my_roster = []
if "trade_send" not in st.session_state: st.session_state.trade_send = []
if "trade_recv" not in st.session_state: st.session_state.trade_recv = []

# --- CALLBACKS ---
def add_player_from_select(side):
    key = "sb_send" if side == 'send' else "sb_recv"
    player = st.session_state.get(key)
    
    if player:
        target = st.session_state.trade_send if side == 'send' else st.session_state.trade_recv
        other = st.session_state.trade_recv if side == 'send' else st.session_state.trade_send
        if player not in target and player not in other:
            target.append(player)
        st.session_state[key] = None

def remove_player(player, side):
    target = st.session_state.trade_send if side == 'send' else st.session_state.trade_recv
    if player in target:
        target.remove(player)

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
    .game-live { margin-top: 5px; font-weight: bold; color: #ff4b4b; font-size: 1.0em; border-top: 1px solid #41444e; padding-top: 2px; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }

    /* NEWS STYLING */
    .news-container { background-color: #1e1e1e; border-radius: 12px; padding: 15px; border: 1px solid #333; }
    .news-card { display: flex; background-color: #262730; border: 1px solid #3a3b42; margin-bottom: 12px; border-radius: 8px; overflow: hidden; transition: transform 0.2s; }
    .news-card:hover { transform: translateY(-2px); border-color: #555; }
    .news-img { width: 110px; height: auto; object-fit: cover; flex-shrink: 0; border-right: 1px solid #3a3b42; }
    .news-content { padding: 10px; display: flex; flex-direction: column; justify-content: center; }
    .news-title { font-weight: bold; font-size: 0.95em; color: #fff; text-decoration: none; margin-bottom: 4px; line-height: 1.3; }
    .news-title:hover { color: #4da6ff; }
    .news-desc { font-size: 0.85em; color: #aaa; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

    /* TRADE STYLES */
    .trade-win { background-color: rgba(76, 175, 80, 0.15); border: 2px solid #4caf50; padding: 15px; border-radius: 8px; text-align: center; }
    .trade-loss { background-color: rgba(244, 67, 54, 0.15); border: 2px solid #f44336; padding: 15px; border-radius: 8px; text-align: center; }
    .selected-player-card { background-color: #333; border: 1px solid #555; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
    
    .link-btn { display: block; background-color: #262730; color: #ddd; text-align: center; padding: 8px; margin-bottom: 5px; text-decoration: none; border-radius: 4px; font-size: 0.9em; border: 1px solid #444; }
    .link-btn:hover { background-color: #444; color: white; border-color: #666; }
</style>
""", unsafe_allow_html=True)

with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. API might be down.")
else:
    # --- START REPLACEMENT HERE (Sidebar and Global Logic) ---

    # ==========================================
    # GLOBAL SETTINGS (SIDEBAR)
    # ==========================================
    with st.sidebar:
        st.header("⚙️ League Settings")
        st.caption("Enter your ESPN League ID (must be public)")

        # 1. League ID Input
        league_id = st.text_input(
            "ESPN League ID",
            key="league_id_input",
            placeholder="e.g., 234472"
        )
        
        # 2. Fantasy Scoring
        with st.expander("Fantasy Scoring (FP)", expanded=False):
            st.caption("Customize these to match your league.")
            val_G = st.number_input("Goals", value=2.0)
            val_A = st.number_input("Assists", value=1.0)
            val_PPP = st.number_input("PPP", value=0.5)
            val_SHP = st.number_input("SHP", value=0.5)
            val_SOG = st.number_input("SOG", value=0.1)
            val_Hit = st.number_input("Hits", value=0.1)
            val_BkS = st.number_input("Blocks", value=0.5)
            val_W = st.number_input("Wins", value=4.0)
            val_GA = st.number_input("GA", value=-2.0)
            val_Svs = st.number_input("Saves", value=0.2)
            val_SO = st.number_input("Shutouts", value=3.0)
            val_OTL = st.number_input("OTL", value=1.0)

    # --- GLOBAL DATA REPLACEMENT LOGIC ---
    if 'initial_df' not in st.session_state:
        st.session_state.initial_df = df.copy()

    if league_id:
        try:
            # Fetch roster data from ESPN (using 2026 for 2025-2026 season)
            roster_data, status = fetch_espn_roster_data(league_id, 2026)
            
            if status == 'SUCCESS':
                roster_players = [p for team in roster_data.values() for p in team]
                
                # Update player roster state
                st.session_state.my_roster = [p for p in st.session_state.my_roster if p in roster_players]

                # Update the main DataFrame's 'Team' column based on fetched roster
                df['Team'] = df['Player'].apply(lambda x: 
                                                next((team_abbr for team_abbr, players in roster_data.items() if x in players), x)
                                                if x in roster_players else 'FA')
            
            elif status == 'PRIVATE':
                st.sidebar.error("Error: League is Private or Invalid ID. Cannot fetch rosters.")
                df = st.session_state.initial_df.copy() # Revert to initial data if error

            elif status == 'FAILED_FETCH':
                st.sidebar.error("Error fetching ESPN data. Check ID or season.")
                df = st.session_state.initial_df.copy() # Revert to initial data if error

        except Exception as e:
            # st.sidebar.error(f"An unexpected error occurred: {e}")
            df = st.session_state.initial_df.copy() # Fallback

    # --- CALCULATE FP GLOBALLY (Needs to run after data substitution) ---
    df['FP'] = ((df['G'] * val_G) + (df['A'] * val_A) + (df['PPP'] * val_PPP) + 
                (df['SHP'] * val_SHP) + (df['SOG'] * val_SOG) + (df['Hits'] * val_Hit) + 
                (df['BkS'] * val_BkS) + (df['W'] * val_W) + (df['GA'] * val_GA) + 
                (df['Svs'] * val_Svs) + (df['SO'] * val_SO) + (df['OTL'] * val_OTL)).round(1)

    df['GamesRemaining'] = 82 - df['GP']
    def calc_ros(col): return (df[col] / df['GP']).fillna(0) * df['GamesRemaining']
    for s in ['G', 'A', 'Pts', 'PPP', 'SHP', 'SOG', 'Hits', 'BkS', 'FP', 'W', 'Svs', 'SO']:
        if s in df.columns: df[f'ROS_{s}'] = calc_ros(s)

    # --- END REPLACEMENT HERE ---

    tab_home, tab_analytics, tab_tools, tab_fantasy = st.tabs(["🏠 Home", "📊 Data & Analytics", "🛠️ Fantasy Tools", "⚔️ My Fantasy Team"])

    # ================= TAB 1: HOME =================
    with tab_home:
        st.header("📅 Today's Games")
        schedule = load_schedule()
        if not schedule: st.info("No games scheduled.")
        else:
            cols_per_row = 5
            for i in range(0, len(schedule), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(schedule):
                        game = schedule[i+j]
                        with cols[j]:
                            status_class = "game-live" if game.get("is_live") else "game-time"
                            st.markdown(f"""
                            <div class="game-card">
                                <div class="team-row">
                                    <div class="team-info"><img src="{game['away_logo']}" class="team-logo"><div class="team-name">{game['away']}</div></div>
                                    <div class="vs-text">@</div>
                                    <div class="team-info"><img src="{game['home_logo']}" class="team-logo"><div class="team-name">{game['home']}</div></div>
                                </div>
                                <div class="{status_class}">{game['time']}</div>
                            </div>""", unsafe_allow_html=True)
        st.divider()
        col_sos, col_news = st.columns([3, 2])
        
        # --- SOS TABLE (LOGOS) ---
        with col_sos:
            st.header("💪 Strength of Schedule")
            with st.spinner("Calculating..."):
                sos_matrix, standings = get_weekly_schedule_matrix()
            
            if not sos_matrix.empty and standings:
                def get_logo(abbr): return f"https://assets.nhle.com/logos/nhl/svg/{abbr}_light.svg"
                sos_display = sos_matrix.copy()
                sos_display.index = sos_display.index.map(get_logo)
                sos_display.reset_index(inplace=True)
                sos_display.rename(columns={'index': 'Team'}, inplace=True) 
                
                day_cols = [c for c in sos_display.columns if c != 'Team']
                for col in day_cols:
                    def transform_cell(val):
                        if not val or val == "": return None
                        parts = val.split(" ")
                        if len(parts) > 1: return get_logo(parts[1])
                        return None
                    sos_display[col] = sos_display[col].apply(transform_cell)

                def color_sos_logos(val, my_team_url):
                    if not val: return 'background-color: #262730'
                    try:
                        opp_abbr = val.split('/')[-1].split('_')[0]
                        my_abbr = my_team_url.split('/')[-1].split('_')[0]
                        my_str = standings.get(my_abbr, 0.5); opp_str = standings.get(opp_abbr, 0.5)
                        diff = my_str - opp_str
                        if diff > 0.15: return 'background-color: #1b5e20'
                        elif diff > 0.05: return 'background-color: #2e7d32'
                        elif diff > 0.00: return 'background-color: #4caf50'
                        elif diff > -0.05: return 'background-color: #fbc02d'
                        elif diff > -0.15: return 'background-color: #c62828'
                        else: return 'background-color: #b71c1c'
                    except: return 'background-color: #262730'

                styled_sos = sos_display.style.apply(lambda row: [color_sos_logos(row[c], row['Team']) for c in sos_display.columns], axis=1)
                column_config = {"Team": st.column_config.ImageColumn("Team", width="small")}
                day_cols = [c for c in sos_display.columns if c != 'Team']
                for col in day_cols: column_config[col] = st.column_config.ImageColumn(col, width="small")

                st.dataframe(styled_sos, use_container_width=True, height=500, column_config=column_config, hide_index=True)
            else: st.info("SOS data unavailable.")

        with col_news:
            st.header("📰 Latest Headlines")
            with st.container(border=True):
                news = load_nhl_news()
                if news:
                    for article in news:
                        img_html = f'<img src="{article["image"]}" class="news-img">' if article['image'] else ''
                        st.markdown(f"""<div class="news-card">{img_html}<div class="news-content"><a href="{article['link']}" target="_blank" class="news-title">{article['headline']}</a><p class="news-desc">{article['description']}</p></div></div>""", unsafe_allow_html=True)
                else: st.info("No news.")

            st.markdown("#### More Trusted Sources")
            st.markdown("""<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px;"><a href="https://www.tsn.ca/nhl" target="_blank" class="link-btn">TSN Hockey</a><a href="https://www.sportsnet.ca/nhl/" target="_blank" class="link-btn">Sportsnet</a><a href="https://www.dailyfaceoff.com/" target="_blank" class="link-btn">Daily Faceoff</a><a href="https://theathletic.com/nhl/" target="_blank" class="link-btn">The Athletic</a></div>""", unsafe_allow_html=True)

        st.divider()
        st.header("🔥 Hot This Week (Last 7 Days)")
        with st.spinner("Loading weekly trends..."):
            df_weekly = load_weekly_leaders()
        if not df_weekly.empty:
            def make_mini_chart(data, x_col, y_col, color, title):
                sorted_data = data.sort_values(y_col, ascending=False).head(5)
                chart = alt.Chart(sorted_data).mark_bar(cornerRadiusEnd=4).encode(x=alt.X(f'{y_col}:Q', title=None), y=alt.Y(f'{x_col}:N', sort='-x', title=None), color=alt.value(color), tooltip=[x_col, y_col]).properties(title=title, height=200)
                text = chart.mark_text(align='left', dx=2).encode(text=f'{y_col}:Q')
                return (chart + text)
            c1, c2 = st.columns(2)
            with c1: st.altair_chart(make_mini_chart(df_weekly, 'Player', 'G', '#ff4b4b', 'Top Goal Scorers'), use_container_width=True)
            with c2: st.altair_chart(make_mini_chart(df_weekly, 'Player', 'Pts', '#0083b8', 'Top Points Leaders'), use_container_width=True)
            c3, c4 = st.columns(2)
            with c3: st.altair_chart(make_mini_chart(df_weekly, 'Player', 'SOG', '#ffa600', 'Most Shots on Goal'), use_container_width=True)
            with c4: st.altair_chart(make_mini_chart(df_weekly, 'Player', 'PPP', '#58508d', 'Power Play Points'), use_container_width=True)

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
        st.subheader("League Summary")
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
        whole_num_cols = ['GP', 'G', 'A', 'Pts', 'PPP', 'SHP', 'SOG', 'Hits', 'BkS', 'W', 'GA', 'Svs', 'SO', 'OTL', '+/-', 'GWG']
        valid_whole = [c for c in whole_num_cols if c in filt_df.columns]
        styled_df = styled_df.format("{:.0f}", subset=valid_whole)
        styled_df = styled_df.format("{:.1f}", subset=['FP', 'ROS_FP', 'Sh%', 'FO%', 'SAT%', 'USAT%'])
        styled_df = styled_df.format("{:.2f}", subset=['GAA', 'GSAA'])
        styled_df = styled_df.format("{:.3f}", subset=['SV%'])
        cols = ['ID', 'Player', 'Team', 'Pos', 'FP', 'ROS_FP'] + [c for c in df.columns if c not in ['ID', 'Player', 'Team', 'Pos', 'FP', 'PosType', 'ROS_FP', 'GamesRemaining'] and not c.startswith('ROS_')]
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600, column_order=cols)

    # ================= TAB 3: FANTASY TOOLS =================
    with tab_tools:
        st.header("⚖️ Trade Analyzer")
        st.info("Compare players based on current stats and **Rest of Season (ROS)** projections.")
        
        if 'Player' in df.columns:
            all_players = sorted(df['Player'].dropna().astype(str).unique().tolist())
        else:
            all_players = []
            st.error("Player data not found.")

        def show_selected_player_card(player_name, side):
            p_data = df[df['Player'] == player_name].iloc[0]
            pid = p_data['ID']
            team = p_data['Team']
            img_url = f"https://assets.nhle.com/mugs/nhl/20252026/{team}/{pid}.png"
            with st.container(border=True):
                r1, r2, r3, r4 = st.columns([0.25, 0.35, 0.3, 0.1])
                with r
