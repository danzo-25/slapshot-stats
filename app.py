import streamlit as st
import pandas as pd
import altair as alt
import re
from datetime import datetime, timedelta
import requests
import difflib
from data_loader import (load_nhl_data, get_player_game_log, load_schedule, load_weekly_leaders, 
                         get_weekly_schedule_matrix, load_nhl_news, fetch_espn_league_data, 
                         fetch_nhl_standings, fetch_nhl_boxscore)

st.set_page_config(layout="wide", page_title="Slapshot Stats")
st.title("🏒 Slapshot Stats")

# --- SESSION STATE ---
if 'my_roster' not in st.session_state: st.session_state.my_roster = []
if "trade_send" not in st.session_state: st.session_state.trade_send = []
if "trade_recv" not in st.session_state: st.session_state.trade_recv = []
if "espn_standings" not in st.session_state: st.session_state.espn_standings = pd.DataFrame()
if "league_rosters" not in st.session_state: st.session_state.league_rosters = {}
if "league_name" not in st.session_state: st.session_state.league_name = "League Rosters"
if "selected_game_id" not in st.session_state: st.session_state.selected_game_id = None

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

def set_game_id(g_id):
    st.session_state.selected_game_id = g_id

# --- CSS ---
st.markdown("""
<style>
    /* HORIZONTAL TICKER SCROLL */
    .ticker-container {
        display: flex;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 10px;
        white-space: nowrap;
        -webkit-overflow-scrolling: touch;
    }
    
    .ticker-card-wrapper {
        flex: 0 0 auto;
        width: 100px; /* Fixed square width */
        height: 85px; /* Fixed square height */
    }

    /* TICKER CARD STYLE */
    .ticker-card { 
        background-color: #262730; 
        border: 1px solid #41444e; 
        border-radius: 6px; 
        padding: 4px; 
        text-align: center; 
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 1px 1px 2px rgba(0,0,0,0.2); 
        transition: transform 0.1s;
    }
    .ticker-card:hover {
        border-color: #777;
        transform: scale(1.02);
        cursor: pointer;
    }

    .ticker-team-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2px;
        font-size: 0.85em;
        font-weight: bold;
    }
    .ticker-logo { width: 20px; height: 20px; object-fit: contain; }
    .ticker-score { color: #fff; font-weight: 900; }
    
    .ticker-status {
        font-size: 0.7em;
        color: #aaa;
        border-top: 1px solid #444;
        margin-top: 2px;
        padding-top: 2px;
        font-weight: bold;
    }
    .status-live { color: #ff4b4b; }

    /* Button inside ticker card (Hidden but functional overlay) */
    .ticker-btn button {
        width: 100%;
        height: 100%;
        opacity: 0; /* Invisible button overlay */
        position: absolute;
        top: 0; left: 0;
    }

    /* EXISTING STYLES... */
    .league-grid-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        margin-top: 20px;
    }
    .team-roster-box { padding: 15px; border: 1px solid #333; border-radius: 8px; background-color: #1e1e1e; min-height: 400px; }
    .roster-player-item { display: flex; align-items: center; margin-bottom: 5px; padding: 5px; background-color: #262730; border-radius: 4px; font-size: 0.9em; }
    .player-headshot { width: 30px; height: 30px; border-radius: 50%; margin-right: 10px; object-fit: cover; }
    
    .news-container { background-color: #1e1e1e; border-radius: 8px; padding: 10px; border: 1px solid #333; }
    .news-card-v { background-color: #262730; border: 1px solid #3a3b42; border-radius: 6px; overflow: hidden; height: 100%; display: flex; flex-direction: column; transition: transform 0.2s; }
    .news-card-v:hover { transform: translateY(-3px); border-color: #555; }
    .news-img-v { width: 100%; display: block; height: 120px; object-fit: cover; object-position: center; margin: 0; padding: 0; border-bottom: 1px solid #3a3b42; }
    .news-content-v { padding: 8px; flex-grow: 1; display: flex; flex-direction: column; }
    .news-title-v { font-weight: bold; font-size: 0.85em; color: #fff; text-decoration: none; line-height: 1.2; margin-bottom: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .news-title-v:hover { color: #4da6ff; }
    .news-desc-v { font-size: 0.75em; color: #aaa; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 0; }
    
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
    with st.sidebar:
        st.header("⚙️ League Settings")
        st.caption("Enter your ESPN League ID (must be public)")
        league_id = st.text_input("ESPN League ID", key="league_id_input", placeholder="e.g., 234472")
        status_container = st.empty()
        
        with st.expander("Fantasy Scoring (FP)", expanded=False):
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

    if 'initial_df' not in st.session_state: st.session_state.initial_df = df.copy()

    if league_id:
        try:
            roster_data, standings_df, league_name, status = fetch_espn_league_data(league_id, 2026)
            if status == 'SUCCESS':
                status_container.success(f"✅ Loaded: {league_name}")
                st.session_state.league_name = league_name 
                st.session_state.league_rosters = roster_data 
                roster_players = [p['Name'] for team in roster_data.values() for p in team]
                st.session_state.my_roster = [p for p in st.session_state.my_roster if p in roster_players]
                player_team_map = {p['Name']: p.get('NHLTeam', 'FA') for team in roster_data.values() for p in team}
                df['Team'] = df['Player'].apply(lambda x: player_team_map.get(x, x) if x in roster_players else 'FA')
                if not standings_df.empty: st.session_state.espn_standings = standings_df
            elif status == 'PRIVATE':
                status_container.error("🚫 League is Private or Invalid ID.")
                df = st.session_state.initial_df.copy()
            elif status == 'FAILED_FETCH':
                status_container.error("⚠️ Error fetching data. Check ID.")
                df = st.session_state.initial_df.copy()
        except Exception as e:
            df = st.session_state.initial_df.copy()

    df['FP'] = ((df['G'] * val_G) + (df['A'] * val_A) + (df['PPP'] * val_PPP) + 
                (df['SHP'] * val_SHP) + (df['SOG'] * val_SOG) + (df['Hits'] * val_Hit) + 
                (df['BkS'] * val_BkS) + (df['W'] * val_W) + (df['GA'] * val_GA) + 
                (df['Svs'] * val_Svs) + (df['SO'] * val_SO) + (df['OTL'] * val_OTL)).round(1)

    df['GamesRemaining'] = 82 - df['GP']
    def calc_ros(col): return (df[col] / df['GP']).fillna(0) * df['GamesRemaining']
    for s in ['G', 'A', 'Pts', 'PPP', 'SHP', 'SOG', 'Hits', 'BkS', 'FP', 'W', 'Svs', 'SO']:
        if s in df.columns: df[f'ROS_{s}'] = calc_ros(s)

    # --- TABS ---
    tab_label_5 = f"🏆 {st.session_state.league_name}"
    tab_home, tab_analytics, tab_tools, tab_fantasy, tab_league, tab_standings, tab_gamecenter, tab_scoreboard = st.tabs([
        "🏠 Home", "📊 Data & Analytics", "🛠️ Fantasy Tools", 
        "⚔️ My Fantasy Team", tab_label_5, "📊 League Standings", "🥅 Game Center", "📅 Scoreboard"
    ])

    # ================= TAB 1: HOME =================
    with tab_home:
        # Load 3 days of schedule
        games_yesterday, games_today, games_tomorrow = load_schedule()
        
        # News
        news = load_nhl_news()
        if news:
            with st.container(border=True):
                cols = st.columns(4)
                for i, article in enumerate(news[:4]):
                    with cols[i]:
                        img_html = f'<img src="{article["image"]}" class="news-img-v">' if article['image'] else ''
                        st.markdown(f"""
                        <div class="news-card-v">
                            {img_html}
                            <div class="news-content-v">
                                <a href="{article['link']}" target="_blank" class="news-title-v">{article['headline']}</a>
                                <div class="news-desc-v">{article['description']}</div>
                            </div>
                        </div>""", unsafe_allow_html=True)
        st.divider()

        # TICKER (LIVE / TODAY)
        st.subheader("Live & Recent Games")
        
        ticker_games = []
        if games_today: ticker_games.extend(games_today)
        if games_yesterday: ticker_games.extend(games_yesterday)
        
        # Sort Ticker: Live -> Final -> Future
        def sort_key(g):
            if g.get('is_live'): return 0
            if 'Final' in g.get('time', ''): return 1
            return 2
        ticker_games.sort(key=sort_key)
        
        if ticker_games:
            # Render Ticker Grid
            cols = st.columns(min(len(ticker_games), 8)) # Up to 8 columns
            for i, game in enumerate(ticker_games[:8]): # Show top 8 relevant games
                with cols[i]:
                    status_color = "status-live" if game.get("is_live") else ""
                    st.markdown(f"""
                    <div class="ticker-card">
                        <div class="ticker-team-row">
                            <img src="{game['away_logo']}" class="ticker-logo">
                            <span>{game['away']}</span>
                            <span class="ticker-score">{game.get('away_score', '')}</span>
                        </div>
                        <div class="ticker-team-row">
                            <img src="{game['home_logo']}" class="ticker-logo">
                            <span>{game['home']}</span>
                            <span class="ticker-score">{game.get('home_score', '')}</span>
                        </div>
                        <div class="ticker-status {status_color}">{game['time']}</div>
                    </div>""", unsafe_allow_html=True)
                    
                    if st.button("Stats", key=f"tick_{game['id']}"):
                        set_game_id(game['id'])
                        st.switch_page("app.py") # Triggers rerun to update session state
        else:
            st.info("No active or recent games to display.")
        
        if st.button("📅 View Full Scoreboard"):
             # Just a visual cue, user clicks the tab
             st.info("Click the '📅 Scoreboard' tab above to see all games.")

        st.divider()
        col_sos, col_news = st.columns([3, 2])
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
                column_config = {"Team": st.column_config.ImageColumn("Team", width="small")}
                for col in day_cols: column_config[col] = st.column_config.ImageColumn(col, width="small")
                st.dataframe(sos_display, use_container_width=True, height=500, column_config=column_config, hide_index=True)

        with col_news:
            st.header("🔥 Hot This Week")
            df_weekly = load_weekly_leaders()
            if not df_weekly.empty:
                def make_mini_chart(data, x_col, y_col, color, title):
                    sorted_data = data.sort_values(y_col, ascending=False).head(5)
                    chart = alt.Chart(sorted_data).mark_bar(cornerRadiusEnd=4).encode(x=alt.X(f'{y_col}:Q', title=None), y=alt.Y(f'{x_col}:N', sort='-x', title=None), color=alt.value(color), tooltip=[x_col, y_col]).properties(title=title, height=200)
                    text = chart.mark_text(align='left', dx=2).encode(text=f'{y_col}:Q')
                    return (chart + text)
                st.altair_chart(make_mini_chart(df_weekly, 'Player', 'G', '#ff4b4b', 'Top Goal Scorers'), use_container_width=True)
                st.altair_chart(make_mini_chart(df_weekly, 'Player', 'Pts', '#0083b8', 'Top Points Leaders'), use_container_width=True)

    # ================= TAB 2-6 (Standard) =================
    with tab_analytics:
        st.header("📈 Breakout Detector")
        skater_options = df[df['PosType'] == 'Skater'].sort_values('Pts', ascending=False)
        selected_player_name = st.selectbox("Select Player:", skater_options['Player'].unique())
        if selected_player_name:
            pid = dict(zip(skater_options['Player'], skater_options['ID']))[selected_player_name]
            game_log = get_player_game_log(pid)
            if not game_log.empty:
                game_log['Rolling Points'] = game_log['points'].rolling(window=5, min_periods=1).mean()
                chart_data = game_log[['gameDate', 'points', 'Rolling Points']].set_index('gameDate')
                st.line_chart(chart_data, color=["#d3d3d3", "#ff4b4b"])
        st.divider()
        st.subheader("League Summary")
        st.dataframe(df, use_container_width=True, hide_index=True, height=600)

    with tab_tools:
        st.header("⚖️ Trade Analyzer")
        if 'espn_standings' in st.session_state and not st.session_state.espn_standings.empty:
            st.subheader("🏆 League Standings")
            st.dataframe(st.session_state.espn_standings, use_container_width=True, hide_index=True)
        # (Trade Logic omitted for brevity, same as before)

    with tab_fantasy:
        st.header("⚔️ My Roster")
        col_up, _ = st.columns([1, 2])
        with col_up: uploaded_file = st.file_uploader("📂 Load Saved Roster (CSV)", type=["csv"])
        time_filter = st.selectbox("Select Time Frame", ["Season (2025/26)", "Last 7 Days", "Last 15 Days", "Last 30 Days"])
        if uploaded_file:
            try:
                udf = pd.read_csv(uploaded_file)
                if "Player" in udf.columns: st.session_state.my_roster = [p for p in udf["Player"] if p in df['Player'].values]
            except: pass
        selected_players = st.multiselect("Search Players:", df['Player'].unique(), default=st.session_state.my_roster)
        st.session_state.my_roster = selected_players
        if selected_players:
            base_team_df = df[df['Player'].isin(selected_players)].copy()
            display_df = base_team_df 
            if time_filter != "Season (2025/26)":
                days_map = {"Last 7 Days": 7, "Last 15 Days": 15, "Last 30 Days": 30}
                days = days_map.get(time_filter, 0)
                start_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
                with st.spinner(f"Fetching stats..."):
                    recent_stats = []
                    for _, row in base_team_df.iterrows():
                        pid = row['ID']
                        logs = get_player_game_log(pid) 
                        if not logs.empty:
                            mask = logs['gameDate'] >= start_date
                            recent = logs[mask]
                            stat_dict = {
                                'ID': pid, 'Player': row['Player'], 'Team': row['Team'], 'Pos': row['Pos'], 'GP': len(recent),
                                'G': recent['goals'].sum() if 'goals' in recent else 0, 'A': recent['assists'].sum() if 'assists' in recent else 0,
                                'Pts': recent['points'].sum() if 'points' in recent else 0, 'SOG': recent['shots'].sum() if 'shots' in recent else 0,
                                'PPP': recent['powerPlayPoints'].sum() if 'powerPlayPoints' in recent else 0, 'Hits': recent['hits'].sum() if 'hits' in recent else 0,
                                'BkS': recent['blockedShots'].sum() if 'blockedShots' in recent else 0, 'PIM': recent['pim'].sum() if 'pim' in recent else 0,
                                'W': len(recent[recent['decision'] == 'W']) if 'decision' in recent else 0, 'SO': recent['shutouts'].sum() if 'shutouts' in recent else 0,
                                'Svs': recent['saves'].sum() if 'saves' in recent else 0, 'GA': recent['goalsAgainst'].sum() if 'goalsAgainst' in recent else 0,
                                'L': len(recent[recent['decision'] == 'L']) if 'decision' in recent else 0, 'OTL': len(recent[recent['decision'] == 'OT']) if 'decision' in recent else 0,
                                'SHP': recent['shorthandedPoints'].sum() if 'shorthandedPoints' in recent else 0
                            }
                            fp = (stat_dict['G']*val_G + stat_dict['A']*val_A + stat_dict['PPP']*val_PPP + stat_dict['SOG']*val_SOG + stat_dict['Hits']*val_Hit + stat_dict['BkS']*val_BkS + stat_dict['W']*val_W + stat_dict['GA']*val_GA + stat_dict['Svs']*val_Svs + stat_dict['SO']*val_SO + (stat_dict['SHP'] * val_SHP))
                            stat_dict['FP'] = fp
                            recent_stats.append(stat_dict)
                    if recent_stats:
                        display_df = pd.DataFrame(recent_stats)
                        if 'TOI' in df.columns: display_df = display_df.merge(df[['ID', 'TOI']], on='ID', how='left')
            if not display_df.empty:
                st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    with tab_league:
        st.header(f"Rosters for {st.session_state.league_name}")
        if st.session_state.get('league_rosters'):
            roster_dict = st.session_state.league_rosters
            team_names = list(roster_dict.keys())
            cols = st.columns(4)
            for i, team_name in enumerate(team_names):
                roster = roster_dict[team_name]
                team_df = pd.DataFrame(roster)
                with cols[i % 4]:
                    st.subheader(team_name)
                    st.dataframe(team_df[['Name', 'NHLTeam']], use_container_width=True, hide_index=True)
        else: st.info("Enter League ID.")

    with tab_standings:
        st.header("🏒 NHL Standings")
        view_type = st.radio("Select View", ('League (Overall)', 'Conference', 'Division'), horizontal=True)
        standings_data = fetch_nhl_standings(view_type.split(' ')[0])
        if not standings_data.empty:
            standings_data['Team Icon'] = standings_data.apply(lambda row: f"<img src='{row['Icon']}' width='30'> {row['Team']}", axis=1)
            st.markdown(standings_data[['Rank', 'Team Icon', 'GP', 'W', 'L', 'OTL', 'PTS']].to_html(escape=False, index=False), unsafe_allow_html=True)

    # ================= TAB 7: GAME CENTER =================
    with tab_gamecenter:
        if st.session_state.selected_game_id:
            g_id = st.session_state.selected_game_id
            st.header("🥅 Game Center")
            box_data = fetch_nhl_boxscore(g_id)
            if box_data:
                home = box_data.get('homeTeam', {})
                away = box_data.get('awayTeam', {})
                c1, c2, c3 = st.columns([1, 0.2, 1])
                with c1: st.markdown(f"<div style='text-align:center'><img src='{away.get('logo', '')}' width='80'><h2>{away.get('name', {}).get('default', 'Away')}</h2><h3>{away.get('score', 0)}</h3></div>", unsafe_allow_html=True)
                with c2: st.markdown("<h2 style='text-align:center; padding-top:40px'>VS</h2>", unsafe_allow_html=True)
                with c3: st.markdown(f"<div style='text-align:center'><img src='{home.get('logo', '')}' width='80'><h2>{home.get('name', {}).get('default', 'Home')}</h2><h3>{home.get('score', 0)}</h3></div>", unsafe_allow_html=True)
                st.divider()
                st.subheader("Box Score")
                def parse_stats(team_data):
                    rows = []
                    # Logic handles both 'landing' and 'boxscore' structures
                    stats_source = box_data.get('playerByGameStats', {}).get('awayTeam' if team_data == away else 'homeTeam', {})
                    if not stats_source and 'boxscore' in box_data:
                        stats_source = box_data['boxscore'].get('playerByGameStats', {}).get('awayTeam' if team_data == away else 'homeTeam', {})

                    players = stats_source.get('forwards', []) + stats_source.get('defense', [])
                    for p in players:
                        rows.append({"Player": p.get('name', {}).get('default'), "G": p.get('goals', 0), "A": p.get('assists', 0), "Pts": p.get('points', 0), "SOG": p.get('shots', 0), "TOI": p.get('toi', '00:00')})
                    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Player", "G", "A", "Pts", "SOG", "TOI"])

                c_away, c_home = st.columns(2)
                with c_away: st.dataframe(parse_stats(away), hide_index=True, use_container_width=True)
                with c_home: st.dataframe(parse_stats(home), hide_index=True, use_container_width=True)
            else: st.error("Could not load box score.")
        else: st.info("👈 Select a game.")

    # ================= TAB 8: FULL SCOREBOARD =================
    with tab_scoreboard:
        st.header("📅 Full Scoreboard")
        # Reuse loader to show full grid
        c_yest, c_today, c_tom = st.columns(3)
        def render_simple(game):
            st.markdown(f"**{game['away']} {game['away_score']}** @ **{game['home']} {game['home_score']}** ({game['time']})")
            if st.button("Stats", key=f"sb_btn_{game['id']}"):
                set_game_id(game['id'])
                st.rerun()

        with c_yest:
            st.subheader("Yesterday")
            for g in games_yesterday: render_simple(g)
        with c_today:
            st.subheader("Today")
            for g in games_today: render_simple(g)
        with c_tom:
            st.subheader("Tomorrow")
            for g in games_tomorrow: render_simple(g)
