"""
opponent_analyzer.py
Analyzes opponent's roster and calculates winnable categories.
Uses Yahoo API to fetch real player stats (season averages as proxy for weekly projection).
Production version with error handling, caching, and logging.
"""

from typing import Dict, List, Optional
from datetime import datetime

# Import production utilities
from util import cache, logger, retry_on_failure, safe_api_call, espn_rate_limiter


class OpponentAnalyzer:
    """Analyzes opponent roster to identify winnable categories."""
    
    def __init__(self, auth_client):
        self.auth = auth_client
        self.categories = ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
        
        # Yahoo stat IDs
        self.stat_ids = {
            'FG%': '5',
            'FT%': '8', 
            '3PTM': '10',
            'PTS': '12',
            'REB': '15',
            'AST': '16',
            'ST': '17',
            'BLK': '18',
            'TO': '19'
        }
        
        # NBA team abbreviations mapping (Yahoo uses different abbrevs sometimes)
        self.team_abbrev_map = {
            'PHO': 'PHX', 'SA': 'SAS', 'NO': 'NOP', 'NY': 'NYK', 'GS': 'GSW'
        }
        
    def analyze_matchup(self, my_roster: List[Dict], 
                       opponent_team_key: str,
                       days_lookback: int = 14,
                       week_start: Optional[str] = None,
                       week_end: Optional[str] = None) -> Dict:
        """
        Full matchup analysis with category projections.
        Production version with validation and error handling.
        
        Args:
            my_roster: Your roster with player data
            opponent_team_key: Opponent's team key
            days_lookback: Not used (kept for compatibility)
            week_start: Week start date for schedule-based projections (optional)
            week_end: Week end date for schedule-based projections (optional)
            
        Returns:
            Dict with category analysis and recommendations
        """
        logger.info(f"Starting matchup analysis vs {opponent_team_key}")
        
        # Validate inputs
        if not my_roster:
            logger.error("Empty roster provided")
            return {'error': 'Empty roster provided'}
        
        if not opponent_team_key:
            logger.error("No opponent team key provided")
            return {'error': 'No opponent team key provided'}
        
        # Get opponent roster
        opponent_roster = self._fetch_opponent_roster(opponent_team_key)
        if not opponent_roster:
            logger.error(f"Could not fetch opponent roster for {opponent_team_key}")
            return {'error': 'Could not fetch opponent roster'}
        
        logger.info(f"Fetched opponent roster: {len(opponent_roster)} players")
        
        # Get games per team if week dates provided
        games_per_team = None
        if week_start and week_end:
            print(f"    Fetching NBA schedule for {week_start} to {week_end}...")
            games_per_team = self._get_games_per_team(week_start, week_end)
            
            if games_per_team:
                avg_games = sum(games_per_team.values()) / len(games_per_team) if games_per_team else 0
                print(f"    ✓ Got schedule for {len(games_per_team)} teams (avg {avg_games:.1f} games)")
                logger.info(f"Schedule fetched: {len(games_per_team)} teams, avg {avg_games:.1f} games")
            else:
                print(f"    ⚠️  Using default 3.5 games/team estimate")
                logger.warning("No schedule data available, using defaults")
        
        # Get season stats for both rosters (proxy for weekly projection)
        try:
            my_stats = self._get_team_stats(my_roster, exclude_injured=True, 
                                            games_per_team=games_per_team)
            opp_stats = self._get_team_stats(opponent_roster, exclude_injured=True,
                                             games_per_team=games_per_team)
        except Exception as e:
            logger.error(f"Error calculating team stats: {e}")
            return {'error': f'Error calculating team stats: {e}'}
        
        # Calculate gaps
        gaps = self._calculate_category_gaps(my_stats, opp_stats)
        
        # Classify categories
        classification = self._classify_categories(gaps)
        
        logger.info("Matchup analysis complete")
        
        return {
            'my_projections': my_stats,
            'opponent_projections': opp_stats,
            'category_gaps': gaps,
            'classification': classification,
            'opponent_roster_size': len(opponent_roster),
            'injury_info': {
                'my_active': my_stats.get('active_players', 0),
                'my_injured': my_stats.get('injured_players', 0),
                'opp_active': opp_stats.get('active_players', 0),
                'opp_injured': opp_stats.get('injured_players', 0)
            },
            'schedule_based': games_per_team is not None
        }
    
    def _fetch_opponent_roster(self, team_key: str) -> Optional[List[Dict]]:
        """Fetch opponent's roster from Yahoo API."""
        try:
            url = f"{self.auth.fantasy_base_url}team/{team_key}/roster/players/stats?format=json"
            response = self.auth.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            roster = []
            
            # Parse roster from Yahoo API response
            team_data = data['fantasy_content']['team']
            for item in team_data:
                if isinstance(item, dict) and 'roster' in item:
                    players_data = item['roster']['0']['players']
                    
                    for key in players_data:
                        if key == 'count':
                            continue
                        if key.isdigit():
                            player_entry = players_data[key]
                            if 'player' in player_entry:
                                player = self._parse_player_data(player_entry['player'])
                                if player:
                                    roster.append(player)
            
            return roster if roster else None
            
        except Exception as e:
            print(f"Debug - Error fetching opponent roster: {e}")
            return None
    
    def _parse_player_data(self, player_list: List) -> Optional[Dict]:
        """Parse player data from Yahoo API format."""
        player_info = {}
        
        if not isinstance(player_list, list):
            return None
        
        for item in player_list:
            if isinstance(item, list):
                for sub_item in item:
                    if isinstance(sub_item, dict):
                        if 'player_key' in sub_item:
                            player_info['player_key'] = sub_item['player_key']
                        if 'name' in sub_item:
                            player_info['name'] = sub_item['name']['full']
                        if 'status' in sub_item:
                            player_info['injury_status'] = sub_item['status']
            elif isinstance(item, dict):
                if 'player_stats' in item:
                    stats_data = item['player_stats']
                    if 'stats' in stats_data:
                        player_info['stats'] = self._parse_stats(stats_data['stats'])
        
        return player_info if 'player_key' in player_info else None
    
    def _parse_stats(self, stats_list: List) -> Dict:
        """Parse stats from Yahoo format."""
        stats = {}
        
        for stat_item in stats_list:
            if 'stat' in stat_item:
                stat = stat_item['stat']
                stat_id = stat.get('stat_id')
                value = stat.get('value', '')
                
                # Map stat_id to category name
                for cat, sid in self.stat_ids.items():
                    if sid == stat_id:
                        # Convert value to float, handle empty strings
                        try:
                            if value == '' or value == '-':
                                stats[cat] = 0.0
                            else:
                                stats[cat] = float(value)
                        except:
                            stats[cat] = 0.0
                        break
        
        return stats
    
    @retry_on_failure(max_retries=2, delay_seconds=1.0)
    @safe_api_call
    def _get_games_per_team(self, week_start: str, week_end: str) -> Dict[str, int]:
        """
        Get number of games each NBA team plays during the week from ESPN API.
        Includes caching, rate limiting, and error handling.
        
        Args:
            week_start: Week start date (YYYY-MM-DD)
            week_end: Week end date (YYYY-MM-DD)
        
        Returns:
            Dict mapping team abbreviation to game count
        """
        # Check cache first (24 hour TTL)
        if cache:
            cache_key = f"nba_schedule_{week_start}_{week_end}"
            cached_data = cache.get(cache_key, max_age_seconds=86400)
            if cached_data:
                logger.info(f"Using cached schedule data for {week_start}")
                return cached_data
        
        try:
            import requests
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            logger.info(f"Fetching NBA schedule from ESPN API: {week_start} to {week_end}")
            
            # ESPN API endpoint (FREE, no key needed)
            games_count = defaultdict(int)
            
            start_date = datetime.strptime(week_start, '%Y-%m-%d')
            end_date = datetime.strptime(week_end, '%Y-%m-%d')
            
            current_date = start_date
            while current_date <= end_date:
                # Rate limit check
                espn_rate_limiter.wait_if_needed()
                
                date_str = current_date.strftime('%Y%m%d')
                url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
                
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get('events', [])
                    
                    for event in events:
                        competitions = event.get('competitions', [])
                        for comp in competitions:
                            competitors = comp.get('competitors', [])
                            
                            for team_data in competitors:
                                team_abbrev = team_data.get('team', {}).get('abbreviation')
                                if team_abbrev:
                                    games_count[team_abbrev] += 1
                else:
                    logger.warning(f"ESPN API returned {response.status_code} for {date_str}")
                
                current_date += timedelta(days=1)
            
            result = dict(games_count) if games_count else {}
            
            # Cache the result
            if cache and result:
                cache.set(cache_key, result)
                logger.info(f"Cached schedule data: {len(result)} teams")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch NBA schedule: {e}")
            # Fallback: return empty dict (will use default 3.5)
            print(f"    ⚠️  Could not fetch NBA schedule: {e}")
            return {}
    
    def _get_team_stats(self, roster: List[Dict], exclude_injured: bool = True, 
                       games_per_team: Optional[Dict[str, float]] = None) -> Dict:
        """
        Aggregate team stats from roster.
        
        Args:
            roster: List of players with stats
            exclude_injured: If True, exclude OUT/GTD/INJ players (default: True)
            games_per_team: Dict of team abbrev -> games this week (for weighting)
        
        For percentages (FG%, FT%): Calculate weighted average
        For counting stats: Sum totals weighted by games played
        """
        team_stats = {
            'FG%': [],  # Store individual values for weighted avg
            'FT%': [],  # Store individual values for weighted avg
            '3PTM': 0,
            'PTS': 0,
            'REB': 0,
            'AST': 0,
            'ST': 0,
            'BLK': 0,
            'TO': 0,
            'active_players': 0,
            'injured_players': 0
        }
        
        injured_statuses = ['OUT', 'O', 'INJ', 'GTD', 'DTD', 'Suspension', 'IL']
        
        for player in roster:
            # Check injury status
            injury_status = player.get('injury_status')
            
            if exclude_injured and injury_status and any(status in str(injury_status).upper() for status in injured_statuses):
                team_stats['injured_players'] += 1
                continue  # Skip this player
            
            team_stats['active_players'] += 1
            stats = player.get('stats', {})
            
            # Get game multiplier for this player's team
            player_team = player.get('team', 'UNK')
            # Normalize team abbreviation
            player_team = self.team_abbrev_map.get(player_team, player_team)
            
            game_multiplier = 1.0
            if games_per_team and player_team in games_per_team:
                # Divide by average games per week (3.5) to normalize
                game_multiplier = games_per_team[player_team] / 3.5
            
            # Collect percentage stats for averaging (not affected by games)
            if stats.get('FG%', 0) > 0:
                team_stats['FG%'].append(stats['FG%'])
            if stats.get('FT%', 0) > 0:
                team_stats['FT%'].append(stats['FT%'])
            
            # Sum counting stats (weighted by games if available)
            team_stats['3PTM'] += stats.get('3PTM', 0) * game_multiplier
            team_stats['PTS'] += stats.get('PTS', 0) * game_multiplier
            team_stats['REB'] += stats.get('REB', 0) * game_multiplier
            team_stats['AST'] += stats.get('AST', 0) * game_multiplier
            team_stats['ST'] += stats.get('ST', 0) * game_multiplier
            team_stats['BLK'] += stats.get('BLK', 0) * game_multiplier
            team_stats['TO'] += stats.get('TO', 0) * game_multiplier
        
        # Calculate average percentages
        if team_stats['FG%']:
            team_stats['FG%'] = sum(team_stats['FG%']) / len(team_stats['FG%'])
        else:
            team_stats['FG%'] = 0.0
        
        if team_stats['FT%']:
            team_stats['FT%'] = sum(team_stats['FT%']) / len(team_stats['FT%'])
        else:
            team_stats['FT%'] = 0.0
        
        return team_stats
    
    def _calculate_category_gaps(self, my_stats: Dict, opp_stats: Dict) -> Dict:
        """
        Calculate percentage gap for each category.
        Positive = you're ahead, Negative = you're behind.
        """
        gaps = {}
        
        for cat in self.categories:
            my_val = my_stats.get(cat, 0)
            opp_val = opp_stats.get(cat, 0)
            
            if opp_val == 0:
                # If opponent has no value, consider it a tie
                gaps[cat] = {
                    'my_value': my_val,
                    'opp_value': opp_val,
                    'gap_pct': 0.0,
                    'status': 'UNKNOWN'
                }
                continue
            
            # For TO (lower is better), flip the sign
            if cat == 'TO':
                gap_pct = ((opp_val - my_val) / opp_val) * 100
            else:
                gap_pct = ((my_val - opp_val) / opp_val) * 100
            
            # Determine status
            if gap_pct > 15:
                status = 'DOMINATING'
            elif gap_pct > 0:
                status = 'WINNING'
            elif gap_pct > -15:
                status = 'COMPETITIVE'
            else:
                status = 'LOSING'
            
            gaps[cat] = {
                'my_value': round(my_val, 2),
                'opp_value': round(opp_val, 2),
                'gap_pct': round(gap_pct, 1),
                'status': status
            }
        
        return gaps
    
    def _classify_categories(self, gaps: Dict, 
                            dominant_threshold: float = 15.0,
                            winnable_threshold: float = 15.0) -> Dict:
        """
        Classify categories into strategic buckets.
        
        Args:
            dominant_threshold: % ahead to be "dominating" (default 15%)
            winnable_threshold: % range to be "winnable" (default ±15%)
        """
        classification = {
            'dominating': [],   # You're way ahead - protect these
            'winnable': [],     # Close matchup - target these
            'competitive': [],  # Could go either way - monitor
            'losing': []        # Way behind - punt these
        }
        
        for cat, data in gaps.items():
            gap = data.get('gap_pct', 0)
            
            if gap >= dominant_threshold:
                classification['dominating'].append({
                    'category': cat,
                    'gap': gap,
                    'strategy': 'PROTECT'
                })
            elif gap >= 0 and gap < dominant_threshold:
                classification['winnable'].append({
                    'category': cat,
                    'gap': gap,
                    'strategy': 'TARGET'
                })
            elif gap < 0 and gap > -winnable_threshold:
                classification['competitive'].append({
                    'category': cat,
                    'gap': gap,
                    'strategy': 'IMPROVE'
                })
            else:  # gap <= -winnable_threshold
                classification['losing'].append({
                    'category': cat,
                    'gap': gap,
                    'strategy': 'PUNT'
                })
        
        return classification
    
    def format_analysis_for_prompt(self, analysis: Dict) -> str:
        """
        Format analysis into compact prompt text.
        Designed to be token-efficient.
        """
        if 'error' in analysis:
            return f"⚠️ Opponent analysis unavailable: {analysis['error']}"
        
        classification = analysis['classification']
        injury_info = analysis.get('injury_info', {})
        lines = []
        
        lines.append("CATEGORY ANALYSIS:")
        
        # Add injury disclaimer if applicable
        if injury_info:
            my_injured = injury_info.get('my_injured', 0)
            opp_injured = injury_info.get('opp_injured', 0)
            if my_injured > 0 or opp_injured > 0:
                lines.append(f"(Excluding injured: You={my_injured}, Opp={opp_injured})")
        
        if classification['dominating']:
            cats = [f"{c['category']} (+{c['gap']:.0f}%)" for c in classification['dominating']]
            lines.append(f"DOMINATING: {', '.join(cats)} - Protect these")
        
        if classification['winnable']:
            cats = [f"{c['category']} ({c['gap']:+.0f}%)" for c in classification['winnable']]
            lines.append(f"WINNABLE: {', '.join(cats)} - Target these ⭐")
        
        if classification['competitive']:
            cats = [f"{c['category']} ({c['gap']:+.0f}%)" for c in classification['competitive']]
            lines.append(f"COMPETITIVE: {', '.join(cats)} - Improve these")
        
        if classification['losing']:
            cats = [f"{c['category']} ({c['gap']:+.0f}%)" for c in classification['losing']]
            lines.append(f"LOSING: {', '.join(cats)} - Punt these")
        
        return '\n'.join(lines)
