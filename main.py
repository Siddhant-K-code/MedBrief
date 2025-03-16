#!/usr/bin/env python3
"""
MediBrief - Medical Research Paper Summarization System
Main entry point for the application.
"""

import argparse
import logging
import os
import sys
import yaml
from typing import Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import pipeline components
from pipeline.orchestrator import Orchestrator
from utils.config_loader import load_config
from utils.logger import setup_logger


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MediBrief - Medical Research Paper Summarization System"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--specialty",
        type=str,
        help="Medical specialty to process (overrides config)"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to look back for papers (overrides config)"
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        help="Maximum number of papers to process (overrides config)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without uploading to YouTube"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for the application."""
    # Parse command line arguments
    args = parse_arguments()

    # Load configuration
    try:
        config = load_config(args.config)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Set up logging
    log_level = logging.DEBUG if args.debug else getattr(logging, config["logging"]["level"])
    setup_logger(log_level, config["logging"]["format"], config["logging"]["file"])

    # Override config with command line arguments if provided
    if args.specialty:
        config["pubmed"]["specialty"] = args.specialty
    if args.days:
        config["pubmed"]["time_period_days"] = args.days
    if args.max_papers:
        config["pubmed"]["max_results_per_query"] = args.max_papers
    if args.dry_run:
        config["youtube"]["dry_run"] = True

    # Initialize the orchestrator
    orchestrator = Orchestrator(config)

    # Run the pipeline
    try:
        orchestrator.run()
    except Exception as e:
        logging.critical(f"Pipeline execution failed: {e}", exc_info=True)
        sys.exit(1)

    logging.info("Pipeline execution completed successfully")


if __name__ == "__main__":
    main()