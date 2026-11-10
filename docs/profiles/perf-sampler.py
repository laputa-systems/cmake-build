import ctypes
import fcntl
import mmap
import os
import struct
import sys
import time
from pathlib import Path


class Event(ctypes.Structure):
    _fields_ = [('type', ctypes.c_uint32), ('size', ctypes.c_uint32), ('config', ctypes.c_uint64),
                ('period', ctypes.c_uint64), ('sample_type', ctypes.c_uint64), ('read_format', ctypes.c_uint64),
                ('flags', ctypes.c_uint64), ('wakeup_events', ctypes.c_uint32), ('bp_type', ctypes.c_uint32),
                ('remaining', ctypes.c_uint8 * 64)]


if os.uname().machine != 'x86_64':
    raise SystemExit('this study requires native x86-64')
pid = int(sys.argv[1])
seconds = float(sys.argv[2])
output = Path(sys.argv[3])
maps = Path(f'/proc/{pid}/maps').read_text()
event = Event()
event.type = 1
event.size = ctypes.sizeof(event)
event.config = 0
event.period = 1_000_000
event.sample_type = 3
event.flags = 1 | (1 << 5) | (1 << 6)
event.wakeup_events = 1
libc = ctypes.CDLL(None, use_errno=True)
fd = libc.syscall(298, ctypes.byref(event), pid, -1, -1, 0)
if fd < 0:
    error = ctypes.get_errno()
    raise OSError(error, os.strerror(error))
page = os.sysconf('SC_PAGE_SIZE')
ring = mmap.mmap(fd, page * 65, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)
data_offset, data_size = struct.unpack_from('QQ', ring, 1040)
if data_offset != page or data_size != page * 64:
    raise RuntimeError('unexpected perf event ring layout')
tail = struct.unpack_from('Q', ring, 1032)[0]
samples = []
lost = 0


def take(start: int, size: int) -> bytes:
    offset = start % data_size
    first = min(size, data_size - offset)
    return ring[data_offset + offset:data_offset + offset + first] + ring[data_offset:data_offset + size - first]


fcntl.ioctl(fd, 0x2403, 0)
fcntl.ioctl(fd, 0x2400, 0)
deadline = time.monotonic() + seconds
while True:
    head = struct.unpack_from('Q', ring, 1024)[0]
    if head - tail > data_size:
        raise RuntimeError('perf event ring overflowed')
    while tail < head:
        record_type, _, size = struct.unpack('IHH', take(tail, 8))
        if size < 8 or size > data_size or tail + size > head:
            raise RuntimeError('invalid perf event record')
        record = take(tail, size)
        if record_type == 9:
            ip, sample_pid, sample_tid = struct.unpack_from('QII', record, 8)
            samples.append((ip, sample_pid, sample_tid))
        elif record_type == 2:
            lost += struct.unpack_from('Q', record, 16)[0]
        tail += size
    struct.pack_into('Q', ring, 1032, tail)
    if time.monotonic() >= deadline or not Path(f'/proc/{pid}').exists():
        break
    time.sleep(0.05)
fcntl.ioctl(fd, 0x2401, 0)
ring.close()
os.close(fd)
output.with_suffix('.maps').write_text(maps)
output.write_text(''.join(f'{ip:x}\t{sample_pid}\t{sample_tid}\n' for ip, sample_pid, sample_tid in samples))
print(f'samples={len(samples)} lost={lost} output={output}')
if not samples or lost:
    raise SystemExit('perf event sampling produced incomplete data')
