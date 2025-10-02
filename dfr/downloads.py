# dfr/downloads.py
# Download implementations (thumbnail and resumable)

import os, io, time, logging, requests
from typing import Set
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import AuthorizedSession

import drive_fetch_resilient as dfr
from .utils import ensure_dir, human_bytes
from .listing import get_item

# Track targets that are currently being written so we can clean up on cancel/exit
INCOMPLETE_TARGETS: Set[str] = set()


def _mark_incomplete(target: str):
    with dfr._LOCK:
        INCOMPLETE_TARGETS.add(target)


def _mark_complete(target: str):
    with dfr._LOCK:
        INCOMPLETE_TARGETS.discard(target)


def cleanup_incomplete_targets():
    removed = 0
    with dfr._LOCK:
        targets = list(INCOMPLETE_TARGETS)
        INCOMPLETE_TARGETS.clear()
    for t in targets:
        try:
            if os.path.exists(t):
                os.remove(t)
                removed += 1
        except Exception:
            pass
    if removed:
        logging.warning(dfr.L(f"Removed {removed} incomplete file(s) on exit/cancel.",
                              f"Menghapus {removed} berkas yang belum selesai saat keluar/batal."))


def download_thumbnail(url: str, out_path: str, retries=10) -> bool:
    _mark_incomplete(out_path)
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                if r.status_code == 404:
                    raise requests.HTTPError("thumbnail not ready (404)")
                r.raise_for_status()
                bytes_written = 0
                ensure_dir(os.path.dirname(out_path))
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk); bytes_written += len(chunk)
            _mark_complete(out_path)
            logging.info(dfr.L(f"Image saved: {out_path} ({human_bytes(bytes_written)})",
                               f"Gambar tersimpan: {out_path} ({human_bytes(bytes_written)})"))
            logging.info(f"[Bytes] {dfr.TOTALS.grand.bytes_written}")
            dfr.TOTALS.grand.bytes_written += bytes_written
            return True
        except Exception as e:
            if attempt == retries:
                _mark_incomplete(out_path)
                logging.error(dfr.L(f"[!] Thumbnail failed permanently: {url} -> {e}",
                                    f"[!] Thumbnail gagal permanen: {url} -> {e}"))
                return False
            logging.warning(dfr.L(f"Thumbnail attempt {attempt}/{retries} failed: {e}",
                                  f"Percobaan thumbnail {attempt}/{retries} gagal: {e}"))
            dfr.backoff_sleep(attempt)


def download_file_resumable(service, creds, file_id: str, target: str, label: str = "File") -> bool:
    _mark_incomplete(target)
    ensure_dir(os.path.dirname(target))
    session = AuthorizedSession(creds)
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    total_size = None
    try:
        meta = get_item(service, file_id, "size, name")
        if "size" in meta:
            total_size = int(meta["size"])
    except Exception as e:
        logging.debug(dfr.L(f"Could not get size for {file_id}: {e}",
                            f"Tidak bisa mendapatkan ukuran untuk {file_id}: {e}"))
    downloaded = os.path.getsize(target) if os.path.exists(target) else 0
    mode = "ab" if downloaded > 0 else "wb"
    if downloaded > 0:
        logging.info(dfr.L(f"Resuming {label.lower()} at {human_bytes(downloaded)} -> {os.path.basename(target)}",
                           f"Melanjutkan {label.lower()} di {human_bytes(downloaded)} -> {os.path.basename(target)}"))
    if total_size is not None and downloaded >= total_size:
        _mark_complete(target)
        logging.info(dfr.L(f"Already complete: {os.path.basename(target)}",
                           f"Sudah lengkap: {os.path.basename(target)}"))
        return True
    last_report = time.time()
    while True:
        if dfr.INTERRUPTED:
            return False
        dfr.wait_if_paused()
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}
        for attempt in range(1, 9):
            try:
                with session.get(url, headers=headers, stream=True, timeout=60) as r:
                    if r.status_code not in (200, 206):
                        if r.status_code == 416 and total_size and os.path.getsize(target) >= total_size:
                            logging.info(dfr.L("Server reports complete (416).", "Server melapor selesai (416)."))
                            return True
                        r.raise_for_status()
                    with open(target, mode) as f:
                        for chunk in r.iter_content(chunk_size=8*1024*1024):
                            if dfr.INTERRUPTED:
                                return False
                            dfr.wait_if_paused()
                            if chunk:
                                f.write(chunk); downloaded += len(chunk); dfr.TOTALS.grand.bytes_written += len(chunk)
                                now = time.time()
                                if now - last_report >= 1.5:
                                    if total_size:
                                        pct = 100.0 * downloaded / total_size
                                        logging.info(dfr.L(
                                            f"{label} {os.path.basename(target)}: {pct:.1f}% ({human_bytes(downloaded)}/{human_bytes(total_size)})",
                                            f"{label} {os.path.basename(target)}: {pct:.1f}% ({human_bytes(downloaded)}/{human_bytes(total_size)})"
                                        ))
                                        logging.info(f"[Bytes] {dfr.TOTALS.grand.bytes_written}")
                                        last_report = now
                                    else:
                                        logging.info(dfr.L(
                                            f"{label} {os.path.basename(target)}: {human_bytes(downloaded)} downloaded",
                                            f"{label} {os.path.basename(target)}: {human_bytes(downloaded)} diunduh"
                                        ))
                break
            except Exception as e:
                if attempt == 8:
                    logging.error(dfr.L(f"[!] Chunk failed permanently (id={file_id}): {e}",
                                        f"[!] Potongan gagal permanen (id={file_id}): {e}"))
                    return False
                logging.warning(dfr.L(f"Chunk attempt {attempt}/8 failed: {e}",
                                      f"Percobaan potongan {attempt}/8 gagal: {e}"))
                dfr.backoff_sleep(attempt); mode = "ab"
        if total_size is None:
            headers_probe = {"Range": f"bytes={downloaded}-"}
            try:
                dfr.wait_if_paused()
                with session.get(url, headers=headers_probe, stream=True, timeout=30) as r2:
                    if r2.status_code == 416:
                        _mark_complete(target)
                        logging.info(dfr.L("Server indicated EOF (416); treating as complete.",
                                           "Server menunjukkan EOF (416); dianggap selesai."))
                        return True
            except Exception:
                return True
        if total_size is not None and downloaded >= total_size:
            _mark_complete(target)
            logging.info(dfr.L(f"{label} done: {os.path.basename(target)} ({human_bytes(downloaded)})",
                               f"{label} selesai: {os.path.basename(target)} ({human_bytes(downloaded)})"))
            logging.info(f"[Bytes] {dfr.TOTALS.grand.bytes_written}")
            return True


def download_video_resumable(service, creds, file_id: str, target: str) -> bool:
    return download_file_resumable(service, creds, file_id, target, label=dfr.L("Video", "Video"))


def _download_video_simple(service, file_id: str, target: str) -> bool:
    req = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(target, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, req, chunksize=10 * 1024 * 1024)
        done = False; last_pct = -1
        while not done:
            status, done = downloader.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logging.info(dfr.L(f"Video {os.path.basename(target)}: {pct}%",
                                   f"Video {os.path.basename(target)}: {pct}%"))
                last_pct = pct
    try:
        dfr.TOTALS.grand.bytes_written += os.path.getsize(target)
        logging.info(f"[Bytes] {dfr.TOTALS.grand.bytes_written}")
    except Exception:
        pass
    return True
