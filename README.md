# 📚 Library Management System

<div align="center">

### A Smart Library Management Solution Built with Python, Tkinter & MySQL

Manage books, members, issue/return operations, and library records through an intuitive desktop application.

![Python](https://img.shields.io/badge/Python-3.x-blue)
![MySQL](https://img.shields.io/badge/MySQL-Database-orange)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-green)
![Status](https://img.shields.io/badge/Status-Active-success)

</div>

---

## 🌟 Overview

The **Library Management System** is a desktop application designed to simplify library operations through an easy-to-use graphical interface. It enables librarians to efficiently manage books, members, book issuance, returns, and inventory records while storing data securely in a MySQL database.

---

## ✨ Key Features

### 📖 Book Management

* Add new books
* Update book details
* Delete books
* Search books instantly
* Track book availability

### 👥 Member Management

* Register members
* Update member information
* Maintain member records

### 🔄 Book Transactions

* Issue books
* Return books
* Track issued books
* Maintain borrowing history

### 🔍 Search & Tracking

* Search by title
* Search by author
* Search by category
* View available inventory

### 💾 Database Integration

* MySQL-based storage
* Persistent record management
* Fast data retrieval

---

## 🛠️ Technology Stack

| Component            | Technology             |
| -------------------- | ---------------------- |
| Programming Language | Python                 |
| GUI Framework        | Tkinter                |
| Database             | MySQL                  |
| Database Connector   | mysql-connector-python |
| Data Handling        | JSON, CSV              |

---

## 🏗️ System Architecture

```text
User
  │
  ▼
Tkinter GUI
  │
  ▼
Python Application Logic
  │
  ▼
MySQL Database
```

---

## 📂 Project Structure

```text
Library-Management-System/
│
├──LMS
|   ├── library_manager.py
|   ├── db_config.json
|   ├── Books.csv
|   ├── Requirements.txt
|   
└── README.md
```

---

## 🚀 Getting Started

### 1️⃣ Clone Repository

```bash
git clone https://github.com/Hardik7224/Library-Management-System.git
cd Library-Management-System
```

### 2️⃣ Install Dependencies

```bash
pip install -r Requirements.txt
```

### 3️⃣ Create Database

```sql
CREATE DATABASE library_management;
```

Import the SQL file:

```bash
mysql -u root -p library_management < database.sql
```

### 4️⃣ Configure Database

Update `db_config.json`

```json
{
  "host": "localhost",
  "user": "root",
  "password": "",
  "database": "library_management",
  "port": 3306
}
```

### 5️⃣ Run Application

```bash
python library_manager.py
```

---

## 🎯 Real-World Applications

🏫 School Libraries

🎓 College Libraries

📚 Personal Book Collections

🏢 Small Educational Institutions

🏛️ Community Libraries

---

## 📈 Future Enhancements

* Barcode Scanner Integration
* QR-Based Book Tracking
* Fine Calculation System
* Multi-User Authentication
* Admin & Librarian Roles
* Email Notifications
* PDF Report Generation
* Excel Export Functionality
* Cloud Database Support

---
