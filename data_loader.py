import requests
import pandas as pd
import streamlit as st

def load_nhl_data():
    """
    Fetches the current 2024-2025 skater stats directly from the NHL API.
    Returns a cleaned Pandas DataFrame.
    """
    # This is the official endpoint used by the NHL website itself
    url = "https://api.nhle.com/stats/rest/en/skater/summary"
    
    # We ask for the current season, regular season games (gameTypeId=2)
    # limit=-1 means "give me everyone"
    params = {
        "isAggregate": "false",
        "isGame": "false",
        "sort": "[{\"property\":\"points\",\"direction\":\"DESC\"}]",
        "start": 0,
        "limit": -1,
        "factCayenneExp": "gamesPlayed>=1",
        "cayenneExp": "gameTypeId=2 and seasonId=20242025" 
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status() # Raises an error if the connection fails
        
        data = response.json()
        
        # The API puts the actual list of players inside the "data" key
        players_list = data.get("data", [])
        
        if not players_list:
            st.error("Connection successful, but no player data found.")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(players_list)

        # Rename columns to standard Fantasy Hockey terms
        # The API uses very long names (e.g. 'skaterFullName')
        df = df.rename(columns={
            'skaterFullName': 'Player',
            'teamAbbrev': 'Team',
            'positionCode': 'Pos',
            'gamesPlayed': 'GP',
            'goals': 'G',
            'assists': 'A',
            'points': 'Pts',
            'plusMinus': '+/-',
            'penaltyMinutes': 'PIM',
            'powerPlayPoints': 'PPP',
            'shots': 'SOG',
            'shootingPct': 'Sh%',
            'faceoffWinPct': 'FO%'
        })

        # Select only the columns we need for the tool
        cols_to_keep = ['Player', 'Team', 'Pos', 'GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SOG', 'Sh%', 'FO%']
        
        # Safety check: only keep columns that actually exist
        final_cols = [c for c in cols_to_keep if c in df.columns]
        
        return df[final_cols]

    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to NHL API: {e}")
        return pd.DataFrame()