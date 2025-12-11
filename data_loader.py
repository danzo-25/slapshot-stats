import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz
import difflib # Added for fuzzy matching

# --- GENERIC FETCHER ---
def fetch_data(endpoint, report_type, sort_key, override_cayenne=None, aggregate=False):
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
        
        # GSAA Calc
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

    # Clean Data
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

@st.cache_data(ttl=600)
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

@st.cache_data(ttl=3600)
def load_nhl_news():
    """Fetches top news from ESPN and extracts images."""
    url = "http://site.api.espn.com/apis/site/v2/sports/hockey/nhl/news"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        articles = []
        
        for article in data.get('articles', [])[:7]:
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

# --- NEW: UNIFIED ESPN LEAGUE FETCHER (Rosters + Standings + League Name) ---
@st.cache_data(ttl=60)
def fetch_espn_league_data(league_id, season_year):
    """
    Fetches ESPN league data, matches player names to NHL stats, and returns 
    rosters ready for rendering (with ID/Team attached).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
    }
    params = {'view': 'mRoster,mSettings,mTeam'}

    def try_fetch(year):
        url = f"https://fantasy.espn.com/apis/v3/games/fhl/seasons/{year}/segments/0/leagues/{league_id}"
        try:
            r = requests.get(url, params=params, headers=headers, timeout=5)
            if r.status_code == 200: return r.json(), 'SUCCESS'
            if r.status_code == 401: return {}, 'PRIVATE'
            return {}, 'ERROR'
        except:
            return {}, 'ERROR'

    data, status = try_fetch(season_year)
    if status == 'ERROR':
        data, status = try_fetch(season_year - 1)

    if status != 'SUCCESS':
        return {}, pd.DataFrame(), "League Rosters", status

    # 0. Get League Name
    league_name = data.get('settings', {}).get('name', 'League Rosters')

    # --- Fetch Main NHL Data for Matching (Not cached here, relying on app's cached df) ---
    # NOTE: This load is slow, but necessary for matching.
    try:
        nhl_df = load_nhl_data() 
        nhl_player_names = nhl_df['Player'].tolist()
        nhl_metadata = {row['Player']: {'ID': row['ID'], 'Team': row['Team']} for _, row in nhl_df[['Player', 'ID', 'Team']].dropna(subset=['Player']).iterrows()}
    except:
        nhl_player_names = []
        nhl_metadata = {}
    
    # --- Helper Matching Function (Fuzzy Matching) ---
    def find_metadata(roster_name):
        rn = str(roster_name).strip()
        # 1. Exact/Case-Insensitive Match
        if rn in nhl_metadata: return nhl_metadata[rn]
        
        # 2. Fuzzy Match (for slight misspellings or formats like Nicklaus vs Nick)
        candidate = difflib.get_close_matches(rn, nhl_player_names, n=1, cutoff=0.7)
        if candidate and candidate[0] in nhl_metadata:
            return nhl_metadata[candidate[0]]
        
        return None

    # 1. PARSE ROSTERS and ATTACH METADATA
    roster_data = {}
    try:
        teams_map = {}
        for t in data.get('teams', []):
            t_id = t['id']
            name = t.get('abbrev')
            if not name: name = t.get('nickname')
            if not name: name = f"Team {t_id}"
            teams_map[t_id] = name

        for team in data.get('teams', []):
            team_name = teams_map.get(team['id'], "Unknown")
            roster_data[team_name] = []
            entries = team.get('roster', {}).get('entries', [])
            
            for slot in entries:
                player_data = slot.get('playerPoolEntry', {}).get('player', {})
                full_name = player_data.get('fullName')
                
                if full_name:
                    meta = find_metadata(full_name)
                    
                    roster_entry = {
                        'Name': full_name,
                        'ID': str(meta.get('ID', 0)).strip(),
                        'NHLTeam': str(meta.get('Team', 'N/A')).strip()
                    }
                    roster_data[team_name].append(roster_entry)
    except:
        roster_data = {}

    # 2. PARSE STANDINGS
    standings_list = []
    try:
        for team in data.get('teams', []):
            abbrev = team.get('abbrev')
            location = team.get('location', '')
            nickname = team.get('nickname', '')
            if location and nickname: full_name = f"{location} {nickname}"
            elif abbrev: full_name = abbrev
            else: full_name = f"Team {team.get('id')}"

            record = team.get('record', {}).get('overall', {})
            wins = record.get('wins', 0)
            losses = record.get('losses', 0)
            ties = record.get('ties', 0)
            rank = team.get('playoffSeed', team.get('rankCalculatedFinal', 0))

            standings_list.append({'Rank': rank, 'Team': full_name, 'W': wins, 'L': losses, 'T': ties})
        
        df_standings = pd.DataFrame(standings_list)
        if not df_standings.empty:
            df_standings = df_standings.sort_values(by='Rank', ascending=True)
            
    except:
        df_standings = pd.DataFrame()

    return roster_data, df_standings, league_name, 'SUCCESS'
