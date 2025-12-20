import json
import numpy as np

def generate():
    data = {
        "meta": {"duration": 180.0, "fps": 30.0},
        "timeline_events": [
            {"timestamp": 5.5, "type": "safety_alert", "severity": "CRITICAL", "message": "Unsafe Lane Change: No Mirror Check", "duration": 2.0},
            {"timestamp": 15.0, "type": "safety_alert", "severity": "WARNING", "message": "Distracted", "duration": 1.5}
        ],
        "frame_data": []
    }

    # Generate 180s * 30fps = 5400 frames
    for i in range(5400):
        t = i / 30.0
        
        # Fake Lane Lines (Basic inverted V shape)
        # Left lane
        l_x1, l_y1 = 200 + np.sin(t/5)*50, 1080
        l_x2, l_y2 = 800 + np.sin(t/5)*20, 600
        
        # Right lane
        r_x1, r_y1 = 1720 + np.sin(t/5)*50, 1080
        r_x2, r_y2 = 1120 + np.sin(t/5)*20, 600
        
        lanes = [
            [[l_x1, l_y1], [l_x2, l_y2]],
            [[r_x1, r_y1], [r_x2, r_y2]]
        ]

        # Fake Face Info
        # Head nodding
        pitch = np.sin(t) * 10
        yaw = np.cos(t/2) * 15
        
        state = "Looking Ahead"
        if 5.0 < t < 7.0: state = "Distracted"
        if 14.0 < t < 16.0: state = "Right Mirror"

        frame = {
            "time": t,
            "lane_lines": lanes,
            "face_info": {
                "bbox": [200, 200, 400, 400],
                "yaw": yaw,
                "pitch": pitch,
                "roll": 0
            },
            "current_state": state
        }
        data["frame_data"].append(frame)

    with open("mock_results.json", "w") as f:
        json.dump(data, f)
    print("Mock data generated.")

if __name__ == "__main__":
    generate()
