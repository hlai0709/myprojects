#!/usr/bin/env python3
"""
Test script for matchup scheduler integration
Verifies week detection logic and data availability
Location: src/debug/test_integration.py
"""

import os
import sys
from datetime import datetime

# Add parent directory (src/) to path so we can import modules from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

# Import the functions we need to test
try:
    from matchup_scheduler import (
        get_current_or_next_matchup,
        is_sunday,
        get_current_week_number
    )
    print("✅ Successfully imported matchup_scheduler functions")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("   Make sure matchup_scheduler.py is in src/ directory")
    print("   Current sys.path:")
    for p in sys.path[:3]:
        print(f"     - {p}")
    exit(1)

# Load environment
load_dotenv()

# Configuration
TEAM_KEY = "466.l.39285.t.2"


def test_day_detection():
    """Test if day of week detection is working"""
    print("\n" + "=" * 60)
    print("TEST 1: Day Detection")
    print("=" * 60)
    
    today = datetime.now()
    is_sun = is_sunday()
    
    print(f"Current date: {today.strftime('%A, %B %d, %Y')}")
    print(f"Is Sunday?: {is_sun}")
    print(f"Expected behavior: {'Analyze NEXT week' if is_sun else 'Analyze CURRENT week'}")
    
    return is_sun


def test_week_detection():
    """Test if week number detection is working"""
    print("\n" + "=" * 60)
    print("TEST 2: Week Number Detection")
    print("=" * 60)
    
    try:
        current_week = get_current_week_number()
        print(f"Current week number: {current_week}")
        
        if current_week is None:
            print("⚠️  Warning: Could not detect current week")
            return None
        elif current_week < 1 or current_week > 25:
            print(f"⚠️  Warning: Week {current_week} seems unusual")
            return current_week
        else:
            print(f"✅ Week {current_week} looks valid")
            return current_week
            
    except Exception as e:
        print(f"❌ Error detecting week: {e}")
        return None


def test_matchup_fetch(is_sun, current_week):
    """Test if matchup fetching is working"""
    print("\n" + "=" * 60)
    print("TEST 3: Matchup Fetching")
    print("=" * 60)
    
    try:
        matchup_data, week_info = get_current_or_next_matchup(TEAM_KEY)
        
        if not matchup_data:
            print("❌ Failed to fetch matchup data")
            return False
        
        print(f"\n✅ Successfully fetched matchup data!")
        print(f"\nWeek Info:")
        print(f"  - Current week: {week_info['current_week']}")
        print(f"  - Target week: {week_info['target_week']}")
        print(f"  - Is Sunday: {week_info['is_sunday']}")
        print(f"  - Is look-ahead: {week_info['is_look_ahead']}")
        print(f"  - Display name: {week_info['display_name']}")
        
        print(f"\nMatchup Data:")
        print(f"  - Opponent: {matchup_data.get('opponent_name', 'Unknown')}")
        print(f"  - Week: {matchup_data.get('week', '?')}")
        
        # Verify logic
        if is_sun:
            expected_week = current_week + 1
            if week_info['target_week'] == expected_week:
                print(f"\n✅ Correct: Analyzing Week {expected_week} (next week)")
            elif week_info['target_week'] == current_week:
                print(f"\n⚠️  Fallback: Using Week {current_week} (next week not available)")
            else:
                print(f"\n⚠️  Unexpected: Analyzing Week {week_info['target_week']}")
        else:
            if week_info['target_week'] == current_week:
                print(f"\n✅ Correct: Analyzing Week {current_week} (current week)")
            else:
                print(f"\n⚠️  Unexpected: Should analyze Week {current_week}, got Week {week_info['target_week']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fetching matchup: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Run all integration tests"""
    print("\n" + "=" * 60)
    print("MATCHUP SCHEDULER INTEGRATION TESTS")
    print("Running from: src/debug/")
    print("=" * 60)
    
    # Test 1: Day detection
    is_sun = test_day_detection()
    
    # Test 2: Week detection
    current_week = test_week_detection()
    
    # Test 3: Matchup fetching
    success = test_matchup_fetch(is_sun, current_week)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    if success:
        print("✅ All tests passed!")
        print("\nYou're ready to run the integrated ai_analyzer.py")
        print("\nCommand: python src/ai_analyzer.py")
    else:
        print("❌ Some tests failed")
        print("\nTroubleshooting steps:")
        print("1. Verify Yahoo API authentication is working")
        print("2. Check if matchup data exists for target week")
        print("3. Run: python src/matchup_scheduler.py (for detailed debug)")
    
    print("=" * 60)


if __name__ == "__main__":
    test_integration()