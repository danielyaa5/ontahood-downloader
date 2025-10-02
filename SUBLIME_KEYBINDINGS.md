# Sublime Text Keybindings & Workflow Guide

This document provides a comprehensive guide to using Sublime Text effectively with the ontahood-downloader project, including both custom keybindings and general Sublime Text shortcuts.

## 📋 Table of Contents
- [Project-Specific Keybindings](#-project-specific-keybindings)
- [Essential Sublime Text Shortcuts](#-essential-sublime-text-shortcuts)
- [Python Development Shortcuts](#-python-development-shortcuts)
- [Navigation & Selection](#-navigation--selection)
- [Search & Replace](#-search--replace)
- [File Management](#-file-management)
- [Multi-Cursor & Selection](#-multi-cursor--selection)
- [Code Folding & Layout](#-code-folding--layout)
- [Package-Specific Shortcuts](#-package-specific-shortcuts)
- [Terminal Integration](#-terminal-integration)
- [Tips & Tricks](#-tips--tricks)

---

## 🚀 Project-Specific Keybindings

These keybindings are specifically configured for the ontahood-downloader project:

### Python Execution
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+R` | Build/Run | Run current Python file |
| `Cmd+Shift+R` | Run with Input | Run Python file with terminal input capability |
| `Cmd+Alt+R` | Run GUI | Launch drive_fetch_gui.py |

### Code Quality & Formatting
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Shift+F` | Auto-format | Format Python code with PEP8 standards |
| `Cmd+Alt+L` | Toggle Linter | Show/hide linting errors panel |

### Code Navigation (Anaconda Package)
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Alt+Down` | Go to Definition | Jump to function/class definition |
| `Cmd+Alt+F` | Find Usages | Find all references to symbol |
| `Cmd+Alt+D` | Show Documentation | Display function/method documentation |

### Git Integration
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Shift+G` | Next Git Change | Jump to next git diff |
| `Cmd+Shift+Alt+G` | Previous Git Change | Jump to previous git diff |

### Terminal
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Shift+T` | Open Terminal | Open integrated terminal at project root |

---

## ⚡ Essential Sublime Text Shortcuts

### File Operations
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+N` | New File | Create new file |
| `Cmd+O` | Open File | Open file dialog |
| `Cmd+S` | Save | Save current file |
| `Cmd+Shift+S` | Save As | Save file with new name |
| `Cmd+Alt+S` | Save All | Save all open files |
| `Cmd+W` | Close Tab | Close current tab |
| `Cmd+Shift+W` | Close Window | Close current window |
| `Cmd+Shift+T` | Reopen Tab | Reopen recently closed tab |

### Basic Editing
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Z` | Undo | Undo last action |
| `Cmd+Shift+Z` | Redo | Redo last undone action |
| `Cmd+X` | Cut | Cut selected text |
| `Cmd+C` | Copy | Copy selected text |
| `Cmd+V` | Paste | Paste from clipboard |
| `Cmd+A` | Select All | Select entire document |

---

## 🐍 Python Development Shortcuts

### Code Completion & IntelliSense
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Tab` | Auto-complete | Accept suggestion |
| `Esc` | Cancel | Cancel completion popup |
| `Ctrl+Space` | Force Completion | Trigger completion manually |

### Code Snippets
| Trigger | Result | Description |
|---------|--------|-------------|
| `log` + Tab | Bilingual logging | `logging.info(L("English", "Indonesian"))` |
| `try` + Tab | Try-except block | Try-except with error logging |
| `def` + Tab | Function definition | Function with docstring template |
| `class` + Tab | Class definition | Class with init method |

### Indentation & Formatting
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+]` | Indent | Increase indentation |
| `Cmd+[` | Unindent | Decrease indentation |
| `Cmd+Shift+V` | Paste with Indent | Paste and auto-indent |
| `Ctrl+Shift+K` | Delete Line | Delete current line |

---

## 🧭 Navigation & Selection

### Cursor Movement
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Left/Right` | Word Boundaries | Move by word |
| `Cmd+Up/Down` | Document Start/End | Move to beginning/end of file |
| `Cmd+Shift+Left/Right` | Select Words | Select by word boundaries |
| `Cmd+L` | Select Line | Select entire line |
| `Cmd+Shift+A` | Select Tag | Select HTML/XML tag content |

### Quick Navigation
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+P` | Quick Open | Open file by name (fuzzy search) |
| `Cmd+R` | Go to Symbol | Jump to function/class in current file |
| `Cmd+Shift+R` | Go to Symbol in Project | Jump to any symbol in project |
| `Cmd+G` | Go to Line | Jump to specific line number |
| `Ctrl+G` | Go to Definition | Jump to symbol definition |

### Bookmarks
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+F2` | Toggle Bookmark | Add/remove bookmark |
| `F2` | Next Bookmark | Jump to next bookmark |
| `Shift+F2` | Previous Bookmark | Jump to previous bookmark |
| `Cmd+Shift+F2` | Clear All Bookmarks | Remove all bookmarks |

---

## 🔍 Search & Replace

### Find Operations
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+F` | Find | Open find dialog |
| `Cmd+G` | Find Next | Find next occurrence |
| `Cmd+Shift+G` | Find Previous | Find previous occurrence |
| `Cmd+E` | Use Selection for Find | Use selected text as search term |

### Replace Operations
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Alt+F` | Replace | Open find & replace dialog |
| `Cmd+Alt+E` | Replace Next | Replace next occurrence |
| `Cmd+Alt+A` | Replace All | Replace all occurrences |

### Advanced Search
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Shift+F` | Find in Files | Search across entire project |
| `Cmd+I` | Incremental Find | Search as you type |
| `Cmd+Alt+R` | Regex Mode | Toggle regular expression search |
| `Cmd+Alt+C` | Case Sensitive | Toggle case sensitivity |
| `Cmd+Alt+W` | Whole Words | Toggle whole word matching |

---

## 📁 File Management

### Project & Sidebar
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+K, Cmd+B` | Toggle Sidebar | Show/hide file sidebar |
| `Cmd+Shift+P` | Command Palette | Open command palette |
| `Cmd+Shift+N` | New Window | Create new Sublime window |

### Tabs
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+T` | New Tab | Create new tab |
| `Cmd+Shift+]` | Next Tab | Switch to next tab |
| `Cmd+Shift+[` | Previous Tab | Switch to previous tab |
| `Cmd+Alt+Right` | Next Tab | Alternative next tab |
| `Cmd+Alt+Left` | Previous Tab | Alternative previous tab |

---

## 🎯 Multi-Cursor & Selection

### Multiple Cursors
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+D` | Select Next | Add next occurrence to selection |
| `Cmd+K, Cmd+D` | Skip Next | Skip current, select next occurrence |
| `Cmd+U` | Undo Selection | Remove last added cursor |
| `Cmd+Shift+L` | Split Selection | Create cursor at each line of selection |
| `Ctrl+Shift+Up/Down` | Add Cursor Above/Below | Add cursor to adjacent line |

### Advanced Selection
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Ctrl+G` | Select All Occurrences | Select all instances of word |
| `Alt+F3` | Quick Find All | Select all occurrences of current selection |
| `Cmd+Shift+Space` | Select Scope | Select current scope (function, class, etc.) |

---

## 📐 Code Folding & Layout

### Code Folding
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Alt+[` | Fold | Fold current code block |
| `Cmd+Alt+]` | Unfold | Unfold current code block |
| `Cmd+K, Cmd+1` | Fold Level 1 | Fold all level 1 blocks |
| `Cmd+K, Cmd+J` | Unfold All | Unfold everything |

### Layout & Views
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Alt+1` | Single Column | Set to 1 column layout |
| `Cmd+Alt+2` | Two Columns | Set to 2 column layout |
| `Cmd+Alt+3` | Three Columns | Set to 3 column layout |
| `Cmd+Alt+5` | Grid Layout | Set to 2x2 grid layout |
| `Ctrl+Shift+1-4` | Move to Group | Move file to specific group |

---

## 🔌 Package-Specific Shortcuts

### Anaconda (Python IDE)
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Ctrl+Alt+G` | Go to Definition | Jump to symbol definition |
| `Ctrl+Alt+F` | Find Usages | Find all references |
| `Ctrl+Alt+D` | Show Documentation | Display docstring |
| `Ctrl+Alt+R` | Rename | Rename symbol project-wide |

### GitGutter
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Shift+G` | Next Change | Jump to next git change |
| `Cmd+Shift+Alt+G` | Previous Change | Jump to previous git change |

### BracketHighlighter
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Ctrl+M` | Jump to Matching Bracket | Jump between matching brackets |
| `Ctrl+Shift+M` | Select Bracket Contents | Select everything inside brackets |

---

## 💻 Terminal Integration

### Terminus Package
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+Shift+T` | Open Terminal | Open terminal in project directory |
| `Ctrl+Shift+Alt+T` | Open Terminal Tab | Open terminal in new tab |

### Build System Shortcuts
| Keybinding | Action | Description |
|------------|--------|-------------|
| `Cmd+B` | Build | Run default build system |
| `Cmd+Shift+B` | Select Build System | Choose build system |
| `Ctrl+C` | Cancel Build | Stop running build |

---

## 💡 Tips & Tricks

### Productivity Hacks

1. **Quick File Switching**: Use `Cmd+P` and type partial filename to quickly open files
2. **Symbol Navigation**: Use `Cmd+R` to quickly jump to any function or class in the current file
3. **Multi-line Editing**: Hold `Alt` and drag to select columns, or use `Cmd+D` to select multiple instances
4. **Command Palette**: `Cmd+Shift+P` gives you access to every Sublime Text command
5. **Vintage Mode**: Enable vim keybindings in Preferences → Settings (remove "Vintage" from ignored_packages)

### Python-Specific Tips

1. **Quick Testing**: Use `Cmd+R` to quickly run and test your Python scripts
2. **Error Navigation**: Click on build errors to jump directly to the problematic line
3. **Code Completion**: Type method names and press `Tab` to auto-complete with parameters
4. **Docstring Viewing**: Use `Cmd+Alt+D` on any function to see its documentation
5. **Import Organization**: Use the Command Palette to sort and organize imports

### Project Management

1. **Project Files**: Save your project as `.sublime-project` to preserve settings and build systems
2. **File Exclusion**: Use project settings to hide unnecessary files (like `__pycache__`)
3. **Build Variants**: Create custom build commands for different execution modes
4. **Snippet Creation**: Create custom code snippets for frequently used patterns

### Debugging Workflow

1. Use the integrated terminal (`Cmd+Shift+T`) to run scripts with full output
2. Set up print statement snippets for quick debugging
3. Use the linting features to catch errors before runtime
4. Leverage the git integration to track changes while debugging

---

## 🔧 Customization

### Adding Custom Keybindings

1. Go to **Sublime Text → Preferences → Key Bindings**
2. Add your custom bindings to the User file (right pane)
3. Use the format:
```json
{
    "keys": ["cmd+shift+x"], 
    "command": "command_name",
    "args": {"argument": "value"}
}
```

### Creating Custom Build Systems

1. Go to **Tools → Build System → New Build System**
2. Configure for your specific needs:
```json
{
    "cmd": ["python3", "-u", "$file"],
    "working_dir": "$file_path",
    "selector": "source.python"
}
```

### Adding Custom Snippets

1. Go to **Tools → Developer → New Snippet**
2. Create reusable code templates:
```xml
<snippet>
    <content><![CDATA[your code here]]></content>
    <tabTrigger>trigger</tabTrigger>
    <scope>source.python</scope>
</snippet>
```

---

## 🆘 Troubleshooting

### Common Issues

- **Package not working**: Restart Sublime Text after installing packages
- **Python not found**: Check that `python3` is in your PATH
- **Linting errors**: Install `flake8` with `pip install flake8`
- **Terminal not opening**: Ensure Terminus package is installed
- **Build system not working**: Check Python path in build system configuration

### Performance Optimization

- Disable unused packages in Preferences → Package Settings
- Exclude large directories in project settings
- Use indexed search for better performance
- Close unused tabs regularly

---

*This guide covers the essential keybindings and workflows for effective Python development with Sublime Text in the ontahood-downloader project. Keep this file handy for quick reference!*