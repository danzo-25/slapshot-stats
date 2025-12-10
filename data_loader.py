import requests
import pandas as pd
import streamlit as st

def load_nhl_data():
    """
    Fetches 2024-2025 Regular Season stats for all skaters.
    Endpoint: https://api.nhle.com/stats/rest/en/skater/summary
    """
    # This is the endpoint used by the official NHL.com/stats page
    url = "https://api.nhle.com/stats/rest/en/skater/summary"

    # params to get all players (limit=-1) for current season (20242025) and regular season (gameTypeId=2)
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

        # 1. Clean up Player Name (The Stats API uses 'skaterFullName')
        df['Player'] = df['skaterFullName']

        # 2. Rename columns to standard Fantasy Hockey terms
        df = df.rename(columns={
            'teamAbbrev': 'Team',
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
        })

        # 3. Ensure numeric columns are actually numbers (for sorting)
        numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SOG', 'Sh%', 'FO%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 4. Select and Reorder columns
        cols_to_keep = ['Player', 'Team', 'Pos'] + numeric_cols
        
        # Safety check to only keep columns that exist
        final_cols = [c for c in cols_to_keep if c in df.columns]
        
        return df[final_cols]

    except Exception as e:
        st.error(f"Error connecting to NHL Stats API: {e}")
        return pd.DataFrame()

