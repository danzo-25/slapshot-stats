You are absolutely right. Since today is December 10, 2025, the 2025-2026 season is well underway! The code I gave you was hardcoded to the previous season (20242025).

To fix this, we just need to update the seasonId in data_loader.py from 20242025 to 20252026.
The Fix: data_loader.py

Replace your entire data_loader.py with this updated version. I have changed the cayenneExp line to target the 2025-2026 season.
Python

import requests
import pandas as pd
import streamlit as st

def load_nhl_data():
    """
    Fetches 2025-2026 Regular Season stats for all skaters.
    Endpoint: https://api.nhle.com/stats/rest/en/skater/summary
    """
    url = "https://api.nhle.com/stats/rest/en/skater/summary"

    # --- UPDATED PARAMS FOR 2025-2026 SEASON ---
    params = {
        "isAggregate": "false",
        "isGame": "false",
        "sort": '[{"property":"points","direction":"DESC"}]',
        "start": 0,
        "limit": -1,
        # UPDATED HERE: seasonId=20252026
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

        # 1. Standardize Column Names
        rename_map = {
            'skaterFullName': 'Player',
            'teamAbbrev': 'Team',
            'teamName': 'Team',
            'positionCode': 'Pos',
            'gamesPlayed': 'GP',
            'goals': 'G',
            'assists': 'A',
            'points': 'Pts',
            'plusMinus': '+/-',
            'penaltyMinutes': 'PIM',
            'ppPoints': 'PPP',
            'shots': 'SOG',
            'shootingPct': 'Sh%',
            'faceoffWinPct': 'FO%'
        }
        df = df.rename(columns=rename_map)

        # 2. Ensure Critical Columns Exist
        if 'Team' not in df.columns:
            df['Team'] = 'N/A'
        if 'Pos' not in df.columns:
            df['Pos'] = 'N/A'
        if 'Player' not in df.columns:
            df['Player'] = df['lastName'] if 'lastName' in df.columns else 'Unknown'

        # 3. Ensure Numeric Columns
        numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SOG', 'Sh%', 'FO%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        # 4. Final Selection
        cols_to_keep = ['Player', 'Team', 'Pos'] + numeric_cols
        return df[cols_to_keep]

    except Exception as e:
        st.error(f"Error connecting to NHL Stats API: {e}")
        return pd.DataFrame()



