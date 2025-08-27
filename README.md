# Flint

A powerful Telegram bot that integrates with Google Gemini AI, Home Assistant, and MCP (Model Control Protocol) servers to provide intelligent assistance and home automation capabilities.

## Features

### 🤖 AI-Powered Intelligence
- **Image Analysis**: Send photos to get AI-generated descriptions using Google Gemini
- **Text Processing**: Chat with Gemini AI for general assistance via `/gemini` command
- **Smart Responses**: Context-aware responses powered by Google's latest AI models

### 🏠 Home Assistant Integration
- **Weather Forecasts**: Get weather updates from your Home Assistant setup
- **Home Automation**: Access and control your smart home devices
- **Daily Briefings**: Automated morning agenda with weather and calendar events

### 🔧 MCP (Model Control Protocol) Integration
- **Extensible Architecture**: Connect to various MCP servers for specialized functionality
- **Dynamic Commands**: Each enabled MCP becomes a Telegram command
- **Configuration Flexibility**: YAML-based configuration for MCP servers
- **List Available MCPs**: Use `/list_mcps` to see all enabled MCP servers

### 📅 Scheduling & Automation
- **Daily Agenda**: Automated morning briefing with a film noir detective persona
- **Calendar Integration**: Sync with calendar services via MCP
- **Timezone Support**: Properly handle different timezones for scheduled tasks

### 🔒 Security Features
- **User Filtering**: Restrict bot access to specific Telegram usernames
- **Secure Token Management**: Environment-based configuration for sensitive data
- **Chat Isolation**: Responses limited to configured chat IDs

## Installation

### Prerequisites
- Python 3.13 or higher
- Telegram Bot Token (obtain from [@BotFather](https://t.me/botfather))
- Google Gemini API Key
- Home Assistant instance (optional)
- MCP servers (optional)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/vrutkovs/flint.git
cd flint
```

2. Install dependencies using uv:
```bash
uv pip install -e .
```

3. Create a `.env` file with your configuration (see Configuration section)

4. Run the bot:
```bash
python src/main.py
```

## Configuration

Flint uses environment variables for configuration. Create a `.env` file in the project root with the following variables:

### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_TOKEN` | Your Telegram Bot API token | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `TELEGRAM_CHAT_ID` | Telegram chat ID where the bot will operate | `-1001234567890` |
| `GOOGLE_API_KEY` | Google Gemini API key for AI features | `AIzaSy...` |
| `MODEL_NAME` | Google Gemini model to use | `gemini-2.0-flash-exp` |
| `HA_URL` | Home Assistant instance URL | `http://homeassistant.local:8123` |
| `HA_TOKEN` | Home Assistant long-lived access token | `eyJ0eXAiOiJKV1...` |
| `HA_WEATHER_ENTITY_ID` | Weather entity ID in Home Assistant | `weather.home` |
| `MCP_CONFIG_PATH` | Path to MCP configuration YAML file | `/path/to/mcp_config.yaml` |
| `SUMMARY_MCP_CALENDAR_NAME` | Name of the MCP server for calendar integration | `calendar` |

### Optional Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SCHEDULED_AGENDA_TIME` | Time for daily agenda (HH:MM format) | Not set | `07:30` |
| `TZ` | Timezone for scheduled tasks | `UTC` | `Europe/Prague` |
| `USER_FILTER` | Comma-separated list of allowed Telegram usernames | Empty (all users allowed) | `user1,user2,user3` |

### Example `.env` file:

```env
# Telegram Configuration
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=-1001234567890

# Google AI Configuration
GOOGLE_API_KEY=your_gemini_api_key_here
MODEL_NAME=gemini-2.0-flash-exp

# Home Assistant Configuration
HA_URL=http://192.168.1.100:8123
HA_TOKEN=your_ha_token_here
HA_WEATHER_ENTITY_ID=weather.home

# MCP Configuration
MCP_CONFIG_PATH=/home/user/.config/mcp/config.yaml
SUMMARY_MCP_CALENDAR_NAME=calendar

# Optional Settings
SCHEDULED_AGENDA_TIME=07:30
TZ=Europe/Prague
USER_FILTER=johndoe,janedoe
```

## MCP Configuration

MCP (Model Control Protocol) servers extend the bot's functionality. Configure them in a YAML file:

### Example MCP Configuration (`mcp_config.yaml`):

```yaml
mcps:
  calendar:
    type: stdio
    enabled: true
    config:
      cmd: /path/to/calendar-mcp
      args: []
      env_keys:
        - CALENDAR_API_KEY

  github:
    type: stdio
    enabled: true
    config:
      cmd: npx
      args: 
        - -y
        - "@modelcontextprotocol/server-github"
      envs:
        GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}

  filesystem:
    type: stdio
    enabled: false
    config:
      cmd: /usr/local/bin/filesystem-mcp
      args:
        - "--read-only"
```

Each enabled MCP becomes available as a Telegram command. For example:
- `/calendar list events today` - Interacts with calendar MCP
- `/github search repos tensorflow` - Uses GitHub MCP
- `/list_mcps` - Shows all available MCP commands

## Usage

### Basic Commands

1. **Send a Photo**: Simply send any image to the bot, and it will provide an AI-generated description

2. **Text Chat**: Use the `/gemini` command followed by your message:
   ```
   /gemini What's the weather like today?
   ```

3. **MCP Commands**: Use any enabled MCP as a command:
   ```
   /calendar show events for tomorrow
   /github list my recent pull requests
   ```

4. **List Available MCPs**:
   ```
   /list_mcps
   ```

### Daily Agenda

If `SCHEDULED_AGENDA_TIME` is configured, the bot will automatically send a daily briefing at the specified time. The briefing includes:
- Weather forecast from Home Assistant
- Calendar events for the next 24 hours
- All delivered in a film noir detective persona

## Architecture

### Project Structure
```
flint/
├── src/
│   ├── main.py              # Application entry point
│   ├── telega/
│   │   ├── main.py          # Main Telegram bot handler
│   │   └── settings.py      # Configuration management
│   └── plugins/
│       ├── homeassistant.py # Home Assistant integration
│       ├── mcp.py           # MCP server management
│       ├── photo.py         # Image processing
│       └── schedule.py      # Scheduled tasks
├── tests/                   # Test suite
├── pyproject.toml          # Project dependencies
└── README.md               # This file
```

### Key Components

- **Telega Class**: Core bot logic and message handling
- **Settings Class**: Centralized configuration management
- **MCP Integration**: Dynamic command registration and execution
- **Plugin System**: Modular architecture for features
- **Structured Logging**: Comprehensive logging with structlog

## Dependencies

Main dependencies include:
- `python-telegram-bot` - Telegram Bot API wrapper
- `google-genai` - Google Gemini AI integration
- `homeassistant-api` - Home Assistant API client
- `mcp` - Model Control Protocol support
- `pillow` - Image processing
- `structlog` - Structured logging
- `python-dotenv` - Environment variable management
- `pytz` - Timezone handling
- `pyyaml` - YAML configuration parsing

## Security Considerations

1. **API Keys**: Never commit API keys or tokens to version control
2. **User Filtering**: Always configure `USER_FILTER` in production to limit access
3. **Chat ID**: Use specific chat IDs to prevent unauthorized access
4. **Token Security**: Use environment variables or secure vaults for sensitive data
5. **Home Assistant**: Ensure your HA instance is properly secured if exposed to the internet

## Troubleshooting

### Common Issues

1. **Bot doesn't respond**:
   - Check if the bot token is correct
   - Verify the chat ID matches where you're sending messages
   - Check if your username is in `USER_FILTER` (if configured)

2. **MCP commands not working**:
   - Verify MCP configuration file path
   - Check if the MCP server is properly installed
   - Review logs for MCP initialization errors

3. **Daily agenda not sending**:
   - Verify `SCHEDULED_AGENDA_TIME` format (HH:MM)
   - Check timezone configuration
   - Ensure calendar MCP is properly configured

4. **Image analysis fails**:
   - Verify Google API key is valid
   - Check if the selected model supports vision
   - Ensure image format is supported (JPEG, PNG, etc.)

### Logging

The bot uses structured logging. Check logs for detailed error messages and debugging information. Each message includes an `update_id` for tracking specific interactions.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is open source. Please check the repository for license details.

## Support

For issues, questions, or suggestions, please open an issue on the GitHub repository.