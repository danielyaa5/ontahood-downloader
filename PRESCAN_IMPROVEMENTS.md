# Prescan Window Improvements

## Summary of Changes

This document describes the improvements made to the prescan window functionality to provide better user experience.

## Problems Fixed

1. **Prescan window didn't open immediately** - Previously, the window only appeared after all folders were scanned
2. **No loading indication** - Users had no feedback that scanning was in progress
3. **No incremental updates** - All folders appeared at once instead of as they completed
4. **Start button remained disabled after closing prescan** - Closing the prescan window left the Start button disabled

## Changes Made

### 1. Internationalization Updates (`gui/i18n.py`)

Added new translation keys for loading states:
- `prescan_loading`: "Scanning folders" / "Memindai folder"
- `prescan_scanning`: "Scanning in progress..." / "Pemindaian sedang berlangsung..."

### 2. Main Application Updates (`gui/main_app.py`)

#### New Method: `create_prescan_window()`
- Opens the prescan window **immediately** when Start is clicked
- Shows an empty treeview ready to be populated
- Starts a loading animation in the footer
- Disables the "Start Download" button until prescan completes
- Sets up proper window close handlers (`WM_DELETE_WINDOW` protocol)
- Signals backend to stop when closed (`dfr.INTERRUPTED = True`)

#### New Method: `_animate_prescan_loading()`
- Animates dots after "Scanning in progress" text
- Updates every 500ms for smooth animation
- Automatically stops when prescan completes

#### New Method: `add_prescan_folder(summary)`
- Called incrementally as each folder completes scanning
- Adds folder to the treeview immediately
- Updates running totals dynamically
- Shows progress in real-time

#### New Method: `_update_prescan_totals()`
- Updates the totals label with current counts
- Shows: Images, Videos, Data (with "have N" counts)
- Updates estimated bytes

#### New Method: `finish_prescan(tasks, total_bytes)`
- Called when all folders are scanned
- Stops the loading animation
- Updates final totals
- **Enables the "Start Download" button**
- Handles case where window was closed early (re-enables main Start button)

#### Updated Method: `start()`
- Now calls `create_prescan_window()` immediately
- Window appears before prescan worker starts
- Provides instant user feedback

### 3. Worker Thread Updates (`gui/workers.py`)

#### Updated Function: `run_prescan()`

**New polling mechanism:**
- Starts a background timer that checks for new folder summaries every 300ms
- When new folders complete, sends them to GUI immediately via `add_prescan_folder()`
- Uses mutable list `[sent_count]` to track which summaries have been sent
- Continues polling until prescan completes

**Flow:**
1. Reset `dfr.INTERRUPTED = False` to allow new scan
2. Start polling timer (checks every 300ms)
3. Run `prescan_tasks(service)` (blocks until complete or interrupted)
4. Mark prescan as done (stops polling)
5. Send any remaining summaries
6. Call `finish_prescan()` to enable Start button

**Interruption handling:**
- When window is closed, `dfr.INTERRUPTED` is set to `True`
- Backend prescan tasks check this flag and stop early
- Start button is re-enabled regardless of completion status

## User Experience Improvements

### Before:
1. User clicks "Start"
2. **Long wait with no feedback** (window opens after 20-30+ seconds)
3. All folders appear at once
4. User confirms and starts download

### After:
1. User clicks "Start"
2. **Prescan window opens immediately** (<100ms)
3. **Loading animation shows progress** ("Scanning in progress...")
4. **Folders appear as they complete** (incremental updates every ~300ms)
5. **Totals update in real-time**
6. Loading animation stops, Start button enables
7. User confirms and starts download

## Technical Details

### Threading Model
- Main GUI runs in main thread (Tk event loop)
- Prescan runs in worker thread (via `start_worker_thread`)
- Polling timer runs in separate timer threads
- Updates sent to GUI via `app_ref.after(0, callback)` for thread safety

### State Management
- `_prescan_loading`: Boolean flag controlling animation
- `_prescan_tasks`: List of tasks to pass to download worker
- `_prescan_totals`: Dictionary of running totals
- `_prescan_total_bytes`: Estimated total bytes
- `sent_count[0]`: Tracks which summaries have been sent (mutable reference)

### Error Handling
- All GUI updates wrapped in try/except
- Fallback to re-enable buttons if errors occur
- Graceful degradation if window is closed early

### Cancel/Close Behavior
- **Cancel button**: Stops loading animation, signals backend to stop, closes window, re-enables Start button
- **X button (window close)**: Same as Cancel button via `WM_DELETE_WINDOW` protocol
- **Backend interrupt**: Sets `dfr.INTERRUPTED = True` to stop prescan tasks
- **Reset on restart**: `dfr.INTERRUPTED` is reset to `False` when starting new prescan
- **Finish after close**: If prescan completes after window is closed, Start button is still re-enabled

## Testing

A test script `test_prescan_ui.py` is provided to verify:
- ✓ Window opens immediately
- ✓ Loading animation runs smoothly
- ✓ Folders added incrementally
- ✓ Start button initially disabled
- ✓ Start button enables when complete

Run: `python3 test_prescan_ui.py`

## Future Enhancements

Potential improvements for the future:
1. Add progress bar showing N/Total folders scanned
2. Show current folder being scanned
3. Cancel button that actually interrupts prescan
4. Persist prescan results between sessions
5. Add "Skip prescan" option for users who want to start immediately
