"""Telega class for handling Telegram bot operations with AI integration."""

import io
from typing import Optional

import structlog
from PIL import Image

from telegram import Update
from telegram.ext import ContextTypes

from google import genai


class Telega:
    """Main class for Telegram bot operations with AI integration."""

    def __init__(self, genai_client: genai.Client, logger: structlog.BoundLogger):
        """
        Initialize Telega with AI client and logger.

        Args:
            genai_client: Google GenAI client for text generation
            logger: Structured logger instance
        """
        self.genai_client = genai_client
        self.logger = logger

    async def download_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[io.BytesIO]:
        """
        Download file from Telegram message.

        Args:
            update: Telegram update object
            context: Telegram context object

        Returns:
            BytesIO buffer with file content or None if failed
        """
        try:
            file_obj = None
            upd = update.message
            if upd is None:
                return None

            if upd.photo:
                # Get the largest photo
                photo = upd.photo[-1]
                file_obj = await context.bot.get_file(photo.file_id)
            elif upd.document:
                file_obj = await context.bot.get_file(upd.document.file_id)
            elif upd.video:
                file_obj = await context.bot.get_file(upd.video.file_id)
            elif upd.sticker:
                file_obj = await context.bot.get_file(upd.sticker.file_id)
            elif upd.animation:
                file_obj = await context.bot.get_file(upd.animation.file_id)

            if not file_obj:
                return None

            # Download file to BytesIO buffer
            file_buffer = io.BytesIO()
            await file_obj.download_to_memory(file_buffer)
            file_buffer.seek(0)

            return file_buffer

        except Exception as e:
            self.logger.error("Failed to download file", error=str(e), update_id=update.update_id)
            return None

    async def generate_text_for_image(self, image: Image.Image, prompt: str = "Describe this image in detail") -> str:
        """
        Generate text description for an image using AI.

        Args:
            image: PIL Image object
            prompt: Text prompt for AI generation

        Returns:
            Generated text description
        """
        try:
            # Convert PIL image to bytes
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)

            # Use GenAI to generate text
            response = await self.genai_client.aio.models.generate_content(
                model='gemini-1.5-flash',
                contents=[
                    prompt,
                    image,
                ]
            )
            result = response.text
            if result is None:
                raise ValueError("AI response is None")
            return result.strip()

        except Exception as e:
            self.logger.error("Failed to generate text for image", error=str(e))
            return "Sorry, I couldn't analyze this image. Please try again."

    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming Telegram messages with media content.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        # Check if message contains supported media
        if (
            not update.message
            or not update.effective_chat
            or not update.message.photo
        ):
            self.logger.debug("Unsupported message type", update_id=update.update_id)
            return

        self.logger.info("Processing message", update_id=update.update_id)

        # Download the file
        file_buffer = await self.download_file(update, context)
        if not file_buffer:
            await update.message.reply_text(
                "Sorry, I couldn't download your file. Please try again."
            )
            return

        try:
            # Open image from buffer
            image = Image.open(file_buffer)

            # Generate description
            self.logger.info("Generating image description", update_id=update.update_id)
            description = await self.generate_text_for_image(image)

            self.logger.info(
                "Generated description",
                update_id=update.update_id,
                description=description[:100] + "..." if len(description) > 100 else description
            )

            # Reply with generated text
            await update.message.reply_text(
                description,
                reply_to_message_id=update.message.message_id
            )

        except Exception as e:
            self.logger.error("Error processing image", error=str(e), update_id=update.update_id)
            await update.message.reply_text(
                "Sorry, I encountered an error processing your image. Please try again."
            )
        finally:
            # Clean up file buffer
            file_buffer.close()

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle text-only messages.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        if not update.message or not update.message.text:
            return

        self.logger.info("Processing text message", update_id=update.update_id)

        try:
            # Generate response using AI
            response = await self.genai_client.aio.models.generate_content(
                model='gemini-1.5-flash',
                contents=[
                    update.message.text,
                ]
            )
            if not response.text:
                self.logger.error("Empty response from AI", update_id=update.update_id)
                raise ValueError("Empty response from AI")

            reply_text = response.text.strip()

            await update.message.reply_text(
                reply_text,
                reply_to_message_id=update.message.message_id
            )

        except Exception as e:
            self.logger.error("Error processing text message", error=str(e), update_id=update.update_id)
            await update.message.reply_text(
                "Sorry, I couldn't process your message. Please try again."
            )
