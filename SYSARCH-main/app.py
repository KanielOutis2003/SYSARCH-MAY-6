from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, send_file, make_response, current_app, Response
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import timedelta, datetime
import logging
import sys
from functools import wraps
import os
from werkzeug.utils import secure_filename
import uuid
import time
import sqlite3
import xlsxwriter
from io import BytesIO
import re
import csv
import io
import matplotlib
import matplotlib.pyplot as plt
import base64
from flask_mail import Mail, Message
import json

# Try to import pdfkit but don't fail if it's not available
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False

# Import reportlab for PDF generation (alternative to pdfkit)
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Configure logging
logging.basicConfig(
    filename='error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_very_secure_secret_key_here'
app.permanent_session_lifetime = timedelta(minutes=30)  # Session expires after 30 minutes

# Global variable to track if we're in offline mode
OFFLINE_MODE = False

# Define lab room mapping
lab_room_mapping = {
    'Lab 1': 'Lab 524',
    'Lab 2': 'Lab 526',
    'Lab 3': 'Lab 528',
    'Lab 4': 'Lab 530',
    'Lab 5': 'Lab 532',
    'Lab 6': 'Lab 540',
    'Lab 7': 'Lab 544'
}

# Add lab_room filter to Jinja templates
@app.template_filter('lab_room')
def format_lab_room(lab_code):
    return lab_room_mapping.get(lab_code, lab_code)

# Ensure you have a folder for storing uploaded images
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'profile_pictures')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'csv', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'}

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Create uploads directory for lab resources
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Database connection
def get_db_connection():
    global OFFLINE_MODE
    
    if OFFLINE_MODE:
        print("Running in offline mode. Database features are disabled.")
        return None
        
    try:
        # First try to connect without specifying a database
        connection = mysql.connector.connect(
            host='localhost',
            user='root',  # replace with your XAMPP MySQL username
            password='',   # replace with your XAMPP MySQL password
            port=3306,     # default MySQL port
            connection_timeout=5  # timeout after 5 seconds
        )
        cursor = connection.cursor()
        
        # Create the database if it doesn't exist
        cursor.execute("CREATE DATABASE IF NOT EXISTS students")
        cursor.execute("USE students")
        connection.commit()
        cursor.close()
        
        # Now reconnect with the database specified
        connection = mysql.connector.connect(
            host='localhost',
            user='root',  # replace with your XAMPP MySQL username
            password='',  # replace with your XAMPP MySQL password
            database='students',  # now we can safely use this database
            port=3306,     # default MySQL port
            connection_timeout=5  # timeout after 5 seconds
        )
        return connection
    except mysql.connector.Error as e:
        logging.error(f"Database connection error: {str(e)}")
        print(f"Database connection error: {str(e)}")
        print("Make sure XAMPP is running and MySQL service is started.")
        return None

# Initialize database tables
def init_db():
    """Initialize the database with tables."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                idno VARCHAR(50) NOT NULL UNIQUE,
                firstname VARCHAR(100) NOT NULL,
                lastname VARCHAR(100) NOT NULL,
                middlename VARCHAR(100),
                course VARCHAR(10) NOT NULL,
                year_level VARCHAR(10) NOT NULL,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100),
                contact_number VARCHAR(20),
                profile_picture VARCHAR(255) DEFAULT 'default.jpg',
                sessions_used INT DEFAULT 0,
                max_sessions INT DEFAULT 25,
                points INT DEFAULT 0,
                total_points INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                date_time DATETIME NOT NULL,
                lab_room VARCHAR(50) NOT NULL,
                pc_number VARCHAR(10),
                programming_language VARCHAR(50),
                purpose TEXT,
                check_in_time DATETIME,
                check_out_time DATETIME,
                duration INT DEFAULT 0,
                status VARCHAR(50) DEFAULT 'pending',
                approval_status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        ''')
        
        # Create feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                session_id INT NOT NULL,
                rating INT NOT NULL,
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                UNIQUE KEY (session_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lab_resources (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                resource_type VARCHAR(50),
                lab_room VARCHAR(50),
                file_path VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')
        
        # Create admins table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create announcements table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')
        
        # Create activity_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                student_id INT,
                lab_room VARCHAR(50),
                action VARCHAR(50) NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
            )
        ''')
        
        # Create pc_status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pc_status (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lab_room VARCHAR(50) NOT NULL,
                pc_number VARCHAR(10) NOT NULL,
                status VARCHAR(20) DEFAULT 'vacant',
                student_id INT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY (lab_room, pc_number),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
            )
        ''')
        
        # Create lab_schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lab_schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lab_room VARCHAR(50) NOT NULL,
                day_of_week TINYINT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                course_name VARCHAR(255),
                instructor VARCHAR(255),
                semester_term VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if admin exists, if not create default admin
        cursor.execute("SELECT * FROM admins WHERE username = 'admin'")
        admin = cursor.fetchone()
        
        if not admin:
            # Create default admin user
            hashed_password = generate_password_hash('admin123')
            cursor.execute("""
                INSERT INTO admins (username, password)
                VALUES (%s, %s)
            """, ('admin', hashed_password))
        
        # Commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Database initialized successfully")
        return True
    except Exception as e:
        print("Error initializing database:", e)
        return False

# Helper function to check if file extension is allowed
def allowed_file(filename):
    """Check if the file extension is allowed"""
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'csv', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to safely execute database operations
def safe_db_operation(operation_func, fallback_value=None, *args, **kwargs):
    global OFFLINE_MODE
    
    if OFFLINE_MODE:
        return fallback_value
        
    try:
        return operation_func(*args, **kwargs)
    except Exception as e:
        logging.error(f"Database operation error: {str(e)}")
        print(f"Database operation error: {str(e)}")
        return fallback_value

# Login required decorator
def login_required(f): 
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if OFFLINE_MODE:
        flash('The application is running in offline mode. Database features are not available. Please start XAMPP and restart the application.', 'warning')
    return render_template('index.html', offline_mode=OFFLINE_MODE)

@app.route('/lab-rules')
def lab_rules():
    return render_template('lab_rules.html')

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        # Get form data
        idno = request.form['idno']
        lastname = request.form['lastname']
        firstname = request.form['firstname']
        middlename = request.form.get('middlename', '')
        course = request.form['course']
        year_level = request.form['year_level']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        
        # Set max sessions based on course
        # BSIT (1), BSCS (2), BSCE (3) get 30 sessions, others get 25
        max_sessions = 30 if course in ['1', '2', '3'] else 25
        
        # Hash the password
        hashed_password = generate_password_hash(password)
        
        try:
            # Make sure the database and tables exist
            with app.app_context():
                init_db()
                
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if username or email already exists
            cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
            existing_username = cursor.fetchone()
            
            cursor.execute("SELECT * FROM students WHERE email = %s", (email,))
            existing_email = cursor.fetchone()
            
            cursor.execute("SELECT * FROM students WHERE idno = %s", (idno,))
            existing_idno = cursor.fetchone()
            
            if existing_username:
                flash('Username already exists. Please choose a different username.', 'error')
                return redirect(url_for('index'))
            
            if existing_email:
                flash('Email already exists. Please use a different email address.', 'error')
                return redirect(url_for('index'))
            
            if existing_idno:
                flash('ID number already exists. Please check your ID number.', 'error')
                return redirect(url_for('index'))
            
            # Insert new student
            cursor.execute('''
            INSERT INTO students (idno, lastname, firstname, middlename, course, year_level, email, username, password, sessions_used, max_sessions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (idno, lastname, firstname, middlename, course, year_level, email, username, hashed_password, 0, max_sessions))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    global OFFLINE_MODE
    
    if OFFLINE_MODE:
        flash('Database is not available. The application is running in offline mode.', 'error')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn is None:
            flash('Database connection failed. The application may be in offline mode.', 'error')
            return redirect(url_for('index'))
            
        cursor = conn.cursor(dictionary=True)
        
        # Check if it's an admin login
        if username == 'admin':
            cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], password):
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['user_type'] = 'admin'
                flash('Welcome, Admin!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials', 'error')
                return redirect(url_for('index'))
        
        # Check if it's a student login
        cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            # Ensure sessions_used and max_sessions exist
            if 'sessions_used' not in user or user['sessions_used'] is None:
                # Update the user record to include sessions_used if it doesn't exist
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Set max_sessions based on course
                max_sessions = 30 if user['course'] in ['1', '2', '3'] else 25
                
                cursor.execute("""
                UPDATE students 
                SET sessions_used = 0, max_sessions = %s
                WHERE id = %s
                """, (max_sessions, user['id']))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                # Update the user object
                user['sessions_used'] = 0
                user['max_sessions'] = max_sessions
            
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = 'student'
            session['student_info'] = {
                'id': user['id'],
                'idno': user['idno'],
                'name': f"{user['firstname']} {user['lastname']}",
                'profile_picture': user['profile_picture']
            }
            flash(f'Welcome, {user["firstname"]}!', 'success')
            return redirect(url_for('student_dashboard'))
        
        flash('Invalid username or password', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/student-dashboard')
@login_required
def student_dashboard():
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Use safe database operation
    def get_student_data():
        conn = get_db_connection()
        if conn is None:
            return None
            
        cursor = conn.cursor(dictionary=True)
        
        # Get student information with proper session count
        cursor.execute("""
            SELECT s.*, 
                   COALESCE(COUNT(DISTINCT CASE WHEN ses.status = 'completed' OR ses.status = 'active' THEN ses.id END), 0) as sessions_used
            FROM students s
            LEFT JOIN sessions ses ON s.id = ses.student_id
            WHERE s.id = %s
            GROUP BY s.id
        """, (session['user_id'],))
        student = cursor.fetchone()
        
        if not student:
            cursor.close()
            conn.close()
            return None
        
        # Update the sessions_used in the database
        cursor.execute("""
            UPDATE students 
            SET sessions_used = %s 
            WHERE id = %s
        """, (student['sessions_used'], student['id']))
        conn.commit()
        
        # Get student's sessions
        cursor.execute("""
        SELECT * FROM sessions 
        WHERE student_id = %s 
        ORDER BY date_time DESC
        """, (session['user_id'],))
        sessions = cursor.fetchall() or []
        
        # Get student's feedback
        try:
            cursor.execute("""
            SELECT f.*, s.lab_room 
            FROM feedback f
            JOIN sessions s ON f.session_id = s.id
            WHERE f.student_id = %s
            ORDER BY f.created_at DESC
            """, (session['user_id'],))
            feedback_list = cursor.fetchall() or []
        except:
            feedback_list = []
        
        cursor.close()
        conn.close()
        
        return {
            'student': student,
            'sessions': sessions,
            'feedback_list': feedback_list
        }
    
    # Get data safely
    data = safe_db_operation(get_student_data, {
        'student': {'firstname': 'User', 'lastname': '', 'sessions_used': 0, 'max_sessions': 0},
        'sessions': [],
        'feedback_list': []
    })
    
    if data is None:
        flash('Error retrieving student data. The application may be in offline mode.', 'error')
        return redirect(url_for('index'))
    
    return render_template('student_dashboard.html', 
                          student=data['student'], 
                          sessions=data['sessions'],
                          feedback_list=data['feedback_list'],
                          offline_mode=OFFLINE_MODE)

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    import datetime

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        today_date = datetime.datetime.now().strftime('%A, %B %d, %Y')
        
        # Get all students with proper session counts
        cursor.execute("""
            SELECT s.*, 
                   COALESCE(COUNT(DISTINCT CASE WHEN ses.status = 'completed' OR ses.status = 'active' THEN ses.id END), 0) as sessions_used
            FROM students s
            LEFT JOIN sessions ses ON s.id = ses.student_id
            GROUP BY s.id
            ORDER BY s.lastname
        """)
        students = cursor.fetchall()
        
        # Update sessions_used for all students
        for student in students:
            cursor.execute("""
                UPDATE students 
                SET sessions_used = %s 
                WHERE id = %s
            """, (student['sessions_used'], student['id']))
        conn.commit()
        
        # Check if approval_status column exists in sessions table
        has_approval_status = False
        try:
            cursor.execute("SHOW COLUMNS FROM sessions LIKE 'approval_status'")
            if cursor.fetchone():
                has_approval_status = True
        except:
            pass

        # Get pending sessions
        try:
            if has_approval_status:
                cursor.execute("""
                SELECT s.*, st.firstname, st.lastname, st.idno, st.course
                FROM sessions s
                JOIN students st ON s.student_id = st.id
                WHERE s.status = 'pending' AND s.approval_status = 'pending'
                ORDER BY s.date_time ASC
                """)
            else:
                cursor.execute("""
                SELECT s.*, st.firstname, st.lastname, st.idno, st.course
                FROM sessions s
                JOIN students st ON s.student_id = st.id
                WHERE s.status = 'pending'
                ORDER BY s.date_time ASC
                """)
            pending_sessions = cursor.fetchall()
            
            # Format dates for pending sessions
            for session in pending_sessions:
                if 'date_time' in session and session['date_time']:
                    session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
        except Exception as e:
            logging.error(f"Error fetching pending sessions: {str(e)}")
            pending_sessions = []

        # Get active sessions
        try:
            cursor.execute("""
            SELECT s.*, st.firstname, st.lastname, st.idno, st.course
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE s.status = 'active' AND s.check_in_time IS NOT NULL
            ORDER BY s.check_in_time DESC, s.date_time ASC
            """)
            active_sessions = cursor.fetchall()
            
            # Format dates for active sessions
            for session in active_sessions:
                if 'date_time' in session and session['date_time']:
                    session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
        except Exception as e:
            logging.error(f"Error fetching active sessions: {str(e)}")
            active_sessions = []
        
        # Get reservation logs (both approved and rejected)
        try:
            cursor.execute("""
            SELECT s.*, st.firstname, st.lastname, st.idno, st.course
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE (s.approval_status = 'pending' OR s.approval_status = 'approved' OR s.approval_status = 'rejected')
            ORDER BY 
                CASE 
                    WHEN s.approval_status = 'pending' THEN 1
                    WHEN s.approval_status = 'approved' AND s.status = 'pending' THEN 2
                    WHEN s.approval_status = 'approved' AND s.status = 'active' THEN 3
                    WHEN s.approval_status = 'rejected' THEN 4
                    ELSE 5
                END,
                s.created_at DESC
            LIMIT 50
            """)
            reservation_logs = cursor.fetchall()
            
            # Format dates for display
            for session in reservation_logs:
                if 'date_time' in session and session['date_time']:
                    session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
        except Exception as e:
            logging.error(f"Error fetching reservation logs: {str(e)}")
            reservation_logs = []
            
        # Get recent activity for display
        try:
            cursor.execute("""
            SELECT a.*, s.firstname, s.lastname, s.idno, s.course, a.timestamp as timestamp_date, a.timestamp as timestamp_time
            FROM activity_logs a
            LEFT JOIN students s ON a.student_id = s.id
            ORDER BY a.timestamp DESC
            LIMIT 10
            """)
            recent_activity = cursor.fetchall()
            
            # Format dates for display
            for activity in recent_activity:
                if 'timestamp' in activity and activity['timestamp']:
                    activity['timestamp_date'] = activity['timestamp'].strftime('%Y-%m-%d')
                    activity['timestamp_time'] = activity['timestamp'].strftime('%H:%M:%S')
        except Exception as e:
            logging.error(f"Error fetching recent activity: {str(e)}")
            recent_activity = []
        
        # Get lab room usage statistics for charts
        try:
            cursor.execute("""
            SELECT lab_room, COUNT(*) as count
            FROM sessions
            WHERE status = 'completed'
            GROUP BY lab_room
            ORDER BY count DESC
            """)
            lab_stats = cursor.fetchall()
            
            # Add pretty lab room names
            for lab in lab_stats:
                if lab['lab_room'] == 'Lab 1':
                    lab['lab_room_name'] = 'Lab 524'
                elif lab['lab_room'] == 'Lab 2':
                    lab['lab_room_name'] = 'Lab 526'
                elif lab['lab_room'] == 'Lab 3':
                    lab['lab_room_name'] = 'Lab 528'
                elif lab['lab_room'] == 'Lab 4':
                    lab['lab_room_name'] = 'Lab 530'
                elif lab['lab_room'] == 'Lab 5':
                    lab['lab_room_name'] = 'Lab 532'
                elif lab['lab_room'] == 'Lab 6':
                    lab['lab_room_name'] = 'Lab 540'
                elif lab['lab_room'] == 'Lab 7':
                    lab['lab_room_name'] = 'Lab 544'
                else:
                    lab['lab_room_name'] = lab['lab_room']
        except Exception as e:
            logging.error(f"Error fetching lab stats: {str(e)}")
            lab_stats = []
        
        # Get programming language statistics
        try:
            cursor.execute("""
            SELECT programming_language, COUNT(*) as count
            FROM sessions
            WHERE programming_language IS NOT NULL AND programming_language != ''
            GROUP BY programming_language
            ORDER BY count DESC
            """)
            language_stats = cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching language stats: {str(e)}")
            language_stats = []
        
        # Get feedback statistics
        try:
            cursor.execute("""
            SELECT 
                COUNT(*) as total_feedback,
                AVG(rating) as average_rating,
                SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as positive_feedback,
                SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) as negative_feedback
            FROM feedback
            """)
            feedback_stats = cursor.fetchone()
            
            cursor.execute("""
            SELECT f.*, s.firstname, s.lastname, s.idno, s.course
            FROM feedback f
            JOIN students s ON f.student_id = s.id
            ORDER BY f.created_at DESC
            LIMIT 10
            """)
            feedback_list = cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching feedback stats: {str(e)}")
            feedback_stats = {"total_feedback": 0, "average_rating": 0, "positive_feedback": 0, "negative_feedback": 0}
            feedback_list = []
        
        # Get announcements
        try:
            cursor.execute("""
            SELECT * FROM announcements
            ORDER BY created_at DESC
            """)
            announcements = cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching announcements: {str(e)}")
            announcements = []
        
        # Calculate course distribution statistics for charts
        course_stats = {
            'BSIT': 0,
            'BSCS': 0,
            'BSCE': 0,
            'Other': 0
        }
        
        for student in students:
            if student['course'] == '1':
                course_stats['BSIT'] += 1
            elif student['course'] == '2':
                course_stats['BSCS'] += 1
            elif student['course'] == '3':
                course_stats['BSCE'] += 1
            else:
                course_stats['Other'] += 1
        
        # Calculate session purpose distribution
        try:
            cursor.execute("""
            SELECT 
                CASE 
                    WHEN purpose LIKE '%python%' THEN 'Python'
                    WHEN purpose LIKE '%java%' THEN 'Java'
                    WHEN purpose LIKE '%c#%' THEN 'C#'
                    WHEN purpose LIKE '%c++%' THEN 'C++'
                    WHEN purpose LIKE '%javascript%' THEN 'JavaScript'
                    WHEN purpose LIKE '%php%' THEN 'PHP'
                    WHEN purpose LIKE '%project%' THEN 'Project'
                    WHEN purpose LIKE '%assignment%' THEN 'Assignment'
                    WHEN purpose LIKE '%research%' THEN 'Research'
                    ELSE 'Other'
                END as purpose_category,
                COUNT(*) as count
            FROM sessions
            WHERE status = 'completed'
            GROUP BY purpose_category
            ORDER BY count DESC
            """)
            purpose_stats = cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching purpose stats: {str(e)}")
            purpose_stats = []
        
        # Compute status statistics for status chart
        status_stats = {
            'active': len([s for s in active_sessions if s.get('status') == 'active']),
            'pending': len(pending_sessions),
            'completed': 0,
            'cancelled': 0,
            'rejected': 0
        }
        
        try:
            cursor.execute("""
            SELECT 
                status,
                approval_status,
                COUNT(*) as count
            FROM sessions
            WHERE status IN ('completed', 'cancelled') OR approval_status = 'rejected'
            GROUP BY status, approval_status
            """)
            status_results = cursor.fetchall()
            
            for status in status_results:
                if status['status'] == 'completed':
                    status_stats['completed'] = status['count']
                elif status['status'] == 'cancelled':
                    status_stats['cancelled'] = status['count']
                elif status['approval_status'] == 'rejected':
                    status_stats['rejected'] = status['count']
        except Exception as e:
            logging.error(f"Error fetching status stats: {str(e)}")
        
        cursor.close()
        conn.close()
        
        # Pass all data to the template
        return render_template('admin_dashboard.html', 
                              pending_sessions=pending_sessions,
                              active_sessions=active_sessions, 
                              reservation_logs=reservation_logs, 
                              students=students,
                              recent_activity=recent_activity,
                              has_approval_status=has_approval_status,
                              feedback_stats=feedback_stats,
                              feedback_list=feedback_list,
                              announcements=announcements,
                              language_stats=language_stats,
                              lab_stats=lab_stats,
                              course_stats=course_stats,
                              purpose_stats=purpose_stats,
                              status_stats=status_stats,
                              today_date=today_date,
                              leaderboard=[])
    except Exception as e:
        logging.error(f"Error in admin dashboard: {str(e)}")
        # Provide default values if database access fails
        return render_template('admin_dashboard.html', 
                              pending_sessions=[],
                              active_sessions=[], 
                              reservation_logs=[], 
                              students=[],
                              recent_activity=[],
                              has_approval_status=False,
                              feedback_stats={"total_feedback": 0, "average_rating": 0, "positive_feedback": 0, "negative_feedback": 0},
                              feedback_list=[],
                              announcements=[],
                              language_stats=[],
                              lab_stats=[],
                              course_stats={'BSIT': 0, 'BSCS': 0, 'BSCE': 0, 'Other': 0},
                              purpose_stats=[],
                              status_stats={'active': 0, 'pending': 0, 'completed': 0, 'cancelled': 0, 'rejected': 0},
                              today_date=datetime.datetime.now().strftime('%A, %B %d, %Y'),
                              leaderboard=[])

@app.route('/admin/delete-student/<int:student_id>', methods=['POST'])
@admin_required
def delete_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Delete student's sessions
        cursor.execute("DELETE FROM sessions WHERE student_id = %s", (student_id,))
        
        # Delete student's feedback
        cursor.execute("DELETE FROM feedback WHERE student_id = %s", (student_id,))
        
        # Delete the student
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
        
        conn.commit()
        flash(f'Student {student["firstname"]} {student["lastname"]} has been deleted successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to delete student: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.template_filter('format_schedule_time')
def format_schedule_time(time_value):
    if not time_value:
        return ''
    
    # Extract hours and minutes from time_value
    hours = time_value.seconds // 3600
    minutes = (time_value.seconds % 3600) // 60
    
    # Convert to 12-hour format with AM/PM
    period = 'AM' if hours < 12 else 'PM'
    hours = hours if hours <= 12 else hours - 12
    hours = 12 if hours == 0 else hours
    
    return f"{hours}:{minutes:02d} {period}"

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    """Format a date using the given format."""
    if not date:
        return ''
    if fmt:
        return date.strftime(fmt)
    return date.strftime('%Y-%m-%d %H:%M:%S')

def get_leaderboard():
    """Get the student leaderboard data"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get students with points and sessions data
            cursor.execute('''
                SELECT 
                    s.id, 
                    s.idno, 
                    s.firstname, 
                    s.lastname, 
                    s.course, 
                    s.year_level,
                    s.points,
                    s.total_points, 
                    (SELECT COUNT(*) FROM sessions 
                     WHERE student_id = s.id 
                     AND status = 'completed') as completed_sessions
                FROM students s
                ORDER BY s.total_points DESC, completed_sessions DESC
                LIMIT 50
            ''')
            
            result = cursor.fetchall()
            
            # Log some debug information
            for student in result:
                logging.info(f"Leaderboard: Student {student['firstname']} {student['lastname']}: Points={student['points']}, Total Points={student['total_points']}, Completed Sessions={student['completed_sessions']}")
            
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            logging.error(f"Error fetching leaderboard: {e}")
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            return []
    except Exception as e:
        logging.error(f"Error fetching leaderboard: {str(e)}")
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
        return []

@app.before_first_request
def initialize_database():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to database during initialization")
        return
    
    cursor = conn.cursor()
    
    try:
        # Check if students table exists
        cursor.execute("SHOW TABLES LIKE 'students'")
        if cursor.fetchone():
            # Check if points column exists in students table
            cursor.execute("SHOW COLUMNS FROM students LIKE 'points'")
            if not cursor.fetchone():
                # Add points column to students table
                cursor.execute("ALTER TABLE students ADD COLUMN points INT DEFAULT 0")
                print("Added points column to students table")
            
            # Check if total_points column exists in students table
            cursor.execute("SHOW COLUMNS FROM students LIKE 'total_points'")
            if not cursor.fetchone():
                # Add total_points column to students table
                cursor.execute("ALTER TABLE students ADD COLUMN total_points INT DEFAULT 0")
                print("Added total_points column to students table")
            
            # Check if max_sessions column exists in students table
            cursor.execute("SHOW COLUMNS FROM students LIKE 'max_sessions'")
            if not cursor.fetchone():
                # Add max_sessions column to students table
                cursor.execute("ALTER TABLE students ADD COLUMN max_sessions INT DEFAULT 25")
                print("Added max_sessions column to students table")
        
        # Check if lab_resources table exists
        cursor.execute("SHOW TABLES LIKE 'lab_resources'")
        if not cursor.fetchone():
            # Create lab_resources table
            cursor.execute("""
                CREATE TABLE lab_resources (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    resource_type VARCHAR(50),
                    lab_room VARCHAR(50),
                    file_path VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            print("Created lab_resources table")
        
        conn.commit()
    except Exception as e:
        print(f"Error during database initialization: {e}")
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/check_out_student_with_reward/<int:session_id>', methods=['POST'])
@admin_required
def check_out_student_with_reward(session_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First get the session data to get student_id, lab_room and pc_number
        cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
        session_data = cursor.fetchone()
        
        if not session_data:
            conn.close()
            flash('Session not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        student_id = session_data['student_id']
        
        # Get the current time
        check_out_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update session status to completed and set check_out_time
        cursor.execute('''
            UPDATE sessions 
            SET status = 'completed', check_out_time = %s 
            WHERE id = %s AND status = 'active'
        ''', (check_out_time, session_id))
        
        # Check if any row was affected
        if cursor.rowcount == 0:
            # Session might not exist or is not active
            conn.close()
            flash('Session not found or already completed', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Increment the sessions_used count for the student
        cursor.execute("""
            UPDATE students 
            SET sessions_used = sessions_used + 1 
            WHERE id = %s
        """, (student_id,))
        
        # Get PC number directly from the session data first
        pc_number = session_data.get('pc_number')
            
        # Special handling for PC 0 (ensure it's a string)
        if pc_number == 0 or pc_number == '0':
            pc_number = '0'
            logging.info(f"Handling PC #0 specifically during check-out")
        
        # If not found, try to extract it from purpose field
        if not pc_number and session_data.get('purpose'):
            # Try to extract PC number from purpose using regex
            import re
            pc_match = re.search(r'PC #(\d+)', session_data['purpose'])
            if pc_match:
                pc_number = pc_match.group(1)
                logging.info(f"Extracted PC number {pc_number} from purpose: {session_data['purpose']}")
        
        # Update PC status if a PC number was provided
        if pc_number:
            lab_room = session_data['lab_room']
            
            # Only update PC status to vacant if it's not in maintenance mode
            cursor.execute("""
                UPDATE pc_status 
                SET status = CASE WHEN status != 'maintenance' THEN 'vacant' ELSE status END,
                    student_id = NULL
                WHERE lab_room = %s AND pc_number = %s
            """, (lab_room, pc_number))
            
            logging.info(f"Updated PC #{pc_number} in {lab_room} to vacant after student checkout")
            
            # If no rows were updated, create the PC status record
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status)
                    VALUES (%s, %s, 'vacant')
                """, (lab_room, pc_number))
                logging.info(f"Created new vacant PC status for PC #{pc_number} in {lab_room}")
        
        # Award 1 point to the student - increment both points and total_points
        cursor.execute("""
            UPDATE students 
            SET 
                points = points + 1, 
                total_points = COALESCE(total_points, 0) + 1 
            WHERE id = %s
        """, (student_id,))
        
        # Get the student's points after the update
        cursor.execute("SELECT points, total_points, firstname, lastname FROM students WHERE id = %s", (student_id,))
        student_data = cursor.fetchone()
        
        if not student_data:
            conn.close()
            flash('Student not found', 'error')
            return redirect(url_for('admin_dashboard'))
            
        current_points = student_data['points']
        total_points = student_data.get('total_points', current_points)  # Use total_points if available
        student_name = f"{student_data['firstname']} {student_data['lastname']}"
        
        # Check if points can be converted to free sessions (3 points = 1 free session)
        if current_points >= 3:
            # Calculate how many free sessions to add
            free_sessions = current_points // 3
            remaining_points = current_points % 3
            
            # Reset points to the remainder
            cursor.execute("UPDATE students SET points = %s WHERE id = %s", (remaining_points, student_id))
            
            # Add free session by increasing max_sessions
            cursor.execute("UPDATE students SET max_sessions = max_sessions + %s WHERE id = %s", (free_sessions, student_id))
            
            flash(f'Checked out {student_name}. Awarded 1 point! {free_sessions * 3} points converted to {free_sessions} free session(s). {remaining_points} points remaining. Total points earned: {total_points}', 'success')
        else:
            flash(f'Checked out {student_name}. Awarded 1 point! Current points: {current_points}. Total points earned: {total_points}', 'success')
        
        # Log the activity
        try:
            cursor.execute("""
                INSERT INTO activity_logs (user_id, student_id, lab_room, action, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                session.get('user_id', 0),
                student_id,
                session_data['lab_room'],
                'checkout_with_reward',
                f"Checked out with reward (1 point). Current points: {current_points}, Total earned: {total_points}",
                check_out_time
            ))
        except Exception as e:
            logging.error(f"Error logging activity: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        logging.error(f"Error checking out student with reward: {str(e)}")
        flash(f'Error checking out student: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/student/leaderboard')
@login_required
def student_leaderboard():
    """View student sit-in leaderboard (student view)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get top students by number of sessions and points
        cursor.execute("""
            SELECT s.id, s.idno, s.firstname, s.lastname, s.course, s.year_level,
                   s.points, s.total_points,
                   COUNT(ss.id) AS total_sessions,
                   SUM(CASE WHEN ss.status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions,
                   SUM(TIMESTAMPDIFF(MINUTE, ss.check_in_time, ss.check_out_time)) AS total_minutes
            FROM students s
            LEFT JOIN sessions ss ON s.id = ss.student_id
            GROUP BY s.id
            ORDER BY s.total_points DESC, completed_sessions DESC
            LIMIT 50
        """)
        
        leaderboard = cursor.fetchall()
        
        # Get the current student's ranking
        current_student_id = session.get('user_id')
        cursor.execute("""
            SELECT s.id, s.idno, s.firstname, s.lastname, s.course, s.year_level,
                   s.points, s.total_points,
                   COUNT(ss.id) AS total_sessions,
                   SUM(CASE WHEN ss.status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions,
                   SUM(TIMESTAMPDIFF(MINUTE, ss.check_in_time, ss.check_out_time)) AS total_minutes,
                   (
                      SELECT COUNT(*) + 1
                      FROM (
                          SELECT st.id, st.total_points, COUNT(CASE WHEN ses.status = 'completed' THEN 1 END) as comp_sessions
                          FROM students st
                          LEFT JOIN sessions ses ON st.id = ses.student_id
                          GROUP BY st.id
                          HAVING total_points > (
                              SELECT total_points
                              FROM students
                              WHERE id = %s
                          ) OR (
                              total_points = (
                                  SELECT total_points
                                  FROM students
                                  WHERE id = %s
                              ) AND comp_sessions > (
                                  SELECT COUNT(*)
                                  FROM sessions
                                  WHERE student_id = %s AND status = 'completed'
                              )
                          )
                      ) AS better_students
                   ) AS rank
            FROM students s
            LEFT JOIN sessions ss ON s.id = ss.student_id
            WHERE s.id = %s
            GROUP BY s.id
        """, (current_student_id, current_student_id, current_student_id, current_student_id))
        
        current_student = cursor.fetchone()
        
        # Format data for display
        for student in leaderboard:
            # Format course name
            if student['course'] == '1':
                student['course_name'] = 'BSIT'
            elif student['course'] == '2':
                student['course_name'] = 'BSCS'
            elif student['course'] == '3':
                student['course_name'] = 'BSCE'
            else:
                student['course_name'] = student['course']
            
            # Format total time
            if student['total_minutes']:
                hours = student['total_minutes'] // 60
                minutes = student['total_minutes'] % 60
                student['total_time'] = f"{hours} hr {minutes} min"
            else:
                student['total_time'] = "0 min"
            
            # Ensure points exist
            if 'points' not in student or student['points'] is None:
                student['points'] = 0
            if 'total_points' not in student or student['total_points'] is None:
                student['total_points'] = 0
        
        # Format current student data
        if current_student:
            if current_student['course'] == '1':
                current_student['course_name'] = 'BSIT'
            elif current_student['course'] == '2':
                current_student['course_name'] = 'BSCS'
            elif current_student['course'] == '3':
                current_student['course_name'] = 'BSCE'
            else:
                current_student['course_name'] = current_student['course']
            
            if current_student['total_minutes']:
                hours = current_student['total_minutes'] // 60
                minutes = current_student['total_minutes'] % 60
                current_student['total_time'] = f"{hours} hr {minutes} min"
            else:
                current_student['total_time'] = "0 min"
            
            if 'points' not in current_student or current_student['points'] is None:
                current_student['points'] = 0
            if 'total_points' not in current_student or current_student['total_points'] is None:
                current_student['total_points'] = 0
        
        cursor.close()
        conn.close()
        
        return render_template('admin_leaderboard.html', 
                              leaderboard=leaderboard, 
                              current_student=current_student,
                              is_student_view=True)
        
    except Exception as e:
        logging.error(f"Error viewing leaderboard: {str(e)}")
        flash(f"Error viewing leaderboard: {str(e)}", 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/admin/leaderboard')
@admin_required
def admin_leaderboard():
    """View student sit-in leaderboard (admin view)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get top students by number of sessions and points
        cursor.execute("""
            SELECT s.id, s.idno, s.firstname, s.lastname, s.course, s.year_level,
                   s.points, s.total_points,
                   COUNT(ss.id) AS total_sessions,
                   SUM(CASE WHEN ss.status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions
            FROM students s
            LEFT JOIN sessions ss ON s.id = ss.student_id
            GROUP BY s.id
            ORDER BY s.total_points DESC, completed_sessions DESC
            LIMIT 50
        """)
        
        leaderboard = cursor.fetchall()
        
        # Calculate total time spent for each student in a readable format
        for student in leaderboard:
            # Ensure total_points exists, default to 0 if missing
            if 'total_points' not in student or student['total_points'] is None:
                student['total_points'] = 0
                
            # Ensure points exists, default to 0 if missing
            if 'points' not in student or student['points'] is None:
                student['points'] = 0
                
            # Query for total duration
            cursor.execute("""
                SELECT SUM(duration) AS total_minutes
                FROM sessions
                WHERE student_id = %s AND status = 'completed'
            """, (student['id'],))
            
            duration_result = cursor.fetchone()
            total_minutes = duration_result['total_minutes'] if duration_result and duration_result['total_minutes'] else 0
            
            if total_minutes:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                student['total_time'] = f"{hours} hr {minutes} min"
            else:
                student['total_time'] = "0 min"
        
        cursor.close()
        conn.close()
        
        return render_template('admin_leaderboard.html', leaderboard=leaderboard, is_student_view=False)
        
    except Exception as e:
        logging.error(f"Error viewing leaderboard: {str(e)}")
        flash(f"Error viewing leaderboard: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/lab-resources')
@admin_required
def admin_lab_resources():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM lab_resources
        ORDER BY created_at DESC
    """)
    resources = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('lab_resources.html', resources=resources)

@app.route('/student/lab-resources')
@login_required
def student_lab_resources():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM lab_resources
        ORDER BY created_at DESC
    """)
    resources = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('student_lab_resources.html', resources=resources)

@app.route('/add-resource', methods=['POST'])
@admin_required
def add_resource():
    resource_source = request.form.get('resource_source', 'file')
    
    # Handle URL resources
    if resource_source == 'url':
        resource_url = request.form.get('resource_url')
        if not resource_url:
            flash('URL is required for external resources', 'error')
            return redirect(url_for('admin_lab_resources'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure lab_resources table exists with url field
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_resources (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                resource_type VARCHAR(50),
                lab_room VARCHAR(50),
                file_path VARCHAR(255),
                resource_url VARCHAR(255),
                is_url BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Check if url column exists, add if not
        try:
            cursor.execute("""
                ALTER TABLE lab_resources 
                ADD COLUMN IF NOT EXISTS resource_url VARCHAR(255),
                ADD COLUMN IF NOT EXISTS is_url BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
        except Exception as e:
            # If MySQL version doesn't support IF NOT EXISTS in ALTER TABLE
            print(f"Note: Could not check for column existence: {e}")
            # Continue anyway as the insert will work if columns exist
        
        cursor.execute("""
            INSERT INTO lab_resources (title, description, resource_type, lab_room, resource_url, is_url)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, (
            request.form['title'],
            request.form['description'],
            request.form['resource_type'],
            request.form['lab_room'],
            resource_url
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('External resource added successfully', 'success')
        return redirect(url_for('admin_lab_resources'))
    
    # Handle file upload (original functionality)
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin_lab_resources'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_lab_resources'))
    
    if file:
        filename = secure_filename(file.filename)
        # Create uploads directory if it doesn't exist
        os.makedirs('uploads', exist_ok=True)
        
        # Generate a unique filename to prevent overwriting
        file_extension = os.path.splitext(filename)[1]
        unique_filename = str(uuid.uuid4()) + file_extension
        
        file_path = os.path.join('uploads', unique_filename)
        file.save(file_path)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure lab_resources table exists with url field
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_resources (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                resource_type VARCHAR(50),
                lab_room VARCHAR(50),
                file_path VARCHAR(255),
                resource_url VARCHAR(255),
                is_url BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Check if url column exists, add if not
        try:
            cursor.execute("""
                ALTER TABLE lab_resources 
                ADD COLUMN IF NOT EXISTS resource_url VARCHAR(255),
                ADD COLUMN IF NOT EXISTS is_url BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
        except Exception as e:
            # If MySQL version doesn't support IF NOT EXISTS in ALTER TABLE
            print(f"Note: Could not check for column existence: {e}")
        
        cursor.execute("""
            INSERT INTO lab_resources (title, description, resource_type, lab_room, file_path, is_url)
            VALUES (%s, %s, %s, %s, %s, FALSE)
        """, (
            request.form['title'],
            request.form['description'],
            request.form['resource_type'],
            request.form['lab_room'],
            unique_filename
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Resource added successfully', 'success')
        return redirect(url_for('admin_lab_resources'))
    
    flash('Error uploading file', 'error')
    return redirect(url_for('admin_lab_resources'))

@app.route('/edit-resource', methods=['POST'])
@admin_required
def edit_resource():
    resource_id = request.form['resource_id']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get current resource details
    cursor.execute("SELECT * FROM lab_resources WHERE id = %s", (resource_id,))
    current_resource = cursor.fetchone()
    
    if not current_resource:
        cursor.close()
        conn.close()
        flash('Resource not found', 'error')
        return redirect(url_for('admin_lab_resources'))
    
    # Determine if this is a URL resource or file resource
    is_url = current_resource.get('is_url', False)
    
    if is_url:
        # Update URL resource
        cursor.execute("""
            UPDATE lab_resources 
            SET title = %s, description = %s, resource_type = %s, lab_room = %s
            WHERE id = %s
        """, (
            request.form['title'],
            request.form['description'],
            request.form['resource_type'],
            request.form['lab_room'],
            resource_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Resource updated successfully', 'success')
        return redirect(url_for('admin_lab_resources'))
    
    # Handle file resource updates
    current_file_path = current_resource['file_path']
    new_file_path = current_file_path
    
    # Check if a new file was uploaded
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filename = secure_filename(file.filename)
        
        # Generate a unique filename
        file_extension = os.path.splitext(filename)[1]
        unique_filename = str(uuid.uuid4()) + file_extension
        
        # Create uploads directory if it doesn't exist
        os.makedirs('uploads', exist_ok=True)
        
        file_path = os.path.join('uploads', unique_filename)
        file.save(file_path)
        
        # Update file path
        new_file_path = unique_filename
        
        # Delete old file if it exists
        try:
            old_file_path = os.path.join('uploads', current_file_path)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        except Exception as e:
            print(f"Error removing old file: {e}")
    
    # Update resource in database
    cursor.execute("""
        UPDATE lab_resources 
        SET title = %s, description = %s, resource_type = %s, lab_room = %s, file_path = %s
        WHERE id = %s
    """, (
        request.form['title'],
        request.form['description'],
        request.form['resource_type'],
        request.form['lab_room'],
        new_file_path,
        resource_id
    ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Resource updated successfully', 'success')
    return redirect(url_for('admin_lab_resources'))

@app.route('/delete-resource/<int:resource_id>', methods=['POST'])
@admin_required
def delete_resource(resource_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get file path before deleting
    cursor.execute("SELECT file_path FROM lab_resources WHERE id = %s", (resource_id,))
    resource = cursor.fetchone()
    
    if not resource:
        cursor.close()
        conn.close()
        flash('Resource not found', 'error')
        return redirect(url_for('admin_lab_resources'))
    
    # Delete from database
    cursor.execute("DELETE FROM lab_resources WHERE id = %s", (resource_id,))
    conn.commit()
    
    cursor.close()
    conn.close()
    
    # Delete file if it exists
    try:
        file_path = os.path.join('uploads', resource['file_path'])
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error removing file: {e}")
    
    flash('Resource deleted successfully', 'success')
    return redirect(url_for('admin_lab_resources'))

@app.route('/admin/get-resource/<int:resource_id>')
@admin_required
def get_resource(resource_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM lab_resources WHERE id = %s", (resource_id,))
    resource = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not resource:
        return jsonify({'error': 'Resource not found'}), 404
    
    return jsonify(resource)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        # Import current_app from flask
        from flask import current_app
        
        # First try to serve from app's uploads directory
        uploads_path = os.path.join(current_app.root_path, 'uploads')
        
        # Check multiple paths for the file
        search_paths = [
            os.path.join(uploads_path, filename),  # App's uploads directory
            os.path.join('uploads', filename),      # Relative to current working directory
            filename                               # Direct path if absolute
        ]
        
        # Try each path until the file is found
        for file_path in search_paths:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                # Get the file extension to determine MIME type
                file_ext = os.path.splitext(filename)[1].lower()
                
                # Map common extensions to MIME types
                mime_types = {
                    '.pdf': 'application/pdf',
                    '.doc': 'application/msword',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.ppt': 'application/vnd.ms-powerpoint',
                    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    '.xls': 'application/vnd.ms-excel',
                    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    '.txt': 'text/plain',
                    '.csv': 'text/csv',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif'
                }
                
                mime_type = mime_types.get(file_ext, 'application/octet-stream')
                
                # Get the original filename from the database if available
                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT title FROM lab_resources WHERE file_path = %s", (filename,))
                resource = cursor.fetchone()
                cursor.close()
                conn.close()
                
                original_filename = resource['title'] + file_ext if resource else filename
                
                # Determine if browser should display or download
                display_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/gif', 'text/plain']
                if mime_type in display_types:
                    # For files that can be displayed in browser
                    return send_file(file_path, mimetype=mime_type)
                else:
                    # For files that should be downloaded
                    return send_file(
                        file_path,
                        mimetype=mime_type,
                        as_attachment=True,
                        download_name=original_filename
                    )
        
        # If file not found in any location
        return render_template('error.html', 
                              error_message=f"File '{filename}' not found.",
                              search_paths=search_paths), 404
            
    except Exception as e:
        return render_template('error.html', error_message=f"Error serving file: {str(e)}"), 500

@app.route('/export-report/<format>')
@admin_required
def export_report(format):
    # Get date filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Get database connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Define the base query
    query = """
    SELECT s.id, st.idno, st.firstname, st.lastname, st.course, st.year_level,
           s.lab_room, s.date_time, s.check_in_time, s.check_out_time, 
           s.duration, s.purpose, s.status, s.created_at, s.approval_status
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    """
    
    # Add date filters if provided
    params = []
    if start_date and end_date:
        query += " WHERE s.date_time BETWEEN %s AND %s"
        params.append(start_date)
        params.append(end_date)
    
    # Complete the query with ordering
    query += " ORDER BY s.date_time DESC"
    
    # Execute the query
    cursor.execute(query, params)
    sessions = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Process the data based on the requested format
    if format == 'excel':
        import xlsxwriter
        from io import BytesIO
        
        # Create an in-memory Excel file
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Add styles
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'font_color': '#003366'
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 12
        })
        
        column_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#003366',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # Add header
        worksheet.merge_range('A1:M1', 'UNIVERSITY OF CEBU', header_format)
        worksheet.merge_range('A2:M2', 'COLLEGE OF COMPUTER STUDIES', header_format)
        worksheet.merge_range('A3:M3', 'CSS SIT-IN MONITORING SYSTEM', header_format)
        
        # Add title
        if start_date and end_date:
            worksheet.merge_range('A4:M4', f"Session Report ({start_date} to {end_date})", title_format)
        else:
            worksheet.merge_range('A4:M4', "Session Report", title_format)
        
        # Add generation date
        worksheet.merge_range('A5:M5', f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", workbook.add_format({'align': 'center'}))
        
        # Set column widths
        worksheet.set_column('A:A', 5)  # ID
        worksheet.set_column('B:B', 15)  # Student ID
        worksheet.set_column('C:C', 25)  # Name
        worksheet.set_column('D:D', 8)  # Course
        worksheet.set_column('E:E', 6)  # Year
        worksheet.set_column('F:F', 12)  # Lab Room
        worksheet.set_column('G:G', 18)  # Date & Time
        worksheet.set_column('H:H', 18)  # Check In
        worksheet.set_column('I:I', 18)  # Check Out
        worksheet.set_column('J:J', 12)  # Duration
        worksheet.set_column('K:K', 30)  # Purpose
        worksheet.set_column('L:L', 12)  # Status
        worksheet.set_column('M:M', 18)  # Created At
        
        # Add header row (now row 6)
        headers = ['ID', 'Student ID', 'Name', 'Course', 'Year', 'Lab Room', 
                 'Date & Time', 'Check In', 'Check Out', 'Duration (min)', 
                 'Purpose', 'Status', 'Created At']
                 
        for col, header in enumerate(headers):
            worksheet.write(6, col, header, column_header_format)
        
        # Add data rows (starting at row 7)
        for row, session in enumerate(sessions, start=7):
            worksheet.write(row, 0, session['id'])
            worksheet.write(row, 1, session['idno'])
            worksheet.write(row, 2, f"{session['firstname']} {session['lastname']}")
            
            course = session['course']
            if course == '1':
                course = 'BSIT'
            elif course == '2':
                course = 'BSCS'
            elif course == '3':
                course = 'BSCE'
                
            worksheet.write(row, 3, course)
            worksheet.write(row, 4, session['year_level'])
            worksheet.write(row, 5, session['lab_room'])
            
            # Format date fields
            if session['date_time']:
                date_str = session['date_time'].strftime('%Y-%m-%d %H:%M')
                worksheet.write(row, 6, date_str)
            else:
                worksheet.write(row, 6, '')
                
            if session['check_in_time']:
                check_in_str = session['check_in_time'].strftime('%Y-%m-%d %H:%M')
                worksheet.write(row, 7, check_in_str)
            else:
                worksheet.write(row, 7, '')
                
            if session['check_out_time']:
                check_out_str = session['check_out_time'].strftime('%Y-%m-%d %H:%M')
                worksheet.write(row, 8, check_out_str)
            else:
                worksheet.write(row, 8, '')
            
            worksheet.write(row, 9, session['duration'])
            worksheet.write(row, 10, session['purpose'])
            worksheet.write(row, 11, session['status'])
            
            if session['created_at']:
                created_str = session['created_at'].strftime('%Y-%m-%d %H:%M')
                worksheet.write(row, 12, created_str)
            else:
                worksheet.write(row, 12, '')
        
        workbook.close()
        
        # Prepare response
        output.seek(0)
        
        filename = f"session_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    elif format == 'csv':
        import csv
        from io import StringIO
        
        # Create an in-memory CSV file
        output = StringIO()
        writer = csv.writer(output)
        
        # Add university header
        writer.writerow(['UNIVERSITY OF CEBU'])
        writer.writerow(['COLLEGE OF COMPUTER STUDIES'])
        writer.writerow(['CSS SIT-IN MONITORING SYSTEM'])
        writer.writerow([])  # Empty row for spacing
        
        # Add title
        if start_date and end_date:
            writer.writerow([f"Session Report ({start_date} to {end_date})"])
        else:
            writer.writerow(['Session Report'])
            
        writer.writerow([f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
        writer.writerow([])  # Empty row for spacing
        
        # Add header row
        writer.writerow(['ID', 'Student ID', 'Name', 'Course', 'Year', 'Lab Room', 
                        'Date & Time', 'Check In', 'Check Out', 'Duration (min)', 
                        'Purpose', 'Status', 'Created At'])
        
        # Add data rows
        for session in sessions:
            course = session['course']
            if course == '1':
                course = 'BSIT'
            elif course == '2':
                course = 'BSCS'
            elif course == '3':
                course = 'BSCE'
                
            date_str = ''
            if session['date_time']:
                date_str = session['date_time'].strftime('%Y-%m-%d %H:%M')
                
            check_in_str = ''
            if session['check_in_time']:
                check_in_str = session['check_in_time'].strftime('%Y-%m-%d %H:%M')
                
            check_out_str = ''
            if session['check_out_time']:
                check_out_str = session['check_out_time'].strftime('%Y-%m-%d %H:%M')
                
            created_str = ''
            if session['created_at']:
                created_str = session['created_at'].strftime('%Y-%m-%d %H:%M')
                
            writer.writerow([
                session['id'],
                session['idno'],
                f"{session['firstname']} {session['lastname']}",
                course,
                session['year_level'],
                session['lab_room'],
                date_str,
                check_in_str,
                check_out_str,
                session['duration'],
                session['purpose'],
                session['status'],
                created_str
            ])
        
        # Prepare response
        output_str = output.getvalue()
        
        response = make_response(output_str)
        response.headers["Content-Disposition"] = f"attachment; filename=session_report_{datetime.now().strftime('%Y%m%d')}.csv"
        response.headers["Content-type"] = "text/csv"
        return response
        
    elif format == 'pdf':
        if not REPORTLAB_AVAILABLE:
            flash('PDF generation requires the reportlab library', 'error')
            return redirect(url_for('admin_dashboard'))
        
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from io import BytesIO
        
        # Create an in-memory PDF file
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Add university logo and header
        logo_path = os.path.join(app.static_folder, 'CSS.png')
        if os.path.exists(logo_path):
            from reportlab.platypus import Image
            logo = Image(logo_path, width=60, height=60)
            elements.append(logo)
            elements.append(Spacer(1, 10))
        
        # Get the styles
        styles = getSampleStyleSheet()
        
        # Add university header
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,  # Center
            spaceAfter=6
        )
        elements.append(Paragraph("UNIVERSITY OF CEBU", header_style))
        elements.append(Paragraph("COLLEGE OF COMPUTER STUDIES", header_style))
        elements.append(Paragraph("CSS SIT-IN MONITORING SYSTEM", header_style))
        elements.append(Spacer(1, 20))
        
        # Add report title
        title_style = styles['Heading2']
        title_style.alignment = 1  # Center alignment
        
        if start_date and end_date:
            title_text = f"Session Report ({start_date} to {end_date})"
        else:
            title_text = "Session Report"
            
        title = Paragraph(title_text, title_style)
        elements.append(title)
        elements.append(Spacer(1, 10))
        
        # Add generation date
        date_style = ParagraphStyle(
            'Date',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1,  # Center
            textColor=colors.gray
        )
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style))
        elements.append(Spacer(1, 20))
        
        # Format data for the table
        data = [['ID', 'Student ID', 'Name', 'Course', 'Year', 'Lab Room', 
                'Date & Time', 'Check In', 'Check Out', 'Duration (min)', 
                'Purpose', 'Status']]
        
        for session in sessions[:100]:  # Limit to 100 rows to avoid memory issues
            course = session['course']
            if course == '1':
                course = 'BSIT'
            elif course == '2':
                course = 'BSCS'
            elif course == '3':
                course = 'BSCE'
                
            date_str = ''
            if session['date_time']:
                date_str = session['date_time'].strftime('%Y-%m-%d %H:%M')
                
            data.append([
                str(session['id']),
                session['idno'],
                f"{session['firstname']} {session['lastname']}",
                course,
                session['year_level'],
                session['lab_room'],
                date_str,
                session['check_in_time'] or '',
                session['check_out_time'] or '',
                session['duration'] or 0,
                session['purpose'] or '',
                session['status']
            ])
        
        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        
        # Build the PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        
        filename = f"session_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    
    else:
        flash(f'Unsupported format: {format}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/reset-semester', methods=['POST'])
@admin_required
def reset_semester():
    """Reset session counts for all students"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Reset sessions_used count to 0 for all students
        cursor.execute("UPDATE students SET sessions_used = 0")
        
        # Commit the changes
        conn.commit()
        
        # Log the action
        logging.info(f"Admin {session.get('username')} reset semester for all students")
        
        flash('All student session counts have been reset to zero successfully', 'success')
    except Exception as e:
        logging.error(f"Error resetting semester: {str(e)}")
        flash(f'Error resetting semester: {str(e)}', 'error')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Allow students to edit their profile information"""
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get the student's current information
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
    student = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('index'))
    
    # Handle form submission
    if request.method == 'POST':
        try:
            # Get form data
            email = request.form.get('email')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Validate current password if trying to change password
            if new_password:
                if not current_password:
                    flash('Current password is required to change password', 'error')
                    return render_template('edit_profile.html', student=student)
                
                if not check_password_hash(student['password'], current_password):
                    flash('Current password is incorrect', 'error')
                    return render_template('edit_profile.html', student=student)
                
                if new_password != confirm_password:
                    flash('New passwords do not match', 'error')
                    return render_template('edit_profile.html', student=student)
            
            # Process profile picture if uploaded
            profile_picture = student['profile_picture']  # Default to current
            if 'profile_picture' in request.files and request.files['profile_picture'].filename:
                file = request.files['profile_picture']
                filename = secure_filename(file.filename)
                if filename:
                    # Generate a unique filename
                    file_extension = os.path.splitext(filename)[1]
                    new_filename = f"{uuid.uuid4()}{file_extension}"
                    
                    # Ensure profile_pictures directory exists
                    profile_pic_dir = os.path.join(app.static_folder, 'profile_pictures')
                    os.makedirs(profile_pic_dir, exist_ok=True)
                    
                    # Save the file
                    file_path = os.path.join(profile_pic_dir, new_filename)
                    file.save(file_path)
                    
                    profile_picture = new_filename
            
            # Update the database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Build the update query based on what's changed
            update_fields = []
            params = []
            
            if email and email != student['email']:
                update_fields.append("email = %s")
                params.append(email)
            
            if profile_picture != student['profile_picture']:
                update_fields.append("profile_picture = %s")
                params.append(profile_picture)
            
            if new_password:
                update_fields.append("password = %s")
                params.append(generate_password_hash(new_password))
            
            if update_fields:
                query = "UPDATE students SET " + ", ".join(update_fields) + " WHERE id = %s"
                params.append(session['user_id'])
                
                cursor.execute(query, tuple(params))
                conn.commit()
                
                flash('Profile updated successfully', 'success')
            else:
                flash('No changes made', 'info')
            
            cursor.close()
            conn.close()
            
            return redirect(url_for('student_dashboard'))
            
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
            return render_template('edit_profile.html', student=student)
    
    # Display the edit profile form
    return render_template('edit_profile.html', student=student)

@app.route('/todays-sit-ins')
@admin_required
def todays_sit_ins():
    """View all sit-in sessions for today"""
    try:
        # Get today's date in the format stored in the database
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query for sessions with today's date
        cursor.execute("""
            SELECT s.*, st.idno, st.firstname, st.lastname, st.course, st.year_level
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE DATE(s.date_time) = %s
            ORDER BY s.check_in_time DESC
        """, (today,))
        
        sessions = cursor.fetchall()
        
        # Format check-in and check-out times
        for session in sessions:
            if session['check_in_time']:
                session['check_in_time'] = session['check_in_time'].strftime('%I:%M %p')
            if session['check_out_time']:
                session['check_out_time'] = session['check_out_time'].strftime('%I:%M %p')
            
            # Add formatted date
            if session['date_time']:
                session['formatted_date'] = session['date_time'].strftime('%A, %B %d, %Y')
        
        # Get lab room counts
        cursor.execute("""
            SELECT lab_room, COUNT(*) as count
            FROM sessions
            WHERE DATE(date_time) = %s
            GROUP BY lab_room
        """, (today,))
        
        lab_counts = cursor.fetchall()
        
        # Get status counts
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM sessions
            WHERE DATE(date_time) = %s
            GROUP BY status
        """, (today,))
        
        status_counts = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template(
            'todays_sit_ins.html', 
            sessions=sessions,
            todays_sessions=sessions, # Add this for compatibility 
            lab_counts=lab_counts, 
            status_counts=status_counts,
            today=datetime.now().strftime('%A, %B %d, %Y')
        )
        
    except Exception as e:
        logging.error(f"Error viewing today's sit-ins: {str(e)}")
        flash(f"Error viewing today's sit-ins: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/view-announcements')
@admin_required
def view_announcements():
    """View and manage all announcements"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all announcements sorted by creation date (most recent first)
        cursor.execute("""
            SELECT * FROM announcements
            ORDER BY created_at DESC
        """)
        
        announcements = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('admin_announcements.html', announcements=announcements)
        
    except Exception as e:
        logging.error(f"Error viewing announcements: {str(e)}")
        flash(f"Error viewing announcements: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/add-announcement', methods=['POST'])
@admin_required
def add_announcement():
    """Add a new announcement"""
    try:
        # Get form data
        title = request.form.get('title')
        content = request.form.get('content')
        
        # Validate data
        if not title or not content:
            flash('Title and content are required', 'error')
            return redirect(url_for('view_announcements'))
        
        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO announcements (title, content, created_at)
            VALUES (%s, %s, %s)
        """, (title, content, datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Announcement added successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error adding announcement: {str(e)}")
        flash(f'Error adding announcement: {str(e)}', 'error')
    
    return redirect(url_for('view_announcements'))

@app.route('/reset-student-sessions/<int:student_id>', methods=['POST'])
@admin_required
def reset_student_sessions(student_id):
    """Reset the sessions count for a specific student"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First verify student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Reset the sessions_used count for this student
        cursor.execute("UPDATE students SET sessions_used = 0 WHERE id = %s", (student_id,))
        conn.commit()
        
        # Log the action
        cursor.execute("""
            INSERT INTO activity_logs (user_id, student_id, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session.get('user_id', 0),
            student_id,
            'reset_sessions',
            'Administrator reset session count',
            datetime.now()
        ))
        conn.commit()
        
        flash('Sessions reset successfully for student', 'success')
        
    except Exception as e:
        logging.error(f"Error resetting student sessions: {str(e)}")
        flash(f'Error resetting student sessions: {str(e)}', 'error')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/direct-sit-in', methods=['POST'])
@admin_required
def direct_sit_in():
    """Process a direct sit-in request from admin dashboard"""
    try:
        # Get form data
        student_id = request.form.get('student_id')
        lab_room = request.form.get('lab_room')
        pc_number = request.form.get('pc_number')
        purpose = request.form.get('purpose')
        programming_language = request.form.get('programming_language')
        
        if not student_id or not lab_room:
            flash('Student ID and Lab Room are required', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            cursor.close()
            conn.close()
            flash('Student not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Check if student has an active session
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE student_id = %s AND status = 'active'
        """, (student_id,))
        
        active_session = cursor.fetchone()
        if active_session:
            cursor.close()
            conn.close()
            flash('Student already has an active session', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Create a new session - direct sit-in is automatically approved and active
        current_time = datetime.now()
        
        # If PC number is provided but not in the purpose, add it to the purpose
        if pc_number and purpose and 'PC #' not in purpose:
            purpose = f"{purpose} (PC #{pc_number})"
        elif pc_number and not purpose:
            purpose = f"Direct Sit-in (PC #{pc_number})"
        
        cursor.execute("""
            INSERT INTO sessions 
            (student_id, date_time, lab_room, pc_number, programming_language, purpose, check_in_time, status, approval_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            student_id,
            current_time,
            lab_room,
            pc_number,
            programming_language,
            purpose,
            current_time,
            'active',
            'approved',
            current_time
        ))
        
        session_id = cursor.lastrowid
        
        # Update PC status if a PC number was provided
        if pc_number:
            # Ensure pc_number is treated as a string
            pc_number = str(pc_number)
            
            # Check if PC exists in status table
            cursor.execute("SELECT * FROM pc_status WHERE lab_room = %s AND pc_number = %s", 
                          (lab_room, pc_number))
            pc = cursor.fetchone()
            
            if pc:
                # Update PC status to occupied
                cursor.execute("""
                    UPDATE pc_status 
                    SET status = 'occupied', student_id = %s 
                    WHERE lab_room = %s AND pc_number = %s
                """, (student_id, lab_room, pc_number))
                logging.info(f"Updated PC #{pc_number} in {lab_room} to occupied for student {student_id}")
            else:
                # Create new PC status entry
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, %s, %s, %s)
                """, (lab_room, pc_number, 'occupied', student_id))
                logging.info(f"Created new PC status entry for PC #{pc_number} in {lab_room} set to occupied for student {student_id}")
        
        # Increment sessions_used count for the student
        cursor.execute("UPDATE students SET sessions_used = sessions_used + 1 WHERE id = %s", (student_id,))
        
        # Log the activity
        try:
            cursor.execute("""
                INSERT INTO activity_logs (user_id, student_id, lab_room, action, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                session.get('user_id', 0),
                student_id,
                lab_room,
                'direct_sit_in',
                f'Administrator created direct sit-in for {student["firstname"]} {student["lastname"]} in {lab_room} at PC #{pc_number}',
                current_time
            ))
        except Exception as e:
            # Don't fail if logging fails
            logging.error(f"Error logging activity: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f'Direct sit-in recorded for {student["firstname"]} {student["lastname"]} in {lab_room} at PC #{pc_number}', 'success')
        return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        logging.error(f"Error processing direct sit-in: {str(e)}")
        flash(f'Error processing direct sit-in: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/student/announcements')
@login_required
def student_announcements():
    """View student announcements page"""
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all active announcements sorted by creation date (newest first)
        cursor.execute("""
            SELECT * FROM announcements
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        """)
        
        announcements = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('student_announcements.html', announcements=announcements)
        
    except Exception as e:
        logging.error(f"Error viewing student announcements: {str(e)}")
        flash(f'Error viewing announcements: {str(e)}', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/student/lab-schedules')
@login_required
def student_lab_schedules():
    """View lab schedules for students"""
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all lab schedules
        cursor.execute("""
            SELECT * FROM lab_schedules
            ORDER BY day_of_week, start_time
        """)
        
        schedules = cursor.fetchall()
        
        # Group schedules by lab room
        lab_schedules = {}
        for schedule in schedules:
            lab_room = schedule['lab_room']
            if lab_room not in lab_schedules:
                lab_schedules[lab_room] = []
            lab_schedules[lab_room].append(schedule)
        
        cursor.close()
        conn.close()
        
        return render_template('student_lab_schedules.html', lab_schedules=lab_schedules)
        
    except Exception as e:
        logging.error(f"Error viewing lab schedules: {str(e)}")
        flash(f'Error viewing lab schedules: {str(e)}', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/edit-announcement', methods=['POST'])
@admin_required
def edit_announcement():
    """Edit an existing announcement"""
    try:
        # Get form data
        announcement_id = request.form.get('announcement_id')
        title = request.form.get('title')
        content = request.form.get('content')
        is_active = 'is_active' in request.form
        
        # Validate data
        if not announcement_id or not title or not content:
            flash('Announcement ID, title, and content are required', 'error')
            return redirect(url_for('view_announcements'))
        
        # Update the announcement in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE announcements 
            SET title = %s, content = %s, is_active = %s
            WHERE id = %s
        """, (title, content, is_active, announcement_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Announcement updated successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error updating announcement: {str(e)}")
        flash(f'Error updating announcement: {str(e)}', 'error')
    
    return redirect(url_for('view_announcements'))

@app.route('/toggle-announcement/<int:announcement_id>', methods=['POST'])
@admin_required
def toggle_announcement(announcement_id):
    """Toggle the active status of an announcement"""
    try:
        # Get the announcement
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current status first
        cursor.execute("SELECT is_active FROM announcements WHERE id = %s", (announcement_id,))
        announcement = cursor.fetchone()
        
        if not announcement:
            flash('Announcement not found', 'error')
            return redirect(url_for('view_announcements'))
        
        # Toggle the is_active status
        new_status = not announcement['is_active']
        
        cursor.execute("""
            UPDATE announcements 
            SET is_active = %s
            WHERE id = %s
        """, (new_status, announcement_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        status_text = "activated" if new_status else "deactivated"
        flash(f'Announcement {status_text} successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error toggling announcement: {str(e)}")
        flash(f'Error toggling announcement: {str(e)}', 'error')
    
    return redirect(url_for('view_announcements'))

@app.route('/delete-announcement/<int:announcement_id>', methods=['POST'])
@admin_required
def delete_announcement(announcement_id):
    """Delete an announcement"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete the announcement
        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Announcement deleted successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error deleting announcement: {str(e)}")
        flash(f'Error deleting announcement: {str(e)}', 'error')
    
    return redirect(url_for('view_announcements'))

@app.route('/lab-resources')
def lab_resources():
    """General endpoint for lab resources, redirects based on user type"""
    if 'user_type' not in session:
        flash('Please login to access this page', 'error')
        return redirect(url_for('index'))
    
    if session['user_type'] == 'admin':
        return redirect(url_for('admin_lab_resources'))
    else:
        return redirect(url_for('student_lab_resources'))

@app.route('/add_session', methods=['POST'])
@login_required
def add_session():
    """Add a new lab session reservation for students"""
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        # Get student ID from session
        student_id = session.get('user_id')
        
        # Get form data
        lab_room = request.form.get('lab_room')
        pc_number = request.form.get('pc_number')
        purpose = request.form.get('purpose')
        other_purpose = request.form.get('other_purpose')
        date_str = request.form.get('date')
        time_in = request.form.get('time_in')
        
        # Handle 'Other' purpose
        if purpose == 'Other' and other_purpose:
            purpose = other_purpose
        
        # Validate data
        if not lab_room or not pc_number or not purpose or not date_str or not time_in:
            flash('All fields are required for session reservation', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Combine date and time into a datetime object
        date_time_str = f"{date_str} {time_in}"
        date_time = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M')
        
        # Check if date is not in the past
        current_dt = datetime.now()
        if date_time < current_dt:
            flash('Reservation date and time cannot be in the past', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if student has sessions left
        cursor.execute("SELECT sessions_used, max_sessions FROM students WHERE id = %s", (student_id,))
        student_data = cursor.fetchone()
        
        if not student_data:
            flash('Student data not found', 'error')
            return redirect(url_for('student_dashboard'))
        
        if student_data['sessions_used'] >= student_data['max_sessions']:
            flash('You have used all your allotted sessions for this semester', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Check for overlapping reservations
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM sessions
            WHERE student_id = %s
            AND date_time BETWEEN %s AND DATE_ADD(%s, INTERVAL 1 HOUR)
            AND (status = 'pending' OR status = 'active')
        """, (student_id, date_time, date_time))
        
        overlapping = cursor.fetchone()
        if overlapping and overlapping['count'] > 0:
            flash('You already have a reservation at this time', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Check PC availability for the selected time
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM sessions
            WHERE lab_room = %s AND pc_number = %s
            AND date_time BETWEEN %s AND DATE_ADD(%s, INTERVAL 1 HOUR)
            AND (status = 'pending' OR status = 'active')
        """, (lab_room, pc_number, date_time, date_time))
        
        pc_booked = cursor.fetchone()
        if pc_booked and pc_booked['count'] > 0:
            flash('The selected PC is already booked for this time slot', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Add purpose prefix with PC number
        purpose_with_pc = f"{purpose} (PC #{pc_number})"
        
        # Insert the new session
        cursor.execute("""
            INSERT INTO sessions 
            (student_id, date_time, lab_room, pc_number, purpose, status, approval_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            student_id,
            date_time,
            lab_room,
            pc_number,
            purpose_with_pc,
            'pending',
            'pending',
            current_dt
        ))
        
        # Get the new session ID
        session_id = cursor.lastrowid
        
        # Log the activity
        cursor.execute("""
            INSERT INTO activity_logs 
            (student_id, lab_room, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            student_id,
            lab_room,
            'reservation_added',
            f'Session reservation created for {date_time_str} in {lab_room}',
            current_dt
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Session reservation submitted successfully. Waiting for admin approval.', 'success')
        return redirect(url_for('student_dashboard'))
        
    except Exception as e:
        logging.error(f"Error adding session: {str(e)}")
        flash(f'Error adding session: {str(e)}', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/cancel_session/<int:session_id>', methods=['POST'])
@login_required
def cancel_session(session_id):
    """Cancel a pending session reservation"""
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        student_id = session.get('user_id')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify session belongs to student and is pending
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE id = %s AND student_id = %s AND status = 'pending'
        """, (session_id, student_id))
        
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found or cannot be cancelled', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Update session status to cancelled
        cursor.execute("""
            UPDATE sessions 
            SET status = 'cancelled' 
            WHERE id = %s
        """, (session_id,))
        
        # Log the activity
        cursor.execute("""
            INSERT INTO activity_logs 
            (student_id, lab_room, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            student_id,
            session_data['lab_room'],
            'reservation_cancelled',
            f'Session reservation cancelled for {session_data["date_time"]}',
            datetime.now()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Session reservation cancelled successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error cancelling session: {str(e)}")
        flash(f'Error cancelling session: {str(e)}', 'error')
    
    return redirect(url_for('student_dashboard'))

@app.route('/submit_feedback/<int:session_id>', methods=['POST'])
@login_required
def submit_feedback(session_id):
    """Submit feedback for a completed session"""
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        # Get form data
        rating = request.form.get('rating')
        comments = request.form.get('comments')
        
        # Validate data
        if not rating:
            flash('Rating is required', 'error')
            return redirect(url_for('student_dashboard'))
        
        student_id = session.get('user_id')
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if session exists and belongs to student
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE id = %s AND student_id = %s AND status = 'completed'
        """, (session_id, student_id))
        
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found or not completed', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Check if feedback already exists for this session
        cursor.execute("""
            SELECT * FROM feedback 
            WHERE session_id = %s
        """, (session_id,))
        
        existing_feedback = cursor.fetchone()
        
        if existing_feedback:
            # Update existing feedback
            cursor.execute("""
                UPDATE feedback 
                SET rating = %s, comments = %s, updated_at = %s
                WHERE session_id = %s
            """, (rating, comments, datetime.now(), session_id))
            
            feedback_msg = 'Feedback updated successfully'
        else:
            # Create feedback table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    session_id INT NOT NULL,
                    rating INT NOT NULL,
                    comments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    UNIQUE KEY (session_id)
                )
            """)
            
            # Insert new feedback
            cursor.execute("""
                INSERT INTO feedback (student_id, session_id, rating, comments, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (student_id, session_id, rating, comments, datetime.now()))
            
            feedback_msg = 'Feedback submitted successfully'
        
        # Log the activity
        cursor.execute("""
            INSERT INTO activity_logs 
            (student_id, lab_room, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            student_id,
            session_data['lab_room'],
            'feedback_submitted',
            f'Feedback submitted for session {session_id}',
            datetime.now()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(feedback_msg, 'success')
        
    except Exception as e:
        logging.error(f"Error submitting feedback: {str(e)}")
        flash(f'Error submitting feedback: {str(e)}', 'error')
    
    return redirect(url_for('student_dashboard'))

@app.route('/sit_in_history')
@admin_required
def sit_in_history():
    """View all sit-in history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        lab_room = request.args.get('lab_room')
        status = request.args.get('status')
        
        # Base query
        query = """
            SELECT s.*, st.idno, st.firstname, st.lastname, st.course, st.year_level
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE 1=1
        """
        params = []
        
        # Add filters if provided
        if start_date and end_date:
            query += " AND DATE(s.date_time) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        if lab_room:
            query += " AND s.lab_room = %s"
            params.append(lab_room)
        
        if status:
            query += " AND s.status = %s"
            params.append(status)
        
        # Add ordering
        query += " ORDER BY s.date_time DESC LIMIT 1000"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        # Format dates for display
        for session_data in sessions:
            if session_data['date_time']:
                session_data['formatted_date'] = session_data['date_time'].strftime('%Y-%m-%d')
                session_data['formatted_time'] = session_data['date_time'].strftime('%H:%M')
            if session_data['check_in_time']:
                session_data['check_in_formatted'] = session_data['check_in_time'].strftime('%H:%M')
            if session_data['check_out_time']:
                session_data['check_out_formatted'] = session_data['check_out_time'].strftime('%H:%M')
        
        cursor.close()
        conn.close()
        
        return render_template(
            'sit_in_history.html', 
            sessions=sessions,
            start_date=start_date,
            end_date=end_date,
            lab_room=lab_room,
            status=status
        )
        
    except Exception as e:
        logging.error(f"Error viewing sit-in history: {str(e)}")
        flash(f"Error viewing sit-in history: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/export_sit_in_history')
@admin_required
def export_sit_in_history():
    """Export sit-in history to Excel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        lab_room = request.args.get('lab_room')
        status = request.args.get('status')
        
        # Base query
        query = """
            SELECT s.*, st.idno, st.firstname, st.lastname, st.course, st.year_level
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE 1=1
        """
        params = []
        
        # Add filters if provided
        if start_date and end_date:
            query += " AND DATE(s.date_time) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        if lab_room:
            query += " AND s.lab_room = %s"
            params.append(lab_room)
        
        if status:
            query += " AND s.status = %s"
            params.append(status)
        
        # Add ordering
        query += " ORDER BY s.date_time DESC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Create workbook
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Add styles
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'font_color': '#003366'
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 12
        })
        
        column_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#003366',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # Add university header (merged cells)
        worksheet.merge_range('A1:I1', 'UNIVERSITY OF CEBU', header_format)
        worksheet.merge_range('A2:I2', 'COLLEGE OF COMPUTER STUDIES', header_format)
        worksheet.merge_range('A3:I3', 'CSS SIT-IN MONITORING SYSTEM', header_format)
        
        # Add report title
        worksheet.merge_range('A5:I5', 'SIT-IN HISTORY REPORT', title_format)
        
        # Add date range if provided
        current_row = 6
        if start_date and end_date:
            worksheet.merge_range(f'A{current_row}:I{current_row}', f'Period: {start_date} to {end_date}', title_format)
            current_row += 1
        
        # Add generated date
        worksheet.merge_range(f'A{current_row}:I{current_row}', f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", title_format)
        current_row += 2
        
        # Add column headers
        headers = [
            'Student ID', 'Name', 'Course', 'Lab Room',
            'Date', 'Time', 'Check-in', 'Check-out', 'Status'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(current_row, col, header, column_header_format)
        
        # Set column widths
        worksheet.set_column('A:A', 15)  # Student ID
        worksheet.set_column('B:B', 25)  # Name
        worksheet.set_column('C:C', 10)  # Course
        worksheet.set_column('D:D', 15)  # Lab Room
        worksheet.set_column('E:E', 12)  # Date
        worksheet.set_column('F:F', 10)  # Time
        worksheet.set_column('G:G', 10)  # Check-in
        worksheet.set_column('H:H', 10)  # Check-out
        worksheet.set_column('I:I', 12)  # Status
        
        # Add data
        for row_idx, session_data in enumerate(sessions, start=current_row+1):
            # Format course
            course = session_data['course']
            if course == '1':
                course = 'BSIT'
            elif course == '2':
                course = 'BSCS'
            elif course == '3':
                course = 'BSCE'
            
            # Format dates
            date_str = ''
            time_str = ''
            check_in_str = ''
            check_out_str = ''
            
            if session_data['date_time']:
                date_str = session_data['date_time'].strftime('%Y-%m-%d')
                time_str = session_data['date_time'].strftime('%H:%M')
            
            if session_data['check_in_time']:
                check_in_str = session_data['check_in_time'].strftime('%H:%M')
            
            if session_data['check_out_time']:
                check_out_str = session_data['check_out_time'].strftime('%H:%M')
            
            # Write data to cells
            worksheet.write(row_idx, 0, session_data['idno'])
            worksheet.write(row_idx, 1, f"{session_data['firstname']} {session_data['lastname']}")
            worksheet.write(row_idx, 2, course)
            worksheet.write(row_idx, 3, session_data['lab_room'])
            worksheet.write(row_idx, 4, date_str)
            worksheet.write(row_idx, 5, time_str)
            worksheet.write(row_idx, 6, check_in_str)
            worksheet.write(row_idx, 7, check_out_str)
            worksheet.write(row_idx, 8, session_data['status'])
        
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"sit_in_history_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
        
    except Exception as e:
        logging.error(f"Error exporting sit-in history: {str(e)}")
        flash(f"Error exporting sit-in history: {str(e)}", 'error')
        return redirect(url_for('sit_in_history'))

@app.route('/export_sit_in_history_pdf')
@admin_required
def export_sit_in_history_pdf():
    """Export sit-in history to PDF"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        lab_room = request.args.get('lab_room')
        status = request.args.get('status')
        
        # Base query
        query = """
            SELECT s.*, st.idno, st.firstname, st.lastname, st.course, st.year_level
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE 1=1
        """
        params = []
        
        # Add filters if provided
        if start_date and end_date:
            query += " AND DATE(s.date_time) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        if lab_room:
            query += " AND s.lab_room = %s"
            params.append(lab_room)
        
        if status:
            query += " AND s.status = %s"
            params.append(status)
        
        # Add ordering
        query += " ORDER BY s.date_time DESC LIMIT 100"  # Limit to 100 rows for PDF
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format data for template
        for session_data in sessions:
            # Format course
            course = session_data['course']
            if course == '1':
                session_data['course_name'] = 'BSIT'
            elif course == '2':
                session_data['course_name'] = 'BSCS'
            elif course == '3':
                session_data['course_name'] = 'BSCE'
            else:
                session_data['course_name'] = course
            
            # Format dates
            if session_data['date_time']:
                session_data['date_str'] = session_data['date_time'].strftime('%Y-%m-%d')
                session_data['time_str'] = session_data['date_time'].strftime('%H:%M')
            else:
                session_data['date_str'] = ''
                session_data['time_str'] = ''
            
            if session_data['check_in_time']:
                session_data['check_in_str'] = session_data['check_in_time'].strftime('%H:%M')
            else:
                session_data['check_in_str'] = ''
            
            if session_data['check_out_time']:
                session_data['check_out_str'] = session_data['check_out_time'].strftime('%H:%M')
            else:
                session_data['check_out_str'] = ''
        
        # Use reportlab to create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Create elements list for PDF
        elements = []
        
        # Add university logo and header
        logo_path = os.path.join(app.static_folder, 'CSS.png')
        if os.path.exists(logo_path):
            from reportlab.platypus import Image
            logo = Image(logo_path, width=60, height=60)
            elements.append(logo)
            elements.append(Spacer(1, 10))
        
        # Add university header
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,  # Center
            spaceAfter=6
        )
        elements.append(Paragraph("UNIVERSITY OF CEBU", header_style))
        elements.append(Paragraph("COLLEGE OF COMPUTER STUDIES", header_style))
        elements.append(Paragraph("CSS SIT-IN MONITORING SYSTEM", header_style))
        elements.append(Spacer(1, 20))
        
        # Add title
        title_style = styles['Heading2']
        title_style.alignment = 1  # Center
        elements.append(Paragraph("Sit-In History Report", title_style))
        elements.append(Spacer(1, 12))
        
        # Add date range if provided
        if start_date and end_date:
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontSize=12,
                alignment=1  # Center
            )
            elements.append(Paragraph(f"Period: {start_date} to {end_date}", subtitle_style))
            elements.append(Spacer(1, 12))
        
        # Add generated date
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1  # Center
        )
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style))
        elements.append(Spacer(1, 20))
        
        # Create table data
        data = [
            ['Student ID', 'Name', 'Course', 'Lab Room', 'Date', 'Status']
        ]
        
        for session_data in sessions:
            data.append([
                session_data['idno'],
                f"{session_data['firstname']} {session_data['lastname']}",
                session_data.get('course_name', ''),
                session_data['lab_room'],
                session_data.get('date_str', ''),
                session_data['status']
            ])
        
        # Create table
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"sit_in_history_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        
    except Exception as e:
        logging.error(f"Error exporting sit-in history to PDF: {str(e)}")
        flash(f"Error exporting sit-in history to PDF: {str(e)}", 'error')
        return redirect(url_for('sit_in_history'))

@app.route('/export_sit_in_history_csv')
@admin_required
def export_sit_in_history_csv():
    """Export sit-in history to CSV"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        lab_room = request.args.get('lab_room')
        status = request.args.get('status')
        
        # Base query
        query = """
            SELECT s.*, st.idno, st.firstname, st.lastname, st.course, st.year_level
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE 1=1
        """
        params = []
        
        # Add filters if provided
        if start_date and end_date:
            query += " AND DATE(s.date_time) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        if lab_room:
            query += " AND s.lab_room = %s"
            params.append(lab_room)
        
        if status:
            query += " AND s.status = %s"
            params.append(status)
        
        # Add ordering
        query += " ORDER BY s.date_time DESC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Add header rows
        writer.writerow(['UNIVERSITY OF CEBU'])
        writer.writerow(['COLLEGE OF COMPUTER STUDIES'])
        writer.writerow(['CSS SIT-IN MONITORING SYSTEM'])
        writer.writerow([])
        
        # Add title row
        writer.writerow(['SIT-IN HISTORY REPORT'])
        
        # Add date range if provided
        if start_date and end_date:
            writer.writerow([f"Period: {start_date} to {end_date}"])
        writer.writerow([f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
        writer.writerow([])
        
        # Add column headers
        writer.writerow(['Student ID', 'Name', 'Course', 'Lab Room', 'Date', 'Time', 'Check-in', 'Check-out', 'Status'])
        
        # Add data rows
        for session in sessions:
            # Format course
            course = session['course']
            if course == '1':
                course_name = 'BSIT'
            elif course == '2':
                course_name = 'BSCS'
            elif course == '3':
                course_name = 'BSCE'
            else:
                course_name = course
            
            date_str = ''
            time_str = ''
            check_in_str = ''
            check_out_str = ''
            
            if session['date_time']:
                date_str = session['date_time'].strftime('%Y-%m-%d')
                time_str = session['date_time'].strftime('%H:%M')
            
            if session['check_in_time']:
                check_in_str = session['check_in_time'].strftime('%H:%M')
            
            if session['check_out_time']:
                check_out_str = session['check_out_time'].strftime('%H:%M')
            
            writer.writerow([
                session['idno'],
                f"{session['firstname']} {session['lastname']}",
                course_name,
                session['lab_room'],
                date_str,
                time_str,
                check_in_str,
                check_out_str,
                session['status']
            ])
        
        # Prepare response
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=sit_in_history_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    
    except Exception as e:
        logging.error(f"Error exporting sit-in history to CSV: {str(e)}")
        flash(f"Error exporting sit-in history to CSV: {str(e)}", 'error')
        return redirect(url_for('sit_in_history'))

@app.route('/check_in_student/<int:session_id>', methods=['POST'])
@admin_required
def check_in_student(session_id):
    """Check in a student for their session"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get the session data
        cursor.execute("""
            SELECT s.*, st.firstname, st.lastname, st.id as student_id
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE s.id = %s
        """, (session_id,))
        
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Only allow check-in for approved sessions
        if session_data['approval_status'] != 'approved' and session_data['status'] != 'pending':
            flash('Session is not approved or already checked in', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Record check-in time
        current_time = datetime.now()
        
        cursor.execute("""
            UPDATE sessions 
            SET status = 'active', check_in_time = %s 
            WHERE id = %s
        """, (current_time, session_id))
        
        # Update PC status to occupied if PC number is provided
        if session_data.get('pc_number'):
            pc_number = session_data['pc_number']
            lab_room = session_data['lab_room']
            student_id = session_data['student_id']
            
            # Special handling for PC 0 (ensure it's a string)
            if pc_number == 0 or pc_number == '0':
                pc_number = '0'
                logging.info(f"Handling PC #0 specifically during check-in")
            
            # Check if PC exists in status table
            cursor.execute("SELECT * FROM pc_status WHERE lab_room = %s AND pc_number = %s", 
                          (lab_room, pc_number))
            pc = cursor.fetchone()
            
            if pc:
                # Update PC status to occupied and set student_id
                cursor.execute("""
                    UPDATE pc_status 
                    SET status = 'occupied', student_id = %s 
                    WHERE lab_room = %s AND pc_number = %s
                """, (student_id, lab_room, pc_number))
            else:
                # Create new PC status entry
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, %s, 'occupied', %s)
                """, (lab_room, pc_number, student_id))
                
            logging.info(f"Updated PC #{pc_number} in {lab_room} to occupied for student check-in")
        
        # Log the activity
        cursor.execute("""
            INSERT INTO activity_logs 
            (student_id, lab_room, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session_data['student_id'],
            session_data['lab_room'],
            'student_checked_in',
            f"Student {session_data['firstname']} {session_data['lastname']} checked in",
            current_time
        ))
        
        conn.commit()
        flash('Student checked in successfully', 'success')
        
        cursor.close()
        conn.close()
        
        return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        logging.error(f"Error checking in student: {str(e)}")
        flash(f'Error checking in student: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/check_out_student/<int:session_id>', methods=['POST'])
@admin_required
def check_out_student(session_id):
    """Check out a student from their session"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get the session data
        cursor.execute("""
            SELECT s.*, st.firstname, st.lastname, st.id as student_id
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE s.id = %s
        """, (session_id,))
        
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Only allow check-out for active sessions
        if session_data['status'] != 'active':
            flash('Session is not active', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Record check-out time
        current_time = datetime.now()
        
        # Calculate duration in minutes
        check_in_time = session_data['check_in_time']
        if check_in_time:
            duration_minutes = int((current_time - check_in_time).total_seconds() / 60)
        else:
            duration_minutes = 0
        
        # Update session status and increment sessions_used
        cursor.execute("""
            UPDATE sessions 
            SET status = 'completed', check_out_time = %s, duration = %s 
            WHERE id = %s
        """, (current_time, duration_minutes, session_id))
        
        # Increment the sessions_used count for the student
        cursor.execute("""
            UPDATE students 
            SET sessions_used = sessions_used + 1 
            WHERE id = %s
        """, (session_data['student_id'],))
        
        # Get PC number and handle PC status update
        pc_number = session_data.get('pc_number')
        
        # If not found, try to extract it from purpose field
        if not pc_number and session_data.get('purpose'):
            import re
            pc_match = re.search(r'PC #(\d+)', session_data['purpose'])
            if pc_match:
                pc_number = pc_match.group(1)
                logging.info(f"Extracted PC number {pc_number} from purpose: {session_data['purpose']}")
        
        # Update PC status if a PC number was provided
        if pc_number:
            lab_room = session_data['lab_room']
            
            # Only update PC status to vacant if it's not in maintenance mode
            cursor.execute("""
                UPDATE pc_status 
                SET status = CASE WHEN status != 'maintenance' THEN 'vacant' ELSE status END,
                    student_id = NULL
                WHERE lab_room = %s AND pc_number = %s
            """, (lab_room, pc_number))
            
            logging.info(f"Updated PC #{pc_number} in {lab_room} to vacant after student checkout")
            
            # If no rows were updated, create the PC status record
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status)
                    VALUES (%s, %s, 'vacant')
                """, (lab_room, pc_number))
                logging.info(f"Created new vacant PC status for PC #{pc_number} in {lab_room}")
        
        # Log the activity
        try:
            cursor.execute("""
                INSERT INTO activity_logs (user_id, student_id, lab_room, action, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                session.get('user_id', 0),
                session_data['student_id'],
                session_data['lab_room'],
                'check_out',
                f"Checked out {session_data['firstname']} {session_data['lastname']} from session in {session_data['lab_room']} (Duration: {duration_minutes} min)",
                current_time
            ))
        except Exception as e:
            logging.error(f"Error logging activity: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f"Successfully checked out {session_data['firstname']} {session_data['lastname']}", 'success')
        
        # Determine the redirect target
        if request.referrer and 'todays_sit_ins' in request.referrer:
            return redirect(url_for('todays_sit_ins'))
        else:
            return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        logging.error(f"Error checking out student: {str(e)}")
        flash(f"Error checking out student: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin_lab_schedules')
@admin_required
def admin_lab_schedules():
    """View and manage lab schedules for admin"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all lab schedules
        cursor.execute("""
            SELECT * FROM lab_schedules
            ORDER BY lab_room, day_of_week, start_time
        """)
        
        schedules = cursor.fetchall()
        
        # Get the current semester term (if set) - handle case where semester_term column doesn't exist
        try:
            cursor.execute("""
                SELECT DISTINCT semester_term FROM lab_schedules
                WHERE semester_term IS NOT NULL AND semester_term != ''
                ORDER BY created_at DESC
                LIMIT 1
            """)
            current_term_result = cursor.fetchone()
            current_term = current_term_result['semester_term'] if current_term_result else "Current Semester"
        except Exception as term_error:
            # If semester_term column doesn't exist, use a default value
            current_term = "Current Semester"
        
        # Group schedules by lab room
        lab_schedules = {}
        for schedule in schedules:
            lab_room = schedule['lab_room']
            if lab_room not in lab_schedules:
                lab_schedules[lab_room] = []
            
            # Format times
            if schedule['start_time']:
                hour = schedule['start_time'].seconds // 3600
                minute = (schedule['start_time'].seconds % 3600) // 60
                am_pm = 'AM' if hour < 12 else 'PM'
                display_hour = hour if hour <= 12 else hour - 12
                if hour == 0:
                    display_hour = 12
                schedule['start_time_formatted'] = f"{display_hour}:{minute:02d} {am_pm}"
            else:
                schedule['start_time_formatted'] = ''
                
            if schedule['end_time']:
                hour = schedule['end_time'].seconds // 3600
                minute = (schedule['end_time'].seconds % 3600) // 60
                am_pm = 'AM' if hour < 12 else 'PM'
                display_hour = hour if hour <= 12 else hour - 12
                if hour == 0:
                    display_hour = 12
                schedule['end_time_formatted'] = f"{display_hour}:{minute:02d} {am_pm}"
            else:
                schedule['end_time_formatted'] = ''
            
            # Map day number to name
            day_map = {
                0: 'Monday',
                1: 'Tuesday',
                2: 'Wednesday',
                3: 'Thursday',
                4: 'Friday',
                5: 'Saturday',
                6: 'Sunday'
            }
            schedule['day_name'] = day_map.get(schedule['day_of_week'], '')
            
            lab_schedules[lab_room].append(schedule)
        
        cursor.close()
        conn.close()
        
        # Define lab rooms for dropdown
        lab_rooms = [
            {'code': 'Lab 1', 'name': 'Lab 524'},
            {'code': 'Lab 2', 'name': 'Lab 526'},
            {'code': 'Lab 3', 'name': 'Lab 528'},
            {'code': 'Lab 4', 'name': 'Lab 530'},
            {'code': 'Lab 5', 'name': 'Lab 532'},
            {'code': 'Lab 6', 'name': 'Lab 540'},
            {'code': 'Lab 7', 'name': 'Lab 544'}
        ]
        
        return render_template(
            'admin_lab_schedules.html', 
            lab_schedules=lab_schedules,
            schedules=schedules,
            lab_rooms=lab_rooms,
            current_term=current_term
        )
        
    except Exception as e:
        logging.error(f"Error viewing lab schedules: {str(e)}")
        flash(f"Error viewing lab schedules: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/edit_lab_schedule/<int:schedule_id>', methods=['GET', 'POST'])
@admin_required
def edit_lab_schedule(schedule_id):
    """Edit an existing lab schedule"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            # Get form data
            lab_room = request.form.get('lab_room')
            day_of_week = request.form.get('day_of_week')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            course_name = request.form.get('course_name')
            instructor = request.form.get('instructor')
            semester_term = request.form.get('semester_term')
            is_active = 'is_active' in request.form
            
            # Validate data
            if not lab_room or not day_of_week or not start_time or not end_time:
                flash('Lab room, day, start time, and end time are required', 'error')
                return redirect(url_for('edit_lab_schedule', schedule_id=schedule_id))
            
            # Update the schedule
            cursor.execute("""
                UPDATE lab_schedules
                SET lab_room = %s, day_of_week = %s, start_time = %s, end_time = %s,
                    course_name = %s, instructor = %s, semester_term = %s, is_active = %s
                WHERE id = %s
            """, (
                lab_room, 
                day_of_week, 
                start_time, 
                end_time, 
                course_name, 
                instructor, 
                semester_term,
                is_active,
                schedule_id
            ))
            
            conn.commit()
            flash('Schedule updated successfully', 'success')
            return redirect(url_for('admin_lab_schedules'))
        
        else:
            # Get the schedule data for editing
            cursor.execute("SELECT * FROM lab_schedules WHERE id = %s", (schedule_id,))
            schedule = cursor.fetchone()
            
            if not schedule:
                flash('Schedule not found', 'error')
                return redirect(url_for('admin_lab_schedules'))
            
            cursor.close()
            conn.close()
            
            return render_template('edit_lab_schedule.html', schedule=schedule)
            
    except Exception as e:
        logging.error(f"Error editing lab schedule: {str(e)}")
        flash(f"Error editing lab schedule: {str(e)}", 'error')
        return redirect(url_for('admin_lab_schedules'))

@app.route('/add_lab_schedule', methods=['POST'])
@admin_required
def add_lab_schedule():
    """Add a new lab schedule"""
    try:
        # Get form data
        lab_room = request.form.get('lab_room')
        day_of_week = request.form.get('day_of_week')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        course_name = request.form.get('course_name')
        instructor = request.form.get('instructor')
        semester_term = request.form.get('semester_term')
        
        # Validate data
        if not lab_room or not day_of_week or not start_time or not end_time:
            flash('Lab room, day, start time, and end time are required', 'error')
            return redirect(url_for('admin_lab_schedules'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create the lab_schedules table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lab_room VARCHAR(50) NOT NULL,
                day_of_week TINYINT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                course_name VARCHAR(255),
                instructor VARCHAR(255),
                semester_term VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Insert new schedule
        cursor.execute("""
            INSERT INTO lab_schedules 
            (lab_room, day_of_week, start_time, end_time, course_name, instructor, semester_term, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
        """, (
            lab_room, 
            day_of_week, 
            start_time, 
            end_time, 
            course_name, 
            instructor, 
            semester_term
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Schedule added successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error adding lab schedule: {str(e)}")
        flash(f"Error adding lab schedule: {str(e)}", 'error')
    
    return redirect(url_for('admin_lab_schedules'))

@app.route('/delete_lab_schedule/<int:schedule_id>', methods=['POST'])
@admin_required
def delete_lab_schedule(schedule_id):
    """Delete a lab schedule"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM lab_schedules WHERE id = %s", (schedule_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Schedule deleted successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error deleting lab schedule: {str(e)}")
        flash(f"Error deleting lab schedule: {str(e)}", 'error')
    
    return redirect(url_for('admin_lab_schedules'))

@app.route('/update_record', methods=['POST'])
@login_required
def update_record():
    """Update a student record (used by admin)"""
    if session.get('user_type') != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        # Get form data
        student_id = request.form.get('student_id')
        idno = request.form.get('idno')
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        middlename = request.form.get('middlename', '')
        course = request.form.get('course')
        year_level = request.form.get('year_level')
        email = request.form.get('email')
        contact_number = request.form.get('contact_number', '')
        max_sessions = request.form.get('max_sessions')
        
        # Validate data
        if not student_id or not idno or not firstname or not lastname or not course or not year_level:
            flash('ID Number, Name, Course, and Year Level are required', 'error')
            return redirect(url_for('admin_dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if idno already exists for another student
        cursor.execute("SELECT * FROM students WHERE idno = %s AND id != %s", (idno, student_id))
        existing = cursor.fetchone()
        
        if existing:
            flash('ID Number already exists for another student', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Process profile picture if uploaded
        profile_picture = None
        if 'profile_picture' in request.files and request.files['profile_picture'].filename:
            file = request.files['profile_picture']
            
            # Check if it's an allowed file type
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Generate a unique filename to prevent overwriting
                file_extension = os.path.splitext(filename)[1]
                unique_filename = str(uuid.uuid4()) + file_extension
                
                # Ensure profile_pictures directory exists
                profile_pic_dir = os.path.join('static', 'profile_pictures')
                os.makedirs(profile_pic_dir, exist_ok=True)
                
                # Save the file
                file_path = os.path.join(profile_pic_dir, unique_filename)
                file.save(file_path)
                
                profile_picture = unique_filename
        
        # Build the update query based on what's being updated
        update_fields = []
        params = []
        
        update_fields.append("idno = %s")
        params.append(idno)
        
        update_fields.append("firstname = %s")
        params.append(firstname)
        
        update_fields.append("lastname = %s")
        params.append(lastname)
        
        update_fields.append("middlename = %s")
        params.append(middlename)
        
        update_fields.append("course = %s")
        params.append(course)
        
        update_fields.append("year_level = %s")
        params.append(year_level)
        
        update_fields.append("email = %s")
        params.append(email)
        
        update_fields.append("contact_number = %s")
        params.append(contact_number)
        
        if max_sessions:
            update_fields.append("max_sessions = %s")
            params.append(max_sessions)
        
        if profile_picture:
            update_fields.append("profile_picture = %s")
            params.append(profile_picture)
        
        # Execute the update
        query = "UPDATE students SET " + ", ".join(update_fields) + " WHERE id = %s"
        params.append(student_id)
        
        cursor.execute(query, params)
        
        # Log the activity
        try:
            cursor.execute("""
                INSERT INTO activity_logs 
                (user_id, student_id, action, details, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session.get('user_id', 0),
                student_id,
                'student_updated',
                f"Student record updated: {firstname} {lastname} ({idno})",
                datetime.now()
            ))
        except Exception as e:
            # Don't fail if logging fails
            logging.error(f"Error logging activity: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f"Student {firstname} {lastname} updated successfully", 'success')
        
    except Exception as e:
        logging.error(f"Error updating student record: {str(e)}")
        flash(f"Error updating student record: {str(e)}", 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/get_pc_status')
@admin_required
def get_pc_status():
    """Get PC status for a lab room (Admin view)"""
    try:
        lab_room = request.args.get('lab_room')
        if not lab_room:
            return jsonify({'error': 'Lab room is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First check if student_id column exists in pc_status table
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'pc_status' 
            AND COLUMN_NAME = 'student_id'
        """)
        
        has_student_id = cursor.fetchone() is not None
        
        # Create pc_status table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pc_status (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lab_room VARCHAR(50) NOT NULL,
                pc_number VARCHAR(10) NOT NULL,
                status VARCHAR(20) DEFAULT 'vacant',
                student_id INT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY (lab_room, pc_number),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
            )
        """)
        
        # Get PC status for the lab room with appropriate columns
        if has_student_id:
            cursor.execute("""
                SELECT pc_number, status, student_id
                FROM pc_status
                WHERE lab_room = %s
            """, (lab_room,))
        else:
            cursor.execute("""
                SELECT pc_number, status, NULL as student_id
                FROM pc_status
                WHERE lab_room = %s
            """, (lab_room,))
        
        pc_status = cursor.fetchall()
        
        # Check if there are active sessions with PCs in this lab room not in pc_status
        cursor.execute("""
            SELECT s.pc_number, 'occupied' as status, s.student_id
            FROM sessions s
            WHERE s.lab_room = %s 
            AND s.status = 'active'
            AND s.pc_number IS NOT NULL
            AND s.pc_number != ''
        """, (lab_room,))
        
        active_pcs = cursor.fetchall()
        
        # Add any PCs from active sessions that aren't in pc_status
        pc_status_dict = {pc['pc_number']: pc for pc in pc_status}
        
        for active_pc in active_pcs:
            pc_num = active_pc['pc_number']
            
            # If this PC is not in pc_status or is marked as vacant, update it
            if pc_num not in pc_status_dict or pc_status_dict[pc_num]['status'] != 'occupied':
                logging.info(f"Found active session for PC #{pc_num} but PC status was {pc_status_dict.get(pc_num, {}).get('status', 'not found')}")
                
                # Add or update the PC status in the database
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, %s, 'occupied', %s)
                    ON DUPLICATE KEY UPDATE status = 'occupied', student_id = %s
                """, (lab_room, pc_num, active_pc['student_id'], active_pc['student_id']))
                
                # Also update our local copy
                if pc_num in pc_status_dict:
                    pc_status_dict[pc_num]['status'] = 'occupied'
                    pc_status_dict[pc_num]['student_id'] = active_pc['student_id']
                else:
                    pc_status_dict[pc_num] = active_pc
        
        # Re-query to get up-to-date PC status
        if has_student_id:
            cursor.execute("""
                SELECT pc_number, status, student_id
                FROM pc_status
                WHERE lab_room = %s
            """, (lab_room,))
        else:
            cursor.execute("""
                SELECT pc_number, status, NULL as student_id
                FROM pc_status
                WHERE lab_room = %s
            """, (lab_room,))
        
        pc_status = cursor.fetchall()
        
        # Ensure we have all PC numbers from 0 to 30 for the selected lab room
        existing_pc_numbers = {pc['pc_number'] for pc in pc_status}
        
        # Default number of PCs per lab room
        num_pcs = 30
        
        # Initialize missing PCs with default status (vacant)
        for i in range(0, num_pcs + 1):  # Range from 0 to 30 to include PC 0
            pc_num = str(i)
            if pc_num not in existing_pc_numbers:
                cursor.execute("""
                    INSERT IGNORE INTO pc_status (lab_room, pc_number, status)
                    VALUES (%s, %s, 'vacant')
                """, (lab_room, pc_num))
                
                pc_status.append({
                    'pc_number': pc_num, 
                    'status': 'vacant',
                    'student_id': None
                })
                
        conn.commit()
        
        # Re-query after adding missing PCs to ensure we have the latest data
        if has_student_id:
            cursor.execute("""
                SELECT pc_number, status, student_id
                FROM pc_status
                WHERE lab_room = %s
                ORDER BY CAST(pc_number AS UNSIGNED)
            """, (lab_room,))
        else:
            cursor.execute("""
                SELECT pc_number, status, NULL as student_id
                FROM pc_status
                WHERE lab_room = %s
                ORDER BY CAST(pc_number AS UNSIGNED)
            """, (lab_room,))
        
        pc_status = cursor.fetchall()
        
        # Check for PC 0 if it's not in the results
        pc_numbers = {pc['pc_number'] for pc in pc_status}
        if '0' not in pc_numbers:
            # Check if PC 0 has any active sessions
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM sessions
                WHERE lab_room = %s AND pc_number = '0' AND status = 'active'
            """, (lab_room,))
            
            has_active_pc0 = cursor.fetchone()['count'] > 0
            
            if has_active_pc0:
                # If PC 0 has active sessions, add it as occupied
                cursor.execute("""
                    SELECT s.student_id
                    FROM sessions s
                    WHERE s.lab_room = %s AND s.pc_number = '0' AND s.status = 'active'
                    LIMIT 1
                """, (lab_room,))
                
                student_data = cursor.fetchone()
                student_id = student_data['student_id'] if student_data else None
                
                # Add PC 0 to the pc_status table
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, '0', 'occupied', %s)
                """, (lab_room, student_id))
                
                # Add it to our results
                pc_status.append({
                    'pc_number': '0', 
                    'status': 'occupied',
                    'student_id': student_id
                })
                
                logging.info(f"Added missing PC #0 in {lab_room} with occupied status")
            else:
                # If PC 0 doesn't have active sessions, add it as vacant
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, '0', 'vacant', NULL)
                """, (lab_room, ))
                
                # Add it to our results
                pc_status.append({
                    'pc_number': '0', 
                    'status': 'vacant',
                    'student_id': None
                })
                
                logging.info(f"Added missing PC #0 in {lab_room} with vacant status")
                
            conn.commit()
        
        # Get student info for occupied PCs
        pc_data = {}
        for pc in pc_status:
            pc_info = {
                'status': pc['status'],
                'student_id': pc['student_id'] if 'student_id' in pc else None,
                'student_name': None,
                'student_idno': None
            }
            
            if 'student_id' in pc and pc['student_id'] and pc['status'] == 'occupied':
                cursor.execute("""
                    SELECT firstname, lastname, idno
                    FROM students
                    WHERE id = %s
                """, (pc['student_id'],))
                
                student = cursor.fetchone()
                if student:
                    pc_info['student_name'] = f"{student['firstname']} {student['lastname']}"
                    pc_info['student_idno'] = student['idno']
            
            pc_data[pc['pc_number']] = pc_info
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'lab_room': lab_room, 'pc_status': pc_data})
        
    except Exception as e:
        logging.error(f"Error getting PC status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/student/get_pc_status')
@login_required
def student_get_pc_status():
    """Get PC status for a lab room (Student view)"""
    try:
        if session.get('user_type') != 'student':
            return jsonify({'error': 'Access denied'}), 403
            
        lab_room = request.args.get('lab_room')
        if not lab_room:
            return jsonify({'error': 'Lab room is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Create pc_status table if it doesn't exist with proper schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pc_status (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lab_room VARCHAR(50) NOT NULL,
                pc_number VARCHAR(10) NOT NULL,
                status VARCHAR(20) DEFAULT 'vacant',
                student_id INT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY (lab_room, pc_number),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
            )
        """)
        conn.commit()
        
        # First check if student_id column exists in pc_status table
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'pc_status' 
            AND COLUMN_NAME = 'student_id'
        """)
        
        has_student_id = cursor.fetchone() is not None
        
        # If student_id column doesn't exist, add it
        if not has_student_id:
            try:
                cursor.execute("""
                    ALTER TABLE pc_status
                    ADD COLUMN student_id INT,
                    ADD FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
                """)
                conn.commit()
            except Exception as e:
                logging.error(f"Error adding student_id column: {str(e)}")
        
        # Get PC status for the lab room
        cursor.execute("""
            SELECT pc_number, status
            FROM pc_status
            WHERE lab_room = %s
        """, (lab_room,))
        
        pc_status = cursor.fetchall()
        
        # If no PCs are in the database for this lab, initialize with defaults
        if not pc_status:
            pc_status = []
            
        # Ensure we have all PC numbers from 1 to 30 for the selected lab room
        existing_pc_numbers = {pc['pc_number'] for pc in pc_status}
        
        # Default number of PCs per lab room
        num_pcs = 30
        
        # Initialize missing PCs with default status (vacant)
        for i in range(0, num_pcs + 1):  # Changed from range(1, num_pcs + 1) to include PC 0
            pc_num = str(i)
            if pc_num not in existing_pc_numbers:
                cursor.execute("""
                    INSERT IGNORE INTO pc_status (lab_room, pc_number, status)
                    VALUES (%s, %s, 'vacant')
                """, (lab_room, pc_num))
                
                pc_status.append({'pc_number': pc_num, 'status': 'vacant'})
        
        conn.commit()
        
        # Get updated status after insertions
        cursor.execute("""
            SELECT pc_number, status
            FROM pc_status
            WHERE lab_room = %s
            ORDER BY CAST(pc_number AS UNSIGNED)
        """, (lab_room,))
        
        pc_status = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'lab_room': lab_room, 'pc_status': pc_status})
        
    except Exception as e:
        logging.error(f"Error getting PC status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/update_pc_status', methods=['POST'])
@admin_required
def update_pc_status():
    """Update PC status by admin"""
    try:
        # Check if the data is coming from form or JSON
        content_type = request.headers.get('Content-Type', '')
        
        if 'application/json' in content_type:
            data = request.json
        else:
            # Handle form data
            data = request.form
        
        lab_room = data.get('lab_room')
        pc_number = data.get('pc_number')
        new_status = data.get('status')
        is_bulk = data.get('is_bulk') == 'true'
        
        if not lab_room or not new_status:
            return jsonify({'error': 'Lab room and status are required'}), 400
            
        # For bulk operations, we don't need a PC number
        if not pc_number and not is_bulk:
            return jsonify({'error': 'PC number is required for individual updates'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if student_id column exists in pc_status table
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'pc_status' 
            AND COLUMN_NAME = 'student_id'
        """)
        
        has_student_id = cursor.fetchone() is not None
        
        # If student_id column doesn't exist, add it
        if not has_student_id:
            try:
                cursor.execute("""
                    ALTER TABLE pc_status
                    ADD COLUMN student_id INT,
                    ADD FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
                """)
                conn.commit()
            except Exception as e:
                logging.error(f"Error adding student_id column: {str(e)}")
        
        # Handle bulk operations
        if is_bulk:
            # Update all PCs in the lab room
            if has_student_id:
                cursor.execute("""
                    UPDATE pc_status 
                    SET status = %s, student_id = NULL
                    WHERE lab_room = %s
                """, (new_status, lab_room))
            else:
                cursor.execute("""
                    UPDATE pc_status 
                    SET status = %s
                    WHERE lab_room = %s
                """, (new_status, lab_room))
            
            # Make sure PC 0 is included in the table after bulk update
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM pc_status
                WHERE lab_room = %s AND pc_number = '0'
            """, (lab_room,))
            
            result = cursor.fetchone()
            has_pc0 = result['count'] if isinstance(result, dict) else result[0] > 0
            
            if not has_pc0:
                # Add PC 0 if it doesn't exist
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, '0', %s, NULL)
                """, (lab_room, new_status))
                
                logging.info(f"Added missing PC #0 in {lab_room} during bulk update with {new_status} status")
                
            # Also update sessions with PC 0 if we're marking all PCs as vacant/available
            if new_status in ['vacant', 'available']:
                # Get sessions with PC 0 that are active
                cursor.execute("""
                    SELECT id FROM sessions 
                    WHERE lab_room = %s AND pc_number = '0' AND status = 'active'
                """, (lab_room,))
                
                active_sessions = cursor.fetchall()
                current_time = datetime.now()
                
                # Update these sessions to completed if we're marking all PCs as vacant/available
                for session_record in active_sessions:
                    session_id = session_record['id'] if isinstance(session_record, dict) else session_record[0]
                    cursor.execute("""
                        UPDATE sessions 
                        SET status = 'completed', check_out_time = %s
                        WHERE id = %s
                    """, (current_time, session_id))
                    
                    logging.info(f"Auto-completed session #{session_id} for PC 0 during bulk PC update")
                
            conn.commit()
                
            # Log the activity for bulk update
            try:
                details = f"All PCs in {lab_room} set to {new_status}"
                cursor.execute("""
                    INSERT INTO activity_logs (user_id, lab_room, action, details, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    session.get('user_id', 0),
                    lab_room,
                    'pc_status_bulk_updated',
                    details,
                    datetime.now()
                ))
            except Exception as e:
                logging.error(f"Error logging bulk PC status update: {str(e)}")
        else:
            # Update individual PC
            if has_student_id:
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, %s, %s, NULL)
                    ON DUPLICATE KEY UPDATE status = %s, student_id = NULL
                """, (lab_room, pc_number, new_status, new_status))
            else:
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = %s
                """, (lab_room, pc_number, new_status, new_status))
            
            # Log the activity for individual update
            try:
                details = f"PC #{pc_number} in {lab_room} set to {new_status}"
                cursor.execute("""
                    INSERT INTO activity_logs (user_id, lab_room, action, details, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    session.get('user_id', 0),
                    lab_room,
                    'pc_status_updated',
                    details,
                    datetime.now()
                ))
            except Exception as e:
                logging.error(f"Error logging PC status update: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'PC status updated to {new_status}'})
        
    except Exception as e:
        logging.error(f"Error updating PC status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_student_info/<int:student_id>')
@admin_required
def get_student_info(student_id):
    """Get student information"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get student information
        cursor.execute("""
            SELECT * FROM students WHERE id = %s
        """, (student_id,))
        
        student = cursor.fetchone()
        
        if not student:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Format data for response
        response_data = {
            'id': student['id'],
            'idno': student['idno'],
            'firstname': student['firstname'],
            'lastname': student['lastname'],
            'middlename': student.get('middlename', ''),
            'course': student['course'],
            'year_level': student['year_level'],
            'email': student.get('email', ''),
            'contact_number': student.get('contact_number', ''),
            'profile_picture': student.get('profile_picture', 'default.jpg'),
            'sessions_used': student.get('sessions_used', 0),
            'max_sessions': student.get('max_sessions', 0),
            'points': student.get('points', 0),
            'total_points': student.get('total_points', 0)
        }
        
        # Add course name
        if student['course'] == '1':
            response_data['course_name'] = 'BSIT'
        elif student['course'] == '2':
            response_data['course_name'] = 'BSCS'
        elif student['course'] == '3':
            response_data['course_name'] = 'BSCE'
        else:
            response_data['course_name'] = student['course']
        
        # Get sessions information
        cursor.execute("""
            SELECT COUNT(*) as total_sessions,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                   COUNT(CASE WHEN status = 'pending' AND approval_status = 'pending' THEN 1 END) as pending_sessions,
                   COUNT(CASE WHEN status = 'active' THEN 1 END) as active_sessions
            FROM sessions
            WHERE student_id = %s
        """, (student_id,))
        
        sessions_data = cursor.fetchone()
        response_data.update(sessions_data)
        
        cursor.close()
        conn.close()
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Error getting student info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/add_announcement', methods=['POST'])
@admin_required
def admin_add_announcement():
    """Add a new announcement (Admin route)"""
    try:
        # Get form data
        title = request.form.get('title')
        content = request.form.get('content')
        
        # Validate data
        if not title or not content:
            flash('Title and content are required', 'error')
            return redirect(url_for('view_announcements'))
        
        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO announcements (title, content, created_at)
            VALUES (%s, %s, %s)
        """, (title, content, datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Announcement added successfully', 'success')
        
    except Exception as e:
        logging.error(f"Error adding announcement: {str(e)}")
        flash(f'Error adding announcement: {str(e)}', 'error')
    
    # Check if the request is from admin_dashboard or view_announcements
    referrer = request.referrer or ''
    if 'admin_dashboard' in referrer:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('view_announcements'))

@app.route('/combined_lab_schedules')
@login_required
def combined_lab_schedules():
    """View combined lab schedules in calendar format"""
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all lab schedules - removed is_active filter that was causing errors
        cursor.execute("""
            SELECT * FROM lab_schedules
            ORDER BY day_of_week, start_time
        """)
        
        schedules = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format schedules for the calendar
        calendar_events = []
        day_map = {
            0: 'Monday',
            1: 'Tuesday',
            2: 'Wednesday',
            3: 'Thursday',
            4: 'Friday',
            5: 'Saturday',
            6: 'Sunday'
        }
        
        for schedule in schedules:
            start_time = ''
            end_time = ''
            
            if schedule['start_time']:
                hour = schedule['start_time'].seconds // 3600
                minute = (schedule['start_time'].seconds % 3600) // 60
                start_time = f"{hour:02d}:{minute:02d}"
            
            if schedule['end_time']:
                hour = schedule['end_time'].seconds // 3600
                minute = (schedule['end_time'].seconds % 3600) // 60
                end_time = f"{hour:02d}:{minute:02d}"
            
            event = {
                'id': schedule['id'],
                'title': f"{schedule.get('subject', 'Class')} - {schedule['lab_room']}",
                'start': start_time,
                'end': end_time,
                'day': schedule['day_of_week'],
                'day_name': day_map.get(schedule['day_of_week'], ''),
                'instructor': schedule.get('instructor', ''),
                'lab_room': schedule['lab_room'],
                'description': f"Instructor: {schedule.get('instructor', 'N/A')}"
            }
            
            calendar_events.append(event)
        
        return render_template(
            'combined_lab_schedules.html',
            schedules=calendar_events
        )
        
    except Exception as e:
        logging.error(f"Error viewing combined lab schedules: {str(e)}")
        flash(f'Error viewing lab schedules: {str(e)}', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/export_lab_schedules_pdf')
@login_required
def export_lab_schedules_pdf():
    """Export lab schedules to PDF"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all lab schedules - removed is_active filter that was causing errors
        cursor.execute("""
            SELECT * FROM lab_schedules
            ORDER BY lab_room, day_of_week, start_time
        """)
        
        schedules = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format schedules for PDF
        day_map = {
            0: 'Monday',
            1: 'Tuesday',
            2: 'Wednesday',
            3: 'Thursday',
            4: 'Friday',
            5: 'Saturday',
            6: 'Sunday'
        }
        
        formatted_schedules = []
        for schedule in schedules:
            formatted_schedule = {
                'lab_room': schedule['lab_room'],
                'day': day_map.get(schedule['day_of_week'], ''),
                'subject': schedule.get('subject', ''),
                'instructor': schedule.get('instructor', '')
            }
            
            if schedule['start_time']:
                hour = schedule['start_time'].seconds // 3600
                minute = (schedule['start_time'].seconds % 3600) // 60
                am_pm = 'AM' if hour < 12 else 'PM'
                display_hour = hour if hour <= 12 else hour - 12
                if hour == 0:
                    display_hour = 12
                formatted_schedule['start_time'] = f"{display_hour}:{minute:02d} {am_pm}"
            else:
                formatted_schedule['start_time'] = ''
                
            if schedule['end_time']:
                hour = schedule['end_time'].seconds // 3600
                minute = (schedule['end_time'].seconds % 3600) // 60
                am_pm = 'AM' if hour < 12 else 'PM'
                display_hour = hour if hour <= 12 else hour - 12
                if hour == 0:
                    display_hour = 12
                formatted_schedule['end_time'] = f"{display_hour}:{minute:02d} {am_pm}"
            else:
                formatted_schedule['end_time'] = ''
            
            formatted_schedules.append(formatted_schedule)
        
        # Group schedules by lab room
        lab_schedules = {}
        for schedule in formatted_schedules:
            lab_room = schedule['lab_room']
            if lab_room not in lab_schedules:
                lab_schedules[lab_room] = []
            lab_schedules[lab_room].append(schedule)
        
        # Create PDF using reportlab
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        
        elements = []
        
        # Add title
        title_style = styles['Heading1']
        title_style.alignment = 1  # Center alignment
        elements.append(Paragraph("Lab Schedules", title_style))
        elements.append(Spacer(1, 20))
        
        # Add date
        date_style = styles['Normal']
        date_style.alignment = 1
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style))
        elements.append(Spacer(1, 20))
        
        # Create tables for each lab room
        for lab_room, schedules in lab_schedules.items():
            # Add lab room header
            lab_header = styles['Heading2']
            elements.append(Paragraph(f"{lab_room}", lab_header))
            elements.append(Spacer(1, 10))
            
            # Create table data
            data = [['Day', 'Start Time', 'End Time', 'Subject', 'Instructor']]
            
            for schedule in schedules:
                data.append([
                    schedule['day'],
                    schedule['start_time'],
                    schedule['end_time'],
                    schedule['subject'],
                    schedule['instructor']
                ])
            
            # Create table
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
        
        # Build the PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        
        filename = f"lab_schedules_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logging.error(f"Error exporting lab schedules to PDF: {str(e)}")
        flash(f"Error exporting lab schedules: {str(e)}", 'error')
        return redirect(url_for('student_lab_schedules'))

@app.route('/approve-session/<int:session_id>', methods=['POST'])
@admin_required
def approve_session(session_id):
    """Approve a pending session"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get the session data
        cursor.execute("""
            SELECT s.*, st.firstname, st.lastname 
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE s.id = %s
        """, (session_id,))
        
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Only allow approval for pending sessions
        if session_data['status'] != 'pending' or session_data['approval_status'] != 'pending':
            flash('Session is not in pending status', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Record approval time
        current_time = datetime.now()
        
        # Set status to active and approval_status to approved, and set check_in_time
        # This will make the session appear in the Current Sit-in section immediately
        cursor.execute("""
            UPDATE sessions 
            SET approval_status = 'approved', status = 'active', check_in_time = %s
            WHERE id = %s
        """, (current_time, session_id))
        
        # Update PC status if a PC number was provided
        if session_data.get('pc_number'):
            pc_number = session_data['pc_number']
            lab_room = session_data['lab_room']
            student_id = session_data['student_id']
            
            # Special handling for PC 0 (ensure it's a string)
            if pc_number == 0 or pc_number == '0':
                pc_number = '0'
                logging.info(f"Handling PC #0 specifically during session approval")
            
            # Check if PC exists in status table
            cursor.execute("SELECT * FROM pc_status WHERE lab_room = %s AND pc_number = %s", 
                          (lab_room, pc_number))
            pc = cursor.fetchone()
            
            if pc:
                # Update PC status to occupied and set student_id
                cursor.execute("""
                    UPDATE pc_status 
                    SET status = 'occupied', student_id = %s 
                    WHERE lab_room = %s AND pc_number = %s
                """, (student_id, lab_room, pc_number))
            else:
                # Create new PC status entry - fixed parameter count
                cursor.execute("""
                    INSERT INTO pc_status (lab_room, pc_number, status, student_id)
                    VALUES (%s, %s, %s, %s)
                """, (lab_room, pc_number, 'occupied', student_id))
                
            logging.info(f"Updated PC #{pc_number} in {lab_room} to occupied when approving session")
        
        # Log the activity
        cursor.execute("""
            INSERT INTO activity_logs 
            (student_id, lab_room, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session_data['student_id'],
            session_data['lab_room'],
            'session_approved',
            f"Session for {session_data['firstname']} {session_data['lastname']} approved and marked active",
            current_time
        ))
        
        conn.commit()
        flash('Session approved and activated successfully', 'success')
        
        cursor.close()
        conn.close()
        
        return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        logging.error(f"Error approving session: {str(e)}")
        flash(f'Error approving session: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/reject-session/<int:session_id>', methods=['POST'])
@admin_required
def reject_session(session_id):
    """Reject a pending session"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get the session data
        cursor.execute("""
            SELECT s.*, st.firstname, st.lastname 
            FROM sessions s
            JOIN students st ON s.student_id = st.id
            WHERE s.id = %s
        """, (session_id,))
        
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Only allow rejection for pending sessions
        if session_data['status'] != 'pending' or session_data['approval_status'] != 'pending':
            flash('Session is not in pending status', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Record rejection time
        current_time = datetime.now()
        
        cursor.execute("""
            UPDATE sessions 
            SET status = 'cancelled', approval_status = 'rejected', rejected_at = %s, rejected_by = %s
            WHERE id = %s
        """, (current_time, session.get('username', 'admin'), session_id))
        
        # Log the activity
        cursor.execute("""
            INSERT INTO activity_logs 
            (student_id, lab_room, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session_data['student_id'],
            session_data['lab_room'],
            'session_rejected',
            f"Session for {session_data['firstname']} {session_data['lastname']} rejected",
            current_time
        ))
        
        conn.commit()
        flash('Session rejected successfully', 'success')
        
        cursor.close()
        conn.close()
        
        return redirect(url_for('admin_dashboard'))
        
    except Exception as e:
        logging.error(f"Error rejecting session: {str(e)}")
        flash(f'Error rejecting session: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    print("Starting Student Lab Session Management System...")
    print("Checking database connection...")
    print("Make sure XAMPP is running with MySQL service started.")
    print("")
    
    # Try to initialize the database
    for attempt in range(3):
        print(f"Connection attempt {attempt+1}/3...")
        if init_db():
            print("Database initialized successfully!")
            break
        else:
            if attempt < 2:  # Don't wait after the last attempt
                print("Retrying in 3 seconds...")
                time.sleep(3)
    
    if OFFLINE_MODE:
        print("WARNING: Running in offline mode. Database features will not be available.")
        print("To enable database features, please start XAMPP and restart this application.")
    
    print("Starting the Flask application...")
    print("Access the application at: http://127.0.0.1:5000")
    print("Admin credentials: username='admin', password='admin' (when database is available)")
    print("Press CTRL+C to stop the server")
    app.run(debug=True, host="127.0.0.1", port="5000")

