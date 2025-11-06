from flask import Blueprint, render_template, jsonify, current_app
import requests

main_bp = Blueprint('main', __name__)

# Use the correct ESP32 IP - should match your actual ESP32 IP
ESP32_IP = "192.168.1.20"

@main_bp.route('/dashboard')
def dashboard():
    """Dashboard page with detailed monitoring info"""
    return render_template('dashboard.html')

@main_bp.route('/settings')
def settings():
    """Settings page for configuration"""
    return render_template('settings.html')

@main_bp.route('/test_esp32')
def test_esp32():
    """Test ESP32 connection and equipment"""
    try:
        # Test basic connection first
        response = requests.get(f"http://{ESP32_IP}/status", timeout=3)
        if response.status_code == 200:
            # Test equipment
            test_response = requests.get(f"http://{ESP32_IP}/test", timeout=15)  # Longer timeout for equipment test
            if test_response.status_code == 200:
                return jsonify({
                    'status': 'success',
                    'message': 'ESP32-CAM connected and equipment test completed',
                    'test_results': test_response.text,
                    'esp32_ip': ESP32_IP
                })
            else:
                return jsonify({
                    'status': 'partial',
                    'message': f'ESP32-CAM connected but equipment test failed (status: {test_response.status_code})',
                    'esp32_ip': ESP32_IP
                })
        else:
            return jsonify({
                'status': 'error',
                'message': f'ESP32-CAM returned status code: {response.status_code}',
                'esp32_ip': ESP32_IP
            })
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'ESP32-CAM timeout - device not responding. Check if ESP32 is powered on and connected to WiFi.',
            'esp32_ip': ESP32_IP
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error',
            'message': f'Cannot connect to ESP32-CAM at {ESP32_IP} - check IP address and network connection',
            'esp32_ip': ESP32_IP
        })
    except Exception as e:
        current_app.logger.error(f"ESP32 test error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Test failed: {str(e)}',
            'esp32_ip': ESP32_IP
        })

@main_bp.route('/manual_alert')
def manual_alert():
    """Manually trigger alert on ESP32"""
    try:
        data = {'confidence': '0.9'}
        response = requests.post(f"http://{ESP32_IP}/drowsiness_alert", data=data, timeout=3)
        
        if response.status_code == 200:
            current_app.logger.info("Manual alert triggered")
            return jsonify({
                'status': 'success',
                'message': 'Alert triggered successfully - ESP32 should buzz and vibrate for 3 seconds',
                'esp32_ip': ESP32_IP
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to trigger alert (status: {response.status_code})',
                'esp32_ip': ESP32_IP
            })
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'ESP32 timeout - device not responding',
            'esp32_ip': ESP32_IP
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error',
            'message': f'Cannot connect to ESP32 at {ESP32_IP}',
            'esp32_ip': ESP32_IP
        })
    except Exception as e:
        current_app.logger.error(f"Manual alert error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Alert failed: {str(e)}',
            'esp32_ip': ESP32_IP
        })

@main_bp.route('/stop_alert_esp32')
def stop_alert_esp32():
    """Stop alert on ESP32"""
    try:
        response = requests.post(f"http://{ESP32_IP}/stop_alert", timeout=3)
        
        if response.status_code == 200:
            current_app.logger.info("Alert stopped on ESP32")
            return jsonify({
                'status': 'success',
                'message': 'Alert stopped successfully',
                'esp32_ip': ESP32_IP
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to stop alert (status: {response.status_code})',
                'esp32_ip': ESP32_IP
            })
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'ESP32 timeout during stop alert',
            'esp32_ip': ESP32_IP
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error',
            'message': f'Cannot connect to ESP32 at {ESP32_IP}',
            'esp32_ip': ESP32_IP
        })
    except Exception as e:
        current_app.logger.error(f"Stop alert error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Stop alert failed: {str(e)}',
            'esp32_ip': ESP32_IP
        })