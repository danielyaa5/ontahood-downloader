# dfr/process.py
# File processing and progress reporting

import os, logging
from typing import Dict

import drive_fetch_resilient as dfr
from .utils import safe_filename, ensure_dir, classify_media, human_bytes
from .downloads import download_file_resumable, download_video_resumable, download_thumbnail, _download_video_simple


def process_file(service, creds, file_obj: Dict, out_dir: str, counters_key: str) -> bool:
    with dfr._LOCK:
        dfr.TOTALS.grand.scanned += 1
        folder_ctrs = dfr.TOTALS.folder(counters_key)
        folder_ctrs.scanned += 1
    name = safe_filename(file_obj.get("name", file_obj.get("id","file")))
    mime = file_obj.get("mimeType","")
    fid = file_obj.get("id")
    file_ext = file_obj.get("fileExtension")
    media_kind = classify_media(mime, name, file_ext)
    rel_path = file_obj.get("__rel_path","")
    out_subdir = os.path.join(out_dir, rel_path) if rel_path else out_dir
    ensure_dir(out_subdir)

    if media_kind == "image":
        base, ext_from_name = os.path.splitext(name)
        if dfr.DOWNLOAD_IMAGES_ORIGINAL:
            ext = ext_from_name or (("." + file_ext) if file_ext else ".jpg")
            target = os.path.join(out_subdir, f"{base}__{fid}{ext}")
        else:
            target = os.path.join(out_subdir, f"{base}__{fid}_w{dfr.IMAGE_WIDTH}.jpg")
        if not dfr.OVERWRITE and os.path.exists(target):
            logging.info(dfr.L(f"= exists (image): {target}", f"= sudah ada (gambar): {target}"))
            with dfr._LOCK:
                dfr.TOTALS.grand.images_skipped += 1; folder_ctrs.images_skipped += 1
                # In converter mode, count existing originals as completed
                if dfr.CONVERT_THUMBS_DIR:
                    dfr.ALREADY_HAVE_IMAGES += 1
            return True
        if dfr.DOWNLOAD_IMAGES_ORIGINAL:
            logging.info(dfr.L(f"Downloading image original -> {target}",
                               f"Mengunduh gambar ukuran asli -> {target}"))
            ok = download_file_resumable(service, creds, fid, target, label=dfr.L("Image", "Gambar"))
        else:
            url = f"https://drive.google.com/thumbnail?sz=w{dfr.IMAGE_WIDTH}&id={fid}"
            logging.info(dfr.L(f"Downloading image thumbnail -> {target}",
                               f"Mengunduh thumbnail -> {target}"))
            ok = download_thumbnail(url, target)
        if ok:
            with dfr._LOCK:
                dfr.TOTALS.grand.images_done += 1; folder_ctrs.images_done += 1
            return True
        with dfr._LOCK:
            dfr.TOTALS.grand.images_failed += 1; folder_ctrs.images_failed += 1
        try:
            with dfr._LOCK:
                dfr.FAILED_ITEMS.append({
                    "id": fid, "name": name, "kind": "image", "__root_name": counters_key,
                    "__folder_out": out_subdir, "target": target
                })
        except Exception:
            pass
        return False

    elif media_kind == "video":
        base, ext = os.path.splitext(name)
        if not ext:
            ext = ".mp4"
        target = os.path.join(out_subdir, f"{base}__{fid}{ext}")
        if not dfr.OVERWRITE and os.path.exists(target):
            logging.info(dfr.L(f"= exists (video): {target}", f"= sudah ada (video): {target}"))
            with dfr._LOCK:
                dfr.TOTALS.grand.videos_skipped += 1; folder_ctrs.videos_skipped += 1
            return True
        if not dfr.DOWNLOAD_VIDEOS:
            logging.info(dfr.L("Skipping video; option disabled.", "Lewati video (opsi nonaktif)."))
            with dfr._LOCK:
                dfr.TOTALS.grand.videos_skipped += 1; folder_ctrs.videos_skipped += 1
            return False
        logging.info(dfr.L(f"Downloading video -> {target}", f"Mengunduh video -> {target}"))
        ok = download_video_resumable(service, creds, fid, target) if dfr.ROBUST_RESUME else _download_video_simple(service, fid, target)  # type: ignore[name-defined]
        if ok:
            with dfr._LOCK:
                dfr.TOTALS.grand.videos_done += 1; folder_ctrs.videos_done += 1
            return True
        with dfr._LOCK:
            dfr.TOTALS.grand.videos_failed += 1; folder_ctrs.videos_failed += 1
        try:
            with dfr._LOCK:
                dfr.FAILED_ITEMS.append({
                    "id": fid, "name": name, "kind": "video", "__root_name": counters_key,
                    "__folder_out": out_subdir, "target": target
                })
        except Exception:
            pass
        return False

    elif media_kind == "data":
        base, ext = os.path.splitext(name)
        if not ext:
            if "pdf" in (mime or "").lower():
                ext = ".pdf"
            elif "text" in (mime or "").lower():
                ext = ".txt"
            elif file_ext:
                ext = f".{file_ext}"
            else:
                ext = ".dat"
        target = os.path.join(out_subdir, f"{base}__{fid}{ext}")
        if not dfr.OVERWRITE and os.path.exists(target):
            logging.info(dfr.L(f"= exists (data): {target}", f"= sudah ada (data): {target}"))
            with dfr._LOCK:
                dfr.TOTALS.grand.data_skipped += 1; folder_ctrs.data_skipped += 1
            return True
        logging.info(dfr.L(f"Downloading data file -> {target}", f"Mengunduh file data -> {target}"))
        ok = download_file_resumable(service, creds, fid, target, label=dfr.L("Data", "Data"))
        if ok:
            with dfr._LOCK:
                dfr.TOTALS.grand.data_done += 1; folder_ctrs.data_done += 1
            return True
        with dfr._LOCK:
            dfr.TOTALS.grand.data_failed += 1; folder_ctrs.data_failed += 1
        try:
            with dfr._LOCK:
                dfr.FAILED_ITEMS.append({
                    "id": fid, "name": name, "kind": "data", "__root_name": counters_key,
                    "__folder_out": out_subdir, "target": target
                })
        except Exception:
            pass
        return False

    else:
        dfr.logging.debug(dfr.L(f"- skip unclassified: {name} [{mime}]", f"- lewati (tidak terklasifikasi): {name} [{mime}]"))
        return False


def print_folder_summary(root_name: str, link_images: int, link_images_existing: int, link_videos: int, link_videos_existing: int):
    logging.info(dfr.L(
        f"[Pre-Scan Folder] {root_name} | images total={link_images} (have {link_images_existing}) | "
        f"videos total={link_videos} (have {link_videos_existing})",
        f"[Pra-Pindai Folder] {root_name} | total gambar={link_images} (sudah {link_images_existing}) | "
        f"total video={link_videos} (sudah {link_videos_existing})"
    ))


def print_grand_summary():
    g = dfr.TOTALS.grand
    logging.info(dfr.L(
        f"[Grand Summary] elapsed={dfr.elapsed()} | total scanned={g.scanned} | "
        f"images: done={g.images_done} skip={g.images_skipped} fail={g.images_failed} | "
        f"videos: done={g.videos_done} skip={g.videos_skipped} fail={g.videos_failed} | "
        f"bytes written={human_bytes(g.bytes_written)}",
        f"[Ringkasan Total] durasi={dfr.elapsed()} | total dipindai={g.scanned} | "
        f"gambar: selesai={g.images_done} lewati={g.images_skipped} gagal={g.images_failed} | "
        f"video: selesai={g.videos_done} lewati={g.videos_skipped} gagal={g.videos_failed} | "
        f"bytes ditulis={human_bytes(g.bytes_written)}"
    ))


def print_progress():
    total_images = dfr.EXPECTED_IMAGES; total_videos = dfr.EXPECTED_VIDEOS; total_data = dfr.EXPECTED_DATA
    done_images = dfr.ALREADY_HAVE_IMAGES + dfr.TOTALS.grand.images_done
    done_videos = dfr.ALREADY_HAVE_VIDEOS + dfr.TOTALS.grand.videos_done
    done_data = dfr.ALREADY_HAVE_DATA + dfr.TOTALS.grand.data_done
    remaining_images = max(0, total_images - done_images)
    remaining_videos = max(0, total_videos - done_videos)
    remaining_data = max(0, total_data - done_data)
    if total_data > 0:
        logging.info(dfr.L(
            f"[Progress] images {done_images}/{total_images} (left {remaining_images}) | "
            f"videos {done_videos}/{total_videos} (left {remaining_videos}) | "
            f"data {done_data}/{total_data} (left {remaining_data})",
            f"[Progress] gambar {done_images}/{total_images} (sisa {remaining_images}) | "
            f"video {done_videos}/{total_videos} (sisa {remaining_videos}) | "
            f"data {done_data}/{total_data} (sisa {remaining_data})"
        ))
    else:
        logging.info(dfr.L(
            f"[Progress] images {done_images}/{total_images} (left {remaining_images}) | "
            f"videos {done_videos}/{total_videos} (left {remaining_videos})",
            f"[Progress] gambar {done_images}/{total_images} (sisa {remaining_images}) | "
            f"video {done_videos}/{total_videos} (sisa {remaining_videos})"
        ))
