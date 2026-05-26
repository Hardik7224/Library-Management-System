# 📚 Library Management System

A modern desktop-based **Library Management System** built using **Python Tkinter** and **MySQL**, designed to manage book records through an intuitive graphical user interface.

This application supports complete CRUD operations, category-based filtering, statistics tracking, and theme customization, offering a practical real-world desktop database management experience.

---

## ✨ Features

### 📖 Book Management
- Add new books
- View all books
- Update existing records
- Delete books

### 🔍 Search & Filter
- Search books by:
  - Title
  - Author
  - Year
  - Category
- Live filtering
- Filter by category

### 📊 Statistics Dashboard
Displays:
- Total books
- Unique authors
- Books per category
- Books per year
- Available books
- Issued books

### 📦 Book Status
- Issue books
- Return books
- Track availability

### 🎨 UI Enhancements
- Clean Tkinter GUI
- Light / Dark mode toggle
- Responsive layout
- Treeview table display
- Scrollbar support
- Validation & popup alerts

### 📁 Data Export
- Export records to CSV

---

## 🛠️ Tech Stack

- **Python**
- **Tkinter**
- **MySQL**
- **mysql-connector-python**
- **CSV Export**

---

## 🗄️ Database Setup

### 1. Create database

Run in MySQL:

```sql
CREATE DATABASE library_db;

USE library_db;

CREATE TABLE books (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    year INT NOT NULL,
    category VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'Available'
);
```

---

### 2. Install dependency

```bash
pip install mysql-connector-python
```

---

### 3. Configure database connection

Inside `library_manager.py`, update:

```python
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="your_password",
        database="library_db"
    )
```

Replace:

```python
your_password
```

with your MySQL password.

---

## ▶️ Run the Project

Clone repository:

```bash
git clone https://github.com/your-username/library-management-system.git
```

Move into folder:

```bash
cd library-management-system
```

Run:

```bash
python library_manager.py
```

---

## 📂 Project Structure

```bash
library-management-system/
│
├── library_manager.py
├── README.md
└── library.csv   (optional export file)
```

---

## 📸 Preview

Main features include:

- Book entry form
- Category selector
- Search bar
- Statistics
- Treeview records
- Dark mode

---

## 🚀 Future Improvements

Planned upgrades:

- Login / admin authentication
- Book due date tracking
- Fine calculation
- Borrower management
- Search by ISBN
- SQLite support
- Packaging into `.exe`

---

## 🎯 Learning Outcomes

This project helped strengthen understanding of:

- Python GUI development with Tkinter
- MySQL database integration
- CRUD operations
- Event-driven programming
- File export handling
- Desktop application UI design

---

## 👨‍💻 Author

**Hardik**

GitHub: https://github.com/Hardik7224

---

## 📄 License

This project is open-source and available under the MIT License.
