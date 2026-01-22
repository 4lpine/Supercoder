#!/usr/bin/env python3
"""
Test executePwsh with interactive_responses using the test script
"""
import sys
import os

# Add Supercoder to path
sys.path.insert(0, r'C:\Projects\Supercoder')

from tools import execute_pwsh

print("Testing executePwsh with interactive responses...")
print("=" * 70)

# Responses for the interactive test script
responses = [
    "Alice",           # Name
    "8",               # Math answer (5+3)
    "B",               # Capital of France
    "yes",             # Like Python?
    "25",              # Age
    "",                # City (skip)
    "yes"              # Confirmation
]

print(f"Running test_interactive_prompts.py with {len(responses)} responses")
print()

result = execute_pwsh(
    "python test_interactive_prompts.py",
    timeout=30,
    interactive_responses=responses
)

print("\n" + "=" * 70)
print("RESULT:")
print(f"Exit code: {result['returncode']}")
print()

if result['returncode'] == 0:
    print("✓ Test completed successfully!")
else:
    print("✗ Test failed!")
    if result['stderr']:
        print(f"\nError: {result['stderr']}")
