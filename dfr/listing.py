# dfr/listing.py
# Listing utilities and Drive folder traversal

import os, logging
from typing import Iterator, Dict

from googleapiclient.errors import HttpError

import drive_fetch_resilient as dfr
from .utils import safe_filename


def gapi_execute_with_retry(req, retries: int = 8):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return req.execute()
        except HttpError as e:
            code = getattr(getattr(e, "resp", None), "status", None)
            if code in (429, 500, 502, 503, 504):
                last_exc = e; dfr.backoff_sleep(attempt); continue
            raise
        except Exception as e:
            last_exc = e; dfr.backoff_sleep(attempt)
    raise RuntimeError(f"Google API request failed after retries: {last_exc}")


def get_item(service, file_id: str, fields: str) -> Dict:
    req = service.files().get(fileId=file_id, fields=fields, supportsAllDrives=True)
    return gapi_execute_with_retry(req)


def resolve_folder(service, folder_id: str):
    if not folder_id:
        logging.error(dfr.L("Folder URL had no ID.", "URL folder tidak memiliki ID.")); return None, False
    try:
        req = service.files().get(fileId=folder_id, fields="id,name,mimeType", supportsAllDrives=True)
        meta = gapi_execute_with_retry(req)
        if meta.get("mimeType") != "application/vnd.google-apps.folder":
            logging.error(dfr.L(f"Not a folder: {meta.get('name')} ({meta.get('mimeType')})",
                                dfr.L("Bukan folder:", "Bukan folder:")))
            return None, False
        return safe_filename(meta.get("name", folder_id)), True
    except HttpError as e:
        content = (getattr(e, "content", b"") or b"").decode("utf-8", "ignore")
        if e.resp.status == 404:
            logging.error(dfr.L(f"Not found/no access: {folder_id}",
                                f"Folder tidak ditemukan/akses ditolak: {folder_id}"))
        elif e.resp.status == 403:
            logging.error(dfr.L(f"Access denied for folder: {folder_id}",
                                f"Akses ditolak untuk folder: {folder_id}"))
        else:
            logging.error(dfr.L(f"Failed to resolve folder {folder_id}: {e} {content}",
                                f"Gagal resolve folder {folder_id}: {e} {content}"))
        return None, False


def wait_if_paused():
    import time as _t
    while dfr.PAUSE and not dfr.INTERRUPTED:
        _t.sleep(0.2)


def list_folder_recursive(service, folder_id: str, rel_path: str = "", external_cancel_check=None) -> Iterator[Dict]:
    fields = (
        "nextPageToken, "
        "files(id, name, mimeType, fileExtension, size, "
        "      shortcutDetails(targetId, targetMimeType))"
    )
    query = f"'{folder_id}' in parents and trashed = false"
    page_token = None

    while True:
        if dfr.INTERRUPTED or (external_cancel_check and external_cancel_check()):
            return
        wait_if_paused()
        req = service.files().list(
            q=query,
            fields=fields,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
            pageSize=1000,
            orderBy="name_natural"
        )
        resp = gapi_execute_with_retry(req)

        wait_if_paused()
        for item in resp.get("files", []):
            if dfr.INTERRUPTED or (external_cancel_check and external_cancel_check()):
                return
            wait_if_paused()
            mime = item.get("mimeType", "")
            if mime == "application/vnd.google-apps.folder":
                sub_name = safe_filename(item.get("name", ""))
                sub_rel = os.path.join(rel_path, sub_name) if rel_path else sub_name
                dfr.logging.debug(dfr.L(f"Descending into subfolder: {sub_name} -> {sub_rel}",
                                        f"Masuk subfolder: {sub_name} -> {sub_rel}"))
                yield from list_folder_recursive(service, item.get("id"), sub_rel, external_cancel_check)
            elif mime == "application/vnd.google-apps.shortcut":
                sd = item.get("shortcutDetails") or {}
                target_id = sd.get("targetId"); target_mime = sd.get("targetMimeType")
                if target_mime == "application/vnd.google-apps.folder" and target_id:
                    sub_name = safe_filename(item.get("name", "shortcut"))
                    sub_rel = os.path.join(rel_path, sub_name) if rel_path else sub_name
                    dfr.logging.debug(dfr.L(f"Following folder shortcut: {sub_name} -> {target_id}",
                                            f"Mengikuti shortcut folder: {sub_name} -> {target_id}"))
                    yield from list_folder_recursive(service, target_id, sub_rel, external_cancel_check)
                else:
                    norm = {
                        "id": target_id or item.get("id"),
                        "name": item.get("name", "shortcut"),
                        "mimeType": target_mime or mime,
                        "fileExtension": item.get("fileExtension"),
                        "size": item.get("size"),
                        "__rel_path": rel_path,
                        "__from_shortcut": True,
                    }
                    yield norm
            else:
                item["__rel_path"] = rel_path
                yield item

        page_token = resp.get("nextPageToken")
        if not page_token:
            break
