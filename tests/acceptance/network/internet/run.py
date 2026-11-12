from __future__ import annotations

import os
import ssl
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

work = Path('/qualification/internet suite')
work.mkdir(parents=True, exist_ok=True)
try:
    with urlopen('https://github.com/', timeout=15) as response:
        response.read(1)
except HTTPError:
    pass
except URLError as error:
    if isinstance(error.reason, ssl.SSLError):
        raise RuntimeError(f'network preflight TLS failed: {error.reason}') from error  # noqa: TRY004 - a TLS failure is a runtime condition, not a type error
    print(f'skipped: no network ({error})')
    raise SystemExit(0)
except ssl.SSLError as error:
    raise RuntimeError(f'network preflight TLS failed: {error}') from error
except (TimeoutError, OSError) as error:
    print(f'skipped: no network ({error})')
    raise SystemExit(0)
env = {key: value for key, value in os.environ.items() if key.lower() not in {'ssl_cert_file', 'ssl_cert_dir', 'https_proxy', 'http_proxy', 'all_proxy', 'no_proxy'}}
env.update({'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work)})
result = subprocess.run(['/qualification/relocated cmake/bin/cmake', '-S', '/suite', '-B', str(work / 'build'),
                         f'-DLOCKED_URL={sys.argv[1]}', f'-DLOCKED_SHA256={sys.argv[2]}'],
                        cwd=work, env=env, text=True, capture_output=True, timeout=600, check=False)
if result.returncode:
    raise RuntimeError(f'locked FetchContent failed ({result.returncode}):\n{result.stdout}\n{result.stderr}')
print('internet FetchContent: locked CMake source downloaded and verified')
