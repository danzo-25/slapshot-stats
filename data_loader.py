import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz

def fetch_data(endpoint, sort_key, override_cayenne=None, aggregate=False):
    """
    Helper to fetch summary data.
    - override_cayenne: If set, replaces the default seasonId filter completely.
    - aggregate: If True, tells API to sum up the stats (isAggregate=true).
    """
    url = f"https://api.nhle.com/stats/rest/en/{endpoint}/summary"
    
    # LOGIC FIX: If we have a custom filter (like weekly dates), use that.
    # Otherwise, default to the full 2025-2026 Season.
    if override_cayenne:
        cayenne_exp = override_cayenne
    else:
        cayenne_exp = "seasonId=20252026 and gameTypeId=2"

    params = {
        "isAggregate": "true" if aggregate else "false",
        "isGame": "false",
        "sort": f'[{{"property":"{sort_key}","direction":"DESC"}}]',
        "start": 0,
        "limit": 50,
        "cayenneExp": cayenne_exp
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

def load_schedule():
    """Fetches the current week's schedule and filters for Today."""
    url = "https://api-web.nhle.com/v1/schedule/now"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        todays_games = []
        for day in data.get('gameWeek', []):
            if day['date'] == today_str:
                todays_games = day.get('games', [])
                break
        
        processed_games = []
        for g in todays_games:
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
    except: return []

def load_weekly_leaders():
    """Fetches top performers for the last 7 days using API Aggregation."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    # CRITICAL FIX: Only filter by Date and GameType. Do NOT include seasonId.
    clean_date_filter = f"gameTypeId=2 and gameDate >= '{start_date.strftime('%Y-%m-%d')}' and gameDate <= '{end_date.strftime('%Y-%m-%d')}'"
    
    # Call fetch_data with override_cayenne to use ONLY our date filter
    df = fetch_data("skater", "points", override_cayenne=clean_date_filter, aggregate=True)
    
    if df.empty: return pd.DataFrame()

    rename_map = {
        'skaterFullName': 'Player', 'teamAbbrevs': 'Team', 'positionCode': 'Pos',
        'goals': 'G', 'assists': 'A', 'points': 'Pts', 'shots': 'SOG', 'ppPoints': 'PPP'
    }
    df = df.rename(columns=rename_map)
    return df





