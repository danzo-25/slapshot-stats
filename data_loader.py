import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz

def fetch_data(endpoint, sort_key, extra_filter=""):
    """Helper to fetch summary data"""
    url = f"https://api.nhle.com/stats/rest/en/{endpoint}/summary"
    
    # Base filter for 2025-2026 Regular Season
    base_exp = "seasonId=20252026 and gameTypeId=2"
    if extra_filter:
        base_exp += f" and {extra_filter}"

    params = {
        "isAggregate": "false",
        "isGame": "false",
        "sort": f'[{{"property":"{sort_key}","direction":"DESC"}}]',
        "start": 0,
        "limit": 50, # Limit to top 50 for weekly leaders to save speed
        "cayenneExp": base_exp
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
    """Fetches Season Summary for Skaters and Goalies (Full Season)."""
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

    if df_skaters.empty and df_goalies.empty: return pd.DataFrame()
    elif df_skaters.empty: df_combined = df_goalies
    elif df_goalies.empty: df_combined = df_skaters
    else: df_combined = pd.concat([df_skaters, df_goalies], ignore_index=True)

    # Clean Data
    if 'Team' in df_combined.columns:
        df_combined['Team'] = df_combined['Team'].apply(lambda x: x.split(',')[-1].strip() if isinstance(x, str) else 'N/A')
    else: df_combined['Team'] = 'N/A'
    
    df_combined['Player'] = df_combined['Player'].fillna('Unknown')
    
    numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'PPG', 'SHP', 'GWG', 'SOG', 'Sh%', 'FO%', 'W', 'L', 'OTL', 'GAA', 'SV%', 'SO']
    for col in numeric_cols:
        if col not in df_combined.columns: df_combined[col] = 0
        df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0)

    cols_to_keep = ['ID', 'Player', 'Team', 'Pos', 'PosType'] + numeric_cols + ['TOI']
    final_cols = [c for c in cols_to_keep if c in df_combined.columns]
    
    return df_combined[final_cols]

def get_player_game_log(player_id):
    """Fetches game log for trend analysis."""
    url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/20252026/2"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        games = data.get("gameLog", [])
        if not games: return pd.DataFrame()
        df_log = pd.DataFrame(games)
        df_log['gameDate'] = pd.to_datetime(df_log['gameDate'])
        return df_log.sort_values(by='gameDate')
    except: return pd.DataFrame()

# --- NEW: SCHEDULE & WEEKLY LEADERS ---

def load_schedule():
    """Fetches the current week's schedule and filters for Today."""
    url = "https://api-web.nhle.com/v1/schedule/now"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Get today's date in YYYY-MM-DD
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Find games for today
        todays_games = []
        for day in data.get('gameWeek', []):
            if day['date'] == today_str:
                todays_games = day.get('games', [])
                break
        
        processed_games = []
        for g in todays_games:
            # Convert UTC to EST
            utc_time = datetime.strptime(g['startTimeUTC'], "%Y-%m-%dT%H:%M:%SZ")
            utc_time = utc_time.replace(tzinfo=pytz.utc)
            est_time = utc_time.astimezone(pytz.timezone('US/Eastern'))
            
            processed_games.append({
                "home": g['homeTeam']['abbrev'],
                "home_logo": g['homeTeam'].get('logo', ''),
                "away": g['awayTeam']['abbrev'],
                "away_logo": g['awayTeam'].get('logo', ''),
                "time": est_time.strftime("%I:%M %p EST")
            })
            
        return processed_games
    except Exception as e:
        print(f"Schedule Error: {e}")
        return []

def load_weekly_leaders():
    """Fetches top performers for the last 7 days."""
    # Calculate date 7 days ago
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    date_filter = f"gameDate >= '{start_date.strftime('%Y-%m-%d')}' and gameDate <= '{end_date.strftime('%Y-%m-%d')}'"
    
    # We reuse fetch_data but with the date filter
    df = fetch_data("skater", "points", extra_filter=date_filter)
    
    if df.empty: return pd.DataFrame()

    # Rename just enough for the charts
    rename_map = {
        'skaterFullName': 'Player', 'teamAbbrevs': 'Team', 'positionCode': 'Pos',
        'goals': 'G', 'assists': 'A', 'points': 'Pts', 'shots': 'SOG', 'ppPoints': 'PPP'
    }
    df = df.rename(columns=rename_map)
    return df
