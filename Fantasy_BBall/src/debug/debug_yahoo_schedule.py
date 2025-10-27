"""
Test roster endpoint for game schedule data
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import YahooAuth
import json

auth = YahooAuth()

# Test roster endpoint with weekly stats
url = 'https://fantasysports.yahooapis.com/fantasy/v2/team/466.l.39285.t.2/roster/players/stats;type=week;week=2?format=json'

print("Testing roster endpoint for player game schedules...")
response = auth.session.get(url, timeout=10)

if response.status_code == 200:
    data = response.json()
    
    with open('roster_schedule_test.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✓ Saved to roster_schedule_test.json")
    print("\nSearching for schedule-related fields...")
    
    # Search for game-related keywords
    json_str = json.dumps(data)
    keywords = ['game', 'schedule', 'matchup', 'remaining']
    
    for keyword in keywords:
        count = json_str.lower().count(keyword)
        if count > 0:
            print(f"  Found '{keyword}': {count} occurrences")
    
    print("\nNow run: grep 'game' roster_schedule_test.json | head -20")
else:
    print(f"✗ Failed: {response.status_code}")