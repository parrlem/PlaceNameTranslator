# custom_message_box.py
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


def get_resource_path(relative_path: str) -> Path:
    """获取资源的绝对路径，兼容打包和脚本运行"""
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS) # pyright: ignore[reportAttributeAccessIssue]
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path


class CustomMessageBox(QDialog):
    """现代化自定义提示框"""

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
        self.setMinimumWidth(320)  # 保证弹窗不会太窄

        # 整体纵向布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 15)

        # 上半部分：图标 + 文字
        content_layout = QHBoxLayout()
        self.icon_label = QLabel()

        # 【修改点 1】：更新图片读取路径到 custom_message_box 文件夹下
        icon_path = get_resource_path(f"images/custom_message_box/{icon_name}")
        if icon_path.exists():
            self.icon_label.setPixmap(QIcon(str(icon_path)).pixmap(40, 40))
        else:
            self.icon_label.hide()  # 如果找不到图片就隐藏图标区域

        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("font-size: 14px; color: #303133;")
        self.text_label.setWordWrap(True)  # 允许长文本换行

        content_layout.addWidget(self.icon_label)
        content_layout.addSpacing(15)
        content_layout.addWidget(self.text_label)
        content_layout.addStretch()

        # 下半部分：底部按钮
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton(btn_text)
        self.ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_btn.setFixedSize(90, 32)

        # 【修改点 2】：根据不同类型注入不同颜色的独立 QSS 样式
        self.apply_button_style(msg_type)

        self.ok_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)

        layout.addLayout(content_layout)
        layout.addSpacing(20)
        layout.addLayout(btn_layout)

    def apply_button_style(self, msg_type: str) -> None:
        """根据消息紧急程度，动态生成不同颜色的按钮样式"""
        # 定义颜色主题：格式为 (默认背景色, 悬停颜色, 点击颜色)
        themes = {
            "success": ("#67C23A", "#85CE61", "#5DAF34"),  # 绿色
            "warning": ("#E6A23C", "#EBB563", "#CF9236"),  # 橙色/黄色
            "critical": ("#F56C6C", "#F78989", "#DD6161"),  # 红色
            "info": ("#409EFF", "#66B1FF", "#3A8EE6"),  # 蓝色
        }

        # 如果传入了未知的类型，默认使用 info 的蓝色主题
        bg, hover, pressed = themes.get(msg_type, themes["info"])

        # 独立注入样式，不影响全局 QSS
        style_sheet = f"""
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
        self.ok_btn.setStyleSheet(style_sheet)

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
