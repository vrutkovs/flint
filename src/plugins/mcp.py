from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import json
import os
from dataclasses import dataclass, field
from contextlib import asynccontextmanager, AsyncExitStack

from telega.settings import Settings

from google.genai import types as genai_types

from mcp import ClientSession, StdioServerParameters, stdio_client

import structlog

@dataclass
class MCPConfiguration:
    """Configuration for a single MCP (Model Control Protocol) instance."""
    name: str
    type: str
    enabled: bool = True
    config: dict = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.name:
            raise ValueError("MCP name cannot be empty")
        if not self.type:
            raise ValueError("MCP type cannot be empty")

    async def get_server_params(self):
        envs = self.config.get('envs', {})
        if not envs:
            env_keys = self.config.get('env_keys', [])
            for key in env_keys:
                envs[key] = os.environ.get(key, '')

        # Handle different command field names (cmd for extensions format, command for legacy)
        command = self.config.get('cmd') or self.config.get('command', '')
        if not command:
            raise ValueError(f"No command specified for MCP '{self.name}'")

        return StdioServerParameters(
            command=command,
            args=self.config.get('args', []),
            env=envs
        )


def clean_schema(schema: genai_types.Schema):
    if isinstance(schema, dict):
        # schema.pop("title", None)
        schema.pop("$schema", None)
        if "properties" in schema and isinstance(schema["properties"], dict):
            for key in schema["properties"]:
                schema["properties"][key] = clean_schema(schema["properties"][key])
        schema.pop("additionalProperties", None)
        schema.pop("additional_properties", None)
        for k, v in schema.items():
            v = clean_schema(v)
    return schema


class MCPClient:
    def __init__(self, name: str, server: StdioServerParameters, logger: structlog.BoundLogger):
        self.name = name
        self.server = server
        self._client_session = None
        self._exit_stack = None
        self.logger = logger

    @asynccontextmanager
    async def initialize(self):
        """Initialize the client connection using AsyncExitStack"""
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(self.server))
            mcp_client = await stack.enter_async_context(ClientSession(read, write))
            await mcp_client.initialize()
            self._client_session = mcp_client
            yield mcp_client

    async def call_tool(self, name, arguments):
        """Call a tool by name with given arguments"""
        if not self._client_session:
            raise RuntimeError("Client not initialized")
        return await self._client_session.call_tool(name=name, arguments=arguments)

    async def list_tools(self):
        """List available tools"""
        if not self._client_session:
            raise RuntimeError("Client not initialized")
        return await self._client_session.list_tools()

    async def get_response(self, settings: Settings, prompt):
        """Get a response from the MCP"""
        async with self.initialize() as mcp_session:
            mcp_tools = await mcp_session.list_tools()
            tools = [
                genai_types.Tool(
                    function_declarations=[
                        genai_types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters=clean_schema(tool.inputSchema),
                        )
                    ]
                )
                for tool in mcp_tools.tools
            ]
            self.logger.info(f"MCP {self.name} available tools: {[t.name for t in mcp_tools.tools]}")

            final_text = []
            config = genai_types.GenerateContentConfig(
                temperature=0,
                tools=tools,
            )
            self.logger.info(f"MCP {self.name} starting a new chat")
            chat_history = []
            chat = settings.genai_client.chats.create(
                model=settings.model_name,
                config=config,
                history=chat_history
            )
            final_text = []
            messages = []
            messages.append({"role": "user", "content": prompt})

            try:
                self.logger.debug(f"MCP {self.name} sending '{prompt}'")
                response = chat.send_message(prompt)
                self.logger.info(f"Response: {response}")

                # Process the response
                final_text, messages = await self._process_gemini_response(
                    response,
                    final_text,
                    messages,
                    settings.model_name,
                    config,
                    settings.genai_client,
                )

            except Exception as e:
                self.logger.error(f"Error in Gemini processing: {str(e)}", exc_info=True)
                final_text.append(f"I encountered an error while processing your request: {str(e)}")

            return "\n".join(final_text), messages

    def _parse_gemini_function_args(self, function_call):
        """Parse function arguments from Gemini function call."""
        tool_args = {}
        try:
            if hasattr(function_call.args, "items"):
                for k, v in function_call.args.items():
                    tool_args[k] = v
            else:
                # Fallback if it's a string
                args_str = str(function_call.args)
                if args_str.strip():
                    tool_args = json.loads(args_str)
        except Exception as e:
            self.logger.error(f"Failed to parse function args: {e}", exc_info=True)
        return tool_args

    async def _process_gemini_response(self, response, final_text, messages, model, config, genai_client):
        """Process the response from Gemini, including any function calls."""
        if not hasattr(response, "candidates") or not response.candidates:
            self.logger.warning("No candidates in Gemini response")
            final_text.append("I couldn't generate a proper response.")
            return final_text, messages

        candidate = response.candidates[0]
        if not hasattr(candidate, "content") or not hasattr(candidate.content, "parts"):
            self.logger.warning("No content or parts in Gemini response")
            final_text.append("I received an incomplete response.")
            return final_text, messages

        # Process text and function calls
        for part in candidate.content.parts:
            # Process text part
            if hasattr(part, "text") and part.text:
                final_text.append(part.text)

            # Process function call part
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                tool_name = function_call.name

                # Parse tool arguments
                tool_args = self._parse_gemini_function_args(function_call)

                # Add function call info to response
                function_call_text = f"I need to call the {tool_name} function to help with your request."
                final_text.append(function_call_text)

                # Execute tool call
                try:
                    self.logger.debug(f"Calling tool {tool_name} with args {tool_args}...")
                    # final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                    result = await self._client_session.call_tool(tool_name, tool_args)
                    # final_text.append(f"[tool results: {result}]")
                    self.logger.debug(f"tool {tool_name} result: {result}")

                    # Create a function response and send to Gemini for follow-up
                    final_text, messages = await self._handle_tool_result(
                        tool_name,
                        function_call,
                        result,
                        final_text,
                        messages,
                        model,
                        config,
                        genai_client
                    )
                except Exception as e:
                    error_msg = f"Error executing tool {tool_name}: {str(e)}"
                    self.logger.error(error_msg, exc_info=True)
                    final_text.append(error_msg)

        return final_text, messages

    async def _handle_tool_result(self, tool_name, function_call, result, final_text, messages, model, config, genai_client):
            """Handle the result of a tool call and get follow-up response."""
            try:
                # Prepare function response
                function_response_part = genai_types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result.content if hasattr(result, "content") else str(result)},
                )

                # Prepare contents for follow-up
                contents = [
                    genai_types.Content(
                        role="model",
                        parts=[genai_types.Part(function_call=function_call)]
                    )
                ]

                # Add to messages history
                messages.append({
                    "role": "assistant",
                    "content": function_call.model_dump_json()
                })

                # Add function response to contents
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=[function_response_part]
                    )
                )

                # Add to messages history
                result_content = result.content if hasattr(result, "content") else str(result)
                messages.append({
                    "role": "user",
                    "content": {"result": result_content}
                })

                # Send function response to get final answer
                follow_up_response = genai_client.models.generate_content(
                    model=model,
                    config=config,
                    contents=contents,
                )

                # Extract text from follow-up response
                if hasattr(follow_up_response, "candidates") and follow_up_response.candidates:
                    follow_up_candidate = follow_up_response.candidates[0]
                    if (hasattr(follow_up_candidate, "content") and
                        hasattr(follow_up_candidate.content, "parts")):

                        follow_up_text = ""
                        for follow_up_part in follow_up_candidate.content.parts:
                            if hasattr(follow_up_part, "text"):
                                follow_up_text += follow_up_part.text

                        if follow_up_text:
                            final_text.append(follow_up_text)
                            messages.append({
                                "role": "assistant",
                                "content": follow_up_text
                            })
                        else:
                            final_text.append("I received the tool results but couldn't generate a follow-up response.")

                else:
                    final_text.append("I processed your request but couldn't generate a follow-up response.")

            except Exception as e:
                self.logger.error(f"Error in follow-up response: {str(e)}", exc_info=True)
                final_text.append(f"I received the tool results but encountered an error: {str(e)}")

            return final_text, messages

        #     if not response:
        #         raise ValueError("No response received")
        #     candidates = response.candidates
        #     if not candidates:
        #         raise ValueError("No candidate found")
        #     content = candidates[0].content
        #     if not content:
        #         raise ValueError("No content found")
        #     parts = content.parts
        #     if not parts:
        #         raise ValueError("No parts found")
        #     if not parts[0].function_call:
        #         return response.text

        #     function = parts[0].function_call
        #     self.logger.info(f"Calling {function}")
        #     if not function:
        #         raise ValueError("No function found")
        #     result = await mcp_client.call_tool(
        #         name=function.name, arguments=function.args
        #     )
        #     response_text = None
        #     for content in result.content:
        #         if content.type == "text":
        #             response_text = content
        #             break
        #     self.logger.info(f"Result: {response_text}")
        #     settings.genai_client.aio.chats.create(
        #         messages=[{"role": "user", "content": response_text}]
        #     )
        #     return response_text
        # return


class MCPConfigReader:
    """
    A class to read and manage MCP configurations from YAML files.

    This class handles loading, parsing, and validating MCP configurations
    from YAML files, providing easy access to configured MCPs.
    """

    def __init__(self, settings: Settings):
        """
        Initialize the MCP configuration reader.

        Args:
            settings: TeleHelper settings instance
        """
        self.logger = settings.logger
        self.config_path = Path(settings.mcp_config_path)
        self.mcps: Dict[str, MCPConfiguration] = {}
        self._raw_config: Dict[str, Any] = {}

    def load_config(self) -> None:
        if not self.config_path.exists():
            self.logger.warning(f"MCP configuration file not found at {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._raw_config = yaml.safe_load(file) or {}

            self.logger.info(f"Loaded MCP configuration from {self.config_path}")
            self._parse_configuration()

        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse YAML configuration: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to load MCP configuration: {e}")
            raise

    def _parse_configuration(self) -> None:
        """Parse the raw configuration into MCP objects."""
        self.mcps.clear()

        mcp_configs = self._raw_config['extensions']  # Extensions format

        if not isinstance(mcp_configs, dict):
            raise ValueError("MCP configuration must be a dictionary")

        for name, config in mcp_configs.items():
            try:
                mcp = self._create_mcp_configuration(name, config)
                self.mcps[name] = mcp
                self.logger.debug(f"Loaded MCP configuration: {name}")
            except Exception as e:
                self.logger.error(f"Failed to parse MCP '{name}': {e}")
                raise ValueError(f"Invalid MCP configuration for '{name}': {e}")

    def _create_mcp_configuration(self, name: str, config: Dict[str, Any]) -> MCPConfiguration:
        """
        Create an MCP configuration object from raw config data.

        Args:
            name: Name of the MCP
            config: Raw configuration dictionary

        Returns:
            MCPConfiguration object
        """
        if isinstance(config, str):
            # Simple string configuration (just type)
            return MCPConfiguration(name=name, type=config)

        if not isinstance(config, dict):
            raise ValueError(f"MCP configuration for '{name}' must be a dictionary or string")

        # Extract configuration fields
        mcp_type = config.get('type', config.get('command', ''))
        enabled = config.get('enabled', True)
        mcp_config = config.get('config', {})
        metadata = config.get('metadata', {})

        # Handle extensions format
        if 'cmd' in config:
            # This is the extensions format
            mcp_config = {
                'cmd': config.get('cmd'),
                'args': config.get('args', []),
                'envs': config.get('envs', {}),
                'env_keys': config.get('env_keys', []),
                'timeout': config.get('timeout', 300),
                'bundled': config.get('bundled'),
            }
            metadata = {
                'description': config.get('description', ''),
                'name': config.get('name', name),
            }
        # Handle legacy args format
        elif 'args' in config and not mcp_config:
            mcp_config = {'args': config['args']}

        # Handle legacy formats
        if not mcp_type and 'command' in config:
            mcp_type = 'command'
            mcp_config = {'command': config['command']}
            if 'args' in config:
                mcp_config['args'] = config['args']

        return MCPConfiguration(
            name=name,
            type=mcp_type,
            enabled=enabled,
            config=mcp_config,
            metadata=metadata
        )

    def get_mcp_configuration(self, name: str) -> Optional[MCPConfiguration]:
        """
        Get a specific MCP configuration by name.

        Args:
            name: Name of the MCP

        Returns:
            MCPConfiguration object or None if not found
        """
        return self.mcps.get(name)

    def get_enabled_mcps(self) -> Dict[str, MCPConfiguration]:
        """
        Get all enabled MCP configurations.

        Returns:
            Dictionary of enabled MCP configurations
        """
        return {name: mcp for name, mcp in self.mcps.items() if mcp.enabled}

    def get_mcps_by_type(self, mcp_type: str) -> List[MCPConfiguration]:
        """
        Get all MCPs of a specific type.

        Args:
            mcp_type: Type of MCP to filter by

        Returns:
            List of MCPConfiguration objects
        """
        return [mcp for mcp in self.mcps.values() if mcp.type == mcp_type]

    def list_mcp_names(self) -> List[str]:
        """
        Get a list of all MCP names.

        Returns:
            List of MCP names
        """
        return list(self.mcps.keys())

    def reload_config(self) -> None:
        """Reload the configuration from file."""
        self.load_config()

    def validate_configuration(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.mcps:
            self.logger.warning("No MCPs configured")
            return True

        for name, mcp in self.mcps.items():
            if not mcp.name or not mcp.type:
                raise ValueError(f"MCP '{name}' has invalid configuration")

        self.logger.info(f"Configuration validated successfully. {len(self.mcps)} MCPs loaded.")
        return True

    def __repr__(self) -> str:
        return f"MCPConfigReader(config_path='{self.config_path}', mcps={len(self.mcps)})"

    def __len__(self) -> int:
        return len(self.mcps)

    def __contains__(self, name: str) -> bool:
        return name in self.mcps

    def __iter__(self):
        return iter(self.mcps.items())
