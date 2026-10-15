import sys
import time
import speech_recognition as sr
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QWidget

import comandos

# --- CEREBRO Y MÁQUINA DE ESTADOS (PET BRAIN) ---
class PetBrain:
    def __init__(self):
        self.current_state = "normal"  # normal, escuchando, procesando, feliz, aburrida
        self.last_interaction_time = time.time()

    def registrar_actividad(self):
        """Reinicia el cronómetro de inactividad solo ante acciones reales"""
        self.last_interaction_time = time.time()
        # Si estaba aburrida y el usuario interactúa, regresa a normal
        if self.current_state == "aburrida":
            self.current_state = "normal"

    def verificar_inactividad(self):
        """Si pasan más de 45 segundos sin interacción real, pasa a aburrida"""
        if time.time() - self.last_interaction_time > 45:
            if self.current_state == "normal":
                return True
        return False


# --- HILO EN SEGUNDO PLANO PARA LA VOZ ---
class VoiceWorker(QThread):
    change_state = pyqtSignal(str)
    command_executed = pyqtSignal(str, str, bool) # (estado, mensaje, es_actividad_real)

    def run(self):
        r = sr.Recognizer()
        r.dynamic_energy_threshold = False
        r.energy_threshold = 200
        r.pause_threshold = 1.0

        while True:
            try:
                with sr.Microphone() as source:
                    self.change_state.emit("escuchando")
                    audio = r.listen(source, timeout=5, phrase_time_limit=6)
                
                self.change_state.emit("procesando")
                texto = r.recognize_google(audio, language="es-MX").lower()
                print(f"🗣️ [Tú dijiste]: \"{texto}\"")
                
                # Delegamos la ejecución a comandos.py
                estado, mensaje = comandos.ejecutar_comando(texto)
                
                if estado:
                    # Comando exitoso: Cuenta como actividad real del usuario
                    self.command_executed.emit(estado, mensaje, True)
                else:
                    # Habló pero no fue un comando reconocido
                    self.command_executed.emit("normal", f"No entendí '{texto}'", True)
                
                self.msleep(2000)

            except sr.WaitTimeoutError:
                # El tiempo de escucha expiró (solo silencio/fondo). NO cuenta como actividad.
                self.change_state.emit("normal")
            except sr.UnknownValueError:
                self.change_state.emit("normal")
            except Exception as e:
                print(f"⚠️ Error en voz: {e}")
                self.change_state.emit("normal")


# --- VENTANA DE LA MASCOTA CON ESTADOS Y BURBUJA ---
class MascotWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(220, 190)
        
        self.brain = PetBrain()
        self.bubble_text = "¡Hola! Te escucho"
        self.show_bubble = True
        self.old_pos = None

        # Temporizador para ocultar la burbuja automáticamente
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.hide_bubble_text)
        self.bubble_timer.start(4000)

        # Temporizador de latido del sistema (revisa inactividad cada 5 segundos)
        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self.check_system_state)
        self.system_timer.start(5000)

        # Iniciar hilo de voz
        self.worker = VoiceWorker()
        self.worker.change_state.connect(self.update_state_only)
        self.worker.command_executed.connect(self.trigger_action_feedback)
        self.worker.start()

    def update_state_only(self, new_state):
        # Solo cambia el estado visual momentáneo (escuchando/procesando) 
        # PERO NO reinicia el cronómetro de inactividad.
        if self.brain.current_state != "aburrida":
            self.brain.current_state = new_state
            
        if new_state == "escuchando":
            self.bubble_text = "Escuchando..."
            self.show_bubble = True
        elif new_state == "procesando":
            self.bubble_text = "Procesando..."
            self.show_bubble = True
        self.update()

    def trigger_action_feedback(self, new_state, message, es_actividad_real):
        if es_actividad_real:
            self.brain.registrar_actividad() # ¡Aquí sí reiniciamos el reloj porque el usuario hizo algo!
            
        self.brain.current_state = new_state
        self.bubble_text = message
        self.show_bubble = True
        self.bubble_timer.start(4000)
        self.update()

    def check_system_state(self):
        """Verifica si la mascota debe aburrirse por inactividad real"""
        if self.brain.verificar_inactividad():
            self.brain.current_state = "aburrida"
            self.bubble_text = "¿Sigues ahí? 😴"
            self.show_bubble = True
            self.update()

    def hide_bubble_text(self):
        self.show_bubble = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Dibujar Burbuja de Texto
        if self.show_bubble and self.bubble_text:
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(QColor(200, 200, 200))
            painter.drawRoundedRect(10, 10, 200, 45, 10, 10)
            
            painter.setPen(QColor(45, 55, 72))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(20, 20, 180, 25, Qt.AlignmentFlag.AlignCenter, self.bubble_text)

        # 2. Dibujar Ojitos según el estado
        painter.setBrush(QColor(45, 55, 72))
        painter.setPen(Qt.PenStyle.NoPen)
        state = self.brain.current_state
        
        if state == "normal":
            painter.drawEllipse(60, 85, 30, 45)
            painter.drawEllipse(130, 85, 30, 45)
            
        elif state == "escuchando":
            painter.drawEllipse(58, 80, 34, 50)
            painter.drawEllipse(128, 80, 34, 50)
            
        elif state == "procesando":
            painter.drawRect(60, 100, 30, 15)
            painter.drawRect(130, 100, 30, 15)
            
        elif state == "feliz":
            painter.drawChord(60, 95, 30, 30, 0, 180 * 16)
            painter.drawChord(130, 95, 30, 30, 0, 180 * 16)
            
        elif state == "aburrida":
            # Ojos cansados
            painter.drawRect(60, 102, 30, 8)
            painter.drawRect(130, 102, 30, 8)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.brain.registrar_actividad() # Si hace clic o arrastra la mascota, también cuenta como actividad
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def trigger_action_feedback(self, new_state, message, es_actividad_real):
        if es_actividad_real:
            self.brain.registrar_actividad()
            
        self.brain.current_state = new_state
        self.bubble_text = message
        self.show_bubble = True
        self.bubble_timer.start(4000)
        self.update()

        # --- AQUÍ VA EL TRIGGER DE CIERRE ---
        if message == "¡Hasta luego!":
            QTimer.singleShot(1500, QApplication.quit)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = MascotWindow()
    pet.show()
    sys.exit(app.exec())