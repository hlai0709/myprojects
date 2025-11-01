"""
roster_analyzer.py
Fetches and analyzes your current team roster.
"""

import json
import os
from datetime import datetime
from auth import YahooAuth
from league_config import LeagueConfig

# Import NBA stats fetcher (for minutes and games played)
try:
    from nba_stats_fetcher import NBAStatsFetcher
    NBA_STATS_AVAILABLE = True
except ImportError:
    NBA_STATS_AVAILABLE = False
    print("⚠️  NBA stats fetcher not available for roster")


class RosterAnalyzer:
    def __init__(self, auth: YahooAuth, config: LeagueConfig):
        self.auth = auth
        self.config = config
        self.fantasy_base_url = auth.fantasy_base_url
        self.session = auth.session
        self.nba_stats_fetcher = NBAStatsFetcher() if NBA_STATS_AVAILABLE else None
    
    def get_my_roster(self, league_id, team_id, date=None):
        """
        Fetch your current roster.
        
        Args:
            league_id: Your league ID
            team_id: Your team ID
            date: Date for roster (YYYY-MM-DD), defaults to today
        
        Returns:
            List of player dictionaries
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        team_key = self.auth.get_team_key(league_id, team_id)
        
        # NOTE: We do NOT request ;out=stats from Yahoo
        # Yahoo stats are unreliable (league-specific, unclear format)
        # We get all stats from NBA.com instead (more accurate)
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
                    
                    # Clean and extract player data
                    cleaned_player = self._clean_roster_player(player_info)
                    players.append(cleaned_player)
        
        # Enrich roster with NBA stats (minutes, games played)
        if players and self.nba_stats_fetcher:
            players = self._enrich_roster_with_nba_stats(players)
        
        return players
    
    def _clean_roster_player(self, player_info):
        """
        Extract and clean roster player data.
        """
        # Extract name
        name_data = player_info.get('name', {})
        full_name = name_data.get('full', 'Unknown') if isinstance(name_data, dict) else str(name_data)
        
        # Extract positions
        eligible_positions = []
        if 'eligible_positions' in player_info:
            pos_data = player_info['eligible_positions']
            if isinstance(pos_data, list):
                for item in pos_data:
                    if isinstance(item, dict) and 'position' in item:
                        eligible_positions.append(item['position'])
        
        display_position = player_info.get('display_position', 'N/A')
        
        # Extract selected position (roster slot)
        selected_position = 'N/A'
        if 'selected_position' in player_info:
            sel_pos = player_info['selected_position']
            if isinstance(sel_pos, dict):
                selected_position = sel_pos.get('position', 'N/A')
            elif isinstance(sel_pos, list):
                for item in sel_pos:
                    if isinstance(item, dict) and 'position' in item:
                        selected_position = item['position']
                        break
        
        # Extract injury status
        injury_status = player_info.get('status', None)
        
        # Extract NBA team
        editorial_team_abbr = player_info.get('editorial_team_abbr', 'FA')
        
        # Extract player ID and key
        player_id = player_info.get('player_id')
        player_key = player_info.get('player_key')
        
        # NOTE: We do NOT extract stats from Yahoo API here.
        # Stats will come from NBA.com API during enrichment.
        # Yahoo returns league-specific stats that don't match reality.
        
        return {
            'player_id': player_id,
            'player_key': player_key,
            'name': full_name,
            'team': editorial_team_abbr,
            'primary_position': display_position,
            'eligible_positions': eligible_positions,
            'selected_position': selected_position,
            'injury_status': injury_status,
            'season_stats': {},  # Empty - will be filled from NBA.com
            'raw_data': player_info
        }
    
    def analyze_team_categories(self, roster):
        """
        Analyze your team's performance by category.
        Returns strengths and weaknesses.
        """
        # This is a basic analysis - we'll enhance with actual stats later
        categories = self.config.scoring.get_category_list()
        
        analysis = {
            'total_players': len(roster),
            'active_players': len([p for p in roster if p['selected_position'] not in ['BN', 'IL']]),
            'bench_players': len([p for p in roster if p['selected_position'] == 'BN']),
            'injured_players': len([p for p in roster if p['injury_status']]),
            'position_breakdown': {},
            'team_breakdown': {},
            'category_notes': {}
        }
        
        # Count by position
        for player in roster:
            pos = player['primary_position']
            analysis['position_breakdown'][pos] = analysis['position_breakdown'].get(pos, 0) + 1
            
            team = player['team']
            analysis['team_breakdown'][team] = analysis['team_breakdown'].get(team, 0) + 1
        
        # Basic category analysis (we'll enhance this later with real stats)
        for cat in categories:
            analysis['category_notes'][cat] = {
                'name': self.config.scoring.categories[cat]['name'],
                'strategy': self.config.scoring.categories[cat]['strategy']
            }
        
        return analysis
    
    def print_roster_summary(self, roster):
        """
        Print a nice summary of your roster.
        """
        print(f"\n{'='*80}")
        print(f"YOUR CURRENT ROSTER")
        print(f"{'='*80}\n")
        
        # Group by roster position
        starters = [p for p in roster if p['selected_position'] not in ['BN', 'IL']]
        bench = [p for p in roster if p['selected_position'] == 'BN']
        injured = [p for p in roster if p['selected_position'] == 'IL']
        
        # Print starters
        print("STARTING LINEUP:")
        print("-" * 80)
        for player in starters:
            name = player['name']
            team = player['team']
            pos = player['primary_position']
            slot = player['selected_position']
            injury = f" [{player['injury_status']}]" if player['injury_status'] else ""
            
            print(f"  {slot:4s} | {name:25s} {team:4s} {pos:10s}{injury}")
        
        # Print bench
        if bench:
            print(f"\nBENCH:")
            print("-" * 80)
            for player in bench:
                name = player['name']
                team = player['team']
                pos = player['primary_position']
                injury = f" [{player['injury_status']}]" if player['injury_status'] else ""
                
                print(f"  BN   | {name:25s} {team:4s} {pos:10s}{injury}")
        
        # Print injured list
        if injured:
            print(f"\nINJURED LIST:")
            print("-" * 80)
            for player in injured:
                name = player['name']
                team = player['team']
                pos = player['primary_position']
                injury = f" [{player['injury_status']}]" if player['injury_status'] else ""
                
                print(f"  IL   | {name:25s} {team:4s} {pos:10s}{injury}")
        
        print(f"\n{'='*80}")
    
    def print_team_analysis(self, analysis):
        """
        Print team analysis summary.
        """
        print(f"\n{'='*80}")
        print(f"TEAM ANALYSIS")
        print(f"{'='*80}\n")
        
        print(f"Total Players: {analysis['total_players']}")
        print(f"  Active: {analysis['active_players']}")
        print(f"  Bench: {analysis['bench_players']}")
        print(f"  Injured: {analysis['injured_players']}")
        
        print(f"\nPosition Breakdown:")
        for pos, count in sorted(analysis['position_breakdown'].items()):
            print(f"  {pos:5s}: {count}")
        
        print(f"\nNBA Team Distribution:")
        for team, count in sorted(analysis['team_breakdown'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {team:4s}: {count} player(s)")
        
        print(f"\n{'='*80}")
    
    def _enrich_roster_with_nba_stats(self, players: list) -> list:
        """
        Add NBA.com stats to roster players.
        
        NBA.com is the SINGLE SOURCE OF TRUTH for all player statistics.
        Yahoo stats are unreliable (league-specific, unclear format).
        
        Args:
            players: List of roster player dicts (names, teams, positions only)
        
        Returns:
            Same list with NBA.com stats added as 'season_stats'
        """
        if not self.nba_stats_fetcher:
            return players
        
        print(f"\n[Roster] Enriching {len(players)} roster players with NBA.com stats...")
        print(f"[Roster] NBA.com is the SOURCE OF TRUTH for all player statistics")
        
        # Fetch NBA season leaders
        nba_stats = self.nba_stats_fetcher.fetch_season_leaders(season="2025-26")
        
        if not nba_stats:
            print("  ⚠️  Could not fetch NBA stats for roster")
            return players
        
        # Match and enrich each roster player
        matched = 0
        for player in players:
            name = player.get('name', '')
            team = player.get('team', '')
            
            nba_match = self.nba_stats_fetcher.match_player(name, team, nba_stats)
            
            if nba_match:
                # Use NBA.com as source of truth for ALL stats
                player['season_stats'] = self.nba_stats_fetcher.get_stats_dict(nba_match)
                player['minutes'] = nba_match['minutes']
                player['games_played'] = nba_match['games_played']
                player['nba_matched'] = True
                matched += 1
            else:
                # No NBA match = no stats
                player['season_stats'] = {}
                player['minutes'] = 0
                player['games_played'] = 0
                player['nba_matched'] = False
        
        print(f"  ✓ Matched {matched}/{len(players)} roster players with NBA.com")
        
        return players
    
    def save_roster_to_file(self, roster, analysis, filename='data/my_roster.json'):
        """
        Save roster and analysis to file.
        """
        # Create directory if needed
        directory = os.path.dirname(filename)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'team_name': self.config.settings.team_name,
            'league_name': self.config.settings.league_name,
            'roster_count': len(roster),
            'roster': roster,
            'analysis': analysis
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"✓ Saved roster to {filename}")


if __name__ == "__main__":
    # Initialize
    auth = YahooAuth()
    config = LeagueConfig()
    analyzer = RosterAnalyzer(auth, config)
    
    LEAGUE_ID = config.settings.league_id
    TEAM_ID = config.settings.team_id
    
    print(f"\n{'='*80}")
    print(f"Yahoo Fantasy Basketball - Roster Analyzer")
    print(f"League: {config.settings.league_name}")
    print(f"Team: {config.settings.team_name}")
    print(f"{'='*80}\n")
    
    print("Fetching your current roster...")
    
    # Get roster
    my_roster = analyzer.get_my_roster(LEAGUE_ID, TEAM_ID)
    
    print(f"✓ Fetched {len(my_roster)} players from your roster")
    
    # Analyze team
    team_analysis = analyzer.analyze_team_categories(my_roster)
    
    # Print summaries
    analyzer.print_roster_summary(my_roster)
    analyzer.print_team_analysis(team_analysis)
    
    # Save to file
    analyzer.save_roster_to_file(my_roster, team_analysis)
    
    print(f"\n{'='*80}")
    print("✓ Phase 2B Complete!")
    print(f"  - Your roster saved to data/my_roster.json")
    print(f"  - Ready for AI comparison!")
    print(f"{'='*80}\n")