import requests
import pandas as pd
import streamlit as st

def fetch_data(endpoint, sort_key):
    """Helper to fetch summary data"""
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
    """Fetches Season Summary for Skaters and Goalies."""
    # 1. Fetch Skaters
    df_skaters = fetch_data("skater", "points")
    if not df_skaters.empty:
        df_skaters['PosType'] = 'Skater'
        df_skaters = df_skaters.rename(columns={
            'skaterFullName': 'Player', 'playerId': 'ID', 'teamAbbrevs': 'Team', 'positionCode': 'Pos',
            'gamesPlayed': 'GP', 'goals': 'G', 'assists': 'A', 'points': 'Pts',
            'plusMinus': '+/-', 'penaltyMinutes': 'PIM', 'ppPoints': 'PPP', 'ppGoals': 'PPG',
            'shPoints': 'SHP', 'gameWinningGoals': 'GWG', 'shots': 'SOG', 'shootingPct': 'Sh%',
            'faceoffWinPct': 'FO%', 'timeOnIcePerGame': 'TOI'
        })

    # 2. Fetch Goalies
    df_goalies = fetch_data("goalie", "wins")
    if not df_goalies.empty:
        df_goalies['PosType'] = 'Goalie'
        df_goalies['Pos'] = 'G'
        df_goalies = df_goalies.rename(columns={
            'goalieFullName': 'Player', 'playerId': 'ID', 'teamAbbrevs': 'Team',
            'gamesPlayed': 'GP', 'wins': 'W', 'losses': 'L', 'otLosses': 'OTL',
            'goalsAgainstAverage': 'GAA', 'savePct': 'SV%', 'shutouts': 'SO',
            'goals': 'G', 'assists': 'A', 'points': 'Pts', 'penaltyMinutes': 'PIM', 'timeOnIcePerGame': 'TOI'
        })

    # 3. Combine
    df_combined = pd.concat([df_skaters, df_goalies], ignore_index=True)
    if df_combined.empty: return pd.DataFrame()

    # 4. Clean
    df_combined['Team'] = df_combined['Team'].apply(lambda x: x.split(',')[-1].strip() if isinstance(x, str) else 'N/A')
    df_combined['Player'] = df_combined['Player'].fillna('Unknown')
    
    # Fill Numeric
    numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'PPG', 'SHP', 'GWG', 'SOG', 'Sh%', 'FO%', 'W', 'L', 'OTL', 'GAA', 'SV%', 'SO']
    for col in numeric_cols:
        if col not in df_combined.columns: df_combined[col] = 0
        df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0)

    cols_to_keep = ['ID', 'Player', 'Team', 'Pos', 'PosType'] + numeric_cols + ['TOI']
    final_cols = [c for c in cols_to_keep if c in df_combined.columns]
    
    return df_combined[final_cols]

# --- NEW FUNCTION FOR TRENDS ---
def get_player_game_log(player_id):
    """
    Fetches the game-by-game log for a specific player for 2025-2026.
    Endpoint: NHL V1 API (Best for game logs)
    """
    url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/20252026/2"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        games = data.get("gameLog", [])
        
        if not games: return pd.DataFrame()

        df_log = pd.DataFrame(games)
        # Ensure date is datetime for plotting
        df_log['gameDate'] = pd.to_datetime(df_log['gameDate'])
        return df_log.sort_values(by='gameDate') # Sort Oldest to Newest
    except Exception as e:
        print(f"Error fetching game log: {e}")
        return pd.DataFrame()



