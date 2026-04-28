"""
地名翻译助手 - 基于 DeepSeek API 的地名翻译工具
严格遵循《地名管理条例实施办法》与《外语地名汉字译写导则 英语》
"""

import sys
import json
from typing import cast

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from PySide6.QtCore import QSettings, QTimer, Signal, QThread
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
    QMenuBar,
)


# -------------------------------
# 翻译工作线程
# -------------------------------
class TranslationWorker(QThread):
    """后台翻译线程，避免阻塞界面"""

    finished = Signal(object)  # 成功时发送 list[str]，失败时发送 Exception

    def __init__(self, text: str, api_key: str, model: str):
        super().__init__()
        self.text = text
        self.api_key = api_key
        self.model = model

    def run(self) -> None:
        """执行翻译请求"""
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

            # 显式构造符合 API 类型要求的消息列表
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
            # 确保 content 不为 None 再解析
            if content is None:
                raise ValueError("AI 返回内容为空")

            data = json.loads(content)
            options = data.get("translations", [])

            if not isinstance(options, list) or not options:
                raise ValueError("AI 返回的数据格式不正确，未找到翻译备选")

            self.finished.emit([str(opt) for opt in options])

        except Exception as e:  # pylint: disable=broad-exception-caught
            # 捕获所有异常并传递给主线程处理
            self.finished.emit(e)


# -------------------------------
# 设置对话框
# -------------------------------
class SettingsDialog(QDialog):
    """API 与功能设置对话框"""

    def __init__(
        self,
        api_key: str,
        model: str,
        copy_as_dict: bool,
        auto_read_clipboard: bool,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("API 与输出设置")
        self.resize(400, 270)

        layout = QFormLayout(self)

        # 模型选择
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(["deepseek-v4-pro", "deepseek-v4-flash"])
        if model:
            self.model_combo.setCurrentText(model)

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setText(api_key)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        # 展示 API Key 复选框
        self.show_key_check = QCheckBox("展示 API Key（明文）")
        self.show_key_check.toggled.connect(self.toggle_api_key_visibility)

        # 复制格式复选框
        self.copy_dict_check = QCheckBox(
            "复制为字典格式 (name=..., name:zh=..., name:en=...)"
        )
        self.copy_dict_check.setChecked(copy_as_dict)

        # 自动读取剪贴板复选框
        self.auto_clipboard_check = QCheckBox("自动读取剪贴板模式（每1秒检查）")
        self.auto_clipboard_check.setChecked(auto_read_clipboard)

        layout.addRow("模型名称:", self.model_combo)
        layout.addRow("API Key:", self.api_key_edit)
        layout.addRow("", self.show_key_check)
        layout.addRow("", self.copy_dict_check)
        layout.addRow("", self.auto_clipboard_check)

        # 按钮
        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("清空设置")
        self.clear_btn.clicked.connect(self.clear_settings)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(button_box)
        layout.addRow(btn_layout)

    def toggle_api_key_visibility(self, checked: bool) -> None:
        """切换 API Key 输入框的明文/密码模式"""
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def clear_settings(self) -> None:
        """清除所有持久化设置"""
        settings = QSettings("MyCompany", "PlaceNameTranslator")
        settings.clear()
        self.api_key_edit.clear()
        self.model_combo.setCurrentIndex(0)
        self.copy_dict_check.setChecked(False)
        self.auto_clipboard_check.setChecked(False)
        QMessageBox.information(self, "提示", "所有设置已清除")

    def get_settings(self) -> tuple[str, str, bool, bool]:
        """获取当前对话框中的配置值"""
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
    """地名翻译助手主界面"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("地名翻译助手")
        self.resize(250, 200)
        self.setMinimumSize(220, 180)

        self.settings = QSettings("MyCompany", "PlaceNameTranslator")

        # 加载持久化设置（显式类型转换确保类型安全）
        self.api_key = str(self.settings.value("api_key", ""))
        self.model = str(self.settings.value("model", "deepseek-v4-pro"))
        self.copy_as_dict = bool(self.settings.value("copy_as_dict", False))
        self.auto_read_clipboard = bool(
            self.settings.value("auto_read_clipboard", False)
        )

        self.worker: TranslationWorker | None = None

        # 自动读取剪贴板相关
        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.setInterval(1000)
        self.clipboard_timer.timeout.connect(self.check_clipboard)
        self.last_clipboard_text = ""
        self.ignore_clipboard_change = False
        self.clipboard: QClipboard = QApplication.clipboard()

        if self.auto_read_clipboard:
            self.clipboard_timer.start()

        self.init_ui()
        self.init_menu()

    def init_ui(self) -> None:
        """构建用户界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 输入区域
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入中文地名")
        self.input_edit.returnPressed.connect(self.translate)

        self.translate_btn = QPushButton("翻译")
        self.translate_btn.clicked.connect(self.translate)

        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.translate_btn)
        main_layout.addLayout(input_layout)

        # 结果列表
        result_label = QLabel("备选翻译（点击复制）：")
        main_layout.addWidget(result_label)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self.copy_selected)
        main_layout.addWidget(self.result_list)

        # 状态标签（单行限制，超出省略，悬停显示完整内容）
        self.status_label = QLabel("")
        self.status_label.setWordWrap(False)
        self.status_label.setFixedHeight(20)
        main_layout.addWidget(self.status_label)

    def init_menu(self) -> None:
        """初始化菜单栏"""
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        settings_action = menu_bar.addAction("设置")
        settings_action.triggered.connect(self.open_settings)

    def set_status(self, text: str) -> None:
        """设置状态栏文本，并添加完整内容作为工具提示"""
        self.status_label.setText(text)
        self.status_label.setToolTip(text)

    def open_settings(self) -> None:
        """打开设置对话框并保存配置"""
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

            # 持久化保存
            self.settings.setValue("api_key", self.api_key)
            self.settings.setValue("model", self.model)
            self.settings.setValue("copy_as_dict", self.copy_as_dict)
            self.settings.setValue("auto_read_clipboard", self.auto_read_clipboard)

            # 控制剪贴板定时器
            if self.auto_read_clipboard:
                if not self.clipboard_timer.isActive():
                    self.clipboard_timer.start()
            else:
                if self.clipboard_timer.isActive():
                    self.clipboard_timer.stop()

            self.set_status("设置已保存")

    def translate(self) -> None:
        """发起翻译请求"""
        text = self.input_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入中文地名")
            return

        if not self.api_key:
            QMessageBox.warning(self, "提示", "请先在“设置”中填写 API Key")
            return

        self.input_edit.setEnabled(False)
        self.translate_btn.setEnabled(False)
        self.set_status("正在翻译，请稍候...")
        self.result_list.clear()

        self.worker = TranslationWorker(text, self.api_key, self.model)
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.start()

    def on_translation_finished(self, result: object) -> None:
        """翻译完成回调"""
        self.input_edit.setEnabled(True)
        self.translate_btn.setEnabled(True)

        if isinstance(result, Exception):
            QMessageBox.critical(self, "翻译失败", f"发生错误：{result}")
            self.set_status("翻译失败")
        else:
            # result 是 List[str]
            translations = cast(list[str], result)
            self.result_list.addItems(translations)
            self.set_status(f"共 {len(translations)} 个备选项，单击可复制到剪贴板")

    def copy_selected(self, item: QListWidgetItem) -> None:
        """复制选中的翻译结果，支持字典格式，并避免自动读取冲突"""
        if self.copy_as_dict:
            original = self.input_edit.text().strip()
            clipboard_text = (
                f"name={original}\nname:zh={original}\nname:en={item.text()}"
            )
        else:
            clipboard_text = item.text()

        # 设置忽略标志，防止自动读取剪贴板时把翻译结果填回输入框
        self.ignore_clipboard_change = True
        self.clipboard.setText(clipboard_text)
        # 状态栏复制信息只展示一行
        self.set_status(f"已复制：{clipboard_text.split('\n')[0]}")

    def check_clipboard(self) -> None:
        """定时器回调：检测剪贴板变化并自动填入输入框"""
        if self.ignore_clipboard_change:
            self.ignore_clipboard_change = False
            self.last_clipboard_text = self.clipboard.text()
            return

        current_text = self.clipboard.text()
        if current_text and current_text != self.last_clipboard_text:
            self.last_clipboard_text = current_text
            self.input_edit.setText(current_text)
            # 状态栏信息只展示一行
            self.set_status(f"已自动填入剪贴板内容：{current_text.split('\n')[0]}")


# -------------------------------
# 程序入口
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
