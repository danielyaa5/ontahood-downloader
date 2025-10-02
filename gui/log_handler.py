"""
Logging bridge between the backend and Tkinter GUI.
"""

import queue
import re
import tkinter as tk
from tkinter import scrolledtext
from tkinter import font as tkfont


class TkLogHandler:
    """
    Log → Tkinter ScrolledText bridge that only auto-scrolls when the user is at the bottom.
    If the user scrolls up, it stops following until they scroll back down.
    
    Features:
    - Colorize timestamp and level
    - Emphasize bracket tags like [Progress]/[Count] and counters like 10/20 or key=123
    - Smart auto-scrolling
    """
    
    def __init__(self, widget: scrolledtext.ScrolledText):
        self.widget = widget
        self.queue = queue.Queue()
        self._follow_tail = True  # auto-scroll enabled iff user is at bottom
        
        # Set up fonts and styling
        self._setup_fonts_and_tags()
        
        # Bind scroll events to detect user scrolling
        self._setup_scroll_detection()
        
        # Start processing log messages
        self._check_queue()
    
    def _setup_fonts_and_tags(self):
        """Set up fonts and text tags for styling."""
        try:
            base_font = tkfont.nametofont(self.widget.cget("font"))
        except Exception:
            base_font = tkfont.nametofont("TkFixedFont")
        
        self.bold_font = base_font.copy()
        try:
            self.bold_font.configure(weight="bold")
        except Exception:
            pass
        
        # Configure text tags for styling
        self.widget.tag_configure("timestamp", foreground="blue", font=self.bold_font)
        self.widget.tag_configure("level_info", foreground="green", font=self.bold_font)
        self.widget.tag_configure("level_warning", foreground="orange", font=self.bold_font)
        self.widget.tag_configure("level_error", foreground="red", font=self.bold_font)
        self.widget.tag_configure("level_debug", foreground="gray", font=self.bold_font)
        self.widget.tag_configure("bracket_tag", foreground="purple", font=self.bold_font)
        self.widget.tag_configure("counter", foreground="darkblue", font=self.bold_font)
        self.widget.tag_configure("bytes_info", foreground="darkgreen")
    
    def _setup_scroll_detection(self):
        """Set up scroll event detection to control auto-scrolling."""
        def on_scroll(*args):
            # Check if user scrolled away from bottom
            try:
                # Get current scroll position
                view_top, view_bottom = self.widget.yview()
                # If not at bottom (within small threshold), disable auto-scroll
                self._follow_tail = (view_bottom >= 0.99)
            except Exception:
                pass
        
        # Bind to various scroll events
        self.widget.bind("<MouseWheel>", lambda e: on_scroll())
        self.widget.bind("<Button-4>", lambda e: on_scroll())
        self.widget.bind("<Button-5>", lambda e: on_scroll())
        self.widget.bind("<Key-Up>", lambda e: on_scroll())
        self.widget.bind("<Key-Down>", lambda e: on_scroll())
        self.widget.bind("<Key-Prior>", lambda e: on_scroll())  # Page Up
        self.widget.bind("<Key-Next>", lambda e: on_scroll())   # Page Down
    
    def put(self, message: str):
        """Queue a log message for display."""
        try:
            self.queue.put_nowait(message)
        except queue.Full:
            # If queue is full, drop oldest messages
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(message)
            except queue.Empty:
                pass
    
    def _check_queue(self):
        """Check for new log messages and display them."""
        try:
            while True:
                message = self.queue.get_nowait()
                self._append_message(message)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.widget.after(100, self._check_queue)
    
    def _append_message(self, message: str):
        """Append a styled message to the text widget."""
        if not message.strip():
            return
        
        # Ensure message ends with newline
        if not message.endswith('\n'):
            message += '\n'
        
        # Parse and style the message
        self._insert_styled_message(message)
        
        # Auto-scroll if user is at bottom
        if self._follow_tail:
            try:
                self.widget.see(tk.END)
            except Exception:
                pass
        
        # Limit buffer size to prevent memory issues
        self._limit_buffer_size()
    
    def _insert_styled_message(self, message: str):
        """Insert message with appropriate styling."""
        # Pattern for timestamp and level
        ts_level_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| ([A-Z]+)\s*\| (.*)$'
        match = re.match(ts_level_pattern, message.strip())
        
        if match:
            timestamp, level, content = match.groups()
            
            # Insert timestamp
            self.widget.insert(tk.END, timestamp, "timestamp")
            self.widget.insert(tk.END, " | ")
            
            # Insert level with appropriate color
            level_tag = f"level_{level.lower()}"
            if level_tag not in ["level_info", "level_warning", "level_error", "level_debug"]:
                level_tag = "level_info"
            self.widget.insert(tk.END, level, level_tag)
            self.widget.insert(tk.END, " | ")
            
            # Insert content with special formatting
            self._insert_styled_content(content)
        else:
            # Insert message as-is if it doesn't match expected format
            self._insert_styled_content(message.strip())
        
        self.widget.insert(tk.END, "\n")
    
    def _insert_styled_content(self, content: str):
        """Insert content with special styling for brackets and counters."""
        # Pattern for bracket tags like [Progress], [Count], [GUI]
        bracket_pattern = r'\[([^\]]+)\]'
        
        # Pattern for counters like 10/20, done=5, bytes=1234
        counter_pattern = r'\b(\d+/\d+|\w+=\d+)\b'
        
        # Pattern for [Bytes] specifically
        bytes_pattern = r'\[Bytes\] (\d+)'
        
        last_pos = 0
        
        # First handle [Bytes] pattern specially
        for match in re.finditer(bytes_pattern, content):
            # Insert text before match
            if match.start() > last_pos:
                self._insert_with_counters(content[last_pos:match.start()])
            
            # Insert [Bytes] in special color
            self.widget.insert(tk.END, "[Bytes] ", "bracket_tag")
            self.widget.insert(tk.END, match.group(1), "bytes_info")
            last_pos = match.end()
        
        if last_pos < len(content):
            self._insert_with_counters(content[last_pos:])
    
    def _insert_with_counters(self, text: str):
        """Insert text with counter highlighting."""
        bracket_pattern = r'\[([^\]]+)\]'
        counter_pattern = r'\b(\d+/\d+|\w+=\d+)\b'
        
        last_pos = 0
        
        # Handle bracket tags
        for match in re.finditer(bracket_pattern, text):
            # Insert text before match
            if match.start() > last_pos:
                self._insert_with_simple_counters(text[last_pos:match.start()])
            
            # Insert bracket tag with styling
            self.widget.insert(tk.END, match.group(0), "bracket_tag")
            last_pos = match.end()
        
        # Insert remaining text
        if last_pos < len(text):
            self._insert_with_simple_counters(text[last_pos:])
    
    def _insert_with_simple_counters(self, text: str):
        """Insert text with simple counter highlighting."""
        counter_pattern = r'\b(\d+/\d+|\w+=\d+)\b'
        
        last_pos = 0
        for match in re.finditer(counter_pattern, text):
            # Insert text before match
            if match.start() > last_pos:
                self.widget.insert(tk.END, text[last_pos:match.start()])
            
            # Insert counter with styling
            self.widget.insert(tk.END, match.group(1), "counter")
            last_pos = match.end()
        
        # Insert remaining text
        if last_pos < len(text):
            self.widget.insert(tk.END, text[last_pos:])
    
    def _limit_buffer_size(self, max_lines: int = 1000):
        """Limit the text buffer to prevent memory issues."""
        try:
            # Get current line count
            current_lines = int(self.widget.index(tk.END).split('.')[0]) - 1
            
            if current_lines > max_lines:
                # Delete excess lines from the beginning
                lines_to_delete = current_lines - max_lines + 100  # Delete extra to avoid frequent trimming
                self.widget.delete("1.0", f"{lines_to_delete}.0")
        except Exception:
            pass  # Ignore errors in buffer limiting
    
    def clear(self):
        """Clear the log display."""
        try:
            self.widget.delete("1.0", tk.END)
        except Exception:
            pass