#!/usr/bin/env python

import csv
import hashlib
import argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime
from collections.abc import Iterable

import pytz
from tqdm import tqdm
from PIL import Image
from PIL import ExifTags
from pillow_heif import register_heif_opener
from pymediainfo import MediaInfo
from tabulate import tabulate
from dateutil.parser import isoparse


register_heif_opener()


class PhotoOrganizer:

    pillow_exts = ('.jpg', '.jpeg', '.heic')
    mediainfo_exts = ('.mov', '.mp4', '.m4v')
    screenshot_exts = ('.png', '.gif', '.bmp', '.webp')
    allowed_exts = pillow_exts + mediainfo_exts + screenshot_exts
    timezone = pytz.timezone('America/Vancouver')

    def __init__(self, src_dir: Path, dst_dir: Path, mtime_only: bool = False) -> None:
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.rename_tasks: list[tuple[Path, Path, str]] = []
        self.skipped_items: list[tuple[Path, str]] = []
        self.mtime_only = mtime_only

    def get_time_taken(self, photo: Path) -> tuple[datetime, str]:
        if self.mtime_only:
            return self.get_time_from_file(photo)

        if photo.suffix.lower() in self.pillow_exts:
            dt, dt_source = self.get_time_from_pillow(photo)
        elif photo.suffix.lower() in self.mediainfo_exts:
            dt, dt_source = self.get_time_from_mediainfo(photo)
        elif self.is_screenshot(photo):
            dt, dt_source = self.get_time_from_file(photo)
        else:
            raise RuntimeError(f'Unexpected extension: {photo}')

        assert dt.tzinfo is not None, 'timezone does not exist'
        assert str(dt.tzinfo) == str(self.timezone), 'timezone does not match'
        return dt, dt_source

    def parse_timestamp(self, ts: int | float) -> datetime:
        '''Parse Unix timestamp into an aware datetime'''
        return datetime.fromtimestamp(ts, tz=self.timezone)

    def get_time_from_file(self, photo: Path) -> tuple[datetime, str]:
        '''Return file mtime as an aware datetime'''
        return self.parse_timestamp(photo.stat().st_mtime), 'mtime'

    def is_screenshot(self, photo: Path) -> bool:
        return photo.suffix.lower() in self.screenshot_exts or photo.parent.name == 'Screenshots'

    def get_time_from_pillow(self, photo: Path) -> tuple[datetime, str]:
        image = Image.open(photo)
        _exif1 = image.getexif()
        _exif2 = _exif1.get_ifd(0x8769)
        _exif = dict(_exif1) | _exif2
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in _exif.items()
            if k in ExifTags.TAGS and type(v) is not bytes
        }

        # If photo does not have EXIF at all, use mtime
        if not exif:
            return self.get_time_from_file(photo)

        # Extract dt from EXIF
        _exif_dt = exif.get('DateTimeOriginal') or exif.get('DateTimeDigitized') or exif.get('DateTime')
        if _exif_dt is None:
            #tqdm.write(f'{photo}: Cannot extract datetime from EXIF: {exif}')
            return self.get_time_from_file(photo)
        else:
            # Some software appends non-ASCII bytes like '下午'
            # 'DateTime': '2018:12:25 18:19:37ä¸\x8bå\x8d\x88'
            _exif_dt = _exif_dt[:19]
            exif_dt = self.timezone.localize(datetime.strptime(_exif_dt, '%Y:%m:%d %H:%M:%S'))
            return exif_dt, 'EXIF'

    def get_time_from_mediainfo(self, photo: Path) -> tuple[datetime, str]:
        mediainfo = MediaInfo.parse(photo)
        general_track = mediainfo.general_tracks[0]  # type: ignore
        if dt_str := general_track.comapplequicktimecreationdate:
            # com.apple.quicktime.creationdate         : 2018-10-08T21:24:34-0700
            dt = isoparse(dt_str)
        elif dt_str := general_track.encoded_date or general_track.tagged_date:
            assert dt_str.startswith('UTC') or dt_str.endswith('UTC'), 'encoded_date/tagged_date should have UTC marking'
            dt_str = dt_str.removeprefix('UTC').removesuffix('UTC').strip()
            dt = isoparse(dt_str)
        else:
            tqdm.write(f'{photo}: Cannot extract datetime from MediaInfo')
            return self.get_time_from_file(photo)
        # If dt is aware, convert to local dt
        if dt.tzinfo:
            local_dt = dt.astimezone(self.timezone)
        # If dt is naive, assume it's UTC
        else:
            local_dt = pytz.utc.localize(dt).astimezone(self.timezone)
        return local_dt, 'MediaInfo'

    def start(self):
        if self.src_dir.is_file():
            photo_paths = [self.src_dir]
        else:
            photo_paths = self.src_dir.rglob('*.*')

        self._prepare_rename_tasks(photo_paths)
        self.rename_tasks = sorted(self.rename_tasks)
        self.skipped_items = sorted(self.skipped_items)
        print(f'Collected {len(self.rename_tasks)} rename tasks.')
        print(f'Collected {len(self.skipped_items)} skipped items.')
        self._confirm_rename()

    def _get_rename_task(self, photo: Path) -> tuple[Path, Path, str] | None:
        dt, dt_source = self.get_time_taken(photo)

        # Compute filename
        if self.is_screenshot(photo):
            prefix = 'Screenshot_'
        else:
            prefix = 'IMG_'
        timestamp = dt.strftime('%Y%m%d_%H%M%S')
        # Generate a Git-like hash (first 7 chars of SHA-1)
        with open(photo, 'rb') as f:
            hash_obj = hashlib.sha1()
            while chunk := f.read(1024 * 1024 * 10):  # 10 MiB
                hash_obj.update(chunk)
        h = hash_obj.hexdigest()[:7]
        fn = f'{prefix}{timestamp}_{h}{photo.suffix.lower()}'

        full_path = self.dst_dir / str(dt.year) / fn
        if full_path.exists():
            # Ignore already renamed files (allow idempotent operations)
            if full_path.samefile(photo):
                return None
            msg = f'Destination already exists: {full_path}'
            raise FileExistsError(msg)

        rename_task = (photo, full_path, dt_source)
        return rename_task

    def _prepare_rename_tasks(self, photo_paths: Iterable[Path]) -> None:
        # Prime the generator so that we can see progress in tqdm
        photos = sorted(p for p in photo_paths if p.suffix.lower() in self.allowed_exts)

        tpe = concurrent.futures.ThreadPoolExecutor()
        futures_map = {
            tpe.submit(self._get_rename_task, photo): photo
            for photo in photos
        }
        pending = set(futures_map.keys())
        pbar = tqdm(total=len(futures_map))
        try:
            while pending:
                # Wait for a few to complete
                done_now, pending = concurrent.futures.wait(pending, timeout=0.1, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done_now:
                    try:
                        rename_task = future.result()
                    except Exception as e:
                        photo = futures_map[future]
                        msg = f'Error @ {photo}: {e!r}'
                        tqdm.write(msg)
                        self.skipped_items.append((photo, msg))
                    else:
                        if rename_task:
                            self.rename_tasks.append(rename_task)
                    pbar.update(1)
        except KeyboardInterrupt:
            tqdm.write('KeyboardInterrupt')
            tpe.shutdown(wait=False, cancel_futures=True)
        finally:
            pbar.close()

    def _confirm_rename(self) -> None:
        print('Rename the files, preview the tasks, save the tasks in CSV, or abort?')
        try:
            resp = input('(R)ename/(p)review/(s)ave/(a)bort? ').lower()
        except KeyboardInterrupt:
            return

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
            src, dst, _ = task
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)

    def _preview_tasks(self) -> None:
        print(f'Rename ({len(self.rename_tasks)}):')
        print(tabulate(self.rename_tasks))
        print(f'Skip ({len(self.skipped_items)}):')
        print(tabulate(self.skipped_items))

    def _save_tasks(self) -> None:
        with open('rename_tasks.csv', 'w', encoding='utf-8') as f:
            rename_tasks_csv = csv.writer(f)
            rename_tasks_csv.writerow(['src', 'dst', 'dt_source'])
            rename_tasks_csv.writerows(self.rename_tasks)
        with open('skipped_items.csv', 'w', encoding='utf-8') as f:
            skipped_items_csv = csv.writer(f)
            skipped_items_csv.writerow(['item', 'message'])
            skipped_items_csv.writerows(self.skipped_items)
        print('Preview of operations written to `rename_tasks.csv` and `skipped_items.csv`')


def main():

    ap = argparse.ArgumentParser()
    ap.add_argument('src_dir', type=Path)
    ap.add_argument('-d', dest='dst_dir', type=Path, default='.')
    ap.add_argument('--mtime-only', action='store_true')
    args = ap.parse_args()

    org = PhotoOrganizer(args.src_dir, args.dst_dir, args.mtime_only)
    org.start()


if __name__ == '__main__':
    main()
