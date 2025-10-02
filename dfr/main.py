# dfr/main.py
# Orchestration of normal run and converter mode

import os, re, logging, time
from pathlib import Path
from typing import List, Dict

import drive_fetch_resilient as dfr
from .logfmt import setup_logging
from .auth import get_service_and_creds, get_account_info
from .utils import human_bytes
from .process import process_file, print_progress, print_grand_summary
from .downloads import cleanup_incomplete_targets, download_file_resumable
from .prescan import prescan_tasks
from .listing import wait_if_paused
from .utils import extract_folder_id


def main():
    # Reset runtime counters but preserve prescan expectations and already-have counts
    # so progress (done = already + done) reflects existing files.
    dfr.TOTALS = dfr.Totals()
    # EXPECTED_* and ALREADY_HAVE_* are set by prescan; keep them as-is.
    dfr.START_TS = time.time()
    dfr.INTERRUPTED = False
    setup_logging()

    # Conversion mode
    if dfr.CONVERT_THUMBS_DIR:
        logging.info(dfr.L(
            f"=== Convert thumbnails in {dfr.CONVERT_THUMBS_DIR} to originals ===",
            f"=== Konversi thumbnail di {dfr.CONVERT_THUMBS_DIR} ke ukuran asli ==="
        ))
        service, creds = get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
        acct = get_account_info(service)
        if acct.get("email") or acct.get("name"):
            logging.info(dfr.L(
                f"Using account: {acct.get('name') or ''} <{acct.get('email') or ''}>",
                f"Menggunakan akun: {acct.get('name') or ''} <{acct.get('email') or ''}>"
            ))
        thumb_dir = Path(dfr.CONVERT_THUMBS_DIR)
        if not thumb_dir.exists():
            logging.error(dfr.L(f"Folder not found: {thumb_dir}", f"Folder tidak ditemukan: {thumb_dir}"))
            print_grand_summary()
            return
        pat = re.compile(r"__(?P<fid>[A-Za-z0-9_-]+)_w\d+\.jpg$", re.IGNORECASE)
        for path in thumb_dir.rglob("*_w*.jpg"):
            if dfr.INTERRUPTED:
                break
            m = pat.search(path.name)
            if not m:
                continue
            fid = m.group("fid")
            ext_out = ".jpg"
            try:
                from .listing import get_item
                meta = get_item(service, fid, "id,name,fileExtension")
                name_on_drive = meta.get("name") or fid
                _, name_ext = os.path.splitext(name_on_drive)
                if name_ext:
                    ext_out = name_ext
                elif meta.get("fileExtension"):
                    ext_out = f".{meta['fileExtension']}"
            except Exception as e:
                logging.debug(dfr.L(f"Could not query ext for {fid}: {e}",
                                    f"Tidak bisa mengambil ekstensi untuk {fid}: {e}"))
            base_no_thumb = re.sub(r"_w\d+\.jpg$", "", path.name, flags=re.IGNORECASE)
            target = path.with_name(f"{base_no_thumb}{ext_out}")
            if target.exists() and not dfr.OVERWRITE:
                logging.info(dfr.L(f"Already have original: {target.name}",
                                   f"Sudah ada ukuran asli: {target.name}"))
                dfr.TOTALS.grand.images_skipped += 1
                continue
            logging.info(dfr.L(f"Fetching original for {path.name} (id={fid}) -> {target.name}",
                               f"Mengambil ukuran asli untuk {path.name} (id={fid}) -> {target.name}"))
            ok = download_file_resumable(service, creds, fid, str(target), label=dfr.L("Image", "Gambar"))
            if ok:
                dfr.TOTALS.grand.images_done += 1
            else:
                dfr.TOTALS.grand.images_failed += 1
        print_grand_summary()
        return

    # Normal run
    logging.info(dfr.L(
        "=== Drive Previews (images) + Full Videos ===",
        "=== Ambil Pratinjau Drive (gambar) + Video Penuh ==="
    ))
    logging.info(
        dfr.L(
            f"Output dir: {dfr.OUTPUT_DIR}\nImage width: {dfr.IMAGE_WIDTH}px | Overwrite: {dfr.OVERWRITE} | Resume: {dfr.ROBUST_RESUME} | "
            f"Download videos: {dfr.DOWNLOAD_VIDEOS} | Image originals: {dfr.DOWNLOAD_IMAGES_ORIGINAL}",
            f"Folder keluaran: {dfr.OUTPUT_DIR}\nLebar gambar: {dfr.IMAGE_WIDTH}px | Overwrite: {dfr.OVERWRITE} | Resume: {dfr.ROBUST_RESUME} | "
            f"Unduh video: {dfr.DOWNLOAD_VIDEOS} | Gambar asli: {dfr.DOWNLOAD_IMAGES_ORIGINAL}"
        )
    )

    from .auth import get_service_and_creds, get_account_info
    service, creds = get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
    acct = get_account_info(service)
    if acct.get("email") or acct.get("name"):
        logging.info(dfr.L(
            f"Using account: {acct.get('name') or ''} <{acct.get('email') or ''}>",
            f"Menggunakan akun: {acct.get('name') or ''} <{acct.get('email') or ''}>"
        ))

    if dfr.DIRECT_TASKS:
        tasks = dfr.DIRECT_TASKS
        from .utils import classify_media
        dfr.EXPECTED_IMAGES = sum(1 for t in tasks if classify_media(t.get("mimeType",""), t.get("name",""), t.get("fileExtension")) == "image")
        dfr.EXPECTED_VIDEOS = sum(1 for t in tasks if classify_media(t.get("mimeType",""), t.get("name",""), t.get("fileExtension")) == "video")
        dfr.EXPECTED_DATA = sum(1 for t in tasks if classify_media(t.get("mimeType",""), t.get("name",""), t.get("fileExtension")) == "data")
        logging.info(dfr.L(f"Using direct task list: {len(tasks)} items", f"Memakai daftar tugas langsung: {len(tasks)} item"))
    else:
        tasks = prescan_tasks(service)

    image_tasks: List[Dict] = []
    video_tasks: List[Dict] = []
    data_tasks: List[Dict] = []
    from .utils import classify_media
    for f in tasks:
        kind = classify_media(f.get("mimeType",""), f.get("name",""), f.get("fileExtension"))
        if kind == "video":
            video_tasks.append(f)
        elif kind == "data":
            data_tasks.append(f)
        else:
            image_tasks.append(f)

    # Sequential images
    for f in image_tasks:
        if dfr.INTERRUPTED:
            break
        wait_if_paused()
        try:
            ok = process_file(service, creds, f, f['__folder_out'], f['__root_name'])
            if ok:
                print_progress()
        except Exception as e:
            logging.error(dfr.L(f"Worker error: {e}", f"Kesalahan pekerja: {e}"))

    # Sequential videos
    for f in video_tasks:
        if dfr.INTERRUPTED:
            break
        wait_if_paused()
        try:
            ok = process_file(service, creds, f, f['__folder_out'], f['__root_name'])
            if ok:
                print_progress()
        except Exception as e:
            logging.error(dfr.L(f"Worker error: {e}", f"Kesalahan pekerja: {e}"))

    # Sequential data
    for f in data_tasks:
        if dfr.INTERRUPTED:
            break
        wait_if_paused()
        try:
            ok = process_file(service, creds, f, f['__folder_out'], f['__root_name'])
            if ok:
                print_progress()
        except Exception as e:
            logging.error(dfr.L(f"Data worker error: {e}", f"Kesalahan pekerja data: {e}"))

    cleanup_incomplete_targets()
    print_progress()
    print_grand_summary()
    logging.info(dfr.L("Done.", "Selesai."))
    dfr.DIRECT_TASKS = None
