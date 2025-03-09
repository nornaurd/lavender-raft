import os
import re
import subprocess
import requests
from config import OPENAI_API_KEY

# Шлях до аудіофайлу
AUDIO_FILE = "audio/2025-03-08-audio.mp4"
TRIMMED_AUDIO_FILE = "audio/trimmed_lecture.mp4"

# Ліміт для OpenAI API (25MB)
FILE_SIZE_LIMIT_MB = 25

def get_file_size(file_path):
    return os.path.getsize(file_path) / (1024 * 1024)

def detect_voice_start(file_path):
    """
    Використовуємо ffmpeg для визначення моменту, коли закінчується тиша.
    Функція шукає рядок типу "silence_end: <час>" за допомогою регулярного виразу.
    """
    command = [
        "ffmpeg", "-i", file_path,
        "-af", "silencedetect=noise=-40dB:d=0.5",
        "-f", "null", "-"
    ]
    result = subprocess.run(command, stderr=subprocess.PIPE, text=True)
    # Розкоментуйте наступний рядок для перегляду виводу ffmpeg, якщо потрібно відлагодження:
    # print(result.stderr)
    match = re.search(r"silence_end:\s*([\d\.]+)", result.stderr)
    if match:
        return match.group(1)  # Повертаємо час закінчення тиші
    return None  # Якщо не знайдено, повертаємо None

def trim_silence(file_path, output_path):
    start_time = detect_voice_start(file_path)
    if start_time:
        print(f"🔹 Автоматично обрізаю тишу до {start_time} секунди...")
        # Виконуємо обрізання з перекодуванням аудіо для точнішого обрізання
        command = [
            "ffmpeg", "-i", file_path,
            "-ss", start_time,
            "-c:a", "aac", "-b:a", "128k",  # Використовуємо перекодування аудіо
            output_path
        ]
        subprocess.run(command, check=True)
        return output_path
    else:
        print("🔹 Тиша не знайдена або дуже коротка. Використовую оригінальний файл.")
        return file_path

def split_audio(file_path, output_folder, segment_length=300):
    """
    Розбиває аудіофайл на частини по 5 хвилин (300 секунд)
    та зберігає їх у форматі MP3 з використанням libmp3lame.
    """
    os.makedirs(output_folder, exist_ok=True)
    output_pattern = os.path.join(output_folder, "part_%03d.mp3")
    command = [
        "ffmpeg", "-i", file_path,
        "-f", "segment",
        "-segment_time", str(segment_length),
        "-c:a", "libmp3lame", "-b:a", "128k",
        output_pattern
    ]
    subprocess.run(command, check=True)
    return sorted([os.path.join(output_folder, f) for f in os.listdir(output_folder) if f.endswith(".mp3")])


def transcribe_audio(file_path):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    with open(file_path, "rb") as file:
        files = {"file": file}
        data = {
            "model": "whisper-1",
            "language": "uk",
            "temperature": 0,
            "prompt": "",
            "response_format": "json"
        }
        print(f"Відправляю {file_path} до OpenAI Whisper API...")
        response = requests.post("https://api.openai.com/v1/audio/transcriptions",
                                 headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json()["text"]

# Обрізаємо тишу перед транскрипцією або використовуємо оригінальний файл
AUDIO_FILE = trim_silence(AUDIO_FILE, TRIMMED_AUDIO_FILE)

# Виконання транскрипції
if get_file_size(AUDIO_FILE) > FILE_SIZE_LIMIT_MB:
    print("🔹 Файл завеликий, розбиваю на частини...")
    parts = split_audio(AUDIO_FILE, "audio_parts")
    transcriptions = []
    for part in parts:
        transcription = transcribe_audio(part)
        transcriptions.append(transcription)
    full_transcription = "\n".join(transcriptions)
else:
    print("🔹 Файл менший за 25MB, відправляю без розбиття...")
    full_transcription = transcribe_audio(AUDIO_FILE)

# Збереження транскрипції у файл
OUTPUT_FILE = "output/lecture.txt"
os.makedirs("output", exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(full_transcription)

print(f"✅ Транскрипція завершена! Результат збережено у {OUTPUT_FILE}")
