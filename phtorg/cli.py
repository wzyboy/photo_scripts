from pathlib import Path

import click
import tzlocal
from tabulate import tabulate
from phtorg.tpe import tpe_submit
from phtorg.logging import setup_logging
from phtorg.organizer import PhotoOrganizer


@click.group()
@click.option('--timezone', default=tzlocal.get_localzone_name(), show_default=True, help='Timezone name (e.g., "UTC", "America/Vancouver")')
@click.pass_context
def cli(ctx, timezone: str):
    setup_logging()
    ctx.ensure_object(dict)
    ctx.obj['timezone'] = timezone


@cli.command()
@click.argument('src_dir', type=click.Path(exists=True, path_type=Path))
@click.option('-d', '--dst-dir', type=click.Path(path_type=Path), default=Path('.'), help='Destination directory')
@click.option('--allow-mtime', is_flag=True, show_default=True, help='Allow using mtime as a fallback if datetime cannot be extracted from EXIF/MediaInfo')
@click.pass_obj
def organize(obj: dict, src_dir: Path, dst_dir: Path, allow_mtime: bool):
    '''Organize photos/videos into folders'''
    org = PhotoOrganizer(src_dir, dst_dir, obj['timezone'])
    org.allow_mtime = allow_mtime
    org.start()


@cli.command()
@click.argument('src_dir', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--datetime-source',
    type=click.Choice(['EXIF', 'MediaInfo', 'mtime'], case_sensitive=False),
    multiple=True,
    help='Filter by datetime_source (can be used multiple times)'
)
@click.option('--only-errors', is_flag=True, default=False)
@click.pass_obj
def analyze(obj: dict, src_dir: Path, datetime_source: tuple[str], only_errors: bool | None):
    '''Analyze photos/videos for datetime'''
    org = PhotoOrganizer(src_dir, Path('.'), obj['timezone'])
    completed, _ = tpe_submit(org.get_info, org.iter_photo(), raise_exception=True)
    infos = (info for _, info in completed)

    # Apply filters
    if datetime_source:
        infos = (i for i in infos if i.datetime_source in datetime_source)
    if only_errors:
        infos = (i for i in infos if i.errors)

    click.echo_via_pager(tabulate(sorted(infos), headers=['path', 'datetime', 'datetime_source', 'errors']))
