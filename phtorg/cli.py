from pathlib import Path

import click
from phtorg.organizer import PhotoOrganizer
from phtorg.logging import setup_logging


@click.group()
def cli():
    setup_logging()


@cli.command()
@click.argument('src_dir', type=click.Path(exists=True, path_type=Path))
@click.option('-d', '--dst-dir', type=click.Path(path_type=Path), default=Path('.'), help='Destination directory')
@click.option('--allow-mtime', is_flag=True, show_default=True, help='Allow using mtime for EXIF/MediaInfo files. For other files (PNG/GIF), mtime is always allowed.')
def organize(src_dir: Path, dst_dir: Path, allow_mtime: bool):
    '''Organize photos/videos into folders'''
    org = PhotoOrganizer(src_dir, dst_dir, allow_mtime)
    org.start()


#@cli.command()
#@click.argument('src_dir', type=click.Path(exists=True))
#def dedup(src_dir, dry_run):
#    '''Detect and optionally remove duplicate files'''
#    deduper = PhotoDeduper(Path(src_dir), dry_run)
#    deduper.run()
