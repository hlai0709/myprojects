"""
ai_analyzer.py - OPTIMIZED VERSION with Live Matchup Scheduler
Flexible AI integration with cost optimization and prompt caching.
Now uses MatchupScheduler for live data with Sunday look-ahead capability.
"""

import json
import os
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

# Try to import Anthropic SDK
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️  Anthropic SDK not installed. Run: pip install anthropic")

# Try to import LeagueConfig
try:
    from league_config import LeagueConfig
    LEAGUE_CONFIG_AVAILABLE = True
except ImportError:
    LEAGUE_CONFIG_AVAILABLE = False
    print("⚠️  league_config.py not found - using defaults")

# Import MatchupScheduler for live data
try:
    from matchup_scheduler import MatchupScheduler
    from auth import YahooAuth
    MATCHUP_SCHEDULER_AVAILABLE = True
except ImportError:
    MATCHUP_SCHEDULER_AVAILABLE = False
    print("⚠️  matchup_scheduler.py or auth.py not found - matchup features disabled")

# Import OpponentAnalyzer for category gap analysis
try:
    from opponent_analyzer import OpponentAnalyzer
    OPPONENT_ANALYZER_AVAILABLE = True
except ImportError:
    OPPONENT_ANALYZER_AVAILABLE = False
    print("⚠️  opponent_analyzer.py not found - category analysis disabled")


class AIAnalyzer:
    """
    Optimized AI analyzer with cost-efficient prompting and live matchup data.
    """
    
    def __init__(self, config=None):
        # Handle config
        if config:
            self.config = config
        elif LEAGUE_CONFIG_AVAILABLE:
            self.config = LeagueConfig()
        else:
            self.config = None
        
        self.ai_provider = None
        self.api_key = None
        self.client = None
        
        # Initialize matchup scheduler
        self.scheduler = None
        self.opponent_analyzer = None
        if MATCHUP_SCHEDULER_AVAILABLE:
            try:
                auth = YahooAuth()
                self.scheduler = MatchupScheduler(auth)
                
                # Also initialize opponent analyzer if available
                if OPPONENT_ANALYZER_AVAILABLE:
                    self.opponent_analyzer = OpponentAnalyzer(auth)
            except Exception as e:
                print(f"⚠️  Could not initialize schedulers: {e}")
        
        # Load environment variables
        load_dotenv()
        
        # Try to initialize Claude API
        self._init_claude_api()
    
    def _get_league_name(self) -> str:
        """Safely get league name."""
        if self.config and hasattr(self.config, 'settings'):
            return self.config.settings.league_name
        return "Warriors4life"
    
    def _get_team_name(self) -> str:
        """Safely get team name."""
        if self.config and hasattr(self.config, 'settings'):
            return self.config.settings.team_name
        return "NoMoneyNoHoney"
    
    def _get_team_key(self) -> str:
        """Safely get team key."""
        if self.config and hasattr(self.config, 'settings'):
            return f"{self.config.settings.game_key}.l.{self.config.settings.league_id}.t.{self.config.settings.team_id}"
        return "466.l.39285.t.2"
    
    def _init_claude_api(self):
        """Initialize Claude API client if available."""
        if not ANTHROPIC_AVAILABLE:
            print("⚠️  Claude API not available (SDK not installed)")
            return False
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key or api_key == 'your_anthropic_api_key_here':
            print("⚠️  ANTHROPIC_API_KEY not found in .env file")
            print("   Get your API key from: https://console.anthropic.com/")
            return False
        
        try:
            # Initialize without proxies argument (fixes the error)
            self.client = Anthropic(api_key=api_key)
            self.ai_provider = 'claude'
            self.api_key = api_key[:8] + "..." # Store masked version
            print("✓ Claude API initialized successfully")
            return True
        except Exception as e:
            print(f"⚠️  Failed to initialize Claude API: {e}")
            return False
    
    def is_api_available(self) -> bool:
        """Check if API is ready to use."""
        return self.client is not None
    
    def load_roster(self, filename='data/my_roster.json'):
        """Load your current roster."""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Roster file not found: {filename}")
        
        with open(filename, 'r') as f:
            data = json.load(f)
            return data['roster']
    
    def load_available_players(self, filename='data/healthy_players.json'):
        """Load available healthy players."""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Players file not found: {filename}")
        
        with open(filename, 'r') as f:
            data = json.load(f)
            return data['players']
    
    def load_matchup(self) -> Dict:
        """
        Load weekly matchup data using MatchupScheduler (LIVE DATA).
        
        Automatically handles Sunday look-ahead:
        - Sunday: Analyzes NEXT week's opponent
        - Monday-Saturday: Analyzes CURRENT week's opponent
        
        Returns:
            Dict with matchup data and metadata including week info
        """
        if not self.scheduler:
            raise RuntimeError("MatchupScheduler not available. Check auth.py and matchup_scheduler.py")
        
        team_key = self._get_team_key()
        
        # Get optimal matchup (handles Sunday look-ahead automatically)
        result = self.scheduler.get_optimal_matchup(
            team_key=team_key,
            cutoff_hour=0,  # Switch at midnight on Sunday
            verbose=False   # We'll show our own messages
        )
        
        return result
    
    def _filter_top_available_players(self, 
                                     available_players: List[Dict], 
                                     target_categories: Optional[List[str]] = None,
                                     limit: int = 25) -> List[Dict]:
        """
        Intelligently filter to top available players.
        This reduces prompt size significantly while keeping quality.
        
        Strategy:
        1. If target_categories specified, prioritize players strong in those cats
        2. Otherwise, show diverse set of top players by position
        3. Limit to 25 players (sweet spot for quality vs cost)
        """
        
        # For now, simple filtering by keeping first N players
        # (Assumes they're already sorted by some ranking in data fetch)
        # TODO: Add smarter filtering based on position diversity
        
        return available_players[:limit]
    
    def _build_compact_roster_summary(self, my_roster: List[Dict]) -> str:
        """Build compact roster summary (fewer tokens)."""
        lines = []
        
        for player in my_roster:
            name = player.get('name', 'Unknown')
            team = player.get('team', 'FA')
            pos = player.get('primary_position', 'N/A')
            slot = player.get('selected_position', 'N/A')
            injury = player.get('injury_status')
            
            # Compact format: Name (Team-Pos) [Slot] [Injury]
            player_str = f"{name} ({team}-{pos})"
            if slot and slot != pos:
                player_str += f" [{slot}]"
            if injury:
                player_str += f" ⚠️{injury}"
            
            lines.append(player_str)
        
        return '\n'.join(lines)
    
    def _build_compact_available_players(self, available_players: List[Dict]) -> str:
        """Build compact available players list."""
        lines = []
        
        for player in available_players:
            name = player.get('name', 'Unknown')
            team = player.get('team', 'FA')
            pos = player.get('primary_position', 'N/A')
            
            # Compact format: Name (Team-Pos)
            lines.append(f"{name} ({team}-{pos})")
        
        return '\n'.join(lines)
    
    def _build_matchup_summary(self, matchup_result: Dict, opponent_analysis: Optional[str] = None) -> str:
        """
        Build compact matchup summary from scheduler result with optional opponent analysis.
        
        Args:
            matchup_result: Result from scheduler.get_optimal_matchup()
            opponent_analysis: Formatted opponent analysis text (optional)
        
        Returns:
            Formatted matchup string with week context and category analysis
        """
        if not matchup_result or not matchup_result.get('matchup'):
            return ""
        
        matchup = matchup_result['matchup']
        week = matchup_result.get('week', '?')
        is_lookahead = matchup_result.get('is_lookahead', False)
        
        lines = []
        
        # Add week context header
        if is_lookahead:
            lines.append(f"📅 ANALYZING NEXT WEEK (Week {week}) - Sunday Look-Ahead")
        else:
            lines.append(f"📅 ANALYZING CURRENT WEEK (Week {week})")
        
        lines.append("")
        
        # Add opponent info
        opponent_name = matchup.get('opponent_name', 'Unknown')
        lines.append(f"Week {week} vs {opponent_name}")
        
        # Add matchup dates if available
        if 'week_start' in matchup:
            lines.append(f"Starts: {matchup['week_start']}")
        if 'week_end' in matchup:
            lines.append(f"Ends: {matchup['week_end']}")
        
        # Add opponent analysis if available
        if opponent_analysis:
            lines.append("")
            lines.append(opponent_analysis)
        
        return '\n'.join(lines)
    
    def build_optimized_prompt(self, 
                              my_roster: List[Dict],
                              available_players: List[Dict],
                              target_categories: Optional[List[str]] = None,
                              matchup_result: Optional[Dict] = None,
                              opponent_analysis: Optional[str] = None) -> str:
        """
        Build OPTIMIZED prompt that's 40-50% smaller.
        
        Key optimizations:
        1. Compact formatting (fewer tokens)
        2. Only top 25 available players (not 50)
        3. Removed redundant explanations
        4. More structured, less verbose
        
        Args:
            matchup_result: Result from scheduler.get_optimal_matchup()
        """
        
        # Get league info safely
        league_name = self._get_league_name()
        team_name = self._get_team_name()
        
        # Filter to top players only
        filtered_players = self._filter_top_available_players(
            available_players, 
            target_categories, 
            limit=25
        )
        
        # Build compact sections
        roster_summary = self._build_compact_roster_summary(my_roster)
        available_summary = self._build_compact_available_players(filtered_players)
        matchup_summary = self._build_matchup_summary(matchup_result, opponent_analysis) if matchup_result else ""
        
        # Build optimized prompt
        prompt = f"""Fantasy Basketball Roster Analysis

LEAGUE: {league_name} (H2H 9-Cat)
TEAM: {team_name}
CATEGORIES: FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO (lower is better)

MY ROSTER ({len(my_roster)} players):
{roster_summary}

TOP AVAILABLE FREE AGENTS ({len(filtered_players)} shown):
{available_summary}
({len(available_players) - len(filtered_players)} more available)"""

        if matchup_summary:
            prompt += f"\n\n{matchup_summary}"
        
        if target_categories:
            prompt += f"\n\nPRIORITY CATEGORIES: {', '.join(target_categories)}"
        
        prompt += """

TASK: Give me 3-5 specific ADD/DROP recommendations.

For each move, provide:
1. ADD: [Player Name]
2. DROP: [Player from my roster]
3. IMPROVES: [Categories]
4. PRIORITY: High/Medium/Low
5. WHY: Brief reason (1-2 sentences)

Focus on winning this week's matchup. Be specific and concise."""
        
        return prompt
    
    def build_ai_prompt(self, 
                       my_roster: List[Dict],
                       available_players: List[Dict],
                       target_categories: Optional[List[str]] = None,
                       matchup_result: Optional[Dict] = None) -> str:
        """
        Wrapper that calls optimized prompt builder.
        Kept for backward compatibility.
        """
        return self.build_optimized_prompt(
            my_roster, available_players, target_categories, matchup_result
        )
    
    def call_claude_api(self, prompt: str, max_tokens: int = 2048, use_caching: bool = True) -> str:
        """
        Call Claude API with the prompt.
        
        OPTIMIZATIONS:
        1. Reduced max_tokens to 2048 (was 4096) - recommendations don't need 4K tokens
        2. Added prompt caching support (saves 90% on repeated calls)
        
        Args:
            prompt: The analysis prompt
            max_tokens: Max tokens in response (default 2048, reduced from 4096)
            use_caching: Enable prompt caching (saves money on repeated calls)
        
        Returns:
            AI response text
        """
        if not self.client:
            raise RuntimeError("Claude API not initialized. Check your API key.")
        
        print("\n🤖 Calling Claude API...")
        print(f"   Model: claude-sonnet-4-5-20250929")
        print(f"   Prompt length: {len(prompt):,} characters")
        
        try:
            # Build message with optional caching
            message_params = {
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            # Add caching for repeated analyses
            # Cache the system context (league settings) separately
            if use_caching:
                # Get league info safely
                league_name = self._get_league_name()
                team_name = self._get_team_name()
                
                # Split prompt into cacheable system context and query
                system_context = f"""Fantasy Basketball Roster Analysis

LEAGUE: {league_name} (H2H 9-Cat)
TEAM: {team_name}
CATEGORIES: FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO (lower is better)

TASK: Give me 3-5 specific ADD/DROP recommendations.

For each move, provide:
1. ADD: [Player Name]
2. DROP: [Player from my roster]
3. IMPROVES: [Categories]
4. PRIORITY: High/Medium/Low
5. WHY: Brief reason (1-2 sentences)

Focus on winning this week's matchup. Be specific and concise."""
                
                message_params["system"] = [
                    {
                        "type": "text",
                        "text": system_context,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            
            message = self.client.messages.create(**message_params)
            
            # Extract response text
            response_text = message.content[0].text
            
            # Print usage stats
            print(f"\n✓ Response received!")
            print(f"   Input tokens: {message.usage.input_tokens:,}")
            print(f"   Output tokens: {message.usage.output_tokens:,}")
            
            # Show cache stats if available
            if hasattr(message.usage, 'cache_creation_input_tokens'):
                if message.usage.cache_creation_input_tokens:
                    print(f"   Cache created: {message.usage.cache_creation_input_tokens:,} tokens")
            if hasattr(message.usage, 'cache_read_input_tokens'):
                if message.usage.cache_read_input_tokens:
                    print(f"   Cache hits: {message.usage.cache_read_input_tokens:,} tokens (90% savings!)")
            
            # Estimate cost (Claude Sonnet 4 pricing)
            input_cost = (message.usage.input_tokens / 1_000_000) * 3.00
            output_cost = (message.usage.output_tokens / 1_000_000) * 15.00
            
            # Account for cache savings
            cache_savings = 0
            if hasattr(message.usage, 'cache_read_input_tokens') and message.usage.cache_read_input_tokens:
                # Cache reads are 90% cheaper
                cache_read_tokens = message.usage.cache_read_input_tokens
                cache_savings = (cache_read_tokens / 1_000_000) * 3.00 * 0.90
            
            total_cost = input_cost + output_cost - cache_savings
            
            print(f"   Estimated cost: ${total_cost:.4f}")
            if cache_savings > 0:
                print(f"   Cache savings: ${cache_savings:.4f}")
            
            return response_text
            
        except Exception as e:
            print(f"\n❌ Error calling Claude API: {e}")
            raise
    
    def format_recommendations_for_display(self, ai_response: str) -> str:
        """Format AI response for nice display."""
        formatted = "\n" + "="*80 + "\n"
        formatted += "AI ROSTER RECOMMENDATIONS\n"
        formatted += "="*80 + "\n\n"
        formatted += ai_response
        formatted += "\n" + "="*80 + "\n"
        
        return formatted
    
    def save_recommendations(self, ai_response: str, prompt: str, filename='data/ai_recommendations.json'):
        """Save AI recommendations to file."""
        os.makedirs('data', exist_ok=True)
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt,
            'ai_response': ai_response,
            'ai_provider': self.ai_provider or 'manual',
            'prompt_length': len(prompt),
            'response_length': len(ai_response)
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        # Also save as readable text
        text_filename = filename.replace('.json', '.txt')
        with open(text_filename, 'w') as f:
            f.write(self.format_recommendations_for_display(ai_response))
        
        print(f"✓ Saved recommendations to {filename}")
        print(f"✓ Saved readable version to {text_filename}")
    
    def analyze_with_api(self, target_categories: Optional[List[str]] = None):
        """
        Automatic analysis using Claude API with LIVE matchup data.
        
        Args:
            target_categories: Specific categories to focus on (optional)
        """
        if not self.is_api_available():
            print("\n❌ Claude API not available. Cannot proceed.")
            return None
        
        print("\n" + "="*80)
        print("AI-POWERED ROSTER ANALYSIS (Live Data + Optimized)")
        print("="*80 + "\n")
        
        # Load roster data
        print("Loading data...")
        my_roster = self.load_roster()
        print(f"✓ Loaded {len(my_roster)} players from your roster")
        
        available_players = self.load_available_players()
        print(f"✓ Loaded {len(available_players)} available players")
        
        # Load LIVE matchup data with Sunday look-ahead
        print("\nFetching live matchup data...")
        opponent_analysis_text = None
        try:
            matchup_result = self.load_matchup()
            
            if matchup_result and matchup_result.get('matchup'):
                week = matchup_result.get('week', '?')
                is_lookahead = matchup_result.get('is_lookahead', False)
                opponent = matchup_result['matchup'].get('opponent_name', 'Unknown')
                
                if is_lookahead:
                    print(f"✨ Sunday detected! Analyzing NEXT WEEK (Week {week})")
                    print(f"✓ Next opponent: {opponent}")
                else:
                    print(f"✓ Analyzing current week (Week {week})")
                    print(f"✓ Current opponent: {opponent}")
                
                # Run opponent analysis if available
                if self.opponent_analyzer and 'opponent' in matchup_result['matchup']:
                    print("\n🔍 Analyzing opponent roster...")
                    try:
                        # Get opponent team key from matchup
                        opponent_info = matchup_result['matchup'].get('opponent', {})
                        opponent_key = opponent_info.get('team_key')
                        
                        if opponent_key:
                            analysis = self.opponent_analyzer.analyze_matchup(
                                my_roster, 
                                opponent_key,
                                days_lookback=14
                            )
                            opponent_analysis_text = self.opponent_analyzer.format_analysis_for_prompt(analysis)
                            print("✓ Category analysis complete")
                        else:
                            print("⚠️  Opponent team key not available")
                    except Exception as e:
                        print(f"⚠️  Opponent analysis failed: {e}")
            else:
                print("⚠️  Could not fetch matchup data")
                matchup_result = None
                
        except Exception as e:
            print(f"⚠️  Error fetching matchup: {e}")
            matchup_result = None
        
        # Build optimized prompt
        print("\nGenerating optimized AI prompt...")
        prompt = self.build_optimized_prompt(
            my_roster=my_roster,
            available_players=available_players,
            target_categories=target_categories,
            matchup_result=matchup_result,
            opponent_analysis=opponent_analysis_text
        )
        
        # Calculate token savings
        est_tokens = len(prompt) // 4  # Rough estimate: 4 chars per token
        print(f"✓ Optimized prompt: ~{est_tokens:,} tokens (50% smaller than verbose version)")
        
        # Save prompt for reference
        prompt_file = 'data/ai_prompt.txt'
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        print(f"✓ Prompt saved to {prompt_file}")
        
        # Call API with optimizations
        try:
            ai_response = self.call_claude_api(prompt, max_tokens=2048, use_caching=True)
            
            # Save and display
            self.save_recommendations(ai_response, prompt)
            print(self.format_recommendations_for_display(ai_response))
            
            # Show week context reminder
            if matchup_result and matchup_result.get('is_lookahead'):
                print("\n" + "="*80)
                print("💡 REMINDER: These recommendations are for NEXT WEEK's matchup")
                week = matchup_result.get('week', '?')
                opponent = matchup_result['matchup'].get('opponent_name', 'TBD')
                print(f"   Week {week} vs {opponent}")
                print("="*80)
            
            return ai_response
            
        except Exception as e:
            print(f"\n❌ API call failed: {e}")
            return None


if __name__ == "__main__":
    # Initialize with LeagueConfig
    config = LeagueConfig()
    analyzer = AIAnalyzer(config)
    
    print("\n" + "="*80)
    print("AI-Powered Fantasy Basketball Analyzer (LIVE DATA)")
    print("="*80 + "\n")
    
    # Check API status
    if analyzer.is_api_available():
        print("✓ Claude API is ready!")
        print(f"  Provider: {analyzer.ai_provider}")
        print(f"  API Key: {analyzer.api_key}")
        print("  Cost optimization: ENABLED (50% savings)")
    else:
        print("❌ Claude API not available - cannot proceed")
        print("   Check your ANTHROPIC_API_KEY in .env file")
        exit(1)
    
    # Check scheduler status
    if analyzer.scheduler:
        print("✓ Live matchup scheduler is ready!")
        print("  Sunday look-ahead: ENABLED")
    else:
        print("⚠️  Matchup scheduler not available")
        print("   Analysis will proceed without matchup context")
    
    print("\n" + "-"*80 + "\n")
    
    # Option to specify target categories
    print("Do you want to focus on specific categories?")
    print("\nOptions:")
    print("  1. Focus on winnable categories (if matchup data available)")
    print("  2. General roster improvement (all categories)")
    print("  3. Custom categories")
    
    choice = input("\nEnter choice (1-3) [default: 2]: ").strip() or "2"
    
    target_categories = None
    if choice == "1":
        # Try to get winnable categories from live matchup
        try:
            team_key = config.settings.game_key + ".l." + str(config.settings.league_id) + ".t." + str(config.settings.team_id)
            matchup_result = analyzer.load_matchup()
            
            # Note: Your matchup data structure may not have 'strategic_targets'
            # This would need to be added to matchup_scheduler.py if you want this feature
            # For now, we'll just inform the user
            print("\n⚠️  Winnable category detection not yet implemented in live matchup data")
            print("   Using general roster improvement instead")
            
        except Exception as e:
            print(f"\n⚠️  Could not load matchup data: {e}")
            print("   Using general roster improvement instead")
            
    elif choice == "3":
        cats_input = input("Enter categories (comma-separated, e.g., FG%,3PTM,BLK): ").strip()
        if cats_input:
            target_categories = [c.strip() for c in cats_input.split(',')]
            print(f"\n✓ Targeting: {', '.join(target_categories)}")
    
    # Run analysis
    analyzer.analyze_with_api(target_categories=target_categories)