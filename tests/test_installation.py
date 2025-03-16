#!/usr/bin/env python3
"""
Test script to verify MediBrief installation.
"""

import os
import sys
import importlib
from typing import List, Tuple

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_module(module_name: str) -> Tuple[bool, str]:
    """
    Check if a module can be imported.

    Args:
        module_name: Name of the module to check.

    Returns:
        Tuple of (success, message).
    """
    try:
        importlib.import_module(module_name)
        return True, f"✅ {module_name} imported successfully"
    except ImportError as e:
        return False, f"❌ {module_name} import failed: {e}"

def check_file(file_path: str) -> Tuple[bool, str]:
    """
    Check if a file exists.

    Args:
        file_path: Path to the file to check.

    Returns:
        Tuple of (success, message).
    """
    if os.path.exists(file_path):
        return True, f"✅ {file_path} exists"
    else:
        return False, f"❌ {file_path} does not exist"

def check_directory(directory_path: str) -> Tuple[bool, str]:
    """
    Check if a directory exists.

    Args:
        directory_path: Path to the directory to check.

    Returns:
        Tuple of (success, message).
    """
    if os.path.isdir(directory_path):
        return True, f"✅ {directory_path} exists"
    else:
        return False, f"❌ {directory_path} does not exist"

def main() -> None:
    """Main entry point."""
    print("Testing MediBrief installation...\n")

    # Check modules
    modules = [
        "pubmed.api",
        "pdf_processing.extractor",
        "ai_processing.vertex_ai",
        "image_analysis.vision_ai",
        "tts.speech_generator",
        "video_generation.movie_creator",
        "cloud_storage.storage_client",
        "youtube.uploader",
        "pipeline.orchestrator",
        "utils.config_loader",
        "utils.logger"
    ]

    module_results = [check_module(module) for module in modules]

    # Check files
    files = [
        "config.example.yaml",
        "main.py",
        "requirements.txt",
        "README.md"
    ]

    file_results = [check_file(file) for file in files]

    # Check directories
    directories = [
        "pubmed",
        "pdf_processing",
        "ai_processing",
        "image_analysis",
        "tts",
        "video_generation",
        "cloud_storage",
        "youtube",
        "pipeline",
        "utils",
        "tests",
        "docs"
    ]

    directory_results = [check_directory(directory) for directory in directories]

    # Print results
    print("Module checks:")
    for success, message in module_results:
        print(message)

    print("\nFile checks:")
    for success, message in file_results:
        print(message)

    print("\nDirectory checks:")
    for success, message in directory_results:
        print(message)

    # Check for config.yaml
    config_exists, config_message = check_file("config.yaml")
    if not config_exists:
        print("\n⚠️  config.yaml not found. Please run init.py to create it.")

    # Calculate overall success
    all_results = module_results + file_results + directory_results
    success_count = sum(1 for success, _ in all_results if success)
    total_count = len(all_results)

    print(f"\nOverall: {success_count}/{total_count} checks passed")

    if success_count == total_count:
        print("\n✅ MediBrief installation looks good!")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues and try again.")

if __name__ == "__main__":
    main()