from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import os
from dataclasses import dataclass, field

from telega.settings import Settings


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


class MCPClient:
    def __init__(self, name: str, server_params: StdioServerParameters, logger: structlog.BoundLogger):
        self.name = name
        self.server_params = server_params
        self.logger = logger

    async def get_response(self, settings: Settings, prompt):
        """Get a response from the MCP"""
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                genconfig = settings.genconfig.copy()
                genconfig.tools = [session]
                genconfig.temperature = 0

                self.logger.debug(f"MCP {self.name} running prompt: {prompt}")
                response = await settings.genai_client.aio.models.generate_content(
                    model=settings.model_name,
                    contents=[
                        prompt,
                    ],
                    config=genconfig,
                )
                self.logger.debug(f"MCP {self.name} response: {response}")
                try:
                    return response.candidates[0].content.parts[0].text #pyright: ignore
                except Exception as e:
                    self.logger.error(f"MCP {self.name} failed to generate a response: {e}")
                    return None


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
            settings: Flint settings instance
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
