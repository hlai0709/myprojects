"""
debug_week2.py
Debug script to see what Yahoo API returns for Week 2
"""

import sys
import os
# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import YahooAuth
import json

auth = YahooAuth()

LEAGUE_ID = 39285
TEAM_ID = 2

team_key = auth.get_team_key(LEAGUE_ID, TEAM_ID)
league_key = team_key.rsplit('.t.', 1)[0]

print("="*80)
print("DEBUGGING WEEK 2 MATCHUP")
print("="*80)
print(f"\nTeam Key: {team_key}")
print(f"League Key: {league_key}")

# Try 1: Team matchups endpoint
print("\n" + "-"*80)
print("TEST 1: Team Matchups Endpoint")
print("-"*80)

url = f"{auth.fantasy_base_url}team/{team_key}/matchups;weeks=2?format=json"
print(f"URL: {url}")

response = auth.session.get(url, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("\n✓ Response received!")
    print(json.dumps(data, indent=2)[:2000])  # First 2000 chars
else:
    print(f"❌ Failed: {response.text[:500]}")

# Try 2: League scoreboard endpoint
print("\n" + "-"*80)
print("TEST 2: League Scoreboard Endpoint")
print("-"*80)

url = f"{auth.fantasy_base_url}league/{league_key}/scoreboard;week=2?format=json"
print(f"URL: {url}")

response = auth.session.get(url, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("\n✓ Response received!")
    print(json.dumps(data, indent=2)[:2000])  # First 2000 chars
else:
    print(f"❌ Failed: {response.text[:500]}")

# Try 3: League scoreboard without week parameter (current week)
print("\n" + "-"*80)
print("TEST 3: League Scoreboard (Current Week)")
print("-"*80)

url = f"{auth.fantasy_base_url}league/{league_key}/scoreboard?format=json"
print(f"URL: {url}")

response = auth.session.get(url, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("\n✓ Response received!")
    
    # Try to find week number
    league_data = data['fantasy_content']['league']
    for item in league_data:
        if isinstance(item, dict) and 'scoreboard' in item:
            scoreboard = item['scoreboard']
            if '0' in scoreboard:
                week_info = scoreboard['0']
                print(f"\nWeek info: {json.dumps(week_info, indent=2)[:500]}")
    
    print(json.dumps(data, indent=2)[:2000])
else:
    print(f"❌ Failed: {response.text[:500]}")

print("\n" + "="*80)
print("Debug complete!")
print("="*80)