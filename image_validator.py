import face_recognition

def is_valid_face_image(image_path):
    try:
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)

        if len(face_locations) == 0:
            return False, "❌ Kein Gesicht erkannt."
        elif len(face_locations) > 1:
            return False, "⚠️ Mehrere Gesichter erkannt. Bitte nur dein eigenes Profilbild hochladen."
        else:
            return True, "✅ Ein einzelnes Gesicht erkannt – Bild gültig."
    except Exception as e:
        return False, f"❌ Fehler beim Bildprüfen: {e}"
