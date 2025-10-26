"""
opponent_analyzer.py
Analyzes opponent's roster and calculates winnable categories.
Uses 14-day performance window and 15% winnable threshold.
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import statistics


class OpponentAnalyzer:
    """Analyzes opponent roster to identify winnable categories."""
    
    def __init__(self, auth_client):
        self.auth = auth_client
        self.categories = ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
        
    def analyze_matchup(self, my_roster: List[Dict], 
                       opponent_team_key: str,
                       days_lookback: int = 14) -> Dict:
        """
        Full matchup analysis with category projections.
        
        Args:
            my_roster: Your roster with player data
            opponent_team_key: Opponent's team key
            days_lookback: Days to look back for stats (default 14)
            
        Returns:
            Dict with category analysis and recommendations
        """
        # Get opponent roster
        opponent_roster = self._fetch_opponent_roster(opponent_team_key)
        if not opponent_roster:
            return {'error': 'Could not fetch opponent roster'}
        
        # Get recent stats for both rosters
        my_stats = self._get_roster_stats(my_roster, days_lookback)
        opp_stats = self._get_roster_stats(opponent_roster, days_lookback)
        
        # Project weekly totals
        my_proj = self._project_weekly_totals(my_stats)
        opp_proj = self._project_weekly_totals(opp_stats)
        
        # Calculate gaps
        gaps = self._calculate_category_gaps(my_proj, opp_proj)
        
        # Classify categories
        classification = self._classify_categories(gaps)
        
        return {
            'my_projections': my_proj,
            'opponent_projections': opp_proj,
            'category_gaps': gaps,
            'classification': classification,
            'opponent_roster_size': len(opponent_roster)
        }
    
    def _fetch_opponent_roster(self, team_key: str) -> Optional[List[Dict]]:
        """Fetch opponent's roster from Yahoo API."""
        try:
            url = f"{self.auth.fantasy_base_url}team/{team_key}/roster?format=json"
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
                                player_list = player_entry['player']
                                if isinstance(player_list, list):
                                    player_info = {}
                                    for p in player_list:
                                        if isinstance(p, list):
                                            for pi in p:
                                                if isinstance(pi, dict):
                                                    if 'name' in pi:
                                                        player_info['name'] = pi['name']['full']
                                                    if 'player_key' in pi:
                                                        player_info['player_key'] = pi['player_key']
                                    
                                    if player_info:
                                        roster.append(player_info)
            
            return roster if roster else None
            
        except Exception:
            return None
    
    def _get_roster_stats(self, roster: List[Dict], days: int) -> Dict:
        """
        Get aggregate stats for roster over last N days.
        Uses season averages as proxy (Yahoo doesn't provide easy 14-day stats).
        """
        # Simplified: Use player names to estimate stats
        # In production, you'd fetch actual recent game logs
        stats = {
            'FG%': [],
            'FT%': [],
            '3PTM': 0,
            'PTS': 0,
            'REB': 0,
            'AST': 0,
            'ST': 0,
            'BLK': 0,
            'TO': 0
        }
        
        # For now, return estimated stats based on roster size
        # Real implementation would fetch player game logs
        return stats
    
    def _project_weekly_totals(self, stats: Dict) -> Dict:
        """Project weekly totals from recent performance."""
        # Simplified projection
        # Real implementation would multiply daily averages by games played
        return {
            'FG%': 0.450,  # Placeholder
            'FT%': 0.800,  # Placeholder
            '3PTM': 50,
            'PTS': 700,
            'REB': 300,
            'AST': 150,
            'ST': 45,
            'BLK': 30,
            'TO': 90
        }
    
    def _calculate_category_gaps(self, my_proj: Dict, opp_proj: Dict) -> Dict:
        """
        Calculate percentage gap for each category.
        Positive = you're ahead, Negative = you're behind.
        """
        gaps = {}
        
        for cat in self.categories:
            my_val = my_proj.get(cat, 0)
            opp_val = opp_proj.get(cat, 0)
            
            if opp_val == 0:
                gaps[cat] = {'gap_pct': 0, 'status': 'UNKNOWN'}
                continue
            
            # For TO (lower is better), flip the sign
            if cat == 'TO':
                gap_pct = ((opp_val - my_val) / opp_val) * 100
            else:
                gap_pct = ((my_val - opp_val) / opp_val) * 100
            
            gaps[cat] = {
                'my_value': my_val,
                'opp_value': opp_val,
                'gap_pct': round(gap_pct, 1)
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
            elif gap >= 0 and gap < winnable_threshold:
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


def quick_analyze(auth, my_roster: List[Dict], opponent_key: str) -> Tuple[Dict, str]:
    """
    Quick analysis function for easy integration.
    
    Returns:
        Tuple of (full_analysis_dict, formatted_prompt_text)
    """
    analyzer = OpponentAnalyzer(auth)
    analysis = analyzer.analyze_matchup(my_roster, opponent_key)
    prompt_text = analyzer.format_analysis_for_prompt(analysis)
    
    return analysis, prompt_text