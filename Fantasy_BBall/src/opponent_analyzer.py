"""
opponent_analyzer.py
Analyzes opponent's roster and calculates winnable categories.
Uses Yahoo API to fetch real player stats (season averages as proxy for weekly projection).
"""

from typing import Dict, List, Optional
from datetime import datetime


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
        
    def analyze_matchup(self, my_roster: List[Dict], 
                       opponent_team_key: str,
                       days_lookback: int = 14) -> Dict:
        """
        Full matchup analysis with category projections.
        
        Args:
            my_roster: Your roster with player data
            opponent_team_key: Opponent's team key
            days_lookback: Not used (kept for compatibility)
            
        Returns:
            Dict with category analysis and recommendations
        """
        # Get opponent roster
        opponent_roster = self._fetch_opponent_roster(opponent_team_key)
        if not opponent_roster:
            return {'error': 'Could not fetch opponent roster'}
        
        # Get season stats for both rosters (proxy for weekly projection)
        my_stats = self._get_team_stats(my_roster)
        opp_stats = self._get_team_stats(opponent_roster)
        
        # Calculate gaps
        gaps = self._calculate_category_gaps(my_stats, opp_stats)
        
        # Classify categories
        classification = self._classify_categories(gaps)
        
        return {
            'my_projections': my_stats,
            'opponent_projections': opp_stats,
            'category_gaps': gaps,
            'classification': classification,
            'opponent_roster_size': len(opponent_roster)
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
    
    def _get_team_stats(self, roster: List[Dict]) -> Dict:
        """
        Aggregate team stats from roster.
        
        For percentages (FG%, FT%): Calculate weighted average
        For counting stats: Sum totals
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
            'TO': 0
        }
        
        for player in roster:
            stats = player.get('stats', {})
            
            # Collect percentage stats for averaging
            if stats.get('FG%', 0) > 0:
                team_stats['FG%'].append(stats['FG%'])
            if stats.get('FT%', 0) > 0:
                team_stats['FT%'].append(stats['FT%'])
            
            # Sum counting stats
            team_stats['3PTM'] += stats.get('3PTM', 0)
            team_stats['PTS'] += stats.get('PTS', 0)
            team_stats['REB'] += stats.get('REB', 0)
            team_stats['AST'] += stats.get('AST', 0)
            team_stats['ST'] += stats.get('ST', 0)
            team_stats['BLK'] += stats.get('BLK', 0)
            team_stats['TO'] += stats.get('TO', 0)
        
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
        lines = []
        
        lines.append("CATEGORY ANALYSIS:")
        
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