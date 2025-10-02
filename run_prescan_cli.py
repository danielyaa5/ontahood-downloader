#!/usr/bin/env python3
import drive_fetch_resilient as dfr
from dfr.auth import get_service_and_creds
from dfr.prescan import prescan_tasks

import sys

urls = [
    "https://drive.google.com/drive/folders/1E7mmYtjm-joq7jNX8Dx_QON51G-tFASu",
    "https://drive.google.com/drive/folders/1n7c-7P4KzDbTml4rvZyBjbAtVrUtJ1zw",
    "https://drive.google.com/drive/folders/1zhKzZhrCbJwi282TCm-ibSM23RgumKn-",
    "https://drive.google.com/drive/folders/1F4SdtyEoYC6qriFSffaaK9_749B94Xyv",
    "https://drive.google.com/drive/folders/1KgTrhw1xeF6x66yi4MOvKv79ONHN-aTz",
    "https://drive.google.com/drive/folders/1jUjWloriy-cRugvQFCU93Q7RSESo3HxR",
    "https://drive.google.com/drive/folders/1Is_wAFb6VMs1C6r8UDbWInWb8bQCiFEi",
    "https://drive.google.com/drive/folders/1xWqEKC-7VsZpzeaYEwOVg0x8Pvf9k8EH",
    "https://drive.google.com/drive/folders/1hHXR-uxk6lpZIN2kIgqaqErvUEk_D_7P",
    "https://drive.google.com/drive/folders/1r-SX_trEA5sEZeYQzrPjCmkTIhP_cszI",
    "https://drive.google.com/drive/folders/1i7RslwSVFTef7twKdoXDZuXsEx0DNMwk",
]

# Configure globals
dfr.FOLDER_URLS = urls

svc, _ = get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)

# Run prescan
_ = prescan_tasks(svc)

print("\n[CLI Prescan Totals]")
print(f"Images expected: {dfr.EXPECTED_IMAGES} (already {dfr.ALREADY_HAVE_IMAGES})")
print(f"Videos expected: {dfr.EXPECTED_VIDEOS} (already {dfr.ALREADY_HAVE_VIDEOS})")
print(f"Total expected bytes: {dfr.EXPECTED_TOTAL_BYTES}")
