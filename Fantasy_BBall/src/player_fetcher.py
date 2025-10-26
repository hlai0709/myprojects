"""
player_fetcher.py
Fetches all available players (free agents) from your Yahoo Fantasy Basketball league.
"""

import json
import os
from datetime import datetime
from auth import YahooAuth
from league_config import LeagueConfig


class PlayerFetcher:
    def __init__(self, auth: YahooAuth):
        self.auth = auth
        self.fantasy_base_url = auth.fantasy_base_url
        self.session = auth.session
    
    def get_league_players(self, league_id, status='A', position=None, start=0, count=25):
        """
        Fetch players from the league.
        
        Args:
            league_id: Your league ID
            status: 'A' = available (free agents), 'T' = taken, 'K' = keepers, 'W' = waivers
            position: Filter by position (e.g., 'PG', 'C', None for all)
            start: Starting index for pagination
            count: Number of players to fetch (max 25 per request)
        
        Returns:
            List of player dictionaries
        """
        game_key = self.auth.get_game_key(league_id)
        
        # Build URL with filters
        url = f"{self.fantasy_base_url}league/{game_key}.l.{league_id}/players"
        
        # Add filters
        filters = [f"status={status}", f"start={start}", f"count={count}"]
        if position:
            filters.append(f"position={position}")
        
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
                    
                    # Extract and clean player data
                    cleaned_player = self._clean_player_data(player_info)
                    players.append(cleaned_player)
        
        return players
    
    def get_all_available_players(self, league_id, max_players=500):
        """
        Fetch all available free agents (paginated).
        
        Args:
            league_id: Your league ID
            max_players: Maximum number of players to fetch
        
        Returns:
            List of all available player dictionaries
        """
        all_players = []
        start = 0
        batch_size = 25  # Yahoo API max per request
        
        print(f"Fetching available players from league {league_id}...")
        
        while start < max_players:
            batch = self.get_league_players(
                league_id=league_id,
                status='A',  # Available only
                start=start,
                count=batch_size
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
        return all_players
    
    def _clean_player_data(self, player_info):
        """
        Extract and clean relevant player data.
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
        
        # Extract stats (if available)
        player_stats = {}
        if 'player_stats' in player_info:
            stats_data = player_info['player_stats']
            if 'stats' in stats_data:
                stats_list = stats_data['stats']
                if isinstance(stats_list, list):
                    for stat in stats_list:
                        if 'stat' in stat:
                            stat_data = stat['stat']
                            if isinstance(stat_data, dict):
                                stat_id = stat_data.get('stat_id')
                                value = stat_data.get('value')
                                if stat_id and value:
                                    player_stats[stat_id] = value
        
        return {
            'player_id': player_id,
            'player_key': player_key,
            'name': full_name,
            'team': editorial_team_abbr,
            'primary_position': display_position,
            'eligible_positions': eligible_positions,
            'injury_status': injury_status,
            'stats': player_stats,
            'raw_data': player_info  # Keep raw data for reference
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
        Print summary of players.
        """
        print(f"\n{'='*80}")
        print(f"Available Players Summary (showing first {limit})")
        print(f"{'='*80}\n")
        
        for i, player in enumerate(players[:limit], 1):
            name = player['name']
            team = player['team']
            pos = player['primary_position']
            injury = player.get('injury_status', '-')
            
            injury_str = f"[{injury}]" if injury else ""
            print(f"{i:3d}. {name:25s} {team:4s} {pos:10s} {injury_str}")
        
        if len(players) > limit:
            print(f"\n... and {len(players) - limit} more players")


if __name__ == "__main__":
    # Initialize
    auth = YahooAuth()
    fetcher = PlayerFetcher(auth)
    config = LeagueConfig()
    
    LEAGUE_ID = config.settings.league_id
    
    print(f"\n{'='*80}")
    print(f"Yahoo Fantasy Basketball - Available Players Fetcher")
    print(f"League: {config.settings.league_name}")
    print(f"Team: {config.settings.team_name}")
    print(f"{'='*80}\n")
    
    # Fetch all available players
    available_players = fetcher.get_all_available_players(
        league_id=LEAGUE_ID,
        max_players=500
    )
    
    # Filter based on strategy preferences
    if config.strategy.avoid_injured:
        healthy_players = fetcher.filter_healthy_players(available_players)
        injured_count = len(available_players) - len(healthy_players)
    else:
        healthy_players = available_players
        injured_count = 0
    
    print(f"\n{'='*80}")
    print(f"Player Breakdown:")
    print(f"  Total available: {len(available_players)}")
    print(f"  Healthy: {len(healthy_players)}")
    print(f"  Injured (filtered): {injured_count}")
    print(f"{'='*80}")
    
    # Print summary
    fetcher.print_player_summary(healthy_players, limit=30)
    
    # Save to file
    fetcher.save_players_to_file(available_players, 'data/available_players.json')
    fetcher.save_players_to_file(healthy_players, 'data/healthy_players.json')
    
    # Save config
    config.save_to_file()
    
    print(f"\n{'='*80}")
    print("✓ Phase 2A Complete!")
    print(f"  - Available players saved")
    print(f"  - League config saved")
    print(f"  - Ready for AI analysis")
    print(f"{'='*80}\n")