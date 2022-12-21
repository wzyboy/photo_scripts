#!/usr/bin/env python

import csv
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from datetime import timedelta
from collections import deque

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

    dt_tolerance = timedelta(days=1)  # timezone
    allowed_exts = ('.jpg', '.heic', '.mov')
    pillow_exts = ('.jpg', '.heic')
    mediainfo_exts = ('.mov')

    def __init__(self, src_dir: Path, dst_dir: Path) -> None:
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.rename_tasks = deque()
        self.skipped_items = deque()

    def get_time_taken(self, photo: Path, verify: bool = True) -> datetime:
        if photo.suffix.lower() in self.pillow_exts:
            dt = self.get_time_taken_pillow(photo)
        elif photo.suffix.lower() in self.mediainfo_exts:
            dt = self.get_time_taken_mediainfo(photo)
        else:
            raise RuntimeError()

        # Verify DateTime does not deviate from mtime too much
        _file_dt = photo.stat().st_mtime
        file_dt = datetime.fromtimestamp(_file_dt)
        if verify and abs(file_dt - dt) > self.dt_tolerance:
            msg = f'EXIF DateTime deviates from file mtime: {dt=} {file_dt=}'
            raise PhotoException(photo, msg) from None

        return dt

    def get_time_taken_pillow(self, photo: Path) -> datetime:
        image = Image.open(photo)
        _exif = image.getexif()
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in _exif.items()
            if k in ExifTags.TAGS and type(v) is not bytes
        }
        try:
            _exit_dt: str = exif['DateTime']
        except KeyError:
            msg = 'Cannot extract EXIF DateTime'
            raise PhotoException(photo, msg) from None
        else:
            exif_dt = datetime.strptime(_exit_dt, '%Y:%m:%d %H:%M:%S')
        return exif_dt

    def get_time_taken_mediainfo(self, photo: Path) -> datetime:
        mediainfo = MediaInfo.parse(photo)
        general_track = mediainfo.general_tracks[0]  # type: ignore
        dt = datetime.strptime(general_track.comapplequicktimecreationdate, '%Y-%m-%dT%H:%M:%S%z')  # type: ignore
        # Make naive
        dt = dt.replace(tzinfo=None)
        return dt

    def start(self):
        # If src_dir is a file, just print the info and exit
        if self.src_dir.is_file():
            print(self.get_time_taken(self.src_dir, verify=False))
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

        for photo in tqdm(self.src_dir.rglob('*.*')):
            if photo.suffix.lower() not in self.allowed_exts:
                continue

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
            prefix = 'IMG_'
            timestamp = dt.strftime('%Y%m%d_%H%M%S')
            # Generate a Git-like hash (first 7 chars of SHA-1)
            sha1 = hashlib.sha256()
            sha1.update(photo.read_bytes())
            h = sha1.hexdigest()[:7]
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
    args = ap.parse_args()

    org = PhotoOrganizer(args.src_dir, args.dst_dir)
    org.start()


if __name__ == '__main__':
    main()
