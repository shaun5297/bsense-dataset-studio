"""GUI 层回归测试。

覆盖 bug: SART 任务中按空格误触有焦点的 ttk.Button, 弹出"确认中止"
（操作员介入）对话框, 打断采集流程。

根因: ttk.Button 有焦点时, 空格键会先被按钮 class 绑定激活 (bindtags 顺序
widget -> class -> toplevel -> all), 而 ExecutionWindow 在 toplevel 层绑定的
_handle_space 返回 "break" 已经太晚, 无法阻止按钮激活。

修复: 所有按钮 takefocus=False (点击/Tab 都不会让按钮获得键盘焦点),
start() 时把焦点移到刺激标签上。
"""
import unittest

try:
    from tkinter import Tk, ttk

    _TK_OK = True
except Exception:  # pragma: no cover - 无 Tk 环境
    _TK_OK = False

from bsense_dataset_studio.acquisition.session import AcquisitionSession
from bsense_dataset_studio.app.execution_window import AnnotationDialog, ExecutionWindow
from bsense_dataset_studio.protocols.definitions import Protocol
from bsense_dataset_studio.storage import plan_run_storage


def _find_buttons(widget: object) -> list[ttk.Button]:
    buttons: list[ttk.Button] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            buttons.append(child)
        buttons.extend(_find_buttons(child))
    return buttons


def _make_window(root: Tk, directory: str) -> ExecutionWindow:
    storage = plan_run_storage(directory, "P001", "01", "m6_readiness_field", "001")
    protocol = Protocol("m6_readiness_field", "测试协议", "test", "2.0", ())
    session = AcquisitionSession(
        storage,
        protocol,
        participant_id="P001",
        session_id="01",
        run_id="001",
    )
    return ExecutionWindow(root, session, protocol)


@unittest.skipUnless(_TK_OK, "tkinter 不可用")
class ExecutionWindowButtonFocusTests(unittest.TestCase):
    def test_all_buttons_do_not_take_keyboard_focus(self) -> None:
        """所有操作按钮不应获得键盘焦点, 否则 SART 任务中空格/回车会误触按钮。"""
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Tk()
            try:
                window = _make_window(root, directory)
                root.update()
                buttons = _find_buttons(window)
                self.assertTrue(buttons, "应能找到所有按钮")
                for button in buttons:
                    self.assertEqual(
                        button.cget("takefocus"),
                        0,
                        f"按钮 {button.cget('text')!r} 不应接收键盘焦点",
                    )
                window.destroy()
            finally:
                root.destroy()

    def test_annotation_dialog_button_does_not_take_focus(self) -> None:
        """人工标注对话框的"保存标注"按钮也不应获得键盘焦点。"""
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Tk()
            try:
                window = _make_window(root, directory)
                root.update()
                dialog = AnnotationDialog(window, window.session)
                root.update()
                save_buttons = [
                    button
                    for button in _find_buttons(dialog)
                    if button.cget("text") == "保存标注"
                ]
                self.assertTrue(save_buttons, "应能找到“保存标注”按钮")
                for button in save_buttons:
                    self.assertEqual(
                        button.cget("takefocus"),
                        0,
                        "保存标注按钮不应接收键盘焦点",
                    )
                dialog.destroy()
                window.destroy()
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
