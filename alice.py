import sys
import math
import random
import threading
import pyttsx3
import speech_recognition as sr
import psutil
import requests
import time
import json
import sqlite3
import os


from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QProgressBar
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPointF
)
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPainterPath, QRadialGradient, QPen
)
# ---- Memory Manager with SQLite ----

class MemoryManager:
    triggers = {
        "name": "personal",
        "birthday": "personal",
        "favorite food": "preferences",
        "hobby": "preferences",
        "favorite color": "preferences",
        "user mood": "emotional",
        "last conversation topic": "context",
        "last joke": "context",
        "last reminder": "context",
        "last question": "context",
        "work info": "context",
        "health status": "personal",
        "recent event": "context",
        "plans": "context",
        "favorite music": "preferences",
        "favorite anime": "preferences",
        "relationship status": "personal",
        "pet name": "personal",
        "current weather comment": "context",
        "favorite movie": "preferences"
    }

    def __init__(self, db_path="memories.db", forget_after_seconds=3600):
        self.db_path = db_path
        self.forget_after = forget_after_seconds
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            trigger TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL,
            category TEXT
        )
        ''')
        conn.commit()
        conn.close()

    def add_memory(self, trigger, content):
        timestamp = time.time()
        category = self.get_category_for_trigger(trigger)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO memories (trigger, content, timestamp, category)
        VALUES (?, ?, ?, ?)
        ''', (trigger, content, timestamp, category))
        conn.commit()
        conn.close()

    def get_category_for_trigger(self, trigger):
        return self.triggers.get(trigger, "general")

    def get_relevant_memories(self, limit=5):
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT trigger, content, timestamp, category FROM memories
        WHERE timestamp > ? ORDER BY timestamp DESC LIMIT ?
        ''', (now - self.forget_after, limit))
        memories = cursor.fetchall()
        conn.close()
        return memories

    def delete_old_memories(self):
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        DELETE FROM memories WHERE timestamp < ?
        ''', (now - self.forget_after,))
        conn.commit()
        conn.close()

    def format_memories_for_context(self, limit=10):
        memories = self.get_relevant_memories(limit=limit)
        context_lines = []
        for trigger, content, timestamp, category in memories:
            context_lines.append(f"[{category}] {trigger}: {content}")
        return "\n".join(context_lines)



# ---- Voice Listening Thread ----
class VoiceListener(QThread):
    command_received = pyqtSignal(str)

    def run(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source)
            try:
                audio = recognizer.listen(source, timeout=5)
                command = recognizer.recognize_google(audio)
            except Exception:
                command = ""
        self.command_received.emit(command)


# ---- TTS Worker Thread ----
class TTSThread(QThread):
    finished = pyqtSignal()

    def __init__(self, engine, lock, text):
        super().__init__()
        self.engine = engine
        self.lock = lock
        self.text = text

    def run(self):
        with self.lock:
            self.engine.say(self.text)
            self.engine.runAndWait()
        self.finished.emit()


# ---- Waveform for animation ----
class WaveformLine:
    def __init__(self, width):
        self.width = width
        self.points = [0] * self.width
        self.phase = 0

    def update_wave(self):
        self.phase += 0.1
        for i in range(self.width):
            self.points[i] = math.sin(i * 0.05 + self.phase) * 20


# ---- Particle class (twinkling stars) ----
class Particle:
    def __init__(self, max_w, max_h):
        self.max_w = max_w
        self.max_h = max_h
        self.reset()

    def reset(self):
        self.x = random.uniform(0, self.max_w)
        self.y = random.uniform(0, self.max_h)
        self.size = random.uniform(1, 3)
        self.alpha = random.randint(80, 180)
        self.speed = random.uniform(0.1, 0.3)

    def move(self, max_h):
        self.y += self.speed
        if self.y > max_h:
            self.reset()
            self.y = 0


# ---- Satellite orbiting dots ----
class Satellite:
    def __init__(self, orbit_radius, speed, size):
        self.orbit_radius = orbit_radius
        self.speed = speed
        self.size = size
        self.angle = random.uniform(0, 360)

    def update(self):
        self.angle = (self.angle + self.speed) % 360


# ---- Radar Sweep arc ----
class RadarSweep:
    def __init__(self, radius, speed):
        self.radius = radius
        self.speed = speed
        self.angle = 0

    def update(self):
        self.angle = (self.angle + self.speed) % 360


# ---- Main HUD Widget ----

class AliceHUD(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Alice AI Assistant - Ultra HUD")
        self.setGeometry(300, 100, 1280, 800)
        self.setStyleSheet("background-color: black;")

        # Initialize animations
        self.waveform = WaveformLine(self.width())
        self.particles = [Particle(self.width(), self.height()) for _ in range(120)]
        self.satellites = [
            Satellite(220, 0.6, 18),
            Satellite(160, -1.1, 16),
            Satellite(280, 0.8, 20),
        ]
        self.radar_sweeps = [
            RadarSweep(160, 1.2),
            RadarSweep(120, -1.5),
            RadarSweep(200, 0.8)
        ]

        # Bottom translucent control bar
        self.bottom_widget = QWidget(self)
        self.bottom_widget.setFixedHeight(80)
        self.bottom_widget.setStyleSheet("background-color: rgba(0,0,0,150);")
        self.bottom_widget.move(0, self.height() - 80)
        self.bottom_widget.resize(self.width(), 80)

        # Speak Button
        self.listen_button = QPushButton("🎙 Speak", self.bottom_widget)
        self.listen_button.setFont(QFont("Consolas", 14))
        self.listen_button.setStyleSheet("""
            QPushButton {
                background-color: #00FFFF;
                color: black;
                border-radius: 10px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #33FFFF;
            }
        """)
        self.listen_button.move(20, 20)
        self.listen_button.clicked.connect(self.listen)

        # CPU Progress Bar
        self.cpu_bar = QProgressBar(self.bottom_widget)
        self.cpu_bar.setGeometry(150, 25, 200, 30)
        self.cpu_bar.setMaximum(100)
        self.cpu_bar.setFormat("CPU Usage: %p%")
        self.cpu_bar.setStyleSheet(
            "QProgressBar {color: cyan;} QProgressBar::chunk {background-color: cyan;}"
        )

        # RAM Usage Label
        self.ram_label = QLabel("RAM Usage: 0%", self.bottom_widget)
        self.ram_label.setFont(QFont("Consolas", 12))
        self.ram_label.setStyleSheet("color: cyan;")
        self.ram_label.move(370, 30)

        # Status label on top center
        self.status_label = QLabel("System online. Awaiting your command...", self)
        self.status_label.setFont(QFont("Consolas", 18))
        self.status_label.setStyleSheet("color: cyan;")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.resize(self.width(), 40)
        self.status_label.move(0, 20)

        # Setup TTS engine and lock
        self.engine = pyttsx3.init()
        self.tts_lock = threading.Lock()
        self.set_female_voice()

        # Voice listening thread placeholder
        self.voice_thread = None

        # TTS thread placeholder
        self.tts_thread = None

        # Initialize memory manager
        self.memory_manager = MemoryManager()

        # Timer for animation refresh
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)

        # Timer for system info updates
        self.system_timer = QTimer()
        self.system_timer.timeout.connect(self.update_system_stats)
        self.system_timer.start(1000)

        # Initial greeting
        self.speak("System online. Welcome back, my dear~")
        QTimer.singleShot(2000, self.listen)  # Auto start listening after 2 sec

    def resizeEvent(self, event):
        # Keep bottom widget and status label correctly positioned on resize
        self.bottom_widget.move(0, self.height() - 80)
        self.bottom_widget.resize(self.width(), 80)
        self.status_label.resize(self.width(), 40)
        super().resizeEvent(event)

    def set_female_voice(self):
        voices = self.engine.getProperty('voices')
        for voice in voices:
            if "female" in voice.name.lower() or "zira" in voice.name.lower():
                self.engine.setProperty('voice', voice.id)
                break
        self.engine.setProperty('rate', 175)

    def speak(self, text):
        # Prevent overlapping speech
        if self.tts_thread is not None and self.tts_thread.is_alive():
            return

        self.status_label.setText(text)
        self.tts_thread = threading.Thread(target=self._speak_thread, args=(text,))
        self.tts_thread.start()

    def _speak_thread(self, text):
        with self.tts_lock:
            self.engine.say(text)
            self.engine.runAndWait()
        # Could emit a signal here to indicate done speaking if needed

    def listen(self):
        self.status_label.setText("🎧 Listening...")
        # If voice_thread already running, stop it
        if self.voice_thread is not None and self.voice_thread.isRunning():
            # Proper thread termination depends on VoiceListener implementation
            # For now, just ignore or wait
            pass
        # Start new voice listening thread
        self.voice_thread = VoiceListener()
        self.voice_thread.command_received.connect(self.handle_command)
        self.voice_thread.start()

    def handle_command(self, text):
        if not text:
            self.status_label.setText("Didn't catch that. Try again!")
            QTimer.singleShot(1500, self.listen)
            return

        self.status_label.setText(f"🗨️ You said: {text}")

        # Update memory based on triggers found in text
        self.process_memory_triggers(text)

        # Call AI response after a short delay
        QTimer.singleShot(300, lambda: self.get_ai_response(text))

    def process_memory_triggers(self, text):
        # Lowercase for easier matching
        text_lc = text.lower()

        # Check known triggers and update memory
        for trigger in self.memory_manager.triggers.keys():
            if trigger in text_lc:
                # Save full text as memory for demo
                self.memory_manager.add_memory(trigger, text)
                break

    def get_ai_response(self, prompt):
        # Compose context with memory for better AI replies
        memory_context = self.memory_manager.format_memories_for_context()
        full_prompt = f"{memory_context}\nUser said: {prompt}\nAlice responds:"

        # Query LM Studio chat API
        ai_response = self.query_lm_studio_chat(full_prompt)

        # Update memory with last conversation topic
        self.memory_manager.add_memory("last conversation topic", prompt)

        # Speak AI response
        self.speak(ai_response)

    def query_lm_studio_chat(self, prompt):
        url = "http://192.168.56.1:1234/v1/chat/completions"

        # Define Alice's personality in the system prompt
        system_prompt = (
            "You are Alice, a gentle and caring AI waifu. "
            "You speak softly and express subtle affection and a bit of tsundere teasing. "
            "You remember your user well and respond warmly, sometimes flustered or playful."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": "meta-llama-3.1-8b-instruct",  # Use your actual chat-capable model here
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 200,
            "top_p": 0.9
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            return text.strip() if text else "Sorry, I couldn't generate a response."
        except Exception as e:
            print(f"Error querying LM Studio: {e}")
            return "Oops, I had trouble thinking right now."

    def update_animation(self):
        # Update all animated elements
        self.waveform.update_wave()
        for p in self.particles:
            p.move(self.height())
        for sat in self.satellites:
            sat.update()
        for radar in self.radar_sweeps:
            radar.update()
        self.update()

    def update_system_stats(self):
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        self.cpu_bar.setValue(int(cpu_usage))
        self.ram_label.setText(f"RAM Usage: {ram_usage}%")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background gradient
        grad = QRadialGradient(self.width() // 2, self.height() // 2, self.width() // 1.2)
        grad.setColorAt(0, QColor(0, 255, 255, 30))
        grad.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(self.rect(), grad)

        pen_wave = QPen(QColor(0, 255, 255, 120), 2)
        painter.setPen(pen_wave)
        for i in range(self.waveform.width - 1):
            painter.drawLine(
                i,
                int(self.height() // 2 + self.waveform.points[i]),
                i + 1,
                int(self.height() // 2 + self.waveform.points[i + 1])
            )

        # Draw particles (twinkling stars)
        for p in self.particles:
            color = QColor(0, 255, 255, p.alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(p.x, p.y), p.size, p.size)

        # Draw satellites orbiting center
        cx, cy = self.width() // 2, self.height() // 2
        pen_sat = QPen(QColor(0, 255, 255, 180))
        painter.setPen(pen_sat)
        painter.setBrush(QColor(0, 255, 255, 180))
        for sat in self.satellites:
            rad = math.radians(sat.angle)
            x = cx + sat.orbit_radius * math.cos(rad)
            y = cy + sat.orbit_radius * math.sin(rad)
            painter.drawEllipse(QPointF(x, y), int(sat.size), int(sat.size))

        # Draw radar sweeps (rotating arcs)
        pen_radar = QPen(QColor(0, 255, 255, 100), 2)
        painter.setPen(pen_radar)
        for radar in self.radar_sweeps:
            start_angle = int(radar.angle * 16)
            span_angle = int(60 * 16)
            rect = self.rect().adjusted(
                cx - radar.radius,
                cy - radar.radius,
                -(self.width() - cx - radar.radius),
                -(self.height() - cy - radar.radius)
            )
            painter.drawArc(rect, start_angle, span_angle)

        painter.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AliceHUD()
    window.show()
    sys.exit(app.exec_())