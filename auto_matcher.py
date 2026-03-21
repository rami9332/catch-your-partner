import face_recognition
import os
import sys
import json

def save_profile(name):
    profile = {
        "name": name
    }

    if not os.path.exists("users.json"):
        with open("users.json", "w") as f:
            json.dump([profile], f, indent=2)
    else:
        with open("users.json", "r+") as f:
            data = json.load(f)
            data.append(profile)
            f.seek(0)
            json.dump(data, f, indent=2)

def match_face(test_image_path, known_faces_dir="known_faces"):
    print("🧠 Gesichtsanalyse läuft...")

    known_faces = []
    known_names = []

    for filename in os.listdir(known_faces_dir):
        if filename.startswith('.'):  # ignoriert .DS_Store und versteckte Dateien
            continue
        try:
            image = face_recognition.load_image_file(os.path.join(known_faces_dir, filename))
            encoding = face_recognition.face_encodings(image)
            if encoding:
                known_faces.append(encoding[0])
                known_names.append(os.path.splitext(filename)[0])
        except Exception as e:
            print(f"❗️Fehler mit Datei {filename}: {e}")

    unknown_image = face_recognition.load_image_file(test_image_path)
    unknown_encodings = face_recognition.face_encodings(unknown_image)

    if not unknown_encodings:
        print("❌ Kein Gesicht erkannt.")
        return

    result = face_recognition.compare_faces(known_faces, unknown_encodings[0])
    distances = face_recognition.face_distance(known_faces, unknown_encodings[0])

    if True in result:
        match_index = result.index(True)
        name = known_names[match_index]
        print(f"✅ Match gefunden: {name} (Distanz: {distances[match_index]:.2f})")
    else:
        # neuen Namen generieren
        name = os.path.splitext(os.path.basename(test_image_path))[0]
        new_filename = f"known_faces/{name}.jpg"
        os.rename(test_image_path, new_filename)
        save_profile(name)
        print(f"📥 Kein Match – neues Profil gespeichert als '{name}'.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Fehler beim Laden: Bildpfad fehlt")
    else:
        match_face(sys.argv[1])
