# Chat Extractor (Standalone Version)

ver 1.0.0

Extracts conversations with AI from HTML in the clipboard and converts them to Markdown format.

> [!IMPORTANT]
> This tool is currently **Windows only**. It depends on Windows-specific clipboard formats and notification systems.

## Features
- Read directly from clipboard (no manual file saving required)
- Support for Windows HTML clipboard format
- Auto-detect AI models (Gemini, ChatGPT, Claude, etc.)
- Convert HTML/text to clean Markdown
- Support for Windows toast notifications
- Customizable output directory and filename format

## Quick Start (Windows)

1. **Prerequisites**:
   - **Python 3.10+**: Make sure Python is installed and added to PATH. You can verify with `python --version` in the terminal.

2. **Install dependencies**:
   ```bash
   pip install pyperclip beautifulsoup4 PyYAML
   ```

3. **Run the script**:
   Copy a conversation with AI from your browser and run:
   ```bash
   python run.py
   ```
   > [!TIP]
   > **Recommended**: Provide a clean HTML structure for the best Markdown output.
   >
   > **Workflow**: `Select All (Ctrl+A)` -> `Right-click` -> `Inspect` -> `Navigate to the top of the chat element tree` -> `Right-click` -> `Copy` -> `Copy outer HTML`.

4. **(Optional) Silent Launcher & Hotkey**:
   You can use `launch.vbs` to run the script without showing a console window.
   - **Create shortcut**: Right-click `launch.vbs` -> `Send to` -> `Desktop (create shortcut)`.
   - **Set hotkey**: Right-click the created shortcut -> `Properties` -> `Shortcut` tab -> Click `Shortcut key` -> Press any key (e.g., `Ctrl+Alt+X`) -> `OK`.
   Now you can extract chats with a single hotkey.

## Command-line Usage
You can also run the script with arguments:

```bash
# Extract from clipboard (default)
python run.py

# Extract from specific file
python run.py "C:\path\to\chat.html"

# Show debug logs
python run.py --debug

# Advanced: Save raw clipboard data (Base64) for debugging
python run.py --save-raw raw_clipboard.txt

# Advanced: Test processing using saved raw data
python run.py --test raw_clipboard.txt
```

## Configuration
The tool automatically searches for `config.yaml` in this order:
1. **Local directory**: Same folder as `run.py` (convenient for portable use)
2. **App Data**: `%APPDATA%\ai-chat-extractor\config.yaml` (Windows standard location)

### First-time Setup
If `config.yaml` is not found, the script will start an **interactive CLI setup** to guide you through basic configuration:
- **Output directory**: Where to save extracted Markdown files
- **Toast notification**: Enable/disable Windows system notifications

Settings are saved by default to the `%APPDATA%` location.

### Manual Configuration
You can also copy `config.default.yaml` to `config.yaml` and modify settings directly:
- `output.dir`: Where to save Markdown files
- `output.filename`: Filename format for saved files
- `clip.enabled`: Whether to write results back to clipboard
- `clip.notice.toast.enabled`: Whether to show Windows notifications

## Adding New Models
Add YAML profiles to the `models/` directory. Refer to existing profiles as examples.

## Repository Management
If you use this tool as part of another project, consider adding it as a **Git Submodule**:
```bash
git submodule add https://github.com/gsr-4325/ai-chat-extractor.git scripts/chat_extractor
```
