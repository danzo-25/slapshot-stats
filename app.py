import streamlit as st
import pandas as pd
import altair as alt
from data_loader import load_nhl_data, get_player_game_log, load_schedule, load_weekly_leaders, get_weekly_schedule_matrix, load_nhl_news

st.set_page_config(layout="wide", page_title="Slapshot Stats")
st.title("🏒 Slapshot Stats")

# --- SESSION STATE ---
if 'my_roster' not in st.session_state: st.session_state.my_roster = []
if "trade_send" not in st.session_state: st.session_state.trade_send = []
if "trade_recv" not in st.session_state: st.session_state.trade_recv = []

# --- CALLBACKS ---
def add_player_from_select(side):
    """Adds player from selectbox and clears it."""
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
    .news-card { background-color: #1e1e1e; border-left: 4px solid #0083b8; padding: 10px; margin-bottom: 10px; border-radius: 4px; }
    .news-title { font-weight: bold; font-size: 1.05em; color: #fff; text-decoration: none; }
    .news-desc { font-size: 0.9em; color: #ccc; margin-top: 5px; }
    .trade-win { background-color: rgba(76, 175, 80, 0.15); border: 2px solid #4caf50; padding: 15px; border-radius: 8px; text-align: center; }
    .trade-loss { background-color: rgba(244, 67, 54, 0.15); border: 2px solid #f44336; padding: 15px; border-radius: 8px; text-align: center; }
    
    /* SELECTED PLAYER CARD STYLING */
    .selected-player-card {
        background-color: #333;
        border: 1px solid #555;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
    }
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

    # --- GLOBAL CALC ---
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
            for i in range(0, len(schedule), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(schedule):
                        game = schedule[i+j]
                        with cols[j]:
                            st.markdown(f"""
                            <div class="game-card">
                                <div class="team-row">
                                    <div class="team-info"><img src="{game['away_logo']}" class="team-logo"><div class="team-name">{game['away']}</div></div>
                                    <div class="vs-text">@</div>
                                    <div class="team-info"><img src="{game['home_logo']}" class="team-logo"><div class="team-name">{game['home']}</div></div>
                                </div>
                                <div class="game-time">{game['time']}</div>
                            </div>""", unsafe_allow_html=True)
        st.divider()
        col_sos, col_news = st.columns([2, 1])
        with col_sos:
            st.header("💪 Strength of Schedule")
            with st.spinner("Calculating..."):
                sos_matrix, standings = get_weekly_schedule_matrix()
            if not sos_matrix.empty and standings:
                def color_sos(val, my_team_abbr):
                    if not val or val == "": return 'background-color: #262730'
                    opp_abbr = val.split(" ")[1] 
                    my_str = standings.get(my_team_abbr, 0.5); opp_str = standings.get(opp_abbr, 0.5)
                    diff = my_str - opp_str
                    if diff > 0.15: return 'background-color: #1b5e20; color: white'
                    elif diff > 0.05: return 'background-color: #2e7d32; color: white'
                    elif diff > 0.00: return 'background-color: #4caf50; color: black'
                    elif diff > -0.05: return 'background-color: #fbc02d; color: black'
                    elif diff > -0.15: return 'background-color: #c62828; color: white'
                    else: return 'background-color: #b71c1c; color: white'
                styled_sos = sos_matrix.style.apply(lambda row: [color_sos(val, row.name) for val in row], axis=1).set_properties(**{'text-align': 'center'})
                st.dataframe(styled_sos, use_container_width=False, height=500, width=800)
            else: st.info("SOS data unavailable.")
        with col_news:
            st.header("📰 Latest News")
            news = load_nhl_news()
            if news:
                for article in news:
                    st.markdown(f"""<div class="news-card"><a href="{article['link']}" target="_blank" class="news-title">{article['headline']}</a><div class="news-desc">{article['description']}</div></div>""", unsafe_allow_html=True)
            else: st.info("No news.")

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
        whole_num_cols = ['GP', 'G', 'A', 'Pts', 'PPP', 'SHP', 'SOG', 'Hits', 'BkS', 'W', 'GA', 'Svs', 'SO', 'OTL', '+/-']
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
        
        all_players = sorted(df['Player'].unique().tolist())
        c1, c_mid, c2 = st.columns([1, 0.1, 1])

        # --- HELPER: PLAYER CARD DISPLAY ---
        def show_selected_player_card(player_name, side):
            p_data = df[df['Player'] == player_name].iloc[0]
            pid = p_data['ID']
            team = p_data['Team']
            # ASSET URL FIX: Use 20242025 + Team Code to ensure image loads
            img_url = f"https://assets.nhle.com/mugs/nhl/20242025/{team}/{pid}.png"
            
            # --- CARD LAYOUT ---
            # Image | Info | Stats | Close
            with st.container(border=True):
                r1, r2, r3, r4 = st.columns([0.25, 0.35, 0.3, 0.1])
                
                with r1:
                    st.image(img_url, width=60)
                
                with r2:
                    st.markdown(f"**{player_name}**")
                    st.caption(f"{p_data['Team']} • {p_data['Pos']}")

