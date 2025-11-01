"""
player_evaluator.py

Advanced player evaluation system for fantasy basketball.
Implements quality-first scoring with smart games bonus and position adjustments.

Based on user criteria:
- Min 20 MPG to be rosterable
- Quality score from per-36 stats
- Games bonus only for good players
- Position bonus only for specialists
"""

from typing import Dict, List, Optional


class PlayerEvaluator:
    """Evaluates fantasy basketball players using multi-factor scoring."""
    
    def __init__(self):
        # Quality tiers (based on per-36 scoring)
        self.TRASH_THRESHOLD = 30      # Below this = no games bonus
        self.BORDERLINE_THRESHOLD = 45 # Between 30-45 = small games bonus
        self.GOOD_THRESHOLD = 45       # Above 45 = full games bonus
        
        # Position bonus thresholds
        self.MIN_QUALITY_FOR_POSITION_BONUS = 35
        
        # Category weights for quality score
        self.WEIGHTS = {
            'PTS': 1.0,   # Points (baseline)
            'REB': 1.2,   # Rebounds (valuable)
            'AST': 1.5,   # Assists (high value)
            'ST': 3.0,    # Steals (scarce!)
            'BLK': 3.0,   # Blocks (scarce!)
            '3PTM': 1.5,  # 3-pointers (valuable)
            'TO': -0.5    # Turnovers (negative)
        }
        
        # Percentage bonuses
        self.FG_ELITE = 0.50   # Elite FG%
        self.FG_GOOD = 0.45    # Good FG%
        self.FT_ELITE = 0.85   # Elite FT%
        self.FT_GOOD = 0.80    # Good FT%
    
    def evaluate_player(self, player: Dict) -> Dict:
        """
        Evaluate a player and add scoring data.
        
        Args:
            player: Player dict with stats
        
        Returns:
            Same player dict with added fields:
                - 'quality_score': Base quality (0-100)
                - 'final_score': After multipliers
                - 'passes_filter': Boolean
                - 'score_breakdown': Dict with details
        """
        # Phase 1: Hard filters
        passes = self.passes_hard_filters(player)
        
        if not passes:
            player['passes_filter'] = False
            player['quality_score'] = 0
            player['final_score'] = 0
            player['score_breakdown'] = {'reason': 'Failed hard filters'}
            return player
        
        # Phase 2: Quality score
        quality = self.calculate_quality_score(player)
        
        # Phase 3: Games multiplier
        games_mult = self.calculate_games_multiplier(player, quality)
        
        # Phase 4: Position bonus
        position_mult = self.calculate_position_bonus(player, quality)
        
        # Final score
        final = quality * games_mult * position_mult
        
        # Add to player dict
        player['passes_filter'] = True
        player['quality_score'] = round(quality, 2)
        player['final_score'] = round(final, 2)
        player['score_breakdown'] = {
            'quality': round(quality, 2),
            'games_multiplier': round(games_mult, 2),
            'position_multiplier': round(position_mult, 2),
            'games_remaining': player.get('games_remaining', 0)
        }
        
        return player
    
    def passes_hard_filters(self, player: Dict) -> bool:
        """
        Check if player passes hard filters.
        
        Filters:
        1. Must play 20+ minutes per game
        2. Must score 8+ points per game (slightly below 10 to catch specialists)
        3. Must be strong in at least 2 categories
        
        Args:
            player: Player dict with stats
        
        Returns:
            True if passes all filters
        """
        minutes = player.get('minutes')
        stats = player.get('season_stats', {})
        
        # Filter 1: Minutes threshold
        if not minutes or minutes < 20:
            return False
        
        # Filter 2: Minimum production
        pts = stats.get('PTS', 0)
        if pts < 8:
            return False
        
        # Filter 3: Must be strong in at least 2 categories
        strong_cats = 0
        if pts >= 10: strong_cats += 1
        if stats.get('REB', 0) >= 6: strong_cats += 1
        if stats.get('AST', 0) >= 4: strong_cats += 1
        if stats.get('ST', 0) >= 1: strong_cats += 1
        if stats.get('BLK', 0) >= 1: strong_cats += 1
        if stats.get('3PTM', 0) >= 1.5: strong_cats += 1
        
        if strong_cats < 2:
            return False
        
        return True
    
    def calculate_quality_score(self, player: Dict) -> float:
        """
        Calculate player's fantasy quality score.
        
        Uses per-36 minute normalization to compare players fairly.
        Weights categories by scarcity and value.
        
        Args:
            player: Player dict with stats
        
        Returns:
            Quality score (0-100+ range, higher = better)
        """
        stats = player.get('season_stats', {})
        minutes = player.get('minutes', 36)
        
        if minutes <= 0:
            return 0
        
        # Calculate per-36 stats
        scale = 36.0 / minutes
        
        pts_36 = stats.get('PTS', 0) * scale
        reb_36 = stats.get('REB', 0) * scale
        ast_36 = stats.get('AST', 0) * scale
        stl_36 = stats.get('ST', 0) * scale
        blk_36 = stats.get('BLK', 0) * scale
        tpm_36 = stats.get('3PTM', 0) * scale
        to_36 = stats.get('TO', 0) * scale
        
        # Weighted scoring
        score = (
            pts_36 * self.WEIGHTS['PTS'] +
            reb_36 * self.WEIGHTS['REB'] +
            ast_36 * self.WEIGHTS['AST'] +
            stl_36 * self.WEIGHTS['ST'] +
            blk_36 * self.WEIGHTS['BLK'] +
            tpm_36 * self.WEIGHTS['3PTM'] +
            to_36 * self.WEIGHTS['TO']  # Negative weight
        )
        
        # Percentage bonuses
        fg_pct = stats.get('FG%', 0)
        ft_pct = stats.get('FT%', 0)
        
        if fg_pct >= self.FG_ELITE:
            score += 5
        elif fg_pct >= self.FG_GOOD:
            score += 2
        
        if ft_pct >= self.FT_ELITE:
            score += 3
        elif ft_pct >= self.FT_GOOD:
            score += 1
        
        return max(0, score)
    
    def calculate_games_multiplier(self, player: Dict, quality_score: float) -> float:
        """
        Calculate games remaining multiplier.
        
        SMART SCALING: Only good players get games bonus.
        - Trash (<30): No bonus (more games of bad play doesn't help)
        - Borderline (30-45): Small bonus (5-10%)
        - Good (45+): Full bonus (15-30%)
        
        Args:
            player: Player dict
            quality_score: Player's quality score
        
        Returns:
            Multiplier (1.0 - 1.30)
        """
        games = player.get('games_remaining', 0)
        
        # Trash tier: No games bonus
        if quality_score < self.TRASH_THRESHOLD:
            return 1.0
        
        # Borderline tier: Small games bonus
        elif quality_score < self.BORDERLINE_THRESHOLD:
            if games <= 2:
                return 1.0
            elif games == 3:
                return 1.05
            else:  # 4+ games
                return 1.10
        
        # Good/Elite tier: Full games bonus
        else:
            if games <= 2:
                return 1.0
            elif games == 3:
                return 1.15
            else:  # 4+ games
                return min(1.30, 1.0 + (games - 2) * 0.15)
    
    def calculate_position_bonus(self, player: Dict, quality_score: float) -> float:
        """
        Calculate position scarcity bonus.
        
        ONLY applies if:
        1. Player quality is above borderline threshold (35+)
        2. Player is actually good at position-relevant stats
        
        Args:
            player: Player dict
            quality_score: Player's quality score
        
        Returns:
            Multiplier (1.0 - 1.15)
        """
        # Only apply to good players
        if quality_score < self.MIN_QUALITY_FOR_POSITION_BONUS:
            return 1.0
        
        position = player.get('primary_position', '')
        stats = player.get('season_stats', {})
        
        # Centers: Need rebounds or blocks
        if position == 'C':
            reb = stats.get('REB', 0)
            blk = stats.get('BLK', 0)
            
            if reb >= 8 or blk >= 1.0:
                return 1.15  # Full bonus for good centers
            else:
                return 1.05  # Small bonus for weak centers
        
        # Point Guards: Need assists
        elif position == 'PG':
            ast = stats.get('AST', 0)
            
            if ast >= 6:
                return 1.15  # Full bonus for good PGs
            else:
                return 1.05  # Small bonus for weak PGs
        
        # Other positions: No bonus
        return 1.0
    
    def filter_and_rank(self, players: List[Dict], limit: int = 25) -> List[Dict]:
        """
        Filter and rank players by final score.
        
        Args:
            players: List of players to evaluate
            limit: Number of top players to return
        
        Returns:
            List of top players sorted by final_score
        """
        # Evaluate all players
        evaluated = []
        for player in players:
            evaluated_player = self.evaluate_player(player)
            if evaluated_player['passes_filter']:
                evaluated.append(evaluated_player)
        
        # Sort by final score (highest first)
        evaluated.sort(key=lambda p: p['final_score'], reverse=True)
        
        # Return top N
        return evaluated[:limit]
    
    def get_tier_name(self, quality_score: float) -> str:
        """Get tier name for a quality score."""
        if quality_score < self.TRASH_THRESHOLD:
            return "Waiver Trash"
        elif quality_score < self.BORDERLINE_THRESHOLD:
            return "Borderline"
        elif quality_score < 60:
            return "Good"
        else:
            return "Elite"


# Convenience function for easy import
def evaluate_players(players: List[Dict], limit: int = 25) -> List[Dict]:
    """
    Evaluate and filter players (convenience function).
    
    Args:
        players: List of player dicts
        limit: Number of top players to return
    
    Returns:
        Top players sorted by score
    """
    evaluator = PlayerEvaluator()
    return evaluator.filter_and_rank(players, limit)


if __name__ == "__main__":
    # Test with sample players
    print("Testing PlayerEvaluator...")
    
    # Sample data
    curry = {
        'name': 'Stephen Curry',
        'team': 'GSW',
        'primary_position': 'PG',
        'minutes': 35,
        'games_remaining': 4,
        'season_stats': {
            'PTS': 28.0, 'REB': 5.0, 'AST': 6.0, 'ST': 1.2, 'BLK': 0.3,
            '3PTM': 4.5, 'TO': 2.8, 'FG%': 0.465, 'FT%': 0.920
        }
    }
    
    naz = {
        'name': 'Naz Reid',
        'team': 'MIN',
        'primary_position': 'C',
        'minutes': 25,
        'games_remaining': 3,
        'season_stats': {
            'PTS': 12.0, 'REB': 5.0, 'AST': 1.0, 'ST': 0.5, 'BLK': 0.8,
            '3PTM': 1.5, 'TO': 1.2, 'FG%': 0.520, 'FT%': 0.800
        }
    }
    
    trash = {
        'name': 'Terry Rozier',
        'team': 'MIA',
        'primary_position': 'SG',
        'minutes': 18,
        'games_remaining': 4,
        'season_stats': {
            'PTS': 8.0, 'REB': 2.0, 'AST': 3.0, 'ST': 0.6, 'BLK': 0.2,
            '3PTM': 1.0, 'TO': 1.5, 'FG%': 0.380, 'FT%': 0.750
        }
    }
    
    evaluator = PlayerEvaluator()
    
    players = [curry, naz, trash]
    for p in players:
        result = evaluator.evaluate_player(p)
        print(f"\n{result['name']}:")
        print(f"  Passes filter: {result['passes_filter']}")
        if result['passes_filter']:
            print(f"  Quality: {result['quality_score']}")
            print(f"  Final: {result['final_score']}")
            print(f"  Tier: {evaluator.get_tier_name(result['quality_score'])}")
            print(f"  Breakdown: {result['score_breakdown']}")