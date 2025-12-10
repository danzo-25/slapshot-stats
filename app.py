import requests
import pandas as pd
import streamlit as st

def fetch_data(endpoint, sort_key):
    """Helper function to fetch data from a specific NHL endpoint"""
    url = f"https://api.nhle.com/stats/rest/en/{endpoint}/summary"
    params = {
        "isAggregate": "false",
        "isGame": "false",
        "sort": f'[{{"property":"{sort_key}","direction":"DESC"}}]',
        "start": 0,
        "limit": -1,
        "cayenneExp": "seasonId=20252026 and gameTypeId=2"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return pd.DataFrame(data.get("data", []))
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}")
        return pd.DataFrame()

def load_nhl_data():
    """
    Fetches 2025-2026 stats for BOTH Skaters and Goalies.
    """
    # 1. Fetch Skaters
    df_skaters = fetch_data("skater", "points")
    if not df_skaters.empty:
        df_skaters['PosType'] = 'Skater'
        # Standardize Skater Columns
        df_skaters = df_skaters.rename(columns={
            'skaterFullName': 'Player',
            'teamAbbrevs': 'Team',
            'positionCode': 'Pos',
            'gamesPlayed': 'GP',
            'goals': 'G',
            'assists': 'A',
            'points': 'Pts',
            'plusMinus': '+/-',
            'penaltyMinutes': 'PIM',
            'ppPoints': 'PPP',
            'ppGoals': 'PPG',
            'shPoints': 'SHP',
            'gameWinningGoals': 'GWG',
            'shots': 'SOG',
            'shootingPct': 'Sh%',
            'faceoffWinPct': 'FO%',
            'timeOnIcePerGame': 'TOI'
        })

    # 2. Fetch Goalies
    df_goalies = fetch_data("goalie", "wins")
    if not df_goalies.empty:
        df_goalies['PosType'] = 'Goalie'
        df_goalies['Pos'] = 'G' # Ensure Position is set
        # Standardize Goalie Columns
        df_goalies = df_goalies.rename(columns={
            'goalieFullName': 'Player',
            'teamAbbrevs': 'Team',
            'gamesPlayed': 'GP',
            'wins': 'W',
            'losses': 'L',
            'otLosses': 'OTL',
            'goalsAgainstAverage': 'GAA',
            'savePct': 'SV%',
            'shutouts': 'SO',
            # Goalies also have Goals/Assists (rare but possible)
            'goals': 'G',
            'assists': 'A',
            'points': 'Pts',
            'penaltyMinutes': 'PIM',
            'timeOnIcePerGame': 'TOI'
        })

    # 3. Combine Them
    # We use concat, which aligns matching columns (GP, Team) and adds new ones (W, SV%) with NaN
    df_combined = pd.concat([df_skaters, df_goalies], ignore_index=True)

    if df_combined.empty:
        return pd.DataFrame()

    # 4. Clean Up
    
    # Fix Team Names (Handle "CGY, TOR")
    df_combined['Team'] = df_combined['Team'].apply(lambda x: x.split(',')[-1].strip() if isinstance(x, str) else 'N/A')
    
    # Fill N/A with Unknown
    df_combined['Player'] = df_combined['Player'].fillna('Unknown')
    df_combined['Pos'] = df_combined['Pos'].fillna('N/A')

    # 5. Handle Numeric Columns
    # We list ALL possible stats. If a skater row has NaN for 'Wins', it becomes 0.
    numeric_cols = [
        'GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'PPG', 'SHP', 'GWG', 
        'SOG', 'Sh%', 'FO%', # Skater Stats
        'W', 'L', 'OTL', 'GAA', 'SV%', 'SO' # Goalie Stats
    ]
    
    for col in numeric_cols:
        if col not in df_combined.columns:
            df_combined[col] = 0
        
        # Force numeric
        df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0)

    # 6. Final Column Selection
    cols_to_keep = ['Player', 'Team', 'Pos', 'PosType'] + numeric_cols + ['TOI']
    final_cols = [c for c in cols_to_keep if c in df_combined.columns]
    
    return df_combined[final_cols]

Step 2: Update app.py

This update adds the Goalie columns to the table config and adds "Total Wins" to your fantasy team metrics.

Replace app.py with this:
Python

import streamlit as st
import pandas as pd
from data_loader import load_nhl_data

# Set page config
st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")
st.title("🏒 NHL 2025-26 Fantasy Tool")

# --- LOAD DATA ---
with st.spinner('Loading Skater & Goalie Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. The API might be busy or the season hasn't started.")
else:
    tab1, tab2 = st.tabs(["🏆 League Leaders", "⚔️ My Fantasy Team"])

    # Define Column Config (Used in both tabs)
    column_config = {
        "Player": st.column_config.TextColumn("Player", pinned=True),
        "Team": st.column_config.TextColumn("Team", help="Team"),
        "Pos": st.column_config.TextColumn("Pos", help="Position"),
        # Common
        "GP": st.column_config.NumberColumn("GP", help="Games Played"),
        "G": st.column_config.NumberColumn("G", help="Goals"),
        "A": st.column_config.NumberColumn("A", help="Assists"),
        "Pts": st.column_config.NumberColumn("Pts", help="Points"),
        "PIM": st.column_config.NumberColumn("PIM", help="Penalty Minutes"),
        # Skater Specific
        "+/-": st.column_config.NumberColumn("+/-", help="Plus/Minus"),
        "PPP": st.column_config.NumberColumn("PPP", help="Power Play Points"),
        "PPG": st.column_config.NumberColumn("PPG", help="Power Play Goals"),
        "GWG": st.column_config.NumberColumn("GWG", help="Game Winning Goals"),
        "SOG": st.column_config.NumberColumn("SOG", help="Shots on Goal"),
        "Sh%": st.column_config.NumberColumn("Sh%", help="Shooting %", format="%.1f%%"),
        "FO%": st.column_config.NumberColumn("FO%", help="Faceoff Win %", format="%.1f%%"),
        # Goalie Specific
        "W": st.column_config.NumberColumn("W", help="Wins"),
        "L": st.column_config.NumberColumn("L", help="Losses"),
        "OTL": st.column_config.NumberColumn("OTL", help="Overtime Losses"),
        "GAA": st.column_config.NumberColumn("GAA", help="Goals Against Average", format="%.2f"),
        "SV%": st.column_config.NumberColumn("SV%", help="Save Percentage", format="%.3f"),
        "SO": st.column_config.NumberColumn("SO", help="Shutouts"),
        "TOI": st.column_config.TextColumn("TOI", help="Time On Ice")
    }

    # ==========================================
    # TAB 1: LEAGUE LEADERS
    # ==========================================
    with tab1:
        st.header("League Leaders")
        
        with st.expander("Filter Options", expanded=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                if 'Team' in df.columns:
                    unique_teams = sorted(df['Team'].dropna().unique())
                    selected_teams = st.multiselect("Filter by Team", unique_teams, default=unique_teams)
            with col_f2:
                if 'Pos' in df.columns:
                    # Sort positions so 'G' is usually at the end or distinct
                    unique_pos = sorted(df['Pos'].dropna().unique())
                    selected_positions = st.multiselect("Filter by Position", unique_pos, default=unique_pos)

        # Apply Filters
        filtered_df = df.copy()
        if selected_teams and 'Team' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Team'].isin(selected_teams)]
        if selected_positions and 'Pos' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Pos'].isin(selected_positions)]

        # Leader Metrics (Dynamic based on Position)
        st.markdown("### Top Performers")
        m1, m2, m3, m4 = st.columns(4)
        
        def get_top(d, col):
            if d.empty or col not in d.columns: return "N/A", 0
            row = d.sort_values(by=col, ascending=False).iloc[0]
            return row['Player'], row[col]

        # If only Goalies are selected, show Goalie Metrics
        is_only_goalies = (len(selected_positions) == 1 and 'G' in selected_positions)
        
        if is_only_goalies:
            w_name, w_val = get_top(filtered_df, 'W')
            sv_name, sv_val = get_top(filtered_df, 'SV%')
            gaa_name, gaa_val = get_top(filtered_df[filtered_df['GP'] > 5], 'GAA') # Filter low GP for GAA sort logic
            so_name, so_val = get_top(filtered_df, 'SO')

            m1.metric("Wins Leader", str(int(w_val)), w_name)
            m2.metric("Best SV%", f"{sv_val:.3f}", sv_name)
            m3.metric("Shutout Leader", str(int(so_val)), so_name)
            m4.metric("Total Players", len(filtered_df))
        else:
            p_name, p_val = get_top(filtered_df, 'Pts')
            g_name, g_val = get_top(filtered_df, 'G')
            a_name, a_val = get_top(filtered_df, 'A')
            w_name, w_val = get_top(filtered_df, 'W') # Show Wins as 4th metric if mixed

            m1.metric("Points", str(int(p_val)), p_name)
            m2.metric("Goals", str(int(g_val)), g_name)
            m3.metric("Assists", str(int(a_val)), a_name)
            m4.metric("Wins (Goalies)", str(int(w_val)), w_name)

        st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=600, column_config=column_config)

    # ==========================================
    # TAB 2: MY FANTASY TEAM
    # ==========================================
    with tab2:
        st.header("⚔️ My Roster")
        
        # --- 1. LOAD TEAM (UPLOAD) ---
        col_up, col_help = st.columns([1, 2])
        with col_up:
            uploaded_file = st.file_uploader("📂 Load Saved Roster", type=["csv"])
        
        default_roster = []
        all_player_names = sorted(df['Player'].unique())

        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                if "Player" in uploaded_df.columns:
                    valid_players = [p for p in uploaded_df["Player"] if p in all_player_names]
                    default_roster = valid_players
                    st.success(f"Loaded {len(valid_players)} players!")
            except Exception as e:
                st.error(f"Error reading file: {e}")

        # --- 2. SELECT PLAYERS ---
        my_team_list = st.multiselect(
            "Search and Add Players (Skaters & Goalies):", 
            all_player_names, 
            default=default_roster,
            placeholder="Type a name (e.g. McDavid, Shesterkin)..."
        )

        if my_team_list:
            my_team_df = df[df['Player'].isin(my_team_list)]

            # --- 3. SAVE TEAM (DOWNLOAD) ---
            csv_data = my_team_df[['Player']].to_csv(index=False)
            st.download_button(
                label="💾 Save Roster to File",
                data=csv_data,
                file_name="my_fantasy_roster.csv",
                mime="text/csv"
            )

            st.divider()

            # Team Stats
            st.markdown("### Team Totals")
            t1, t2, t3, t4 = st.columns(4)
            
            # Skater Totals
            total_goals = int(my_team_df['G'].sum())
            total_pts = int(my_team_df['Pts'].sum())
            
            # Goalie Totals
            total_wins = int(my_team_df['W'].sum())
            total_so = int(my_team_df['SO'].sum())

            t1.metric("Total Goals", total_goals)
            t2.metric("Total Points", total_pts)
            t3.metric("Goalie Wins", total_wins)
            t4.metric("Goalie Shutouts", total_so)

            st.markdown("### Roster Breakdown")
            st.dataframe(
                my_team_df, 
                use_container_width=True, 
                hide_index=True, 
                column_config=column_config
            )
        else:
            st.info("Start by adding players or uploading a saved roster.")


