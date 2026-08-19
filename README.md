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
```
---

## 📦 Instalación y Configuración
1. Clonar o descargar el repositorio
```bash
git clone [https://github.com/tu-usuario/stream-glass-overlay.git](https://github.com/tu-usuario/stream-glass-overlay.git)
cd stream-glass-overlay
```
2. Crear y activar el entorno virtual
```bash
python -m venv venv
.\venv\Scripts\activate
```
3. Instalar dependencias
```bash
pip install -r requirements.txt
```

## ⚙️ Uso en Desarrollo
Para ejecutar la aplicación desde el código fuente:
```bash
python main.py
```
**¿Prefieres usar la versión compilada?** Si no deseas instalar Python ni clonar el repositorio, puedes ir a la sección de Releases y descargar el archivo ejecutable listo para usar (.exe) con un solo clic.
---

## 🛠️ Compilación a Ejecutable (.exe)
Si realizas cambios en el código y deseas regenerar el ejecutable usando PyInstaller:
```bash
pyinstaller StreamGlass.spec
```
O mediante el comando directo:
```bash
pyinstaller --noconsole --onefile --icon="assets/icon-window.ico" --add-data "assets;assets" --name="StreamGlass" main.py
```

El ejecutable resultante se ubicará en la carpeta dist/StreamGlass.exe.

---

## 📌 Puntos Técnicos Destacados
* **Icono de la Barra de Tareas:** Se configuró ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID y se removió la bandera Qt.WindowType.Tool para permitir que Windows asocie la aplicación con su propio ejecutable e icono .ico.
* **Manejo de Rutas Relativas:** Bucle dinámico possible_paths para cargar imágenes desde assets/ tanto en el entorno de desarrollo .py como dentro del paquete empaquetado de PyInstaller.
* **Persistencia de Tokens OAuth:** Control de sesión para evitar que twitchAPI reabra el navegador en cada inicio.
