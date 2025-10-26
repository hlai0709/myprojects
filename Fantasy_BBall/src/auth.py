import os
import json
from datetime import datetime
from dotenv import load_dotenv
import requests
import webbrowser
import base64

load_dotenv()

class YahooAuth:
    def __init__(self):
        self.client_id = os.getenv('YAHOO_CONSUMER_KEY')
        self.client_secret = os.getenv('YAHOO_CONSUMER_SECRET')
        if not self.client_id or not self.client_secret:
            raise ValueError("Missing YAHOO_CONSUMER_KEY or YAHOO_CONSUMER_SECRET in .env")
        
        self.base_url = 'https://api.login.yahoo.com/oauth2/'
        self.fantasy_base_url = 'https://fantasysports.yahooapis.com/fantasy/v2/'
        self.token_file = 'oauth2.json'
        self.league_cache_file = 'league_cache.json'
        self.session = requests.Session()
        self._load_token()
        self._league_cache = self._load_league_cache()
    
    def _load_token(self):
        """Load OAuth token from file or authenticate"""
        if os.path.exists(self.token_file):
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
                self.access_token = token_data['access_token']
                self.refresh_token = token_data['refresh_token']
                self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})
                if not self._is_token_valid():
                    self._refresh_token()
        else:
            self._perform_auth()
    
    def _is_token_valid(self):
        """Check if current token is valid"""
        try:
            response = self.session.get(self.base_url + 'get_token_info', timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def _perform_auth(self):
        """Perform OAuth authentication flow"""
        auth_url = f"{self.base_url}request_auth?client_id={self.client_id}&redirect_uri=oob&response_type=code&language=en-us"
        print(f"Go to this URL in browser and approve:\n{auth_url}")
        webbrowser.open(auth_url)
        
        verifier = input("\nEnter verifier code from browser: ").strip()
        
        encoded = base64.b64encode((self.client_id + ':' + self.client_secret).encode("utf-8")).decode("utf-8")
        headers = {
            'Authorization': f'Basic {encoded}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri': 'oob',
            'code': verifier
        }
        response = self.session.post(self.base_url + 'get_token', headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']
            self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})
            self._save_token()
            print("✓ Authentication successful!")
        else:
            raise ValueError(f"Auth failed: {response.status_code} - {response.text}")
    
    def _refresh_token(self):
        """Refresh expired OAuth token"""
        encoded = base64.b64encode((self.client_id + ':' + self.client_secret).encode("utf-8")).decode("utf-8")
        headers = {
            'Authorization': f'Basic {encoded}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        response = self.session.post(self.base_url + 'get_token', headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data['access_token']
            if 'refresh_token' in token_data:
                self.refresh_token = token_data['refresh_token']
            self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})
            self._save_token()
        else:
            raise ValueError(f"Token refresh failed: {response.status_code}")
    
    def _save_token(self):
        """Save OAuth token to file"""
        with open(self.token_file, 'w') as f:
            json.dump({
                'access_token': self.access_token,
                'refresh_token': self.refresh_token
            }, f)
    
    def _load_league_cache(self):
        """Load cached league data"""
        if os.path.exists(self.league_cache_file):
            with open(self.league_cache_file, 'r') as f:
                cache = json.load(f)
                # Check if cache is less than 24 hours old
                if cache.get('timestamp', 0) > datetime.now().timestamp() - 86400:
                    return cache.get('leagues', {})
        return {}
    
    def _save_league_cache(self, leagues):
        """Save league data to cache"""
        with open(self.league_cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().timestamp(),
                'leagues': leagues
            }, f)
    
    def get_all_user_leagues(self, force_refresh=False):
        """
        Fetch all NBA leagues for the current user.
        Returns dict with league_id as key.
        """
        if not force_refresh and self._league_cache:
            return self._league_cache
        
        url = f"{self.fantasy_base_url}users;use_login=1/games;game_codes=nba/leagues?format=json"
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch user leagues: {response.status_code}")
        
        data = response.json()
        users = data['fantasy_content']['users']
        user_data = users['0']['user'][1]
        
        leagues_by_id = {}
        
        if 'games' in user_data:
            games = user_data['games']
            
            for game_key in games:
                if game_key == 'count':
                    continue
                if game_key.isdigit():
                    game_data = games[game_key]['game']
                    
                    game_info = {}
                    for item in game_data:
                        if isinstance(item, dict):
                            game_info.update(item)
                    
                    game_key_val = game_info.get('game_key')
                    season = game_info.get('season')
                    
                    for item in game_data:
                        if isinstance(item, dict) and 'leagues' in item:
                            leagues_data = item['leagues']
                            
                            for league_key in leagues_data:
                                if league_key == 'count':
                                    continue
                                if league_key.isdigit():
                                    league_entry = leagues_data[league_key]['league']
                                    
                                    league_info = {}
                                    for league_item in league_entry:
                                        if isinstance(league_item, dict):
                                            league_info.update(league_item)
                                    
                                    league_id = str(league_info.get('league_id'))
                                    
                                    if league_id not in leagues_by_id:
                                        leagues_by_id[league_id] = []
                                    
                                    leagues_by_id[league_id].append({
                                        'league_id': league_id,
                                        'league_name': league_info.get('name'),
                                        'league_key': league_info.get('league_key'),
                                        'game_key': game_key_val,
                                        'season': season
                                    })
        
        self._league_cache = leagues_by_id
        self._save_league_cache(leagues_by_id)
        return leagues_by_id
    
    def get_game_key(self, league_id):
        """
        Get the game_key for a specific league_id.
        Uses most recent season if multiple exist.
        """
        leagues = self.get_all_user_leagues()
        league_id = str(league_id)
        
        if league_id not in leagues:
            raise ValueError(f"League {league_id} not found in your leagues")
        
        matching_leagues = leagues[league_id]
        
        if len(matching_leagues) == 1:
            return matching_leagues[0]['game_key']
        
        # Return most recent season (highest game_key)
        most_recent = max(matching_leagues, key=lambda x: int(x['game_key']))
        return most_recent['game_key']
    
    def get_team_key(self, league_id, team_id):
        """
        Get the team_key for a specific team in a league.
        """
        game_key = self.get_game_key(league_id)
        
        # Fetch all teams in the league
        url = f"{self.fantasy_base_url}league/{game_key}.l.{league_id}/teams?format=json"
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch teams: {response.status_code}")
        
        data = response.json()
        league_data = data['fantasy_content']['league']
        
        teams_data = None
        for item in league_data:
            if isinstance(item, dict) and 'teams' in item:
                teams_data = item['teams']
                break
        
        if not teams_data:
            raise ValueError("Could not find teams in league data")
        
        # Find the team with matching team_id
        for key in teams_data:
            if key == 'count':
                continue
            if key.isdigit():
                team_entry = teams_data[key]
                if 'team' in team_entry:
                    team_list = team_entry['team']
                    
                    team_info = {}
                    for item in team_list:
                        if isinstance(item, list):
                            for subitem in item:
                                if isinstance(subitem, dict):
                                    team_info.update(subitem)
                        elif isinstance(item, dict):
                            team_info.update(item)
                    
                    if str(team_info.get('team_id')) == str(team_id):
                        return team_info.get('team_key')
        
        raise ValueError(f"Team {team_id} not found in league {league_id}")
    
    def get_league_info(self, league_id):
        """Get league information"""
        game_key = self.get_game_key(league_id)
        url = f"{self.fantasy_base_url}league/{game_key}.l.{league_id}?format=json"
        response = self.session.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            league_info = data['fantasy_content']['league'][0]
            return league_info
        raise ValueError(f"Failed to fetch league info: {response.status_code}")
    
    def get_roster(self, team_key, date=None):
        """
        Get roster for a team on a specific date.
        For NBA, date format: YYYY-MM-DD
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.fantasy_base_url}team/{team_key}/roster;date={date}?format=json"
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch roster: {response.status_code}")
        
        data = response.json()
        team_data = data['fantasy_content']['team']
        
        # Find roster data
        roster_data = None
        for item in team_data:
            if isinstance(item, dict) and 'roster' in item:
                roster_data = item['roster']
                break
        
        if not roster_data:
            return []
        
        players_data = roster_data['0']['players']
        
        # Parse players
        players = []
        for key in players_data:
            if key == 'count':
                continue
            if key.isdigit():
                player_entry = players_data[key]
                if 'player' in player_entry:
                    player_list = player_entry['player']
                    
                    player_info = {}
                    for item in player_list:
                        if isinstance(item, list):
                            for subitem in item:
                                if isinstance(subitem, dict):
                                    player_info.update(subitem)
                        elif isinstance(item, dict):
                            player_info.update(item)
                    
                    players.append(player_info)
        
        return players

if __name__ == "__main__":
    # Initialize authentication
    auth = YahooAuth()
    
    # Your league and team info
    LEAGUE_ID = 39285
    TEAM_ID = 2
    DATE = '2025-10-22'
    
    print(f"\n{'='*60}")
    print(f"Yahoo Fantasy Basketball - Team Roster")
    print(f"{'='*60}\n")
    
    # Get team key
    team_key = auth.get_team_key(LEAGUE_ID, TEAM_ID)
    
    # Get league info
    league_info = auth.get_league_info(LEAGUE_ID)
    league_name = league_info.get('name')
    season = league_info.get('season')
    
    print(f"League: {league_name} ({season} season)")
    print(f"Team Key: {team_key}\n")
    
    # Get roster
    roster = auth.get_roster(team_key, date=DATE)
    
    print(f"{'='*60}")
    print(f"Roster for {DATE}: {len(roster)} players")
    print(f"{'='*60}\n")
    
    for i, player in enumerate(roster, 1):
        # Extract player name
        name = player.get('name', {})
        if isinstance(name, dict):
            full_name = name.get('full', 'Unknown')
        else:
            full_name = str(name)
        
        # Extract position
        position = player.get('display_position', 'N/A')
        
        # Extract selected position (roster slot)
        selected_pos = player.get('selected_position', {})
        if isinstance(selected_pos, dict):
            roster_slot = selected_pos.get('position', 'N/A')
        else:
            roster_slot = 'N/A'
        
        print(f"{i:2d}. {full_name:25s} {position:10s} [{roster_slot}]")
    
    print(f"\n{'='*60}")
    print("✓ Success!")
    print(f"{'='*60}\n")