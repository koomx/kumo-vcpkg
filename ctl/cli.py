import argparse
import importlib
import sys
from pathlib import Path


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'autocomplete':
        _do_autocomplete()
        return

    parser = argparse.ArgumentParser(
        prog='vcpkgctl',
        description='vcpkg control tool'
    )
    subparsers = parser.add_subparsers(dest='command')

    cmd_dir = Path(__file__).parent / 'commands'
    if not cmd_dir.is_dir():
        print('error: commands directory not found', file=sys.stderr)
        sys.exit(1)

    commands = []
    for f in sorted(cmd_dir.glob('*.py')):
        if f.stem.startswith('_'):
            continue
        mod = importlib.import_module('commands.' + f.stem)
        if not hasattr(mod, 'setup'):
            continue
        name = getattr(mod, 'COMMAND_NAME', f.stem)
        doc = (mod.__doc__ or '').strip()
        help_text = doc.split('\n')[0] if doc else ''
        sp = subparsers.add_parser(name, help=help_text, description=doc)
        mod.setup(sp)
        commands.append(name)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


def _do_autocomplete():
    words = sys.argv[2:]
    sep = '--'
    if sep in words:
        idx = words.index(sep)
        partial = words[idx + 1] if idx + 1 < len(words) else ''
    else:
        partial = words[-1] if words else ''

    cmd_dir = Path(__file__).parent / 'commands'
    names = sorted(
        getattr(importlib.import_module('commands.' + f.stem), 'COMMAND_NAME', f.stem)
        for f in cmd_dir.glob('*.py')
        if not f.stem.startswith('_')
    )

    for n in names:
        if n.startswith(partial):
            print(n)
