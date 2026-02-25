import json
import pickle
import logging
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from sqlmodel import Session, select

from ..models.calibration import UserCalibration
from ..core.config import UPLOAD_DIR

logger = logging.getLogger(__name__)

# Mirrors combined_analysis/src/config.py CLASS_NAMES — kept local to avoid cross-package imports
CLASS_NAMES = {0: 'Left Mirror', 1: 'Right Mirror', 2: 'Looking Ahead', 3: 'Rear Mirror'}
LABEL_TO_IDX = {v: k for k, v in CLASS_NAMES.items()}
MIN_SAMPLES_PER_CLASS = 3

# Large storage fallback path (same as used in job_service.py)
LARGE_STORAGE = Path("/dcs/large/safedrive_cs310_2526/uploads")


def get_user_model_dir(user_id: str, cal_id: str) -> Path:
    """Returns the path to a specific calibration model directory."""
    return UPLOAD_DIR / "calibrations" / user_id / cal_id


def has_trained_model(user_id: str, cal_id: str) -> bool:
    """Returns True if both pkl files exist on disk for this calibration."""
    model_dir = get_user_model_dir(user_id, cal_id)
    return (
        (model_dir / "svm_head_pose_model.pkl").exists() and
        (model_dir / "pca_head_pose_model.pkl").exists()
    )


def list_calibrations(user_id: str, session: Session) -> List[UserCalibration]:
    """Returns all calibrations for a given user."""
    statement = select(UserCalibration).where(UserCalibration.user_id == user_id).order_by(UserCalibration.created_at.desc())
    return session.exec(statement).all()


def get_calibration(cal_id: str, user_id: str, session: Session) -> Optional[UserCalibration]:
    """Fetches a specific calibration, ensuring it belongs to the user."""
    cal = session.get(UserCalibration, cal_id)
    if cal and cal.user_id == user_id:
        return cal
    return None


def get_calibration_by_id(cal_id: str, session: Session) -> Optional[UserCalibration]:
    """Fetches a specific calibration by ID, regardless of user (internal helper)."""
    return session.get(UserCalibration, cal_id)


def create_calibration(user_id: str, session: Session, name: Optional[str] = None) -> UserCalibration:
    """Creates a new calibration entry for the user."""
    if not name:
        # Generate a default name like "Calibration 1", "Calibration 2"
        existing_count = len(list_calibrations(user_id, session))
        name = f"Calibration {existing_count + 1}"
    
    cal = UserCalibration(user_id=user_id, name=name)
    session.add(cal)
    session.commit()
    session.refresh(cal)
    return cal


def delete_calibration(cal_id: str, user_id: str, session: Session) -> bool:
    """Deletes a calibration and its associated files."""
    cal = get_calibration(cal_id, user_id, session)
    if not cal:
        return False
    
    # Delete from DB
    session.delete(cal)
    session.commit()
    
    # Delete files
    model_dir = get_user_model_dir(user_id, cal_id)
    if model_dir.exists():
        shutil.rmtree(model_dir)
    
    return True


def rename_calibration(cal_id: str, user_id: str, new_name: str, session: Session) -> Optional[UserCalibration]:
    """Renames an existing calibration."""
    cal = get_calibration(cal_id, user_id, session)
    if not cal:
        return None
    
    cal.name = new_name
    cal.updated_at = datetime.utcnow()
    session.add(cal)
    session.commit()
    session.refresh(cal)
    return cal


def get_status(cal_id: str, user_id: str, session: Session) -> dict:
    """Returns calibration status and per-class sample counts."""
    cal = get_calibration(cal_id, user_id, session)
    if not cal:
        return {"error": "Calibration not found"}
        
    samples = json.loads(cal.training_data) if cal.training_data else []

    counts = {name: 0 for name in CLASS_NAMES.values()}
    for s in samples:
        label = s.get("label")
        if label in counts:
            counts[label] += 1

    return {
        "id": cal.id,
        "name": cal.name,
        "has_calibration": cal.is_trained,
        "is_trained": cal.is_trained,
        "sample_counts": counts,
        "total_samples": len(samples),
        "created_at": cal.created_at,
        "updated_at": cal.updated_at,
    }


def _resolve_results_path(job_id: str) -> Optional[Path]:
    """Finds results.json for a job, checking both storage locations."""
    for base in [UPLOAD_DIR, LARGE_STORAGE]:
        path = base / job_id / "results.json"
        if path.exists():
            return path
    return None


def extract_pose_from_job(
    job_id: str,
    segments: list,  # list of {start_time: float, end_time: float, label: str}
    session: Session,
) -> list:
    """
    Reads results.json for job_id and extracts yaw/pitch/roll values for
    frames that fall within each segment's time window.

    Returns a list of {yaw, pitch, roll, label} dicts ready for training.
    """
    result_path = _resolve_results_path(job_id)
    if not result_path:
        raise FileNotFoundError(f"results.json not found for job {job_id}")

    with open(result_path, "r") as f:
        results = json.load(f)

    frame_data = results.get("frame_data", [])
    extracted = []

    for seg in segments:
        start = float(seg["start_time"])
        end = float(seg["end_time"])
        label = seg["label"]

        if label not in LABEL_TO_IDX:
            logger.warning(f"Skipping unknown label '{label}'")
            continue

        for frame in frame_data:
            t = frame.get("time", -1)
            if start <= t <= end:
                fi = frame.get("face_info")
                if fi and fi.get("yaw") is not None:
                    extracted.append({
                        "yaw": int(fi["yaw"]),
                        "pitch": int(fi["pitch"]),
                        "roll": int(fi["roll"]),
                        "label": label,
                    })

    return extracted


def add_samples(cal_id: str, user_id: str, new_samples: list, session: Session) -> dict:
    """Merges new_samples into the user's existing training data. Returns updated status."""
    cal = get_calibration(cal_id, user_id, session)
    if not cal:
        return {"error": "Calibration not found"}
        
    existing = json.loads(cal.training_data) if cal.training_data else []
    combined = existing + new_samples
    cal.training_data = json.dumps(combined)
    cal.updated_at = datetime.utcnow()
    session.add(cal)
    session.commit()
    session.refresh(cal)
    return get_status(cal_id, user_id, session)


def get_samples(cal_id: str, user_id: str, session: Session) -> list:
    """Returns the raw stored training samples [{yaw, pitch, roll, label}]."""
    cal = get_calibration(cal_id, user_id, session)
    if not cal:
        return []
    return json.loads(cal.training_data) if cal.training_data else []


def reset_samples(cal_id: str, user_id: str, session: Session) -> None:
    """Clears all training samples and marks model as untrained."""
    cal = get_calibration(cal_id, user_id, session)
    if not cal:
        return
    cal.training_data = None
    cal.is_trained = False
    cal.updated_at = datetime.utcnow()
    session.add(cal)
    session.commit()


# Colours matching frontend GAZE_STATES (videoConstants.js)
_CLASS_COLORS = {
    'Left Mirror':   '#6f42c1',
    'Right Mirror':  '#0ffc10',
    'Looking Ahead': '#20c997',
    'Rear Mirror':   '#ffc107',
}


def _generate_plots(X, X_pca, y, samples, pca, svm, model_dir: Path) -> dict:
    """
    Generates 3 dark-themed diagnostic PNGs.
    """
    try:
        import io, base64 as b64lib
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
    except Exception as exc:
        logger.warning(f"Plot generation skipped: {exc}")
        return {}

    DARK_BG   = '#111827'
    PANEL_BG  = '#1f2937'
    MUTED     = '#9ca3af'
    BORDER    = '#374151'
    LEG_BG    = '#1f2937'
    LEG_FG    = '#d1d5db'

    def _style(ax, fig):
        fig.patch.set_facecolor(DARK_BG)
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)
        ax.title.set_color('#f9fafb')
        for sp in ax.spines.values():
            sp.set_edgecolor(BORDER)
        ax.grid(True, alpha=0.12, color='#6b7280')

    def _to_b64(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=110,
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        data = b64lib.b64encode(buf.read()).decode()
        plt.close(fig)
        return f"data:image/png;base64,{data}"

    def _scatter_by_class(ax, data, labels_list, label_col=None):
        seen = list(dict.fromkeys(s['label'] for s in samples))
        for lbl in seen:
            idxs = [i for i, s in enumerate(samples) if s['label'] == lbl]
            xs = data[idxs, 0]
            ys = data[idxs, 1]
            ax.scatter(xs, ys, c=_CLASS_COLORS.get(lbl, '#888'),
                       label=lbl, alpha=0.75, edgecolors='white',
                       linewidths=0.4, s=42)

    ev = pca.explained_variance_ratio_
    plots = {}

    # ── Plot 1: Yaw vs Pitch ──────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    _style(ax, fig)
    _scatter_by_class(ax, X, samples)
    ax.set_xlabel('Yaw (°)')
    ax.set_ylabel('Pitch (°)')
    ax.set_title('Head Pose: Yaw vs Pitch', fontweight='bold')
    ax.legend(facecolor=LEG_BG, edgecolor=BORDER, labelcolor=LEG_FG, fontsize=8)
    plots['head_pose'] = _to_b64(fig)

    # ── Plot 2: PCA scatter ───────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    _style(ax, fig)
    _scatter_by_class(ax, X_pca, samples)
    ax.set_xlabel(f'PC1 ({ev[0]*100:.1f}% var.)')
    ax.set_ylabel(f'PC2 ({ev[1]*100:.1f}% var.)')
    ax.set_title('PCA of Head Pose Data', fontweight='bold')
    ax.legend(facecolor=LEG_BG, edgecolor=BORDER, labelcolor=LEG_FG, fontsize=8)
    plots['pca'] = _to_b64(fig)

    # ── Plot 3: SVM Decision Boundary ────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    _style(ax, fig)

    xr = X_pca[:, 0].max() - X_pca[:, 0].min()
    yr = X_pca[:, 1].max() - X_pca[:, 1].min()
    margin = max(1.0, (xr + yr) * 0.1)
    x_min, x_max = X_pca[:, 0].min() - margin, X_pca[:, 0].max() + margin
    y_min, y_max = X_pca[:, 1].min() - margin, X_pca[:, 1].max() + margin
    h = max(0.04, (x_max - x_min) / 250)
    xx, yy = np.meshgrid(np.arange(x_min, x_max, h), np.arange(y_min, y_max, h))
    Z = svm.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

    all_idxs = sorted(set(y))
    cmap = ListedColormap([_CLASS_COLORS.get(CLASS_NAMES.get(i, ''), '#888') for i in all_idxs])
    idx_map = {v: i for i, v in enumerate(all_idxs)}
    Z_mapped = np.vectorize(idx_map.get)(Z)
    ax.pcolormesh(xx, yy, Z_mapped, cmap=cmap, alpha=0.22, shading='auto')
    ax.contour(xx, yy, Z, colors='white', linewidths=0.5, linestyles='--', alpha=0.35)

    _scatter_by_class(ax, X_pca, samples)
    ax.set_xlabel(f'PC1 ({ev[0]*100:.1f}% var.)')
    ax.set_ylabel(f'PC2 ({ev[1]*100:.1f}% var.)')
    ax.set_title('SVM Decision Boundary', fontweight='bold')
    ax.legend(facecolor=LEG_BG, edgecolor=BORDER, labelcolor=LEG_FG, fontsize=8)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    plots['decision_boundary'] = _to_b64(fig)

    # Persist PNGs alongside model files
    import base64 as b64lib2
    model_dir.mkdir(parents=True, exist_ok=True)
    for key, data_url in plots.items():
        png_bytes = b64lib2.b64decode(data_url.split(',', 1)[1])
        with open(model_dir / f"plot_{key}.png", 'wb') as f:
            f.write(png_bytes)

    return plots


def get_saved_plots_b64(cal_id: str, user_id: str) -> dict:
    """Loads plot PNGs saved by the last training run and returns them as data URLs."""
    import base64
    model_dir = get_user_model_dir(user_id, cal_id)
    plots = {}
    for key in ('head_pose', 'pca', 'decision_boundary'):
        path = model_dir / f"plot_{key}.png"
        if path.exists():
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            plots[key] = f"data:image/png;base64,{b64}"
    return plots


def train_user_model(cal_id: str, user_id: str, session: Session) -> dict:
    """
    Trains a PCA + SVC model from a specific calibration's samples.
    """
    try:
        import numpy as np
        from sklearn.decomposition import PCA
        from sklearn.svm import SVC
    except ImportError as e:
        return {"success": False, "message": f"Missing dependency: {e}"}

    cal = get_calibration(cal_id, user_id, session)
    if not cal:
        return {"success": False, "message": "Calibration not found"}
        
    samples = json.loads(cal.training_data) if cal.training_data else []

    if not samples:
        return {"success": False, "message": "No training samples found."}

    # Validate minimum samples per class
    counts: dict = {}
    for s in samples:
        counts[s["label"]] = counts.get(s["label"], 0) + 1

    MANDATORY_LABELS = {'Left Mirror', 'Right Mirror', 'Looking Ahead'}
    missing = []
    for label in MANDATORY_LABELS:
        if counts.get(label, 0) < MIN_SAMPLES_PER_CLASS:
            missing.append(f"'{label}' ({counts.get(label, 0)}/{MIN_SAMPLES_PER_CLASS})")
    if missing:
        return {
            "success": False,
            "message": f"Not enough samples: {', '.join(missing)}.",
        }

    # Build feature matrix
    X = np.array([[s["yaw"], s["pitch"], s["roll"]] for s in samples], dtype=float)
    y = [LABEL_TO_IDX[s["label"]] for s in samples]

    # Train
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X)

    svm = SVC(kernel="rbf", C=10, probability=True)
    svm.fit(X_pca, y)

    # Persist models
    model_dir = get_user_model_dir(user_id, cal_id)
    model_dir.mkdir(parents=True, exist_ok=True)

    with open(model_dir / "pca_head_pose_model.pkl", "wb") as f:
        pickle.dump(pca, f)
    with open(model_dir / "svm_head_pose_model.pkl", "wb") as f:
        pickle.dump(svm, f)

    # Save audit copy of training data
    with open(model_dir / "training_data.json", "w") as f:
        json.dump(samples, f)

    # Update DB record
    cal.is_trained = True
    cal.updated_at = datetime.utcnow()
    session.add(cal)
    session.commit()

    # Generate diagnostic plots (non-fatal if matplotlib unavailable)
    plots = _generate_plots(X, X_pca, y, samples, pca, svm, model_dir)

    logger.info(f"Trained calibration model {cal_id} for user {user_id} with {len(samples)} samples.")
    return {
        "success": True,
        "message": f"Model trained on {len(samples)} samples across {len(counts)} classes.",
        "plots": plots,
    }
