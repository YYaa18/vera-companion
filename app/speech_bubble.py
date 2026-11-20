"""对话气泡：在角色旁边显示它说的话。

语音不是随时能听到（静音、没戴耳机、环境吵），所以每句都同时显示成文字。
气泡透明、置顶、不吃鼠标事件，几秒后自动淡出。
"""
import math

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

BG = QColor(24, 27, 34, 238)
BORDER = QColor(95, 200, 245, 210)
FG = QColor(232, 240, 248)
DIM = QColor(150, 160, 175)

MAX_W = 420
PAD_X = 16
PAD_Y = 13
FONT_PX = 18
LABEL_PX = 13


# 字号档位：名字 -> (正文字号, 名字字号, 最大宽度)
SIZES = {
    "small": (15, 11, 360),
    "normal": (18, 13, 420),
    "large": (22, 15, 500),
    "huge": (26, 18, 580),
}
DEFAULT_SIZE = "normal"


def metrics_for(key):
    return SIZES.get(key) or SIZES[DEFAULT_SIZE]


class SpeechBubble(QWidget):
    """A rounded speech bubble that points at the character."""

    def __init__(self):
        super().__init__()
        # 不用 Qt.WindowTransparentForInput：那个标志会让窗口完全不进入
        # 事件循环，叠在角色上时会把角色的点击一起吃掉，
        # 表现就是"点一下之后就没反应了"。用属性做穿透即可。
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.text = ""
        self.label = ""
        self.tail_left = True     # 气泡尾巴朝左（角色在气泡左边）
        self.alpha = 0.0
        self.target_alpha = 0.0
        self.label_h = 0
        self.tail_h = 12

        # 尺寸档位可在设置里改，改完调用 apply_size()
        self.size_key = DEFAULT_SIZE
        self.font_px, self.label_px, self.max_w = metrics_for(self.size_key)
        self.pad_x = 16
        self.pad_y = 13

        self._font = QFont("Microsoft YaHei", 10)
        self._label_font = QFont("Microsoft YaHei", 8)
        self._apply_fonts()

        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self._fade_step)
        self.fade_timer.start(40)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out)

        self.hide()

    # ------------------------------------------------------------ content
    def _apply_fonts(self):
        self._font.setPixelSize(self.font_px)
        self._label_font.setPixelSize(self.label_px)

    def apply_size(self, key):
        """Switch size preset; takes effect on the next message."""
        if key == self.size_key and hasattr(self, "_font"):
            return
        self.size_key = key if key in SIZES else DEFAULT_SIZE
        self.font_px, self.label_px, self.max_w = metrics_for(self.size_key)
        self._apply_fonts()
        if self.text:
            self._relayout()
            self.update()

    def set_size(self, key):
        self.apply_size(key)

    def show_text(self, text, seconds=None, label="小蓝"):
        """Display a message; auto-hides after a duration based on its length."""
        text = (text or "").strip()
        if not text:
            return
        self.text = text
        self.label = label
        self._relayout()

        if seconds is None:
            # ~0.22s per character, clamped
            seconds = max(3.5, min(14.0, len(text) * 0.22 + 2.0))

        self.target_alpha = 1.0
        self.show()
        self.raise_()
        self.hide_timer.start(int(seconds * 1000))

    def fade_out(self):
        self.target_alpha = 0.0

    def bump(self, dx, dy):
        """Follow the character as it moves."""
        if self.isVisible():
            self.move(self.x() + dx, self.y() + dy)

    # ------------------------------------------------------------ layout
    def _relayout(self):
        fm = QFontMetrics(self._font)
        rect = fm.boundingRect(
            0, 0, self.max_w - self.pad_x * 2 - 4, 2000,
            int(Qt.TextWordWrap) | int(Qt.AlignLeft), self.text
        )
        text_w = max(60, min(self.max_w - self.pad_x * 2, rect.width()))
        text_h = rect.height()

        lfm = QFontMetrics(self._label_font)
        label_h = lfm.height() + 3 if self.label else 0

        self.w = text_w + self.pad_x * 2
        self.h = text_h + self.pad_y * 2 + label_h
        self.label_h = label_h
        self.tail_h = 12
        self.resize(int(self.w), int(self.h + self.tail_h))

    def place_near(self, pet_rect, screen_rect):
        """Put the bubble above the character, flipping sides near the screen edge."""
        w, h = self.width(), self.height()
        cx = pet_rect.center().x()
        x = cx - w // 2
        y = pet_rect.top() - h - 6

        if y < screen_rect.top() + 4:
            y = pet_rect.bottom() + 6            # 上方放不下就放下面
        x = max(screen_rect.left() + 4, min(x, screen_rect.right() - w - 4))

        self.tail_left = True
        self.move(int(x), int(y))

    # ------------------------------------------------------------ paint
    def _fade_step(self):
        step = 0.16
        if self.alpha < self.target_alpha:
            self.alpha = min(self.target_alpha, self.alpha + step)
        elif self.alpha > self.target_alpha:
            self.alpha = max(self.target_alpha, self.alpha - step)
            if self.alpha <= 0.01:
                self.hide()
        else:
            return
        self.setWindowOpacity(self.alpha)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        body_h = h - self.tail_h
        r = 12

        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, body_h - 1), r, r)

        # 尾巴：指向角色
        tail_x = w * 0.28 if self.tail_left else w * 0.72
        tail = QPainterPath()
        tail.moveTo(tail_x - 7, body_h - 1)
        tail.lineTo(tail_x, h - 1)
        tail.lineTo(tail_x + 7, body_h - 1)
        tail.closeSubpath()
        path = path.united(tail)

        p.setBrush(BG)
        p.setPen(QPen(BORDER, 1.2))
        p.drawPath(path)

        # 名字标签
        y = self.pad_y
        if self.label:
            p.setFont(self._label_font)
            p.setPen(QPen(BORDER))
            p.drawText(QRectF(self.pad_x, y, w - self.pad_x * 2, self.label_h),
                       int(Qt.AlignLeft | Qt.AlignVCenter), self.label)
            y += self.label_h

        # 正文
        p.setFont(self._font)
        p.setPen(QPen(FG))
        p.drawText(QRectF(self.pad_x, y, w - self.pad_x * 2, body_h - y - self.pad_y + 4),
                   int(Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop), self.text)
