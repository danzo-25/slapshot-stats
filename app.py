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
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ League Settings")
        st.caption("Enter your ESPN League ID (must be public)")

        league_id = st.text_input(
            "ESPN League ID",
            key="league_id_input",
            placeholder="e.g., 234472"
        )
        
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
            roster_data, status = fetch_espn_roster_data(league_id, 2026)
            
            if status == 'SUCCESS':
                roster_players = [p for team in roster_data.values() for p in team]
                st.session_state.my_roster = [p for p in st.session_state.my_roster if p in roster_players]

                df['Team'] = df['Player'].apply(lambda x: 
                                                next((team_abbr for team_abbr, players in roster_data.items() if x in players), x)
                                                if x in roster_players else 'FA')
            
            elif status == 'PRIVATE':
                st.sidebar.error("Error: League is Private or Invalid ID. Cannot fetch rosters.")
                df = st.session_state.initial_df.copy()

            elif status == 'FAILED_FETCH':
                st.sidebar.error("Error fetching ESPN data. Check ID or season.")
                df = st.session_state.initial_df.copy()

        except Exception as e:
            df = st.session_state.initial_df.copy()

    # --- CALCULATE FP GLOBALLY ---
    df['FP'] = ((df['G'] * val_G) + (df['A'] * val_A) + (df['PPP'] * val_PPP) + 
                (df['SHP'] * val_SHP) + (df['SOG'] * val_SOG) + (df['Hits'] * val_Hit) + 
                (df['BkS'] * val_BkS) + (df['W'] * val_W) + (df['GA'] * val_GA) + 
                (df['Svs'] * val_Svs) + (df['SO'] * val_SO) + (df['OTL'] * val_OTL)).round(1)

    df['GamesRemaining'] = 82 - df['GP']
    def calc_ros(col): return (df[col] / df['GP']).fillna(0) * df['GamesRemaining']
    for s in ['G', 'A', 'Pts', 'PPP', 'SHP', 'SOG', 'Hits', 'BkS', 'FP', 'W', 'Svs', 'SO']:
        if s in df.columns: df[f'ROS_{s}'] = calc_ros(s)

    tab_home, tab_analytics, tab_tools, tab_fantasy = st.tabs(["🏠 Home", "📊 Data & Analytics", "🛠️ Fantasy Tools", "⚔️ My Fantasy Team"])

    # ================= TAB 1: HOME =================
    with tab_home:
        st.header("📅 Today's Games")
        schedule = load_schedule()
        if not schedule: st.info("No games scheduled.")
        else:
            cols_per_row = 5
            for i in range(0,
