# Minimal persistent event log on /flash for post-mortem debugging.
#
# Flash-friendliness matters more than completeness here:
# - The XBee3 file system cannot modify a file in place ('w' raises EEXIST,
#   there is no append), so every event rewrites the whole file via
#   remove + create. Log rare events only (boots, failures, recoveries),
#   never per-cycle data.
# - Deleting a file only reclaims its space when the file is at the end of
#   the file system. A remove + create cycle normally reuses the same tail
#   space, but if another file (e.g. config.json) was created in between,
#   each cycle leaves a dead hole that only os.format() recovers. The
#   free-space guard below makes sure logging gives up long before that
#   could fill the file system.

import os

try:
    from time import time as uptime  # seconds since boot (no RTC on XBee3)
    uptime()
except Exception:
    from time import ticks_ms

    def uptime():
        return ticks_ms() // 1000

PATH = '/flash/log.txt'
# The file system is ~382 KB (firmware 1014, per ATFS INFO), so a 4 KB log
# is ~1% of it. Each rewrite briefly holds the log twice in RAM, so the cap
# also has to stay small relative to the MicroPython heap.
_MAX_BYTES = 4096   # oldest lines are dropped beyond this
_MAX_WRITES = 20    # per boot, bounds flash wear if an event fires in a loop
_MIN_FREE = 16384   # stop writing when flash free space drops below this

_writes = 0
_busy = False

def _free():
    try:
        st = os.statvfs('/flash')
        return st[1] * st[3]  # f_frsize * f_bfree
    except Exception:
        return None  # statvfs unavailable - fall back to the write caps only

def log(msg):
    # Must never raise: callers include the radio rx callback, where an
    # escaped exception would kill the callback for good.
    global _writes, _busy
    try:
        line = 'up={} {}'.format(uptime(), msg)
        print('LOG ' + line)
        if _writes >= _MAX_WRITES:
            return
        if _busy:
            # Re-entered from the rx callback while a write below is in
            # progress; skip the file write rather than lose the history
            # that the interrupted remove + create cycle is carrying.
            return
        free = _free()
        if free is not None and free < _MIN_FREE:
            print('log skip: only {} bytes free'.format(free))
            return
        _busy = True
        _writes += 1
        try:
            try:
                with open(PATH) as f:
                    data = f.read()
            except OSError:
                data = ''
            data += line + '\n'
            if len(data) > _MAX_BYTES:
                cut = data.find('\n', len(data) - _MAX_BYTES) + 1
                # cut == len(data) when one giant line fills the whole
                # window; keep its tail instead of emptying the log.
                data = data[cut:] if cut < len(data) else data[-_MAX_BYTES:]
            try:
                os.remove(PATH)
            except OSError:
                pass
            with open(PATH, 'w') as f:
                f.write(data)
        finally:
            _busy = False
    except Exception as e:
        try:
            print('log write fail: {}'.format(e))
        except Exception:
            pass

def log_exception(prefix, e):
    # Like log(), must never raise.
    try:
        import io
        import sys
        buf = io.StringIO()
        sys.print_exception(e, buf)
        log('{}: {}'.format(prefix, buf.getvalue().strip()))
    except Exception:
        try:
            log('{}: {}'.format(prefix, e))
        except Exception:
            pass

def dump():
    try:
        with open(PATH) as f:
            print(f.read(), end='')
    except OSError:
        print('(no log)')
