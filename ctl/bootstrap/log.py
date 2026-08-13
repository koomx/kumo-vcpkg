import os
import sys
import time


def _can_encode(char):
    try:
        char.encode(sys.stdout.encoding)
        return True
    except (UnicodeEncodeError, AttributeError, LookupError):
        return False


def _color(stream):
    if not hasattr(stream, 'isatty') or not stream.isatty():
        return False
    if sys.platform == 'win32':
        return bool(os.environ.get('TERM'))
    return True


_use_color = _color(sys.stdout)

if _can_encode('\u2713'):
    _OK = '\u2713'
    _WARN = '\u26a0'
    _ERR = '\u2717'
else:
    _OK = '+'
    _WARN = '!'
    _ERR = 'x'


def _c(code, text):
    if _use_color:
        return code + text + '\033[0m'
    return text


_B = '\033[1m'
_G = '\033[32m'
_Y = '\033[33m'
_R = '\033[31m'
_C = '\033[36m'


class Logger:
    def __init__(self):
        self._start = time.time()
        self._step = 0
        self._total = 0

    def set_total(self, n):
        self._total = n

    def step(self, title):
        self._step += 1
        self._step_start = time.time()
        tag = _c(_C, '[{}/{}]'.format(self._step, self._total))
        print('')
        print('{} {}...'.format(tag, title), flush=True)

    def detail(self, key, value):
        print('  {}: {}'.format(key, _c(_C if _use_color else '', value)), flush=True)

    def ok(self, msg=''):
        if msg:
            print('  {} {}'.format(_c(_G, _OK), msg), flush=True)
        else:
            print('  {}'.format(_c(_G, _OK)), flush=True)

    def warn(self, msg):
        print('  {} {}'.format(_c(_Y, _WARN), msg), flush=True)

    def err(self, msg):
        print('  {} {}'.format(_c(_R, _ERR), msg), flush=True)

    def done(self):
        elapsed = time.time() - self._step_start
        self.ok('done ({:.1f}s)'.format(elapsed))

    def complete(self):
        elapsed = time.time() - self._start
        print('')
        print('{} {} ({:.1f}s)'.format(
            _c(_G, _OK), _c(_B, 'Bootstrap complete!'), elapsed
        ), flush=True)

    def progress(self, current, total):
        bar_len = 25
        frac = current / total if total > 0 else 0
        filled = int(bar_len * frac)
        bar = '=' * filled + '-' * (bar_len - filled)
        pct = frac * 100
        sys.stdout.write(
            '\r  [{}] {:3.0f}%  {:6.1f} / {:6.1f} MB'.format(
                bar, pct,
                current / 1024 / 1024,
                total / 1024 / 1024
            )
        )
        sys.stdout.flush()
        if current >= total:
            sys.stdout.write('\n')
