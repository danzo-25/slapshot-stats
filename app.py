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
    /* Horizontal scrolling container for game tiles */
    .horizontal-scroll-container {
        display: flex;
        flex-direction: row;
        overflow-x: auto;
        gap: 10px;
        padding: 10px 0;
        white-space: nowrap;
        -webkit-overflow-scrolling: touch; /* For smooth scrolling on mobile */
    }

    /* Ensure game cards are inline-block to sit next to each other */
    .game-card-wrapper {
        display: inline-block;
        width: 200px; /* Fixed width for uniformity */
        flex-shrink: 0; /* Prevent cards from shrinking */
    }

    /* Tab 5 Grid */
    .league-grid-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        margin-top: 20px;
    }
    .team-roster-box {
        padding: 15px;
        border: 1px solid #333;
        border-radius: 8px;
        background-color: #1e1e1e;
        min-height: 400px;
    }
    .roster-player-item {
        display: flex;
        align-items: center;
        margin-bottom: 5px;
        padding: 5px;
        background-color: #262730;
        border-radius: 4px;
        font-size: 0.9em;
    }
    .player-headshot {
        width: 30px;
        height: 30px;
        border-radius: 50%;
        margin-right: 10px;
        object-fit: cover;
    }

    /* ULTRA COMPACT GAME CARDS */
    .game-card { 
        background-color: #262730; 
        border: 1px solid #41444e; 
        border-radius: 4px; 
        padding: 0px 1px; 
        text-align: center; 
        margin: 0 auto 0 auto; 
        width: 100%; /* Fill the wrapper */
        box-shadow: 1px 1px 2px rgba(0,0,0,0.2); 
        line-height: 1.0; 
    }
    .team-row { 
        display: flex; 
        justify-content: center; 
        align-items: center; 
        gap: 2px; 
        padding-top: 0px;
        padding-bottom: 0px;
    }
    .team-info { 
        display: flex; 
        flex-direction: row; 
        align-items: center;
        gap: 2px;
    }
    .team-logo { 
        width: 24px; 
        height: 24px; 
        object-fit: contain; 
        margin: 0;
    }
    .team-name { 
        font-weight: 900; 
        font-size: 1.0em; 
        margin: 0; 
        line-height: 1;
        color: #fff;
    }
    .vs-text { 
        font-size: 0.9em; 
        font-weight: bold; 
        color: #aaa; 
        margin: 0; 
    }
    .game-time { 
        margin-top: 0px; 
        font-weight: bold; 
        color: #FF4B4B; 
        font-size: 0.9em; 
        border-top: 1px solid #41444e; 
        padding-top: 0px;
        padding-bottom: 0px;
    }
    .game-live { 
        margin-top: 0px; 
        font-weight: bold; 
        color: #ff4b4b; 
        font-size: 0.95em; 
        border-top: 1px solid #41444e; 
        padding-top: 0px;
        padding-bottom: 0px;
        animation: pulse 2s infinite; 
    }
    
    div.stButton > button {
        width: 100%; /* Match card width */
        padding: 2px 5px;
        font-size: 0.75rem;
        line-height: 1.2;
        min-height: 0px;
        margin-top: 2px;
    }

    /* NEWS STYLING */
    .news-container { background-color: #1e1e1e; border-radius: 8px; padding: 10px; border: 1px solid #333; }
    .news-card-v { background-color: #262730; border: 1px solid #3a3b42; border-radius: 6px; overflow: hidden; height: 100%; display: flex; flex-direction: column; transition: transform 0.2s; }
    .news-card-v:hover { transform: translateY(-3px); border-color: #555; }
    .news-img-v { width: 100%; display: block; height: 120px; object-fit: cover; object-position: center; margin: 0; padding: 0; border-bottom: 1px solid #3a3b42; }
    .news-content-v { padding: 8px; flex-grow: 1; display: flex; flex-direction: column; }
    .news-title-v { font-weight: bold; font-size: 0.85em; color: #fff; text-decoration: none; line-height: 1.2; margin-bottom: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .news-title-v:hover { color: #4da6ff; }
    .news-desc-v { font-size: 0.75em; color: #aaa; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 0; }

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
    # --- SIDEBAR ---
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

    # --- GLOBAL DATA REPLACEMENT ---
    if 'initial_df' not in st.session_state:
        st.session_state.initial_df = df.copy()

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
                if not standings_df.empty:
                    st.session_state.espn_standings = standings_df
            elif status == 'PRIVATE':
                status_container.error("🚫 League is Private or Invalid ID.")
                df = st.session_state.initial_df.copy()
            elif status == 'FAILED_FETCH':
                status_container.error("⚠️ Error fetching data. Check ID.")
                df = st.session_state.initial_df.copy()
        except Exception as e:
            df = st.session_state.initial_df.copy()

    # --- CALCULATE FP ---
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
    tab_home, tab_analytics, tab_tools, tab_fantasy, tab_league, tab_standings, tab_gamecenter = st.tabs([
        "🏠 Home", "📊 Data & Analytics", "🛠️ Fantasy Tools", 
        "⚔️ My Fantasy Team", tab_label_5, "📊 League Standings", "🥅 Game Center"
    ])

    # ================= TAB 1: HOME =================
    with tab_home:
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
                        </div>
                        """, unsafe_allow_html=True)
        st.divider()

        # Games (Horizontal Banner Layout)
        def render_game_card_with_button(game):
            status_class = "game-live" if game.get("is_live") else "game-time"
            st.markdown(f"""
            <div class="game-card">
                <div class="team-row">
                    <div class="team-info"><img src="{game['away_logo']}" class="team-logo"><div class="team-name">{game['away']}</div></div>
                    <div class="vs-text">@</div>
                    <div class="team-info"><div class="team-name">{game['home']}</div><img src="{game['home_logo']}" class="team-logo"></div>
                </div>
                <div class="{status_class}">{game['time']}</div>
            </div>""", unsafe_allow_html=True)
            
            if st.button("Stats", key=f"btn_{game['id']}", use_container_width=True):
                set_game_id(game['id'])
                st.rerun()

        # Combine all games into one list
        all_games = []
        if games_yesterday: all_games.extend(games_yesterday)
        if games_today: all_games.extend(games_today)
        if games_tomorrow: all_games.extend(games_tomorrow)

        if not all_games:
            st.info("No games found for Yesterday, Today, or Tomorrow.")
        else:
            # Use a horizontal scrolling container
            st.markdown('<div class="horizontal-scroll-container">', unsafe_allow_html=True)
            for game in all_games:
                # Wrap each card in a container to control its width in the flex row
                st.markdown(f'<div class="game-card-wrapper">', unsafe_allow_html=True)
                render_game_card_with_button(game)
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

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
                st.dataframe(styled_sos := sos_display.style.apply(lambda row: ['background-color: #262730']*len(row), axis=1), use_container_width=True, hide_index=True, column_config=column_config)

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

    # ================= TAB 2-6 (Standard Tabs) =================
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
        filt_df = df.copy() 
        st.dataframe(filt_df, use_container_width=True, hide_index=True, height=600)

    with tab_tools:
        st.header("⚖️ Trade Analyzer")
        
        # ADDED CHECK: Ensure main DF is loaded
        if df.empty:
            st.warning("Player data is not available. Please check the API connection.")
        else:
            if 'espn_standings' in st.session_state and not st.session_state.espn_standings.empty:
                st.subheader("🏆 League Standings")
                st.dataframe(
                    st.session_state.espn_standings.style.apply(lambda x: ['background-color: #262730']*len(x), axis=1),
                    use_container_width=True,
                    hide_index=True
                )
                st.divider()

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
                    with r1: st.image(img_url, width=60)
                    with r2:
                        st.markdown(f"**{player_name}**")
                        st.caption(f"{p_data['Team']} • {p_data['Pos']}")
                    with r3:
                        st.markdown(f"**FP:** {p_data['FP']:.1f}")
                        st.markdown(f"**ROS:** {p_data['ROS_FP']:.1f}")
                    with r4:
                        if st.button("❌", key=f"del_{side}_{player_name}"):
                            remove_player(player_name, side)
                            st.rerun()

            c1, c_mid, c2 = st.columns([1, 0.1, 1])
            with c1:
                st.subheader("📤 Sending")
                opts_s = [p for p in all_players if p not in st.session_state.trade_recv]
                st.selectbox("Add Player", options=opts_s, index=None, placeholder="Type to add...", key="sb_send", on_change=add_player_from_select, args=('send',), label_visibility="collapsed")
                if st.session_state.trade_send:
                    for p in st.session_state.trade_send: show_selected_player_card(p, "send")
            with c2:
                st.subheader("📥 Receiving")
                opts_r = [p for p in all_players if p not in st.session_state.trade_send]
                st.selectbox("Add Player", options=opts_r, index=None, placeholder="Type to add...", key="sb_recv", on_change=add_player_from_select, args=('recv',), label_visibility="collapsed")
                if st.session_state.trade_recv:
                    for p in st.session_state.trade_recv: show_selected_player_card(p, "recv")

            if st.session_state.trade_send or st.session_state.trade_recv:
                st.divider()
                df_send = df[df['Player'].isin(st.session_state.trade_send)]
                df_recv = df[df['Player'].isin(st.session_state.trade_recv)]
                
                if not df_send.empty and not df_recv.empty:
                    diff = df_recv['ROS_FP'].sum() - df_send['ROS_FP'].sum()
                    st.subheader("The Verdict")
                    if diff > 0: st.markdown(f"""<div class="trade-win"><h2>✅ You Win!</h2><p>Projected Gain: <b>+{diff:.1f} FP</b></p></div>""", unsafe_allow_html=True)
                    elif diff < 0: st.markdown(f"""<div class="trade-loss"><h2>❌ You Lose.</h2><p>Projected Loss: <b>{diff:.1f} FP</b></p></div>""", unsafe_allow_html=True)
                    else: st.info("Trade is even.")

                st.markdown("#### Projected Totals (Rest of Season)")
                stats_map = {'Fantasy Points': 'ROS_FP', 'Goals': 'ROS_G', 'Assists': 'ROS_A', 'Points': 'ROS_Pts', 'PPP': 'ROS_PPP', 'SOG': 'ROS_SOG', 'Hits': 'ROS_Hits', 'Blocks': 'ROS_BkS', 'Wins': 'ROS_W'}
                summary_data = []
                for label, col in stats_map.items():
                    if col in df.columns:
                        val_s = df_send[col].sum(); val_r = df_recv[col].sum()
                        summary_data.append({'Stat': label, 'Sending': val_s, 'Receiving': val_r, 'Net': val_r - val_s})
                
                # ADDED CHECK: Ensure summary data exists
                if summary_data:
                    summary_df = pd.DataFrame(summary_data).set_index('Stat')
                    def highlight_winner(row):
                        s, r = row['Sending'], row['Receiving']
                        green, red = 'color: #4caf50; font-weight: bold', 'color: #f44336; font-weight: bold'
                        if r > s: return [red, green, green] 
                        elif s > r: return [green, red, red] 
                        return ['', '', '',]
                    styled_summary = summary_df.style.format("{:+.1f}", subset=['Net']).format("{:.1f}", subset=['Sending', 'Receiving']).apply(highlight_winner, axis=1)
                    st.dataframe(styled_summary, use_container_width=True)
                else:
                    st.warning("Could not calculate projected totals. Missing data.")

                st.caption("Individual Player Stats (Current & Projected)")
                full_list = pd.concat([df_send, df_recv])
                if not full_list.empty:
                    full_list['Side'] = full_list['Player'].apply(lambda x: 'Receiving' if x in st.session_state.trade_recv else 'Sending')
                    cols_to_show = ['Side', 'Player', 'Team', 'Pos', 'FP', 'ROS_FP', 'G', 'ROS_G', 'A', 'ROS_A', 'Pts', 'ROS_Pts', 'PPP', 'ROS_PPP', 'SOG', 'ROS_SOG', 'Hits', 'ROS_Hits']
                    final_cols = [c for c in cols_to_show if c in full_list.columns]
                    trade_config = {
                        "Side": st.column_config.TextColumn("Side", pinned=True),
                        "Player": st.column_config.TextColumn("Player", pinned=True),
                        "FP": st.column_config.NumberColumn("FP", help="Current Fantasy Points", format="%.1f"),
                        "ROS_FP": st.column_config.NumberColumn("ROS FP", help="Rest of Season Projected FP", format="%.1f"),
                        "G": st.column_config.NumberColumn("G", help="Current Goals"), "ROS_G": st.column_config.NumberColumn("ROS G", help="Projected Goals"),
                        "A": st.column_config.NumberColumn("A", help="Current Assists"), "ROS_A": st.column_config.NumberColumn("ROS A", help="Projected Assists"),
                        "Pts": st.column_config.NumberColumn("Pts", help="Current Points"), "ROS_Pts": st.column_config.NumberColumn("ROS Pts", help="Projected Points"),
                    }
                    current_stats = ['G', 'A', 'Pts', 'PPP', 'SOG', 'Hits', 'BkS']
                    valid_current = [c for c in current_stats if c in final_cols]
                    proj_stats = [c for c in final_cols if 'ROS_' in c or 'FP' in c]
                    styled_player_table = full_list[final_cols].style.format("{:.0f}", subset=valid_current).format("{:.1f}", subset=proj_stats)
                    st.dataframe(styled_player_table, use_container_width=True, hide_index=True, column_config=trade_config)

    with tab_fantasy:
        st.header("⚔️ My Roster")
        col_up, _ = st.columns([1, 2])
        
        # --- ROW 1: FILE UPLOAD & TIME FILTER ---
        with col_up:
            uploaded_file = st.file_uploader("📂 Load Saved Roster (CSV)", type=["csv"])
        
        time_filter = st.selectbox("Select Time Frame", ["Season (2025/26)", "Last 7 Days", "Last 15 Days", "Last 30 Days"])

        # Import Roster from CSV if available
        if uploaded_file:
            try:
                udf = pd.read_csv(uploaded_file)
                if "Player" in udf.columns: st.session_state.my_roster = [p for p in udf["Player"] if p in df['Player'].values]
            except: pass

        # Manual Selection (Used for display if league ID isn't entered)
        selected_players = st.multiselect("Search Players:", df['Player'].unique(), default=st.session_state.my_roster)
        st.session_state.my_roster = selected_players

        if selected_players:
            base_team_df = df[df['Player'].isin(selected_players)].copy()
            
            # --- DATE FILTERING LOGIC ---
            display_df = base_team_df # Default to Season stats
            
            if time_filter != "Season (2025/26)":
                days_map = {"Last 7 Days": 7, "Last 15 Days": 15, "Last 30 Days": 30}
                days = days_map.get(time_filter, 0)
                
                # FIXED: Force Start Date to Midnight to avoid missing early games using Pandas Timestamp
                start_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
                
                st.caption(f"Showing stats from **{start_date.strftime('%Y-%m-%d')}** to Present")
                
                with st.spinner(f"Fetching stats for last {days} days..."):
                    recent_stats = []
                    for _, row in base_team_df.iterrows():
                        pid = row['ID']
                        logs = get_player_game_log(pid) 
                        if not logs.empty:
                            mask = logs['gameDate'] >= start_date
                            recent = logs[mask]
                            
                            stat_dict = {
                                'ID': pid, 'Player': row['Player'], 'Team': row['Team'], 'Pos': row['Pos'],
                                'GP': len(recent),
                                'G': recent['goals'].sum() if 'goals' in recent.columns else 0,
                                'A': recent['assists'].sum() if 'assists' in recent.columns else 0,
                                'Pts': recent['points'].sum() if 'points' in recent.columns else 0,
                                'SOG': recent['shots'].sum() if 'shots' in recent.columns else 0,
                                'PPP': recent['powerPlayPoints'].sum() if 'powerPlayPoints' in recent.columns else 0,
                                'Hits': recent['hits'].sum() if 'hits' in recent.columns else 0,
                                'BkS': recent['blockedShots'].sum() if 'blockedShots' in recent.columns else 0,
                                'PIM': recent['pim'].sum() if 'pim' in recent.columns else 0,
                                'W': len(recent[recent['decision'] == 'W']) if 'decision' in recent.columns else 0,
                                'SO': recent['shutouts'].sum() if 'shutouts' in recent.columns else 0,
                                'Svs': recent['saves'].sum() if 'saves' in recent.columns else 0,
                                'GA': recent['goalsAgainst'].sum() if 'goalsAgainst' in recent.columns else 0,
                                'L': len(recent[recent['decision'] == 'L']) if 'decision' in recent.columns else 0,
                                'OTL': len(recent[recent['decision'] == 'OT']) if 'decision' in recent.columns else 0,
                                'SHP': recent['shorthandedPoints'].sum() if 'shorthandedPoints' in recent.columns else 0,
                            }
                            fp = (stat_dict['G']*val_G + stat_dict['A']*val_A + stat_dict['PPP']*val_PPP + 
                                  stat_dict['SOG']*val_SOG + stat_dict['Hits']*val_Hit + stat_dict['BkS']*val_BkS +
                                  stat_dict['W']*val_W + stat_dict['GA']*val_GA + stat_dict['Svs']*val_Svs + stat_dict['SO']*val_SO + (stat_dict['SHP'] * val_SHP))
                            stat_dict['FP'] = fp
                            recent_stats.append(stat_dict)
                    
                    if recent_stats:
                        display_df = pd.DataFrame(recent_stats)
                        # Re-merge TOI from main df as it's not easily aggregated
                        if 'TOI' in df.columns:
                            display_df = display_df.merge(df[['ID', 'TOI']], on='ID', how='left')
            
            # --- RENDER METRICS ---
            st.download_button("💾 Save Roster", base_team_df[['Player']].to_csv(index=False), "roster.csv", "text/csv")
            
            # ADDED CHECK: Ensure display_df is not empty before rendering metrics and table
            if not display_df.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Goals", int(display_df['G'].sum()) if 'G' in display_df.columns else 0)
                c2.metric("Points", int(display_df['Pts'].sum()) if 'Pts' in display_df.columns else 0)
                c3.metric("Total FP", f"{display_df['FP'].sum():,.1f}" if 'FP' in display_df.columns else "0.0")
                c4.metric("Goalie Wins", int(display_df['W'].sum()) if 'W' in display_df.columns else 0)
                
                # --- RENDER TABLE ---
                all_possible_cols = ['Player', 'Team', 'Pos', 'FP', 'GP', 'G', 'A', 'Pts', 'GWG', 'SOG', 'Sh%', 'FO%', 'L', 'OTL', 'GAA', 'SV%', 'GSAA', 'SO', 'PIM', 'Hits', 'BkS', 'W', 'Svs', 'GA', 'TOI', 'SHP', 'PPP']
                final_cols = [c for c in all_possible_cols if c in display_df.columns and c != 'ID'] 
                
                roster_config = {
                    "Player": st.column_config.TextColumn("Player", pinned=True),
                    "FP": st.column_config.NumberColumn("FP", format="%.1f", help="Fantasy Points"),
                    "GP": st.column_config.NumberColumn("GP", format="%.0f", help="Games Played"),
                    "GWG": st.column_config.NumberColumn("GWG", format="%.0f", help="Game Winning Goals"),
                    "Sh%": st.column_config.NumberColumn("Sh%", format="%.1f", help="Shooting Percentage"),
                    "FO%": st.column_config.NumberColumn("FO%", format="%.1f", help="Faceoff Win Percentage"),
                    "L": st.column_config.NumberColumn("L", format="%.0f", help="Losses"),
                    "OTL": st.column_config.NumberColumn("OTL", format="%.0f", help="Overtime Losses"),
                    "GAA": st.column_config.NumberColumn("GAA", format="%.2f", help="Goals Against Average"),
                    "SV%": st.column_config.NumberColumn("SV%", format="%.3f", help="Save Percentage"),
                    "GSAA": st.column_config.NumberColumn("GSAA", format="%.2f", help="Goals Saved Above Average"),
                    "SO": st.column_config.NumberColumn("SO", format="%.0f", help="Shutouts"),
                    "PIM": st.column_config.NumberColumn("PIM", format="%.0f"),
                    "Hits": st.column_config.NumberColumn("Hits", format="%.0f"),
                    "BkS": st.column_config.NumberColumn("BkS", format="%.0f"),
                    "G": st.column_config.NumberColumn("G", format="%.0f"),
                    "A": st.column_config.NumberColumn("A", format="%.0f"),
                    "Pts": st.column_config.NumberColumn("Pts", format="%.0f"),
                    "SOG": st.column_config.NumberColumn("SOG", format="%.0f"),
                    "W": st.column_config.NumberColumn("W", format="%.0f"),
                    "GA": st.column_config.NumberColumn("GA", format="%.0f"),
                    "TOI": st.column_config.TextColumn("TOI", help="Time On Ice per Game (string format)"),
                    "SHP": st.column_config.NumberColumn("SHP", format="%.0f", help="Shorthanded Points"),
                    "PPP": st.column_config.NumberColumn("PPP", format="%.0f", help="Power Play Points"),
                }
                
                full_whole_num_cols = ['G', 'A', 'Pts', 'GWG', 'SOG', 'L', 'OTL', 'SO', 'GP', 'PIM', 'Hits', 'BkS', 'W', 'GA', 'Svs', 'SHP', 'PPP']
                valid_whole = [c for c in full_whole_num_cols if c in display_df.columns]
                
                valid_one_dec = [c for c in ['FP', 'Sh%', 'FO%'] if c in display_df.columns]
                valid_two_dec = [c for c in ['GAA', 'GSAA'] if c in display_df.columns]
                valid_three_dec = [c for c in ['SV%'] if c in display_df.columns]

                styled_team = display_df[final_cols].style \
                    .format("{:.0f}", subset=valid_whole) \
                    .format("{:.1f}", subset=valid_one_dec) \
                    .format("{:.2f}", subset=valid_two_dec) \
                    .format("{:.3f}", subset=valid_three_dec)

                st.dataframe(styled_team, use_container_width=True, hide_index=True, column_config=roster_config)
            else:
                st.info("No stats available for the selected players in this time frame.")
            
            # --- COLD TRENDS GRAPH ---
            st.divider()
            st.subheader("❄️ Cold Trends (Last 5 Games vs Season Avg)")
            
            trend_data = []
            for _, row in base_team_df.iterrows():
                pid = row['ID']
                logs = get_player_game_log(pid)
                
                if not logs.empty and len(logs) >= 5:
                    logs['GF_FP'] = (logs.get('goals',0)*val_G + logs.get('assists',0)*val_A + 
                                     logs.get('shots',0)*val_SOG + logs.get('hits',0)*val_Hit + 
                                     logs.get('blockedShots',0)*val_BkS)
                    
                    last_5_avg = logs.tail(5)['GF_FP'].mean()
                    season_avg = row['FP'] / row['GP'] if row['GP'] > 0 else 0
                    diff = last_5_avg - season_avg
                    
                    trend_data.append({'Player': row['Player'], 'Trend': diff, 'Val': last_5_avg})
            
            if trend_data:
                df_trend = pd.DataFrame(trend_data).sort_values('Trend')
                chart = alt.Chart(df_trend).mark_bar().encode(
                    x=alt.X('Player', sort=None),
                    y=alt.Y('Trend', title='FP Diff (Last 5 vs Season)'),
                    color=alt.condition(
                        alt.datum.Trend > 0,
                        alt.value("#4caf50"),
                        alt.value("#f44336")
                    ),
                    tooltip=['Player', alt.Tooltip('Trend', format='.1f'), alt.Tooltip('Val', title='L5 Avg', format='.1f')]
                ).properties(height=300)
                
                st.altair_chart(chart, use_container_width=True)
            else:
                st.caption("Not enough data to analyze recent trends (Need 5+ games).")

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
                # 1. SCOREBOARD
                home = box_data.get('homeTeam', {})
                away = box_data.get('awayTeam', {})
                
                c1, c2, c3 = st.columns([1, 0.2, 1])
                with c1: 
                    st.markdown(f"<div style='text-align:center'><img src='{away.get('logo', '')}' width='80'><h2>{away.get('name', {}).get('default', 'Away')}</h2><h3>{away.get('score', 0)}</h3></div>", unsafe_allow_html=True)
                with c2: st.markdown("<h2 style='text-align:center; padding-top:40px'>VS</h2>", unsafe_allow_html=True)
                with c3: 
                    st.markdown(f"<div style='text-align:center'><img src='{home.get('logo', '')}' width='80'><h2>{home.get('name', {}).get('default', 'Home')}</h2><h3>{home.get('score', 0)}</h3></div>", unsafe_allow_html=True)
                
                st.divider()
                
                # --- SEASON STATS COMPARISON ---
                st.subheader("Season Stats Comparison (Avg per Game)")
                
                away_abbr = away.get('abbrev')
                home_abbr = home.get('abbrev')
                
                def get_team_avg(abbr):
                    if abbr and 'Team' in df.columns:
                        tdf = df[df['Team'] == abbr]
                        if not tdf.empty:
                            return {
                                'GF/G': round(tdf['G'].sum() / 82, 2),
                                'PP%': round(tdf['PPP'].sum() / tdf['Pts'].sum() * 100, 1) if tdf['Pts'].sum() > 0 else 0,
                                'Shots/G': round(tdf['SOG'].sum() / 82, 1),
                                'Hits/G': round(tdf['Hits'].sum() / 82, 1)
                            }
                    return {'GF/G': 0, 'PP%': 0, 'Shots/G': 0, 'Hits/G': 0}

                s_away = get_team_avg(away_abbr)
                s_home = get_team_avg(home_abbr)
                comp_df = pd.DataFrame([s_away, s_home], index=[away_abbr, home_abbr])
                st.dataframe(comp_df, use_container_width=True)

                st.divider()

                # --- BOX SCORE (Robust Parser for Boxscore Endpoint) ---
                st.subheader("Box Score")
                
                def parse_stats(team_data):
                    rows = []
                    # Check for playerByGameStats (Boxscore endpoint structure)
                    if 'playerByGameStats' in box_data:
                        stats_key = 'awayTeam' if team_data == away else 'homeTeam'
                        p_stats = box_data['playerByGameStats'].get(stats_key, {})
                        
                        players = p_stats.get('forwards', []) + p_stats.get('defense', [])
                        for p in players:
                            rows.append({
                                "Player": p.get('name', {}).get('default'),
                                "G": p.get('goals', 0),
                                "A": p.get('assists', 0),
                                "Pts": p.get('points', 0),
                                "SOG": p.get('shots', 0),
                                "TOI": p.get('toi', '00:00')
                            })
                    
                    if not rows:
                         return pd.DataFrame(columns=["Player", "G", "A", "Pts", "SOG", "TOI"])
                         
                    return pd.DataFrame(rows)

                away_stats = parse_stats(away)
                home_stats = parse_stats(home)
                
                c_away, c_home = st.columns(2)
                with c_away:
                    st.markdown(f"**{away.get('abbrev')}**")
                    st.dataframe(away_stats, hide_index=True, use_container_width=True)
                with c_home:
                    st.markdown(f"**{home.get('abbrev')}**")
                    st.dataframe(home_stats, hide_index=True, use_container_width=True)
                
            else:
                st.error("Could not load box score.")
        else:
            st.info("👈 Select a game from the **Home** tab to view details here.")
