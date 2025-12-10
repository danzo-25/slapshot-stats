import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz

# --- GENERIC FETCHER ---
def fetch_data(endpoint, report_type, sort_key, override_cayenne=None, aggregate=False):
    url = f"https://api.nhle.com/stats/rest/en/{endpoint}/{report_type}"
    if override_cayenne:
        cayenne_exp = override_cayenne
    else:
        # User specified 2025-2026 Season
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
        return pd.DataFrame()

# --- MAIN DATA LOADER (CACHED) ---
@st.cache_data(ttl=3600)
def load_nhl_data():
    # 1. Skaters
    df_sum = fetch_data("skater", "summary", "points")
    df_real = fetch_data("skater", "realtime", "hits")
    df_adv = fetch_data("skater", "puckPossession", "satPct")

    if not df_sum.empty:
        rename_skaters = {
            'playerId': 'ID', 'skaterFullName': 'Player', 'teamAbbrevs': 'Team', 'positionCode': 'Pos',
            'gamesPlayed': 'GP', 'goals': 'G', 'assists': 'A', 'points': 'Pts',
            'plusMinus': '+/-', 'penaltyMinutes': 'PIM', 'ppPoints': 'PPP', 
            'shPoints': 'SHP', 'gameWinningGoals': 'GWG', 'shots': 'SOG', 'shootingPct': 'Sh%', 
            'faceoffWinPct': 'FO%', 'timeOnIcePerGame': 'TOI'
        }
        df_sum = df_sum.rename(columns=rename_skaters)
        
        if not df_real.empty:
            df_real = df_real[['playerId', 'hits', 'blockedShots']].rename(columns={'playerId': 'ID', 'hits': 'Hits', 'blockedShots': 'BkS'})
            df_sum = df_sum.merge(df_real, on='ID', how='left')

        if not df_adv.empty:
            df_adv = df_adv[['playerId', 'satPct', 'usatPct']].rename(columns={'playerId': 'ID', 'satPct': 'SAT%', 'usatPct': 'USAT%'})
            df_sum = df_sum.merge(df_adv, on='ID', how='left')
        
        df_sum['PosType'] = 'Skater'

    # 2. Goalies
    df_goalies = fetch_data("goalie", "summary", "wins")
    if not df_goalies.empty:
        df_goalies['PosType'] = 'Goalie'
        df_goalies['Pos'] = 'G'
        df_goalies = df_goalies.rename(columns={
            'goalieFullName': 'Player', 'playerId': 'ID', 'teamAbbrevs': 'Team',
            'gamesPlayed': 'GP', 'wins': 'W', 'losses': 'L', 'otLosses': 'OTL',
            'goalsAgainstAverage': 'GAA', 'savePct': 'SV%', 'shutouts': 'SO',
            'shotsAgainst': 'SA', 'saves': 'Svs', 'goalsAgainst': 'GA',
            'goals': 'G', 'assists': 'A', 'points': 'Pts', 'penaltyMinutes': 'PIM', 'timeOnIcePerGame': 'TOI'
        })
        
        total_shots = df_goalies['SA'].sum()
        total_saves = df_goalies['Svs'].sum()
        if total_shots > 0:
            league_avg_sv = total_saves / total_shots
            df_goalies['GSAA'] = df_goalies['Svs'] - (df_goalies['SA'] * league_avg_sv)
            df_goalies['GSAA'] = df_goalies['GSAA'].round(2)
        else:
            df_goalies['GSAA'] = 0

    if df_sum.empty and df_goalies.empty: return pd.DataFrame()
    elif df_sum.empty: df_combined = df_goalies
    elif df_goalies.empty: df_combined = df_sum
    else: df_combined = pd.concat([df_sum, df_goalies], ignore_index=True)

    if 'Team' in df_combined.columns:
        df_combined['Team'] = df_combined['Team'].apply(lambda x: x.split(',')[-1].strip() if isinstance(x, str) else 'N/A')
    else: df_combined['Team'] = 'N/A'
    
    df_combined['Player'] = df_combined['Player'].fillna('Unknown')
    
    numeric_cols = ['GP', 'G', 'A', 'Pts', '+/-', 'PIM', 'PPP', 'SHP', 'GWG', 'SOG', 'Sh%', 'FO%', 
                    'Hits', 'BkS', 'SAT%', 'USAT%', 'W', 'L', 'OTL', 'GAA', 'SV%', 'SO', 'GSAA', 'GA', 'Svs']
    
    for col in numeric_cols:
        if col not in df_combined.columns: df_combined[col] = 0
        df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0)

    cols_to_keep = ['ID', 'Player', 'Team', 'Pos', 'PosType'] + numeric_cols + ['TOI']
    final_cols = [c for c in cols_to_keep if c in df_combined.columns]
    
    return df_combined[final_cols]

@st.cache_data(ttl=3600)
def get_player_game_log(player_id):
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

@st.cache_data(ttl=60)
def load_schedule():
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
            
            game_state = g.get('gameState', 'FUT')
            status_text = est_time.strftime("%I:%M %p EST")
            is_live = False
            
            if game_state in ['LIVE', 'CRIT']:
                home_score = g['homeTeam'].get('score', 0)
                away_score = g['awayTeam'].get('score', 0)
                status_text = f"LIVE: {away_score} - {home_score}"
                is_live = True
            elif game_state in ['OFF', 'FINAL']:
                home_score = g['homeTeam'].get('score', 0)
                away_score = g['awayTeam'].get('score', 0)
                status_text = f"Final: {away_score} - {home_score}"

            processed_games.append({
                "home": g['homeTeam']['abbrev'],
                "home_logo": g['homeTeam'].get('logo', ''),
                "away": g['awayTeam']['abbrev'],
                "away_logo": g['awayTeam'].get('logo', ''),
                "time": status_text,
                "is_live": is_live
            })
        return processed_games
    except: return []

@st.cache_data(ttl=3600)
def load_weekly_leaders():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    clean_date_filter = f"gameTypeId=2 and gameDate >= '{start_date.strftime('%Y-%m-%d')}' and gameDate <= '{end_date.strftime('%Y-%m-%d')}'"
    df = fetch_data("skater", "summary", "points", override_cayenne=clean_date_filter, aggregate=True)
    if df.empty: return pd.DataFrame()
    rename_map = {'skaterFullName': 'Player', 'teamAbbrevs': 'Team', 'positionCode': 'Pos', 'goals': 'G', 'assists': 'A', 'points': 'Pts', 'shots': 'SOG', 'ppPoints': 'PPP'}
    df = df.rename(columns=rename_map)
    return df

@st.cache_data(ttl=3600)
def get_weekly_schedule_matrix():
    return _get_weekly_schedule_matrix_impl()

def _get_weekly_schedule_matrix_impl():
    url_sched = "https://api-web.nhle.com/v1/schedule/now"
    url_stand = "https://api-web.nhle.com/v1/standings/now"
    try:
        resp_sched = requests.get(url_sched, timeout=5)
        data_sched = resp_sched.json()
        game_week = data_sched.get('gameWeek', [])
        
        if not game_week: return pd.DataFrame(), {}
        
        days_map = {} 
        ordered_days = []
        for day_obj in game_week:
            date_str = day_obj['date']
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = dt.strftime("%A") 
            days_map[date_str] = day_name
            ordered_days.append(day_name)
            
        all_teams = sorted(list(set([g['homeTeam']['abbrev'] for d in game_week for g in d['games']] + 
                                    [g['awayTeam']['abbrev'] for d in game_week for g in d['games']])))
        
        matrix = pd.DataFrame(index=all_teams, columns=ordered_days).fillna("")
        
        for day_obj in game_week:
            date_str = day_obj['date']
            day_name = days_map[date_str]
            for game in day_obj['games']:
                home = game['homeTeam']['abbrev']
                away = game['awayTeam']['abbrev']
                matrix.at[home, day_name] = f"vs {away}"
                matrix.at[away, day_name] = f"@ {home}"

        resp_stand = requests.get(url_stand, timeout=5)
        data_stand = resp_stand.json()
        standings = {}
        for team in data_stand.get('standings', []):
            team_abbr = team['teamAbbrev']['default']
            standings[team_abbr] = team.get('pointPctg', 0.5)
            
        return matrix, standings
    except:
        return pd.DataFrame(), {}

# --- NEW: Enhanced News Fetcher ---
@st.cache_data(ttl=3600)
def load_nhl_news():
    """Fetches top news from ESPN and extracts images."""
    url = "http://site.api.espn.com/apis/site/v2/sports/hockey/nhl/news"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        articles = []
        
        for article in data.get('articles', [])[:7]: # Get top 7
            # Extract Image
            img_url = ""
            if 'images' in article and len(article['images']) > 0:
                img_url = article['images'][0].get('url', '')
            
            articles.append({
                "headline": article.get('headline', 'No Headline'),
                "description": article.get('description', ''),
                "link": article['links']['web']['href'] if 'links' in article else '#',
                "image": img_url
            })
        return articles
    except Exception as e:
        return []
