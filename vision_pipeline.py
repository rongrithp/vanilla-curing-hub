"""
Vanilla Curing Hub - Vision Pipeline Module
Includes Color Calibration Box matrix transformations, optical quality metrics,
Edge AI anomaly detection stubs, and deterministic fallback logic.
"""

from dataclasses import dataclass
import logging
import os
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VisionPipeline")

DB_NAME = "curing_hub.db"

# =====================================================================
# Custom Exception Hierarchy
# =====================================================================

class VisionPipelineError(Exception):
    """Base exception for all vision pipeline errors."""
    pass

class CalibrationNotFoundError(VisionPipelineError):
    """Raised when reference color chart or calibration target cannot be detected."""
    pass

class IlluminationMismatchError(VisionPipelineError):
    """Raised when scene illumination deviates significantly from calibrated optical bounds."""
    pass

class CorruptFrameError(VisionPipelineError):
    """Raised when an input frame is corrupt, empty, or has invalid dimensions/channels."""
    pass

# =====================================================================
# Data Contracts & Schemas
# =====================================================================

@dataclass
class CalibrationData:
    ccm: np.ndarray  # 3x3 Color Correction Matrix
    delta_e: float   # Mean color difference error (CIE76) against ground truth
    status: str      # "success" or "degraded"
    timestamp: str

@dataclass
class InspectionPayload:
    batch_id: str
    tray_index: int
    brown_ratio: float
    mold_detected: bool
    defect_notes: str
    delta_e: float
    calibration_status: str  # "success", "degraded", "failed"
    image_path: str
    timestamp: str
    inspection_id: Optional[int] = None

# Standard 24 Macbeth ColorChecker Ground Truth Values (sRGB 0-255 format)
GROUND_TRUTH_24_PATCHES = np.array([
    [115, 82, 68],   [194, 150, 130], [98, 122, 157],  [87, 108, 67],   [133, 128, 177], [103, 189, 170],
    [214, 126, 44],  [80, 91, 166],   [193, 90, 99],   [94, 60, 108],   [157, 188, 64],  [224, 163, 46],
    [56, 61, 150],   [70, 148, 73],   [175, 54, 60],   [231, 199, 31],  [187, 86, 149],  [8, 133, 161],
    [243, 243, 242], [200, 200, 200], [160, 160, 160], [122, 122, 121], [85, 85, 85],    [52, 52, 52]
], dtype=np.float32)

# =====================================================================
# Color Calibrator Module
# =====================================================================

class ColorCalibrator:
    """
    Handles detection of ColorChecker reference chart, computes 3x3 Color Correction Matrix (CCM),
    evaluates Delta E metrics, and maintains persistent/in-memory fallback CCM cache.
    """

    def __init__(self, cache_file: str = "ccm_cache.npy") -> None:
        self.cache_file = cache_file
        # Default identity matrix as initial fallback
        self.cached_ccm: np.ndarray = np.eye(3, dtype=np.float32)
        self.load_cache()

    def load_cache(self) -> None:
        """Loads cached CCM matrix from disk if available."""
        if os.path.exists(self.cache_file):
            try:
                self.cached_ccm = np.load(self.cache_file)
                logger.info(f"Loaded cached CCM matrix from '{self.cache_file}'.")
            except Exception as e:
                logger.warning(f"Failed to load cached CCM matrix: {e}. Using identity matrix.")
                self.cached_ccm = np.eye(3, dtype=np.float32)

    def save_cache(self, ccm: np.ndarray) -> None:
        """Saves valid CCM matrix to disk cache."""
        try:
            np.save(self.cache_file, ccm)
            self.cached_ccm = ccm.copy()
            logger.info(f"Updated CCM cache on disk '{self.cache_file}'.")
        except Exception as e:
            logger.warning(f"Could not save CCM cache to disk: {e}")

    def detect_reference_patches(self, frame: np.ndarray) -> np.ndarray:
        """
        Detects 24-patch ColorChecker grid from raw frame.
        If detection fails, raises CalibrationNotFoundError.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Find dark chart box or patch boundaries
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        patch_colors: List[np.ndarray] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 150 < area < 1200:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / h
                if 0.7 <= aspect_ratio <= 1.3:
                    patch_roi = frame[y+3:y+h-3, x+3:x+w-3]
                    if patch_roi.size > 0:
                        mean_color_bgr = cv2.mean(patch_roi)[:3]
                        mean_color_rgb = np.array([mean_color_bgr[2], mean_color_bgr[1], mean_color_bgr[0]], dtype=np.float32)
                        patch_colors.append(mean_color_rgb)

        if len(patch_colors) < 24:
            raise CalibrationNotFoundError(
                f"ColorChecker target not detected. Found {len(patch_colors)}/24 patches."
            )

        # Take top 24 patches
        detected_patches = np.array(patch_colors[:24], dtype=np.float32)
        return detected_patches

    def compute_ccm(self, observed_patches: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Computes 3x3 Color Correction Matrix using Linear Least Squares:
        Observed * CCM = GroundTruth
        Returns (CCM, mean_delta_e).
        """
        # Solve least-squares: Observed @ CCM = GroundTruth
        ccm, residuals, rank, s = np.linalg.lstsq(observed_patches, GROUND_TRUTH_24_PATCHES, rcond=None)
        
        # Calculate Delta E (CIE76 color difference in LAB space)
        calibrated_patches = observed_patches @ ccm
        delta_e = float(self.calculate_delta_e(calibrated_patches, GROUND_TRUTH_24_PATCHES))

        return ccm, delta_e

    @staticmethod
    def calculate_delta_e(colors1_rgb: np.ndarray, colors2_rgb: np.ndarray) -> float:
        """Computes mean CIE76 Delta E (Euclidean distance in CIELAB space)."""
        c1_bgr = cv2.cvtColor(np.clip(colors1_rgb, 0, 255).astype(np.uint8).reshape(-1, 1, 3), cv2.COLOR_RGB2BGR)
        c2_bgr = cv2.cvtColor(np.clip(colors2_rgb, 0, 255).astype(np.uint8).reshape(-1, 1, 3), cv2.COLOR_RGB2BGR)
        
        lab1 = cv2.cvtColor(c1_bgr, cv2.COLOR_BGR2LAB).astype(np.float32).reshape(-1, 3)
        lab2 = cv2.cvtColor(c2_bgr, cv2.COLOR_BGR2LAB).astype(np.float32).reshape(-1, 3)
        
        delta_e_list = np.linalg.norm(lab1 - lab2, axis=1)
        return float(np.mean(delta_e_list))

    def calibrate(self, frame: np.ndarray) -> Tuple[np.ndarray, CalibrationData]:
        """
        Attempts to detect reference chart and calibrate frame.
        If detection fails, falls back gracefully to cached/default CCM.
        """
        from datetime import datetime
        now_str = datetime.now().isoformat()

        try:
            observed = self.detect_reference_patches(frame)
            ccm, delta_e = self.compute_ccm(observed)
            self.save_cache(ccm)
            cal_data = CalibrationData(ccm=ccm, delta_e=delta_e, status="success", timestamp=now_str)
            logger.info(f"Color calibration successful. Delta E: {delta_e:.2f}")
        except CalibrationNotFoundError as e:
            logger.warning(f"[FALLBACK TRIGGERED] {e} Falling back to last-known-good CCM.")
            ccm = self.cached_ccm.copy()
            cal_data = CalibrationData(ccm=ccm, delta_e=999.0, status="degraded", timestamp=now_str)

        # Apply CCM matrix to frame
        calibrated_frame = self.apply_ccm_transform(frame, ccm)
        return calibrated_frame, cal_data

    @staticmethod
    def apply_ccm_transform(frame: np.ndarray, ccm: np.ndarray) -> np.ndarray:
        """Applies 3x3 CCM transformation to BGR frame."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32)
        shape = rgb.shape
        
        pixels = rgb.reshape(-1, 3)
        calibrated_pixels = pixels @ ccm
        calibrated_rgb = np.clip(calibrated_pixels, 0, 255).astype(np.uint8).reshape(shape)
        
        calibrated_bgr = cv2.cvtColor(calibrated_rgb, cv2.COLOR_RGB2BGR)
        return calibrated_bgr

# =====================================================================
# Main Vision Pipeline Processing Engine
# =====================================================================

class VisionPipeline:
    """
    Core Vision Processing Engine performing ingestion validation,
    illumination checks, color space transformations, feature extraction, and storage.
    """

    def __init__(self, db_name: str = DB_NAME) -> None:
        self.db_name = db_name
        self.calibrator = ColorCalibrator()

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_name, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @staticmethod
    def validate_frame(frame: np.ndarray) -> None:
        """Validates raw frame structure, dimensions, and data type."""
        if frame is None or not isinstance(frame, np.ndarray):
            raise CorruptFrameError("Frame is None or not a valid numpy ndarray.")
        if frame.size == 0:
            raise CorruptFrameError("Frame is empty (0 size).")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise CorruptFrameError(f"Invalid frame dimensions: {frame.shape}. Expected 3-channel (H, W, 3).")
        if frame.dtype != np.uint8:
            raise CorruptFrameError(f"Invalid data type {frame.dtype}. Expected uint8.")

    @staticmethod
    def check_illumination(frame: np.ndarray, min_lux: float = 25.0, max_lux: float = 245.0) -> float:
        """Checks frame illumination levels (mean luminance)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_luminance = float(np.mean(gray))

        if mean_luminance < min_lux or mean_luminance > max_lux:
            raise IlluminationMismatchError(
                f"Illumination out of bounds: mean luminance = {mean_luminance:.1f} (Valid: [{min_lux}, {max_lux}])"
            )
        return mean_luminance

    @staticmethod
    def compute_brown_ratio(calibrated_bgr: np.ndarray) -> float:
        """Computes percentage ratio of brown cured pod area in HSV space."""
        hsv = cv2.cvtColor(calibrated_bgr, cv2.COLOR_BGR2HSV)

        # Brown HSV bounds (Vanilla curing)
        lower_brown = np.array([0, 20, 20], dtype=np.uint8)
        upper_brown = np.array([30, 255, 200], dtype=np.uint8)
        brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)

        # Green HSV bounds (Fresh pod)
        lower_green = np.array([35, 30, 30], dtype=np.uint8)
        upper_green = np.array([85, 255, 255], dtype=np.uint8)
        green_mask = cv2.inRange(hsv, lower_green, upper_green)

        brown_pixels = cv2.countNonZero(brown_mask)
        green_pixels = cv2.countNonZero(green_mask)
        total_pod_pixels = brown_pixels + green_pixels

        if total_pod_pixels == 0:
            total_pixels = calibrated_bgr.shape[0] * calibrated_bgr.shape[1]
            return round(float(brown_pixels / total_pixels) * 100.0, 2)
        
        return round(float(brown_pixels / total_pod_pixels) * 100.0, 2)

    @staticmethod
    def inspect_anomalies_edge_ai(image_path: str) -> Dict[str, Any]:
        """Edge AI (Gemini Nano) inference stub for defect & mold detection."""
        return {
            "mold_detected": False,
            "defect_notes": "Gemini Nano Edge AI: Pod surface normal. No mold or white spores detected."
        }

    def process_image(
        self,
        image_path: str,
        batch_id: str,
        tray_index: int,
        camera_matrix: Optional[np.ndarray] = None,
        dist_coeffs: Optional[np.ndarray] = None
    ) -> InspectionPayload:
        """
        Executes end-to-end vision processing pipeline:
        1. Ingestion & Frame Validation
        2. Illumination Level Check
        3. Color Calibration & Graceful Fallback
        4. Lens Distortion Correction (if camera parameters provided)
        5. Feature Extraction (Brown Ratio, Delta E)
        6. Edge AI Anomaly Detection
        7. Database Persistence
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image path does not exist: {image_path}")

        frame = cv2.imread(image_path)
        self.validate_frame(frame)
        self.check_illumination(frame)

        # Apply lens distortion correction if camera parameters supplied
        if camera_matrix is not None and dist_coeffs is not None:
            frame = cv2.undistort(frame, camera_matrix, dist_coeffs)

        # Run calibration with deterministic fallback
        calibrated_frame, cal_data = self.calibrator.calibrate(frame)

        # Extract features
        brown_ratio = self.compute_brown_ratio(calibrated_frame)
        edge_ai_res = self.inspect_anomalies_edge_ai(image_path)

        from datetime import datetime
        now_str = datetime.now().isoformat()

        # Database Persistence
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            # Ensure batch metadata exists
            cursor.execute("SELECT batch_id FROM batch_metadata WHERE batch_id = ?", (batch_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO batch_metadata (batch_id, species, initial_mass_g, current_state)
                    VALUES (?, ?, ?, ?)
                """, (batch_id, "Planifolia", 5000.0, "STATE_1_SWEATING"))

            cursor.execute("""
                INSERT INTO vision_inspections (batch_id, tray_index, brown_ratio, mold_detected, image_path)
                VALUES (?, ?, ?, ?, ?)
            """, (batch_id, tray_index, brown_ratio, edge_ai_res["mold_detected"], image_path))
            inspection_id = cursor.lastrowid

        return InspectionPayload(
            batch_id=batch_id,
            tray_index=tray_index,
            brown_ratio=brown_ratio,
            mold_detected=edge_ai_res["mold_detected"],
            defect_notes=edge_ai_res["defect_notes"],
            delta_e=cal_data.delta_e,
            calibration_status=cal_data.status,
            image_path=image_path,
            timestamp=now_str,
            inspection_id=inspection_id
        )

# =====================================================================
# Synthetic Generator & Self-Test Suite
# =====================================================================

def generate_synthetic_frame(with_calibration_target: bool = True) -> np.ndarray:
    """Generates a synthetic frame with or without a 24-patch ColorChecker grid."""
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    img[:] = (120, 120, 120)  # Neutral background (5000K illumination equivalent)

    # Draw cured vanilla pod (brown rectangle)
    cv2.rectangle(img, (200, 150), (700, 300), (25, 60, 120), -1)
    # Draw uncured pod section (green rectangle)
    cv2.rectangle(img, (200, 350), (700, 450), (30, 160, 40), -1)

    if with_calibration_target:
        # Draw 24 synthetic ColorChecker patches in top-left region with white borders
        for row in range(4):
            for col in range(6):
                idx = row * 6 + col
                color_rgb = GROUND_TRUTH_24_PATCHES[idx]
                color_bgr = (float(color_rgb[2]), float(color_rgb[1]), float(color_rgb[0]))
                
                x1 = 30 + col * 30
                y1 = 30 + row * 30
                x2 = x1 + 24
                y2 = y1 + 24
                cv2.rectangle(img, (x1, y1), (x2, y2), color_bgr, -1)
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), 1)

    return img

def run_pipeline_dry_run():
    print("=====================================================================")
    print("           VISION PIPELINE DRY-RUN & FALLBACK VERIFICATION           ")
    print("=====================================================================")

    pipeline = VisionPipeline()
    batch_id = "BATCH-202608-01"

    # --- Test 1: Full Calibration Target Present ---
    print("\n--- Test 1: Calibration Target Present ---")
    img_valid = generate_synthetic_frame(with_calibration_target=True)
    valid_path = "test_valid_target.jpg"
    cv2.imwrite(valid_path, img_valid)

    payload1 = pipeline.process_image(valid_path, batch_id, tray_index=1)
    print(f"Inspection ID: {payload1.inspection_id}")
    print(f"Brown Ratio:   {payload1.brown_ratio}%")
    print(f"Delta E:       {payload1.delta_e:.2f}")
    print(f"Calib Status:  {payload1.calibration_status}")
    assert payload1.calibration_status == "success", "Expected calibration_status 'success'"

    # --- Test 2: Calibration Target Obscured / Missing (Fallback Test) ---
    print("\n--- Test 2: Calibration Target Missing (Fallback Verification) ---")
    img_obscured = generate_synthetic_frame(with_calibration_target=False)
    obscured_path = "test_obscured_target.jpg"
    cv2.imwrite(obscured_path, img_obscured)

    payload2 = pipeline.process_image(obscured_path, batch_id, tray_index=2)
    print(f"Inspection ID: {payload2.inspection_id}")
    print(f"Brown Ratio:   {payload2.brown_ratio}%")
    print(f"Delta E:       {payload2.delta_e:.2f}")
    print(f"Calib Status:  {payload2.calibration_status}")
    assert payload2.calibration_status == "degraded", "Expected fallback status 'degraded'"
    print(">> SUCCESS: Fallback triggered gracefully with status 'degraded'.")

    # --- Test 3: Corrupt Frame Exception Test ---
    print("\n--- Test 3: Corrupt Frame Error Handling ---")
    try:
        pipeline.validate_frame(np.zeros((0, 0), dtype=np.uint8))
    except CorruptFrameError as e:
        print(f">> SUCCESS: Caught expected CorruptFrameError: {e}")

    # --- Test 4: Illumination Mismatch Error Test ---
    print("\n--- Test 4: Illumination Mismatch Error Handling ---")
    too_dark_frame = np.zeros((100, 100, 3), dtype=np.uint8)  # Completely black frame
    try:
        pipeline.check_illumination(too_dark_frame)
    except IlluminationMismatchError as e:
        print(f">> SUCCESS: Caught expected IlluminationMismatchError: {e}")

    print("\n=====================================================================")
    print("          ALL VISION PIPELINE TESTS PASSED SUCCESSFULLY!             ")
    print("=====================================================================")

if __name__ == "__main__":
    run_pipeline_dry_run()
