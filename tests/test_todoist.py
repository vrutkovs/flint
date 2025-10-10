"""Tests for todoist utilities."""

import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from utils.todoist import (
    ExportConfig,
    ObsidianExporter,
    TodoistAPIError,
    TodoistClient,
    TodoistComment,
    TodoistProject,
    TodoistSection,
    TodoistTask,
    clean_title_for_obsidian_link,
    extract_comments_section,
    get_todoist_files,
    is_task_completed,
    parse_comment_line,
    parse_todoist_frontmatter,
    read_todoist_file,
)


class TestTodoistModels:
    """Test Todoist model creation and conversions."""

    def test_todoist_project_creation(self):
        """Test TodoistProject creation."""
        project = TodoistProject(id="1", name="Test Project", color="blue", is_shared=False, url="test.url")
        assert project.id == "1"
        assert project.name == "Test Project"
        assert project.color == "blue"
        assert project.is_shared is False
        assert project.url == "test.url"

    def test_todoist_project_from_api_project(self):
        """Test TodoistProject creation from API project."""
        mock_api_project = Mock(id="api1", name="API Project", color="green", is_shared=True, url="api.url")
        project = TodoistProject.from_api_project(mock_api_project)
        assert project.id == "api1"
        assert project.name == "API Project"
        assert project.color == "green"
        assert project.is_shared is True
        assert project.url == "api.url"

    def test_todoist_section_creation(self):
        """Test TodoistSection creation."""
        section = TodoistSection(id="1", name="Test Section", project_id="p1", order=1)
        assert section.id == "1"
        assert section.name == "Test Section"
        assert section.project_id == "p1"
        assert section.order == 1

    def test_todoist_task_creation(self):
        """Test TodoistTask creation and properties."""
        now = datetime.datetime.now(datetime.UTC)
        task = TodoistTask(
            id="t1",
            content="Buy groceries",
            description="Milk, eggs, bread",
            project_id="p1",
            section_id="s1",
            order=1,
            priority=2,
            labels=["shopping", "home"],
            due={"date": "2023-01-01", "string": "tomorrow", "datetime": None, "is_recurring": False},
            is_completed=False,
            created_at=now.isoformat(),
            completed_date=None,
        )
        assert task.id == "t1"
        assert task.content == "Buy groceries"
        assert task.description == "Milk, eggs, bread"
        assert task.project_id == "p1"
        assert task.section_id == "s1"
        assert task.order == 1
        assert task.priority == 2
        assert task.labels == ["shopping", "home"]
        assert task.due == {"date": "2023-01-01", "string": "tomorrow", "datetime": None, "is_recurring": False}
        assert task.is_completed is False
        assert task.created_at == now.isoformat()
        assert task.completed_date is None
        assert task.due_date == datetime.date(2023, 1, 1)

    def test_todoist_task_priority_text(self):
        """Test task priority text representation."""
        now = datetime.datetime.now(datetime.UTC).isoformat()
        task_p1 = TodoistTask(id="1", content="Task", project_id="p1", order=1, created_at=now, priority=1)
        task_p2 = TodoistTask(id="1", content="Task", project_id="p1", order=1, created_at=now, priority=2)
        task_p3 = TodoistTask(id="1", content="Task", project_id="p1", order=1, created_at=now, priority=3)
        task_p4 = TodoistTask(id="1", content="Task", project_id="p1", order=1, created_at=now, priority=4)

        assert task_p1.priority_text == "None"
        assert task_p2.priority_text == "Low"
        assert task_p3.priority_text == "Medium"
        assert task_p4.priority_text == "High"

    def test_todoist_comment_creation(self):
        """Test TodoistComment creation."""
        now = datetime.datetime.now(datetime.UTC)
        comment = TodoistComment(
            id="c1",
            task_id="t1",
            content="First comment",
            posted_at=now.isoformat(),
            attachment=None,
        )
        assert comment.id == "c1"
        assert comment.task_id == "t1"
        assert comment.content == "First comment"
        assert comment.posted_at == now.isoformat()
        assert comment.attachment is None


class TestTodoistClient:
    """Test TodoistClient functionality."""

    def _get_api_client(self, client):
        """Helper to access _api for testing."""
        return client._api

    def test_client_init_without_library(self):
        """Test client initialization when todoist library is unavailable."""
        with patch("flint.src.utils.todoist.todoist_available", False):
            client = TodoistClient("fake_token")
            assert self._get_api_client(client) is None

    def test_client_init_success(self):
        """Test successful client initialization."""
        with (
            patch("flint.src.utils.todoist.todoist_available", True),
            patch("todoist_api_python.TodoistAPI") as mock_api,
        ):
            client = TodoistClient("test_token")
            mock_api.assert_called_once_with("test_token")
            assert self._get_api_client(client) is not None

    def test_client_init_failure(self):
        """Test client initialization failure."""
        with (
            patch("flint.src.utils.todoist.todoist_available", True),
            patch("todoist_api_python.TodoistAPI", side_effect=Exception("API error")),
            pytest.raises(TodoistAPIError),
        ):
            TodoistClient("test_token")

    @patch("flint.src.utils.todoist.todoist_available", True)
    @patch("todoist_api_python.TodoistAPI")
    def test_get_projects_success(self, mock_api_class):
        """Test getting projects successfully."""
        mock_api = mock_api_class.return_value
        mock_api.get_projects.return_value = [Mock(id="p1", name="Project 1")]

        client = TodoistClient("test_token")
        projects = client.get_projects()

        mock_api.get_projects.assert_called_once()
        assert len(projects) == 1
        assert projects[0].id == "p1"

    @patch("flint.src.utils.todoist.todoist_available", True)
    @patch("todoist_api_python.TodoistAPI")
    def test_get_projects_failure(self, mock_api_class):
        """Test getting projects with API error."""
        mock_api = mock_api_class.return_value
        mock_api.get_projects.side_effect = Exception("Network error")

        client = TodoistClient("test_token")
        with pytest.raises(TodoistAPIError):
            client.get_projects()


class TestExportConfig:
    """Test ExportConfig dataclass."""

    def test_export_config_defaults(self):
        """Test default values of ExportConfig."""
        config = ExportConfig(output_dir=Path("/tmp"))
        assert config.output_dir == Path("/tmp")
        assert config.include_completed is False
        assert config.include_comments is True
        assert config.tag_prefix is None
        assert config.sync_completed_tasks is False

    def test_export_config_custom_values(self):
        """Test custom values of ExportConfig."""
        config = ExportConfig(
            output_dir=Path("/home/user/obsidian"),
            include_completed=True,
            include_comments=True,
            tag_prefix="td",
        )
        assert config.output_dir == Path("/home/user/obsidian")
        assert config.include_completed is True
        assert config.include_comments is True
        assert config.tag_prefix == "td"
        assert config.include_completed is True


class TestObsidianExporter:
    """Test ObsidianExporter functionality."""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        exporter = ObsidianExporter(ExportConfig(output_dir=Path("/tmp/vault")))
        assert exporter.sanitize_filename("My Task Name") == "My Task Name"
        assert exporter.sanitize_filename("Task / with : illegal \\ chars") == "Task - with - illegal - chars"
        assert exporter.sanitize_filename("  Leading and trailing spaces  ") == "Leading and trailing spaces"

    def test_format_yaml_string(self):
        """Test YAML string formatting."""
        exporter = ObsidianExporter(ExportConfig(output_dir=Path("/tmp/vault")))
        assert exporter.format_yaml_string("test_value") == '"test_value"'
        assert exporter.format_yaml_string("value with 'single quotes'") == "\"value with 'single quotes'\""
        assert exporter.format_yaml_string('value with "double quotes"') == "'value with \"double quotes\"'"
        assert exporter.format_yaml_string("value with\\nnewline") == '"value with\\nnewline"'

    def test_format_tags(self):
        """Test tag formatting."""
        now = datetime.datetime.now(datetime.UTC).isoformat()
        mock_task = TodoistTask(
            id="1", content="Task", project_id="p1", order=1, created_at=now, labels=["label1", "label with spaces"]
        )
        mock_project = TodoistProject(id="p1", name="Project A", color="red", is_shared=False)

        exporter_with_prefix = ObsidianExporter(ExportConfig(output_dir=Path("/tmp/vault"), tag_prefix="td"))

        assert exporter_with_prefix.format_tags(mock_task, mock_project) == [
            "td/Project-A",
            "td/label1",
            "td/label-with-spaces",
        ]

        # Test with no labels
        mock_task_no_labels = TodoistTask(id="2", content="Task", project_id="p1", order=1, created_at=now, labels=[])
        assert exporter_with_prefix.format_tags(mock_task_no_labels, mock_project) == ["td/Project-A"]

    def test_format_frontmatter(self):
        """Test frontmatter formatting."""
        today = datetime.datetime(2023, 1, 1)
        task = TodoistTask(
            id="1",
            content="Test Task",
            description="A description",
            project_id="p1",
            section_id="s1",
            order=1,
            priority=4,
            labels=["work", "urgent"],
            due={"date": today.strftime("%Y-%m-%d"), "string": "today", "datetime": None, "is_recurring": False},
            is_completed=False,
            created_at="2023-01-01T12:00:00Z",
            completed_date=None,
        )
        project = TodoistProject(
            id="p1", name="Work", color="red", is_shared=False, url="https://todoist.com/project/p1"
        )
        section = TodoistSection(id="s1", name="Inbox", project_id="p1", order=1)

        exporter = ObsidianExporter(ExportConfig(output_dir=Path("/tmp/vault"), tag_prefix="td"))
        frontmatter = exporter.format_frontmatter(task, project, section)

        expected_frontmatter_incomplete = (
            "---\n"
            'title: "Test Task"\n'
            'todoist_id: "1"\n'
            'project: "Work"\n'
            'project_id: "p1"\n'
            'section: "Inbox"\n'
            'section_id: "s1"\n'
            'created: "2023-01-01T12:00:00Z"\n'
            f'due_date: "{today.strftime("%Y-%m-%d")}"\n'
            "priority: 4\n"
            'priority_text: "High"\n'
            'labels: ["work", "urgent"]\n'
            "completed: false\n"
            'tags: ["td/Work", "td/work", "td/urgent"]\n'
            "---"
        )
        assert frontmatter.strip() == expected_frontmatter_incomplete.strip()

        # Test for a completed task
        completed_task = TodoistTask(
            id="2",
            content="Completed Task",
            description="",
            project_id="p1",
            section_id="s1",
            order=2,
            priority=1,
            labels=[],
            due=None,
            is_completed=True,
            created_at="2023-01-01T12:00:00Z",
            completed_date="2023-01-02",
        )
        completed_frontmatter = exporter.format_frontmatter(completed_task, project, section)
        expected_frontmatter_complete = (
            "---\n"
            'title: "Completed Task"\n'
            'todoist_id: "2"\n'
            'project: "Work"\n'
            'project_id: "p1"\n'
            'section: "Inbox"\n'
            'section_id: "s1"\n'
            'created: "2023-01-01T12:00:00Z"\n'
            "priority: 1\n"
            'priority_text: "None"\n'
            "completed: true\n"
            'completed_date: "2023-01-02"\n'
            'tags: ["td/Work"]\n'
            "---"
        )
        assert completed_frontmatter.strip() == expected_frontmatter_complete.strip()


class TestUtilityFunctions:
    """Test utility functions for Todoist integration."""

    def test_clean_title_for_obsidian_link(self):
        """Test cleaning titles for Obsidian links."""
        assert clean_title_for_obsidian_link("My Task Name") == "My Task Name"
        assert clean_title_for_obsidian_link("Task / with : illegal \\ chars") == "Task - with - illegal - chars"
        assert clean_title_for_obsidian_link("  Leading and trailing spaces  ") == "Leading and trailing spaces"

    def test_parse_todoist_frontmatter_valid(self):
        """Test parsing valid Todoist frontmatter."""
        content = """---
title: "My Task"
todoist_id: "12345"
project: "Work"
section: "Meetings"
completed_date: "2023-01-01"
---
Task content
"""
        title, todoist_id, project, section, completed_date = parse_todoist_frontmatter(content)
        assert title == "My Task"
        assert todoist_id == "12345"
        assert project == "Work"
        assert section == "Meetings"
        assert completed_date == "2023-01-01"

    def test_parse_todoist_frontmatter_minimal(self):
        """Test parsing minimal Todoist frontmatter."""
        content = """---
title: "Another Task"
todoist_id: "67890"
---
Task content
"""
        title, todoist_id, project, section, completed_date = parse_todoist_frontmatter(content)
        assert title == "Another Task"
        assert todoist_id == "67890"
        assert project is None
        assert section is None
        assert completed_date is None

    def test_parse_todoist_frontmatter_invalid(self):
        """Test parsing invalid Todoist frontmatter."""
        content = """---
invalid: "content"
---"""
        title, todoist_id, project, section, completed_date = parse_todoist_frontmatter(content)
        assert title is None
        assert todoist_id is None
        assert project is None
        assert section is None
        assert completed_date is None

    def test_is_task_completed_true(self):
        """Test detecting completed tasks."""
        content = """---
completed: true
---"""
        assert is_task_completed(content) is True

    def test_is_task_completed_false(self):
        """Test detecting incomplete tasks."""
        content = """---
completed: false
---"""
        assert is_task_completed(content) is False

    def test_extract_comments_section(self):
        """Test extracting the comments section from content."""
        content = """
# Task Title

Some task description.

## Comments
- Comment 1
- Comment 2
"""
        expected_comments = """- Comment 1
- Comment 2"""
        assert extract_comments_section(content) == expected_comments

    def test_extract_comments_section_not_found(self):
        """Test extracting comments when section is not found."""
        content = """
# Task Title

Some task description.
"""
        assert extract_comments_section(content) is None

    def test_parse_comment_line_valid(self):
        """Test parsing a valid comment line."""
        line = "- 2023-01-01: This is a comment."
        date, comment = parse_comment_line(line)
        assert date == "2023-01-01"
        assert comment == "This is a comment."

    def test_parse_comment_line_invalid(self):
        """Test parsing an invalid comment line."""
        line = "This is not a valid comment line."
        date, comment = parse_comment_line(line)
        assert date is None
        assert comment is None

    def test_get_todoist_files_nonexistent(self):
        """Test getting Todoist files from a nonexistent directory."""
        nonexistent_path = Path("/nonexistent/path/to/vault")
        assert get_todoist_files(str(nonexistent_path)) == []

    def test_read_todoist_file_success(self):
        """Test successful reading of a Todoist file."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "test_task.md"
            file_path.write_text('---\ntodoist_id: "123"\n---\nContent')
            task_file = read_todoist_file(file_path)
            assert task_file is not None  # Ensure a TodoistTaskFile object was returned
            assert task_file == file_path

    def test_read_todoist_file_failure(self):
        """Test reading a non-existent file."""
        nonexistent_file = Path("/nonexistent/file.md")
        assert read_todoist_file(nonexistent_file) is None
