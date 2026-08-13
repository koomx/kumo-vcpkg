"""Initialize vcpkg environment: download vcpkg binary, setup shell config"""
import sys

from bootstrap import run_bootstrap


def setup(subparser):
    subparser.add_argument(
        '--musl', action='store_true',
        help='force download the musl-linked binary (Linux only)'
    )
    subparser.add_argument(
        '--disable-metrics', action='store_true',
        help='disable telemetry for this vcpkg root'
    )
    subparser.set_defaults(func=run)


def run(args):
    try:
        run_bootstrap({
            'musl': args.musl,
            'disable_metrics': args.disable_metrics,
        })
    except Exception as e:
        print('error: {}'.format(e), file=sys.stderr, flush=True)
        sys.exit(1)
