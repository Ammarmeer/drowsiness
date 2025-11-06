# routes/drowsiness.py
import os, cv2, torch, threading, numpy as np, anyio, time, logging
from typing import List, Dict, Tuple
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from ultralytics import YOLO
from ultralytics.nn.tasks import DetectionModel
import requests  # <-- new

# ====== CONFIG ======
MODEL_PATH = r"models/best.pt"
OUTPUT_DIR = r"outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

templates = Jinja2Templates(directory="templates")
log = logging.getLogger("drowsiness")
log.setLevel(logging.INFO)

# ====== TORCH SAFE GLOBALS ======
torch.serialization.add_safe_globals({'ultralytics.nn.tasks.DetectionModel': DetectionModel})

# ====== LOAD MODEL ======
try:
    model = YOLO(MODEL_PATH)
    if torch.cuda.is_available():
        model.to("cuda")
except Exception as e:
    raise RuntimeError(f"Failed to load YOLO model from {MODEL_PATH}: {e}")

_model_lock = threading.Lock()
router = APIRouter(prefix="/drowsiness", tags=["drowsiness"])

# ---------- helpers ----------

# ---- ESP32 ALERT CONFIG ----
ESP32_IP = os.getenv("ESP32_IP", "http://192.168.1.20/")  # apna ESP32 IP yahan set ya env var se do
ESP32_ALERT_LEVEL = os.getenv("ESP32_ALERT_LEVEL", "crit")  # "warn" ya "crit"
ALERT_COOLDOWN_S = float(os.getenv("ESP32_ALERT_COOLDOWN", "2.0"))

_last_alert_ts = 0.0

def _trigger_esp32(level: str = ESP32_ALERT_LEVEL):
    try:
        r = requests.get(f"{ESP32_IP}/alert", params={"level": level}, timeout=1.5)
        log.info("ESP32 alert %s -> %s", level, (r.text or r.status_code))
    except Exception as e:
        log.warning("ESP32 trigger failed: %s", e)

def _maybe_resize(frame: np.ndarray, max_side: int = 640) -> Tuple[np.ndarray, float, float]:
    h, w = frame.shape[:2]
    scale = 1.0
    if max(h, w) > max_side:
        scale = max_side / float(max(h, w))
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized, scale, scale
    return frame, 1.0, 1.0

def _annotate_frame(frame: np.ndarray) -> np.ndarray:
    # lightweight annotate for saved images/videos
    with _model_lock, torch.inference_mode():
        results = model(frame)
    return results[0].plot()

def _detect_labels_and_boxes(frame: np.ndarray) -> Dict:
    """Return labels, boxes, confidences, and drowsy flag for a single frame (blocking)."""
    # Downscale for speed, then scale boxes back
    h0, w0 = frame.shape[:2]
    fr, sx, sy = _maybe_resize(frame, 640)
    with _model_lock, torch.inference_mode():
        results = model(fr)
    r = results[0]
    names = r.names

    if r.boxes is None or r.boxes.cls is None:
        return {"labels": [], "boxes": [], "confs": [], "drowsy": False}

    cls = r.boxes.cls.tolist()
    conf = r.boxes.conf.tolist() if r.boxes.conf is not None else [0.0]*len(cls)
    xyxy = r.boxes.xyxy.cpu().numpy().tolist()

    # scale boxes back to original canvas size if we resized
    if sx != 1.0 or sy != 1.0:
        inv = 1.0 / sx
        for b in xyxy:
            b[0] *= inv; b[1] *= inv; b[2] *= inv; b[3] *= inv

    labels: List[str] = [names[int(c)] for c in cls]
    text = " ".join(labels).lower()
    drowsy_keywords = ("drowsy", "sleep", "asleep", "closed", "yawn", "tired")
    is_drowsy = any(k in text for k in drowsy_keywords)

    # ---- NEW: trigger ESP32 with simple cooldown ----
    if is_drowsy:
        global _last_alert_ts
        now = time.time()
        if (now - _last_alert_ts) >= ALERT_COOLDOWN_S:
            _trigger_esp32(ESP32_ALERT_LEVEL)
            _last_alert_ts = now

    return {"labels": labels, "boxes": xyxy, "confs": conf, "drowsy": is_drowsy}

def _hash_bytes(b: bytes) -> str:
    import hashlib
    return hashlib.sha1(b).hexdigest()[:10]

def _read_all(upload: UploadFile) -> bytes:
    data = upload.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    return data

def _decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image.")
    return img

def _safe_fps(cap: cv2.VideoCapture) -> float:
    fps = cap.get(cv2.CAP_PROP_FPS)
    return fps if fps and fps > 0 else 30.0

# ---------- pages ----------
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("drowsiness_dashboard.html", {"request": request})

@router.get("/dashboard-live", response_class=HTMLResponse)
def dashboard_live(request: Request):
    return templates.TemplateResponse("drowsiness_live.html", {"request": request})

# ---------- api ----------
@router.get("/health")
def health():
    return {"status": "ok",
            "torch": torch.__version__,
            "cuda_version": torch.version.cuda,
            "cuda_available": torch.cuda.is_available()}

@router.post("/image-json")
def detect_image_json(file: UploadFile = File(...)):
    data = _read_all(file)
    img = _decode_image(data)
    det = _detect_labels_and_boxes(img)
    annotated = _annotate_frame(img)
    base = os.path.basename(file.filename or "image.jpg")
    if not os.path.splitext(base)[1]:
        base += ".jpg"
    out_name = f"output_{_hash_bytes(data)}_{base}"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    cv2.imwrite(out_path, annotated)
    det["annotated_url"] = f"/drowsiness/file/{out_name}"
    return JSONResponse(det)

@router.get("/file/{name}")
def get_output_file(name: str):
    path = os.path.join(OUTPUT_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found.")
    ext = os.path.splitext(name)[1].lower()
    mt = "image/jpeg" if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp") else "video/mp4"
    return FileResponse(path, media_type=mt, filename=name)

@router.post("/video")
def detect_video(file: UploadFile = File(...)):
    raw = _read_all(file)
    in_ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    stem = f"upload_{_hash_bytes(raw)}"
    in_path = os.path.join(OUTPUT_DIR, f"{stem}{in_ext}")
    with open(in_path, "wb") as f:
        f.write(raw)

    cap = cv2.VideoCapture(in_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not open uploaded video.")

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps    = _safe_fps(cap)
    out_name = f"output_{stem}.mp4"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            annotated = _annotate_frame(frame)
            out.write(annotated)
    finally:
        cap.release()
        out.release()

    return FileResponse(out_path, media_type="video/mp4", filename=out_name)

# ---------- LIVE WS (offload inference to a thread, drop if busy) ----------
@router.websocket("/ws")
async def ws_infer(websocket: WebSocket):
    await websocket.accept()
    log.info("WS connected")
    busy = False
    try:
        while True:
            data = await websocket.receive_bytes()
            arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                await websocket.send_json({"error": "decode_failed"})
                continue

            if busy:
                # drop frame if previous inference still running (keeps latency low)
                continue
            busy = True

            # run blocking YOLO in a worker thread
            try:
                det = await anyio.to_thread.run_sync(_detect_labels_and_boxes, frame)
            except Exception as e:
                det = {"error": str(e), "labels": [], "boxes": [], "confs": [], "drowsy": False}

            await websocket.send_json(det)
            busy = False
    except WebSocketDisconnect:
        log.info("WS disconnected")
    except Exception as e:
        log.exception("WS error: %s", e)
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
