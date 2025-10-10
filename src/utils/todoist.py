"""Todoist utilities for processing Todoist markdown files and API interactions."""

import datetime
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

import structlog
from pydantic import BaseModel, Field

try:
    from todoist_api_python.api import TodoistAPI

    todoist_available = True
except ImportError:
    TodoistAPI = None
    todoist_available = False


class TodoistTaskFile(NamedTuple):
    """Todoist task file data."""

    title: str
    todoist_id: str
    completed: bool
    file_path: Path


class TodoistProject(BaseModel):
    """Represents a Todoist project."""

    id: str
    name: str
    color: str
    is_shared: bool = False
    url: str = ""

    @classmethod
    def from_api_project(cls, api_project: Any) -> "TodoistProject":
        """Create TodoistProject from the API project object."""
        return cls(
            id=api_project.id,
            name=api_project.name,
            color=api_project.color,
            is_shared=api_project.is_shared,
            url=api_project.url,
        )


class TodoistSection(BaseModel):
    """Represents a Todoist section."""

    id: str
    project_id: str
    name: str
    order: int

    @classmethod
    def from_api_section(cls, api_section: Any) -> "TodoistSection":
        """Create TodoistSection from the API section object."""
        return cls(
            id=api_section.id,
            project_id=api_section.project_id,
            name=api_section.name,
            order=api_section.order,
        )


class TodoistTask(BaseModel):
    """Represents a Todoist task."""

    id: str
    content: str
    description: str = ""
    project_id: str
    section_id: str | None = None
    parent_id: str | None = None
    order: int
    priority: int = 1
    labels: list[str] = Field(default_factory=list)
    due: dict[str, Any] | None = None
    url: str = ""

    is_completed: bool = False
    created_at: str
    completed_date: str | None = None
    creator_id: str = ""
    assignee_id: str | None = None
    assigner_id: str | None = None

    @property
    def due_date(self) -> str | None:
        """Extract due date as string if available."""
        if self.due and "date" in self.due:
            date_value = self.due["date"]
            return str(date_value) if date_value is not None else None
        return None

    @property
    def priority_text(self) -> str:
        """Convert priority number to text."""
        priority_map = {4: "High", 3: "Medium", 2: "Low", 1: "None"}
        return priority_map.get(self.priority, "None")

    @classmethod
    def from_api_task(
        cls, api_task: Any, is_completed: bool = False, completed_date: str | None = None
    ) -> "TodoistTask":
        """Create TodoistTask from the API task object."""
        # Convert due object to dict if present
        due_dict = None
        if api_task.due:
            due_dict = {
                "date": api_task.due.date,
                "string": getattr(api_task.due, "string", ""),
                "datetime": getattr(api_task.due, "datetime", None),
                "is_recurring": getattr(api_task.due, "is_recurring", False),
            }

        return cls(
            id=api_task.id,
            content=api_task.content,
            description=api_task.description or "",
            project_id=api_task.project_id,
            section_id=api_task.section_id,
            parent_id=api_task.parent_id,
            order=api_task.order,
            priority=api_task.priority,
            labels=api_task.labels or [],
            due=due_dict,
            url=api_task.url,
            is_completed=is_completed,
            created_at=str(api_task.created_at),
            completed_date=completed_date,
            creator_id=api_task.creator_id or "",
            assignee_id=api_task.assignee_id,
            assigner_id=api_task.assigner_id,
        )


class TodoistComment(BaseModel):
    """Represents a comment on a Todoist task."""

    id: str
    task_id: str
    content: str
    posted_at: str
    attachment: dict[str, Any] | None = None

    @classmethod
    def from_api_comment(cls, api_comment: Any) -> "TodoistComment":
        """Create TodoistComment from the API comment object."""
        attachment_dict = None
        if hasattr(api_comment, "attachment") and api_comment.attachment:
            attachment_dict = {
                "file_name": getattr(api_comment.attachment, "file_name", None),
                "file_type": getattr(api_comment.attachment, "file_type", None),
                "file_url": getattr(api_comment.attachment, "file_url", None),
                "resource_type": getattr(api_comment.attachment, "resource_type", None),
            }

        return cls(
            id=api_comment.id,
            task_id=api_comment.task_id or "",
            content=api_comment.content,
            posted_at=str(api_comment.posted_at),
            attachment=attachment_dict,
        )


class TodoistAPIError(Exception):
    """Custom exception for Todoist API errors."""

    pass


class TodoistClient:
    """Client for interacting with the Todoist REST API."""

    def __init__(self, api_token: str):
        """Initialize the Todoist client."""
        if not todoist_available:
            raise TodoistAPIError("todoist-api-python library is not available")
        self.api_token = api_token
        try:
            self._api = TodoistAPI(api_token)  # type: ignore
        except Exception as e:
            raise TodoistAPIError(f"Failed to initialize Todoist API client: {e}") from e

    def get_projects(self) -> list[TodoistProject]:
        """Fetch all projects."""
        try:
            api_projects_paginator = self._api.get_projects()
            all_projects = []
            for projects_page in api_projects_paginator:
                for project in projects_page:
                    all_projects.append(TodoistProject.from_api_project(project))
            return all_projects
        except Exception as e:
            raise TodoistAPIError(f"Failed to fetch projects: {e}") from e

    def get_sections(self, project_id: str | None = None) -> list[TodoistSection]:
        """Fetch sections, optionally filtered by project."""
        try:
            if project_id:
                api_sections_paginator = self._api.get_sections(project_id=project_id)
            else:
                api_sections_paginator = self._api.get_sections()

            all_sections = []
            for sections_page in api_sections_paginator:
                for section in sections_page:
                    all_sections.append(TodoistSection.from_api_section(section))
            return all_sections
        except Exception as e:
            raise TodoistAPIError(f"Failed to fetch sections: {e}") from e

    def get_tasks(self, project_id: str | None = None, filter_expr: str | None = None) -> list[TodoistTask]:
        """Fetch tasks, optionally filtered by project or filter expression."""
        try:
            if filter_expr:
                api_tasks_paginator = self._api.filter_tasks(query=filter_expr)
            elif project_id:
                api_tasks_paginator = self._api.get_tasks(project_id=project_id)
            else:
                api_tasks_paginator = self._api.get_tasks()

            all_tasks = []
            for tasks_page in api_tasks_paginator:
                for task in tasks_page:
                    all_tasks.append(TodoistTask.from_api_task(task))
            return all_tasks
        except Exception as e:
            raise TodoistAPIError(f"Failed to fetch tasks: {e}") from e

    def get_task_comments(self, task_id: str) -> list[TodoistComment]:
        """Fetch comments for a specific task."""
        try:
            comments_iterator = self._api.get_comments(task_id=task_id)
            all_comments = []
            for comments_page in comments_iterator:
                for comment in comments_page:
                    all_comments.append(TodoistComment.from_api_comment(comment))
            return all_comments
        except Exception as e:
            raise TodoistAPIError(f"Failed to fetch comments for task {task_id}: {e}") from e

    def get_completed_tasks_by_completion_date(self, completion_date: datetime.datetime) -> list[TodoistTask]:
        """Fetch completed tasks for a specific completion date."""
        try:
            start_time = completion_date.replace(hour=0, minute=0)
            end_time = completion_date.replace(hour=23, minute=59)
            completed_items_iterator = self._api.get_completed_tasks_by_completion_date(
                since=start_time, until=end_time
            )
            all_completed_tasks = []
            for items_page in completed_items_iterator:
                for item in items_page:
                    all_completed_tasks.append(
                        TodoistTask.from_api_task(item, is_completed=True, completed_date=completion_date.isoformat())
                    )
            print(f"Completed tasks fetched for date {completion_date.isoformat()}")
            print(f"Total completed tasks: {len(all_completed_tasks)}")
            return all_completed_tasks
        except Exception as e:
            raise TodoistAPIError(f"Failed to fetch completed tasks for date {completion_date.isoformat()}: {e}") from e


@dataclass
class ExportConfig:
    """Configuration for the export process."""

    output_dir: Path
    include_completed: bool = False
    include_comments: bool = True
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M"
    tag_prefix: str = "todoist"
    priority_as_tags: bool = True
    labels_as_tags: bool = True


class ObsidianExporter:
    """Export Todoist tasks as Obsidian markdown notes."""

    def __init__(self, config: ExportConfig):
        """Initialize the exporter with configuration."""
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename."""
        ascii_name = unicodedata.normalize("NFKD", name)
        ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", ascii_name)
        sanitized = re.sub(r"_+", "_", sanitized)
        sanitized = sanitized.strip("_ ")
        if len(sanitized) > 200:
            sanitized = sanitized[:200].rstrip("_")
        return sanitized or "untitled"

    def format_yaml_string(self, value: str) -> str:
        """Format a string value for safe YAML output."""
        if "'" in value and '"' not in value:
            return f'"{value}"'
        if '"' in value and "'" not in value:
            return f"'{value}'"
        if '"' in value or "'" in value or "\n" in value or "\t" in value or "\\" in value:
            escaped = value.replace("\\", "\\\\")
            escaped = escaped.replace('"', '\\"')
            escaped = escaped.replace("\n", "\\n")
            escaped = escaped.replace("\t", "\\t")
            return f'"{escaped}"'
        return f'"{value}"'

    def format_tags(self, task: TodoistTask, project: TodoistProject) -> list[str]:
        """Generate tags for a task."""
        tags = []
        tags.append(f"#{self.config.tag_prefix}")

        project_tag = self.sanitize_filename(project.name.lower().replace(" ", "-"))
        tags.append(f"#{self.config.tag_prefix}/{project_tag}")

        if self.config.priority_as_tags and task.priority > 1:
            priority_name = task.priority_text.lower()
            tags.append(f"#{self.config.tag_prefix}/priority/{priority_name}")

        if self.config.labels_as_tags:
            for label in task.labels:
                label_tag = self.sanitize_filename(label.lower().replace(" ", "-"))
                tags.append(f"#{self.config.tag_prefix}/label/{label_tag}")

        status = "completed" if task.is_completed else "active"
        tags.append(f"#{self.config.tag_prefix}/status/{status}")

        return tags

    def format_frontmatter(
        self,
        task: TodoistTask,
        project: TodoistProject,
        section: TodoistSection | None = None,
    ) -> str:
        """Generate YAML frontmatter for a task."""
        frontmatter = ["---"]
        frontmatter.append(f"title: {self.format_yaml_string(task.content)}")
        frontmatter.append(f"todoist_id: {self.format_yaml_string(task.id)}")
        frontmatter.append(f"project: {self.format_yaml_string(project.name)}")
        frontmatter.append(f'project_id: "{project.id}"')

        if section:
            frontmatter.append(f"section: {self.format_yaml_string(section.name)}")
            frontmatter.append(f'section_id: "{section.id}"')

        frontmatter.append(f'created: "{task.created_at}"')

        if task.due_date:
            frontmatter.append(f'due_date: "{task.due_date}"')

        frontmatter.append(f"priority: {task.priority}")
        frontmatter.append(f'priority_text: "{task.priority_text}"')

        if task.labels:
            labels_str = '", "'.join(task.labels)
            frontmatter.append(f'labels: ["{labels_str}"]')

        frontmatter.append(f"completed: {str(task.is_completed).lower()}")

        if task.completed_date:
            frontmatter.append(f'completed_date: "{task.completed_date}"')

        if task.url:
            frontmatter.append(f'todoist_url: "{task.url}"')

        tags = self.format_tags(task, project)
        if tags:
            tags_str = '", "'.join(tag.lstrip("#") for tag in tags)
            frontmatter.append(f'tags: ["{tags_str}"]')

        frontmatter.append("---")
        frontmatter.append("")
        return "\n".join(frontmatter)

    def format_task_content(
        self,
        task: TodoistTask,
        project: TodoistProject,
        comments: list[TodoistComment] | None = None,
        child_tasks: list[TodoistTask] | None = None,
        section: TodoistSection | None = None,
    ) -> str:
        """Format a task as markdown content."""
        content = []
        content.append(self.format_frontmatter(task, project, section))

        status_icon = "✅" if task.is_completed else "⬜"
        content.append(f"# {status_icon} {task.content}")
        content.append("")

        if task.description:
            content.append("## Description")
            content.append("")
            content.append(task.description)
            content.append("")

        if child_tasks:
            content.append("## Subtasks")
            content.append("")
            for child_task in sorted(child_tasks, key=lambda t: t.order):
                checkbox = "[x]" if child_task.is_completed else "[ ]"
                content.append(f"- {checkbox} {child_task.content}")
            content.append("")

        if comments and self.config.include_comments:
            content.append("## Comments")
            content.append("")
            for comment in comments:
                dt_object = datetime.datetime.fromisoformat(comment.posted_at.replace("Z", "+00:00"))
                formatted_datetime = dt_object.strftime("%d %b %H:%M")
                content.append(f"* {formatted_datetime} - {comment.content}")

        return "\n".join(content)

    def get_output_path(self, task: TodoistTask, project: TodoistProject) -> Path:  # noqa: ARG002
        """Determine the output path for a task note."""
        filename = task.id
        return self.output_dir / f"{filename}.md"

    def export_task(
        self,
        task: TodoistTask,
        project: TodoistProject,
        comments: list[TodoistComment] | None = None,
        child_tasks: list[TodoistTask] | None = None,
        section: TodoistSection | None = None,
    ) -> Path:
        """Export a single task as a markdown note."""
        output_path = self.get_output_path(task, project)

        if task.is_completed and not self.config.include_completed:
            return output_path

        # Preserve existing user content after ---
        existing_user_content = ""
        if output_path.exists():
            try:
                with open(output_path, encoding="utf-8") as f:
                    existing_content = f.read()

                lines = existing_content.split("\n")
                separators = []
                for i, line in enumerate(lines):
                    if line.strip() == "---":
                        separators.append(i)

                if len(separators) >= 3:
                    user_content_start = separators[2] + 1
                    user_lines = lines[user_content_start:]
                    if user_lines and any(line.strip() for line in user_lines):
                        existing_user_content = "\n".join(user_lines)
                        if existing_user_content.strip():
                            existing_user_content = "\n\n---\n\n" + existing_user_content
            except Exception:
                pass  # Ignore errors reading existing file

        new_content = self.format_task_content(task, project, comments, child_tasks, section)
        final_content = new_content + existing_user_content

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_content)

        return output_path


def export_tasks_internal(
    client: TodoistClient,
    export_config: ExportConfig,
    project_id: str | None = None,
    project_name: str | None = None,
    filter_expr: str | None = None,
    include_completed: bool = False,
) -> int:
    """Internal function to export tasks."""
    # Get projects
    projects = client.get_projects()
    projects_dict = {p.id: p for p in projects}

    # Get sections
    sections = client.get_sections()
    sections_dict = {s.id: s for s in sections}

    # Resolve project name to ID if needed
    target_project_id = project_id
    if project_name and not project_id:
        matching_projects = [p for p in projects if p.name.lower() == project_name.lower()]
        if not matching_projects:
            raise TodoistAPIError(f"Project '{project_name}' not found")
        target_project_id = matching_projects[0].id

    # Get tasks
    tasks = client.get_tasks(project_id=target_project_id, filter_expr=filter_expr)

    # Fetch completed tasks for today if include_completed is True
    if include_completed:
        today = datetime.datetime.now() - datetime.timedelta(days=1)
        completed_tasks_today = client.get_completed_tasks_by_completion_date(today)

        # Filter completed tasks by project_id if specified
        if target_project_id:
            completed_tasks_today = [t for t in completed_tasks_today if t.project_id == target_project_id]

        tasks.extend(completed_tasks_today)

    if not tasks:
        return 0

    # Group tasks by parent/child relationship
    parent_tasks = []
    child_tasks_by_parent: dict[str, list[TodoistTask]] = {}

    for task in tasks:
        # Skip tasks that start with *
        if task.content.startswith("*"):
            continue

        if task.parent_id:
            if task.parent_id not in child_tasks_by_parent:
                child_tasks_by_parent[task.parent_id] = []
            child_tasks_by_parent[task.parent_id].append(task)
        else:
            parent_tasks.append(task)

    # Initialize exporter
    exporter = ObsidianExporter(export_config)

    # Export only parent tasks
    exported_count = 0
    for task in parent_tasks:
        project = projects_dict.get(task.project_id)
        if not project:
            continue

        if task.is_completed and not include_completed:
            continue

        # Get child tasks for this parent
        child_tasks = child_tasks_by_parent.get(task.id, [])

        # Get comments if enabled
        comments = None
        if export_config.include_comments:
            try:
                comments = client.get_task_comments(task.id)
            except TodoistAPIError:
                comments = None  # Ignore comment fetch errors

        # Get section for this task
        section = sections_dict.get(task.section_id) if task.section_id else None

        # Export the task with its child tasks
        try:
            exporter.export_task(task, project, comments, child_tasks, section)
            exported_count += 1
        except Exception:
            pass  # Ignore export errors for individual tasks

    return exported_count


def parse_todoist_frontmatter(content: str) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Parse title, todoist_id, project, section, and completed_date from frontmatter.

    Args:
        content: File content with YAML frontmatter

    Returns:
        Tuple of (title, todoist_id, project, section, completed_date) or (None, None, None, None, None) if parsing fails
    """
    title_match = re.search(r'^title: "(.+)"$', content, re.MULTILINE)
    todoist_id_match = re.search(r'^todoist_id: "(.+)"$', content, re.MULTILINE)
    project_match = re.search(r'^project: "(.+)"$', content, re.MULTILINE)
    section_match = re.search(r'^section: "(.+)"$', content, re.MULTILINE)
    completed_match = re.search(r'^completed: "(.+)"$', content, re.MULTILINE)

    if not title_match or not todoist_id_match:
        return None, None, None, None, None

    title = title_match.group(1)
    todoist_id = todoist_id_match.group(1)
    project = project_match.group(1) if project_match else "Other"
    section = section_match.group(1) if section_match else None
    completed_date = completed_match.group(1) if completed_match else None

    return title, todoist_id, project, section, completed_date


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


def is_file_modified_today(file_path: Path, today: datetime.date) -> bool:
    """Check if file was modified today.

    Args:
        file_path: Path to the file

    Returns:
        True if file was modified today
    """
    file_stat = file_path.stat()
    file_modified_date = datetime.datetime.fromtimestamp(file_stat.st_mtime).date()
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


def scan_todoist_completed_tasks_today(todoist_folder: str, today: datetime.date) -> str:
    """Scan Todoist folder for tasks completed today.

    Args:
        todoist_folder: Path to the Todoist folder
        today: Date object representing today's date

    Returns:
        Formatted string with today's completed tasks grouped by project
    """
    log: structlog.BoundLogger = structlog.get_logger()
    completed_by_project = {}

    todoist_files = get_todoist_files(todoist_folder)
    if not todoist_files:
        return "Todoist folder not found"

    for md_file in todoist_files:
        content = read_todoist_file(md_file)
        if not content:
            continue

        # Extract frontmatter including completed_date
        title, todoist_id, project, section, completed_date_str = parse_todoist_frontmatter(content)
        if not title or not todoist_id or not completed_date_str:
            continue

        # Check if the task's completed_date matches today
        try:
            task_completed_date = datetime.datetime.fromisoformat(completed_date_str).date()
        except ValueError:
            # Handle cases where completed_date is not in ISO format
            log.warning(f"Invalid completed date format in {md_file}: {completed_date_str}")
            continue

        if task_completed_date == today:
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


def scan_todoist_comments_for_today(todoist_folder: str, today: datetime.date) -> str:
    """Scan Todoist folder for comments made today.

    Args:
        todoist_folder: Path to the Todoist folder
    Returns:
        Formatted string with today's comments grouped by project
    """
    today_str = today.strftime("%d %b")
    comments_by_project = {}

    todoist_files = get_todoist_files(todoist_folder)
    if not todoist_files:
        return "Todoist folder not found"

    for md_file in todoist_files:
        content = read_todoist_file(md_file)
        if not content:
            continue

        # Extract title, todoist_id, project, and section from frontmatter
        title, todoist_id, project, section, _ = parse_todoist_frontmatter(content)
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
            if comment_date == today_str and comment_text:
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
