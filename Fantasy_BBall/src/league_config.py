"""
league_config.py
Stores all league settings, scoring categories, and strategy preferences
for AI-driven roster optimization.
"""

from dataclasses import dataclass
from typing import List, Dict
import json


@dataclass
class LeagueSettings:
    """Core league settings"""
    league_id: int = 39285
    league_name: str = "Warriors4life"
    team_id: int = 2
    team_name: str = "NoMoneyNoHoney"
    
    # Season info
    season: str = "2025-26"
    game_key: str = "466"
    
    # Timezone for week calculations (CRITICAL for Sunday night analysis)
    # Use IANA timezone names: "US/Pacific", "US/Eastern", "US/Central", "US/Mountain"
    # Or: "America/Los_Angeles", "America/New_York", "America/Chicago", "America/Denver"
    timezone: str = "US/Pacific"
    
    # League structure
    max_teams: int = 12
    scoring_type: str = "Head-to-Head - Categories"
    
    # Roster configuration
    roster_positions: List[str] = None
    total_roster_spots: int = 15
    starting_spots: int = 10
    bench_spots: int = 3
    il_spots: int = 2
    
    # Transaction rules
    max_acquisitions_season: int = 100
    max_acquisitions_week: int = 4
    max_trades_season: str = "No maximum"
    waiver_time: str = "2 days"
    waiver_type: str = "Continual rolling list"
    weekly_deadline: str = "Daily - Tomorrow"
    
    # Playoff info
    playoff_teams: int = 6
    playoff_weeks: str = "Week 21, 22, 23"
    playoff_end: str = "Sunday, Apr 5"
    
    # Draft info
    draft_type: str = "Live Standard Draft"
    draft_date: str = "Sun Oct 19 5:00pm PDT"
    
    def __post_init__(self):
        if self.roster_positions is None:
            self.roster_positions = [
                'PG', 'SG', 'G', 'SF', 'PF', 'F', 
                'C', 'C', 'Util', 'Util',
                'BN', 'BN', 'BN', 'IL', 'IL'
            ]


@dataclass
class ScoringCategories:
    """
    H2H Categories - Win each category against opponent each week.
    9 total categories (best record wins league).
    """
    categories: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = {
                'FG%': {
                    'name': 'Field Goal Percentage',
                    'stat_id': '5',
                    'type': 'percentage',
                    'higher_is_better': True,
                    'importance': 'high',
                    'strategy': 'Target high-efficiency players (big men, slashers). Avoid high-volume low-efficiency shooters.'
                },
                'FT%': {
                    'name': 'Free Throw Percentage',
                    'stat_id': '8',
                    'type': 'percentage',
                    'higher_is_better': True,
                    'importance': 'high',
                    'strategy': 'Target guards and wings. Avoid poor FT shooters (some centers). Can punt if building around bigs.'
                },
                '3PTM': {
                    'name': '3-Point Shots Made',
                    'stat_id': '10',
                    'type': 'counting',
                    'higher_is_better': True,
                    'importance': 'high',
                    'strategy': 'Target high-volume 3-point shooters. Guards and modern wings are key.'
                },
                'PTS': {
                    'name': 'Points Scored',
                    'stat_id': '12',
                    'type': 'counting',
                    'higher_is_better': True,
                    'importance': 'high',
                    'strategy': 'Target high-usage scorers. Correlates with minutes and role.'
                },
                'REB': {
                    'name': 'Total Rebounds',
                    'stat_id': '15',
                    'type': 'counting',
                    'higher_is_better': True,
                    'importance': 'medium',
                    'strategy': 'Target big men and versatile forwards. Double-double machines are valuable.'
                },
                'AST': {
                    'name': 'Assists',
                    'stat_id': '16',
                    'type': 'counting',
                    'higher_is_better': True,
                    'importance': 'medium',
                    'strategy': 'Target point guards and playmakers. High usage + low turnovers ideal.'
                },
                'ST': {
                    'name': 'Steals',
                    'stat_id': '17',
                    'type': 'counting',
                    'higher_is_better': True,
                    'importance': 'medium',
                    'strategy': 'Target perimeter defenders and gambling defenders. Hardest cat to find.'
                },
                'BLK': {
                    'name': 'Blocked Shots',
                    'stat_id': '18',
                    'type': 'counting',
                    'higher_is_better': True,
                    'importance': 'medium',
                    'strategy': 'Target rim protectors and tall forwards. Elite shot blockers are scarce.'
                },
                'TO': {
                    'name': 'Turnovers',
                    'stat_id': '19',
                    'type': 'counting',
                    'higher_is_better': False,  # LOWER is better!
                    'importance': 'low',
                    'strategy': 'MINIMIZE turnovers. Avoid high-usage ball-handlers if they turn it over. Low-usage players help.'
                }
            }
    
    def get_category_list(self) -> List[str]:
        """Return list of category abbreviations"""
        return list(self.categories.keys())
    
    def is_percentage_stat(self, cat: str) -> bool:
        """Check if category is percentage-based"""
        return self.categories[cat]['type'] == 'percentage'
    
    def is_higher_better(self, cat: str) -> bool:
        """Check if higher values are better for this category"""
        return self.categories[cat]['higher_is_better']


@dataclass
class StrategyPreferences:
    """Your personal strategy preferences and constraints"""
    
    # Player health preferences
    avoid_injured: bool = True
    injury_statuses_to_avoid: List[str] = None
    
    # Playing time preferences
    min_minutes_per_game: float = 20.0  # Prefer players with good PT
    prefer_starters: bool = True
    
    # Team preferences (optional)
    preferred_teams: List[str] = None  # e.g., ['GSW', 'LAL'] if you want
    avoid_teams: List[str] = None  # Teams with bad schedules
    
    # Category strategy
    punt_categories: List[str] = None  # Categories you're willing to lose (e.g., ['TO', 'FT%'])
    target_categories: List[str] = None  # Categories you want to dominate
    
    # Risk tolerance
    risk_tolerance: str = "medium"  # low, medium, high
    value_consistency: bool = True  # Prefer consistent over boom/bust
    
    # Roster construction
    balance_positions: bool = True  # Ensure all positions covered
    max_players_per_nba_team: int = 3  # Diversification
    
    def __post_init__(self):
        if self.injury_statuses_to_avoid is None:
            self.injury_statuses_to_avoid = [
                'INJ', 'O', 'Out', 'GTD', 'DTD', 'Suspension'
            ]
        
        # Default: don't punt any categories (try to win all)
        if self.punt_categories is None:
            self.punt_categories = []
        
        # Default: target all categories
        if self.target_categories is None:
            self.target_categories = [
                'FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO'
            ]


class LeagueConfig:
    """
    Master configuration object that combines all settings.
    This is what the AI will reference for recommendations.
    """
    
    def __init__(self):
        self.settings = LeagueSettings()
        self.scoring = ScoringCategories()
        self.strategy = StrategyPreferences()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for AI context"""
        return {
            'league_settings': {
                'league_id': self.settings.league_id,
                'league_name': self.settings.league_name,
                'team_id': self.settings.team_id,
                'team_name': self.settings.team_name,
                'season': self.settings.season,
                'scoring_type': self.settings.scoring_type,
                'max_teams': self.settings.max_teams,
                'roster_positions': self.settings.roster_positions,
                'max_acquisitions_week': self.settings.max_acquisitions_week,
                'weekly_deadline': self.settings.weekly_deadline
            },
            'scoring_categories': self.scoring.categories,
            'strategy': {
                'avoid_injured': self.strategy.avoid_injured,
                'min_minutes_per_game': self.strategy.min_minutes_per_game,
                'prefer_starters': self.strategy.prefer_starters,
                'punt_categories': self.strategy.punt_categories,
                'target_categories': self.strategy.target_categories,
                'risk_tolerance': self.strategy.risk_tolerance
            }
        }
    
    def to_ai_context(self) -> str:
        """
        Generate a formatted string for AI prompts.
        This tells the AI exactly what to optimize for.
        """
        context = f"""
LEAGUE CONFIGURATION:
League: {self.settings.league_name} (ID: {self.settings.league_id})
Team: {self.settings.team_name}
Format: {self.settings.scoring_type} - {len(self.scoring.categories)} categories
Season: {self.settings.season} NBA

ROSTER STRUCTURE:
- Total spots: {self.settings.total_roster_spots}
- Starting lineup: {self.settings.starting_spots} players
- Bench: {self.settings.bench_spots} spots
- IL spots: {self.settings.il_spots}
- Positions: {', '.join(self.settings.roster_positions[:10])}

SCORING CATEGORIES (Win each category weekly):
"""
        
        for cat, info in self.scoring.categories.items():
            direction = "↑ HIGHER better" if info['higher_is_better'] else "↓ LOWER better"
            context += f"  • {cat} ({info['name']}): {direction}\n"
            context += f"    Strategy: {info['strategy']}\n"
        
        context += f"""
ROSTER OPTIMIZATION STRATEGY:
- Avoid injured players: {self.strategy.avoid_injured}
- Minimum playing time: {self.strategy.min_minutes_per_game} MPG
- Prefer starters: {self.strategy.prefer_starters}
- Risk tolerance: {self.strategy.risk_tolerance}
- Target categories: {', '.join(self.strategy.target_categories)}
"""
        
        if self.strategy.punt_categories:
            context += f"- Punt categories (willing to lose): {', '.join(self.strategy.punt_categories)}\n"
        
        context += f"""
TRANSACTION LIMITS:
- Max adds per week: {self.settings.max_acquisitions_week}
- Max adds per season: {self.settings.max_acquisitions_season}
- Deadline: {self.settings.weekly_deadline}

GOAL: Optimize roster to win maximum categories each week and win the league.
"""
        
        return context
    
    def save_to_file(self, filename='data/league_config.json'):
        """Save configuration to JSON file"""
        import os
        
        # Create directory if it doesn't exist
        directory = os.path.dirname(filename)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ Created directory: {directory}")
        
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"✓ Saved league configuration to {filename}")
    
    @classmethod
    def load_from_file(cls, filename='data/league_config.json'):
        """Load configuration from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)
        
        config = cls()
        # You can add logic here to load from file if needed
        return config


if __name__ == "__main__":
    # Initialize and test configuration
    config = LeagueConfig()
    
    print("="*80)
    print("LEAGUE CONFIGURATION")
    print("="*80)
    print(config.to_ai_context())
    
    # Save to file
    config.save_to_file()
    
    print("\n" + "="*80)
    print("✓ Configuration ready for AI analysis!")
    print("="*80)