import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import cv2
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent / 'src'
sys.path.append(str(src_path))

from face_analyzer import FaceAnalyzer

class TestFaceAnalyzer(unittest.TestCase):
    @patch('face_analyzer.FaceAnalysis')
    @patch('face_analyzer.FaceAnalyzer._load_model')
    def setUp(self, mock_load, mock_app):
        self.analyzer = FaceAnalyzer('dummy_models_dir')
        self.analyzer.app = MagicMock()
        self.analyzer.svm = MagicMock()
        self.analyzer.pca = MagicMock()

    def test_identify_driver_landscape_left(self):
        # Landscape: 1280x720
        frame_shape = (720, 1280, 3)
        
        # Mock faces
        face_left = MagicMock()
        face_left.bbox = np.array([100, 100, 300, 300]) # Left side (center x=200 < 640)
        
        face_right = MagicMock()
        face_right.bbox = np.array([800, 100, 1100, 400]) # Right side (center x=950 > 640), larger area
        
        faces = [face_left, face_right]
        
        driver = self.analyzer._identify_driver(faces, frame_shape)
        self.assertEqual(driver, face_left)

    def test_identify_driver_landscape_no_left(self):
        # Landscape: 1280x720
        frame_shape = (720, 1280, 3)
        
        # Mock faces
        face_right_small = MagicMock()
        face_right_small.bbox = np.array([700, 100, 800, 200]) # Right side
        
        face_right_large = MagicMock()
        face_right_large.bbox = np.array([850, 100, 1100, 400]) # Right side, larger
        
        faces = [face_right_small, face_right_large]
        
        driver = self.analyzer._identify_driver(faces, frame_shape)
        self.assertEqual(driver, face_right_large)

    def test_identify_driver_portrait(self):
        # Portrait: 720x1280
        frame_shape = (1280, 720, 3)
        
        # Mock faces
        face_small = MagicMock()
        face_small.bbox = np.array([50, 100, 150, 200]) # Left side
        
        face_large = MagicMock()
        face_large.bbox = np.array([400, 100, 650, 400]) # Right side, larger
        
        faces = [face_small, face_large]
        
        driver = self.analyzer._identify_driver(faces, frame_shape)
        self.assertEqual(driver, face_large)

    def test_apply_blurring(self):
        # Create a frame with some noise/pattern to detect blur better
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Checkerboard pattern in ROIs
        for i in range(200):
            for j in range(200):
                if (i + j) % 2 == 0:
                    frame[i, j] = 255
        
        face1 = MagicMock()
        face1.bbox = np.array([10, 10, 60, 60]) # 50x50
        
        face2 = MagicMock()
        face2.bbox = np.array([100, 100, 160, 160]) # 60x60
        
        # Case: face1 is driver, face2 should be blurred
        # Mock faces must be in a list
        faces = [face1, face2]
        blurred = self.analyzer._apply_blurring(frame, faces, face1)
        
        # Area of face1 should remain exactly same
        self.assertTrue(np.array_equal(frame[10:60, 10:60], blurred[10:60, 10:60]))
        
        # Area of face2 should be different (blurred)
        # We use a checkerboard pattern which is very sensitive to blurring
        is_equal = np.array_equal(frame[100:160, 100:160], blurred[100:160, 100:160])
        self.assertFalse(is_equal, "Face 2 area should have been blurred but remained equal")

if __name__ == '__main__':
    unittest.main()
