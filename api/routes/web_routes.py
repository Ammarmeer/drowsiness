# routes/web_routes.py
from flask import Blueprint, render_template

web_bp = Blueprint('web', __name__)

@web_bp.route('/dashboard')
def dashboard():
    """Dashboard page with detailed stats"""
    return render_template('dashboard.html')

@web_bp.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')

@web_bp.route('/history')
def history():
    """Detection history page"""
    return render_template('history.html')