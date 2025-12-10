import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz

def fetch_data(endpoint, report_type, sort_key, override_cayenne=None, aggregate=False):
    """
    Generic fetcher for different report types (summary, realtime, puckPossession).
    """
    url = f"https://api.nhle.com/stats/rest/en/{endpoint}/{report_type}"
    
    if override_cayenne:
        cayenne_exp = override_cayenne
    else:
        cayenne_exp = "seasonId=20252026 and gameTypeId=2"

    params = {
        "isAggregate": "true" if aggregate else "false",
        "isGame": "false",
        "sort": f'[{{"property":"{sort_key}","direction":"DESC"}}]',
        "start": 0,
        "limit": -1,
        "cayenneExp": cayenne_exp
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return pd.DataFrame(data.get("data", []))
    except Exception as e:
        print(f"Error fetching {endpoint}/{report_type}: {e}")
        return pd.DataFrame()

def load_nhl_data():
    """
    Fetches stats. RENAMES columns early to prevent duplicates during merge.
    """
    # ================= SKATERS =================
    df_sum = fetch_data("skater", "summary", "points")
    df_real = fetch_data("skater", "realtime", "hits")
    df_adv = fetch_data("skater", "puckPossession", "satPct")

    if not df_sum.empty:
        # 1. RENAME SKATERS IMMEDIATELY
        rename_skaters = {
            'playerId': 'ID', 'skaterFullName': 'Player', 'teamAbbrevs': 'Team', 'positionCode': 'Pos',
            'gamesPlayed': 'GP', 'goals': 'G', 'assists': 'A', 'points': 'Pts',
            'plusMinus': '+/-', 'penaltyMinutes': 'PIM', 'ppPoints': 'PPP', 
            'shPoints': 'SHP',  # <--- CRITICAL FIX: Adds SHP column
            'gameWinningGoals': 'GWG', 'shots': 'SOG', 'shootingPct': 'Sh%', 
            'faceoffWinPct': 'FO%', 'timeOnIcePerGame': 'TOI'
        }
        df_sum = df_sum.rename(columns=rename_skaters)
        
        # 2. Merge Realtime (Hits, Blocks)
        if not df_real.empty:
            df_real = df_real[['playerId', 'hits', 'blockedShots']].rename(columns={'playerId': 'ID', 'hits': 'Hits', 'blockedShots': 'BkS'})
            df_sum = df_sum.merge(df_real, on='ID', how='left')

        # 3. Merge Advanced (Corsi/Fenwick)
        if not df_adv.empty:
            df_adv = df_adv[['playerId', 'satPct', 'usatPct']].rename(columns={'playerId': 'ID', 'satPct': 'SAT%', 'usatPct': 'USAT%'})
            df_sum = df_sum.merge(df_adv, on='ID', how='left')
        
        df_sum['PosType'] = 'Skater'

    # ================= GOALIES =================
    df_goalies = fetch_data("goalie", "summary", "wins")
    
    if not df_goalies.empty:
        df_goalies['PosType'] = 'Goalie'
        df_goalies['Pos'] = 'G'
        # Rename Goalies to match the standardized keys above
        df_goalies = df_goalies.rename(columns={
            'goalieFullName': 'Player', 'playerId': 'ID', 'teamAbbrevs': 'Team',
            'gamesPlayed': 'GP', 'wins': 'W', 'losses': 'L', 'otLosses': 'OTL',
            'goalsAgainstAverage': 'GAA', 'savePct': 'SV%', 'shutouts': 'SO',
            'shotsAgainst': 'SA', 'saves': 'Svs', 
            'goalsAgainst': 'GA', # <--- CRITICAL FIX: Adds GA column
            'goals': 'G', 'assists': 'A', 'points': 'Pts', 'penaltyMinutes': 'PIM', 'timeOnIcePerGame': 'TOI'
        })
        
        # Calculate GSAA
        total_shots = df_goalies['SA'].sum()
        total_saves = df_goalies['Svs'].sum()
        if total_shots > 0:
            league_avg_sv = total_saves / total_shots
            df_goalies['GSAA'] = df_goalies['Svs'] - (df_goalies['SA'] * league_avg_sv)
            df_goalies['GSAA'] = df_goalies['GSAA'].round(2)
        else:
            df_goalies['GSAA'] = 0

    # ================= COMBINE =================
    if df_sum.empty and df_goalies.empty: return pd.DataFrame()
    elif df_sum.empty: df_combined = df_goalies
    elif df_goalies.empty: df_combined = df_sum
    else: df_combined = pd.concat([df_sum, df_goalies], ignore_index=True)

    # Clean Team Names
    if 'Team' in df_combined.columns:
        df_combined['Team'] = df_combined['Team'].apply(lambda x: x.split(',')[-1].strip() if isinstance(x, str) else 'N/A')
    else: df_combined['Team'] = 'N/A'
    
    df_combined['Player'] = df_combined['Player'].fillna('Unknown')
    
    # Fill Numeric (Safety check ensures all columns exist)
    numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SHP', 'GWG', 'SOG', 'Sh%', 'FO%', 
                    'Hits', 'BkS', 'SAT%', 'USAT%', 
                    'W', 'L', 'OTL', 'GAA', 'SV%', 'SO', 'GSAA', 'GA', 'Svs']
    
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
    clean_date_filter = f"gameTypeId=2 and gameDate >= '{start_date.strftime('%Y-%m-%d')}' and gameDate <= '{end_date.strftime('%Y-%m-%d')}'"
    df = fetch_data("skater", "summary", "points", override_cayenne=clean_date_filter, aggregate=True)
    
    if df.empty: return pd.DataFrame()

    rename_map = {
        'skaterFullName': 'Player', 'teamAbbrevs': 'Team', 'positionCode': 'Pos',
        'goals': 'G', 'assists': 'A', 'points': 'Pts', 'shots': 'SOG', 'ppPoints': 'PPP'
    }
    df = df.rename(columns=rename_map)
    return df
