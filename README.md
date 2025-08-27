# 🔥 Flint

A sophisticated Telegram bot that seamlessly integrates AI capabilities, smart home automation, and extensible protocol servers to create your personal digital assistant.

![Python](https://img.shields.io/badge/python-3.13%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-supported-blue)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-integrated-red)

## ✨ Overview

Flint transforms your Telegram experience into a powerful command center, bringing together:
- **Advanced AI capabilities** through Google Gemini
- **Extensible functionality** with Model Control Protocol (MCP) servers
- **Intelligent automation** with scheduled tasks and contextual responses

Whether you're analyzing images, controlling your smart home, managing your calendar, or just chatting with AI, Flint handles it all through a simple Telegram interface.

## 🚀 Key Features

### 🤖 AI Intelligence
- **Vision Analysis**: Send photos for instant AI-powered descriptions and analysis
- **Conversational AI**: Natural language interactions with Google Gemini
- **Context-Aware Responses**: Smart replies based on conversation history
- **Multi-Modal Support**: Process text, images, and structured data

### 🏠 Smart Home Control
- **Weather Updates**: Real-time weather information from your HA weather entities

### 🔌 Extensible Architecture (MCP)
- **Dynamic Plugin System**: Add new capabilities through MCP servers
- **Command Auto-Registration**: Each MCP server becomes a Telegram command
- **Popular Integrations**: GitHub, Calendar, Filesystem, and more
- **Custom Protocols**: Build your own MCP servers for specialized needs

### 📅 Automation & Scheduling
- **Daily Briefings**: Customizable morning agenda with personality
- **Smart Scheduling**: Timezone-aware task automation
- **Calendar Integration**: Sync with your calendar services
- **Event Reminders**: Never miss important appointments

### 🔐 Security First
- **User Allowlisting**: Restrict access to authorized users only
- **Environment-Based Config**: Secure credential management
- **Chat Isolation**: Separate conversations by chat ID
- **Token Security**: Best practices for API key handling

## 📦 Installation

### Prerequisites

- **Python 3.13+** (required for latest features)
- **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
- **Google Gemini API Key** from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Home Assistant** instance with long-lived access token (optional)
- **MCP Servers** for extended functionality (optional)

### Quick Start

#### 1. Clone the Repository

```bash
git clone https://github.com/vrutkovs/flint.git
cd flint
```

#### 2. Set Up Python Environment

Using `uv` (recommended):
```bash
uv venv
uv pip install -e .
```

Or using standard `pip`:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

#### 3. Configure Environment

Create a `.env` file in the project root:

```env
# Core Configuration (Required)
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=-1001234567890
GOOGLE_API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.0-flash-exp

# Home Assistant (Required for weather updates in agenda updates)
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token
HA_WEATHER_ENTITY_ID=weather.home

# MCP Configuration (Required for MCP features)
MCP_CONFIG_PATH=/path/to/mcp_config.yaml
SUMMARY_MCP_CALENDAR_NAME=calendar

# Optional Features
SCHEDULED_AGENDA_TIME=07:30
TZ=America/New_York
USER_FILTER=allowed_user1,allowed_user2
```

#### 4. Launch Flint

```bash
python src/main.py
```

## ⚙️ Configuration Guide

### Environment Variables

#### Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_TOKEN` | Bot API token from BotFather | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `TELEGRAM_CHAT_ID` | Target chat/group ID | `-1001234567890` |
| `GOOGLE_API_KEY` | Google AI API key | `AIzaSyA...` |
| `MODEL_NAME` | Gemini model variant | `gemini-2.0-flash-exp` |
| `HA_URL` | Home Assistant URL | `http://192.168.1.100:8123` |
| `HA_TOKEN` | HA access token | `eyJ0eXAi...` |
| `HA_WEATHER_ENTITY_ID` | Weather entity | `weather.home` |
| `MCP_CONFIG_PATH` | MCP config file | `/home/user/.config/flint/mcp.yaml` |
| `SUMMARY_MCP_CALENDAR_NAME` | Calendar MCP name | `calendar` |

#### Optional Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SCHEDULED_AGENDA_TIME` | Daily briefing time | None | `07:30` |
| `TZ` | Timezone | `UTC` | `Europe/London` |
| `USER_FILTER` | Allowed usernames | None | `alice,bob` |

### MCP Server Configuration

Configure MCP servers in a YAML file specified by `MCP_CONFIG_PATH`:

```yaml
mcps:
  # Calendar Integration
  calendar:
    type: stdio
    enabled: true
    config:
      cmd: /usr/local/bin/calendar-mcp
      args: ["--format", "json"]
      env_keys:
        - GOOGLE_CALENDAR_API_KEY

  # GitHub Integration
  github:
    type: stdio
    enabled: true
    config:
      cmd: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      envs:
        GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}

  # Filesystem Access (disabled by default for security)
  filesystem:
    type: stdio
    enabled: false
    config:
      cmd: /usr/local/bin/filesystem-mcp
      args: ["--read-only", "--path", "/safe/directory"]

  # Custom MCP Server
  custom:
    type: stdio
    enabled: true
    config:
      cmd: python
      args: ["/path/to/custom_mcp.py"]
      envs:
        API_KEY: ${CUSTOM_API_KEY}
```

## 📱 Usage

### Basic Commands

#### 🖼️ Image Analysis
Simply send any photo to the bot:
```
[Send an image]
Bot: "I can see a sunset over the ocean with vibrant orange and purple hues..."
```

#### 💬 AI Chat
```
/gemini Explain quantum computing in simple terms
```

#### 🔧 MCP Commands
```
/calendar show events tomorrow
/github list my pull requests
/filesystem read /path/to/file.txt
```

#### 📋 List Available Commands
```
/list_mcps
```

### Advanced Features

#### Daily Agenda
Configure `SCHEDULED_AGENDA_TIME` to receive a personalized daily briefing:
```
🕵️ Morning Report - Tuesday, March 5, 2024

The fog rolls in at 7°C, climbing to 15°C by noon.
Rain expected around 3 PM - pack an umbrella, detective.

Your dance card for today:
• 9:00 AM - Team standup (Zoom)
• 2:00 PM - Client meeting (Conference Room B)
• 5:30 PM - Gym session

Another day in the city that never sleeps...
```

## 🏗️ Architecture

### Project Structure
```
flint/
├── src/
│   ├── main.py                 # Application entry point
│   ├── telega/
│   │   ├── main.py            # Core bot logic
│   │   └── settings.py        # Configuration management
│   └── plugins/
│       ├── homeassistant.py  # HA integration
│       ├── mcp.py            # MCP server management
│       ├── photo.py          # Image processing
│       └── schedule.py       # Task scheduling
├── tests/                     # Test suite
├── .env.example              # Environment template
├── pyproject.toml            # Dependencies
├── LICENSE                   # Apache 2.0
└── README.md                 # Documentation
```

### Technology Stack

- **Core Framework**: `python-telegram-bot` for Telegram integration
- **AI Engine**: `google-genai` for Gemini AI capabilities
- **Smart Home**: `homeassistant-api` for HA communication
- **Protocol Support**: `mcp` for Model Control Protocol
- **Image Processing**: `pillow` for image manipulation
- **Logging**: `structlog` for structured logging
- **Configuration**: `python-dotenv` for environment management

## 🛠️ Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black src/

# Lint
ruff check src/
```

### Creating Custom MCP Servers

Example custom MCP server:

```python
# custom_mcp.py
from mcp import Server, Tool

class CustomMCPServer(Server):
    def __init__(self):
        super().__init__("custom-server")

    @Tool("get_data")
    async def get_data(self, query: str) -> str:
        # Your custom logic here
        return f"Data for: {query}"

if __name__ == "__main__":
    server = CustomMCPServer()
    server.run()
```

## 🐛 Troubleshooting

### Common Issues

<details>
<summary><b>Bot Not Responding</b></summary>

1. Verify your bot token is correct
2. Check if the chat ID matches your conversation
3. Ensure your username is in `USER_FILTER` if configured
4. Check bot permissions in the group/channel

</details>

<details>
<summary><b>MCP Commands Not Working</b></summary>

1. Verify MCP configuration file exists and is valid YAML
2. Check MCP server installation: `which your-mcp-server`
3. Review logs for initialization errors
4. Ensure required environment variables are set

</details>

<details>
<summary><b>Daily Agenda Not Sending</b></summary>

1. Verify time format: `HH:MM` (24-hour)
2. Check timezone setting matches your location
3. Ensure calendar MCP is properly configured
4. Review logs at the scheduled time

</details>

<details>
<summary><b>Image Analysis Errors</b></summary>

1. Verify Google API key has Gemini API access
2. Check selected model supports vision capabilities
3. Ensure image size is under 20MB
4. Supported formats: JPEG, PNG, GIF, WebP

</details>

### Debug Mode

Enable verbose logging by setting:
```bash
export LOG_LEVEL=DEBUG
python src/main.py
```

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Keep commits atomic and descriptive

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for the excellent Telegram API wrapper
- [Google Gemini](https://deepmind.google/technologies/gemini/) for powerful AI capabilities
- [Home Assistant](https://www.home-assistant.io/) for the amazing home automation platform
- [Model Control Protocol](https://github.com/modelcontextprotocol) for the extensible server architecture

## 📮 Support

- **Issues**: [GitHub Issues](https://github.com/vrutkovs/flint/issues)
- **Discussions**: [GitHub Discussions](https://github.com/vrutkovs/flint/discussions)
- **Security**: Report security vulnerabilities privately via GitHub Security Advisories

---

<p align="center">
Built with ❤️ by <a href="https://github.com/vrutkovs">vrutkovs</a>
</p>
