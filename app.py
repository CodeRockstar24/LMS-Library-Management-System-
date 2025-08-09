from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_bcrypt import Bcrypt
import mysql.connector
from datetime import date

app = Flask(__name__)
app.secret_key = '1206justin'  # Change this to your secret key
bcrypt = Bcrypt(app)

# MySQL connection parameters
MYSQL_HOST = 'localhost'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'mark1000'
MYSQL_DB = 'lms_db'

def get_db_connection():
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB
    )
    return conn

# --------- Existing Routes ---------

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    query = request.args.get('query', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if query:
        sql = "SELECT * FROM books WHERE title LIKE %s"
        like_query = f"%{query}%"
        cursor.execute(sql, (like_query,))
    else:
        cursor.execute("SELECT * FROM books")

    books = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('index.html', books=books)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("SELECT * FROM members WHERE email=%s", (email,))
        account = cursor.fetchone()
        if account:
            flash("Email already registered!")
            return redirect(url_for('register'))

        # Assign role='student' by default here
        role = 'student'

        cursor.execute(
            "INSERT INTO members (name, email, password_hash, join_date, role) VALUES (%s, %s, %s, CURDATE(), %s)",
            (name, email, password_hash, role)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful! Please login.")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM members WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            session['user_id'] = user['member_id']
            session['user_name'] = user['name']
            # Use 'student' as fallback role
            session['user_role'] = user.get('role', 'student')

            flash(f"Welcome {user['name']}!")

            if session['user_role'] == 'admin':
                return redirect(url_for('admin_members'))
            elif session['user_role'] == 'student':
                return redirect(url_for('student_page'))
            else:
                return redirect(url_for('index'))
        else:
            flash("Invalid email or password.")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('login'))

@app.route('/books/add', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        genre = request.form['genre']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO books (title, author, genre, available) VALUES (%s, %s, %s, %s)",
                       (title, author, genre, True))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Book added successfully!')
        return redirect(url_for('index'))

    return render_template('add_book.html')

@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        genre = request.form['genre']

        cursor.execute("""
            UPDATE books SET title=%s, author=%s, genre=%s WHERE book_id=%s
        """, (title, author, genre, book_id))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Book updated successfully!')
        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM books WHERE book_id=%s", (book_id,))
    book = cursor.fetchone()
    cursor.close()
    conn.close()

    if book is None:
        flash("Book not found.")
        return redirect(url_for('index'))

    return render_template('edit_book.html', book=book)

@app.route('/books/delete/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE book_id=%s", (book_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Book deleted successfully!')
    return redirect(url_for('index'))

@app.route('/books/borrow/<int:book_id>', methods=['POST'])
def borrow_book(book_id):
    if 'user_id' not in session:
        flash("Please log in to borrow books.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM books WHERE book_id=%s", (book_id,))
    book = cursor.fetchone()
    if not book:
        flash("Book not found.")
        cursor.close()
        conn.close()
        return redirect(url_for('index'))

    if not book['available']:
        flash("Book is currently unavailable.")
        cursor.close()
        conn.close()
        return redirect(url_for('index'))

    cursor.execute("UPDATE books SET available = FALSE WHERE book_id=%s", (book_id,))
    cursor.execute("INSERT INTO borrow_records (book_id, member_id, borrow_date, return_date) VALUES (%s, %s, CURDATE(), NULL)",
                   (book_id, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash(f"You have borrowed '{book['title']}'. Please return it on time.")
    return redirect(url_for('index'))

@app.route('/books/return/<int:record_id>', methods=['POST'])
def return_book(record_id):
    if 'user_id' not in session:
        flash("Please log in to return books.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT br.*, b.title 
        FROM borrow_records br 
        JOIN books b ON br.book_id = b.book_id 
        WHERE br.record_id=%s AND br.member_id=%s AND br.return_date IS NULL
    """, (record_id, user_id))
    record = cursor.fetchone()

    if not record:
        flash("Invalid return request or book already returned.")
        cursor.close()
        conn.close()
        return redirect(url_for('index'))

    cursor.execute("UPDATE borrow_records SET return_date = CURDATE() WHERE record_id = %s", (record_id,))
    cursor.execute("UPDATE books SET available = TRUE WHERE book_id = %s", (record['book_id'],))

    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Book '{record['title']}' returned successfully.")
    return redirect(url_for('my_borrowings'))

@app.route('/my_borrowings')
def my_borrowings():
    if 'user_id' not in session:
        flash("Please log in to view your borrowings.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT br.record_id, b.title, br.borrow_date, br.return_date 
        FROM borrow_records br
        JOIN books b ON br.book_id = b.book_id
        WHERE br.member_id = %s
        ORDER BY br.borrow_date DESC
    """, (user_id,))

    borrowings = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('my_borrowings.html', borrowings=borrowings)

def is_admin():
    return session.get('user_role') == 'admin'

@app.route('/admin/members')
def admin_members():
    if not is_admin():
        flash("Access denied.")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT member_id, name, email, join_date, role FROM members")
    members = cursor.fetchall()

    for member in members:
        cursor.execute("""
            SELECT br.record_id, b.title, br.borrow_date, br.return_date
            FROM borrow_records br
            JOIN books b ON br.book_id = b.book_id
            WHERE br.member_id = %s
            ORDER BY br.borrow_date DESC
        """, (member['member_id'],))
        member['borrow_history'] = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_members.html', members=members)

# --------- Binary Search & KMP String Matching ---------

def binary_search_books(books, query):
    """Perform binary search on a sorted list of books by title for exact matches."""
    low, high = 0, len(books) - 1
    query = query.lower()
    while low <= high:
        mid = (low + high) // 2
        mid_title = books[mid]['title'].lower()
        if mid_title == query:
            return books[mid]
        elif mid_title < query:
            low = mid + 1
        else:
            high = mid - 1
    return None

def compute_kmp_lps(pattern):
    """Computing longest prefix-suffix (LPS) array for KMP algorithm."""
    lps = [0] * len(pattern)
    length = 0
    i = 1
    while i < len(pattern):
        if pattern[i] == pattern[length]:
            length += 1
            lps[i] = length
            i += 1
        else:
            if length != 0:
                length = lps[length-1]
            else:
                lps[i] = 0
                i += 1
    return lps

def kmp_search(text, pattern):
    """Return True if pattern found in text using KMP algorithm."""
    if not pattern:
        return True
    lps = compute_kmp_lps(pattern)
    i = j = 0
    while i < len(text):
        if pattern[j] == text[i]:
            i += 1
            j += 1
            if j == len(pattern):
                return True
        else:
            if j != 0:
                j = lps[j-1]
            else:
                i += 1
    return False

@app.route('/search_advanced', methods=['GET'])
def search_advanced():
    query = request.args.get('query', '').strip().lower()
    if not query:
        flash("Please enter a search query.")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books ORDER BY title ASC")
    books = cursor.fetchall()
    cursor.close()
    conn.close()

    # Try exact match using binary search
    exact_match = binary_search_books(books, query)
    if exact_match:
        return render_template('search_results.html', books=[exact_match], message="Exact match found.")

    # Partial match using KMP substring search
    matched_books = [book for book in books if kmp_search(book['title'].lower(), query)]

    if matched_books:
        return render_template('search_results.html', books=matched_books, message="Partial matches found.")
    else:
        return render_template('search_results.html', books=[], message="No match found.")


@app.route('/student')
def student_page():
    if 'user_id' not in session or session.get('user_role') != 'student':
        flash("Access denied.")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get user info
    cursor.execute("SELECT name, email FROM members WHERE member_id=%s", (user_id,))
    user = cursor.fetchone()
    
    # Get borrowings & calculate fines
    cursor.execute("""
        SELECT br.record_id, b.title, br.borrow_date, br.return_date,
               DATEDIFF(CURDATE(), DATE_ADD(br.borrow_date, INTERVAL 14 DAY)) AS days_overdue
        FROM borrow_records br
        JOIN books b ON br.book_id = b.book_id
        WHERE br.member_id=%s AND (br.return_date IS NULL OR br.return_date > DATE_ADD(br.borrow_date, INTERVAL 14 DAY))
    """, (user_id,))
    borrowings = cursor.fetchall()
    
    # Calculate fines per borrowing (e.g., $1 per day overdue)
    for br in borrowings:
        br['fine'] = max(br['days_overdue'], 0) * 1  # $1 per day overdue
    
    cursor.close()
    conn.close()
    
    return render_template('student.html', user=user, borrowings=borrowings)


if __name__ == "__main__":
    app.run(debug=True)
