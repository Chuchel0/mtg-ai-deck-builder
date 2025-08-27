"""
A command-line utility for downloading the official Magic: The Gathering
Comprehensive Rules text file.

This script fetches the rules from a predefined URL provided by Wizards of the
Coast and saves them to the project's /data directory. It is intended to be
run manually to update the local copy of the rules when a new version is released.
"""

import sys
import requests
from pathlib import Path

# The official URL for the MTG Comprehensive Rules text file.
# NOTE: This URL is date-stamped and may require periodic updates.
RULES_URL = "https://media.wizards.com/2025/downloads/MagicCompRules%2020250725.txt"

# Define the project's root directory to construct absolute paths.
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "rules.txt"

def fetch_and_save_rules(url: str, output_path: Path):
    """
    Downloads content from a URL and saves it to a local file.

    Args:
        url (str): The source URL to download from.
        output_path (Path): The destination file path.
    
    Raises:
        requests.exceptions.RequestException: Propagates exceptions for network
                                              or HTTP status code errors.
    """
    print(f"Downloading MTG Comprehensive Rules from: {url}")
    
    try:
        # A timeout is specified to prevent the request from hanging indefinitely.
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes

        # Ensure the target directory exists before writing.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        output_path.write_text(response.text, encoding='utf-8')
        
        print(f"Successfully saved rules to: {output_path.resolve()}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: A network error occurred while downloading the rules: {e}", file=sys.stderr)
        raise

def main():
    """Main execution function for the script."""
    try:
        fetch_and_save_rules(url=RULES_URL, output_path=OUTPUT_FILE)
    except Exception:
        print("\nOperation failed. Please check your network connection and the URL in the script.", file=sys.stderr)
        # Exit with a non-zero status code to signal failure to shell environments.
        sys.exit(1)

if __name__ == "__main__":
    main()