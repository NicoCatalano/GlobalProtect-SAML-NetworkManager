#!/usr/bin/env python3
"""Convert the staged shared extension to GNOME 42-44's module entry point."""
import json
from pathlib import Path
import re
import sys


def convert(directory):
    root = Path(directory)
    source = (root / 'extension.js').read_text()
    if 'export default class SsoWindowExtension extends Extension' not in source:
        raise ValueError('Expected the canonical modern extension entry point')
    source = re.sub(r'^import .*;\n', '', source, flags=re.MULTILINE)
    source = source.replace('export default class SsoWindowExtension', 'class SsoWindowExtension', 1)
    prefix = '''const {Gio, GLib, NM} = imports.gi;
const ExtensionUtils = imports.misc.extensionUtils;
const Tracker = ExtensionUtils.getCurrentExtension().imports.tracker.Tracker;
class Extension {
    getSettings() { return ExtensionUtils.getSettings(); }
}
'''
    tracker = (root / 'tracker.js').read_text()
    if 'export class Tracker' not in tracker:
        raise ValueError('Expected the shared tracker module')
    metadata = json.loads((root / 'metadata.json').read_text())
    metadata['shell-version'] = ['42', '43', '44']
    (root / 'extension.js').write_text(prefix + source + '\nfunction init() { return new SsoWindowExtension(); }\n')
    (root / 'tracker.js').write_text(tracker.replace('export class Tracker', 'var Tracker = class Tracker', 1))
    (root / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')


if __name__ == '__main__':
    convert(sys.argv[1])
