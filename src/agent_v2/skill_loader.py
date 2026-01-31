"""Skill loader for agent_v2.

Skills are like specialized knowledge modules that can be loaded into an agent.
Each skill has:
- SKILL.md: Main instructions with YAML frontmatter + markdown content
- Optional reference/ folder with additional context
- Optional scripts/ folder with executable scripts

Skill loading modes:
1. No skills: Agent only has basic tools (web_search, bash, session_store)
2. Single skill: Full SKILL.md content is added to system prompt
3. Multiple skills: Skill routing prompt added, agent can request skill details
"""
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Skill:
    """Represents a loaded skill."""
    name: str
    description: str
    content: str  # Full markdown content (after frontmatter)
    path: Path
    references: Dict[str, str] = field(default_factory=dict)  # filename -> content

    @property
    def summary(self) -> str:
        """Short summary for skill routing."""
        return f"/{self.name}: {self.description}"


class SkillLoader:
    """Loads and manages skills from SKILL.md files."""

    def __init__(self, skills_dir: Optional[Path] = None):
        """Initialize skill loader.

        Args:
            skills_dir: Directory containing skill folders
        """
        self.skills_dir = skills_dir or Path("./skills")
        self._cache: Dict[str, Skill] = {}

    def discover_skills(self) -> List[str]:
        """Discover all available skill names."""
        if not self.skills_dir.exists():
            return []

        skills = []
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.md"
                if skill_file.exists():
                    skills.append(item.name)
        return sorted(skills)

    def load_skill(self, skill_name: str) -> Optional[Skill]:
        """Load a skill by name.

        Args:
            skill_name: Name of the skill folder

        Returns:
            Skill object or None if not found
        """
        if skill_name in self._cache:
            return self._cache[skill_name]

        skill_path = self.skills_dir / skill_name
        skill_file = skill_path / "SKILL.md"

        if not skill_file.exists():
            return None

        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                raw_content = f.read()

            # Parse YAML frontmatter
            frontmatter, content = self._parse_frontmatter(raw_content)

            skill = Skill(
                name=frontmatter.get("name", skill_name),
                description=frontmatter.get("description", ""),
                content=content.strip(),
                path=skill_path,
                references=self._load_references(skill_path)
            )

            self._cache[skill_name] = skill
            return skill

        except Exception as e:
            print(f"Error loading skill '{skill_name}': {e}")
            return None

    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content.

        Args:
            content: Raw file content

        Returns:
            Tuple of (frontmatter dict, remaining content)
        """
        # Match frontmatter between --- markers
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}, content

        frontmatter_str = match.group(1)
        body = match.group(2)

        # Simple YAML parsing (key: value format)
        frontmatter = {}
        for line in frontmatter_str.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()

        return frontmatter, body

    def _load_references(self, skill_path: Path) -> Dict[str, str]:
        """Load reference files from skill's reference/ folder."""
        references = {}
        ref_dir = skill_path / "reference"

        if ref_dir.exists():
            for ref_file in ref_dir.glob("*.md"):
                try:
                    with open(ref_file, "r", encoding="utf-8") as f:
                        references[ref_file.name] = f.read()
                except IOError:
                    continue

        return references

    def get_skill_content(self, skill_name: str) -> str:
        """Get full content of a skill including references summary."""
        skill = self.load_skill(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found."

        content = f"# Skill: {skill.name}\n\n{skill.content}"

        if skill.references:
            content += "\n\n## Available References\n"
            content += "Use `get_skill_reference` to load any of these:\n"
            for ref_name in skill.references:
                content += f"- {ref_name}\n"

        return content

    def get_reference(self, skill_name: str, ref_name: str) -> str:
        """Get a specific reference file from a skill."""
        skill = self.load_skill(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found."

        if ref_name not in skill.references:
            available = ", ".join(skill.references.keys()) if skill.references else "none"
            return f"Reference '{ref_name}' not found. Available: {available}"

        return skill.references[ref_name]


def generate_skill_routing_prompt(skills: List[Skill]) -> str:
    """Generate a routing prompt for multiple skills.

    This prompt helps the agent understand available skills and
    how to request more information about them.
    """
    skill_list = "\n".join(f"- {s.summary}" for s in skills)

    return f"""## Available Skills

You have access to the following specialized skills:

{skill_list}

### How to Use Skills

1. **Review skill summaries above** to understand what each skill does
2. **Request skill details** using the `get_skill` tool when you need to use a skill
3. **Follow skill instructions** once you have the full skill content

The skill content will provide detailed instructions, examples, and any special tools or procedures.

### Tools for Skill Management

- `get_skill(skill_name)`: Load full instructions for a skill
- `get_skill_reference(skill_name, ref_name)`: Load additional reference material from a skill

Only request skill details when you're about to use that skill - don't load all skills upfront.
"""


def generate_single_skill_prompt(skill: Skill) -> str:
    """Generate prompt content for a single skill.

    When only one skill is assigned, the full content is included directly.
    """
    content = f"""## Skill: {skill.name}

{skill.content}
"""

    if skill.references:
        content += "\n### Available References\n"
        content += "You can use `get_skill_reference` to load:\n"
        for ref_name in skill.references:
            content += f"- `{ref_name}`\n"

    return content
