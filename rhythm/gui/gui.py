from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from core.audio import play_beep as play_rhythm_beep, play_notification_sound
from core.config import DEFAULT_AUTHOR, ParameterState, RHYTHM_VERSION
from core.fileio import build_timestamped_path, ensure_directory, save_pickle, timestamp_string
from core.timing import Stopwatch, format_countdown_text, run_blocking_countdown
from core.utils import get_app_icon, set_groupbox_title_font, translate

VERSION = RHYTHM_VERSION
AUTHOR = DEFAULT_AUTHOR
ICON_PATH = Path(__file__).resolve().parents[1] / "icon" / "icon.png"

PART_KEYS = ["rest_pre", "cued_movement", "rest_instruction", "internal_movement", "rest_post"]


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "app_title": {"en": "Rhythmic Movement Task", "zh": "节律运动任务"},
    "paradigm_name": {"en": "Paradigm Name", "zh": "范式名称"},
    "language_en": {"en": "English", "zh": "English"},
    "language_zh": {"en": "中文", "zh": "中文"},
    "test_mode": {"en": "Test mode", "zh": "测试模式"},
    "cue_type": {"en": "Cue type", "zh": "提示类型"},
    "cue_frequency": {"en": "Cue frequency (Hz)", "zh": "提示频率 (Hz)"},
    "cue_tone": {"en": "Audio tone (Hz)", "zh": "提示音频率 (Hz)"},
    "cue_on_time": {"en": "Cue on-time (ms)", "zh": "提示持续 (毫秒)"},
    "cue_audio": {"en": "Audio", "zh": "音频"},
    "cue_visual": {"en": "Visual", "zh": "视觉"},
    "visual_color": {"en": "Visual color", "zh": "颜色"},
    "visual_radius": {"en": "Visual radius (px)", "zh": "半径 (像素)"},
    "num_blocks": {"en": "Number of blocks", "zh": "区块数量"},
    "inter_block_interval": {"en": "Inter-block interval (s)", "zh": "区块间隔 (秒)"},
    "block_structure": {"en": "Block structure", "zh": "区块结构"},
    "rest_pre": {"en": "Pre-block rest (s)", "zh": "区块前休息 (秒)"},
    "cued_movement": {"en": "External guidance (s)", "zh": "外部提示 (秒)"},
    "rest_instruction": {"en": "Intra-block rest (s)", "zh": "区块内休息 (秒)"},
    "internal_movement": {"en": "Internal generation (s)", "zh": "内部运动 (秒)"},
    "rest_post": {"en": "Post-block rest (s)", "zh": "区块后休息 (秒)"},
    "output_folder": {"en": "Output folder", "zh": "输出文件夹"},
    "browse": {"en": "Browse…", "zh": "浏览…"},
    "notes": {"en": "Notes", "zh": "备注"},
    "preview_cue": {"en": "Preview cue", "zh": "预览提示"},
    "cue_settings": {"en": "Cue settings", "zh": "提示设置"},
    "timeline_preview": {"en": "Timeline preview", "zh": "时间线预览"},
    "block_rest_prompt": {"en": "Block {n} finished.\nPlease rest.", "zh": "第 {n} 段结束。\n请休息。"},
    "language_label": {"en": "Language", "zh": "语言"},
    "status_ready": {"en": "Ready", "zh": "就绪"},
    "status_running": {"en": "Running…", "zh": "运行中…"},
    "status_completed": {"en": "Completed", "zh": "完成"},
    "status_aborted": {"en": "Aborted (ESC)", "zh": "已终止 (ESC)"},
    "validation_error": {"en": "Validation error", "zh": "校验错误"},
    "log_not_ready": {"en": "No completed run to export.", "zh": "没有可导出的运行。"},
    "test_mode_no_export": {"en": "Cannot export in test mode.", "zh": "测试模式下不导出。"},
    "log_saved": {"en": "Log saved to", "zh": "日志已保存到"},
    "instruction_rest": {"en": "Rest", "zh": "休息"},
    "instruction_cued": {"en": "Follow the cue", "zh": "跟随提示运动"},
    "instruction_internal": {"en": "Move according to \nthe previous rhythm", "zh": "按刚才的\n节奏运动"},
    "start_label": {"en": "Start", "zh": "开始"},
    "end_label": {"en": "End", "zh": "结束"},
    "mojack_version": {"en": "mojack  v1.0.0", "zh": "mojack  v1.0.0"},
    "global_settings": {"en": "Global settings", "zh": "全局设置"},
    "notes_placeholder": {"en": "Patient info / Electrode info / Notes", "zh": "患者信息 / 电极信息 / 备注"},
    "start_button": {"en": "Start", "zh": "开始"},
    "reset_button": {"en": "Reset", "zh": "重置"},
}


def tr(key: str, lang: str) -> str:
    return translate(TRANSLATIONS, lang, key)


class Logger:
    def __init__(self, params: ParameterState) -> None:
        self.meta: Dict[str, object] = {
            "version": VERSION,
            "author": AUTHOR,
            "language": params.language,
            "test_mode": params.test_mode,
            "paradigm_name": params.paradigm_name,
            "created_at_iso": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:23],
        }
        self.params_dict = params.to_dict()
        self.notes = params.notes
        self.timeline_absolute: Dict[str, object] = {}
        self.timeline_relative: Dict[str, object] = {}
        self.status: Dict[str, object] = {"completed": False, "stopped_early": False, "reason": "not_started"}
        self.stopwatch: Optional[Stopwatch] = None
        self.t0_perf: Optional[float] = None
        self.t0_datetime: Optional[datetime] = None

    def start_paradigm(self) -> None:
        self.stopwatch = Stopwatch()
        self.t0_perf = self.stopwatch.start_perf
        self.t0_datetime = self.stopwatch.start_datetime
        start_str = self.t0_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")[:23]
        self.timeline_absolute["paradigm_start"] = start_str
        self.timeline_relative["paradigm_start_ms"] = 0

    def mark_paradigm_end(self) -> None:
        absolute_str, relative_ms = self.get_timestamp_pair()
        self.timeline_absolute["paradigm_end"] = absolute_str
        self.timeline_relative["paradigm_end_ms"] = relative_ms

    def get_timestamp_pair(self) -> Tuple[str, int]:
        if self.stopwatch is None:
            self.start_paradigm()
        now_dt, rel_seconds = self.stopwatch.timestamp_pair() if self.stopwatch else (datetime.now(), 0.0)
        absolute_str = now_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:23]
        relative_ms = int(rel_seconds * 1000)
        return absolute_str, relative_ms

    def init_blocks(self, num_blocks: int) -> None:
        self.timeline_absolute["blocks"] = []
        self.timeline_relative["blocks"] = []
        for idx in range(num_blocks):
            abs_block = {
                "block_index": idx,
                "block_start": None,
                "parts": {k: {} for k in PART_KEYS},
                "cue_events": {k: [] for k in PART_KEYS},
                "interval_after_block": {},
            }
            rel_block = {
                "block_index": idx,
                "block_start_ms": None,
                "parts": {k: {} for k in PART_KEYS},
                "cue_events_ms": {k: [] for k in PART_KEYS},
                "interval_after_block_ms": {},
            }
            self.timeline_absolute["blocks"].append(abs_block)
            self.timeline_relative["blocks"].append(rel_block)

    def mark_block_start(self, block_index: int) -> None:
        absolute_str, relative_ms = self.get_timestamp_pair()
        self.timeline_absolute["blocks"][block_index]["block_start"] = absolute_str
        self.timeline_relative["blocks"][block_index]["block_start_ms"] = relative_ms

    def mark_part_start(self, block_index: int, part_key: str, planned_duration_s: float) -> None:
        absolute_str, relative_ms = self.get_timestamp_pair()
        self.timeline_absolute["blocks"][block_index]["parts"][part_key]["start_absolute"] = absolute_str
        self.timeline_absolute["blocks"][block_index]["parts"][part_key]["planned_duration_s"] = planned_duration_s
        self.timeline_relative["blocks"][block_index]["parts"][part_key]["start_relative_ms"] = relative_ms
        self.timeline_relative["blocks"][block_index]["parts"][part_key]["planned_duration_s"] = planned_duration_s

    def log_cue_event(self, block_index: int, part_key: str) -> None:
        absolute_str, relative_ms = self.get_timestamp_pair()
        self.timeline_absolute["blocks"][block_index]["cue_events"][part_key].append(absolute_str)
        self.timeline_relative["blocks"][block_index]["cue_events_ms"][part_key].append(relative_ms)

    def mark_interval_start(self, block_index: int, interval_s: float) -> None:
        absolute_str, relative_ms = self.get_timestamp_pair()
        self.timeline_absolute["blocks"][block_index]["interval_after_block"]["start_absolute"] = absolute_str
        self.timeline_absolute["blocks"][block_index]["interval_after_block"]["planned_duration_s"] = interval_s
        self.timeline_relative["blocks"][block_index]["interval_after_block_ms"]["start_relative_ms"] = relative_ms
        self.timeline_relative["blocks"][block_index]["interval_after_block_ms"]["planned_duration_s"] = interval_s

    def set_status_completed(self) -> None:
        self.status["completed"] = True
        self.status["stopped_early"] = False
        self.status["reason"] = "normal_end"

    def set_status_aborted(self) -> None:
        absolute_str, relative_ms = self.get_timestamp_pair()
        self.status["completed"] = False
        self.status["stopped_early"] = True
        self.status["reason"] = "esc_pressed"
        self.status["stop_absolute"] = absolute_str
        self.status["stop_relative_ms"] = relative_ms

    def build_log_dict(self) -> dict:
        return {
            "meta": self.meta,
            "notes": self.notes,
            "params": self.params_dict,
            "timeline_absolute": self.timeline_absolute,
            "timeline_relative": self.timeline_relative,
            "status": self.status,
        }

    def save_to_pkl(self, path: str) -> None:
        ensure_directory(Path(path).parent)
        save_pickle(self.build_log_dict(), path)


class StimulusWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.visual_cue_visible = False
        self.visual_color = QtGui.QColor("#FFFFFF")
        self.visual_radius = 60
        self.current_text: str = ""
        self.multi_lines: Optional[list[str]] = None
        self.show_countdown_box = False
        self.countdown_box_size: Optional[QtCore.QSize] = None
        self.text_font = QtGui.QFont()
        self.text_font.setPointSize(164)
        self.text_font.setBold(True)
        self.rest_font = QtGui.QFont(self.text_font)
        self.rest_font.setPointSize(360)
        self.rest_font.setBold(True)
        self.mid_font = QtGui.QFont(self.text_font)
        self.mid_font.setPointSize(164)
        self.mid_font.setBold(True)
        self.display_font = QtGui.QFont(self.text_font)
        self.multi_font = QtGui.QFont(self.rest_font)
        self.on_abort_requested: Optional[Callable[[], None]] = None
        self.setWindowTitle("Stimulus")
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAutoFillBackground(False)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

    def sizeHint(self) -> QtCore.QSize:  # pragma: no cover - GUI sizing
        return QtCore.QSize(800, 600)

    def set_visual_cue_style(self, color_hex: str, radius_px: int) -> None:
        self.visual_color = QtGui.QColor(color_hex)
        self.visual_radius = max(5, radius_px)
        self.update()

    def set_visual_cue_visible(self, visible: bool) -> None:
        self.visual_cue_visible = visible
        self.update()

    def set_instruction(self, text: str, use_rest_font: bool = False, use_mid_font: bool = False) -> None:
        self.current_text = text
        self.multi_lines = None
        self.show_countdown_box = False
        self.countdown_box_size = None
        if use_mid_font:
            self.display_font = self.mid_font
        elif use_rest_font:
            self.display_font = self.rest_font
        else:
            self.display_font = self.text_font
        self.update()

    def set_instruction_with_countdown(self, message: str, countdown_text: str, font_choice: str = "rest") -> None:
        """Set multi-line message + countdown using chosen font ('rest'|'mid'|'text') and monospace countdown."""
        self.multi_lines = []
        for part in message.replace("<br>", "\n").split("\n"):
            if part.strip():
                self.multi_lines.append(part.strip())
        if countdown_text.strip():
            self.multi_lines.append(countdown_text.strip())
        self.current_text = ""
        self.show_countdown_box = False
        self.countdown_box_size = None
        if font_choice == "mid":
            self.multi_font = self.mid_font
        elif font_choice == "text":
            self.multi_font = self.text_font
        else:
            self.multi_font = self.rest_font
        self.display_font = self.multi_font
        self.update()

    def set_instruction_boxed(self, text: str, max_text: Optional[str] = None) -> None:
        self.current_text = text
        self.show_countdown_box = True
        metrics = QtGui.QFontMetrics(self.text_font)
        target = max_text or text
        rect = metrics.boundingRect(target)
        width = int(rect.width() * 1.2)
        height = int(rect.height() * 1.2)
        self.countdown_box_size = QtCore.QSize(max(1, width), max(1, height))
        self.update()

    def clear_to_black(self) -> None:
        self.current_text = ""
        self.multi_lines = None
        self.visual_cue_visible = False
        self.show_countdown_box = False
        self.countdown_box_size = None
        self.display_font = self.text_font
        self.update()

    def show_start_screen(self, duration_ms: int, text: str = "Start") -> None:
        self.current_text = text
        self.show_countdown_box = False
        self.display_font = self.rest_font
        self.showFullScreen()
        self.grabKeyboard()
        self.update()
        QtCore.QTimer.singleShot(duration_ms, self.clear_to_black)

    def show_end_screen(self, duration_ms: int, text: str = "End") -> None:
        self.current_text = text
        self.show_countdown_box = False
        self.display_font = self.rest_font
        self.visual_cue_visible = False
        self.update()
        QtCore.QTimer.singleShot(duration_ms, self._hide_after_end)

    def _hide_after_end(self) -> None:
        self.clear_to_black()
        self.releaseKeyboard()
        self.hide()

    def set_abort_callback(self, callback: Callable[[], None]) -> None:
        self.on_abort_requested = callback

    def keyPressEvent(self, event) -> None:  # pragma: no cover - GUI event
        if event.key() == QtCore.Qt.Key_Escape:
            if self.on_abort_requested:
                self.on_abort_requested()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # pragma: no cover - GUI paint
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtCore.Qt.black)

        if self.visual_cue_visible:
            painter.setBrush(self.visual_color)
            painter.setPen(QtCore.Qt.NoPen)
            center = self.rect().center()
            painter.drawEllipse(center, self.visual_radius, self.visual_radius)

        if self.current_text:
            painter.setPen(QtCore.Qt.white)
            painter.setFont(self.display_font)
            text_rect = painter.fontMetrics().boundingRect(self.rect(), QtCore.Qt.AlignCenter, self.current_text)
            if self.show_countdown_box:
                if self.countdown_box_size:
                    box_w = self.countdown_box_size.width()
                    box_h = self.countdown_box_size.height()
                    center = self.rect().center()
                    boxed = QtCore.QRect(
                        center.x() - box_w // 2,
                        center.y() - box_h // 2,
                        box_w,
                        box_h,
                    )
                else:
                    boxed = text_rect.adjusted(-16, -10, 16, 10)
                pen = painter.pen()
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawRect(boxed)
                painter.setPen(QtCore.Qt.white)
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, self.current_text)
        elif self.multi_lines:
            # Draw multi-line message + countdown, centered
            lines = self.multi_lines
            spacing = 20
            base_font = self.multi_font
            fm_base = QtGui.QFontMetrics(base_font)
            mono_font = QtGui.QFont("Courier New")
            mono_font.setPointSize(base_font.pointSize())
            mono_font.setBold(True)
            fm_mono = QtGui.QFontMetrics(mono_font)
            heights = []
            for idx, line in enumerate(lines):
                fm = fm_mono if idx == len(lines) - 1 else fm_base
                heights.append(fm.height())
            total_height = sum(heights) + spacing * (len(lines) - 1)
            y = (self.height() - total_height) // 2
            for idx, line in enumerate(lines):
                fm = fm_mono if idx == len(lines) - 1 else fm_base
                font = mono_font if idx == len(lines) - 1 else base_font
                painter.setFont(font)
                painter.setPen(QtCore.Qt.white)
                w = fm.horizontalAdvance(line)
                x = (self.width() - w) // 2
                y += fm.ascent()
                painter.drawText(x, y, line)
                y += (fm.height() - fm.ascent()) + spacing


class ParadigmRunner(QtCore.QObject):
    def __init__(self, params: ParameterState, logger: Logger, stimulus_window: StimulusWindow, parent=None) -> None:
        super().__init__(parent)
        self.params = params
        self.logger = logger
        self.stimulus_window = stimulus_window
        self.abort_requested = False

    def request_abort(self) -> None:
        """Abort the paradigm and immediately hide the fullscreen window.

        MODIFIED: clear screen and hide window as soon as ESC is pressed.
        """
        self.abort_requested = True
        self.stimulus_window.clear_to_black()
        self.stimulus_window.hide()
        self.stimulus_window.close()
        self.stimulus_window.deleteLater()
        self.stimulus_window.releaseKeyboard()
        QtWidgets.QApplication.processEvents()

    def run(self) -> None:
        self.abort_requested = False
        self.logger.start_paradigm()
        self.logger.init_blocks(self.params.num_blocks)

        self.stimulus_window.set_visual_cue_style(self.params.visual_color_hex, self.params.visual_radius_px)
        self.stimulus_window.set_abort_callback(self.request_abort)
        self.stimulus_window.showFullScreen()
        play_notification_sound(self.params.start_sound_type)
        self.stimulus_window.show_start_screen(800, tr("start_label", self.params.language))
        self._wait_with_abort(0.8)

        for block_index in range(self.params.num_blocks):
            if self.abort_requested:
                break
            self.logger.mark_block_start(block_index)
            self._run_block(block_index)
            if self.abort_requested:
                break
            if block_index < self.params.num_blocks - 1:
                self.logger.mark_interval_start(block_index, self.params.inter_block_interval_s)
                rest_msg = tr("block_rest_prompt", self.params.language).format(n=block_index + 1)
                self._wait_with_countdown(self.params.inter_block_interval_s, rest_msg)

        self.logger.mark_paradigm_end()
        if self.abort_requested:
            self.logger.set_status_aborted()
        else:
            self.logger.set_status_completed()
            play_notification_sound(self.params.end_sound_type)
            self.stimulus_window.show_end_screen(800, tr("end_label", self.params.language))
            self._wait_with_abort(0.8)
        self.stimulus_window.clear_to_black()
        self.stimulus_window.hide()
        self.stimulus_window.close()
        self.stimulus_window.deleteLater()

    def _run_block(self, block_index: int) -> None:
        for part_key in PART_KEYS:
            if self.abort_requested:
                break
            duration_s = self.params.part_durations_s.get(part_key, 0)
            self.logger.mark_part_start(block_index, part_key, duration_s)
            self._run_part(part_key, block_index, duration_s)

    def _run_part(self, part_key: str, block_index: int, duration_s: float) -> None:
        if part_key == "cued_movement":
            self.stimulus_window.set_instruction(tr("instruction_cued", self.params.language), use_mid_font=True)
            self._run_cue_train(block_index, part_key, duration_s)
        elif part_key == "internal_movement":
            self.stimulus_window.set_instruction(tr("instruction_internal", self.params.language), use_mid_font=True)
            self._wait_with_abort(duration_s)
        else:
            self.stimulus_window.set_instruction(tr("instruction_rest", self.params.language), use_rest_font=True)
            self._wait_with_abort(duration_s)
        self.stimulus_window.set_visual_cue_visible(False)
        QtWidgets.QApplication.processEvents()

    def _run_cue_train(self, block_index: int, part_key: str, duration_s: float) -> None:
        if self.params.cue_frequency_hz <= 0:
            self._wait_with_abort(duration_s)
            return

        period_s = 1.0 / self.params.cue_frequency_hz
        start_time = time.perf_counter()
        next_cue_time = start_time

        while time.perf_counter() - start_time < duration_s:
            if self.abort_requested:
                break
            now = time.perf_counter()
            if now >= next_cue_time:
                self._trigger_cue(block_index, part_key)
                next_cue_time += period_s
            time.sleep(0.001)
            QtWidgets.QApplication.processEvents()
        self.stimulus_window.set_visual_cue_visible(False)

    def _trigger_cue(self, block_index: int, part_key: str) -> None:
        self.logger.log_cue_event(block_index, part_key)
        if self.params.cue_type == "audio":
            play_rhythm_beep(self.params.cue_tone_hz, self.params.cue_on_time_ms)
        else:  # visual
            self.stimulus_window.set_visual_cue_visible(True)
            QtCore.QTimer.singleShot(self.params.cue_on_time_ms, lambda: self.stimulus_window.set_visual_cue_visible(False))

    def _wait_with_abort(self, duration_s: float) -> None:
        end_time = time.perf_counter() + duration_s
        while time.perf_counter() < end_time:
            if self.abort_requested:
                break
            time.sleep(0.01)
            QtWidgets.QApplication.processEvents()

    def _wait_with_countdown(self, duration_s: float, rest_text: str | None = None) -> None:
        lang = self.params.language
        if rest_text is None:
            rest_text = tr("instruction_rest", lang)
        max_countdown_text = f"{duration_s:06.3f}s"
        metrics = QtGui.QFontMetrics(self.stimulus_window.rest_font)
        min_width = metrics.boundingRect(max_countdown_text).width() + 40

        def on_tick(ms_left: int) -> None:
            countdown_str = f"{ms_left/1000:06.3f}s"
            self.stimulus_window.set_instruction_with_countdown(rest_text, countdown_str, font_choice="text")
            self.stimulus_window.setMinimumWidth(min_width)
            QtWidgets.QApplication.processEvents()

        def on_finished() -> None:
            self.stimulus_window.set_instruction(rest_text, use_rest_font=True)

        run_blocking_countdown(
            duration_s=duration_s,
            on_tick=on_tick,
            on_finished=on_finished,
            check_abort=lambda: self.abort_requested,
            step_s=0.01,
        )


class TimelinePreviewWidget(QtWidgets.QWidget):
    def __init__(self, params: ParameterState, parent=None) -> None:
        super().__init__(parent)
        self.params = params
        self.part_colors = {
            "rest_pre": QtGui.QColor("#4A5568"),
            "cued_movement": QtGui.QColor("#2B6CB0"),
            "rest_instruction": QtGui.QColor("#718096"),
            "internal_movement": QtGui.QColor("#38A169"),
            "rest_post": QtGui.QColor("#A0AEC0"),
        }
        self.setMinimumHeight(60)
        self.setMinimumWidth(600)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def set_parameters(self, params: ParameterState) -> None:
        self.params = params
        self.update()

    def paintEvent(self, event) -> None:  # pragma: no cover - GUI paint
        painter = QtGui.QPainter(self)
        total_block_duration = sum(self.params.part_durations_s.values())
        total_block_duration += self.params.inter_block_interval_s
        if total_block_duration <= 0:
            return
        width = self.rect().width()
        height = self.rect().height()
        block_height = max(30, height - 5)
        y = 10
        x = 10
        for part_key in PART_KEYS:
            part_dur = self.params.part_durations_s.get(part_key, 0)
            w = int((part_dur / total_block_duration) * (width - 20))
            h = int(block_height - 20)
            rect = QtCore.QRect(int(x), int(y), max(1, w), max(1, h))
            painter.fillRect(rect, self.part_colors[part_key])
            painter.setPen(QtCore.Qt.black)
            painter.drawRect(rect)
            duration_text = f"{part_dur:.1f}"
            painter.setPen(QtCore.Qt.white)
            painter.drawText(rect, QtCore.Qt.AlignCenter, duration_text)
            x += w
        interval_w = int((self.params.inter_block_interval_s / total_block_duration) * (width - 20))
        interval_rect = QtCore.QRect(int(x), int(y), max(1, interval_w), max(1, int(block_height - 20)))
        painter.fillRect(interval_rect, QtGui.QColor("#1a202c"))
        painter.setPen(QtCore.Qt.black)
        painter.drawRect(interval_rect)
        painter.setPen(QtCore.Qt.white)
        painter.drawText(interval_rect, QtCore.Qt.AlignCenter, f"{self.params.inter_block_interval_s:.1f}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.params = ParameterState.from_defaults()
        self.last_logger: Optional[Logger] = None
        self.last_params: Optional[ParameterState] = None
        self.current_status_key = "status_ready"
        self._preview_overlay: Optional[StimulusWindow] = None
        self.timeline_widget = TimelinePreviewWidget(self.params)
        self.status_label = QtWidgets.QLabel(tr("status_ready", self.params.language))
        self.test_mode_checkbox_top: Optional[QtWidgets.QCheckBox] = None

        self._build_ui()
        self.test_mode_checkbox_top.setChecked(self.params.test_mode)
        self.update_language()

    @property
    def language(self) -> str:
        return self.params.language

    def t(self, key: str) -> str:
        return tr(key, self.params.language)

    def _build_ui(self) -> None:
        self.setWindowTitle(tr("app_title", self.params.language))
        self.setWindowIcon(get_app_icon(ICON_PATH))
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root_layout = QtWidgets.QVBoxLayout(central)

        # Top bar
        top_bar = QtWidgets.QHBoxLayout()
        self.language_label = QtWidgets.QLabel(tr("language_label", self.params.language))
        self.language_en_button = QtWidgets.QPushButton(tr("language_en", "en"))
        self.language_zh_button = QtWidgets.QPushButton(tr("language_zh", "zh"))
        self.language_en_button.setCheckable(True)
        self.language_zh_button.setCheckable(True)
        self.language_en_button.clicked.connect(lambda: self.set_language("en"))
        self.language_zh_button.clicked.connect(lambda: self.set_language("zh"))
        top_bar.addWidget(self.language_label)
        top_bar.addWidget(self.language_en_button)
        top_bar.addWidget(self.language_zh_button)
        top_bar.addStretch()
        self.test_mode_checkbox_top = QtWidgets.QCheckBox(tr("test_mode", self.params.language))
        self.test_mode_checkbox_top.stateChanged.connect(self.sync_test_mode)
        top_bar.addWidget(self.test_mode_checkbox_top)
        root_layout.addLayout(top_bar)

        main_grid = QtWidgets.QGridLayout()
        root_layout.addLayout(main_grid)

        # Global settings spanning two columns
        global_group = QtWidgets.QGroupBox(tr("global_settings", self.params.language))
        global_layout = QtWidgets.QFormLayout()
        self.paradigm_name_edit = QtWidgets.QLineEdit("Rhythm")
        self.paradigm_name_edit.setMinimumWidth(420)
        self.paradigm_name_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.output_folder_edit = QtWidgets.QLineEdit(self.params.output_folder)
        self.output_folder_edit.setMinimumWidth(420)
        self.output_folder_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.output_folder_button = QtWidgets.QPushButton("...")
        self.output_folder_button.setFixedWidth(32)
        self.output_folder_button.clicked.connect(self.choose_output_folder)
        output_line = QtWidgets.QHBoxLayout()
        output_line.setContentsMargins(0, 0, 0, 0)
        output_line.addWidget(self.output_folder_edit)
        output_line.addWidget(self.output_folder_button)
        output_widget = QtWidgets.QWidget()
        output_widget.setLayout(output_line)
        global_layout.addRow(QtWidgets.QLabel(tr("paradigm_name", self.params.language)), self.paradigm_name_edit)
        global_layout.addRow(QtWidgets.QLabel(tr("output_folder", self.params.language)), output_widget)
        global_group.setLayout(global_layout)
        main_grid.addWidget(global_group, 0, 0, 1, 2)

        # Timeline preview spanning two columns
        preview_group = QtWidgets.QGroupBox(tr("timeline_preview", self.params.language))
        pv_layout = QtWidgets.QVBoxLayout()
        pv_layout.addWidget(self.timeline_widget)
        preview_group.setLayout(pv_layout)
        main_grid.addWidget(preview_group, 1, 0, 1, 2)

        # Block structure (left)
        block_group = QtWidgets.QGroupBox(tr("block_structure", self.params.language))
        block_layout = QtWidgets.QGridLayout()
        self.num_blocks_spin = QtWidgets.QSpinBox()
        self.num_blocks_spin.setRange(1, 100)
        self.num_blocks_spin.setValue(4)
        self.num_blocks_spin.valueChanged.connect(self.update_timeline_preview)
        self.inter_block_spin = QtWidgets.QDoubleSpinBox()
        self.inter_block_spin.setRange(0, 600)
        self.inter_block_spin.setValue(30.0)
        self.inter_block_spin.valueChanged.connect(self.update_timeline_preview)
        entries = [("num_blocks", self.num_blocks_spin), ("inter_block_interval", self.inter_block_spin)]
        self.part_spinboxes: Dict[str, QtWidgets.QDoubleSpinBox] = {}
        defaults = {
            "rest_pre": 10.0,
            "cued_movement": 30.0,
            "rest_instruction": 5.0,
            "internal_movement": 30.0,
            "rest_post": 10.0,
        }
        for key in PART_KEYS:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0, 600)
            spin.setSingleStep(0.5)
            spin.setValue(defaults.get(key, self.params.part_durations_s.get(key, 0)))
            spin.valueChanged.connect(self.update_timeline_preview)
            self.part_spinboxes[key] = spin
            entries.append((key, spin))
        for row, (key, widget) in enumerate(entries):
            block_layout.addWidget(QtWidgets.QLabel(tr(key, self.params.language)), row, 0)
            block_layout.addWidget(widget, row, 1)
        block_group.setLayout(block_layout)
        main_grid.addWidget(block_group, 2, 0)

        # Right column stack: Cue settings, Notes, Controls
        cue_group = QtWidgets.QGroupBox(tr("cue_settings", self.params.language))
        cue_layout = QtWidgets.QGridLayout()
        self.cue_type_combo = QtWidgets.QComboBox()
        self.cue_type_combo.addItem(tr("cue_audio", self.params.language), "audio")
        self.cue_type_combo.addItem(tr("cue_visual", self.params.language), "visual")
        idx = self.cue_type_combo.findData(self.params.cue_type)
        if idx >= 0:
            self.cue_type_combo.setCurrentIndex(idx)
        self.cue_freq_spin = QtWidgets.QDoubleSpinBox()
        self.cue_freq_spin.setRange(0.1, 10.0)
        self.cue_freq_spin.setSingleStep(0.1)
        self.cue_freq_spin.setValue(self.params.cue_frequency_hz)
        self.cue_freq_spin.valueChanged.connect(self.update_timeline_preview)
        self.cue_tone_spin = QtWidgets.QDoubleSpinBox()
        self.cue_tone_spin.setRange(100, 4000)
        self.cue_tone_spin.setSingleStep(10)
        self.cue_tone_spin.setValue(self.params.cue_tone_hz)
        self.cue_on_time_spin = QtWidgets.QSpinBox()
        self.cue_on_time_spin.setRange(10, 2000)
        self.cue_on_time_spin.setValue(self.params.cue_on_time_ms)
        self.visual_color_edit = QtWidgets.QLineEdit(self.params.visual_color_hex)
        self.visual_color_button = QtWidgets.QPushButton("🎨")
        self.visual_color_button.clicked.connect(self.choose_color)
        self.visual_radius_spin = QtWidgets.QSpinBox()
        self.visual_radius_spin.setRange(5, 500)
        self.visual_radius_spin.setValue(self.params.visual_radius_px)
        self.preview_button = QtWidgets.QPushButton(tr("preview_cue", self.params.language))
        self.preview_button.clicked.connect(self.preview_cue)

        cue_layout.addWidget(QtWidgets.QLabel(tr("cue_type", self.params.language)), 0, 0)
        cue_layout.addWidget(self.cue_type_combo, 0, 1)
        cue_layout.addWidget(QtWidgets.QLabel(tr("cue_frequency", self.params.language)), 1, 0)
        cue_layout.addWidget(self.cue_freq_spin, 1, 1)
        cue_layout.addWidget(QtWidgets.QLabel(tr("cue_on_time", self.params.language)), 2, 0)
        cue_layout.addWidget(self.cue_on_time_spin, 2, 1)
        cue_layout.addWidget(QtWidgets.QLabel(tr("cue_tone", self.params.language)), 3, 0)
        tone_line = QtWidgets.QHBoxLayout()
        tone_line.setContentsMargins(0, 0, 0, 0)
        tone_line.addWidget(self.cue_tone_spin)
        tone_line.addWidget(self.preview_button)
        cue_layout.addLayout(tone_line, 3, 1)
        cue_layout.addWidget(QtWidgets.QLabel(tr("visual_color", self.params.language)), 4, 0)
        color_line = QtWidgets.QHBoxLayout()
        color_line.setContentsMargins(0, 0, 0, 0)
        color_line.addWidget(self.visual_color_edit)
        color_line.addWidget(self.visual_color_button)
        cue_layout.addLayout(color_line, 4, 1)
        cue_layout.addWidget(QtWidgets.QLabel(tr("visual_radius", self.params.language)), 5, 0)
        cue_layout.addWidget(self.visual_radius_spin, 5, 1)
        cue_group.setLayout(cue_layout)

        notes_group = QtWidgets.QGroupBox(tr("notes", self.params.language))
        notes_layout = QtWidgets.QVBoxLayout()
        self.notes_edit = QtWidgets.QTextEdit(self.params.notes)
        self.notes_edit.setPlaceholderText(tr("notes_placeholder", self.params.language))
        notes_layout.addWidget(self.notes_edit)
        notes_group.setLayout(notes_layout)

        right_stack = QtWidgets.QVBoxLayout()
        right_stack.addWidget(cue_group)
        right_stack.addWidget(notes_group)

        # Buttons and status
        self.start_button = QtWidgets.QPushButton(tr("start_button", self.params.language))
        self.reset_button = QtWidgets.QPushButton(tr("reset_button", self.params.language))
        self.start_button.clicked.connect(self.start_experiment)
        self.reset_button.clicked.connect(self.reset_defaults)
        btn_font = self.start_button.font()
        btn_font.setPointSize(btn_font.pointSize() + 4)
        btn_font.setBold(True)
        self.start_button.setFont(btn_font)
        self.reset_button.setFont(btn_font)

        self.status_label = QtWidgets.QLabel(tr("status_ready", self.params.language))
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
        right_stack.addLayout(controls_layout)

        main_grid.addLayout(right_stack, 2, 1)

        # Footer
        footer = QtWidgets.QHBoxLayout()
        self.signature_label = QtWidgets.QLabel(tr("mojack_version", self.params.language))
        footer.addStretch()
        footer.addWidget(self.signature_label)
        root_layout.addLayout(footer)

        # Apply groupbox title font similar to GoStop
        for gb in [global_group, preview_group, block_group, cue_group, notes_group]:
            set_groupbox_title_font(gb, 12)
        # Bolden labels inside group boxes similar to GoStop
        for lbl in self.findChildren(QtWidgets.QLabel):
            f = lbl.font()
            f.setBold(True)
            lbl.setFont(f)

    def set_language(self, lang: str) -> None:
        if lang not in ("en", "zh"):
            return
        self.params.language = lang
        self.language_en_button.setChecked(lang == "en")
        self.language_zh_button.setChecked(lang == "zh")
        self.update_language()

    def update_language(self) -> None:
        lang = self.params.language
        self.setWindowTitle(tr("app_title", lang))
        self.signature_label.setText(tr("mojack_version", lang))
        self.status_label.setText(tr(self.current_status_key, lang))
        self.output_folder_button.setText("...")
        self.preview_button.setText(tr("preview_cue", lang))
        self.start_button.setText(tr("start_button", lang))
        self.reset_button.setText(tr("reset_button", lang))
        self.notes_edit.setPlaceholderText(tr("notes_placeholder", lang))

        self.language_en_button.setText(tr("language_en", lang))
        self.language_zh_button.setText(tr("language_zh", lang))
        if hasattr(self, "language_label"):
            self.language_label.setText(tr("language_label", lang))
        self.test_mode_checkbox_top.setText(tr("test_mode", lang))
        self._update_cue_type_labels()
        self.update_group_titles()
        self.timeline_widget.set_parameters(self.gather_config(update_only=True))

    def _update_cue_type_labels(self) -> None:
        lang = self.params.language
        for idx in range(self.cue_type_combo.count()):
            data = self.cue_type_combo.itemData(idx)
            if data == "audio":
                self.cue_type_combo.setItemText(idx, tr("cue_audio", lang))
            elif data == "visual":
                self.cue_type_combo.setItemText(idx, tr("cue_visual", lang))

    def update_group_titles(self) -> None:
        lang = self.params.language
        for widget in self.findChildren(QtWidgets.QGroupBox):
            title = widget.title()
            for key in ["cue_settings", "block_structure", "timeline_preview", "global_settings", "notes"]:
                if title == tr(key, "en") or title == tr(key, "zh"):
                    widget.setTitle(tr(key, lang))
        self.update_form_labels()
        self.timeline_widget.set_parameters(self.gather_config(update_only=True))

    def update_form_labels(self) -> None:
        lang = self.params.language
        labels = self.centralWidget().findChildren(QtWidgets.QLabel)
        for lbl in labels:
            text = lbl.text()
            for key in [
                "paradigm_name",
                "num_blocks",
                "inter_block_interval",
                "cue_type",
                "cue_frequency",
                "cue_tone",
                "cue_on_time",
                "visual_color",
                "visual_radius",
                "output_folder",
                "notes",
                "rest_pre",
                "cued_movement",
                "rest_instruction",
                "internal_movement",
                "rest_post",
                "timeline_preview",
            ]:
                if text in (tr(key, "en"), tr(key, "zh")):
                    lbl.setText(tr(key, lang))

    def sync_test_mode(self) -> None:
        sender = self.sender()
        checked = bool(sender.isChecked()) if sender and hasattr(sender, "isChecked") else bool(self.params.test_mode)
        if self.test_mode_checkbox_top and sender is not self.test_mode_checkbox_top:
            self.test_mode_checkbox_top.blockSignals(True)
            self.test_mode_checkbox_top.setChecked(checked)
            self.test_mode_checkbox_top.blockSignals(False)
        self.params.test_mode = checked

    def choose_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.visual_color_edit.text()), self, "Select color")
        if color.isValid():
            self.visual_color_edit.setText(color.name())

    def choose_output_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, tr("output_folder", self.params.language), self.output_folder_edit.text()
        )
        if folder:
            self.output_folder_edit.setText(folder)

    def preview_cue(self) -> None:
        params = self.gather_config(update_only=True)
        if params.cue_type == "audio":
            play_rhythm_beep(params.cue_tone_hz, params.cue_on_time_ms)
        else:
            overlay = StimulusWindow()
            overlay.set_visual_cue_style(params.visual_color_hex, params.visual_radius_px)
            overlay.set_instruction("")
            overlay.show()
            overlay.set_visual_cue_visible(True)
            QtCore.QTimer.singleShot(params.cue_on_time_ms, overlay.close)
            self._preview_overlay = overlay

    def validate_config(self, params: ParameterState) -> Optional[str]:
        if params.cue_frequency_hz <= 0:
            return "Cue frequency must be > 0"
        if not params.visual_color_hex.startswith("#") or len(params.visual_color_hex) != 7:
            return "Visual color must be in #RRGGBB format"
        for key, val in params.part_durations_s.items():
            if val < 0:
                return f"Duration for {key} must be >= 0"
        if params.num_blocks <= 0:
            return "Number of blocks must be > 0"
        if params.inter_block_interval_s < 0:
            return "Inter-block interval must be >= 0"
        return None

    def gather_config(self, update_only: bool = False) -> ParameterState:
        params = ParameterState.from_defaults()
        params.paradigm_name = self.paradigm_name_edit.text()
        params.language = self.params.language
        params.test_mode = self.test_mode_checkbox_top.isChecked() if self.test_mode_checkbox_top else False
        params.cue_type = self.cue_type_combo.currentData() or self.cue_type_combo.currentText()
        params.cue_frequency_hz = float(self.cue_freq_spin.value())
        params.cue_tone_hz = float(self.cue_tone_spin.value())
        params.cue_on_time_ms = int(self.cue_on_time_spin.value())
        params.start_sound_type = self.params.start_sound_type
        params.end_sound_type = self.params.end_sound_type
        params.visual_color_hex = self.visual_color_edit.text()
        params.visual_radius_px = int(self.visual_radius_spin.value())
        params.num_blocks = int(self.num_blocks_spin.value())
        params.inter_block_interval_s = float(self.inter_block_spin.value())
        params.part_durations_s = {k: float(spin.value()) for k, spin in self.part_spinboxes.items()}
        params.output_folder = self.output_folder_edit.text()
        params.file_prefix = (params.paradigm_name or "").strip() or "Rhythm"
        params.notes = self.notes_edit.toPlainText()
        if not update_only:
            self.params = params
        return params

    def reset_defaults(self) -> None:
        self.paradigm_name_edit.setText("Rhythm")
        self.num_blocks_spin.setValue(4)
        self.output_folder_edit.setText(self.params.output_folder)
        self.inter_block_spin.setValue(30.0)
        defaults = {
            "rest_pre": 10.0,
            "cued_movement": 30.0,
            "rest_instruction": 5.0,
            "internal_movement": 30.0,
            "rest_post": 10.0,
        }
        for key, spin in self.part_spinboxes.items():
            spin.setValue(defaults.get(key, 0.0))
        self.cue_type_combo.setCurrentText(self.params.cue_type)
        self.cue_freq_spin.setValue(self.params.cue_frequency_hz)
        self.cue_tone_spin.setValue(self.params.cue_tone_hz)
        self.cue_on_time_spin.setValue(self.params.cue_on_time_ms)
        self.visual_color_edit.setText(self.params.visual_color_hex)
        self.visual_radius_spin.setValue(self.params.visual_radius_px)
        self.notes_edit.clear()
        self.status_label.setText(tr("status_ready", self.params.language))

    def start_experiment(self) -> None:
        params = self.gather_config()
        error = self.validate_config(params)
        if error:
            QtWidgets.QMessageBox.warning(self, tr("validation_error", params.language), error)
            return
        self.params = params
        self.timeline_widget.set_parameters(params)
        self.set_controls_enabled(False)
        self.current_status_key = "status_running"
        self.status_label.setText(tr(self.current_status_key, params.language))
        QtWidgets.QApplication.processEvents()

        logger = Logger(params)
        stim_window = StimulusWindow()
        runner = ParadigmRunner(params, logger, stim_window)
        runner.run()

        self.last_logger = logger
        self.last_params = params

        if logger.status.get("stopped_early"):
            self.current_status_key = "status_aborted"
        else:
            self.current_status_key = "status_completed"
        self.status_label.setText(tr(self.current_status_key, params.language))

        # NEW: auto-save log and show file path (if not in test mode)
        self.auto_save_log()

        self.set_controls_enabled(True)

    def auto_save_log(self) -> None:
        """Automatically save the last run log and show a message box.

        NEW: behavior similar to Go/No-Go example:
        - If test_mode is False: save pkl into output_folder with timestamped name.
        - Show an information dialog with the saved path.
        """
        if not self.last_logger or not self.last_params:
            return
        if self.last_params.test_mode:
            # In test mode we do not write any log file.
            return

        lang = self.params.language
        filename = build_timestamped_path(
            folder=self.last_params.output_folder or ".",
            prefix=self.last_params.file_prefix,
            suffix="pkl",
        )
        try:
            self.last_logger.save_to_pkl(str(filename))
            QtWidgets.QMessageBox.information(
                self,
                tr("export_log", lang),
                f"{tr('log_saved', lang)}\n{filename}",
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                tr("validation_error", lang),
                f"Failed to save log file:\n{exc}",
            )

    def set_controls_enabled(self, enabled: bool) -> None:
        for widget in [
            self.paradigm_name_edit,
            self.num_blocks_spin,
            self.inter_block_spin,
            self.cue_type_combo,
            self.cue_freq_spin,
            self.cue_tone_spin,
            self.cue_on_time_spin,
            self.visual_color_edit,
            self.visual_color_button,
            self.visual_radius_spin,
            self.output_folder_edit,
            self.output_folder_button,
            self.notes_edit,
        ]:
            widget.setEnabled(enabled)
        for spin in self.part_spinboxes.values():
            spin.setEnabled(enabled)
        self.preview_button.setEnabled(enabled)
        self.start_button.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)

    def update_timeline_preview(self) -> None:
        params = self.gather_config(update_only=True)
        self.timeline_widget.set_parameters(params)


def main() -> None:  # pragma: no cover - entry point
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(get_app_icon(ICON_PATH))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
