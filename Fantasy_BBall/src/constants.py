"""
constants.py
Configuration constants for Fantasy Basketball AI Analyzer

Centralizes magic numbers and configuration values for maintainability.
"""

# Cache TTL (Time To Live) in seconds
CACHE_TTL_AVAILABLE_PLAYERS = 1800  # 30 minutes
CACHE_TTL_NBA_SCHEDULE = 86400      # 24 hours (1 day)
CACHE_TTL_ROSTER = 300              # 5 minutes
CACHE_TTL_MATCHUP = 600             # 10 minutes

# Player filtering
DEFAULT_PLAYER_LIMIT = 25           # Number of top players to show
MAX_AVAILABLE_PLAYERS = 500         # Maximum players to fetch from API

# Week detection
SUNDAY_CUTOFF_HOUR = 22             # Hour (0-23) to switch to next week on Sundays

# Roster moves
DEFAULT_MAX_MOVES_PER_WEEK = 4      # Common league setting

# Player scoring thresholds (for _filter_top_available_players)
SCORING_GAMES_REMAINING_MAX = 10    # Max points for games remaining
SCORING_TARGET_CATS_MAX = 15        # Max points for target category strength
SCORING_PRODUCTION_MAX = 10         # Max points for overall production
SCORING_POSITION_MAX = 5            # Max points for position scarcity

# Games per week normalization
AVERAGE_GAMES_PER_WEEK = 3.5        # Used to normalize schedule data

# Season configuration
SEASON_START_DATE = (2024, 10, 21)  # Year, Month, Day - Week 1 start
DAYS_PER_WEEK = 7                   # Fantasy weeks run Monday-Sunday

# Category thresholds for "excellent" and "good" performance
THRESHOLDS = {
    'FG%': {'excellent': 0.50, 'good': 0.45},
    'FT%': {'excellent': 0.85, 'good': 0.80},
    '3PTM': {'excellent': 2.5, 'good': 2.0},
    'PTS': {'excellent': 20, 'good': 15},
    'REB': {'excellent': 10, 'good': 7},
    'AST': {'excellent': 7, 'good': 5},
    'ST': {'excellent': 1.5, 'good': 1.0},
    'BLK': {'excellent': 1.5, 'good': 1.0},
    'TO': {'excellent': 1.5, 'good': 2.0},  # Lower is better for turnovers
}

# Production scoring thresholds (for overall player value)
PRODUCTION_THRESHOLDS = {
    'PTS': 12,
    'REB': 6,
    'AST': 4,
    '3PTM': 1.5,
    'ST': 0.8,
    'BLK': 0.8,
    'FG%': 0.45,
    'FT%': 0.75,
}

# Position scarcity scoring
POSITION_SCARCITY = {
    'C': 3,   # Centers are most scarce
    'PG': 3,  # Point guards are also scarce
    'PF': 1,  # Power forwards get minor bonus
    'SG': 1,  # Shooting guards get minor bonus
    'SF': 0,  # Small forwards - default (no bonus)
}

# API rate limiting
YAHOO_API_RATE_LIMIT = 60           # Max calls per minute
ESPN_API_RATE_LIMIT = 100           # Max calls per minute

# File paths
DATA_DIR = 'data'
CACHE_DIR = 'data/cache'
