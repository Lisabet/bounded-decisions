import json
import pytest
from decision_kit.examples.__main__ import main


def test_installed_starters_are_readable_and_preserve_existing_files(tmp_path):
    output = tmp_path / 'inputs'
    assert main([str(output)]) == 0
    assert json.loads((output / 'plusvibe.json').read_text())['provider'] == 'plusvibe'
    assert len(json.loads((output / 'cases.json').read_text())) == 1
    (output / 'cases.json').write_text('owner content')
    with pytest.raises(SystemExit):
        main([str(output)])
    assert (output / 'cases.json').read_text() == 'owner content'
