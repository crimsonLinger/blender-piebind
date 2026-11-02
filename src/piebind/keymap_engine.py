"""兼容别名：piebind.keymap_engine -> piebind.core.keymap。"""

from .core import keymap as _impl

__all__ = [name for name in dir(_impl) if not name.startswith("__")]


def __getattr__(name):
    return getattr(_impl, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_impl)))
