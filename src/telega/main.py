"""Telega class for handling Telegram bot operations with AI integration."""

import io
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from plugins import photo
from plugins.mcp import MCPConfigReader, MCPClient
from telega.settings import Settings


class Telega:
    """Main class for Telegram bot operations with AI integration."""

    def __init__(self, settings: Settings):
        """
        Initialize Telega with settings configuration.

        Args:
            settings: Settings object containing genai client, logger, and model name
        """
        self.settings = settings
        self.mcps = MCPConfigReader(self.settings)

    async def download_file(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[io.BytesIO]:
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
            self.settings.logger.error(
                "Failed to download file", error=str(e), update_id=update.update_id
            )
            return None

    async def is_user_allowed(self, update: Update):
        """
        Verify if the user is allowed to use the bot.

        Args:
            update: Telegram update object
            context: Telegram context object
        """

        if not self.settings.USER_FILTER or self.settings.USER_FILTER == []:
            return True

        # Check if user is allowed to use the bot
        if not update.effective_user:
            self.settings.logger.info(
                "Bot message, ignoring", update_id=update.update_id
            )
            return False

        if update.effective_user.username not in self.settings.USER_FILTER:
            self.settings.logger.info(
                "Unexpected user",
                user_filter=self.settings.USER_FILTER,
                user=update.effective_user.username,
                update_id=update.update_id,
            )
            return False

        return True

    async def reply_to_message(self, update: Update, text: str):
        """
        Reply to a message with a text. This renders the text as Markdown with necessary escaping.

        Args:
            update: Telegram update object
            text: Text to reply with
        """
        if update.message is None:
            return

        await update.message.reply_text(
            text=text,
            reply_to_message_id=update.message.message_id,
            # parse_mode="Markdown",
        )

    async def handle_photo_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle incoming Telegram messages with media content.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        # Check if message contains supported media
        if not update.message or not update.effective_chat or not update.message.photo:
            self.settings.logger.debug(
                "Unsupported message type", update_id=update.update_id
            )
            return

        # Check if user is allowed to use the bot
        if not await self.is_user_allowed(update):
            return

        self.settings.logger.info("Processing message", update_id=update.update_id)

        # Download the file
        file_buffer = await self.download_file(update, context)
        if not file_buffer:
            await self.reply_to_message(
                update, "Sorry, I couldn't download your file. Please try again."
            )
            return

        try:
            # Generate description
            self.settings.logger.info(
                "Generating image description", update_id=update.update_id
            )
            description = await photo.generate_text_for_image(
                self.settings,
                file_buffer,
            )

            self.settings.logger.info(
                "Generated description",
                update_id=update.update_id,
                description=(
                    description[:100] + "..." if len(description) > 100 else description
                ),
            )

            # Reply with generated text
            await self.reply_to_message(update, description)

        except Exception as e:
            self.settings.logger.error(
                "Error processing image", error=str(e), update_id=update.update_id
            )
            await self.reply_to_message(
                update,
                f"Sorry, I encountered an error processing your image. See logs for update ID: {update.update_id}",
            )
        finally:
            # Clean up file buffer
            file_buffer.close()

    async def handle_list_mcps_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Output a list of enabled MCPs.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        # Check if user is allowed to use the bot
        if not await self.is_user_allowed(update):
            return

        if not update.message:
            return

        try:
            self.settings.logger.info("Listing MCPs", update_id=update.update_id)

            # Get list of enabled MCPs
            mcps = self.mcps.get_enabled_mcps()

            # Reply with list of enabled MCPs
            await self.reply_to_message(
                update,
                f"Here are the MCPs I have enabled:\n{"\n".join(mcps)}",
            )
        except Exception as e:
            self.settings.logger.error(
                "Error listing MCPs", error=str(e), update_id=update.update_id
            )
            await self.reply_to_message(
                update,
                f"Sorry, I encountered an error processing this command. See logs for update ID: {update.update_id}",
            )

    async def handle_mcp_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle messages to MCPs.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        # Check if user is allowed to use the bot
        if not await self.is_user_allowed(update):
            return

        if not update.message or not update.message.text or not context.args:
            return

        tool_name = update.message.text.split()[0].replace("/", "").lower()
        tool_prompt = " ".join(context.args)
        self.settings.logger.info(
            "Processing MCP message",
            update_id=update.update_id,
            command=tool_name,
            params=tool_prompt,
        )

        try:
            self.mcps.reload_config()

            mcp_config = self.mcps.get_mcp_configuration(tool_name)
            if not mcp_config:
                raise ValueError(f"MCP {tool_name} configuration not found")
            else:
                server_params = await mcp_config.get_server_params()
                mcp = MCPClient(
                    name=mcp_config.name,
                    server_params=server_params,
                    logger=self.settings.logger,
                )
                if mcp is None:
                    raise ValueError(f"MCP {tool_name} cannot be created")
                else:
                    reply_text = await mcp.get_response(
                        settings=self.settings, prompt=tool_prompt
                    )
            self.settings.logger.error(f"MCP {tool_name} response: {reply_text}")

            if not reply_text:
                raise ValueError(f"MCP {tool_name} response is empty")

            # Reply with generated text
            await self.reply_to_message(update, reply_text)

        except Exception as e:
            self.settings.logger.error(
                "Error processing command", error=str(e), update_id=update.update_id
            )
            await self.reply_to_message(
                update,
                f"Sorry, I encountered an error processing this command. See logs for update ID: {update.update_id}",
            )

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle text-only messages.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        # Check if user is allowed to use the bot
        if not await self.is_user_allowed(update):
            return

        if not update.message or not update.message.text:
            return

        self.settings.logger.info("Processing text message", update_id=update.update_id)

        try:
            # Generate response using AI
            response = await self.settings.genai_client.aio.models.generate_content(
                model=self.settings.model_name,
                contents=[
                    update.message.text,
                ],
                config=self.settings.genconfig,
            )
            if not response.text:
                raise ValueError("Empty response from AI")

            reply_text = response.text.strip()

            await self.reply_to_message(update, reply_text)

        except Exception as e:
            self.settings.logger.error(
                "Error processing message", error=str(e), update_id=update.update_id
            )
            await self.reply_to_message(
                update,
                f"Sorry, I couldn't process your message. See logs for update ID: {update.update_id}",
            )
