# Chat Extractor (Standalone)

ver 1.0.0

Extract AI conversation from clipboard HTML and convert it to Markdown.

> [!IMPORTANT]
> This tool is currently **Windows-only**. It relies on Windows-specific clipboard formats and notification systems.


## Features
- Reads directly from the clipboard (no need to save files manually).
- Supports Windows HTML clipboard format.
- Automatically detects AI models (Gemini, ChatGPT, Claude, etc.).
- Converts HTML/Text to clean Markdown.
- Supports Toast notifications on Windows.
- Configurable output directory and filename formats.

## Quick Start (Windows)

1. **Prerequisites**:
   - **Python 3.10+**: Ensure Python is installed and added to your PATH. Verify with `python --version`.

2. **Install Dependencies**:
   ```bash
   pip install pyperclip beautifulsoup4 PyYAML
   ```

3. **Run the Script**:
   Copy an AI conversation from your browser, then run:
   ```bash
   python run.py
   ```
   > [!TIP]
   > **Recommended**: Providing a clean HTML structure ensures the best Markdown output.
   > 
   > **Workflow**: `Select All (Ctrl+A)` -> `Right Click` -> `Inspect` -> `Navigate to the top of the chat element tree` -> `Right Click` -> `Copy` -> `Copy outer HTML`.

4. **(Optional) Silent Launcher & Hotkey**:
   Use `launch.vbs` to run the script silently (no console window). 
   - **Create Shortcut**: Right-click `launch.vbs` -> `Send to` -> `Desktop (create shortcut)`.
   - **Set Hotkey**: Right-click the new shortcut -> `Properties` -> `Shortcut` tab -> click `Shortcut key` -> press your desired keys (e.g., `Ctrl+Alt+X`) -> `OK`.
   Now you can extract chats instantly with your hotkey.

## Configuration
The tool automatically searches for `config.yaml` in the following order:
1.  **Local Directory**: Same folder as `run.py` (useful for portable use).
2.  **App Data**: `%APPDATA%\ai-chat-extractor\config.yaml` (standard Windows location).

### First-run Setup
If no `config.yaml` is found, the script will launch an **interactive CLI setup** to guide you through basic settings:
- **Output Directory**: Where to save extracted Markdown files.
- **Toast Notifications**: Enable/disable Windows system notifications.

Settings are saved to the `%APPDATA%` location by default.

### Manual Configuration
You can also manually copy `config.default.yaml` to `config.yaml` and modify:
- `output.dir`: Where to save Markdown files.
- `output.filename`: How to name the saved files.
- `clip.enabled`: Whether to copy the result back to the clipboard.
- `clip.notice.toast.enabled`: Show Windows notifications.

## Adding New Models
Add a YAML profile in the `models/` directory. See existing profiles for reference.

## Repository Management
If you're using this as a part of another project, consider adding it as a **Git Submodule**:
```bash
git submodule add https://github.com/gsr-4325/ai-chat-extractor.git scripts/chat_extractor
```
