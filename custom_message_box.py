import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


# Compute once — never changes during the process lifetime.
if hasattr(sys, "_MEIPASS"):
    _BASE_PATH = Path(sys._MEIPASS)  # pyright: ignore[reportAttributeAccessIssue]
else:
    _BASE_PATH = Path(__file__).resolve().parent


def get_resource_path(relative_path: str) -> Path:
    return _BASE_PATH / relative_path


# Pre-render icon pixmaps so SVGs aren't parsed on every dialog show.
_ICON_CACHE: dict[str, QPixmap] = {}

def _get_icon_pixmap(icon_name: str) -> QPixmap | None:
    pix = _ICON_CACHE.get(icon_name)
    if pix is None:
        icon_path = get_resource_path(f"images/custom_message_box/{icon_name}")
        pix = QIcon(str(icon_path)).pixmap(40, 40)
        _ICON_CACHE[icon_name] = pix
    return pix if not pix.isNull() else None


class CustomMessageBox(QDialog):
    """现代化自定义提示框"""

    _THEMES: dict[str, tuple[str, str, str]] = {
        "success": ("#67C23A", "#85CE61", "#5DAF34"),
        "warning": ("#E6A23C", "#EBB563", "#CF9236"),
        "critical": ("#F56C6C", "#F78989", "#DD6161"),
        "info": ("#409EFF", "#66B1FF", "#3A8EE6"),
    }

    _STYLESHEETS: dict[str, str] = {}

    @classmethod
    def _get_stylesheet(cls, msg_type: str) -> str:
        ss = cls._STYLESHEETS.get(msg_type)
        if ss is None:
            bg, hover, pressed = cls._THEMES.get(msg_type, cls._THEMES["info"])
            ss = f"""
                QPushButton {{
                    background-color: {bg};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {hover};
                }}
                QPushButton:pressed {{
                    background-color: {pressed};
                }}
            """
            cls._STYLESHEETS[msg_type] = ss
        return ss

    def __init__(
        self,
        parent=None,
        title="",
        text="",
        icon_name="info.svg",
        btn_text="我知道了",
        msg_type="info",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)

        # 整体纵向布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 15)

        content_layout = QHBoxLayout()
        self._icon_label = QLabel()
        pixmap = _get_icon_pixmap(icon_name)
        if pixmap is not None:
            self._icon_label.setPixmap(pixmap)
        else:
            self._icon_label.hide()

        self._text_label = QLabel(text)
        self._text_label.setStyleSheet("font-size: 14px; color: #303133;")
        self._text_label.setWordWrap(True)

        content_layout.addWidget(self._icon_label)
        content_layout.addSpacing(15)
        content_layout.addWidget(self._text_label)
        content_layout.addStretch()

        # 下半部分：底部按钮
        btn_layout = QHBoxLayout()
        self._ok_btn = QPushButton(btn_text)
        self._ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ok_btn.setFixedSize(90, 32)
        self._ok_btn.setStyleSheet(self._get_stylesheet(msg_type))
        self._ok_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self._ok_btn)

        layout.addLayout(content_layout)
        layout.addSpacing(20)
        layout.addLayout(btn_layout)

    @staticmethod
    def success(parent, title: str, text: str):
        """成功提示 (绿色按钮)"""
        dialog = CustomMessageBox(
            parent, title, text, "success.svg", "好的", "success"
        )
        dialog.exec()

    @staticmethod
    def warning(parent, title: str, text: str):
        """警告提示 (橙色按钮)"""
        dialog = CustomMessageBox(
            parent, title, text, "warning.svg", "我知道了", "warning"
        )
        dialog.exec()

    @staticmethod
    def critical(parent, title: str, text: str):
        """错误提示 (红色按钮)"""
        dialog = CustomMessageBox(parent, title, text, "error.svg", "关闭", "critical")
        dialog.exec()

    @staticmethod
    def information(parent, title: str, text: str):
        """普通信息提示 (蓝色按钮)"""
        dialog = CustomMessageBox(parent, title, text, "info.svg", "确认", "info")
        dialog.exec()
