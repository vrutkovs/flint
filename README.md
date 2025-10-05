# 🔥 Flint

A sophisticated Telegram bot that seamlessly integrates AI capabilities and extensible protocol servers to create your personal digital assistant.

![Python](https://img.shields.io/badge/python-3.13%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
[![codecov](https://codecov.io/gh/vrutkovs/flint/graph/badge.svg?token=LV7KLZWARS)](https://codecov.io/gh/vrutkovs/flint)

## ✨ Overview

Flint transforms your Telegram experience into a powerful command center, bringing together:
- **Advanced AI capabilities** through Google Gemini - just type naturally, no commands needed
- **Extensible functionality** with Model Control Protocol (MCP) servers
- **Intelligent automation** with scheduled tasks and contextual responses

Whether you're analyzing images, checking the weather, managing your calendar, or just chatting with AI, Flint handles it all through a simple Telegram interface. Simply send text messages for AI conversations, or use commands for specific tools and features.

## 🚀 Key Features

### 🤖 AI Intelligence
- **Vision Analysis**: Send photos for instant AI-powered descriptions and analysis
- **Conversational AI**: Natural language interactions with Google Gemini
- **Conversation Mode**: Replies use Telegram's reply chain for stateless multi-turn conversations
- **Context-Aware Responses**: Smart replies based on reply-to-message history
- **Multi-Modal Support**: Process text, images, and structured data
- **Customizable Personality**: Configure system instructions for unique response styles
- **RAG Support**: Integrate your own knowledge base with Retrieval Augmented Generation using LangChain

### 🔌 Extensible Architecture (MCP)
- **Dynamic Plugin System**: Add new capabilities through MCP servers
- **Command Auto-Registration**: Each MCP server becomes a Telegram command
- **Popular Integrations**: GitHub, Calendar, Weather, Filesystem, and more
- **Custom Protocols**: Build your own MCP servers for specialized needs

### 📅 Automation & Scheduling
- **Daily Briefings**: Customizable morning agenda with weather and calendar events
- **Smart Scheduling**: Timezone-aware task automation
- **Calendar Integration**: Sync with your calendar services via MCP
- **Weather Updates**: Real-time weather information via MCP servers

### 🔐 Security First
- **User Allowlisting**: Restrict access to authorized users only
- **Environment-Based Config**: Secure credential management
- **Chat Isolation**: Separate conversations by chat ID
- **Token Security**: Best practices for API key handling

## 📦 Installation

### Prerequisites

- **Python 3.13+** (required for latest features)
- **uv** (recommended) or **pip** for package management
- **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
- **Google Gemini API Key** from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **MCP Servers** for extended functionality (required - at minimum weather and calendar for daily briefings)
- **Node.js** (optional, for npx-based MCP servers)

### Quick Start

After setup, just send a message to your bot - no commands needed for AI chat!

## 🗣️ Conversation Mode

Flint supports conversation mode, allowing the bot to reply using historical context from your chat by traversing the Telegram `reply_to_message` chain. This enables multi-turn, context-aware conversations where the bot uses the actual reply chain for context, making the system stateless and robust.

- The bot automatically extracts previous messages by following the reply chain for each incoming message.
- No configuration is needed—just reply to previous messages and Flint will use the reply chain for smarter, context-aware responses.

### Example

```
User: What's the weather like today?
Bot: The weather is sunny and 22°C.
User (replies to previous bot message): And tomorrow?
Bot: Tomorrow is expected to be partly cloudy with a high of 20°C.
```

The bot understands "And tomorrow?" by using the previous weather question as context, thanks to the reply chain.

### Technical Details

- Conversation context is extracted by recursively traversing the `reply_to_message` chain in Telegram messages.
- No in-memory or persistent history is used; context is stateless and based solely on the reply chain.
- Contextual replies work for both AI and RAG-powered responses.


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

#### Optional: Enhanced Document Support for RAG

For full document format support in RAG, install additional dependencies:
```bash
# For PDF support
pip install "unstructured[pdf]"

# For HTML and web content
pip install "unstructured[html]"

# For all document types
pip install "unstructured[all-docs]"
```

#### 3. Configure Environment

Create a `.env` file in the project root (see `.env.example` for a complete template):

```env
# Core Configuration (Required)
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=-1001234567890
GOOGLE_API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.0-flash-exp

# MCP Configuration (Required)
MCP_CONFIG_PATH=/path/to/mcp_config.yaml
MCP_CALENDAR_NAME=calendar
MCP_WEATHER_NAME=weather

# Optional Features
SCHEDULED_AGENDA_TIME=07:30
TZ=America/New_York
USER_FILTER=allowed_user1,allowed_user2
SYSTEM_INSTRUCTIONS="Custom personality instructions for the bot"
```

💡 **Tip**: Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
# Edit .env with your favorite editor
```

💡 **Tip**: An `.env.example` file is available as a reference template

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
| `MCP_CONFIG_PATH` | MCP config file path | `/home/user/.config/flint/mcp.yaml` |

#### Optional Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MCP_CALENDAR_NAME` | Calendar MCP server name (required for daily briefings) | None | `calendar` |
| `MCP_WEATHER_NAME` | Weather MCP server name (required for daily briefings) | None | `weather` |
| `MCP_TODOIST_NAME` | Todoist MCP server name (required for diary entries) | None | `todoist` |
| `SCHEDULED_AGENDA_TIME` | Daily briefing time | None | `07:30` |
| `SCHEDULED_DIARY_TIME` | Daily diary generation time | `23:59` | `23:59` |
| `DAILY_NOTE_FOLDER` | Directory to save daily diary entries | None | `/home/user/notes` |
| `TZ` | Timezone | `UTC` | `Europe/London` |
| `USER_FILTER` | Allowed usernames (comma-separated) | None | `alice,bob` |
| `SYSTEM_INSTRUCTIONS` | Custom AI personality | Film noir detective | See below |
| `RAG_EMBEDDING_MODEL` | Google Generative AI embedding model | None | `gemini-embedding-001` |
| `RAG_LOCATION` | Local path to knowledge base documents | None | `/path/to/docs` |
| `MCP_{name}_PROMPT` | Custom prompt for specific MCP server | None | See MCP Custom Prompts |

#### Default System Instructions

The bot defaults to a film noir detective persona. You can customize this via the `SYSTEM_INSTRUCTIONS` environment variable:

```env
SYSTEM_INSTRUCTIONS="You are a helpful assistant. Adopt the following persona for your response: The city's a cold, hard place. You're a world-weary film noir detective called Fenton 'Flint' Foster. Deliver the facts, straight, no chaser."
```

#### RAG (Retrieval Augmented Generation) Configuration

Enable RAG to give the bot access to your custom knowledge base using LangChain:

1. **Prepare your documents** in a local directory (supports various formats including PDF, Markdown, text files)
2. **Set the environment variables**:
   - `RAG_EMBEDDING_MODEL`: The Google Generative AI embedding model (e.g., `gemini-embedding-001`)
   - `RAG_LOCATION`: Local filesystem path to your documents directory (e.g., `/home/user/documents`)
   - `RAG_VECTOR_STORAGE`: Local filesystem path to the vector store directory (e.g., `/home/user/vector_store`)

The bot will automatically:
- Load documents from the specified directory
- Split them into chunks for efficient retrieval
- Create embeddings using Google's embedding model
- Store vectors in a persistent Chroma vector store for fast retrieval
- Use LangChain's RetrievalQA chain to answer questions based on your documents

### MCP Server Configuration

Create a YAML configuration file at the path specified by `MCP_CONFIG_PATH`:

```yaml
mcps:
  # Weather Integration (Required for daily briefings)
  weather:
    type: stdio
    enabled: true
    config:
      cmd: npx
      args: ["-y", "@modelcontextprotocol/server-weather"]
      envs:
        OPENWEATHER_API_KEY: ${WEATHER_API_KEY}

  # Calendar Integration (Required for daily briefings)
  calendar:
    type: stdio
    enabled: true
    config:
      cmd: npx
      args: ["-y", "@modelcontextprotocol/server-google-calendar"]
      envs:
        GOOGLE_CALENDAR_CREDENTIALS: ${GOOGLE_CALENDAR_API_KEY}

  # GitHub Integration
  github:
    type: stdio
    enabled: true
    config:
      cmd: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      envs:
        GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}

  # Add more MCP servers as needed
```

Each MCP server automatically becomes a Telegram command with the same name.

#### MCP Custom Prompts

You can customize the system prompt for individual MCP servers by setting environment variables in the format `MCP_{NAME}_PROMPT`, where `{NAME}` is the uppercase name of the MCP server.

For example, to add a custom prompt for the GitHub MCP server:

```env
MCP_GITHUB_PROMPT="You are a GitHub expert assistant. Focus on providing clear, concise information about repositories, issues, and pull requests."
```

This custom prompt will be prepended to the user's message when invoking that specific MCP server, allowing you to tailor the AI's behavior for different integrations.

## 📱 Usage

### Message Handling

Flint processes messages in two ways:
- **Plain text messages** (no command prefix) → Sent directly to Gemini AI
- **Commands** (starting with `/`) → Handled by specific command processors

### Basic Commands

#### 🖼️ Image Analysis
Simply send any photo to the bot:
```
[Send an image]
Bot: "I can see a sunset over the ocean with vibrant orange and purple hues..."
```

#### 💬 AI Chat
Just type your message - no command needed:
```
User: Explain quantum computing in simple terms
Bot: Quantum computing uses quantum bits or "qubits" that can exist in multiple states...
```

#### 📚 RAG Knowledge Base (Optional)
When RAG is configured, use `/rag` to query your documents:
```
/rag What's our deployment process?
Bot: According to the documentation, the deployment process involves...
Sources:
- /docs/deployment-guide.md
- /docs/ci-cd-pipeline.pdf
```

#### 🔧 MCP Server Commands
Each configured MCP server automatically becomes a command:
```
/weather What's the forecast for tomorrow?
/calendar Show events for next week
/github List my pull requests
/filesystem Read /path/to/file.txt
```

You can customize the behavior of each MCP server by setting custom prompts using environment variables (see MCP Custom Prompts section above).

#### 📊 System Commands
```
/list_mcps       # Show all available MCP server commands
/rag <query>     # Query your knowledge base (only when RAG is configured)
```

### Advanced Features

#### Daily Agenda
Configure `SCHEDULED_AGENDA_TIME` to receive a personalized daily briefing with weather and calendar information:
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

#### Daily Diary
Configure `SCHEDULED_DIARY_TIME` and `DAILY_NOTE_FOLDER` to automatically generate daily diary entries as markdown files:

**Required Environment Variables:**
- `SCHEDULED_DIARY_TIME`: Time to generate diary (default: `23:59`)
- `DAILY_NOTE_FOLDER`: Directory where diary files will be saved
- `MCP_CALENDAR_NAME`: Calendar MCP server for events
- `MCP_TODOIST_NAME`: Todoist MCP server for completed tasks

**Generated File Format:**
- Filename: `YYYY-MM-DD.md` (e.g., `2024-03-05.md`)
- Location: `$DAILY_NOTE_FOLDER/YYYY-MM-DD.md`

**Example Generated Diary:**
```markdown
## Diary

### Events
* 09:00 - Team standup meeting completed
* 14:00 - Client meeting in Conference Room B

### Tasks
* 10:30 - Completed project documentation review
* 16:45 - Finished quarterly report submission
```

The bot will send a confirmation message when the diary is successfully saved.

#### Todoist Task Sync
Configure automatic synchronization of your Todoist tasks to Obsidian-compatible markdown notes:

**Required Environment Variables:**
- `TODOIST_API_TOKEN`: Your Todoist API token (get from https://todoist.com/prefs/integrations)
- `TODOIST_NOTES_FOLDER`: Directory where task notes will be saved
- `TODOIST_NOTES_SCHEDULE`: Sync interval (default: `1h`, examples: `30m`, `2h`)

**Features:**
- **Periodic Sync**: Automatically syncs tasks every specified interval
- **Markdown Export**: Each task becomes a separate markdown file named by task ID
- **Frontmatter**: YAML metadata including project, priority, labels, due dates
- **Subtasks**: Child tasks are included as checkboxes in the parent task note
- **Comments**: Task comments are preserved (configurable)
- **User Content**: Preserves any manual notes added after the `---` separator

**Generated File Format:**
```markdown
---
title: "Complete project documentation"
todoist_id: "1234567890"
project: "Work"
priority: 3
priority_text: "Medium"
labels: ["urgent", "documentation"]
completed: false
due_date: "2024-03-15"
tags: ["todoist", "todoist/work", "todoist/priority/medium"]
---

# ⬜ Complete project documentation

## Description
Review and update all API documentation for the new release.

## Subtasks
- [ ] Update endpoint descriptions
- [x] Add new authentication examples
- [ ] Review code samples

## Comments
* 14 Mar 10:30 - Started working on this task
* 14 Mar 15:45 - Need to coordinate with backend team

---

<!-- Your personal notes can go here and will be preserved -->
```

**Setup:**
1. Get your Todoist API token from https://todoist.com/prefs/integrations
2. Set the required environment variables
3. Install the todoist-api-python dependency: `pip install todoist-api-python`
4. Restart Flint - sync will start automatically

The bot will send notifications when sync completes, showing the number of tasks exported.

#### Understanding Message Flow

**Regular Text Messages:**
```
User: Tell me about black holes
→ Processed by Gemini AI
Bot: Black holes are regions in spacetime where gravity is so strong...
```

**RAG Command (when configured):**
```
User: /rag What's our API rate limits?
→ Searches your document knowledge base
Bot: Based on the API documentation, our rate limits are...
Sources:
- /docs/api-reference.md
- /docs/rate-limiting.yaml
```

**MCP Commands:**
```
User: /weather tomorrow in NYC
→ Processed by weather MCP server
Bot: Tomorrow's forecast for New York City: Partly cloudy, high 72°F...
```

The RAG system supports various document formats:
- Plain text files (.txt)
- Markdown files (.md) - included by default
- PDF documents (.pdf) - requires `unstructured[pdf]`
- HTML files (.html) - requires `unstructured[html]`
- Word documents (.docx) - requires `unstructured[docx]`
- And more via the `unstructured` library with appropriate extras

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
│       ├── mcp.py            # MCP server management
│       ├── photo.py          # Image processing
│       └── schedule.py       # Task scheduling
├── .env.example              # Environment variables template
├── pyproject.toml            # Dependencies
├── uv.lock                   # Lock file for dependencies
├── LICENSE                   # Apache 2.0
└── README.md                 # Documentation
```

### Technology Stack

- **Core Framework**: `python-telegram-bot[job-queue]` for Telegram integration
- **AI Engine**: `google-genai` for Gemini AI capabilities
- **RAG Framework**: `langchain` with Google Generative AI embeddings
- **Document Processing**: `langchain-community` and `unstructured[md]` for document loading
- **Vector Storage**: In-memory vector store for fast retrieval
- **Chain Management**: LangChain's RetrievalQA for context-aware responses
- **Embeddings**: Google Generative AI embeddings for semantic search
- **Protocol Support**: `mcp` for Model Control Protocol
- **Image Processing**: `pillow` for image manipulation
- **Logging**: `structlog` for structured logging
- **Configuration**: `python-dotenv` for environment management
- **Timezone Support**: `pytz` for timezone handling
- **YAML Parsing**: `pyyaml` for configuration files

## 🛠️ Development

### Setting Up Development Environment

```bash
# Install development dependencies
make install-dev

# Install pre-commit hooks
make install-pre-commit
```

### Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality and consistency. The hooks will automatically:

- **Format code** with Ruff (line length: 120)
- **Lint code** with Ruff
- **Run tests** with pytest
- **Check** for common issues (trailing whitespace, large files, merge conflicts, etc.)

#### Manual Usage

```bash
# Run all pre-commit hooks on all files
make pre-commit

# Run hooks automatically on git commit (after installation)
git commit -m "Your commit message"

# Update hooks to latest versions
make pre-commit-update
```

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage report
make test-cov

# Run tests directly with pytest
pytest tests/ -v
```

### Code Style

```bash
# Format code with ruff (both formatting and auto-fix)
make format

# Run linting checks only
make lint

# Run type checking
make typecheck
```

### Available Make Commands

```bash
# Show all available commands
make help

# Common commands:
make install          # Install project dependencies
make install-dev      # Install development dependencies
make install-pre-commit # Install pre-commit hooks
make format          # Format code with ruff (formatting + auto-fix)
make lint            # Run linting checks with ruff
make test            # Run unit tests
make test-cov        # Run tests with coverage report
make typecheck       # Run type checking with mypy
make pre-commit      # Run all pre-commit hooks on all files
make clean           # Clean up cache and build files
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

Popular MCP servers you can configure:
- **Weather providers**: OpenWeatherMap, Weather.gov
- **Calendar services**: Google Calendar, CalDAV
- **GitHub integration**: Issues, PRs, Actions
- **Database connections**: PostgreSQL, SQLite
- **Slack integration**: Messages and channels
- **Web search**: Google, DuckDuckGo
- **File system**: Local file operations
- **And many more**: Check the [MCP servers directory](https://github.com/modelcontextprotocol/servers)

## 🐛 Troubleshooting

### Common Issues

<details>
<summary><b>Bot Not Responding</b></summary>

1. Verify your bot token is correct
2. Check if the chat ID matches your conversation
3. Ensure your username is in `USER_FILTER` if configured
4. Check bot permissions in the group/channel
5. Verify the bot is running: check logs for startup errors

</details>

<details>
<summary><b>MCP Commands Not Working</b></summary>

1. Verify MCP configuration file exists and is valid YAML
2. Check MCP server installation: `npx -y @modelcontextprotocol/server-name`
3. Review logs for initialization errors
4. Ensure required environment variables are set
5. Verify both `MCP_CALENDAR_NAME` and `MCP_TODOIST_NAME` match server names in your MCP config
6. For npx-based servers, ensure Node.js is installed and in PATH

</details>

<details>
<summary><b>Daily Agenda Not Sending</b></summary>

1. Verify time format: `HH:MM` (24-hour)
2. Check timezone setting matches your location
3. Ensure both calendar and weather MCP servers are properly configured
4. Verify `MCP_CALENDAR_NAME` and `MCP_WEATHER_NAME` are set (both required for scheduling)
5. Review logs at the scheduled time

**Note**: Both `MCP_CALENDAR_NAME` and `MCP_WEATHER_NAME` must be set for scheduled features to work. If either is missing, scheduling will be disabled with a warning in the logs.

</details>

<details>
<summary><b>Image Analysis Errors</b></summary>

1. Verify Google API key has Gemini API access
2. Check selected model supports vision capabilities (e.g., gemini-2.0-flash-exp)
3. Ensure image size is under 20MB
4. Supported formats: JPEG, PNG, GIF, WebP
5. Check API quotas and rate limits in Google AI Studio

</details>

<details>
<summary><b>RAG Not Working</b></summary>

1. Verify documents exist at `RAG_LOCATION` path
2. Check file permissions for reading documents
3. Ensure `RAG_EMBEDDING_MODEL` is a valid Google model name
4. Verify Google API key has embeddings API access
5. Check logs for document loading errors
6. For PDF/HTML support, install additional dependencies:
   ```bash
   pip install "unstructured[pdf,html]"
   ```

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

### Command Development

When adding new features, consider:
- **Plain text** → Use for AI conversations
- **`/command`** → Use for specific actions or tools
- **MCP servers** → Auto-register as commands

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
- [Model Control Protocol](https://github.com/modelcontextprotocol) for the extensible server architecture

## 📮 Support

- **Issues**: [GitHub Issues](https://github.com/vrutkovs/flint/issues)
- **Discussions**: [GitHub Discussions](https://github.com/vrutkovs/flint/discussions)
- **Security**: Report security vulnerabilities privately via GitHub Security Advisories

---

<p align="center">
Built with ❤️ by <a href="https://github.com/vrutkovs">vrutkovs</a>
</p>
