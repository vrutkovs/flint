"""Telega class for handling Telegram bot operations with AI integration."""

import io
from typing import Any, cast

from PIL import Image
from structlog.processors import format_exc_info
from structlog.types import EventDict
from telegram import Update
from telegram.ext import ContextTypes

from plugins import photo
from plugins.diary import generate_diary_entry_manual
from plugins.mcp import MCPClient, MCPConfigReader, MCPConfiguration, StdioServerParameters
from telega.settings import Settings


class Telega:
    """Main class for Telegram bot operations with AI integration."""

    def __init__(self, settings: Settings) -> None:
        """
        Initialize Telega with settings configuration.

        Args:
            settings: Settings object containing genai client, logger, and model name
        """
        self.settings: Settings = settings
        self.mcps: MCPConfigReader = MCPConfigReader(self.settings)

    async def download_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> io.BytesIO | None:
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
            file_buffer: io.BytesIO = io.BytesIO()
            await file_obj.download_to_memory(file_buffer)
            file_buffer.seek(0)

            return file_buffer

        except Exception:
            err: EventDict = format_exc_info(self.settings.logger, "exception", {"exc_info": True})
            self.settings.logger.error("Failed to download file", error=err, update_id=update.update_id)
            return None

    async def is_user_allowed(self, update: Update) -> bool:
        """
        Verify if the user is allowed to use the bot.

        Args:
            update: Telegram update object

        Returns:
            True if user is allowed, False otherwise
        """

        if not self.settings.user_filter or self.settings.user_filter == []:
            return True

        # Check if user is allowed to use the bot
        if not update.effective_user:
            self.settings.logger.info("Bot message, ignoring", update_id=update.update_id)
            return False

        if update.effective_user.username not in self.settings.user_filter:
            self.settings.logger.info(
                "Unexpected user",
                user_filter=self.settings.user_filter,
                user=update.effective_user.username,
                update_id=update.update_id,
            )
            return False

        return True

    async def reply_to_message(self, update: Update, text: str) -> None:
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

    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle incoming Telegram messages with media content.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        # Check if message contains supported media
        if not update.message or not update.effective_chat or not update.message.photo:
            self.settings.logger.debug("Unsupported message type", update_id=update.update_id)
            return

        # Check if user is allowed to use the bot
        if not await self.is_user_allowed(update):
            return

        self.settings.logger.info("Processing message", update_id=update.update_id)

        # Download the file
        file_buffer: io.BytesIO | None = await self.download_file(update, context)
        if not file_buffer:
            await self.reply_to_message(update, "Sorry, I couldn't download your file. Please try again.")
            return

        try:
            # Generate description
            self.settings.logger.info("Generating image description", update_id=update.update_id)
            description: str = await photo.generate_text_for_image(
                self.settings,
                file_buffer,
            )

            self.settings.logger.info(
                "Generated description",
                update_id=update.update_id,
                description=(description[:100] + "..." if len(description) > 100 else description),
            )

            # Reply with generated text
            await self.reply_to_message(update, description)

        except Exception:
            err: EventDict = format_exc_info(self.settings.logger, "exception", {"exc_info": True})
            self.settings.logger.error("Error processing image", error=err, update_id=update.update_id)
            await self.reply_to_message(
                update,
                f"Sorry, I encountered an error processing your image. See logs for update ID: {update.update_id}",
            )
        finally:
            # Clean up file buffer
            file_buffer.close()

    async def handle_list_mcps_message(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
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
            mcps: dict[str, Any] = self.mcps.get_enabled_mcps()
            mcp_names: list[str] = list(mcps.keys())

            # Reply with list of enabled MCPs
            await self.reply_to_message(
                update,
                f"Here are the MCPs I have enabled:\n{'\n'.join(mcp_names)}",
            )
        except Exception:
            err: EventDict = format_exc_info(self.settings.logger, "exception", {"exc_info": True})
            self.settings.logger.error("Error listing MCPs", error=err, update_id=update.update_id)
            await self.reply_to_message(
                update,
                f"Sorry, I encountered an error processing this command. See logs for update ID: {update.update_id}",
            )

    async def handle_mcp_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

        tool_name: str = update.message.text.split()[0].replace("/", "").lower()
        tool_prompt: str = " ".join(context.args)
        self.settings.logger.info(
            "Processing MCP message",
            update_id=update.update_id,
            command=tool_name,
            params=tool_prompt,
        )

        try:
            self.mcps.reload_config()

            mcp_config: MCPConfiguration | None = self.mcps.get_mcp_configuration(tool_name)
            if not mcp_config:
                raise ValueError(f"MCP {tool_name} configuration not found")
            else:
                server_params: StdioServerParameters = await mcp_config.get_server_params()
                mcp: MCPClient = MCPClient(
                    name=mcp_config.name,
                    server_params=server_params,
                    logger=self.settings.logger,
                )
                if mcp is None:
                    raise ValueError(f"MCP {tool_name} cannot be created")
                else:
                    reply_text: str | None = await mcp.get_response(settings=self.settings, prompt=tool_prompt)
            self.settings.logger.error(f"MCP {tool_name} response: {reply_text}")

            if not reply_text:
                raise ValueError(f"MCP {tool_name} response is empty")

            # Reply with generated text
            await self.reply_to_message(update, reply_text)

        except Exception:
            err: EventDict = format_exc_info(self.settings.logger, "exception", {"exc_info": True})
            self.settings.logger.error("Error processing command", error=err, update=update.update_id)
            await self.reply_to_message(
                update,
                f"Sorry, I encountered an error processing this command. See logs for update ID: {update.update_id}",
            )

    async def handle_text_message(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle text-only messages with conversation mode (contextual replies).

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

        user_text = update.message.text

        # Helper to recursively extract reply chain texts
        def extract_reply_chain(msg: Any) -> list[str]:
            chain: list[str] = []
            current = msg
            count = 0
            while current and getattr(current, "reply_to_message", None) and count < 10:
                reply = current.reply_to_message
                if getattr(reply, "text", None):
                    chain.insert(0, reply.text)
                current = reply
                count += 1
            return chain

        # Extract context from reply chain if available
        context_messages = []
        if update.message and update.message.reply_to_message:
            context_messages = extract_reply_chain(update.message)
        # Always add current user message at the end
        context_messages.append(user_text)

        try:
            # Generate response using AI with context
            response = await self.settings.genai_client.aio.models.generate_content(
                model=self.settings.model_name,
                contents=cast(list[str | Image.Image | Any | Any], context_messages),
                config=self.settings.genconfig,
            )
            reply_text = ""
            if response.text:
                reply_text = response.text.strip()

            if not reply_text:
                raise ValueError("Empty response from AI")

            await self.reply_to_message(update, reply_text)

        except Exception as e:
            self.settings.logger.error("Error processing message", error=str(e), update_id=update.update_id)
            err: EventDict = format_exc_info(self.settings.logger, "exception", {"exc_info": True})
            self.settings.logger.error("Error processing message", error=err, update_id=update.update_id)
            await self.reply_to_message(
                update,
                f"Sorry, I couldn't process your message. See logs for update ID: {update.update_id}",
            )

    async def handle_diary_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle /diary command to generate a manual diary entry.

        Args:
            update: Telegram update object
            _context: Telegram context object (unused)
        """
        # Check if user is allowed to use the bot
        if not await self.is_user_allowed(update):
            return

        if not update.message:
            return

        try:
            self.settings.logger.info("Processing diary command", update_id=update.update_id)

            # Generate diary entry
            diary_entry = await generate_diary_entry_manual(
                settings=self.settings
            )

            # Reply with the generated diary entry
            await update.message.reply_text(
                text=diary_entry,
                parse_mode="Markdown"
            )

        except Exception:
            err: EventDict = format_exc_info(self.settings.logger, "exception", {"exc_info": True})
            self.settings.logger.error("Error generating diary entry", error=err, update_id=update.update_id)
            await self.reply_to_message(
                update,
                f"Sorry, I encountered an error generating your diary entry. See logs for update ID: {update.update_id}",
            )

    async def handle_rag_request(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle requests to RAG database.

        Args:
            update: Telegram update object
            context: Telegram context object
        """
        # Check if user is allowed to use the bot
        if not await self.is_user_allowed(update):
            return

        if not update.message or not update.message.text or not self.settings.qa_chain:
            return

        self.settings.logger.info("Processing text message", update_id=update.update_id)

        try:
            result: dict[str, Any] = self.settings.qa_chain.invoke({"query": update.message.text})
            reply_text: str = result["result"].strip()
            sources = {doc.metadata["source"] for doc in result["source_documents"]}
            if sources:
                reply_text += "\nSources:"
                for source in sorted(sources):
                    reply_text += f"\n- {source}"
            await self.reply_to_message(update, reply_text)

        except Exception as e:
            self.settings.logger.error("Error processing message", error=str(e), update_id=update.update_id)
            err: EventDict = format_exc_info(self.settings.logger, "exception", {"exc_info": True})
            self.settings.logger.error("Error processing message", error=err, update_id=update.update_id)
            await self.reply_to_message(
                update,
                f"Sorry, I couldn't process your message. See logs for update ID: {update.update_id}",
            )
