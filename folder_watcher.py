import os
import time
import face_recognition
import shutil

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
REJECTED_DIR = "rejected"
KNOWN_FACES_DIR = "known_faces"

def match_face(test_image_path):
    known_faces = []
    known_names = []

    for filename in os.listdir(KNOWN_FACES_DIR):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        image = face_recognition.load_image_file(os.path.join(KNOWN_FACES_DIR, filename))
        encoding = face_recognition.face_encodings(image)
        if encoding:
            known_faces.append(encoding[0])
            known_names.append(os.path.splitext(filename)[0])

    unknown_image = face_recognition.load_image_file(test_image_path)
    unknown_encodings = face_recognition.face_encodings(unknown_image)

    if not unknown_encodings:
        return None, None

    result = face_recognition.compare_faces(known_faces, unknown_encodings[0])
    face_distances = face_recognition.face_distance(known_faces, unknown_encodings[0])

    if any(result):
        best_match_index = face_distances.argmin()
        return known_names[best_match_index], face_distances[best_match_index]

    return None, None

def watch_upload_folder():
    print("🔍 Beobachte Ordner:", UPLOAD_DIR)
    already_seen = set()

    while True:
        for filename in os.listdir(UPLOAD_DIR):
            if filename in already_seen or not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            file_path = os.path.join(UPLOAD_DIR, filename)
            already_seen.add(filename)
            print(f"🖼️ Neues Bild erkannt: {filename}")
            print("🧠 Gesichtsanalyse läuft...")

            match_name, distance = match_face(file_path)

            if match_name:
                print(f"✅ Match gefunden: {match_name} (Distanz: {distance:.2f})")
                target_path = os.path.join(PROCESSED_DIR, filename)
            else:
                print("❌ Kein Match gefunden.")
                target_path = os.path.join(REJECTED_DIR, filename)

            shutil.move(file_path, target_path)
            print(f"💾 Datei verschoben nach: {target_path}")

        time.sleep(1)

if __name__ == "__main__":
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)
    watch_upload_folder()
