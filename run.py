#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chat Extractor - Extract AI conversation from clipboard HTML

This script reads HTML content from the clipboard (supporting Windows HTML format),
detects the AI model format, and converts the conversation into Markdown.
The result is copied back to the clipboard if configured.
"""

import sys
import json
import yaml
import re
import os
import time
import tempfile
import datetime as dt
import subprocess
import argparse
from pathlib import Path
from bs4 import BeautifulSoup, Comment
import pyperclip

# --- Global State ---
args = None

# --- Lock ---
_LOCK_DIR = Path(tempfile.gettempdir()) / "chat_extractor"
_LOCK_FILE = _LOCK_DIR / "chat_extractor.lock"
_LOCK_MAX_AGE = 300  # seconds before a lock file is considered stale (crash recovery)

def acquire_lock() -> bool:
    """Try to acquire a process lock. Returns True if acquired, False if another instance is running."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    if _LOCK_FILE.exists():
        age = time.time() - _LOCK_FILE.stat().st_mtime
        if age < _LOCK_MAX_AGE:
            return False  # Active lock held by another instance
        _LOCK_FILE.unlink(missing_ok=True)  # Stale lock (e.g. previous crash)
    _LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True

def release_lock():
    _LOCK_FILE.unlink(missing_ok=True)

def log_debug(msg):
    if args and args.debug:
        print(f"DEBUG: {msg}", file=sys.stderr)

def log_warn(msg):
    # Always show warnings unless we want to be very quiet
    print(f"WARN: {msg}", file=sys.stderr)

# --- Configuration ---

def get_config_paths():
    """Get candidate paths for config.yaml and the folder for storage."""
    base_dir = Path(__file__).resolve().parent
    local_path = base_dir / "config.yaml"
    
    appdata = os.environ.get("APPDATA")
    if appdata:
        appdata_dir = Path(appdata) / "ai-chat-extractor"
        appdata_path = appdata_dir / "config.yaml"
    else:
        appdata_dir = None
        appdata_path = None
        
    return {
        "local": local_path,
        "appdata": appdata_path,
        "appdata_dir": appdata_dir,
        "default": base_dir / "config.default.yaml"
    }

def interactive_setup(config_paths):
    """Run an interactive CLI setup to create the initial config.yaml."""
    print("\n=== Chat Extractor: First Time Setup ===")
    print("Welcome! No configuration file found. Let's set up the basics.\n")
    
    # Default output directory
    default_out = "outputs/chat_logs"
    user_out = input(f"Enter output directory (default: {default_out}): ").strip()
    if not user_out:
        user_out = default_out
        
    # Toast notification toggle
    user_toast = input("Enable Windows Toast notifications? (y/n) [y]: ").strip().lower()
    toast_enabled = user_toast != 'n'
    
    new_config = {
        "output": {
            "dir": user_out
        },
        "clip": {
            "notice": {
                "toast": {
                    "enabled": toast_enabled
                }
            }
        }
    }
    
    target_path = config_paths["appdata"] or config_paths["local"]
    target_dir = config_paths["appdata_dir"]
    
    if target_dir and not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {target_dir}: {e}")
            target_path = config_paths["local"]
            
    print(f"\nSaving configuration to: {target_path}")
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(new_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print("Setup complete!\n")
    except Exception as e:
        print(f"Failed to save configuration: {e}")
        
    return new_config

def load_config():
    """Load configuration from config.default.yaml and override with config.yaml."""
    paths = get_config_paths()
    default_path = paths["default"]
    
    config = {
        "clip": {"enabled": True, "notice": {"toast": {"enabled": True}, "sound": {"enabled": True}}},
        "output": {
            "enabled": True,
            "dir": "outputs/chat_logs",
            "filename": "chat_log_{time}_{model}.md"
        },
        "time_format": "%Y%m%d_%H%M%S",
        "year_format": "%Y",
        "month_format": "%m",
        "date_format": "%Y%m%d",
        "removes": []
    }
    
    def deep_merge(target, source):
        for k, v in source.items():
            if k in target and isinstance(target[k], dict) and isinstance(v, dict):
                deep_merge(target[k], v)
            else:
                target[k] = v

    def load_file(path):
        if not path or not path.exists(): return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            def normalize(d):
                if isinstance(d, dict):
                    return {k: normalize(v) for k, v in d.items()}
                if isinstance(d, list):
                    return [normalize(i) for i in d]
                if isinstance(d, str) and d.lower() in ("true", "false"):
                    return d.lower() == "true"
                return d
            return normalize(data)
        except Exception as e:
            log_warn(f"Failed to load {path.name}: {e}")
            return {}

    # Migrate old JSON config to YAML if it exists
    def migrate_json_to_yaml(json_path, yaml_path):
        if json_path and json_path.exists() and not yaml_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                with open(yaml_path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                json_path.rename(json_path.with_name(json_path.name + ".bak"))
                log_debug(f"Migrated {json_path.name} to {yaml_path.name}")
            except Exception as e:
                log_warn(f"Migration from JSON to YAML failed: {e}")

    migrate_json_to_yaml(paths["local"].with_suffix(".json"), paths["local"])
    if paths["appdata"]:
        migrate_json_to_yaml(paths["appdata"].with_suffix(".json"), paths["appdata"])

    # 1. Load defaults
    deep_merge(config, load_file(default_path))
    
    # 2. Check for user overrides (Priority: Local > AppData)
    user_config_data = {}
    if paths["local"].exists():
        user_config_data = load_file(paths["local"])
    elif paths["appdata"] and paths["appdata"].exists():
        user_config_data = load_file(paths["appdata"])
    else:
        # No user config found -> First run setup
        user_config_data = interactive_setup(paths)
        
    deep_merge(config, user_config_data)
    
    # Post-process JS-like tokens to Python strftime tokens
    token_map = {
        "yyyy": "%Y", "MM": "%m", "dd": "%d",
        "HH": "%H", "mm": "%M", "ss": "%S"
    }
    for key in ("time_format", "year_format", "month_format", "date_format"):
        if key in config:
            fmt = str(config[key])
            for js_tok, py_tok in token_map.items():
                fmt = fmt.replace(js_tok, py_tok)
            config[key] = fmt
                
    return config

def show_toast(config, model_name, summary, turn_count=0, filepath: Path = None):
    """Show Windows Toast notification via PowerShell.
    If filepath is provided, clicking the toast will open the file."""
    clip_cfg = config.get("clip", {})
    if not isinstance(clip_cfg, dict): return
    if not clip_cfg.get("enabled"): return

    notice = clip_cfg.get("notice", {})
    toast = notice.get("toast", {})
    if not toast.get("enabled"): return

    turns_str = str(turn_count)
    title = toast.get("title", "Chat Extracted ({model}) [{turns} turns]").replace("{ai model}", model_name).replace("{model}", model_name).replace("{turns}", turns_str).replace("{n}", turns_str)
    msg = toast.get("message", "{short summary}").replace("{ai model}", model_name).replace("{model}", model_name).replace("{short summary}", summary).replace("{turns}", turns_str).replace("{n}", turns_str)
    
    sound = notice.get("sound", {})
    is_silent = not sound.get("enabled", True)
    
    # Click behavior
    open_on_click = toast.get("open_on_click", True)
    can_open = filepath and filepath.exists() and open_on_click

    # Building PowerShell command
    silent_snippet = ""
    if is_silent:
        silent_snippet = '$audio = $xml.CreateElement("audio"); $audio.SetAttribute("silent", "true"); $xml.GetElementsByTagName("toast")[0].AppendChild($audio) | Out-Null'

    if not can_open:
        # Simple fire-and-forget toast
        ps_code = f"""
$appId = "ChatExtractor"
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$xml = [xml]$template.GetXml()
$xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode("{title}")) | Out-Null
$xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode("{msg}")) | Out-Null
{silent_snippet}
$toastXml = New-Object Windows.Data.Xml.Dom.XmlDocument
$toastXml.LoadXml($xml.OuterXml)
$toast = New-Object Windows.UI.Notifications.ToastNotification $toastXml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
""".strip()
    else:
        # Interactive toast that waits for events
        # We use Unregister-Event and long timeout to ensure the process lives long enough to handle the click
        abs_path = str(filepath.absolute()).replace("'", "''")
        ps_code = f"""
$appId = "ChatExtractor"
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$xml = [xml]$template.GetXml()
$xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode("{title}")) | Out-Null
$xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode("{msg}")) | Out-Null
{silent_snippet}
$toastXml = New-Object Windows.Data.Xml.Dom.XmlDocument
$toastXml.LoadXml($xml.OuterXml)
$toast = New-Object Windows.UI.Notifications.ToastNotification $toastXml

$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)

# Register events
$onActivated = Register-ObjectEvent -InputObject $toast -EventName Activated -Action {{
    Invoke-Item '{abs_path}'
    $global:toastActionDone = $true
}}
$onDismissed = Register-ObjectEvent -InputObject $toast -EventName Dismissed -Action {{
    $global:toastActionDone = $true
}}
$onFailed = Register-ObjectEvent -InputObject $toast -EventName Failed -Action {{
    $global:toastActionDone = $true
}}

$notifier.Show($toast)

# Wait for interaction or timeout (approx 15s)
$timeout = 15
$timer = 0
while (-not $global:toastActionDone -and $timer -lt $timeout) {{
    Start-Sleep -Seconds 1
    $timer++
}}

# Cleanup
Unregister-Event -SourceIdentifier $onActivated.Name
Unregister-Event -SourceIdentifier $onDismissed.Name
Unregister-Event -SourceIdentifier $onFailed.Name
""".strip()

    # Base64 encoding for PowerShell to avoid escaping issues
    import base64
    encoded_ps = base64.b64encode(ps_code.encode("utf-16le")).decode("ascii")
    full_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand {encoded_ps}'
    
    # Per user rule: always use cmd /c start /min cmd /c
    # We use a separate process so run.py doesn't hang while waiting for the toast
    subprocess.Popen(f'cmd /c start /min cmd /c "{full_cmd}"', shell=True)


def show_status_toast(config, title: str, message: str):
    """Show a fast, always-silent status toast (processing / busy) via direct PowerShell.
    Uses no cmd /c layers so it appears more quickly than show_toast."""
    clip_cfg = config.get("clip", {})
    if not isinstance(clip_cfg, dict): return
    if not clip_cfg.get("enabled"): return
    notice = clip_cfg.get("notice", {})
    toast = notice.get("toast", {})
    if not toast.get("enabled"): return

    ps_code = f"""
$appId = "ChatExtractor"
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$xml = [xml]$template.GetXml()
$xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode("{title}")) | Out-Null
$xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode("{message}")) | Out-Null
$audio = $xml.CreateElement("audio"); $audio.SetAttribute("silent", "true"); $xml.GetElementsByTagName("toast")[0].AppendChild($audio) | Out-Null
$toastXml = New-Object Windows.Data.Xml.Dom.XmlDocument
$toastXml.LoadXml($xml.OuterXml)
$toast = New-Object Windows.UI.Notifications.ToastNotification $toastXml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
""".strip()
    import base64
    encoded_ps = base64.b64encode(ps_code.encode("utf-16le")).decode("ascii")
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded_ps],
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
    )

def try_repair_mojibake(text: str) -> str:
    """Repair strings where UTF-8 bytes were misinterpreted as Latin-1 or other single-byte encodings."""
    # Common problem: UTF-8 bytes read as Latin-1 (ã ® -> の) or CP1252
    # If the text already has high-code characters that don't look like mojibake (e.g. Japanese), skip
    if any(ord(c) > 0x1000 for c in text):
        return text

    for enc in ['latin-1', 'cp1252']:
        try:
            # Try to encode back to original bytes
            # Latin-1 works for 00-FF, CP1252 handles the "smart quotes" range 80-9F
            repaired_bytes = text.encode(enc)
            repaired_text = repaired_bytes.decode('utf-8')
            
            # Heuristic: if repaired text has CJK characters, it's probably correct
            if any(ord(c) >= 0x3000 for c in repaired_text):
                return repaired_text
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text

def get_clipboard_raw_b64():
    """Get raw clipboard data as Base64 string from PowerShell."""
    if sys.platform != "win32":
        return None
    
    try:
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$do = [Windows.Forms.Clipboard]::GetDataObject(); "
            "$data = $null; "
            "if ($do.GetFormats() -contains 'Html') { $data = $do.GetData('Html') } "
            "else { $data = [Windows.Forms.Clipboard]::GetText() } "
            "if ($data) { "
            "  if ($data -is [System.IO.MemoryStream]) { $bytes = $data.ToArray() } "
            "  else { $bytes = [System.Text.Encoding]::UTF8.GetBytes($data.ToString()) } "
            "  [Convert]::ToBase64String($bytes) "
            "}"
        )
        cmd = ["powershell", "-NoProfile", "-Command", ps_cmd]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.decode('ascii', errors='ignore').strip()
    except Exception:
        pass
    return None

def get_clipboard_html():
    """Attempt to get HTML or Text from clipboard using a robust Base64 transfer from PowerShell."""
    b64_str = get_clipboard_raw_b64()
    if b64_str:
        import base64
        try:
            raw_bytes = base64.b64decode(b64_str)
            try:
                full_raw = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                full_raw = raw_bytes.decode('cp932', errors='replace')
            
            full_raw = try_repair_mojibake(full_raw)
            
            if "StartFragment:" in full_raw:
                match = re.search(r'<!--StartFragment-->(.*)<!--EndFragment-->', full_raw, re.DOTALL)
                if match: return match.group(1)
            return full_raw
        except Exception as e:
            log_debug(f"Clipboard decoding error: {e}")
    
    return try_repair_mojibake(pyperclip.paste())

# --- Logic from scripts/collector ---

def load_profiles() -> dict[str, dict]:
    models_dir = Path(__file__).resolve().parent / "models"
    profiles = {}
    if not models_dir.exists(): return {}
    for p_path in models_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(p_path.read_text(encoding="utf-8"))
            if data:
                profiles[p_path.stem] = data
        except Exception as e:
            log_warn(f"Failed to load profile {p_path.name}: {e}")
    return profiles

def detect_profile(soup: BeautifulSoup, profiles: dict[str, dict]) -> tuple[str, dict]:
    for key, profile in profiles.items():
        if profile.get("method") == "tag_stream":
            for tag in profile.get("tags", []):
                if soup.find(tag): return key, profile
        elif profile.get("method") == "container_list":
            sel = profile.get("container_selector")
            if sel and soup.select_one(sel): return key, profile
        elif profile.get("method") == "turn_list":
            sel = profile.get("detect_selector") or profile.get("turn_selector")
            if sel and soup.select_one(sel): return key, profile
        elif profile.get("method") == "sequence_pair":
            sel = profile.get("scope_selector")
            if sel and soup.select_one(sel): return key, profile

    # Fallback search for model names
    text_content = soup.get_text().lower()
    if "gemini" in text_content: return "gemini", profiles.get("gemini", {})
    if "chatgpt" in text_content: return "chatgpt", profiles.get("chatgpt", {})
    
    for key, profile in profiles.items():
        if profile.get("is_default"): return key, profile
    return "unknown", {}

def clean_fragment_html(fragment_html: str) -> str:
    # Use 'html.parser' but be careful with fragment behavior
    soup = BeautifulSoup(fragment_html, "html.parser")
    for tag_name in ("script", "style", "noscript", "svg", "path", "button", "mat-icon", "nav", "aside"):
        for el in soup.find_all(tag_name): el.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)): comment.extract()
    
    # Return inner HTML of body or the whole thing if no body
    if soup.body:
        return "".join(str(c) for c in soup.body.children).strip()
    return "".join(str(c) for c in soup.children).strip()

def detect_role(tag, profile: dict) -> str:
    """Detects role (user/ai) for a tag using attributes or child selectors."""
    role_attr = profile.get("role_attr")
    if role_attr:
        val = tag.get(role_attr)
        if val in profile.get("role_map", {}):
            return profile["role_map"][val]
            
    # Check content selectors as fallback
    for role_key, selectors in profile.get("content_selectors", {}).items():
        for sel in selectors:
            if tag.select_one(f":scope {sel}") or tag.select_one(sel):
                return role_key
    return "unknown"

def extract_content_by_selectors(tag, selectors, fallback_html=True) -> str:
    parts: list[str] = []; found = False
    for sel in selectors:
        # Check if the tag itself matches the selector
        if tag.select_one(f":scope > {sel}") or tag.select_one(sel):
             el = tag.select_one(sel)
             if el: parts.append(el.decode_contents()); found = True; break
    
    if not found and fallback_html:
        # If no internal content element found, treat the whole tag's content as the message
        parts.append(tag.decode_contents())
    
    return clean_fragment_html("\n".join(p for p in parts if p and p.strip()))

def extract_turns_from_soup(soup: BeautifulSoup, profile: dict) -> list[dict[str, str]]:
    main_sel = profile.get("main_selector")
    if main_sel:
        main = soup.select_one(main_sel)
        if main: soup = main

    turns: list[dict[str, str]] = []
    
    # Try Regex detection for plain text first if no tags found or as extra measure
    text_content = soup.get_text("\n")
    if not soup.find(): # No tags, likely plain text
        # Simple line-based turn detection
        lines = text_content.split("\n")
        current_role, current_lines = None, []
        # Support basic model identification and various header styles
        user_patterns = [r"^(You|User) said$", r"^You$", r"^User$", r"^##\s*User$", r"^User:$"]
        ai_patterns = [r"^(Gemini|ChatGPT|Claude|AI) said$", r"^(Gemini|ChatGPT|Claude|AI)$", r"^##\s*AI$", r"^(Gemini|ChatGPT|Claude|AI):$"]
        
        def flush():
            if current_role and current_lines:
                text = "\n".join(current_lines).strip()
                if text: turns.append({"role": current_role, "html": f"<p>{text}</p>"})
        
        for line in lines:
            line = line.strip()
            if not line: continue
            is_user = any(re.match(p, line, re.I) for p in user_patterns)
            is_ai = any(re.match(p, line, re.I) for p in ai_patterns)
            
            if is_user:
                flush(); current_role, current_lines = "user", []
            elif is_ai:
                flush(); current_role, current_lines = "ai", []
            elif current_role:
                current_lines.append(line)
        flush()
        if turns: return turns

    method = profile.get("method", "tag_stream")
    if method == "tag_stream":
        tags, role_map = profile.get("tags", []), profile.get("role_map", {})
        content_selectors = profile.get("content_selectors", {})
        fallback_ai = profile.get("fallback_ai_text", False)
        for tag in soup.find_all(tags):
            role_key = role_map.get(tag.name)
            if not role_key: continue
            content_html = extract_content_by_selectors(tag, content_selectors.get(role_key, []), fallback_html=True)
            if content_html.strip(): turns.append({"role": role_key, "html": content_html})
    elif method == "container_list":
        container_sel = profile.get("container_selector")
        content_selectors = profile.get("content_selectors", {})
        if container_sel:
            for tag in soup.select(container_sel):
                role_key = detect_role(tag, profile)
                if not role_key or role_key == "unknown": continue
                content_html = extract_content_by_selectors(tag, content_selectors.get(role_key, []), fallback_html=True)
                if content_html.strip(): turns.append({"role": role_key, "html": content_html})
    elif method == "turn_list":
        turn_sel = profile.get("turn_selector")
        content_selectors = profile.get("content_selectors", {})
        if turn_sel:
            for turn_container in soup.select(turn_sel):
                for role in ("user", "ai"):
                    for sel in content_selectors.get(role, []):
                        found = False
                        for el in turn_container.select(sel):
                            content_html = clean_fragment_html(el.decode_contents())
                            if content_html.strip():
                                turns.append({"role": role, "html": content_html})
                                found = True
                                break
                        if found:
                            break

    elif method == "sequence_pair":
        scope_sel = profile.get("scope_selector")
        user_sel = profile.get("user_selector")
        user_excl = profile.get("user_exclude_class")
        user_content_sel = profile.get("user_content_selector")
        ai_sel = profile.get("ai_selector")
        scope = soup.select_one(scope_sel) if scope_sel else soup
        if not scope:
            scope = soup
        user_els = scope.select(user_sel) if user_sel else []
        if user_excl:
            user_els = [el for el in user_els if user_excl not in el.get("class", [])]
        ai_els = scope.select(ai_sel) if ai_sel else []
        for user_el, ai_el in zip(user_els, ai_els):
            content_el = user_el.select_one(user_content_sel) if user_content_sel else user_el
            if content_el:
                content_html = clean_fragment_html(content_el.decode_contents())
                if content_html.strip():
                    turns.append({"role": "user", "html": content_html})
            content_html = clean_fragment_html(ai_el.decode_contents())
            if content_html.strip():
                turns.append({"role": "ai", "html": content_html})

    if not turns:
        potential_turns = soup.find_all(["div", "p", "span", "section", "article"])
        current_role, current_html = None, []
        def flush_tag(role, html_list):
            if role and html_list:
                cleaned = clean_fragment_html("".join(html_list))
                if cleaned: turns.append({"role": role, "html": cleaned})
        
        # Extended patterns for HTML elements containing text headers
        user_re = r"^(You|User) said$|^You$|^User$|^##\s*User$|^User:$"
        ai_re = r"^(Gemini|ChatGPT|Claude|AI) said$|^(Gemini|ChatGPT|Claude|AI)$|^##\s*AI$|^(Gemini|ChatGPT|Claude|AI):$"
        
        for elem in potential_turns:
            text = elem.get_text().strip()
            if re.match(user_re, text, re.I):
                flush_tag(current_role, current_html)
                current_role, current_html = "user", []
            elif re.match(ai_re, text, re.I):
                flush_tag(current_role, current_html)
                current_role, current_html = "ai", []
            elif current_role and elem.name in ["div", "p", "pre", "span"]:
                if not any(parent in potential_turns for parent in elem.parents):
                    current_html.append(str(elem))
        flush_tag(current_role, current_html)
    return turns

def shift_headers(soup: BeautifulSoup):
    """Shift h1-h6 headers down by one level to avoid conflict with turn headers (h2)."""
    # Shift from h5 down to h1 to avoid overwriting newly created higher-level headers
    for i in range(5, 0, -1):
        for h in soup.find_all(f"h{i}"):
            h.name = f"h{i+1}"
    # h6 remains h6 or becomes h6 (Markdown limit)

def html_to_markdown(turn_html: str, noise_patterns: list[str] = None) -> str:
    soup = BeautifulSoup(turn_html, "html.parser")

    # 1. Shift headers
    shift_headers(soup)
    log_debug(f"Headers shifted. HTML state:\n{soup.prettify()[:500]}...")

    def convert_element(el):
        if el.name is None: # NavigableString
            text = str(el)
            # Normalize HTML whitespace like browsers do: collapse whitespace to a single
            # space, except inside <pre> where whitespace is significant.
            if el.find_parent("pre") is None:
                text = re.sub(r'\s+', ' ', text)
            return text

        # Hidden/Omitted tags
        if el.name in ("script", "style", "noscript"):
            return ""

        # Gemini custom code-block element: extract language and code directly
        # to avoid the language label appearing as plain text before the fence.
        if el.name == "code-block":
            lang = ""
            dec = el.select_one("div.code-block-decoration")
            if dec:
                sp = next((s for s in dec.find_all("span") if s.get_text().strip()), None)
                if sp:
                    lang = re.sub(r'\s+', ' ', sp.get_text()).strip()
            code_el = el.find(attrs={"data-test-id": "code-content"}) or el.find("code")
            if code_el:
                return f"\n\n```{lang}\n{code_el.get_text().rstrip()}\n```\n\n"
            # Fall through to default processing if structure not recognized

        # Recursive content
        content = "".join(convert_element(child) for child in el.children).strip()
        if not content and el.name not in ("br", "hr"):
            return ""

        if el.name in ("b", "strong"):
            return f"**{content}**"
        if el.name in ("i", "em"):
            return f"*{content}*"
        if el.name == "code":
            if el.parent and el.parent.name == "pre": return content
            return f"`{content}`"
        if el.name == "br":
            return "\n"
        if el.name == "p":
            return f"\n\n{content}\n\n"
        if re.match(r"^h[1-6]$", el.name):
            level = int(el.name[1])
            return f"\n\n{'#' * level} {content}\n\n"
        if el.name == "blockquote":
            lines = content.split("\n")
            return "\n" + "\n".join(f"> {l}" for l in lines) + "\n"
        if el.name in ("ul", "ol"):
            items = []
            for idx, li in enumerate(el.find_all("li", recursive=False), 1):
                li_content = "".join(convert_element(c) for c in li.children).strip()
                prefix = f"{idx}." if el.name == "ol" else "-"
                items.append(f"{prefix} {li_content}")
            return "\n" + "\n".join(items) + "\n"
        if el.name == "pre":
            code_tag = el.find("code")
            lang = ""
            if code_tag and code_tag.get("class"):
                for cls in code_tag.get("class"):
                    if cls.startswith("language-"): lang = cls.replace("language-", "")
            return f"\n\n``` {lang}\n{content}\n```\n\n"
        if el.name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cols = []
                for td in tr.find_all(["td", "th"]):
                    cols.append("".join(convert_element(c) for c in td.children).strip().replace("|", "\\|"))
                if cols: rows.append("| " + " | ".join(cols) + " |")
            if rows:
                first_row_cols = len(rows[0].split("|")) - 2
                sep = "| " + " | ".join(["---"] * first_row_cols) + " |"
                if len(rows) > 1: rows.insert(1, sep)
                return "\n\n" + "\n".join(rows) + "\n\n"
        
        # Treat Gemini/Angular wrapper elements as block-level so that code blocks
        # inside them retain their surrounding blank lines after stripping.
        if el.name == "response-element":
            return f"\n\n{content}\n\n" if content else ""

        # ARIA role=heading support (e.g., Google AI Mode uses div[role=heading])
        if el.get("role") == "heading":
            level = int(el.get("aria-level", 3))
            level = max(1, min(6, level))
            return f"\n\n{'#' * level} {content}\n\n"

        # Default fallback for divs, spans, etc.
        return content

    text = convert_element(soup).strip()
    
    # 5. Clean up noise and whitespace
    if noise_patterns:
        for p in noise_patterns:
            if not p: continue
            text = re.sub(rf"^\s*{re.escape(p)}\s*$", "", text, flags=re.M | re.I)
            text = text.replace(p, "")
    
    text = re.sub(r"^\s*.+ said\s*$", "", text, flags=re.M | re.I)
    # Remove lines that contain only spaces/tabs (HTML formatting artefacts from
    # whitespace-normalization of text nodes between block elements).
    text = re.sub(r'^[ \t]+$', '', text, flags=re.M)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', "", name)
    name = re.sub(r'[<>:"/\\|?*#]', "_", name)
    name = name.replace("`", "").replace("*", "").replace("#", "").strip()
    return name[:80]

def main():
    global args
    parser = argparse.ArgumentParser(description="Extract AI chat from clipboard or file.")
    parser.add_argument("--save-raw", help="Path to save raw clipboard data (Base64).")
    parser.add_argument("--test", help="Path to load raw clipboard data (Base64) from for testing.")
    parser.add_argument("--debug", action="store_true", help="Show debug information.")
    args = parser.parse_args()

    # Fix Windows console encoding
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    config = load_config()

    # Lock: prevent concurrent executions (skip in --test mode)
    use_lock = not args.test
    if use_lock:
        if not acquire_lock():
            status_cfg = config.get("clip", {}).get("notice", {}).get("status_toast", {})
            show_status_toast(config, "Chat Extractor", status_cfg.get("busy", "Already extracting, please wait."))
            print("Another instance is already running. Exiting.")
            return
        show_status_toast(config, "Chat Extractor", config.get("clip", {}).get("notice", {}).get("status_toast", {}).get("processing", "Processing clipboard..."))

    if use_lock:
        import atexit
        atexit.register(release_lock)

    content = ""

    if args.test:
        test_path = Path(args.test)
        if not test_path.exists():
            print(f"Test file not found: {args.test}"); return
        raw_text = test_path.read_text(encoding="utf-8").strip()
        import base64
        # Try to decode as Base64 first
        try:
            # Check if it looks like base64 (alphanumeric, +, /, =)
            if re.match(r'^[A-Za-z0-9+/=\s]+$', raw_text) and len(raw_text) % 4 == 0:
                raw_bytes = base64.b64decode(raw_text)
                try: content = raw_bytes.decode('utf-8')
                except UnicodeDecodeError: content = raw_bytes.decode('cp932', errors='replace')
            else:
                content = raw_text
        except:
            content = raw_text
        
        content = try_repair_mojibake(content)
        if "StartFragment:" in content:
            match = re.search(r'<!--StartFragment-->(.*)<!--EndFragment-->', content, re.DOTALL)
            if match: content = match.group(1)
    else:
        if args.save_raw:
            raw_b64 = get_clipboard_raw_b64()
            if raw_b64:
                save_path = Path(args.save_raw)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(raw_b64, encoding="utf-8")
                print(f"Raw clipboard data saved to: {args.save_raw}")
        content = get_clipboard_html()

    if not content or not content.strip():
        print("Clipboard or test file is empty."); return

    hex_debug = " ".join(f"{ord(c):04x}" for c in content[:100])
    log_debug(f"Raw content hex (first 100 chars): {hex_debug}")

    soup = BeautifulSoup(content, "html.parser")
    profiles = load_profiles()
    model_key, profile = detect_profile(soup, profiles)
    
    if profile:
        print(f"Detected profile: {model_key}")
    else:
        log_debug("AI model format not detected. Falling back to generic text extraction.")

    turns = extract_turns_from_soup(soup, profile)
    if not turns:
        log_debug("Processing as plain text.")
        turns = [{"role": "user", "html": content}]
        if model_key == "unknown": model_key = "text"

    md_output = []; title = ""
    title_tag = soup.find("title")
    if title_tag: title = title_tag.get_text().strip()
    if not title:
        for turn in turns:
            if turn["role"] == "user":
                t_soup = BeautifulSoup(turn["html"], "html.parser")
                title = t_soup.get_text().strip()[:40].split("\n")[0].strip()
                break
    if not title: title = f"Chat_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"Extracting: {title}")

    md_output.append(f"# {title}\n\nModel Profile: {model_key}\nExtracted Date: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n---\n")
    
    # Merge noise patterns: Profile + Global 'removes'
    noise = profile.get("noise_patterns", []) + config.get("removes", [])
    
    for idx, turn in enumerate(turns):
        header = "## User" if turn["role"] == "user" else "## AI"
        log_debug(f"Turn {idx} ({turn['role']}) raw HTML:\n{turn['html'][:200]}...")
        text = html_to_markdown(turn["html"], noise_patterns=noise)
        if text.strip(): md_output.append(f"{header}\n\n{text}\n")

    final_md = "\n".join(md_output)

    filepath = None
    if config["output"]["enabled"]:
        now = dt.datetime.now()
        y_str = now.strftime(config.get("year_format", "%Y"))
        m_str = now.strftime(config.get("month_format", "%m"))
        d_str = now.strftime(config.get("date_format", "%Y%m%d"))
        time_str = now.strftime(config["time_format"])
        
        # Resolve variables in directory path
        out_dir_tmpl = config["output"]["dir"]
        resolved_out_dir = out_dir_tmpl.replace("{year}", y_str).replace("{month}", m_str).replace("{date}", d_str)
        
        # If path is relative, make it relative to the script's parent directory
        out_path = Path(resolved_out_dir)
        if not out_path.is_absolute():
            out_dir = Path(__file__).resolve().parent / resolved_out_dir
        else:
            out_dir = out_path
            
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Resolve variables in filename
        filename = config["output"]["filename"].replace("{year}", y_str).replace("{month}", m_str).replace("{date}", d_str)
        filename = filename.replace("{time}", time_str).replace("{model}", model_key).replace("{ai model}", model_key).replace("{title}", sanitize_filename(title))
        
        filepath = out_dir / filename
        try:
            filepath.write_text(final_md, encoding="utf-8-sig")
            print("-" * 40)
            print(f"Success! Extracted {len(turns)} turns.")
            print(f"Saved to: {filepath}")
        except Exception as e:
            print(f"Error saving file: {e}")
            filepath = None

    if config["clip"]["enabled"]:
        try:
            pyperclip.copy(final_md)
            print("Markdown result has been copied to clipboard.")
            summary_txt = title[:50] + "..." if len(title) > 50 else title
            show_toast(config, model_key, summary_txt, len(turns), filepath=filepath)
        except Exception as e:
            print(f"Error copying to clipboard: {e}")

    print("-" * 40)

if __name__ == "__main__":
    main()
