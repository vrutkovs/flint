import io

from PIL import Image

from telega.settings import Settings

async def generate_text_for_image(settings: Settings, file_buffer: io.BytesIO,  prompt: str = "Describe this image in detail") -> str:
    """
    Generate text description for an image using AI.

    Args:
        file_buffer: image encoded as bytes
        prompt: Text prompt for AI generation

    Returns:
        Generated text description
    """
    image = Image.open(file_buffer)
    # img_buffer = io.BytesIO()
    # image.save(img_buffer, format='PNG')
    # img_buffer.seek(0)

    # Use GenAI to generate text
    response = await settings.genai_client.aio.models.generate_content(
        model=settings.model,
        contents=[
            prompt,
            image,
        ]
    )
    result = response.text
    if result is None:
        raise ValueError("AI response is None")
    return result.strip()
