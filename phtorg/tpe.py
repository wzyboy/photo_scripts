import concurrent.futures
from collections.abc import Callable
from collections.abc import Iterable
from typing import Any
from typing import TypeVar

from tqdm import tqdm


T = TypeVar('T')
Completed = tuple[T, Any]
Failed = tuple[T, Exception]


def tpe_submit(func: Callable, items: Iterable[T]) -> tuple[list[Completed], list[Failed]]:
    '''Run tasks through TPE with a progress bar.'''
    completed: list[Completed] = []
    failed: list[Failed] = []

    tpe = concurrent.futures.ThreadPoolExecutor()
    futures_map = {
        tpe.submit(func, item): item
        for item in items
    }
    pending = set(futures_map.keys())
    pbar = tqdm(total=len(futures_map))
    try:
        while pending:
            # Wait for a few to complete
            done_now, pending = concurrent.futures.wait(pending, timeout=0.1, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done_now:
                pbar.update(1)
                try:
                    result = future.result()
                except Exception as e:
                    item = futures_map[future]
                    failed.append((item, e))
                    continue
                else:
                    item = futures_map[future]
                    completed.append((item, result))
    except KeyboardInterrupt:
        tqdm.write('KeyboardInterrupt')
        tpe.shutdown(wait=False, cancel_futures=True)
    finally:
        pbar.close()
        return completed, failed
