"""
matchup_analyzer.py
Analyzes your weekly H2H matchup using LIVE team stats.
"""

import json
import os
from datetime import datetime
from auth import YahooAuth
from league_config import LeagueConfig


class MatchupAnalyzer:
    def __init__(self, auth: YahooAuth, config: LeagueConfig):
        self.auth = auth
        self.config = config
        self.fantasy_base_url = auth.fantasy_base_url
        self.session = auth.session
    
    def get_current_week(self, league_id):
        """Get the current week number."""
        game_key = self.auth.get_game_key(league_id)
        url = f"{self.fantasy_base_url}league/{game_key}.l.{league_id}?format=json"
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch league info: {response.status_code}")
        
        data = response.json()
        league_info = data['fantasy_content']['league'][0]
        return int(league_info.get('current_week', 1))
    
    def get_league_scoreboard(self, league_id, week=None):
        """Get league scoreboard to find matchups."""
        if week is None:
            week = self.get_current_week(league_id)
        
        game_key = self.auth.get_game_key(league_id)
        url = f"{self.fantasy_base_url}league/{game_key}.l.{league_id}/scoreboard?format=json"
        
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch scoreboard: {response.status_code}")
        
        data = response.json()
        league_data = data['fantasy_content']['league']
        
        scoreboard = None
        for item in league_data:
            if isinstance(item, dict) and 'scoreboard' in item:
                scoreboard = item['scoreboard']
                break
        
        if not scoreboard or '0' not in scoreboard:
            return None
        
        matchups = []
        matchups_data = scoreboard['0'].get('matchups', {})
        
        for key in matchups_data:
            if key.isdigit():
                matchup_entry = matchups_data[key].get('matchup')
                if matchup_entry:
                    parsed = self._parse_matchup(matchup_entry, week)
                    if parsed:
                        matchups.append(parsed)
        
        return matchups
    
    def _parse_matchup(self, matchup_data, week):
        """Parse matchup structure."""
        matchup = {
            'week': week,
            'status': matchup_data.get('status'),
            'week_start': matchup_data.get('week_start'),
            'week_end': matchup_data.get('week_end'),
            'teams': []
        }
        
        if '0' in matchup_data and 'teams' in matchup_data['0']:
            teams_data = matchup_data['0']['teams']
            
            for key in teams_data:
                if key.isdigit():
                    team_entry = teams_data[key].get('team')
                    if team_entry:
                        team_info = self._parse_team(team_entry)
                        if team_info:
                            matchup['teams'].append(team_info)
        
        return matchup if matchup['teams'] else None
    
    def _parse_team(self, team_entry):
        """Parse team data."""
        team_info = {'team_id': None, 'team_key': None, 'name': None, 'managers': []}
        
        if isinstance(team_entry, list):
            for item in team_entry:
                if isinstance(item, list):
                    for subitem in item:
                        if isinstance(subitem, dict):
                            team_info.update({k: v for k, v in subitem.items() if k in team_info})
                elif isinstance(item, dict):
                    team_info.update({k: v for k, v in item.items() if k in team_info})
        
        return team_info if team_info['team_id'] else None
    
    def find_my_matchup(self, matchups, my_team_id):
        """Find your matchup."""
        my_team_id_str = str(my_team_id)
        
        for matchup in matchups:
            for team in matchup['teams']:
                if str(team.get('team_id')) == my_team_id_str:
                    return matchup
        return None
    
    def get_opponent_info(self, matchup, my_team_id):
        """Get opponent info."""
        my_team_id_str = str(my_team_id)
        
        for team in matchup['teams']:
            if str(team.get('team_id')) != my_team_id_str:
                managers = team.get('managers', [])
                manager_name = 'Unknown'
                
                if managers and isinstance(managers, list) and len(managers) > 0:
                    manager_data = managers[0]
                    if isinstance(manager_data, dict):
                        if 'manager' in manager_data:
                            manager_name = manager_data['manager'].get('nickname', 'Unknown')
                        elif 'nickname' in manager_data:
                            manager_name = manager_data['nickname']
                
                return {
                    'team_id': team.get('team_id'),
                    'team_key': team.get('team_key'),
                    'team_name': team.get('name', 'Unknown'),
                    'manager': manager_name
                }
        return None
    
    def get_team_stats_for_week(self, team_key, week):
        """Fetch LIVE team stats for the week."""
        url = f"{self.fantasy_base_url}team/{team_key}/stats;type=week;week={week}?format=json"
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        team_data = data['fantasy_content']['team']
        
        stats = {}
        for item in team_data:
            if isinstance(item, dict) and 'team_stats' in item:
                team_stats = item['team_stats']
                if 'stats' in team_stats:
                    stats_list = team_stats['stats']
                    if isinstance(stats_list, list):
                        for stat in stats_list:
                            if 'stat' in stat:
                                stat_data = stat['stat']
                                if isinstance(stat_data, dict):
                                    stat_id = stat_data.get('stat_id')
                                    value = stat_data.get('value')
                                    if stat_id and value:
                                        stats[stat_id] = value
        
        return stats
    
    def compare_teams_with_live_stats(self, my_stats, opponent_stats):
        """Compare using LIVE stats."""
        categories = self.config.scoring.categories
        comparison = {}
        
        wins = 0
        losses = 0
        ties = 0
        
        for cat_abbr, cat_info in categories.items():
            stat_id = cat_info['stat_id']
            
            my_value = my_stats.get(stat_id, '0')
            opp_value = opponent_stats.get(stat_id, '0')
            
            try:
                my_val_float = float(my_value)
                opp_val_float = float(opp_value)
            except:
                my_val_float = 0.0
                opp_val_float = 0.0
            
            higher_is_better = cat_info['higher_is_better']
            
            if my_val_float == opp_val_float:
                status = 'TIED'
                ties += 1
            elif higher_is_better:
                if my_val_float > opp_val_float:
                    status = 'WINNING'
                    wins += 1
                else:
                    status = 'LOSING'
                    losses += 1
            else:  # Lower is better (TO)
                if my_val_float < opp_val_float:
                    status = 'WINNING'
                    wins += 1
                else:
                    status = 'LOSING'
                    losses += 1
            
            comparison[cat_abbr] = {
                'name': cat_info['name'],
                'my_value': my_value,
                'opponent_value': opp_value,
                'status': status,
                'higher_is_better': higher_is_better,
                'importance': cat_info['importance']
            }
        
        return comparison, wins, losses, ties
    
    def identify_target_categories(self, comparison):
        """Identify target categories."""
        targets = {'winnable': [], 'must_hold': [], 'losing': [], 'tied': []}
        
        for cat, data in comparison.items():
            status = data['status']
            cat_info = {'category': cat, 'name': data['name']}
            
            if status == 'TIED':
                targets['tied'].append(cat_info)
                targets['winnable'].append(cat_info)
            elif status == 'WINNING':
                targets['must_hold'].append(cat_info)
            elif status == 'LOSING':
                targets['losing'].append(cat_info)
                targets['winnable'].append(cat_info)
        
        return targets
    
    def print_matchup_summary(self, matchup, opponent_info):
        """Print matchup overview."""
        print(f"\n{'='*80}")
        print(f"WEEK {matchup['week']} MATCHUP")
        print(f"{'='*80}\n")
        print(f"Your Team: {self.config.settings.team_name}")
        print(f"Opponent:  {opponent_info['team_name']} (Manager: {opponent_info['manager']})")
        print(f"Status:    {matchup['status']}")
        print(f"Period:    {matchup['week_start']} to {matchup['week_end']}")
        print(f"\n{'='*80}")
    
    def print_category_comparison(self, comparison, wins, losses, ties):
        """Print category comparison."""
        print(f"\n{'='*80}")
        print(f"CATEGORY BREAKDOWN (LIVE STATS)")
        print(f"{'='*80}\n")
        print(f"{'Category':<8} {'You':<12} {'Opponent':<12} {'Status':<12}")
        print("-" * 80)
        
        for cat, data in comparison.items():
            status = data['status']
            symbol = "✓" if status == 'WINNING' else "✗" if status == 'LOSING' else "="
            print(f"{cat:<8} {data['my_value']:<12} {data['opponent_value']:<12} {symbol} {status:<12}")
        
        print("-" * 80)
        print(f"\nCurrent Score: YOU {wins} - {losses} OPP (Ties: {ties})")
        print(f"Need to win: {max(0, 5 - wins)} more categories")
        print(f"\n{'='*80}")
    
    def print_strategic_recommendations(self, targets):
        """Print recommendations."""
        print(f"\n{'='*80}")
        print(f"STRATEGIC RECOMMENDATIONS")
        print(f"{'='*80}\n")
        
        if targets['tied']:
            print("⚖️  TIED CATEGORIES:")
            for item in targets['tied']:
                print(f"  • {item['category']} ({item['name']})")
            print()
        
        if targets['losing']:
            print("🎯 LOSING CATEGORIES:")
            for item in targets['losing']:
                print(f"  • {item['category']} ({item['name']})")
            print()
        
        if targets['must_hold']:
            print("✅ WINNING:")
            for item in targets['must_hold']:
                print(f"  • {item['category']} ({item['name']})")
            print()
    
    def save_matchup_analysis(self, matchup, opponent_info, comparison, targets, wins, losses, ties, filename='data/weekly_matchup.json'):
        """Save analysis."""
        os.makedirs('data', exist_ok=True)
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'week': matchup['week'],
            'my_team': self.config.settings.team_name,
            'opponent': opponent_info,
            'matchup_status': matchup['status'],
            'category_comparison': comparison,
            'strategic_targets': targets,
            'current_score': {'wins': wins, 'losses': losses, 'ties': ties}
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"✓ Saved to {filename}")


if __name__ == "__main__":
    auth = YahooAuth()
    config = LeagueConfig()
    analyzer = MatchupAnalyzer(auth, config)
    
    LEAGUE_ID = config.settings.league_id
    TEAM_ID = config.settings.team_id
    
    print(f"\n{'='*80}")
    print(f"Yahoo Fantasy Basketball - Weekly Matchup Analyzer")
    print(f"{'='*80}\n")
    
    current_week = analyzer.get_current_week(LEAGUE_ID)
    print(f"Current Week: {current_week}")
    
    print(f"\nFetching scoreboard...")
    all_matchups = analyzer.get_league_scoreboard(LEAGUE_ID, week=current_week)
    
    if not all_matchups:
        print("\n❌ No matchups found")
        exit(1)
    
    print(f"✓ Found {len(all_matchups)} matchups")
    
    my_matchup = analyzer.find_my_matchup(all_matchups, TEAM_ID)
    if not my_matchup:
        print("\n❌ Could not find your matchup")
        exit(1)
    
    opponent_info = analyzer.get_opponent_info(my_matchup, TEAM_ID)
    if not opponent_info:
        print("\n❌ Could not find opponent")
        exit(1)
    
    analyzer.print_matchup_summary(my_matchup, opponent_info)
    
    # Fetch LIVE stats for both teams
    my_team_key = auth.get_team_key(LEAGUE_ID, TEAM_ID)
    opponent_team_key = opponent_info['team_key']
    
    print("\nFetching LIVE team stats...")
    my_stats = analyzer.get_team_stats_for_week(my_team_key, current_week)
    opponent_stats = analyzer.get_team_stats_for_week(opponent_team_key, current_week)
    
    if not my_stats or not opponent_stats:
        print("\n⚠️  Could not fetch live stats")
        exit(1)
    
    # Compare with LIVE stats
    comparison, wins, losses, ties = analyzer.compare_teams_with_live_stats(my_stats, opponent_stats)
    
    analyzer.print_category_comparison(comparison, wins, losses, ties)
    
    targets = analyzer.identify_target_categories(comparison)
    analyzer.print_strategic_recommendations(targets)
    
    analyzer.save_matchup_analysis(my_matchup, opponent_info, comparison, targets, wins, losses, ties)
    
    print(f"\n{'='*80}")
    print("✓ Phase 2C Complete - Using LIVE stats!")
    print(f"{'='*80}\n")