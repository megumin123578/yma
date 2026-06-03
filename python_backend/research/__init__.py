"""Pipeline nghiên cứu ngách YouTube (trích từ project FMC, gộp vào yt_manage_app).

Trước đây code chạy dưới package tên `core` (app desktp Tkinter). Khi gộp vào
backend, các module đổi sang `python_backend.research.*`. Nhưng dữ liệu đã thu
thập nằm trong các file .pkl được pickle với đường dẫn class CŨ là
`core.<module>.<Class>` (vd `core.youtube_client.ChannelInfo`). Để unpickle lại
được mà KHÔNG phải migrate 700+ file pkl, ta cài một meta path finder ánh xạ
`core` và `core.*` về `python_backend.research.*` (cùng object module, nên
isinstance + attribute access đều đúng). Active ngay khi import package này.
"""

import importlib
import importlib.abc
import importlib.util
import sys


class _CoreAliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Ánh xạ import `core[.x]` -> `python_backend.research[.x]` cho pickle cũ."""

    PREFIX = "core"
    TARGET = __name__  # "python_backend.research"

    def find_spec(self, fullname, path=None, target=None):
        if fullname != self.PREFIX and not fullname.startswith(self.PREFIX + "."):
            return None
        new_name = self.TARGET + fullname[len(self.PREFIX):]
        module = importlib.import_module(new_name)
        sys.modules[fullname] = module
        return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        return sys.modules[spec.name]

    def exec_module(self, module):
        pass


if not any(isinstance(f, _CoreAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _CoreAliasFinder())
