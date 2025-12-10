import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz

def fetch_data(endpoint, sort_key):
    """Helper to fetch summary data"""
    url = f"https://api.nhle.com/stats/rest/en/{endpoint}/summary"
    params = {
        "isAggregate": "false",
        "isGame": "false",
        "sort": f'[{{"property":"{sort_key}","direction":"DESC"}}]',
        "start": 0,
        "limit": 50, # Get top 50 to ensure we have a good pool
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
    """Fetches Season Summary for Skaters and Goalies (Full Season)."""
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

def get_weekly_hot_players():
    """
    Robust Method:
    1. Gets top 20 scorers from season list.
    2. Fetches their game logs.
    3. Calculates their stats for Last 7 Days manually.
    """
    # 1. Get Top Players (Base Pool)
    df_all = load_nhl_data()
    if df_all.empty: return pd.DataFrame()
    
    # Filter to Skaters only and take top 20 by Points
    top_candidates = df_all[df_all['PosType'] == 'Skater'].sort_values('Pts', ascending=False).head(20)
    
    # 2. Date Range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    hot_list = []
    
    # 3. Iterate and Fetch Logs
    for _, player in top_candidates.iterrows():
        pid = player['ID']
        logs = get_player_game_log(pid)
        
        if not logs.empty:
            # Filter logs for last 7 days
            recent_logs = logs[
                (logs['gameDate'] >= start_date) & 
                (logs['gameDate'] <= end_date)
            ]
            
            if not recent_logs.empty:
                # Sum up stats
                hot_list.append({
                    'Player': player['Player'],
                    'G': recent_logs['goals'].sum(),
                    'A': recent_logs['assists'].sum(),
                    'Pts': recent_logs['points'].sum(),
                    'SOG': recent_logs['shots'].sum(),
                    'PPP': recent_logs['powerPlayPoints'].sum()
                })
    
    if not hot_list: return pd.DataFrame()
    
    return pd.DataFrame(hot_list)





