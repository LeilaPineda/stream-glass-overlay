# 🌟 StreamGlass Overlay

**StreamGlass Overlay** es una aplicación de escritorio desarrollada en Python y PyQt6 pensada para streamers. Ofrece una superposición flotante con estilo *Glassmorphism* (cristal esmerilado) totalmente transparente a los clics (*click-through*), permitiendo monitorear eventos e interactuar con transmisiones en directo de **TikTok** y **Twitch** sin interrumpir el juego o pantalla principal.

---

## 🚀 Características Principales

* **Interfaz Glassmorphism:** Fondo translúcido elegante que se integra sobre cualquier juego o ventana.
* **Transparencia de Clics (Click-Through):** Modo flotante pasivo que deja pasar los clics del mouse hacia los juegos u otras aplicaciones activas.
* **Multichat & Eventos:** Conexión a WebSockets en tiempo real para capturar chats y eventos de TikTok Live y Twitch.
* **Temporizador / Cronómetro Incorporado:** Ideal para metas, retos y dinámicas de subathon o retransmisión.
* **Integración Nativa en Windows:** Configuración de `AppUserModelID` para asignar el icono personalizado a la barra de tareas.
* **Ejecutable Autónomo (.exe):** Generación de ejecutable listo para correr sin requerir instalación previa de Python.

---

## 🛠️ Tecnologías Utilizadas

* **Lenguaje:** Python 3.10+
* **GUI Framework:** PyQt6
* **Integraciones:** `TikTokLive`, `twitchAPI`
* **Compilación:** PyInstaller
* **Sistema Operativo:** Windows 10 / 11

---

## 📁 Estructura del Proyecto

```text
stream-glass-overlay/
├── assets/
│   ├── icon-window.ico
│   ├── icon-window.jpg
│   └── icon.png
├── config.json
├── main.py
├── main.spec
├── README.md
├── requirements.txt
└── StreamGlass.spec
