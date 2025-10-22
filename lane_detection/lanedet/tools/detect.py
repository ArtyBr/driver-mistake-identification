import os, cv2, glob, torch, argparse
import numpy as np
from tqdm import tqdm
from pathlib import Path
from lanedet.datasets.process import Process
from lanedet.models.registry import build_net
from lanedet.utils.config import Config
from lanedet.utils.visualization import imshow_lanes
from lanedet.utils.net_utils import load_network
from helper_classes import LaneTracker

LANE_COLORS = [
    (0, 0, 255),   # Red
    (0, 255, 0),   # Green
    (255, 0, 0),   # Blue
    (0, 255, 255),  # Yellow
    (255, 0, 255),  # Magenta
    (255, 255, 0),  # Cyan
]

class Detect:
    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = Process(cfg.val_process, cfg)
        self.net = torch.nn.DataParallel(build_net(cfg), device_ids=range(1)).cuda().eval()
        load_network(self.net, cfg.load_from)

    def _pre(self, img):
        ori = cv2.resize(img, (self.cfg.ori_img_w, self.cfg.ori_img_h))
        data = {'img': ori[self.cfg.cut_height:].astype(np.float32), 'lanes': []}
        data = self.proc(data)
        data['img'] = data['img'].unsqueeze(0)
        data['ori_img'] = ori
        return data

    def preprocess(self, path):
        img = cv2.imread(path)
        data = self._pre(img)
        data['img_path'] = path
        return data

    @torch.no_grad()
    def inference(self, data):
        out = self.net(data)
        return self.net.module.get_lanes(out)[0]

    def visualize(self, ori_img, lanes, path=None):
        lanes = [l.to_array(self.cfg) for l in lanes]
        imshow_lanes(ori_img, lanes, show=self.cfg.show, out_file=path)

    def run(self, path):
        d = self.preprocess(path)
        d['lanes'] = self.inference(d)
        if self.cfg.show or self.cfg.savedir:
            out = os.path.join(self.cfg.savedir, os.path.basename(path)) if self.cfg.savedir else None
            os.makedirs(self.cfg.savedir, exist_ok=True) if out else None
            self.visualize(d['ori_img'], d['lanes'], out)
        return d

    def run_on_frame(self, frame):
        d = self._pre(frame)
        lanes = self.inference(d)
        lanes = [l.to_array(self.cfg) for l in lanes]
        return imshow_lanes(d['ori_img'], lanes, show=False)
    
    # Added
    def get_lane_detections(self, frame):
        d = self._pre(frame)
        lane_objects = self.inference(d)
        
        detected_lanes_coeffs = []
        for lane in lane_objects:
            points = lane.to_array(self.cfg)
            if points.shape[0] < 2: # Need at least 2 points to fit
                continue
                
            y_points = points[:, 1]
            x_points = points[:, 0]
            
            try:
                # Fit a 2nd degree polynomial
                coeffs = np.polyfit(y_points, x_points, 2) # [a, b, c]
                detected_lanes_coeffs.append(coeffs)
            except np.linalg.LinAlgError:
                # Fitting can fail
                continue
                
        return detected_lanes_coeffs, d['ori_img']


def get_paths(p):
    p = str(Path(p).absolute())
    if '*' in p: return sorted(glob.glob(p, recursive=True))
    if os.path.isdir(p): return sorted(glob.glob(os.path.join(p, '*.*')))
    if os.path.isfile(p): return [p]
    raise FileNotFoundError(f'{p} not found')


def process_image(args, cfg):
    det = Detect(cfg)
    for p in tqdm(get_paths(args.img), desc='Images'):
        det.run(p)

# added
def visualize_tracked_lanes(ori_img, lanes_coeffs, cfg, show=False, out_file=None):
    vis_img = ori_img.copy()
    
    # Define the y-values to evaluate the polynomial at
    y_points = np.linspace(2*vis_img.shape[0]//3, vis_img.shape[0] - 1, 100)
    
    for coeffs in lanes_coeffs:
        (a, b, c), id = coeffs
        this_color = LANE_COLORS[id % len(LANE_COLORS)]

        # Calculate x for each y: x = ay^2 + by + c
        x_points = a * y_points**2 + b * y_points + c
        
        # Create (x, y) points
        points = np.vstack((x_points, y_points)).T
        
        # Filter out points outside the image width
        points = points[(points[:, 0] >= 0) & (points[:, 0] < vis_img.shape[1])]
        
        # Draw the lane as a polyline
        cv2.polylines(vis_img, [points.astype(np.int32)], isClosed=False, color=this_color, thickness=2)

    if show:
        cv2.imshow('Tracked Lanes', vis_img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return None # Signal to quit

    if out_file:
        cv2.imwrite(out_file, vis_img)
        
    return vis_img

def process_video(args, cfg):
    det = Detect(cfg)
    tracker = LaneTracker() # <-- Initialize the tracker
    
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened(): raise Exception(f"Cannot open {args.video}")
    fps, out_w, out_h = cap.get(cv2.CAP_PROP_FPS), cfg.ori_img_w, cfg.ori_img_h

    if args.savedir:
        os.makedirs(args.savedir, exist_ok=True)
        out_path = os.path.join(args.savedir, f"{Path(args.video).stem}_output.mp4")
        out_writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (out_w, out_h))
        print(f"Saving to: {out_path}")
    
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    skip = max(1, args.skip_frame)
    frame_idx = 0

    for _ in tqdm(range(total), desc=f"Video {Path(args.video).name}"):
        ret, frame = cap.read()
        if not ret: break
        if frame_idx % skip != 0:
            frame_idx += 1
            continue
        frame_idx += 1

        # 1. Get polynomial detections
        detected_coeffs, ori_img = det.get_lane_detections(frame)
        
        # 2. Update tracker
        filtered_lane_coeffs = tracker.update(detected_coeffs)
        
        # 3. Visualize the filtered lanes
        vis = visualize_tracked_lanes(ori_img, filtered_lane_coeffs, cfg, show=args.show)
        
        if args.show and vis is None: # Quit signal
             break

        if out_writer: out_writer.write(vis)

    cap.release()
    if out_writer: out_writer.release()
    cv2.destroyAllWindows()

# def process_video(args, cfg):
#     det = Detect(cfg)
#     cap = cv2.VideoCapture(args.video)
#     if not cap.isOpened(): raise Exception(f"Cannot open {args.video}")
#     fps, out_w, out_h = cap.get(cv2.CAP_PROP_FPS), cfg.ori_img_w, cfg.ori_img_h

#     out_writer = None
#     if args.savedir:
#         os.makedirs(args.savedir, exist_ok=True)
#         out_path = os.path.join(args.savedir, f"{Path(args.video).stem}_output.mp4")
#         out_writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (out_w, out_h))
#         print(f"Saving to: {out_path}")

#     total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#     skip = max(1, args.skip_frame)
#     frame_idx = 0

#     for _ in tqdm(range(total), desc=f"Video {Path(args.video).name}"):
#         ret, frame = cap.read()
#         if not ret: break
#         if frame_idx % skip != 0:
#             frame_idx += 1
#             continue
#         frame_idx += 1

#         vis = det.run_on_frame(frame)
#         if args.show:
#             cv2.imshow('Lane Detection', vis)
#             if cv2.waitKey(1) & 0xFF == ord('q'): break
#         if out_writer: out_writer.write(vis)

#     cap.release()
#     if out_writer: out_writer.release()
#     cv2.destroyAllWindows()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('config')
    ap.add_argument('--img', help='Path to image or folder')
    ap.add_argument('--video', help='Path to video file')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--savedir')
    ap.add_argument('--load_from', default='best.pth')
    ap.add_argument('--skip_frame', type=int, default=1,
                    help='Process one in every N frames (default: 1 = all frames)')
    a = ap.parse_args()

    cfg = Config.fromfile(a.config)
    cfg.show, cfg.savedir, cfg.load_from = a.show, a.savedir, a.load_from

    if a.video: process_video(a, cfg)
    elif a.img: process_image(a, cfg)
    else: ap.print_help()
