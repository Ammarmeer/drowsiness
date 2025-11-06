import os
import cv2
import torch
from ultralytics import YOLO
from ultralytics.nn.tasks import DetectionModel

# ✅ ADD THIS FIX (required in PyTorch ≥ 2.6)
torch.serialization.add_safe_globals({'ultralytics.nn.tasks.DetectionModel': DetectionModel})

# ✅ Model path (your .pt file from Ultralytics)
model_path = "D:/Drowsiness Detection/Driver-Drowsines-Detection-FYP-main/Driver-Drowsines-Detection-FYP-main/best.pt"

# ✅ Load YOLOv8 model
model = YOLO(model_path)

def process_image(image_path):
    if not os.path.exists(image_path):
        print(f"[❌] Image not found: {image_path}")
        return

    image = cv2.imread(image_path)
    results = model(image)
    annotated = results[0].plot()

    output_path = "output_" + os.path.basename(image_path)
    cv2.imwrite(output_path, annotated)

    cv2.imshow("Drowsiness Detection - Image", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    print(f"[✅] Output saved: {output_path}")

def process_video(video_path):
    if not os.path.exists(video_path):
        print(f"[❌] Video not found: {video_path}")
        return

    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    output_path = "output_" + os.path.basename(video_path)

    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    print("[ℹ️] Processing video. Press 'q' to exit early.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame)
        annotated = results[0].plot()

        out.write(annotated)
        cv2.imshow("Drowsiness Detection - Video", annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"[✅] Output saved: {output_path}")

if __name__ == "__main__":
    file_path = input("Enter image or video path: ").strip().strip('"')
    ext = os.path.splitext(file_path)[1].lower()

    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
        process_image(file_path)
    elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
        process_video(file_path)
    else:
        print("[❌] Unsupported file format.")
