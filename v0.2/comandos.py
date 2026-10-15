import subprocess
import webbrowser
import os
import random
import pyttsx3
import threading

# --- SISTEMA DE VOZ LOCAL (SAPI5 de Windows) ---
def hablar(texto):
    """Hace que la mascota hable en segundo plano sin congelar la app"""
    def _run_tts():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 165) # Velocidad de la voz
            
            # Buscar una voz en español si está disponible en Windows
            voices = engine.getProperty('voices')
            for voice in voices:
                if "spanish" in voice.name.lower() or "es" in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
                    
            engine.say(texto)
            engine.runAndWait()
        except Exception as e:
            print(f"Error de voz: {e}")

    threading.Thread(target=_run_tts, daemon=True).start()

# Frases para cotorrear antes de chambear
SALUDOS = [
    "A volar 🚀",
    "Señor...",
    "Ya tome Café virtual ☕",
    "¡Set-up Listo! 💻",
    "¡A sus Ordenes!"
]

def ejecutar_comando(texto):
    """
    Analiza el texto reconocido por voz y ejecuta la acción correspondiente.
    Retorna una tupla: (nombre_estado_feliz, mensaje_para_la_burbuja) o (None, None) si no coincide.
    """
    texto = texto.lower()
    
    # --- COTORREO / SALUDOS ---
    if any(palabra in texto for palabra in ["hola", "buenos días", "buenas tardes", "que onda"]):
        return "feliz", random.choice(SALUDOS)

    if "programar" in texto:
        # Abre el entorno de IA y Colab
        webbrowser.open("https://claude.ai")
        webbrowser.open("https://gemini.google.com")
        webbrowser.open("https://colab.research.google.com")
        return "feliz", "Preparando entorno de programación"
        
    elif "descargar" in texto:
        # Abre el explorador local y Google Drive
        subprocess.Popen(["explorer.exe"])
        webbrowser.open("https://drive.google.com")
        return "feliz", "Abriendo Drive y Archivos"

    elif "conjunto" in texto:
        webbrowser.open("https://www.kaggle.com")
        webbrowser.open("https://huggingface.co/datasets")
        webbrowser.open("https://github.com")
        return "feliz", "Abriendo entornos de datos"

    elif "limpiar" in texto:
        # Cierra Edge, VS Code, Bloc de notas y Calculadora (estén o no abiertos)
        programas = ["msedge.exe", "notepad.exe", "calc.exe"]
        for app in programas:
            subprocess.run(["taskkill", "/f", "/im", app], capture_output=True)
        return "feliz", "Edge, VS Code y apps cerradas"

    elif "notas" in texto:
        subprocess.Popen(["notepad.exe"])
        return "feliz", "Abriendo Bloc de notas"
        
    elif "calculadora" in texto:
        subprocess.Popen(["calc.exe"])
        return "feliz", "Abriendo Calculadora"
        
    elif "explorador" in texto or "archivos" in texto:
        subprocess.Popen(["explorer.exe"])
        return "feliz", "Abriendo Archivos"
        
    elif "claudio" in texto:
        webbrowser.open("https://claude.ai")
        return "feliz", "Abriendo Claude"
        
    elif "navegador" in texto:
        subprocess.Popen(["msedge.exe"], shell=True)
        return "feliz", "Abriendo Edge"

    elif "apágate" in texto:
        return "feliz", "¡Hasta luego!"
        
    # Si dice cualquier otra cosa que no sea comando, cotorrea un poco
    return None, None