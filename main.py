"""
地名翻译助手 - 基于 DeepSeek API 的地名翻译工具
严格遵循《地名管理条例实施办法》与《外语地名汉字译写导则 英语》
"""

import sys
import json
from pathlib import Path
from typing import cast

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from PySide6.QtCore import Qt, QSettings, QTimer, Signal, QThread
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QGraphicsDropShadowEffect,
)


def add_shadow(widget: QWidget) -> None:
    """为组件添加柔和的现代阴影"""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(15)
    shadow.setColor(Qt.GlobalColor.black)
    shadow.setOffset(0, 2)
    # 降低透明度让阴影更柔和
    color = shadow.color()
    color.setAlpha(15)
    shadow.setColor(color)
    widget.setGraphicsEffect(shadow)


# -------------------------------
# 翻译工作线程
# -------------------------------
class TranslationWorker(QThread):
    finished = Signal(object)

    def __init__(self, text: str, api_key: str, model: str):
        super().__init__()
        self.text = text
        self.api_key = api_key
        self.model = model

    def run(self) -> None:
        try:
            client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
            system_prompt = """
            你是一位顶级的地名翻译专家，请严格遵循以下规范将用户输入的中文地名翻译成英文：
            1. 《地名管理条例实施办法》中关于地名罗马字母拼写和译写的规定。
            2. 《外语地名汉字译写导则 英语》（GB/T 17693.1-2008）的译写总则和细则。
            
            你需要提供多个可能的翻译备选，例如：
            - 标准汉语拼音（如 Beijing）。
            - 历史或惯用的英文译名（如 Peking）。
            - 遵循导则的意译或音译，按照“专名”+“通名”的方式翻译（如 Yellow River）。
            
            你必须严格按照JSON格式输出，格式如下：
            {
                "translations": ["备选1", "备选2", "备选3"]
            }
            请确保输出是纯粹的 JSON 对象，不要包含任何其他说明文字。
            """
            messages: list[
                ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam
            ] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.text},
            ]
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("AI 返回内容为空")
            data = json.loads(content)
            options = data.get("translations", [])
            if not isinstance(options, list) or not options:
                raise ValueError("AI 返回的数据格式不正确，未找到翻译备选")
            self.finished.emit([str(opt) for opt in options])
        except Exception as e:
            self.finished.emit(e)


# -------------------------------
# 设置对话框
# -------------------------------
class SettingsDialog(QDialog):
    def __init__(
        self,
        api_key: str,
        model: str,
        copy_as_dict: bool,
        auto_read_clipboard: bool,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("API 与设置")
        self.resize(450, 220)

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignVCenter)  # 强制标签垂直居中

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(["deepseek-v4-pro", "deepseek-v4-flash"])
        if model:
            self.model_combo.setCurrentText(model)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setText(api_key)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.show_key_check = QCheckBox("显示 API Key")
        self.show_key_check.toggled.connect(self.toggle_api_key_visibility)

        self.copy_dict_check = QCheckBox("复制为键=值格式")
        self.copy_dict_check.setChecked(copy_as_dict)
        self.copy_dict_check.setToolTip("name=原文 name:zh=原文 name:en=译文")

        self.auto_clipboard_check = QCheckBox("自动读取剪贴板内容")
        self.auto_clipboard_check.setChecked(auto_read_clipboard)
        self.auto_clipboard_check.setToolTip(
            "每1秒检查一次剪贴板，如果有新内容则填入输入框"
        )

        layout.addRow("模型名称", self.model_combo)
        layout.addRow("API Key", self.api_key_edit)
        layout.addRow("", self.show_key_check)
        layout.addRow("", self.copy_dict_check)
        layout.addRow("", self.auto_clipboard_check)

        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("清空设置")
        self.clear_btn.setObjectName("iconBtn")
        self.clear_btn.clicked.connect(self.clear_settings)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # 应用样式到弹窗按钮
        button_box.button(QDialogButtonBox.StandardButton.Ok).setObjectName(
            "primaryBtn"
        )
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "iconBtn"
        )

        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(button_box)
        layout.addRow(btn_layout)

    def toggle_api_key_visibility(self, checked: bool) -> None:
        self.api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def clear_settings(self) -> None:
        settings = QSettings("PlaceNameTranslator", "PlaceNameTranslator")
        settings.clear()
        self.api_key_edit.clear()
        self.model_combo.setCurrentIndex(0)
        self.copy_dict_check.setChecked(False)
        self.auto_clipboard_check.setChecked(False)
        QMessageBox.information(self, "提示", "所有设置已清除")

    def get_settings(self) -> tuple[str, str, bool, bool]:
        return (
            self.api_key_edit.text().strip(),
            self.model_combo.currentText().strip(),
            self.copy_dict_check.isChecked(),
            self.auto_clipboard_check.isChecked(),
        )


# -------------------------------
# 主窗口
# -------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("地名翻译助手")
        # 增大初始尺寸以适应现代UI
        self.resize(450, 400)
        self.setMinimumSize(350, 300)

        self.settings = QSettings("PlaceNameTranslator", "PlaceNameTranslator")
        self.api_key = str(self.settings.value("api_key", ""))
        self.model = str(self.settings.value("model", "deepseek-v4-pro"))
        self.copy_as_dict = bool(self.settings.value("copy_as_dict", False))
        self.auto_read_clipboard = bool(
            self.settings.value("auto_read_clipboard", False)
        )

        self.worker: TranslationWorker | None = None

        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.setInterval(1000)
        self.clipboard_timer.timeout.connect(self.check_clipboard)
        self.last_clipboard_text = ""
        self.ignore_clipboard_change = False
        self.clipboard: QClipboard = QApplication.clipboard()

        if self.auto_read_clipboard:
            self.clipboard_timer.start()

        self.init_ui()

    def init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        # 增加外边距和内间距
        main_layout.setContentsMargins(20, 20, 20, 16)
        main_layout.setSpacing(12)

        # 头部：标题与设置按钮
        header_layout = QHBoxLayout()
        title_label = QLabel("地名翻译助手")
        title_label.setObjectName("headerLabel")

        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setObjectName("iconBtn")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.open_settings)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(settings_btn)
        main_layout.addLayout(header_layout)

        # 搜索输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入中文地名，按回车翻译...")
        self.input_edit.setClearButtonEnabled(True)  # 现代输入框自带清除按钮
        self.input_edit.returnPressed.connect(self.translate)
        add_shadow(self.input_edit)

        self.translate_btn = QPushButton("翻译")
        self.translate_btn.setObjectName("primaryBtn")
        self.translate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.translate_btn.clicked.connect(self.translate)
        add_shadow(self.translate_btn)

        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.translate_btn)
        main_layout.addLayout(input_layout)

        # 结果列表
        result_label = QLabel("翻译结果 (点击即可复制)：")
        result_label.setStyleSheet("color: #606266; font-size: 13px; margin-top: 8px;")
        main_layout.addWidget(result_label)

        self.result_list = QListWidget()
        self.result_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.result_list.itemClicked.connect(self.copy_selected)
        add_shadow(self.result_list)
        main_layout.addWidget(self.result_list)

        # 状态栏标签
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(False)
        self.status_label.setFixedHeight(20)
        main_layout.addWidget(self.status_label)

    def set_status(self, text: str, is_success: bool = False) -> None:
        self.status_label.setText(text.split("\n")[0])
        self.status_label.setToolTip(text)
        if is_success:
            self.status_label.setStyleSheet("color: #67C23A; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #909399;")

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.api_key, self.model, self.copy_as_dict, self.auto_read_clipboard, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_key, new_model, new_copy, new_auto = dialog.get_settings()
            if not new_key:
                QMessageBox.warning(self, "提示", "API Key 不能为空")
                return

            self.api_key = new_key
            self.model = new_model
            self.copy_as_dict = new_copy
            self.auto_read_clipboard = new_auto

            self.settings.setValue("api_key", self.api_key)
            self.settings.setValue("model", self.model)
            self.settings.setValue("copy_as_dict", self.copy_as_dict)
            self.settings.setValue("auto_read_clipboard", self.auto_read_clipboard)

            if self.auto_read_clipboard:
                if not self.clipboard_timer.isActive():
                    self.clipboard_timer.start()
            else:
                if self.clipboard_timer.isActive():
                    self.clipboard_timer.stop()

            self.set_status("⚙️ 设置已保存", True)

    def translate(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            self.input_edit.setFocus()
            return

        if not self.api_key:
            QMessageBox.warning(self, "提示", "请先在右上角“设置”中填写 API Key")
            return

        self.input_edit.setEnabled(False)
        self.translate_btn.setEnabled(False)
        self.translate_btn.setText("翻译中...")
        self.set_status("⏳ 正在请求 DeepSeek API，请稍候...")
        self.result_list.clear()

        self.worker = TranslationWorker(text, self.api_key, self.model)
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.start()

    def on_translation_finished(self, result: object) -> None:
        self.input_edit.setEnabled(True)
        self.translate_btn.setEnabled(True)
        self.translate_btn.setText("翻译")
        self.input_edit.setFocus()

        if isinstance(result, Exception):
            QMessageBox.critical(self, "翻译失败", f"发生错误：{result}")
            self.set_status(f"❌ 翻译失败: {result}")
        else:
            translations = cast(list[str], result)
            for text in translations:
                item = QListWidgetItem(text)
                # 为列表项设置更大的字体
                font = item.font()
                font.setPointSize(11)
                item.setFont(font)
                self.result_list.addItem(item)

            self.set_status(
                f"✅ 成功生成 {len(translations)} 个备选项，单击列表项即可复制", True
            )

    def copy_selected(self, item: QListWidgetItem) -> None:
        if self.copy_as_dict:
            original = self.input_edit.text().strip()
            clipboard_text = (
                f"name={original}\nname:zh={original}\nname:en={item.text()}"
            )
        else:
            clipboard_text = item.text()

        self.ignore_clipboard_change = True
        self.clipboard.setText(clipboard_text)
        self.set_status(f"📋 已复制到剪贴板：{clipboard_text}", True)

    def check_clipboard(self) -> None:
        if self.ignore_clipboard_change:
            self.ignore_clipboard_change = False
            self.last_clipboard_text = self.clipboard.text()
            return

        current_text = self.clipboard.text()
        if current_text and current_text != self.last_clipboard_text:
            self.last_clipboard_text = current_text
            self.input_edit.setText(current_text)
            self.set_status(f"✨ 已自动获取剪贴板内容：{current_text}")


# -------------------------------
# 程序入口
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 启用高DPI缩放支持
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    # 获取 main.py 所在的绝对路径，并加载同目录下的 style.qss
    current_dir = Path(__file__).parent
    qss_file = current_dir / "style.qss"

    if qss_file.exists():
        with open(qss_file, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet file '{qss_file}' not found. Using default styles.")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
