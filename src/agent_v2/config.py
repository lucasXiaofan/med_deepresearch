"""Configuration loader for agent_v2.

Loads agent_config.yaml to configure model selection (vision vs text),
API endpoints, and image data sources.
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any

import yaml
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG_PATH = Path(__file__).parent / "agent_config.yaml"


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load agent configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to agent_v2/agent_config.yaml.

    Returns:
        Parsed config dictionary.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config


def get_model_config(config: Dict[str, Any], model_type: Optional[str] = None) -> Dict[str, Any]:
    """Get model configuration for a given type.

    Args:
        config: Full config dict from load_config().
        model_type: "vision" or "text". Defaults to config's default.

    Returns:
        Dict with model_id, provider, api_key_env, base_url, supports_vision.
    """
    model_type = model_type or config.get("defaults", {}).get("model_type", "text")
    models = config.get("models", {})

    if model_type not in models:
        raise ValueError(f"Unknown model_type '{model_type}'. Available: {list(models.keys())}")

    return models[model_type]


def resolve_image_csv_path(config: Dict[str, Any], config_path: Optional[Path] = None) -> Path:
    """Resolve the image CSV path (relative to config file location).

    Args:
        config: Full config dict.
        config_path: Path to the config file (for resolving relative paths).

    Returns:
        Absolute path to the image CSV.
    """
    csv_rel = config.get("image_data", {}).get("csv_path", "")
    base_dir = (Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent)
    resolved = (base_dir / csv_rel).resolve()
    return resolved


def build_client_kwargs(model_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build OpenAI client constructor kwargs from model config.

    Args:
        model_config: Single model config dict (from get_model_config).

    Returns:
        Dict with api_key and base_url for OpenAI() constructor.
    """
    api_key = os.getenv(model_config["api_key_env"])
    if not api_key:
        raise ValueError(
            f"Missing API key: set {model_config['api_key_env']} environment variable"
        )

    return {
        "api_key": api_key,
        "base_url": model_config["base_url"]
    }
