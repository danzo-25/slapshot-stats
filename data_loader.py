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




