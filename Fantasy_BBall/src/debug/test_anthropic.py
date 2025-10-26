"""
test_anthropic.py
Simple test to diagnose Anthropic SDK issue
"""

import os
from dotenv import load_dotenv

print("Testing Anthropic SDK initialization...\n")

# Load environment
load_dotenv()

# Check if SDK is installed
try:
    import anthropic
    print(f"✓ Anthropic SDK imported")
    print(f"  Version: {anthropic.__version__}")
except ImportError as e:
    print(f"❌ Failed to import anthropic: {e}")
    exit(1)

# Check API key
api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key or api_key == 'your_anthropic_api_key_here':
    print(f"❌ ANTHROPIC_API_KEY not found in .env")
    exit(1)
else:
    print(f"✓ API key found: {api_key[:8]}...")

# Try to initialize client
print("\nAttempting to initialize Anthropic client...")

try:
    # Method 1: Simple initialization
    client = anthropic.Anthropic(api_key=api_key)
    print("✓ Client initialized successfully!")
    
    # Try a simple API call
    print("\nTesting API call...")
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": "Say 'Hello!' in one word"
            }
        ]
    )
    
    response = message.content[0].text
    print(f"✓ API call successful!")
    print(f"  Response: {response}")
    print(f"  Input tokens: {message.usage.input_tokens}")
    print(f"  Output tokens: {message.usage.output_tokens}")
    
    cost = (message.usage.input_tokens / 1_000_000) * 3.00 + (message.usage.output_tokens / 1_000_000) * 15.00
    print(f"  Cost: ${cost:.6f}")
    
except TypeError as e:
    print(f"❌ TypeError during initialization: {e}")
    print(f"\nThis suggests a version mismatch or incompatible arguments.")
    print(f"Try: pip install --upgrade anthropic")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"  Type: {type(e).__name__}")

print("\n" + "="*80)
print("Diagnostic complete!")
print("="*80)