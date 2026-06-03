import os
import json
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import mysql.connector
from mysql.connector import Error

# ==============================================================================
# DATABASE HELPER CLASS
# ==============================================================================
class DatabaseHelper:
    """Manages all MySQL database operations, schema creation, and configuration."""
    
    def __init__(self, config_path="db_config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.connection = None

    def load_config(self):
        """Loads configuration from JSON file or uses standard defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Validate keys are present
                    required_keys = ["host", "user", "password", "port"]
                    if all(key in config for key in required_keys):
                        return config
            except Exception:
                pass
        
        # Default fallback config
        return {
            "host": "localhost",
            "user": "root",
            "password": "",  # Empty default, user-configurable in UI
            "port": 3306
        }

    def save_config(self, host, user, password, port):
        """Saves custom connection configuration details to config path."""
        self.config = {
            "host": host.strip(),
            "user": user.strip(),
            "password": password,
            "port": int(port)
        }
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True, "Config saved"
        except Exception as e:
            return False, f"Failed to save config file: {str(e)}"

    def connect_and_initialize(self):
        """Attempts to connect to MySQL server, creates database and table if missing."""
        try:
            # 1. Connect without specifying database to create it if it doesn't exist
            conn = mysql.connector.connect(
                host=self.config["host"],
                user=self.config["user"],
                password=self.config["password"],
                port=self.config["port"],
                connect_timeout=3  # Fast timeout for responsive GUI connection testing
            )
            cursor = conn.cursor()
            cursor.execute("CREATE DATABASE IF NOT EXISTS library_db")
            cursor.close()
            conn.close()

            # 2. Reconnect specifically to library_db database
            self.connection = mysql.connector.connect(
                host=self.config["host"],
                user=self.config["user"],
                password=self.config["password"],
                port=self.config["port"],
                database="library_db",
                connect_timeout=3
            )
            
            # 3. Create table books if not exists
            cursor = self.connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    author VARCHAR(255) NOT NULL,
                    year INT NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'Available'
                )
            """)
            self.connection.commit()
            cursor.close()
            return True, "Connected and schema initialized successfully!"
            
        except Error as e:
            # Gracefully reset connection
            if self.connection and self.connection.is_connected():
                self.connection.close()
            self.connection = None
            
            error_msg = f"MySQL Error {e.errno}: {e.msg}"
            if e.errno == 2003 or e.errno == 2002:
                error_msg = "Could not connect to MySQL server. Please make sure the MySQL service is running."
            elif e.errno == 1045:
                error_msg = "Access Denied. Please verify your MySQL username and password."
            elif e.errno == 1049:
                error_msg = "Database creation failed. Double check your user privileges."
                
            return False, error_msg
        except Exception as e:
            self.connection = None
            return False, f"Unexpected error: {str(e)}"

    def get_connection(self):
        """Ensures and returns a live connection to the database."""
        if self.connection and self.connection.is_connected():
            return self.connection
        
        # Connection closed or lost, re-establish it
        try:
            self.connection = mysql.connector.connect(
                host=self.config["host"],
                user=self.config["user"],
                password=self.config["password"],
                port=self.config["port"],
                database="library_db",
                connect_timeout=3
            )
            return self.connection
        except Exception:
            return None

    def check_duplicate(self, title, author, exclude_id=None):
        """Returns True if a book with the same title and author exists."""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            if exclude_id:
                cursor.execute(
                    "SELECT id FROM books WHERE LOWER(TRIM(title)) = LOWER(TRIM(%s)) AND LOWER(TRIM(author)) = LOWER(TRIM(%s)) AND id != %s",
                    (title, author, exclude_id)
                )
            else:
                cursor.execute(
                    "SELECT id FROM books WHERE LOWER(TRIM(title)) = LOWER(TRIM(%s)) AND LOWER(TRIM(author)) = LOWER(TRIM(%s))",
                    (title, author)
                )
            row = cursor.fetchone()
            cursor.close()
            return row is not None
        except Exception:
            return False

    def add_book(self, title, author, year, category):
        """Inserts a new book record into the database."""
        if self.check_duplicate(title, author):
            return False, f"Duplicate Warning: '{title}' by '{author}' is already in the library."
        
        conn = self.get_connection()
        if not conn:
            return False, "Database not connected. Please verify connection configurations."
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO books (title, author, year, category, status) VALUES (%s, %s, %s, %s, 'Available')",
                (title.strip(), author.strip(), int(year), category.strip())
            )
            conn.commit()
            cursor.close()
            return True, "Book added successfully!"
        except Exception as e:
            return False, f"Database Insertion Error: {str(e)}"

    def get_all_books(self):
        """Fetches all book records in the database."""
        conn = self.get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM books")
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception:
            return []

    def update_book(self, book_id, title, author, year, category):
        """Updates an existing book record details."""
        if self.check_duplicate(title, author, exclude_id=book_id):
            return False, f"Duplicate Warning: Another book titled '{title}' by '{author}' already exists."

        conn = self.get_connection()
        if not conn:
            return False, "Database not connected"
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE books SET title = %s, author = %s, year = %s, category = %s WHERE id = %s",
                (title.strip(), author.strip(), int(year), category.strip(), int(book_id))
            )
            conn.commit()
            cursor.close()
            return True, "Book updated successfully!"
        except Exception as e:
            return False, f"Database Update Error: {str(e)}"

    def delete_book(self, book_id):
        """Removes a book record from the database."""
        conn = self.get_connection()
        if not conn:
            return False, "Database not connected"
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM books WHERE id = %s", (int(book_id),))
            conn.commit()
            cursor.close()
            return True, "Book deleted successfully!"
        except Exception as e:
            return False, f"Database Deletion Error: {str(e)}"

    def change_status(self, book_id, status):
        """Updates the borrowing status of a book (Available/Issued)."""
        conn = self.get_connection()
        if not conn:
            return False, "Database not connected"
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE books SET status = %s WHERE id = %s", (status, int(book_id)))
            conn.commit()
            cursor.close()
            return True, f"Book status updated to '{status}'"
        except Exception as e:
            return False, f"Database Status Update Error: {str(e)}"

    def get_books_filtered_sorted(self, query_str="", category_filter="All", sort_by="id", order="ASC"):
        """Performs search, filter, and sorting operations in a single query."""
        conn = self.get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Map secure sorting options to avoid SQL injection
            allowed_sorts = {"title": "title", "year": "year", "id": "id"}
            order_by = allowed_sorts.get(sort_by.lower(), "id")
            order_direction = "DESC" if order.upper() == "DESC" else "ASC"
            
            sql = "SELECT * FROM books WHERE 1=1"
            params = []
            
            if category_filter and category_filter != "All":
                sql += " AND category = %s"
                params.append(category_filter)
                
            if query_str:
                # Support partial match across Title, Author, Year, and Category
                sql += " AND (title LIKE %s OR author LIKE %s OR CAST(year AS CHAR) LIKE %s OR category LIKE %s)"
                like_param = f"%{query_str}%"
                params.extend([like_param, like_param, like_param, like_param])
                
            sql += f" ORDER BY {order_by} {order_direction}"
            
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception:
            return []

    def get_statistics(self):
        """Calculates all key metrics for the Library dashboard."""
        conn = self.get_connection()
        stats = {
            "total_books": 0,
            "unique_authors": 0,
            "issued_count": 0,
            "available_count": 0,
            "by_category": {},
            "by_year": {}
        }
        if not conn:
            return stats
            
        try:
            cursor = conn.cursor()
            
            # Total books
            cursor.execute("SELECT COUNT(*) FROM books")
            stats["total_books"] = cursor.fetchone()[0]
            
            # Unique authors
            cursor.execute("SELECT COUNT(DISTINCT author) FROM books")
            stats["unique_authors"] = cursor.fetchone()[0]
            
            # Issued
            cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'Issued'")
            stats["issued_count"] = cursor.fetchone()[0]
            
            # Available
            cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'Available'")
            stats["available_count"] = cursor.fetchone()[0]
            
            # Books per category
            cursor.execute("SELECT category, COUNT(*) FROM books GROUP BY category")
            stats["by_category"] = dict(cursor.fetchall())
            
            # Books per year (top 10 years by book count)
            cursor.execute("SELECT year, COUNT(*) FROM books GROUP BY year ORDER BY COUNT(*) DESC LIMIT 10")
            stats["by_year"] = dict(cursor.fetchall())
            
            cursor.close()
            return stats
        except Exception:
            return stats


# ==============================================================================
# CUSTOM MODERN GUI COMPONENT IMPLEMENTATIONS
# ==============================================================================
class ModernEntry(tk.Frame):
    """A highly polished Tkinter Entry component with padding and custom focus indicator."""
    
    def __init__(self, parent, width=25, show="", placeholder="", bg_color="#ffffff", border_color="#cbd5e1", focus_color="#008080", text_color="#1e293b", placeholder_color="#94a3b8"):
        super().__init__(parent, bg=border_color, bd=1)
        self.bg_color = bg_color
        self.border_color = border_color
        self.focus_color = focus_color
        self.text_color = text_color
        self.placeholder_color = placeholder_color
        self.placeholder = placeholder
        
        self.entry_frame = tk.Frame(self, bg=bg_color, bd=0)
        self.entry_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        self.entry = tk.Entry(
            self.entry_frame,
            bg=bg_color,
            fg=text_color if not placeholder else placeholder_color,
            relief="flat",
            bd=0,
            width=width,
            show=show,
            font=("Segoe UI", 10),
            insertbackground=text_color
        )
        self.entry.pack(fill="both", expand=True, padx=8, pady=6)
        
        if placeholder:
            self.entry.insert(0, placeholder)
            self.entry.bind("<FocusIn>", self._clear_placeholder)
            self.entry.bind("<FocusOut>", self._set_placeholder)
            
        self.entry.bind("<FocusIn>", self._on_focus, add="+")
        self.entry.bind("<FocusOut>", self._on_unfocus, add="+")

    def get(self):
        val = self.entry.get()
        if val == self.placeholder:
            return ""
        return val.strip()

    def set_text(self, text):
        self.entry.delete(0, tk.END)
        self.entry.config(fg=self.text_color)
        self.entry.insert(0, text)

    def clear(self):
        self.entry.delete(0, tk.END)
        if self.placeholder:
            self.entry.config(fg=self.placeholder_color)
            self.entry.insert(0, self.placeholder)

    def _clear_placeholder(self, event):
        if self.entry.get() == self.placeholder:
            self.entry.delete(0, tk.END)
            self.entry.config(fg=self.text_color)

    def _set_placeholder(self, event):
        if not self.entry.get():
            self.entry.config(fg=self.placeholder_color)
            self.entry.insert(0, self.placeholder)

    def _on_focus(self, event):
        self.config(bg=self.focus_color)

    def _on_unfocus(self, event):
        self.config(bg=self.border_color)
        
    def set_colors(self, bg_color, border_color, focus_color, text_color, placeholder_color):
        self.bg_color = bg_color
        self.border_color = border_color
        self.focus_color = focus_color
        self.text_color = text_color
        self.placeholder_color = placeholder_color
        
        self.config(bg=border_color)
        self.entry_frame.config(bg=bg_color)
        
        is_placeholder = self.entry.get() == self.placeholder
        self.entry.config(
            bg=bg_color,
            fg=placeholder_color if is_placeholder else text_color,
            insertbackground=text_color
        )


class ModernButton(tk.Button):
    """A sleek modern flat button that supports custom colors, hover, and click animations."""
    
    def __init__(self, parent, text, command=None, bg_color="#008080", hover_color="#00a6a6", text_color="#ffffff", button_type="primary", font=("Segoe UI", 10, "bold"), padding_y=6, padding_x=12):
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.button_type = button_type
        
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=text_color,
            activebackground=hover_color,
            activeforeground=text_color,
            font=font,
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=padding_x,
            pady=padding_y
        )
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self.config(bg=self.hover_color)

    def _on_leave(self, event):
        self.config(bg=self.bg_color)
        
    def set_colors(self, bg_color, hover_color, text_color):
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.config(
            bg=bg_color,
            fg=text_color,
            activebackground=hover_color,
            activeforeground=text_color
        )


# ==============================================================================
# MAIN LIBRARY APPLICATION CLASS
# ==============================================================================
class LMSApp(tk.Tk):
    """Main LMS GUI window controller."""
    
    def __init__(self):
        super().__init__()
        
        self.title("📖 Library Management System")
        self.geometry("1200x720")
        self.minsize(1080, 650)
        
        # Center application window
        self.center_window(1200, 720)
        
        # Database Instance
        self.db = DatabaseHelper()
        
        # Global states
        self.current_theme = "light"
        self.selected_book_id = None
        self.is_connected = False
        
        # Track active sort constraints
        self.current_sort_col = "id"
        self.current_sort_order = "ASC"
        
        # Load theme design assets
        self.define_colors()
        
        # Create custom styling using TTK styles
        self.style = ttk.Style()
        
        # Build core panels
        self.build_layouts()
        
        # Check database connection in the background
        self.test_initial_connection()

    def center_window(self, width, height):
        """Helper to center the Tkinter window on screen."""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def define_colors(self):
        """Initializes the style palettes for Light and Dark modes."""
        self.colors = {
            "light": {
                "bg": "#f1f5f9",           # Tailwind slate-100
                "card_bg": "#ffffff",      # Solid white panels
                "primary": "#008080",      # Classic solid Teal
                "primary_light": "#0d9488",# Slightly lighter teal (Teal-600)
                "text": "#0f172a",         # Slate-900
                "text_muted": "#64748b",   # Slate-500
                "border": "#e2e8f0"        # Slate-200
            },
            "dark": {
                "bg": "#0f172a",           # Slate-900
                "card_bg": "#1e293b",      # Slate-800
                "primary": "#14b8a6",      # Bright Teal/Cyan accent (Teal-500)
                "primary_light": "#2dd4bf",# Vibrant Cyan/Teal (Teal-400)
                "text": "#f8fafc",         # Slate-50
                "text_muted": "#94a3b8",   # Slate-400
                "border": "#334155"        # Slate-700
            }
        }

    # ==========================================================================
    # LAYOUT AND INTERFACE CONSTRUCTION
    # ==========================================================================
    def build_layouts(self):
        """Constructs and packs the panel layouts."""
        
        # Configure root responsive weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # Content area expands
        
        # 1. HEADER SECTION
        self.header_frame = tk.Frame(self, height=70, relief="flat", bd=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_propagate(False)
        self.header_frame.columnconfigure(1, weight=1)
        self.header_frame.rowconfigure(0, weight=1)
        
        # Logo Icon and Label
        self.header_title = tk.Label(
            self.header_frame,
            text="📖 LIBRARY MANAGER",
            font=("Segoe UI", 18, "bold")
        )
        self.header_title.label_type = "heading"
        self.header_title.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        # Theme and Database Status Operations Frame (Top Right)
        self.header_right = tk.Frame(self.header_frame, bg="white")
        self.header_right.grid(row=0, column=2, padx=20, pady=10, sticky="e")
        
        self.conn_dot = tk.Canvas(self.header_right, width=12, height=12, bd=0, highlightthickness=0)
        self.conn_dot.pack(side="left", padx=(0, 6))
        self.conn_dot_indicator = self.conn_dot.create_oval(2, 2, 10, 10, fill="#ef4444")
        
        self.conn_status_lbl = tk.Label(
            self.header_right,
            text="Disconnected",
            font=("Segoe UI", 9, "bold")
        )
        self.conn_status_lbl.pack(side="left", padx=(0, 20))
        
        self.theme_btn = ModernButton(
            self.header_right,
            text="🌙 Dark Mode",
            command=self.toggle_theme,
            button_type="secondary",
            font=("Segoe UI", 9, "bold"),
            padding_x=10,
            padding_y=4
        )
        self.theme_btn.pack(side="left")
        
        # 2. MAIN WORKSPACE CONTAINER
        self.main_container = tk.Frame(self, relief="flat", bd=0)
        self.main_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
        self.main_container.columnconfigure(0, weight=3)  # Form frame (3 parts)
        self.main_container.columnconfigure(1, weight=7)  # Table grid frame (7 parts)
        self.main_container.rowconfigure(0, weight=1)
        
        # 2A. LEFT FRAME: BOOK FORM
        self.form_panel = tk.Frame(self.main_container, relief="flat", bd=0)
        self.form_panel.is_panel = True
        self.form_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        self.form_panel.columnconfigure(0, weight=1)
        
        # Left Panel Header
        self.form_header = tk.Label(
            self.form_panel,
            text="Book Details Manager",
            font=("Segoe UI", 13, "bold"),
            anchor="w"
        )
        self.form_header.label_type = "panel_heading"
        self.form_header.in_panel = True
        self.form_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 15))
        
        # Scrollable panel in form frame if contents exceed screen height
        self.form_fields_frame = tk.Frame(self.form_panel, bd=0)
        self.form_fields_frame.is_panel = True
        self.form_fields_frame.grid(row=1, column=0, sticky="nsew", padx=20)
        self.form_fields_frame.columnconfigure(1, weight=1)
        
        # FORM FIELD: BOOK ID (Read Only)
        tk.Label(self.form_fields_frame, text="Book ID", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.book_id_entry = ModernEntry(self.form_fields_frame, placeholder="Auto-generated", width=20)
        self.book_id_entry.entry.config(state="disabled")
        self.book_id_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        
        # FORM FIELD: BOOK TITLE
        tk.Label(self.form_fields_frame, text="Book Title *", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=2, column=0, sticky="w", pady=(0, 2))
        self.title_entry = ModernEntry(self.form_fields_frame, placeholder="e.g. Clean Code", width=20)
        self.title_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        
        # FORM FIELD: AUTHOR
        tk.Label(self.form_fields_frame, text="Author *", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=4, column=0, sticky="w", pady=(0, 2))
        self.author_entry = ModernEntry(self.form_fields_frame, placeholder="e.g. Robert C. Martin", width=20)
        self.author_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        
        # FORM FIELD: PUBLICATION YEAR
        tk.Label(self.form_fields_frame, text="Publication Year *", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=6, column=0, sticky="w", pady=(0, 2))
        self.year_entry = ModernEntry(self.form_fields_frame, placeholder="e.g. 2008", width=20)
        self.year_entry.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        
        # FORM FIELD: CATEGORY
        tk.Label(self.form_fields_frame, text="Category *", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=8, column=0, sticky="w", pady=(0, 2))
        
        # Outer border frame for stylish combobox
        self.category_cb_border = tk.Frame(self.form_fields_frame, bg="#cbd5e1", bd=1)
        self.category_cb_border.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        
        self.category_cb = ttk.Combobox(
            self.category_cb_border,
            values=["Fiction", "Science", "History", "Biography", "Other"],
            state="readonly",
            font=("Segoe UI", 10)
        )
        self.category_cb.set("Select")
        self.category_cb.pack(fill="both", expand=True, padx=1, pady=1)
        
        # FORM ACTION BUTTONS
        self.form_actions_frame = tk.Frame(self.form_panel, bd=0)
        self.form_actions_frame.is_panel = True
        self.form_actions_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.form_actions_frame.columnconfigure(0, weight=1)
        self.form_actions_frame.columnconfigure(1, weight=1)
        
        # ROW 1 Buttons: Add & Update
        self.btn_add = ModernButton(self.form_actions_frame, text="➕ Add Book", command=self.add_book)
        self.btn_add.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=4)
        
        self.btn_update = ModernButton(self.form_actions_frame, text="🔄 Update", command=self.update_book)
        self.btn_update.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=4)
        
        # ROW 2 Buttons: Issue & Return
        self.btn_issue = ModernButton(self.form_actions_frame, text="📤 Issue Book", command=self.issue_book)
        self.btn_issue.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=4)
        
        self.btn_return = ModernButton(self.form_actions_frame, text="📥 Return Book", command=self.return_book)
        self.btn_return.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=4)
        
        # ROW 3 Buttons: Clear & Delete (DANGER STYLE BUTTONS)
        self.btn_clear = ModernButton(self.form_actions_frame, text="🧹 Clear Form", command=self.clear_form, button_type="secondary")
        self.btn_clear.grid(row=2, column=0, sticky="ew", padx=(0, 5), pady=4)
        
        self.btn_delete = ModernButton(self.form_actions_frame, text="🗑️ Delete", command=self.delete_book, button_type="danger")
        self.btn_delete.grid(row=2, column=1, sticky="ew", padx=(5, 0), pady=4)
        
        # 2B. RIGHT FRAME: DATABASE LIST & GRID CONTROLS
        self.grid_panel = tk.Frame(self.main_container, relief="flat", bd=0)
        self.grid_panel.is_panel = True
        self.grid_panel.grid(row=0, column=1, sticky="nsew", padx=(15, 0))
        self.grid_panel.columnconfigure(0, weight=1)
        self.grid_panel.rowconfigure(2, weight=1)  # Table stretches to fill height
        
        # Search & Filter Controls Frame (Row 0)
        self.search_filter_frame = tk.Frame(self.grid_panel, bd=0)
        self.search_filter_frame.is_panel = True
        self.search_filter_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.search_filter_frame.columnconfigure(0, weight=1) # Search expands
        
        # Search Box
        self.search_entry = ModernEntry(
            self.search_filter_frame, 
            placeholder="🔍 Live Search by title, author, year...",
            width=30
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        # Bind typing to live search trigger
        self.search_entry.entry.bind("<KeyRelease>", self.on_live_search)
        
        # Dropdown Category Filter
        self.filter_cb_border = tk.Frame(self.search_filter_frame, bg="#cbd5e1", bd=1)
        self.filter_cb_border.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        self.filter_cb = ttk.Combobox(
            self.filter_cb_border,
            values=["All", "Fiction", "Science", "History", "Biography", "Other"],
            state="readonly",
            font=("Segoe UI", 10),
            width=18
        )
        self.filter_cb.set("Filter by Category")
        self.filter_cb.pack(fill="both", expand=True, padx=1, pady=1)
        self.filter_cb.bind("<<ComboboxSelected>>", self.on_filter_changed)
        
        # Refresh Books Button
        self.btn_refresh = ModernButton(
            self.search_filter_frame, 
            text="🔄 Refresh", 
            command=self.refresh_table,
            button_type="secondary",
            font=("Segoe UI", 9, "bold"),
            padding_x=10,
            padding_y=5
        )
        self.btn_refresh.grid(row=0, column=2, sticky="ew")
        
        # Sorting Indicators Bar (Row 1)
        self.sort_bar = tk.Frame(self.grid_panel, bd=0)
        self.sort_bar.is_panel = True
        self.sort_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        self.sort_bar.columnconfigure(3, weight=1)
        
        # Construct Label first and assign 'in_panel' attribute to resolve TclError
        lbl_sort = tk.Label(self.sort_bar, text="Sort Options:", font=("Segoe UI", 9, "bold"))
        lbl_sort.in_panel = True
        lbl_sort.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        self.btn_sort_title = ModernButton(
            self.sort_bar,
            text="Sort by Title ↕",
            command=lambda: self.toggle_sort("title"),
            button_type="secondary",
            font=("Segoe UI", 8, "bold"),
            padding_x=8,
            padding_y=3
        )
        self.btn_sort_title.grid(row=0, column=1, sticky="w", padx=4)
        
        self.btn_sort_year = ModernButton(
            self.sort_bar,
            text="Sort by Year ↕",
            command=lambda: self.toggle_sort("year"),
            button_type="secondary",
            font=("Segoe UI", 8, "bold"),
            padding_x=8,
            padding_y=3
        )
        self.btn_sort_year.grid(row=0, column=2, sticky="w", padx=4)
        
        # CSV Export Button placed in sort bar aligned right
        self.btn_export = ModernButton(
            self.sort_bar,
            text="📥 Export to CSV",
            command=self.export_csv,
            button_type="success",
            font=("Segoe UI", 8, "bold"),
            padding_x=10,
            padding_y=3
        )
        self.btn_export.grid(row=0, column=4, sticky="e")
        
        # Grid View (Treeview Table) and Scrollbar Container (Row 2)
        self.table_container = tk.Frame(self.grid_panel, bd=0)
        self.table_container.is_panel = True
        self.table_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_container.columnconfigure(0, weight=1)
        self.table_container.rowconfigure(0, weight=1)
        
        # Empty State Placeholder frame (displayed when table is empty)
        self.empty_state_frame = tk.Frame(self.table_container, bd=0)
        self.empty_state_frame.grid(row=0, column=0, sticky="nsew")
        self.empty_state_frame.columnconfigure(0, weight=1)
        self.empty_state_frame.rowconfigure(0, weight=1)
        
        self.empty_lbl = tk.Label(
        self.empty_state_frame,
        text="📚 No Books Found\nAdd books or adjust search filter.",
        font=("Segoe UI", 12, "italic"),
        fg="#94a3b8")

        self.empty_lbl.label_type = "muted"
        self.empty_lbl.in_panel = True
        self.empty_lbl.grid(row=0, column=0, sticky="nsew")

        # Set up TTK Treeview
        columns = ("id", "title", "author", "year", "category", "status")
        self.tree = ttk.Treeview(self.table_container, columns=columns, show="headings", selectmode="browse")
        
        # Bind row selection event
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)
        
        # Setup Column headings & widths
        self.tree.heading("id", text="ID", anchor="center")
        self.tree.heading("title", text="Book Title", anchor="w")
        self.tree.heading("author", text="Author", anchor="w")
        self.tree.heading("year", text="Year", anchor="center")
        self.tree.heading("category", text="Category", anchor="w")
        self.tree.heading("status", text="Status", anchor="center")
        
        self.tree.column("id", width=50, minwidth=40, anchor="center")
        self.tree.column("title", width=250, minwidth=180, anchor="w")
        self.tree.column("author", width=180, minwidth=120, anchor="w")
        self.tree.column("year", width=80, minwidth=60, anchor="center")
        self.tree.column("category", width=120, minwidth=90, anchor="w")
        self.tree.column("status", width=100, minwidth=80, anchor="center")
        
        # Modern Styled Scrollbar
        self.scrollbar = ttk.Scrollbar(self.table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        # 3. FOOTER & STATISTICS QUICK-VIEW BAR
        self.footer = tk.Frame(self, height=45, relief="flat", bd=0)
        self.footer.grid(row=2, column=0, sticky="ew")
        self.footer.grid_propagate(False)
        self.footer.columnconfigure(1, weight=1)
        self.footer.rowconfigure(0, weight=1)
        
        # Dashboard Overview label (Left aligned)
        self.stats_summary_lbl = tk.Label(
            self.footer,
            text="Dashboard: Loading statistics...",
            font=("Segoe UI", 9, "bold")
        )
        self.stats_summary_lbl.grid(row=0, column=0, padx=20, sticky="w")
        
        # Operation buttons aligned right
        self.footer_right = tk.Frame(self.footer)
        self.footer_right.grid(row=0, column=2, padx=20, sticky="e")
        
        self.btn_stats = ModernButton(
            self.footer_right,
            text="📊 View Detailed Stats",
            command=self.show_statistics_modal,
            button_type="success",
            font=("Segoe UI", 8, "bold"),
            padding_x=10,
            padding_y=3
        )
        self.btn_stats.pack(side="left", padx=(0, 10))
        
        self.btn_db_settings = ModernButton(
            self.footer_right,
            text="⚙️ DB Settings",
            command=self.show_db_settings_modal,
            button_type="secondary",
            font=("Segoe UI", 8, "bold"),
            padding_x=10,
            padding_y=3
        )
        self.btn_db_settings.pack(side="left")

        # 4. FULL SCREEN CONNECTION ERROR OVERLAY FRAME
        # Built to gracefully handle connection failure, blocking usage until database configuration is sound
        self.error_overlay = tk.Frame(self, bd=0)
        self.error_overlay.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
        self.error_overlay.columnconfigure(0, weight=1)
        self.error_overlay.rowconfigure(0, weight=1)
        self.error_overlay.grid_remove() # Hide initially
        
        self.error_box = tk.Frame(self.error_overlay, bd=1, highlightthickness=1)
        self.error_box.is_panel = True
        self.error_box.has_border = True
        self.error_box.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        self.error_box.columnconfigure(0, weight=1)
        
        # Error text & connection entry form elements will populate this dynamically in show_error_screen()

    # ==========================================================================
    # DATABASE & SYSTEM CONNECTION CONTROL
    # ==========================================================================
    def test_initial_connection(self):
        """Attempts to establish connection to the database. Activates normal UI or prompts configuration overlay."""
        self.update_status_indicator("connecting", "Connecting...")
        
        success, message = self.db.connect_and_initialize()
        if success:
            self.is_connected = True
            self.update_status_indicator("connected", "Connected")
            
            # Hide connection error screen if visible
            self.error_overlay.grid_remove()
            self.main_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
            
            # Populate UI elements
            self.refresh_table()
            self.update_dashboard_stats()
        else:
            self.is_connected = False
            self.update_status_indicator("disconnected", "Disconnected")
            self.show_error_screen(message)

    def update_status_indicator(self, state, text):
        """Updates the top status light and label text."""
        self.conn_status_lbl.config(text=text)
        if state == "connected":
            self.conn_dot.itemconfig(self.conn_dot_indicator, fill="#22c55e") # Green
        elif state == "connecting":
            self.conn_dot.itemconfig(self.conn_dot_indicator, fill="#f59e0b") # Yellow/Amber
        else:
            self.conn_dot.itemconfig(self.conn_dot_indicator, fill="#ef4444") # Red

    def show_error_screen(self, error_message):
        """Replaces the dashboard workspace with a configuration screen due to a missing/faulty database connection."""
        self.main_container.grid_remove()
        self.error_overlay.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
        
        # Clear old error box elements
        for child in self.error_box.winfo_children():
            child.destroy()
            
        colors = self.colors[self.current_theme]
        self.error_box.config(bg=colors["card_bg"], highlightbackground=colors["border"])
        
        # Title Warning
        tk.Label(
            self.error_box,
            text="⚠️ Database Connection Failed",
            font=("Segoe UI", 14, "bold"),
            fg="#ef4444",
            bg=colors["card_bg"]
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=25, pady=(25, 10))
        
        # Error Description
        tk.Label(
            self.error_box,
            text=error_message,
            font=("Segoe UI", 10),
            fg=colors["text_muted"],
            bg=colors["card_bg"],
            wraplength=480,
            justify="left"
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=25, pady=(0, 20))
        
        # Info notice
        tk.Label(
            self.error_box,
            text="Please ensure MySQL Server is active on localhost, or provide custom settings below:",
            font=("Segoe UI", 9, "bold"),
            fg=colors["text"],
            bg=colors["card_bg"],
            justify="left"
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=25, pady=(0, 15))
        
        # Configuration Inputs
        tk.Label(self.error_box, text="Host Name / IP", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=3, column=0, sticky="w", padx=(25, 10), pady=4)
        host_entry = ModernEntry(self.error_box, placeholder=self.db.config["host"], width=20, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        host_entry.set_text(self.db.config["host"])
        host_entry.grid(row=3, column=1, sticky="w", padx=(0, 25), pady=4)
        
        tk.Label(self.error_box, text="MySQL Port", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=4, column=0, sticky="w", padx=(25, 10), pady=4)
        port_entry = ModernEntry(self.error_box, placeholder=str(self.db.config["port"]), width=20, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        port_entry.set_text(str(self.db.config["port"]))
        port_entry.grid(row=4, column=1, sticky="w", padx=(0, 25), pady=4)
        
        tk.Label(self.error_box, text="Username", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=5, column=0, sticky="w", padx=(25, 10), pady=4)
        user_entry = ModernEntry(self.error_box, placeholder=self.db.config["user"], width=20, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        user_entry.set_text(self.db.config["user"])
        user_entry.grid(row=5, column=1, sticky="w", padx=(0, 25), pady=4)
        
        tk.Label(self.error_box, text="Password", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=6, column=0, sticky="w", padx=(25, 10), pady=4)
        pass_entry = ModernEntry(self.error_box, show="*", width=20, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        pass_entry.set_text(self.db.config["password"])
        pass_entry.grid(row=6, column=1, sticky="w", padx=(0, 25), pady=4)
        
        # Save and Connect button
        def attempt_reconnect():
            host = host_entry.entry.get().strip()
            port = port_entry.entry.get().strip()
            user = user_entry.entry.get().strip()
            password = pass_entry.entry.get().strip()
            
            # Simple UI validation
            if not host or not user or not port:
                messagebox.showerror("Validation Error", "Host, Port, and Username cannot be empty.", parent=self)
                return
                
            try:
                int(port)
            except ValueError:
                messagebox.showerror("Validation Error", "Port must be an integer.", parent=self)
                return
                
            # Update DB config details and test connection
            self.db.save_config(host, user, password, port)
            self.test_initial_connection()
            
        btn_reconnect = ModernButton(
            self.error_box, 
            text="⚡ Connect & Save Configuration", 
            command=attempt_reconnect,
            bg_color=colors["primary"],
            hover_color=colors["primary_light"],
            text_color="#ffffff"
        )
        btn_reconnect.grid(row=7, column=0, columnspan=2, sticky="ew", padx=25, pady=(20, 25))
        
        # Force redraw error overlay theme
        self.apply_theme()

    # ==========================================================================
    # CENTRALIZED DATA MANAGEMENT & CORE LOGIC
    # ==========================================================================
    def refresh_table(self):
        """Re-fetches and renders all active books in Treeview."""
        if not self.is_connected:
            return
            
        # Get matching records depending on searches & dropdown filters
        q = self.search_entry.get()
        f = self.filter_cb.get()
        if f == "Filter by Category":
            f = "All"
            
        books = self.db.get_books_filtered_sorted(
            query_str=q,
            category_filter=f,
            sort_by=self.current_sort_col,
            order=self.current_sort_order
        )
        
        # Re-draw the table grid
        self.render_treeview_rows(books)
        self.update_dashboard_stats()

    def render_treeview_rows(self, books):
        """Fills standard listview rows and toggles empty state panel if necessary."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if not books:
            # Hide Treeview & display empty placeholder
            self.tree.pack_forget()
            self.scrollbar.pack_forget()
            self.empty_state_frame.grid(row=0, column=0, sticky="nsew")
        else:
            # Hide placeholder & display Treeview table
            self.empty_state_frame.grid_forget()
            self.tree.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
            
            # Populate records with zebra striping
            for idx, book in enumerate(books):
                tags = ("evenrow",) if idx % 2 == 0 else ("oddrow",)
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        book["id"],
                        book["title"],
                        book["author"],
                        book["year"],
                        book["category"],
                        book["status"]
                    ),
                    tags=tags
                )
        
        # Keep selected row highlighting sync
        self.selected_book_id = None
        self.btn_update.config(state="normal")
        self.btn_delete.config(state="normal")
        self.btn_issue.config(state="normal")
        self.btn_return.config(state="normal")

    def update_dashboard_stats(self):
        """Queries database stats to update quick-view status bar badges."""
        if not self.is_connected:
            self.stats_summary_lbl.config(text="Dashboard: Database Offline")
            return
            
        stats = self.db.get_statistics()
        tot = stats["total_books"]
        uni = stats["unique_authors"]
        iss = stats["issued_count"]
        av = stats["available_count"]
        
        self.stats_summary_lbl.config(
            text=f"📊 Library Summary: Total Books: {tot}  |  Unique Authors: {uni}  |  Available: {av}  |  Issued: {iss}"
        )

    # ==========================================================================
    # CORE INTERACTIVE COMPONENT EVENT BINDINGS
    # ==========================================================================
    def on_live_search(self, event):
        """Triggers live table filtering as the user types."""
        self.refresh_table()

    def on_filter_changed(self, event):
        """Forces table updates when the category filter dropdown changes."""
        self.refresh_table()

    def toggle_sort(self, column):
        """Swaps sorting order ascending / descending for a target column."""
        if self.current_sort_col == column:
            # Toggle sorting direction
            self.current_sort_order = "DESC" if self.current_sort_order == "ASC" else "ASC"
        else:
            self.current_sort_col = column
            self.current_sort_order = "ASC"
            
        # Update sorting button displays
        t_indicator = " ▲" if self.current_sort_order == "ASC" else " ▼"
        if column == "title":
            self.btn_sort_title.config(text=f"Sort by Title{t_indicator}")
            self.btn_sort_year.config(text="Sort by Year ↕")
        elif column == "year":
            self.btn_sort_year.config(text=f"Sort by Year{t_indicator}")
            self.btn_sort_title.config(text="Sort by Title ↕")
            
        self.refresh_table()

    def on_row_selected(self, event):
        """Fills the book editor control fields with values from the selected table row."""
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        row_values = self.tree.item(selected_items[0])["values"]
        if not row_values:
            return
            
        self.selected_book_id = row_values[0]
        
        # Populate Editor inputs
        self.book_id_entry.entry.config(state="normal")
        self.book_id_entry.set_text(str(row_values[0]))
        self.book_id_entry.entry.config(state="disabled")
        
        self.title_entry.set_text(str(row_values[1]))
        self.author_entry.set_text(str(row_values[2]))
        self.year_entry.set_text(str(row_values[3]))
        
        cat = str(row_values[4])
        if cat in ["Fiction", "Science", "History", "Biography", "Other"]:
            self.category_cb.set(cat)
        else:
            self.category_cb.set("Other")

    # ==========================================================================
    # CORE CRUD OPERATIONS & FLOW LOGIC
    # ==========================================================================
    def validate_form(self):
        """Helper to validate that form input parameters meet system schema constraints."""
        title = self.title_entry.get()
        author = self.author_entry.get()
        year = self.year_entry.get()
        category = self.category_cb.get()
        
        if not title:
            messagebox.showwarning("Validation Error", "Book Title field is required.", parent=self)
            return None
            
        if not author:
            messagebox.showwarning("Validation Error", "Author Name field is required.", parent=self)
            return None
            
        if not year:
            messagebox.showwarning("Validation Error", "Publication Year field is required.", parent=self)
            return None
            
        # Validate that year is a positive integer
        try:
            year_val = int(year)
            if year_val <= 0 or year_val > 2100:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Validation Error", "Please provide a valid publication year (e.g. 1 to 2100).", parent=self)
            return None
            
        if category == "Select":
            messagebox.showwarning("Validation Error", "Please select a valid Book Category.", parent=self)
            return None
            
        return title, author, year_val, category

    def add_book(self):
        """Triggers DB book addition."""
        if not self.is_connected:
            messagebox.showerror("System Error", "Database not connected. Operation locked.", parent=self)
            return
            
        inputs = self.validate_form()
        if not inputs:
            return
            
        title, author, year, category = inputs
        success, message = self.db.add_book(title, author, year, category)
        
        if success:
            messagebox.showinfo("Success", message, parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", message, parent=self)

    def update_book(self):
        """Triggers DB book modification for the currently selected record."""
        if not self.is_connected:
            messagebox.showerror("System Error", "Database not connected. Operation locked.", parent=self)
            return
            
        if not self.selected_book_id:
            messagebox.showwarning("Selection Warning", "Please select a book from the table to update.", parent=self)
            return
            
        inputs = self.validate_form()
        if not inputs:
            return
            
        title, author, year, category = inputs
        
        # Double check confirmation
        confirm = messagebox.askyesno(
            "Confirm Update", 
            f"Are you sure you want to update Book ID {self.selected_book_id}?", 
            parent=self
        )
        if not confirm:
            return
            
        success, message = self.db.update_book(self.selected_book_id, title, author, year, category)
        if success:
            messagebox.showinfo("Success", message, parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", message, parent=self)

    def delete_book(self):
        """Deletes the selected book record, requiring explicit user warning validation."""
        if not self.is_connected:
            messagebox.showerror("System Error", "Database not connected. Operation locked.", parent=self)
            return
            
        if not self.selected_book_id:
            messagebox.showwarning("Selection Warning", "Please select a book from the table to delete.", parent=self)
            return
            
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"⚠️ CRITICAL ACTION ⚠️\n\nAre you sure you want to permanently delete Book ID: {self.selected_book_id}?",
            parent=self
        )
        if not confirm:
            return
            
        success, message = self.db.delete_book(self.selected_book_id)
        if success:
            messagebox.showinfo("Success", message, parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", message, parent=self)

    def issue_book(self):
        """Updates borrowing status of chosen book to 'Issued'."""
        if not self.is_connected:
            messagebox.showerror("System Error", "Database not connected. Operation locked.", parent=self)
            return
            
        if not self.selected_book_id:
            messagebox.showwarning("Selection Warning", "Please select a book from the table to issue.", parent=self)
            return
            
        # Get details of selection
        selected_item = self.tree.selection()[0]
        status = self.tree.item(selected_item)["values"][5]
        title = self.tree.item(selected_item)["values"][1]
        
        if status == "Issued":
            messagebox.showwarning("Operation Error", f"'{title}' is already issued. Cannot double-issue.", parent=self)
            return
            
        success, message = self.db.change_status(self.selected_book_id, "Issued")
        if success:
            messagebox.showinfo("Success", f"Book issued successfully:\n'{title}' is now checked out.", parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", message, parent=self)

    def return_book(self):
        """Updates borrowing status of chosen book back to 'Available'."""
        if not self.is_connected:
            messagebox.showerror("System Error", "Database not connected. Operation locked.", parent=self)
            return
            
        if not self.selected_book_id:
            messagebox.showwarning("Selection Warning", "Please select a book from the table to return.", parent=self)
            return
            
        selected_item = self.tree.selection()[0]
        status = self.tree.item(selected_item)["values"][5]
        title = self.tree.item(selected_item)["values"][1]
        
        if status == "Available":
            messagebox.showwarning("Operation Error", f"'{title}' is already in the library as 'Available'.", parent=self)
            return
            
        success, message = self.db.change_status(self.selected_book_id, "Available")
        if success:
            messagebox.showinfo("Success", f"Book returned successfully:\n'{title}' is now back in stock.", parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", message, parent=self)

    def clear_form(self):
        """Resets all left editor entry panel fields."""
        self.selected_book_id = None
        self.book_id_entry.entry.config(state="normal")
        self.book_id_entry.clear()
        self.book_id_entry.entry.config(state="disabled")
        
        self.title_entry.clear()
        self.author_entry.clear()
        self.year_entry.clear()
        self.category_cb.set("Select")
        
        # Reset table selections
        self.tree.selection_remove(self.tree.selection())

    # ==========================================================================
    # UTILITIES & EXPORT FEATURES
    # ==========================================================================
    def export_csv(self):
        """Writes entire books database schema table records to an external CSV file."""
        if not self.is_connected:
            messagebox.showerror("System Error", "Database not connected. Operation locked.", parent=self)
            return
            
        books = self.db.get_all_books()
        if not books:
            messagebox.showwarning("Export Warning", "There are no records in the library to export.", parent=self)
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export Books to CSV File",
            parent=self
        )
        if not file_path:
            return
            
        try:
            with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Write header columns
                writer.writerow(["ID", "Title", "Author", "Year", "Category", "Status"])
                # Write record rows
                for book in books:
                    writer.writerow([
                        book["id"],
                        book["title"],
                        book["author"],
                        book["year"],
                        book["category"],
                        book["status"]
                    ])
            messagebox.showinfo("Export Successful", f"Database successfully written to:\n{file_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Failure", f"An error occurred during file writing:\n{str(e)}", parent=self)

    # ==========================================================================
    # MODAL DIALOG POPUPS (DB SETTINGS, FULL STATS)
    # ==========================================================================
    def show_db_settings_modal(self):
        """Displays database credentials config popup for mid-operation edits."""
        modal = tk.Toplevel(self)
        modal.title("Database Connection Settings")
        modal.geometry("380x360")
        modal.resizable(False, False)
        modal.grab_set() # Block primary window focus
        modal.focus_set()
        
        # Center modal relative to main app
        x = self.winfo_x() + (self.winfo_width() // 2) - (380 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (360 // 2)
        modal.geometry(f"380x360+{x}+{y}")
        
        colors = self.colors[self.current_theme]
        modal.config(bg=colors["card_bg"])
        
        # Modal Title
        tk.Label(modal, text="⚙️ Connection Settings", font=("Segoe UI", 12, "bold"), fg=colors["primary"], bg=colors["card_bg"]).pack(anchor="w", padx=25, pady=(25, 15))
        
        # Fields container
        fields_frame = tk.Frame(modal, bg=colors["card_bg"])
        fields_frame.pack(fill="both", expand=True, padx=25)
        fields_frame.columnconfigure(1, weight=1)
        
        # Host
        tk.Label(fields_frame, text="Host", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=0, column=0, sticky="w", pady=6)
        host_entry = ModernEntry(fields_frame, placeholder=self.db.config["host"], width=18, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        host_entry.set_text(self.db.config["host"])
        host_entry.grid(row=0, column=1, sticky="ew", padx=(15, 0), pady=6)
        
        # Port
        tk.Label(fields_frame, text="Port", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=1, column=0, sticky="w", pady=6)
        port_entry = ModernEntry(fields_frame, placeholder=str(self.db.config["port"]), width=18, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        port_entry.set_text(str(self.db.config["port"]))
        port_entry.grid(row=1, column=1, sticky="ew", padx=(15, 0), pady=6)
        
        # User
        tk.Label(fields_frame, text="Username", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=2, column=0, sticky="w", pady=6)
        user_entry = ModernEntry(fields_frame, placeholder=self.db.config["user"], width=18, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        user_entry.set_text(self.db.config["user"])
        user_entry.grid(row=2, column=1, sticky="ew", padx=(15, 0), pady=6)
        
        # Password
        tk.Label(fields_frame, text="Password", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=3, column=0, sticky="w", pady=6)
        pass_entry = ModernEntry(fields_frame, show="*", width=18, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
        pass_entry.set_text(self.db.config["password"])
        pass_entry.grid(row=3, column=1, sticky="ew", padx=(15, 0), pady=6)
        
        def save_and_reconnect():
            h = host_entry.get()
            p = port_entry.get()
            u = user_entry.get()
            pwd = pass_entry.get()
            
            if not h or not u or not p:
                messagebox.showerror("Validation Error", "Host, Port, and Username cannot be empty.", parent=modal)
                return
            try:
                int(p)
            except ValueError:
                messagebox.showerror("Validation Error", "Port must be an integer.", parent=modal)
                return
                
            self.db.save_config(h, u, pwd, p)
            modal.destroy()
            self.test_initial_connection()
            
        # Action Buttons
        btn_frame = tk.Frame(modal, bg=colors["card_bg"])
        btn_frame.pack(fill="x", padx=25, pady=(0, 25))
        
        ModernButton(btn_frame, text="Cancel", command=modal.destroy, button_type="secondary").pack(side="left")
        ModernButton(btn_frame, text="Save & Connect", command=save_and_reconnect, bg_color=colors["primary"], hover_color=colors["primary_light"]).pack(side="right")
        
        # Recursively theme modal widgets
        self._style_widgets_recursive(modal, colors)

    def show_statistics_modal(self):
        """Displays beautiful detailed statistics dialog including categories and years distribution charts."""
        if not self.is_connected:
            messagebox.showerror("System Error", "Database not connected. Action locked.", parent=self)
            return
            
        stats = self.db.get_statistics()
        
        modal = tk.Toplevel(self)
        modal.title("Library Data Statistics Dashboard")
        modal.geometry("520x560")
        modal.resizable(False, False)
        modal.grab_set()
        modal.focus_set()
        
        x = self.winfo_x() + (self.winfo_width() // 2) - (520 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (560 // 2)
        modal.geometry(f"520x560+{x}+{y}")
        
        colors = self.colors[self.current_theme]
        modal.config(bg=colors["bg"])
        
        # Modal Header
        tk.Label(
            modal,
            text="📊 Library Dashboard Analytics",
            font=("Segoe UI", 14, "bold"),
            fg=colors["primary"],
            bg=colors["bg"]
        ).pack(anchor="w", padx=25, pady=(25, 10))
        
        # 1. CORE METRICS BLOCK (GRID PANELS)
        metrics_frame = tk.Frame(modal, bg=colors["bg"])
        metrics_frame.pack(fill="x", padx=25, pady=10)
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.columnconfigure(1, weight=1)
        metrics_frame.columnconfigure(2, weight=1)
        
        def make_metric_card(parent, col, value, label):
            card = tk.Frame(parent, bg=colors["card_bg"], bd=1, highlightthickness=0)
            card.grid(row=0, column=col, sticky="nsew", padx=4 if col != 0 else (0, 4))
            
            tk.Label(card, text=str(value), font=("Segoe UI", 18, "bold"), fg=colors["primary"], bg=colors["card_bg"]).pack(pady=(12, 2))
            tk.Label(card, text=label, font=("Segoe UI", 8, "bold"), fg=colors["text_muted"], bg=colors["card_bg"]).pack(pady=(0, 12))
            return card
            
        make_metric_card(metrics_frame, 0, stats["total_books"], "Total Books")
        make_metric_card(metrics_frame, 1, stats["unique_authors"], "Unique Authors")
        make_metric_card(metrics_frame, 2, f"{stats['available_count']} / {stats['issued_count']}", "Avail / Issued")
        
        # 2. CATEGORY DISTRIBUTION PANEL
        cat_panel = tk.Frame(modal, bg=colors["card_bg"], bd=1, highlightthickness=0)
        cat_panel.pack(fill="both", expand=True, padx=25, pady=8)
        
        tk.Label(
            cat_panel, 
            text="Category Distribution", 
            font=("Segoe UI", 10, "bold"), 
            fg=colors["text"], 
            bg=colors["card_bg"]
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        tot_books = stats["total_books"]
        
        # If no books are in the library, show simple notification
        if tot_books == 0:
            tk.Label(
                cat_panel, 
                text="No book records registered to build a distribution.", 
                font=("Segoe UI", 9, "italic"), 
                fg=colors["text_muted"], 
                bg=colors["card_bg"]
            ).pack(anchor="w", padx=15, pady=20)
        else:
            # Display category progress bars representing percentages
            # Supported Categories: Fiction, Science, History, Biography, Other
            all_cats = ["Fiction", "Science", "History", "Biography", "Other"]
            for idx, cat in enumerate(all_cats):
                count = stats["by_category"].get(cat, 0)
                pct = (count / tot_books) * 100 if tot_books > 0 else 0
                
                bar_row = tk.Frame(cat_panel, bg=colors["card_bg"])
                bar_row.pack(fill="x", padx=15, pady=4)
                
                # Label & Count
                tk.Label(bar_row, text=f"{cat} ({count})", font=("Segoe UI", 9), fg=colors["text"], bg=colors["card_bg"]).pack(side="left")
                tk.Label(bar_row, text=f"{pct:.1f}%", font=("Segoe UI", 8, "bold"), fg=colors["text_muted"], bg=colors["card_bg"]).pack(side="right")
                
                # Bar Canvas (A modern flat CSS-like progress bar)
                bar_bg = tk.Frame(cat_panel, height=6, bg=colors["border"])
                bar_bg.pack(fill="x", padx=15, pady=(0, 8))
                
                # The filled bar
                if pct > 0:
                    bar_fill = tk.Frame(bar_bg, height=6, bg=colors["primary"])
                    # Use relwidth to dynamically set visual size
                    bar_fill.place(relx=0, rely=0, relwidth=pct/100, relheight=1.0)
                    
        # 3. TOP YEARS DISTRIBUTION SUMMARY PANEL
        years_panel = tk.Frame(modal, bg=colors["card_bg"], bd=1, highlightthickness=0)
        years_panel.pack(fill="x", padx=25, pady=(8, 20))
        
        tk.Label(
            years_panel, 
            text="Top Book Years Distribution", 
            font=("Segoe UI", 10, "bold"), 
            fg=colors["text"], 
            bg=colors["card_bg"]
        ).pack(anchor="w", padx=15, pady=(15, 8))
        
        y_text_list = []
        # Sort year keys by counts descending
        top_years = sorted(stats["by_year"].items(), key=lambda item: item[1], reverse=True)[:5]
        for y, cnt in top_years:
            y_text_list.append(f"{y}: {cnt} books")
            
        y_summary = ",   ".join(y_text_list) if y_text_list else "No publications registered."
        tk.Label(
            years_panel,
            text=y_summary,
            font=("Segoe UI", 9),
            fg=colors["text_muted"],
            bg=colors["card_bg"],
            wraplength=440,
            justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 15))
        
        # Close Button
        ModernButton(
            modal, 
            text="Close Dashboard", 
            command=modal.destroy, 
            bg_color=colors["primary"], 
            hover_color=colors["primary_light"]
        ).pack(pady=(0, 20))
        
        # Recursively theme modal widgets
        self._style_widgets_recursive(modal, colors)

    # ==========================================================================
    # SYSTEM THEMING ENGINE
    # ==========================================================================
    def toggle_theme(self):
        """Swaps active application theme between light and dark modes."""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        
        # Update Toggle button label
        btn_lbl = "☀️ Light Mode" if self.current_theme == "dark" else "🌙 Dark Mode"
        self.theme_btn.config(text=btn_lbl)
        
        self.apply_theme()

    def apply_theme(self):
        """Forces full application window hierarchy to redraw colors matching the active theme."""
        colors = self.colors[self.current_theme]
        
        # Main Window
        self.config(bg=colors["bg"])
        
        # Configure TTK Styles (standard theme maps)
        self.style.theme_use("clam")
        
        # 1. Custom Treeview Styles
        self.style.configure(
            "Treeview", 
            background=colors["card_bg"], 
            foreground=colors["text"], 
            fieldbackground=colors["card_bg"],
            rowheight=32,
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 9)
        )
        self.style.map(
            "Treeview", 
            background=[("selected", colors["primary"])], 
            foreground=[("selected", "#ffffff")]
        )
        
        # Zebra Striping colors
        even_bg = colors["card_bg"]
        odd_bg = colors["bg"] if self.current_theme == "light" else "#24324a" # Custom subtle off-slate for dark zebra
        self.tree.tag_configure("evenrow", background=even_bg, foreground=colors["text"])
        self.tree.tag_configure("oddrow", background=odd_bg, foreground=colors["text"])
        
        # Custom Treeview Column Headings
        self.style.configure(
            "Treeview.Heading", 
            background=colors["border"], 
            foreground=colors["text"], 
            relief="flat",
            borderwidth=1,
            font=("Segoe UI", 9, "bold")
        )
        # Prevent gray flash on click
        self.style.map(
            "Treeview.Heading", 
            background=[("active", colors["border"])]
        )
        
        # 2. Custom Scrollbar Styling
        self.style.configure(
            "Vertical.TScrollbar", 
            background=colors["border"], 
            troughcolor=colors["bg"], 
            arrowcolor=colors["text"],
            relief="flat",
            borderwidth=0
        )
        self.style.map(
            "Vertical.TScrollbar",
            background=[("active", colors["primary"]), ("pressed", colors["primary_light"])]
        )
        
        # 3. Custom Combobox Styling
        self.style.configure(
            "TCombobox", 
            fieldbackground=colors["card_bg"], 
            background=colors["border"], 
            foreground=colors["text"],
            relief="flat",
            borderwidth=0,
            arrowcolor=colors["text"]
        )
        self.style.map(
            "TCombobox", 
            fieldbackground=[("readonly", colors["card_bg"])],
            selectbackground=[("readonly", colors["primary"])],
            selectforeground=[("readonly", "#ffffff")]
        )
        
        # Recursively update standard Tkinter elements
        self._style_widgets_recursive(self, colors)

    def _style_widgets_recursive(self, widget, colors):
     for child in widget.winfo_children():
        w_class = child.winfo_class()

        # Custom widgets
        if isinstance(child, ModernEntry):
            child.set_colors(
                colors["card_bg"],
                colors["border"],
                colors["primary"],
                colors["text"],
                colors["text_muted"]
            )

        elif isinstance(child, ModernButton):
            b_type = getattr(child, "button_type", "primary")

            btn_colors = {
                "primary": (colors["primary"], colors["primary_light"], "#fff"),
                "danger": ("#ef4444", "#dc2626", "#fff"),
                "success": ("#22c55e", "#16a34a", "#fff"),
                "secondary": (colors["border"], colors["bg"], colors["text"])
            }

            child.set_colors(*btn_colors.get(b_type, btn_colors["secondary"]))

        # Frames
        elif w_class in ("Frame", "Labelframe"):
            is_panel = getattr(child, "is_panel", False)
            child.config(bg=colors["card_bg"] if is_panel else colors["bg"])

            if getattr(child, "has_border", False):
                child.config(
                    highlightbackground=colors["border"],
                    highlightcolor=colors["border"]
                )

            self._style_widgets_recursive(child, colors)

        # Labels
        elif w_class == "Label":
            l_type = getattr(child, "label_type", "normal")
            in_panel = getattr(child, "in_panel", False)

            bg = colors["card_bg"] if in_panel else colors["bg"]

            if l_type == "heading":
                child.config(bg=colors["bg"], fg=colors["primary"])
            elif l_type == "panel_heading":
                child.config(bg=colors["card_bg"], fg=colors["primary"])
            elif l_type == "muted":
                child.config(bg=bg, fg=colors["text_muted"])
            else:
                child.config(bg=bg, fg=colors["text"])

        # Canvas
        elif w_class == "Canvas":
            child.config(bg=colors["card_bg"] if getattr(child, "in_panel", False) else colors["bg"])

        # Skip native inputs
        elif w_class in ("Entry", "Listbox", "Scrollbar", "TScrollbar", "Combobox"):
            pass

        else:
            self._style_widgets_recursive(child, colors)

# ==============================================================================
# MAIN LAUNCH BLOCK
# ==============================================================================
if __name__ == "__main__":
    app = LMSApp()
    app.mainloop()