from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
from datetime import datetime
import traceback

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Flash messages

# ✅ Database Configuration (Update with your details)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345'
app.config['MYSQL_DB'] = 'library'
mysql = MySQL(app)

# 🔹 Home Route
@app.route('/')
def home():
    return render_template('index.html')

# 🔹 View Books (with Search)
@app.route('/view_books')
def view_books():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    search_query = request.args.get('search', '')

    try:
        if search_query:
            cursor.execute("SELECT * FROM books WHERE title LIKE %s OR author LIKE %s", (f"%{search_query}%", f"%{search_query}%"))
        else:
            cursor.execute("SELECT * FROM books")
        
        books = cursor.fetchall()
    except Exception as e:
        print("❌ Error fetching books:", traceback.format_exc())
        books = []
    finally:
        cursor.close()
    
    return render_template('books.html', books=books, search_query=search_query)

# 🔹 Add Book
@app.route('/add_book', methods=['POST'])
def add_book():
    title = request.form['title']
    author = request.form['author']
    stock = request.form['stock']

    cursor = mysql.connection.cursor()
    
    try:
        cursor.execute("INSERT INTO books (title, author, stock) VALUES (%s, %s, %s)", (title, author, stock))
        mysql.connection.commit()
        flash("📚 Book added successfully!", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("❌ Error adding book!", "danger")
        print(traceback.format_exc())
    finally:
        cursor.close()

    return redirect(url_for('view_books'))

# 🔹 Issue Book
@app.route('/issue', methods=['POST'])
def issue_book():
    book_id = request.form['book_id']
    member_id = request.form['member_id']
    issue_date = request.form['issue_date']

    cursor = mysql.connection.cursor()

    try:
        # ✅ Check Member Debt
        cursor.execute("SELECT outstanding_debt FROM members WHERE id = %s", (member_id,))
        member = cursor.fetchone()
        
        if not member:
            flash("❌ Error: Member ID not found!", "danger")
            return redirect(url_for('view_books'))

        if member[0] > 500:
            flash("⚠️ Member has outstanding debt over Rs.500! Cannot issue book.", "warning")
            return redirect(url_for('view_books'))

        # ✅ Issue Book & Reduce Stock
        cursor.execute("INSERT INTO issued_books (book_id, member_id, issue_date) VALUES (%s, %s, %s)", (book_id, member_id, issue_date))
        cursor.execute("UPDATE books SET stock = stock - 1 WHERE id = %s AND stock > 0", (book_id,))
        mysql.connection.commit()

        flash("✅ Book issued successfully!", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("❌ Error issuing book!", "danger")
        print(traceback.format_exc())
    finally:
        cursor.close()

    return redirect(url_for('view_books'))

# 🔹 View Members
@app.route('/view_members')
def view_members():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        cursor.execute("SELECT * FROM members")
        members = cursor.fetchall()
    except Exception as e:
        print("❌ Error fetching members:", traceback.format_exc())
        members = []
    finally:
        cursor.close()

    return render_template('members.html', members=members)

# 🔹 Add Member
@app.route('/add_member', methods=['POST'])
def add_member():
    name = request.form['name']

    cursor = mysql.connection.cursor()
    
    try:
        cursor.execute("INSERT INTO members (name, outstanding_debt) VALUES (%s, %s)", (name, 0))
        mysql.connection.commit()
        flash("👤 Member added successfully!", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("❌ Error adding member!", "danger")
        print(traceback.format_exc())
    finally:
        cursor.close()

    return redirect(url_for('view_members'))

# 🔹 Return Book
@app.route('/return_book', methods=['POST'])
def return_book():
    book_id = request.form['book_id']
    member_id = request.form['member_id']
    return_date = request.form['return_date']

    cursor = mysql.connection.cursor()

    try:
        # ✅ Get Issue Date
        cursor.execute("SELECT issue_date FROM issued_books WHERE book_id = %s AND member_id = %s", (book_id, member_id))
        issue_date = cursor.fetchone()

        if not issue_date:
            flash("❌ No record of this book being issued to this member!", "danger")
            return redirect(url_for('view_books'))

        issue_date = str(issue_date[0])  # Convert to string for processing
        rent_fee = calculate_rent_fee(issue_date, return_date)

        # ✅ Update Member Debt & Return Book
        cursor.execute("UPDATE members SET outstanding_debt = outstanding_debt + %s WHERE id = %s", (rent_fee, member_id))
        cursor.execute("DELETE FROM issued_books WHERE book_id = %s AND member_id = %s", (book_id, member_id))
        cursor.execute("UPDATE books SET stock = stock + 1 WHERE id = %s", (book_id,))
        mysql.connection.commit()

        flash(f"✅ Book returned successfully! Rent Fee: Rs.{rent_fee}", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("❌ Error returning book!", "danger")
        print(traceback.format_exc())
    finally:
        cursor.close()

    return redirect(url_for('view_books'))

# 🔹 Calculate Rent Fee
def calculate_rent_fee(issue_date, return_date):
    try:
        issue_date = datetime.strptime(issue_date, "%Y-%m-%d")
        return_date = datetime.strptime(return_date, "%Y-%m-%d")
    except ValueError:
        return 0  # Invalid date format

    days_rented = (return_date - issue_date).days
    return max(days_rented * 10, 0)  # Rs.10 per day

# 🔹 View Issued Books
@app.route('/view_issued_books')
def view_issued_books():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT issued_books.id, books.title, members.name, issued_books.issue_date 
            FROM issued_books 
            JOIN books ON issued_books.book_id = books.id 
            JOIN members ON issued_books.member_id = members.id
        """)
        issued_books = cursor.fetchall()
    except Exception as e:
        print("❌ Error fetching issued books:", traceback.format_exc())
        issued_books = []
    finally:
        cursor.close()

    return render_template('issued_books.html', issued_books=issued_books)

# 🔹 Run Flask App
if __name__ == "__main__":
    app.run(debug=True)
