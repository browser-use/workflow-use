#!/usr/bin/env python3
"""
Example usage of the voice recording functionality in Workflow Use CLI.

This script demonstrates how to use the new --voice flag with the create-workflow command.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Demonstrate voice recording workflow creation."""
    print("=== Workflow Use Voice Recording Example ===\n")
    
    print("This example shows how to use the new voice recording feature.")
    print("The voice recording will be used as context for workflow generation.\n")
    
    # Check if we're in the right directory
    if not Path("cli.py").exists():
        print("Error: Please run this script from the workflows directory.")
        print("Current directory:", Path.cwd())
        sys.exit(1)
    
    print("Available commands:")
    print("1. Create workflow with voice recording:")
    print("   python cli.py create-workflow --voice")
    print()
    print("2. Create workflow without voice recording (original):")
    print("   python cli.py create-workflow")
    print()
    print("3. See all available commands:")
    print("   python cli.py --help")
    print()
    
    # Show the help for create-workflow command
    print("=== Command Help ===")
    try:
        result = subprocess.run(
            ["python", "cli.py", "create-workflow", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(result.stdout)
    except subprocess.TimeoutExpired:
        print("Command timed out")
    except Exception as e:
        print(f"Error running command: {e}")
    
    print("\n=== How it works ===")
    print("1. When you run 'python cli.py create-workflow --voice':")
    print("   - You'll be prompted to record your voice (10 seconds)")
    print("   - The voice will be transcribed using Whisper")
    print("   - You can add additional text instructions")
    print("   - The combined prompt will be used for workflow generation")
    print("   - Then the normal browser recording process begins")
    print()
    print("2. The voice transcription provides context for the LLM")
    print("   - Helps understand the purpose of the workflow")
    print("   - Improves workflow generation quality")
    print("   - Makes the process more natural and intuitive")
    print()
    print("3. Example voice prompts:")
    print("   - 'I want to search for products on Amazon'")
    print("   - 'Fill out this contact form with my information'")
    print("   - 'Navigate to the login page and enter credentials'")
    print()
    
    print("=== Requirements ===")
    print("Make sure you have:")
    print("- A working microphone")
    print("- OpenAI API key set (for Whisper transcription)")
    print("- The required dependencies installed (SpeechRecognition, pyaudio, openai-whisper)")
    print()
    
    print("=== Installation ===")
    print("If you haven't installed the voice recording dependencies:")
    print("uv sync  # This will install the new dependencies from pyproject.toml")
    print()
    
    print("Ready to try voice recording? Run:")
    print("python cli.py create-workflow --voice")


if __name__ == "__main__":
    main() 