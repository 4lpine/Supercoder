#!/usr/bin/env python3
"""
Interactive test script to verify executePwsh interactive_responses handling.
This script asks for various inputs to test the interactive command system.
"""

def main():
    print("=" * 60)
    print("INTERACTIVE TEST SCRIPT")
    print("=" * 60)
    print()
    
    # Test 1: Simple text input
    print("Test 1: What is your name?")
    name = input("Enter your name: ")
    print(f"Hello, {name}!")
    print()
    
    # Test 2: Math equation
    print("Test 2: Solve this math problem")
    answer = input("What is 5 + 3? ")
    if answer == "8":
        print("✓ Correct!")
    else:
        print(f"✗ Wrong! You said {answer}, but the answer is 8")
    print()
    
    # Test 3: Multiple choice
    print("Test 3: Multiple choice question")
    print("What is the capital of France?")
    print("  A) London")
    print("  B) Paris")
    print("  C) Berlin")
    print("  D) Madrid")
    choice = input("Enter your choice (A/B/C/D): ")
    if choice.upper() == "B":
        print("✓ Correct! Paris is the capital of France")
    else:
        print(f"✗ Wrong! You chose {choice}, but the answer is B (Paris)")
    print()
    
    # Test 4: Yes/No question
    print("Test 4: Yes/No question")
    answer = input("Do you like Python? (yes/no): ")
    if answer.lower() in ["yes", "y"]:
        print("Great! Python is awesome!")
    else:
        print("That's okay, everyone has preferences!")
    print()
    
    # Test 5: Number input
    print("Test 5: Number input")
    age = input("How old are you? ")
    try:
        age_num = int(age)
        print(f"You are {age_num} years old")
    except ValueError:
        print(f"'{age}' is not a valid number!")
    print()
    
    # Test 6: Empty input (default)
    print("Test 6: Optional input with default")
    city = input("What city are you from? (press Enter to skip): ")
    if city:
        print(f"You're from {city}")
    else:
        print("You skipped this question")
    print()
    
    # Test 7: Confirmation
    print("Test 7: Final confirmation")
    confirm = input("Are you ready to finish? (yes/no): ")
    if confirm.lower() in ["yes", "y"]:
        print()
        print("=" * 60)
        print("TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("Summary:")
        print(f"  Name: {name}")
        print(f"  Math answer: {answer}")
        print(f"  Capital choice: {choice}")
        print(f"  Likes Python: {answer}")
        print(f"  Age: {age}")
        print(f"  City: {city if city else '(skipped)'}")
    else:
        print("Test cancelled")

if __name__ == "__main__":
    main()
