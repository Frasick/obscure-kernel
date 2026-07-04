#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OBSCURE KERNEL GUI v11.0 (ULTIMATE CUSTOMIZATION + VISIBLE TERMINAL)
Created By Obscure
"""

import os
import sys
import time
import random
import logging
import subprocess
import urllib.parse
import json
import traceback
import re
import threading
from datetime import datetime
from pathlib import Path
from ctypes import *
from contextlib import contextmanager

# PyQt6 Импорты
try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QTabWidget, QPushButton, QLabel, 
                                 QLineEdit, QTextEdit, QSlider, QGroupBox,
                                 QGridLayout, QComboBox, QCheckBox, QFileDialog, QMessageBox)
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QIcon, QTextCursor, QColor, QPalette, QBrush, QPixmap
    HAS_PYQT = True
except ImportError:
    print("Ошибка: Не установлен PyQt6. Выполните: sudo pacman -S python-pyqt6")
    sys.exit(1)

# Внешние зависимости
try:
    import feedparser
    import requests
    import speech_recognition as sr
    import pyaudio
    from pynput.mouse import Controller as MouseController, Button
    from pynput.keyboard import Controller as KeyboardController, Key
    HAS_PYNPUT = True
except ImportError:
    print("Критическая ошибка: Не установлены базовые Python-модули или pynput.")
    print("Выполните: sudo pacman -S python-pyaudio python-requests python-feedparser && pip install --user SpeechRecognition pynput --break-system-packages")
    HAS_PYNPUT = False
    sys.exit(1)

# Интеграция с локальным ИИ
try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

# =====================================================================
# ПОДАВЛЕНИЕ СИСТЕМНЫХ ОШИБОК АУДИО
# =====================================================================
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt): 
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def suppress_alsa_warnings():
    asound = None
    try:
        asound = cdll.LoadLibrary('libasound.so.2')
        asound.snd_lib_error_set_handler(c_error_handler)
    except OSError:
        pass
    try:
        yield
    finally:
        if asound:
            try:
                asound.snd_lib_error_set_handler(None)
            except Exception:
                pass

# =====================================================================
# МЕНЕДЖЕР КОНФИГУРАЦИИ
# =====================================================================
class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "obscure"
        self.config_file = self.config_dir / "config.json"
        self.todo_file = self.config_dir / "todo.txt"
        self.log_file = self.config_dir / "kernel.log"
        self._ensure_dirs()
        self.settings = self._load_or_create()

    def _ensure_dirs(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.todo_file.exists():
            self.todo_file.touch()

    def _load_or_create(self):
        default_config = {
            "app_name": "Obscure Kernel",
            "piper_bin": "/home/obscure/Downloads/piper/piper",
            "model_path": "/home/obscure/Downloads/ru_RU-ruslan-medium.onnx",
            "todo_file": str(self.todo_file),
            "log_file": str(self.log_file),
            "triggers": ["ядро", "кернел", "obscure", "обскур"],
            "temp_raw": "/tmp/obscure_raw.wav",
            "temp_fx": "/tmp/obscure_fx.wav",
            "fx_bass": 5,
            "fx_treble": 4,
            "fx_echo": 60,
            "fx_pitch": 0,
            "fx_tempo": 1.0,
            "mic_energy": 300,
            "mic_pause": 0.6,
            "mic_dynamic": False,
            "mic_phrase_limit": 10,
            "ollama_model": "phi3",
            "city": "Москва",
            "theme": "Хакерская (Зеленый)",
            "wallpaper": "",
            "custom_commands": {},
            "custom_cmd_in_terminal": False
        }
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Ошибка чтения конфига: {e}")
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
            
        return default_config

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Ошибка сохранения конфига: {e}")

# =====================================================================
# СИСТЕМНАЯ АППАРАТУРА И ПЕРИФЕРИЯ
# =====================================================================
class SystemHardware:
    def __init__(self, logger):
        self.logger = logger

    def get_cpu_temp(self):
        try:
            output = subprocess.check_output("cat /sys/class/thermal/thermal_zone*/temp | head -n 1", shell=True).decode().strip()
            return int(output) // 1000
        except: return None

    def get_ram_usage(self):
        try:
            output = subprocess.run("free -m | awk '/Mem:/ {print $3, $2}'", shell=True, capture_output=True, text=True).stdout.strip().split()
            used, total = int(output[0]), int(output[1])
            return used, int((used / total) * 100)
        except: return None, None

    def get_disk_space(self):
        try:
            return subprocess.check_output("df -h / | awk 'NR==2 {print $4}'", shell=True).decode().strip()
        except: return "неизвестно"

class HyprlandController:
    def __init__(self, logger):
        self.logger = logger

    def execute(self, cmd_args):
        try:
            subprocess.run(["hyprctl", "dispatch"] + cmd_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            self.logger.error(f"Hyprland Error: {e}")
            return False

    def save_vscode(self):
        try:
            check = subprocess.run(["xdotool", "search", "--name", "Visual Studio Code"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if check.returncode == 0:
                os.system("xdotool search --name 'Visual Studio Code' windowactivate --sync key ctrl+s")
                self.logger.info("Проекты VS Code автоматически сохранены.")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка xdotool: {e}")
            return False

class MediaController:
    def __init__(self, logger):
        self.logger = logger

    def set_volume(self, level):
        try:
            subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{int(level)/100}"], check=True)
            return True
        except Exception as e: 
            self.logger.error(f"Ошибка громкости: {e}")
            return False

    def player_command(self, action):
        try:
            subprocess.run(["playerctl", action], check=True)
            return True
        except: return False

class MinecraftController:
    def __init__(self, logger):
        self.logger = logger
        self.is_mining = False
        self.is_water_dropping = False
        if HAS_PYNPUT:
            self.mouse = MouseController()
            self.keyboard = KeyboardController()

    def start_mining(self):
        if not HAS_PYNPUT: return
        self.is_mining = True
        try:
            self.keyboard.press('w')
            self.keyboard.press(Key.shift)
            self.mouse.press(Button.left)
            self.logger.info("Майнкрафт: авто-шахта запущена")
        except Exception as e:
            self.logger.error(f"Ошибка авто-шахты: {e}")

    def stop_mining(self):
        if not HAS_PYNPUT: return
        self.is_mining = False
        try:
            self.keyboard.release('w')
            self.keyboard.release(Key.shift)
            self.mouse.release(Button.left)
            self.logger.info("Майнкрафт: авто-шахта остановлена")
        except Exception as e:
            self.logger.error(f"Ошибка остановки шахты: {e}")

    def toggle_water_drop(self, state):
        if not HAS_PYNPUT: return
        self.is_water_dropping = state
        if state:
            threading.Thread(target=self._water_drop_loop, daemon=True).start()
            self.logger.info("Майнкрафт: спам пкм запущен")
        else:
            self.logger.info("Майнкрафт: спам пкм остановлен")

    def _water_drop_loop(self):
        while self.is_water_dropping:
            try:
                self.mouse.click(Button.right)
                time.sleep(0.03) 
            except Exception:
                pass

# =====================================================================
# ДВИЖОК СИНТЕЗА РЕЧИ (TTS)
# =====================================================================
class VoiceEngine:
    def __init__(self, config, ui_signal=None):
        self.cfg = config.settings
        self.config_manager = config
        self.ui_signal = ui_signal
        self.logger = logging.getLogger("VoiceEngine")
        self.dictionary = {
            "discord": "дискорд", "browser": "браузер", "vscode": "ви-эс-код",
            "spotify": "спотифай", "youtube": "ютуб", "github": "гитхаб",
            "hyprland": "хайперлэнд", "ollama": "оллама", "pacman": "пакман"
        }

    def notify(self, title, message):
        try:
            subprocess.run(["notify-send", "-a", self.cfg["app_name"], title, message])
        except Exception as e: self.logger.error(f"Notify error: {e}")

    def preprocess(self, text):
        words = text.split()
        for i, word in enumerate(words):
            clean = word.lower().strip(".,!?:;\"'")
            if clean in self.dictionary:
                pattern = re.compile(re.escape(clean), re.IGNORECASE)
                words[i] = pattern.sub(self.dictionary[clean], word)
        return " ".join(words)

    def speak(self, text):
        if not text.strip(): return
        text = text.strip()
        
        if not (text.lower().endswith("сэр") or text.lower().endswith("сэр.")):
            text = text.rstrip(".!?") + ", сэр."
            
        clean_text = self.preprocess(text)
        self.logger.info(f"Голос: {clean_text}")
        
        # Только короткие ответы дублируем в UI от имени ИИ, длинные списки передаем напрямую
        if len(clean_text) < 150 and self.ui_signal:
            self.ui_signal.emit(f"[Kernel]: {clean_text}")
        
        raw_wav = self.cfg["temp_raw"]
        fx_wav = self.cfg["temp_fx"]
        piper = self.cfg["piper_bin"]
        model = self.cfg["model_path"]

        b = self.cfg.get("fx_bass", 5)
        t = self.cfg.get("fx_treble", 4)
        e = self.cfg.get("fx_echo", 60) / 1000
        p = self.cfg.get("fx_pitch", 0)
        tm = self.cfg.get("fx_tempo", 1.0)
        
        fx_args = f"pitch {p} tempo {tm} bass +{b} treble +{t} equalizer 900 1.2q +3 chorus 0.4 0.6 35 0.25 0.2 2 -t echo 0.8 0.6 10 {e} norm -1"

        cmd = (f'echo "{clean_text}" | {piper} --model {model} --output_file {raw_wav} 2>/dev/null && '
               f'sox {raw_wav} {fx_wav} {fx_args} 2>/dev/null && '
               f'pw-play {fx_wav}')
        try:
            os.system(cmd)
        except Exception as e:
            self.logger.error(f"Ошибка вывода аудио-потока: {e}")

# =====================================================================
# ИНФОРМАЦИОННЫЙ ПРОВАЙДЕР
# =====================================================================
class DataProvider:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.todo_path = config.settings["todo_file"]

    def get_weather_with_advice(self, override_city=None):
        if override_city:
            self.config.settings["city"] = override_city
            self.config.save_config()
        city_name = self.config.settings.get("city", "Москва")
        try:
            safe_city = urllib.parse.quote(city_name)
            weather_data = subprocess.check_output(['curl', '-s', f'wttr.in/{safe_city}?format=%t|%h|%C'], timeout=5).decode().strip()
            if not weather_data or "Unknown" in weather_data:
                return f"Метеостанция не отвечает для города {city_name}."
            
            parts = weather_data.split('|')
            temp = parts[0].replace('+', '')
            hum = parts[1]
            cond_en = parts[2].lower()
            
            cond_ru = cond_en.replace("clear", "ясно").replace("cloudy", "облачно").replace("rain", "дождь").replace("overcast", "пасмурно").replace("snow", "снег")
            
            try: temp_val = int(re.search(r'-?\d+', temp).group())
            except: temp_val = 15

            if "дождь" in cond_ru: advice = "На улице осадки. Возьмите зонт."
            elif temp_val <= -10: advice = "Холодно, надевайте термобелье и зимнюю куртку."
            elif 0 < temp_val <= 12: advice = "Прохладно, лучше надеть плотную толстовку или куртку."
            else: advice = "Погода комфортная, подойдет легкая одежда."

            return f"Погода в локации {city_name}. Температура: {temp}. Небо: {cond_ru}. {advice}"
        except Exception as e:
            self.logger.error(f"Weather error: {e}")
            return "Спутники метеорологии временно вне зоны доступа."

    def get_time(self):
        # Мгновенное системное время Arch Linux
        current_time = datetime.now().strftime('%H:%M')
        return f"Текущее системное время {current_time}."

    def get_news(self):
        try:
            feed = feedparser.parse("https://lenta.ru/rss/news")
            if feed.entries:
                news_list = [entry.title for entry in feed.entries[:3]]
                return "Свежие сводки: " + ". ".join(news_list)
            return "Новостные ленты временно пусты."
        except Exception as e:
            self.logger.error(f"News parsing error: {e}")
            return "Ошибка доступа к новостным серверам."

    def manage_todo(self, action="read", task=None):
        try:
            if action == "read":
                with open(self.todo_path, "r", encoding="utf-8") as f:
                    tasks = [line.strip() for line in f if line.strip()]
                if tasks: return f"В расписании обнаружено {len(tasks)} задач: {'. '.join(tasks)}."
                return "Список текущих задач абсолютно пуст."
            elif action == "add" and task:
                with open(self.todo_path, "a", encoding="utf-8") as f:
                    f.write(f"{task}\n")
                return f"Задача '{task}' успешно добавлена в системный реестр."
            elif action == "clear":
                open(self.todo_path, 'w').close()
                return "База данных расписания полностью уничтожена."
        except Exception as e:
            self.logger.error(f"Todo error: {e}")
            return "Ошибка ввода-вывода файла задач."

# =====================================================================
# СИСТЕМНОЕ ЯДРО ЛОГИКИ (ОБРАБОТКА КОМАНД И НЕЛИНЕЙНЫЙ ИИ)
# =====================================================================
class CoreLogic:
    def __init__(self, tts, config, ui_signal, log_signal):
        self.tts = tts
        self.config = config
        self.ui_signal = ui_signal
        self.log_signal = log_signal
        self.logger = logging.getLogger("CoreLogic")
        self.hardware = SystemHardware(self.logger)
        self.hyprland = HyprlandController(self.logger)
        self.media = MediaController(self.logger)
        self.mc = MinecraftController(self.logger)
        self.data = DataProvider(self.logger, config)
        self.model = config.settings.get("ollama_model", "phi3")
        self.pending_action = None

        self.my_music_urls = [
            "https://youtu.be/s50UVApvnmM?si=2vTPuK49u2XxDNls",
            "https://youtu.be/9JQQIjoIRd0?si=PrkpYLr-JIW5p67W",
            "https://youtu.be/hnWTSvy5VLU?si=xg16H_hl7gz7EdrM",
            "https://youtu.be/LfkdAeBRjfQ?si=iGdeQDBVForp_HhE",
            "https://youtu.be/J0TxrZb4J5k?si=EKIuK574fUJinK9P",
            "https://youtu.be/VroATOYU4ok?si=Qbm3FzGjpLbnGNq3"
        ]

    def respond(self, text):
        self.tts.speak(text)

    def _execute_background_bash(self, cmd):
        try:
            self.logger.info(f"ФОНОВОЕ ВЫПОЛНЕНИЕ КОМАНДЫ: {cmd}")
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.logger.error(f"Ошибка фонового выполнения bash: {e}")

    def execute(self, text):
        if not text: return False
        text_lower = text.lower()

        # =========================================================
        # КАСТОМНЫЕ КОМАНДЫ ПОЛЬЗОВАТЕЛЯ (ВЫСШИЙ ПРИОРИТЕТ)
        # =========================================================
        custom_cmds = self.config.settings.get("custom_commands", {})
        for phrase, bash_cmd in custom_cmds.items():
            if phrase in text_lower:
                self.respond("Выполняю пользовательский макрос, сэр.")
                
                # Проверка: выполнять скрытно или в терминале kitty
                if self.config.settings.get("custom_cmd_in_terminal", False):
                    # Откроет kitty, выполнит команду, поспит 2 сек (чтобы ты увидел) и закроется
                    visible_cmd = f"kitty bash -c '{bash_cmd}; echo \"[Выполнено]\"; sleep 2'"
                    self._execute_background_bash(visible_cmd)
                else:
                    self._execute_background_bash(bash_cmd)
                return True

        # Защита от случайных срабатываний опасных команд
        if self.pending_action:
            if re.search(r'\b(да|конечно|подтверждаю|выполняй)\b', text_lower):
                self._execute_pending()
            else:
                self.respond("Действие отменено, сэр.")
                self.pending_action = None
            return True

        # Секретный протокол
        if re.search(r'\b(я один дома|один дома)\b', text_lower):
            self.respond("Протокол конфиденциальности запущен, сэр. Терминал развернут.")
            subprocess.Popen(["xdg-open", "https://rt.pornhub.com/"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

        # =========================================================
        # ПОМОЩЬ И СПРАВКА
        # =========================================================
        if re.search(r'\b(майнкрафт помощь|minecraft помощь|помощь по игре|майнкрафт команды)\b', text_lower):
            self.respond("Для игры Майнкрафт доступны голосовые протоколы: Копай, Стоп копать, Спам и Стоп спам, сэр.")
            return True

        if re.search(r'\b(помощь|что ты умеешь|твои команды|список команд)\b', text_lower):
            if "майнкрафт" not in text_lower and "minecraft" not in text_lower:
                self.respond("Держи список команд, сэр.")
                
                full_help = """
╔═════════════ ПОЛНЫЙ СПИСОК КОМАНД OBSCURE KERNEL ═════════════╗
║ 
║ [ИНТЕРФЕЙС И ОКНА]
║ • "открой / запусти [программа]" -> Запускает любое приложение.
║ • "перестать / закрой окно / убить процесс" -> Закрывает активное окно.
║ • "перемести окно / на другой рабочий стол" -> Перенос окна (Hyprland).
║ • "настрой мониторы" -> Разворачивает рабочие пространства (VS Code + Music).
║ 
║ [МУЛЬТИМЕДИА]
║ • "включи мою музыку на ютубе" -> Рандомный трек из плейлиста.
║ • "включи видео на ютубе [поиск]" -> Поиск видео по запросу.
║ • "пауза / продолжи" -> Плеер на паузу/воспроизведение.
║ • "громкость [число]" -> Установка громкости системы.
║ 
║ [ИНФОРМАЦИЯ И ЗАМЕТКИ]
║ • "сколько время / текущее время" -> Точное системное время Arch.
║ • "погода / погода в [город]" -> Текущая метеосводка и советы.
║ • "новости / сводка" -> 3 свежих заголовка новостей.
║ • "запиши / добавь в список [текст]" -> Добавить дело в To-Do.
║ • "что по плану / список задач" -> Прочитать все дела.
║ • "очистить задачи" -> Удалить весь список дел.
║ 
║ [СИСТЕМНЫЕ И ОПАСНЫЕ]
║ • "статус / состояние / телеметрия" -> Отчет о CPU, RAM, диске.
║ • "сохрани код / проект" -> Автоматическое Ctrl+S в VS Code.
║ • "я ухожу / покидаю систему" -> Блокировка экрана (hyprlock).
║ • "выключи компьютер / перезагрузи" -> Управление питанием.
║ • "очистить мусор / кэш" -> Очистка кэша pacman.
║ • "очисти загрузки" -> Удаление всех файлов из Downloads.
║ 
║ [НЕЙРОСЕТЬ И МАКРОСЫ]
║ • "терминал [запрос]" -> ИИ сгенерирует команду для Arch и выполнит её.
║ • "майнкрафт помощь" -> Помощь по авто-кликерам.
║ • И любые твои кастомные макросы из настроек!
║ 
╚═══════════════════════════════════════════════════════════════╝
"""
                self.ui_signal.emit(full_help)
                return True

        # =========================================================
        # МАЙНКРАФТ БЛОК 
        # =========================================================
        if re.search(r'\b(стоп копать|хватит копать|останови шахту|стоп шахта)\b', text_lower):
            if HAS_PYNPUT:
                self.mc.stop_mining()
                self.respond("Протокол авто-шахты отключен, сэр.")
            return True

        if re.search(r'\b(копай|начни копать|режим шахты)\b', text_lower):
            if HAS_PYNPUT:
                self.mc.start_mining()
                self.respond("Активирован протокол авто-шахты. Идем вперед и копаем, сэр.")
            return True

        if re.search(r'\b(стоп спам|хватит спамить|останови спам|отключи спам)\b', text_lower):
            if HAS_PYNPUT:
                self.mc.toggle_water_drop(False)
                self.respond("Спам кликами отключен, сэр.")
            return True

        if re.search(r'\b(спам|начни спам|спамить|спам клик)\b', text_lower):
            if HAS_PYNPUT:
                self.mc.toggle_water_drop(True)
                self.respond("Включен спам кликами, сэр.")
            return True

        # =========================================================
        # УПРАВЛЕНИЕ ОКНАМИ И ПРИЛОЖЕНИЯМИ
        # =========================================================
        if re.search(r'\b(перестать|закрой окно|убей процесс|закрыть)\b', text_lower):
            self.hyprland.execute(["killactive"])
            self.respond("Окно закрыто, сэр.")
            return True

        if re.search(r'\b(перемести|сдвинь|передвинь окно|на другой рабочий стол)\b', text_lower):
            self.hyprland.execute(["movetoworkspace", "+1"])
            self.respond("Окно мигрировано, сэр.")
            return True

        if re.search(r'(открой|запусти)\s+(.*)', text_lower):
            app_target = re.search(r'(открой|запусти)\s+(.*)', text_lower).group(2).strip()
            
            if "майнкрафт" in app_target or "minecraft" in app_target:
                self.respond("Запускаю Майнкрафт через дискретную графику, сэр.")
                subprocess.Popen("prime-run legacy-launcher", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif "браузер" in app_target or "хром" in app_target:
                self.respond("Открываю браузер, сэр.")
                subprocess.Popen("chromium", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif "код" in app_target or "vscode" in app_target:
                self.respond("Открываю среду разработки, сэр.")
                subprocess.Popen("code", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                self.respond(f"Инициализирую процесс {app_target}, сэр.")
                subprocess.Popen(app_target, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

        # Мультимедиа
        if re.search(r'\bвключи мою музыку на ютубе\b', text_lower):
            chosen_url = random.choice(self.my_music_urls)
            self.respond("Запускаю один из ваших любимых треков на ютубе, сэр.")
            subprocess.Popen(["xdg-open", chosen_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

        if re.search(r'\bвключи видео на ютубе\b', text_lower):
            search_query = re.sub(r'.*включи видео на ютубе\s*', '', text_lower).strip()
            if search_query:
                self.respond(f"Ищу видео {search_query} на ютубе, сэр.")
                safe_query = urllib.parse.quote(search_query)
                url = f"https://www.youtube.com/results?search_query={safe_query}"
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                self.respond("Какое видео найти, сэр?")
            return True

        if re.search(r'\b(пауза|продолжи)\b', text_lower):
            if "пауза" in text_lower:
                self.media.player_command("pause")
                self.respond("Воспроизведение остановлено, сэр.")
            elif "продолжи" in text_lower:
                self.media.player_command("play")
                self.respond("Возобновляю аудио-поток, сэр.")
            return True

        if re.search(r'\bгромкость\b', text_lower):
            vol_match = re.search(r'\bгромкость\s*(\d+)', text_lower)
            if vol_match:
                level = vol_match.group(1)
                self.media.set_volume(level)
                self.respond(f"Громкость установлена на {level} процентов, сэр.")
            return True

        # Системные действия и Hyprland
        if re.search(r'(состояни|статус|отчет|телеметрия)', text_lower):
            temp = self.hardware.get_cpu_temp()
            used_ram, ram_pct = self.hardware.get_ram_usage()
            msg = f"Логические цепочки стабильны. Температура процессора {temp or 'н/д'} градусов. Память: {ram_pct or 'н/д'}%."
            self.respond(msg)
            return True

        if re.search(r'(сохрани код|сохрани проект)', text_lower):
            self.hyprland.save_vscode()
            self.respond("Изменения зафиксированы, сэр.")
            return True
            
        if re.search(r'(настрой мониторы|рабоче.*пространство)', text_lower):
            self.hyprland.setup_workspaces()
            self.respond("Среда разработки и мультимедиа развернуты по вашим дисплеям, сэр.")
            return True

        if re.search(r'(я ухожу|покидаю систему)', text_lower):
            self.respond("Перевожу ядро в режим блокировки, сэр.")
            self.hyprland.save_vscode()
            os.system("hyprlock &")
            return "SLEEP"

        # Опасные команды
        if re.search(r'(очист.*задач|очист.*план|удал.*задач)', text_lower):
            self.pending_action = "clear_tasks"
            self.respond("Внимание. Вы уверены, что хотите полностью очистить базу данных задач, сэр?")
            return True

        if re.search(r'(очисти загрузки|очисти папку)', text_lower):
            self.pending_action = "clear_downloads"
            self.respond("Вы уверены, что хотите полностью стереть директорию загрузок, сэр?")
            return True
            
        if re.search(r'(очисти кэш|мусор)', text_lower):
            self.pending_action = "clear_cache"
            self.respond("Подтвердите очистку кэша пакетного менеджера pacman, сэр.")
            return True

        if re.search(r'(выключи компьютер|завершение работы)', text_lower):
            self.pending_action = "shutdown"
            self.respond("Подтвердите полное отключение рабочей станции, сэр.")
            return True
            
        if re.search(r'(перезагруз|reboot)', text_lower):
            self.pending_action = "reboot"
            self.respond("Подтвердите перезапуск ядра системы, сэр.")
            return True

        # =========================================================
        # ИНТЕЛЛЕКТУАЛЬНЫЙ ТЕРМИНАЛ НА ARCH LINUX
        # =========================================================
        if re.search(r'\bтерминал\b', text_lower):
            raw_cmd = re.sub(r'.*\bтерминал\s+', '', text_lower).strip()
            if not raw_cmd:
                self.respond("Какую команду выполнить в терминале, сэр?")
                return True
                
            if HAS_OLLAMA:
                self.respond("Обрабатываю директиву для Arch Linux, сэр...")
                try:
                    sys_prompt = """Ты — системный транслятор команд для Arch Linux. 
                    Пользователь скажет, что нужно сделать (например: "открой яндекс", "обнови систему"). 
                    Ты должен ответить ТОЛЬКО чистой Bash командой. Никаких пояснений, без markdown.
                    Если нужно открыть сайт, пиши: xdg-open URL
                    Если запустить приложение, пиши его название."""

                    response = ollama.chat(
                        model=self.model, 
                        messages=[
                            {'role': 'system', 'content': sys_prompt},
                            {'role': 'user', 'content': raw_cmd}
                        ],
                        options={'num_predict': 40, 'temperature': 0.1}
                    )
                    linux_cmd = response['message']['content'].strip().replace('`', '').replace('\n', ' ')
                    linux_cmd = re.sub(r'#.*', '', linux_cmd).strip()
                    self.logger.info(f"Сформирована системная директива: {linux_cmd}")
                    
                    if linux_cmd:
                        self.respond("Команда сгенерирована и отправлена в шелл, сэр.")
                        # Запуск сгенерированной команды в терминале kitty, чтобы было видно процесс
                        visible_cmd = f"kitty bash -c '{linux_cmd}; sleep 2'"
                        threading.Thread(target=self._execute_background_bash, args=(visible_cmd,)).start()
                    else:
                        self.respond("Не удалось сгенерировать команду, сэр.")
                except Exception as e:
                    self.logger.error(f"Ошибка Ollama при парсинге терминала: {e}")
                    self.respond("Синтаксис команды поврежден или нейросеть недоступна, сэр.")
            else:
                self.respond("Интеграция с локальной нейросетью недоступна, сэр.")
            return True

        # =========================================================
        # ВРЕМЯ, ПОГОДА, ЗАМЕТКИ, НОВОСТИ
        # =========================================================
        if re.search(r'(сколько врем|которое врем|какое врем|текущее врем)', text_lower):
            self.respond(self.data.get_time())
            return True

        if re.search(r'погода в ([\w\-а-яА-Я]+)', text_lower):
            city = re.search(r'погода в ([\w\-а-яА-Я]+)', text_lower).group(1)
            self.respond(self.data.get_weather_with_advice(city))
            return True
            
        if re.search(r'(погода|что надеть|за бортом)', text_lower):
            self.respond(self.data.get_weather_with_advice())
            return True
            
        if re.search(r'(новост|сводк)', text_lower):
            self.respond(self.data.get_news())
            return True
            
        if re.search(r'(запиши|добавь в список)', text_lower):
            task = re.sub(r'.*(запиши|добавь в список)\s*', '', text_lower).strip()
            if task: self.respond(self.data.manage_todo("add", task))
            return True
            
        if re.search(r'(что по план|список задач|напомни)', text_lower):
            self.respond(self.data.manage_todo("read"))
            return True

        # =========================================================
        # ГЕНЕРАТИВНЫЙ ИИ (СТРОГИЙ ПРОТОКОЛ)
        # =========================================================
        if HAS_OLLAMA:
            self.log_signal.emit(f"[Система]: Запрос '{text}' перенаправлен нейросети (Ollama)...")
            try:
                system_prompt = """Ты — ИИ-ассистент OBSCURE. Отвечай ультра-кратко на русском языке (строго 1-2 предложения).
                Категорически запрещено выводить служебный текст, рассуждать или додумывать действия. Концовка ответа обязательно должна содержать ", сэр."."""
                
                response = ollama.chat(
                    model=self.model, 
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': text}
                    ],
                    options={'num_predict': 50, 'temperature': 0.2}
                )
                ans = response['message']['content'].strip()
                ans = re.sub(r'(###|Instruction|Question|Твой создатель|Отвечай СТРОГО|Ты — ИИ).*?(?=\n|$)', '', ans, flags=re.IGNORECASE | re.DOTALL)
                
                if ans:
                    clean_ans_for_tts = ans.replace("*", "").replace("`", "")
                    self.respond(clean_ans_for_tts)
                    self.ui_signal.emit(f"[Kernel AI]: {ans}")
                return True
            except Exception as e:
                self.logger.error(f"Ошибка Ollama: {e}")
                self.log_signal.emit("[Ошибка]: Локальная LLM не отвечает.")
                return False
        else:
            self.respond("Неизвестная директива, а модуль нейросети отключен, сэр.")
            return False

    def _execute_pending(self):
        action = self.pending_action
        self.pending_action = None
        
        home = str(Path.home())
        if action == "clear_tasks":
            self.respond(self.data.manage_todo(action="clear"))
        elif action == "clear_downloads":
            target = os.path.expanduser("~/Downloads")
            os.system(f"rm -rf {target}/*")
            self.respond("Сектор загрузок полностью очищен, сэр.")
        elif action == "clear_cache":
            os.system("echo 'y' | sudo pacman -Sc")
            self.respond("Кэш пакетов Arch Linux успешно очищен, сэр.")
        elif action == "shutdown":
            self.respond("Завершаю системные процессы. До встречи, сэр.")
            time.sleep(1)
            os.system("sudo poweroff")
        elif action == "reboot":
            self.respond("Инициирую перезапуск ядра, сэр.")
            time.sleep(1)
            os.system("sudo reboot")

# =====================================================================
# ПОТОК ОБРАБОТКИ РЕЧИ (ФОНОВЫЙ ДЕМОН)
# =====================================================================
class VoiceWorker(QThread):
    log_signal = pyqtSignal(str)
    text_recognized = pyqtSignal(str)
    status_signal = pyqtSignal(bool)

    def __init__(self, config_manager):
        super().__init__()
        self.cfg_mgr = config_manager
        self.running = True
        self.is_active = False 
        self.recognizer = sr.Recognizer()

    def update_mic_settings(self, energy, pause, dynamic, limit):
        self.recognizer.energy_threshold = energy
        self.recognizer.pause_threshold = pause
        self.recognizer.dynamic_energy_threshold = dynamic
        self.cfg_mgr.settings["mic_phrase_limit"] = limit
        self.log_signal.emit(f"[Аудио-Драйвер] Параметры обновлены. Gain: {energy}, Пауза: {pause}с, Динамика: {dynamic}")

    def run(self):
        class QtLogHandler(logging.Handler):
            def __init__(self, signal):
                super().__init__()
                self.signal = signal
            def emit(self, record):
                self.signal.emit(self.format(record))

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(QtLogHandler(self.log_signal))

        self.tts = VoiceEngine(self.cfg_mgr, self.text_recognized)
        self.logic = CoreLogic(self.tts, self.cfg_mgr, self.text_recognized, self.log_signal)
        
        self.recognizer.energy_threshold = self.cfg_mgr.settings.get("mic_energy", 300)
        self.recognizer.pause_threshold = self.cfg_mgr.settings.get("mic_pause", 0.6) 
        self.recognizer.dynamic_energy_threshold = self.cfg_mgr.settings.get("mic_dynamic", False)
        self.recognizer.non_speaking_duration = 0.3 

        with suppress_alsa_warnings():
            try:
                mic = sr.Microphone()
                with mic as source:
                    if self.recognizer.dynamic_energy_threshold:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                self.log_signal.emit("[Система] Микрофон захвачен ядром.")
            except Exception as e:
                self.log_signal.emit(f"[Критическая ошибка] Ошибка микрофона: {e}")
                return

            self.tts.speak("Терминал интерфейса развернут. Ядро слушает.")
            
            while self.running:
                try:
                    limit = self.cfg_mgr.settings.get("mic_phrase_limit", 10)
                    with mic as source:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=limit)
                    text = self.recognizer.recognize_google(audio, language="ru-RU").lower()
                    
                    phonetic_corrections = {
                        "ядло": "ядро", "едро": "ядро", "келнел": "кернел", "кэрнел": "кернел",
                        "обскул": "обскур", "обсцюр": "обскур", "отклой": "открой", "заклой": "закрой", 
                        "плодолжи": "продолжи", "тлерек": "трек", "пелезагрузи": "перезагрузи", 
                        "тлеминал": "терминал", "плоги": "проги", "тлебл": "требл", "клит": "крит",
                        "вленя": "время", "влемя": "время"
                    }
                    for bad_word, good_word in phonetic_corrections.items():
                        text = text.replace(bad_word, good_word)
                    
                    self.text_recognized.emit(f"[Obscure]: {text}")

                    triggers = self.cfg_mgr.settings.get("triggers", ["ядро", "кернел", "обскур", "obscure"])
                    has_trigger = any(t in text for t in triggers)

                    if re.search(r'(отбой|усни|спрячься)', text):
                        if self.is_active:
                            self.is_active = False
                            self.status_signal.emit(False)
                            self.tts.speak("Перехожу в режим наблюдения, сэр.")
                        continue

                    if not self.is_active:
                        if has_trigger:
                            self.is_active = True
                            self.status_signal.emit(True)
                            for t in triggers: text = text.replace(t, "")
                            text = text.strip()
                            if not text:
                                self.tts.speak(random.choice(["Слушаю, сэр.", "Ядро активно.", "Жду команд, сэр."]))
                            else:
                                res = self.logic.execute(text)
                                if res == "SLEEP": 
                                    self.is_active = False
                                    self.status_signal.emit(False)
                    else:
                        for t in triggers: text = text.replace(t, "")
                        text = text.strip()
                        if text:
                            res = self.logic.execute(text)
                            if res == "SLEEP":
                                self.is_active = False
                                self.status_signal.emit(False)
                except sr.WaitTimeoutError: pass
                except sr.UnknownValueError: pass
                except Exception as e:
                    self.log_signal.emit(f"[Ошибка цикла]: {e}")
                    time.sleep(0.5)

    def stop(self):
        self.running = False
        self.wait()

# =====================================================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (ПАНЕЛЬ УПРАВЛЕНИЯ TERMINAL)
# =====================================================================
class ObscureApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg_mgr = ConfigManager()
        self.hardware = SystemHardware(logging.getLogger("GUI"))
        
        self.bg_label = QLabel(self)
        self.bg_label.lower()
        
        self.init_ui()
        
        self.worker = VoiceWorker(self.cfg_mgr)
        self.worker.log_signal.connect(self.append_log)
        self.worker.text_recognized.connect(self.append_chat)
        self.worker.status_signal.connect(self.set_activation_status)
        self.worker.start()

        self.telemetry_timer = QTimer()
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(2000)

        self.apply_theme(self.cfg_mgr.settings.get("theme", "Хакерская (Зеленый)"))

    def init_ui(self):
        self.setWindowTitle("OBSCURE KERNEL v11.0 ULTIMATE")
        self.resize(1000, 700)
        self.font_family = "Courier New"
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        header_title = QLabel(">>> KERNEL AI CONTROL PANEL - CREATED BY OBSCURE <<<")
        header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_title.setStyleSheet("font-size: 18px; font-weight: bold; letter-spacing: 2px;")
        main_layout.addWidget(header_title)

        self.status_lbl = QLabel("[ STATUS: STANDBY - WAITING FOR TRIGGER ]")
        self.status_lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
        main_layout.addWidget(self.status_lbl)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.setup_tab_dashboard()
        self.setup_tab_audio()
        self.setup_tab_settings()

    def setup_tab_dashboard(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        left_panel = QVBoxLayout()
        right_panel = QVBoxLayout()
        
        chat_box = QGroupBox("TERMINAL INTERFACE")
        chat_layout = QVBoxLayout(chat_box)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display)
        
        input_layout = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("root@kernel:~# Введите директиву или спросите ИИ...")
        self.cmd_input.returnPressed.connect(self.send_manual_cmd)
        send_btn = QPushButton("EXECUTE")
        send_btn.clicked.connect(self.send_manual_cmd)
        input_layout.addWidget(self.cmd_input)
        input_layout.addWidget(send_btn)
        chat_layout.addLayout(input_layout)
        left_panel.addWidget(chat_box, 3)

        log_box = QGroupBox("SYSTEM LOGS")
        log_layout = QVBoxLayout(log_box)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("font-size: 11px;")
        log_layout.addWidget(self.log_display)
        left_panel.addWidget(log_box, 2)

        hw_box = QGroupBox("HARDWARE SENSORS")
        hw_layout = QGridLayout(hw_box)
        hw_layout.addWidget(QLabel("CPU TEMP:"), 0, 0)
        self.cpu_lbl = QLabel("WAIT...")
        hw_layout.addWidget(self.cpu_lbl, 0, 1)
        hw_layout.addWidget(QLabel("RAM USAGE:"), 1, 0)
        self.ram_lbl = QLabel("WAIT...")
        hw_layout.addWidget(self.ram_lbl, 1, 1)
        hw_layout.addWidget(QLabel("ROOT DISK:"), 2, 0)
        self.disk_lbl = QLabel("WAIT...")
        hw_layout.addWidget(self.disk_lbl, 2, 1)
        right_panel.addWidget(hw_box)

        macro_box = QGroupBox("MINECRAFT MACROS")
        m_layout = QVBoxLayout(macro_box)
        self.mc_mine_btn = QPushButton("MINE MODE [OFF]")
        self.mc_mine_btn.clicked.connect(self.toggle_mc_mine)
        m_layout.addWidget(self.mc_mine_btn)
        self.mc_spam_btn = QPushButton("SPAM MODE [OFF]")
        self.mc_spam_btn.clicked.connect(self.toggle_mc_spam)
        m_layout.addWidget(self.mc_spam_btn)
        right_panel.addWidget(macro_box)

        right_panel.addStretch()
        layout.addLayout(left_panel, 3)
        layout.addLayout(right_panel, 1)
        self.tabs.addTab(tab, "CONSOLE")

    def setup_tab_audio(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        mic_box = QGroupBox("MICROPHONE SENSITIVITY CALIBRATION")
        mic_layout = QGridLayout(mic_box)

        self.dynamic_cb = QCheckBox("Включить автоматическую адаптацию под шум (Dynamic Energy)")
        self.dynamic_cb.setChecked(self.cfg_mgr.settings.get("mic_dynamic", False))
        self.dynamic_cb.stateChanged.connect(self.update_mic_labels_and_apply)
        mic_layout.addWidget(self.dynamic_cb, 0, 0, 1, 3)

        mic_layout.addWidget(QLabel("Базовый порог громкости (Energy Threshold):"), 1, 0)
        self.energy_slider = QSlider(Qt.Orientation.Horizontal)
        self.energy_slider.setRange(50, 4000)
        self.energy_slider.setValue(self.cfg_mgr.settings.get("mic_energy", 300))
        self.energy_lbl = QLabel(str(self.energy_slider.value()))
        self.energy_slider.valueChanged.connect(self.update_mic_labels_and_apply)
        mic_layout.addWidget(self.energy_slider, 1, 1)
        mic_layout.addWidget(self.energy_lbl, 1, 2)

        mic_layout.addWidget(QLabel("Длина паузы для обрезки (Pause Threshold, сек):"), 2, 0)
        self.pause_slider = QSlider(Qt.Orientation.Horizontal)
        self.pause_slider.setRange(3, 25) 
        val_pause = int(self.cfg_mgr.settings.get("mic_pause", 0.6) * 10)
        self.pause_slider.setValue(val_pause)
        self.pause_lbl = QLabel(f"{val_pause / 10.0}s")
        self.pause_slider.valueChanged.connect(self.update_mic_labels_and_apply)
        mic_layout.addWidget(self.pause_slider, 2, 1)
        mic_layout.addWidget(self.pause_lbl, 2, 2)

        mic_layout.addWidget(QLabel("Макс. время слушания одной фразы (секунды):"), 3, 0)
        self.limit_slider = QSlider(Qt.Orientation.Horizontal)
        self.limit_slider.setRange(3, 30)
        self.limit_slider.setValue(self.cfg_mgr.settings.get("mic_phrase_limit", 10))
        self.limit_lbl = QLabel(f"{self.limit_slider.value()}s")
        self.limit_slider.valueChanged.connect(self.update_mic_labels_and_apply)
        mic_layout.addWidget(self.limit_slider, 3, 1)
        mic_layout.addWidget(self.limit_lbl, 3, 2)

        layout.addWidget(mic_box)

        eq_box = QGroupBox("VOICE SYNTHESIS ENGINE (SOX FX)")
        eq_layout = QGridLayout(eq_box)
        
        eq_layout.addWidget(QLabel("Тональность (Pitch):"), 0, 0)
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-500, 500)
        self.pitch_slider.setValue(self.cfg_mgr.settings.get("fx_pitch", 0))
        self.pitch_slider.valueChanged.connect(self.save_audio_params)
        eq_layout.addWidget(self.pitch_slider, 0, 1)

        eq_layout.addWidget(QLabel("Скорость (Tempo x10):"), 1, 0)
        self.tempo_slider = QSlider(Qt.Orientation.Horizontal)
        self.tempo_slider.setRange(5, 20) 
        self.tempo_slider.setValue(int(self.cfg_mgr.settings.get("fx_tempo", 1.0) * 10))
        self.tempo_slider.valueChanged.connect(self.save_audio_params)
        eq_layout.addWidget(self.tempo_slider, 1, 1)

        eq_layout.addWidget(QLabel("Бас (Bass):"), 2, 0)
        self.bass_slider = QSlider(Qt.Orientation.Horizontal)
        self.bass_slider.setRange(0, 15)
        self.bass_slider.setValue(self.cfg_mgr.settings.get("fx_bass", 5))
        self.bass_slider.valueChanged.connect(self.save_audio_params)
        eq_layout.addWidget(self.bass_slider, 2, 1)
        
        eq_layout.addWidget(QLabel("Высокие (Treble):"), 3, 0)
        self.treble_slider = QSlider(Qt.Orientation.Horizontal)
        self.treble_slider.setRange(0, 15)
        self.treble_slider.setValue(self.cfg_mgr.settings.get("fx_treble", 4))
        self.treble_slider.valueChanged.connect(self.save_audio_params)
        eq_layout.addWidget(self.treble_slider, 3, 1)

        eq_layout.addWidget(QLabel("Эхо (Echo Ms):"), 4, 0)
        self.echo_slider = QSlider(Qt.Orientation.Horizontal)
        self.echo_slider.setRange(10, 150)
        self.echo_slider.setValue(self.cfg_mgr.settings.get("fx_echo", 60))
        self.echo_slider.valueChanged.connect(self.save_audio_params)
        eq_layout.addWidget(self.echo_slider, 4, 1)
        
        layout.addWidget(eq_box)
        
        test_btn = QPushButton("TEST VOICE PARAMETERS")
        test_btn.clicked.connect(lambda: threading.Thread(target=self.worker.tts.speak, args=("Проверка системных фильтров голоса завершена.",), daemon=True).start())
        layout.addWidget(test_btn)
        layout.addStretch()
        
        self.tabs.addTab(tab, "AUDIO_DRIVERS")

    def setup_tab_settings(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Основные настройки
        cfg_box = QGroupBox("SYSTEM VARIABLES")
        cfg_layout = QGridLayout(cfg_box)
        
        cfg_layout.addWidget(QLabel("ЛОКАЦИЯ (ДЛЯ ПОГОДЫ И ВРЕМЕНИ):"), 0, 0)
        self.city_edit = QLineEdit(self.cfg_mgr.settings.get("city", "Москва"))
        cfg_layout.addWidget(self.city_edit, 0, 1)

        cfg_layout.addWidget(QLabel("ТРИГГЕРЫ (ЧЕРЕЗ ЗАПЯТУЮ):"), 1, 0)
        self.triggers_edit = QLineEdit(", ".join(self.cfg_mgr.settings.get("triggers", ["ядро", "кернел"])))
        cfg_layout.addWidget(self.triggers_edit, 1, 1)

        cfg_layout.addWidget(QLabel("ЦВЕТОВАЯ ТЕМА:"), 2, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Хакерская (Зеленый)", "Киберпанк (Неон)", "Кровавая (Красный)", "Темная (Светлый текст)", "Светлая"])
        self.theme_combo.setCurrentText(self.cfg_mgr.settings.get("theme", "Хакерская (Зеленый)"))
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        cfg_layout.addWidget(self.theme_combo, 2, 1)

        wp_layout = QHBoxLayout()
        wp_btn = QPushButton("ВЫБРАТЬ ОБОИ (ФОН)")
        wp_btn.clicked.connect(self.choose_wallpaper)
        wp_clear_btn = QPushButton("УДАЛИТЬ ОБОИ")
        wp_clear_btn.clicked.connect(self.clear_wallpaper)
        wp_layout.addWidget(wp_btn)
        wp_layout.addWidget(wp_clear_btn)
        
        cfg_layout.addLayout(wp_layout, 3, 0, 1, 2)
        
        self.term_cb = QCheckBox("Выполнять кастомные макросы в видимом терминале (kitty)")
        self.term_cb.setChecked(self.cfg_mgr.settings.get("custom_cmd_in_terminal", False))
        cfg_layout.addWidget(self.term_cb, 4, 0, 1, 2)
        
        layout.addWidget(cfg_box)

        # Кастомные команды
        cmd_box = QGroupBox("CUSTOM MACROS (СВОИ КОМАНДЫ)")
        cmd_layout = QGridLayout(cmd_box)
        
        self.cmd_phrase_input = QLineEdit()
        self.cmd_phrase_input.setPlaceholderText("Фраза для активации (например: открой телеграм)")
        self.cmd_bash_input = QLineEdit()
        self.cmd_bash_input.setPlaceholderText("Bash команда (например: telegram-desktop)")
        
        add_cmd_btn = QPushButton("ДОБАВИТЬ МАКРОС")
        add_cmd_btn.clicked.connect(self.add_custom_command)
        
        self.cmd_list_display = QTextEdit()
        self.cmd_list_display.setReadOnly(True)
        self.update_custom_cmd_display()
        
        clear_cmd_btn = QPushButton("ОЧИСТИТЬ ВСЕ КАСТОМНЫЕ КОМАНДЫ")
        clear_cmd_btn.clicked.connect(self.clear_custom_commands)

        cmd_layout.addWidget(QLabel("Голосовая фраза:"), 0, 0)
        cmd_layout.addWidget(self.cmd_phrase_input, 0, 1)
        cmd_layout.addWidget(QLabel("Bash команда:"), 1, 0)
        cmd_layout.addWidget(self.cmd_bash_input, 1, 1)
        cmd_layout.addWidget(add_cmd_btn, 2, 0, 1, 2)
        cmd_layout.addWidget(self.cmd_list_display, 3, 0, 1, 2)
        cmd_layout.addWidget(clear_cmd_btn, 4, 0, 1, 2)

        layout.addWidget(cmd_box)
        
        save_btn = QPushButton("APPLY GLOBAL SETTINGS")
        save_btn.clicked.connect(self.save_global_settings)
        layout.addWidget(save_btn)
        
        self.tabs.addTab(tab, "CONFIG")

    def add_custom_command(self):
        phrase = self.cmd_phrase_input.text().strip().lower()
        bash_cmd = self.cmd_bash_input.text().strip()
        
        if not phrase or not bash_cmd:
            QMessageBox.warning(self, "Ошибка", "Оба поля должны быть заполнены!")
            return
            
        custom_cmds = self.cfg_mgr.settings.get("custom_commands", {})
        custom_cmds[phrase] = bash_cmd
        self.cfg_mgr.settings["custom_commands"] = custom_cmds
        self.cfg_mgr.save_config()
        
        self.cmd_phrase_input.clear()
        self.cmd_bash_input.clear()
        self.update_custom_cmd_display()
        self.append_log(f"[System] Пользовательский макрос '{phrase}' добавлен.")

    def clear_custom_commands(self):
        self.cfg_mgr.settings["custom_commands"] = {}
        self.cfg_mgr.save_config()
        self.update_custom_cmd_display()
        self.append_log("[System] Все пользовательские макросы удалены.")

    def update_custom_cmd_display(self):
        custom_cmds = self.cfg_mgr.settings.get("custom_commands", {})
        if not custom_cmds:
            self.cmd_list_display.setText("Нет добавленных кастомных команд.")
            return
            
        text = "Текущие пользовательские команды:\n"
        for phrase, cmd in custom_cmds.items():
            text += f"• '{phrase}'  -->  [{cmd}]\n"
        self.cmd_list_display.setText(text)

    def apply_theme(self, theme_name):
        bg = "#050505"
        fg = "#00FF41"
        border = "#005918"
        hover = "#008F11"
        bg_alpha = "rgba(5, 5, 5, 210)"

        if theme_name == "Киберпанк (Неон)":
            bg = "#090A0F"; fg = "#00E5FF"; border = "#005566"; hover = "#0088AA"
            bg_alpha = "rgba(9, 10, 15, 210)"
        elif theme_name == "Кровавая (Красный)":
            bg = "#0D0000"; fg = "#FF1E1E"; border = "#660000"; hover = "#990000"
            bg_alpha = "rgba(13, 0, 0, 210)"
        elif theme_name == "Темная (Светлый текст)":
            bg = "#1A1A1A"; fg = "#E0E0E0"; border = "#333333"; hover = "#555555"
            bg_alpha = "rgba(26, 26, 26, 210)"
        elif theme_name == "Светлая":
            bg = "#F0F0F0"; fg = "#111111"; border = "#CCCCCC"; hover = "#AAAAAA"
            bg_alpha = "rgba(240, 240, 240, 220)"

        wp = self.cfg_mgr.settings.get("wallpaper", "")
        if wp and os.path.exists(wp):
            self.set_wallpaper(wp)
            main_bg = "background: transparent;"
            panel_bg = bg_alpha
        else:
            self.bg_label.clear()
            main_bg = f"background-color: {bg};"
            panel_bg = bg

        self.setStyleSheet(f"""
            QMainWindow {{ {main_bg} }}
            QWidget {{ font-family: '{self.font_family}', monospace; color: {fg}; }}
            QTabWidget::pane {{ border: 1px solid {border}; background: transparent; }}
            QTabBar::tab {{ background: {bg}; color: {hover}; padding: 8px 15px; border: 1px solid {border}; }}
            QTabBar::tab:selected {{ background: {border}; color: {fg}; font-weight: bold; }}
            QGroupBox {{ background-color: {panel_bg}; border: 1px solid {border}; margin-top: 15px; color: {fg}; font-weight: bold; padding: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
            QPushButton {{ background-color: {bg}; border: 1px solid {hover}; color: {fg}; padding: 8px 15px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {border}; color: {bg}; }}
            QPushButton:pressed {{ background-color: {fg}; color: {bg}; }}
            QTextEdit, QLineEdit {{ background-color: rgba(0,0,0,0.7); border: 1px solid {border}; color: {fg}; padding: 5px; }}
            QLabel {{ color: {fg}; background: transparent; }}
            QSlider::groove:horizontal {{ height: 4px; background: {border}; }}
            QSlider::handle:horizontal {{ background: {fg}; width: 10px; margin-top: -6px; margin-bottom: -6px; }}
            QComboBox {{ background-color: {bg}; border: 1px solid {border}; color: {fg}; padding: 3px; }}
        """)
        self.cfg_mgr.settings["theme"] = theme_name
        self.cfg_mgr.save_config()

    def choose_wallpaper(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать обои", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            self.cfg_mgr.settings["wallpaper"] = file_name
            self.cfg_mgr.save_config()
            self.apply_theme(self.theme_combo.currentText())

    def clear_wallpaper(self):
        self.cfg_mgr.settings["wallpaper"] = ""
        self.cfg_mgr.save_config()
        self.bg_label.clear()
        self.apply_theme(self.theme_combo.currentText())
        self.append_log("[System] Обои удалены. Применен стандартный фон.")

    def set_wallpaper(self, path):
        if os.path.exists(path):
            pixmap = QPixmap(path)
            self.bg_label.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def append_log(self, text):
        self.log_display.append(text)
        self.log_display.moveCursor(QTextCursor.MoveOperation.End)

    def append_chat(self, text):
        self.chat_display.append(text)
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def set_activation_status(self, active):
        if active:
            self.status_lbl.setText("[ STATUS: ACTIVE - LISTENING COMMAND ]")
        else:
            self.status_lbl.setText("[ STATUS: STANDBY - WAITING FOR TRIGGER ]")

    def update_telemetry(self):
        temp = self.hardware.get_cpu_temp()
        used_ram, pct_ram = self.hardware.get_ram_usage()
        disk = self.hardware.get_disk_space()
        
        self.cpu_lbl.setText(f"{temp}°C" if temp else "N/A")
        self.ram_lbl.setText(f"{used_ram} MB ({pct_ram}%)" if used_ram else "N/A")
        self.disk_lbl.setText(disk)

    def update_mic_labels_and_apply(self):
        energy = self.energy_slider.value()
        pause = self.pause_slider.value() / 10.0
        limit = self.limit_slider.value()
        dynamic = self.dynamic_cb.isChecked()
        
        self.energy_lbl.setText(str(energy))
        self.pause_lbl.setText(f"{pause}s")
        self.limit_lbl.setText(f"{limit}s")
        
        self.cfg_mgr.settings["mic_energy"] = energy
        self.cfg_mgr.settings["mic_pause"] = pause
        self.cfg_mgr.settings["mic_dynamic"] = dynamic
        self.cfg_mgr.settings["mic_phrase_limit"] = limit
        self.cfg_mgr.save_config()
        
        self.worker.update_mic_settings(energy, pause, dynamic, limit)

    def send_manual_cmd(self):
        text = self.cmd_input.text().strip()
        if text:
            self.append_chat(f"[Obscure (Keyboard)]: {text}")
            self.cmd_input.clear()
            threading.Thread(target=self.worker.logic.execute, args=(text.lower(),), daemon=True).start()

    def toggle_mc_mine(self):
        if self.worker.logic.mc.is_mining:
            self.worker.logic.mc.stop_mining()
            self.mc_mine_btn.setText("MINE MODE [OFF]")
        else:
            self.worker.logic.mc.start_mining()
            self.mc_mine_btn.setText("MINE MODE [ON]")

    def toggle_mc_spam(self):
        if self.worker.logic.mc.is_water_dropping:
            self.worker.logic.mc.toggle_water_drop(False)
            self.mc_spam_btn.setText("SPAM MODE [OFF]")
        else:
            self.worker.logic.mc.toggle_water_drop(True)
            self.mc_spam_btn.setText("SPAM MODE [ON]")

    def save_audio_params(self):
        self.cfg_mgr.settings["fx_bass"] = self.bass_slider.value()
        self.cfg_mgr.settings["fx_treble"] = self.treble_slider.value()
        self.cfg_mgr.settings["fx_echo"] = self.echo_slider.value()
        self.cfg_mgr.settings["fx_pitch"] = self.pitch_slider.value()
        self.cfg_mgr.settings["fx_tempo"] = self.tempo_slider.value() / 10.0
        self.cfg_mgr.save_config()

    def save_global_settings(self):
        self.cfg_mgr.settings["city"] = self.city_edit.text().strip()
        raw_trig = self.triggers_edit.text().split(",")
        self.cfg_mgr.settings["triggers"] = [t.strip().lower() for t in raw_trig if t.strip()]
        self.cfg_mgr.settings["custom_cmd_in_terminal"] = self.term_cb.isChecked()
        self.cfg_mgr.save_config()
        self.append_log("[System] Конфигурация ядра обновлена.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg_label.resize(self.size())
        wp = self.cfg_mgr.settings.get("wallpaper")
        if wp and os.path.exists(wp):
            self.set_wallpaper(wp)

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()

# =====================================================================
# ТОЧКА ВХОДА
# =====================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ObscureApp()
    gui.show()
    sys.exit(app.exec())
