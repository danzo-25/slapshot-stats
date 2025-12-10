import requests
import pandas as pd
import streamlit as st

def load_nhl_data():
    """
    Fetches 2024-2025 stats from the NEW NHL V1 API.
    Endpoint: https://api-web.nhle.com/v1/skater-stats-leaders/current
    """
    # This is the new, stable endpoint used by the official NHL website
    url = "https://api-web.nhle.com/v1/skater-stats-leaders/current"
    
    # We request 'points' to get the leaderboard sorted by points
    # limit=-1 fetches ALL active players
    params = {
        "categories": "points",
        "limit": -1
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        # The new API nests the data under the category name "points"
        players_list = data.get("points", [])
        
        if not players_list:
            return pd.DataFrame()

        df = pd.DataFrame(players_list)

        # --- FIX STARTS HERE ---
        # The API returns names as dictionaries: {'default': 'Connor'}
        # We must extract the 'default' value from the dictionary object.
        if 'firstName' in df.columns:
            df['firstName'] = df['firstName'].apply(lambda x: x.get('default') if isinstance(x, dict) else x)
        
        if 'lastName' in df.columns:
            df['lastName'] = df['lastName'].apply(lambda x: x.get('default') if isinstance(x, dict) else x)

        # Now we can safely combine them
        df['Player'] = df['firstName'] + ' ' + df['lastName']
        # --- FIX ENDS HERE ---

        # 2. Rename columns to standard Fantasy Hockey terms
        # Note: 'teamAbbrev' is the key in the new API
        df = df.rename(columns={
            'teamAbbrev': 'Team',
            'positionCode': 'Pos',  # Note: API usually uses 'positionCode', fallback if 'position' is missing
            'position': 'Pos',      # Some endpoints use 'position', keeping both for safety
            'gamesPlayed': 'GP',
            'goals': 'G',
            'assists': 'A',
            'points': 'Pts',
            'plusMinus': '+/-',
            'pim': 'PIM',
            'powerPlayPoints': 'PPP',
            'shots': 'SOG',
            'shootingPct': 'Sh%',
            'faceoffWinPct': 'FO%'
        })

        # 3. Select only the columns we need
        cols_to_keep = ['Player', 'Team', 'Pos', 'GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SOG', 'Sh%', 'FO%']
        
        # Safety: only keep columns that actually exist
        final_cols = [c for c in cols_to_keep if c in df.columns]
        
        return df[final_cols]

    except Exception as e:
        st.error(f"Error connecting to NHL V1 API: {e}")
        return pd.DataFrame()
