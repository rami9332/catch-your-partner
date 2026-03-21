# check_image.py
import face_recognition
import os
import sys
import shutil
from PIL import Image

ACCEPTED_FOLDER = "uploads/accepted"
REJECTED_FOLDER = "uploads/rejected"

MAX_RESOLUTION = (3000, 3000)
MAX_FILE_SIZE_MB = 5
MIN_FACE_AREA_RATIO = 0.05  # Mindestens 5% der Bildfläche muss das Gesicht einnehmen (Selfie-Erkennung)

def check_profile_image(image_path):
    if not os.path.exists(image_path):
        print("❌ Datei nicht gefunden:", image_path)
        return

    if is_fake_suspected(image_path):
        print("🚫 Bild wirkt gefälscht (zu groß oder KI-ähnlich).")
        move_image(image_path, REJECTED_FOLDER)
        return

    try:
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)

        if len(face_locations) == 0:
            print("🚫 Kein Gesicht erkannt – Bild wird abgelehnt.")
            move_image(image_path, REJECTED_FOLDER)
            return

        # Prüfe Selfie-Faktor: Ist das Gesicht groß genug?
        if not is_selfie_like(image, face_locations):
            print("🚫 Gesicht zu klein – kein echtes Selfie. Bild abgelehnt.")
            move_image(image_path, REJECTED_FOLDER)
            return

        print("✅ Gesicht erkannt – Bild akzeptiert.")
        move_image(image_path, ACCEPTED_FOLDER)

    except Exception as e:
        print("⚠️ Fehler beim Verarbeiten des Bildes:", e)
        move_image(image_path, REJECTED_FOLDER)


def is_fake_suspected(image_path):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
            if width > MAX_RESOLUTION[0] or height > MAX_RESOLUTION[1]:
                return True
            if file_size_mb > MAX_FILE_SIZE_MB:
                return True
    except:
        return True
    return False


def is_selfie_like(image, face_locations):
    height, width, _ = image.shape
    for (top, right, bottom, left) in face_locations:
        face_area = (bottom - top) * (right - left)
        image_area = height * width
        ratio = face_area / image_area
        if ratio >= MIN_FACE_AREA_RATIO:
            return True
    return False


def move_image(source_path, target_folder):
    os.makedirs(target_folder, exist_ok=True)
    filename = os.path.basename(source_path)
    target_path = os.path.join(target_folder, filename)
    shutil.move(source_path, target_path)
    print(f"📁 Bild verschoben nach: {target_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Fehlender Bildpfad. Beispiel: python3 check_image.py uploads/test.jpg")
    else:
        image_path = sys.argv[1]
        check_profile_image(image_path)

