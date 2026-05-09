from .common import router
from . import oauth as _oauth  # noqa: F401
from . import tokens as _tokens  # noqa: F401
from . import scheduler as _scheduler  # noqa: F401
from . import admin as _admin  # noqa: F401
from . import profile as _profile  # noqa: F401
from . import rivals as _rivals  # noqa: F401

__all__ = ["router"]