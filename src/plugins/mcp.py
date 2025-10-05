import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import structlog
import yaml
from mcp import ClientSession, StdioServerParameters, stdio_client
from PIL import Image

from telega.settings import Settings

__all__ = [
    "MCPClient",
    "MCPConfigReader",
    "MCPConfiguration",
    "StdioServerParameters",
]


@dataclass
class MCPConfiguration:
    """Configuration for a single MCP (Model Control Protocol) instance."""

    name: str
    type: str
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.name:
            raise ValueError("MCP name cannot be empty")
        if not self.type:
            raise ValueError("MCP type cannot be empty")

    async def get_server_params(self) -> StdioServerParameters:
        """
        Get server parameters for the MCP.

        Returns:
            StdioServerParameters configured for this MCP

        Raises:
            ValueError: If no command is specified for the MCP
        """
        envs: dict[str, str] = self.config.get("envs", {})
        if not envs:
            env_keys: list[str] = self.config.get("env_keys", [])
            for key in env_keys:
                envs[key] = os.environ.get(key, "")

        # Handle different command field names (cmd for extensions format, command for legacy)
        command: str = self.config.get("cmd") or self.config.get("command", "")
        if not command:
            raise ValueError(f"No command specified for MCP '{self.name}'")

        return StdioServerParameters(command=command, args=self.config.get("args", []), env=envs)


class MCPClient:
    def __init__(
        self,
        name: str,
        server_params: StdioServerParameters,
        logger: structlog.BoundLogger,
    ) -> None:
        """
        Initialize MCP client.

        Args:
            name: Name of the MCP
            server_params: Server parameters for stdio connection
            logger: Structured logger instance
        """
        self.name: str = name
        self.server_params: StdioServerParameters = server_params
        self.logger: structlog.BoundLogger = logger

    async def get_response(self, settings: Settings, prompt: str) -> str | None:
        """
        Get a response from the MCP.

        Args:
            settings: Telega settings instance
            prompt: User prompt to process

        Returns:
            Response text from the MCP or None if failed
        """
        async with stdio_client(self.server_params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()

            genconfig = settings.genconfig.copy()
            if not genconfig.tools:
                tools: list[Any] = []
            else:
                tools = list(genconfig.tools)
            tools.append(session)
            genconfig.tools = tools
            genconfig.temperature = 0

            # Check if env var has a custom prompt for this MCP
            custom_prompt: str | None = os.getenv(f"MCP_{self.name}_PROMPT") or os.getenv(
                f"MCP_{self.name.upper()}_PROMPT"
            )
            prompt = f"{custom_prompt}\n{prompt.strip()}" if custom_prompt else prompt.strip()

            self.logger.debug(f"MCP {self.name} running prompt: {prompt}")
            response = await settings.genai_client.aio.models.generate_content(
                model=settings.model_name,
                contents=cast(list[str | Image.Image | Any | Any], [prompt]),
                config=genconfig,
            )
            self.logger.debug(f"MCP {self.name} response: {response}")

            # Robust extraction with None checks
            try:
                candidates = getattr(response, "candidates", None)
                if not candidates or not isinstance(candidates, list) or not candidates:
                    self.logger.error(f"MCP {self.name}: response.candidates is missing or empty")
                    return None

                candidate = candidates[0]
                content = getattr(candidate, "content", None)
                if not content:
                    self.logger.error(f"MCP {self.name}: candidate.content is missing")
                    return None

                parts = getattr(content, "parts", None)
                if not parts or not isinstance(parts, list) or not parts:
                    self.logger.error(f"MCP {self.name}: content.parts is missing or empty")
                    return None

                part = parts[0]
                text = getattr(part, "text", None)
                if not text or not isinstance(text, str):
                    self.logger.error(f"MCP {self.name}: part.text is missing or not a string")
                    return None

                return text.strip()
            except Exception as e:
                self.logger.error(f"MCP {self.name} failed to generate a response: {e}")
                return None


class MCPConfigReader:
    """
    A class to read and manage MCP configurations from YAML files.

    This class handles loading, parsing, and validating MCP configurations
    from YAML files, providing easy access to configured MCPs.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the MCP configuration reader.

        Args:
            settings: Flint settings instance
        """
        self.logger: structlog.BoundLogger = settings.logger
        self.config_path: Path = Path(settings.mcp_config_path)
        self.mcps: dict[str, MCPConfiguration] = {}
        self._raw_config: dict[str, Any] = {}

    def load_config(self) -> None:
        """
        Load configuration from YAML file.

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            self.logger.warning(f"MCP configuration file not found at {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, encoding="utf-8") as file:
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
        """
        Parse the raw configuration into MCP objects.

        Raises:
            ValueError: If configuration is invalid
        """
        self.mcps.clear()

        mcp_configs: dict[str, Any] = self._raw_config["extensions"]  # Extensions format

        for name, config in mcp_configs.items():
            try:
                mcp: MCPConfiguration = self._create_mcp_configuration(name, config)
                self.mcps[name] = mcp
                self.logger.debug(f"Loaded MCP configuration: {name}")
            except Exception as e:
                self.logger.error(f"Failed to parse MCP '{name}': {e}")
                raise ValueError(f"Invalid MCP configuration for '{name}'") from e

    def _create_mcp_configuration(self, name: str, config: str | dict[str, Any]) -> MCPConfiguration:
        """
        Create an MCP configuration object from raw config data.

        Args:
            name: Name of the MCP
            config: Raw configuration dictionary or string

        Returns:
            MCPConfiguration object

        Raises:
            ValueError: If configuration is invalid
        """
        if isinstance(config, str):
            # Simple string configuration (just type)
            return MCPConfiguration(name=name, type=config)

        # Extract configuration fields
        mcp_type: str = str(config.get("type", config.get("command", "")))
        enabled: bool = config.get("enabled", True)
        mcp_config: dict[str, Any] = config.get("config", {})
        metadata: dict[str, Any] = config.get("metadata", {})

        # Handle extensions format
        if "cmd" in config:
            # This is the extensions format
            mcp_config = {
                "cmd": config.get("cmd"),
                "args": config.get("args", []),
                "envs": config.get("envs", {}),
                "env_keys": config.get("env_keys", []),
                "timeout": config.get("timeout", 300),
                "bundled": config.get("bundled"),
            }
            metadata = {
                "description": config.get("description", ""),
                "name": config.get("name", name),
            }
        # Handle legacy args format
        elif "args" in config and not mcp_config:
            mcp_config = {"args": config["args"]}

        # Handle legacy formats
        if not mcp_type and "command" in config:
            mcp_type = "command"
            mcp_config = {"command": config["command"]}
            if "args" in config:
                mcp_config["args"] = config["args"]

        return MCPConfiguration(
            name=name,
            type=mcp_type,
            enabled=enabled,
            config=mcp_config,
            metadata=metadata,
        )

    def get_mcp_configuration(self, name: str) -> MCPConfiguration | None:
        """
        Get a specific MCP configuration by name.

        Args:
            name: Name of the MCP

        Returns:
            MCPConfiguration object or None if not found
        """
        return self.mcps.get(name)

    def get_enabled_mcps(self) -> dict[str, MCPConfiguration]:
        """
        Get all enabled MCP configurations.

        Returns:
            Dictionary of enabled MCP configurations
        """
        return {name: mcp for name, mcp in self.mcps.items() if mcp.enabled}

    def get_mcps_by_type(self, mcp_type: str) -> list[MCPConfiguration]:
        """
        Get all MCPs of a specific type.

        Args:
            mcp_type: Type of MCP to filter by

        Returns:
            List of MCPConfiguration objects
        """
        return [mcp for mcp in self.mcps.values() if mcp.type == mcp_type]

    def list_mcp_names(self) -> list[str]:
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
        """Return string representation of MCPConfigReader."""
        return f"MCPConfigReader(config_path='{self.config_path}', mcps={len(self.mcps)})"

    def __len__(self) -> int:
        """Return number of MCPs configured."""
        return len(self.mcps)

    def __contains__(self, name: str) -> bool:
        """Check if MCP with given name exists."""
        return name in self.mcps

    def __iter__(self) -> Iterator[tuple[str, MCPConfiguration]]:
        """Iterate over MCP configurations."""
        return iter(self.mcps.items())
