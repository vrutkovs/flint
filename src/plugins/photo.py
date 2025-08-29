import io
from typing import Any, Final, cast

from PIL import Image

from telega.settings import Settings

PROMPT: Final[str] = (
    "Describe this image in one sentence. If the picture contains text, include it in the description as is."
)


async def generate_text_for_image(settings: Settings, file_buffer: io.BytesIO, prompt: str = PROMPT) -> str:
    """
    Generate text description for an image using AI.

    Args:
        settings: Settings instance containing genai client and model configuration
        file_buffer: image encoded as bytes
        prompt: Text prompt for AI generation

    Returns:
        Generated text description

    Raises:
        ValueError: If AI response is None
    """
    image: Image.Image = Image.open(file_buffer)

    # Use GenAI to generate text
    response = await settings.genai_client.aio.models.generate_content(
        model=settings.model_name,
        contents=cast(list[str | Image.Image | Any | Any], [prompt, image]),
        config=settings.genconfig,
    )
    result: str | None = response.text
    if result is None:
        raise ValueError("AI response is None")
    return result.strip()
