from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from . import package
from buildsys.inputs import safe_extract, tree_digest


class GenerationError(Exception):
    pass


def qualify(store: Path, archive: Path, expected_digest: str, run: Callable[[Path], dict]) -> Path:
    store.mkdir(parents=True, exist_ok=True)
    with (store / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if package.digest(archive) != expected_digest:
            raise GenerationError('archive digest does not match the candidate')
        with tempfile.TemporaryDirectory(prefix='.candidate-', dir=store) as temporary:
            candidate = Path(temporary)
            copied = candidate / 'artifact.tar.xz'
            shutil.copyfile(archive, copied)
            if package.digest(copied) != expected_digest:
                raise GenerationError('archive changed while copying')
            try:
                package.inspect(copied)
                tree = safe_extract(copied, candidate / 'tree')
            except Exception as error:
                raise GenerationError(f'invalid candidate: {error}') from error
            before = tree_digest(tree)
            results = run(tree)
            if not isinstance(results, dict) or not results:
                raise GenerationError('qualification produced no results')
            if tree_digest(tree) != before or package.digest(copied) != expected_digest:
                raise GenerationError('qualification changed the candidate')
            (candidate / 'results.json').write_text(json.dumps({'archive_sha256': expected_digest, 'archive_size': copied.stat().st_size, 'qualification': results}, sort_keys=True, indent=2) + '\n')
            final = store / expected_digest
            if final.exists():
                if package.digest(final / 'artifact.tar.xz') != expected_digest or tree_digest(final / 'tree') != before:
                    raise GenerationError('existing generation is inconsistent')
            else:
                os.replace(candidate, final)
            link = store / f'.active-{os.getpid()}'
            try:
                link.symlink_to(final.name + '/tree')
                os.replace(link, store / 'active')
            finally:
                link.unlink(missing_ok=True)
            return final
