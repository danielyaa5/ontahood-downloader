#!/usr/bin/env python3
"""
Diagnostic script to verify Google Drive folder file counts.
This script will manually count all files in a folder to verify the listing is complete.
"""

import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

import drive_fetch_resilient as dfr
from dfr.auth import get_service_and_creds
from dfr.utils import extract_folder_id, classify_media
from dfr.listing import list_folder_recursive, resolve_folder

def count_files_in_folder(url: str):
    """Count all images and videos in a Google Drive folder."""
    print(f"\n{'='*80}")
    print(f"Analyzing URL: {url}")
    print(f"{'='*80}\n")
    
    # Get service
    service, _ = get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
    
    # Extract folder ID
    folder_id = extract_folder_id(url)
    if not folder_id:
        print("ERROR: Could not extract folder ID from URL")
        return
    
    print(f"Folder ID: {folder_id}\n")
    
    # Resolve folder name
    folder_name, ok = resolve_folder(service, folder_id)
    if not ok:
        print("ERROR: Could not resolve folder")
        return
    
    print(f"Folder name: {folder_name}\n")
    print("Starting file enumeration...\n")
    
    # Count files
    total_files = 0
    images = 0
    videos = 0
    other = 0
    folders = 0
    
    file_list = []
    
    for item in list_folder_recursive(service, folder_id, rel_path=""):
        total_files += 1
        mime = item.get("mimeType", "")
        name = item.get("name", "")
        file_ext = item.get("fileExtension")
        
        kind = classify_media(mime, name, file_ext)
        
        if kind == "image":
            images += 1
            file_list.append(f"  IMAGE: {name} (ID: {item.get('id')})")
        elif kind == "video":
            videos += 1
            file_list.append(f"  VIDEO: {name} (ID: {item.get('id')})")
        else:
            other += 1
            if total_files <= 20:  # Only show first 20 "other" files
                file_list.append(f"  OTHER: {name} [{mime}]")
        
        # Print progress every 100 files
        if total_files % 100 == 0:
            print(f"Progress: {total_files} files scanned (images: {images}, videos: {videos}, other: {other})")
    
    print(f"\n{'='*80}")
    print(f"RESULTS for: {folder_name}")
    print(f"{'='*80}")
    print(f"Total files scanned: {total_files}")
    print(f"  Images: {images}")
    print(f"  Videos: {videos}")
    print(f"  Other: {other}")
    print(f"{'='*80}\n")
    
    # Show first 10 sample files automatically
    if file_list and len(file_list) > 0:
        print("\nSample files (first 10):")
        for line in file_list[:10]:
            print(line)
        if len(file_list) > 10:
            print(f"... and {len(file_list) - 10} more files")
    
    return {
        "folder_name": folder_name,
        "total": total_files,
        "images": images,
        "videos": videos,
        "other": other
    }

def main():
    print("Google Drive Folder Counter")
    print("This tool will count all files in your Google Drive folders\n")
    
    if len(sys.argv) > 1:
        # URLs provided as command line arguments
        urls = sys.argv[1:]
    else:
        # Interactive mode
        print("Enter Google Drive folder URLs (one per line, empty line to finish):")
        urls = []
        while True:
            url = input("> ").strip()
            if not url:
                break
            urls.append(url)
    
    if not urls:
        print("No URLs provided. Exiting.")
        return
    
    # Process each URL
    results = []
    for url in urls:
        try:
            result = count_files_in_folder(url)
            if result:
                results.append(result)
        except Exception as e:
            print(f"\nERROR processing {url}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    if results:
        print(f"\n\n{'='*80}")
        print("SUMMARY OF ALL FOLDERS")
        print(f"{'='*80}")
        total_images = sum(r["images"] for r in results)
        total_videos = sum(r["videos"] for r in results)
        print(f"\nTotal across {len(results)} folder(s):")
        print(f"  Images: {total_images}")
        print(f"  Videos: {total_videos}")
        print(f"  Total media files: {total_images + total_videos}")
        print(f"\nPer-folder breakdown:")
        for r in results:
            print(f"  {r['folder_name']}: {r['images']} images, {r['videos']} videos")

if __name__ == "__main__":
    main()
