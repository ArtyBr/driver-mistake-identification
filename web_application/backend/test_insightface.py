print("Importing insightface...")
try:
    from insightface.app import FaceAnalysis
    print("Success: from insightface.app import FaceAnalysis")
except Exception as e:
    print(f"Error: {e}")
except:
    print("Error: Unknown crash")
