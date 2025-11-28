import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from gostop.analysis import compute_go_nogo_metrics

from core.audio import play_notification_sound
from core.fileio import build_timestamped_path, save_pickle
from core.randomization import compute_go_ratio, generate_trial_schedule
from core.timing import Stopwatch, format_countdown_text, start_countdown_timer
from core.utils import get_app_icon, set_groupbox_title_font, translate


TRANSLATIONS = {
    "en": {
        "go_digits": "Go digits",
        "nogo_digits": "No-Go digits",
        "digit_weights": "Digit weights",
        "digit_proportions": "Digit proportions",
        "blocks": "Number of blocks",
        "rest_duration": "Pre-block rest (s)",
        "post_block_rest": "Post-block rest (s)",
        "inter_block_interval": "Inter-block interval (s)",
        "stimulus_duration": "Stimulus duration (s)",
        "inter_trial_interval": "Inter-trial interval (s)",
        "max_response_window": "Max response window (s)",
        "notes": "Notes",
        "language": "Language",
        "test_mode": "Test mode",
        "start": "Start",
        "start_experiment": "Start Experiment",
        "reset": "Reset",
        "end": "End",
        "aborted": "Aborted",
        "block_finished": "Block {n} finished. \n Please rest.",
        "ready": "Ready",
        "running_block": "Running block {n}",
        "completed": "Completed",
        "error": "Error",
        "ok": "OK",
        "validation_failed": "Validation failed",
        "file_saved": "Log file saved:\n{path}",
        "file_save_failed": "Failed to save log file:\n{error}",
        "abort_by_user": "user_pressed_esc",
        "language_en": "English",
        "language_zh": "中文",
        "trials_per_block": "Trials per block",
        "timing_and_blocks": "Timing and blocks",
        "options": "Options",
        "digits_section": "Digits (Go / No-Go)",
        "digits_preview": "Digits preview",
        "timing_part_a": "Global settings",
        "timing_part_b": "Block structure",
        "paradigm_name": "Paradigm name",
        "output_folder": "Output folder",
        "notes_placeholder": "Patient info / Electrode info / Notes",
        "result_title": "Result",
        "result_go_hit": "Go hit%",
        "result_nogo_commission": "No-Go commission%",
        "result_mean_rt_go": "Mean RT of go hit (s)",
        "result_mean_rt_nogo": "Mean RT of no go commission (s)",
        "sum": "Sum",
    },
    "zh": {
        "go_digits": "Go 数字",
        "nogo_digits": "No-Go 数字",
        "digit_weights": "数字占比",
        "digit_proportions": "数字占比",
        "blocks": "区块数量",
        "rest_duration": "区块前静息 (秒)",
        "post_block_rest": "区块结束休息 (秒)",
        "inter_block_interval": "区块间隔 (秒)",
        "stimulus_duration": "刺激显示时长 (秒)",
        "inter_trial_interval": "试次间隔 (秒)",
        "max_response_window": "最大反应时间窗 (秒)",
        "notes": "备注",
        "language": "语言",
        "test_mode": "测试模式",
        "start": "开始",
        "start_experiment": "开始实验",
        "reset": "重置",
        "end": "结束",
        "aborted": "已中止",
        "block_finished": "第 {n} 段结束，\n 请休息。",
        "ready": "就绪",
        "running_block": "正在运行第 {n} 段",
        "completed": "已完成",
        "error": "错误",
        "ok": "确定",
        "validation_failed": "验证失败",
        "file_saved": "日志文件已保存：\n{path}",
        "file_save_failed": "保存日志失败：\n{error}",
        "abort_by_user": "用户按下 ESC",
        "language_en": "English",
        "language_zh": "中文",
        "trials_per_block": "每段试次数",
        "timing_and_blocks": "时间与区块",
        "options": "选项",
        "digits_section": "数字（Go / No-Go）",
        "digits_preview": "数字预览",
        "timing_part_a": "全局设置",
        "timing_part_b": "区块结构",
        "paradigm_name": "范式名称",
        "output_folder": "输出文件夹",
        "notes_placeholder": "患者信息 / 电极信息 / 备注",
        "result_title": "结果",
        "result_go_hit": "Go 命中率",
        "result_nogo_commission": "No-Go 误按率",
        "result_mean_rt_go": "Go 命中平均反应时 (秒)",
        "result_mean_rt_nogo": "No-Go 误按平均反应时 (秒)",
        "sum": "总计",
    },
}

ICON_PATH = Path(__file__).resolve().parents[1] / "icon" / "icon.png"


def play_notification_async(sound_type: str) -> None:
    thread = threading.Thread(target=play_notification_sound, args=(sound_type,), daemon=True)
    thread.start()


class ExperimentRunner(QtWidgets.QWidget):
    experiment_finished = QtCore.pyqtSignal(dict)

    def __init__(self, config: Dict, meta: Dict, language: str):
        super().__init__()
        self.setWindowTitle("Go/No-Go Experiment")
        self.setWindowIcon(get_app_icon(ICON_PATH))
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.language = language
        self.config = config
        self.meta = meta
        self.active_timers: List[QtCore.QTimer] = []
        self.current_block_index = 0
        self.current_trial_index = -1
        self.current_trial_entry_abs = None
        self.current_trial_entry_rel = None
        self.in_response_window = False
        self.response_recorded = False
        self.response_timer: QtCore.QTimer | None = None
        self.stimulus_timer: QtCore.QTimer | None = None
        self.experiment_aborted = False
        self.showing_results = False
        self.result_widget: QtWidgets.QWidget | None = None
        self.first_trial_in_block = True
        self.setStyleSheet("background-color: black;")
        self.label = QtWidgets.QLabel("", self)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.base_label_style = "color: white; background-color: black; border: none;"
        self.label.setStyleSheet(self.base_label_style)
        self.label.setTextFormat(QtCore.Qt.RichText)
        font = QtGui.QFont()
        font.setPointSize(360)
        font.setBold(True)
        self.label.setFont(font)
        self.stimulus_font = QtGui.QFont(font)
        self.rest_font = QtGui.QFont(font)
        self.rest_font.setPointSize(164)
        self.rest_font.setBold(True)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.label, alignment=QtCore.Qt.AlignCenter)
        self.setLayout(layout)

        self.log = {
            "meta": self.meta,
            "config": self.config,
            "timing_absolute": {
                "blocks": {},
                "inter_block_intervals": {},
            },
            "timing_relative": {
                "blocks": {},
                "inter_block_intervals": {},
            },
            "status": {
                "completed": False,
                "abort_reason": None,
                "abort_time_absolute": None,
                "abort_time_relative": None,
            },
        }
        self.stopwatch = Stopwatch()
        self.start_datetime = self.stopwatch.start_datetime
        self.log["timing_absolute"]["experiment_start"] = self.start_datetime
        self.log["timing_relative"]["experiment_start"] = 0.0
        self.showFullScreen()
        self.show_start_screen()

    def t(self, key: str) -> str:
        return translate(TRANSLATIONS, self.language, key)

    def make_timer(self, ms: int, callback) -> QtCore.QTimer:
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(ms)
        self.active_timers.append(timer)
        return timer

    def clear_timers(self) -> None:
        for t in self.active_timers:
            t.stop()
        self.active_timers.clear()

    def show_start_screen(self) -> None:
        self.label.setText(self.t("start"))
        self.make_timer(1000, self.start_block)

    def set_blank_screen(self) -> None:
        self.label.setText("")
        self.label.setStyleSheet(self.base_label_style)

    def start_block(self) -> None:
        if self.experiment_aborted:
            return
        if self.current_block_index >= self.config["n_blocks"]:
            self.finish_experiment()
            return
        block_num = self.current_block_index + 1
        block_start_abs, block_start_rel = self.stopwatch.timestamp_pair()
        block_abs = {
            "block_start": block_start_abs,
            "rest_start": None,
            "task_start": None,
            "post_rest_start": None,
            "trials": [],
        }
        block_rel = {
            "block_start": block_start_rel,
            "rest_start": None,
            "task_start": None,
            "post_rest_start": None,
            "trials": [],
        }
        self.log["timing_absolute"]["blocks"][block_num] = block_abs
        self.log["timing_relative"]["blocks"][block_num] = block_rel
        self.set_blank_screen()
        rest_abs, rest_rel = self.stopwatch.timestamp_pair()
        block_abs["rest_start"] = rest_abs
        block_rel["rest_start"] = rest_rel
        rest_ms = int(self.config["rest_duration_s"] * 1000)
        self.make_timer(rest_ms, self.start_trials)

    def start_trials(self) -> None:
        if self.experiment_aborted:
            return
        block_num = self.current_block_index + 1
        block_abs = self.log["timing_absolute"]["blocks"][block_num]
        block_rel = self.log["timing_relative"]["blocks"][block_num]
        task_abs, task_rel = self.stopwatch.timestamp_pair()
        block_abs["task_start"] = task_abs
        block_rel["task_start"] = task_rel
        self.current_trial_index = -1
        self.first_trial_in_block = True
        self.block_trials = self.config["trial_schedule"][block_num]
        self.start_next_trial()

    def start_next_trial(self) -> None:
        if self.experiment_aborted:
            return
        self.current_trial_index += 1
        if self.current_trial_index >= len(self.block_trials):
            self.finish_block()
            return
        self.in_response_window = False
        self.response_recorded = False
        self.current_trial_entry_abs = None
        self.current_trial_entry_rel = None
        self.set_blank_screen()
        if self.first_trial_in_block and self.current_trial_index == 0:
            self.first_trial_in_block = False
            self.show_trial_stimulus()
        else:
            iti_ms = int(self.config["inter_trial_interval_s"] * 1000)
            self.make_timer(iti_ms, self.show_trial_stimulus)

    def show_trial_stimulus(self) -> None:
        if self.experiment_aborted:
            return
        trial_info = self.block_trials[self.current_trial_index]
        digit = trial_info["digit"]
        self.label.setFont(self.stimulus_font)
        self.label.setText(str(digit))
        play_notification_async("high_beep")
        onset_abs, onset_rel = self.stopwatch.timestamp_pair()
        block_num = self.current_block_index + 1
        block_abs = self.log["timing_absolute"]["blocks"][block_num]
        block_rel = self.log["timing_relative"]["blocks"][block_num]

        trial_abs = {
            "trial_index": self.current_trial_index + 1,
            "digit": digit,
            "is_go_trial": trial_info["is_go"],
            "times": (onset_abs, None),
            "response_key": None,
            "outcome": None,
            "response_time": float("nan"),
        }
        trial_rel = {
            "trial_index": self.current_trial_index + 1,
            "digit": digit,
            "is_go_trial": trial_info["is_go"],
            "times": (onset_rel, None),
            "response_key": None,
            "outcome": None,
            "response_time": float("nan"),
        }
        block_abs["trials"].append(trial_abs)
        block_rel["trials"].append(trial_rel)
        self.current_trial_entry_abs = trial_abs
        self.current_trial_entry_rel = trial_rel
        self.in_response_window = True
        self.response_recorded = False
        stim_ms = int(self.config["stimulus_duration_s"] * 1000)
        resp_ms = int(self.config["max_response_window_s"] * 1000)
        self.stimulus_timer = self.make_timer(stim_ms, self.hide_stimulus)
        self.response_timer = self.make_timer(resp_ms, self.response_window_expired)

    def hide_stimulus(self) -> None:
        self.set_blank_screen()

    def response_window_expired(self) -> None:
        if self.experiment_aborted:
            return
        if self.response_recorded or not self.in_response_window:
            return
        self.record_trial_outcome(response_time_abs=None, response_time_rel=None, pressed=False)
        self.in_response_window = False
        self.response_recorded = True
        self.start_next_trial()

    def record_trial_outcome(
        self,
        response_time_abs: datetime | None,
        response_time_rel: float | None,
        pressed: bool,
    ) -> None:
        if not self.current_trial_entry_abs or not self.current_trial_entry_rel:
            return
        trial_info = self.block_trials[self.current_trial_index]
        is_go = trial_info["is_go"]
        outcome = None
        if pressed:
            outcome = "hit" if is_go else "commission_error"
        else:
            outcome = "miss" if is_go else "correct_withholding"
        abs_times = (self.current_trial_entry_abs["times"][0], response_time_abs)
        rel_times = (self.current_trial_entry_rel["times"][0], response_time_rel)
        self.current_trial_entry_abs["times"] = abs_times
        self.current_trial_entry_rel["times"] = rel_times
        self.current_trial_entry_abs["response_key"] = "space" if pressed else None
        self.current_trial_entry_rel["response_key"] = "space" if pressed else None
        self.current_trial_entry_abs["outcome"] = outcome
        self.current_trial_entry_rel["outcome"] = outcome
        rt = float("nan")
        if pressed:
            onset_rel = self.current_trial_entry_rel["times"][0]
            if response_time_rel is not None and onset_rel is not None:
                rt = response_time_rel - onset_rel
            elif response_time_abs is not None and self.current_trial_entry_abs["times"][0] is not None:
                try:
                    rt = (response_time_abs - self.current_trial_entry_abs["times"][0]).total_seconds()
                except Exception:
                    rt = float("nan")
        self.current_trial_entry_abs["response_time"] = rt
        self.current_trial_entry_rel["response_time"] = rt

    def finish_block(self) -> None:
        if self.experiment_aborted:
            return
        block_num = self.current_block_index + 1
        block_abs = self.log["timing_absolute"]["blocks"][block_num]
        block_rel = self.log["timing_relative"]["blocks"][block_num]
        is_last_block = block_num >= self.config["n_blocks"]
        if is_last_block:
            self.current_block_index += 1
            self.finish_experiment()
            return
        rest_abs, rest_rel = self.stopwatch.timestamp_pair()
        block_abs["post_rest_start"] = rest_abs
        block_rel["post_rest_start"] = rest_rel
        total_interval = self.config["post_block_rest_duration_s"] + self.config["inter_block_interval_s"]
        rest_msg = (
            self.t("block_finished")
            .format(n=block_num)
            .replace("\\n", "<br>")
            .replace("\n", "<br>")
        )
        max_countdown_text = f"{total_interval:06.3f}s"
        fm = self.label.fontMetrics()
        min_width = fm.boundingRect(max_countdown_text).width() + 40
        self.label.setMinimumWidth(min_width)
        self.label.setFont(self.rest_font)
        interval_abs, interval_rel = self.stopwatch.timestamp_pair()
        self.log["timing_absolute"]["inter_block_intervals"][block_num] = {"interval_start": interval_abs}
        self.log["timing_relative"]["inter_block_intervals"][block_num] = {"interval_start": interval_rel}

        def update_rest_countdown(ms_left: int) -> None:
            countdown_html = format_countdown_text(rest_msg, ms_left, use_html=True)
            self.label.setStyleSheet(self.base_label_style)
            self.label.setText(countdown_html)

        self.current_block_index += 1
        start_countdown_timer(
            parent=self,
            duration_s=total_interval,
            on_tick=update_rest_countdown,
            on_finished=self.start_block,
            register_timer=self.active_timers.append,
        )

    def start_inter_block(self) -> None:
        if self.experiment_aborted:
            return
        # Countdown now handled in finish_block; start next block immediately.
        self.start_block()

    def show_results_screen(self) -> None:
        if self.showing_results:
            return
        self.showing_results = True
        self.in_response_window = False
        self.response_recorded = True
        self.clear_timers()

        try:
            metrics = compute_go_nogo_metrics(self.log)
        except Exception:
            metrics = {
                "go_hit_percent": None,
                "nogo_commission_percent": None,
                "mean_rt_go_hit": None,
                "mean_rt_nogo_commission": None,
            }
        self.log["metrics"] = metrics

        layout = self.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout()
            self.setLayout(layout)

        if self.label:
            layout.removeWidget(self.label)
            self.label.hide()
        if self.result_widget:
            layout.removeWidget(self.result_widget)
            self.result_widget.deleteLater()

        container = QtWidgets.QWidget(self)
        container.setStyleSheet("background-color: black; color: white;")
        vbox = QtWidgets.QVBoxLayout()
        vbox.setSpacing(40)
        vbox.setContentsMargins(80, 60, 80, 60)
        container.setLayout(vbox)

        title_lbl = QtWidgets.QLabel(self.t("result_title"))
        title_font = QtGui.QFont()
        title_font.setPointSize(120)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        title_lbl.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(title_lbl, alignment=QtCore.Qt.AlignHCenter)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(120)
        grid.setVerticalSpacing(80)
        vbox.addLayout(grid)

        def fmt_percent(val: float | None) -> str:
            try:
                return f"{float(val):.1f}%"
            except (TypeError, ValueError):
                return "N/A"

        def fmt_seconds(val: float | None) -> str:
            try:
                return f"{float(val):.3f}"
            except (TypeError, ValueError):
                return "N/A"

        def build_cell(label_text: str, value_text: str) -> QtWidgets.QWidget:
            widget = QtWidgets.QWidget()
            inner = QtWidgets.QVBoxLayout()
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(12)
            widget.setLayout(inner)

            label_lbl = QtWidgets.QLabel(label_text)
            label_font = QtGui.QFont()
            label_font.setPointSize(56)
            label_font.setBold(True)
            label_lbl.setFont(label_font)
            label_lbl.setAlignment(QtCore.Qt.AlignLeft)

            value_lbl = QtWidgets.QLabel(value_text)
            value_font = QtGui.QFont()
            value_font.setPointSize(80)
            value_font.setBold(True)
            value_lbl.setFont(value_font)
            value_lbl.setAlignment(QtCore.Qt.AlignLeft)

            inner.addWidget(label_lbl)
            inner.addWidget(value_lbl)
            return widget

        grid.addWidget(build_cell(self.t("result_go_hit"), fmt_percent(metrics.get("go_hit_percent"))), 0, 0)
        grid.addWidget(
            build_cell(self.t("result_nogo_commission"), fmt_percent(metrics.get("nogo_commission_percent"))),
            0,
            1,
        )
        grid.addWidget(
            build_cell(self.t("result_mean_rt_go"), fmt_seconds(metrics.get("mean_rt_go_hit"))),
            1,
            0,
        )
        grid.addWidget(
            build_cell(
                self.t("result_mean_rt_nogo"),
                fmt_seconds(metrics.get("mean_rt_nogo_commission")),
            ),
            1,
            1,
        )

        vbox.addStretch()

        layout.addWidget(container, alignment=QtCore.Qt.AlignCenter)
        self.result_widget = container
        self.setFocus()
        self.activateWindow()
        self.raise_()

    def finish_experiment(self) -> None:
        if self.experiment_aborted:
            return
        end_abs, end_rel = self.stopwatch.timestamp_pair()
        self.log["timing_absolute"]["experiment_end"] = end_abs
        self.log["timing_relative"]["experiment_end"] = end_rel
        self.log["status"]["completed"] = True
        play_notification_async("end_sequence")
        QtCore.QTimer.singleShot(0, self.show_results_screen)

    def abort_experiment(self, reason: str) -> None:
        if self.experiment_aborted:
            return
        self.experiment_aborted = True
        self.clear_timers()
        abort_time_abs, abort_time_rel = self.stopwatch.timestamp_pair()
        self.log["status"]["completed"] = False
        self.log["status"]["abort_reason"] = reason
        self.log["status"]["abort_time_absolute"] = abort_time_abs
        self.log["status"]["abort_time_relative"] = abort_time_rel
        self.log["timing_absolute"]["experiment_end"] = abort_time_abs
        self.log["timing_relative"]["experiment_end"] = abort_time_rel
        play_notification_async("end_sequence")
        QtCore.QTimer.singleShot(0, self.show_results_screen)

    def emit_and_close(self) -> None:
        self.experiment_finished.emit(self.log)
        self.hide()
        self.close()
        self.deleteLater()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if self.showing_results:
            if event.key() == QtCore.Qt.Key_Escape:
                self.emit_and_close()
                event.accept()
            return
        if event.key() == QtCore.Qt.Key_Escape:
            self.abort_experiment(self.t("abort_by_user"))
            event.accept()
            return
        if event.key() == QtCore.Qt.Key_Space:
            if not self.in_response_window or self.response_recorded:
                return
            response_time_abs, response_time_rel = self.stopwatch.timestamp_pair()
            if self.response_timer:
                self.response_timer.stop()
            if self.stimulus_timer:
                self.stimulus_timer.stop()
            self.set_blank_screen()
            self.record_trial_outcome(response_time_abs, response_time_rel, pressed=True)
            self.response_recorded = True
            self.in_response_window = False
            self.start_next_trial()
            event.accept()
            return
        super().keyPressEvent(event)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Go/No-Go Task Controller")
        self.setWindowIcon(get_app_icon(ICON_PATH))
        self.language = "en"
        self.runner = None
        self.build_ui()
        self.update_language()
        self.status_label.setText("")

    def t(self, key: str) -> str:
        return translate(TRANSLATIONS, self.language, key)

    def build_ui(self) -> None:
        central = QtWidgets.QWidget()
        root_layout = QtWidgets.QVBoxLayout()
        central.setLayout(root_layout)
        self.setCentralWidget(central)

        header_layout = QtWidgets.QHBoxLayout()
        self.language_label = QtWidgets.QLabel(self.t("language"))
        lang_label_font = QtGui.QFont(self.language_label.font())
        lang_label_font.setBold(True)
        self.language_label.setFont(lang_label_font)
        self.lang_en_btn = QtWidgets.QPushButton(translate(TRANSLATIONS, "en", "language_en"))
        self.lang_en_btn.setCheckable(True)
        self.lang_zh_btn = QtWidgets.QPushButton(translate(TRANSLATIONS, "zh", "language_zh"))
        self.lang_zh_btn.setCheckable(True)
        self.lang_button_group = QtWidgets.QButtonGroup(self)
        self.lang_button_group.setExclusive(True)
        self.lang_button_group.addButton(self.lang_en_btn)
        self.lang_button_group.addButton(self.lang_zh_btn)
        self.lang_en_btn.clicked.connect(lambda: self.set_language("en"))
        self.lang_zh_btn.clicked.connect(lambda: self.set_language("zh"))
        self.lang_en_btn.setChecked(True)
        header_layout.addWidget(self.language_label)
        header_layout.addWidget(self.lang_en_btn)
        header_layout.addWidget(self.lang_zh_btn)
        header_layout.addStretch()
        self.test_mode_checkbox = QtWidgets.QCheckBox(self.t("test_mode"))
        self.test_mode_checkbox.stateChanged.connect(self.update_summary)
        header_layout.addWidget(self.test_mode_checkbox)
        root_layout.addLayout(header_layout)

        main_layout = QtWidgets.QGridLayout()
        main_layout.setHorizontalSpacing(12)
        main_layout.setVerticalSpacing(6)
        root_layout.addLayout(main_layout)

        self.go_checkboxes: Dict[int, QtWidgets.QCheckBox] = {}
        self.nogo_checkboxes: Dict[int, QtWidgets.QCheckBox] = {}
        self.weight_spinboxes: Dict[int, QtWidgets.QDoubleSpinBox] = {}

        self.digits_group = QtWidgets.QGroupBox()
        digits_layout = QtWidgets.QVBoxLayout()
        self.digits_group.setLayout(digits_layout)

        self.go_box = QtWidgets.QGroupBox()
        go_layout = QtWidgets.QGridLayout()
        self.go_box.setLayout(go_layout)
        for i in range(10):
            cb = QtWidgets.QCheckBox(str(i))
            cb.setChecked(i != 9)
            cb.toggled.connect(lambda state, d=i: self.on_go_toggled(d, state))
            self.go_checkboxes[i] = cb
            go_layout.addWidget(cb, i // 5, i % 5)

        self.nogo_box = QtWidgets.QGroupBox()
        nogo_layout = QtWidgets.QGridLayout()
        self.nogo_box.setLayout(nogo_layout)
        for i in range(10):
            cb = QtWidgets.QCheckBox(str(i))
            cb.setChecked(i == 9)
            cb.toggled.connect(lambda state, d=i: self.on_nogo_toggled(d, state))
            self.nogo_checkboxes[i] = cb
            nogo_layout.addWidget(cb, i // 5, i % 5)

        self.weight_box = QtWidgets.QGroupBox()
        weight_layout = QtWidgets.QGridLayout()
        self.weight_box.setLayout(weight_layout)
        for i in range(10):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setRange(0.0, 9999.0)
            spin.setSingleStep(0.1)
            spin.setValue(1.0)
            spin.valueChanged.connect(self.update_summary)
            self.weight_spinboxes[i] = spin
            weight_layout.addWidget(QtWidgets.QLabel(str(i)), i // 5, (i % 5) * 2)
            weight_layout.addWidget(spin, i // 5, (i % 5) * 2 + 1)

        digits_layout.addWidget(self.go_box)
        digits_layout.addWidget(self.nogo_box)
        digits_layout.addWidget(self.weight_box)

        self.timing_box_a = QtWidgets.QGroupBox()
        timing_layout_a = QtWidgets.QVBoxLayout()
        timing_layout_a.setSpacing(8)
        self.timing_box_a.setLayout(timing_layout_a)

        self.timing_box_b = QtWidgets.QGroupBox()
        timing_layout_b = QtWidgets.QGridLayout()
        timing_layout_b.setHorizontalSpacing(20)
        timing_layout_b.setVerticalSpacing(10)
        self.timing_box_b.setLayout(timing_layout_b)

        self.paradigm_name_edit = QtWidgets.QLineEdit("GoNoGo")
        self.paradigm_name_edit.setMinimumWidth(320)
        self.paradigm_name_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.paradigm_name_edit.textChanged.connect(self.update_summary)
        self.output_folder_edit = QtWidgets.QLineEdit(str(Path.cwd()))
        self.output_folder_edit.setMinimumWidth(320)
        self.output_folder_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.output_folder_edit.setReadOnly(True)
        self.output_browse_btn = QtWidgets.QPushButton("...")
        self.output_browse_btn.clicked.connect(self.choose_output_folder)
        output_folder_widget = QtWidgets.QWidget()
        output_layout = QtWidgets.QHBoxLayout()
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_folder_edit)
        output_layout.addWidget(self.output_browse_btn)
        output_folder_widget.setLayout(output_layout)

        self.n_blocks_spin = QtWidgets.QSpinBox()
        self.n_blocks_spin.setMinimum(1)
        self.n_blocks_spin.setValue(4)
        self.n_blocks_spin.valueChanged.connect(self.update_summary)
        self.trials_per_block_spin = QtWidgets.QSpinBox()
        self.trials_per_block_spin.setMinimum(1)
        self.trials_per_block_spin.setValue(75)
        self.trials_per_block_spin.valueChanged.connect(self.update_summary)

        self.rest_duration_spin = QtWidgets.QDoubleSpinBox()
        self.rest_duration_spin.setDecimals(2)
        self.rest_duration_spin.setRange(0.0, 9999.0)
        self.rest_duration_spin.setValue(10.0)
        self.rest_duration_spin.valueChanged.connect(self.update_summary)
        self.post_rest_spin = QtWidgets.QDoubleSpinBox()
        self.post_rest_spin.setDecimals(2)
        self.post_rest_spin.setRange(0.0, 9999.0)
        self.post_rest_spin.setValue(10.0)
        self.post_rest_spin.valueChanged.connect(self.update_summary)
        self.ibi_spin = QtWidgets.QDoubleSpinBox()
        self.ibi_spin.setDecimals(2)
        self.ibi_spin.setRange(0.0, 9999.0)
        self.ibi_spin.setValue(30.0)
        self.ibi_spin.valueChanged.connect(self.update_summary)
        self.stim_duration_spin = QtWidgets.QDoubleSpinBox()
        self.stim_duration_spin.setDecimals(2)
        self.stim_duration_spin.setRange(0.01, 9999.0)
        self.stim_duration_spin.setValue(0.3)
        self.stim_duration_spin.valueChanged.connect(self.update_summary)
        self.iti_spin = QtWidgets.QDoubleSpinBox()
        self.iti_spin.setDecimals(2)
        self.iti_spin.setRange(0.0, 9999.0)
        self.iti_spin.setValue(1.0)
        self.iti_spin.valueChanged.connect(self.update_summary)
        self.max_response_spin = QtWidgets.QDoubleSpinBox()
        self.max_response_spin.setDecimals(2)
        self.max_response_spin.setRange(0.01, 9999.0)
        self.max_response_spin.setValue(0.8)
        self.max_response_spin.valueChanged.connect(self.update_summary)

        self.label_blocks = QtWidgets.QLabel(self.t("blocks"))
        self.label_trials_per_block = QtWidgets.QLabel(self.t("trials_per_block"))
        self.label_rest = QtWidgets.QLabel(self.t("rest_duration"))
        self.label_post_rest = QtWidgets.QLabel(self.t("post_block_rest"))
        self.label_ibi = QtWidgets.QLabel(self.t("inter_block_interval"))
        self.label_stim = QtWidgets.QLabel(self.t("stimulus_duration"))
        self.label_iti = QtWidgets.QLabel(self.t("inter_trial_interval"))
        self.label_max_resp = QtWidgets.QLabel(self.t("max_response_window"))
        self.label_paradigm = QtWidgets.QLabel(self.t("paradigm_name"))
        self.label_output = QtWidgets.QLabel(self.t("output_folder"))
        for lbl in [self.label_paradigm, self.label_output, self.label_blocks, self.label_trials_per_block]:
            lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        paradigm_grid = QtWidgets.QGridLayout()
        paradigm_grid.setContentsMargins(0, 0, 0, 0)
        paradigm_grid.setHorizontalSpacing(10)
        paradigm_grid.setVerticalSpacing(8)
        paradigm_grid.addWidget(self.label_paradigm, 0, 0, alignment=QtCore.Qt.AlignLeft)
        paradigm_grid.addWidget(self.paradigm_name_edit, 0, 1)
        paradigm_grid.addWidget(self.label_output, 1, 0, alignment=QtCore.Qt.AlignLeft)
        paradigm_grid.addWidget(output_folder_widget, 1, 1)
        blocks_row = QtWidgets.QWidget()
        blocks_row_layout = QtWidgets.QHBoxLayout()
        blocks_row_layout.setContentsMargins(0, 0, 0, 0)
        blocks_row_layout.setSpacing(8)
        blocks_row.setLayout(blocks_row_layout)
        blocks_row_layout.addWidget(self.label_blocks)
        blocks_row_layout.addWidget(self.n_blocks_spin)
        blocks_row_layout.addSpacing(12)
        blocks_row_layout.addWidget(self.label_trials_per_block)
        blocks_row_layout.addWidget(self.trials_per_block_spin)
        blocks_row_layout.addStretch()
        paradigm_grid.addWidget(blocks_row, 2, 0, 1, 2)
        paradigm_grid.setColumnStretch(0, 0)
        paradigm_grid.setColumnStretch(1, 1)
        timing_layout_a.addLayout(paradigm_grid)

        timing_layout_b.addWidget(self.label_ibi, 0, 0)
        timing_layout_b.addWidget(self.ibi_spin, 0, 1)
        timing_layout_b.addWidget(self.label_rest, 1, 0)
        timing_layout_b.addWidget(self.rest_duration_spin, 1, 1)
        timing_layout_b.addWidget(self.label_post_rest, 2, 0)
        timing_layout_b.addWidget(self.post_rest_spin, 2, 1)
        timing_layout_b.addWidget(self.label_stim, 0, 2)
        timing_layout_b.addWidget(self.stim_duration_spin, 0, 3)
        timing_layout_b.addWidget(self.label_iti, 1, 2)
        timing_layout_b.addWidget(self.iti_spin, 1, 3)
        timing_layout_b.addWidget(self.label_max_resp, 2, 2)
        timing_layout_b.addWidget(self.max_response_spin, 2, 3)

        self.notes_box = QtWidgets.QGroupBox()
        notes_layout = QtWidgets.QVBoxLayout()
        notes_layout.setContentsMargins(6, 6, 6, 6)
        self.notes_box.setLayout(notes_layout)
        self.notes_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.notes_edit = QtWidgets.QTextEdit()
        self.notes_edit.setPlaceholderText(self.t("notes_placeholder"))
        self.notes_edit.setMinimumHeight(60)
        self.notes_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        notes_layout.addWidget(self.notes_edit)

        self.preview_group = QtWidgets.QGroupBox(self.t("digits_preview"))
        preview_grid = QtWidgets.QGridLayout()
        self.preview_group.setLayout(preview_grid)
        self.preview_header_labels: List[QtWidgets.QLabel] = []
        is_windows = sys.platform.startswith("win")
        cell_width = 52 if is_windows else 38
        cell_height = 36 if is_windows else 28
        cell_margin = 2 if is_windows else 4
        left_margin = 14 if is_windows else 4  # nudge heatmap right on Windows
        preview_grid.setAlignment(QtCore.Qt.AlignLeft)
        preview_grid.setContentsMargins(left_margin, 4, 4, 4)
        preview_grid.setHorizontalSpacing(6 if is_windows else 4)
        preview_grid.setVerticalSpacing(4 if is_windows else 2)
        base_point = self.font().pointSize()
        base_point = base_point if base_point > 0 else 10
        cell_point = base_point + (2 if is_windows else 0)
        header_point = cell_point + 1
        header_font_template = QtGui.QFont(self.font())
        header_font_template.setPointSize(header_point)
        header_font_template.setBold(True)
        cell_font_template = QtGui.QFont(self.font())
        cell_font_template.setPointSize(cell_point)
        row_label_width = cell_width + 120 if is_windows else cell_width + 60
        preview_grid.addWidget(QtWidgets.QLabel(""), 0, 0)
        for d in range(10):
            lbl = QtWidgets.QLabel(str(d))
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setFont(header_font_template)
            lbl.setFixedSize(cell_width, cell_height)
            self.preview_header_labels.append(lbl)
            preview_grid.addWidget(lbl, 0, d + 1)
        self.sum_lbl = QtWidgets.QLabel(self.t("sum"))
        self.sum_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.sum_lbl.setFont(cell_font_template)
        self.sum_lbl.setFixedSize(cell_width, cell_height)
        preview_grid.addWidget(self.sum_lbl, 0, 11)
        self.preview_row_labels = {
            "go": QtWidgets.QLabel(self.t("go_digits")),
            "nogo": QtWidgets.QLabel(self.t("nogo_digits")),
        }
        self.preview_row_labels["go"].setFixedWidth(row_label_width)
        self.preview_row_labels["nogo"].setFixedWidth(row_label_width)
        preview_grid.addWidget(self.preview_row_labels["go"], 1, 0)
        preview_grid.addWidget(self.preview_row_labels["nogo"], 2, 0)
        self.preview_cells: Dict[Tuple[str, int], QtWidgets.QLabel] = {}
        for row_name, row_idx in (("go", 1), ("nogo", 2)):
            for d in range(10):
                cell = QtWidgets.QLabel("0.00")
                cell.setAlignment(QtCore.Qt.AlignCenter)
                cell.setMargin(cell_margin)
                cell.setFont(cell_font_template)
                cell.setAutoFillBackground(True)
                cell.setFixedSize(cell_width, cell_height)
                self.preview_cells[(row_name, d)] = cell
                preview_grid.addWidget(cell, row_idx, d + 1)
        # Sum column with stacked bars
        self.sum_bar_go = QtWidgets.QLabel("0%")
        self.sum_bar_nogo = QtWidgets.QLabel("0%")
        self.sum_bar_go.setAlignment(QtCore.Qt.AlignCenter)
        self.sum_bar_nogo.setAlignment(QtCore.Qt.AlignCenter)
        self.sum_bar_go.setFont(cell_font_template)
        self.sum_bar_nogo.setFont(cell_font_template)
        self.sum_bar_go.setStyleSheet("background-color: green; color: white;")
        self.sum_bar_nogo.setStyleSheet("background-color: red; color: white;")
        self.sum_container = QtWidgets.QWidget()
        self.sum_layout = QtWidgets.QVBoxLayout()
        self.sum_layout.setContentsMargins(2, 2, 2, 2)
        self.sum_layout.setSpacing(2)
        self.sum_layout.addWidget(self.sum_bar_go, stretch=50)
        self.sum_layout.addWidget(self.sum_bar_nogo, stretch=50)
        self.sum_container.setLayout(self.sum_layout)
        self.sum_container.setFixedWidth(cell_width)
        preview_grid.addWidget(self.sum_container, 1, 11, 2, 1)
        right_top_layout = QtWidgets.QVBoxLayout()
        right_top_layout.addWidget(self.timing_box_a)
        right_top_layout.addWidget(self.timing_box_b)
        right_top_layout.addWidget(self.preview_group)
        right_top_layout.addStretch()

        self.start_button = QtWidgets.QPushButton()
        self.start_button.clicked.connect(self.start_experiment)
        self.reset_button = QtWidgets.QPushButton()
        self.reset_button.clicked.connect(self.reset_defaults)
        btn_font = self.start_button.font()
        btn_font.setPointSize(btn_font.pointSize() + 4)
        btn_font.setBold(True)
        self.start_button.setFont(btn_font)
        self.reset_button.setFont(btn_font)
        self.status_label = QtWidgets.QLabel()
        status_font = self.status_label.font()
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        self.status_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.addStretch()
        controls_layout.addWidget(self.start_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.reset_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.status_label)
        controls_layout.addStretch()
        main_layout.addWidget(self.digits_group, 0, 0)
        main_layout.addWidget(self.notes_box, 1, 0)
        main_layout.addLayout(right_top_layout, 0, 1)
        main_layout.addLayout(controls_layout, 1, 1)
        main_layout.setColumnStretch(0, 2)
        main_layout.setColumnStretch(1, 1)
        main_layout.setRowStretch(0, 0)
        main_layout.setRowStretch(1, 1)

        version_label = QtWidgets.QLabel("mojack  v1.0.0")
        self.statusBar().addPermanentWidget(version_label)

        for gb in [
            self.digits_group,
            self.go_box,
            self.nogo_box,
            self.weight_box,
            self.timing_box_a,
            self.timing_box_b,
            self.notes_box,
            self.preview_group,
        ]:
            set_groupbox_title_font(gb, 12)

        self.apply_mutex_constraints()
        self.update_summary()

    def update_language(self) -> None:
        self.setWindowTitle("Go/No-Go Task Controller")
        self.start_button.setText(self.t("start"))
        self.reset_button.setText(self.t("reset"))
        self.statusBar().showMessage("")
        self.digits_group.setTitle(self.t("digits_section"))
        self.go_box.setTitle(self.t("go_digits"))
        self.nogo_box.setTitle(self.t("nogo_digits"))
        self.weight_box.setTitle(self.t("digit_weights"))
        self.timing_box_a.setTitle(self.t("timing_part_a"))
        self.timing_box_b.setTitle(self.t("timing_part_b"))
        self.notes_box.setTitle(self.t("notes"))
        self.notes_edit.setPlaceholderText(self.t("notes_placeholder"))
        self.language_label.setText(self.t("language"))
        self.lang_en_btn.setText(translate(TRANSLATIONS, "en", "language_en"))
        self.lang_zh_btn.setText(translate(TRANSLATIONS, "zh", "language_zh"))
        self.lang_en_btn.setChecked(self.language == "en")
        self.lang_zh_btn.setChecked(self.language == "zh")
        self.test_mode_checkbox.setText(self.t("test_mode"))
        self.label_blocks.setText(self.t("blocks"))
        self.label_trials_per_block.setText(self.t("trials_per_block"))
        self.label_paradigm.setText(self.t("paradigm_name"))
        self.label_output.setText(self.t("output_folder"))
        self.label_rest.setText(self.t("rest_duration"))
        self.label_post_rest.setText(self.t("post_block_rest"))
        self.label_ibi.setText(self.t("inter_block_interval"))
        self.label_stim.setText(self.t("stimulus_duration"))
        self.label_iti.setText(self.t("inter_trial_interval"))
        self.label_max_resp.setText(self.t("max_response_window"))
        self.preview_group.setTitle(self.t("digits_preview"))
        self.preview_row_labels["go"].setText(self.t("go_digits"))
        self.preview_row_labels["nogo"].setText(self.t("nogo_digits"))
        if hasattr(self, "sum_lbl"):
            self.sum_lbl.setText(self.t("sum"))
        self.update_summary()

    def update_sum_bar(self, go_frac: float, nogo_frac: float) -> None:
        go_frac = max(0.0, min(1.0, go_frac))
        nogo_frac = max(0.0, min(1.0, nogo_frac))
        total = go_frac + nogo_frac
        if total > 0:
            go_frac /= total
            nogo_frac /= total
        go_percent = go_frac * 100
        nogo_percent = nogo_frac * 100
        if hasattr(self, "sum_layout"):
            self.sum_layout.setStretch(0, max(1, int(go_percent)))
            self.sum_layout.setStretch(1, max(1, int(nogo_percent)))
        self.sum_bar_go.setText(f"{go_percent:.1f}")
        self.sum_bar_nogo.setText(f"{nogo_percent:.1f}")
        self.sum_bar_go.setToolTip(f"Go: {go_percent:.1f}%")
        self.sum_bar_nogo.setToolTip(f"No-Go: {nogo_percent:.1f}%")

    def set_language(self, lang: str) -> None:
        if lang not in TRANSLATIONS:
            return
        self.language = lang
        self.update_language()

    def choose_output_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, self.t("output_folder"), self.output_folder_edit.text() or str(Path.cwd()))
        if folder:
            self.output_folder_edit.setText(folder)
            self.update_summary()

    def apply_mutex_constraints(self) -> None:
        for d in range(10):
            go_cb = self.go_checkboxes[d]
            nogo_cb = self.nogo_checkboxes[d]
            if go_cb.isChecked():
                nogo_cb.setEnabled(False)
            elif nogo_cb.isChecked():
                go_cb.setEnabled(False)
            else:
                go_cb.setEnabled(True)
                nogo_cb.setEnabled(True)

    def collect_digits(self) -> Tuple[List[int], List[int]]:
        go_digits = [d for d, cb in self.go_checkboxes.items() if cb.isChecked()]
        nogo_digits = [d for d, cb in self.nogo_checkboxes.items() if cb.isChecked()]
        return go_digits, nogo_digits

    def on_go_toggled(self, digit: int, checked: bool) -> None:
        partner = self.nogo_checkboxes[digit]
        if checked:
            partner.blockSignals(True)
            partner.setChecked(False)
            partner.blockSignals(False)
            partner.setEnabled(False)
        else:
            partner.setEnabled(True)
        self.update_summary()

    def on_nogo_toggled(self, digit: int, checked: bool) -> None:
        partner = self.go_checkboxes[digit]
        if checked:
            partner.blockSignals(True)
            partner.setChecked(False)
            partner.blockSignals(False)
            partner.setEnabled(False)
        else:
            partner.setEnabled(True)
        self.update_summary()

    def gather_config(self, include_schedule: bool = True) -> Dict:
        go_digits, nogo_digits = self.collect_digits()
        digit_weights = {d: self.weight_spinboxes[d].value() for d in range(10)}

        config = {
            "go_digits": go_digits,
            "nogo_digits": nogo_digits,
            "digit_weights": digit_weights,
            "paradigm_name": self.paradigm_name_edit.text().strip() or "GoNoGo",
            "output_folder": self.output_folder_edit.text().strip() or str(Path.cwd()),
            "n_blocks": self.n_blocks_spin.value(),
            "n_trials_per_block": self.trials_per_block_spin.value(),
            "rest_duration_s": self.rest_duration_spin.value(),
            "post_block_rest_duration_s": self.post_rest_spin.value(),
            "inter_block_interval_s": self.ibi_spin.value(),
            "stimulus_duration_s": self.stim_duration_spin.value(),
            "inter_trial_interval_s": self.iti_spin.value(),
            "max_response_window_s": self.max_response_spin.value(),
            "test_mode": self.test_mode_checkbox.isChecked(),
            "fullscreen": True,
            "trial_schedule": {},
        }
        if include_schedule:
            config["trial_schedule"] = self.build_trial_schedule(config)
        return config

    def viridis_color(self, value: float) -> Tuple[int, int, int]:
        # Clamp and interpolate over simplified viridis stops
        stops = [
            (68, 1, 84),
            (59, 82, 139),
            (33, 145, 140),
            (94, 201, 98),
            (253, 231, 37),
        ]
        t = max(0.0, min(1.0, value))
        scaled = t * (len(stops) - 1)
        idx = int(scaled)
        frac = scaled - idx
        if idx >= len(stops) - 1:
            return stops[-1]
        c1 = stops[idx]
        c2 = stops[idx + 1]
        r = int(c1[0] + (c2[0] - c1[0]) * frac)
        g = int(c1[1] + (c2[1] - c1[1]) * frac)
        b = int(c1[2] + (c2[2] - c1[2]) * frac)
        return r, g, b

    def set_preview_cell(self, row_name: str, digit: int, prob: float, max_prob: float) -> None:
        cell = self.preview_cells.get((row_name, digit))
        if not cell:
            return
        norm = prob / max_prob if max_prob > 0 else 0.0
        r, g, b = self.viridis_color(norm)
        cell.setText(f"{prob*100:.1f}")
        cell.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); color: {'black' if (r*0.299+g*0.587+b*0.114)>186 else 'white'};"
        )

    def build_trial_schedule(self, config: Dict) -> Dict[int, List[Dict]]:
        ratio = compute_go_ratio(config["go_digits"], config["nogo_digits"], config["digit_weights"])
        config["go_ratio"] = ratio
        schedule: Dict[int, List[Dict]] = {}
        for block_idx in range(1, config["n_blocks"] + 1):
            schedule[block_idx] = generate_trial_schedule(
                go_digits=config["go_digits"],
                nogo_digits=config["nogo_digits"],
                digit_weights=config["digit_weights"],
                go_ratio=ratio,
                n_trials_per_block=config["n_trials_per_block"],
            )
        return schedule

    def gather_meta(self) -> Dict:
        notes_raw = self.notes_edit.toPlainText()
        lines = [ln.strip() for ln in notes_raw.splitlines() if ln.strip()]
        patient_info = lines[0] if lines else ""
        electrode_info = lines[1] if len(lines) > 1 else ""
        meta = {
            "patient_info": patient_info,
            "electrode_info": electrode_info,
            "notes_raw": notes_raw,
            "language": self.language,
            "operator": "",
            "software_version": "v1.0.0",
            "author": "mojack",
        }
        return meta

    def validate_config(self, config: Dict) -> bool:
        go_digits = config["go_digits"]
        nogo_digits = config["nogo_digits"]
        if not go_digits:
            self.show_error(self.t("validation_failed"), "Go digits cannot be empty.")
            return False
        if not nogo_digits:
            self.show_error(self.t("validation_failed"), "No-Go digits cannot be empty.")
            return False
        overlap = set(go_digits) & set(nogo_digits)
        if overlap:
            self.show_error(self.t("validation_failed"), f"Overlapping digits: {sorted(overlap)}")
            return False
        go_weights = [config["digit_weights"][d] for d in go_digits if config["digit_weights"][d] > 0]
        nogo_weights = [config["digit_weights"][d] for d in nogo_digits if config["digit_weights"][d] > 0]
        if not go_weights:
            self.show_error(self.t("validation_failed"), "Go digit weights must be > 0.")
            return False
        if not nogo_weights:
            self.show_error(self.t("validation_failed"), "No-Go digit weights must be > 0.")
            return False
        if not config.get("output_folder"):
            self.show_error(self.t("validation_failed"), "Output folder is required.")
            return False
        if config["n_trials_per_block"] <= 0 or config["n_blocks"] <= 0:
            self.show_error(self.t("validation_failed"), "Blocks and trials must be positive.")
            return False
        durations = [
            config["rest_duration_s"],
            config["post_block_rest_duration_s"],
            config["inter_block_interval_s"],
            config["stimulus_duration_s"],
            config["inter_trial_interval_s"],
            config["max_response_window_s"],
        ]
        if any(v < 0 for v in durations):
            self.show_error(self.t("validation_failed"), "Durations must be non-negative.")
            return False
        try:
            compute_go_ratio(go_digits, nogo_digits, config["digit_weights"])
        except ValueError as exc:
            self.show_error(self.t("validation_failed"), str(exc))
            return False
        return True

    def show_error(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, title, message, QtWidgets.QMessageBox.Ok)

    def start_experiment(self) -> None:
        try:
            config = self.gather_config(include_schedule=False)
        except ValueError as exc:
            self.show_error(self.t("error"), str(exc))
            return
        if not self.validate_config(config):
            return
        try:
            config["trial_schedule"] = self.build_trial_schedule(config)
        except ValueError as exc:
            self.show_error(self.t("error"), str(exc))
            return
        meta = self.gather_meta()
        self.runner = ExperimentRunner(config=config, meta=meta, language=self.language)
        self.runner.experiment_finished.connect(self.handle_experiment_finished)
        self.runner.show()
        play_notification_async("start_sequence")
        self.status_label.setText(self.t("running_block").format(n=1))
        self.start_button.setEnabled(False)
        self.reset_button.setEnabled(False)

    def handle_experiment_finished(self, log: Dict) -> None:
        self.runner = None
        self.start_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        completed = log.get("status", {}).get("completed", False)
        self.status_label.setText(self.t("completed") if completed else self.t("aborted"))
        if not log["config"].get("test_mode", False):
            paradigm_name = log["config"].get("paradigm_name", "GoNoGo") or "GoNoGo"
            start_time_abs = log.get("timing_absolute", {}).get("experiment_start")
            dt_for_ts = start_time_abs if isinstance(start_time_abs, datetime) else None
            try:
                filename = build_timestamped_path(
                    folder=log["config"].get("output_folder", "."),
                    prefix=paradigm_name,
                    dt=dt_for_ts,
                    suffix="pkl",
                )
                save_pickle(log, filename)
                QtWidgets.QMessageBox.information(
                    self,
                    self.t("ok"),
                    self.t("file_saved").format(path=str(filename)),
                )
            except Exception as exc:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.t("error"),
                    self.t("file_save_failed").format(error=str(exc)),
                )
        self.update_summary()

    def reset_defaults(self) -> None:
        for i in range(10):
            go_cb = self.go_checkboxes[i]
            nogo_cb = self.nogo_checkboxes[i]
            go_cb.blockSignals(True)
            nogo_cb.blockSignals(True)
            go_cb.setEnabled(True)
            nogo_cb.setEnabled(True)
            go_cb.setChecked(i != 9)
            nogo_cb.setChecked(i == 9)
            go_cb.blockSignals(False)
            nogo_cb.blockSignals(False)
        for spin in self.weight_spinboxes.values():
            spin.setValue(1.0)
        self.n_blocks_spin.setValue(4)
        self.trials_per_block_spin.setValue(75)
        self.rest_duration_spin.setValue(10.0)
        self.post_rest_spin.setValue(10.0)
        self.ibi_spin.setValue(30.0)
        self.stim_duration_spin.setValue(0.3)
        self.iti_spin.setValue(1.0)
        self.max_response_spin.setValue(0.8)
        self.paradigm_name_edit.setText("GoNoGo")
        self.output_folder_edit.setText(str(Path.cwd()))
        self.test_mode_checkbox.setChecked(False)
        self.notes_edit.clear()
        self.apply_mutex_constraints()
        self.update_summary()

    def update_summary(self) -> None:
        go_digits, nogo_digits = self.collect_digits()
        weights = {d: self.weight_spinboxes[d].value() for d in range(10)}
        try:
            ratio_val = compute_go_ratio(go_digits, nogo_digits, weights)
        except ValueError:
            ratio_val = None

        go_total = sum(weights[d] for d in go_digits if weights[d] > 0)
        nogo_total = sum(weights[d] for d in nogo_digits if weights[d] > 0)

        go_probs = []
        nogo_probs = []
        for d in range(10):
            if ratio_val is None or go_total <= 0:
                go_p = 0.0
            else:
                go_p = (weights[d] / go_total) * ratio_val if d in go_digits and weights[d] > 0 else 0.0
            if ratio_val is None or nogo_total <= 0:
                nogo_p = 0.0
            else:
                nogo_p = (
                    (weights[d] / nogo_total) * (1 - ratio_val)
                    if d in nogo_digits and weights[d] > 0
                    else 0.0
                )
            go_probs.append(go_p)
            nogo_probs.append(nogo_p)

        max_prob = max(go_probs + nogo_probs) if (go_probs + nogo_probs) else 0.0
        max_prob = max_prob if max_prob > 0 else 1.0

        for d in range(10):
            self.set_preview_cell("go", d, go_probs[d], max_prob)
            self.set_preview_cell("nogo", d, nogo_probs[d], max_prob)

        # Update sum column bar
        go_total_prob = sum(go_probs)
        nogo_total_prob = sum(nogo_probs)
        total = go_total_prob + nogo_total_prob
        go_frac = go_total_prob / total if total > 0 else 0.0
        nogo_frac = nogo_total_prob / total if total > 0 else 0.0
        self.update_sum_bar(go_frac, nogo_frac)


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(get_app_icon(ICON_PATH))
    window = MainWindow()
    window.resize(1200, 600)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

# %%
