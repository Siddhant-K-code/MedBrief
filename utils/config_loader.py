"""
Configuration loader utility for MediBrief.
"""

import os
import yaml
from typing import Dict, Any


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Dictionary containing the configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If the configuration file is not valid YAML.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Validate required configuration sections
    required_sections = [
        "api_keys", "pubmed", "pdf_processing", "ai_processing",
        "image_analysis", "tts", "video_generation", "cloud_storage",
        "youtube", "pipeline", "logging"
    ]

    missing_sections = [section for section in required_sections if section not in config]
    if missing_sections:
        raise ValueError(f"Missing required configuration sections: {', '.join(missing_sections)}")

    return config


def get_api_key(config: Dict[str, Any], service: str) -> str:
    """
    Get an API key from the configuration.

    Args:
        config: Configuration dictionary.
        service: Service name to get the API key for.

    Returns:
        API key for the specified service.

    Raises:
        ValueError: If the API key is not found or is empty.
    """
    if service not in config["api_keys"] or not config["api_keys"][service]:
        # Check if the key is in environment variables
        env_var = f"MEDBRIEF_{service.upper()}_API_KEY"
        api_key = os.environ.get(env_var)

        if not api_key:
            raise ValueError(f"API key for {service} not found in configuration or environment variables")

        return api_key

    return config["api_keys"][service]