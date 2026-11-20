"""桌面虚拟角色窗口：透明、无边框、置顶、可拖动、会自由走动。

屏幕上只有角色本身，没有面板、没有输入框。
双击角色开始/结束说话；拖动可以把它挪到别处。
"""
import math
import random

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

BODY_TOP = QColor("#5FC8F5")
BODY_BOT = QColor("#2A8CC4")
DARK = QColor("#1B3A4B")


class PetWindow(QWidget):
    """A frameless, transparent, always-on-top character that wanders and reacts."""

    clicked = Signal()
    dragged_done = Signal(QPoint)
    spoken = Signal()   # emitted when the user wants to talk
    right_clicked = Signal(QPoint)   # context menu fallback

    SIZE_ACTIVE = 200
    SIZE_IDLE = 150

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self.size_px = self.SIZE_IDLE
        self.resize(self.size_px, self.size_px)

        # animation state
        self.t = 0.0
        self.blink = 0.0
        self.mouth_open = 0.0
        self.state = "idle"          # idle | talking | listening | thinking
        self.facing = 1              # 1 right, -1 left

        # wandering
        self.wander = True
        self.drift = QPoint(0, 0)
        self.drift_ticks = 0

        # drag
        self._dragging = False
        self._press_pos = None
        self._win_pos = None
        self._moved = False
        self._speaking = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)

        self.wander_timer = QTimer(self)
        self.wander_timer.timeout.connect(self._pick_direction)
        self.wander_timer.start(2600)

        # idle blinks
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._maybe_blink)
        self.blink_timer.start(700)

    # ----------------------------------------------------------- behaviour
    def set_state(self, s):
        self.state = s
        target = self.SIZE_ACTIVE if s in ("talking", "listening", "thinking") else self.SIZE_IDLE
        if target != self.size_px:
            center = self.geometry().center()
            self.size_px = target
            self.resize(target, target)
            self.move(center.x() - target // 2, center.y() - target // 2)
        self.update()

    def set_wander(self, on):
        self.wander = on

    def _maybe_blink(self):
        if random.random() < 0.35:
            self.blink = 1.0

    def _pick_direction(self):
        if not self.wander or self.state != "idle" or self._dragging:
            self.drift = QPoint(0, 0)
            return
        if random.random() < 0.45:
            self.drift = QPoint(0, 0)
            return
        ang = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 1.4)
        self.drift = QPoint(round(math.cos(ang) * speed), round(math.sin(ang) * speed * 0.5))
        self.drift_ticks = random.randint(18, 46)
        if self.drift.x() != 0:
            self.facing = 1 if self.drift.x() > 0 else -1

    def _tick(self):
        self.t += 0.045
        if self.blink > 0:
            self.blink = max(0.0, self.blink - 0.13)
        if self.state == "talking":
            self.mouth_open = 0.5 + 0.5 * math.sin(self.t * 10)
        else:
            self.mouth_open = max(0.0, self.mouth_open - 0.12)

        # wander inside the screen
        if self.drift_ticks > 0 and self.drift != QPoint(0, 0) and not self._dragging:
            self.drift_ticks -= 1
            nx = self.x() + self.drift.x()
            ny = self.y() + self.drift.y()
            scr = self.screen().availableGeometry() if self.screen() else None
            if scr and (nx < scr.left() or nx + self.width() > scr.right()):
                self.drift = QPoint(-self.drift.x(), self.drift.y())
                self.facing *= -1
                nx = max(scr.left(), min(nx, scr.right() - self.width()))
            if scr and (ny < scr.top() or ny + self.height() > scr.bottom()):
                self.drift = QPoint(self.drift.x(), -self.drift.y())
                ny = max(scr.top(), min(ny, scr.bottom() - self.height()))
            self.move(nx, ny)
        self.update()

    # ----------------------------------------------------------- mouse
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._moved = False
            self._press_pos = e.globalPosition().toPoint()
            self._win_pos = self.pos()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
        elif e.button() == Qt.RightButton:
            # 右键立刻弹菜单；不进入拖拽状态
            self.right_clicked.emit(e.globalPosition().toPoint())
            e.accept()

    def mouseMoveEvent(self, e):
        if self._dragging:
            delta = e.globalPosition().toPoint() - self._press_pos
            if delta.manhattanLength() > 4:
                self._moved = True
            self.move(self._win_pos + delta)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(QCursor(Qt.OpenHandCursor))
            if self._moved:
                self.dragged_done.emit(self.pos())
            else:
                self.clicked.emit()
        elif e.button() == Qt.RightButton:
            self.right_clicked.emit(e.globalPosition().toPoint())

    def enterEvent(self, _e):
        self.setCursor(QCursor(Qt.OpenHandCursor))

    # ----------------------------------------------------------- paint
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w = h = self.size_px
        breathe = math.sin(self.t * 2.4) * 0.014
        bob = math.sin(self.t * 1.7) * (h * 0.012)

        p.translate(w / 2, h * 0.54 + bob)
        if self.facing < 0:
            p.scale(-1, 1)

        bw = w * (0.62 + breathe)
        bh = h * (0.50 + breathe)

        # glow when listening: soft ring hugging the body
        if self.state == "listening":
            pulse = 0.5 + 0.5 * math.sin(self.t * 4)
            for i in range(3):
                grow = 1.0 + i * 0.13
                p.setPen(QPen(QColor(95, 200, 245, int((46 - i * 14) * pulse)),
                              max(2.0, bw * 0.016), Qt.SolidLine, Qt.RoundCap))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(-bw / 2 * grow, -bh / 2 * grow,
                                     bw * grow, bh * grow))

        # tail
        tail = QPainterPath()
        tail.moveTo(bw * 0.30, 0)
        tail.cubicTo(bw * 0.58, -bh * 0.42, bw * 0.86, -bh * 0.62, bw * 0.74, -bh * 0.18)
        tail.cubicTo(bw * 0.86, -bh * 0.02, bw * 0.60, bh * 0.16, bw * 0.30, bh * 0.06)
        tail.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3AA6D8"))
        p.drawPath(tail)

        # body
        grad = QRadialGradient(-bw * 0.15, -bh * 0.22, bw * 0.85)
        grad.setColorAt(0.0, QColor("#7FD8FF"))
        grad.setColorAt(0.55, BODY_TOP)
        grad.setColorAt(1.0, BODY_BOT)
        p.setBrush(grad)
        p.drawEllipse(QRectF(-bw / 2, -bh / 2, bw, bh))

        # belly
        p.setBrush(QColor(255, 255, 255, 42))
        p.drawEllipse(QRectF(-bw * 0.34, -bh * 0.02, bw * 0.62, bh * 0.42))

        # back fin
        fin = QPainterPath()
        fin.moveTo(-bw * 0.02, -bh * 0.46)
        fin.cubicTo(bw * 0.06, -bh * 0.78, bw * 0.20, -bh * 0.70, bw * 0.16, -bh * 0.40)
        fin.closeSubpath()
        p.setBrush(QColor("#3AA6D8"))
        p.drawPath(fin)

        # side fin
        p.save()
        p.translate(-bw * 0.10, bh * 0.22)
        p.rotate(math.sin(self.t * 3.1) * 12)
        side = QPainterPath()
        side.moveTo(0, 0)
        side.cubicTo(-bw * 0.16, bh * 0.10, -bw * 0.18, bh * 0.30, -bw * 0.02, bh * 0.26)
        side.closeSubpath()
        p.setBrush(QColor("#57BEE8"))
        p.drawPath(side)
        p.restore()

        # eyes
        eye_dx = bw * 0.155
        eye_y = -bh * 0.10
        er = bw * 0.072
        for sign in (-1, 1):
            p.save()
            p.translate(sign * eye_dx, eye_y)
            p.scale(1.0, max(0.06, 1.0 - 0.92 * self.blink))
            p.setBrush(QColor("white"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(-er, -er * 1.12, er * 2, er * 2.24))
            look = math.sin(self.t * 1.3) * er * 0.14
            p.setBrush(DARK)
            p.drawEllipse(QRectF(look - er * 0.56, er * 0.10 - er * 0.62,
                                 er * 1.12, er * 1.24))
            p.setBrush(QColor("white"))
            p.drawEllipse(QRectF(look - er * 0.34, er * 0.02 - er * 0.12,
                                 er * 0.34, er * 0.40))
            p.restore()

        # blush
        p.setPen(Qt.NoPen)
        for sign in (-1, 1):
            p.setBrush(QColor(255, 155, 176, 85))
            p.drawEllipse(QRectF(sign * bw * 0.255 - bw * 0.075, bh * 0.055,
                                 bw * 0.15, bh * 0.09))

        # mouth
        my = bh * 0.13
        if self.mouth_open > 0.05:
            p.setBrush(QColor("#7A2138"))
            p.drawEllipse(QRectF(-bw * 0.055, my - bh * 0.038 * self.mouth_open,
                                 bw * 0.11, bh * 0.075 * self.mouth_open))
        else:
            p.setPen(QPen(DARK, max(1.6, bw * 0.014), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(-bw * 0.075, my - bh * 0.035, bw * 0.15, bh * 0.07),
                      200 * 16, 140 * 16)

        # thinking dots
        if self.state == "thinking":
            p.setPen(Qt.NoPen)
            for i in range(3):
                ph = (self.t * 1.6 + i * 0.5) % 1.0
                r = bw * (0.026 + 0.016 * ph)
                p.setBrush(QColor(220, 242, 255, int(190 * (1 - ph))))
                p.drawEllipse(QRectF(bw * (0.30 + i * 0.075) - r,
                                     -bh * (0.52 + 0.13 * ph) - r, r * 2, r * 2))

        # listening mic icon (above the head, clear of the body)
        if self.state == "listening":
            mic = QColor(240, 252, 255, 235)
            p.setPen(Qt.NoPen)
            p.setBrush(mic)
            cxm, cym = 0, -bh * 0.86
            rw, rh = bw * 0.048, bh * 0.078
            p.drawRoundedRect(QRectF(cxm - rw, cym - rh, rw * 2, rh * 2), rw, rw)
            p.setPen(QPen(mic, max(1.6, bw * 0.013)))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(cxm - rw * 1.8, cym - rh * 0.35, rw * 3.6, rh * 2.1),
                      200 * 16, 140 * 16)
            p.setPen(Qt.NoPen)
            p.setBrush(mic)
            p.drawRect(QRectF(cxm - rw * 0.12, cym + rh * 1.45, rw * 0.24, rh * 0.55))
