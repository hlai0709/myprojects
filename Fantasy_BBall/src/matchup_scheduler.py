"""
matchup_scheduler.py
Handles matchup scheduling logic, including Sunday look-ahead.

Key Features:
- Detects if it's Sunday (look ahead to next week)
- Determines which week's matchup to fetch
- Handles week transitions intelligently
- Parses opponent information from matchup data
- TIMEZONE AWARE: Uses configured timezone for accurate week detection
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from zoneinfo import ZoneInfo
import json
import os


class MatchupScheduler:
    """
    Manages matchup scheduling and Sunday look-ahead logic.
    TIMEZONE AWARE: Properly handles week transitions in user's timezone.
    """
    
    def __init__(self, auth_client, config=None):
        """
        Initialize scheduler with Yahoo auth client and optional config.
        
        Args:
            auth_client: YahooAuth instance for API calls
            config: LeagueConfig instance (optional, for timezone)
        """
        self.auth = auth_client
        self.config = config
        
        # Get timezone from config (defaults to US/Pacific if not provided)
        if config and hasattr(config, 'settings') and hasattr(config.settings, 'timezone'):
            self.timezone = ZoneInfo(config.settings.timezone)
        else:
            # Default to Pacific time if no config provided
            self.timezone = ZoneInfo("US/Pacific")
            print("[WARNING] No timezone in config, defaulting to US/Pacific")
        
        self.cache_file = 'data/matchup_schedule_cache.json'
        self._cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached schedule data."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    # Check if cache is less than 24 hours old
                    if cache.get('timestamp', 0) > datetime.now().timestamp() - 86400:
                        return cache.get('data', {})
            except:
                pass
        return {}
    
    def _save_cache(self, data: Dict):
        """Save schedule data to cache."""
        os.makedirs('data', exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().timestamp(),
                'data': data
            }, f, indent=2)
    
    def is_sunday(self, date: Optional[datetime] = None) -> bool:
        """
        Check if given date (or today in configured timezone) is Sunday.
        
        Args:
            date: Date to check (defaults to now in configured timezone)
        
        Returns:
            True if Sunday, False otherwise
        """
        if date is None:
            date = datetime.now(self.timezone)
        return date.weekday() == 6  # Sunday = 6
    
    def get_current_week(self, team_key: str, use_roster_api: bool = True) -> int:
        """
        Get the current fantasy week number.
        
        UPDATED: Now uses roster_adds API as primary source (more reliable during transitions).
        Falls back to matchup API if roster_adds unavailable.
        
        Args:
            team_key: Your team key (e.g., "466.l.39285.t.2")
            use_roster_api: If True, try roster API first (recommended)
        
        Returns:
            Current week number (e.g., 1, 2, 3...)
        """
        # Check cache first
        cache_key = f"current_week_{team_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        week = None
        
        # Method 1: Try roster_adds API first (most reliable during week transitions)
        if use_roster_api:
            try:
                url = f"{self.auth.fantasy_base_url}team/{team_key}?format=json"
                response = self.auth.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    team_data = data['fantasy_content']['team']
                    
                    # Find roster_adds (can be in dict or nested list)
                    for item in team_data:
                        if isinstance(item, dict) and 'roster_adds' in item:
                            roster_adds = item['roster_adds']
                            if 'coverage_value' in roster_adds:
                                week = int(roster_adds['coverage_value'])
                                break
                        elif isinstance(item, list):
                            for sub in item:
                                if isinstance(sub, dict) and 'roster_adds' in sub:
                                    roster_adds = sub['roster_adds']
                                    if 'coverage_value' in roster_adds:
                                        week = int(roster_adds['coverage_value'])
                                        break
                            if week:
                                break
                    
                    if week:
                        # Cache and return
                        self._cache[cache_key] = week
                        self._save_cache(self._cache)
                        return week
            except Exception:
                pass  # Fall through to matchup API
        
        # Method 2: Fallback to matchup API
        try:
            # Fetch current matchup
            url = f"{self.auth.fantasy_base_url}team/{team_key}/matchups?format=json"
            response = self.auth.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                team_data = data['fantasy_content']['team']
                
                # Find matchups data
                for item in team_data:
                    if isinstance(item, dict) and 'matchups' in item:
                        matchups = item['matchups']
                        
                        # Get first matchup (most recent)
                        if '0' in matchups:
                            matchup = matchups['0']['matchup']
                            
                            # Extract week number
                            for match_item in matchup:
                                if isinstance(match_item, dict) and 'week' in match_item:
                                    week = int(match_item['week'])
                                    
                                    # Check if matchup is active (ongoing)
                                    status = match_item.get('status', 'postevent')
                                    
                                    # If matchup is completed, we're in transition
                                    if status == 'postevent':
                                        week += 1  # Next week
                                    
                                    # Cache it
                                    self._cache[cache_key] = week
                                    self._save_cache(self._cache)
                                    
                                    return week
        except Exception:
            pass  # Fall through to fallback methods
            pass  # Fall through to fallback methods
        
        # Fallback: Try to get scoreboard to determine current week
        try:
            league_key = team_key.rsplit('.t.', 1)[0]  # Extract league key
            url = f"{self.auth.fantasy_base_url}league/{league_key}/scoreboard?format=json"
            response = self.auth.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                league_data = data['fantasy_content']['league']
                
                for item in league_data:
                    if isinstance(item, dict) and 'scoreboard' in item:
                        scoreboard = item['scoreboard']
                        
                        if '0' in scoreboard and 'matchups' in scoreboard['0']:
                            matchups = scoreboard['0']['matchups']
                            
                            if '0' in matchups:
                                matchup = matchups['0']['matchup']
                                
                                for match_item in matchup:
                                    if isinstance(match_item, dict) and 'week' in match_item:
                                        week = int(match_item['week'])
                                        
                                        # Cache it
                                        self._cache[cache_key] = week
                                        self._save_cache(self._cache)
                                        
                                        return week
        except:
            pass
        
        # Final fallback: calculate based on season start
        # NBA 2024-25 season started October 21, 2025
        season_start = datetime(2025, 10, 21)
        today = datetime.now()
        
        # If before season start, return 1
        if today < season_start:
            return 1
        
        # Calculate weeks since start
        days_since_start = (today - season_start).days
        estimated_week = max(1, (days_since_start // 7) + 1)
        
        # Cap at reasonable max (NBA regular season is ~23 weeks)
        estimated_week = min(estimated_week, 23)
        
        return estimated_week
    
    def should_look_ahead(self, date: Optional[datetime] = None, 
                          cutoff_hour: int = 0) -> bool:
        """
        Determine if we should look ahead to next week.
        
        On Sundays (after cutoff_hour in configured timezone), we look ahead to next week's matchup.
        
        Args:
            date: Date to check (defaults to now in configured timezone)
            cutoff_hour: Hour of day to switch (0 = midnight, 22 = 10pm)
        
        Returns:
            True if should analyze next week, False for current week
        """
        if date is None:
            date = datetime.now(self.timezone)
        
        # Ensure date is timezone-aware (use configured timezone if naive)
        if date.tzinfo is None:
            date = date.replace(tzinfo=self.timezone)
        
        # Check if it's Sunday
        if not self.is_sunday(date):
            return False
        
        # Check if we're past the cutoff hour
        if date.hour >= cutoff_hour:
            return True
        
        return False
    
    def get_target_week(self, team_key: str, 
                       date: Optional[datetime] = None,
                       cutoff_hour: int = 0,
                       debug: bool = False) -> int:
        """
        Get the week number to analyze (with optional verification logging).
        
        Args:
            team_key: Your team key
            date: Date to check (defaults to now in configured timezone)
            cutoff_hour: Sunday cutoff hour (0-23)
            debug: If True, print week detection details
        
        Returns:
            Week number to analyze
        """
        # Get current week (roster API primary, matchup API fallback)
        current_week = self.get_current_week(team_key, use_roster_api=True)
        
        if debug:
            # Also get matchup API version for comparison
            matchup_week = self.get_current_week(team_key, use_roster_api=False)
            if matchup_week != current_week:
                print(f"[DEBUG] ⚠️ Week API mismatch detected:")
                print(f"[DEBUG]   Roster API (primary): Week {current_week}")
                print(f"[DEBUG]   Matchup API (fallback): Week {matchup_week}")
                print(f"[DEBUG]   Using Roster API week ({current_week}) - more reliable during transitions")
        
        # Check if we should look ahead (only on Sunday nights)
        if self.should_look_ahead(date, cutoff_hour):
            if debug:
                print(f"[DEBUG] Sunday night look-ahead: Week {current_week} → Week {current_week + 1}")
            return current_week + 1
        
        return current_week
    
    def get_matchup_for_week(self, team_key: str, week: int) -> Optional[Dict]:
        """
        Fetch matchup data for a specific week.
        
        Args:
            team_key: Your team key
            week: Week number to fetch
        
        Returns:
            Matchup data dict, or None if not found
        """
        try:
            # Try team matchups endpoint first
            url = f"{self.auth.fantasy_base_url}team/{team_key}/matchups;weeks={week}?format=json"
            response = self.auth.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                team_data = data['fantasy_content']['team']
                
                # team_data is a list: [team_info_dict, matchups_dict]
                for item in team_data:
                    if isinstance(item, dict) and 'matchups' in item:
                        matchups = item['matchups']
                        
                        if '0' in matchups and 'matchup' in matchups['0']:
                            matchup = matchups['0']['matchup']
                            
                            if isinstance(matchup, dict):
                                return matchup
            
            # Fallback: Try league scoreboard endpoint
            league_key = team_key.rsplit('.t.', 1)[0]
            url = f"{self.auth.fantasy_base_url}league/{league_key}/scoreboard;week={week}?format=json"
            response = self.auth.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            league_data = data['fantasy_content']['league']
            
            # Find scoreboard in league data
            for item in league_data:
                if isinstance(item, dict) and 'scoreboard' in item:
                    scoreboard = item['scoreboard']
                    
                    if '0' in scoreboard and 'matchups' in scoreboard['0']:
                        matchups_data = scoreboard['0']['matchups']
                        
                        # Find our team's matchup
                        for key in matchups_data:
                            if key == 'count':
                                continue
                            if key.isdigit():
                                matchup_entry = matchups_data[key]
                                
                                if 'matchup' in matchup_entry:
                                    matchup = matchup_entry['matchup']
                                    
                                    # Check if this matchup involves our team
                                    if '0' in matchup and 'teams' in matchup['0']:
                                        teams = matchup['0']['teams']
                                        
                                        for team_idx in teams:
                                            if team_idx == 'count':
                                                continue
                                            if team_idx.isdigit():
                                                team_entry = teams[team_idx]
                                                
                                                if 'team' in team_entry:
                                                    team_data_list = team_entry['team']
                                                    
                                                    if isinstance(team_data_list, list) and len(team_data_list) > 0:
                                                        team_info_list = team_data_list[0]
                                                        
                                                        if isinstance(team_info_list, list):
                                                            for team_info_item in team_info_list:
                                                                if isinstance(team_info_item, dict) and 'team_key' in team_info_item:
                                                                    if team_info_item['team_key'] == team_key:
                                                                        return matchup
                        
                        # If we didn't find our specific team, return first matchup
                        # (Useful for future weeks when opponent isn't determined yet)
                        if '0' in matchups_data and 'matchup' in matchups_data['0']:
                            return matchups_data['0']['matchup']
            
            return None
            
        except Exception as e:
            # Silent failure - caller will handle None response
            return None
    
    def parse_matchup_info(self, matchup_raw: Dict, my_team_key: str) -> Dict:
        """
        Parse raw Yahoo matchup data to extract opponent info.
        
        Args:
            matchup_raw: Raw matchup dict from Yahoo API
            my_team_key: Your team key to identify opponent
        
        Returns:
            Dict with opponent_name, opponent_key, and other matchup info
        """
        result = {
            'week': matchup_raw.get('week'),
            'week_start': matchup_raw.get('week_start'),
            'week_end': matchup_raw.get('week_end'),
            'status': matchup_raw.get('status'),
            'opponent_name': None,
            'opponent_key': None
        }
        
        # Extract teams from the nested structure
        if '0' in matchup_raw and 'teams' in matchup_raw['0']:
            teams = matchup_raw['0']['teams']
            
            for team_idx in ['0', '1']:
                if team_idx not in teams:
                    continue
                    
                team_data = teams[team_idx]['team']
                if not isinstance(team_data, list) or len(team_data) == 0:
                    continue
                
                team_info_list = team_data[0]
                if not isinstance(team_info_list, list):
                    continue
                
                # Extract team info from the list
                team_key = None
                team_name = None
                
                for item in team_info_list:
                    if isinstance(item, dict):
                        if 'team_key' in item:
                            team_key = item['team_key']
                        if 'name' in item:
                            team_name = item['name']
                
                # If this is the opponent (not my team)
                if team_key and team_key != my_team_key:
                    result['opponent_name'] = team_name
                    result['opponent_key'] = team_key
                    
                    # Store full opponent info
                    result['opponent'] = {
                        'team_key': team_key,
                        'team_name': team_name
                    }
                    break
        
        return result
    
    def get_optimal_matchup(self, team_key: str, 
                           date: Optional[datetime] = None,
                           cutoff_hour: int = 0,
                           verbose: bool = True) -> Dict:
        """
        Get the optimal matchup to analyze (current or next week).
        
        This is the main method you'll use!
        
        Args:
            team_key: Your team key
            date: Date to check (defaults to now)
            cutoff_hour: Sunday cutoff hour (default: midnight)
            verbose: Print status messages
        
        Returns:
            Dict with matchup data and metadata
        """
        if date is None:
            date = datetime.now()
        
        target_week = self.get_target_week(team_key, date, cutoff_hour)
        is_lookahead = self.should_look_ahead(date, cutoff_hour)
        
        if verbose:
            day_name = date.strftime('%A')
            print(f"\n📅 Today is {day_name}, {date.strftime('%B %d, %Y')}")
            
            if is_lookahead:
                print(f"✓ Sunday detected - Looking ahead to Week {target_week}")
            else:
                print(f"✓ Analyzing current week: Week {target_week}")
        
        matchup_raw = self.get_matchup_for_week(team_key, target_week)
        
        # If looking ahead and next week doesn't exist yet, fall back to current week
        if matchup_raw is None and is_lookahead:
            if verbose:
                print(f"⚠️  Week {target_week} not available yet")
                print(f"   Falling back to current week: Week {target_week - 1}")
            
            target_week = target_week - 1
            is_lookahead = False
            matchup_raw = self.get_matchup_for_week(team_key, target_week)
            
            if verbose and matchup_raw:
                print(f"✓ Successfully loaded Week {target_week} matchup as fallback")
        
        if matchup_raw is None:
            if verbose:
                print(f"⚠️  Could not fetch Week {target_week} matchup")
            return {
                'week': target_week,
                'is_lookahead': is_lookahead,
                'matchup': None,
                'error': 'Could not fetch matchup data'
            }
        
        # Parse the raw matchup data
        matchup_parsed = self.parse_matchup_info(matchup_raw, team_key)
        
        return {
            'week': target_week,
            'is_lookahead': is_lookahead,
            'current_date': date.isoformat(),
            'matchup': matchup_parsed,
            'error': None
        }


if __name__ == "__main__":
    """Test the scheduler"""
    from auth import YahooAuth
    
    print("="*80)
    print("MATCHUP SCHEDULER TEST")
    print("="*80)
    
    # Initialize auth
    auth = YahooAuth()
    scheduler = MatchupScheduler(auth)
    
    # Your team info
    LEAGUE_ID = 39285
    TEAM_ID = 2
    
    # Get team key
    team_key = auth.get_team_key(LEAGUE_ID, TEAM_ID)
    print(f"\nTeam Key: {team_key}")
    
    # Test current week detection
    current_week = scheduler.get_current_week(team_key)
    print(f"\nCurrent Week: {current_week}")
    
    # Test Sunday detection
    today = datetime.now()
    is_sunday = scheduler.is_sunday()
    should_lookahead = scheduler.should_look_ahead()
    
    print(f"\nToday: {today.strftime('%A, %B %d, %Y')}")
    print(f"Is Sunday: {is_sunday}")
    print(f"Should look ahead: {should_lookahead}")
    
    # Get optimal matchup
    print("\n" + "="*80)
    print("OPTIMAL MATCHUP ANALYSIS")
    print("="*80)
    
    result = scheduler.get_optimal_matchup(team_key, verbose=True)
    
    if result['matchup']:
        print(f"\n✓ Successfully fetched Week {result['week']} matchup")
        print(f"  Look-ahead mode: {result['is_lookahead']}")
        
        # Show matchup details
        matchup = result['matchup']
        print(f"  Opponent: {matchup.get('opponent_name', 'Unknown')}")
        print(f"  Opponent key: {matchup.get('opponent_key', 'Unknown')}")
        if 'week_start' in matchup:
            print(f"  Week starts: {matchup['week_start']}")
        if 'week_end' in matchup:
            print(f"  Week ends: {matchup['week_end']}")
    else:
        print(f"\n❌ Failed to fetch matchup: {result.get('error')}")
    
    print("\n" + "="*80)
    print("✓ Test complete!")
    print("="*80)