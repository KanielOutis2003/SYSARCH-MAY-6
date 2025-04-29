from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, send_file, make_response
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
import pdfkit
import csv
import io

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
    'Lab 5': 'Lab 532'
}

# Add lab_room filter to Jinja templates
@app.template_filter('lab_room')
def format_lab_room(lab_code):
    return lab_room_mapping.get(lab_code, lab_code)

# Ensure you have a folder for storing uploaded images
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'profile_pictures')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    global OFFLINE_MODE
    
    # Try to connect to the database
    conn = get_db_connection()
    if conn is None:
        print("Failed to initialize database. Running in offline mode.")
        OFFLINE_MODE = True
        return False
        
    cursor = conn.cursor()
    
    try:
        # Create students table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            idno VARCHAR(20) UNIQUE NOT NULL,
            lastname VARCHAR(50) NOT NULL,
            firstname VARCHAR(50) NOT NULL,
            middlename VARCHAR(50),
            course VARCHAR(100) NOT NULL,
            year_level VARCHAR(20) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            profile_picture VARCHAR(255) DEFAULT 'default.jpg',
            sessions_used INT DEFAULT 0,
            max_sessions INT DEFAULT 25,
            points INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Check if sessions_used and max_sessions columns exist, add them if they don't
        try:
            # Check if sessions_used column exists
            cursor.execute("SHOW COLUMNS FROM students LIKE 'sessions_used'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE students ADD COLUMN sessions_used INT DEFAULT 0")
                
            # Check if max_sessions column exists
            cursor.execute("SHOW COLUMNS FROM students LIKE 'max_sessions'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE students ADD COLUMN max_sessions INT DEFAULT 25")
            
            # Check if points column exists
            cursor.execute("SHOW COLUMNS FROM students LIKE 'points'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE students ADD COLUMN points INT DEFAULT 0")
                
            # Update max_sessions based on course for existing users
            cursor.execute("""
            UPDATE students 
            SET max_sessions = CASE 
                WHEN course IN ('1', '2', '3') THEN 30 
                ELSE 25 
            END
            WHERE max_sessions IS NULL OR (course IN ('1', '2', '3') AND max_sessions = 25) OR (course NOT IN ('1', '2', '3') AND max_sessions = 30)
            """)
            
            conn.commit()
        except Exception as e:
            logging.error(f"Error checking/adding columns: {str(e)}")
            conn.rollback()
        
        # Create admin table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create sit-in sessions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            lab_room VARCHAR(50) NOT NULL,
            date_time DATETIME NOT NULL,
            duration INT NOT NULL,
            programming_language VARCHAR(50),
            purpose TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            check_in_time DATETIME,
            check_out_time DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        ''')
        
        # Check if approval_status column exists in sessions table, add it if it doesn't
        try:
            cursor.execute("SHOW COLUMNS FROM sessions LIKE 'approval_status'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE sessions ADD COLUMN approval_status VARCHAR(20) DEFAULT 'pending'")
            
            # Check if programming_language column exists in sessions table, add it if it doesn't
            cursor.execute("SHOW COLUMNS FROM sessions LIKE 'programming_language'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE sessions ADD COLUMN programming_language VARCHAR(50)")
            
            # Check if purpose column exists in sessions table, add it if it doesn't
            cursor.execute("SHOW COLUMNS FROM sessions LIKE 'purpose'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE sessions ADD COLUMN purpose TEXT")
            
            # Check if check_in_time column exists in sessions table, add it if it doesn't
            cursor.execute("SHOW COLUMNS FROM sessions LIKE 'check_in_time'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE sessions ADD COLUMN check_in_time DATETIME")
            
            # Check if check_out_time column exists in sessions table, add it if it doesn't
            cursor.execute("SHOW COLUMNS FROM sessions LIKE 'check_out_time'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE sessions ADD COLUMN check_out_time DATETIME")
            
            conn.commit()
        except Exception as e:
            logging.error(f"Error checking/adding columns to sessions table: {str(e)}")
            conn.rollback()
        
        # Create feedback table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id INT NOT NULL,
            student_id INT NOT NULL,
            rating INT NOT NULL, /* 1-5 star rating */
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        ''')
        
        # Create announcements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(100) NOT NULL,
            content TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create programming languages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS programming_languages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create lab schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lab_schedules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lab_room VARCHAR(50) NOT NULL,
            day_of_week VARCHAR(20) NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            instructor VARCHAR(100),
            subject VARCHAR(100),
            section VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create points table for student rewards
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS points (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            points INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        ''')
        
        # Insert default programming languages if they don't exist
        default_languages = ['PHP', 'Java', 'Python', 'JavaScript', 'C++', 'C#', 'Ruby', 'Swift']
        for language in default_languages:
            cursor.execute("SELECT * FROM programming_languages WHERE name = %s", (language,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO programming_languages (name) VALUES (%s)", (language,))
        
        # Insert default admin if not exists
        cursor.execute("SELECT * FROM admins WHERE username = 'admin'")
        admin = cursor.fetchone()
        if not admin:
            hashed_password = generate_password_hash('admin')
            cursor.execute("INSERT INTO admins (username, password) VALUES (%s, %s)", 
                        ('admin', hashed_password))
        
        # Create lab_resources table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_resources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            file_path VARCHAR(255),
            resource_type ENUM('ppt', 'discussion', 'document', 'other') NOT NULL,
            lab_room VARCHAR(50) NOT NULL,
            is_enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Database initialization error: {str(e)}")
        print(f"Database initialization error: {str(e)}")
        OFFLINE_MODE = True
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        return False

# Helper function to check if file extension is allowed
def allowed_file(filename):
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
        
        # Get student information
        cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
        student = cursor.fetchone()
        
        if not student:
            cursor.close()
            conn.close()
            return None
        
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
        
        # Get active announcements
        try:
            cursor.execute("""
            SELECT * FROM announcements 
            WHERE is_active = TRUE 
            ORDER BY created_at DESC
            """)
            announcements = cursor.fetchall() or []
        except:
            announcements = []
        
        cursor.close()
        conn.close()
        
        return {
            'student': student,
            'sessions': sessions,
            'feedback_list': feedback_list,
            'announcements': announcements
        }
    
    # Get data safely
    data = safe_db_operation(get_student_data, {
        'student': {'firstname': 'User', 'lastname': '', 'sessions_used': 0, 'max_sessions': 0},
        'sessions': [],
        'feedback_list': [],
        'announcements': [{'title': 'Offline Mode', 'content': 'The application is running in offline mode. Database features are not available.', 'created_at': 'Now'}]
    })
    
    if data is None:
        flash('Error retrieving student data. The application may be in offline mode.', 'error')
        return redirect(url_for('index'))
    
    return render_template('student_dashboard.html', 
                          student=data['student'], 
                          sessions=data['sessions'],
                          feedback_list=data['feedback_list'],
                          announcements=data['announcements'],
                          offline_mode=OFFLINE_MODE)

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    import datetime
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get pending requests
    try:
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE s.approval_status = 'pending'
        ORDER BY s.date_time ASC
        """)
        pending_sessions = cursor.fetchall()
        
        # Format dates for display
        for session in pending_sessions:
            if 'date_time' in session and session['date_time']:
                session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        logging.error(f"Error fetching pending sessions: {str(e)}")
        pending_sessions = []

    # Get reservation requests that are approved but not checked in yet
    try:
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE s.approval_status = 'approved' AND s.status = 'pending'
        ORDER BY s.date_time ASC
        """)
        approved_reservations = cursor.fetchall()
        
        # Format dates for display
        for session in approved_reservations:
            if 'date_time' in session and session['date_time']:
                session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        logging.error(f"Error fetching approved reservations: {str(e)}")
        approved_reservations = []

    # Get active sessions
    try:
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE s.status = 'active' AND s.approval_status = 'approved'
        ORDER BY s.check_in_time DESC, s.date_time ASC
        """)
        active_sessions = cursor.fetchall()
    except:
        active_sessions = []
    
    # Get reservation logs (both approved and rejected)
    try:
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE (s.status = 'completed' OR s.status = 'cancelled' OR s.approval_status = 'rejected')
        ORDER BY s.created_at DESC
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

    # Get all students
    try:
        cursor.execute("""
        SELECT * FROM students
        ORDER BY lastname, firstname
        """)
        students = cursor.fetchall()
    except:
        students = []
    
    # Check if approval_status column exists in sessions table
    try:
        cursor.execute("SHOW COLUMNS FROM sessions LIKE 'approval_status'")
        has_approval_status = cursor.fetchone() is not None
    except:
        has_approval_status = False
    
    # Get recent activity (last 10 events)
    cursor.execute("""
    (SELECT 
        s.id, 
        st.firstname, 
        st.lastname, 
        s.lab_room, 
        'Requested a session' as action, 
        s.created_at as timestamp
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    ORDER BY s.created_at DESC
    LIMIT 5)
    
    UNION
    
    (SELECT 
        s.id, 
        st.firstname, 
        st.lastname, 
        s.lab_room, 
        'Checked in' as action, 
        s.check_in_time as timestamp
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    WHERE s.check_in_time IS NOT NULL
    ORDER BY s.check_in_time DESC
    LIMIT 5)
    
    UNION
    
    (SELECT 
        s.id, 
        st.firstname, 
        st.lastname, 
        s.lab_room, 
        'Checked out' as action, 
        s.check_out_time as timestamp
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    WHERE s.check_out_time IS NOT NULL
    ORDER BY s.check_out_time DESC
    LIMIT 5)
    
    ORDER BY timestamp DESC
    LIMIT 10
    """)
    recent_activity = cursor.fetchall()
    
    # Format each timestamp
    for activity in recent_activity:
        if activity['timestamp']:
            activity['formatted_time'] = activity['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
    
    # Get feedback data and statistics
    feedback_stats = {
        'total_feedback': 0,
        'average_rating': 0.0,
        'positive_feedback': 0,
        'negative_feedback': 0
    }
    
    feedback_list = []
    
    try:
        # Get feedback data
        cursor.execute("""
        SELECT f.*, s.lab_room, s.date_time, st.firstname, st.lastname, st.idno
        FROM feedback f
        JOIN sessions s ON f.session_id = s.id
        JOIN students st ON f.student_id = st.id
        ORDER BY f.created_at DESC
        """)
        feedback_list = cursor.fetchall()
        
        # Calculate feedback statistics
        if feedback_list:
            total_ratings = 0
            positive_count = 0
            negative_count = 0
            
            for feedback in feedback_list:
                total_ratings += feedback['rating']
                if feedback['rating'] >= 4:
                    positive_count += 1
                elif feedback['rating'] <= 2:
                    negative_count += 1
            
            feedback_stats = {
                'total_feedback': len(feedback_list),
                'average_rating': round(total_ratings / len(feedback_list), 1),
                'positive_feedback': positive_count,
                'negative_feedback': negative_count
            }
    except Exception as e:
        logging.error(f"Error fetching feedback data: {str(e)}")
    
    cursor.close()
    conn.close()
    
    # Pass all data to the template
    return render_template('admin_dashboard.html', 
                          pending_sessions=pending_sessions,
                          approved_reservations=approved_reservations,
                          active_sessions=active_sessions,
                          reservation_logs=reservation_logs, 
                          students=students,
                          recent_activity=recent_activity,
                          has_approval_status=has_approval_status,
                          feedback_stats=feedback_stats,
                          feedback_list=feedback_list,
                          announcements=[],
                          language_stats=[],
                          lab_stats=[],
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

@app.route('/admin/update-session/<int:session_id>', methods=['POST'])
@admin_required
def update_session(session_id):
    lab_room = request.form.get('lab_room')
    programming_language = request.form.get('programming_language')
    purpose = request.form.get('purpose')
    
    if not lab_room:
        return jsonify({'error': 'Laboratory room is required'}), 400
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        # Update session details
        cursor.execute("""
        UPDATE sessions 
        SET lab_room = %s, programming_language = %s, purpose = %s
        WHERE id = %s
        """, (lab_room, programming_language, purpose, session_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Session details updated successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Failed to update session: {str(e)}'}), 500
        
    finally:
        cursor.close()
        conn.close()

# Get PC Status function to return current status of PCs
@app.route('/get_pc_status', methods=['GET'])
@admin_required
def get_pc_status():
    lab_room = request.args.get('lab_room')
    
    if not lab_room:
        return jsonify({'error': 'Lab room is required'}), 400
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get all active sessions with approved status for the specified lab room
        cursor.execute("""
        SELECT id, student_id, purpose, status
        FROM sessions 
        WHERE lab_room = %s 
        AND (status = 'active' OR status = 'pending')
        AND approval_status = 'approved'
        """, (lab_room,))
        
        active_sessions = cursor.fetchall()
        
        # Initialize all PCs as vacant
        pc_status = {}
        for i in range(1, 51):  # Now supporting 50 PCs per lab
            pc_status[str(i)] = {
                'status': 'vacant',
                'student_id': None,
                'session_id': None,
                'purpose': None
            }
        
        # Update status based on active sessions
        for session in active_sessions:
            # Extract PC number from purpose field (format: "Purpose - PC #X")
            purpose = session.get('purpose', '')
            pc_match = re.search(r'PC #(\d+)', purpose)
            
            if pc_match:
                pc_number = pc_match.group(1)
                if pc_number in pc_status:
                    pc_status[pc_number] = {
                        'status': 'occupied' if session['status'] == 'active' else 'reserved',
                        'student_id': session['student_id'],
                        'session_id': session['id'],
                        'purpose': purpose.split(' - PC #')[0] if ' - PC #' in purpose else purpose
                    }
        
        return jsonify({'pc_status': pc_status})
        
    except Exception as e:
        return jsonify({'error': f'Failed to get PC status: {str(e)}'}), 500
        
    finally:
        cursor.close()
        conn.close()

# Route to manually update PC status (for admin)
@app.route('/admin/update_pc_status', methods=['POST'])
@admin_required
def update_pc_status():
    lab_room = request.form.get('lab_room')
    pc_number = request.form.get('pc_number')
    status = request.form.get('status')  # 'vacant', 'occupied', 'reserved', 'maintenance'
    
    if not lab_room or not pc_number or not status:
        return jsonify({'error': 'Lab room, PC number, and status are required'}), 400
    
    if status not in ['vacant', 'occupied', 'reserved', 'maintenance']:
        return jsonify({'error': 'Invalid status. Must be vacant, occupied, reserved, or maintenance'}), 400
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        # First, check if there's an active session for this PC
        cursor.execute("""
        SELECT id, student_id 
        FROM sessions 
        WHERE lab_room = %s 
        AND purpose LIKE %s
        AND (status = 'active' OR status = 'pending')
        """, (lab_room, f"%PC #{pc_number}%"))
        
        session_data = cursor.fetchone()
        
        if session_data and status == 'vacant':
            # If there's an active session and we're setting to vacant, mark the session as completed
            cursor.execute("""
            UPDATE sessions 
            SET status = 'completed', check_out_time = NOW()
            WHERE id = %s
            """, (session_data[0],))
            
        elif not session_data and status in ['occupied', 'reserved']:
            # If no session exists but we're marking as occupied/reserved, create a manual admin entry
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
            INSERT INTO sessions (student_id, lab_room, date_time, duration, purpose, status, approval_status, check_in_time)
            VALUES (%s, %s, %s, %s, %s, %s, 'approved', %s)
            """, (
                1,  # Admin ID or placeholder for system actions
                lab_room, 
                current_time, 
                1,  # 1 hour duration
                f"Manual Admin Assignment - PC #{pc_number}",
                'active' if status == 'occupied' else 'pending',
                current_time if status == 'occupied' else None
            ))
        
        # For 'maintenance' status, we would typically update a separate PC status table
        # Since we don't have one currently, we could use a maintenance session or other approach
        
        conn.commit()
        return jsonify({'success': True, 'message': f'PC {pc_number} in {lab_room} is now {status}'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Failed to update PC status: {str(e)}'}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/direct-sit-in', methods=['POST'])
@admin_required
def direct_sit_in():
    import datetime
    
    student_id = request.form.get('student_id')
    lab_room = request.form.get('lab_room')
    purpose_select = request.form.get('purpose_select')
    purpose = request.form.get('purpose')
    
    if not student_id or not lab_room:
        flash('Student ID and laboratory room are required', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Handle purpose logic
    if purpose_select == 'Other':
        if not purpose:
            flash('Please specify a purpose for the session', 'error')
            return redirect(url_for('admin_dashboard'))
        final_purpose = purpose
    else:
        final_purpose = purpose_select
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get student information
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Check if student has used all their sessions
        if student['sessions_used'] >= student['max_sessions']:
            flash(f'Student {student["firstname"]} {student["lastname"]} has reached their maximum allowed sessions ({student["max_sessions"]})', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Create a new session with current date and time
        current_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert the new session - directly approved and active
        cursor.execute("""
        INSERT INTO sessions (student_id, lab_room, date_time, duration, purpose, status, approval_status, check_in_time)
        VALUES (%s, %s, %s, %s, %s, 'active', 'approved', %s)
        """, (student_id, lab_room, current_datetime, 1, final_purpose, current_datetime))
        
        # Increment sessions used count
        cursor.execute("UPDATE students SET sessions_used = sessions_used + 1 WHERE id = %s", (student_id,))
        
        conn.commit()
        
        flash(f'Direct sit-in session created for {student["firstname"]} {student["lastname"]} in {lab_room}', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Failed to create direct sit-in session: {str(e)}', 'error')
        logging.error(f"Error creating direct sit-in: {str(e)}")
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/todays_sit_ins')
@admin_required
def todays_sit_ins():
    import datetime
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get today's sit-in sessions, including all completed ones
    cursor.execute("""
    SELECT s.*, st.firstname, st.lastname, st.idno, st.course
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    WHERE (DATE(s.date_time) = CURDATE() OR 
          DATE(s.check_in_time) = CURDATE() OR
          DATE(s.check_out_time) = CURDATE())
          AND (s.status = 'active' OR s.status = 'completed')
          AND s.approval_status = 'approved'
    ORDER BY 
        CASE 
            WHEN s.check_out_time IS NULL AND s.check_in_time IS NOT NULL THEN 1
            WHEN s.status = 'active' THEN 2
            WHEN s.status = 'completed' THEN 3
            ELSE 4
        END,
        COALESCE(s.check_in_time, s.date_time) DESC
    """)
    todays_sessions = cursor.fetchall()
    
    # Format datetime objects for display
    for session in todays_sessions:
        # Format date_time
        if 'date_time' in session and session['date_time']:
            if isinstance(session['date_time'], datetime.datetime):
                session['date_time'] = session['date_time'].strftime('%I:%M %p')
        
        # Format check_in_time
        if 'check_in_time' in session and session['check_in_time']:
            if isinstance(session['check_in_time'], datetime.datetime):
                session['check_in_time'] = session['check_in_time'].strftime('%I:%M %p')
        
        # Format check_out_time
        if 'check_out_time' in session and session['check_out_time']:
            if isinstance(session['check_out_time'], datetime.datetime):
                session['check_out_time'] = session['check_out_time'].strftime('%I:%M %p')
    
    cursor.close()
    conn.close()
    
    return render_template('todays_sit_ins.html', todays_sessions=todays_sessions)

@app.route('/admin/reset_semester', methods=['POST'])
@admin_required
def reset_semester():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Reset sessions_used for all students
        cursor.execute("UPDATE students SET sessions_used = 0")
        
        # Optional: Archive or delete old sessions
        # cursor.execute("DELETE FROM sessions")
        
        conn.commit()
        flash('Semester has been reset successfully. All students\' session counts have been reset to 0.', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to reset semester: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/get-announcement/<int:announcement_id>', methods=['GET'])
@admin_required
def get_announcement(announcement_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM announcements WHERE id = %s", (announcement_id,))
        announcement = cursor.fetchone()
        
        if not announcement:
            return jsonify({'error': 'Announcement not found'}), 404
        
        return jsonify(announcement)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/student/leaderboard')
@login_required
def student_leaderboard():
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get top 5 students for leaderboard
    cursor.execute("""
    SELECT id, idno, firstname, lastname, course, year_level, points,
           (SELECT COUNT(*) FROM sessions WHERE student_id = students.id AND status = 'completed') as completed_sessions
    FROM students
    ORDER BY points DESC, completed_sessions DESC
    LIMIT 5
    """)
    leaderboard = cursor.fetchall()
    
    # Get current user's rank and stats
    student_id = session["user_id"]
    student_rank = 0
    points_to_next_rank = 0
    your_stats = None
    
    # Find student's rank by counting students with more points
    cursor.execute("""
    SELECT COUNT(*) as rank
    FROM students
    WHERE points > (SELECT points FROM students WHERE id = %s)
       OR (points = (SELECT points FROM students WHERE id = %s) 
           AND (SELECT COUNT(*) FROM sessions WHERE student_id = students.id AND status = 'completed') >
               (SELECT COUNT(*) FROM sessions WHERE student_id = %s AND status = 'completed'))
    """, (student_id, student_id, student_id))
    rank_result = cursor.fetchone()
    if rank_result:
        student_rank = rank_result['rank'] + 1  # Add 1 because rank is 0-indexed
    
    # Get student's stats
    cursor.execute("""
    SELECT points, (SELECT COUNT(*) FROM sessions WHERE student_id = %s AND status = 'completed') as completed_sessions
    FROM students WHERE id = %s
    """, (student_id, student_id))
    stats = cursor.fetchone()
    
    if stats:
        # Find points needed for next rank
        cursor.execute("""
        SELECT MIN(points) as next_rank_points
        FROM students
        WHERE points > (SELECT points FROM students WHERE id = %s)
        """, (student_id,))
        next_rank = cursor.fetchone()
        
        points_to_next_rank = 0
        if next_rank and next_rank['next_rank_points']:
            points_to_next_rank = next_rank['next_rank_points'] - stats['points']
        
        your_stats = {
            "rank": student_rank,
            "points": stats['points'],
            "completed_sessions": stats['completed_sessions'],
            "points_to_next_rank": points_to_next_rank
        }
    
    cursor.close()
    conn.close()
    
    # Use the same admin_leaderboard.html template for student view
    return render_template('admin_leaderboard.html', 
                           leaderboard=leaderboard, 
                           your_stats=your_stats, 
                           current_user={"id": student_id},
                           is_student_view=True)

@app.route('/admin/reset_student_sessions/<int:student_id>', methods=['POST'])
@admin_required
def reset_student_sessions(student_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Reset sessions_used for the specific student
        cursor.execute("UPDATE students SET sessions_used = 0 WHERE id = %s", (student_id,))
        
        conn.commit()
        flash(f'Session count has been reset for student {student["firstname"]} {student["lastname"]}', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to reset student sessions: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/lab_resources', methods=['GET', 'POST'])
def lab_resources():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_type = session.get('user_type', '')
    error_message = None
    success_message = None
    lab_resources_list = []
    
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join('static', 'uploads')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if user_type == 'admin' and request.method == 'POST':
            # Existing admin POST handling code
            title = request.form.get('title')
            description = request.form.get('description')
            resource_type = request.form.get('resource_type')
            lab_room = request.form.get('lab_room')
            resource_link = request.form.get('resource_link')
            
            # Flag to determine if we're processing a file or URL
            is_url = False
            file_path = None
            
            # Check if resource_link starts with http:// or https://
            if resource_link and (resource_link.startswith('http://') or resource_link.startswith('https://')):
                is_url = True
                file_path = resource_link  # Store the URL directly in file_path
            else:
                # Handle file upload
                if 'file' in request.files and request.files['file'].filename != '':
                    file = request.files['file']
                    if file and allowed_file(file.filename):
                        # Generate unique filename
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        filename = secure_filename(f"{timestamp}_{file.filename}")
                        
                        # Save file and set path
                        file_path = os.path.join('uploads', filename)
                        file.save(os.path.join('static', file_path))
                    else:
                        error_message = "Invalid file type."
                        flash(error_message, 'error')
            
            if title and (file_path or is_url):
                # Insert the resource into the database
                cursor.execute(
                    "INSERT INTO lab_resources (file_path, title, description, resource_type, lab_room, is_enabled) VALUES (%s, %s, %s, %s, %s, %s)",
                    (file_path, title, description, resource_type, lab_room, True)
                )
                conn.commit()
                success_message = "Resource added successfully."
                flash(success_message, 'success')
            else:
                if not file_path and not is_url:
                    error_message = "Please provide either a file or a valid URL."
                    flash(error_message, 'error')
        
        # Get lab resources for admin or student
        if user_type == 'admin':
            cursor.execute("SELECT * FROM lab_resources ORDER BY id DESC")
            lab_resources_list = cursor.fetchall()
            return render_template('lab_resources.html', resources=lab_resources_list)
        else:
            # For students, get student data and only show enabled resources
            cursor.execute("SELECT * FROM students WHERE id = %s", (session.get('user_id'),))
            student = cursor.fetchone()
            
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('logout'))
            
            # Get the student's current lab
            current_lab = student.get('current_lab')
            
            # Get all enabled resources
            cursor.execute("SELECT * FROM lab_resources WHERE is_enabled = TRUE ORDER BY id DESC")
            lab_resources_list = cursor.fetchall()
            
            return render_template('student_lab_resources.html', 
                                  student=student, 
                                  lab_resources_list=lab_resources_list,
                                  current_lab_room=current_lab)
    
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        flash(error_message, 'error')
        logging.error(f"Error in lab_resources route: {str(e)}")
    
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
    
    # Default returns
    if user_type == 'admin':
        return render_template('lab_resources.html', resources=lab_resources_list)
    else:
        # Try to get student data again for error case
        student = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM students WHERE id = %s", (session.get('user_id'),))
            student = cursor.fetchone()
            cursor.close()
            conn.close()
        except:
            pass
        
        return render_template('student_lab_resources.html', 
                              student=student, 
                              lab_resources_list=lab_resources_list,
                              current_lab_room=None)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Handle both direct uploads and files in subdirectories
    try:
        return send_from_directory('static/uploads', filename)
    except Exception as e:
        logging.error(f"Error serving file {filename}: {str(e)}")
        return "File not found", 404

@app.route('/admin/delete-resource/<int:resource_id>', methods=['POST'])
@admin_required
def delete_resource(resource_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get the resource to find the file path
        cursor.execute("SELECT file_path FROM lab_resources WHERE id = %s", (resource_id,))
        resource = cursor.fetchone()
        
        if resource and resource['file_path']:
            # Delete the file from the filesystem
            file_path = os.path.join('static', resource['file_path'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete the resource from the database
        cursor.execute("DELETE FROM lab_resources WHERE id = %s", (resource_id,))
        conn.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/admin/add-reward-points', methods=['POST'])
@admin_required
def add_reward_points():
    student_id = request.form.get('student_id')
    points = int(request.form.get('points', 0))
    reason = request.form.get('reason', 'No reason provided')
    
    if not student_id or points <= 0:
        flash('Invalid input: Student ID and positive points are required', 'error')
        return redirect(url_for('admin_leaderboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('admin_leaderboard'))
            
        # Log current points for debugging
        logging.info(f"Before update: Student {student_id} has {student['points']} points")
        
        # Calculate new total points
        new_total_points = student['points'] + points
        
        # Direct SQL update to set the new points total
        cursor.execute("UPDATE students SET points = %s WHERE id = %s", (new_total_points, student_id))
        
        # Verify the update
        cursor.execute("SELECT points FROM students WHERE id = %s", (student_id,))
        updated_student = cursor.fetchone()
        logging.info(f"After update: Student {student_id} now has {updated_student['points']} points")
        
        # Log the reward
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO activity_log (action_type, user_id, user_type, details, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, ('reward_points', session.get('user_id'), 'admin', 
             f"Added {points} reward points to student {student['firstname']} {student['lastname']} ({student['idno']}). Reason: {reason}", 
             current_time))
        
        conn.commit()
        flash(f'Successfully added {points} points to {student["firstname"]} {student["lastname"]}', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to add reward points: {str(e)}', 'error')
        logging.error(f"Error adding reward points: {str(e)}")
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_leaderboard'))

@app.route('/admin/lab_resources/<int:resource_id>/toggle', methods=['POST'])
@admin_required
def toggle_lab_resource(resource_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First, check if the resource exists
        cursor.execute("SELECT is_enabled FROM lab_resources WHERE id = %s", (resource_id,))
        resource = cursor.fetchone()
        
        if not resource:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        
        # Toggle status
        new_status = not resource['is_enabled']
        cursor.execute("UPDATE lab_resources SET is_enabled = %s WHERE id = %s", (new_status, resource_id))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return the new status to update the UI without refreshing
        return jsonify({'success': True, 'new_status': new_status})
        
    except Exception as e:
        logging.error(f"Error toggling resource status: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/lab_resources/<int:resource_id>/delete', methods=['POST'])
@admin_required
def delete_lab_resource(resource_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get resource info to delete file if needed
        cursor.execute("SELECT * FROM lab_resources WHERE id = %s", (resource_id,))
        resource = cursor.fetchone()
        
        if not resource:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        
        # Delete the resource
        cursor.execute("DELETE FROM lab_resources WHERE id = %s", (resource_id,))
        conn.commit()
        
        # Delete the file if it exists
        if resource['file_path']:
            file_path = os.path.join('static', resource['file_path'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Error deleting resource: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/student_lab_resources')
@login_required
def student_lab_resources():
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get student information
    cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
    student = cursor.fetchone()
    
    if not student:
        flash('Student not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('logout'))
    
    try:
        # Get only the enabled resources
        cursor.execute("""
            SELECT * FROM lab_resources 
            WHERE is_enabled = 1
            ORDER BY resource_type
        """)
        lab_resources_list = cursor.fetchall()
        
        # Log the resources found for debugging
        logging.info(f"Found {len(lab_resources_list)} resources for student display")
        for resource in lab_resources_list:
            logging.info(f"Resource ID: {resource['id']}, Title: {resource['title']}, " 
                         f"Type: {resource['resource_type']}, Path: {resource['file_path']}")
        
        cursor.close()
        conn.close()
        
        return render_template('student_lab_resources.html', 
                               student=student,
                               lab_resources_list=lab_resources_list)
    except Exception as e:
        error_msg = f"Error retrieving resources: {str(e)}"
        logging.error(error_msg)
        flash(error_msg, "error")
        cursor.close()
        conn.close()
        return render_template('student_lab_resources.html', 
                               student=student,
                               lab_resources_list=[])

@app.route('/add_session', methods=['POST'])
@login_required
def add_session():
    import datetime
    
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get form data
    idno = request.form.get('idno')
    purpose = request.form.get('purpose')
    other_purpose = request.form.get('other_purpose')
    lab_room = request.form.get('lab_room')
    pc_number = request.form.get('pc_number')
    date = request.form.get('date')
    time_in = request.form.get('time_in')
    duration = request.form.get('duration', 1)  # Default to 1 hour
    
    # If purpose is "Other", use the specified purpose
    final_purpose = other_purpose if purpose == 'Other' else purpose
    
    # Combine date and time into datetime object
    try:
        date_time_str = f"{date} {time_in}"
        date_time = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M')
    except Exception as e:
        flash(f'Invalid date or time format: {str(e)}', 'error')
        return redirect(url_for('student_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get student information
        cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('logout'))
        
        # Check if student has used all their sessions
        if student['sessions_used'] >= student['max_sessions']:
            flash('You have used all your available sessions. Please contact the administrator.', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Store PC number in the purpose field for now (can modify schema later)
        reservation_details = f"{final_purpose} - PC #{pc_number}"
        
        # Insert the session
        cursor.execute("""
        INSERT INTO sessions (student_id, lab_room, date_time, duration, purpose, status, approval_status)
        VALUES (%s, %s, %s, %s, %s, 'pending', 'pending')
        """, (session['user_id'], lab_room, date_time, duration, reservation_details))
        
        # Increment sessions_used
        cursor.execute("UPDATE students SET sessions_used = sessions_used + 1 WHERE id = %s", (session['user_id'],))
        
        conn.commit()
        flash('Your reservation has been submitted successfully! Please wait for admin approval.', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to add session: {str(e)}', 'error')
        logging.error(f"Error adding session: {str(e)}")
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('student_dashboard'))

@app.route('/admin/leaderboard')
@admin_required
def admin_leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get top 5 students for leaderboard
    cursor.execute("""
    SELECT id, idno, firstname, lastname, course, year_level, points,
           (SELECT COUNT(*) FROM sessions WHERE student_id = students.id AND status = 'completed') as completed_sessions
    FROM students
    ORDER BY points DESC, completed_sessions DESC
    LIMIT 5
    """)
    leaderboard = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_leaderboard.html', leaderboard=leaderboard)

@app.route('/admin/announcements')
@admin_required
def admin_announcements():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all announcements
    cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    announcements = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_announcements.html', announcements=announcements)

@app.route('/admin/lab_schedules')
@admin_required
def admin_lab_schedules():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all lab schedules
    cursor.execute("""
    SELECT * FROM lab_schedules
    ORDER BY day_of_week, start_time
    """)
    schedules = cursor.fetchall()
    
    # Get list of all lab rooms for the form
    lab_rooms = []
    for key in lab_room_mapping:
        lab_rooms.append({"code": key, "name": lab_room_mapping[key]})
    
    cursor.close()
    conn.close()
    
    return render_template('admin_lab_schedules.html', schedules=schedules, lab_rooms=lab_rooms)

@app.route('/admin/add_lab_schedule', methods=['POST'])
@admin_required
def add_lab_schedule():
    if request.method == 'POST':
        day_of_week = request.form.get('day_of_week')
        lab_room = request.form.get('lab_room')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        instructor = request.form.get('instructor')
        
        if not day_of_week or not lab_room or not start_time or not end_time or not instructor:
            flash('All fields are required', 'error')
            return redirect(url_for('admin_lab_schedules'))
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Insert new schedule
            cursor.execute("""
                INSERT INTO lab_schedules (lab_room, day_of_week, start_time, end_time, instructor, subject, section)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (lab_room, day_of_week, start_time, end_time, instructor, '', ''))
            
            conn.commit()
            flash('Lab schedule has been added successfully', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Failed to add lab schedule: {str(e)}', 'error')
            
        finally:
            cursor.close()
            conn.close()
            
    return redirect(url_for('admin_lab_schedules'))

@app.route('/admin/delete_lab_schedule/<int:schedule_id>', methods=['POST'])
@admin_required
def delete_lab_schedule(schedule_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete the schedule
        cursor.execute("DELETE FROM lab_schedules WHERE id = %s", (schedule_id,))
        
        conn.commit()
        flash('Lab schedule has been deleted successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to delete lab schedule: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_lab_schedules'))

@app.template_filter('format_time')
def format_time(time_value):
    """Format timedelta or string time as HH:MM AM/PM"""
    import datetime
    
    if not time_value:
        return ""
    
    # Handle timedelta objects
    if isinstance(time_value, datetime.timedelta):
        total_seconds = int(time_value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        period = "AM" if hours < 12 else "PM"
        display_hours = hours if hours <= 12 else hours - 12
        # Handle midnight/noon special cases
        if hours == 0:
            display_hours = 12
        if hours == 12:
            display_hours = 12
            
        return f"{display_hours}:{minutes:02d} {period}"
    
    # Handle string times (assume HH:MM:SS format)
    elif isinstance(time_value, str):
        try:
            # Try to parse the time string
            time_parts = time_value.split(':')
            if len(time_parts) >= 2:
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                
                period = "AM" if hours < 12 else "PM"
                display_hours = hours if hours <= 12 else hours - 12
                # Handle midnight/noon special cases
                if hours == 0:
                    display_hours = 12
                if hours == 12:
                    display_hours = 12
                    
                return f"{display_hours}:{minutes:02d} {period}"
        except (ValueError, IndexError):
            # If parsing fails, return the original string
            return time_value
    
    # Return the original value for other types
    return str(time_value)

@app.route('/admin/sit_in_history')
@admin_required
def sit_in_history():
    conn = get_db_connection()
def edit_announcement():
    announcement_id = request.form.get('announcement_id')
    title = request.form.get('title')
    content = request.form.get('content')
    
    if not announcement_id or not title or not content:
        flash('Announcement ID, title, and content are required', 'error')
        return redirect(url_for('admin_announcements'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update the announcement
        cursor.execute("""
        UPDATE announcements 
        SET title = %s, content = %s
        WHERE id = %s
        """, (title, content, announcement_id))
        
        conn.commit()
        flash('Announcement has been updated successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to update announcement: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_announcements'))

@app.route('/admin/toggle-announcement/<int:announcement_id>', methods=['POST'])
@admin_required
def toggle_announcement(announcement_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get the current status
        cursor.execute("SELECT is_active FROM announcements WHERE id = %s", (announcement_id,))
        announcement = cursor.fetchone()
        
        if not announcement:
            flash('Announcement not found', 'error')
            return redirect(url_for('admin_announcements'))
        
        # Toggle the status
        new_status = not announcement['is_active']
        cursor.execute("UPDATE announcements SET is_active = %s WHERE id = %s", 
                      (new_status, announcement_id))
        
        conn.commit()
        
        status_text = "activated" if new_status else "deactivated"
        flash(f'Announcement has been {status_text}', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to update announcement: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_announcements'))

@app.route('/admin/delete-announcement/<int:announcement_id>', methods=['POST'])
@admin_required
def delete_announcement(announcement_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete the announcement
        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
        
        conn.commit()
        flash('Announcement has been deleted successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to delete announcement: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_announcements'))

@app.route('/admin/export-sit-in-history-csv')
@admin_required
def export_sit_in_history_csv():
    try:
        import csv
        import io
        from datetime import datetime
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE (s.status = 'completed' OR s.status = 'cancelled')
          AND s.approval_status = 'approved'
        ORDER BY s.created_at DESC
        """)
        
        sessions = cursor.fetchall()
        
        # Create an in-memory output file
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Add institutional header
        writer.writerow(['UNIVERSITY OF CEBU MAIN CAMPUS'])
        writer.writerow(['COLLEGE OF COMPUTER STUDIES'])
        writer.writerow(['COMPUTER LABORATORY SIT IN MONITORING SYSTEM'])
        writer.writerow([f'Report generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])  # Empty row as separator
        
        # Write headers
        writer.writerow(['Student ID', 'Name', 'Course', 'Lab Room', 'Date & Time', 
                        'Check-In Time', 'Check-Out Time', 'Status', 'Purpose'])
        
        # Write data
        for session in sessions:
            # Format course
            course_name = session['course']
            if session['course'] == '1':
                course_name = 'BSIT'
            elif session['course'] == '2':
                course_name = 'BSCS'
            elif session['course'] == '3':
                course_name = 'BSCE'
            
            # Format dates
            date_time_str = session['date_time'].strftime('%Y-%m-%d %H:%M') if session['date_time'] else 'N/A'
            check_in_str = session['check_in_time'].strftime('%I:%M %p') if session['check_in_time'] else 'N/A'
            check_out_str = session['check_out_time'].strftime('%I:%M %p') if session['check_out_time'] else 'N/A'
            
            # Get lab room name
            lab_room_name = format_lab_room(session['lab_room'])
            
            # Write row
            writer.writerow([
                session['idno'],
                f"{session['lastname']}, {session['firstname']}",
                course_name,
                lab_room_name,
                date_time_str,
                check_in_str,
                check_out_str,
                'Completed' if session['status'] == 'completed' else 'Cancelled',
                session['purpose'] if session['purpose'] else 'N/A'
            ])
        
        cursor.close()
        conn.close()
        
        # Prepare response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=sit_in_history_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        response.headers["Content-type"] = "text/csv"
        
        return response
    
    except Exception as e:
        logging.error(f"Error exporting sit-in history to CSV: {str(e)}")
        flash(f'Failed to export sit-in history to CSV: {str(e)}', 'error')
        return redirect(url_for('sit_in_history'))

@app.route('/admin/export-sit-in-history')
@admin_required
def export_sit_in_history():
    try:
        import xlsxwriter
        from io import BytesIO
        from datetime import datetime
        
        # Create an in-memory output file
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Add header styles
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        subtitle_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#003366',
            'color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Add data style
        data_format = workbook.add_format({
            'border': 1
        })
        
        # Add status styles
        completed_format = workbook.add_format({
            'border': 1,
            'color': '#28a745',
            'bold': True
        })
        
        cancelled_format = workbook.add_format({
            'border': 1,
            'color': '#dc3545',
            'bold': True
        })
        
        # Add institutional header
        worksheet.merge_range('A1:I1', 'UNIVERSITY OF CEBU MAIN CAMPUS', title_format)
        worksheet.merge_range('A2:I2', 'COLLEGE OF COMPUTER STUDIES', subtitle_format)
        worksheet.merge_range('A3:I3', 'COMPUTER LABORATORY SIT IN MONITORING SYSTEM', subtitle_format)
        worksheet.merge_range('A4:I4', f'Report generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', workbook.add_format({'align': 'center'}))
        
        # Add a blank row
        row_offset = 5
        
        # Add column headers
        headers = ['Student ID', 'Name', 'Course', 'Lab Room', 'Date & Time', 
                'Check-In Time', 'Check-Out Time', 'Status', 'Purpose']
        
        for col, header in enumerate(headers):
            worksheet.write(row_offset, col, header, header_format)
        
        # Get data from database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE (s.status = 'completed' OR s.status = 'cancelled')
          AND s.approval_status = 'approved'
        ORDER BY s.created_at DESC
        """)
        sessions = cursor.fetchall()
        
        # Write data to worksheet
        row = row_offset + 1
        for session in sessions:
            # Map course number to name
            course_name = session['course']
            if session['course'] == '1':
                course_name = 'BSIT'
            elif session['course'] == '2':
                course_name = 'BSCS'
            elif session['course'] == '3':
                course_name = 'BSCE'
            
            # Format dates
            date_time_str = session['date_time'].strftime('%Y-%m-%d %H:%M') if session['date_time'] else 'N/A'
            check_in_str = session['check_in_time'].strftime('%I:%M %p') if session['check_in_time'] else 'N/A'
            check_out_str = session['check_out_time'].strftime('%I:%M %p') if session['check_out_time'] else 'N/A'
            
            # Get lab room name
            lab_room_name = format_lab_room(session['lab_room'])
            
            # Write data row
            worksheet.write(row, 0, session['idno'], data_format)
            worksheet.write(row, 1, f"{session['lastname']}, {session['firstname']}", data_format)
            worksheet.write(row, 2, course_name, data_format)
            worksheet.write(row, 3, lab_room_name, data_format)
            worksheet.write(row, 4, date_time_str, data_format)
            worksheet.write(row, 5, check_in_str, data_format)
            worksheet.write(row, 6, check_out_str, data_format)
            
            # Write status with appropriate format
            status_format = completed_format if session['status'] == 'completed' else cancelled_format
            status_text = 'Completed' if session['status'] == 'completed' else 'Cancelled'
            worksheet.write(row, 7, status_text, status_format)
            
            # Write purpose
            purpose = session['purpose'] if session['purpose'] else 'N/A'
            worksheet.write(row, 8, purpose, data_format)
            
            row += 1
        
        # Adjust column widths
        worksheet.set_column(0, 0, 12)  # Student ID
        worksheet.set_column(1, 1, 25)  # Name
        worksheet.set_column(2, 2, 10)  # Course
        worksheet.set_column(3, 3, 15)  # Lab Room
        worksheet.set_column(4, 4, 18)  # Date & Time
        worksheet.set_column(5, 5, 15)  # Check-In Time
        worksheet.set_column(6, 6, 15)  # Check-Out Time
        worksheet.set_column(7, 7, 12)  # Status
        worksheet.set_column(8, 8, 35)  # Purpose
        
        cursor.close()
        conn.close()
        
        # Close workbook and get output
        workbook.close()
        output.seek(0)
        
        # Create filename with current timestamp
        filename = f'sit_in_history_{datetime.now().strftime("%Y%m%d%H%M%S")}.xlsx'
        
        # Create response
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except ImportError as e:
        logging.error(f"Missing module for Excel export: {str(e)}")
        flash(f'Excel export requires the xlsxwriter module. Please install it with pip install xlsxwriter.', 'error')
        return redirect(url_for('sit_in_history'))
    except Exception as e:
        logging.error(f"Error exporting sit-in history: {str(e)}")
        flash(f'Failed to export sit-in history: {str(e)}', 'error')
        return redirect(url_for('sit_in_history'))

@app.route('/admin/export-sit-in-history-pdf')
@admin_required
def export_sit_in_history_pdf():
    try:
        import pdfkit
        from flask import make_response
        from datetime import datetime
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE (s.status = 'completed' OR s.status = 'cancelled')
          AND s.approval_status = 'approved'
        ORDER BY s.created_at DESC
        """)
        sessions = cursor.fetchall()
        
        # Format datetime objects for display
        for session in sessions:
            # Format course
            if session['course'] == '1':
                session['course_name'] = 'BSIT'
            elif session['course'] == '2':
                session['course_name'] = 'BSCS'
            elif session['course'] == '3':
                session['course_name'] = 'BSCE'
            else:
                session['course_name'] = session['course']
                
            # Format lab room
            session['lab_room_name'] = format_lab_room(session['lab_room'])
            
            # Format date and times
            if 'date_time' in session and session['date_time']:
                if isinstance(session['date_time'], datetime):
                    session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
                else:
                    session['date_time_formatted'] = session['date_time']
                    
            if 'check_in_time' in session and session['check_in_time']:
                if isinstance(session['check_in_time'], datetime):
                    session['check_in_formatted'] = session['check_in_time'].strftime('%I:%M %p')
                else:
                    session['check_in_formatted'] = session['check_in_time']
                    
            if 'check_out_time' in session and session['check_out_time']:
                if isinstance(session['check_out_time'], datetime):
                    session['check_out_formatted'] = session['check_out_time'].strftime('%I:%M %p')
                else:
                    session['check_out_formatted'] = session['check_out_time']
                    
            if 'created_at' in session and session['created_at']:
                if isinstance(session['created_at'], datetime):
                    session['created_at_formatted'] = session['created_at'].strftime('%Y-%m-%d %H:%M')
                else:
                    session['created_at_formatted'] = session['created_at']
        
        cursor.close()
        conn.close()
        
        # Generate HTML content for the PDF
        html = render_template('pdf_sit_in_history.html', sessions=sessions)
        
        # Configure PDF options
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None
        }
        
        # Generate PDF from HTML
        try:
            pdf = pdfkit.from_string(html, False, options=options)
            
            # Create response
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename={filename}.pdf'
            
            return response
        except OSError as e:
            if "No wkhtmltopdf executable found" in str(e):
                flash('PDF export requires wkhtmltopdf to be installed. Please install it from https://github.com/JazzCore/python-pdfkit/wiki/Installing-wkhtmltopdf', 'error')
                logging.error(f"wkhtmltopdf not installed: {str(e)}")
            else:
                flash(f'Failed to export report to PDF: {str(e)}', 'error')
                logging.error(f"PDF generation error: {str(e)}")
            return redirect(url_for('admin_dashboard'))
        
    except ImportError:
        flash('PDF generation requires pdfkit. Please install it with pip install pdfkit and ensure wkhtmltopdf is installed.', 'error')
        return redirect(url_for('sit_in_history'))
    except Exception as e:
        logging.error(f"Error exporting sit-in history to PDF: {str(e)}")
        flash(f'Failed to export sit-in history to PDF: {str(e)}', 'error')
        return redirect(url_for('sit_in_history'))

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get student information
    cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
    student = cursor.fetchone()
    
    if not student:
        flash('Student not found', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('logout'))
    
    if request.method == 'POST':
        # Get form data
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        middlename = request.form.get('middlename', '')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        try:
            # Check if email is already used by another student
            cursor.execute("SELECT * FROM students WHERE email = %s AND id != %s", (email, session['user_id']))
            existing_email = cursor.fetchone()
            
            if existing_email:
                flash('Email already in use by another student', 'error')
                cursor.close()
                conn.close()
                return render_template('edit_profile.html', student=student)
            
            # Update profile picture if provided
            if 'profile_picture' in request.files and request.files['profile_picture'].filename != '':
                file = request.files['profile_picture']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{student['idno']}_{int(time.time())}_{file.filename}")
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    # Update profile picture in database
                    cursor.execute("UPDATE students SET profile_picture = %s WHERE id = %s", 
                                 (filename, session['user_id']))
                    
                    # Update session data
                    if 'student_info' in session:
                        session['student_info']['profile_picture'] = filename
            
            # Update basic profile information
            cursor.execute("""
            UPDATE students 
            SET firstname = %s, lastname = %s, middlename = %s, email = %s
            WHERE id = %s
            """, (firstname, lastname, middlename, email, session['user_id']))
            
            # If password change is requested
            if current_password and new_password and confirm_password:
                # Verify current password
                if not check_password_hash(student['password'], current_password):
                    flash('Current password is incorrect', 'error')
                    cursor.close()
                    conn.close()
                    return render_template('edit_profile.html', student=student)
                
                # Check if new passwords match
                if new_password != confirm_password:
                    flash('New passwords do not match', 'error')
                    cursor.close()
                    conn.close()
                    return render_template('edit_profile.html', student=student)
                
                # Update password
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE students SET password = %s WHERE id = %s", 
                             (hashed_password, session['user_id']))
            
            conn.commit()
            flash('Profile updated successfully', 'success')
            
            # Update session data
            if 'student_info' in session:
                session['student_info']['name'] = f"{firstname} {lastname}"
            
            # Redirect to student dashboard
            return redirect(url_for('student_dashboard'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Failed to update profile: {str(e)}', 'error')
            logging.error(f"Profile update error: {str(e)}")
    
    cursor.close()
    conn.close()
    
    return render_template('edit_profile.html', student=student)

@app.route('/student/announcements')
@login_required
def student_announcements():
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get active announcements
    cursor.execute("""
    SELECT * FROM announcements
    WHERE is_active = TRUE
    ORDER BY created_at DESC
    """)
    announcements = cursor.fetchall()
    
    # Get student information
    cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
    student = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('student_announcements.html', 
                          announcements=announcements,
                          student=student)

@app.route('/student/lab-schedules')
@login_required
def student_lab_schedules():
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get all lab schedules
        cursor.execute("""
        SELECT * FROM lab_schedules
        ORDER BY day_of_week, start_time
        """)
        schedules = cursor.fetchall()
        
        # Get student information
        cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
        student = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return render_template('student_lab_schedules.html', 
                            schedules=schedules,
                            student=student)
                            
    except Exception as e:
        flash(f"Error loading lab schedules: {str(e)}", 'error')
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return redirect(url_for('student_dashboard'))

@app.route('/admin/check_out_student/<int:session_id>', methods=['POST'])
@admin_required
def check_out_student(session_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
        
        conn.commit()
        conn.close()
        
        flash('Student checked out successfully', 'success')
    except Exception as e:
        flash(f'Error checking out student: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve-session/<int:session_id>', methods=['POST'])
@admin_required
def approve_session(session_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update session approval status to approved but keep status as pending
        cursor.execute("""
            UPDATE sessions 
            SET approval_status = 'approved'
            WHERE id = %s AND approval_status = 'pending'
        """, (session_id,))
        
        # Check if any row was updated
        if cursor.rowcount == 0:
            flash('Session not found or already approved/rejected', 'error')
            conn.close()
            return redirect(url_for('admin_dashboard'))
        
        conn.commit()
        flash('Session approved successfully', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error approving session: {str(e)}', 'error')
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject-session/<int:session_id>', methods=['POST'])
@admin_required
def reject_session(session_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First get the student ID to later refund the session count
        cursor.execute("SELECT student_id FROM sessions WHERE id = %s", (session_id,))
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found', 'error')
            conn.close()
            return redirect(url_for('admin_dashboard'))
        
        student_id = session_data[0]
        
        # Update session status to rejected
        cursor.execute("""
            UPDATE sessions 
            SET approval_status = 'rejected', status = 'cancelled' 
            WHERE id = %s AND approval_status = 'pending'
        """, (session_id,))
        
        # Check if any row was updated
        if cursor.rowcount == 0:
            flash('Session not found or already approved/rejected', 'error')
            conn.close()
            return redirect(url_for('admin_dashboard'))
        
        # Refund the session count by decrementing sessions_used
        cursor.execute("""
            UPDATE students 
            SET sessions_used = GREATEST(0, sessions_used - 1) 
            WHERE id = %s
        """, (student_id,))
        
        conn.commit()
        flash('Session rejected and session count refunded', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error rejecting session: {str(e)}', 'error')
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/check_in_student/<int:session_id>', methods=['POST'])
@admin_required
def check_in_student(session_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the current time
        check_in_time = datetime.now().strftime('%H:%M:%S')
        
        # Update session status to active and set check_in_time
        cursor.execute("""
            UPDATE sessions 
            SET status = 'active', check_in_time = %s 
            WHERE id = %s AND status = 'pending' AND approval_status = 'approved'
        """, (check_in_time, session_id))
        
        # Check if any row was affected
        if cursor.rowcount == 0:
            # Session might not exist or is not approved
            conn.close()
            flash('Session not found or not approved', 'error')
            return redirect(url_for('admin_dashboard'))
        
        conn.commit()
        conn.close()
        
        flash('Student checked in successfully', 'success')
    except Exception as e:
        flash(f'Error checking in student: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/get-student-info/<int:student_id>', methods=['GET'])
@admin_required
def get_student_info(student_id):
    """
    Get student information for a given student ID and return as JSON.
    Used by admin dashboard for computer control display.
    """
    if OFFLINE_MODE:
        return jsonify({
            'success': False,
            'error': 'Database is offline'
        })
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query the student information
        cursor.execute(
            "SELECT id, idno, firstname, lastname, middlename, course, year_level, email, profile_picture, sessions_used, max_sessions, points FROM students WHERE id = %s",
            (student_id,)
        )
        student = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if student:
            return jsonify({
                'success': True,
                'student': student
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Student not found'
            })
    
    except Exception as e:
        logging.error(f"Error getting student info: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Database error'
        })

@app.template_filter('strftime')
def _jinja2_filter_datetime(date_str, fmt=None):
    """Format a date string or convert the format."""
    date = datetime.now()
    if fmt:
        return date.strftime(fmt)
    return date.strftime('%Y-%m-%d %H:%M:%S')

@app.route('/submit_feedback/<int:session_id>', methods=['POST'])
@login_required
def submit_feedback(session_id):
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    rating = request.form.get('rating')
    comments = request.form.get('comments', '')
    
    if not rating:
        flash('Rating is required', 'error')
        return redirect(url_for('student_dashboard'))
    
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            flash('Rating must be between 1 and 5', 'error')
            return redirect(url_for('student_dashboard'))
    except ValueError:
        flash('Invalid rating value', 'error')
        return redirect(url_for('student_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if session exists and belongs to the current user
        cursor.execute("""
        SELECT * FROM sessions 
        WHERE id = %s AND student_id = %s
        """, (session_id, session['user_id']))
        
        session_data = cursor.fetchone()
        if not session_data:
            flash('Session not found or you are not authorized to submit feedback for this session', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Check if feedback already exists
        cursor.execute("""
        SELECT * FROM feedback 
        WHERE session_id = %s AND student_id = %s
        """, (session_id, session['user_id']))
        
        existing_feedback = cursor.fetchone()
        if existing_feedback:
            # Update existing feedback
            cursor.execute("""
            UPDATE feedback 
            SET rating = %s, comments = %s
            WHERE session_id = %s AND student_id = %s
            """, (rating, comments, session_id, session['user_id']))
            
            conn.commit()
            flash('Feedback updated successfully', 'success')
        else:
            # Insert new feedback
            cursor.execute("""
            INSERT INTO feedback (session_id, student_id, rating, comments)
            VALUES (%s, %s, %s, %s)
            """, (session_id, session['user_id'], rating, comments))
            
            conn.commit()
            flash('Thank you for your feedback!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to submit feedback: {str(e)}', 'error')
        logging.error(f"Error submitting feedback: {str(e)}")
    
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('student_dashboard'))

@app.route('/admin/export-report/<format>')
@admin_required
def export_report(format):
    try:
        from io import BytesIO
        from datetime import datetime
        import xlsxwriter
        import csv
        import pdfkit
        from flask import make_response
        
        # Get data for report
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get sessions data
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE (s.status = 'completed' OR s.status = 'cancelled')
          AND s.approval_status = 'approved'
        ORDER BY s.created_at DESC
        """)
        sessions = cursor.fetchall()
        
        # Get student data
        cursor.execute("SELECT * FROM students ORDER BY lastname, firstname")
        students = cursor.fetchall()
        
        # Get lab usage statistics
        cursor.execute("""
        SELECT 
            lab_room,
            COUNT(*) as count
        FROM sessions
        GROUP BY lab_room
        ORDER BY count DESC
        """)
        lab_stats = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Create report filename with timestamp
        filename = f'lab_report_{datetime.now().strftime("%Y%m%d%H%M%S")}'
        
        # Export based on format
        if format == 'excel':
            # Create Excel file
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output)
            
            # Add header styles
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center',
                'valign': 'vcenter'
            })
            
            subtitle_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'center',
                'valign': 'vcenter'
            })
            
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#003366',
                'color': 'white',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            
            # Create Sessions worksheet
            sessions_sheet = workbook.add_worksheet('Session History')
            
            # Add institutional header
            sessions_sheet.merge_range('A1:I1', 'UNIVERSITY OF CEBU MAIN CAMPUS', title_format)
            sessions_sheet.merge_range('A2:I2', 'COLLEGE OF COMPUTER STUDIES', subtitle_format)
            sessions_sheet.merge_range('A3:I3', 'COMPUTER LABORATORY SIT IN MONITORING SYSTEM', subtitle_format)
            sessions_sheet.merge_range('A4:I4', f'Report generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', workbook.add_format({'align': 'center'}))
            
            # Add blank row
            row_offset = 5
            
            # Add column headers for sessions
            headers = ['Student ID', 'Name', 'Course', 'Lab Room', 'Date & Time', 
                    'Check-In Time', 'Check-Out Time', 'Status', 'Purpose']
            
            for col, header in enumerate(headers):
                sessions_sheet.write(row_offset, col, header, header_format)
            
            # Write sessions data
            row = row_offset + 1
            for session in sessions:
                # Format course name
                course_name = session['course']
                if session['course'] == '1':
                    course_name = 'BSIT'
                elif session['course'] == '2':
                    course_name = 'BSCS'
                elif session['course'] == '3':
                    course_name = 'BSCE'
                
                # Format dates
                date_time_str = session['date_time'].strftime('%Y-%m-%d %H:%M') if session['date_time'] else 'N/A'
                check_in_str = session['check_in_time'].strftime('%I:%M %p') if session['check_in_time'] else 'N/A'
                check_out_str = session['check_out_time'].strftime('%I:%M %p') if session['check_out_time'] else 'N/A'
                
                # Get lab room name
                lab_room_name = format_lab_room(session['lab_room'])
                
                # Write data row
                sessions_sheet.write(row, 0, session['idno'])
                sessions_sheet.write(row, 1, f"{session['lastname']}, {session['firstname']}")
                sessions_sheet.write(row, 2, course_name)
                sessions_sheet.write(row, 3, lab_room_name)
                sessions_sheet.write(row, 4, date_time_str)
                sessions_sheet.write(row, 5, check_in_str)
                sessions_sheet.write(row, 6, check_out_str)
                sessions_sheet.write(row, 7, session['status'].capitalize())
                sessions_sheet.write(row, 8, session['purpose'] if session['purpose'] else 'N/A')
                
                row += 1
            
            # Create Lab Statistics worksheet
            stats_sheet = workbook.add_worksheet('Lab Statistics')
            
            # Add institutional header
            stats_sheet.merge_range('A1:C1', 'UNIVERSITY OF CEBU MAIN CAMPUS', title_format)
            stats_sheet.merge_range('A2:C2', 'COLLEGE OF COMPUTER STUDIES', subtitle_format)
            stats_sheet.merge_range('A3:C3', 'COMPUTER LABORATORY SIT IN MONITORING SYSTEM', subtitle_format)
            stats_sheet.merge_range('A4:C4', 'Lab Usage Statistics', subtitle_format)
            
            # Add column headers for lab stats
            stats_headers = ['Lab Room', 'Usage Count', 'Percentage']
            for col, header in enumerate(stats_headers):
                stats_sheet.write(6, col, header, header_format)
            
            # Calculate total usage
            total_usage = sum(lab['count'] for lab in lab_stats) if lab_stats else 0
            
            # Write lab stats data
            for i, lab in enumerate(lab_stats):
                lab_room_name = format_lab_room(lab['lab_room'])
                percentage = (lab['count'] / total_usage * 100) if total_usage > 0 else 0
                
                stats_sheet.write(7 + i, 0, lab_room_name)
                stats_sheet.write(7 + i, 1, lab['count'])
                stats_sheet.write(7 + i, 2, f"{percentage:.2f}%")
            
            # Adjust column widths
            sessions_sheet.set_column(0, 0, 12)  # Student ID
            sessions_sheet.set_column(1, 1, 25)  # Name
            sessions_sheet.set_column(2, 2, 10)  # Course
            sessions_sheet.set_column(3, 3, 15)  # Lab Room
            sessions_sheet.set_column(4, 4, 18)  # Date & Time
            sessions_sheet.set_column(5, 5, 15)  # Check-In Time
            sessions_sheet.set_column(6, 6, 15)  # Check-Out Time
            sessions_sheet.set_column(7, 7, 12)  # Status
            sessions_sheet.set_column(8, 8, 35)  # Purpose
            
            stats_sheet.set_column(0, 0, 20)  # Lab Room
            stats_sheet.set_column(1, 1, 15)  # Usage Count
            stats_sheet.set_column(2, 2, 15)  # Percentage
            
            # Close workbook and get output
            workbook.close()
            output.seek(0)
            
            # Create response
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'{filename}.xlsx'
            )
            
        elif format == 'csv':
            # Create CSV file
            output = BytesIO()
            output.write(b'UNIVERSITY OF CEBU MAIN CAMPUS\r\n')
            output.write(b'COLLEGE OF COMPUTER STUDIES\r\n')
            output.write(b'COMPUTER LABORATORY SIT IN MONITORING SYSTEM\r\n')
            output.write(f'Report generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\r\n\r\n'.encode('utf-8'))
            
            # Create CSV writer
            output.seek(0, 2)  # Move to the end of the file
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow(['Student ID', 'Name', 'Course', 'Lab Room', 'Date & Time', 
                           'Check-In Time', 'Check-Out Time', 'Status', 'Purpose'])
            
            # Write data
            for session in sessions:
                # Format course
                course_name = session['course']
                if session['course'] == '1':
                    course_name = 'BSIT'
                elif session['course'] == '2':
                    course_name = 'BSCS'
                elif session['course'] == '3':
                    course_name = 'BSCE'
                
                # Format dates
                date_time_str = session['date_time'].strftime('%Y-%m-%d %H:%M') if session['date_time'] else 'N/A'
                check_in_str = session['check_in_time'].strftime('%I:%M %p') if session['check_in_time'] else 'N/A'
                check_out_str = session['check_out_time'].strftime('%I:%M %p') if session['check_out_time'] else 'N/A'
                
                # Get lab room name
                lab_room_name = format_lab_room(session['lab_room'])
                
                # Write row
                writer.writerow([
                    session['idno'],
                    f"{session['lastname']}, {session['firstname']}",
                    course_name,
                    lab_room_name,
                    date_time_str,
                    check_in_str,
                    check_out_str,
                    session['status'].capitalize(),
                    session['purpose'] if session['purpose'] else 'N/A'
                ])
            
            # Add lab statistics to the CSV
            writer.writerow([])
            writer.writerow(['Lab Statistics'])
            writer.writerow(['Lab Room', 'Usage Count', 'Percentage'])
            
            # Calculate total usage
            total_usage = sum(lab['count'] for lab in lab_stats) if lab_stats else 0
            
            # Write lab stats
            for lab in lab_stats:
                lab_room_name = format_lab_room(lab['lab_room'])
                percentage = (lab['count'] / total_usage * 100) if total_usage > 0 else 0
                writer.writerow([lab_room_name, lab['count'], f"{percentage:.2f}%"])
            
            # Prepare response
            output.seek(0)
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = f"attachment; filename={filename}.csv"
            response.headers["Content-type"] = "text/csv"
            
            return response
            
        elif format == 'pdf':
            # Format data for the PDF template
            for session in sessions:
                # Format course
                if session['course'] == '1':
                    session['course_name'] = 'BSIT'
                elif session['course'] == '2':
                    session['course_name'] = 'BSCS'
                elif session['course'] == '3':
                    session['course_name'] = 'BSCE'
                else:
                    session['course_name'] = session['course']
                    
                # Format lab room
                session['lab_room_name'] = format_lab_room(session['lab_room'])
                
                # Format date and times
                if 'date_time' in session and session['date_time']:
                    session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
                
                if 'check_in_time' in session and session['check_in_time']:
                    session['check_in_formatted'] = session['check_in_time'].strftime('%I:%M %p')
                
                if 'check_out_time' in session and session['check_out_time']:
                    session['check_out_formatted'] = session['check_out_time'].strftime('%I:%M %p')
            
            # Calculate lab statistics percentages for the chart
            total_usage = sum(lab['count'] for lab in lab_stats) if lab_stats else 0
            for lab in lab_stats:
                lab['percentage'] = (lab['count'] / total_usage * 100) if total_usage > 0 else 0
                lab['lab_room_name'] = format_lab_room(lab['lab_room'])
            
            # Generate HTML content for the PDF
            html = render_template('pdf_report.html', 
                                   sessions=sessions, 
                                   lab_stats=lab_stats,
                                   report_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Configure PDF options
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None
            }
            
            # Generate PDF from HTML
            try:
                pdf = pdfkit.from_string(html, False, options=options)
                
                # Create response
                response = make_response(pdf)
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'attachment; filename={filename}.pdf'
                
                return response
            except OSError as e:
                if "No wkhtmltopdf executable found" in str(e):
                    flash('PDF export requires wkhtmltopdf to be installed. Please install it from https://github.com/JazzCore/python-pdfkit/wiki/Installing-wkhtmltopdf', 'error')
                    logging.error(f"wkhtmltopdf not installed: {str(e)}")
                else:
                    flash(f'Failed to export report to PDF: {str(e)}', 'error')
                    logging.error(f"PDF generation error: {str(e)}")
                return redirect(url_for('admin_dashboard'))
        
        else:
            flash(f'Unsupported export format: {format}', 'error')
            return redirect(url_for('admin_dashboard'))
            
    except ImportError as e:
        logging.error(f"Missing module for report export: {str(e)}")
        flash(f'Report export requires additional modules. Please install them with pip.', 'error')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        logging.error(f"Error exporting report: {str(e)}")
        flash(f'Failed to export report: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/cancel_session/<int:session_id>', methods=['POST'])
@login_required
def cancel_session(session_id):
    try:
        # Connect to db
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current user ID
        user_id = session.get('user_id')
        
        # Check if the session exists and belongs to the current user
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE id = %s AND student_id = %s
        """, (session_id, user_id))
        
        session_record = cursor.fetchone()
        
        if not session_record:
            flash('Session not found or you do not have permission to cancel it.', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Only active or pending sessions can be cancelled
        if session_record['status'] not in ['active', 'pending']:
            flash('Only active or pending sessions can be cancelled.', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Update session status to cancelled
        cursor.execute("""
            UPDATE sessions 
            SET status = 'cancelled' 
            WHERE id = %s
        """, (session_id,))
        
        conn.commit()
        flash('Session cancelled successfully.', 'success')
        
        cursor.close()
        conn.close()
        return redirect(url_for('student_dashboard'))
    
    except Exception as e:
        logging.error(f"Error cancelling session: {str(e)}")
        flash(f"Error cancelling session: {str(e)}", 'error')
        return redirect(url_for('student_dashboard'))

@app.template_filter('format_schedule_time')
def format_schedule_time(time_value):
    """Format timedelta or string time as HH:MM AM/PM for lab schedules"""
    import datetime
    
    if not time_value:
        return ""
    
    # Handle timedelta objects
    if isinstance(time_value, datetime.timedelta):
        total_seconds = int(time_value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        period = "AM" if hours < 12 else "PM"
        display_hours = hours if hours <= 12 else hours - 12
        # Handle midnight/noon special cases
        if hours == 0:
            display_hours = 12
        if hours == 12:
            display_hours = 12
            
        return f"{display_hours}:{minutes:02d} {period}"
    
    # Handle string times (assume HH:MM:SS format)
    elif isinstance(time_value, str):
        try:
            # Try to parse the time string
            time_parts = time_value.split(':')
            if len(time_parts) >= 2:
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                
                period = "AM" if hours < 12 else "PM"
                display_hours = hours if hours <= 12 else hours - 12
                # Handle midnight/noon special cases
                if hours == 0:
                    display_hours = 12
                if hours == 12:
                    display_hours = 12
                    
                return f"{display_hours}:{minutes:02d} {period}"
        except (ValueError, IndexError):
            # If parsing fails, return the original string
            return time_value
    
    # Return the original value for other types
    return str(time_value)

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

