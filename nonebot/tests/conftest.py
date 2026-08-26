from __future__ import annotations

import pathlib
import sys
import types

import nonebot


try:
    nonebot.get_driver()
except ValueError:
    nonebot.init(log_level="WARNING")


PACKAGE_NAME = "gsz_assist_testpkg"
PACKAGE_PATH = pathlib.Path(__file__).parents[1] / "src" / "plugins" / "gsz-assist"

if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules[PACKAGE_NAME] = package
