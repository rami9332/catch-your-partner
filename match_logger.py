from datetime import datetime

def log_match_result(test_image_path, best_match_name, best_distance, log_path="match_log.txt"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"📅 {timestamp} | Bild: {test_image_path} | Match: {best_match_name} | Distanz: {best_distance:.2f}\n"

    with open(log_path, "a") as log_file:
        log_file.write(log_entry)
