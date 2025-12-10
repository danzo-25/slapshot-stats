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

        # --- FIX IS HERE ---
        # The Stats API uses 'teamAbbrevs' (plural) because players can change teams
        rename_map = {
            'skaterFullName': 'Player',
            'teamAbbrevs': 'Team',   # <--- This is the correct key
            'teamAbbrev': 'Team',    # Keeping this just in case
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

        # Safety Checks
        if 'Team' not in df.columns:
            # If still missing, we try to construct it or default to N/A
            df['Team'] = 'N/A'
        
        if 'Pos' not in df.columns:
            df['Pos'] = 'N/A'
            
        if 'Player' not in df.columns:
            df['Player'] = 'Unknown'

        # Ensure Numeric Columns
        numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SOG', 'Sh%', 'FO%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        cols_to_keep = ['Player', 'Team', 'Pos'] + numeric_cols
        
        # Final safety: only return columns that actually exist
        final_cols = [c for c in cols_to_keep if c in df.columns]
        return df[final_cols]

    except Exception as e:
        st.error(f"Error connecting to NHL Stats API: {e}")
        return pd.DataFrame()


