import requests
import pandas as pd
import streamlit as st

def load_nhl_data():
    """
    Fetches 2024-2025 Regular Season stats for all skaters.
    Endpoint: https://api.nhle.com/stats/rest/en/skater/summary
    """
    url = "https://api.nhle.com/stats/rest/en/skater/summary"

    # Simplified params to minimize errors
    params = {
        "isAggregate": "false",
        "isGame": "false",
        "sort": '[{"property":"points","direction":"DESC"}]',
        "start": 0,
        "limit": -1,
        "cayenneExp": "seasonId=20242025 and gameTypeId=2"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        players_list = data.get("data", [])

        if not players_list:
            return pd.DataFrame()

        df = pd.DataFrame(players_list)

        # --- DEBUGGING / SAFETY ---
        # If the expected columns are missing, this helps us see what we actually got
        # Uncomment the line below to see raw columns in your app if needed:
        # st.write("Raw Columns:", df.columns.tolist())

        # 1. Standardize Column Names
        # We use a mapping to rename whatever the API gives us to our standard names
        rename_map = {
            'skaterFullName': 'Player',
            'teamAbbrev': 'Team',
            'teamName': 'Team',      # Fallback
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
        # If 'Team' or 'Pos' are missing after rename, create them with defaults to prevent crash
        if 'Team' not in df.columns:
            df['Team'] = 'N/A'
        if 'Pos' not in df.columns:
            df['Pos'] = 'N/A'
        if 'Player' not in df.columns:
            # Fallback for player name if skaterFullName is missing
            df['Player'] = df['lastName'] if 'lastName' in df.columns else 'Unknown'

        # 3. Ensure Numeric Columns
        numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SOG', 'Sh%', 'FO%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                # If a stat column is missing, just fill it with 0
                df[col] = 0

        # 4. Final Selection
        cols_to_keep = ['Player', 'Team', 'Pos'] + numeric_cols
        return df[cols_to_keep]

    except Exception as e:
        st.error(f"Error connecting to NHL Stats API: {e}")
        return pd.DataFrame()


