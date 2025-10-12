"""Obsidian plugin for processing Obsidian markdown files and content."""

import difflib
import re
from pathlib import Path
from typing import Final

import structlog


def replace_diary_section(existing_content: str, new_diary_section: str) -> str:
    """Replace existing diary section with new content.

    Args:
        existing_content: Current file content
        new_diary_section: New diary section to insert

    Returns:
        Updated file content with diary section replaced
    """
    if not existing_content.strip():
        return new_diary_section.strip()

    # Split content by lines to work with sections
    lines = existing_content.split("\n")
    result_lines = []
    in_diary_section = False
    diary_section_found = False

    for line in lines:
        if line.strip() == "## Diary":
            # Start of diary section - replace with new content
            diary_section_found = True
            in_diary_section = True
            result_lines.extend(new_diary_section.strip().split("\n"))
        elif in_diary_section and line.startswith("## "):
            # End of diary section, start of new section
            in_diary_section = False
            result_lines.append("")  # Add blank line before next section
            result_lines.append(line)
        elif not in_diary_section:
            # Not in diary section, keep the line
            result_lines.append(line)
        # Skip lines that are in diary section (they get replaced)

    if not diary_section_found:
        # No diary section found, append to end
        result_lines.extend(["", new_diary_section.strip()])

    return "\n".join(result_lines)


def read_obsidian_file(file_path: Path) -> str | None:
    """Read Obsidian markdown file with error handling.

    Args:
        file_path: Path to the markdown file

    Returns:
        File content or None if reading fails
    """
    try:
        with open(file_path, encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        structlog.get_logger().error(f"Failed to read file {file_path}: {e}")
        return None


def write_obsidian_file(file_path: Path, content: str) -> bool:
    """Write content to Obsidian markdown file with error handling.

    Args:
        file_path: Path to the markdown file
        content: Content to write

    Returns:
        True if write successful, False otherwise
    """
    logger = structlog.get_logger()
    existing_content = None
    if file_path.exists():
        existing_content = read_obsidian_file(file_path)

    if existing_content is not None and existing_content != content:
        diff = difflib.unified_diff(
            existing_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{file_path.name}",
            tofile=f"b/{file_path.name}",
            lineterm="",  # To avoid extra newlines if splitlines(keepends=True) is used
        )
        diff_str = "".join(diff)
        if diff_str:  # Only log if there's an actual diff
            logger.info("Obsidian file content diff before writing", file_path=file_path, diff=diff_str)

    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to write to file {file_path}: {e}")
        return False


def ensure_directory_exists(directory_path: Path) -> bool:
    """Ensure directory exists, creating it if necessary.

    Args:
        directory_path: Path to directory

    Returns:
        True if directory exists or was created successfully
    """
    try:
        directory_path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        structlog.get_logger().error(f"Failed to create directory {directory_path}: {e}")
        return False


def create_obsidian_link(link_target: str, display_text: str | None = None) -> str:
    """Create Obsidian-style internal link.

    Args:
        link_target: Target of the link (e.g., "Todoist/task_id")
        display_text: Optional display text for the link

    Returns:
        Formatted Obsidian link
    """
    if display_text:
        return f"[[{link_target}|{display_text}]]"
    return f"[[{link_target}]]"


def extract_frontmatter(content: str) -> dict[str, str] | None:
    """Extract YAML frontmatter from markdown content.

    Args:
        content: Markdown content with potential frontmatter

    Returns:
        Dictionary of frontmatter key-value pairs or None if not found
    """
    frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.MULTILINE | re.DOTALL)
    match = frontmatter_pattern.match(content)

    if not match:
        return None

    frontmatter_content = match.group(1)
    frontmatter = {}

    for line in frontmatter_content.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"')
        frontmatter[key] = value

    return frontmatter


def extract_section(content: str, section_name: str) -> str | None:
    """Extract a specific section from markdown content.

    Args:
        content: Markdown content
        section_name: Name of the section to extract (without ##)

    Returns:
        Section content or None if not found
    """
    pattern = rf"^## {re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        return None

    return match.group(1).strip()


def format_task_checkbox(status: str) -> str:
    """Format task checkbox based on status.

    Args:
        status: Task status ('completed', 'in_progress', 'todo')

    Returns:
        Formatted checkbox string
    """
    status_map = {"completed": "[x]", "in_progress": "[/]", "todo": "[ ]"}
    return status_map.get(status, "[ ]")


OBSIDIAN_LINK_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[\[([^\]|]+)(\|([^\]]+))?\]\]")


def extract_obsidian_links(content: str) -> list[tuple[str, str | None]]:
    """Extract Obsidian-style links from content.

    Args:
        content: Markdown content containing Obsidian links

    Returns:
        List of tuples (link_target, display_text), display_text is None if not specified
    """
    matches = OBSIDIAN_LINK_PATTERN.findall(content)
    return [(match[0], match[2] if match[2] else None) for match in matches]


def replace_obsidian_links(content: str, replacement_func) -> str:
    """Replace Obsidian links in content using a replacement function.

    Args:
        content: Content containing Obsidian links
        replacement_func: Function that takes (link_target, display_text) and returns replacement string

    Returns:
        Content with replaced links
    """

    def replace_match(match):
        link_target = match.group(1)
        display_text = match.group(3) if match.group(3) else None
        return replacement_func(link_target, display_text)

    return OBSIDIAN_LINK_PATTERN.sub(replace_match, content)
