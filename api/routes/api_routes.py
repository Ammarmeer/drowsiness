from flask import Blueprint, jsonify, request, current_app
import requests
from datetime import datetime

api_bp = Blueprint('api', __name__)

@api_bp.route('/system/status')
def system_status():
    """Get comprehensive system status"""
    try:
        # Import from main app context
        from app import is_monitoring, detector, detection_results, ESP32_IP
        
        # Check ESP32 connection
        esp32_connected = False
        esp32_status = "disconnected"
        try:
            response = requests.get(f"http://{ESP32_IP}/", timeout=2)
            esp32_connected = response.status_code == 200
            esp32_status = "connected" if esp32_connected else "error"
        except:
            pass
        
        latest_detection = detection_results[-1] if detection_results else None
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'system': {
                'monitoring_active': is_monitoring,
                'model_loaded': detector.model_loaded,
                'esp32_connected': esp32_connected,
                'esp32_status': esp32_status,
                'esp32_ip': ESP32_IP
            },
            'detection': {
                'latest': latest_detection,
                'total_detections': len(detection_results),
                'recent_count': len([d for d in detection_results[-10:] if d['drowsy']])
            }
        })
    except Exception as e:
        current_app.logger.error(f"System status error: {e}")
        return jsonify({
            'error': 'Failed to get system status',
            'message': str(e)
        }), 500

@api_bp.route('/detection/history')
def detection_history():
    """Get detection history with filtering"""
    try:
        from app import detection_results
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        drowsy_only = request.args.get('drowsy_only', False, type=bool)
        
        # Filter results
        filtered_results = detection_results
        if drowsy_only:
            filtered_results = [d for d in detection_results if d['drowsy']]
        
        # Limit results
        filtered_results = filtered_results[-limit:] if len(filtered_results) > limit else filtered_results
        
        return jsonify({
            'detections': filtered_results,
            'total': len(detection_results),
            'filtered_count': len(filtered_results),
            'filters': {
                'limit': limit,
                'drowsy_only': drowsy_only
            }
        })
    except Exception as e:
        current_app.logger.error(f"Detection history error: {e}")
        return jsonify({
            'error': 'Failed to get detection history',
            'message': str(e)
        }), 500

@api_bp.route('/esp32/command', methods=['POST'])
def esp32_command():
    """Send command to ESP32"""
    try:
        from app import ESP32_IP
        
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'Command is required'
            }), 400
        
        command = data['command']
        current_app.logger.info(f"Sending command to ESP32: {command}")
        
        if command == 'alert':
            confidence = data.get('confidence', 0.9)
            response = requests.post(f"http://{ESP32_IP}/drowsiness_alert", 
                                   data={'confidence': str(confidence)}, timeout=3)
        elif command == 'stop_alert':
            response = requests.post(f"http://{ESP32_IP}/stop_alert", timeout=3)
        elif command == 'test':
            response = requests.get(f"http://{ESP32_IP}/test", timeout=10)
        elif command == 'capture':
            response = requests.get(f"http://{ESP32_IP}/capture", timeout=5)
            if response.status_code == 200:
                return response.content, 200, {'Content-Type': 'image/jpeg'}
        else:
            return jsonify({
                'error': 'Invalid command',
                'message': f'Unknown command: {command}'
            }), 400
        
        if response.status_code == 200:
            result = {
                'status': 'success',
                'command': command,
                'response_code': response.status_code
            }
            
            # Try to parse JSON response
            try:
                result['data'] = response.json()
            except:
                result['data'] = response.text
            
            return jsonify(result)
        else:
            return jsonify({
                'error': 'ESP32 command failed',
                'command': command,
                'status_code': response.status_code
            }), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({
            'error': 'ESP32 timeout',
            'message': 'ESP32 device not responding'
        }), 408
    except requests.exceptions.ConnectionError:
        return jsonify({
            'error': 'ESP32 connection error',
            'message': 'Cannot connect to ESP32 device'
        }), 503
    except Exception as e:
        current_app.logger.error(f"ESP32 command error: {e}")
        return jsonify({
            'error': 'Command failed',
            'message': str(e)
        }), 500

@api_bp.route('/monitoring/control', methods=['POST'])
def monitoring_control():
    """Control monitoring system"""
    try:
        from app import is_monitoring
        
        data = request.get_json()
        if not data or 'action' not in data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'Action is required'
            }), 400
        
        action = data['action']
        current_app.logger.info(f"Monitoring control action: {action}")
        
        if action == 'start':
            if not is_monitoring:
                # This would trigger the start_monitoring function
                # For now, return success (actual implementation would start monitoring)
                return jsonify({
                    'status': 'success',
                    'action': 'start',
                    'message': 'Monitoring start requested'
                })
            else:
                return jsonify({
                    'status': 'info',
                    'message': 'Monitoring already active'
                })
        
        elif action == 'stop':
            if is_monitoring:
                # This would trigger the stop_monitoring function
                return jsonify({
                    'status': 'success',
                    'action': 'stop',
                    'message': 'Monitoring stop requested'
                })
            else:
                return jsonify({
                    'status': 'info',
                    'message': 'Monitoring not active'
                })
        
        else:
            return jsonify({
                'error': 'Invalid action',
                'message': f'Unknown action: {action}'
            }), 400
    
    except Exception as e:
        current_app.logger.error(f"Monitoring control error: {e}")
        return jsonify({
            'error': 'Control failed',
            'message': str(e)
        }), 500

@api_bp.route('/debug/info')
def debug_info():
    """Get debug information"""
    try:
        from app import is_monitoring, detector, detection_results, ESP32_IP, latest_frame
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'debug': {
                'flask_debug': current_app.debug,
                'monitoring_active': is_monitoring,
                'model_loaded': detector.model_loaded,
                'detection_count': len(detection_results),
                'latest_frame_available': latest_frame is not None,
                'esp32_ip': ESP32_IP,
                'recent_detections': detection_results[-5:] if detection_results else []
            }
        })
    except Exception as e:
        current_app.logger.error(f"Debug info error: {e}")
        return jsonify({
            'error': 'Debug info failed',
            'message': str(e)
        }), 500

# Error handlers
@api_bp.errorhandler(404)
def api_not_found(error):
    return jsonify({
        'error': 'API endpoint not found',
        'message': 'The requested API endpoint does not exist'
    }), 404

@api_bp.errorhandler(500)
def api_internal_error(error):
    current_app.logger.error(f"API internal error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An internal error occurred'
    }), 500