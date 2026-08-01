from pathlib import Path
from Core.config import ConfigService

def test_config_get(tmp_path: Path):
    p = tmp_path / 'settings.json'; p.write_text('{"a":{"b":2}}')
    assert ConfigService(p).get('a.b') == 2
    assert ConfigService(p).get('missing', 'x') == 'x'
