"""生化危机：代号维罗妮卡 X —— 统一启动器

一个窗口管三件事：
    1. 配置 AI（API Key、模型、语音）
    2. 启动游戏
    3. 启动陪玩助手（可以和游戏一起启动）

打包后直接运行 exe；开发时 python launcher.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading

from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

import config

ACCENT = "#5FC8F5"
BG = "#15181f"
CARD = "#1d2029"
CARD2 = "#242833"
FG = "#e6edf3"
DIM = "#8b949e"
OK = "#3fb950"
WARN = "#d29922"
ERR = "#f85149"


def dark_palette():
    """A dark Fusion palette.

    Per-widget style sheets only reach the widget itself; spin boxes, combo
    popups, password dots and selection all read the application palette.
    Setting it once here is what actually keeps text light everywhere.
    """
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(FG))
    pal.setColor(QPalette.Base, QColor(CARD2))
    pal.setColor(QPalette.AlternateBase, QColor(CARD))
    pal.setColor(QPalette.ToolTipBase, QColor(CARD2))
    pal.setColor(QPalette.ToolTipText, QColor(FG))
    pal.setColor(QPalette.Text, QColor(FG))
    pal.setColor(QPalette.Button, QColor(CARD2))
    pal.setColor(QPalette.ButtonText, QColor(FG))
    pal.setColor(QPalette.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.Link, QColor(ACCENT))
    pal.setColor(QPalette.Highlight, QColor("#2f6f99"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor(DIM))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#6b7280"))
    return pal


def fish_icon(size=32):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ACCENT))
    p.drawEllipse(2, size * 0.22, size * 0.62, size * 0.56)
    p.setBrush(QColor("#3AA6D8"))
    p.drawEllipse(size * 0.60, size * 0.28, size * 0.36, size * 0.44)
    p.setBrush(QColor("#1B3A4B"))
    p.drawEllipse(size * 0.16, size * 0.36, size * 0.09, size * 0.11)
    p.end()
    return pm


def check_icon(size=16):
    """A small check mark, drawn in code so no asset file is needed."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#0d1117"), max(2.0, size * 0.16), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.drawPolyline([
        QPointF(size * 0.18, size * 0.52),
        QPointF(size * 0.42, size * 0.75),
        QPointF(size * 0.84, size * 0.26),
    ])
    p.end()
    return pm


class Card(QFrame):
    def __init__(self, title=""):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(
            f"#card{{background:{CARD};border-radius:12px;border:1px solid #2b2f3a;}}"
        )
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(16, 14, 16, 14)
        self.lay.setSpacing(10)
        if title:
            t = QLabel(title)
            t.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            t.setStyleSheet(f"color:{FG};border:none;")
            self.lay.addWidget(t)


class Launcher(QMainWindow):
    # worker threads report back through these; Qt queues them onto the UI thread
    test_result = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        self.game_proc = None
        self.assist_proc = None
        self.setWindowTitle("维罗妮卡 X · 启动器")
        self.setWindowIcon(QIcon(fish_icon(64)))
        self.resize(680, 780)
        self.setMinimumSize(620, 520)
        self.setStyleSheet(f"QMainWindow{{background:{BG};}}")
        self.test_result.connect(self._test_done)

        # 内容放滚动区：卡片变多后小屏也能看全
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:transparent;width:9px;}"
            "QScrollBar::handle:vertical{background:#3a4150;border-radius:4px;min-height:28px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        self.setCentralWidget(scroll)

        root = QWidget()
        root.setStyleSheet(f"background:{BG};")
        scroll.setWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_api_card())
        outer.addWidget(self._build_game_card())
        outer.addWidget(self._build_peer_card())
        outer.addWidget(self._build_launch_card())
        outer.addStretch()
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{DIM};font-size:11px;")
        self.status.setFont(QFont("Microsoft YaHei", 8))
        outer.addWidget(self.status)

        self.refresh_status()
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(1500)

        if not config.has_api_key(self.cfg):
            QTimer.singleShot(400, self._prompt_key)

    # ------------------------------------------------------------ ui
    def _build_header(self):
        row = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(fish_icon(44))
        icon.setFixedSize(48, 48)
        row.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(1)
        title = QLabel("生化危机：代号维罗妮卡 X")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        title.setStyleSheet(f"color:{FG};")
        col.addWidget(title)
        sub = QLabel("PC 重编译版 + AI 语音陪玩")
        sub.setFont(QFont("Microsoft YaHei", 8))
        sub.setStyleSheet(f"color:{DIM};")
        col.addWidget(sub)
        row.addLayout(col)
        row.addStretch()
        return row

    def _build_api_card(self):
        card = Card("① AI 配置")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        def lab(text):
            """One label, styled once. (A lambda here would create fresh,
            unstyled widgets at addWidget time -- that was the black-text bug.)"""
            w = QLabel(text)
            w.setFont(QFont("Microsoft YaHei", 9))
            w.setStyleSheet(f"color:{DIM};border:none;background:transparent;")
            return w

        self.key_edit = QLineEdit(self.cfg.get("api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-… （在 platform.deepseek.com 创建）")
        self.key_edit.setMinimumHeight(32)

        self.url_edit = QLineEdit(self.cfg.get("base_url", "https://api.deepseek.com"))
        self.url_edit.setMinimumHeight(32)

        self.model_box = QComboBox()
        self.model_box.setEditable(True)
        self.model_box.addItems(["deepseek-flash", "deepseek-v4-pro"])
        self.model_box.setCurrentText(self.cfg.get("model", "deepseek-flash"))
        self.model_box.setMinimumHeight(32)

        self.voice_box = QComboBox()
        self.voice_box.addItems(["stella（女声）", "tide（男声）"])
        self.voice_box.setCurrentIndex(0 if self.cfg.get("voice", "stella") == "stella" else 1)
        self.voice_box.setMinimumHeight(32)

        self.persona_box = QComboBox()
        self.persona_items = []
        try:
            import personas
            self.persona_items = personas.available()
        except Exception:
            self.persona_items = []
        for name, key, desc in self.persona_items:
            self.persona_box.addItem(self._persona_thumb(key), name)
            idx = self.persona_box.count() - 1
            if desc:
                self.persona_box.setItemData(idx, desc, Qt.ToolTipRole)
            self.persona_box.setItemData(idx, key, Qt.UserRole)
        cur = self.cfg.get("persona", "gentle")
        for i, (name, key, desc) in enumerate(self.persona_items):
            if key == cur:
                self.persona_box.setCurrentIndex(i)
                break
        self.persona_box.setMinimumHeight(32)
        self.persona_box.setIconSize(QSize(44, 44))
        self.persona_box.setStyleSheet(
            f"QComboBox{{background:{CARD2};color:{FG};border:1px solid #2f3441;"
            "border-radius:7px;padding:3px 8px;}"
            "QComboBox QAbstractItemView{background:#1d2029;color:#e6edf3;"
            "selection-background-color:#2f6f99;padding:4px;}"
        )
        if self.persona_items:
            first = self.persona_items[0]
            for name, key, desc in self.persona_items:
                if key == cur and desc:
                    self.persona_box.setToolTip(desc)
                    break
            else:
                self.persona_box.setToolTip(first[2])
        self.persona_box.currentIndexChanged.connect(self._persona_changed)

        for w in (self.key_edit, self.url_edit, self.model_box, self.voice_box,
                  self.persona_box):
            w.setStyleSheet(
                f"background:{CARD2};color:{FG};border:1px solid #2f3441;"
                "border-radius:7px;padding:4px 8px;"
            )

        grid.addWidget(lab("API Key"), 0, 0)
        grid.addWidget(self.key_edit, 0, 1, 1, 2)

        show = QPushButton("显示")
        show.setFixedWidth(54)
        show.setCheckable(True)
        show.setStyleSheet(
            f"QPushButton{{background:{CARD2};color:{DIM};border:1px solid #2f3441;"
            "border-radius:7px;padding:5px;font-size:11px;}"
            f"QPushButton:checked{{color:{ACCENT};border-color:{ACCENT};}}"
        )

        def toggle_echo(checked):
            self.key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            show.setText("隐藏" if checked else "显示")

        show.toggled.connect(toggle_echo)
        grid.addWidget(show, 0, 3)

        grid.addWidget(lab("API 地址"), 1, 0)
        grid.addWidget(self.url_edit, 1, 1, 1, 3)

        # 模型 / 语音 / 人设 各占一行，统一宽度，标签独立一列
        grid.addWidget(lab("模型"), 2, 0)
        grid.addWidget(self.model_box, 2, 1, 1, 3)
        grid.addWidget(lab("人设"), 3, 0)
        grid.addWidget(self.persona_box, 3, 1, 1, 3)
        grid.addWidget(lab("语音"), 4, 0)
        grid.addWidget(self.voice_box, 4, 1, 1, 3)

        grid.addWidget(lab("气泡字号"), 5, 0)
        self.bubble_size_box = QComboBox()
        for label, key in (("标准", "small"), ("大（推荐）", "normal"),
                           ("特大", "large"), ("超大", "huge")):
            self.bubble_size_box.addItem(label, key)
        cur_size = self.cfg.get("bubble_size", "normal")
        for i in range(self.bubble_size_box.count()):
            if self.bubble_size_box.itemData(i) == cur_size:
                self.bubble_size_box.setCurrentIndex(i)
                break
        self.bubble_size_box.setMinimumHeight(32)
        self.bubble_size_box.setStyleSheet(
            f"background:{CARD2};color:{FG};border:1px solid #2f3441;"
            "border-radius:7px;padding:4px 8px;"
        )
        grid.addWidget(self.bubble_size_box, 5, 1, 1, 3)

        self.duck_check = QCheckBox("说话时自动压低游戏音量（避免两个声音打架）")
        self.duck_check.setChecked(bool(self.cfg.get("duck_game_audio", True)))
        self._style_check(self.duck_check)
        grid.addWidget(self.duck_check, 6, 0, 1, 4)

        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(0, 70)

        self.persona_hint = QLabel("")
        self.persona_hint.setWordWrap(True)
        self.persona_hint.setFont(QFont("Microsoft YaHei", 8))
        self.persona_hint.setStyleSheet(f"color:{DIM};border:none;background:transparent;")
        grid.addWidget(self.persona_hint, 7, 1, 1, 3)
        self._persona_changed()

        card.lay.addLayout(grid)

        btns = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setMinimumHeight(30)
        self.test_btn.clicked.connect(self.test_api)
        self.test_btn.setStyleSheet(self._btn_style(secondary=True))
        btns.addWidget(self.test_btn)

        save_btn = QPushButton("保存配置")
        save_btn.setMinimumHeight(30)
        save_btn.clicked.connect(self.save_cfg)
        save_btn.setStyleSheet(self._btn_style(secondary=True))
        btns.addWidget(save_btn)

        self.api_status = QLabel("")
        self.api_status.setStyleSheet(f"color:{DIM};font-size:11px;border:none;")
        self.api_status.setFont(QFont("Microsoft YaHei", 8))
        btns.addWidget(self.api_status, 1)
        card.lay.addLayout(btns)
        return card

    def _build_game_card(self):
        card = Card("② 游戏")
        row = QHBoxLayout()
        lab = QLabel("镜像")
        lab.setFont(QFont("Microsoft YaHei", 9))
        lab.setStyleSheet(f"color:{DIM};border:none;background:transparent;")
        row.addWidget(lab)

        self.iso_edit = QLineEdit(self.cfg.get("iso_path", ""))
        self.iso_edit.setPlaceholderText("RE-CodeVeronicaX-USA-SLUS-20184.iso")
        self.iso_edit.setMinimumHeight(32)
        self.iso_edit.setStyleSheet(
            f"background:{CARD2};color:{FG};border:1px solid #2f3441;"
            "border-radius:7px;padding:4px 8px;"
        )
        row.addWidget(self.iso_edit, 1)

        browse = QPushButton("浏览…")
        browse.setFixedWidth(64)
        browse.setMinimumHeight(32)
        browse.clicked.connect(self.pick_iso)
        browse.setStyleSheet(self._btn_style(secondary=True))
        row.addWidget(browse)
        card.lay.addLayout(row)

        self.iso_status = QLabel("")
        self.iso_status.setStyleSheet(f"color:{DIM};font-size:11px;border:none;")
        self.iso_status.setFont(QFont("Microsoft YaHei", 8))
        card.lay.addWidget(self.iso_status)

        # ---- 联机（UU 虚拟局域网）----
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#2b2f3a;border:none;")
        card.lay.addWidget(sep)

        net_head = QLabel("联机 · UU 虚拟局域网")
        net_head.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        net_head.setStyleSheet(f"color:{FG};border:none;background:transparent;")
        card.lay.addWidget(net_head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)

        def lab2(t):
            w = QLabel(t)
            w.setFont(QFont("Microsoft YaHei", 9))
            w.setStyleSheet(f"color:{DIM};border:none;background:transparent;")
            return w

        edit_style = (f"background:{CARD2};color:{FG};border:1px solid #2f3441;"
                      "border-radius:7px;padding:4px 8px;")

        self.game_net_adapter = QComboBox()
        try:
            import net_adapters
            rows = net_adapters.list_adapters()
        except Exception:
            rows = []
        self._game_adapters = rows
        for ip, alias, kind in rows:
            tag = {"lan": "局域网", "public": "公网", "link-local": "未配置"}.get(kind, "")
            self.game_net_adapter.addItem(f"{ip}  ({alias}, {tag})", ip)
        if not rows:
            self.game_net_adapter.addItem("（没检测到网卡）", "")
        self.game_net_adapter.setMinimumHeight(30)
        self.game_net_adapter.setStyleSheet(edit_style)

        self.game_room_code = QLineEdit(self.cfg.get("game_room_code", ""))
        self.game_room_code.setPlaceholderText("游戏里 COPY JOIN ADDRESS 得到的 8 位加入码")
        self.game_room_code.setMinimumHeight(30)
        self.game_room_code.setStyleSheet(edit_style)

        grid.addWidget(lab2("我的地址"), 0, 0)
        grid.addWidget(self.game_net_adapter, 0, 1, 1, 2)
        grid.addWidget(lab2("加入码"), 1, 0)
        grid.addWidget(self.game_room_code, 1, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        card.lay.addLayout(grid)

        # 生成好的完整地址 + 复制按钮
        combo = QHBoxLayout()
        self.game_addr_label = QLabel("")
        self.game_addr_label.setWordWrap(True)
        self.game_addr_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.game_addr_label.setFont(QFont("Consolas", 9))
        self.game_addr_label.setStyleSheet(
            f"color:{ACCENT};background:{CARD2};border:1px solid #2f3441;"
            "border-radius:7px;padding:6px 9px;")
        combo.addWidget(self.game_addr_label, 1)

        copy_btn = QPushButton("复制")
        copy_btn.setFixedWidth(56)
        copy_btn.setMinimumHeight(30)
        copy_btn.clicked.connect(self._copy_game_addr)
        copy_btn.setStyleSheet(self._btn_style(secondary=True))
        combo.addWidget(copy_btn)
        card.lay.addLayout(combo)

        self.game_net_hint = QLabel("")
        self.game_net_hint.setWordWrap(True)
        self.game_net_hint.setFont(QFont("Microsoft YaHei", 8))
        self.game_net_hint.setStyleSheet(f"color:{DIM};border:none;background:transparent;")
        card.lay.addWidget(self.game_net_hint)

        self._refresh_game_addr()
        self.game_net_adapter.currentIndexChanged.connect(self._refresh_game_addr)
        self.game_room_code.textChanged.connect(self._refresh_game_addr)
        return card

    def _game_addr(self):
        """Build ip:7140#CODE from the chosen adapter and the join code."""
        ip = self.game_net_adapter.currentData() or ""
        code = self.game_room_code.text().strip().upper()
        if not ip:
            return ""
        if code:
            return f"{ip}:7140#{code}"
        return f"{ip}:7140"

    def _refresh_game_addr(self, *_):
        addr = self._game_addr()
        if addr:
            self.game_addr_label.setText(addr)
            self.game_addr_label.setStyleSheet(
                f"color:{ACCENT};background:{CARD2};border:1px solid #2f3441;"
                "border-radius:7px;padding:6px 9px;")
        else:
            self.game_addr_label.setText("（先选一块网卡）")
            self.game_addr_label.setStyleSheet(
                f"color:{DIM};background:{CARD2};border:1px solid #2f3441;"
                "border-radius:7px;padding:6px 9px;")

        # 有没有识别到 UU
        uu = any("uu" in alias.lower() for _ip, alias, _k in self._game_adapters)
        if uu:
            self.game_net_hint.setText(
                "把上面这行发给对方。UU 同房间内直接用，不需要开端口转发。\n"
                "加入方：MULTIPLAYER → Direct → JOIN A GAME → 把整行粘进 ADDRESS。")
        else:
            self.game_net_hint.setText(
                "没检测到 UU Lanplay 网卡。用 UU 虚拟局域网联机的话，"
                "请先在 UU 里进入同一个房间，然后重启本启动器。\n"
                "不用 UU 的话，需要在路由器放行 UDP 7140 并填公网 IP。")

    def _copy_game_addr(self):
        addr = self._game_addr()
        if not addr:
            return
        QApplication.clipboard().setText(addr)
        self.game_addr_label.setText(addr + "   ✓ 已复制")
        QTimer.singleShot(1600, self._refresh_game_addr)

    def _build_peer_card(self):
        card = Card("③ AI 之间对话（联机时）")

        self.peer_enabled = QCheckBox("允许你的 AI 和对方的 AI 聊天")
        self.peer_enabled.setChecked(bool(self.cfg.get("peer_enabled", False)))
        self._style_check(self.peer_enabled)
        card.lay.addWidget(self.peer_enabled)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)

        def lab(t):
            w = QLabel(t)
            w.setFont(QFont("Microsoft YaHei", 9))
            w.setStyleSheet(f"color:{DIM};border:none;background:transparent;")
            return w

        edit_style = (f"background:{CARD2};color:{FG};border:1px solid #2f3441;"
                      "border-radius:7px;padding:4px 8px;")

        self.peer_mode = QComboBox()
        self.peer_mode.addItems(["我是房主（等对方来连）", "我是加入方（连对方）"])
        self.peer_mode.setCurrentIndex(0 if self.cfg.get("peer_is_host", True) else 1)
        self.peer_mode.setMinimumHeight(30)
        self.peer_mode.setStyleSheet(edit_style)

        # 网卡选择：虚拟局域网下必须走 UU 分配的那块网卡
        self.peer_adapter = QComboBox()
        self.peer_adapters = []
        try:
            import net_adapters
            self.peer_adapters = net_adapters.list_adapters()
            auto_ip, auto_alias = net_adapters.guess_virtual_lan()
        except Exception:
            self.peer_adapters, auto_ip, auto_alias = [], None, None

        for ip, alias, kind in self.peer_adapters:
            tag = {"lan": "局域网", "public": "公网", "link-local": "未配置"}.get(kind, "")
            self.peer_adapter.addItem(f"{ip}  ({alias}, {tag})", ip)
        if not self.peer_adapters:
            self.peer_adapter.addItem("（没检测到网卡）", "")
        else:
            want = self.cfg.get("peer_local_ip") or auto_ip or ""
            for i in range(self.peer_adapter.count()):
                if self.peer_adapter.itemData(i) == want:
                    self.peer_adapter.setCurrentIndex(i)
                    break
        self.peer_adapter.setMinimumHeight(30)
        self.peer_adapter.setStyleSheet(edit_style)

        self.peer_remote = QLineEdit(self.cfg.get("peer_remote", ""))
        self.peer_remote.setPlaceholderText("对方的 IP，例如 203.0.113.5")
        self.peer_remote.setMinimumHeight(30)
        self.peer_remote.setStyleSheet(edit_style)

        self.peer_port = QLineEdit(str(self.cfg.get("peer_port", 7150)))
        self.peer_port.setFixedWidth(80)
        self.peer_port.setMinimumHeight(30)
        self.peer_port.setStyleSheet(edit_style)

        grid.addWidget(lab("角色"), 0, 0)
        grid.addWidget(self.peer_mode, 0, 1, 1, 3)
        grid.addWidget(lab("网卡"), 1, 0)
        grid.addWidget(self.peer_adapter, 1, 1, 1, 3)
        grid.addWidget(lab("对方地址"), 2, 0)
        grid.addWidget(self.peer_remote, 2, 1)
        grid.addWidget(lab("端口"), 2, 2)
        grid.addWidget(self.peer_port, 2, 3)
        grid.setColumnStretch(1, 1)

        card.lay.addLayout(grid)

        # 房主该告诉对方什么地址
        self.peer_hint_dynamic = QLabel("")
        self.peer_hint_dynamic.setWordWrap(True)
        self.peer_hint_dynamic.setFont(QFont("Microsoft YaHei", 9))
        self.peer_hint_dynamic.setStyleSheet(
            f"color:{ACCENT};border:none;background:transparent;")
        card.lay.addWidget(self.peer_hint_dynamic)
        self._peer_mode_changed()

        hint = QLabel(
            "只在这些时候说话：换房间、捡到东西、血量骤降，或者你右键让它去问对面。\n"
            "不闲聊。这条通道和游戏的联机完全独立，游戏仍走它自己的加密连接。\n"
            "房主需在路由器放行 TCP 端口（默认 7150），加入方填房主公网 IP。\n"
            "内置刹车：每分钟最多 4 条事件消息，单次会话累计 2 万字，2 小时自动断。"
        )
        hint.setWordWrap(True)
        hint.setFont(QFont("Microsoft YaHei", 8))
        hint.setStyleSheet(f"color:{DIM};border:none;background:transparent;")
        card.lay.addWidget(hint)

        self._peer_mode_changed()
        self.peer_mode.currentIndexChanged.connect(self._peer_mode_changed)
        self.peer_adapter.currentIndexChanged.connect(self._peer_mode_changed)
        self.peer_port.textChanged.connect(self._peer_mode_changed)
        return card

    def _peer_mode_changed(self, _i=None):
        is_host = self.peer_mode.currentIndex() == 0
        self.peer_remote.setEnabled(not is_host)
        ip = self.peer_adapter.currentData() or ""
        port = self.peer_port.text().strip() or "7150"

        if is_host:
            self.peer_remote.setPlaceholderText("房主不需要填，等对方连你")
            if ip:
                self.peer_hint_dynamic.setText(
                    f"把这句发给对方 →  {ip}:{port}")
            else:
                self.peer_hint_dynamic.setText("没检测到网卡，无法确定自己地址")
        else:
            self.peer_remote.setPlaceholderText("填房主那一串，例如 10.1.2.3")
            self.peer_hint_dynamic.setText(
                "填入房主「网卡」那行显示的地址，端口要和对方一致")

    def _build_launch_card(self):
        card = Card("③ 启动")

        self.with_assist = QCheckBox("同时启动 AI 陪玩助手（小鲸鱼）")
        self.with_assist.setChecked(bool(self.cfg.get("auto_launch_assistant", True)))
        self._style_check(self.with_assist)
        card.lay.addWidget(self.with_assist)

        self.record_progress = QCheckBox("记录探索进度（去过哪些房间）")
        self.record_progress.setChecked(bool(self.cfg.get("record_progress", True)))
        self._style_check(self.record_progress)
        card.lay.addWidget(self.record_progress)

        btns = QHBoxLayout()

        self.play_btn = QPushButton("▶  开始游戏")
        self.play_btn.setMinimumHeight(44)
        self.play_btn.clicked.connect(self.launch)
        self.play_btn.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        self.play_btn.setStyleSheet(
            f"QPushButton{{background:{ACCENT};color:#0d1117;border:none;border-radius:9px;}}"
            "QPushButton:hover{background:#7fd8ff;}"
            "QPushButton:disabled{background:#2f3441;color:#6b7280;}"
        )
        btns.addWidget(self.play_btn, 2)

        self.assist_btn = QPushButton("只启动助手")
        self.assist_btn.setMinimumHeight(44)
        self.assist_btn.clicked.connect(self.launch_assistant_only)
        self.assist_btn.setStyleSheet(self._btn_style(secondary=True))
        btns.addWidget(self.assist_btn, 1)

        self.progress_btn = QPushButton("进度")
        self.progress_btn.setMinimumHeight(44)
        self.progress_btn.setFixedWidth(70)
        self.progress_btn.clicked.connect(self.show_progress)
        self.progress_btn.setStyleSheet(self._btn_style(secondary=True))
        btns.addWidget(self.progress_btn)

        card.lay.addLayout(btns)
        return card

    def _persona_changed(self, _index=None):
        """Show the chosen persona's one-line description under the dropdown."""
        if not hasattr(self, "persona_hint"):
            return
        idx = self.persona_box.currentIndex()
        if 0 <= idx < len(self.persona_items):
            name, key, desc = self.persona_items[idx]
            self.persona_hint.setText(desc or "")
            self.persona_box.setToolTip(desc or "")
        else:
            self.persona_hint.setText("")

    def _current_persona_key(self):
        key = self.persona_box.currentData()
        if key:
            return key
        idx = self.persona_box.currentIndex()
        if 0 <= idx < len(self.persona_items):
            return self.persona_items[idx][1]
        return "gentle"

    def _persona_thumb(self, key):
        """Render a small preview of the character so the user can see it."""
        try:
            from pet_window import PetWindow
            from PySide6.QtGui import QPixmap, QPainter
            from PySide6.QtCore import Qt as _Qt
            w = PetWindow()
            w.size_px = 96
            w.resize(96, 96)
            w.set_persona(key)
            w.t = 1.2
            pm = w.grab()
            # 圆角裁切，看起来像头像
            S = 64
            out = QPixmap(S, S)
            out.fill(_Qt.transparent)
            p = QPainter(out)
            p.setRenderHint(QPainter.Antialiasing)
            p.setClipPath(self._round_path(S, S, 12))
            p.drawPixmap(0, 0, pm.scaled(S, S, _Qt.KeepAspectRatioByExpanding,
                                         _Qt.SmoothTransformation))
            p.end()
            return QIcon(out)
        except Exception:
            return QIcon()

    @staticmethod
    def _round_path(w, h, r):
        from PySide6.QtGui import QPainterPath
        from PySide6.QtCore import QRectF
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        return path

    def _style_check(self, box):
        """Fusion draws an invisible indicator on dark backgrounds; draw our own.

        The check mark is rendered to a temp PNG and referenced from the QSS,
        because Qt style sheets cannot embed vector drawings.
        """
        box.setFont(QFont("Microsoft YaHei", 9))
        box.setCursor(Qt.PointingHandCursor)

        mark = ""
        try:
            tmp = os.path.join(tempfile.gettempdir(), "vera_check_16.png")
            check_icon(16).save(tmp, "PNG")
            mark = tmp.replace("\\", "/")
        except Exception:
            mark = ""

        img_rule = f"image: url({mark});" if mark else ""
        box.setStyleSheet(f"""
            QCheckBox {{ color: {FG}; border: none; spacing: 9px; padding: 2px 0; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid #3b4250;
                border-radius: 4px;
                background: {CARD2};
            }}
            QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border: 1px solid {ACCENT};
                {img_rule}
            }}
        """)

    def _btn_style(self, secondary=False):
        if secondary:
            return (f"QPushButton{{background:{CARD2};color:{FG};border:1px solid #2f3441;"
                    "border-radius:8px;padding:6px 12px;font-size:12px;}"
                    f"QPushButton:hover{{background:#2c313d;border-color:{ACCENT};}}"
                    "QPushButton:disabled{color:#5b6270;}")
        return f"QPushButton{{background:{ACCENT};color:#0d1117;border-radius:8px;}}"

    # ------------------------------------------------------------ actions
    def _gather(self):
        self.cfg["api_key"] = self.key_edit.text().strip()
        self.cfg["base_url"] = self.url_edit.text().strip() or "https://api.deepseek.com"
        self.cfg["model"] = self.model_box.currentText().strip() or "deepseek-flash"
        self.cfg["voice"] = "stella" if self.voice_box.currentIndex() == 0 else "tide"
        self.cfg["persona"] = self._current_persona_key()
        self.cfg["iso_path"] = self.iso_edit.text().strip()
        self.cfg["game_room_code"] = self.game_room_code.text().strip().upper()
        self.cfg["auto_launch_assistant"] = self.with_assist.isChecked()
        self.cfg["record_progress"] = self.record_progress.isChecked()
        self.cfg["bubble_size"] = self.bubble_size_box.currentData()
        self.cfg["duck_game_audio"] = self.duck_check.isChecked()
        self.cfg["peer_enabled"] = self.peer_enabled.isChecked()
        self.cfg["peer_is_host"] = self.peer_mode.currentIndex() == 0
        self.cfg["peer_remote"] = self.peer_remote.text().strip()
        self.cfg["peer_local_ip"] = self.peer_adapter.currentData() or ""
        try:
            self.cfg["peer_port"] = int(self.peer_port.text().strip() or 7150)
        except ValueError:
            self.cfg["peer_port"] = 7150
        return self.cfg

    def save_cfg(self):
        cfg = self._gather()
        if config.save(cfg):
            self.api_status.setText("已保存")
            self.api_status.setStyleSheet(f"color:{OK};font-size:11px;border:none;")
        else:
            self.api_status.setText("保存失败")
            self.api_status.setStyleSheet(f"color:{ERR};font-size:11px;border:none;")

    def test_api(self):
        cfg = self._gather()
        key = cfg.get("api_key")
        if not key:
            self.api_status.setText("先填 API Key")
            self.api_status.setStyleSheet(f"color:{WARN};font-size:11px;border:none;")
            return
        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中…")
        self.api_status.setText("正在连接…")
        self.api_status.setStyleSheet(f"color:{DIM};font-size:11px;border:none;")

        base = cfg["base_url"].rstrip("/")
        model = cfg["model"]

        def work():
            import urllib.error
            import urllib.request
            try:
                payload = json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                }).encode()
                req = urllib.request.Request(base + "/chat/completions", data=payload, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Authorization", f"Bearer {key}")
                with urllib.request.urlopen(req, timeout=20) as r:
                    r.read()
                msg, col = "连接成功", OK
            except urllib.error.HTTPError as e:
                code = e.code
                msg = {401: "Key 无效", 403: "无权限", 402: "余额不足",
                       429: "请求太频繁"}.get(code, f"HTTP {code}")
                col = ERR
            except Exception as ex:
                msg, col = f"连不上（{type(ex).__name__}）", ERR
            # cross-thread: emit a signal, never touch widgets or QTimer here
            try:
                self.test_result.emit(msg, col)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _test_done(self, msg, col):
        self.test_btn.setEnabled(True)
        self.test_btn.setText("测试连接")
        self.api_status.setText(msg)
        self.api_status.setStyleSheet(f"color:{col};font-size:11px;border:none;")

    def pick_iso(self):
        start = os.path.dirname(self.iso_edit.text()) or config.GAME_ROOT
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 PS2 镜像", start,
            "PS2 镜像 (*.iso *.bin *.img);;所有文件 (*.*)")
        if path:
            self.iso_edit.setText(path)
            self._check_iso()

    def _check_iso(self):
        p = self.iso_edit.text().strip()
        if not p:
            return
        if not os.path.exists(p):
            self.iso_status.setText("文件不存在")
            self.iso_status.setStyleSheet(f"color:{ERR};font-size:11px;border:none;")
            return
        size = os.path.getsize(p)
        gb = size / 1073741824
        ok = 1.5 < gb < 5.0
        note = "大小正常" if ok else "大小可疑（正常约 1.75 GB）"
        self.iso_status.setText(f"{gb:.2f} GB · {note}")
        self.iso_status.setStyleSheet(
            f"color:{OK if ok else WARN};font-size:11px;border:none;")

    def _exe(self):
        """The game executable."""
        return os.path.join(config.GAME_ROOT, "recvx.exe")

    def _assist_cmd(self):
        """Command that starts the assistant, whether frozen or from source."""
        if config.FROZEN:
            return [sys.executable, "--assistant"]
        script = os.path.join(config.DATA, "voice_companion.py")
        py = sys.executable
        pyw = py.replace("python.exe", "pythonw.exe")
        return [pyw if os.path.exists(pyw) else py, script]

    def launch(self):
        cfg = self._gather()
        iso = cfg["iso_path"]
        exe = self._exe()

        if not os.path.exists(exe):
            QMessageBox.critical(self, "出错", f"找不到游戏程序：\n{exe}")
            return
        if not iso or not os.path.exists(iso):
            QMessageBox.warning(self, "缺少镜像",
                                "请先选择 PS2 游戏镜像（美版 SLUS-20184）。")
            return

        config.save(cfg)

        if self.game_proc is None or self.game_proc.poll() is not None:
            try:
                # NEW_PROCESS_GROUP lets the game outlive the launcher;
                # NO_WINDOW keeps a console from flashing up.
                flags = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                         | getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.game_proc = subprocess.Popen(
                    [exe, iso, "--windowed"],
                    cwd=config.GAME_ROOT,
                    creationflags=flags,
                    stdin=subprocess.DEVNULL,
                )
            except Exception as e:
                QMessageBox.critical(self, "启动失败", f"游戏启动失败：\n{e}")
                return

        if self.with_assist.isChecked():
            want_assist = config.has_api_key(cfg)
            if want_assist:
                self._start_assistant()
            else:
                self.status.setText("未配置 API Key，助手未启动。")

        self.refresh_status()

    def launch_assistant_only(self):
        cfg = self._gather()
        if not config.has_api_key(cfg):
            self._prompt_key()
            return
        config.save(cfg)
        self._start_assistant()

    def _start_assistant(self):
        if self.assist_proc and self.assist_proc.poll() is None:
            self.status.setText("助手已经在运行了。")
            return
        try:
            self.assist_proc = subprocess.Popen(
                self._assist_cmd(), cwd=config.DATA,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"助手启动失败：\n{e}")

    def _prompt_key(self):
        QMessageBox.information(
            self, "需要配置 AI",
            "还没有填写 API Key。\n\n"
            "陪玩助手需要 DeepSeek 的 API Key 才能工作：\n"
            "1. 打开 platform.deepseek.com\n"
            "2. 注册登录后，左侧「API Keys」→「创建 API Key」\n"
            "3. 复制 sk- 开头的那串，粘贴到上面的「API Key」框\n\n"
            "不填也能正常玩游戏，只是没有 AI 陪玩。"
        )

    def show_progress(self):
        p = config.load_progress()
        rooms = p.get("rooms", {})
        if not rooms:
            QMessageBox.information(self, "探索进度", "还没有记录。开始游戏后会自动累积。")
            return

        lines = [f"共探索 {len(rooms)} 个房间"]
        if p.get("first_seen"):
            lines.append(f"首次游玩：{p['first_seen']}")
        lines.append("")
        for key, info in sorted(rooms.items(), key=lambda kv: kv[1].get("last", ""), reverse=True)[:20]:
            lines.append(f"· {info.get('label', key)}  （{info.get('visits', 1)} 次）")
        if len(rooms) > 20:
            lines.append(f"… 还有 {len(rooms) - 20} 个")
        QMessageBox.information(self, "探索进度", "\n".join(lines))

    def refresh_status(self):
        parts = []
        running_game = self.game_proc is not None and self.game_proc.poll() is None
        running_ai = self.assist_proc is not None and self.assist_proc.poll() is None
        parts.append("游戏运行中" if running_game else "游戏未启动")
        if config.has_api_key(self.cfg):
            parts.append("助手运行中" if running_ai else "助手待命")
        else:
            parts.append("AI 未配置")
        self.status.setText("  ·  ".join(parts))
        if not self.iso_status.text() and self.iso_edit.text():
            self._check_iso()


def main():
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    w = Launcher()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
