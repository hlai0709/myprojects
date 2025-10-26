"""
Debug script to find correct stat ID mappings
"""

from auth import YahooAuth
from league_config import LeagueConfig

auth = YahooAuth()
config = LeagueConfig()

LEAGUE_ID = 39285
TEAM_ID = 2
current_week = 1

# Get team keys
my_team_key = auth.get_team_key(LEAGUE_ID, TEAM_ID)
opponent_team_key = "466.l.39285.t.4"  # Humongous Baller

print("="*80)
print("FETCHING LIVE STATS FROM YAHOO API")
print("="*80)

# Fetch my stats
url = f"https://fantasysports.yahooapis.com/fantasy/v2/team/{my_team_key}/stats;type=week;week={current_week}?format=json"
response = auth.session.get(url, timeout=10)

if response.status_code == 200:
    data = response.json()
    team_data = data['fantasy_content']['team']
    
    print("\nMY TEAM STATS:")
    print("-"*80)
    
    for item in team_data:
        if isinstance(item, dict) and 'team_stats' in item:
            team_stats = item['team_stats']
            if 'stats' in team_stats:
                stats_list = team_stats['stats']
                for stat in stats_list:
                    if 'stat' in stat:
                        stat_data = stat['stat']
                        stat_id = stat_data.get('stat_id')
                        value = stat_data.get('value')
                        print(f"  Stat ID {stat_id}: {value}")

# Fetch opponent stats
url = f"https://fantasysports.yahooapis.com/fantasy/v2/team/{opponent_team_key}/stats;type=week;week={current_week}?format=json"
response = auth.session.get(url, timeout=10)

if response.status_code == 200:
    data = response.json()
    team_data = data['fantasy_content']['team']
    
    print("\nOPPONENT STATS:")
    print("-"*80)
    
    for item in team_data:
        if isinstance(item, dict) and 'team_stats' in item:
            team_stats = item['team_stats']
            if 'stats' in team_stats:
                stats_list = team_stats['stats']
                for stat in stats_list:
                    if 'stat' in stat:
                        stat_data = stat['stat']
                        stat_id = stat_data.get('stat_id')
                        value = stat_data.get('value')
                        print(f"  Stat ID {stat_id}: {value}")

print("\n" + "="*80)
print("EXPECTED VALUES (from your screenshot):")
print("="*80)
print("\nYou should be WINNING:")
print("  FT%: .870 vs .794")
print("  ST: 32 vs 28")
print("  TO: 55 vs 60 (lower is better)")
print("\nCompare the stat IDs above to figure out the correct mapping!")