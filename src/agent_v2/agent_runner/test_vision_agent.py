"""Test script for vision agent support.

Tests:
1. ImageLoader: CSV loading, case lookup, API formatting
2. Config: YAML loading, model selection, client setup
3. Vision Agent: gpt-5-mini with image injection
4. Text Agent: deepseek-chat with text descriptions
5. Navigate injection: images injected after navigate tool calls

Usage:
    # Run all tests
    uv run python src/agent_v2/agent_runner/test_vision_agent.py

    # Run specific test
    uv run python src/agent_v2/agent_runner/test_vision_agent.py --test image_loader
    uv run python src/agent_v2/agent_runner/test_vision_agent.py --test config
    uv run python src/agent_v2/agent_runner/test_vision_agent.py --test vision_agent
    uv run python src/agent_v2/agent_runner/test_vision_agent.py --test text_agent
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent_v2.image_loader import ImageLoader
from agent_v2.config import load_config, get_model_config, resolve_image_csv_path, build_client_kwargs

# Paths
AGENT_V2_DIR = Path(__file__).parent.parent
SKILLS_DIR = AGENT_V2_DIR / "skills"
CONFIG_PATH = AGENT_V2_DIR / "agent_config.yaml"


def test_image_loader():
    """Test ImageLoader: CSV loading, lookup, formatting."""
    print("=" * 60)
    print("TEST: ImageLoader")
    print("=" * 60)

    # Resolve CSV path from config
    config = load_config(CONFIG_PATH)
    csv_path = resolve_image_csv_path(config, CONFIG_PATH)
    print(f"CSV path: {csv_path}")
    print(f"CSV exists: {csv_path.exists()}")

    loader = ImageLoader(csv_path)
    print(f"Total images: {loader.total_images}")
    print(f"Total cases: {len(loader.case_ids)}")
    print(f"First 10 case IDs: {loader.case_ids[:10]}")

    # Test case lookup
    test_case = "68"
    images = loader.get_images(test_case)
    print(f"\nCase {test_case}: {len(images)} images")
    for img in images:
        print(f"  - {img['caption']} ({img['url'][:60]}...)")

    # Test has_images
    assert loader.has_images(68), "Case 68 should have images"
    assert loader.has_images("68"), "String case ID should work"
    assert not loader.has_images(999999), "Non-existent case should return False"

    # Test API content formatting
    blocks = loader.format_as_api_content(test_case)
    print(f"\nAPI content blocks for case {test_case}: {len(blocks)}")
    for block in blocks:
        if block["type"] == "text":
            print(f"  text: {block['text']}")
        elif block["type"] == "image_url":
            print(f"  image_url: {block['image_url']['url'][:60]}...")

    # Test text formatting
    text = loader.format_as_text(test_case)
    print(f"\nText format:\n{text}")

    # Test empty case
    empty_blocks = loader.format_as_api_content(999999)
    assert len(empty_blocks) == 0, "Non-existent case should return empty list"
    empty_text = loader.format_as_text(999999)
    assert empty_text == "", "Non-existent case should return empty string"

    print("\nPASSED: ImageLoader")
    return True


def test_config():
    """Test config loading and model selection."""
    print("=" * 60)
    print("TEST: Config")
    print("=" * 60)

    config = load_config(CONFIG_PATH)
    print(f"Config loaded from: {CONFIG_PATH}")
    print(f"Models defined: {list(config.get('models', {}).keys())}")
    print(f"Default model_type: {config.get('defaults', {}).get('model_type')}")

    # Test vision model config
    vision_cfg = get_model_config(config, "vision")
    print(f"\nVision model:")
    print(f"  model_id: {vision_cfg['model_id']}")
    print(f"  provider: {vision_cfg['provider']}")
    print(f"  base_url: {vision_cfg['base_url']}")
    print(f"  supports_vision: {vision_cfg['supports_vision']}")
    assert vision_cfg["supports_vision"] is True

    # Test text model config
    text_cfg = get_model_config(config, "text")
    print(f"\nText model:")
    print(f"  model_id: {text_cfg['model_id']}")
    print(f"  provider: {text_cfg['provider']}")
    print(f"  base_url: {text_cfg['base_url']}")
    print(f"  supports_vision: {text_cfg['supports_vision']}")
    assert text_cfg["supports_vision"] is False

    # Test CSV path resolution
    csv_path = resolve_image_csv_path(config, CONFIG_PATH)
    print(f"\nResolved CSV path: {csv_path}")
    print(f"CSV exists: {csv_path.exists()}")

    # Test invalid model type
    try:
        get_model_config(config, "nonexistent")
        assert False, "Should raise ValueError"
    except ValueError as e:
        print(f"\nCorrectly raised ValueError for bad model_type: {e}")

    print("\nPASSED: Config")
    return True


def test_vision_agent():
    """Test vision agent with gpt-5-mini and case images.

    Requires OPENAI_API_KEY environment variable.
    """
    import os
    print("=" * 60)
    print("TEST: Vision Agent (gpt-5-mini)")
    print("=" * 60)

    if not os.getenv("OPENAI_API_KEY"):
        print("SKIPPED: OPENAI_API_KEY not set")
        return None

    from agent_v2.agent import Agent

    agent = Agent(
        model_type="vision",
        skills=["med-deepresearch"],
        skills_dir=SKILLS_DIR,
        max_turns=3,
        temperature=0.3,
        agent_name="test-vision"
    )

    print(f"Model: {agent.model} (vision={agent.supports_vision})")
    print(f"Image loader: {'loaded' if agent.image_loader else 'not loaded'}")
    if agent.image_loader:
        print(f"  Total images: {agent.image_loader.total_images}")

    # Test with case_id - images should be in the initial message
    test_case_id = 68
    prompt = (
        "You are given medical images for case 68. "
        "Describe what you see in the images briefly. "
        "Do not use any tools, just describe the images."
    )

    print(f"\nRunning vision agent with case_id={test_case_id}...")
    response = agent.run(
        user_input=prompt,
        case_id=test_case_id
    )

    print(f"\nResponse (first 500 chars):\n{response[:500]}")
    print(f"\nTrajectory:")
    print(f"  Turns: {agent.trajectory['total_turns']}")
    print(f"  Tokens: {agent.trajectory['tokens']}")
    print(f"  Termination: {agent.trajectory['termination_reason']}")
    print(f"  case_id tracked: {agent.trajectory.get('case_id')}")
    print(f"  supports_vision tracked: {agent.trajectory.get('supports_vision')}")

    assert agent.trajectory["case_id"] == str(test_case_id)
    assert agent.trajectory["supports_vision"] is True

    print("\nPASSED: Vision Agent")
    return True


def test_text_agent():
    """Test text agent with deepseek-chat and text image descriptions.

    Requires DEEPSEEK_API_KEY environment variable.
    """
    import os
    print("=" * 60)
    print("TEST: Text Agent (deepseek-chat)")
    print("=" * 60)

    if not os.getenv("DEEPSEEK_API_KEY"):
        print("SKIPPED: DEEPSEEK_API_KEY not set")
        return None

    from agent_v2.agent import Agent

    agent = Agent(
        model_type="text",
        skills=["med-deepresearch"],
        skills_dir=SKILLS_DIR,
        max_turns=3,
        temperature=0.3,
        agent_name="test-text"
    )

    print(f"Model: {agent.model} (vision={agent.supports_vision})")
    print(f"Image loader: {'loaded' if agent.image_loader else 'not loaded'}")

    # Text model should NOT have image loader
    assert not agent.supports_vision
    assert agent.image_loader is None

    # Test with case_id - should get text descriptions only
    test_case_id = 68
    prompt = (
        "You are given information about medical case 68. "
        "Based on the image descriptions provided, what type of imaging was used? "
        "Do not use any tools, just answer from the context."
    )

    print(f"\nRunning text agent with case_id={test_case_id}...")

    # Manually load image loader to test text fallback
    config = load_config(CONFIG_PATH)
    csv_path = resolve_image_csv_path(config, CONFIG_PATH)
    agent.image_loader = ImageLoader(csv_path)

    response = agent.run(
        user_input=prompt,
        case_id=test_case_id
    )

    print(f"\nResponse (first 500 chars):\n{response[:500]}")
    print(f"\nTrajectory:")
    print(f"  Turns: {agent.trajectory['total_turns']}")
    print(f"  Tokens: {agent.trajectory['tokens']}")
    print(f"  Termination: {agent.trajectory['termination_reason']}")

    assert agent.trajectory["supports_vision"] is False

    print("\nPASSED: Text Agent")
    return True


def test_navigate_injection():
    """Test that navigate commands trigger image injection.

    Unit test - does not call LLM.
    """
    print("=" * 60)
    print("TEST: Navigate Image Injection (unit)")
    print("=" * 60)

    from agent_v2.agent import Agent

    # Test _extract_navigate_case_id
    agent = Agent.__new__(Agent)  # Create without __init__

    # Test pattern matching
    cases = [
        ("uv run python research_tools.py navigate --case-id 1234 --reason test", "1234"),
        ("research_tools.py navigate --case-id 68", "68"),
        ("navigate --case-id 99999 --reason \"test\"", "99999"),
        ("query --name something", None),
        ("bash echo hello", None),
    ]

    for cmd, expected in cases:
        result = agent._extract_navigate_case_id(cmd)
        status = "OK" if result == expected else "FAIL"
        print(f"  [{status}] '{cmd[:50]}...' -> {result} (expected {expected})")
        assert result == expected, f"Expected {expected}, got {result}"

    # Test _inject_case_images with real loader
    config = load_config(CONFIG_PATH)
    csv_path = resolve_image_csv_path(config, CONFIG_PATH)
    agent.image_loader = ImageLoader(csv_path)
    agent.supports_vision = True

    messages = []
    injected = agent._inject_case_images("68", messages)
    assert injected, "Should inject images for case 68"
    assert len(messages) == 1, "Should add exactly one user message"
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert isinstance(content, list), "Vision content should be a list"
    # Should have header + (caption + image_url) pairs
    img_count = len(agent.image_loader.get_images("68"))
    expected_blocks = 1 + (img_count * 2)  # header + pairs
    assert len(content) == expected_blocks, f"Expected {expected_blocks} blocks, got {len(content)}"
    print(f"  Injected {img_count} images as {len(content)} content blocks")

    # Test text mode
    agent.supports_vision = False
    messages2 = []
    injected2 = agent._inject_case_images("68", messages2)
    assert injected2, "Should inject text for case 68"
    assert messages2[0]["role"] == "user"
    assert isinstance(messages2[0]["content"], str), "Text content should be a string"
    print(f"  Text mode: {messages2[0]['content'][:80]}...")

    # Test non-existent case
    messages3 = []
    injected3 = agent._inject_case_images("999999", messages3)
    assert not injected3, "Should not inject for non-existent case"
    assert len(messages3) == 0

    print("\nPASSED: Navigate Image Injection")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test vision agent support")
    parser.add_argument(
        "--test",
        choices=["image_loader", "config", "vision_agent", "text_agent", "navigate", "all"],
        default="all",
        help="Which test to run"
    )
    args = parser.parse_args()

    tests = {
        "image_loader": test_image_loader,
        "config": test_config,
        "navigate": test_navigate_injection,
        "vision_agent": test_vision_agent,
        "text_agent": test_text_agent,
    }

    if args.test == "all":
        run_tests = list(tests.items())
    else:
        run_tests = [(args.test, tests[args.test])]

    results = {}
    for name, test_fn in run_tests:
        try:
            result = test_fn()
            results[name] = "PASSED" if result else ("SKIPPED" if result is None else "FAILED")
        except Exception as e:
            print(f"\nFAILED: {name} - {e}")
            import traceback
            traceback.print_exc()
            results[name] = "FAILED"
        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, status in results.items():
        print(f"  {name}: {status}")

    failed = sum(1 for s in results.values() if s == "FAILED")
    if failed:
        print(f"\n{failed} test(s) FAILED")
        sys.exit(1)
    else:
        print("\nAll tests passed!")


if __name__ == "__main__":
    # main()
    from agent_v2.agent import Agent

    agent = Agent(
        model_type="vision",
        skills=["med-deepresearch"],
        skills_dir=SKILLS_DIR,
        max_turns=3,
        temperature=1,
        agent_name="test-vision"
    )

    print(f"Model: {agent.model} (vision={agent.supports_vision})")
    print(f"Image loader: {'loaded' if agent.image_loader else 'not loaded'}")
    if agent.image_loader:
        print(f"  Total images: {agent.image_loader.total_images}")

    # Test with case_id - images should be in the initial message
    test_case_id = 68
    prompt = (
        "You are given medical images for case 68. "
        "Describe what you see in the images briefly. "
    )

    print(f"\nRunning vision agent with case_id={test_case_id}...")
    response = agent.run(
        user_input=prompt,
        case_id=test_case_id
    )
    print(response)
