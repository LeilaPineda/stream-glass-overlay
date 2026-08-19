import sys
import os
import json
import asyncio
import socket
import ctypes
from ctypes import wintypes
from datetime import datetime
import base64
from pathlib import Path
from twitchAPI.oauth import UserAuthenticator
from aiohttp import web

# ------------------------------------------------------------------------------
# TRUCO DE WINDOWS: Permite que muestre el icono personalizado en la barra de tareas
# ------------------------------------------------------------------------------
try:
    myappid = 'streamglass.overlay.app.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# PyQt6
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QDialog, QFormLayout,
    QSizeGrip, QFrame, QTabWidget, QCheckBox, QColorDialog, QSlider
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect, QAbstractNativeEventFilter, QCoreApplication, QTimer
from PyQt6.QtGui import QPainter, QColor, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView

# Twitch API
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope

# TikTok Live
from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    CommentEvent, LikeEvent, FollowEvent, ShareEvent, GiftEvent
)

# Constantes de Windows
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WM_HOTKEY = 0x0312
HOTKEY_ID = 1001
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
VK_L = 0x4C  # Tecla 'L'

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "tiktok_username": "",
    "twitch_channel": "",
    "twitch_client_id": "",
    "twitch_client_secret": "",
    "theme": {
        "user_color": "#38bdf8",
        "time_color": "#cbd5e1",
        "card_bg": "#1e293b",
        "card_opacity": 75,
        "glass_bg": "#0f172a",
        "border_color": "#38bdf8",
        "show_badges": True,
        "show_time": True,
        "show_tiktok_chat": True,
        "show_tiktok_gifts": True,
        "show_tiktok_likes": True,
        "show_tiktok_follows": True,
        "show_tiktok_shares": True,
        "show_twitch_chat": True,
        "show_twitch_gifts": True,
        "show_twitch_rewards": True
    }
}

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

def load_config():
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.update(data)
                if "theme" in data:
                    config["theme"] = {**DEFAULT_CONFIG["theme"], **data["theme"]}
        except Exception as e:
            print(f"[Config Load Error]: {e}")
    else:
        save_config(config)
    return config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Config Save Error]: {e}")

def hex_to_rgba(hex_str, opacity_percent):
    hex_str = hex_str.lstrip('#')
    r = int(hex_str[0:2], 16) if len(hex_str) >= 2 else 0
    g = int(hex_str[2:4], 16) if len(hex_str) >= 4 else 0
    b = int(hex_str[4:6], 16) if len(hex_str) >= 6 else 0
    a = round(opacity_percent / 100.0, 2)
    return f"rgba({r}, {g}, {b}, {a})"


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("StreamGlass")
        self.setFixedSize(460, 540)
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; }
            QTabWidget::pane { border: 1px solid #334155; background-color: #0f172a; border-radius: 6px; }
            QTabBar::tab { background-color: #1e293b; color: #94a3b8; padding: 6px 12px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: 600; font-size: 11px; }
            QTabBar::tab:selected { background-color: #38bdf8; color: #0f172a; }
            QLabel { color: #94a3b8; font-size: 12px; font-weight: 600; }
            QLineEdit { background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #f8fafc; padding: 6px 10px; font-size: 12px; }
            QLineEdit:focus { border: 1px solid #38bdf8; }
            QCheckBox { color: #f8fafc; font-size: 12px; }
            QSlider::groove:horizontal { height: 6px; background: #334155; border-radius: 3px; }
            QSlider::handle:horizontal { background: #38bdf8; width: 14px; margin: -4px 0; border-radius: 7px; }
            QPushButton { background-color: #38bdf8; color: #0f172a; border: none; border-radius: 6px; padding: 8px 16px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #0284c7; color: white; }
            QPushButton#cancelBtn { background-color: #334155; color: #94a3b8; }
            QPushButton#cancelBtn:hover { background-color: #475569; color: white; }
            QPushButton#resetBtn { background-color: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
            QPushButton#resetBtn:hover { background-color: rgba(239, 68, 68, 0.8); color: white; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("⚙️ Configuración de StreamGlass")
        title.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: 800; margin-bottom: 4px;")
        layout.addWidget(title)

        self.cfg = load_config()
        theme = self.cfg.get("theme", DEFAULT_CONFIG["theme"])

        tabs = QTabWidget()

        tab_conn = QWidget()
        conn_layout = QFormLayout(tab_conn)
        conn_layout.setSpacing(10)

        self.tiktok_input = QLineEdit(self.cfg.get("tiktok_username", ""))
        self.tiktok_input.setPlaceholderText("Tu usuario de TikTok")

        self.twitch_channel_input = QLineEdit(self.cfg.get("twitch_channel", ""))
        self.twitch_channel_input.setPlaceholderText("Tu canal de Twitch")

        self.twitch_id_input = QLineEdit(self.cfg.get("twitch_client_id", ""))
        self.twitch_id_input.setPlaceholderText("Client ID de Twitch (Opcional)")

        self.twitch_secret_input = QLineEdit(self.cfg.get("twitch_client_secret", ""))
        self.twitch_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.twitch_secret_input.setPlaceholderText("Client Secret de Twitch")

        conn_layout.addRow("TikTok Username:", self.tiktok_input)
        conn_layout.addRow("Twitch Channel:", self.twitch_channel_input)
        conn_layout.addRow("Twitch Client ID:", self.twitch_id_input)
        conn_layout.addRow("Twitch Client Secret:", self.twitch_secret_input)
        tabs.addTab(tab_conn, "Conexiones")

        tab_color = QWidget()
        color_layout = QVBoxLayout(tab_color)
        color_layout.setSpacing(8)

        self.btn_border_color = self.create_color_button("Borde Neón Glass", theme.get("border_color", "#38bdf8"))
        self.btn_glass_bg = self.create_color_button("Fondo Ventana Principal", theme.get("glass_bg", "#0f172a"))
        self.btn_card_bg = self.create_color_button("Color Casillas de Chat", theme.get("card_bg", "#1e293b"))
        self.btn_user_color = self.create_color_button("Color Nombre Usuario", theme.get("user_color", "#38bdf8"))
        self.btn_time_color = self.create_color_button("Color Hora del Mensaje", theme.get("time_color", "#cbd5e1"))

        opacity_layout = QHBoxLayout()
        self.lbl_opacity = QLabel(f"Opacidad Casillas: {theme.get('card_opacity', 75)}%")
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(theme.get("card_opacity", 75))
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity.setText(f"Opacidad Casillas: {v}%"))
        
        opacity_layout.addWidget(self.lbl_opacity)
        opacity_layout.addWidget(self.slider_opacity)

        self.reset_btn = QPushButton("🔄 Restablecer Colores por Defecto")
        self.reset_btn.setObjectName("resetBtn")
        self.reset_btn.clicked.connect(self.reset_colors_to_default)

        color_layout.addWidget(self.btn_border_color)
        color_layout.addWidget(self.btn_glass_bg)
        color_layout.addWidget(self.btn_card_bg)
        color_layout.addLayout(opacity_layout)
        color_layout.addWidget(self.btn_user_color)
        color_layout.addWidget(self.btn_time_color)
        color_layout.addWidget(self.reset_btn)
        color_layout.addStretch()
        tabs.addTab(tab_color, "Colores")

        tab_view = QWidget()
        view_layout = QVBoxLayout(tab_view)
        view_layout.setSpacing(6)

        lbl_gen = QLabel("--- GENERAL ---")
        lbl_gen.setStyleSheet("color: #38bdf8; font-size: 11px; margin-top: 2px;")
        self.chk_badges = QCheckBox("Mostrar Badges de Plataforma")
        self.chk_badges.setChecked(theme.get("show_badges", True))
        self.chk_time = QCheckBox("Mostrar Hora de Mensaje")
        self.chk_time.setChecked(theme.get("show_time", True))

        lbl_tt = QLabel("--- TIKTOK ---")
        lbl_tt.setStyleSheet("color: #ff0050; font-size: 11px; margin-top: 6px;")
        self.chk_tt_chat = QCheckBox("Mensajes del Chat")
        self.chk_tt_chat.setChecked(theme.get("show_tiktok_chat", True))
        self.chk_tt_gifts = QCheckBox("Regalos (Gifts)")
        self.chk_tt_gifts.setChecked(theme.get("show_tiktok_gifts", True))
        self.chk_tt_likes = QCheckBox("Likes")
        self.chk_tt_likes.setChecked(theme.get("show_tiktok_likes", True))
        self.chk_tt_follows = QCheckBox("Seguidores (Follows)")
        self.chk_tt_follows.setChecked(theme.get("show_tiktok_follows", True))
        self.chk_tt_shares = QCheckBox("Compartidos (Shares)")
        self.chk_tt_shares.setChecked(theme.get("show_tiktok_shares", True))

        lbl_tw = QLabel("--- TWITCH ---")
        lbl_tw.setStyleSheet("color: #9146ff; font-size: 11px; margin-top: 6px;")
        self.chk_tw_chat = QCheckBox("Mensajes del Chat")
        self.chk_tw_chat.setChecked(theme.get("show_twitch_chat", True))
        self.chk_tw_gifts = QCheckBox("Bits y Suscripciones")
        self.chk_tw_gifts.setChecked(theme.get("show_twitch_gifts", True))
        self.chk_tw_rewards = QCheckBox("Canjes de Puntos y Raids")
        self.chk_tw_rewards.setChecked(theme.get("show_twitch_rewards", True))

        view_layout.addWidget(lbl_gen)
        view_layout.addWidget(self.chk_badges)
        view_layout.addWidget(self.chk_time)
        view_layout.addWidget(lbl_tt)
        view_layout.addWidget(self.chk_tt_chat)
        view_layout.addWidget(self.chk_tt_gifts)
        view_layout.addWidget(self.chk_tt_likes)
        view_layout.addWidget(self.chk_tt_follows)
        view_layout.addWidget(self.chk_tt_shares)
        view_layout.addWidget(lbl_tw)
        view_layout.addWidget(self.chk_tw_chat)
        view_layout.addWidget(self.chk_tw_gifts)
        view_layout.addWidget(self.chk_tw_rewards)
        
        view_layout.addStretch()
        tabs.addTab(tab_view, "Visibilidad")

        layout.addWidget(tabs)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Guardar y Aplicar")
        save_btn.clicked.connect(self.save_and_close)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def create_color_button(self, label_text, initial_color):
        btn = QPushButton(f"  {label_text}")
        btn.color_val = initial_color
        btn.setStyleSheet(f"background-color: {initial_color}; color: #ffffff; text-align: left; padding: 6px; font-weight: bold; border-radius: 6px;")
        btn.clicked.connect(lambda: self.pick_color(btn))
        return btn

    def pick_color(self, button):
        color = QColorDialog.getColor(QColor(button.color_val), self, "Seleccionar Color")
        if color.isValid():
            button.color_val = color.name()
            button.setStyleSheet(f"background-color: {color.name()}; color: #ffffff; text-align: left; padding: 6px; font-weight: bold; border-radius: 6px;")

    def reset_colors_to_default(self):
        def_theme = DEFAULT_CONFIG["theme"]
        self.btn_border_color.color_val = def_theme["border_color"]
        self.btn_border_color.setStyleSheet(f"background-color: {def_theme['border_color']}; color: #ffffff; text-align: left; padding: 6px; font-weight: bold; border-radius: 6px;")
        self.btn_glass_bg.color_val = def_theme["glass_bg"]
        self.btn_glass_bg.setStyleSheet(f"background-color: {def_theme['glass_bg']}; color: #ffffff; text-align: left; padding: 6px; font-weight: bold; border-radius: 6px;")
        self.btn_card_bg.color_val = def_theme["card_bg"]
        self.btn_card_bg.setStyleSheet(f"background-color: {def_theme['card_bg']}; color: #ffffff; text-align: left; padding: 6px; font-weight: bold; border-radius: 6px;")
        self.btn_user_color.color_val = def_theme["user_color"]
        self.btn_user_color.setStyleSheet(f"background-color: {def_theme['user_color']}; color: #ffffff; text-align: left; padding: 6px; font-weight: bold; border-radius: 6px;")
        self.btn_time_color.color_val = def_theme["time_color"]
        self.btn_time_color.setStyleSheet(f"background-color: {def_theme['time_color']}; color: #ffffff; text-align: left; padding: 6px; font-weight: bold; border-radius: 6px;")
        self.slider_opacity.setValue(def_theme["card_opacity"])

    def save_and_close(self):
        new_config = {
            "tiktok_username": self.tiktok_input.text().strip(),
            "twitch_channel": self.twitch_channel_input.text().strip(),
            "twitch_client_id": self.twitch_id_input.text().strip(),
            "twitch_client_secret": self.twitch_secret_input.text().strip(),
            "theme": {
                "border_color": self.btn_border_color.color_val,
                "glass_bg": self.btn_glass_bg.color_val,
                "card_bg": self.btn_card_bg.color_val,
                "card_opacity": self.slider_opacity.value(),
                "user_color": self.btn_user_color.color_val,
                "time_color": self.btn_time_color.color_val,
                "show_badges": self.chk_badges.isChecked(),
                "show_time": self.chk_time.isChecked(),
                "show_tiktok_chat": self.chk_tt_chat.isChecked(),
                "show_tiktok_gifts": self.chk_tt_gifts.isChecked(),
                "show_tiktok_likes": self.chk_tt_likes.isChecked(),
                "show_tiktok_follows": self.chk_tt_follows.isChecked(),
                "show_tiktok_shares": self.chk_tt_shares.isChecked(),
                "show_twitch_chat": self.chk_tw_chat.isChecked(),
                "show_twitch_gifts": self.chk_tw_gifts.isChecked(),
                "show_twitch_rewards": self.chk_tw_rewards.isChecked()
            }
        }
        save_config(new_config)
        self.accept()


class TwitchEventSubWorker(QThread):
    event_received = pyqtSignal(str, str, str, str)

    def __init__(self, client_id, client_secret, channel):
        super().__init__()
        self.daemon = True
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.channel = channel.strip()
        self.is_running = True

    def run(self):
        if not self.client_secret or not self.client_id or not self.channel:
            return

        while self.is_running:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start_eventsub())
            except Exception as e:
                print(f"[Twitch EventSub Error]: {e}")
            finally:
                loop.close()

            for _ in range(5):
                if not self.is_running:
                    break
                self.msleep(1000)

    async def start_eventsub(self):
        try:
            twitch = await Twitch(self.client_id, self.client_secret)
            target_scopes = [
                AuthScope.CHANNEL_READ_REDEMPTIONS,
                AuthScope.BITS_READ,
                AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
                AuthScope.MODERATOR_READ_FOLLOWERS
            ]

            # 1. Función para leer tu logo local de forma segura y convertirlo a texto Base64
            def obtener_logo_base64():
                # Buscamos de forma segura la ruta: assets/logo.png (o cambia a .jpg si es necesario)
                ruta_logo = Path(__file__).parent / 'assets' / 'icon.png'
                
                if ruta_logo.exists():
                    with open(ruta_logo, "rb") as image_file:
                        # Convertimos los bytes de la imagen a una cadena Base64
                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                        return f"data:image/png;base64,{encoded_string}"
                else:
                    # Si por alguna razón no encuentra el archivo, devolvemos un string vacío
                    print(f"[Advertencia]: No se encontró el logo en {ruta_logo}")
                    return ""

            # Guardamos el logo procesado en una variable
            LOGO_SRC = obtener_logo_base64()

            # 2. Definimos tu HTML moderno con la etiqueta de imagen adaptada para StreamGlass
            HTML_PERSONALIZADO = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                {"<link rel='icon' type='image/png' href='" + LOGO_SRC + "'>" if LOGO_SRC else ""}
                
                <title>StreamGlass - Autenticación</title>
                <style>
                    body {{
                        background-color: #0e0e10;
                        color: #efeff1;
                        font-family: 'Segoe UI', Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                    }}
                    .card {{
                        background-color: #1f1f23;
                        padding: 40px;
                        border-radius: 12px;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.6);
                        text-align: center;
                        border: 2px solid #9146ff;
                        max-width: 420px;
                    }}
                    .app-header {{
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        gap: 12px;
                        margin-bottom: 25px;
                    }}
                    .app-logo {{
                        width: 70px;
                        height: 70px;
                        object-fit: contain;
                    }}
                    .app-name {{
                        font-weight: bold;
                        color: #00fff0;
                        font-size: 20px;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                    }}
                    h1 {{
                        color: #9146ff;
                        font-size: 24px;
                        margin-top: 0;
                        margin-bottom: 12px;
                    }}
                    p {{
                        color: #adadb8;
                        font-size: 15px;
                        line-height: 1.6;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="app-header">
                        <!-- Aquí se inyecta dinámicamente tu imagen de la carpeta assets -->
                        {"<img src='" + LOGO_SRC + "' class='app-logo' alt='Logo'>" if LOGO_SRC else ""}
                        <div class="app-name">StreamGlass</div>
                    </div>
                    <h1>¡Autenticación Exitosa!</h1>
                    <p>Tu cuenta se ha conectado correctamente.</p>
                    <p style="margin-top: 25px; font-size: 13px; color: #70707c;">Ya puedes cerrar esta pestaña de forma segura.</p>
                </div>
            </body>
            </html>
            """

            # 3. INYECCIÓN ABSOLUTA A NIVEL DE RESPUESTA DE RED (Mantenemos tu parche exitoso)
            _original_response_init = web.Response.__init__

            def custom_response_init(self, *args, **kwargs):
                if 'text' in kwargs and isinstance(kwargs['text'], str) and 'Authenticating' in kwargs['text']:
                    kwargs['text'] = HTML_PERSONALIZADO
                elif len(args) > 0 and isinstance(args[0], str) and 'Authenticating' in args[0]:
                    args = (HTML_PERSONALIZADO,) + args[1:]
                _original_response_init(self, *args, **kwargs)

            web.Response.__init__ = custom_response_init


            # # Authenticator configurado al puerto 8080
            auth = UserAuthenticator(
                twitch,
                target_scopes,
                force_verify=False,
                url='http://localhost:8080',
                port=8080
            )

            # # Iniciar autenticación
            token, refresh_token = await auth.authenticate()
            await twitch.set_user_authentication(token, target_scopes, refresh_token)


            user_id = None
            async for u in twitch.get_users(logins=[self.channel]):
                user_id = u.id
                break

            if not user_id:
                return

            eventsub = EventSubWebsocket(twitch)
            eventsub.start()

            async def on_reward_redemption(data):
                try:
                    event = data.event
                    user_name = getattr(event, 'user_name', 'Usuario')
                    reward_info = getattr(event, 'reward', None)
                    reward_title = reward_info.title if reward_info else "Recompensa"
                    user_input = getattr(event, 'user_input', '')
                    input_text = f": <i>{user_input}</i>" if user_input else ""
                    self.event_received.emit("Twitch", "reward", user_name, f"canjeó <b>{reward_title}</b>{input_text}")
                except Exception as err:
                    print(f"[Reward Error]: {err}")

            async def on_cheer(data):
                try:
                    event = data.event
                    user_name = getattr(event, 'user_name', 'Anónimo')
                    bits = getattr(event, 'bits', 0)
                    msg = getattr(event, 'message', '')
                    msg_text = f": <i>{msg}</i>" if msg else ""
                    self.event_received.emit("Twitch", "gift", user_name, f"envió <b>{bits} bits</b> 💎{msg_text}")
                except Exception as err:
                    print(f"[Cheer Error]: {err}")

            async def on_raid(data):
                try:
                    event = data.event
                    from_user = getattr(event, 'from_broadcaster_user_name', 'Alguien')
                    viewers = getattr(event, 'viewers', 0)
                    self.event_received.emit("Twitch", "reward", from_user, f"llegó con una <b>Raid de {viewers} espectadores</b>! 🚀")
                except Exception as err:
                    print(f"[Raid Error]: {err}")

            await eventsub.listen_channel_points_custom_reward_redemption_add(user_id, on_reward_redemption)
            await eventsub.listen_channel_cheer(user_id, on_cheer)
            await eventsub.listen_channel_raid(to_broadcaster_user_id=user_id, callback=on_raid)

            while self.is_running:
                await asyncio.sleep(1)

        except Exception as e:
            print(f"[Twitch EventSub Error]: {e}")

    def stop(self):
        self.is_running = False


class TikTokWorker(QThread):
    event_received = pyqtSignal(str, str, str, str)

    def __init__(self, username):
        super().__init__()
        self.daemon = True
        self.username = username
        self.is_running = True

    def run(self):
        if not self.username:
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                client = TikTokLiveClient(unique_id=self.username)

                @client.on(CommentEvent)
                async def on_comment(event: CommentEvent):
                    comment_text = event.comment or ""
                    if hasattr(event, 'emotes') and event.emotes:
                        for emote in event.emotes:
                            image_url = None
                            if hasattr(emote, 'image') and hasattr(emote.image, 'url_list') and emote.image.url_list:
                                image_url = emote.image.url_list[0]
                            elif hasattr(emote, 'url'):
                                image_url = emote.url

                            if image_url:
                                img_tag = f'<img src="{image_url}" class="chat-emote" alt="emote"/>'
                                if not comment_text.strip():
                                    comment_text = img_tag
                                else:
                                    place_holder = getattr(emote, 'place_holder', '')
                                    if place_holder and place_holder in comment_text:
                                        comment_text = comment_text.replace(place_holder, img_tag)
                                    else:
                                        comment_text += f" {img_tag}"

                    tiktok_emoji_map = {
                        "[heart]": "❤️", "[love]": "😍", "[smile]": "😊", "[happy]": "😄",
                        "[laugh]": "😂", "[cry]": "😭", "[angry]": "😡", "[surprised]": "😮",
                        "[thinking]": "🤔", "[thumbup]": "👍", "[fire]": "🔥", "[rose]": "🌹",
                        "[crown]": "👑", "[star]": "⭐", "[100]": "💯", "[party]": "🎉"
                    }
                    for code, emoji_char in tiktok_emoji_map.items():
                        if code in comment_text:
                            comment_text = comment_text.replace(code, emoji_char)

                    if comment_text and comment_text.strip():
                        self.event_received.emit("TikTok", "chat", event.user.nickname, comment_text)

                @client.on(LikeEvent)
                async def on_like(event: LikeEvent):
                    self.event_received.emit("TikTok", "like", event.user.nickname, f"envió {event.count} likes 💖")

                @client.on(FollowEvent)
                async def on_follow(event: FollowEvent):
                    self.event_received.emit("TikTok", "follow", event.user.nickname, "¡ahora te sigue! 👤")

                @client.on(GiftEvent)
                async def on_gift(event: GiftEvent):
                    if event.gift.streakable and event.streaking:
                        return
                    gift_text = f"envió {event.repeat_count} x {event.gift.name}" if event.gift.streakable else f"envió {event.gift.name}"
                    self.event_received.emit("TikTok", "gift", event.user.nickname, gift_text)

                @client.on(ShareEvent)
                async def on_share(event: ShareEvent):
                    self.event_received.emit("TikTok", "share", event.user.nickname, "¡compartió el live! ⭐")

                client.run()

            except Exception as e:
                print(f"[TikTok Error]: {e}")
            
            for _ in range(5):
                if not self.is_running:
                    break
                self.sleep(1)

    def stop(self):
        self.is_running = False


class TwitchWorker(QThread):
    event_received = pyqtSignal(str, str, str, str)

    def __init__(self, channel):
        super().__init__()
        self.daemon = True
        self.channel = channel
        self.is_running = True

    def run(self):
        if not self.channel:
            return
        
        server = "irc.chat.twitch.tv"
        port = 6667
        nickname = "justinfan84729"
        channel_name = f"#{self.channel.lower()}"

        while self.is_running:
            sock = None
            try:
                sock = socket.socket()
                sock.settimeout(15.0)
                sock.connect((server, port))
                sock.send("CAP REQ :twitch.tv/tags twitch.tv/commands\r\n".encode("utf-8"))
                sock.send(f"NICK {nickname}\r\n".encode("utf-8"))
                sock.send(f"JOIN {channel_name}\r\n".encode("utf-8"))

                while self.is_running:
                    try:
                        resp = sock.recv(4096).decode("utf-8", errors="ignore")
                    except socket.timeout:
                        sock.send("PING :tmi.twitch.tv\r\n".encode("utf-8"))
                        continue

                    if not resp:
                        break

                    if resp.startswith("PING"):
                        sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                        continue

                    for line in resp.split("\r\n"):
                        if not line:
                            continue

                        if "USERNOTICE" in line:
                            tags = {}
                            if line.startswith("@"):
                                tag_part = line.split(" ")[0][1:]
                                for tag in tag_part.split(";"):
                                    if "=" in tag:
                                        k, v = tag.split("=", 1)
                                        tags[k] = v
                            
                            user = tags.get("display-name") or tags.get("login") or "Usuario"
                            msg_id = tags.get("msg-id", "")
                            system_msg = tags.get("system-msg", "").replace(r"\s", " ")

                            if msg_id in ["sub", "resub", "subgift", "anonsubgift", "submysterygift"]:
                                detail = "¡se ha <b>suscripto</b> al canal! ⭐"
                                if system_msg:
                                    detail += f" (<i>{system_msg}</i>)"
                                self.event_received.emit("Twitch", "gift", user, detail)

                            elif msg_id == "raid":
                                viewers = tags.get("msg-param-viewerCount", "varios")
                                detail = f"llegó con una <b>Raid de {viewers} espectadores</b>! 🚀"
                                self.event_received.emit("Twitch", "reward", user, detail)

                        elif "PRIVMSG" in line:
                            tags = {}
                            if line.startswith("@"):
                                tag_part = line.split(" ")[0][1:]
                                for tag in tag_part.split(";"):
                                    if "=" in tag:
                                        k, v = tag.split("=", 1)
                                        tags[k] = v
                            
                            user = tags.get("display-name", "Usuario")
                            msg = line.split(" PRIVMSG ")[1].split(" :", 1)[1] if " :" in line else ""
                            emotes_tag = tags.get("emotes", "")
                            bits = tags.get("bits", "0")

                            if bits != "0":
                                detail = f"envió <b>{bits} bits</b> 💎: <i>{msg}</i>"
                                self.event_received.emit("Twitch", "gift", user, detail)
                            else:
                                if msg and emotes_tag:
                                    msg = self.parse_twitch_emotes(msg, emotes_tag)

                                if msg:
                                    self.event_received.emit("Twitch", "chat", user, msg)

            except Exception as e:
                print(f"[Twitch IRC Error]: {e}")
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

            for _ in range(5):
                if not self.is_running:
                    break
                self.sleep(1)

    def parse_twitch_emotes(self, message, emotes_str):
        try:
            replacements = []
            for emote_data in emotes_str.split('/'):
                if not emote_data:
                    continue
                emote_id, positions = emote_data.split(':')
                first_pos = positions.split(',')[0]
                start, end = map(int, first_pos.split('-'))
                emote_code = message[start:end+1]
                
                img_tag = f'<img src="https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/dark/1.0" class="chat-emote" alt="{emote_code}"/>'
                replacements.append((emote_code, img_tag))

            for code, img_tag in replacements:
                message = message.replace(code, img_tag)
        except Exception as e:
            print(f"[Emote Parse Error]: {e}")
            
        return message

    def stop(self):
        self.is_running = False


class GlassCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.opacity_val = 0.70
        self.border_color_val = QColor(56, 189, 248)
        self.bg_color_val = QColor(15, 23, 42)

    def set_opacity(self, opacity):
        self.opacity_val = opacity
        self.update()

    def set_border_color(self, hex_color):
        self.border_color_val = QColor(hex_color)
        self.update()

    def set_bg_color(self, hex_color):
        self.bg_color_val = QColor(hex_color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        alpha = int(self.opacity_val * 255)
        bg_color = QColor(self.bg_color_val)
        bg_color.setAlpha(alpha)

        border_c = QColor(self.border_color_val)
        border_c.setAlpha(int(min(255, alpha + 60)))

        painter.setBrush(bg_color)
        painter.setPen(border_c)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)


class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))

            # Atajo global (Ctrl + Alt + L) para alternar el bloqueo
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.overlay.toggle_lock()
                return True, 0

        return False, 0


class StreamGlassOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.is_locked = False
        self.tiktok_thread = None
        self.twitch_thread = None
        self.twitch_eventsub_thread = None
        self.current_conn_credentials = {}

        # CÓDIGO CORREGIDO:
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(360, 520)

        # REGISTRAR ATAJO GLOBAL (Ctrl + Alt + L)
        self.win_filter = WinEventFilter(self)
        QCoreApplication.instance().installNativeEventFilter(self.win_filter)
        
        hwnd = int(self.winId())
        ctypes.windll.user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_L)

        base_dir = os.path.dirname(__file__)
        possible_paths = [
            os.path.join(base_dir, 'assets', 'icon.png'),
            os.path.join(base_dir, 'icon.png'),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                break

        # TIMER PARA DETECTAR EL CURSOR SIN HOOKS
        self.lock_checker_timer = QTimer(self)
        self.lock_checker_timer.setInterval(30)
        self.lock_checker_timer.timeout.connect(self._check_mouse_over_lock)

        self.init_ui()
        self.apply_theme()
        self.start_workers()

        cfg = load_config()
        if not cfg.get("tiktok_username") and not cfg.get("twitch_channel"):
            self.open_settings()

    def _check_mouse_over_lock(self):
        if not self.is_locked or not hasattr(self, 'lock_btn'):
            return

        user32 = ctypes.windll.user32
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))

        btn = self.lock_btn
        global_pos = btn.mapToGlobal(btn.rect().topLeft())
        btn_rect = QRect(global_pos, btn.size())

        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        if btn_rect.contains(pt.x, pt.y):
            if style & WS_EX_TRANSPARENT:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
        else:
            if not (style & WS_EX_TRANSPARENT):
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT)

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.card = GlassCard(self)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 8)
        card_layout.setSpacing(6)

        self.header_layout = QHBoxLayout()
        self.title_label = QLabel("StreamGlass")
        self.title_label.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 13px; background: transparent;")

        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.12);
                color: white;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.4);
            }
        """

        btn_close_style = """
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                color: #f87171;
                border-radius: 6px;
                border: 1px solid rgba(239, 68, 68, 0.4);
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.8);
                color: white;
            }
        """

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(22, 22)
        self.settings_btn.setStyleSheet(btn_style)
        self.settings_btn.clicked.connect(self.open_settings)

        self.test_btn = QPushButton("🧪")
        self.test_btn.setToolTip("Probar alertas (Simulación Offline)")
        self.test_btn.setFixedSize(22, 22)
        self.test_btn.setStyleSheet(btn_style)
        self.test_btn.clicked.connect(self.simulate_events)

        self.op_minus_btn = QPushButton("-")
        self.op_minus_btn.setFixedSize(22, 22)
        self.op_minus_btn.setStyleSheet(btn_style)
        self.op_minus_btn.clicked.connect(lambda: self.change_opacity(-0.1))

        self.op_plus_btn = QPushButton("+")
        self.op_plus_btn.setFixedSize(22, 22)
        self.op_plus_btn.setStyleSheet(btn_style)
        self.op_plus_btn.clicked.connect(lambda: self.change_opacity(0.1))

        self.clear_btn = QPushButton("🗑️")
        self.clear_btn.setFixedSize(22, 22)
        self.clear_btn.setStyleSheet(btn_style)
        self.clear_btn.clicked.connect(self.clear_chat)

        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setFixedSize(26, 22)
        self.lock_btn.setStyleSheet(btn_style)
        self.lock_btn.clicked.connect(self.toggle_lock)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setStyleSheet(btn_close_style)
        self.close_btn.clicked.connect(self.close_app)

        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.test_btn)
        self.header_layout.addWidget(self.settings_btn)
        self.header_layout.addWidget(self.op_minus_btn)
        self.header_layout.addWidget(self.op_plus_btn)
        self.header_layout.addWidget(self.clear_btn)
        self.header_layout.addWidget(self.lock_btn)
        self.header_layout.addWidget(self.close_btn)

        self.header_container = QWidget()
        self.header_container.setLayout(self.header_layout)
        card_layout.addWidget(self.header_container, 0)

        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.web_view.setStyleSheet("background: transparent;")
        card_layout.addWidget(self.web_view, 1)

        self.init_html_chat()

        self.footer_layout = QHBoxLayout()
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        self.size_grip.setStyleSheet("QSizeGrip { background-color: #38bdf8; border-radius: 4px; }")

        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.size_grip)
        
        self.footer_container = QWidget()
        self.footer_container.setLayout(self.footer_layout)
        card_layout.addWidget(self.footer_container, 0)

        root_layout.addWidget(self.card)
        self.old_pos = None

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        if self.is_locked:
            self.lock_btn.setText("🔒")

            if hasattr(self, 'pin_btn'): self.pin_btn.hide()
            if hasattr(self, 'settings_btn'): self.settings_btn.hide()
            if hasattr(self, 'clear_btn'): self.clear_btn.hide()
            if hasattr(self, 'close_btn'): self.close_btn.hide()
            if hasattr(self, 'test_btn'): self.test_btn.hide()
            if hasattr(self, 'op_minus_btn'): self.op_minus_btn.hide()
            if hasattr(self, 'op_plus_btn'): self.op_plus_btn.hide()
            if hasattr(self, 'size_grip'): self.size_grip.hide()

            self.web_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.web_view.page().runJavaScript("hideScrollbar(); clearSelection();")

            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT)
            self.lock_checker_timer.start()

        else:
            self.lock_btn.setText("🔓")
            self.lock_checker_timer.stop()

            if hasattr(self, 'pin_btn'): self.pin_btn.show()
            if hasattr(self, 'settings_btn'): self.settings_btn.show()
            if hasattr(self, 'clear_btn'): self.clear_btn.show()
            if hasattr(self, 'close_btn'): self.close_btn.show()
            if hasattr(self, 'test_btn'): self.test_btn.show()
            if hasattr(self, 'op_minus_btn'): self.op_minus_btn.show()
            if hasattr(self, 'op_plus_btn'): self.op_plus_btn.show()
            if hasattr(self, 'size_grip'): self.size_grip.show()

            self.web_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.web_view.page().runJavaScript("showScrollbar();")

            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)

        self.update()

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.apply_theme()
            self.start_workers()

    def apply_theme(self):
        cfg = load_config()
        theme = cfg.get("theme", DEFAULT_CONFIG["theme"])

        self.card.set_border_color(theme.get("border_color", "#38bdf8"))
        self.card.set_bg_color(theme.get("glass_bg", "#0f172a"))

        card_rgba = hex_to_rgba(
            theme.get("card_bg", "#1e293b"), 
            theme.get("card_opacity", 75)
        )

        hide_badges = "true" if not theme.get("show_badges", True) else "false"
        hide_time = "true" if not theme.get("show_time", True) else "false"

        js_script = f"""
            document.documentElement.style.setProperty('--user-color', '{theme.get("user_color", "#38bdf8")}');
            document.documentElement.style.setProperty('--time-color', '{theme.get("time_color", "#cbd5e1")}');
            document.documentElement.style.setProperty('--card-bg', '{card_rgba}');

            document.body.classList.toggle('hide-badges', {hide_badges});
            document.body.classList.toggle('hide-time', {hide_time});
        """
        self.web_view.page().runJavaScript(js_script)

    def simulate_events(self):
        import random
        tests = [
            ("Twitch", "gift", "Viewer_Fiel", "envió <b>500 bits</b> 💎"),
            ("Twitch", "gift", "Fanatico_01", "¡se ha <b>suscripto</b> al canal! ⭐ (Tier 1)"),
            ("Twitch", "reward", "StreamerAmigo", "llegó con una <b>Raid de 45 espectadores</b>! 🚀"),
            ("TikTok", "gift", "UserTikTok", "envió 5 x Rosa 🎁"),
            ("TikTok", "follow", "NuevoSeguidor", "¡ahora te sigue! 👤")
        ]
        p, t, u, d = random.choice(tests)
        self.handle_event(p, t, u, d)

    def init_html_chat(self):
        base_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                :root {
                    --user-color: #38bdf8;
                    --time-color: #cbd5e1;
                    --card-bg: rgba(30, 41, 59, 0.75);
                }

                * {
                    user-select: none !important;
                    -webkit-user-select: none !important;
                }

                html, body {
                    height: 100%; margin: 0; padding: 0;
                    overflow-x: hidden;
                    overflow-y: auto;
                    background-color: transparent;
                    font-family: 'Segoe UI', Inter, sans-serif;
                    color: #f1f5f9; font-size: 13px;
                    scroll-behavior: smooth;
                }
                
                ::-webkit-scrollbar { width: 5px; }
                ::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.2); border-radius: 4px; }
                ::-webkit-scrollbar-thumb { background: rgba(56, 189, 248, 0.4); border-radius: 4px; }
                ::-webkit-scrollbar-thumb:hover { background: rgba(56, 189, 248, 0.8); }

                #chat-wrapper {
                    display: flex;
                    flex-direction: column;
                    justify-content: flex-end;
                    min-height: 100%;
                    box-sizing: border-box;
                    padding-right: 6px;
                    padding-bottom: 6px;
                }

                .msg-card {
                    background: var(--card-bg);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px; padding: 8px 10px;
                    margin-top: 6px; backdrop-filter: blur(8px);
                    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                    word-wrap: break-word; line-height: 1.4;
                }
                .reward-card {
                    background: linear-gradient(135deg, rgba(16, 185, 129, 0.3), rgba(6, 78, 59, 0.6));
                    border: 1px solid #10b981;
                    box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
                }
                .gift-card {
                    background: linear-gradient(135deg, rgba(236, 72, 153, 0.3), rgba(131, 24, 67, 0.6));
                    border: 1px solid #ec4899;
                    box-shadow: 0 0 10px rgba(236, 72, 153, 0.3);
                }
                .badge {
                    display: inline-block; padding: 2px 6px;
                    border-radius: 4px; font-weight: 800; font-size: 9px;
                    color: white; margin-right: 4px; text-transform: uppercase;
                }
                
                .time {
                    font-size: 10px;
                    color: var(--time-color);
                    margin-right: 6px;
                    font-weight: 700;
                    background: rgba(0, 0, 0, 0.35);
                    padding: 2px 5px;
                    border-radius: 4px;
                    text-shadow: 0px 1px 2px rgba(0, 0, 0, 0.9);
                    letter-spacing: 0.3px;
                }

                .tiktok { background: #ff0050; }
                .twitch { background: #9146FF; }
                .reward-badge { background: #10b981; color: #000; }
                .user { color: var(--user-color); font-weight: 700; }
                
                .chat-emote {
                    height: 28px;
                    vertical-align: middle;
                    margin: 0 2px;
                }

                body.hide-badges .badge { display: none !important; }
                body.hide-time .time { display: none !important; }

                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(12px) scale(0.96); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }
            </style>
        </head>
        <body>
            <div id="chat-wrapper"></div>
            <script>
                let autoScroll = true;

                window.addEventListener('scroll', () => {
                    const distanceToBottom = document.documentElement.scrollHeight - window.innerHeight - window.scrollY;
                    autoScroll = distanceToBottom < 50;
                });

                function scrollToBottomForce() {
                    if (autoScroll) {
                        const wrapper = document.getElementById('chat-wrapper');
                        if (wrapper.lastElementChild) {
                            wrapper.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
                        }
                    }
                }

                function appendCard(htmlContent, extraClass) {
                    const wrapper = document.getElementById('chat-wrapper');
                    const div = document.createElement('div');
                    div.className = 'msg-card ' + (extraClass || '');
                    div.innerHTML = htmlContent;
                    wrapper.appendChild(div);

                    const images = div.querySelectorAll('img');
                    images.forEach(img => {
                        img.onload = () => scrollToBottomForce();
                    });

                    scrollToBottomForce();
                }

                function clearChat() {
                    document.getElementById('chat-wrapper').innerHTML = '';
                    autoScroll = true;
                }

                function clearSelection() {
                    if (window.getSelection) {
                        window.getSelection().removeAllRanges();
                    }
                }

                function hideScrollbar() {
                    document.body.style.overflow = 'hidden';
                    clearSelection();
                }

                function showScrollbar() {
                    document.body.style.overflow = 'auto';
                }
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(base_html)

    def change_opacity(self, delta):
        new_op = max(0.1, min(1.0, self.card.opacity_val + delta))
        self.card.set_opacity(new_op)

    def clear_chat(self):
        self.web_view.page().runJavaScript("clearChat();")

    def handle_event(self, platform, event_type, user, detail):
        cfg = load_config()
        theme = cfg.get("theme", DEFAULT_CONFIG["theme"])

        if platform == "TikTok":
            if event_type == "chat" and not theme.get("show_tiktok_chat", True):
                return
            if event_type == "gift" and not theme.get("show_tiktok_gifts", True):
                return
            if event_type == "like" and not theme.get("show_tiktok_likes", True):
                return
            if event_type == "follow" and not theme.get("show_tiktok_follows", True):
                return
            if event_type == "share" and not theme.get("show_tiktok_shares", True):
                return

        elif platform == "Twitch":
            if event_type == "chat" and not theme.get("show_twitch_chat", True):
                return
            if event_type == "gift" and not theme.get("show_twitch_gifts", True):
                return
            if event_type == "reward" and not theme.get("show_twitch_rewards", True):
                return

        badge_class = "tiktok" if platform == "TikTok" else "twitch"
        p_badge = f'<span class="badge {badge_class}">{platform}</span>'
        current_time = datetime.now().strftime("%H:%M")
        time_tag = f'<span class="time">{current_time}</span>'
        card_class = ""

        if event_type == "reward":
            p_badge = '<span class="badge reward-badge">ALERTA</span>'
            msg_html = f'{time_tag}{p_badge} <span class="user">{user}</span> {detail}'
            card_class = "reward-card"
        elif event_type in ["gift", "like"]:
            msg_html = f'{time_tag}{p_badge} <span class="user">{user}</span> {detail}'
            card_class = "gift-card" if event_type == "gift" else ""
        elif event_type == "chat":
            msg_html = f'{time_tag}{p_badge} <span class="user">{user}:</span> {detail}'
        else:
            msg_html = f'{time_tag}{p_badge} <span class="user">{user}</span> {detail}'

        clean_html = msg_html.replace("'", "\\'").replace("\n", "")
        js_code = f"appendCard('{clean_html}', '{card_class}');"
        self.web_view.page().runJavaScript(js_code)

    def start_workers(self):
        cfg = load_config()
        
        new_credentials = {
            "tiktok": cfg.get("tiktok_username"),
            "twitch": cfg.get("twitch_channel"),
            "twitch_id": cfg.get("twitch_client_id"),
            "twitch_secret": cfg.get("twitch_client_secret")
        }

        if self.current_conn_credentials == new_credentials:
            return

        self.current_conn_credentials = new_credentials

        if self.tiktok_thread and self.tiktok_thread.isRunning():
            self.tiktok_thread.terminate()
        if self.twitch_thread and self.twitch_thread.isRunning():
            self.twitch_thread.terminate()
        if self.twitch_eventsub_thread and self.twitch_eventsub_thread.isRunning():
            self.twitch_eventsub_thread.stop()
            self.twitch_eventsub_thread.terminate()

        if cfg.get("tiktok_username"):
            self.tiktok_thread = TikTokWorker(cfg.get("tiktok_username"))
            self.tiktok_thread.event_received.connect(self.handle_event)
            self.tiktok_thread.start()

        if cfg.get("twitch_channel"):
            self.twitch_thread = TwitchWorker(cfg.get("twitch_channel"))
            self.twitch_thread.event_received.connect(self.handle_event)
            self.twitch_thread.start()

        if cfg.get("twitch_client_id") and cfg.get("twitch_client_secret") and cfg.get("twitch_channel"):
            self.twitch_eventsub_thread = TwitchEventSubWorker(
                cfg.get("twitch_client_id"),
                cfg.get("twitch_client_secret"),
                cfg.get("twitch_channel")
            )
            self.twitch_eventsub_thread.event_received.connect(self.handle_event)
            self.twitch_eventsub_thread.start()

    def close_app(self):
        self.lock_checker_timer.stop()
        hwnd = int(self.winId())
        ctypes.windll.user32.UnregisterHotKey(hwnd, HOTKEY_ID)
        QApplication.quit()
        sys.exit(0)

    def closeEvent(self, event):
        self.lock_checker_timer.stop()
        hwnd = int(self.winId())
        ctypes.windll.user32.UnregisterHotKey(hwnd, HOTKEY_ID)
        QApplication.quit()
        sys.exit(0)

    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if not self.is_locked and self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    base_dir = os.path.dirname(__file__)
    possible_paths = [
        os.path.join(base_dir, 'assets', 'icon-window.jpg'),
        os.path.join(base_dir, 'icon-window.jpg'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            app.setWindowIcon(QIcon(path))
            break

    overlay = StreamGlassOverlay()
    overlay.show()
    sys.exit(app.exec())