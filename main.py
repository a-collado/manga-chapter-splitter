import gc
import os
import re
import shutil
import timeit
import zipfile
from argparse import ArgumentParser

from PIL import Image
from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion, RapidOCR

VOLUME_RE = re.compile(r".*\.cb[zr]")

ocr = RapidOCR()


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "-i",
        "--input",
        help="Input manga directory",
        metavar="path",
        required=True,
        type=os.path.abspath,
    )
    parser.add_argument("-c", "--compress", help="Compress manga", action="store_true")
    parser.add_argument(
        "-r",
        "--regex",
        help="Specify alternative regex pattern for chapter number",
        metavar="regex",
        required=False,
    )
    parser.add_argument("-d", "--debug", help="Debug OCR", action="store_true")

    args = parser.parse_args()
    manga_dir = args.input
    cbz = args.compress
    deb = args.debug

    # Compile regex once
    if args.regex:
        chapter_re = re.compile(args.regex, re.IGNORECASE)
    else:
        chapter_re = re.compile(
            r"C.{0,5}p.{0,5}t.{0,5}l[oOóò0]{0,5}\s{0,6}(\d{2,3}|\d{1,3})",
            re.IGNORECASE,
            # r"Cap.\s{0,6}(\d{1,3})", re.IGNORECASE,
        )  # Pre-compile default regex

    manga_list = [x for x in os.listdir(manga_dir) if VOLUME_RE.match(x)]
    for manga in manga_list:
        split_manga(manga, manga_dir, cbz, chapter_re, deb)


def split_manga(manga, manga_dir, cbz: bool, chapter_re, deb: bool):
    zip_path = os.path.join(manga_dir, manga)
    extract_dir = os.path.join(manga_dir, manga[:-4])

    extract_zip(zip_path, extract_dir)

    files, _ = folders_split(extract_dir)

    new_chapters = read_pages(files, extract_dir, chapter_re, deb)

    if cbz:
        for ch in new_chapters:
            compress_chapter(ch, extract_dir, manga_dir)

        shutil.rmtree(extract_dir)

    return extract_dir


def extract_zip(zip_path, extract_dir):
    """Synchronous function to extract ZIP."""
    with zipfile.ZipFile(zip_path, "r") as manga_zip:
        os.makedirs(extract_dir, exist_ok=True)
        manga_zip.extractall(extract_dir)


def folders_split(directory):
    """Synchronously split into files and folders."""
    files = []
    folders = []
    for dirpath, dirnames, filenames in os.walk(directory):
        for dirname in sorted(dirnames):
            folders.append(os.path.join(dirpath, dirname))
        for filename in sorted(filenames):
            files.append(os.path.join(dirpath, filename))
    return files, folders


def read_pages(files, extract_dir, chapter_re, deb: bool):
    chapters = {}
    chapter_num = "1"
    first = False
    vol_one = False
    for page in files:
        if page.lower().endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif")):

            # print(page)
            img = Image.open(page)
            width, height = img.size

            if width < 200:
                continue

            result = ocr(page)
            text = ""
            if result:
                if hasattr(result.txts, "__iter__"):
                    text = text.join(result.txts)
                else:
                    text = result.txts
                # print(text)

            match = chapter_re.search(text)

            if deb:
                print(text)

            if match:
                # print(text)
                chapter_num = match.group(1)
                # print(chapter_num)
                if chapter_num == "1":
                    vol_one = True
                if not vol_one:
                    first = True

            chapter_dir = os.path.join(extract_dir, chapter_num)

            if first and not vol_one and os.path.exists(os.path.join(extract_dir, "1")):
                os.rename(os.path.join(extract_dir, "1"), chapter_dir)

            # Create dir if needed
            if not os.path.exists(chapter_dir):
                os.makedirs(chapter_dir, exist_ok=True)

            # Move file
            dest = os.path.join(chapter_dir, os.path.basename(page))
            shutil.move(page, dest)
            if first or vol_one:
                chapters.setdefault(chapter_num, []).append(page)
        gc.collect()
    return chapters


def compress_chapter(chapter_num, extract_dir, manga_dir):
    """Synchronous compression."""
    chapter_path = os.path.join(extract_dir, chapter_num)
    output_dir = os.path.join(manga_dir, os.path.basename(manga_dir))
    os.makedirs(output_dir, exist_ok=True)
    cbz_path = os.path.join(
        output_dir, f"{os.path.basename(extract_dir)} ch. {chapter_num}.cbz"
    )
    with zipfile.ZipFile(cbz_path, "w") as zf:
        for file in os.listdir(chapter_path):
            file_path = os.path.join(chapter_path, file)
            zf.write(file_path, arcname=file, compress_type=zipfile.ZIP_DEFLATED)


if __name__ == "__main__":
    time_taken = timeit.timeit(lambda: main(), number=1)
