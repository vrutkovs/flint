"""Unit tests for the Telega class."""

import io
import os
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest
import yaml
from telegram import Animation, Chat, Document, Message, PhotoSize, Sticker, Update, User, Video
from telegram.ext import ContextTypes

from src.plugins.mcp import MCPClient, MCPConfigReader, MCPConfiguration, StdioServerParameters
from telega.main import Telega
from telega.settings import Settings


class TestTelega:
    """Test cases for the Telega class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.logger = Mock()
        settings.user_filter = []
        settings.genai_client = Mock()
        settings.model_name = "test-model"
        settings.genconfig = Mock()
        settings.qa_chain = None
        return settings

    @pytest.fixture
    def telega(self, mock_settings):
        """Create Telega instance with mock settings."""
        with patch("telega.main.MCPConfigReader"):
            return Telega(mock_settings)

    @pytest.fixture
    def mock_update(self):
        """Create mock update object."""
        update = Mock(spec=Update)
        update.update_id = 12345
        update.message = Mock(spec=Message)
        update.effective_user = Mock(spec=User)
        update.effective_user.username = "testuser"
        update.effective_chat = Mock(spec=Chat)
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context object."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = AsyncMock()
        context.args = []
        return context

    def test_telega_initialization(self, mock_settings):
        """Test Telega initialization."""
        with patch("telega.main.MCPConfigReader") as mock_mcp_reader:
            telega = Telega(mock_settings)

            assert telega.settings == mock_settings
            mock_mcp_reader.assert_called_once_with(mock_settings)
            assert telega.mcps == mock_mcp_reader.return_value

    @pytest.mark.asyncio
    async def test_download_file_with_photo(self, telega, mock_update, mock_context):
        """Test downloading a photo file."""
        # Setup photo
        photo = Mock(spec=PhotoSize)
        photo.file_id = "photo123"
        mock_update.message.photo = [photo]
        mock_update.message.document = None
        mock_update.message.video = None
        mock_update.message.sticker = None
        mock_update.message.animation = None

        # Setup file object
        mock_file = AsyncMock()
        mock_file.download_to_memory = AsyncMock()
        mock_context.bot.get_file.return_value = mock_file

        # Execute
        result = await telega.download_file(mock_update, mock_context)

        # Verify
        assert isinstance(result, io.BytesIO)
        mock_context.bot.get_file.assert_called_once_with("photo123")
        mock_file.download_to_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_file_with_document(self, telega, mock_update, mock_context):
        """Test downloading a document file."""
        # Setup document
        document = Mock(spec=Document)
        document.file_id = "doc456"
        mock_update.message.photo = None
        mock_update.message.document = document
        mock_update.message.video = None
        mock_update.message.sticker = None
        mock_update.message.animation = None

        # Setup file object
        mock_file = AsyncMock()
        mock_file.download_to_memory = AsyncMock()
        mock_context.bot.get_file.return_value = mock_file

        # Execute
        result = await telega.download_file(mock_update, mock_context)

        # Verify
        assert isinstance(result, io.BytesIO)
        mock_context.bot.get_file.assert_called_once_with("doc456")

    @pytest.mark.asyncio
    async def test_download_file_no_message(self, telega, mock_update, mock_context):
        """Test download_file with no message."""
        mock_update.message = None

        result = await telega.download_file(mock_update, mock_context)

        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_exception(self, telega, mock_update, mock_context):
        """Test download_file with exception."""
        mock_update.message.photo = [Mock(file_id="photo123")]
        mock_context.bot.get_file.side_effect = Exception("Download failed")

        with patch("telega.main.format_exc_info") as mock_format_exc:
            mock_format_exc.return_value = {"error": "test"}
            result = await telega.download_file(mock_update, mock_context)

        assert result is None
        telega.settings.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_is_user_allowed_no_filter(self, telega, mock_update):
        """Test user allowed when no filter is set."""
        telega.settings.user_filter = []

        result = await telega.is_user_allowed(mock_update)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_user_allowed_with_filter_allowed(self, telega, mock_update):
        """Test user allowed when in filter list."""
        telega.settings.user_filter = ["testuser", "otheruser"]
        mock_update.effective_user.username = "testuser"

        result = await telega.is_user_allowed(mock_update)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_user_allowed_with_filter_not_allowed(self, telega, mock_update):
        """Test user not allowed when not in filter list."""
        telega.settings.user_filter = ["alloweduser"]
        mock_update.effective_user.username = "testuser"

        result = await telega.is_user_allowed(mock_update)

        assert result is False
        telega.settings.logger.info.assert_called_with(
            "Unexpected user", user_filter=["alloweduser"], user="testuser", update_id=12345
        )

    @pytest.mark.asyncio
    async def test_is_user_allowed_no_effective_user(self, telega, mock_update):
        """Test bot message detection."""
        telega.settings.user_filter = ["testuser"]
        mock_update.effective_user = None

        result = await telega.is_user_allowed(mock_update)

        assert result is False
        telega.settings.logger.info.assert_called_with("Bot message, ignoring", update_id=12345)

    @pytest.mark.asyncio
    async def test_reply_to_message(self, telega, mock_update):
        """Test reply_to_message method."""
        mock_update.message.message_id = 999
        mock_update.message.reply_text = AsyncMock()

        await telega.reply_to_message(mock_update, "Test reply")

        mock_update.message.reply_text.assert_called_once_with(text="Test reply", reply_to_message_id=999)

    @pytest.mark.asyncio
    async def test_reply_to_message_no_message(self, telega, mock_update):
        """Test reply_to_message with no message."""
        mock_update.message = None

        await telega.reply_to_message(mock_update, "Test reply")

        # Should not raise exception, just return

    @pytest.mark.asyncio
    async def test_handle_photo_message_success(self, telega, mock_update, mock_context):
        """Test successful photo message handling."""
        # Setup
        mock_update.message.photo = [Mock(file_id="photo123")]
        mock_update.message.reply_text = AsyncMock()
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.download_file = AsyncMock(return_value=io.BytesIO(b"test"))
        telega.reply_to_message = AsyncMock()

        with patch("telega.main.photo.generate_text_for_image", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "This is a test image"

            await telega.handle_photo_message(mock_update, mock_context)

            # Verify
            telega.is_user_allowed.assert_called_once_with(mock_update)
            telega.download_file.assert_called_once_with(mock_update, mock_context)
            mock_generate.assert_called_once()
            telega.reply_to_message.assert_called_once_with(mock_update, "This is a test image")

    @pytest.mark.asyncio
    async def test_handle_photo_message_no_photo(self, telega, mock_update, mock_context):
        """Test photo handler with no photo."""
        mock_update.message.photo = None

        await telega.handle_photo_message(mock_update, mock_context)

        telega.settings.logger.debug.assert_called_with("Unsupported message type", update_id=12345)

    @pytest.mark.asyncio
    async def test_handle_photo_message_user_not_allowed(self, telega, mock_update, mock_context):
        """Test photo handler with unauthorized user."""
        mock_update.message.photo = [Mock()]
        telega.is_user_allowed = AsyncMock(return_value=False)

        await telega.handle_photo_message(mock_update, mock_context)

        telega.is_user_allowed.assert_called_once_with(mock_update)

    @pytest.mark.asyncio
    async def test_handle_photo_message_download_failed(self, telega, mock_update, mock_context):
        """Test photo handler when download fails."""
        mock_update.message.photo = [Mock()]
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.download_file = AsyncMock(return_value=None)
        telega.reply_to_message = AsyncMock()

        await telega.handle_photo_message(mock_update, mock_context)

        telega.reply_to_message.assert_called_once_with(
            mock_update, "Sorry, I couldn't download your file. Please try again."
        )

    @pytest.mark.asyncio
    async def test_handle_list_mcps_message(self, telega, mock_update, mock_context):
        """Test listing MCPs command."""
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()
        telega.mcps.get_enabled_mcps.return_value = {"mcp1": {}, "mcp2": {}, "mcp3": {}}

        await telega.handle_list_mcps_message(mock_update, mock_context)

        telega.reply_to_message.assert_called_once()
        call_args = telega.reply_to_message.call_args[0]
        assert "mcp1" in call_args[1]
        assert "mcp2" in call_args[1]
        assert "mcp3" in call_args[1]

    @pytest.mark.asyncio
    async def test_handle_mcp_message_success(self, telega, mock_update, mock_context):
        """Test successful MCP message handling."""
        mock_update.message.text = "/test_mcp arg1 arg2"
        mock_context.args = ["arg1", "arg2"]
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()
        telega.mcps.reload_config = Mock()

        mock_config = Mock(spec=MCPConfiguration)
        mock_config.name = "test_mcp"
        mock_config.get_server_params = AsyncMock()
        telega.mcps.get_mcp_configuration.return_value = mock_config

        with patch("telega.main.MCPClient") as mock_mcp_client_class:
            mock_mcp_instance = Mock(spec=MCPClient)
            mock_mcp_instance.get_response = AsyncMock(return_value="MCP response")
            mock_mcp_client_class.return_value = mock_mcp_instance

            await telega.handle_mcp_message(mock_update, mock_context)

            telega.reply_to_message.assert_called_once_with(mock_update, "MCP response")

    @pytest.mark.asyncio
    async def test_handle_mcp_message_no_config(self, telega, mock_update, mock_context):
        """Test MCP message with no configuration found."""
        mock_update.message.text = "/unknown_mcp test"
        mock_context.args = ["test"]
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()
        telega.mcps.reload_config = Mock()
        telega.mcps.get_mcp_configuration.return_value = None

        await telega.handle_mcp_message(mock_update, mock_context)

        assert telega.reply_to_message.call_args[0][1].startswith("Sorry, I encountered an error")

    @pytest.mark.asyncio
    async def test_handle_text_message_success(self, telega, mock_update, mock_context):
        """Test successful text message handling."""
        mock_update.message.text = "Hello bot"
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()

        mock_response = Mock()
        mock_response.text = "Hello human!"
        telega.settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        await telega.handle_text_message(mock_update, mock_context)

        telega.settings.genai_client.aio.models.generate_content.assert_called_once_with(
            model=telega.settings.model_name, contents=["Hello bot"], config=telega.settings.genconfig
        )
        telega.reply_to_message.assert_called_once_with(mock_update, "Hello human!")

    @pytest.mark.asyncio
    async def test_handle_text_message_empty_response(self, telega, mock_update, mock_context):
        """Test text message with empty AI response."""
        mock_update.message.text = "Hello bot"
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()

        mock_response = Mock()
        mock_response.text = None
        telega.settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        await telega.handle_text_message(mock_update, mock_context)

        assert telega.reply_to_message.call_args[0][1].startswith("Sorry, I couldn't process")

    @pytest.mark.asyncio
    async def test_handle_rag_request_success(self, telega, mock_update, mock_context):
        """Test successful RAG request handling."""
        mock_update.message.text = "/rag What is the capital?"
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()

        mock_qa_chain = Mock()
        mock_qa_chain.invoke.return_value = {
            "result": "The capital is Paris.",
            "source_documents": [Mock(metadata={"source": "doc1.pdf"}), Mock(metadata={"source": "doc2.pdf"})],
        }
        telega.settings.qa_chain = mock_qa_chain

        await telega.handle_rag_request(mock_update, mock_context)

        mock_qa_chain.invoke.assert_called_once_with({"query": "/rag What is the capital?"})
        call_args = telega.reply_to_message.call_args[0]
        assert "The capital is Paris." in call_args[1]
        assert "doc1.pdf" in call_args[1]
        assert "doc2.pdf" in call_args[1]

    @pytest.mark.asyncio
    async def test_handle_rag_request_no_qa_chain(self, telega, mock_update, mock_context):
        """Test RAG request when QA chain is not configured."""
        mock_update.message.text = "/rag test query"
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.settings.qa_chain = None

        await telega.handle_rag_request(mock_update, mock_context)

        # Should return early without processing

    @pytest.mark.asyncio
    async def test_handle_photo_message_exception(self, telega, mock_update, mock_context):
        """Test photo handler with exception during processing."""
        mock_update.message.photo = [Mock()]
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.download_file = AsyncMock(return_value=io.BytesIO(b"test"))
        telega.reply_to_message = AsyncMock()

        with patch("telega.main.photo.generate_text_for_image", new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = Exception("Processing failed")
            with patch("telega.main.format_exc_info") as mock_format_exc:
                mock_format_exc.return_value = {"error": "test"}

                await telega.handle_photo_message(mock_update, mock_context)

                telega.settings.logger.error.assert_called()
                assert telega.reply_to_message.call_args[0][1].startswith("Sorry, I encountered an error")

    @pytest.mark.asyncio
    async def test_download_file_with_video(self, telega, mock_update, mock_context):
        """Test downloading a video file."""
        # Setup video
        video = Mock(spec=Video)
        video.file_id = "video789"
        mock_update.message.photo = None
        mock_update.message.document = None
        mock_update.message.video = video
        mock_update.message.sticker = None
        mock_update.message.animation = None

        # Setup file object
        mock_file = AsyncMock()
        mock_file.download_to_memory = AsyncMock()
        mock_context.bot.get_file.return_value = mock_file

        # Execute
        result = await telega.download_file(mock_update, mock_context)

        # Verify
        assert isinstance(result, io.BytesIO)
        mock_context.bot.get_file.assert_called_once_with("video789")

    @pytest.mark.asyncio
    async def test_download_file_with_sticker(self, telega, mock_update, mock_context):
        """Test downloading a sticker file."""
        # Setup sticker
        sticker = Mock(spec=Sticker)
        sticker.file_id = "sticker101"
        mock_update.message.photo = None
        mock_update.message.document = None
        mock_update.message.video = None
        mock_update.message.sticker = sticker
        mock_update.message.animation = None

        # Setup file object
        mock_file = AsyncMock()
        mock_file.download_to_memory = AsyncMock()
        mock_context.bot.get_file.return_value = mock_file

        # Execute
        result = await telega.download_file(mock_update, mock_context)

        # Verify
        assert isinstance(result, io.BytesIO)
        mock_context.bot.get_file.assert_called_once_with("sticker101")

    @pytest.mark.asyncio
    async def test_download_file_with_animation(self, telega, mock_update, mock_context):
        """Test downloading an animation file."""
        # Setup animation
        animation = Mock(spec=Animation)
        animation.file_id = "anim202"
        mock_update.message.photo = None
        mock_update.message.document = None
        mock_update.message.video = None
        mock_update.message.sticker = None
        mock_update.message.animation = animation

        # Setup file object
        mock_file = AsyncMock()
        mock_file.download_to_memory = AsyncMock()
        mock_context.bot.get_file.return_value = mock_file

        # Execute
        result = await telega.download_file(mock_update, mock_context)

        # Verify
        assert isinstance(result, io.BytesIO)
        mock_context.bot.get_file.assert_called_once_with("anim202")

    @pytest.mark.asyncio
    async def test_handle_text_message_with_rag(self, telega, mock_update, mock_context):
        """Test text message handling when RAG is configured."""
        mock_update.message.text = "What is the capital?"
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()

        # Setup RAG chain
        mock_qa_chain = Mock()
        mock_qa_chain.invoke.return_value = {"result": "The capital is Paris.", "source_documents": []}
        telega.settings.qa_chain = mock_qa_chain

        # Setup GenAI response
        mock_response = Mock()
        mock_response.text = "The capital is London."
        telega.settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        await telega.handle_text_message(mock_update, mock_context)

        # Should use GenAI, not RAG for regular text messages
        telega.settings.genai_client.aio.models.generate_content.assert_called_once()
        telega.reply_to_message.assert_called_once_with(mock_update, "The capital is London.")

    @pytest.mark.asyncio
    async def test_handle_mcp_message_exception(self, telega, mock_update, mock_context):
        """Test MCP message handling with exception."""
        mock_update.message.text = "/test_mcp arg1"
        mock_context.args = ["arg1"]
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()
        telega.mcps.reload_config = Mock()

        mock_config = Mock(spec=MCPConfiguration)
        mock_config.name = "test_mcp"
        mock_config.get_server_params = AsyncMock(side_effect=Exception("MCP error"))
        telega.mcps.get_mcp_configuration.return_value = mock_config

        await telega.handle_mcp_message(mock_update, mock_context)

        assert telega.reply_to_message.call_args[0][1].startswith("Sorry, I encountered an error")

    @pytest.mark.asyncio
    async def test_handle_list_mcps_message_empty(self, telega, mock_update, mock_context):
        """Test listing MCPs when none are enabled."""
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()
        telega.mcps.get_enabled_mcps.return_value = {}

        await telega.handle_list_mcps_message(mock_update, mock_context)

        telega.reply_to_message.assert_called_once()
        call_args = telega.reply_to_message.call_args[0]
        assert "Here are the MCPs I have enabled:" in call_args[1]

    @pytest.mark.asyncio
    async def test_handle_rag_request_with_exception(self, telega, mock_update, mock_context):
        """Test RAG request with exception during processing."""
        mock_update.message.text = "/rag What is the capital?"
        telega.is_user_allowed = AsyncMock(return_value=True)
        telega.reply_to_message = AsyncMock()

        mock_qa_chain = Mock()
        mock_qa_chain.invoke.side_effect = Exception("RAG processing failed")
        telega.settings.qa_chain = mock_qa_chain

        with patch("telega.main.format_exc_info") as mock_format_exc:
            mock_format_exc.return_value = {"error": "test"}

            await telega.handle_rag_request(mock_update, mock_context)

            telega.settings.logger.error.assert_called()
            assert telega.reply_to_message.call_args[0][1].startswith("Sorry, I couldn't process")


class TestMCPConfigReader:
    """Test cases for the MCPConfigReader class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for MCPConfigReader."""
        settings = Mock(spec=Settings)
        settings.logger = Mock()
        settings.logger.info = Mock()
        settings.logger.debug = Mock()
        settings.logger.warning = Mock()
        settings.logger.error = Mock()
        settings.mcp_config_path = "/path/to/config.yaml"
        return settings

    @pytest.fixture
    def mcp_reader(self, mock_settings):
        """Create MCPConfigReader instance."""
        return MCPConfigReader(mock_settings)

    @pytest.fixture
    def sample_config(self):
        """Create a sample MCP configuration."""
        return {
            "extensions": {
                "test_mcp": {
                    "cmd": "test-command",
                    "args": ["arg1", "arg2"],
                    "envs": {"KEY1": "value1"},
                    "description": "Test MCP",
                    "enabled": True,
                    "type": "stdio",
                },
                "disabled_mcp": {"cmd": "disabled-command", "enabled": False, "type": "stdio"},
                "simple_mcp": "simple-type",
            }
        }

    def test_mcp_config_reader_initialization(self, mock_settings):
        """Test MCPConfigReader initialization."""
        reader = MCPConfigReader(mock_settings)

        assert reader.logger == mock_settings.logger
        assert str(reader.config_path) == "/path/to/config.yaml"
        assert reader.mcps == {}
        assert reader._raw_config == {}

    def test_load_config_file_not_found(self, mcp_reader, mock_settings):
        """Test loading config when file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                mcp_reader.load_config()

            mock_settings.logger.warning.assert_called_once()

    def test_load_config_yaml_error(self, mcp_reader, mock_settings):
        """Test loading config with invalid YAML."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data="invalid: yaml: content:")),
            patch("yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML")),
        ):
            with pytest.raises(yaml.YAMLError):
                mcp_reader.load_config()

            mock_settings.logger.error.assert_called()

    def test_load_config_success(self, mcp_reader, mock_settings, sample_config):
        """Test successful config loading."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open()),
            patch("yaml.safe_load", return_value=sample_config),
        ):
            mcp_reader.load_config()

            assert len(mcp_reader.mcps) == 3
            assert "test_mcp" in mcp_reader.mcps
            assert "disabled_mcp" in mcp_reader.mcps
            assert "simple_mcp" in mcp_reader.mcps
            mock_settings.logger.info.assert_called()

    def test_parse_configuration_invalid_format(self, mcp_reader):
        """Test parsing invalid configuration format."""
        mcp_reader._raw_config = {"extensions": "not a dict"}

        with pytest.raises(ValueError, match="MCP configuration must be a dictionary"):
            mcp_reader._parse_configuration()

    def test_parse_configuration_invalid_mcp(self, mcp_reader, mock_settings):
        """Test parsing configuration with invalid MCP."""
        mcp_reader._raw_config = {"extensions": {"invalid_mcp": {"invalid_field": "value"}}}

        with pytest.raises(ValueError, match="Invalid MCP configuration"):
            mcp_reader._parse_configuration()

    def test_create_mcp_configuration_string(self, mcp_reader):
        """Test creating MCP configuration from string."""
        mcp = mcp_reader._create_mcp_configuration("simple", "simple-type")

        assert mcp.name == "simple"
        assert mcp.type == "simple-type"
        assert mcp.enabled is True
        assert mcp.config == {}

    def test_create_mcp_configuration_dict(self, mcp_reader):
        """Test creating MCP configuration from dictionary."""
        config = {
            "cmd": "test-cmd",
            "args": ["arg1"],
            "envs": {"KEY": "value"},
            "description": "Test MCP",
            "type": "stdio",
        }

        mcp = mcp_reader._create_mcp_configuration("test", config)

        assert mcp.name == "test"
        assert mcp.type == "stdio"
        assert mcp.config["cmd"] == "test-cmd"
        assert mcp.config["args"] == ["arg1"]
        assert mcp.metadata["description"] == "Test MCP"

    def test_get_mcp_configuration(self, mcp_reader):
        """Test getting specific MCP configuration."""
        test_mcp = MCPConfiguration(name="test", type="test-type")
        mcp_reader.mcps = {"test": test_mcp}

        result = mcp_reader.get_mcp_configuration("test")
        assert result == test_mcp

        result = mcp_reader.get_mcp_configuration("nonexistent")
        assert result is None

    def test_get_enabled_mcps(self, mcp_reader):
        """Test getting enabled MCPs."""
        enabled_mcp = MCPConfiguration(name="enabled", type="type1", enabled=True)
        disabled_mcp = MCPConfiguration(name="disabled", type="type2", enabled=False)

        mcp_reader.mcps = {"enabled": enabled_mcp, "disabled": disabled_mcp}

        result = mcp_reader.get_enabled_mcps()

        assert len(result) == 1
        assert "enabled" in result
        assert "disabled" not in result

    def test_get_mcps_by_type(self, mcp_reader):
        """Test getting MCPs by type."""
        mcp1 = MCPConfiguration(name="mcp1", type="type-a")
        mcp2 = MCPConfiguration(name="mcp2", type="type-b")
        mcp3 = MCPConfiguration(name="mcp3", type="type-a")

        mcp_reader.mcps = {"mcp1": mcp1, "mcp2": mcp2, "mcp3": mcp3}

        result = mcp_reader.get_mcps_by_type("type-a")

        assert len(result) == 2
        assert mcp1 in result
        assert mcp3 in result
        assert mcp2 not in result

    def test_list_mcp_names(self, mcp_reader):
        """Test listing MCP names."""
        mcp_reader.mcps = {"mcp1": Mock(), "mcp2": Mock(), "mcp3": Mock()}

        names = mcp_reader.list_mcp_names()

        assert len(names) == 3
        assert "mcp1" in names
        assert "mcp2" in names
        assert "mcp3" in names

    def test_reload_config(self, mcp_reader):
        """Test reloading configuration."""
        with patch.object(mcp_reader, "load_config") as mock_load:
            mcp_reader.reload_config()
            mock_load.assert_called_once()

    def test_validate_configuration_empty(self, mcp_reader, mock_settings):
        """Test validating empty configuration."""
        mcp_reader.mcps = {}

        result = mcp_reader.validate_configuration()

        assert result is True
        mock_settings.logger.warning.assert_called_with("No MCPs configured")

    def test_validate_configuration_valid(self, mcp_reader, mock_settings):
        """Test validating valid configuration."""
        mcp_reader.mcps = {
            "test1": MCPConfiguration(name="test1", type="type1"),
            "test2": MCPConfiguration(name="test2", type="type2"),
        }

        result = mcp_reader.validate_configuration()

        assert result is True
        mock_settings.logger.info.assert_called()

    def test_validate_configuration_invalid(self, mcp_reader):
        """Test validating invalid configuration."""
        # Create a valid MCP first, then make it invalid
        invalid_mcp = Mock(spec=MCPConfiguration)
        invalid_mcp.name = ""  # Invalid name
        invalid_mcp.type = "type1"

        mcp_reader.mcps = {"invalid": invalid_mcp}

        with pytest.raises(ValueError, match="has invalid configuration"):
            mcp_reader.validate_configuration()

    def test_repr(self, mcp_reader):
        """Test string representation."""
        mcp_reader.mcps = {"test1": Mock(), "test2": Mock()}

        result = repr(mcp_reader)

        assert "MCPConfigReader" in result
        assert "config_path=" in result
        assert "mcps=2" in result

    def test_len(self, mcp_reader):
        """Test length operation."""
        mcp_reader.mcps = {"test1": Mock(), "test2": Mock(), "test3": Mock()}

        assert len(mcp_reader) == 3

    def test_contains(self, mcp_reader):
        """Test contains operation."""
        mcp_reader.mcps = {"test_mcp": Mock()}

        assert "test_mcp" in mcp_reader
        assert "nonexistent" not in mcp_reader

    @pytest.mark.asyncio
    async def test_mcp_configuration_get_server_params(self):
        """Test MCPConfiguration get_server_params method."""
        config = {"cmd": "test-command", "args": ["arg1", "arg2"], "envs": {"KEY1": "value1"}}

        mcp = MCPConfiguration(name="test", type="test-type", config=config)

        params = await mcp.get_server_params()

        assert params.command == "test-command"
        assert params.args == ["arg1", "arg2"]
        assert params.env == {"KEY1": "value1"}

    @pytest.mark.asyncio
    async def test_mcp_configuration_get_server_params_env_keys(self):
        """Test get_server_params with env_keys."""
        with patch.dict(os.environ, {"TEST_KEY": "test_value"}):
            config = {"cmd": "test-command", "env_keys": ["TEST_KEY", "MISSING_KEY"]}

            mcp = MCPConfiguration(name="test", type="test-type", config=config)

            params = await mcp.get_server_params()

            assert params.env == {"TEST_KEY": "test_value", "MISSING_KEY": ""}

    @pytest.mark.asyncio
    async def test_mcp_configuration_get_server_params_no_command(self):
        """Test get_server_params with no command."""
        mcp = MCPConfiguration(name="test", type="test-type", config={})

        with pytest.raises(ValueError, match="No command specified"):
            await mcp.get_server_params()

    def test_mcp_configuration_post_init_validation(self):
        """Test MCPConfiguration validation in post_init."""
        with pytest.raises(ValueError, match="MCP name cannot be empty"):
            MCPConfiguration(name="", type="test-type")

        with pytest.raises(ValueError, match="MCP type cannot be empty"):
            MCPConfiguration(name="test", type="")

    def test_parse_configuration_with_metadata(self, mcp_reader):
        """Test parsing configuration with metadata."""
        mcp_reader._raw_config = {
            "extensions": {"test_mcp": {"type": "test-type", "metadata": {"author": "Test Author", "version": "1.0.0"}}}
        }

        mcp_reader._parse_configuration()

        assert "test_mcp" in mcp_reader.mcps
        mcp = mcp_reader.mcps["test_mcp"]
        assert mcp.metadata["author"] == "Test Author"
        assert mcp.metadata["version"] == "1.0.0"


class TestMCPClient:
    """Test cases for the MCPClient class."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        logger = Mock()
        logger.debug = Mock()
        logger.error = Mock()
        return logger

    @pytest.fixture
    def mock_server_params(self):
        """Create mock server parameters."""
        params = Mock(spec=StdioServerParameters)
        params.command = "test-command"
        params.args = ["arg1", "arg2"]
        params.env = {"KEY": "value"}
        return params

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.genai_client = Mock()
        settings.genai_client.aio = Mock()
        settings.genai_client.aio.models = Mock()
        settings.model_name = "test-model"
        settings.genconfig = Mock()
        settings.genconfig.copy = Mock(return_value=Mock(tools=None))
        return settings

    @pytest.fixture
    def mcp_client(self, mock_logger, mock_server_params):
        """Create MCPClient instance."""
        return MCPClient("test_mcp", mock_server_params, mock_logger)

    def test_mcp_client_initialization(self, mock_logger, mock_server_params):
        """Test MCPClient initialization."""
        client = MCPClient("test_mcp", mock_server_params, mock_logger)

        assert client.name == "test_mcp"
        assert client.server_params == mock_server_params
        assert client.logger == mock_logger

    @pytest.mark.asyncio
    async def test_get_response_success(self, mcp_client, mock_settings):
        """Test successful response generation."""
        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content = Mock()
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = Mock()
        mock_response.candidates[0].content.parts[0].text.strip = Mock(return_value="Test response")

        mock_settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.plugins.mcp.stdio_client") as mock_stdio:
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

            with patch("src.plugins.mcp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

                result = await mcp_client.get_response(mock_settings, "test prompt")

                assert result == "Test response"
                mock_session.initialize.assert_called_once()
                mock_settings.genai_client.aio.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_response_with_custom_prompt(self, mcp_client, mock_settings):
        """Test response generation with custom prompt from env var."""
        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content = Mock()
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = Mock()
        mock_response.candidates[0].content.parts[0].text.strip = Mock(return_value="Custom response")

        mock_settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch.dict(os.environ, {"MCP_test_mcp_PROMPT": "Custom prefix"}),
            patch("src.plugins.mcp.stdio_client") as mock_stdio,
        ):
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

            with patch("src.plugins.mcp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

                result = await mcp_client.get_response(mock_settings, "test prompt")

                assert result == "Custom response"
                # Check that custom prompt was used
                call_args = mock_settings.genai_client.aio.models.generate_content.call_args
                assert call_args.kwargs["contents"][0] == "Custom prefix\ntest prompt"

    @pytest.mark.asyncio
    async def test_get_response_with_existing_tools(self, mcp_client, mock_settings):
        """Test response generation when genconfig already has tools."""
        existing_tool = Mock()
        mock_genconfig = Mock(tools=[existing_tool])
        mock_genconfig.copy = Mock(return_value=Mock(tools=[existing_tool]))
        mock_settings.genconfig = mock_genconfig

        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content = Mock()
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = Mock()
        mock_response.candidates[0].content.parts[0].text.strip = Mock(return_value="Response with tools")

        mock_settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.plugins.mcp.stdio_client") as mock_stdio:
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

            with patch("src.plugins.mcp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

                result = await mcp_client.get_response(mock_settings, "test prompt")

                assert result == "Response with tools"
                # Verify tools list was extended
                call_args = mock_settings.genai_client.aio.models.generate_content.call_args
                config = call_args.kwargs["config"]
                assert existing_tool in config.tools
                assert mock_session in config.tools
                assert config.temperature == 0

    @pytest.mark.asyncio
    async def test_get_response_exception_handling(self, mcp_client, mock_settings, mock_logger):
        """Test response generation with exception."""
        mock_response = Mock()
        mock_response.candidates = None  # This will cause an exception

        mock_settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.plugins.mcp.stdio_client") as mock_stdio:
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

            with patch("src.plugins.mcp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

                result = await mcp_client.get_response(mock_settings, "test prompt")

                assert result is None
                mock_logger.error.assert_called()
                assert "failed to generate a response" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_get_response_strips_whitespace(self, mcp_client, mock_settings):
        """Test that response text is stripped of whitespace."""
        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content = Mock()
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = Mock()
        mock_response.candidates[0].content.parts[0].text.strip = Mock(return_value="Stripped response")

        mock_settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.plugins.mcp.stdio_client") as mock_stdio:
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

            with patch("src.plugins.mcp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

                result = await mcp_client.get_response(mock_settings, "  test prompt  ")

                assert result == "Stripped response"
                # Verify input prompt was also stripped
                call_args = mock_settings.genai_client.aio.models.generate_content.call_args
                assert call_args.kwargs["contents"][0] == "test prompt"

    @pytest.mark.asyncio
    async def test_get_response_logging(self, mcp_client, mock_settings, mock_logger):
        """Test that debug logging is performed."""
        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content = Mock()
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = Mock()
        mock_response.candidates[0].content.parts[0].text.strip = Mock(return_value="Test response")

        mock_settings.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.plugins.mcp.stdio_client") as mock_stdio:
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

            with patch("src.plugins.mcp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

                await mcp_client.get_response(mock_settings, "test prompt")

                # Verify debug logging
                assert mock_logger.debug.call_count == 2
                first_call = str(mock_logger.debug.call_args_list[0])
                second_call = str(mock_logger.debug.call_args_list[1])
                assert "running prompt" in first_call
                assert "response" in second_call
