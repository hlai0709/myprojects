"""
ai_analyzer.py - PHASE 4A COMPLETE + CRITICAL FIXES
- LIVE data fetching using existing modules
- Phase 4A strategic analysis
- Roster moves tracking (FIXED)
- FIXED: Correct week detection using matchup_scheduler
- FIXED: Sunday look-ahead for next week's opponent
- FIXED: Filter out already-dropped players
- FIXED: Timezone-aware week detection (uses configured timezone)
- FIXED: Injury hallucination prevention
- Enhanced logging
"""

import json
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Try to import Anthropic SDK
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️  Anthropic SDK not installed. Run: pip install anthropic")

# Try to import LeagueConfig
try:
    from league_config import LeagueConfig
    LEAGUE_CONFIG_AVAILABLE = True
except ImportError:
    LEAGUE_CONFIG_AVAILABLE = False
    print("⚠️  league_config.py not found - using defaults")

# Import data fetchers
try:
    from auth import YahooAuth
    from roster_analyzer import RosterAnalyzer
    from player_fetcher import PlayerFetcher
    from matchup_analyzer import MatchupAnalyzer
    from matchup_scheduler import MatchupScheduler
    DATA_FETCHERS_AVAILABLE = True
except ImportError as e:
    DATA_FETCHERS_AVAILABLE = False
    print(f"⚠️  Data fetchers not available: {e}")

# Import Phase 4A strategic analyzer
try:
    from strategic_analyzer import StrategicAnalyzer
    STRATEGIC_ANALYZER_AVAILABLE = True
except ImportError:
    STRATEGIC_ANALYZER_AVAILABLE = False
    print("⚠️  strategic_analyzer.py not found - Phase 4A features disabled")

# Import PlayerEvaluator for advanced player evaluation
try:
    from player_evaluator import PlayerEvaluator
    PLAYER_EVALUATOR_AVAILABLE = True
except ImportError:
    PLAYER_EVALUATOR_AVAILABLE = False
    print("⚠️  player_evaluator.py not found - using basic filtering")

# Import OpponentAnalyzer for schedule and category analysis
try:
    from opponent_analyzer import OpponentAnalyzer
    OPPONENT_ANALYZER_AVAILABLE = True
except ImportError:
    OPPONENT_ANALYZER_AVAILABLE = False
    print("⚠️  opponent_analyzer.py not found - schedule features disabled")

# Import caching utilities
try:
    from util import cache, logger
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    cache = None
    logger = None
    print("⚠️  util.py caching not available")

# Import constants
try:
    from constants import (
        CACHE_TTL_AVAILABLE_PLAYERS,
        DEFAULT_PLAYER_LIMIT,
        MAX_AVAILABLE_PLAYERS,
        SUNDAY_CUTOFF_HOUR,
        DEFAULT_MAX_MOVES_PER_WEEK,
        SEASON_START_DATE,
        DAYS_PER_WEEK,
        THRESHOLDS,
        PRODUCTION_THRESHOLDS,
        POSITION_SCARCITY,
        SCORING_GAMES_REMAINING_MAX,
        SCORING_TARGET_CATS_MAX,
        SCORING_PRODUCTION_MAX,
    )
    CONSTANTS_AVAILABLE = True
except ImportError:
    # Fallback to hardcoded values if constants.py not available
    CONSTANTS_AVAILABLE = False
    CACHE_TTL_AVAILABLE_PLAYERS = 1800
    DEFAULT_PLAYER_LIMIT = 25
    MAX_AVAILABLE_PLAYERS = 500
    SUNDAY_CUTOFF_HOUR = 22
    DEFAULT_MAX_MOVES_PER_WEEK = 4
    SEASON_START_DATE = (2024, 10, 21)
    DAYS_PER_WEEK = 7
    print("⚠️  constants.py not found - using fallback values")


class AIAnalyzer:
    """
    Phase 4A Enhanced AI analyzer with CRITICAL FIXES:
    - Correct week detection (uses matchup_scheduler)
    - Sunday look-ahead logic
    - Already-dropped player filtering
    - LIVE data fetching
    - Strategic analysis
    """
    
    def __init__(self, config=None):
        if logger:
            logger.debug("Initializing AIAnalyzer...")
        
        # Handle config
        if config:
            self.config = config
            if logger:
                logger.debug("Using provided config")
        elif LEAGUE_CONFIG_AVAILABLE:
            self.config = LeagueConfig()
            if logger:
                logger.debug("Loaded LeagueConfig")
        else:
            self.config = None
            if logger:
                logger.debug("No config available")
        
        self.ai_provider = None
        self.api_key = None
        self.client = None
        
        # Initialize auth and data fetchers
        self.auth = None
        self.roster_analyzer = None
        self.player_fetcher = None
        self.matchup_analyzer = None
        self.matchup_scheduler = None
        self.opponent_analyzer = None
        
        if DATA_FETCHERS_AVAILABLE and self.config:
            try:
                self.auth = YahooAuth()
                self.roster_analyzer = RosterAnalyzer(self.auth, self.config)
                self.player_fetcher = PlayerFetcher(self.auth)
                self.matchup_analyzer = MatchupAnalyzer(self.auth, self.config)
                self.matchup_scheduler = MatchupScheduler(self.auth, self.config)
                
                # Initialize OpponentAnalyzer for schedule data
                if OPPONENT_ANALYZER_AVAILABLE:
                    self.opponent_analyzer = OpponentAnalyzer(self.auth)
                    print(f"[DEBUG] Opponent analyzer initialized")
                
                print(f"[DEBUG] Data fetchers initialized")
            except Exception as e:
                print(f"⚠️  Could not initialize data fetchers: {e}")
        
        # Initialize Phase 4A strategic analyzer
        if STRATEGIC_ANALYZER_AVAILABLE:
            self.strategic_analyzer = StrategicAnalyzer()
            print(f"[DEBUG] Strategic analyzer initialized")
        else:
            self.strategic_analyzer = None
            print(f"[DEBUG] Strategic analyzer NOT available")
        
        # Load environment variables
        load_dotenv()
        
        # Try to initialize Claude API
        self._init_claude_api()
    
    def _get_league_name(self) -> str:
        """Safely get league name."""
        if self.config and hasattr(self.config, 'settings'):
            return self.config.settings.league_name
        return "Warriors4life"
    
    def _get_team_name(self) -> str:
        """Safely get team name."""
        if self.config and hasattr(self.config, 'settings'):
            return self.config.settings.team_name
        return "NoMoneyNoHoney"
    
    def _get_team_key(self) -> str:
        """Get team key."""
        if not self.config or not self.auth:
            return None
        return self.auth.get_team_key(
            self.config.settings.league_id,
            self.config.settings.team_id
        )
    
    def _get_week_dates(self, week_number: int) -> Dict[str, str]:
        """
        Calculate week start and end dates for a given week number.
        
        Args:
            week_number: Fantasy week number (1-based)
        
        Returns:
            Dict with 'start' and 'end' date strings (YYYY-MM-DD)
        """
        # Fantasy basketball weeks typically start on Monday
        # Week 1 starts around Oct 21, 2024
        season_start = datetime(2024, 10, 21)  # Adjust based on actual season start
        
        # Calculate week start (Monday of the target week)
        days_offset = (week_number - 1) * 7
        week_start = season_start + timedelta(days=days_offset)
        
        # Week runs Monday through Sunday (7 days)
        week_end = week_start + timedelta(days=6)
        
        return {
            'start': week_start.strftime('%Y-%m-%d'),
            'end': week_end.strftime('%Y-%m-%d')
        }
    
    def _init_claude_api(self):
        """Initialize Claude API client if available."""
        if not ANTHROPIC_AVAILABLE:
            print("⚠️  Claude API not available (SDK not installed)")
            return False
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key or api_key == 'your_anthropic_api_key_here':
            print("⚠️  ANTHROPIC_API_KEY not found in .env file")
            print("   Get your API key from: https://console.anthropic.com/")
            return False
        
        try:
            self.client = Anthropic(api_key=api_key)
            self.ai_provider = 'claude'
            self.api_key = api_key[:8] + "..."
            print("✓ Claude API initialized successfully")
            return True
        except Exception as e:
            print(f"⚠️  Failed to initialize Claude API: {e}")
            return False
    
    def is_api_available(self) -> bool:
        """Check if API is ready to use."""
        return self.client is not None
    
    def _get_target_week(self, sunday_cutoff_hour: int = SUNDAY_CUTOFF_HOUR) -> int:
        """
        Get the correct week to analyze (handles Sunday look-ahead with TIMEZONE AWARENESS).
        
        CRITICAL FIX: Uses matchup_scheduler.get_target_week() which:
        - Returns current week normally
        - Returns NEXT week on Sundays after cutoff_hour (in configured timezone!)
        - Now properly handles PST vs UTC timezone differences
        
        Args:
            sunday_cutoff_hour: Hour (0-23) to switch to next week on Sundays
        
        Returns:
            Week number to analyze
        """
        if not self.matchup_scheduler:
            print("[DEBUG] No scheduler - falling back to manual week detection")
            return self.matchup_analyzer.get_current_week(self.config.settings.league_id)
        
        team_key = self._get_team_key()
        target_week = self.matchup_scheduler.get_target_week(
            team_key,
            cutoff_hour=sunday_cutoff_hour,
            debug=True  # Enable detailed logging
        )
        
        # Log what we're doing (use configured timezone!)
        tz = ZoneInfo(self.config.settings.timezone) if self.config else ZoneInfo("US/Pacific")
        now = datetime.now(tz)
        
        is_sunday = now.weekday() == 6
        timezone_name = self.config.settings.timezone if self.config else "PST"
        current_time_str = now.strftime('%a %I:%M %p')
        
        if is_sunday and now.hour >= sunday_cutoff_hour:
            print(f"[DEBUG] Sunday after {sunday_cutoff_hour}:00 {timezone_name} ({current_time_str}) - Looking ahead to Week {target_week}")
        else:
            print(f"[DEBUG] Analyzing Week {target_week} (current time: {current_time_str} {timezone_name})")
        
        return target_week
    
    def _get_roster_for_date(self, date_str: str) -> List[Dict]:
        """
        Get roster for a specific date.
        
        Args:
            date_str: Date in YYYY-MM-DD format
        
        Returns:
            List of players on roster for that date
        """
        if not self.roster_analyzer or not self.config:
            return []
        
        try:
            roster = self.roster_analyzer.get_my_roster(
                self.config.settings.league_id,
                self.config.settings.team_id,
                date=date_str
            )
            return roster
        except Exception as e:
            print(f"[DEBUG] Error fetching roster for {date_str}: {e}")
            return []
    
    def _get_already_dropped_players(self) -> set:
        """
        CRITICAL FIX: Detect players already dropped (pending drop).
        
        Compares today's roster vs tomorrow's roster. Players on today's
        roster but not tomorrow's are pending drops.
        
        Returns:
            Set of player names that are already dropped
        """
        print("\n[DEBUG] Checking for already-dropped players...")
        
        if not self.roster_analyzer or not self.config:
            print("[DEBUG] Cannot check - no roster analyzer")
            return set()
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            print(f"[DEBUG] Comparing roster: {today} vs {tomorrow}")
            
            roster_today = self._get_roster_for_date(today)
            roster_tomorrow = self._get_roster_for_date(tomorrow)
            
            if not roster_today or not roster_tomorrow:
                print("[DEBUG] Could not fetch both rosters")
                return set()
            
            # Get player names
            players_today = {p.get('name') for p in roster_today if p.get('name')}
            players_tomorrow = {p.get('name') for p in roster_tomorrow if p.get('name')}
            
            # Players on today's roster but not tomorrow's = already dropped
            already_dropped = players_today - players_tomorrow
            
            if already_dropped:
                print(f"[DEBUG] Found {len(already_dropped)} already-dropped players: {already_dropped}")
            else:
                print(f"[DEBUG] No pending drops detected")
            
            return already_dropped
            
        except Exception as e:
            print(f"[DEBUG] Error checking already-dropped players: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return set()
    
    def _get_roster_moves_remaining(self) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Get roster moves remaining this week from Yahoo API.
        
        Returns:
            (moves_made, max_moves, moves_remaining)
        """
        print("[DEBUG] Fetching roster moves data from Yahoo API...")
        
        if not self.auth or not self.config:
            print("[DEBUG] No auth/config available for roster moves")
            return (None, None, None)
        
        try:
            league_id = self.config.settings.league_id
            team_id = self.config.settings.team_id
            
            team_key = self.auth.get_team_key(league_id, team_id)
            url = f"{self.auth.fantasy_base_url}team/{team_key}?format=json"
            
            print(f"[DEBUG] Calling Yahoo API: {url}")
            response = self.auth.session.get(url, timeout=10)
            print(f"[DEBUG] Response status: {response.status_code}")
            
            if response.status_code != 200:
                return (None, None, None)
            
            data = response.json()
            team_data = data['fantasy_content']['team']
            
            # Find roster_adds in team data (can be nested in a list) - FIXED BUG
            roster_adds = None
            for item in team_data:
                if isinstance(item, dict) and 'roster_adds' in item:
                    roster_adds = item['roster_adds']
                    print(f"[DEBUG] Found roster_adds in dict: {roster_adds}")
                    break
                elif isinstance(item, list):
                    for sub in item:
                        if isinstance(sub, dict) and 'roster_adds' in sub:
                            roster_adds = sub['roster_adds']
                            print(f"[DEBUG] Found roster_adds in list: {roster_adds}")
                            break
                    if roster_adds:
                        break
            
            if roster_adds:
                moves_made = int(roster_adds.get('value', 0))
                max_moves = DEFAULT_MAX_MOVES_PER_WEEK  # From constants
                moves_remaining = max(0, max_moves - moves_made)
                
                print(f"[DEBUG] Roster moves: {moves_made}/{max_moves} used, {moves_remaining} remaining")
                return (moves_made, max_moves, moves_remaining)
            
            print(f"[DEBUG] roster_adds not found in team data")
            return (None, None, None)
            
        except Exception as e:
            print(f"[DEBUG] Error fetching roster moves: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return (None, None, None)
    
    def fetch_live_roster(self, filter_dropped: bool = True) -> List[Dict]:
        """
        Fetch LIVE roster data from Yahoo API.
        
        Args:
            filter_dropped: If True, exclude already-dropped players
        
        Returns:
            List of players (filtered if requested)
        """
        print("\n[DEBUG] Fetching LIVE roster data from Yahoo API...")
        
        if not self.roster_analyzer or not self.config:
            print("[DEBUG] Falling back to JSON file")
            return self._load_roster_from_file()
        
        try:
            roster_data = self.roster_analyzer.get_my_roster(
                self.config.settings.league_id, 
                self.config.settings.team_id
            )
            
            if roster_data:
                print(f"[DEBUG] Successfully fetched {len(roster_data)} players from Yahoo API")
                
                # CRITICAL FIX: Filter out already-dropped players
                if filter_dropped:
                    already_dropped = self._get_already_dropped_players()
                    if already_dropped:
                        original_count = len(roster_data)
                        roster_data = [p for p in roster_data if p.get('name') not in already_dropped]
                        filtered_count = original_count - len(roster_data)
                        print(f"[DEBUG] Filtered out {filtered_count} already-dropped players")
                
                # Save for backup
                os.makedirs('data', exist_ok=True)
                output = {
                    'timestamp': datetime.now().isoformat(),
                    'league_id': self.config.settings.league_id,
                    'team_id': self.config.settings.team_id,
                    'roster': roster_data
                }
                with open('data/my_roster.json', 'w') as f:
                    json.dump(output, f, indent=2)
                print(f"[DEBUG] Saved backup to data/my_roster.json")
                
                return roster_data
            else:
                print("[DEBUG] Invalid roster data, falling back to file")
                return self._load_roster_from_file()
                
        except Exception as e:
            print(f"[DEBUG] Error fetching live roster: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            print("[DEBUG] Falling back to JSON file")
            return self._load_roster_from_file()
    
    def _load_roster_from_file(self) -> List[Dict]:
        """Fallback: Load roster from JSON file."""
        filename = 'data/my_roster.json'
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Roster file not found: {filename}")
        
        with open(filename, 'r') as f:
            data = json.load(f)
            return data['roster']
    
    def fetch_live_available_players(self, use_cache: bool = True) -> List[Dict]:
        """
        Fetch LIVE available players from Yahoo API with caching.
        
        Args:
            use_cache: If True, use cached data if available (default: True)
        
        Returns:
            List of available players
        """
        print("\n[DEBUG] Fetching LIVE available players from Yahoo API...")
        
        if not self.player_fetcher or not self.config:
            print("[DEBUG] Falling back to JSON file")
            return self._load_players_from_file()
        
        # Check cache first (uses CACHE_TTL_AVAILABLE_PLAYERS from constants)
        cache_key = f"available_players_{self.config.settings.league_id}"
        if use_cache and CACHE_AVAILABLE and cache:
            cached_data = cache.get(cache_key, max_age_seconds=CACHE_TTL_AVAILABLE_PLAYERS)
            if cached_data:
                print(f"[DEBUG] ✓ Using cached available players ({len(cached_data)} players)")
                return cached_data
        
        try:
            print(f"[DEBUG] Fetching all available players...")
            all_players = self.player_fetcher.get_all_available_players(
                self.config.settings.league_id,
                max_players=MAX_AVAILABLE_PLAYERS
            )
            
            print(f"[DEBUG] Filtering for healthy players...")
            players = self.player_fetcher.filter_healthy_players(all_players)
            
            if players:
                print(f"[DEBUG] Successfully fetched {len(players)} available players from Yahoo API")
                
                # Cache the data (30 minute TTL)
                if CACHE_AVAILABLE and cache:
                    cache.set(cache_key, players)
                    print(f"[DEBUG] ✓ Cached available players for 30 minutes")
                
                # Save for backup
                os.makedirs('data', exist_ok=True)
                output = {
                    'timestamp': datetime.now().isoformat(),
                    'league_id': self.config.settings.league_id,
                    'count': len(players),
                    'players': players
                }
                with open('data/healthy_players.json', 'w') as f:
                    json.dump(output, f, indent=2)
                print(f"[DEBUG] Saved backup to data/healthy_players.json")
                
                return players
            else:
                print("[DEBUG] No players returned, falling back to file")
                return self._load_players_from_file()
                
        except Exception as e:
            print(f"[DEBUG] Error fetching live players: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            print("[DEBUG] Falling back to JSON file")
            return self._load_players_from_file()
    
    def _load_players_from_file(self) -> List[Dict]:
        """Fallback: Load players from JSON file."""
        filename = 'data/healthy_players.json'
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Players file not found: {filename}")
        
        with open(filename, 'r') as f:
            data = json.load(f)
            return data['players']
    
    def fetch_live_matchup(self, target_week: Optional[int] = None) -> Optional[Dict]:
        """
        Fetch LIVE matchup data from Yahoo API.
        
        CRITICAL FIX: Uses target_week parameter (supports Sunday look-ahead).
        
        Args:
            target_week: Week to analyze (if None, uses _get_target_week())
        
        Returns:
            Matchup data for the target week
        """
        print("\n[DEBUG] Fetching LIVE matchup data from Yahoo API...")
        
        if not self.matchup_analyzer or not self.config:
            print("[DEBUG] Falling back to JSON file")
            return self._load_matchup_from_file()
        
        try:
            league_id = self.config.settings.league_id
            team_id = self.config.settings.team_id
            
            # CRITICAL FIX: Use target week (handles Sunday look-ahead)
            if target_week is None:
                target_week = self._get_target_week()
            
            print(f"[DEBUG] Target week: {target_week}")
            
            print(f"[DEBUG] Fetching scoreboard...")
            all_matchups = self.matchup_analyzer.get_league_scoreboard(league_id, week=target_week)
            
            if not all_matchups:
                print(f"[DEBUG] No matchups found")
                return None
            
            print(f"[DEBUG] Found {len(all_matchups)} matchups")
            
            my_matchup = self.matchup_analyzer.find_my_matchup(all_matchups, team_id)
            if not my_matchup:
                print(f"[DEBUG] Could not find your matchup")
                return None
            
            opponent_info = self.matchup_analyzer.get_opponent_info(my_matchup, team_id)
            if not opponent_info:
                print(f"[DEBUG] Could not find opponent")
                return None
            
            print(f"[DEBUG] Opponent: {opponent_info['team_name']}")
            
            # Fetch live stats
            my_team_key = self.auth.get_team_key(league_id, team_id)
            opponent_team_key = opponent_info['team_key']
            
            print(f"[DEBUG] Fetching team stats...")
            my_stats = self.matchup_analyzer.get_team_stats_for_week(my_team_key, target_week)
            opponent_stats = self.matchup_analyzer.get_team_stats_for_week(opponent_team_key, target_week)
            
            if not my_stats or not opponent_stats:
                print(f"[DEBUG] Could not fetch stats")
                return None
            
            # Compare stats
            comparison, wins, losses, ties = self.matchup_analyzer.compare_teams_with_live_stats(my_stats, opponent_stats)
            targets = self.matchup_analyzer.identify_target_categories(comparison)
            
            matchup_data = {
                'timestamp': datetime.now().isoformat(),
                'week': target_week,
                'my_team': self.config.settings.team_name,
                'opponent': opponent_info,
                'matchup_status': my_matchup['status'],
                'category_comparison': comparison,
                'strategic_targets': targets,
                'current_score': {'wins': wins, 'losses': losses, 'ties': ties}
            }
            
            print(f"[DEBUG] Successfully fetched matchup data for Week {target_week}")
            print(f"[DEBUG] Current score: {wins}-{losses}-{ties}")
            
            # ENHANCEMENT: Fetch schedule data using OpponentAnalyzer
            if self.opponent_analyzer:
                print(f"[DEBUG] Fetching schedule data via OpponentAnalyzer...")
                try:
                    week_dates = self._get_week_dates(target_week)
                    
                    # Get current roster for opponent analysis
                    # This allows OpponentAnalyzer to validate properly and provide full analysis
                    current_roster = self.roster_analyzer.get_my_roster(
                        league_id,
                        team_id
                    ) if self.roster_analyzer else []
                    
                    schedule_analysis = self.opponent_analyzer.analyze_matchup(
                        my_roster=current_roster,
                        opponent_team_key=opponent_team_key,
                        week_start=week_dates['start'],
                        week_end=week_dates['end']
                    )
                    
                    if schedule_analysis and 'games_per_team' in schedule_analysis:
                        matchup_data['games_per_team'] = schedule_analysis['games_per_team']
                        num_teams = len(schedule_analysis['games_per_team'])
                        print(f"[DEBUG] Got schedule for {num_teams} teams")
                    else:
                        print(f"[DEBUG] No schedule data in opponent analysis")
                        
                except Exception as e:
                    print(f"[DEBUG] Could not fetch schedule data: {e}")
            
            # Save for backup
            os.makedirs('data', exist_ok=True)
            with open('data/weekly_matchup.json', 'w') as f:
                json.dump(matchup_data, f, indent=2)
            print(f"[DEBUG] Saved backup to data/weekly_matchup.json")
            
            return matchup_data
            
        except Exception as e:
            print(f"[DEBUG] Error fetching live matchup: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            print("[DEBUG] Falling back to JSON file")
            return self._load_matchup_from_file()
    
    def _load_matchup_from_file(self) -> Optional[Dict]:
        """Fallback: Load matchup from JSON file."""
        filename = 'data/weekly_matchup.json'
        if not os.path.exists(filename):
            return None
        
        with open(filename, 'r') as f:
            return json.load(f)
    
    def _get_schedule_data(self, matchup_data: Dict) -> Optional[Dict[str, int]]:
        """
        Get schedule data (games per team) from matchup analysis.
        
        Note: This comes from OpponentAnalyzer which fetches NBA schedule from ESPN.
        The matchup_data should already contain this if available.
        
        Args:
            matchup_data: Matchup data dict (may contain schedule info)
        
        Returns:
            Dict of {team_abbrev: num_games} or None
        """
        if not matchup_data:
            return None
        
        # Check if matchup_data has schedule info embedded
        # (OpponentAnalyzer includes this when week_start/week_end provided)
        if 'games_per_team' in matchup_data:
            print(f"[DEBUG] Using schedule data from matchup analysis")
            return matchup_data['games_per_team']
        
        # No schedule data available
        print("[DEBUG] No schedule data available in matchup")
        return None
    
    def _enrich_players_with_schedule(self, players: List[Dict], 
                                      games_per_team: Optional[Dict[str, int]]) -> List[Dict]:
        """
        Add games_remaining field to each player based on their team's schedule.
        
        Args:
            players: List of player dicts
            games_per_team: Dict of {team_abbrev: num_games} from schedule
        
        Returns:
            Same player list with 'games_remaining' added
        """
        if not games_per_team:
            # No schedule data - set all to 0 (unknown)
            for player in players:
                player['games_remaining'] = 0
            return players
        
        # Add games_remaining based on player's team
        for player in players:
            team = player.get('team', '')
            player['games_remaining'] = games_per_team.get(team, 0)
        
        return players
    
    def _filter_top_available_players(self, 
                                     available_players: List[Dict], 
                                     target_categories: Optional[List[str]] = None,
                                     limit: int = DEFAULT_PLAYER_LIMIT) -> List[Dict]:
        """
        Uses PlayerEvaluator with quality-first scoring.
        Falls back to basic filtering if PlayerEvaluator not available.
        """
        if not available_players:
            return []
        
        # Use PlayerEvaluator if available
        if PLAYER_EVALUATOR_AVAILABLE:
            evaluator = PlayerEvaluator()
            top_players = evaluator.filter_and_rank(available_players, limit=limit)
            
            if top_players:
                print(f"[FILTER] {len(top_players)} players passed hard filters (MIN>=20, PTS>=8)")
                print(f"[FILTER] Top player: {top_players[0].get('name')} (score: {top_players[0].get('final_score', 0):.1f})")
            
            return top_players
        
        # Fallback to basic filtering
        print("[FILTER] Using fallback filtering (PlayerEvaluator not available)")
        
        scored_players = []
        
        for player in available_players:
            score = 0
            
            # 1. Games remaining (0-10 points, scaled)
            games = player.get('games_remaining', 0)
            if games > 0:
                score += min(10, games * 2.5)
            
            # 2. Target category strength (0-15 points if target_categories provided)
            if target_categories:
                stats = player.get('season_stats', {})
                target_strength = 0
                
                for cat in target_categories:
                    cat_clean = cat.strip().upper()
                    stat_value = 0
                    
                    if cat_clean == 'FG%':
                        stat_value = stats.get('FG%', 0)
                        if stat_value >= 0.50:
                            target_strength += 3
                        elif stat_value >= 0.45:
                            target_strength += 2
                    elif cat_clean == 'FT%':
                        stat_value = stats.get('FT%', 0)
                        if stat_value >= 0.85:
                            target_strength += 3
                        elif stat_value >= 0.80:
                            target_strength += 2
                    elif cat_clean == '3PTM':
                        stat_value = stats.get('3PTM', 0)
                        if stat_value >= 2.5:
                            target_strength += 3
                        elif stat_value >= 2.0:
                            target_strength += 2
                    elif cat_clean in ['PTS', 'POINTS']:
                        stat_value = stats.get('PTS', 0)
                        if stat_value >= 20:
                            target_strength += 3
                        elif stat_value >= 15:
                            target_strength += 2
                    elif cat_clean in ['REB', 'REBOUNDS']:
                        stat_value = stats.get('REB', 0)
                        if stat_value >= 10:
                            target_strength += 3
                        elif stat_value >= 7:
                            target_strength += 2
                    elif cat_clean in ['AST', 'ASSISTS']:
                        stat_value = stats.get('AST', 0)
                        if stat_value >= 7:
                            target_strength += 3
                        elif stat_value >= 5:
                            target_strength += 2
                    elif cat_clean in ['ST', 'STEALS']:
                        stat_value = stats.get('ST', 0)
                        if stat_value >= 1.5:
                            target_strength += 3
                        elif stat_value >= 1.0:
                            target_strength += 2
                    elif cat_clean in ['BLK', 'BLOCKS']:
                        stat_value = stats.get('BLK', 0)
                        if stat_value >= 1.5:
                            target_strength += 3
                        elif stat_value >= 1.0:
                            target_strength += 2
                    elif cat_clean == 'TO':
                        stat_value = stats.get('TO', 99)
                        if stat_value <= 1.5:
                            target_strength += 3
                        elif stat_value <= 2.0:
                            target_strength += 2
                
                score += min(15, target_strength)
            
            # 3. Overall production (0-10 points)
            stats = player.get('season_stats', {})
            production_score = 0
            
            if stats.get('PTS', 0) >= 12:
                production_score += 1.5
            if stats.get('REB', 0) >= 6:
                production_score += 1.5
            if stats.get('AST', 0) >= 4:
                production_score += 1.5
            if stats.get('3PTM', 0) >= 1.5:
                production_score += 1.5
            if stats.get('ST', 0) >= 0.8:
                production_score += 1
            if stats.get('BLK', 0) >= 0.8:
                production_score += 1
            if stats.get('FG%', 0) >= 0.45:
                production_score += 1
            if stats.get('FT%', 0) >= 0.75:
                production_score += 0.5
            
            score += min(10, production_score)
            
            # 4. Position scarcity bonus (0-5 points)
            position = player.get('primary_position', '')
            if position in ['C', 'PG']:
                score += 3
            elif position in ['PF', 'SG']:
                score += 1
            
            scored_players.append({
                'player': player,
                'score': score
            })
        
        # Sort by score (highest first)
        scored_players.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top N players
        top_players = [item['player'] for item in scored_players[:limit]]
        
        if scored_players:
            print(f"[DEBUG] Filtered {len(available_players)} → {len(top_players)} players")
            print(f"[DEBUG] Top player score: {scored_players[0]['score']:.1f}, Bottom: {scored_players[min(limit-1, len(scored_players)-1)]['score']:.1f}")
        
        return top_players

    
    def _build_compact_roster_summary(self, my_roster: List[Dict]) -> str:
        """Build compact roster summary with ALL stats and CLEAR injury status."""
        
        # Injury code mapping to prevent AI hallucinations
        INJURY_CODES = {
            'O': 'OUT',
            'GTD': 'QUESTIONABLE',
            'DTD': 'DAY-TO-DAY',
            'IR': 'INJ-RESERVE',
            'INJ': 'INJURED',
            'SUSP': 'SUSPENDED',
            'NA': 'NOT-ACTIVE',
            'PUP': 'UNABLE-TO-PLAY'
        }
        
        lines = []
        
        for player in my_roster:
            name = player.get('name', 'Unknown')
            team = player.get('team', 'FA')
            pos = player.get('primary_position', 'N/A')
            slot = player.get('selected_position', 'N/A')
            injury = player.get('injury_status')
            games = player.get('games_remaining', 0)
            stats = player.get('season_stats', {})
            
            # Format: Name (TEAM-POS, Xg) - PPG/RPG/AST/ST/BLK/3PM/TO/FG%/FT%/MIN
            player_str = f"{name} ({team}-{pos}"
            if games > 0:
                player_str += f", {games}g"
            player_str += ") - "
            
            # Add all stats
            player_str += f"{stats.get('PTS', 0):.1f}/"
            player_str += f"{stats.get('REB', 0):.1f}/"
            player_str += f"{stats.get('AST', 0):.1f}/"
            player_str += f"{stats.get('ST', 0):.1f}/"
            player_str += f"{stats.get('BLK', 0):.1f}/"
            player_str += f"{stats.get('3PTM', 0):.1f}/"
            player_str += f"{stats.get('TO', 0):.1f}/"
            player_str += f"{stats.get('FG%', 0):.3f}/"
            player_str += f"{stats.get('FT%', 0):.3f}/"
            player_str += f"{stats.get('MIN', 0):.1f}"
            
            if slot and slot != pos:
                player_str += f" [{slot}]"
            if injury:
                # Expand cryptic injury codes for clarity
                clear_status = INJURY_CODES.get(injury, injury)
                player_str += f" ⚠️{clear_status}"
            
            lines.append(player_str)

        
        return '\n'.join(lines)
    
    def _build_compact_available_players(self, available_players: List[Dict]) -> str:
        """Build compact available players list with ALL stats and quality scores."""
        lines = []
        
        for player in available_players:
            name = player.get('name', 'Unknown')
            team = player.get('team', 'FA')
            pos = player.get('primary_position', 'N/A')
            games = player.get('games_remaining', 0)
            stats = player.get('season_stats', {})
            final_score = player.get('final_score', 0)
            
            # Format: Name (TEAM-POS, Xg) - PPG/RPG/AST/ST/BLK/3PM/TO/FG%/FT%/MIN [Score: XX.X]
            player_str = f"{name} ({team}-{pos}"
            if games > 0:
                player_str += f", {games}g"
            player_str += ") - "
            
            # Add all stats
            player_str += f"{stats.get('PTS', 0):.1f}/"
            player_str += f"{stats.get('REB', 0):.1f}/"
            player_str += f"{stats.get('AST', 0):.1f}/"
            player_str += f"{stats.get('ST', 0):.1f}/"
            player_str += f"{stats.get('BLK', 0):.1f}/"
            player_str += f"{stats.get('3PTM', 0):.1f}/"
            player_str += f"{stats.get('TO', 0):.1f}/"
            player_str += f"{stats.get('FG%', 0):.3f}/"
            player_str += f"{stats.get('FT%', 0):.3f}/"
            player_str += f"{stats.get('MIN', 0):.1f}"
            
            # Add quality score if available
            if final_score > 0:
                player_str += f" [Score: {final_score:.1f}]"
            
            lines.append(player_str)
        
        return '\n'.join(lines)
    
    def _build_matchup_summary(self, matchup_data: Dict) -> str:
        """Build compact matchup summary."""
        if not matchup_data:
            return ""
        
        lines = []
        lines.append(f"Week {matchup_data.get('week', 'N/A')} vs {matchup_data.get('opponent', {}).get('team_name', 'Unknown')}")
        
        if 'category_comparison' in matchup_data:
            comparison = matchup_data['category_comparison']
            
            winning = [cat for cat, data in comparison.items() if data.get('status') == 'WINNING']
            losing = [cat for cat, data in comparison.items() if data.get('status') == 'LOSING']
            tied = [cat for cat, data in comparison.items() if data.get('status') == 'TIED']
            
            lines.append(f"WINNING: {', '.join(winning) if winning else 'None'}")
            lines.append(f"LOSING: {', '.join(losing) if losing else 'None'}")
            lines.append(f"TIED: {', '.join(tied) if tied else 'None'}")
        
        if 'strategic_targets' in matchup_data:
            targets = matchup_data['strategic_targets']
            
            if targets.get('winnable'):
                winnable_cats = [f"{item['category']}" for item in targets['winnable'][:3]]
                lines.append(f"🎯 WINNABLE: {', '.join(winnable_cats)}")
        
        return '\n'.join(lines)
    
    def build_optimized_prompt(self, 
                              my_roster: List[Dict],
                              available_players: List[Dict],
                              target_categories: Optional[List[str]] = None,
                              matchup_data: Optional[Dict] = None,
                              use_phase4a: bool = True) -> str:
        """
        Build OPTIMIZED prompt with Phase 4A enhancements.
        """
        
        print("\n[DEBUG] Building AI prompt...")
        
        league_name = self._get_league_name()
        team_name = self._get_team_name()
        
        filtered_players = self._filter_top_available_players(
            available_players, 
            target_categories, 
            limit=25
        )
        
        print(f"[DEBUG] Filtered to top {len(filtered_players)} players")
        
        # ENHANCEMENT: Enrich players with games remaining from schedule
        games_per_team = self._get_schedule_data(matchup_data)
        if games_per_team:
            print(f"[DEBUG] Enriching players with schedule data ({len(games_per_team)} teams)")
            my_roster = self._enrich_players_with_schedule(my_roster, games_per_team)
            filtered_players = self._enrich_players_with_schedule(filtered_players, games_per_team)
        
        roster_summary = self._build_compact_roster_summary(my_roster)
        available_summary = self._build_compact_available_players(filtered_players)
        matchup_summary = self._build_matchup_summary(matchup_data) if matchup_data else ""
        
        prompt = f"""Fantasy Basketball Roster Analysis

LEAGUE: {league_name} (H2H 9-Cat)
TEAM: {team_name}
CATEGORIES: FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO (lower is better)

MY ROSTER ({len(my_roster)} players):
{roster_summary}

TOP AVAILABLE FREE AGENTS ({len(filtered_players)} shown):
{available_summary}
({len(available_players) - len(filtered_players)} more available)"""

        if matchup_summary:
            prompt += f"\n\nMATCHUP:\n{matchup_summary}"
            print(f"[DEBUG] Added matchup summary")
        
        if target_categories:
            prompt += f"\n\nPRIORITY CATEGORIES: {', '.join(target_categories)}"
            print(f"[DEBUG] Added priority categories: {target_categories}")
        
        # Phase 4A: Add strategic analysis insights
        if use_phase4a and self.strategic_analyzer:
            print("[DEBUG] Adding Phase 4A strategic analysis...")
            
            try:
                # Get schedule data from matchup if available
                games_per_team = self._get_schedule_data(matchup_data)
                
                # Generate enhanced strategic section
                strategic_section = self.strategic_analyzer.generate_enhanced_prompt_section(
                    my_roster, available_players, games_per_team
                )
                
                if strategic_section:
                    prompt += f"\n\n{strategic_section}"
                    print("✓ Added Phase 4A strategic analysis")
                else:
                    print("[DEBUG] No strategic analysis generated")
                    
            except Exception as e:
                print(f"[DEBUG] Error adding Phase 4A analysis: {e}")
        
        # Add roster moves constraint
        moves_made, max_moves, moves_remaining = self._get_roster_moves_remaining()
        if moves_remaining is not None:
            prompt += f"\n\nROSTER MOVES: {moves_made}/{max_moves} used, {moves_remaining} remaining this week"
            print(f"[DEBUG] Added roster moves constraint: {moves_remaining} remaining")
        
        # Add task instructions with moves constraint
        if moves_remaining is not None:
            if moves_remaining == 0:
                task_instruction = "\n\nIMPORTANT: You have NO MOVES REMAINING this week. Do NOT recommend any adds. Instead, provide lineup optimization advice for maximizing points with current roster."
            elif moves_remaining == 1:
                task_instruction = "\n\nIMPORTANT: You have ONLY 1 MOVE REMAINING this week. Recommend ONLY your single best add/drop that will have the biggest impact."
            else:
                task_instruction = f"\n\nTASK: You have {moves_remaining} moves remaining this week. Give me up to {moves_remaining} specific ADD/DROP recommendations, ranked by priority."
        else:
            task_instruction = "\n\nTASK: Give me 3-5 specific ADD/DROP recommendations."
        
        prompt += task_instruction + """

For each move, provide:
1. ADD: [Player Name]
2. DROP: [Player from my roster]
3. IMPROVES: [Categories]
4. PRIORITY: High/Medium/Low
5. WHY: Brief reason (1-2 sentences)

Focus on winning this week's matchup. Consider roster balance, positional scarcity, and schedule advantages. Be specific and concise."""
        
        print(f"[DEBUG] Prompt built successfully: {len(prompt)} characters")
        return prompt
    
    def call_claude_api(self, prompt: str, max_tokens: int = 2048, use_caching: bool = True) -> str:
        """Call Claude API with optimizations."""
        if not self.client:
            raise RuntimeError("Claude API not initialized. Check your API key.")
        
        print("\n🤖 Calling Claude API...")
        print(f"   Model: claude-sonnet-4-5-20250929")
        print(f"   Prompt length: {len(prompt):,} characters")
        
        try:
            message_params = {
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            if use_caching:
                league_name = self._get_league_name()
                team_name = self._get_team_name()
                
                system_context = f"""Fantasy Basketball Roster Analysis

LEAGUE: {league_name} (H2H 9-Cat)
TEAM: {team_name}
CATEGORIES: FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO (lower is better)

You are an expert fantasy basketball analyst. Provide strategic recommendations considering roster composition, positional scarcity, schedule advantages, and category targets."""
                
                message_params["system"] = [
                    {
                        "type": "text",
                        "text": system_context,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            
            message = self.client.messages.create(**message_params)
            response_text = message.content[0].text
            
            print(f"\n✓ Response received!")
            print(f"   Input tokens: {message.usage.input_tokens:,}")
            print(f"   Output tokens: {message.usage.output_tokens:,}")
            
            if hasattr(message.usage, 'cache_creation_input_tokens'):
                if message.usage.cache_creation_input_tokens:
                    print(f"   Cache created: {message.usage.cache_creation_input_tokens:,} tokens")
            if hasattr(message.usage, 'cache_read_input_tokens'):
                if message.usage.cache_read_input_tokens:
                    print(f"   Cache hits: {message.usage.cache_read_input_tokens:,} tokens (90% savings!)")
            
            input_cost = (message.usage.input_tokens / 1_000_000) * 3.00
            output_cost = (message.usage.output_tokens / 1_000_000) * 15.00
            
            cache_savings = 0
            if hasattr(message.usage, 'cache_read_input_tokens') and message.usage.cache_read_input_tokens:
                cache_read_tokens = message.usage.cache_read_input_tokens
                cache_savings = (cache_read_tokens / 1_000_000) * 3.00 * 0.90
            
            total_cost = input_cost + output_cost - cache_savings
            
            print(f"   Estimated cost: ${total_cost:.4f}")
            if cache_savings > 0:
                print(f"   Cache savings: ${cache_savings:.4f}")
            
            return response_text
            
        except Exception as e:
            print(f"\n❌ Error calling Claude API: {e}")
            raise
    
    def format_recommendations_for_display(self, ai_response: str) -> str:
        """Format AI response for nice display."""
        formatted = "\n" + "="*80 + "\n"
        formatted += "AI ROSTER RECOMMENDATIONS (Phase 4A Enhanced)\n"
        formatted += "="*80 + "\n\n"
        formatted += ai_response
        formatted += "\n" + "="*80 + "\n"
        
        return formatted
    
    def save_recommendations(self, ai_response: str, prompt: str, filename='data/ai_recommendations.json'):
        """Save AI recommendations to file."""
        os.makedirs('data', exist_ok=True)
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt,
            'ai_response': ai_response,
            'ai_provider': self.ai_provider or 'manual',
            'prompt_length': len(prompt),
            'response_length': len(ai_response),
            'phase': '4A'
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        text_filename = filename.replace('.json', '.txt')
        with open(text_filename, 'w') as f:
            f.write(self.format_recommendations_for_display(ai_response))
        
        print(f"✓ Saved recommendations to {filename}")
        print(f"✓ Saved readable version to {text_filename}")
    
    def analyze_with_api(self, target_categories: Optional[List[str]] = None):
        """Run Phase 4A enhanced analysis with Claude API using LIVE data."""
        if not self.is_api_available():
            print("\n❌ Claude API not available.")
            return None
        
        print("\n" + "="*80)
        print("AI-POWERED ROSTER ANALYSIS (Phase 4A - LIVE DATA + ALL FIXES)")
        print("="*80 + "\n")
        
        # Fetch LIVE data
        print("Fetching LIVE data from Yahoo API...")
        
        # CRITICAL FIX: Filter out already-dropped players
        my_roster = self.fetch_live_roster(filter_dropped=True)
        print(f"✓ Loaded {len(my_roster)} players from your roster (excluding pending drops)")
        
        available_players = self.fetch_live_available_players()
        print(f"✓ Loaded {len(available_players)} available players")
        
        # CRITICAL FIX: Use correct target week (handles Sunday look-ahead)
        target_week = self._get_target_week(sunday_cutoff_hour=SUNDAY_CUTOFF_HOUR)
        matchup_data = self.fetch_live_matchup(target_week=target_week)
        if matchup_data:
            print(f"✓ Loaded Week {matchup_data.get('week')} matchup data")
            print(f"✓ Opponent: {matchup_data.get('opponent', {}).get('team_name', 'Unknown')}")
        else:
            print("⚠️  No matchup data available")
        
        # Check roster moves
        moves_made, max_moves, moves_remaining = self._get_roster_moves_remaining()
        if moves_remaining is not None:
            print(f"✓ Roster moves: {moves_made}/{max_moves} used, {moves_remaining} remaining this week")
        else:
            print("⚠️  Could not fetch roster moves info")
        
        # Build Phase 4A enhanced prompt
        print("\nGenerating Phase 4A enhanced AI prompt...")
        prompt = self.build_optimized_prompt(
            my_roster=my_roster,
            available_players=available_players,
            target_categories=target_categories,
            matchup_data=matchup_data,
            use_phase4a=True
        )
        
        est_tokens = len(prompt) // 4
        print(f"✓ Phase 4A prompt: ~{est_tokens:,} tokens")
        
        # Save prompt
        prompt_file = 'data/ai_prompt.txt'
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        print(f"✓ Prompt saved to {prompt_file}")
        
        # Call API
        try:
            ai_response = self.call_claude_api(prompt, max_tokens=2048, use_caching=True)
            
            self.save_recommendations(ai_response, prompt)
            print(self.format_recommendations_for_display(ai_response))
            
            return ai_response
            
        except Exception as e:
            print(f"\n❌ API call failed: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return None


if __name__ == "__main__":
    config = LeagueConfig() if LEAGUE_CONFIG_AVAILABLE else None
    analyzer = AIAnalyzer(config)
    
    print("\n" + "="*80)
    print("AI-Powered Fantasy Basketball Analyzer (Phase 4A - ALL FIXES)")
    print("="*80 + "\n")
    
    if analyzer.is_api_available():
        print("✓ Claude API is ready!")
        print(f"  Provider: {analyzer.ai_provider}")
        print(f"  API Key: {analyzer.api_key}")
        print("  Optimizations: ENABLED")
        print("  Phase 4A: ENABLED (roster balance, scarcity, schedule)")
        print("  FIXES: Correct week detection, Sunday look-ahead, filter dropped players")
        mode = "automatic"
    else:
        print("⚠️  Claude API not available")
        mode = "manual"
    
    print("\n" + "-"*80 + "\n")
    
    print("Do you want to focus on specific categories?")
    print("\nOptions:")
    print("  1. Focus on winnable categories (if matchup data available)")
    print("  2. General roster improvement (all categories)")
    print("  3. Custom categories")
    
    choice = input("\nEnter choice (1-3) [default: 2]: ").strip() or "2"
    
    target_categories = None
    if choice == "1":
        try:
            # This will use the correct target week
            target_week = analyzer._get_target_week(sunday_cutoff_hour=SUNDAY_CUTOFF_HOUR)
            matchup_data = analyzer.fetch_live_matchup(target_week=target_week)
            if matchup_data and 'strategic_targets' in matchup_data:
                winnable = matchup_data['strategic_targets'].get('winnable', [])
                if winnable:
                    target_categories = [w['category'] for w in winnable]
                    print(f"\n✓ Targeting winnable categories: {', '.join(target_categories)}")
                else:
                    print("\n⚠️  No winnable categories found in matchup data")
            else:
                print("\n⚠️  No matchup data available for targeted analysis")
        except Exception as e:
            print(f"\n⚠️  Could not load matchup data: {e}")
    elif choice == "3":
        cats_input = input("Enter categories (comma-separated, e.g., FG%,3PTM,BLK): ").strip()
        if cats_input:
            target_categories = [c.strip() for c in cats_input.split(',')]
            print(f"\n✓ Targeting: {', '.join(target_categories)}")
    
    # Run Phase 4A analysis
    if mode == "automatic":
        analyzer.analyze_with_api(target_categories=target_categories)