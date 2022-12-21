#!/usr/bin/env python

import csv
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from collections import deque

import pytz
from tqdm import tqdm
from PIL import Image
from PIL import ExifTags
from pillow_heif import register_heif_opener
from pymediainfo import MediaInfo
from tabulate import tabulate


register_heif_opener()


class PhotoException(Exception):
    def __init__(self, photo: Path, message) -> None:
        self.photo = photo
        self.message = message


class PhotoOrganizer:

    pillow_exts = ('.jpg', '.jpeg', '.heic')
    mediainfo_exts = ('.mov', '.mp4')
    screenshot_exts = ('.png', '.gif', '.bmp', '.webp')
    allowed_exts = pillow_exts + mediainfo_exts + screenshot_exts

    #known_software = ('Instagram', 'Google', 'Picasa', 'Adobe Photoshop CC (Windows)', 'Polarr Photo Editor')

    def __init__(self, src_dir: Path, dst_dir: Path, mtime_only: bool = False) -> None:
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.rename_tasks = deque()
        self.skipped_items = deque()
        self.mtime_only = mtime_only

    def get_time_taken(self, photo: Path) -> datetime:
        if self.mtime_only:
            return datetime.fromtimestamp(photo.stat().st_mtime)

        if photo.suffix.lower() in self.pillow_exts:
            dt = self.get_time_taken_pillow(photo)
        elif photo.suffix.lower() in self.mediainfo_exts:
            dt = self.get_time_taken_mediainfo(photo)
        elif (
            photo.suffix.lower() in self.screenshot_exts
            or photo.parent.name == 'Screenshots'
        ):
            dt = datetime.fromtimestamp(photo.stat().st_mtime)
        else:
            raise RuntimeError('Unexpected exts.')

        return dt

    def get_time_taken_pillow(self, photo: Path) -> datetime:
        image = Image.open(photo)
        _exif1 = image.getexif()
        _exif2 = _exif1.get_ifd(0x8769)
        _exif = dict(_exif1) | _exif2
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in _exif.items()
            if k in ExifTags.TAGS and type(v) is not bytes
        }

        # If the photo is edited by some software, trust its mtime
        if exif.get('Software'):
            dt = datetime.fromtimestamp(photo.stat().st_mtime)
            return dt

        # Extract dt from EXIF
        _exif_dt = exif.get('DateTimeOriginal') or exif.get('DateTimeDigitized')
        if _exif_dt is None:
            msg = f'Cannot extract dt from EXIF: {exif}'
            raise PhotoException(photo, msg)
        else:
            exif_dt = datetime.strptime(_exif_dt, '%Y:%m:%d %H:%M:%S')
        return exif_dt

    def get_time_taken_mediainfo(self, photo: Path) -> datetime:
        mediainfo = MediaInfo.parse(photo)
        general_track = mediainfo.general_tracks[0]  # type: ignore
        if general_track.comapplequicktimecreationdate:
            dt = datetime.strptime(general_track.comapplequicktimecreationdate, '%Y-%m-%dT%H:%M:%S%z')
        elif general_track.encoded_date:
            dt = datetime.strptime(general_track.encoded_date, 'UTC %Y-%m-%d %H:%M:%S')
        elif general_track.tagged_date:
            dt = datetime.strptime(general_track.tagged_date, 'UTC %Y-%m-%d %H:%M:%S')
        else:
            raise PhotoException(photo, 'Cannot extract date from mediainfo')
        # Attach to UTC tzinfo to naive dt, and convert to Vancouver time
        if not dt.tzinfo:
            dt = pytz.utc.localize(dt).astimezone(pytz.timezone('America/Vancouver'))
        # Make naive (strip tzinfo)
        dt = dt.replace(tzinfo=None)
        return dt

    def start(self):
        # If src_dir is a file, just print the info and exit
        if self.src_dir.is_file():
            print(self.get_time_taken(self.src_dir))
            return

        try:
            self._prepare_rename_tasks()
        except KeyboardInterrupt:
            print('KeyboardInterrupt')

        self.rename_tasks = sorted(self.rename_tasks)
        self.skipped_items = sorted(self.skipped_items)
        print(f'Collected {len(self.rename_tasks)} rename tasks.')
        print(f'Collected {len(self.skipped_items)} skipped items.')
        self._confirm_rename()

    def _prepare_rename_tasks(self) -> None:

        # Prime the generator so that we can see progress in tqdm
        photos = sorted(self.src_dir.rglob('*.*'))
        for photo in tqdm(photos):
            if photo.suffix.lower() not in self.allowed_exts:
                continue

            is_screenshot = photo.suffix.lower() in self.screenshot_exts

            try:
                dt = self.get_time_taken(photo)
            except PhotoException as e:
                self.skipped_items.append((e.photo, e.message))
                continue
            except Exception as e:
                msg = repr(e)
                self.skipped_items.append((photo, msg))
                continue

            # Compute filename
            prefix = 'IMG_' if not is_screenshot else 'Screenshot_'
            timestamp = dt.strftime('%Y%m%d_%H%M%S')
            # Generate a Git-like hash (first 7 chars of SHA-1)
            with open(photo, 'rb') as f:
                hash_obj = hashlib.sha1()
                while chunk := f.read(1024 * 1024 * 10):  # 10 MiB
                    hash_obj.update(chunk)
            h = hash_obj.hexdigest()[:7]
            fn = f'{prefix}{timestamp}_{h}{photo.suffix.lower()}'
            full_path = self.dst_dir / str(dt.year) / fn
            if not full_path.exists():
                rename_task = (photo, full_path)
            else:
                msg = f'Destination already exists: {full_path}'
                self.skipped_items.append((photo, msg))
                continue

            # Queue rename task
            self.rename_tasks.append(rename_task)

    def _confirm_rename(self) -> None:
        print('Rename the files, preview the tasks, save the tasks in CSV, or abort?')
        resp = input('(R)ename/(p)review/(s)ave/(a)bort? ').lower()

        if resp == 'r':
            self._do_rename()
        elif resp == 'p':
            self._preview_tasks()
            self._confirm_rename()
        elif resp == 's':
            self._save_tasks()
            self._confirm_rename()
        elif resp == 'a':
            return
        else:
            self._confirm_rename()

    def _do_rename(self) -> None:
        for task in tqdm(self.rename_tasks):
            src, dst = task
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)

    def _preview_tasks(self) -> None:
        print(tabulate(self.rename_tasks))
        print(tabulate(self.skipped_items))

    def _save_tasks(self) -> None:
        with open('rename_tasks.csv', 'w') as f:
            rename_tasks_csv = csv.writer(f)
            rename_tasks_csv.writerow(['src', 'dst'])
            rename_tasks_csv.writerows(self.rename_tasks)
        with open('skipped_items.csv', 'w') as f:
            skipped_items_csv = csv.writer(f)
            skipped_items_csv.writerow(['item', 'message'])
            skipped_items_csv.writerows(self.skipped_items)
        print('Preview of operations written to `rename_tasks.csv` and `skipped_items.csv`')


def main():

    ap = argparse.ArgumentParser()
    ap.add_argument('src_dir', type=Path)
    ap.add_argument('dst_dir', type=Path)
    ap.add_argument('--mtime-only', action='store_true')
    args = ap.parse_args()

    org = PhotoOrganizer(args.src_dir, args.dst_dir, args.mtime_only)
    org.start()


if __name__ == '__main__':
    main()
