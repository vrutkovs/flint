"""Todoist plugin for processing Todoist markdown files."""

import datetime
import re
from pathlib import Path
from typing import NamedTuple

import pytz
import structlog


class TodoistTask(NamedTuple):
    """Todoist task data."""

    title: str
    todoist_id: str
    completed: bool
    file_path: Path


def parse_todoist_frontmatter(content: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Parse title, todoist_id, project, and section from frontmatter.

    Args:
        content: File content with YAML frontmatter

    Returns:
        Tuple of (title, todoist_id, project, section) or (None, None, None, None) if parsing fails
    """
    title_match = re.search(r'^title: "(.+)"$', content, re.MULTILINE)
    todoist_id_match = re.search(r'^todoist_id: "(.+)"$', content, re.MULTILINE)
    project_match = re.search(r'^project: "(.+)"$', content, re.MULTILINE)
    section_match = re.search(r'^section: "(.+)"$', content, re.MULTILINE)

    if not title_match or not todoist_id_match:
        return None, None, None, None

    title = title_match.group(1)
    todoist_id = todoist_id_match.group(1)
    project = project_match.group(1) if project_match else "Other"
    section = section_match.group(1) if section_match else None

    return title, todoist_id, project, section


def read_todoist_file(file_path: Path) -> str | None:
    """Read Todoist markdown file with error handling.

    Args:
        file_path: Path to the markdown file

    Returns:
        File content or None if reading fails
    """
    try:
        with open(file_path, encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        structlog.get_logger().warning(f"Error reading {file_path}: {e}")
        return None


def is_task_completed(content: str) -> bool:
    """Check if task is marked as completed in frontmatter.

    Args:
        content: File content

    Returns:
        True if task is completed
    """
    return "completed: true" in content


def is_file_modified_today(file_path: Path, timezone: pytz.tzinfo.BaseTzInfo) -> bool:
    """Check if file was modified today.

    Args:
        file_path: Path to the file
        timezone: Timezone for date comparison

    Returns:
        True if file was modified today
    """
    today = datetime.datetime.now(timezone).date()
    file_stat = file_path.stat()
    file_modified_date = datetime.datetime.fromtimestamp(file_stat.st_mtime, tz=timezone).date()
    return file_modified_date == today


def clean_title_for_obsidian_link(title: str) -> str:
    """Clean title for Obsidian link format by removing special characters.

    Args:
        title: Original task title

    Returns:
        Cleaned title suitable for Obsidian links
    """
    return re.sub(r"[^\w\s-]", "", title).strip()


def get_todoist_files(todoist_folder: str) -> list[Path]:
    """Get list of Todoist markdown files.

    Args:
        todoist_folder: Path to Todoist folder

    Returns:
        List of Path objects for markdown files
    """
    todoist_path = Path(todoist_folder)
    if not todoist_path.exists():
        return []
    return list(todoist_path.glob("*.md"))


def scan_todoist_completed_tasks_today(todoist_folder: str, timezone: pytz.tzinfo.BaseTzInfo) -> str:
    """Scan Todoist folder for tasks completed today.

    Args:
        todoist_folder: Path to the Todoist folder
        timezone: Timezone to use for date comparison

    Returns:
        Formatted string with today's completed tasks grouped by project
    """
    today = datetime.datetime.now(timezone).date()
    completed_by_project = {}

    todoist_files = get_todoist_files(todoist_folder)
    if not todoist_files:
        return "Todoist folder not found"

    for md_file in todoist_files:
        content = read_todoist_file(md_file)
        if not content:
            continue

        # Check if task is completed
        if not is_task_completed(content):
            continue

        # Extract title, todoist_id, project, and section from frontmatter
        title, todoist_id, project, section = parse_todoist_frontmatter(content)
        if not title or not todoist_id:
            continue

        # Check file modification time to see if completed today
        if is_file_modified_today(md_file, timezone):
            clean_title = clean_title_for_obsidian_link(title)
            task_entry = f"* [x] [[Todoist/{todoist_id}|{clean_title}]] ✅ {today}"

            # Create project key with section if available
            project_key = f"{project} - {section}" if section else project

            if project_key not in completed_by_project:
                completed_by_project[project_key] = []
            completed_by_project[project_key].append(task_entry)

    if not completed_by_project:
        return "No tasks completed today"

    # Format output by project and section
    result = []
    for project_key, tasks in sorted(completed_by_project.items()):
        result.append(f"**{project_key}:**")
        result.extend(tasks)
        result.append("")  # Empty line between sections

    # Remove trailing empty line
    if result and result[-1] == "":
        result.pop()

    return "\n".join(result)


def extract_comments_section(content: str) -> str | None:
    """Extract comments section from markdown content.

    Args:
        content: Markdown file content

    Returns:
        Comments section text or None if not found
    """
    comments_section = re.search(r"^## Comments\s*\n(.*?)(?=\n##|\Z)", content, re.MULTILINE | re.DOTALL)
    if not comments_section:
        return None
    return comments_section.group(1).strip()


def parse_comment_line(line: str) -> tuple[str | None, str | None]:
    """Parse comment line to extract date and text.

    Args:
        line: Comment line in format "* DD MMM HH:MM - comment text"

    Returns:
        Tuple of (date_str, comment_text) or (None, None) if parsing fails
    """
    comment_pattern = re.compile(r"^\* (\d{1,2} \w{3}) \d{2}:\d{2} - (.+)$")
    match = comment_pattern.match(line.strip())
    if match:
        return match.group(1), match.group(2)
    return None, None


def scan_todoist_comments_for_today(todoist_folder: str, timezone: pytz.tzinfo.BaseTzInfo) -> str:
    """Scan Todoist folder for comments made today.

    Args:
        todoist_folder: Path to the Todoist folder
        timezone: Timezone to use for date comparison

    Returns:
        Formatted string with today's comments grouped by project
    """
    today = datetime.datetime.now(timezone).strftime("%d %b")
    comments_by_project = {}

    todoist_files = get_todoist_files(todoist_folder)
    if not todoist_files:
        return "Todoist folder not found"

    for md_file in todoist_files:
        content = read_todoist_file(md_file)
        if not content:
            continue

        # Extract title, todoist_id, project, and section from frontmatter
        title, todoist_id, project, section = parse_todoist_frontmatter(content)
        if not title or not todoist_id:
            continue

        # Find Comments section
        comments_text = extract_comments_section(content)
        if not comments_text:
            continue

        # Find today's comments
        task_comments = []
        for line in comments_text.split("\n"):
            if not line.strip():
                continue

            comment_date, comment_text = parse_comment_line(line)
            if comment_date == today and comment_text:
                task_comments.append(f"\t* {comment_text}")

        if task_comments:
            clean_title = clean_title_for_obsidian_link(title)
            task_entry = [f"* [/] [[Todoist/{todoist_id}|{clean_title}]]"]
            task_entry.extend(task_comments)

            # Create project key with section if available
            project_key = f"{project} - {section}" if section else project

            if project_key not in comments_by_project:
                comments_by_project[project_key] = []
            comments_by_project[project_key].extend(task_entry)

    if not comments_by_project:
        return "No comments made today"

    # Format output by project and section
    result = []
    for project_key, comments in sorted(comments_by_project.items()):
        result.append(f"**{project_key}:**")
        result.extend(comments)
        result.append("")  # Empty line between sections

    # Remove trailing empty line
    if result and result[-1] == "":
        result.pop()

    return "\n".join(result)
