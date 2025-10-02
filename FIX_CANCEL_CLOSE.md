# Fix: Prescan Window Close/Cancel Button Issue

## Problem

When the user closed the prescan preview window (either by clicking Cancel or the X button), the main "Start" button remained disabled. This prevented the user from starting a new prescan without restarting the application.

## Root Cause

The prescan window's close handlers were not properly re-enabling the main Start button and Cancel button states when the window was closed prematurely.

## Solution

### Changes Made

#### 1. Added Window Close Protocol Handler (`gui/main_app.py`)

Added `WM_DELETE_WINDOW` protocol handler in `create_prescan_window()`:

```python
def on_window_close():
    self._prescan_loading = False
    try:
        # Signal the backend to stop
        import drive_fetch_resilient as dfr
        dfr.INTERRUPTED = True
    except Exception:
        pass
    try:
        win.destroy()
    except Exception:
        pass
    # Re-enable Start, disable Cancel
    try:
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
    except Exception:
        pass

win.protocol("WM_DELETE_WINDOW", on_window_close)
```

This ensures that clicking the X button on the window triggers the same cleanup as clicking Cancel.

#### 2. Updated Cancel Button Handler (`gui/main_app.py`)

Enhanced `on_cancel()` to properly signal backend interruption:

```python
def on_cancel():
    self._prescan_loading = False  # Stop animation
    try:
        # Signal the backend to stop
        import drive_fetch_resilient as dfr
        dfr.INTERRUPTED = True
    except Exception:
        pass
    try:
        win.destroy()
    except Exception:
        pass
    # Re-enable Start, disable Cancel
    try:
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
    except Exception:
        pass
```

#### 3. Added Safety Checks in `finish_prescan()` (`gui/main_app.py`)

Enhanced `finish_prescan()` to handle the case where the window was closed before prescan completes:

```python
# Check if window was closed early
if not hasattr(self, "_prescan_win") or not self._prescan_win:
    # Window was closed, just re-enable the main Start button
    try:
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
    except Exception:
        pass
    return

try:
    # Check if window still exists
    if not tk.Toplevel.winfo_exists(self._prescan_win):
        # Window was closed, just re-enable the main Start button
        try:
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
        except Exception:
            pass
        return
except Exception:
    # Window was closed, just re-enable the main Start button
    try:
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
    except Exception:
        pass
    return
```

#### 4. Reset INTERRUPTED Flag (`gui/workers.py`)

Added reset of `dfr.INTERRUPTED` flag at the start of each prescan:

```python
# Configure backend variables for prescan
dfr.FOLDER_URLS = list(urls)
dfr.OUTPUT_DIR = str(out_root)
dfr.IMAGE_WIDTH = int(preview_width)
dfr.DOWNLOAD_VIDEOS = bool(download_videos)
dfr.DOWNLOAD_IMAGES_ORIGINAL = bool(img_original)
dfr.CONVERT_THUMBS_DIR = ""

# Reset interrupted flag for new scan
dfr.INTERRUPTED = False
```

This ensures that a new prescan can run even if the previous one was interrupted.

## Behavior After Fix

### Scenario 1: User Clicks Cancel Button
1. Loading animation stops
2. Backend receives interrupt signal (`dfr.INTERRUPTED = True`)
3. Prescan window closes
4. Start button re-enables
5. Cancel button disables
6. User can click Start again

### Scenario 2: User Clicks X Button (Window Close)
1. Same as Scenario 1 (handled by `WM_DELETE_WINDOW` protocol)

### Scenario 3: User Closes Window, Prescan Completes Later
1. Prescan worker thread finishes
2. Calls `finish_prescan()`
3. `finish_prescan()` detects window is closed
4. Re-enables Start button
5. User can click Start again

### Scenario 4: Prescan Completes Normally
1. Loading animation stops
2. Totals update
3. "Start Download" button in prescan window enables
4. User can proceed with download or cancel

## Testing

### Manual Testing Steps

1. **Test Cancel Button:**
   - Click Start
   - Prescan window opens
   - Click Cancel in prescan window
   - ✓ Start button should be enabled again
   - Click Start again
   - ✓ New prescan should start

2. **Test X Button:**
   - Click Start
   - Prescan window opens
   - Click X to close window
   - ✓ Start button should be enabled again
   - Click Start again
   - ✓ New prescan should start

3. **Test Normal Completion:**
   - Click Start
   - Wait for prescan to complete
   - ✓ "Start Download" button should enable
   - Click Cancel or close window
   - ✓ Start button should be enabled again

### Automated Test

Run `test_prescan_cancel.py` to verify all scenarios:

```bash
python3 test_prescan_cancel.py
```

Expected output:
```
✓ Test 1 PASSED: Start button re-enabled after Cancel
✓ Test 2 PASSED: Start button re-enabled after X button
✓ Test 3 PASSED: Start button re-enabled after completion

==================================================
TEST RESULTS:
  ✓ PASSED: Cancel button test
  ✓ PASSED: X button test
  ✓ PASSED: Normal completion test
==================================================

✓ ALL TESTS PASSED!
```

## Files Modified

1. `gui/main_app.py`:
   - Added `on_window_close()` handler
   - Updated `on_cancel()` handler
   - Enhanced `finish_prescan()` with safety checks

2. `gui/workers.py`:
   - Added `dfr.INTERRUPTED = False` reset at start of prescan

## Impact

- ✅ Users can now cancel/close prescan window and start again
- ✅ No need to restart the application
- ✅ Backend properly stops when interrupted
- ✅ Button states are always correct
- ✅ All error scenarios are handled gracefully

## Related Issues

This fix complements the previous improvements:
- Prescan window opens immediately
- Loading animation provides feedback
- Folders populate incrementally
- **Now: Cancel/close works properly**
