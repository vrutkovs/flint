"""Unit tests for the photo plugin."""

import io
import pytest
from unittest.mock import Mock, AsyncMock
from PIL import Image

from src.plugins.photo import generate_text_for_image, PROMPT
from src.telega.settings import Settings


class TestPhotoPlugin:
    """Test cases for the photo plugin."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.genai_client = Mock()
        settings.genai_client.aio = Mock()
        settings.genai_client.aio.models = Mock()
        settings.model_name = "test-model"
        settings.genconfig = Mock()
        return settings

    @pytest.fixture
    def sample_image_buffer(self):
        """Create a sample image buffer."""
        # Create a simple 10x10 RGB image
        img = Image.new('RGB', (10, 10), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    @pytest.mark.asyncio
    async def test_generate_text_for_image_success(self, mock_settings, sample_image_buffer):
        """Test successful text generation for an image."""
        # Setup mock response
        mock_response = Mock()
        mock_response.text = "This is a red square image."
        mock_settings.genai_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        # Execute
        result = await generate_text_for_image(mock_settings, sample_image_buffer)

        # Verify
        assert result == "This is a red square image."
        mock_settings.genai_client.aio.models.generate_content.assert_called_once()

        # Check the call arguments
        call_args = mock_settings.genai_client.aio.models.generate_content.call_args
        assert call_args.kwargs['model'] == "test-model"
        assert call_args.kwargs['config'] == mock_settings.genconfig

        # Check contents
        contents = call_args.kwargs['contents']
        assert len(contents) == 2
        assert contents[0] == PROMPT
        assert isinstance(contents[1], Image.Image)

    @pytest.mark.asyncio
    async def test_generate_text_for_image_different_formats(self, mock_settings):
        """Test with different image formats."""
        formats = ['PNG', 'JPEG', 'BMP']

        mock_response = Mock()
        mock_response.text = "Test image description."
        mock_settings.genai_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        for img_format in formats:
            # Create image in specific format
            img = Image.new('RGB', (10, 10), color='blue')
            buffer = io.BytesIO()

            # BMP doesn't support all save options
            if img_format == 'BMP':
                img.save(buffer, format=img_format)
            else:
                img.save(buffer, format=img_format)

            buffer.seek(0)

            # Execute
            result = await generate_text_for_image(mock_settings, buffer)

            # Verify
            assert result == "Test image description."

    @pytest.mark.asyncio
    async def test_generate_text_for_image_strips_whitespace(self, mock_settings, sample_image_buffer):
        """Test that generated text is stripped of whitespace."""
        # Setup mock response with whitespace
        mock_response = Mock()
        mock_response.text = "  This has whitespace.  \n"
        mock_settings.genai_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        # Execute
        result = await generate_text_for_image(mock_settings, sample_image_buffer)

        # Verify
        assert result == "This has whitespace."
