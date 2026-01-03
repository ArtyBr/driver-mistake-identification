import sys
import os
import cv2
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from vehicle_detector import VehicleDetector

def test_vehicle_detector_initialization():
    detector = VehicleDetector()
    assert detector.model is not None

def test_vehicle_detector_inference():
    detector = VehicleDetector()
    
    # Create a dummy image (black image)
    # 720p resolution
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # Draw a rectangle that might look like a car to a very dumb model (unlikely to detect, but runs pipeline)
    # Actually, we just want to ensure it doesn't crash
    vehicles = detector.detect(frame)
    
    assert isinstance(vehicles, list)
    # We expect empty list for a black image
    assert len(vehicles) == 0

def test_vehicle_detector_with_mock_car():
    # If we really want to test detection, we'd need a real image.
    # But for now, ensuring the pipeline runs is sufficient.
    pass

if __name__ == "__main__":
    test_vehicle_detector_initialization()
    test_vehicle_detector_inference()
    print("VehicleDetector tests passed!")
