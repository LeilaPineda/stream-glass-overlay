import sys
import os
import json
import asyncio
import socket
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QDialog, QFormLayout,
    QSizeGrip, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView

# Twitch API
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope
from twitchAPI.eventsub.websocket import EventSubWebsocket

# TikTok Live
from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    CommentEvent, LikeEvent, FollowEvent, ShareEvent, GiftEvent
)

CONFIG_FILE = "config.json"

# ==============================================================================
# GESTOR DE CONFIGURACIÓN (config.json)
# ==============================================================================
def load_config():
    default_config = {
        "tiktok_username": "xleiila__",
        "twitch_channel": "xLEILA__",
        "twitch_client_id": "gwdubz4u3jmdxixwhwu6gu0vswkylq",
        "twitch_client_secret": ""
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:
            print(f"[Config Load Error]: {e}")
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Config Save Error]: {e}")

# ==============================================================================
# DIÁLOGO DE CONFIGURACIÓN / SETTINGS
# ==============================================================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Configuración - StreamGlass")
        self.setFixedSize(380, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background-color: #38bdf8;
                color: #0f172a;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: white;
            }
            QPushButton#cancelBtn {
                background-color: #334155;
                color: #94a3b8;
            }
            QPushButton#cancelBtn:hover {
                background-color: #475569;
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("🔑 Configuración de Cuentas & API")
        title.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: 800; margin-bottom: 8px;")
        layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.cfg = load_config()

        self.tiktok_input = QLineEdit(self.cfg.get("tiktok_username", ""))
        self.tiktok_input.setPlaceholderText("Ej: xleiila__")

        self.twitch_channel_input = QLineEdit(self.cfg.get("twitch_channel", ""))
        self.twitch_channel_input.setPlaceholderText("Ej: xLEILA__")

        self.twitch_id_input = QLineEdit(self.cfg.get("twitch_client_id", ""))
        self.twitch_id_input.setPlaceholderText("Client ID de Twitch")

        self.twitch_secret_input = QLineEdit(self.cfg.get("twitch_client_secret", ""))
        self.twitch_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.twitch_secret_input.setPlaceholderText("Client Secret de Twitch")

        form_layout.addRow("TikTok Username:", self.tiktok_input)
        form_layout.addRow("Twitch Channel:", self.twitch_channel_input)
        form_layout.addRow("Twitch Client ID:", self.twitch_id_input)
        form_layout.addRow("Twitch Client Secret:", self.twitch_secret_input)

        layout.addLayout(form_layout)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Guardar y Conectar")
        save_btn.clicked.connect(self.save_and_close)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def save_and_close(self):
        new_config = {
            "tiktok_username": self.tiktok_input.text().strip(),
            "twitch_channel": self.twitch_channel_input.text().strip(),
            "twitch_client_id": self.twitch_id_input.text().strip(),
            "twitch_client_secret": self.twitch_secret_input.text().strip()
        }
        save_config(new_config)
        self.accept()

# ==============================================================================
# WORKERS
# ==============================================================================
class TwitchEventSubWorker(QThread):
    event_received = pyqtSignal(str, str, str, str)

    def __init__(self, client_id, client_secret, channel):
        super().__init__()
        self.daemon = True
        self.client_id = client_id
        self.client_secret = client_secret
        self.channel = channel.strip()
        self.is_running = True

    def run(self):
        if not self.client_secret or not self.client_id or not self.channel:
            print("[EventSub] ⚠️ Falta Client ID, Secret o Channel en la configuración.")
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start_eventsub())
        except Exception as e:
            print(f"[Twitch EventSub Error Grave]: {e}")

    async def start_eventsub(self):
        try:
            print(f"[EventSub] Iniciando autenticación para el canal: {self.channel}...")
            twitch = await Twitch(self.client_id, self.client_secret)
            
            scopes = [
                AuthScope.CHANNEL_READ_REDEMPTIONS,
                AuthScope.BITS_READ,
                AuthScope.CHANNEL_READ_SUBSCRIPTIONS
            ]
            
            # Forzamos puerto 1755 para renovar la autorización limpia
            auth = UserAuthenticator(twitch, scopes, port=1755, url='http://localhost:1755')
            token, refresh_token = await auth.authenticate()
            await twitch.set_user_authentication(token, scopes, refresh_token)

            # Obtener ID del streamer
            user_id = None
            async for u in twitch.get_users(logins=[self.channel]):
                user_id = u.id
                print(f"[EventSub] ID de usuario encontrado para {self.channel}: {user_id}")
                break

            if not user_id:
                print(f"[EventSub] ❌ No se pudo encontrar el ID de Twitch para {self.channel}")
                return

            eventsub = EventSubWebsocket(twitch)
            eventsub.start()

            # --- CALLBACK DE CANJES ---
            async def on_reward_redemption(data):
                try:
                    event = data.event
                    user_name = getattr(event, 'user_name', 'Usuario')
                    
                    # Extraer el título de la recompensa de forma segura
                    reward_info = getattr(event, 'reward', None)
                    reward_title = reward_info.title if reward_info else "Recompensa"
                    
                    user_input = getattr(event, 'user_input', '')
                    input_text = f": <i>{user_input}</i>" if user_input else ""
                    
                    detail = f"canjeó <b>{reward_title}</b>{input_text}"
                    print(f"[EventSub DETECTADO]: {user_name} -> {reward_title}")
                    
                    self.event_received.emit("Twitch", "reward", user_name, detail)
                except Exception as err:
                    print(f"[EventSub Error en Callback]: {err}")

            # Suscribir evento
            await eventsub.listen_channel_points_custom_reward_redemption_add(user_id, on_reward_redemption)
            
            print("✅ [EventSub]: Escuchando Canjes de Puntos en tiempo real...")

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

    def run(self):
        if not self.username:
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = TikTokLiveClient(unique_id=self.username)

        # 1. COMENTARIOS Y EMOTES
        @client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            comment_text = event.comment or ""

            # Procesar emotes personalizados (tus 15 emoticonos) y la barra interactiva de TikTok
            if hasattr(event, 'emotes') and event.emotes:
                for emote in event.emotes:
                    image_url = None
                    if hasattr(emote, 'image') and hasattr(emote.image, 'url_list') and emote.image.url_list:
                        image_url = emote.image.url_list[0]
                    elif hasattr(emote, 'url'):
                        image_url = emote.url

                    if image_url:
                        img_tag = f'<img src="{image_url}" class="chat-emote" alt="emote"/>'
                        
                        # Si envió SOLO el emote sin texto adicional
                        if not comment_text.strip():
                            comment_text = img_tag
                        else:
                            # Si envió texto + emote
                            place_holder = getattr(emote, 'place_holder', '')
                            if place_holder and place_holder in comment_text:
                                comment_text = comment_text.replace(place_holder, img_tag)
                            else:
                                comment_text += f" {img_tag}"

            # Mapeo de stickers/caritas de sistema si TikTok no mandó URL de imagen
            tiktok_emoji_map = {
                "[heart]": "❤️", "[love]": "😍", "[smile]": "😊", "[happy]": "😄",
                "[laugh]": "😂", "[cry]": "😭", "[angry]": "😡", "[surprised]": "😮",
                "[thinking]": "🤔", "[thumbup]": "👍", "[fire]": "🔥", "[rose]": "🌹",
                "[crown]": "👑", "[star]": "⭐", "[100]": "💯", "[party]": "🎉"
            }

            for code, emoji_char in tiktok_emoji_map.items():
                if code in comment_text:
                    comment_text = comment_text.replace(code, emoji_char)

            # Emitir si hay texto o la imagen del emote renderizada
            if comment_text and comment_text.strip():
                
                self.event_received.emit("TikTok", "chat", event.user.nickname, comment_text)

        @client.on(LikeEvent)
        async def on_like(event: LikeEvent):
            self.event_received.emit("TikTok", "like", event.user.nickname, f"envió {event.count} likes 💖")

        @client.on(FollowEvent)
        async def on_follow(event: FollowEvent):
            self.event_received.emit("TikTok", "follow", event.user.nickname, "¡ahora te sigue! 👤")

        # Define la función que reacciona al evento de regalo
        @client.on(GiftEvent)
        async def on_gift(event: GiftEvent):
            client.logger.info("Received a gift!")

        # Can have a streak and streak is over
            if event.gift.streakable and event.streaking:
                return

            # Cannot have a streak
            if event.gift.streakable:
                gift_text = f"envió {event.repeat_count} x {event.gift.name}"

            else: 
                gift_text = f"envió {event.gift.name}"

            self.event_received.emit("TikTok", "gift", event.user.nickname, gift_text)
                    


        @client.on(ShareEvent)
        async def on_share(event: ShareEvent):
            self.event_received.emit("TikTok", "share", event.user.nickname, f"¡compartió el live! ⭐")

        try:
            client.run()
        except Exception as e:
            print(f"[TikTok Error]: {e}")


class TwitchWorker(QThread):
    event_received = pyqtSignal(str, str, str, str)

    def __init__(self, channel):
        super().__init__()
        self.daemon = True
        self.channel = channel

    def run(self):
        if not self.channel:
            return
        server = "irc.chat.twitch.tv"
        port = 6667
        nickname = "justinfan84729"
        channel_name = f"#{self.channel.lower()}"

        try:
            sock = socket.socket()
            sock.connect((server, port))
            sock.send("CAP REQ :twitch.tv/tags twitch.tv/commands\r\n".encode("utf-8"))
            sock.send(f"NICK {nickname}\r\n".encode("utf-8"))
            sock.send(f"JOIN {channel_name}\r\n".encode("utf-8"))

            while True:
                resp = sock.recv(4096).decode("utf-8", errors="ignore")
                if resp.startswith("PING"):
                    sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                    continue

                for line in resp.split("\r\n"):
                    if "PRIVMSG" in line:
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

                        if msg and emotes_tag:
                            msg = self.parse_twitch_emotes(msg, emotes_tag)

                        if msg:
                            self.event_received.emit("Twitch", "chat", user, msg)
        except Exception as e:
            print(f"[Twitch IRC Error]: {e}")

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


# ==============================================================================
# MARCO GLASSMORPHISM NEÓN
# ==============================================================================
class GlassCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.opacity_val = 0.70

    def set_opacity(self, opacity):
        self.opacity_val = opacity
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        alpha = int(self.opacity_val * 255)
        bg_color = QColor(15, 23, 42, alpha)
        border_color = QColor(56, 189, 248, int(min(255, alpha + 60)))

        painter.setBrush(bg_color)
        painter.setPen(border_color)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)


# ==============================================================================
# OVERLAY PRINCIPAL
# ==============================================================================
class StreamGlassOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.is_locked = False
        self.tiktok_thread = None
        self.twitch_thread = None
        self.twitch_eventsub_thread = None
        
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(360, 520)
        self.init_ui()
        self.start_workers()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.card = GlassCard(self)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 8)
        card_layout.setSpacing(6)

        # HEADER
        self.header_layout = QHBoxLayout()
        self.title_label = QLabel("✨ StreamGlass")
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

        # WEB ENGINE CHAT
        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.web_view.setStyleSheet("background: transparent;")
        card_layout.addWidget(self.web_view, 1)

        self.init_html_chat()

        # FOOTER
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

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.start_workers()

    def simulate_events(self):
        """Boton de pruebas (offline)"""
        import random
        tests = [
            ("Twitch", "gift", "Viewer_Fiel", "envió <b>500 bits</b> 💎"),
            ("Twitch", "gift", "Fanatico_01", "¡se ha <b>suscripto</b> al canal! ⭐ (Tier 1)"),
            ("Twitch", "reward", "StreamerAmigo", "llegó con una <b>Raid de 45 espectadores</b>! 🚀"),
            ("Twitch", "follow", "NuevoSeguidor", "¡ahora sigue el canal! 💜"),
            ("TikTok", "gift", "UserTikTok", "regaló 5x Rosa 🎁")
        ]
        p, t, u, d = random.choice(tests)
        self.handle_event(p, t, u, d)

    def init_html_chat(self):
        base_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                html, body {
                    height: 100%; margin: 0; padding: 0;
                    overflow-x: hidden;
                    overflow-y: auto;
                    background-color: transparent;
                    font-family: 'Segoe UI', Inter, sans-serif;
                    color: #f1f5f9; font-size: 13px;
                    scroll-behavior: smooth;
                }
                
                ::-webkit-scrollbar {
                    width: 5px;
                }
                ::-webkit-scrollbar-track {
                    background: rgba(15, 23, 42, 0.2);
                    border-radius: 4px;
                }
                ::-webkit-scrollbar-thumb {
                    background: rgba(56, 189, 248, 0.4);
                    border-radius: 4px;
                }
                ::-webkit-scrollbar-thumb:hover {
                    background: rgba(56, 189, 248, 0.8);
                }

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
                    background: rgba(30, 41, 59, 0.75);
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
                    color: #94a3b8;
                    margin-right: 6px;
                    font-weight: 600;
                }
                .tiktok { background: #ff0050; }
                .twitch { background: #9146FF; }
                .reward-badge { background: #10b981; color: #000; }
                .user { color: #38bdf8; font-weight: 700; }
                
                .chat-emote {
                height: 28px;              /* Ajusta la altura del emote */
                vertical-align: middle;    /* Lo alinea a la mitad del texto */
                margin: 0 2px;             /* Un pequeño margen a los lados */
                }

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

                function hideScrollbar() {
                    document.body.style.overflow = 'hidden';
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

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.header_container.hide()
            self.footer_container.hide()
            self.lock_btn.setParent(self)
            self.lock_btn.move(self.width() - 34, 8)
            self.lock_btn.show()
            self.web_view.page().runJavaScript("hideScrollbar();")
        else:
            self.lock_btn.setText("🔓")
            self.lock_btn.setParent(None)
            self.header_layout.addWidget(self.lock_btn)
            self.header_layout.addWidget(self.close_btn)
            self.close_btn.show()
            self.header_container.show()
            self.footer_container.show()
            self.web_view.page().runJavaScript("showScrollbar();")

    def handle_event(self, platform, event_type, user, detail):
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
        QApplication.quit()
        sys.exit(0)

    def closeEvent(self, event):
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
    overlay = StreamGlassOverlay()
    overlay.show()
    sys.exit(app.exec())