# Vision Agent Support

Agent V2 supports vision-capable LLMs that can analyze medical images alongside text. This document covers configuration, image loading, and how images flow through the agent.

## Architecture

```
agent_config.yaml          <-- Model profiles (vision/text)
       |
    config.py              <-- Loads YAML, resolves paths
       |
  image_loader.py          <-- CSV -> case_id -> [image_url, caption]
       |
    agent.py               <-- Injects images into LLM messages
       |
  ┌────┴────┐
  │ Initial │  On run(): case images loaded into first user message
  │  Load   │
  └─────────┘
  ┌────┴────┐
  │Navigate │  On navigate --case-id X: images injected after tool result
  │ Inject  │
  └─────────┘
```

## Configuration

### agent_config.yaml

```yaml
models:
  vision:
    model_id: gpt-5-mini
    provider: openai
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
    supports_vision: true

  text:
    model_id: deepseek-chat
    provider: deepseek
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com
    supports_vision: false

defaults:
  model_type: text
  temperature: 0.3
  max_turns: 15

image_data:
  csv_path: ../../deepresearch图片链接.csv
  case_id_pattern: "https://www.eurorad.org/case/{case_id}"
  columns:
    plink: plink
    img_url: img_url
    caption: img_alt
    img_id: img_id
```

### Model Selection Priority

When creating an Agent, model is resolved in this order:

1. **Explicit `model=`** parameter (highest priority, vision=False by default)
2. **`model_type=`** parameter ("vision" or "text", reads from config)
3. **`AGENT_MODEL` env var** (fallback)
4. **Default** `deepseek-chat` (text only)

## Usage

### Creating a Vision Agent

```python
from agent_v2.agent import Agent

# Using model_type (recommended)
agent = Agent(
    model_type="vision",          # Selects gpt-5-mini from config
    skills=["med-deepresearch"],
    skills_dir=Path("/path/to/skills"),
    max_turns=10
)

# Agent auto-loads image CSV on init:
# [Vision] Loaded 69347 images across 18421 cases
```

### Running with Case Images

```python
# Case images auto-loaded into the initial message
response = agent.run(
    user_input="Analyze this clinical case: ...",
    case_id=68  # Loads all images for eurorad case 68
)
```

### Running with a Local Image

```python
# Local file (base64 encoded)
response = agent.run(
    user_input="What do you see in this scan?",
    image="/path/to/scan.jpg"
)
```

### Navigate Image Injection

When the agent calls `navigate --case-id X` during research, images for case X are automatically injected as a follow-up user message. The LLM sees:

```
[tool result] Case details for case 1234...
[user message] --- Medical images for case 1234 ---
               [Image 1/3] CT scan with contrast
               [image_url: https://...]
               [Image 2/3] Axial T1W SE
               [image_url: https://...]
```

This happens transparently -- no code changes needed in skills.

## Image Data Source

The image CSV (`deepresearch图片链接.csv`) has ~69K rows mapping eurorad cases to images:

| Column | Description | Example |
|--------|-------------|---------|
| plink | Case page URL | `https://www.eurorad.org/case/68` |
| img_url | Direct image URL | `https://www.eurorad.org/.../000001.jpg` |
| img_alt | Image caption | "CT scan with contrast" |
| img_id | Unique ID | `hgbMLHis` |

Case ID is extracted from the plink URL: `/case/68` -> `68`.

### ImageLoader API

```python
from agent_v2.image_loader import ImageLoader

loader = ImageLoader("path/to/deepresearch图片链接.csv")

# Check availability
loader.has_images(68)           # True
loader.get_images(68)           # [{"url": ..., "caption": ..., "img_id": ...}, ...]
loader.total_images             # 69347
len(loader.case_ids)            # 18421

# Format for OpenAI API (vision models)
blocks = loader.format_as_api_content(68)
# [{"type": "text", "text": "[Image 1/2] CT scan..."}, {"type": "image_url", ...}, ...]

# Format as text (non-vision models)
text = loader.format_as_text(68)
# "Case 68 has 2 image(s):\n  1. CT scan with contrast (URL: https://...)"
```

## Text vs Vision Model Behavior

| Feature | Text Model | Vision Model |
|---------|-----------|--------------|
| Initial case images | Text descriptions appended | Image URL blocks in message |
| Navigate images | Text descriptions | Image URL blocks injected |
| Local image file | Skipped | Base64 encoded in message |
| Image loader init | Not loaded | Auto-loaded from CSV |

## Trajectory Tracking

Vision runs include extra fields in trajectory JSON:

```json
{
  "supports_vision": true,
  "case_id": "68",
  "turns": [
    {
      "turn": 3,
      "images_injected": ["1234"],
      "tool_calls": [...]
    }
  ]
}
```

## Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `OPENAI_API_KEY` | Vision model | OpenAI API key for gpt-5-mini |
| `DEEPSEEK_API_KEY` | Text model | DeepSeek API key |
| `OPENROUTER_API_KEY` | Legacy path | OpenRouter API key |

## Known Limitations

**Eurorad image URL accessibility**: The eurorad image URLs in the CSV may be
blocked by hotlink protection when OpenAI's servers try to fetch them. If you see
`invalid_image_url` errors from the API, the images need to be either:
1. Downloaded locally and served via a public URL / base64 encoded
2. Proxied through an accessible endpoint

The text model path (captions only) is unaffected since it doesn't send URLs to the API.

## Testing

See `agent_runner/test_vision_agent.py` for integration tests covering:
- Vision agent with gpt-5-mini + case images
- Text agent with deepseek-chat + text descriptions
- Image loader unit tests
- Navigate image injection

```bash
# Run all tests
uv run python src/agent_v2/agent_runner/test_vision_agent.py

# Run specific test
uv run python src/agent_v2/agent_runner/test_vision_agent.py --test image_loader
uv run python src/agent_v2/agent_runner/test_vision_agent.py --test config
uv run python src/agent_v2/agent_runner/test_vision_agent.py --test navigate
uv run python src/agent_v2/agent_runner/test_vision_agent.py --test vision_agent
uv run python src/agent_v2/agent_runner/test_vision_agent.py --test text_agent
```
