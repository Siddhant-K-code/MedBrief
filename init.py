#!/usr/bin/env python3
"""
Initialization script for MediBrief.
This script sets up the project by creating necessary directories and configuration files.
"""

import os
import sys
import shutil
import argparse
from typing import Dict, Any, List

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Initialize MediBrief project")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of existing files"
    )

    return parser.parse_args()

def create_directories() -> None:
    """Create necessary directories."""
    directories = [
        "output",
        "logs",
        "temp",
        "temp/pdfs"
    ]

    for directory in directories:
        if not os.path.exists(directory):
            print(f"Creating directory: {directory}")
            os.makedirs(directory, exist_ok=True)
        else:
            print(f"Directory already exists: {directory}")

def create_config_file(config_path: str, force: bool = False) -> None:
    """
    Create configuration file from template.

    Args:
        config_path: Path to the configuration file.
        force: Whether to overwrite existing file.
    """
    template_path = "config.example.yaml"

    if os.path.exists(config_path) and not force:
        print(f"Configuration file already exists: {config_path}")
        print("Use --force to overwrite")
        return

    if not os.path.exists(template_path):
        print(f"Template file not found: {template_path}")
        return

    print(f"Creating configuration file: {config_path}")
    shutil.copy(template_path, config_path)
    print(f"Configuration file created: {config_path}")
    print("Please edit the configuration file with your API keys and settings")

def check_dependencies() -> List[str]:
    """
    Check if required dependencies are installed.

    Returns:
        List of missing dependencies.
    """
    required_packages = [
        "requests",
        "pyyaml",
        "google-cloud-aiplatform",
        "google-cloud-vision",
        "google-cloud-texttospeech",
        "google-cloud-storage",
        "google-api-python-client",
        "google-auth-oauthlib",
        "moviepy",
        "Pillow",
        "PyPDF2",
        "pdf2image",
        "pytesseract",
        "pdfminer.six"
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_").split(".")[0])
        except ImportError:
            missing_packages.append(package)

    return missing_packages

def main() -> None:
    """Main entry point."""
    args = parse_args()

    print("Initializing MediBrief project...")

    # Create directories
    create_directories()

    # Create configuration file
    create_config_file(args.config, args.force)

    # Check dependencies
    missing_packages = check_dependencies()
    if missing_packages:
        print("\nWarning: The following dependencies are missing:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nPlease install them using:")
        print(f"pip install {' '.join(missing_packages)}")
    else:
        print("\nAll dependencies are installed")

    print("\nInitialization complete!")
    print("\nNext steps:")
    print("1. Edit the configuration file with your API keys and settings")
    print("2. Run the application with: python main.py")

if __name__ == "__main__":
    main()