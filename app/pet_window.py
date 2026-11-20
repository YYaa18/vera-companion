"""桌面角色：一条会呼吸、眨眼、说话的小鲸鱼。

外观由人设主题驱动（见 pet_personas.py）——四种人设不只是配色不同，
眼睛、嘴型、配饰、动作节奏都不一样。

纯 QPainter 绘制，无任何图片素材，全部原创。
"""
import math
import random

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QCursor, QLinearGradient, QPainter,
                           QPainterPath, QPen, QRadialGradient)
from PySide6.QtWidgets import QWidget

import pet_personas


class PetWindow(QWidget):
    """透明、无边框、置顶、可拖动、会自由游动的角色窗口。"""

    clicked = Signal()
    right_clicked = Signal(QPoint)
    dragged_done = Signal(QPoint)

    SIZE_ACTIVE = 215
    SIZE_IDLE = 165

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self.size_px = self.SIZE_IDLE
        self.resize(self.size_px, self.size_px)

        # 人设主题
        self.persona_key = pet_personas.DEFAULT
        self.theme = pet_personas.get(self.persona_key)

        # 动画状态
        self.t = 0.0
        self.blink = 0.0
        self.mouth_open = 0.0
        self.state = "idle"
        self.facing = 1
        self.hop = 0.0
        self.look = 0.0
        self.look_target = 0.0

        # 游动
        self.wander = True
        self.drift = QPoint(0, 0)
        self.drift_ticks = 0

        # 拖拽
        self._dragging = False
        self._press_pos = None
        self._win_pos = None
        self._moved = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)

        self.wander_timer = QTimer(self)
        self.wander_timer.timeout.connect(self._pick_direction)
        self.wander_timer.start(2600)

        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._maybe_blink)
        self.blink_timer.start(700)

        self.look_timer = QTimer(self)
        self.look_timer.timeout.connect(self._pick_look)
        self.look_timer.start(1900)

    # ----------------------------------------------------------- 人设
    def set_persona(self, key):
        """Switch appearance. The window size and behaviour stay the same."""
        self.persona_key = key if key in pet_personas.THEMES else pet_personas.DEFAULT
        self.theme = pet_personas.get(self.persona_key)
        self.update()

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

    def hop_once(self):
        self.hop = 1.0
        QTimer.singleShot(880, lambda: setattr(self, "hop", 0.0))

    def _maybe_blink(self):
        if self.blink <= 0 and self.state != "listening":
            self.blink = 1.0

    def _pick_look(self):
        if self.state in ("thinking", "talking"):
            self.look_target = 0.0
            return
        # 邪恶：目光几乎不动；鬼灵精怪：东张西望
        span = {"evil": 0.25, "gentle": 0.5, "cute": 0.6, "mischief": 0.9}
        amp = span.get(self.persona_key, 0.6)
        self.look_target = random.uniform(-amp, amp)

    def _pick_direction(self):
        if not self.wander or self.state != "idle" or self._dragging:
            self.drift = QPoint(0, 0)
            return
        if random.random() < 0.45:
            self.drift = QPoint(0, 0)
            return
        ang = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 1.4)
        self.drift = QPoint(round(math.cos(ang) * speed),
                            round(math.sin(ang) * speed * 0.5))
        self.drift_ticks = random.randint(18, 46)
        if self.drift.x() != 0:
            self.facing = 1 if self.drift.x() > 0 else -1

    def _tick(self):
        self.t += 0.045

        if self.blink > 0:
            self.blink = max(0.0, self.blink - 0.13)

        self.look += (self.look_target - self.look) * 0.12

        if self.state == "talking":
            self.mouth_open = 0.5 + 0.5 * math.sin(self.t * 10)
        else:
            self.mouth_open = max(0.0, self.mouth_open - 0.12)

        if self.hop > 0:
            self.hop = max(0.0, self.hop - 0.045)

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

    def enterEvent(self, _e):
        self.setCursor(QCursor(Qt.OpenHandCursor))

    # ----------------------------------------------------------- paint
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = self.theme

        w = h = self.size_px
        breathe = math.sin(self.t * t["breathe_hz"]) * t["breathe_amp"]
        bob = math.sin(self.t * (t["breathe_hz"] * 0.8)) * (h * 0.010)

        # 弹跳（鬼灵精怪）与跳跃
        bounce_y = 0.0
        if t["bounce"] > 0 and self.state in ("talking", "idle"):
            bounce_y = -abs(math.sin(self.t * 3.4)) * (h * 0.010 * t["bounce"])
        hop_y = -abs(math.sin(self.hop * math.pi)) * (h * 0.11) if self.hop > 0 else 0.0

        p.translate(w / 2, h * 0.55 + bob + hop_y + bounce_y)
        if t["tilt"]:
            p.rotate(t["tilt"] * 0.35 + math.sin(self.t * 1.3) * (t["tilt"] * 0.25))
        if self.facing < 0:
            p.scale(-1, 1)

        bw = w * (0.60 + breathe)
        bh = h * (0.50 + breathe)

        self._draw_aura(p, bw, bh)
        self._draw_tail(p, bw, bh)
        self._draw_back_fin(p, bw, bh)
        self._draw_body(p, bw, bh)
        self._draw_gills(p, bw, bh)
        self._draw_side_fin(p, bw, bh)
        self._draw_face(p, bw, bh)
        self._draw_accessory_back(p, bw, bh)
        self._draw_face_over(p, bw, bh)
        self._draw_accessory_front(p, bw, bh)
        self._draw_extras(p, bw, bh)

    # ---- 基础 ---------------------------------------------------------
    def _draw_aura(self, p, bw, bh):
        if self.state != "listening":
            return
        pulse = 0.5 + 0.5 * math.sin(self.t * 4)
        base = self.theme["body_deep"]
        for i in range(3):
            grow = 1.02 + i * 0.11
            a = int((52 - i * 15) * pulse)
            p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), a),
                          max(2.0, bw * 0.014), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(-bw / 2 * grow, -bh / 2 * grow,
                                 bw * grow, bh * grow))

    def _draw_tail(self, p, bw, bh):
        t = self.theme
        path = QPainterPath()
        path.moveTo(bw * 0.26, -bh * 0.04)
        path.cubicTo(bw * 0.52, -bh * 0.42, bw * 0.82, -bh * 0.54, bw * 0.68, -bh * 0.12)
        path.cubicTo(bw * 0.82, bh * 0.04, bw * 0.54, bh * 0.18, bw * 0.26, bh * 0.06)
        path.closeSubpath()
        g = QLinearGradient(bw * 0.3, -bh * 0.4, bw * 0.75, bh * 0.2)
        g.setColorAt(0.0, t["fin_light"])
        g.setColorAt(1.0, t["fin_dark"])
        p.setPen(QPen(QColor(255, 255, 255, 42), max(1.0, bw * 0.008)))
        p.setBrush(QBrush(g))
        p.drawPath(path)

    def _draw_back_fin(self, p, bw, bh):
        t = self.theme
        fin = QPainterPath()
        fin.moveTo(-bw * 0.04, -bh * 0.44)
        fin.cubicTo(bw * 0.02, -bh * 0.78, bw * 0.16, -bh * 0.72, bw * 0.14, -bh * 0.38)
        fin.closeSubpath()
        g = QLinearGradient(0, -bh * 0.74, 0, -bh * 0.38)
        g.setColorAt(0.0, t["fin_light"])
        g.setColorAt(1.0, t["fin_dark"])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawPath(fin)

    def _draw_body(self, p, bw, bh):
        t = self.theme
        g = QRadialGradient(-bw * 0.12, -bh * 0.20, bw * 1.02)
        g.setColorAt(0.00, t["body_light"])
        g.setColorAt(0.38, t["body_mid"])
        g.setColorAt(0.78, t["body_mid"])
        g.setColorAt(1.00, t["body_deep"])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QRectF(-bw / 2, -bh / 2, bw, bh))

        belly = QRadialGradient(-bw * 0.04, bh * 0.18, bw * 0.52)
        bc = t["belly"]
        belly.setColorAt(0.00, QColor(bc.red(), bc.green(), bc.blue(), 130))
        belly.setColorAt(0.55, QColor(bc.red(), bc.green(), bc.blue(), 58))
        belly.setColorAt(1.00, QColor(bc.red(), bc.green(), bc.blue(), 0))
        p.setBrush(QBrush(belly))
        p.drawEllipse(QRectF(-bw * 0.44, -bh * 0.04, bw * 0.84, bh * 0.56))

        # 高光：邪恶人设不给亮光，显得暗
        if self.persona_key != "evil":
            p.setPen(QPen(QColor(255, 255, 255, 100), max(2.0, bw * 0.020),
                          Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(-bw * 0.19, -bh * 0.36, bw * 0.34, bh * 0.26),
                      100 * 16, 55 * 16)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawEllipse(QRectF(-bw * 0.175, -bh * 0.245, bw * 0.058, bh * 0.044))
        else:
            # 一道冷光，位置更低
            p.setPen(QPen(QColor(190, 210, 255, 55), max(1.6, bw * 0.014),
                          Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(-bw * 0.26, -bh * 0.28, bw * 0.30, bh * 0.20),
                      110 * 16, 45 * 16)

    def _draw_gills(self, p, bw, bh):
        t = self.theme
        line = t["line"]
        p.setPen(QPen(QColor(line.red(), line.green(), line.blue(), 95),
                      max(1.3, bw * 0.011), Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        for i in range(3):
            x = -bw * (0.365 + i * 0.033)
            p.drawArc(QRectF(x, bh * 0.01, bw * 0.030, bh * 0.075),
                      245 * 16, 100 * 16)

    def _draw_side_fin(self, p, bw, bh):
        t = self.theme
        # 动作节奏：鬼灵精怪摆得快，邪恶几乎不动
        speed = {"gentle": 2.4, "cute": 3.0, "mischief": 5.0, "evil": 1.2}
        amp = {"gentle": 12, "cute": 16, "mischief": 26, "evil": 6}
        sp = speed.get(self.persona_key, 3.0)
        am = amp.get(self.persona_key, 14)

        p.save()
        p.translate(-bw * 0.32, bh * 0.16)
        p.rotate(math.sin(self.t * sp) * am - 12)
        side = QPainterPath()
        side.moveTo(0, 0)
        side.cubicTo(-bw * 0.17, bh * 0.06, -bw * 0.20, bh * 0.26, -bw * 0.02, bh * 0.24)
        side.closeSubpath()
        g = QLinearGradient(-bw * 0.18, 0, 0, bh * 0.24)
        g.setColorAt(0.0, t["fin_light"])
        g.setColorAt(1.0, t["fin_dark"])
        p.setPen(QPen(QColor(255, 255, 255, 52), max(0.9, bw * 0.007)))
        p.setBrush(QBrush(g))
        p.drawPath(side)
        p.restore()

    # ---- 表情 ---------------------------------------------------------
    def _draw_face(self, p, bw, bh):
        t = self.theme
        style = t["eye_style"]
        eye_dx = bw * 0.150
        eye_y = -bh * 0.08
        er = bw * 0.076

        if style == "soft":              # 温柔：大眼、下垂眼角、睫毛
            self._eyes_round(p, bw, bh, eye_dx, eye_y, er, t, lash=True)
        elif style == "blank":           # 呆萌：很大但无神，小瞳孔
            self._eyes_blank(p, bw, bh, eye_dx, eye_y, er, t)
        elif style == "sly":             # 鬼灵精怪：一大一小，单边挑眉
            self._eyes_sly(p, bw, bh, eye_dx, eye_y, er, t)
        else:                            # 邪恶：竖瞳 + 压低的眼睑
            self._eyes_evil(p, bw, bh, eye_dx, eye_y, er, t)

    def _eyes_round(self, p, bw, bh, dx, y, er, t, lash=False):
        open_ratio = 1.0 - 0.93 * self.blink
        for sign in (-1, 1):
            p.save()
            p.translate(sign * dx, y)
            p.scale(1.0, max(0.06, open_ratio))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(-er, -er * 1.14, er * 2, er * 2.28))

            px = self.look * er * 0.30
            p.setBrush(t["line"])
            p.drawEllipse(QRectF(px - er * 0.55, er * 0.08 - er * 0.62, er * 1.10, er * 1.24))
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawEllipse(QRectF(px - er * 0.34, er * 0.08 - er * 0.44, er * 0.36, er * 0.42))
            p.restore()
            if lash:
                p.setPen(QPen(t["line"], max(1.4, bw * 0.011), Qt.SolidLine, Qt.RoundCap))
                p.setBrush(Qt.NoBrush)
                p.drawArc(QRectF(sign * dx - er * 1.1, y - er * 1.35, er * 2.2, er * 1.5),
                          35 * 16, 110 * 16)

    def _eyes_blank(self, p, bw, bh, dx, y, er, t):
        """Huge eyes, tiny pupils, no catchlight — the 'nobody home' look."""
        open_ratio = 1.0 - 0.90 * self.blink
        for sign in (-1, 1):
            p.save()
            p.translate(sign * dx, y)
            p.scale(1.0, max(0.06, open_ratio))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(-er * 1.10, -er * 1.22, er * 2.20, er * 2.44))
            px = self.look * er * 0.34
            p.setBrush(t["line"])
            p.drawEllipse(QRectF(px - er * 0.30, er * 0.10 - er * 0.32, er * 0.60, er * 0.64))
            p.restore()

    def _eyes_sly(self, p, bw, bh, dx, y, er, t):
        """One eye wide, one half-lidded — reads as a grin even at rest."""
        open_ratio = 1.0 - 0.93 * self.blink
        for idx, sign in enumerate((-1, 1)):
            big = idx == 0
            p.save()
            p.translate(sign * dx, y)
            p.scale(1.0, max(0.06, open_ratio * (1.0 if big else 0.62)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(-er, -er * 1.14, er * 2, er * 2.28))
            px = self.look * er * 0.34
            p.setBrush(t["line"])
            p.drawEllipse(QRectF(px - er * 0.50, er * 0.08 - er * 0.58, er * 1.00, er * 1.16))
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QRectF(px - er * 0.30, er * 0.08 - er * 0.40, er * 0.32, er * 0.38))
            p.restore()
            # 上眼睑线，单边抬高
            lift = er * (0.55 if big else 0.20)
            p.setPen(QPen(t["line"], max(1.8, bw * 0.014), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawLine(int(sign * dx - er * 1.05), int(y - lift),
                       int(sign * dx + er * 1.05), int(y - lift))

    def _eyes_evil(self, p, bw, bh, dx, y, er, t):
        """Vertical slit pupils plus a heavy lid line."""
        open_ratio = 1.0 - 0.92 * self.blink
        for sign in (-1, 1):
            p.save()
            p.translate(sign * dx, y)
            p.scale(1.0, max(0.06, open_ratio))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#E8ECF8"))
            p.drawEllipse(QRectF(-er, -er * 1.05, er * 2, er * 2.10))

            px = self.look * er * 0.18
            # 竖瞳
            p.setBrush(QColor("#0A0E1A"))
            p.drawEllipse(QRectF(px - er * 0.20, er * 0.02 - er * 0.62, er * 0.40, er * 1.30))
            # 一点点冷色反光
            p.setBrush(QColor(150, 190, 255, 150))
            p.drawEllipse(QRectF(px - er * 0.12, er * 0.02 - er * 0.46, er * 0.14, er * 0.30))
            p.restore()

            # 压低的眼睑：斜线，内低外高——标准"凶相"
            p.setPen(QPen(t["line"], max(2.0, bw * 0.016), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            inner = sign * dx - sign * er * 0.95
            outer = sign * dx + sign * er * 0.95
            p.drawLine(int(inner), int(y - er * 0.35),
                       int(outer), int(y - er * 0.95))

    # ---- 腮红与嘴 -----------------------------------------------------
    def _draw_face_over(self, p, bw, bh):
        t = self.theme
        style = t["mouth_style"]

        # 腮红
        p.setPen(Qt.NoPen)
        for sign in (-1, 1):
            c = t["blush"]
            p.setBrush(QColor(c.red(), c.green(), c.blue(),
                              t["blush_alpha"] if self.state == "happy"
                              else int(t["blush_alpha"] * 0.78)))
            p.drawEllipse(QRectF(sign * bw * 0.255 - bw * 0.072, bh * 0.045,
                                 bw * 0.144, bh * 0.086))

        my = bh * 0.135
        if self.mouth_open > 0.06:
            mw = bw * 0.052
            mh = bh * 0.040 * self.mouth_open
            p.setBrush(QColor("#7A2138"))
            p.drawEllipse(QRectF(-mw, my - mh, mw * 2, mh * 2))
            p.setBrush(QColor(230, 120, 140, 190))
            p.drawEllipse(QRectF(-mw * 0.55, my + mh * 0.15, mw * 1.1, mh * 0.85))
            return

        line = t["line"]
        if style == "smile":
            p.setPen(QPen(line, max(1.7, bw * 0.014), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(-bw * 0.068, my - bh * 0.030, bw * 0.136, bh * 0.062),
                      200 * 16, 140 * 16)
        elif style == "small_o":
            p.setPen(QPen(line, max(1.5, bw * 0.012), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(-bw * 0.026, my - bh * 0.012, bw * 0.052, bh * 0.038))
        elif style == "smirk":
            # 一边上翘的坏笑
            p.setPen(QPen(line, max(1.8, bw * 0.015), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(-bw * 0.062, my + bh * 0.004)
            path.quadTo(-bw * 0.010, my + bh * 0.028, bw * 0.062, my - bh * 0.020)
            p.drawPath(path)
        elif style == "flat":
            p.setPen(QPen(line, max(1.8, bw * 0.015), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(int(-bw * 0.052), int(my), int(bw * 0.052), int(my))
        else:
            p.setPen(QPen(line, max(1.6, bw * 0.014), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(-bw * 0.068, my - bh * 0.030, bw * 0.136, bh * 0.062),
                      200 * 16, 140 * 16)

    # ---- 配饰 ---------------------------------------------------------
    def _draw_accessory_back(self, p, bw, bh):
        t = self.theme
        acc = t["accessory"]
        if acc == "horns":
            # 两只角，从头顶后侧长出来
            for sign in (-1, 1):
                path = QPainterPath()
                bx = sign * bw * 0.20
                path.moveTo(bx - bw * 0.055, -bh * 0.42)
                path.quadTo(bx - bw * 0.02, -bh * 0.66,
                            bx + sign * bw * 0.06, -bh * 0.72)
                path.quadTo(bx + bw * 0.03, -bh * 0.52,
                            bx + bw * 0.055, -bh * 0.40)
                path.closeSubpath()
                g = QLinearGradient(0, -bh * 0.72, 0, -bh * 0.40)
                g.setColorAt(0.0, QColor("#20263C"))
                g.setColorAt(1.0, QColor("#4A5480"))
                p.setPen(QPen(QColor(10, 14, 26), max(1.0, bw * 0.008)))
                p.setBrush(QBrush(g))
                p.drawPath(path)

        elif acc == "tuft":
            # 一根呆毛：根部粗、末端翘，会随风摆
            sway = math.sin(self.t * 2.6) * 0.09
            path = QPainterPath()
            base_x, base_y = bw * 0.03, -bh * 0.455
            path.moveTo(base_x - bw * 0.065, base_y)
            path.cubicTo(base_x - bw * (0.03 - sway), base_y - bh * 0.20,
                         base_x + bw * (0.08 + sway), base_y - bh * 0.30,
                         base_x + bw * (0.175 + sway * 1.6), base_y - bh * 0.43)
            path.cubicTo(base_x + bw * (0.085 + sway * 0.6), base_y - bh * 0.20,
                         base_x + bw * 0.075, base_y - bh * 0.12,
                         base_x + bw * 0.065, base_y)
            path.closeSubpath()
            p.setPen(QPen(QColor(20, 60, 80, 90), max(0.9, bw * 0.007)))
            p.setBrush(t["fin_dark"])
            p.drawPath(path)

    def _draw_accessory_front(self, p, bw, bh):
        t = self.theme
        acc = t["accessory"]

        if acc == "scarf":
            # 围巾：一条贴着身体下缘的弧带，末端有个小结垂下来
            y0 = bh * 0.33
            band = QPainterPath()
            band.moveTo(-bw * 0.36, y0)
            band.quadTo(0, y0 + bh * 0.20, bw * 0.36, y0 - bh * 0.02)
            band.lineTo(bw * 0.36, y0 + bh * 0.055)
            band.quadTo(0, y0 + bh * 0.26, -bw * 0.36, y0 + bh * 0.055)
            band.closeSubpath()
            g = QLinearGradient(0, y0, 0, y0 + bh * 0.26)
            g.setColorAt(0.0, QColor("#FFB3C6"))
            g.setColorAt(1.0, QColor("#E06788"))
            p.setPen(QPen(QColor(160, 60, 84, 110), max(1.0, bw * 0.008)))
            p.setBrush(QBrush(g))
            p.drawPath(band)
            # 小结
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FF8FA8"))
            p.drawEllipse(QRectF(bw * 0.26, y0 + bh * 0.045, bw * 0.080, bh * 0.065))

        elif acc == "goggles":
            # 护目镜：推到额头顶上，不能压到眼睛
            y = -bh * 0.40
            p.setPen(QPen(QColor(40, 52, 60), max(1.4, bw * 0.012)))
            p.setBrush(QColor(38, 48, 56, 225))
            p.drawRoundedRect(QRectF(-bw * 0.29, y - bh * 0.050,
                                     bw * 0.58, bh * 0.100),
                              bw * 0.028, bw * 0.028)
            for sign in (-1, 1):
                p.setBrush(QColor(150, 230, 255, 155))
                p.setPen(QPen(QColor(70, 90, 100), max(1.0, bw * 0.008)))
                p.drawEllipse(QRectF(sign * bw * 0.140 - bw * 0.082,
                                     y - bh * 0.038, bw * 0.164, bh * 0.076))
                p.setPen(QPen(QColor(255, 255, 255, 175), max(0.8, bw * 0.006)))
                p.setBrush(Qt.NoBrush)
                p.drawArc(QRectF(sign * bw * 0.140 - bw * 0.062,
                                 y - bh * 0.026, bw * 0.080, bh * 0.044),
                          60 * 16, 60 * 16)

        elif acc == "horns":
            # 项圈：细一些，压在身体下沿，露出嘴
            # 项圈：贴着身体下缘的一道弧，两端收窄，不会戳出轮廓
            y = bh * 0.245
            band = QPainterPath()
            band.moveTo(-bw * 0.285, y)
            band.quadTo(0, y + bh * 0.150, bw * 0.285, y)
            band.lineTo(bw * 0.265, y + bh * 0.048)
            band.quadTo(0, y + bh * 0.196, -bw * 0.265, y + bh * 0.048)
            band.closeSubpath()
            p.setPen(QPen(QColor(18, 22, 36), max(1.0, bw * 0.008)))
            p.setBrush(QColor(44, 32, 52, 235))
            p.drawPath(band)
            # 宝石挂在弧的最低点
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(200, 76, 118, 240))
            p.drawEllipse(QRectF(-bw * 0.028, y + bh * 0.108, bw * 0.056, bh * 0.044))

    # ---- 状态图标 -----------------------------------------------------
    def _draw_extras(self, p, bw, bh):
        if self.state == "thinking":
            p.setPen(Qt.NoPen)
            for i in range(3):
                ph = (self.t * 1.5 + i * 0.42) % 1.0
                r = bw * (0.022 + 0.014 * ph)
                p.setBrush(QColor(225, 244, 255, int(200 * (1 - ph))))
                p.drawEllipse(QRectF(bw * (0.28 + i * 0.072) - r,
                                     -bh * (0.50 + 0.12 * ph) - r, r * 2, r * 2))

        if self.state == "listening":
            mic = QColor(245, 253, 255, 240)
            cxm, cym = 0, -bh * 0.86
            rw, rh = bw * 0.042, bh * 0.068
            p.setPen(Qt.NoPen)
            p.setBrush(mic)
            p.drawRoundedRect(QRectF(cxm - rw, cym - rh, rw * 2, rh * 2), rw, rw)
            p.setPen(QPen(mic, max(1.5, bw * 0.012)))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(cxm - rw * 1.7, cym - rh * 0.30, rw * 3.4, rh * 1.9),
                      200 * 16, 140 * 16)
            p.setPen(Qt.NoPen)
            p.setBrush(mic)
            p.drawRoundedRect(QRectF(cxm - rw * 0.11, cym + rh * 1.3, rw * 0.22, rh * 0.5),
                              rw * 0.11, rw * 0.11)
