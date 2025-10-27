"""
utils.py - Production utilities for error handling, logging, and caching
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps


class SimpleCache:
    """Simple file-based cache with TTL support."""
    
    def __init__(self, cache_dir: str = 'data/cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get(self, key: str, max_age_seconds: int = 3600) -> Optional[Any]:
        """Get cached value if it exists and isn't expired."""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Check expiration
            cached_time = data.get('timestamp', 0)
            if time.time() - cached_time > max_age_seconds:
                return None
            
            return data.get('value')
        except:
            return None
    
    def set(self, key: str, value: Any):
        """Cache a value with current timestamp."""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'value': value
                }, f)
        except:
            pass  # Silent failure for cache writes
    
    def clear(self, key: Optional[str] = None):
        """Clear specific key or all cache."""
        if key:
            cache_file = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.exists(cache_file):
                os.remove(cache_file)
        else:
            # Clear all cache files
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, filename))


class SimpleLogger:
    """Simple logger for tracking operations."""
    
    def __init__(self, log_file: str = 'data/app.log', verbose: bool = True):
        self.log_file = log_file
        self.verbose = verbose
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def _write(self, level: str, message: str):
        """Write log entry."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        # Write to file
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except:
            pass
        
        # Print if verbose
        if self.verbose:
            if level == 'ERROR':
                print(f"❌ {message}")
            elif level == 'WARNING':
                print(f"⚠️  {message}")
            elif level == 'INFO':
                print(f"ℹ️  {message}")
    
    def info(self, message: str):
        self._write('INFO', message)
    
    def warning(self, message: str):
        self._write('WARNING', message)
    
    def error(self, message: str):
        self._write('ERROR', message)
    
    def debug(self, message: str):
        if self.verbose:
            self._write('DEBUG', message)


def retry_on_failure(max_retries: int = 3, delay_seconds: float = 1.0):
    """Decorator to retry functions on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay_seconds * (attempt + 1))  # Exponential backoff
            
            # All retries failed
            raise last_exception
        
        return wrapper
    return decorator


def safe_api_call(func):
    """Decorator for safe API calls with error handling."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the error but don't crash
            print(f"⚠️  API call failed: {func.__name__} - {str(e)}")
            return None
    
    return wrapper


class RateLimiter:
    """Simple rate limiter to prevent API throttling."""
    
    def __init__(self, max_calls: int = 60, period_seconds: int = 60):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self.calls = []
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove old calls outside the window
        self.calls = [call_time for call_time in self.calls 
                     if now - call_time < self.period_seconds]
        
        # Check if we're at the limit
        if len(self.calls) >= self.max_calls:
            # Wait until oldest call expires
            wait_time = self.period_seconds - (now - self.calls[0]) + 0.1
            if wait_time > 0:
                print(f"⏳ Rate limit reached, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                self.calls = []
        
        # Record this call
        self.calls.append(now)


# Global instances
cache = SimpleCache()
logger = SimpleLogger()
yahoo_rate_limiter = RateLimiter(max_calls=60, period_seconds=60)  # 60 calls/min
espn_rate_limiter = RateLimiter(max_calls=100, period_seconds=60)  # More lenient


def validate_team_key(team_key: str) -> bool:
    """Validate team key format."""
    if not team_key or not isinstance(team_key, str):
        return False
    
    # Format: game_key.l.league_id.t.team_id
    parts = team_key.split('.')
    if len(parts) != 5:
        return False
    
    if parts[1] != 'l' or parts[3] != 't':
        return False
    
    # Check IDs are numeric
    try:
        int(parts[0])  # game_key
        int(parts[2])  # league_id
        int(parts[4])  # team_id
        return True
    except ValueError:
        return False


def validate_week_dates(week_start: str, week_end: str) -> bool:
    """Validate week date format and range."""
    try:
        start = datetime.strptime(week_start, '%Y-%m-%d')
        end = datetime.strptime(week_end, '%Y-%m-%d')
        
        # Week should be 7 days or less
        delta = (end - start).days
        if delta < 0 or delta > 7:
            return False
        
        return True
    except:
        return False