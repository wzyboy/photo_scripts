from pathlib import Path

import click
from phtorg.organizer import PhotoOrganizer
from phtorg.logging import setup_logging


@click.group()
def cli():
    setup_logging()


@cli.command()
@click.argument('src_dir', type=click.Path(exists=True, path_type=Path))
@click.option('-d', '--dst-dir', type=click.Path(path_type=Path), default=Path.cwd(), help='Destination directory')
@click.option('--mtime-only', is_flag=True, help='Use file mtime instead of metadata')
def organize(src_dir: Path, dst_dir: Path, mtime_only: bool):
    '''Organize photos/videos into folders'''
    org = PhotoOrganizer(src_dir, dst_dir, mtime_only)
    org.start()


#@cli.command()
#@click.argument('src_dir', type=click.Path(exists=True))
#def dedup(src_dir, dry_run):
#    '''Detect and optionally remove duplicate files'''
#    deduper = PhotoDeduper(Path(src_dir), dry_run)
#    deduper.run()
