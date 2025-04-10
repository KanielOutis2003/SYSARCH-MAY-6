from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
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
    'Lab 6': 'Lab 534',
    'Lab 7': 'Lab 536',
    'Lab 8': 'Lab 538',
    'Lab 9': 'Lab 540',
    'Lab 10': 'Lab 542',
    'Lab 11': 'Lab 544'
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all students
    cursor.execute("""
    SELECT s.*, 
           (SELECT COUNT(*) FROM sessions WHERE student_id = s.id AND status = 'active') as active_sessions,
           (SELECT COUNT(*) FROM sessions WHERE student_id = s.id AND status = 'completed') as completed_sessions
    FROM students s
    ORDER BY lastname, firstname
    """)
    students = cursor.fetchall()
    
    # Check if approval_status column exists in sessions table
    try:
        cursor.execute("SHOW COLUMNS FROM sessions LIKE 'approval_status'")
        has_approval_status = cursor.fetchone() is not None
    except:
        has_approval_status = False
    
    # Get active sessions (approved but not completed)
    if has_approval_status:
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE s.status = 'active' AND s.approval_status = 'approved'
        ORDER BY s.date_time DESC
        """)
    else:
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE s.status = 'active'
        ORDER BY s.date_time DESC
        """)
    active_sessions = cursor.fetchall()
    
    # Get pending session requests
    if has_approval_status:
        cursor.execute("""
        SELECT s.*, st.firstname, st.lastname, st.idno, st.course
        FROM sessions s
        JOIN students st ON s.student_id = st.id
        WHERE s.approval_status = 'pending'
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
    
    # Get current sit-ins (checked in but not checked out)
    cursor.execute("""
    SELECT s.*, st.firstname, st.lastname, st.idno, st.course
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    WHERE s.status = 'active' AND s.check_in_time IS NOT NULL AND s.check_out_time IS NULL
    ORDER BY s.check_in_time DESC
    """)
    current_sit_ins = cursor.fetchall()
    
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
    
    # Format timestamps in recent_activity
    for activity in recent_activity:
        import datetime
        if 'timestamp' in activity and activity['timestamp']:
            if isinstance(activity['timestamp'], datetime.datetime):
                activity['timestamp_date'] = activity['timestamp'].strftime('%Y-%m-%d')
                activity['timestamp_time'] = activity['timestamp'].strftime('%H:%M')
            else:
                activity['timestamp_date'] = activity['timestamp']
                activity['timestamp_time'] = ''
    
    # Get programming language statistics
    try:
        cursor.execute("""
        SELECT 
            programming_language,
            COUNT(*) as count,
            (COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sessions WHERE programming_language IS NOT NULL)) as percentage
        FROM sessions
        WHERE programming_language IS NOT NULL
        GROUP BY programming_language
        ORDER BY count DESC
        """)
        language_stats = cursor.fetchall()
        
        # Ensure we have data for all default languages
        default_languages = ['PHP', 'Java', 'Python', 'JavaScript', 'C++', 'C#', 'Ruby', 'Swift']
        existing_languages = [lang['programming_language'] for lang in language_stats]
        
        # Add missing languages with count 0
        for lang in default_languages:
            if lang not in existing_languages:
                language_stats.append({
                    'programming_language': lang,
                    'count': 0,
                    'percentage': 0
                })
    except Exception as e:
        print(f"Error getting language stats: {str(e)}")
        language_stats = []
    
    # Get lab room usage statistics
    try:
        cursor.execute("""
        SELECT 
            lab_room,
            COUNT(*) as count,
            (COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sessions)) as percentage,
            SUM(duration) as total_hours
        FROM sessions
        GROUP BY lab_room
        ORDER BY count DESC
        """)
        lab_stats = cursor.fetchall()
        
        # Ensure we have data for all lab rooms
        default_labs = ['Lab 1', 'Lab 2', 'Lab 3', 'Lab 4', 'Lab 5', 'Lab 6', 'Lab 7', 'Lab 8', 'Lab 9', 'Lab 10', 'Lab 11']
        existing_labs = [lab['lab_room'] for lab in lab_stats]
        
        # Add missing labs with count 0
        for lab in default_labs:
            if lab not in existing_labs:
                lab_stats.append({
                    'lab_room': lab,
                    'count': 0,
                    'percentage': 0,
                    'total_hours': 0
                })
    except Exception as e:
        print(f"Error getting lab stats: {str(e)}")
        lab_stats = []
    
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
    except:
        feedback_stats = {
            'total_feedback': 0,
            'average_rating': 0,
            'positive_feedback': 0,
            'negative_feedback': 0
        }
    
    # Get feedback list with student and session details
    try:
        cursor.execute("""
        SELECT f.*, s.lab_room, st.firstname, st.lastname, st.idno
        FROM feedback f
        JOIN sessions s ON f.session_id = s.id
        JOIN students st ON f.student_id = st.id
        ORDER BY f.created_at DESC
        """)
        feedback_list = cursor.fetchall()
    except:
        feedback_list = []
    
    # Get announcements
    try:
        cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
        announcements = cursor.fetchall()
    except:
        announcements = []
    
    # Get leaderboard data - top 5 students by points
    try:
        cursor.execute("""
        SELECT id, idno, firstname, lastname, course, points,
               (SELECT COUNT(*) FROM sessions WHERE student_id = students.id AND status = 'completed') as completed_sessions
        FROM students
        ORDER BY points DESC, completed_sessions DESC
        LIMIT 5
        """)
        leaderboard = cursor.fetchall()
    except Exception as e:
        print(f"Error getting leaderboard: {str(e)}")
        leaderboard = []
    
    # Format datetime fields in various session lists
    import datetime
    
    # Format active_sessions
    for session in active_sessions:
        if 'date_time' in session and session['date_time']:
            if isinstance(session['date_time'], datetime.datetime):
                session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
            else:
                session['date_time_formatted'] = session['date_time']
    
    # Format pending_sessions
    for session in pending_sessions:
        if 'date_time' in session and session['date_time']:
            if isinstance(session['date_time'], datetime.datetime):
                session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
            else:
                session['date_time_formatted'] = session['date_time']
    
    # Format current_sit_ins
    for session in current_sit_ins:
        if 'date_time' in session and session['date_time']:
            if isinstance(session['date_time'], datetime.datetime):
                session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d %H:%M')
            else:
                session['date_time_formatted'] = session['date_time']
    
    cursor.close()
    conn.close()
    
    return render_template('admin_dashboard.html', 
                          students=students, 
                          active_sessions=active_sessions,
                          pending_sessions=pending_sessions,
                          current_sit_ins=current_sit_ins,
                          recent_activity=recent_activity,
                          language_stats=language_stats,
                          lab_stats=lab_stats,
                          feedback_stats=feedback_stats,
                          feedback_list=feedback_list,
                          announcements=announcements,
                          leaderboard=leaderboard)

@app.route('/export-report/<format>')
@admin_required
def export_report(format):
    if format not in ['csv', 'pdf', 'excel']:
        flash('Invalid export format', 'error')
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all sessions
    cursor.execute("""
    SELECT s.*, st.firstname, st.lastname, st.idno, st.course
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    ORDER BY s.date_time DESC
    """)
    sessions = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if format == 'csv':
        # Generate CSV
        import csv
        from io import StringIO
        import datetime
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Student ID', 'Student Name', 'Course', 'Lab Room', 'Date & Time', 
                         'Duration', 'Programming Language', 'Purpose', 'Status'])
        
        # Map lab room codes to actual room numbers
        lab_room_mapping = {
            'Lab 1': 'Lab 524',
            'Lab 2': 'Lab 526',
            'Lab 3': 'Lab 528',
            'Lab 4': 'Lab 530',
            'Lab 5': 'Lab 532',
            'Lab 6': 'Lab 534',
            'Lab 7': 'Lab 536',
            'Lab 8': 'Lab 538',
            'Lab 9': 'Lab 540',
            'Lab 10': 'Lab 542',
            'Lab 11': 'Lab 544'
        }
        
        # Write data
        for session in sessions:
            course_name = ''
            if session['course'] == '1':
                course_name = 'BSIT'
            elif session['course'] == '2':
                course_name = 'BSCS'
            elif session['course'] == '3':
                course_name = 'BSCE'
            else:
                course_name = session['course']
            
            # Get the actual lab room name with number
            lab_room_display = lab_room_mapping.get(session['lab_room'], session['lab_room'])
                
            writer.writerow([
                session['id'],
                session['idno'],
                f"{session['firstname']} {session['lastname']}",
                course_name,
                lab_room_display,
                session['date_time'].strftime('%Y-%m-%d %H:%M') if isinstance(session['date_time'], datetime.datetime) else session['date_time'],
                session['duration'],
                session.get('programming_language', 'Not specified'),
                session.get('purpose', 'Not specified')[:50] + '...' if session.get('purpose') and len(session.get('purpose')) > 50 else session.get('purpose', 'Not specified'),
                session['status']
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=sit_in_history.csv"}
        )
    
    elif format == 'excel':
        # For Excel, we'd typically use a library like openpyxl or xlsxwriter
        # For simplicity, we'll just return a CSV with an Excel mimetype
        import csv
        from io import StringIO
        import datetime
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Student ID', 'Student Name', 'Course', 'Lab Room', 'Date & Time', 
                         'Duration', 'Programming Language', 'Purpose', 'Status'])
        
        # Write data
        for session in sessions:
            course_name = ''
            if session['course'] == '1':
                course_name = 'BSIT'
            elif session['course'] == '2':
                course_name = 'BSCS'
            elif session['course'] == '3':
                course_name = 'BSCE'
            else:
                course_name = session['course']
            
            # Get the actual lab room name with number
            lab_room_display = lab_room_mapping.get(session['lab_room'], session['lab_room'])
                
            writer.writerow([
                session['id'],
                session['idno'],
                f"{session['firstname']} {session['lastname']}",
                course_name,
                lab_room_display,
                session['date_time'].strftime('%Y-%m-%d %H:%M') if isinstance(session['date_time'], datetime.datetime) else session['date_time'],
                session['duration'],
                session.get('programming_language', 'Not specified'),
                session.get('purpose', 'Not specified')[:50] + '...' if session.get('purpose') and len(session.get('purpose')) > 50 else session.get('purpose', 'Not specified'),
                session['status']
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="application/vnd.ms-excel",
            headers={"Content-disposition": "attachment; filename=sit_in_history.xls"}
        )
    
    elif format == 'pdf':
        # For PDF generation, we'd typically use a library like ReportLab or WeasyPrint
        # This is a placeholder that would be implemented with a proper PDF library
        flash('PDF export is not implemented yet', 'info')
        return redirect(url_for('admin_dashboard'))

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Get form data
        lastname = request.form['lastname']
        firstname = request.form['firstname']
        middlename = request.form.get('middlename', '')
        email = request.form['email']
        
        # Handle profile picture upload
        profile_picture = None
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '' and allowed_file(file.filename):
                # Generate unique filename
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                profile_picture = unique_filename
        
        try:
            # Update student information
            if profile_picture:
                cursor.execute('''
                UPDATE students 
                SET lastname = %s, firstname = %s, middlename = %s, email = %s, profile_picture = %s
                WHERE id = %s
                ''', (lastname, firstname, middlename, email, profile_picture, session['user_id']))
                
                # Update session data with new profile picture
                session['student_info']['profile_picture'] = profile_picture
            else:
                cursor.execute('''
                UPDATE students 
                SET lastname = %s, firstname = %s, middlename = %s, email = %s
                WHERE id = %s
                ''', (lastname, firstname, middlename, email, session['user_id']))
            
            conn.commit()
            
            # Update session data
            session['student_info']['name'] = f"{firstname} {lastname}"
            
            flash('Profile updated successfully', 'success')
            return redirect(url_for('student_dashboard'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Profile update failed: {str(e)}', 'error')
            return redirect(url_for('edit_profile'))
    
    # Get student information for the form
    cursor.execute("SELECT * FROM students WHERE id = %s", (session['user_id'],))
    student = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('logout'))
    
    return render_template('edit_profile.html', student=student)

@app.route('/add-session', methods=['POST'])
@login_required
def add_session():
    if request.method == 'POST':
        student_id = session.get('user_id')
        lab_room = request.form.get('lab_room', 'Lab 1')
        date_time = request.form.get('date_time')
        duration = request.form.get('duration', 1)
        programming_language = request.form.get('programming_language')
        purpose = request.form.get('purpose')
        
        # Validate input
        if not date_time:
            flash('Please provide a date and time for your session', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Handle purpose logic - if programming_language is "Other", use purpose field,
        # otherwise use programming_language as the purpose
        if programming_language == 'Other':
            if not purpose:
                flash('Please specify a purpose for your session', 'error')
                return redirect(url_for('student_dashboard'))
        else:
            # If programming_language is selected and not "Other", default purpose will be "[language] Programming"
            if not purpose:
                purpose = f"{programming_language} Programming"
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if student has used all their sessions
            cursor.execute("SELECT sessions_used, max_sessions FROM students WHERE id = %s", (student_id,))
            result = cursor.fetchone()
            
            if not result:
                flash('Student not found', 'error')
                return redirect(url_for('student_dashboard'))
            
            sessions_used, max_sessions = result
            
            if sessions_used >= max_sessions:
                flash('You have reached your maximum allowed sessions.', 'error')
                return redirect(url_for('student_dashboard'))
            
            # Insert new session
            cursor.execute("""
            INSERT INTO sessions (student_id, lab_room, date_time, duration, programming_language, purpose, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            """, (student_id, lab_room, date_time, duration, programming_language, purpose))
            
            # Increment sessions used count
            cursor.execute("UPDATE students SET sessions_used = sessions_used + 1 WHERE id = %s", (student_id,))
            
            conn.commit()
            
            flash('Your session has been requested successfully. It is pending approval.', 'success')
            
        except Exception as e:
            flash(f'Failed to add session: {str(e)}', 'error')
            logging.error(f"Error adding session: {str(e)}")
            
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('student_dashboard'))

@app.route('/cancel-session/<int:session_id>', methods=['POST'])
@login_required
def cancel_session(session_id):
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if session belongs to the student
        cursor.execute("""
        SELECT * FROM sessions 
        WHERE id = %s AND student_id = %s
        """, (session_id, session['user_id']))
        sit_in_session = cursor.fetchone()
        
        if not sit_in_session:
            flash('Session not found or not authorized', 'error')
            return redirect(url_for('student_dashboard'))
        
        # Cancel session
        cursor.execute("""
        UPDATE sessions SET status = 'cancelled'
        WHERE id = %s
        """, (session_id,))
        
        # Update sessions used
        cursor.execute("""
        UPDATE students SET sessions_used = sessions_used - 1
        WHERE id = %s
        """, (session['user_id'],))
        
        conn.commit()
        flash('Session cancelled successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to cancel session: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('student_dashboard'))

@app.route('/admin/complete-session/<int:session_id>', methods=['POST'])
@admin_required
def complete_session(session_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Mark session as completed
        cursor.execute("""
        UPDATE sessions SET status = 'completed'
        WHERE id = %s
        """, (session_id,))
        
        conn.commit()
        flash('Session marked as completed', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to update session: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/end-student-session/<int:student_id>', methods=['POST'])
@admin_required
def end_student_session(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get student information
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Mark all active sessions for this student as completed
        cursor.execute("""
        UPDATE sessions SET status = 'completed'
        WHERE student_id = %s AND status = 'active'
        """, (student_id,))
        
        conn.commit()
        flash(f'All active sessions for student {student_id} have been ended', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to end sessions: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/get-student-info/<int:student_id>', methods=['GET'])
@admin_required
def get_student_info(student_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get student information
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Get student's active sessions
        cursor.execute("""
        SELECT * FROM sessions 
        WHERE student_id = %s AND status = 'active'
        ORDER BY date_time DESC
        """, (student_id,))
        sessions = cursor.fetchall()
        
        # Convert sessions to a serializable format
        serializable_sessions = []
        for s in sessions:
            session_dict = dict(s)
            session_dict['date_time'] = session_dict['date_time'].strftime('%Y-%m-%d %H:%M')
            session_dict['created_at'] = session_dict['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            serializable_sessions.append(session_dict)
        
        # Prepare student data
        student_data = {
            'id': student['id'],
            'idno': student['idno'],
            'name': f"{student['firstname']} {student['lastname']}",
            'firstname': student['firstname'],
            'lastname': student['lastname'],
            'middlename': student['middlename'],
            'course': student['course'],
            'year_level': student['year_level'],
            'email': student['email'],
            'profile_picture': student['profile_picture'],
            'sessions_used': student['sessions_used'],
            'max_sessions': student['max_sessions'],
            'active_sessions': serializable_sessions
        }
        
        return jsonify(student_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/approve-session/<int:session_id>', methods=['POST'])
@admin_required
def approve_session(session_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get session information
        cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Update session status to approved
        cursor.execute("""
        UPDATE sessions 
        SET approval_status = 'approved', status = 'active'
        WHERE id = %s
        """, (session_id,))
        
        # Increment sessions_used for the student
        cursor.execute("""
        UPDATE students 
        SET sessions_used = sessions_used + 1
        WHERE id = %s
        """, (session_data['student_id'],))
        
        conn.commit()
        flash('Session approved successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to approve session: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject-session/<int:session_id>', methods=['POST'])
@admin_required
def reject_session(session_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Update session status to rejected
        cursor.execute("""
        UPDATE sessions 
        SET approval_status = 'rejected', status = 'cancelled'
        WHERE id = %s
        """, (session_id,))
        
        conn.commit()
        flash('Session rejected', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to reject session: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/check-in/<int:session_id>', methods=['POST'])
@admin_required
def check_in_student(session_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Set check-in time to current time
        cursor.execute("""
        UPDATE sessions 
        SET check_in_time = NOW()
        WHERE id = %s
        """, (session_id,))
        
        conn.commit()
        flash('Student checked in successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to check in student: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/check-out/<int:session_id>', methods=['POST'])
@admin_required
def check_out_student(session_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get session information
        cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
        session_data = cursor.fetchone()
        
        if not session_data:
            flash('Session not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Set check-out time to current time and mark session as completed
        cursor.execute("""
        UPDATE sessions 
        SET check_out_time = NOW(), status = 'completed'
        WHERE id = %s
        """, (session_id,))
        
        # Award 3 points to the student for completing a sit-in session
        cursor.execute("""
        UPDATE students 
        SET points = points + 3
        WHERE id = %s
        """, (session_data['student_id'],))
        
        conn.commit()
        flash('Student checked out successfully and awarded 3 points', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to check out student: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/submit-feedback/<int:session_id>', methods=['POST'])
@login_required
def submit_feedback(session_id):
    if session.get('user_type') != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    rating = request.form.get('rating')
    comments = request.form.get('comments', '')
    
    if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
        flash('Please provide a valid rating (1-5)', 'error')
        return redirect(url_for('student_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if session belongs to the student
        cursor.execute("""
        SELECT * FROM sessions 
        WHERE id = %s AND student_id = %s
        """, (session_id, session['user_id']))
        
        session_data = cursor.fetchone()
        if not session_data:
            flash('Session not found or not authorized', 'error')
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
            flash('Feedback updated successfully', 'success')
        else:
            # Insert new feedback
            cursor.execute("""
            INSERT INTO feedback (session_id, student_id, rating, comments)
            VALUES (%s, %s, %s, %s)
            """, (session_id, session['user_id'], rating, comments))
            flash('Feedback submitted successfully', 'success')
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to submit feedback: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('student_dashboard'))

@app.route('/admin/announcements', methods=['GET'])
@admin_required
def view_announcements():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    announcements = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_announcements.html', announcements=announcements)

@app.route('/admin/add-announcement', methods=['POST'])
@admin_required
def add_announcement():
    title = request.form.get('title')
    content = request.form.get('content')
    
    if not title or not content:
        flash('Title and content are required', 'error')
        return redirect(url_for('view_announcements'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        INSERT INTO announcements (title, content)
        VALUES (%s, %s)
        """, (title, content))
        
        conn.commit()
        flash('Announcement added successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to add announcement: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('view_announcements'))

@app.route('/admin/edit-announcement', methods=['POST'])
@admin_required
def edit_announcement():
    announcement_id = request.form.get('announcement_id')
    title = request.form.get('title')
    content = request.form.get('content')
    
    if not announcement_id or not title or not content:
        flash('Announcement ID, title, and content are required', 'error')
        return redirect(url_for('view_announcements'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        UPDATE announcements 
        SET title = %s, content = %s
        WHERE id = %s
        """, (title, content, announcement_id))
        
        conn.commit()
        flash('Announcement updated successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to update announcement: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('view_announcements'))

@app.route('/admin/toggle-announcement/<int:announcement_id>', methods=['POST'])
@admin_required
def toggle_announcement(announcement_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        UPDATE announcements 
        SET is_active = NOT is_active
        WHERE id = %s
        """, (announcement_id,))
        
        conn.commit()
        flash('Announcement status updated', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to update announcement: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('view_announcements'))

@app.route('/admin/delete-announcement/<int:announcement_id>', methods=['POST'])
@admin_required
def delete_announcement(announcement_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
        
        conn.commit()
        flash('Announcement deleted successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to delete announcement: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('view_announcements'))

@app.route('/student/announcements', methods=['GET'])
@login_required
def student_announcements():
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
    
    # Get active announcements
    try:
        cursor.execute("SELECT * FROM announcements WHERE is_active = TRUE ORDER BY created_at DESC")
        announcements = cursor.fetchall()
    except:
        announcements = []
    
    cursor.close()
    conn.close()
    
    return render_template('student_announcements.html', student=student, announcements=announcements)

@app.route('/student/lab-schedules', methods=['GET'])
@login_required
def student_lab_schedules():
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
    
    # Get lab schedules grouped by lab room
    try:
        cursor.execute("""
        SELECT * FROM lab_schedules 
        ORDER BY lab_room, day_of_week, start_time
        """)
        lab_schedules = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching lab schedules: {str(e)}")
        lab_schedules = []
    
    # Format schedules by lab room for easier display
    lab_schedules_by_room = {}
    for schedule in lab_schedules:
        room = schedule['lab_room']
        if room not in lab_schedules_by_room:
            lab_schedules_by_room[room] = []
        lab_schedules_by_room[room].append(schedule)
    
    cursor.close()
    conn.close()
    
    return render_template('student_lab_schedules.html', 
                          student=student, 
                          lab_schedules=lab_schedules,
                          lab_schedules_by_room=lab_schedules_by_room)

@app.route('/admin/lab-schedules', methods=['GET'])
@admin_required
def admin_lab_schedules():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all lab schedules
    cursor.execute("""
    SELECT * FROM lab_schedules 
    ORDER BY lab_room, day_of_week, start_time
    """)
    lab_schedules = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_lab_schedules.html', lab_schedules=lab_schedules)

@app.route('/admin/add-lab-schedule', methods=['POST'])
@admin_required
def add_lab_schedule():
    lab_room = request.form.get('lab_room')
    day_of_week = request.form.get('day_of_week')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    
    if not all([lab_room, day_of_week, start_time, end_time]):
        flash('All fields are required', 'error')
        return redirect(url_for('admin_lab_schedules'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            INSERT INTO lab_schedules 
            (lab_room, day_of_week, start_time, end_time) 
            VALUES (%s, %s, %s, %s)
        """, (lab_room, day_of_week, start_time, end_time))
        
        conn.commit()
        flash('Lab schedule added successfully', 'success')
    except Exception as e:
        print(f"Error: {str(e)}")
        flash(f'Failed to add lab schedule: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_lab_schedules'))

@app.route('/admin/edit-lab-schedule', methods=['POST'])
@admin_required
def edit_lab_schedule():
    schedule_id = request.form.get('schedule_id')
    lab_room = request.form.get('lab_room')
    day_of_week = request.form.get('day_of_week')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    
    if not all([schedule_id, lab_room, day_of_week, start_time, end_time]):
        flash('All fields are required', 'error')
        return redirect(url_for('admin_lab_schedules'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            UPDATE lab_schedules 
            SET lab_room = %s, day_of_week = %s, start_time = %s, end_time = %s
            WHERE id = %s
        """, (lab_room, day_of_week, start_time, end_time, schedule_id))
        
        conn.commit()
        flash('Lab schedule updated successfully', 'success')
    except Exception as e:
        print(f"Error: {str(e)}")
        flash(f'Failed to update lab schedule: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_lab_schedules'))

@app.route('/admin/delete-lab-schedule/<int:schedule_id>', methods=['POST'])
@admin_required
def delete_lab_schedule(schedule_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM lab_schedules WHERE id = %s", (schedule_id,))
        
        conn.commit()
        flash('Lab schedule deleted successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to delete lab schedule: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_lab_schedules'))

@app.route('/admin/award-points/<int:student_id>', methods=['POST'])
@admin_required
def award_points(student_id):
    points = request.form.get('points', 0)
    
    if not points or not points.isdigit():
        flash('Valid point value is required', 'error')
        return redirect(url_for('admin_leaderboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get student information
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('admin_leaderboard'))
        
        # Update student points
        cursor.execute("""
        UPDATE students SET points = points + %s
        WHERE id = %s
        """, (points, student_id))
        
        conn.commit()
        flash(f'Points awarded successfully', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Failed to award points: {str(e)}', 'error')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_leaderboard'))

@app.route('/admin/leaderboard')
@admin_required
def admin_leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get total students count
        cursor.execute("SELECT COUNT(*) as count FROM students")
        total_students = cursor.fetchone()['count']
        
        # Get leaderboard data
        cursor.execute("""
        SELECT 
            s.id,
            s.idno,
            s.firstname,
            s.lastname,
            s.course,
            s.points,
            COUNT(ses.id) as total_sessions
        FROM students s
        LEFT JOIN sessions ses ON s.id = ses.student_id AND ses.status = 'completed'
        GROUP BY s.id, s.idno, s.firstname, s.lastname, s.course, s.points
        ORDER BY s.points DESC, total_sessions DESC
        """)
        leaderboard_data = cursor.fetchall()
        
    except Exception as e:
        print(f"Error getting leaderboard data: {str(e)}")
        total_students = 0
        leaderboard_data = []
    
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin_leaderboard.html', 
                         leaderboard_data=leaderboard_data,
                         total_students=total_students)

@app.route('/export-report/by-lab/<format>')
@admin_required
def export_report_by_lab(format):
    if format not in ['csv', 'excel', 'pdf']:
        flash('Invalid export format', 'error')
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get lab usage statistics
    cursor.execute("""
    SELECT 
        lab_room,
        COUNT(*) as total_sessions,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_sessions,
        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_sessions,
        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_sessions,
        SUM(duration) as total_hours
    FROM sessions
    GROUP BY lab_room
    ORDER BY total_sessions DESC
    """)
    lab_stats = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if format == 'csv':
        # Generate CSV
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Lab Room', 'Total Sessions', 'Completed Sessions', 'Active Sessions', 
                         'Pending Sessions', 'Cancelled Sessions', 'Total Hours'])
        
        # Write data
        for stat in lab_stats:
            lab_room_display = lab_room_mapping.get(stat['lab_room'], stat['lab_room'])
            writer.writerow([
                lab_room_display,
                stat['total_sessions'],
                stat['completed_sessions'],
                stat['active_sessions'],
                stat['pending_sessions'],
                stat['cancelled_sessions'],
                stat['total_hours']
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=lab_usage_report.csv"}
        )
    
    elif format == 'excel':
        # Generate Excel file
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Lab Room', 'Total Sessions', 'Completed Sessions', 'Active Sessions', 
                         'Pending Sessions', 'Cancelled Sessions', 'Total Hours'])
        
        # Write data
        for stat in lab_stats:
            lab_room_display = lab_room_mapping.get(stat['lab_room'], stat['lab_room'])
            writer.writerow([
                lab_room_display,
                stat['total_sessions'],
                stat['completed_sessions'],
                stat['active_sessions'],
                stat['pending_sessions'],
                stat['cancelled_sessions'],
                stat['total_hours']
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="application/vnd.ms-excel",
            headers={"Content-disposition": "attachment; filename=lab_usage_report.xls"}
        )
    
    elif format == 'pdf':
        # PDF export placeholder
        flash('PDF export is not implemented yet', 'info')
        return redirect(url_for('admin_dashboard'))

@app.route('/export-report/by-purpose/<format>')
@admin_required
def export_report_by_purpose(format):
    if format not in ['csv', 'excel', 'pdf']:
        flash('Invalid export format', 'error')
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get purpose statistics
    cursor.execute("""
    SELECT 
        COALESCE(programming_language, purpose, 'Not specified') as purpose,
        COUNT(*) as total_sessions,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
        SUM(duration) as total_hours
    FROM sessions
    GROUP BY purpose, programming_language
    ORDER BY total_sessions DESC
    """)
    purpose_stats = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if format == 'csv':
        # Generate CSV
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Purpose', 'Total Sessions', 'Completed Sessions', 'Total Hours'])
        
        # Write data
        for stat in purpose_stats:
            writer.writerow([
                stat['purpose'],
                stat['total_sessions'],
                stat['completed_sessions'],
                stat['total_hours']
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=purpose_usage_report.csv"}
        )
    
    elif format == 'excel':
        # Generate Excel file
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Purpose', 'Total Sessions', 'Completed Sessions', 'Total Hours'])
        
        # Write data
        for stat in purpose_stats:
            writer.writerow([
                stat['purpose'],
                stat['total_sessions'],
                stat['completed_sessions'],
                stat['total_hours']
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="application/vnd.ms-excel",
            headers={"Content-disposition": "attachment; filename=purpose_usage_report.xls"}
        )
    
    elif format == 'pdf':
        # PDF export placeholder
        flash('PDF export is not implemented yet', 'info')
        return redirect(url_for('admin_dashboard'))

@app.route('/sit-in-history')
@admin_required
def sit_in_history():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all sessions with student information
    cursor.execute("""
    SELECT s.*, st.firstname, st.lastname, st.idno, st.course
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    ORDER BY s.date_time DESC
    """)
    sessions = cursor.fetchall()
    
    # Format datetime objects for display
    for session in sessions:
        import datetime
        
        # Format date_time for display
        if 'date_time' in session and session['date_time']:
            if isinstance(session['date_time'], datetime.datetime):
                session['date_time_formatted'] = session['date_time'].strftime('%Y-%m-%d')
            else:
                session['date_time_formatted'] = session['date_time']
        
        # Format check_in_time
        if 'check_in_time' in session and session['check_in_time']:
            if isinstance(session['check_in_time'], datetime.datetime):
                session['check_in_time_formatted'] = session['check_in_time'].strftime('%H:%M')
            else:
                session['check_in_time_formatted'] = session['check_in_time']
        else:
            session['check_in_time_formatted'] = '-'
        
        # Format check_out_time
        if 'check_out_time' in session and session['check_out_time']:
            if isinstance(session['check_out_time'], datetime.datetime):
                session['check_out_time_formatted'] = session['check_out_time'].strftime('%H:%M')
            else:
                session['check_out_time_formatted'] = session['check_out_time']
        else:
            session['check_out_time_formatted'] = '-'
    
    cursor.close()
    conn.close()
    
    return render_template('sit_in_history.html', sessions=sessions)

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

@app.route('/admin/direct-sit-in', methods=['POST'])
@admin_required
def direct_sit_in():
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
        from datetime import datetime
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get today's sit-in sessions, including all completed ones
    cursor.execute("""
    SELECT s.*, st.firstname, st.lastname, st.idno, st.course
    FROM sessions s
    JOIN students st ON s.student_id = st.id
    WHERE DATE(s.date_time) = CURDATE() OR 
          DATE(s.check_in_time) = CURDATE() OR
          DATE(s.check_out_time) = CURDATE()
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
        import datetime
        
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all students for leaderboard
    cursor.execute("""
    SELECT id, idno, firstname, lastname, course, points,
           (SELECT COUNT(*) FROM sessions WHERE student_id = students.id AND status = 'completed') as completed_sessions
    FROM students
    ORDER BY points DESC, completed_sessions DESC
    """)
    leaderboard = cursor.fetchall()
    
    # Get current user's rank and stats
    student_id = session["user_id"]
    student_rank = 0
    points_to_next_rank = 0
    your_stats = None
    
    for i, student in enumerate(leaderboard):
        if student["id"] == student_id:
            student_rank = i + 1
            if i > 0:  # If not already at the top
                points_to_next_rank = leaderboard[i-1]["points"] - student["points"]
            your_stats = {
                "rank": student_rank,
                "points": student["points"],
                "completed_sessions": student["completed_sessions"],
                "points_to_next_rank": points_to_next_rank
            }
            break
    
    cursor.close()
    conn.close()
    
    return render_template('student_leaderboard.html', leaderboard=leaderboard, your_stats=your_stats, current_user={"id": student_id})

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
                                  resources=lab_resources_list,
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
                              resources=lab_resources_list,
                              current_lab_room=None)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('static/uploads', filename)

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
    points = request.form.get('points')
    reason = request.form.get('reason')
    
    if not student_id or not points:
        flash('Student ID and points are required', 'error')
        return redirect(url_for('admin_leaderboard'))
    
    try:
        points = int(points)
        if points <= 0 or points > 100:
            flash('Points must be between 1 and 100', 'error')
            return redirect(url_for('admin_leaderboard'))
    except ValueError:
        flash('Points must be a valid number', 'error')
        return redirect(url_for('admin_leaderboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if student exists
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('admin_leaderboard'))
        
        # Add points to the student
        cursor.execute("UPDATE students SET points = points + %s WHERE id = %s", (points, student_id))
        
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
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_leaderboard'))

@app.route('/admin/lab_resources/<int:resource_id>/toggle', methods=['POST'])
def toggle_lab_resource(resource_id):
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current status
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
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Error toggling resource status: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/lab_resources/<int:resource_id>/delete', methods=['POST'])
def delete_lab_resource(resource_id):
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
            
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
def student_lab_resources():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    # Connect to the database
    connection = sqlite3.connect('sit_in_db.db')
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    
    try:
        # Get only the enabled resources
        cursor.execute('''
            SELECT * FROM lab_resources 
            WHERE is_enabled = 1
            ORDER BY lab_room
        ''')
        lab_resources_list = cursor.fetchall()
        
        # Get lab room mapping for display
        lab_rooms = lab_room_mapping
        
        return render_template('student_lab_resources.html', 
                              lab_resources_list=lab_resources_list,
                              lab_rooms=lab_rooms,
                              username=session['username'])
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return render_template('student_lab_resources.html', 
                              lab_resources_list=[],
                              lab_rooms=lab_room_mapping,
                              username=session['username'])
    finally:
        cursor.close()
        connection.close()

# Initialize the database on startup
# Moved to if __name__ == '__main__' block

@app.template_filter('format_time')
def format_time(time_delta):
    """Format timedelta as HH:MM AM/PM"""
    if not time_delta:
        return ""
    
    total_seconds = int(time_delta.total_seconds())
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

