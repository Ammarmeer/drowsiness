from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import numpy as np
import cv2
import tempfile
import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import hashlib
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load YOLO model
try:
    model = YOLO("models/best.pt")
    logger.info("YOLO model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load YOLO model: {e}")
    model = None

app = FastAPI(title="DrowsyGuard API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing functions
def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    try:
        salt, password_hash = hashed.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
    except:
        return False

# Database setup
def init_db():
    conn = sqlite3.connect('drowsiness.db')
    cursor = conn.cursor()
    
    # Updated users table with password field
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        total_detections INTEGER DEFAULT 0,
        drowsy_detections INTEGER DEFAULT 0,
        distance_km REAL DEFAULT 0.0,
        start_lat REAL,
        start_lng REAL,
        end_lat REAL,
        end_lng REAL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        prediction TEXT,
        confidence REAL,
        latitude REAL,
        longitude REAL,
        FOREIGN KEY (session_id) REFERENCES sessions (id)
    )
    ''')
    
    # Check if password_hash column exists, if not add it
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'password_hash' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
        # Set default password for existing users (you should prompt them to change it)
        cursor.execute('UPDATE users SET password_hash = ? WHERE password_hash IS NULL', 
                      (hash_password('defaultpassword123'),))
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Updated Pydantic models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class SessionStart(BaseModel):
    user_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class SessionEnd(BaseModel):
    distance_km: Optional[float] = 0.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class DetectionLog(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None

def get_db_connection():
    return sqlite3.connect('drowsiness.db')

def infer_image(img_bgr: np.ndarray) -> Dict[str, Any]:
    """Run YOLOv8 on a BGR image and return prediction."""
    if model is None:
        return {"prediction": "model_error", "confidence": 0.0}
    
    try:
        results = model(img_bgr)
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return {"prediction": "no_detection", "confidence": 0.0}

        confs = results[0].boxes.conf.cpu().numpy()
        clss = results[0].boxes.cls.cpu().numpy().astype(int)
        top_idx = int(np.argmax(confs))
        label = results[0].names[clss[top_idx]]
        conf = float(confs[top_idx])
        
        return {"prediction": label, "confidence": round(conf, 4)}
    except Exception as e:
        logger.error(f"Inference error: {e}")
        return {"prediction": "error", "confidence": 0.0}

@app.get("/")
async def root():
    return {"message": "DrowsyGuard API", "status": "running"}

@app.post("/users/register")
async def register_user(user: UserCreate):
    """Register a new user with password"""
    try:
        # Hash the password
        password_hash = hash_password(user.password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, phone) VALUES (?, ?, ?, ?)",
            (user.username, user.email, password_hash, user.phone)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"success": True, "user_id": user_id, "message": "User registered successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/users/login")
async def login_user(login_data: UserLogin):
    """Login with username and password"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, phone, password_hash FROM users WHERE username = ?",
            (login_data.username,)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user and verify_password(login_data.password, user[4]):
            return {
                "success": True,
                "user": {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "phone": user[3]
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid username or password")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# Legacy login endpoint for backward compatibility
@app.post("/users/login_legacy")
async def login_user_legacy(username: str, email: str):
    """Legacy login - just check if user exists (for backward compatibility)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, phone FROM users WHERE username = ? AND email = ?",
            (username, email)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                "success": True,
                "user": {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "phone": user[3]
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.post("/sessions/start")
async def start_session(session_data: SessionStart):
    """Start a new detection session"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (user_id, start_time, start_lat, start_lng) VALUES (?, ?, ?, ?)",
            (session_data.user_id, datetime.now(), session_data.latitude, session_data.longitude)
        )
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"success": True, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@app.post("/sessions/{session_id}/end")
async def end_session(session_id: int):
    """End a detection session"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET end_time = ? WHERE id = ?",
            (datetime.now(), session_id)
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")
            
        conn.commit()
        conn.close()
        return {"success": True, "message": "Session ended successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end session: {str(e)}")

@app.post("/detect/{session_id}")
async def detect_drowsiness(
    session_id: int,
    file: UploadFile = File(...),
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
):
    """Detect drowsiness from uploaded frame"""
    try:
        # Process image
        data = await file.read()
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "message": "Invalid image"}
        
        # Get prediction
        result = infer_image(img)
        
        # Check if drowsy (customize based on your model's labels)
        is_drowsy = result["prediction"].lower() in ['drowsy', 'sleepy', 'tired'] and result["confidence"] > 0.7
        
        # Log detection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO detections (session_id, prediction, confidence, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            (session_id, result["prediction"], result["confidence"], latitude, longitude)
        )
        
        # Update session stats
        cursor.execute(
            "UPDATE sessions SET total_detections = total_detections + 1, drowsy_detections = drowsy_detections + ? WHERE id = ?",
            (1 if is_drowsy else 0, session_id)
        )
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "data": {
                "prediction": result["prediction"],
                "confidence": result["confidence"],
                "is_drowsy": is_drowsy,
                "alert_level": "high" if is_drowsy and result["confidence"] > 0.8 else "low"
            }
        }
        
    except Exception as e:
        logger.error(f"Detection error: {e}")
        return {"success": False, "message": f"Detection failed: {str(e)}"}

@app.get("/users/{user_id}/dashboard")
async def get_dashboard(user_id: int):
    """Get user dashboard data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(drowsy_detections) as total_drowsy,
                SUM(total_detections) as total_detections
            FROM sessions 
            WHERE user_id = ? AND end_time IS NOT NULL
        """, (user_id,))
        
        stats = cursor.fetchone()
        
        # Get recent sessions with more details
        cursor.execute("""
            SELECT 
                s.id, 
                s.start_time, 
                s.end_time, 
                s.drowsy_detections, 
                s.total_detections,
                COUNT(d.id) as detection_count
            FROM sessions s 
            LEFT JOIN detections d ON s.id = d.session_id
            WHERE s.user_id = ? AND s.end_time IS NOT NULL
            GROUP BY s.id
            ORDER BY s.start_time DESC 
            LIMIT 10
        """, (user_id,))
        
        recent_sessions = cursor.fetchall()
        
        # Calculate safety score
        total_detections = stats[2] if stats[2] else 0
        total_drowsy = stats[1] if stats[1] else 0
        
        if total_detections > 0:
            drowsy_percentage = (total_drowsy / total_detections) * 100
            safety_score = max(0, 100 - (drowsy_percentage * 2))  # More sensitive scoring
        else:
            safety_score = 100
        
        # Get session duration average
        cursor.execute("""
            SELECT AVG(
                CASE 
                    WHEN end_time IS NOT NULL AND start_time IS NOT NULL 
                    THEN (julianday(end_time) - julianday(start_time)) * 24 * 60 
                    ELSE 0 
                END
            ) as avg_duration_minutes
            FROM sessions 
            WHERE user_id = ? AND end_time IS NOT NULL
        """, (user_id,))
        
        avg_duration = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "total_sessions": stats[0] or 0,
                "total_alerts": total_drowsy,
                "total_detections": total_detections,
                "safety_score": round(safety_score, 1),
                "avg_session_duration": round(avg_duration, 1),
                "recent_sessions": [
                    {
                        "id": session[0],
                        "start_time": session[1],
                        "end_time": session[2],
                        "alerts": session[3] or 0,
                        "total_detections": session[4] or 0,
                        "detection_count": session[5] or 0,
                        "duration_minutes": _calculate_duration(session[1], session[2])
                    }
                    for session in recent_sessions
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")

def _calculate_duration(start_time: str, end_time: str) -> float:
    """Calculate session duration in minutes"""
    try:
        if not start_time or not end_time:
            return 0
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration = (end - start).total_seconds() / 60
        return round(duration, 1)
    except:
        return 0
    
@app.post("/predict_frame")
async def predict_frame_simple(file: UploadFile = File(...)):
    """Simple frame prediction without session tracking"""
    try:
        data = await file.read()
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "message": "Invalid image"}
        
        result = infer_image(img)
        return {"success": True, "data": result}
        
    except Exception as e:
        print(f"Frame prediction error: {e}")
        return {"success": False, "message": f"Prediction failed: {str(e)}"}

@app.post("/predict_image")
async def predict_image(file: UploadFile = File(...)):
    """Single image prediction endpoint"""
    try:
        data = await file.read()
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "message": "Invalid image"}
        
        result = infer_image(img)
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Image prediction error: {e}")
        return {"success": False, "message": f"Prediction failed: {str(e)}"}

@app.get("/sessions/{session_id}/details")
async def get_session_details(session_id: int):
    """Get detailed session information"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        cursor.execute(
            "SELECT timestamp, prediction, confidence, latitude, longitude FROM detections WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )
        detections = cursor.fetchall()
        conn.close()
        
        return {
            "success": True,
            "data": {
                "session": {
                    "id": session[0],
                    "start_time": session[2],
                    "end_time": session[3],
                    "distance": session[6],
                    "total_detections": session[4],
                    "drowsy_detections": session[5]
                },
                "detections": [
                    {
                        "timestamp": det[0],
                        "prediction": det[1],
                        "confidence": det[2],
                        "location": {"lat": det[3], "lng": det[4]} if det[3] and det[4] else None
                    }
                    for det in detections
                ]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session details: {str(e)}")

# Password reset endpoint (bonus feature)
@app.post("/users/reset-password")
async def reset_password(username: str, new_password: str):
    """Reset user password (simplified version)"""
    try:
        password_hash = hash_password(new_password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username)
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        conn.commit()
        conn.close()
        return {"success": True, "message": "Password reset successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password reset failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)