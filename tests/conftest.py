"""pytest 配置:让 backend/app/... 可被测试文件导入。

QA Studio 没有 pyproject.toml,backend 目录不在默认 sys.path,
这里把 D:/Code/QA_Studio/backend 加入路径,以便:
    from app.services.preprocess_service import ...
"""

import pathlib
import sys

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
