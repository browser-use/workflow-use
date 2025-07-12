# Voice Recording Setup Guide

This guide helps you set up voice recording functionality for Workflow Use.

## Prerequisites

### 1. Install System Dependencies

**macOS:**
```bash
# Install portaudio (required for pyaudio)
brew install portaudio

# Install ffmpeg (required for Whisper)
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
# Install portaudio
sudo apt-get install portaudio19-dev

# Install ffmpeg
sudo apt-get install ffmpeg
```

**Windows:**
- Download and install [PortAudio](http://www.portaudio.com/download.html)
- Download and install [FFmpeg](https://ffmpeg.org/download.html)

### 2. Install Python Dependencies

The voice recording functionality requires these Python packages:

```bash
# If using uv (recommended)
uv sync

# If using pip
pip install SpeechRecognition pyaudio openai-whisper
```

## Usage

### Basic Voice Recording

```bash
# Enable voice recording
python cli.py create-workflow --voice
```

### Text-Only Fallback

If voice recording dependencies are not available, the system will automatically fall back to text input:

```bash
# This will work even without voice recording dependencies
python cli.py create-workflow --voice
# System will prompt for text input instead
```

## How It Works

1. **Voice Recording**: Records 10 seconds of audio from your microphone
2. **Transcription**: Uses OpenAI Whisper to convert speech to text
3. **Fallback**: If Whisper fails, tries Google Speech Recognition
4. **Text Input**: Allows additional text instructions
5. **Combination**: Combines voice and text into a single prompt
6. **Workflow Generation**: Uses the combined prompt for better workflow generation

## Troubleshooting

### Common Issues

**1. "portaudio.h not found"**
```bash
# macOS
brew install portaudio

# Linux
sudo apt-get install portaudio19-dev
```

**2. "ffmpeg not found"**
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt-get install ffmpeg
```

**3. Microphone not working**
- Check system microphone permissions
- Ensure microphone is not muted
- Try a different microphone

**4. Whisper transcription fails**
- Check internet connection (for Google fallback)
- Ensure OpenAI API key is set
- Try speaking more clearly

### Fallback Behavior

If any voice recording dependencies are missing, the system will:

1. Detect missing dependencies
2. Automatically switch to text-only input
3. Continue with workflow creation
4. Show a message about the fallback

### Testing Voice Recording

You can test the voice recording functionality:

```bash
# Test voice recording (if dependencies installed)
python -c "
from workflow_use.recorder.service import record_voice_prompt
result = record_voice_prompt(duration=5)
print(f'Transcription: {result}')
"
```

## Example Voice Prompts

Good voice prompts for workflow creation:

- "I want to search for products on Amazon"
- "Fill out this contact form with my information"
- "Navigate to the login page and enter credentials"
- "Search for restaurants in my area"
- "Book a flight from New York to London"

## Advanced Configuration

### Custom Recording Duration

You can modify the recording duration in `workflow_use/recorder/service.py`:

```python
def record_voice_prompt(duration: int = 10) -> Optional[str]:
    # Change the default duration here
```

### Using Different Whisper Models

You can specify different Whisper models for better accuracy:

```python
# In record_voice_prompt function
model = whisper.load_model("base")  # Options: "tiny", "base", "small", "medium", "large"
```

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Ensure all system dependencies are installed
3. Verify Python dependencies are correctly installed
4. Test with the text-only fallback first

The voice recording feature is designed to gracefully degrade to text input if any dependencies are missing, so the workflow creation process will always work. 