# Supercoder TUI - Changelog

## Version 1.0.0 (2025)

### 🎉 NEW: Terminal User Interface (TUI)

Supercoder now has a modern, interactive terminal interface inspired by Claude Code!

#### Features

**Visual Interface**
- Split-pane layout with file explorer and chat area
- Real-time streaming AI responses
- Syntax highlighting for code blocks
- Markdown rendering in messages
- Auto-scrolling chat
- Status bar with model info, token usage, and settings

**File Explorer**
- Browse workspace files in sidebar
- Directory tree with folder/file icons
- Smart ignore patterns (.git, node_modules, etc.)
- Auto-refreshes on changes

**Chat Interface**
- User and AI messages with distinct styling
- Tool execution shown visually
- Tool results in collapsible panels
- Command system (help, status, models, etc.)
- Message history

**Keyboard Shortcuts**
- `Ctrl+Q` - Quit
- `Ctrl+C` - Clear chat
- `Ctrl+N` - Focus input
- `Ctrl+M` - Switch model
- `Ctrl+T` - Toggle autonomous mode
- `F1` - Help

**Tool Integration**
- Full access to all 80+ Supercoder tools
- Visual feedback for tool execution
- File operations (read, write, search)
- Shell commands (executePwsh)
- Browser automation (Selenium)
- Vision analysis (screenshots)
- Git operations
- Database tools (PostgreSQL)
- Image generation

#### How to Use

**Installation:**
```bash
pip install textual rich
```

**Launch:**
```bash
# Windows
run_tui.bat

# Linux/macOS
./run_tui.sh

# Or directly
python supercoder_tui.py
```

**Commands:**
- `help` - Show all commands
- `status` - Session info
- `models` - List AI models
- `model <name>` - Switch model
- `auto` - Toggle autonomous mode
- `clear` - Clear chat

#### Technical Details

**Built With:**
- Textual 0.47.0+ - Modern TUI framework
- Rich 13.7.0+ - Terminal formatting
- Python 3.8+ - Runtime

**Architecture:**
- SupercoderTUI - Main app class
- ChatLog - Scrollable message container
- ChatMessage - Individual message widget
- FileTree - Workspace browser
- StatusBar - Model/token/settings display
- ToolOutput - Tool execution results

**Comparison with CLI:**

| Feature | TUI | CLI |
|---------|-----|-----|
| Visual Feedback | ✅ Real-time | ❌ Text only |
| File Explorer | ✅ Built-in | ❌ Manual |
| Mouse Support | ✅ Yes | ❌ No |
| Tool Display | ✅ Visual panels | ❌ Text output |
| Status Display | ✅ Always visible | ❌ On request |
| History Nav | ✅ Scroll | ❌ Limited |
| Resource Usage | Higher | Lower |

#### Files Added

**Core TUI:**
- `tui.py` - Main TUI implementation (17KB)
- `supercoder_tui.py` - Entry point script (760B)

**Launchers:**
- `run_tui.bat` - Windows launcher (629B)
- `run_tui.sh` - Linux/macOS launcher (591B)

**Documentation:**
- `docs/TUI.md` - Complete TUI documentation (8KB)
- `docs/TUI_QUICKSTART.md` - Quick start guide (7.6KB)
- `CHANGELOG.md` - This file

**Updated:**
- `requirements.txt` - Added textual and rich
- `README.md` - Added TUI section and launch instructions
- `main.py` - Added TUI mode detection (--tui flag)

#### Known Issues

None - fully functional!

#### Future Enhancements

Planned features:
- [ ] Multi-tab support
- [ ] Diff viewer for file changes
- [ ] Terminal emulator widget
- [ ] Image preview for vision analysis
- [ ] Custom themes
- [ ] Plugin system
- [ ] Export chat history
- [ ] Search in chat
- [ ] Collapsible sidebar
- [ ] Split pane for code editing

#### Migration from CLI

The TUI is fully compatible with existing Supercoder installations:
- Uses same configuration (~/.supercoder/tokens.txt)
- Same .supercoder/ project directory
- Same tool system
- Same AI models
- Same file operations

You can switch between CLI and TUI freely!

#### Credits

Inspired by:
- Claude Code (Anthropic) - TUI design patterns
- Textual framework - Modern terminal UI
- Rich library - Terminal formatting

---

**Enjoy the new Supercoder TUI!** 🚀
