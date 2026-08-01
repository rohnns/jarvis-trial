from __future__ import annotations

import inspect
from pathlib import Path

import openwakeword
from openwakeword.model import Model

print(openwakeword.__file__)
print(inspect.signature(Model))
package_dir = Path(openwakeword.__file__).parent
for path in package_dir.rglob("*.onnx"):
    print(path)
