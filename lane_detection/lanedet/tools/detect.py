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

def visualize_tracked_lanes(ori_img, lanes_coeffs, show=False, out_file=None):
    vis_img = ori_img.copy()
    y_points = np.linspace(2 * vis_img.shape[0] // 3, vis_img.shape[0] - 1, 100)
    
    for coeffs_data in lanes_coeffs:
        (a, b, c), id, misses = coeffs_data
        this_color = LANE_COLORS[id % len(LANE_COLORS)]

        x_points = a * y_points**2 + b * y_points + c
        points = np.vstack((x_points, y_points)).T
        points = points[(points[:, 0] >= 0) & (points[:, 0] < vis_img.shape[1])]

        cv2.polylines(vis_img, [points.astype(np.int32)], isClosed=False, color=this_color, thickness=2)
        
        if len(points) > 0:
            middle_idx = len(points) // 2
            text_x = int(points[middle_idx, 0])
            text_y = int(points[middle_idx, 1])
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            
            lane_text = f'lane: {id}'
            misses_text = f'misses: {misses}'
            
            (lane_width, lane_height), _ = cv2.getTextSize(lane_text, font, font_scale, thickness)
            (misses_width, misses_height), _ = cv2.getTextSize(misses_text, font, font_scale, thickness)
            
            max_width = max(lane_width, misses_width)
            padding = 5
            total_height = lane_height + misses_height + padding + 5
            
            rect_x1 = text_x - padding
            rect_y1 = text_y - total_height // 2
            rect_x2 = text_x + max_width + padding
            rect_y2 = text_y + total_height // 2
            
            overlay = vis_img.copy()
            cv2.rectangle(overlay, (rect_x1, rect_y1), (rect_x2, rect_y2), (0, 0, 0), -1)
            
            alpha = 0.6
            cv2.addWeighted(overlay, alpha, vis_img, 1 - alpha, 0, vis_img)
            
            lane_text_x = text_x
            lane_text_y = text_y - misses_height - 2
            misses_text_x = text_x
            misses_text_y = text_y + lane_height - 2
            
            cv2.putText(vis_img, lane_text, (lane_text_x, lane_text_y), 
                       font, font_scale, (255, 255, 255), thickness)
            cv2.putText(vis_img, misses_text, (misses_text_x, misses_text_y),
                       font, font_scale, (255, 255, 255), thickness)

    if show:
        cv2.imshow('Tracked Lanes', vis_img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return None # Signal to quit

    if out_file:
        cv2.imwrite(out_file, vis_img)
        
    return vis_img

def process_video(args, cfg):
    # This assumes 'Detect' is imported from another file
    det = Detect(cfg) 
    tracker = LaneTracker() 
    
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened(): 
        raise Exception(f"Cannot open {args.video}")
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    out_w = cfg.ori_img_w
    out_h = cfg.ori_img_h
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start_frame = max(0, int(args.start_seconds * fps))
    
    if args.end_seconds is not None:
        end_frame = min(total_frames, int(args.end_seconds * fps))
    else:
        end_frame = total_frames
        
    if start_frame >= end_frame:
        print(f"Error: Start time ({args.start_seconds}s) is after or at end time ({args.end_seconds}s).")
        cap.release()
        return

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    num_frames_to_process = end_frame - start_frame

    out_writer = None
    if args.savedir:
        os.makedirs(args.savedir, exist_ok=True)
        out_path = os.path.join(args.savedir, f"{Path(args.video).stem}_output.mp4")
        out_writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (out_w, out_h))
        print(f"Saving to: {out_path}")
    
    skip = max(1, args.skip_frame)
    frame_idx = start_frame 

    for _ in tqdm(range(num_frames_to_process), desc=f"Video {Path(args.video).name}"):
        ret, frame = cap.read()
        if not ret: 
            print("\nWarning: Video stream ended unexpectedly.")
            break
        
        if frame_idx % skip != 0:
            frame_idx += 1
            continue
        frame_idx += 1 

        detected_coeffs, ori_img = det.get_lane_detections(frame)
        filtered_lane_coeffs = tracker.update(detected_coeffs)
        vis = visualize_tracked_lanes(ori_img, filtered_lane_coeffs, show=args.show)
        
        if args.show and vis is None: # Quit signal
             print("\n'q' pressed, stopping.")
             break

        if out_writer: 
            out_writer.write(vis)

    print(f"\nFinished processing. Processed up to frame {frame_idx-1}.")
    cap.release()
    if out_writer: 
        out_writer.release()
        print("Output video saved.")
    cv2.destroyAllWindows()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Lane Detection and Tracking")
    ap.add_argument('config', help='Path to the config file')
    ap.add_argument('--img', help='Path to image or folder for image processing')
    ap.add_argument('--video', help='Path to video file for video processing')
    ap.add_argument('--show', action='store_true', help='Show processing window')
    ap.add_argument('--savedir', help='Directory to save output video')
    ap.add_argument('--load_from', default='best.pth', help='Path to load model weights from')
    ap.add_argument('--skip_frame', type=int, default=1,
                     help='Process one in every N frames (default: 1 = all frames)')
    ap.add_argument('--start_seconds', type=float, default=0.0,
                     help='Start processing time in seconds (default: 0.0)')
    ap.add_argument('--end_seconds', type=float, default=None,
                     help='End processing time in seconds (default: None = end of video)')
    
    a = ap.parse_args()

    # Assumes Config class is imported or defined elsewhere
    cfg = Config.fromfile(a.config)
    cfg.show, cfg.savedir, cfg.load_from = a.show, a.savedir, a.load_from

    # This assumes 'process_image' and 'Detect' are defined elsewhere
    if a.video: 
        process_video(a, cfg) 
    elif a.img: 
        # process_image(a, cfg) 
        print("Image processing not implemented in this snippet.")
    else: 
        print("No video or image path provided. Use --video or --img.")
        ap.print_help()