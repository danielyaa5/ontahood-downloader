# dfr/prescan.py
# Pre-scan tasks generation with per-URL parallelism retained

import os, logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

import drive_fetch_resilient as dfr
from .utils import safe_filename, extract_folder_id, ensure_dir, classify_media
from .listing import list_folder_recursive, get_item
from .process import print_folder_summary


def prescan_tasks(service) -> List[Dict]:
    dfr.LINK_SUMMARIES = []

    urls = list(dfr.FOLDER_URLS)
    tasks_all: List[Dict] = []

    def _scan_one(url: str):
        local_tasks: List[Dict] = []
        if dfr.INTERRUPTED:
            return local_tasks
        try:
            from .auth import get_service_and_creds
            svc, _ = get_service_and_creds(dfr.TOKEN_FILE, dfr.CREDENTIALS_FILE)
            folder_id = extract_folder_id(url)
            from .listing import resolve_folder
            name, ok = resolve_folder(svc, folder_id)
            if not ok:
                return local_tasks
            url_label = safe_filename(url)[:160]
            base_out = os.path.join(dfr.OUTPUT_DIR, url_label); ensure_dir(base_out)
            root_name = name
            folder_out = os.path.join(base_out, root_name); ensure_dir(folder_out)

            logging.info(dfr.L(
                f"# Pre-scan: {root_name} ({url}) -> parent {url_label}",
                f"# Pra-pindai: {root_name} ({url}) -> induk {url_label}"
            ))

            link_images = link_videos = link_data = 0
            link_images_existing = link_videos_existing = link_data_existing = 0
            link_images_bytes = link_videos_bytes = link_data_bytes = 0

            for f in list_folder_recursive(svc, folder_id, rel_path=""):
                if dfr.INTERRUPTED:
                    break
                fid  = f.get("id"); mime = f.get("mimeType",""); fext = f.get("fileExtension")
                kind = classify_media(mime, f.get("name",""), fext)
                if kind in ("image", "video", "data"):
                    f["__root_name"] = root_name
                    f["__folder_out"] = folder_out
                    rel = f.get("__rel_path","")
                    target_dir = os.path.join(folder_out, rel); ensure_dir(target_dir)
                    base, ext = os.path.splitext(f.get("name","file"))

                    if kind == "image":
                        link_images += 1
                        with dfr._LOCK:
                            dfr.EXPECTED_IMAGES += 1
                        if dfr.DOWNLOAD_IMAGES_ORIGINAL:
                            ext_out = ext or (("." + fext) if fext else ".jpg")
                            img_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                        else:
                            img_target = os.path.join(target_dir, f"{base}__{fid}_w{dfr.IMAGE_WIDTH}.jpg")
                        if os.path.exists(img_target):
                            with dfr._LOCK:
                                dfr.ALREADY_HAVE_IMAGES += 1
                            link_images_existing += 1
                        else:
                            local_tasks.append(f)
                            if dfr.DOWNLOAD_IMAGES_ORIGINAL:
                                try:
                                    sz = int(f.get("size") or 0)
                                    if not sz:
                                        meta = get_item(svc, fid, "size")
                                        sz = int(meta.get("size") or 0)
                                    link_images_bytes += sz
                                except Exception:
                                    pass
                            else:
                                try:
                                    from .utils import estimate_thumbnail_size_bytes
                                    link_images_bytes += estimate_thumbnail_size_bytes(int(dfr.IMAGE_WIDTH))
                                except Exception:
                                    link_images_bytes += 100 * 1024
                    elif kind == "data":
                        link_data += 1
                        with dfr._LOCK:
                            dfr.EXPECTED_DATA += 1
                        if not ext:
                            if "pdf" in (mime or "").lower():
                                ext = ".pdf"
                            elif "text" in (mime or "").lower():
                                ext = ".txt"
                            elif fext:
                                ext = f".{fext}"
                            else:
                                ext = ".dat"
                        data_target = os.path.join(target_dir, f"{base}__{fid}{ext}")
                        if os.path.exists(data_target):
                            with dfr._LOCK:
                                dfr.ALREADY_HAVE_DATA += 1
                            link_data_existing += 1
                        else:
                            local_tasks.append(f)
                            try:
                                sz = int(f.get("size") or 0)
                                if not sz:
                                    meta = get_item(svc, fid, "size")
                                    sz = int(meta.get("size") or 0)
                                link_data_bytes += sz
                            except Exception:
                                logging.debug(dfr.L(
                                    f"Could not get size for data file {fid}",
                                    f"Tidak bisa mendapatkan ukuran untuk file data {fid}"
                                ))
                    else:  # video
                        link_videos += 1
                        with dfr._LOCK:
                            dfr.EXPECTED_VIDEOS += 1
                        ext_out = ext or ".mp4"
                        vid_target = os.path.join(target_dir, f"{base}__{fid}{ext_out}")
                        if os.path.exists(vid_target):
                            with dfr._LOCK:
                                dfr.ALREADY_HAVE_VIDEOS += 1
                            link_videos_existing += 1
                        else:
                            if dfr.DOWNLOAD_VIDEOS:
                                local_tasks.append(f)
                                try:
                                    sz = int(f.get("size") or 0)
                                    if not sz:
                                        meta = get_item(svc, fid, "size")
                                        sz = int(meta.get("size") or 0)
                                    link_videos_bytes += sz
                                except Exception:
                                    logging.debug(dfr.L(
                                        f"Could not get size for video {fid}",
                                        f"Tidak bisa mendapatkan ukuran untuk video {fid}"
                                    ))
        except Exception as e:
            logging.error(dfr.L(f"Listing failed for URL {url}: {e}", f"Listing gagal untuk URL {url}: {e}"))
            return local_tasks

        if link_data > 0:
            logging.info(dfr.L(
                f"[Count] {root_name}: images={link_images} (have {link_images_existing}) | "
                f"videos={link_videos} (have {link_videos_existing}) | data={link_data} (have {link_data_existing})",
                f"[Jumlah] {root_name}: gambar={link_images} (sudah {link_images_existing}) | "
                f"video={link_videos} (sudah {link_videos_existing}) | data={link_data} (sudah {link_data_existing})"
            ))
        else:
            logging.info(dfr.L(
                f"[Count] {root_name}: images={link_images} (have {link_images_existing}) | videos={link_videos} (have {link_videos_existing})",
                f"[Jumlah] {root_name}: gambar={link_images} (sudah {link_images_existing}) | video={link_videos} (sudah {link_videos_existing})"
            ))
        with dfr._LOCK:
            dfr.LINK_SUMMARIES.append({
                "root_name": root_name,
                "images": link_images,
                "images_existing": link_images_existing,
                "images_bytes": link_images_bytes,
                "videos": link_videos,
                "videos_existing": link_videos_existing,
                "videos_bytes": link_videos_bytes,
                "data": link_data,
                "data_existing": link_data_existing,
                "data_bytes": link_data_bytes,
                "url": url,
            })
            dfr.EXPECTED_TOTAL_BYTES += (link_images_bytes + link_videos_bytes + link_data_bytes)
        print_folder_summary(root_name, link_images, link_images_existing, link_videos, link_videos_existing)
        return local_tasks

    futures = []
    with ThreadPoolExecutor(max_workers=max(1, int(dfr.CONCURRENCY) if str(dfr.CONCURRENCY).isdigit() else 1)) as ex:
        for url in urls:
            if dfr.INTERRUPTED:
                break
            futures.append(ex.submit(_scan_one, url))
        for fut in as_completed(futures):
            try:
                ts = fut.result()
                if ts:
                    tasks_all.extend(ts)
            except Exception as e:
                logging.error(dfr.L(f"Prescan worker error: {e}", f"Kesalahan prescan: {e}"))

    if dfr.EXPECTED_DATA > 0:
        logging.info(dfr.L(
            f"[Pre-Scan Summary] images={dfr.EXPECTED_IMAGES} (have {dfr.ALREADY_HAVE_IMAGES}) | "
            f"videos={dfr.EXPECTED_VIDEOS} (have {dfr.ALREADY_HAVE_VIDEOS}) | data={dfr.EXPECTED_DATA} (have {dfr.ALREADY_HAVE_DATA})",
            f"[Ringkasan Pra-Pindai] gambar={dfr.EXPECTED_IMAGES} (sudah {dfr.ALREADY_HAVE_IMAGES}) | "
            f"video={dfr.EXPECTED_VIDEOS} (sudah {dfr.ALREADY_HAVE_VIDEOS}) | data={dfr.EXPECTED_DATA} (sudah {dfr.ALREADY_HAVE_DATA})"
        ))
    else:
        logging.info(dfr.L(
            f"[Pre-Scan Summary] images={dfr.EXPECTED_IMAGES} (have {dfr.ALREADY_HAVE_IMAGES}) | videos={dfr.EXPECTED_VIDEOS} (have {dfr.ALREADY_HAVE_VIDEOS})",
            f"[Ringkasan Pra-Pindai] gambar={dfr.EXPECTED_IMAGES} (sudah {dfr.ALREADY_HAVE_IMAGES}) | video={dfr.EXPECTED_VIDEOS} (sudah {dfr.ALREADY_HAVE_VIDEOS})"
        ))
    return tasks_all
