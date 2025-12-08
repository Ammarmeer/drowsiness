from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import numpy as np
import cv2
import tempfile
import os
import sqlite3
from datetime import datetime, timedelta
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
    
    # Updated users table with role field
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        role TEXT DEFAULT 'driver',
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
    
    # Check if role column exists, if not add it
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'role' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "driver"')
    
    # Create default admin if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        admin_password = hash_password('admin123')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ('admin', 'admin@drowsyguard.com', admin_password, 'admin')
        )
        logger.info("Default admin created: username=admin, password=admin123")
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    phone: Optional[str] = None
    role: Optional[str] = 'driver'

class UserLogin(BaseModel):
    username: str
    password: str
    role: Optional[str] = None

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
        # Only allow driver registration through this endpoint
        if user.role and user.role != 'driver':
            raise HTTPException(status_code=403, detail="Only driver registration allowed")
        
        password_hash = hash_password(user.password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, phone, role) VALUES (?, ?, ?, ?, ?)",
            (user.username, user.email, password_hash, user.phone, 'driver')
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
            "SELECT id, username, email, phone, password_hash, role FROM users WHERE username = ?",
            (login_data.username,)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user and verify_password(login_data.password, user[4]):
            # Check role if specified
            user_role = user[5]
            if login_data.role and user_role != login_data.role:
                raise HTTPException(status_code=403, detail="Invalid role for this account")
            
            return {
                "success": True,
                "user": {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "phone": user[3],
                    "role": user_role
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid username or password")
    except HTTPException:
        raise
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
        
        # Check if drowsy
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
        
        # Get recent sessions
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
            safety_score = max(0, 100 - (drowsy_percentage * 2))
        else:
            safety_score = 100
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "total_sessions": stats[0] or 0,
                "total_alerts": total_drowsy,
                "total_detections": total_detections,
                "safety_score": round(safety_score, 1),
                "recent_sessions": [
                    {
                        "id": session[0],
                        "start_time": session[1],
                        "end_time": session[2],
                        "alerts": session[3] or 0,
                        "total_detections": session[4] or 0,
                        "detection_count": session[5] or 0,
                    }
                    for session in recent_sessions
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")

@app.get("/admin/dashboard")
async def get_admin_dashboard():
    """Get admin dashboard with all drivers' data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total drivers
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'driver'")
        total_drivers = cursor.fetchone()[0]
        
        # Get active sessions (sessions without end_time)
        cursor.execute("""
            SELECT 
                s.id as session_id,
                s.user_id,
                u.username,
                s.start_time,
                s.total_detections,
                s.drowsy_detections,
                (
                    SELECT d.prediction 
                    FROM detections d 
                    WHERE d.session_id = s.id 
                    ORDER BY d.timestamp DESC 
                    LIMIT 1
                ) as latest_prediction
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.end_time IS NULL
            ORDER BY s.start_time DESC
        """)
        active_sessions = cursor.fetchall()
        
        # Count drowsy drivers (active sessions with recent drowsy detection)
        drowsy_count = 0
        active_sessions_list = []
        
        for session in active_sessions:
            latest_prediction = session[6]
            is_drowsy = latest_prediction and 'drowsy' in latest_prediction.lower()
            
            if is_drowsy:
                drowsy_count += 1
            
            active_sessions_list.append({
                "session_id": session[0],
                "user_id": session[1],
                "username": session[2],
                "start_time": session[3],
                "total_detections": session[4] or 0,
                "alerts": session[5] or 0,
                "latest_drowsy": is_drowsy
            })
        
        # Get total sessions count
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE end_time IS NOT NULL")
        total_sessions = cursor.fetchone()[0]
        
        # Get recent detection logs (last 50)
        cursor.execute("""
            SELECT 
                d.id,
                d.session_id,
                d.timestamp,
                d.prediction,
                d.confidence,
                u.username
            FROM detections d
            JOIN sessions s ON d.session_id = s.id
            JOIN users u ON s.user_id = u.id
            ORDER BY d.timestamp DESC
            LIMIT 50
        """)
        recent_logs = cursor.fetchall()
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "total_drivers": total_drivers,
                "active_drivers": len(active_sessions),
                "drowsy_drivers": drowsy_count,
                "total_sessions": total_sessions,
                "active_sessions": active_sessions_list,
                "recent_logs": [
                    {
                        "id": log[0],
                        "session_id": log[1],
                        "timestamp": log[2],
                        "prediction": log[3],
                        "confidence": log[4],
                        "username": log[5]
                    }
                    for log in recent_logs
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get admin dashboard: {str(e)}")

@app.get("/admin/drivers")
async def get_all_drivers():
    """Get list of all drivers"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.email,
                u.phone,
                u.created_at,
                COUNT(DISTINCT s.id) as total_sessions,
                SUM(s.drowsy_detections) as total_alerts,
                (
                    SELECT s2.start_time 
                    FROM sessions s2 
                    WHERE s2.user_id = u.id AND s2.end_time IS NULL 
                    LIMIT 1
                ) as active_session_start
            FROM users u
            LEFT JOIN sessions s ON u.id = s.user_id
            WHERE u.role = 'driver'
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """)
        
        drivers = cursor.fetchall()
        conn.close()
        
        return {
            "success": True,
            "data": [
                {
                    "id": driver[0],
                    "username": driver[1],
                    "email": driver[2],
                    "phone": driver[3],
                    "created_at": driver[4],
                    "total_sessions": driver[5] or 0,
                    "total_alerts": driver[6] or 0,
                    "is_active": driver[7] is not None,
                    "active_session_start": driver[7]
                }
                for driver in drivers
            ]
        }
        
    except Exception as e:
        logger.error(f"Get drivers error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get drivers: {str(e)}")

@app.get("/admin/sessions")
async def get_all_sessions(limit: int = 50, offset: int = 0):
    """Get all sessions with pagination"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.id,
                s.user_id,
                u.username,
                s.start_time,
                s.end_time,
                s.total_detections,
                s.drowsy_detections,
                s.distance_km
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            ORDER BY s.start_time DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        sessions = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "sessions": [
                    {
                        "id": session[0],
                        "user_id": session[1],
                        "username": session[2],
                        "start_time": session[3],
                        "end_time": session[4],
                        "total_detections": session[5] or 0,
                        "alerts": session[6] or 0,
                        "distance": session[7] or 0.0
                    }
                    for session in sessions
                ],
                "total": total_count,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)