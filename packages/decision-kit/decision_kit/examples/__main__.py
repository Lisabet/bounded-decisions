"""Create synthetic local config and cases from installed package resources."""
import argparse
from importlib.resources import files
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    names = ('plusvibe.json', 'cases.json')
    args.directory.mkdir(parents=True, exist_ok=True)
    if any((args.directory / name).exists() for name in names):
        parser.error('starter files already exist; choose a fresh directory')
    for name in names:
        with (args.directory / name).open('xb') as stream:
            stream.write(files('decision_kit.examples').joinpath(name).read_bytes())
    print('Created plusvibe.json and cases.json in the selected directory.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
