import sys
print("Python version:", sys.version)
print("Python executable:", sys.executable)

try:
    import numpy
    print("numpy imported, version:", numpy.__version__)
except Exception as e:
    print("numpy import failed:", e)

try:
    import cv2
    print("cv2 imported, version:", cv2.__version__)
except Exception as e:
    print("cv2 import failed:", e)

try:
    import torch
    print("torch imported, version:", torch.__version__)
except Exception as e:
    print("torch import failed:", e)

try:
    import torchvision
    print("torchvision imported, version:", torchvision.__version__)
except Exception as e:
    print("torchvision import failed:", e)