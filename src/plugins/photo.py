import io

from PIL import Image

from telega.settings import Settings

PROMPT = "Describe this image in one sentence. If the picture contains text, include it in the description as is."

async def generate_text_for_image(settings: Settings, file_buffer: io.BytesIO,  prompt: str = PROMPT) -> str:
    """
    Generate text description for an image using AI.

    Args:
        file_buffer: image encoded as bytes
        prompt: Text prompt for AI generation

    Returns:
        Generated text description
    """
    image = Image.open(file_buffer)

    # Use GenAI to generate text
    response = await settings.genai_client.aio.models.generate_content(
        model=settings.model_name,
        contents=[
            prompt,
            image,
        ],
        config=settings.genconfig
    )
    result = response.text
    if result is None:
        raise ValueError("AI response is None")
    return result.strip()
