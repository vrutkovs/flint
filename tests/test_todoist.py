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
    export_tasks_internal,
    extract_comments_section,
    get_todoist_files,
    is_file_modified_today,
    is_task_completed,
    parse_comment_line,
    parse_todoist_frontmatter,
    read_todoist_file,
    scan_todoist_comments_for_today,
    scan_todoist_completed_tasks_today,
    todoist_available,
)


class TestTodoistModels:
    """Test Todoist model classes."""

    def test_todoist_project_creation(self):
        """Test TodoistProject creation."""
        project = TodoistProject(
            id="123", name="Test Project", color="blue", is_shared=True, url="https://todoist.com/project/123"
        )

        assert project.id == "123"
        assert project.name == "Test Project"
        assert project.color == "blue"
        assert project.is_shared is True
        assert project.url == "https://todoist.com/project/123"

    def test_todoist_project_from_api_project(self):
        """Test creating TodoistProject from API object."""
        api_project = Mock()
        api_project.id = "456"
        api_project.name = "API Project"
        api_project.color = "red"
        api_project.is_shared = False
        api_project.url = "https://todoist.com/project/456"

        project = TodoistProject.from_api_project(api_project)

        assert project.id == "456"
        assert project.name == "API Project"
        assert project.color == "red"
        assert project.is_shared is False
        assert project.url == "https://todoist.com/project/456"

    def test_todoist_section_creation(self):
        """Test TodoistSection creation."""
        section = TodoistSection(id="sec1", project_id="proj1", name="Test Section", order=1)

        assert section.id == "sec1"
        assert section.project_id == "proj1"
        assert section.name == "Test Section"
        assert section.order == 1

    def test_todoist_task_creation(self):
        """Test TodoistTask creation."""
        task = TodoistTask(
            id="task1",
            content="Test task",
            description="Task description",
            project_id="proj1",
            section_id="sec1",
            parent_id=None,
            order=1,
            priority=3,
            labels=["urgent", "work"],
            due={"date": "2024-12-31", "string": "Dec 31"},
            url="https://todoist.com/task/task1",
            is_completed=False,
            created_at="2024-01-01T00:00:00Z",
            creator_id="user1",
        )

        assert task.id == "task1"
        assert task.content == "Test task"
        assert task.description == "Task description"
        assert task.priority == 3
        assert task.priority_text == "Medium"
        assert task.due_date == "2024-12-31"
        assert task.labels == ["urgent", "work"]

    def test_todoist_task_priority_text(self):
        """Test priority text conversion."""
        task_high = TodoistTask(
            id="1", content="High", project_id="p1", order=1, priority=4, created_at="2024-01-01T00:00:00Z"
        )
        task_medium = TodoistTask(
            id="2", content="Medium", project_id="p1", order=1, priority=3, created_at="2024-01-01T00:00:00Z"
        )
        task_low = TodoistTask(
            id="3", content="Low", project_id="p1", order=1, priority=2, created_at="2024-01-01T00:00:00Z"
        )
        task_none = TodoistTask(
            id="4", content="None", project_id="p1", order=1, priority=1, created_at="2024-01-01T00:00:00Z"
        )

        assert task_high.priority_text == "High"
        assert task_medium.priority_text == "Medium"
        assert task_low.priority_text == "Low"
        assert task_none.priority_text == "None"

    def test_todoist_comment_creation(self):
        """Test TodoistComment creation."""
        comment = TodoistComment(
            id="comment1",
            task_id="task1",
            content="This is a comment",
            posted_at="2024-01-01T12:00:00Z",
            attachment={"file_name": "test.pdf", "file_url": "https://example.com/test.pdf"},
        )

        assert comment.id == "comment1"
        assert comment.task_id == "task1"
        assert comment.content == "This is a comment"
        assert comment.posted_at == "2024-01-01T12:00:00Z"
        assert comment.attachment is not None
        assert comment.attachment["file_name"] == "test.pdf"


class TestTodoistClient:
    """Test TodoistClient class."""

    def test_client_init_without_library(self):
        """Test client initialization when library is not available."""
        with (
            patch("utils.todoist.todoist_available", False),
            pytest.raises(TodoistAPIError, match="todoist-api-python library is not available"),
        ):
            TodoistClient("fake-token")

    @patch("utils.todoist.todoist_available", True)
    @patch("utils.todoist.TodoistAPI")
    def test_client_init_success(self, mock_api):
        """Test successful client initialization."""
        client = TodoistClient("test-token")
        assert client.api_token == "test-token"
        mock_api.assert_called_once_with("test-token")

    @patch("utils.todoist.todoist_available", True)
    @patch("utils.todoist.TodoistAPI")
    def test_client_init_failure(self, mock_api):
        """Test client initialization failure."""
        mock_api.side_effect = Exception("API Error")

        with pytest.raises(TodoistAPIError, match="Failed to initialize Todoist API client"):
            TodoistClient("test-token")

    @patch("utils.todoist.todoist_available", True)
    @patch("utils.todoist.TodoistAPI")
    def test_get_projects_success(self, mock_api):
        """Test successful project fetching."""
        mock_project = Mock()
        mock_project.id = "proj1"
        mock_project.name = "Test Project"
        mock_project.color = "blue"
        mock_project.is_shared = False
        mock_project.url = "https://example.com"

        mock_api_instance = Mock()
        mock_api_instance.get_projects.return_value = [[mock_project]]
        mock_api.return_value = mock_api_instance

        client = TodoistClient("test-token")
        projects = client.get_projects()

        assert len(projects) == 1
        assert projects[0].id == "proj1"
        assert projects[0].name == "Test Project"

    @patch("utils.todoist.todoist_available", True)
    @patch("utils.todoist.TodoistAPI")
    def test_get_projects_failure(self, mock_api):
        """Test project fetching failure."""
        mock_api_instance = Mock()
        mock_api_instance.get_projects.side_effect = Exception("API Error")
        mock_api.return_value = mock_api_instance

        client = TodoistClient("test-token")

        with pytest.raises(TodoistAPIError, match="Failed to fetch projects"):
            client.get_projects()


class TestExportConfig:
    """Test ExportConfig dataclass."""

    def test_export_config_defaults(self):
        """Test ExportConfig default values."""
        config = ExportConfig(output_dir=Path("/tmp"))

        assert config.output_dir == Path("/tmp")
        assert config.include_completed is False
        assert config.include_comments is True
        assert config.date_format == "%Y-%m-%d"
        assert config.time_format == "%H:%M"
        assert config.tag_prefix == "todoist"
        assert config.priority_as_tags is True
        assert config.labels_as_tags is True

    def test_export_config_custom_values(self):
        """Test ExportConfig with custom values."""
        config = ExportConfig(
            output_dir=Path("/custom"), include_completed=True, include_comments=False, tag_prefix="custom"
        )

        assert config.output_dir == Path("/custom")
        assert config.include_completed is True
        assert config.include_comments is False
        assert config.tag_prefix == "custom"


class TestObsidianExporter:
    """Test ObsidianExporter class."""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        with TemporaryDirectory() as temp_dir:
            config = ExportConfig(output_dir=Path(temp_dir))
            exporter = ObsidianExporter(config)

            assert exporter.sanitize_filename("Normal Name") == "Normal Name"
            assert exporter.sanitize_filename("Name/with*special?chars") == "Name_with_special_chars"
            assert exporter.sanitize_filename("   Name with spaces   ") == "Name with spaces"
            assert exporter.sanitize_filename("") == "untitled"

    def test_format_yaml_string(self):
        """Test YAML string formatting."""
        with TemporaryDirectory() as temp_dir:
            config = ExportConfig(output_dir=Path(temp_dir))
            exporter = ObsidianExporter(config)

            assert exporter.format_yaml_string("simple") == '"simple"'
            assert exporter.format_yaml_string("has'quote") == '"has\'quote"'
            assert exporter.format_yaml_string('has"quote') == "'has\"quote'"
            assert exporter.format_yaml_string("has\"both'quotes") == '"has\\"both\'quotes"'

    def test_format_tags(self):
        """Test tag formatting."""
        with TemporaryDirectory() as temp_dir:
            config = ExportConfig(output_dir=Path(temp_dir), tag_prefix="test")
            exporter = ObsidianExporter(config)

            project = TodoistProject(id="1", name="Work Project", color="blue")
            task = TodoistTask(
                id="1",
                content="Test",
                project_id="1",
                order=1,
                priority=3,
                labels=["urgent"],
                created_at="2024-01-01T00:00:00Z",
            )

            tags = exporter.format_tags(task, project)

            assert "#test" in tags
            assert "#test/work-project" in tags
            assert "#test/priority/medium" in tags
            assert "#test/label/urgent" in tags
            assert "#test/status/active" in tags

    def test_format_frontmatter(self):
        """Test frontmatter formatting."""
        with TemporaryDirectory() as temp_dir:
            config = ExportConfig(output_dir=Path(temp_dir))
            exporter = ObsidianExporter(config)

            project = TodoistProject(id="1", name="Test Project", color="blue")
            task = TodoistTask(
                id="task1",
                content="Test Task",
                project_id="1",
                order=1,
                priority=2,
                labels=["work"],
                created_at="2024-01-01T00:00:00Z",
                due={"date": "2024-12-31"},
            )

            frontmatter = exporter.format_frontmatter(task, project)

            assert "---" in frontmatter
            assert 'title: "Test Task"' in frontmatter
            assert 'todoist_id: "task1"' in frontmatter
            assert 'project: "Test Project"' in frontmatter
            assert 'due_date: "2024-12-31"' in frontmatter
            assert "priority: 2" in frontmatter


class TestUtilityFunctions:
    """Test utility functions."""

    def test_clean_title_for_obsidian_link(self):
        """Test title cleaning for Obsidian links."""
        assert clean_title_for_obsidian_link("Simple Title") == "Simple Title"
        assert clean_title_for_obsidian_link("Title with @special #chars!") == "Title with special chars"
        assert clean_title_for_obsidian_link("   Title with spaces   ") == "Title with spaces"

    def test_parse_todoist_frontmatter_valid(self):
        """Test parsing valid frontmatter."""
        content = """---
title: "Test Task"
todoist_id: "123456"
project: "Work"
section: "Current Sprint"
---

# Task content here"""

        title, todoist_id, project, section = parse_todoist_frontmatter(content)

        assert title == "Test Task"
        assert todoist_id == "123456"
        assert project == "Work"
        assert section == "Current Sprint"

    def test_parse_todoist_frontmatter_minimal(self):
        """Test parsing frontmatter with minimal fields."""
        content = """---
title: "Minimal Task"
todoist_id: "789"
---

# Task content"""

        title, todoist_id, project, section = parse_todoist_frontmatter(content)

        assert title == "Minimal Task"
        assert todoist_id == "789"
        assert project == "Other"
        assert section is None

    def test_parse_todoist_frontmatter_invalid(self):
        """Test parsing invalid frontmatter."""
        content = """---
invalid: "content"
---"""

        title, todoist_id, project, section = parse_todoist_frontmatter(content)

        assert title is None
        assert todoist_id is None
        assert project is None
        assert section is None

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

    def test_is_file_modified_today(self):
        """Test file modification date checking."""
        today = datetime.datetime.now()

        with TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.md"
            test_file.write_text("test content")

            # File should be modified today since we just created it
            assert is_file_modified_today(test_file, today) is True

    def test_extract_comments_section(self):
        """Test extracting comments section."""
        content = """# Task Title

## Description
Task description here.

## Comments

* 14 Mar 10:30 - First comment
* 14 Mar 15:45 - Second comment

## Other Section
Other content."""

        comments = extract_comments_section(content)
        expected = "* 14 Mar 10:30 - First comment\n* 14 Mar 15:45 - Second comment"
        assert comments == expected

    def test_extract_comments_section_not_found(self):
        """Test extracting comments when section doesn't exist."""
        content = """# Task Title

## Description
No comments here."""

        comments = extract_comments_section(content)
        assert comments is None

    def test_parse_comment_line_valid(self):
        """Test parsing valid comment lines."""
        line = "* 14 Mar 10:30 - This is a comment"
        date, text = parse_comment_line(line)

        assert date == "14 Mar"
        assert text == "This is a comment"

    def test_parse_comment_line_invalid(self):
        """Test parsing invalid comment lines."""
        line = "Invalid comment format"
        date, text = parse_comment_line(line)

        assert date is None
        assert text is None

    def test_get_todoist_files(self):
        """Test getting list of Todoist files."""
        with TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "task1.md").write_text("Task 1")
            (Path(temp_dir) / "task2.md").write_text("Task 2")
            (Path(temp_dir) / "other.txt").write_text("Not a markdown file")

            files = get_todoist_files(temp_dir)

            assert len(files) == 2
            assert all(f.suffix == ".md" for f in files)

    def test_get_todoist_files_nonexistent(self):
        """Test getting files from nonexistent directory."""
        files = get_todoist_files("/nonexistent/path")
        assert files == []

    def test_read_todoist_file_success(self):
        """Test reading Todoist file successfully."""
        with TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.md"
            test_content = "Test content"
            test_file.write_text(test_content)

            content = read_todoist_file(test_file)
            assert content == test_content

    def test_read_todoist_file_failure(self):
        """Test reading nonexistent file."""
        content = read_todoist_file(Path("/nonexistent/file.md"))
        assert content is None


class TestIntegrationFunctions:
    """Test integration functions that combine multiple utilities."""

    def test_scan_todoist_completed_tasks_today(self):
        """Test scanning for completed tasks today."""
        today = datetime.datetime.now().date()

        with TemporaryDirectory() as temp_dir:
            # Create a completed task file
            task_content = """---
title: "Completed Task"
todoist_id: "123"
project: "Work"
section: "Done"
completed: true
---

# ✅ Completed Task"""

            task_file = Path(temp_dir) / "123.md"
            task_file.write_text(task_content)

            result = scan_todoist_completed_tasks_today(temp_dir, today)

            assert "Work - Done:" in result
            assert "Completed Task" in result
            assert str(today) in result

    def test_scan_todoist_comments_for_today(self):
        """Test scanning for comments made today."""
        today = datetime.datetime.now().strftime("%d %b")

        with TemporaryDirectory() as temp_dir:
            # Create a task file with today's comments
            task_content = f"""---
title: "Task with Comments"
todoist_id: "456"
project: "Personal"
---

# Task with Comments

## Comments

* {today} 10:30 - Comment from today
* 13 Mar 15:45 - Old comment"""

            task_file = Path(temp_dir) / "456.md"
            task_file.write_text(task_content)

            result = scan_todoist_comments_for_today(temp_dir)

            assert "Personal:" in result
            assert "Task with Comments" in result
            assert "Comment from today" in result
            assert "Old comment" not in result


@pytest.mark.skipif(not todoist_available, reason="todoist-api-python not available")
class TestExportTasksInternal:
    """Test the export_tasks_internal function."""

    @patch("utils.todoist.TodoistAPI")
    def test_export_tasks_internal_basic(self, mock_api):
        """Test basic task export functionality."""
        # Mock API responses
        mock_project = Mock()
        mock_project.id = "proj1"
        mock_project.name = "Test Project"
        mock_project.color = "blue"
        mock_project.is_shared = False
        mock_project.url = "https://example.com"

        mock_task = Mock()
        mock_task.id = "task1"
        mock_task.content = "Test Task"
        mock_task.description = ""
        mock_task.project_id = "proj1"
        mock_task.section_id = None
        mock_task.parent_id = None
        mock_task.order = 1
        mock_task.priority = 1
        mock_task.labels = []
        mock_task.due = None
        mock_task.url = "https://example.com/task1"
        mock_task.created_at = "2024-01-01T00:00:00Z"
        mock_task.creator_id = "user1"
        mock_task.assignee_id = None
        mock_task.assigner_id = None

        mock_api_instance = Mock()
        mock_api_instance.get_projects.return_value = [[mock_project]]
        mock_api_instance.get_sections.return_value = [[]]
        mock_api_instance.get_tasks.return_value = [[mock_task]]
        mock_api_instance.get_comments.return_value = [[]]
        mock_api.return_value = mock_api_instance

        with TemporaryDirectory() as temp_dir:
            config = ExportConfig(output_dir=Path(temp_dir))
            client = TodoistClient("test-token")

            exported_count = export_tasks_internal(client, config)

            assert exported_count == 1

            # Check that file was created
            task_file = Path(temp_dir) / "task1.md"
            assert task_file.exists()

            content = task_file.read_text()
            assert "Test Task" in content
            assert "Test Project" in content

    @patch("utils.todoist.TodoistAPI")
    def test_export_tasks_internal_no_tasks(self, mock_api):
        """Test export when no tasks are found."""
        mock_api_instance = Mock()
        mock_api_instance.get_projects.return_value = [[]]
        mock_api_instance.get_sections.return_value = [[]]
        mock_api_instance.get_tasks.return_value = [[]]
        mock_api.return_value = mock_api_instance

        with TemporaryDirectory() as temp_dir:
            config = ExportConfig(output_dir=Path(temp_dir))
            client = TodoistClient("test-token")

            exported_count = export_tasks_internal(client, config)

            assert exported_count == 0
