"""陪玩角色的矢量形象：一条会呼吸、会眨眼、会说话的蓝色鲸鱼。

纯 QPainter 绘制，不依赖任何图片素材。
状态: idle(呼吸+眨眼) / thinking(转圈) / talking(嘴动) / happy(跳跃)
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath,
                           QPen, QRadialGradient)
from PySide6.QtWidgets import QWidget

BODY_TOP = QColor("#5FC8F5")
BODY_BOT = QColor("#2A8CC4")
BELLY = QColor("#DCF2FF")
DARK = QColor("#1B3A4B")
BLUSH = QColor("#FF9BB0")


class PetWidget(QWidget):
    def __init__(self, parent=None, size=180):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.state = "idle"
        self.t = 0.0
        self.blink = 0.0
        self.blink_timer = 0
        self.mouth_open = 0.0
        self.hop = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)  # 25 fps

    def set_state(self, state):
        self.state = state
        self.update()

    def _tick(self):
        self.t += 0.045
        if self.blink > 0:
            self.blink = max(0.0, self.blink - 0.14)
        elif random.random() < 0.012:
            self.blink = 1.0

        if self.state == "talking":
            self.mouth_open = 0.5 + 0.5 * math.sin(self.t * 9)
        else:
            self.mouth_open = max(0.0, self.mouth_open - 0.1)

        if self.state == "happy":
            self.hop = max(0.0, self.hop - 0.05)

        self.update()

    def hop_once(self):
        self.hop = 1.0
        self.set_state("happy")
        QTimer.singleShot(900, lambda: self.set_state("idle"))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        cx = w / 2

        # breathing: 2.5s cycle
        breathe = math.sin(self.t * 2.4) * 0.014
        bob = math.sin(self.t * 1.7) * (h * 0.012)
        hop_y = -abs(math.sin(self.hop * math.pi)) * (h * 0.10) if self.hop > 0 else 0
        spin = self.t * 2.2 if self.state == "thinking" else 0.0

        p.translate(cx, h * 0.54 + bob + hop_y)
        if spin:
            p.rotate(math.sin(spin) * 4)

        body_w = w * (0.62 + breathe)
        body_h = h * (0.50 + breathe)

        # --- tail (behind body) ---
        tail = QPainterPath()
        tw = body_w * 0.30
        tail.moveTo(body_w * 0.30, 0)
        tail.cubicTo(body_w * 0.58, -body_h * 0.42,
                     body_w * 0.86, -body_h * 0.62,
                     body_w * 0.74, -body_h * 0.18)
        tail.cubicTo(body_w * 0.86, -body_h * 0.02,
                     body_w * 0.60, body_h * 0.16,
                     body_w * 0.30, body_h * 0.06)
        tail.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3AA6D8"))
        p.drawPath(tail)

        # --- body ---
        body = QPainterPath()
        body.addEllipse(QPointF(0, 0), body_w / 2, body_h / 2)
        grad = QLinearGradient(0, -body_h / 2, 0, body_h / 2)
        grad.setColorAt(0.0, BODY_TOP)
        grad.setColorAt(1.0, BODY_BOT)
        p.setBrush(QBrush(grad))
        p.drawPath(body)

        # --- belly highlight ---
        belly = QPainterPath()
        belly.addEllipse(QPointF(-body_w * 0.04, body_h * 0.20),
                         body_w * 0.30, body_h * 0.26)
        p.setBrush(QColor(255, 255, 255, 46))
        p.drawPath(belly)

        # --- back fin ---
        fin = QPainterPath()
        fin.moveTo(-body_w * 0.02, -body_h * 0.46)
        fin.cubicTo(body_w * 0.06, -body_h * 0.78,
                    body_w * 0.20, -body_h * 0.70,
                    body_w * 0.16, -body_h * 0.40)
        fin.closeSubpath()
        p.setBrush(QColor("#3AA6D8"))
        p.drawPath(fin)

        # --- side fin (waves) ---
        p.save()
        p.translate(-body_w * 0.10, body_h * 0.22)
        p.rotate(math.sin(self.t * 3.1) * 12)
        side = QPainterPath()
        side.moveTo(0, 0)
        side.cubicTo(-body_w * 0.16, body_h * 0.10,
                     -body_w * 0.18, body_h * 0.30,
                     -body_w * 0.02, body_h * 0.26)
        side.closeSubpath()
        p.setBrush(QColor("#57BEE8"))
        p.drawPath(side)
        p.restore()

        # --- eyes (symmetric around the face, which sits left of centre) ---
        eye_dx = body_w * 0.155
        eye_y = -body_h * 0.10
        eye_r = body_w * 0.070
        for sign in (-1, 1):
            ex = sign * eye_dx
            open_ratio = 1.0 - 0.92 * self.blink
            p.save()
            p.translate(ex, eye_y)
            p.scale(1.0, max(0.06, open_ratio))
            p.setBrush(QColor("white"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(0, 0), eye_r, eye_r * 1.12)
            # pupil looks slightly toward the "thinking" direction
            look = math.sin(spin) * eye_r * 0.16 if self.state == "thinking" else 0
            p.setBrush(DARK)
            p.drawEllipse(QPointF(look, eye_r * 0.10), eye_r * 0.56, eye_r * 0.62)
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(look - eye_r * 0.18, eye_r * 0.02),
                          eye_r * 0.18, eye_r * 0.20)
            p.restore()

        # --- blush ---
        for sign in (-1, 1):
            bx = sign * body_w * 0.255
            p.setBrush(QColor(255, 155, 176, 90))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(bx, body_h * 0.10), body_w * 0.075, body_h * 0.045)

        # --- mouth ---
        mouth_y = body_h * 0.13
        if self.mouth_open > 0.05:
            mw = body_w * 0.11
            mh = body_h * 0.075 * self.mouth_open
            p.setBrush(QColor("#7A2138"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(0, mouth_y), mw, mh)
        else:
            p.setPen(QPen(DARK, max(1.6, body_w * 0.014), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            arc = QRectF(-body_w * 0.075, mouth_y - body_h * 0.035,
                         body_w * 0.15, body_h * 0.07)
            p.drawArc(arc, 200 * 16, 140 * 16)

        # --- thinking bubbles ---
        if self.state == "thinking":
            p.setPen(Qt.NoPen)
            for i in range(3):
                phase = (self.t * 1.6 + i * 0.5) % 1.0
                r = body_w * (0.026 + 0.016 * phase)
                a = int(190 * (1.0 - phase))
                p.setBrush(QColor(220, 242, 255, a))
                p.drawEllipse(QPointF(body_w * (0.30 + i * 0.075),
                                      -body_h * (0.52 + 0.13 * phase)), r, r)
