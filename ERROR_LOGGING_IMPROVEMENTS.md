# Error Logging Improvements

## Problem: Missing Stack Traces in Error Logs

The error logs were missing detailed stack traces, making debugging difficult. For example, errors like "Folder URL had no ID" provided no context about what URL caused the problem or why.

## Root Causes Discovered

1. **Logic Bug**: The main issue was that `resolve_folder(service, url)` was being called with a folder ID instead of a URL:
   ```python
   # WRONG:
   folder_id = extract_folder_id(url)
   name, ok = resolve_folder(svc, folder_id)  # Passing ID, not URL!
   
   # CORRECT:
   folder_id = extract_folder_id(url) 
   name, ok = resolve_folder(svc, url)  # Pass the original URL
   ```

2. **Using `logging.error()` instead of `logging.exception()`**
   - `logging.error(f"Error: {e}")` only logs the error message
   - `logging.exception(f"Error: {e}")` logs the error message AND full stack trace

3. **Missing contextual information**
   - Error messages didn't include the problematic data (e.g., the actual URL)
   - Made it impossible to identify which input caused the error

4. **Incomplete exception details**
   - Only logging `str(e)` instead of the full exception context

## Changes Made

### 1. Fixed Logic Bug in resolve_folder Calls
**Files:** `drive_fetch_resilient.py:763` and `drive_fetch_gui.py:1210`

**Before:**
```python
folder_id = extract_folder_id(url)
name, ok = resolve_folder(svc, folder_id)  # WRONG: passing ID instead of URL
```

**After:**
```python
folder_id = extract_folder_id(url) 
name, ok = resolve_folder(svc, url)  # CORRECT: pass the original URL
```

### 2. Enhanced URL Error Logging
**File:** `drive_fetch_resilient.py:309`

**Before:**
```python
logging.error(L("Folder URL had no ID.", "URL folder tidak memiliki ID."))
```

**After:**
```python
logging.error(L(f"Folder URL had no ID: '{url}'", f"URL folder tidak memiliki ID: '{url}'"))
# Add stack trace for debugging logical errors
import traceback
logging.debug("Call stack for URL validation error:\n" + "".join(traceback.format_stack()))
```

### 3. Added Stack Traces for Worker Errors
**Files:** `drive_fetch_resilient.py` (multiple locations)

**Before:**
```python
except Exception as e:
    logging.error(L(f"Worker error: {e}", f"Kesalahan pekerja: {e}"))
```

**After:**
```python
except Exception as e:
    logging.exception(L(f"Worker error: {e}", f"Kesalahan pekerja: {e}"))
```

### 4. Enhanced GUI Error Logging
**File:** `drive_fetch_gui.py`

**Before:**
```python
except Exception as e:
    logging.error(f"Scan error for URL {url}: {e}")
```

**After:**
```python
except Exception as e:
    logging.exception(f"Scan error for URL {url}: {e}")
```

## Specific Locations Changed

1. `drive_fetch_resilient.py:309` - URL validation error with context
2. `drive_fetch_resilient.py:887` - Listing errors for URLs
3. `drive_fetch_resilient.py:933` - Prescan worker errors
4. `drive_fetch_resilient.py:1107` - Image processing worker errors
5. `drive_fetch_resilient.py:1119` - Video processing worker errors  
6. `drive_fetch_resilient.py:1131` - Data processing worker errors
7. `drive_fetch_gui.py:1359` - GUI scan errors
8. `drive_fetch_gui.py:1442` - GUI parallel scan errors

## Testing the Improvements

Run the test script to see the improved error logging:
```bash
python3 test_error_logging.py
```

## Benefits

1. **Full Stack Traces**: When unexpected errors occur, you'll see exactly where they happened in the code
2. **Contextual Information**: Error messages now include the specific data that caused the problem
3. **Better Debugging**: Much easier to identify and fix issues when they occur
4. **Preserved Multilingual Support**: All changes maintain both English and Indonesian error messages

## Example: Before vs After

**Before (from your log):**
```
2025-10-01 20:33:34 | ERROR   | Folder URL had no ID.
```

**After (with improvements):**
```
2025-10-01 20:33:34 | ERROR   | Folder URL had no ID: 'https://invalid-url-here'
Traceback (most recent call last):
  File "path/to/file.py", line X, in function_name
    ... (full stack trace showing exactly where the error occurred)
```

## Note

The main exception handler at the bottom of `drive_fetch_resilient.py` was already correctly using `logging.exception()`, so no changes were needed there.