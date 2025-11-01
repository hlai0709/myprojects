"""
nba_stats_fetcher.py

Fetches player statistics from NBA.com Stats API to supplement Yahoo data.
Provides minutes per game, games played, and other stats not available from Yahoo.

Uses official NBA.com stats.nba.com endpoint.
"""

import requests
from typing import Dict, Optional
from datetime import datetime


class NBAStatsFetcher:
    """Fetches NBA player stats from NBA.com's official Stats API."""
    
    def __init__(self):
        self.base_url = "https://stats.nba.com/stats/leagueleaders"
        self.cache = {}
        self.cache_timestamp = None
        self.cache_ttl = 3600  # 1 hour
        
        # Updated headers (as of Sept 2025 - nba_api fix #571)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://stats.nba.com/',
            'Origin': 'https://stats.nba.com',
            'Sec-Ch-Ua': '"Chromium";v="140", "Google Chrome";v="140", "Not A Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive'
        }
    
    def fetch_season_leaders(self, season: str = "2025-26", limit: int = 500) -> Dict[str, Dict]:
        """
        Fetch NBA season leaders with detailed stats from NBA.com Stats API.
        
        Args:
            season: NBA season (e.g., "2025-26" for 2025-2026 season)
            limit: Not used (API returns all players), kept for compatibility
        
        Returns:
            Dict mapping "PlayerName|TEAM" -> {minutes, games_played, stats...}
        """
        # Check cache
        if self._is_cache_valid():
            print(f"[NBA Stats] Using cached stats ({len(self.cache)} players)")
            return self.cache
        
        print(f"[NBA Stats] Fetching season leaders from NBA.com Stats API...")
        print(f"[NBA Stats] Season: {season}")
        
        try:
            # API parameters for season leaders
            params = {
                'LeagueID': '00',                    # NBA
                'PerMode': 'PerGame',                # Per game averages
                'Scope': 'S',                        # Season scope
                'Season': season,                    # e.g., "2025-26"
                'SeasonType': 'Regular Season',      # Regular season only
                'StatCategory': 'PTS',               # Any category (returns all stats)
                'ActiveFlag': ''                     # Optional (empty = all players)
            }
            
            response = requests.get(
                self.base_url,
                headers=self.headers,
                params=params,
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"[NBA Stats] ⚠️  HTTP {response.status_code}")
                print(f"[NBA Stats] Response: {response.text[:200]}")
                return {}
            
            data = response.json()
            
            # Parse NBA Stats API format (headers + rowSet)
            players_dict = self._parse_response(data)
            
            # Cache the results
            self.cache = players_dict
            self.cache_timestamp = datetime.now()
            
            print(f"[NBA Stats] ✓ Fetched stats for {len(players_dict)} players")
            return players_dict
        
        except Exception as e:
            print(f"[NBA Stats] ⚠️  Error fetching stats: {e}")
            import traceback
            print(f"[NBA Stats] Traceback: {traceback.format_exc()}")
            return {}
    
    def _parse_response(self, data: Dict) -> Dict[str, Dict]:
        """
        Parse NBA Stats API response format.
        
        NBA.com returns data as:
        {
          "resultSet": {
            "headers": ["PLAYER_ID", "RANK", "PLAYER", "TEAM", "GP", "MIN", ...],
            "rowSet": [
              [203999, 1, "Nikola Jokic", "DEN", 8, 37.5, 9.1, ...],
              [...]
            ]
          }
        }
        
        Args:
            data: Raw JSON response from NBA Stats API
        
        Returns:
            Dict mapping "PlayerName|TEAM" -> player stats dict
        """
        players_dict = {}
        
        try:
            result_set = data.get('resultSet', {})
            headers = result_set.get('headers', [])
            rows = result_set.get('rowSet', [])
            
            if not headers or not rows:
                print(f"[NBA Stats] ⚠️  No data in response")
                return {}
            
            # Create column index mapping for fast lookup
            col_map = {header: idx for idx, header in enumerate(headers)}
            
            # Required columns (verify they exist)
            required = ['PLAYER', 'TEAM', 'GP', 'MIN']
            missing = [col for col in required if col not in col_map]
            if missing:
                print(f"[NBA Stats] ⚠️  Missing required columns: {missing}")
                print(f"[NBA Stats] Available columns: {headers}")
                return {}
            
            # Parse each player row
            for row in rows:
                try:
                    name = row[col_map['PLAYER']]
                    team = row[col_map['TEAM']]
                    
                    if not name or not team:
                        continue
                    
                    # Create unique key
                    key = f"{name}|{team}"
                    
                    # Extract all relevant stats
                    players_dict[key] = {
                        'name': name,
                        'team': team,
                        'player_id': self._safe_int(row[col_map.get('PLAYER_ID', 0)]),
                        'rank': self._safe_int(row[col_map.get('RANK', 0)]),
                        'games_played': self._safe_int(row[col_map['GP']]),
                        'minutes': self._safe_float(row[col_map['MIN']]),
                        
                        # Counting stats (for validation/reference)
                        'points': self._safe_float(row[col_map.get('PTS', 0)]),
                        'rebounds': self._safe_float(row[col_map.get('REB', 0)]),
                        'assists': self._safe_float(row[col_map.get('AST', 0)]),
                        'steals': self._safe_float(row[col_map.get('STL', 0)]),
                        'blocks': self._safe_float(row[col_map.get('BLK', 0)]),
                        'turnovers': self._safe_float(row[col_map.get('TOV', 0)]),
                        
                        # Shooting stats (for validation/reference)
                        'fg_pct': self._safe_float(row[col_map.get('FG_PCT', 0)]),
                        'ft_pct': self._safe_float(row[col_map.get('FT_PCT', 0)]),
                        'three_pm': self._safe_float(row[col_map.get('FG3M', 0)]),
                    }
                
                except (IndexError, KeyError) as e:
                    # Skip malformed rows
                    continue
            
            return players_dict
        
        except Exception as e:
            print(f"[NBA Stats] Error parsing response: {e}")
            return {}
    
    def get_stats_dict(self, nba_match: Dict) -> Dict:
        """
        Convert NBA.com stats to season_stats dict compatible with Yahoo format.
        
        NBA.com API returns per-game averages (PerGame mode), so no conversion needed.
        This method just maps NBA field names to Yahoo field names.
        
        Args:
            nba_match: Dict from match_player() containing NBA.com stats
        
        Returns:
            Dict with keys matching Yahoo format: PTS, REB, AST, ST, BLK, TO, 3PTM, FG%, FT%, MIN
            All values are per-game averages (already from API).
        
        Example:
            >>> nba_match = {'points': 24.5, 'rebounds': 8.2, 'blocks': 0.6, ...}
            >>> stats = fetcher.get_stats_dict(nba_match)
            >>> stats
            {'PTS': 24.5, 'REB': 8.2, 'BLK': 0.6, ...}
        """
        return {
            'PTS': round(nba_match.get('points', 0), 1),
            'REB': round(nba_match.get('rebounds', 0), 1),
            'AST': round(nba_match.get('assists', 0), 1),
            'ST': round(nba_match.get('steals', 0), 1),
            'BLK': round(nba_match.get('blocks', 0), 1),
            'TO': round(nba_match.get('turnovers', 0), 1),
            '3PTM': round(nba_match.get('three_pm', 0), 1),
            'FG%': round(nba_match.get('fg_pct', 0), 3),
            'FT%': round(nba_match.get('ft_pct', 0), 3),
            'MIN': round(nba_match.get('minutes', 0), 1)
        }
    
    def match_player(self, yahoo_name: str, yahoo_team: str, 
                     nba_stats: Optional[Dict] = None) -> Optional[Dict]:
        """
        Find NBA.com stats for a Yahoo player by name and team.
        
        Args:
            yahoo_name: Player name from Yahoo (e.g., "LeBron James")
            yahoo_team: Team abbreviation from Yahoo (e.g., "LAL")
            nba_stats: Pre-fetched NBA stats dict (optional)
        
        Returns:
            Dict with NBA stats or None if not found
        """
        result, _ = self.match_player_with_debug(yahoo_name, yahoo_team, nba_stats)
        return result
    
    def match_player_with_debug(self, yahoo_name: str, yahoo_team: str,
                                nba_stats: Optional[Dict] = None) -> tuple[Optional[Dict], Dict]:
        """
        Find NBA.com stats for a Yahoo player with detailed debug info.
        
        Args:
            yahoo_name: Player name from Yahoo (e.g., "LeBron James")
            yahoo_team: Team abbreviation from Yahoo (e.g., "LAL")
            nba_stats: Pre-fetched NBA stats dict (optional)
        
        Returns:
            Tuple of (match_result, debug_info)
            - match_result: Dict with NBA stats or None if not found
            - debug_info: Dict with debug details (reason, suggestions, etc.)
        """
        debug_info = {
            'yahoo_name': yahoo_name,
            'yahoo_team': yahoo_team,
            'reason': None,
            'suggestions': [],
            'closest_matches': []
        }
        
        if nba_stats is None:
            nba_stats = self.fetch_season_leaders()
        
        if not nba_stats:
            debug_info['reason'] = 'NO_NBA_DATA'
            return None, debug_info
        
        # Try exact match first
        key = f"{yahoo_name}|{yahoo_team}"
        if key in nba_stats:
            debug_info['reason'] = 'EXACT_MATCH'
            return nba_stats[key], debug_info
        
        # Try fuzzy match (case insensitive, handle name variations)
        yahoo_name_lower = yahoo_name.lower().strip()
        yahoo_team_lower = yahoo_team.lower().strip()
        
        # Track potential matches for debugging
        name_matches = []  # Same name, different team
        team_matches = []  # Same team, different name
        similar_names = []  # Similar names on same team
        
        for nba_key, nba_data in nba_stats.items():
            nba_name = nba_data['name'].lower().strip()
            nba_team = nba_data['team'].lower().strip()
            
            # Check if names match (case insensitive)
            if nba_name == yahoo_name_lower:
                if nba_team == yahoo_team_lower:
                    debug_info['reason'] = 'CASE_INSENSITIVE_MATCH'
                    return nba_data, debug_info
                else:
                    # Same name, different team - possible trade
                    name_matches.append({
                        'name': nba_data['name'],
                        'team': nba_data['team'],
                        'games_played': nba_data['games_played']
                    })
            
            # Check if on same team
            if nba_team == yahoo_team_lower:
                # Calculate name similarity
                similarity = self._calculate_name_similarity(yahoo_name_lower, nba_name)
                if similarity > 0.7:  # 70% similar
                    similar_names.append({
                        'name': nba_data['name'],
                        'team': nba_data['team'],
                        'similarity': similarity,
                        'games_played': nba_data['games_played']
                    })
                team_matches.append({
                    'name': nba_data['name'],
                    'team': nba_data['team']
                })
            
            # Handle common variations (e.g., "O.G. Anunoby" vs "OG Anunoby")
            if self._names_similar(yahoo_name_lower, nba_name) and nba_team == yahoo_team_lower:
                debug_info['reason'] = 'FUZZY_MATCH'
                return nba_data, debug_info
        
        # No match found - categorize the reason
        if name_matches:
            debug_info['reason'] = 'TEAM_MISMATCH'
            debug_info['suggestions'] = name_matches
        elif similar_names:
            debug_info['reason'] = 'NAME_MISMATCH'
            debug_info['closest_matches'] = sorted(similar_names, key=lambda x: x['similarity'], reverse=True)[:3]
        elif team_matches:
            debug_info['reason'] = 'NAME_MISMATCH_SAME_TEAM'
            debug_info['closest_matches'] = team_matches[:5]
        else:
            debug_info['reason'] = 'NOT_IN_NBA_DATA'
        
        return None, debug_info
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names (0.0 to 1.0).
        Uses simple character-based similarity.
        """
        # Remove common punctuation and normalize
        clean1 = name1.replace('.', '').replace('-', '').replace("'", '').lower()
        clean2 = name2.replace('.', '').replace('-', '').replace("'", '').lower()
        
        # If identical after cleaning
        if clean1 == clean2:
            return 1.0
        
        # Calculate Jaccard similarity on character trigrams
        def get_trigrams(s):
            s = ' ' + s + ' '  # Add padding
            return set(s[i:i+3] for i in range(len(s)-2))
        
        trigrams1 = get_trigrams(clean1)
        trigrams2 = get_trigrams(clean2)
        
        if not trigrams1 or not trigrams2:
            return 0.0
        
        intersection = len(trigrams1 & trigrams2)
        union = len(trigrams1 | trigrams2)
        
        return intersection / union if union > 0 else 0.0
    
    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar enough to be the same player."""
        # Remove periods and spaces for comparison
        clean1 = name1.replace('.', '').replace(' ', '').replace('-', '')
        clean2 = name2.replace('.', '').replace(' ', '').replace('-', '')
        
        # Exact match after cleaning
        if clean1 == clean2:
            return True
        
        # Handle nicknames/shortened names (e.g., "Bob" vs "Robert")
        # Split into parts and check if all parts of shorter name are in longer
        parts1 = set(name1.split())
        parts2 = set(name2.split())
        
        # If all parts of one name are in the other
        if parts1.issubset(parts2) or parts2.issubset(parts1):
            return True
        
        return False
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _safe_int(self, value) -> int:
        """Safely convert value to int."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if not self.cache or not self.cache_timestamp:
            return False
        
        age = (datetime.now() - self.cache_timestamp).total_seconds()
        return age < self.cache_ttl
    
    def clear_cache(self):
        """Clear cached NBA stats."""
        self.cache = {}
        self.cache_timestamp = None
        print("[NBA Stats] Cache cleared")


# Convenience functions for easy import
def fetch_nba_stats(season: str = "2025-26", limit: int = 500) -> Dict[str, Dict]:
    """Fetch NBA season leaders (convenience function)."""
    fetcher = NBAStatsFetcher()
    return fetcher.fetch_season_leaders(season, limit)


def enrich_player_with_nba_stats(player: Dict, nba_stats: Dict) -> Dict:
    """
    Add NBA.com stats (minutes, GP) to a Yahoo player dict.
    
    Args:
        player: Yahoo player dict with 'name' and 'team'
        nba_stats: Dict from fetch_nba_stats()
    
    Returns:
        Updated player dict with NBA stats added
    """
    name = player.get('name', '')
    team = player.get('team', '')
    
    fetcher = NBAStatsFetcher()
    nba_match = fetcher.match_player(name, team, nba_stats)
    
    if nba_match:
        player['minutes'] = nba_match['minutes']
        player['games_played'] = nba_match['games_played']
        player['nba_matched'] = True
    else:
        player['minutes'] = None
        player['games_played'] = None
        player['nba_matched'] = False
    
    return player


if __name__ == "__main__":
    # Quick test
    print("="*80)
    print(" Testing NBA Stats Fetcher")
    print("="*80)
    
    fetcher = NBAStatsFetcher()
    stats = fetcher.fetch_season_leaders(season="2025-26")
    
    print(f"\n✓ Fetched {len(stats)} players from NBA.com Stats API")
    
    if stats:
        # Show a few examples
        print("\nSample players (top 5 by rank):")
        sorted_players = sorted(
            stats.values(), 
            key=lambda x: x.get('rank', 999)
        )[:5]
        
        for i, player in enumerate(sorted_players, 1):
            print(f"{i}. {player['name']} ({player['team']})")
            print(f"   GP: {player['games_played']}, MIN: {player['minutes']:.1f}, "
                  f"PTS: {player['points']:.1f}")
    
    print("\n" + "="*80)
    print(" Test Complete")
    print("="*80)