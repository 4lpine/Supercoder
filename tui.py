"""
TUI (Text User Interface) for Supercoder
Chat interface with banner, message bubbles, and fixed input
"""
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl, Container, UIControl, UIContent
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.styles import Style
from prompt_toolkit.mouse_events import MouseEventType
from pathlib import Path
from datetime import datetime
import getpass
import sys
import io

# ANSI color codes
class C:
    RST = "\033[0m"
    RED = "\033[31m"
    BRED = "\033[91m"
    PURPLE = "\033[35m"
    BPURPLE = "\033[95m"
    BYELLOW = "\033[93m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    GREEN = BRED

class TUIOutput:
    """Redirect stdout/stderr to TUI messages"""
    def __init__(self, tui):
        self.tui = tui
        self.buffer = ""
    
    def write(self, text):
        if text and text.strip():
            # Add message and schedule redraw on event loop
            self.tui.messages.append(f"{C.GRAY}{text.strip()}{C.RST}\n")
            self.tui._update_history()
            # Use call_from_executor to safely update from any thread
            if hasattr(self.tui.app, 'loop') and self.tui.app.loop:
                try:
                    self.tui.app.loop.call_soon_threadsafe(self.tui.app.invalidate)
                except:
                    pass
    
    def flush(self):
        pass


class ScrollableFormattedTextControl(UIControl):
    """Custom scrollable control that supports ANSI colors and mouse wheel scrolling"""
    
    def __init__(self, get_text_func):
        self.get_text_func = get_text_func
        self.scroll_offset = 0
    
    def create_content(self, width, height):
        # Get the formatted text
        text = self.get_text_func()
        lines = to_formatted_text(text)
        
        # Split into lines for rendering
        text_lines = []
        current_line = []
        
        for item in lines:
            if isinstance(item, tuple):
                style, text_content = item[0], item[1]
                for char in text_content:
                    if char == '\n':
                        text_lines.append(current_line)
                        current_line = []
                    else:
                        current_line.append((style, char))
            else:
                # Handle plain strings
                for char in str(item):
                    if char == '\n':
                        text_lines.append(current_line)
                        current_line = []
                    else:
                        current_line.append(('', char))
        
        if current_line:
            text_lines.append(current_line)
        
        # Apply scroll offset
        total_lines = len(text_lines)
        max_scroll = max(0, total_lines - height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        
        # Get visible lines
        visible_lines = text_lines[self.scroll_offset:self.scroll_offset + height]
        
        # Pad if needed
        while len(visible_lines) < height:
            visible_lines.append([])
        
        def get_line(i):
            if i < len(visible_lines):
                return visible_lines[i]
            return []
        
        return UIContent(
            get_line=get_line,
            line_count=height,
            show_cursor=False
        )
    
    def mouse_handler(self, mouse_event):
        """Handle mouse events for scrolling"""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self.scroll_offset = max(0, self.scroll_offset - 3)
            return None
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self.scroll_offset += 3
            return None
        # Return NotImplemented for other mouse events to allow text selection
        return NotImplemented
    
    def is_focusable(self):
        return True
    
    def get_key_bindings(self):
        return None

class SupercoderTUI:
    def __init__(self):
        self.messages = []
        self.balance = None
        self.model = "mistralai/devstral-2512:free"
        self.user = getpass.getuser()
        self.cwd = Path.cwd().name or "~"
        
        # Banner
        self.banner = f"""{C.RED}  ██████  █    ██  ██▓███  ▓█████  ██▀███   ▄████▄   {C.PURPLE}▒{C.RED}█████  ▓█████▄ ▓█████  ██▀███  
{C.PURPLE}▒{C.RED}██    {C.PURPLE}▒  {C.RED}██  ▓██{C.PURPLE}▒{C.RED}▓██{C.PURPLE}░  {C.RED}██{C.PURPLE}▒{C.RED}▓█   ▀ ▓██ {C.PURPLE}▒ {C.RED}██{C.PURPLE}▒▒{C.RED}██▀ ▀█  {C.PURPLE}▒{C.RED}██{C.PURPLE}▒  {C.RED}██{C.PURPLE}▒▒{C.RED}██▀ ██▌▓█   ▀ ▓██ {C.PURPLE}▒ {C.RED}██{C.PURPLE}▒
{C.PURPLE}░ {C.RED}▓██▄   ▓██  {C.PURPLE}▒{C.RED}██{C.PURPLE}░{C.RED}▓██{C.PURPLE}░ {C.RED}██▓{C.PURPLE}▒▒{C.RED}███   ▓██ {C.PURPLE}░{C.RED}▄█ {C.PURPLE}▒▒{C.RED}▓█    ▄ {C.PURPLE}▒{C.RED}██{C.PURPLE}░  {C.RED}██{C.PURPLE}▒░{C.RED}██   {C.RED}█▌{C.PURPLE}▒{C.RED}███   ▓██ {C.PURPLE}░{C.RED}▄█ {C.PURPLE}▒
{C.PURPLE}  ▒   {C.RED}██{C.PURPLE}▒{C.RED}▓▓█  {C.PURPLE}░{C.RED}██{C.PURPLE}░▒{C.RED}██▄█▓{C.PURPLE}▒ ▒▒{C.RED}▓█  ▄ {C.PURPLE}▒{C.RED}██▀▀█▄  {C.PURPLE}▒{C.RED}▓▓▄ ▄██{C.PURPLE}▒▒{C.RED}██   ██{C.PURPLE}░░{C.RED}▓█▄   ▌{C.PURPLE}▒{C.RED}▓█  ▄ {C.PURPLE}▒{C.RED}██▀▀█▄  
{C.PURPLE}▒{C.RED}██████{C.PURPLE}▒▒▒▒{C.RED}█████▓{C.PURPLE} ▒{C.RED}██{C.PURPLE}▒ ░  ░░▒{C.RED}████{C.PURPLE}▒░{C.RED}██▓{C.PURPLE} ▒{C.RED}██{C.PURPLE}▒▒ {C.RED}▓███▀{C.PURPLE} ░░ {C.RED}████▓{C.PURPLE}▒░░▒{C.RED}████▓{C.PURPLE} ░▒{C.RED}████{C.PURPLE}▒░{C.RED}██▓{C.PURPLE} ▒{C.RED}██{C.PURPLE}▒
{C.PURPLE}▒ ▒{C.RED}▓{C.PURPLE}▒ ▒ ░░▒{C.RED}▓{C.PURPLE}▒ ▒ ▒ ▒{C.RED}▓{C.PURPLE}▒░ ░  ░░░ ▒░ ░░ ▒{C.RED}▓ {C.PURPLE}░▒{C.RED}▓{C.PURPLE}░░ ░▒ ▒  ░░ ▒░▒░▒░  ▒▒{C.RED}▓{C.PURPLE}  ▒ ░░ ▒░ ░░ ▒{C.RED}▓ {C.PURPLE}░▒{C.RED}▓{C.PURPLE}░
{C.PURPLE}░ ░▒  ░ ░░░▒░ ░ ░ ░▒ ░      ░ ░  ░  ░▒ ░ ▒░  ░  ▒     ░ ▒ ▒░  ░ ▒  ▒  ░ ░  ░  ░▒ ░ ▒░
{C.PURPLE}░  ░  ░   ░░░ ░ ░ ░░          ░     ░░   ░ ░        ░ ░ ░ ▒   ░ ░  ░    ░     ░░   ░
{C.PURPLE}      ░     ░                 ░  ░   ░     ░ ░          ░ ░     ░       ░  ░   ░
{C.PURPLE}                                           ░                  ░                      {C.RST}

"""
        
        # Message history display - custom scrollable control with ANSI support
        self.history_control = ScrollableFormattedTextControl(
            get_text_func=lambda: ANSI(self._get_history_text())
        )
        
        self.history_window = Window(
            content=self.history_control,
            wrap_lines=True,
            always_hide_cursor=True
        )
        
        # Status bar
        self.status_control = FormattedTextControl(
            text=self._get_status_text,
            focusable=False
        )
        
        # Input field
        self.input_field = TextArea(
            height=3,
            multiline=True,
            wrap_lines=True,
            prompt=">>> ",
            style="class:input-field"
        )
        
        # Key bindings
        kb = KeyBindings()
        
        @kb.add('c-c')
        def _(event):
            event.app.exit()
        
        @kb.add('c-d')
        def _(event):
            event.app.exit()
        
        @kb.add('up')
        def _(event):
            """Scroll up in history"""
            self.history_control.scroll_offset = max(0, self.history_control.scroll_offset - 1)
        
        @kb.add('down')
        def _(event):
            """Scroll down in history"""
            self.history_control.scroll_offset += 1
        
        @kb.add('pageup')
        def _(event):
            """Scroll up in history (page)"""
            self.history_control.scroll_offset = max(0, self.history_control.scroll_offset - 10)
        
        @kb.add('pagedown')
        def _(event):
            """Scroll down in history (page)"""
            self.history_control.scroll_offset += 10
        
        @kb.add('c-j')  # Ctrl+J (alternative for Enter in some terminals)
        def _(event):
            """Send message on Ctrl+J"""
            text = event.app.current_buffer.text
            if text.strip() and self.on_submit:
                self.on_submit(text)
                event.app.current_buffer.text = ""
        
        @kb.add('escape', 'enter')
        def _(event):
            """Send message on Esc then Enter"""
            text = event.app.current_buffer.text
            if text.strip() and self.on_submit:
                self.on_submit(text)
                event.app.current_buffer.text = ""
        
        # Layout with frames
        self.layout = Layout(
            HSplit([
                # Message history with frame (scrollable) - includes banner
                Frame(
                    self.history_window,
                    title="Chat History (Mouse wheel, Arrow keys, or PageUp/PageDown to scroll)"
                ),
                # Status bar
                Window(
                    height=1,
                    content=self.status_control,
                    style="class:status"
                ),
                # Input with frame
                Frame(
                    self.input_field,
                    title="Input (Ctrl+J or Esc+Enter to send, Enter for newline, Ctrl+C to exit)"
                )
            ])
        )
        
        # Focus on input by default
        self.layout.focus(self.input_field)
        
        # Style
        self.style = Style.from_dict({
            'status': 'bg:#222222 #00ff00',
            'input-field': 'bg:#000000 #ffffff',
            'frame.border': '#ff00ff',
            'frame.label': '#ff00ff bold',
        })
        
        # Application
        self.app = Application(
            layout=self.layout,
            key_bindings=kb,
            style=self.style,
            full_screen=True,
            mouse_support=True  # Enable for scrolling
        )
        
        self.on_submit = None
    
    def _get_history_text(self):
        """Generate formatted text for message history"""
        if not self.messages:
            return f"{self.banner}\n{C.GRAY}Type your message below to start. Commands: help, model, quit, plan, tasks{C.RST}"
        
        return self.banner + ''.join(self.messages)
    
    def _update_history(self):
        """Update the history display"""
        # FormattedTextControl will call _get_history_text automatically
        self.app.invalidate()
    
    def _get_status_text(self):
        """Generate status bar text"""
        balance_str = f" | ${self.balance}" if self.balance else ""
        return ANSI(f"{C.GREEN}Model:{C.RST} {self.model} | {C.GREEN}Dir:{C.RST} {self.cwd}{balance_str}")
    
    def add_message(self, text):
        """Add a message to history"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.messages.append(f"[{timestamp}] {text}\n")
        self._update_history()
    
    def add_thinking(self):
        """Add animated thinking indicator"""
        self.messages.append(f"{C.GRAY}thinking...{C.RST}\n")
        self._update_history()
    
    def remove_last_message(self):
        """Remove last message (for removing thinking indicator)"""
        if self.messages:
            self.messages.pop()
            self._update_history()
    
    def add_box_message(self, title, content, color=None):
        """Add a framed message box"""
        if color is None:
            color = C.BPURPLE
        
        lines = content.split('\n')
        max_width = max(len(line) for line in lines) if lines else 50
        max_width = min(max_width, 70)
        
        box = f"\n{color}╭{'─' * (max_width + 2)}╮{C.RST}\n"
        box += f"{color}│{C.RST} {C.WHITE}{title}{C.RST}\n"
        box += f"{color}├{'─' * (max_width + 2)}┤{C.RST}\n"
        
        for line in lines:
            if line:
                box += f"{color}│{C.RST} {line}\n"
        
        box += f"{color}╰{'─' * (max_width + 2)}╯{C.RST}\n"
        
        self.messages.append(box)
        self._update_history()
    
    def update_balance(self, balance):
        self.balance = balance
        self.app.invalidate()
    
    def update_model(self, model):
        self.model = model
        self.app.invalidate()
    
    def update_cwd(self, cwd):
        self.cwd = cwd
        self.app.invalidate()
    
    def run(self, on_submit_callback):
        """Run the TUI application"""
        self.on_submit = on_submit_callback
        self._update_history()  # Initial update
        self.app.run()
    
    def exit(self):
        self.app.exit()
