"""
player_fetcher.py - UPDATED WITH STATS
Fetches all available players (free agents) from Yahoo Fantasy Basketball league.
NOW INCLUDES: Yahoo stats (9 categories) + ESPN stats (minutes, GP) for top players
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from auth import YahooAuth
from league_config import LeagueConfig

# Import NBA stats fetcher (for minutes and games played)
try:
    from nba_stats_fetcher import NBAStatsFetcher, fetch_nba_stats
    NBA_STATS_AVAILABLE = True
except ImportError:
    NBA_STATS_AVAILABLE = False
    print("⚠️  NBA stats fetcher not available")


class PlayerFetcher:
    def __init__(self, auth: YahooAuth):
        self.auth = auth
        self.fantasy_base_url = auth.fantasy_base_url
        self.session = auth.session
        self.nba_stats_fetcher = NBAStatsFetcher() if NBA_STATS_AVAILABLE else None
    
    def get_league_players(self, league_id, status='A', position=None, start=0, count=25, 
                          include_stats=True):
        """
        Fetch players from the league WITH STATS.
        
        Args:
            league_id: Your league ID
            status: 'A' = available (free agents), 'T' = taken, 'K' = keepers, 'W' = waivers
            position: Filter by position (e.g., 'PG', 'C', None for all)
            start: Starting index for pagination
            count: Number of players to fetch (max 25 per request)
            include_stats: If True, fetch player stats (default: True)
        
        Returns:
            List of player dictionaries with stats
        """
        game_key = self.auth.get_game_key(league_id)
        
        # Build URL with filters
        url = f"{self.fantasy_base_url}league/{game_key}.l.{league_id}/players"
        
        # Add filters
        filters = [f"status={status}", f"start={start}", f"count={count}"]
        if position:
            filters.append(f"position={position}")
        
        # NOTE: We do NOT request ;out=stats from Yahoo
        # Yahoo stats are unreliable (league-specific, unclear format)
        # We get all stats from NBA.com instead (more accurate)
        
        url += ";" + ";".join(filters) + "?format=json"
        
        response = self.session.get(url, timeout=10)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch players: {response.status_code}")
        
        data = response.json()
        
        # Navigate to players data
        league_data = data['fantasy_content']['league']
        players_data = None
        
        for item in league_data:
            if isinstance(item, dict) and 'players' in item:
                players_data = item['players']
                break
        
        if not players_data:
            return []
        
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
                    
                    # Extract and clean player data (now with stats!)
                    cleaned_player = self._clean_player_data(player_info)
                    players.append(cleaned_player)
        
        return players
    
    def get_all_available_players(self, league_id, max_players=500, enrich_with_espn=True):
        """
        Fetch all available free agents (paginated) WITH STATS.
        
        Args:
            league_id: Your league ID
            max_players: Maximum number of players to fetch
            enrich_with_espn: If True, add ESPN stats (minutes, GP) to top players
        
        Returns:
            List of all available player dictionaries with stats
        """
        all_players = []
        start = 0
        batch_size = 25  # Yahoo API max per request
        
        print(f"Fetching available players from league {league_id} (WITH STATS)...")
        
        while start < max_players:
            batch = self.get_league_players(
                league_id=league_id,
                status='A',  # Available only
                start=start,
                count=batch_size,
                include_stats=True  # Get stats!
            )
            
            if not batch:
                break
            
            all_players.extend(batch)
            print(f"  Fetched {len(batch)} players (total: {len(all_players)})")
            
            start += batch_size
            
            # Break if we got fewer than batch_size (last page)
            if len(batch) < batch_size:
                break
        
        print(f"✓ Total available players: {len(all_players)}")
        
        # Enrich with NBA stats (minutes, games played)
        if enrich_with_espn and self.nba_stats_fetcher:
            all_players = self._enrich_with_nba_stats(all_players)
        
        return all_players
    
    def _enrich_with_nba_stats(self, players: List[Dict]) -> List[Dict]:
        """
        Add NBA.com stats to Yahoo players.
        
        NBA.com is the SINGLE SOURCE OF TRUTH for all player statistics.
        Yahoo stats are unreliable (league-specific, unclear if totals or averages).
        
        Args:
            players: List of Yahoo player dicts (names, teams, positions only)
        
        Returns:
            Same list with NBA.com stats added as 'season_stats'
        """
        if not self.nba_stats_fetcher:
            print("  ⚠️  NBA stats fetcher not available")
            return players
        
        print(f"\n[NBA Stats] Enriching {len(players)} players with NBA.com stats...")
        print(f"[NBA Stats] NBA.com is the SOURCE OF TRUTH for all player statistics")
        
        # Fetch NBA season leaders (single API call for 2025-26 season)
        nba_stats = self.nba_stats_fetcher.fetch_season_leaders(season="2025-26")
        
        if not nba_stats:
            print("  ⚠️  Could not fetch NBA stats")
            return players
        
        # Match Yahoo players with NBA stats
        matched = 0
        for player in players:
            name = player.get('name', '')
            team = player.get('team', '')
            
            nba_match = self.nba_stats_fetcher.match_player(name, team, nba_stats)
            
            if nba_match:
                # Use NBA.com as source of truth for ALL stats
                # get_stats_dict() converts NBA field names to Yahoo format
                player['season_stats'] = self.nba_stats_fetcher.get_stats_dict(nba_match)
                player['minutes'] = nba_match['minutes']
                player['games_played'] = nba_match['games_played']
                player['nba_matched'] = True
                matched += 1
            else:
                # No NBA match = no stats (will be filtered out by hard filters)
                player['season_stats'] = {}
                player['minutes'] = 0
                player['games_played'] = 0
                player['nba_matched'] = False
        
        print(f"  ✓ Matched {matched}/{len(players)} players with NBA.com ({100*matched//len(players)}%)")
        print(f"  ℹ️  Unmatched players have no stats (will be filtered: MIN < 20)")
        
        return players
    
    
    def _calculate_quality_score(self, player: Dict) -> float:
        """
        Calculate estimated player quality from Yahoo stats.
        Used for players not in ESPN top 200.
        
        Args:
            player: Player dict with season_stats
        
        Returns:
            Quality score (higher = better)
        """
        stats = player.get('season_stats', {})
        
        score = (
            stats.get('PTS', 0) * 1.0 +
            stats.get('REB', 0) * 1.2 +
            stats.get('AST', 0) * 1.5 +
            stats.get('3PTM', 0) * 1.5 +
            stats.get('ST', 0) * 3.0 +
            stats.get('BLK', 0) * 3.0 -
            stats.get('TO', 0) * 0.5  # Turnovers hurt
        )
        
        return max(0, score)  # Don't go negative
    
    def _clean_player_data(self, player_info):
        """
        Extract and clean relevant player data INCLUDING STATS.
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
        
        # Display position (primary position)
        display_position = player_info.get('display_position', 'N/A')
        
        # Extract injury status
        injury_status = None
        if 'status' in player_info:
            injury_status = player_info['status']
        
        # Extract editorial team (NBA team)
        editorial_team_abbr = player_info.get('editorial_team_abbr', 'FA')
        
        # Extract player ID and key
        player_id = player_info.get('player_id')
        player_key = player_info.get('player_key')
        
        # NOTE: We do NOT extract stats from Yahoo API here.
        # Stats will come from NBA.com API during enrichment.
        # This is more reliable - Yahoo returns league-specific stats that don't match reality.
        
        return {
            'player_id': player_id,
            'player_key': player_key,
            'name': full_name,
            'team': editorial_team_abbr,
            'primary_position': display_position,
            'eligible_positions': eligible_positions,
            'injury_status': injury_status,
            'season_stats': {},  # Empty - will be filled from NBA.com
            'raw_data': player_info
        }
    
    def filter_healthy_players(self, players):
        """
        Filter out injured players.
        
        Args:
            players: List of player dictionaries
        
        Returns:
            List of healthy players only
        """
        healthy = []
        for player in players:
            injury = player.get('injury_status')
            
            # Keep if no injury status or if status is empty
            if not injury or injury == '':
                healthy.append(player)
        
        return healthy
    
    def save_players_to_file(self, players, filename='available_players.json'):
        """
        Save players data to JSON file.
        Auto-creates directory if it doesn't exist.
        """
        # Create directory if it doesn't exist
        directory = os.path.dirname(filename)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ Created directory: {directory}")
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'count': len(players),
            'players': players
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"✓ Saved {len(players)} players to {filename}")
    
    def print_player_summary(self, players, limit=20):
        """
        Print summary of players with stats.
        """
        print(f"\n{'='*80}")
        print(f"Available Players Summary (showing first {limit})")
        print(f"{'='*80}\n")
        
        for i, player in enumerate(players[:limit], 1):
            name = player['name']
            team = player['team']
            pos = player['primary_position']
            injury = player.get('injury_status', '-')
            
            # Show stats
            stats = player.get('season_stats', {})
            pts = stats.get('PTS', 0)
            reb = stats.get('REB', 0)
            ast = stats.get('AST', 0)
            
            # Show ESPN data if available
            minutes = player.get('minutes')
            gp = player.get('games_played')
            
            stats_str = f"PTS: {pts:.1f}, REB: {reb:.1f}, AST: {ast:.1f}"
            if minutes:
                stats_str += f", MIN: {minutes:.1f}"
            if gp:
                stats_str += f", GP: {gp}"
            
            injury_str = f"[{injury}]" if injury and injury != '-' else ""
            print(f"{i:3d}. {name:25s} {team:4s} {pos:10s} {stats_str} {injury_str}")
        
        if len(players) > limit:
            print(f"\n... and {len(players) - limit} more players")


if __name__ == "__main__":
    # Test the updated player fetcher
    auth = YahooAuth()
    fetcher = PlayerFetcher(auth)
    config = LeagueConfig()
    
    LEAGUE_ID = config.settings.league_id
    
    print(f"\n{'='*80}")
    print(f"Yahoo Fantasy Basketball - Player Fetcher (WITH STATS)")
    print(f"{'='*80}\n")
    
    # Fetch just 10 players as a test
    print("Fetching 10 available players...")
    players = fetcher.get_all_available_players(LEAGUE_ID, max_players=10, enrich_with_espn=True)
    
    # Print summary
    fetcher.print_player_summary(players, limit=10)
    
    # Save to file
    fetcher.save_players_to_file(players, 'data/test_players_with_stats.json')