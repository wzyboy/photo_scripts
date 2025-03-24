import logging
from pathlib import Path

from tqdm import tqdm
from datetime import datetime


class TqdmLoggingHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logging(log_dir: Path = Path.cwd(), prefix: str = 'phtorg') -> Path:
    iso_now = datetime.now().isoformat(timespec='seconds').replace(':', '-')
    log_filename = f'{prefix}.{iso_now}.log'
    log_path = log_dir / log_filename

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    file_handler = logging.FileHandler(log_path, encoding='utf-8', delay=True)
    file_handler.setFormatter(formatter)

    console_handler = TqdmLoggingHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARN)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return log_path
