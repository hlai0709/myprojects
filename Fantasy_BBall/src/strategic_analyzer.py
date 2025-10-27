"""
roster_analyzer.py - Phase 4A Enhancement Module
Provides strategic roster insights for AI prompt optimization:
- Positional balance analysis
- Positional scarcity detection
- Schedule advantage identification
"""

from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict


class StrategicAnalyzer:
    """
    Analyzes roster composition for strategic insights.
    Integrates with existing ai_analyzer.py to enhance prompts.
    """
    
    # Position groupings for balance analysis
    GUARDS = {'PG', 'SG', 'G'}
    WINGS = {'SF', 'F', 'SF/SG'}
    BIGS = {'PF', 'C', 'F/C', 'PF/C'}
    
    # Rare stat thresholds by position (per game averages)
    # These identify elite/scarce player types
    RARE_STATS_THRESHOLDS = {
        'C': {
            '3PTM': 1.5,   # Stretch big
            'FT%': 0.800,  # Good FT shooting big
            'AST': 3.0,    # Playmaking big
            'ST': 1.2      # Defensive big
        },
        'PF': {
            '3PTM': 2.0,   # 3-and-D big
            'FT%': 0.820,  # Good FT shooting forward
            'AST': 3.5,    # Point forward
            'BLK': 1.5,    # Rim protector
            'ST': 1.3      # Defensive forward
        },
        'PG': {
            'BLK': 0.5,    # Defensive guard (rare!)
            'REB': 6.0,    # Rebounding guard
            '3PTM': 3.0,   # Elite shooter
            'TO': 1.5      # Low turnover (under 1.5 is good)
        },
        'SG': {
            'BLK': 0.7,    # Defensive guard
            'REB': 5.0,    # Rebounding guard  
            'AST': 6.0,    # Playmaking SG
            '3PTM': 3.0    # Elite shooter
        },
        'SF': {
            'BLK': 1.0,    # Defensive wing
            'AST': 5.0,    # Playmaking wing
            '3PTM': 2.5,   # Elite shooting wing
            'ST': 1.5      # Defensive specialist
        }
    }
    
    # Schedule advantage thresholds
    HEAVY_GAME_WEEK = 4  # 4+ games is a heavy week
    LIGHT_GAME_WEEK = 2  # 2 or fewer games is light
    
    def __init__(self):
        """Initialize the analyzer."""
        pass
    
    def analyze_roster_balance(self, roster: List[Dict]) -> Dict:
        """
        Analyzes positional balance of the roster.
        
        Args:
            roster: List of player dicts with 'eligible_positions' and 'primary_position'
        
        Returns:
            Dict with balance metrics and recommendations
        """
        # Count by position group
        guards = 0
        wings = 0
        bigs = 0
        
        position_details = []
        
        for player in roster:
            primary = player.get('primary_position', '')
            name = player.get('name', 'Unknown')
            
            if primary in self.GUARDS:
                guards += 1
                position_details.append(f"{name} ({primary})")
            elif primary in self.WINGS:
                wings += 1
                position_details.append(f"{name} ({primary})")
            elif primary in self.BIGS:
                bigs += 1
                position_details.append(f"{name} ({primary})")
        
        total = guards + wings + bigs
        
        if total == 0:
            return {
                'guards': 0, 'wings': 0, 'bigs': 0,
                'balance': 'unknown', 'recommendation': None,
                'summary': 'Unable to analyze roster balance'
            }
        
        # Calculate percentages
        guard_pct = guards / total
        wing_pct = wings / total
        big_pct = bigs / total
        
        # Determine balance type
        balance = self._classify_balance(guard_pct, wing_pct, big_pct)
        
        # Generate recommendation
        recommendation = self._generate_balance_recommendation(
            balance, guard_pct, wing_pct, big_pct
        )
        
        return {
            'guards': guards,
            'wings': wings,
            'bigs': bigs,
            'guard_pct': guard_pct,
            'wing_pct': wing_pct,
            'big_pct': big_pct,
            'balance': balance,
            'recommendation': recommendation,
            'summary': self._format_balance_summary(
                guards, wings, bigs, balance, recommendation
            )
        }
    
    def _classify_balance(self, guard_pct: float, wing_pct: float, big_pct: float) -> str:
        """Classify roster balance type."""
        if guard_pct >= 0.5:
            return 'guard_heavy'
        elif big_pct >= 0.5:
            return 'big_heavy'
        elif wing_pct >= 0.4:
            return 'wing_heavy'
        elif max(guard_pct, wing_pct, big_pct) - min(guard_pct, wing_pct, big_pct) <= 0.2:
            return 'balanced'
        else:
            return 'moderate'
    
    def _generate_balance_recommendation(
        self, balance: str, guard_pct: float, wing_pct: float, big_pct: float
    ) -> str:
        """Generate strategic recommendation based on balance."""
        if balance == 'guard_heavy':
            return "Prioritize bigs (C/PF) for rebounds and blocks"
        elif balance == 'big_heavy':
            return "Prioritize guards (PG/SG) for assists, steals, and FT%"
        elif balance == 'wing_heavy':
            return "Diversify with guards or bigs for category depth"
        elif balance == 'balanced':
            return "Well-balanced roster - target best available talent"
        else:
            # Find the weakest position group
            positions = [('guards', guard_pct), ('wings', wing_pct), ('bigs', big_pct)]
            weakest = min(positions, key=lambda x: x[1])
            return f"Consider adding more {weakest[0]} for better balance"
    
    def _format_balance_summary(
        self, guards: int, wings: int, bigs: int, balance: str, rec: str
    ) -> str:
        """Format balance summary for AI prompt."""
        balance_label = balance.replace('_', ' ').title()
        return (
            f"{guards} Guards / {wings} Wings / {bigs} Bigs ({balance_label})\n"
            f"→ {rec}"
        )
    
    def find_positional_scarcity(
        self, 
        roster: List[Dict], 
        available: List[Dict],
        top_n: int = 10
    ) -> Dict:
        """
        Identifies rare stat combinations by position.
        
        Args:
            roster: Current roster
            available: Available players pool
            top_n: Number of top rare players to return
        
        Returns:
            Dict with scarcity insights and elite targets
        """
        # Analyze current roster for rare combos
        roster_rare = self._find_rare_players(roster)
        
        # Find elite targets in available pool
        available_rare = self._find_rare_players(available)
        
        # Generate scarcity insights
        insights = self._generate_scarcity_insights(roster_rare, available_rare)
        
        return {
            'roster_rare_count': len(roster_rare),
            'roster_rare_players': roster_rare,
            'available_rare_count': len(available_rare),
            'available_rare_players': available_rare[:top_n],
            'insights': insights,
            'summary': self._format_scarcity_summary(roster_rare, available_rare)
        }
    
    def _find_rare_players(self, players: List[Dict]) -> List[Dict]:
        """Find players with rare stat combinations for their position."""
        rare_players = []
        
        for player in players:
            # Get position - try primary_position first, fall back to first eligible
            position = player.get('primary_position', '')
            if not position:
                eligible = player.get('eligible_positions', [])
                position = eligible[0] if eligible else ''
            
            # Normalize position to base position
            if position in self.GUARDS:
                base_pos = 'PG' if position == 'PG' else 'SG'
            elif position in self.WINGS:
                base_pos = 'SF'
            elif position in self.BIGS:
                base_pos = 'C' if position == 'C' else 'PF'
            else:
                continue
            
            stats = player.get('stats', {})
            if not stats:
                continue
            
            # Check for rare stat combos
            rare_stats = []
            thresholds = self.RARE_STATS_THRESHOLDS.get(base_pos, {})
            
            for stat, threshold in thresholds.items():
                value = stats.get(stat)
                if value is None:
                    continue
                
                # Special handling for TO (lower is better)
                if stat == 'TO':
                    if value <= threshold:
                        rare_stats.append(f"Low TO ({value:.1f})")
                else:
                    if value >= threshold:
                        rare_stats.append(f"{stat} {value:.1f}")
            
            if rare_stats:
                rare_players.append({
                    'name': player.get('name', 'Unknown'),
                    'position': position,
                    'base_position': base_pos,
                    'rare_stats': rare_stats,
                    'rare_count': len(rare_stats),
                    'player_key': player.get('player_key', ''),
                    'team': player.get('team', 'FA')
                })
        
        # Sort by number of rare stats (most rare first)
        rare_players.sort(key=lambda x: x['rare_count'], reverse=True)
        return rare_players
    
    def _generate_scarcity_insights(
        self, roster_rare: List[Dict], available_rare: List[Dict]
    ) -> List[str]:
        """Generate strategic insights about positional scarcity."""
        insights = []
        
        # Count rare combos by base position in roster
        roster_positions = Counter(p['base_position'] for p in roster_rare)
        
        # Count available by base position
        available_positions = Counter(p['base_position'] for p in available_rare)
        
        # Identify gaps and opportunities
        for position in ['C', 'PF', 'SF', 'SG', 'PG']:
            roster_count = roster_positions.get(position, 0)
            available_count = available_positions.get(position, 0)
            
            if roster_count == 0 and available_count >= 2:
                insights.append(
                    f"🎯 SCARCITY GAP: No elite {position}s on roster - "
                    f"{available_count} rare options available"
                )
            elif roster_count == 1 and available_count >= 3:
                insights.append(
                    f"💡 UPGRADE PATH: Only 1 elite {position} - "
                    f"{available_count} elite options available"
                )
            elif roster_count >= 2 and available_count == 0:
                insights.append(
                    f"✓ STRENGTH: {roster_count} elite {position}s - no upgrades needed"
                )
        
        # Identify specific rare combos available
        if available_rare:
            top_3 = available_rare[:3]
            rare_descriptions = []
            for p in top_3:
                stats_str = ', '.join(p['rare_stats'][:2])  # First 2 rare stats
                rare_descriptions.append(f"{p['name']} ({p['position']}): {stats_str}")
            
            if rare_descriptions:
                insights.append(
                    f"⭐ TOP RARE TALENTS: {'; '.join(rare_descriptions)}"
                )
        
        return insights
    
    def _format_scarcity_summary(
        self, roster_rare: List[Dict], available_rare: List[Dict]
    ) -> str:
        """Format scarcity summary for AI prompt."""
        if not roster_rare and not available_rare:
            return "No rare stat combinations identified"
        
        lines = []
        
        if roster_rare:
            lines.append(f"Your roster has {len(roster_rare)} elite/rare players:")
            for p in roster_rare[:3]:  # Top 3
                stats = ', '.join(p['rare_stats'][:2])
                lines.append(f"  • {p['name']} ({p['position']}): {stats}")
        else:
            lines.append("Your roster lacks elite rare stat combinations")
        
        if available_rare:
            lines.append(f"\n{len(available_rare)} rare talents available on waivers:")
            for p in available_rare[:5]:  # Top 5
                stats = ', '.join(p['rare_stats'][:2])
                lines.append(f"  • {p['name']} ({p['position']}): {stats}")
        
        return '\n'.join(lines)
    
    def analyze_schedule_advantage(
        self, 
        roster: List[Dict], 
        games_per_team: Dict[str, int]
    ) -> Dict:
        """
        Analyzes schedule advantages for the week.
        
        Args:
            roster: Current roster with team abbreviations
            games_per_team: Dict mapping team abbreviation to game count
        
        Returns:
            Dict with schedule analysis and recommendations
        """
        if not games_per_team:
            return {
                'heavy_week_players': [],
                'light_week_players': [],
                'avg_games': 0,
                'summary': 'Schedule data not available'
            }
        
        # Categorize roster players by schedule
        heavy_week_players = []
        light_week_players = []
        normal_week_players = []
        
        for player in roster:
            team = player.get('team', '')
            games = games_per_team.get(team, 0)
            
            player_info = {
                'name': player.get('name', 'Unknown'),
                'team': team,
                'games': games,
                'position': player.get('primary_position', 'N/A')
            }
            
            if games >= self.HEAVY_GAME_WEEK:
                heavy_week_players.append(player_info)
            elif games <= self.LIGHT_GAME_WEEK:
                light_week_players.append(player_info)
            else:
                normal_week_players.append(player_info)
        
        # Calculate average games for roster
        total_games = sum(p['games'] for p in heavy_week_players + light_week_players + normal_week_players)
        avg_games = total_games / len(roster) if roster else 0
        
        # Calculate league average
        league_avg_games = sum(games_per_team.values()) / len(games_per_team) if games_per_team else 0
        
        # Determine schedule advantage
        advantage_status = self._classify_schedule_advantage(avg_games, league_avg_games)
        
        return {
            'heavy_week_players': heavy_week_players,
            'light_week_players': light_week_players,
            'normal_week_players': normal_week_players,
            'avg_games': avg_games,
            'league_avg_games': league_avg_games,
            'advantage_status': advantage_status,
            'summary': self._format_schedule_summary(
                heavy_week_players, light_week_players, avg_games, 
                league_avg_games, advantage_status, games_per_team
            )
        }
    
    def _classify_schedule_advantage(self, avg_games: float, league_avg: float) -> str:
        """Classify schedule advantage relative to league."""
        diff = avg_games - league_avg
        
        if diff >= 0.3:
            return 'strong_advantage'
        elif diff >= 0.15:
            return 'moderate_advantage'
        elif diff >= -0.15:
            return 'neutral'
        elif diff >= -0.3:
            return 'slight_disadvantage'
        else:
            return 'disadvantage'
    
    def _format_schedule_summary(
        self,
        heavy_week: List[Dict],
        light_week: List[Dict],
        avg_games: float,
        league_avg: float,
        advantage: str,
        games_per_team: Dict[str, int]
    ) -> str:
        """Format schedule summary for AI prompt."""
        lines = []
        
        # Overall status
        lines.append(f"Your roster avg: {avg_games:.1f} games | League avg: {league_avg:.1f} games")
        
        # Advantage interpretation
        advantage_labels = {
            'strong_advantage': '✓ STRONG VOLUME ADVANTAGE',
            'moderate_advantage': '✓ Moderate volume advantage',
            'neutral': '= Neutral schedule',
            'slight_disadvantage': '⚠️ Slight volume disadvantage',
            'disadvantage': '⚠️ VOLUME DISADVANTAGE'
        }
        lines.append(advantage_labels.get(advantage, 'Unknown'))
        
        # Heavy week players
        if heavy_week:
            heavy_teams = set(p['team'] for p in heavy_week)
            heavy_names = [p['name'] for p in heavy_week[:5]]  # Top 5
            lines.append(
                f"\n{len(heavy_week)} players with 4+ games ({', '.join(heavy_teams)}): "
                f"{', '.join(heavy_names)}"
            )
            if len(heavy_week) > 5:
                lines.append(f"  + {len(heavy_week) - 5} more")
        
        # Light week players (targets to replace)
        if light_week:
            light_names = [f"{p['name']} ({p['team']}, {p['games']}g)" for p in light_week]
            lines.append(
                f"\n⚠️ {len(light_week)} players with light schedule: {', '.join(light_names)}"
            )
            lines.append("  → Consider replacing with 4-game players")
        
        # Find teams with heavy schedules for waiver targets
        heavy_schedule_teams = [team for team, games in games_per_team.items() 
                                if games >= self.HEAVY_GAME_WEEK]
        if heavy_schedule_teams and len(heavy_schedule_teams) <= 10:
            lines.append(f"\n🎯 Target waiver players from: {', '.join(sorted(heavy_schedule_teams))}")
        
        return '\n'.join(lines)
    
    def generate_enhanced_prompt_section(
        self,
        roster: List[Dict],
        available_players: List[Dict],
        games_per_team: Optional[Dict[str, int]] = None
    ) -> str:
        """
        Generate the complete enhanced prompt section for Phase 4A.
        This is the main method to call from ai_analyzer.py.
        
        Args:
            roster: Current roster
            available_players: Available players
            games_per_team: Optional schedule data
        
        Returns:
            Formatted string to insert into AI prompt
        """
        sections = []
        
        # 1. Roster Balance Analysis
        balance = self.analyze_roster_balance(roster)
        sections.append("ROSTER COMPOSITION:")
        sections.append(balance['summary'])
        
        # 2. Positional Scarcity Analysis
        scarcity = self.find_positional_scarcity(roster, available_players, top_n=8)
        if scarcity['insights']:
            sections.append("\nPOSITIONAL SCARCITY:")
            for insight in scarcity['insights'][:4]:  # Top 4 insights
                sections.append(insight)
        
        # 3. Schedule Advantage (if data available)
        if games_per_team:
            schedule = self.analyze_schedule_advantage(roster, games_per_team)
            sections.append("\nSCHEDULE ADVANTAGE:")
            sections.append(schedule['summary'])
        
        return '\n'.join(sections)


# Convenience function for integration
def enhance_prompt_with_strategic_analysis(
    roster: List[Dict],
    available_players: List[Dict],
    games_per_team: Optional[Dict[str, int]] = None
) -> str:
    """
    Convenience function to generate enhanced prompt section.
    
    Usage in ai_analyzer.py:
        from strategic_analyzer import enhance_prompt_with_strategic_analysis
        
        strategic_section = enhance_prompt_with_strategic_analysis(
            my_roster, available_players, games_per_team
        )
        prompt += f"\n\n{strategic_section}\n"
    """
    analyzer = StrategicAnalyzer()
    return analyzer.generate_enhanced_prompt_section(
        roster, available_players, games_per_team
    )


if __name__ == "__main__":
    # Test the analyzer with sample data
    print("RosterAnalyzer Module - Phase 4A")
    print("=" * 80)
    
    # Sample roster for testing
    sample_roster = [
        {'name': 'Trae Young', 'primary_position': 'PG', 'team': 'ATL', 
         'stats': {'3PTM': 2.8, 'AST': 11.0, 'REB': 3.0, 'TO': 4.0}},
        {'name': 'Anthony Davis', 'primary_position': 'C', 'team': 'LAL',
         'stats': {'BLK': 2.3, 'REB': 12.0, 'FT%': 0.780, 'AST': 3.5}},
        {'name': 'De\'Aaron Fox', 'primary_position': 'PG', 'team': 'SAC',
         'stats': {'PTS': 26.0, 'AST': 6.0, 'ST': 1.8}},
    ]
    
    sample_games = {
        'ATL': 4, 'LAL': 2, 'SAC': 3, 'PHI': 4, 'GSW': 4
    }
    
    analyzer = StrategicAnalyzer()
    
    # Test balance
    print("\n1. ROSTER BALANCE:")
    print("-" * 80)
    balance = analyzer.analyze_roster_balance(sample_roster)
    print(balance['summary'])
    
    # Test schedule
    print("\n2. SCHEDULE ADVANTAGE:")
    print("-" * 80)
    schedule = analyzer.analyze_schedule_advantage(sample_roster, sample_games)
    print(schedule['summary'])
    
    print("\n" + "=" * 80)
    print("✓ Module ready for integration")