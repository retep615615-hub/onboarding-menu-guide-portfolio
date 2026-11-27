"""설정 불러오기.

config.py(실행 PC 전용)가 있으면 그것을, 없으면 config.example.py(견본)를 읽는다.
다른 파일은 `from guide.settings import cfg` 후 `cfg.DATA_DIR`처럼 쓴다.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    for name in ("config.py", "config.example.py"):
        path = ROOT / name
        if path.exists():
            spec = importlib.util.spec_from_file_location("hr_guide_config", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.SOURCE_FILE = name
            return module
    raise FileNotFoundError("설정 파일이 없습니다: config.py 또는 config.example.py를 저장소 맨 위 폴더에 두세요.")


cfg = _load()


def get(name, default=None):
    """설정에 없는 값이면 default를 돌려준다(예전 config.py를 써도 멈추지 않게)."""
    return getattr(cfg, name, default)
