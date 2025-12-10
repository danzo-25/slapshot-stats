import requests
import pandas as pd
import streamlit as st

def load_nhl_data():
    """
    Fetches 2025-2026 Regular Season stats for all skaters.
    Endpoint: https://api.nhle.com/stats/rest/en/skater/summary
    """
    url = "https://api.nhle.com/stats/rest/en/skater/summary"

    params = {
        "isAggregate": "false",
        "isGame": "false",
        "sort": '[{"property":"points","direction":"DESC"}]',
        "start": 0,
        "limit": -1,
        "cayenneExp": "seasonId=20252026 and gameTypeId=2"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        players_list = data.get("data", [])

        if not players_list:
            return pd.DataFrame()

        df = pd.DataFrame(players_list)

        # 1. Update Rename Map
        rename_map = {
            'skaterFullName': 'Player',
            'teamAbbrevs': 'Team',   # Often returns "TEAM1, TEAM2" for traded players
            'teamAbbrev': 'Team',
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
            'timeOnIcePerGame': 'TOI',
            'shots': 'SOG',
            'shootingPct': 'Sh%',
            'faceoffWinPct': 'FO%'
        }
        df = df.rename(columns=rename_map)

        # Safety Checks
        if 'Team' not in df.columns:
            df['Team'] = 'N/A'
        if 'Pos' not in df.columns:
            df['Pos'] = 'N/A'
        if 'Player' not in df.columns:
            df['Player'] = 'Unknown'

        # --- FIX: CLEAN UP DUPLICATE TEAMS ---
        # If Team is "CGY, TOR", split by comma and take the last one ("TOR")
        df['Team'] = df['Team'].apply(lambda x: x.split(',')[-1].strip() if isinstance(x, str) else x)

        # Ensure Numeric Columns
        numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'PPG', 'SHP', 'GWG', 'SOG', 'Sh%', 'FO%']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        # Select Columns
        cols_to_keep = ['Player', 'Team', 'Pos', 'GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'PPG', 'SHP', 'GWG', 'SOG', 'Sh%', 'FO%', 'TOI']
        
        final_cols = [c for c in cols_to_keep if c in df.columns]
        return df[final_cols]

    except Exception as e:
        st.error(f"Error connecting to NHL Stats API: {e}")
        return pd.DataFrame()



