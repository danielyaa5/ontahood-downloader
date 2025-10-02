"""
Internationalization support for the GUI application.
Provides bilingual English/Indonesian interface.
"""

# Internationalization dictionary
I18N = {
    "en": {
        "app_title": "ontahood-downloader",
        "intro": (
            "Paste Google Drive folder URLs below. Choose ORIGINAL to fetch full-size images, "
            "or a thumbnail width (up to 6000 px) for previews. Each URL is saved under its own parent folder."
        ),
        "urls_label": "Google Drive folder URLs (one per line):",
        "output_label": "Output folder:",
        "choose": "Choose…",
        "mode_label": "Image mode (thumbnail width / ORIGINAL):",
        "mode_hint": "ORIGINAL = full-size download; XXXpx = reduced image size (MUCH smaller file size).",
        "videos_check": "Download videos (full size)",
        "btn_start": "Start",
        "log": "Log:",
        "images": "Images:",
        "videos": "Videos:",
        "data": "Data:",
        "concurrency_label": "Parallel downloads (concurrency):",
        "concurrency_hint": "How many images to fetch at once. 3–6 recommended; higher may trigger API rate limiting.",
        "missing_urls_msg": "Paste at least one folder URL.",
        "missing_out_title": "Missing output folder",
        "missing_out_msg": "Choose an output folder.",
        "invalid_size_title": "Invalid size",
        "invalid_size_msg": "Pick 100–6000 or ORIGINAL.",
        "progress_left": "left",
        "log_img_mode_original": "[GUI] Image mode: ORIGINAL (full size)",
        "log_img_mode_thumb": "[GUI] Image mode: THUMBNAIL {w}px",
        "log_vids": "[GUI] Download videos: {state}",
        "log_vids_on": "ENABLED",
        "log_vids_off": "DISABLED",
        "log_processing": "[GUI] Processing {n} URL(s)",
        "log_creds_found": "[GUI] credentials.json found: {path}",
        "log_creds_missing": "[GUI] credentials.json not found — sign-in will fail until included.",
        "done": "[GUI] Done.",
        "fatal": "[GUI] Fatal error:",
        "language": "Language / Bahasa",
        "lang_en": "English",
        "lang_id": "Bahasa Indonesia",

        # Pre-scan dialog
        "prescan_title": "Pre-Scan Preview",
        "prescan_desc": "Review expected downloads per link, then click Start to begin.",
        "prescan_col_root": "Folder",
        "prescan_col_images": "Images",
        "prescan_col_videos": "Videos",
        "prescan_col_data": "Data",
        "prescan_totals": "Totals",
        "prescan_bytes_total": "Estimated bytes",
        "prescan_btn_start": "Start Download",
        "prescan_btn_cancel": "Cancel",
        "prescan_have_fmt": "have {n}",
        "prescan_none": "Nothing to download.",
        "prescan_loading": "Scanning folders",
        "prescan_scanning": "Scanning in progress...",

        # Converter section
        "conv_title": "🔁 Convert Thumbnails to Original Images",
        "conv_subtitle": (
            "Once you finish your downloads, pick the images you want in full size and put them into a folder on your computer. "
            "Then run this. It will add the full-size images to that same folder."
        ),
        "conv_pick_label": "Folder containing chosen thumbnails:",
        "conv_btn_choose": "Choose Folder…",
        "conv_btn_start": "Start Conversion",
        "missing_conv_dir_title": "Missing folder",
        "missing_conv_dir_msg": "Please choose the folder that contains your selected thumbnails.",
        "log_conv_using": "[GUI] Converting thumbnails in: {path}",
        "log_conv_start": "[GUI] Starting original-size fetch for files in this folder…",
    },
    "id": {
        "app_title": "Drive Fetch",
        "intro": (
            "Tempel tautan folder Google Drive di bawah. Pilih ORIGINAL untuk mengunduh gambar ukuran penuh, "
            "atau lebar thumbnail (hingga 6000 px) untuk pratinjau. Setiap URL disimpan pada folder induknya sendiri."
        ),
        "urls_label": "Tautan folder Google Drive (satu per baris):",
        "output_label": "Folder keluaran:",
        "choose": "Pilih…",
        "mode_label": "Mode gambar (lebar thumbnail / ORIGINAL):",
        "mode_hint": "ORIGINAL = unduhan ukuran penuh; angka = thumbnail lokal.",
        "videos_check": "Unduh video (ukuran penuh)",
        "btn_start": "Mulai",
        "log": "Log:",
        "images": "Gambar:",
        "videos": "Video:",
        "data": "Data:",
        "concurrency_label": "Unduhan paralel (konkurensi):",
        "concurrency_hint": "Jumlah gambar yang diambil bersamaan. Disarankan 3–6; lebih tinggi bisa kena batas API.",
        "missing_urls_msg": "Tempel minimal satu tautan folder.",
        "missing_out_title": "Folder keluaran kosong",
        "missing_out_msg": "Pilih folder keluaran.",
        "invalid_size_title": "Ukuran tidak valid",
        "invalid_size_msg": "Pilih 100–6000 atau ORIGINAL.",
        "progress_left": "sisa",
        "log_img_mode_original": "[GUI] Mode gambar: ORIGINAL (ukuran penuh)",
        "log_img_mode_thumb": "[GUI] Mode gambar: THUMBNAIL {w}px",
        "log_vids": "[GUI] Unduh video: {state}",
        "log_vids_on": "DIAKTIFKAN",
        "log_vids_off": "DINONAKTIFKAN",
        "log_processing": "[GUI] Memproses {n} URL",
        "log_creds_found": "[GUI] credentials.json ditemukan: {path}",
        "log_creds_missing": "[GUI] credentials.json tidak ditemukan — login akan gagal sampai disertakan.",
        "done": "[GUI] Selesai.",
        "fatal": "[GUI] Kesalahan fatal:",
        "language": "Bahasa / Language",
        "lang_en": "English",
        "lang_id": "Bahasa Indonesia",

        # Pre-scan dialog
        "prescan_title": "Pra-Pindai",
        "prescan_desc": "Tinjau perkiraan unduhan per tautan, lalu klik Mulai untuk memulai.",
        "prescan_col_root": "Folder",
        "prescan_col_images": "Gambar",
        "prescan_col_videos": "Video",
        "prescan_col_data": "Data",
        "prescan_totals": "Total",
        "prescan_bytes_total": "Perkiraan byte",
        "prescan_btn_start": "Mulai Unduh",
        "prescan_btn_cancel": "Batal",
        "prescan_have_fmt": "sudah {n}",
        "prescan_none": "Tidak ada yang diunduh.",
        "prescan_loading": "Memindai folder",
        "prescan_scanning": "Pemindaian sedang berlangsung...",

        # Converter section
        "conv_title": "🔁 Ubah Thumbnail ke Gambar Asli",
        "conv_subtitle": (
            "Setelah selesai mengunduh, pilih gambar yang Anda inginkan ukuran aslinya dan masukkan ke sebuah folder di komputer. "
            "Lalu jalankan bagian ini. Aplikasi akan menambahkan gambar ukuran penuh ke folder yang sama."
        ),
        "conv_pick_label": "Folder berisi thumbnail pilihan:",
        "conv_btn_choose": "Pilih Folder…",
        "conv_btn_start": "Mulai Ambil Ukuran Asli",
        "missing_conv_dir_title": "Folder belum dipilih",
        "missing_conv_dir_msg": "Silakan pilih folder yang berisi thumbnail pilihan Anda.",
        "log_conv_using": "[GUI] Mengonversi thumbnail di: {path}",
        "log_conv_start": "[GUI] Memulai unduhan gambar ukuran asli untuk file di folder ini…",
    },
}


def T(lang: str, key: str, **kw) -> str:
    """
    Translate a key to the specified language with optional formatting.
    
    Args:
        lang: Language code ('en' or 'id')
        key: Translation key
        **kw: Format arguments for string formatting
        
    Returns:
        Translated and formatted string
    """
    txt = I18N.get(lang, I18N["en"]).get(key, I18N["en"].get(key, key))
    return txt.format(**kw) if kw else txt