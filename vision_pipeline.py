import os
import sqlite3
from datetime import datetime

# Try importing OpenCV and NumPy, with fallback if missing
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

DB_NAME = "curing_hub.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def inspect_anomalies_edge_ai(image_path: str) -> dict:
    """
    Modular Edge AI inference stub for Gemini Nano / On-device Multimodal LLM.
    Inspects pod image for mold, fungus spores, or defects.
    
    Returns:
        dict: {'mold_detected': bool, 'defect_notes': str}
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path: {image_path}")

    # Modular stub structured for Gemini Nano integration.
    # In production, this invokes the on-device Gemini Nano / TFLite runtime API.
    mold_detected = False
    defect_notes = "Edge AI (Gemini Nano Stub): Pod surface normal. No mold or white spores detected."

    return {
        "mold_detected": mold_detected,
        "defect_notes": defect_notes
    }

def compute_brown_ratio(image_path: str) -> float:
    """
    Loads an image and calculates the brown color ratio (%) of vanilla pods.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if HAS_OPENCV:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to load image via OpenCV: {image_path}")

        # Convert image to HSV color space for color segmentation
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Define HSV range for Brown (cured vanilla pod)
        lower_brown = np.array([0, 20, 20], dtype=np.uint8)
        upper_brown = np.array([30, 255, 200], dtype=np.uint8)
        brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)

        # Define HSV range for Green (fresh/uncured vanilla pod)
        lower_green = np.array([35, 30, 30], dtype=np.uint8)
        upper_green = np.array([85, 255, 255], dtype=np.uint8)
        green_mask = cv2.inRange(hsv, lower_green, upper_green)

        brown_pixels = cv2.countNonZero(brown_mask)
        green_pixels = cv2.countNonZero(green_mask)
        total_pod_pixels = brown_pixels + green_pixels

        if total_pod_pixels == 0:
            total_pixels = img.shape[0] * img.shape[1]
            brown_ratio = round((brown_pixels / total_pixels) * 100.0, 2)
        else:
            brown_ratio = round((brown_pixels / total_pod_pixels) * 100.0, 2)

        return brown_ratio
    else:
        # Fallback RGB heuristic if OpenCV is unavailable
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        pixels = list(img.getdata())
        brown_count = 0
        total_count = len(pixels)

        for r, g, b in pixels:
            if r > g and g >= b and r > 40:
                brown_count += 1

        return round((brown_count / total_count) * 100.0, 2) if total_count > 0 else 0.0

def analyze_pod_image(image_path: str, batch_id: str, tray_index: int) -> dict:
    """
    Analyzes pod image, runs Edge AI anomaly detection, and saves results into database.
    """
    # 1. Compute brown ratio using OpenCV color masking
    brown_ratio = compute_brown_ratio(image_path)

    # 2. Run Edge AI anomaly detection stub (Gemini Nano interface)
    edge_ai_result = inspect_anomalies_edge_ai(image_path)
    mold_detected = edge_ai_result["mold_detected"]

    # 3. Save inspection record to database
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vision_inspections (batch_id, tray_index, brown_ratio, mold_detected, image_path)
            VALUES (?, ?, ?, ?, ?)
        """, (batch_id, tray_index, brown_ratio, mold_detected, image_path))
        inspection_id = cursor.lastrowid

    return {
        "inspection_id": inspection_id,
        "batch_id": batch_id,
        "tray_index": tray_index,
        "brown_ratio": brown_ratio,
        "mold_detected": mold_detected,
        "defect_notes": edge_ai_result["defect_notes"],
        "image_path": image_path
    }

def create_synthetic_test_image(output_path: str = "test_pod_sample.jpg"):
    """
    Generates a synthetic test image containing brown and green sections representing vanilla pods.
    """
    if HAS_OPENCV:
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)  # Dark background

        # Draw a brown cured vanilla pod section (BGR)
        cv2.rectangle(img, (50, 100), (350, 220), (25, 60, 120), -1)

        # Draw a green uncured vanilla pod section (BGR)
        cv2.rectangle(img, (50, 250), (350, 320), (30, 160, 40), -1)

        cv2.imwrite(output_path, img)
    else:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 400), (30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 100, 350, 220], fill=(120, 60, 25))
        draw.rectangle([50, 250, 350, 320], fill=(40, 160, 30))
        img.save(output_path)

    print(f"Synthetic test image created at: {output_path}")

if __name__ == "__main__":
    print("=== Running Vision Pipeline Self-Test ===")
    test_img = "test_pod_sample.jpg"
    create_synthetic_test_image(test_img)

    batch_id = "BATCH-202608-01"

    # Ensure batch metadata exists
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT batch_id FROM batch_metadata WHERE batch_id = ?", (batch_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO batch_metadata (batch_id, species, initial_mass_g, current_state)
                VALUES (?, ?, ?, ?)
            """, (batch_id, "Planifolia", 5000.0, "STATE_1_SWEATING"))

    # Execute analysis
    result = analyze_pod_image(test_img, batch_id, tray_index=1)
    print("\nAnalysis Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Database Verification
    print("\nDatabase Verification (`vision_inspections` table):")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT inspection_id, batch_id, timestamp, tray_index, brown_ratio, mold_detected, image_path
            FROM vision_inspections
            WHERE batch_id = ?
            ORDER BY inspection_id DESC LIMIT 1
        """, (batch_id,))
        row = cursor.fetchone()
        if row:
            print(f"  ID: {row[0]}")
            print(f"  Batch ID: {row[1]}")
            print(f"  Timestamp: {row[2]}")
            print(f"  Tray Index: {row[3]}")
            print(f"  Brown Ratio: {row[4]}%")
            print(f"  Mold Detected: {bool(row[5])}")
            print(f"  Image Path: {row[6]}")
        else:
            print("  [ERROR] No record found in vision_inspections!")
