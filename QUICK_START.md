# Quick Start Guide - Prescan Feature

## What Changed?

The prescan window now provides much better feedback:

### ✅ Immediate Window Opening
- The prescan dialog opens **instantly** when you click "Start"
- No more waiting in confusion!

### ✅ Live Loading Animation
- You'll see "Scanning in progress..." with animated dots
- This confirms the app is working and scanning your folders

### ✅ Real-Time Folder Updates
- Folders appear in the list **as they complete scanning**
- No need to wait for all folders to finish before seeing results
- Watch the totals update in real-time!

### ✅ Smart Button States
- "Start Download" button is disabled while scanning
- It automatically enables when scanning completes
- "Cancel" button works during scanning

## How to Use

1. **Enter folder URLs** in the text box (one per line)
2. **Choose output directory** 
3. **Set image mode** (ORIGINAL or width in pixels)
4. **Click "Start"**
5. 🎉 **Prescan window opens immediately!**
   - Watch folders appear as they're scanned
   - See totals update live
   - Loading animation shows progress
6. **Wait for scanning to complete**
   - "Start Download" button will enable when ready
   - Review the folder counts
7. **Click "Start Download"** to begin the actual download
   - Or click "Cancel" to abort

## What You'll See

```
╔══════════════════════════════════════════════════╗
║ Pre-Scan Preview                                 ║
╠══════════════════════════════════════════════════╣
║ Review expected downloads per link...            ║
║                                                  ║
║ ┌──────────────────────────────────────────┐    ║
║ │ Folder          Images    Videos   Data   │    ║
║ ├──────────────────────────────────────────┤    ║
║ │ Folder 1      469 (have 0)  7 (have 0)  0│← Appears immediately
║ │ Folder 2      886 (have 0)  0 (have 0)  0│← Appears as scanned
║ │ Folder 3      567 (have 0)  0 (have 0)  0│← Appears as scanned
║ └──────────────────────────────────────────┘    ║
║                                                  ║
║ Totals: Images=1922 | Videos=7 | Data=0          ║← Updates live!
║ Estimated bytes: 1.2 GB                          ║
║                                                  ║
║ Scanning in progress...                          ║← Loading animation
║                                                  ║
║ [Cancel]                     [Start Download]    ║← Disabled while scanning
╚══════════════════════════════════════════════════╝
```

## Troubleshooting

### Window doesn't open?
- Check that you have valid folder URLs
- Verify output directory is selected
- Check image mode is valid (100-6000 or ORIGINAL)

### Folders not appearing?
- Check your network connection
- Verify you're signed in to Google Drive
- Check the log panel for error messages

### Animation stuck?
- The prescan might be taking time for large folders
- Check the log panel for progress messages
- Be patient - scanning can take time for many files

## Tips

- **Large folders**: Scanning 1000+ files per folder can take 10-30 seconds each
- **Multiple folders**: They scan in parallel (up to CONCURRENCY workers)
- **Network issues**: Slow connections will slow down scanning
- **First scan**: Initial scans are slower as the app authenticates

## Need Help?

Check the main log panel for detailed progress messages and any error information.
