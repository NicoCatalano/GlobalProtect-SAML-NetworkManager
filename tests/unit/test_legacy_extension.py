"""Legacy artifacts reuse the reviewed tracker instead of a second implementation."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('legacy_builder', ROOT / 'scripts/build-legacy-extension.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


@pytest.mark.parametrize('mode', ['valid', 'wrong-entry', 'wrong-tracker'])
def test_legacy_conversion(tmp_path, mode):
    source = ROOT / 'extensions/gpclient-sso@globalprotect-saml-networkmanager'
    shutil.copytree(source, tmp_path, dirs_exist_ok=True)
    if mode == 'wrong-entry':
        (tmp_path / 'extension.js').write_text('arbitrary code\n')
    if mode == 'wrong-tracker':
        (tmp_path / 'tracker.js').write_text('arbitrary code\n')
    before = (tmp_path / 'extension.js').read_bytes()
    if mode != 'valid':
        with pytest.raises(ValueError):
            legacy.convert(tmp_path)
        assert (tmp_path / 'extension.js').read_bytes() == before
        return
    legacy.convert(tmp_path)
    assert json.loads((tmp_path / 'metadata.json').read_text())['shell-version'] == ['42', '43', '44']
    assert 'function init()' in (tmp_path / 'extension.js').read_text()
    assert 'import ' not in (tmp_path / 'extension.js').read_text()
    assert (tmp_path / 'tracker.js').read_text() == (source / 'tracker.js').read_text().replace(
        'export class Tracker', 'var Tracker = class Tracker', 1)
