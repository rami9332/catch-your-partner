import face_recognition
import os
import sys
from image_validator import is_valid_face_image as is_valid_image
from match_logger import log_match_result

def match_face(test_image_path, known_faces_dir="known_faces"):
    print("🧠 Gesichtsanalyse läuft...")

    if not is_valid_image(test_image_path):
        print("❌ Bildprüfung: Fehler beim Bildprüfen – ungültiges oder leeres Bild.")
        return

    known_faces = []
    known_names = []

    for filename in os.listdir(known_faces_dir):
        if filename.startswith("."):
            continue

        filepath = os.path.join(known_faces_dir, filename)
        image = face_recognition.load_image_file(filepath)
        encoding = face_recognition.face_encodings(image)

        if encoding:
            known_faces.append(encoding[0])
            known_names.append(os.path.splitext(filename)[0])

    if not known_faces:
        print("⚠️ Keine bekannten Gesichter zum Vergleich gefunden.")
        return

    unknown_image = face_recognition.load_image_file(test_image_path)
    unknown_encodings = face_recognition.face_encodings(unknown_image)

    if not unknown_encodings:
        print("⚠️ Kein Gesicht im Testbild gefunden.")
        return

    unknown_encoding = unknown_encodings[0]

    distances = face_recognition.face_distance(known_faces, unknown_encoding)
    best_match_index = distances.argmin()
    best_distance = distances[best_match_index]
    best_match_name = known_names[best_match_index]

    print(f"✅ Match gefunden: {best_match_name} (Distanz: {best_distance:.2f})")
    log_match_result(test_image_path, best_match_name, best_distance)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Nutzung: python3 face_matcher.py <bildpfad>")
    else:
        match_face(sys.argv[1])
