# Live Voice Translation

A real-time voice translation assistant powered by Azure OpenAI VoiceLive API. Translates conversations between two languages in real-time with low latency.

## Features

✨ **Real-time Translation** - Instant audio-to-audio translation between two languages  
🎙️ **Voice Interface** - Speak naturally, get translated responses immediately  
🌐 **Multi-language Support** - Supports 10+ languages including Spanish, French, German, Chinese, Japanese, etc.  
⚙️ **Web Interface** - Web-based UI for easy access  
🔧 **Configurable** - Customize voice, language pair, and behavior via environment variables  
📝 **Logging** - Optional file-based or console logging  

## Prerequisites

- Python 3.8+
- Azure OpenAI VoiceLive API access (with valid credentials)
- Microphone and speakers for audio input/output
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) for authentication

## Quick Start

### 1. Clone and Set Up

```bash
# Clone the repository
git clone <repository-url>
cd live-voice-translation

# Create Python virtual environment (optional but recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Azure

```bash
# Log in to Azure
az login

# Verify you have access to your subscription
az account show
```

### 3. Set Up Environment Variables

```bash
# Copy the example configuration
cp .env.example .env

# Edit .env with your actual Azure credentials
# Required fields to fill in:
# - AZURE_VOICELIVE_ENDPOINT
# - AZURE_SUBSCRIPTION_ID
# - AZURE_VOICELIVE_PROJECT_NAME
# - AZURE_LOCATION
# - AZURE_ENV_NAME

nano .env  # or use your preferred editor
```

See [Configuration](#configuration) section for details on each variable.

### 4. Run the Application

Choose one of the two options below:

#### Option A: Web Interface (Recommended)

```bash
# Start the FastAPI server
uvicorn server:app --reload

# Open browser to:
# http://localhost:8000
```

The web interface provides:
- Visual start/stop buttons
- Real-time transcript display
- Easy language selection
- Responsive design

#### Option B: Command Line

```bash
# Run the translator directly
python main.py

# With custom settings:
python main.py \
  --voice "en-US-Guy:DragonHDLatestNeural" \
  --verbose
```

### 5. Use the Translator

1. **Start translation:**
   - Web: Click "Start"
   - CLI: Wait for "VOICE ASSISTANT READY"

2. **Specify languages:**
   - Agent asks: "Which two languages would you like me to translate between?"
   - You respond: "Spanish and English"

3. **Confirm:**
   - Agent confirms: "I will translate between Spanish and English. You may now begin."

4. **Start translating:**
   - Speak in one language
   - Get instant translation in the other

5. **Stop:**
   - Web: Click "Stop"
   - CLI: Press `Ctrl+C`

## Installation Details

### Full Step-by-Step Guide

The quick start covers basic setup. Here's more detail:

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd live-voice-translation
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Azure credentials:**
   ```bash
   az login
   ```

4. **Configure environment variables** (see [Configuration](#configuration) section)

## Configuration

Copy and update the `.env` file with your Azure credentials:

```bash
# Azure VoiceLive API
AZURE_VOICELIVE_ENDPOINT="your-endpoint-url"
AZURE_VOICELIVE_MODEL="gpt-realtime"
AZURE_VOICELIVE_VOICE="en-US-Ava:DragonHDLatestNeural"

# Azure project settings
AZURE_VOICELIVE_PROJECT_NAME="your-project-name"
AZURE_VOICELIVE_API_VERSION="2025-10-01"

# Logging
ENABLE_LOGGING=true  # Set to false to disable file logging

# Instructions file
AZURE_VOICELIVE_INSTRUCTIONS_FILE="system_instructions.txt"
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_VOICELIVE_ENDPOINT` | Azure VoiceLive API endpoint | Required |
| `AZURE_VOICELIVE_MODEL` | Model to use for translation | `gpt-realtime` |
| `AZURE_VOICELIVE_VOICE` | TTS voice for response audio | `en-US-Ava:DragonHDLatestNeural` |
| `AZURE_VOICELIVE_INSTRUCTIONS_FILE` | Path to system instructions file | `system_instructions.txt` |
| `ENABLE_LOGGING` | Enable/disable log file generation | `true` |

### Supported Voices

- `en-US-Ava:DragonHDLatestNeural`
- `en-US-Guy:DragonHDLatestNeural`
- Or specify OpenAI voices: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

### Supported Languages

- Spanish, French, German, Italian, Portuguese
- Japanese, Korean, Chinese (Simplified & Traditional)
- Arabic, Russian, Hindi
- And more...

## Usage

### Web Interface (Recommended)

1. **Start the server:**
   ```bash
   uvicorn server:app --reload
   ```

2. **Open in browser:**
   ```
   http://localhost:8000
   ```

3. **Use the interface:**
   - Click "Start" to begin
   - Specify the two languages you want to translate between
   - Speak in either language, get translations in the other
   - Click "Stop" to end session

### Command Line

1. **Run the assistant directly:**
   ```bash
   python main.py
   ```

2. **Specify settings via arguments:**
   ```bash
   python main.py \
     --endpoint "your-endpoint-url" \
     --model "gpt-realtime" \
     --voice "en-US-Ava:DragonHDLatestNeural" \
     --verbose
   ```

3. **Speak naturally:**
   - Wait for agent to ask for the two languages
   - Say the language pair (e.g., "Spanish and English")
   - Confirm the setup
   - Start translating!

## How It Works

### Translation Workflow

```
User speaks in Language A
    ↓
Audio captured and sent to Azure VoiceLive
    ↓
Speech-to-text conversion
    ↓
Translation to Language B (LLM)
    ↓
Text-to-speech synthesis
    ↓
Audio response played back
```

### Language Confirmation

The assistant requires explicit confirmation of the language pair upfront:

1. **Agent asks:** "Which two languages would you like me to translate between?"
2. **User responds:** "Spanish and English"
3. **Agent confirms:** "I will translate between Spanish and English. You may now begin."
4. **Translation begins**

This ensures clarity and prevents misunderstandings.

## Project Structure

```
live-voice-translation/
├── main.py                          # Core translator logic
├── server.py                        # FastAPI web server
├── system_instructions.txt          # Agent behavior instructions
├── requirements.txt                 # Python dependencies
├── .env                             # Configuration (secrets)
├── README.md                        # This file
├── logs/                            # Log files (if enabled)
├── web/                             # Web frontend
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── QUICK_GUIDE.md                   # Quick start guide
```

## Key Files Explained

### `main.py`
- **AudioProcessor** - Handles audio capture and playback
- **BasicVoiceAssistant** - Main translation logic
- Core event handling and session management

### `server.py`
- FastAPI server with WebSocket support
- REST endpoint for web interface
- AssistantManager for lifecycle management

### `system_instructions.txt`
- System prompt for the AI agent
- Defines translation behavior and rules
- Version controlled in git for collaboration

## Logging

### Enabled (default)
```
ENABLE_LOGGING=true
```
- Creates `logs/` folder
- Writes to timestamped files: `logs/YYYY-MM-DD_HH-MM-SS_voicelive.log`
- Includes all debug, info, and error messages

### Disabled
```
ENABLE_LOGGING=false
```
- No log files created
- Output to console only
- Useful for development

### View Logs
```bash
# Show latest log
cat logs/$(ls -t logs | head -1)

# Follow logs in real-time (web server)
tail -f logs/[timestamp]_voicelive.log
```

## Troubleshooting

### "AZURE_VOICELIVE_ENDPOINT not set"
- Verify `.env` file exists
- Check `AZURE_VOICELIVE_ENDPOINT` is configured
- Run: `echo $AZURE_VOICELIVE_ENDPOINT` to verify

### "No audio input devices found"
- Check microphone is connected
- Run: `python -c "import pyaudio; p = pyaudio.PyAudio(); print([p.get_device_info_by_index(i) for i in range(p.get_device_count())])"`
- Ensure audio drivers are installed

### "Connection failed"
- Verify Azure credentials: `az account show`
- Check endpoint URL is correct
- Ensure network connectivity to Azure

### "Translations are too verbose"
- Check `system_instructions.txt` - instructions may need refinement
- See [INSTRUCTION_IMPROVEMENTS.md](INSTRUCTION_IMPROVEMENTS.md) for tuning guidance

### Server won't start
- Check port 8000 is available: `netstat -an | grep 8000` (or `netstat -ano | findstr :8000` on Windows)
- Try different port: `uvicorn server:app --port 8001`

## Development

### Enable Verbose Logging
```bash
# Command line
python main.py --verbose

# Or set env var
export LOGGING_LEVEL=DEBUG
```

### Run Tests
```bash
# Check code quality
pylint main.py server.py

# Type checking
mypy main.py server.py
```

### Modify Instructions
1. Edit `system_instructions.txt`
2. Restart server
3. Test behavior
4. Commit changes to git

See [INSTRUCTION_IMPROVEMENTS.md](INSTRUCTION_IMPROVEMENTS.md) for detailed guidance on improving agent behavior.

## Performance Tips

**For faster translations:**
- Use `gpt-4-realtime-preview` model (more responsive)
- Lower temperature in session config (0.6 vs 0.8-1.0)
- Use high-performance TTS voices

**For better accuracy:**
- Use `gpt-4-realtime-preview` model
- Ensure clear audio input (quiet environment)
- Speak at normal pace

**For lower latency:**
- Reduce VAD silence duration
- Optimize network connection
- Use SSD for log storage

## API Documentation

### WebSocket Endpoint (`/ws`)

Bidirectional WebSocket for real-time translation control.

**Messages sent to server:**
```json
{
  "type": "start",
  "text": "optional initial message"
}
```

```json
{
  "type": "stop"
}
```

**Messages received from server:**
```json
{
  "type": "status",
  "message": "Ready"
}
```

```json
{
  "type": "transcript_done",
  "text": "User's transcribed speech"
}
```

```json
{
  "type": "assistant_done",
  "text": "Translation response"
}
```

## Contributing

To improve the project:

1. Test your changes thoroughly
2. Update instructions in `system_instructions.txt` if needed
3. Commit changes with clear messages
4. Test across different language pairs

## Supported Models

- `gpt-4-realtime-preview` (Recommended - best instruction following)
- `gpt-4-turbo-realtime` (Good accuracy and speed)
- `gpt-realtime` (Faster, good for basic use)

## License

[Add your license here]

## Support

For issues or questions:
1. Check [QUICK_GUIDE.md](QUICK_GUIDE.md) for quick answers
2. Review logs for error details
3. See [INSTRUCTION_IMPROVEMENTS.md](INSTRUCTION_IMPROVEMENTS.md) for tuning guidance
4. Check Azure VoiceLive documentation

## Resources

- [Azure OpenAI VoiceLive Documentation](https://learn.microsoft.com/azure/ai-services/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Azure CLI Documentation](https://learn.microsoft.com/cli/azure/)

## Roadmap

- [ ] Multi-language group conversations (3+ languages)
- [ ] Custom voice cloning
- [ ] Translation quality metrics
- [ ] Batch processing for documents
- [ ] Mobile app
- [ ] Offline mode with local models

---

**Last Updated:** February 3, 2026  
**Version:** 1.0.0
