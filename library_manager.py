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
    def __init__(self, config_path="db_config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.connection = None

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    if all(key in config for key in ["host", "user", "password", "port"]):
                        return config
            except Exception:
                pass
        return {"host": "localhost", "user": "root", "password": "", "port": 3306}

    def save_config(self, host, user, password, port):
        self.config = {"host": host.strip(), "user": user.strip(), "password": password, "port": int(port)}
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True, "Config saved"
        except Exception as e:
            return False, f"Failed to save config file: {str(e)}"

    def connect_and_initialize(self):
        try:
            conn = mysql.connector.connect(
                host=self.config["host"], user=self.config["user"],
                password=self.config["password"], port=self.config["port"], connect_timeout=3
            )
            cursor = conn.cursor()
            cursor.execute("CREATE DATABASE IF NOT EXISTS library_db")
            cursor.close()
            conn.close()

            self.connection = mysql.connector.connect(
                host=self.config["host"], user=self.config["user"],
                password=self.config["password"], port=self.config["port"],
                database="library_db", connect_timeout=3
            )
            
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
            if self.connection and self.connection.is_connected():
                self.connection.close()
            self.connection = None
            error_msg = f"MySQL Error {e.errno}: {e.msg}"
            if e.errno in (2002, 2003):
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
        if not (self.connection and self.connection.is_connected()):
            try:
                self.connection = mysql.connector.connect(
                    host=self.config["host"], user=self.config["user"],
                    password=self.config["password"], port=self.config["port"],
                    database="library_db", connect_timeout=3
                )
            except Exception:
                self.connection = None
        return self.connection

    def check_duplicate(self, title, author, exclude_id=None):
        conn = self.get_connection()
        if not conn: return False
        try:
            cursor = conn.cursor()
            sql = "SELECT id FROM books WHERE LOWER(TRIM(title)) = LOWER(TRIM(%s)) AND LOWER(TRIM(author)) = LOWER(TRIM(%s))"
            params = [title, author]
            if exclude_id:
                sql += " AND id != %s"
                params.append(exclude_id)
            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            cursor.close()
            return row is not None
        except Exception:
            return False

    def add_book(self, title, author, year, category):
        if self.check_duplicate(title, author):
            return False, f"Duplicate Warning: '{title}' by '{author}' is already in the library."
        conn = self.get_connection()
        if not conn: return False, "Database not connected. Please verify connection configurations."
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
        conn = self.get_connection()
        if not conn: return []
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM books")
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception:
            return []

    def update_book(self, book_id, title, author, year, category):
        if self.check_duplicate(title, author, exclude_id=book_id):
            return False, f"Duplicate Warning: Another book titled '{title}' by '{author}' already exists."
        conn = self.get_connection()
        if not conn: return False, "Database not connected"
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
        conn = self.get_connection()
        if not conn: return False, "Database not connected"
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM books WHERE id = %s", (int(book_id),))
            conn.commit()
            cursor.close()
            return True, "Book deleted successfully!"
        except Exception as e:
            return False, f"Database Deletion Error: {str(e)}"

    def change_status(self, book_id, status):
        conn = self.get_connection()
        if not conn: return False, "Database not connected"
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE books SET status = %s WHERE id = %s", (status, int(book_id)))
            conn.commit()
            cursor.close()
            return True, f"Book status updated to '{status}'"
        except Exception as e:
            return False, f"Database Status Update Error: {str(e)}"

    def get_books_filtered_sorted(self, query_str="", category_filter="All", sort_by="id", order="ASC"):
        conn = self.get_connection()
        if not conn: return []
        try:
            cursor = conn.cursor(dictionary=True)
            order_by = {"title": "title", "year": "year"}.get(sort_by.lower(), "id")
            order_direction = "DESC" if order.upper() == "DESC" else "ASC"
            sql = "SELECT * FROM books WHERE 1=1"
            params = []
            if category_filter and category_filter != "All":
                sql += " AND category = %s"
                params.append(category_filter)
            if query_str:
                sql += " AND (title LIKE %s OR author LIKE %s OR CAST(year AS CHAR) LIKE %s OR category LIKE %s)"
                params.extend([f"%{query_str}%"] * 4)
            sql += f" ORDER BY {order_by} {order_direction}"
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception:
            return []

    def get_statistics(self):
        conn = self.get_connection()
        stats = {"total_books": 0, "unique_authors": 0, "issued_count": 0, "available_count": 0, "by_category": {}, "by_year": {}}
        if not conn: return stats
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM books")
            stats["total_books"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT author) FROM books")
            stats["unique_authors"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'Issued'")
            stats["issued_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'Available'")
            stats["available_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT category, COUNT(*) FROM books GROUP BY category")
            stats["by_category"] = dict(cursor.fetchall())
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
    def __init__(self, parent, width=25, show="", placeholder="", bg_color="#ffffff", border_color="#cbd5e1", focus_color="#008080", text_color="#1e293b", placeholder_color="#94a3b8"):
        super().__init__(parent, bg=border_color, bd=1)
        self.bg_color, self.border_color, self.focus_color = bg_color, border_color, focus_color
        self.text_color, self.placeholder_color, self.placeholder = text_color, placeholder_color, placeholder
        self.entry_frame = tk.Frame(self, bg=bg_color, bd=0)
        self.entry_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        self.entry = tk.Entry(
            self.entry_frame, bg=bg_color, fg=text_color if not placeholder else placeholder_color,
            relief="flat", bd=0, width=width, show=show, font=("Segoe UI", 10), insertbackground=text_color
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
        return "" if val == self.placeholder else val.strip()

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
        self.bg_color, self.border_color, self.focus_color = bg_color, border_color, focus_color
        self.text_color, self.placeholder_color = text_color, placeholder_color
        self.config(bg=border_color)
        self.entry_frame.config(bg=bg_color)
        self.entry.config(
            bg=bg_color, fg=placeholder_color if self.entry.get() == self.placeholder else text_color,
            insertbackground=text_color
        )

class ModernButton(tk.Button):
    def __init__(self, parent, text, command=None, bg_color="#008080", hover_color="#00a6a6", text_color="#ffffff", button_type="primary", font=("Segoe UI", 10, "bold"), padding_y=6, padding_x=12):
        self.bg_color, self.hover_color, self.text_color, self.button_type = bg_color, hover_color, text_color, button_type
        super().__init__(
            parent, text=text, command=command, bg=bg_color, fg=text_color,
            activebackground=hover_color, activeforeground=text_color,
            font=font, bd=0, relief="flat", cursor="hand2", padx=padding_x, pady=padding_y
        )
        self.bind("<Enter>", lambda e: self.config(bg=self.hover_color))
        self.bind("<Leave>", lambda e: self.config(bg=self.bg_color))

    def set_colors(self, bg_color, hover_color, text_color):
        self.bg_color, self.hover_color, self.text_color = bg_color, hover_color, text_color
        self.config(bg=bg_color, fg=text_color, activebackground=hover_color, activeforeground=text_color)

# ==============================================================================
# MAIN LIBRARY APPLICATION CLASS
# ==============================================================================
class LMSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📖 Library Management System")
        self.geometry("1200x720")
        self.minsize(1080, 650)
        self.center_window(1200, 720)
        
        self.db = DatabaseHelper()
        self.current_theme = "light"
        self.selected_book_id = None
        self.is_connected = False
        self.current_sort_col = "id"
        self.current_sort_order = "ASC"
        
        self.define_colors()
        self.style = ttk.Style()
        self.build_layouts()
        self.test_initial_connection()

    def center_window(self, width, height):
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def define_colors(self):
        self.colors = {
            "light": {
                "bg": "#f1f5f9", "card_bg": "#ffffff",
                "primary": "#008080", "primary_light": "#0d9488",
                "text": "#0f172a", "text_muted": "#64748b", "border": "#e2e8f0"
            },
            "dark": {
                "bg": "#0f172a", "card_bg": "#1e293b",
                "primary": "#14b8a6", "primary_light": "#2dd4bf",
                "text": "#f8fafc", "text_muted": "#94a3b8", "border": "#334155"
            }
        }

    # ==========================================================================
    # LAYOUT AND INTERFACE CONSTRUCTION
    # ==========================================================================
    def build_layouts(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        
        # 1. HEADER SECTION
        self.header_frame = tk.Frame(self, height=70, relief="flat", bd=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_propagate(False)
        self.header_frame.columnconfigure(1, weight=1)
        self.header_frame.rowconfigure(0, weight=1)
        
        self.header_title = tk.Label(self.header_frame, text="📖 LIBRARY MANAGER", font=("Segoe UI", 18, "bold"))
        self.header_title.label_type = "heading"
        self.header_title.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.header_right = tk.Frame(self.header_frame, bg="white")
        self.header_right.grid(row=0, column=2, padx=20, pady=10, sticky="e")
        
        self.conn_dot = tk.Canvas(self.header_right, width=12, height=12, bd=0, highlightthickness=0)
        self.conn_dot.pack(side="left", padx=(0, 6))
        self.conn_dot_indicator = self.conn_dot.create_oval(2, 2, 10, 10, fill="#ef4444")
        
        self.conn_status_lbl = tk.Label(self.header_right, text="Disconnected", font=("Segoe UI", 9, "bold"))
        self.conn_status_lbl.pack(side="left", padx=(0, 20))
        
        self.theme_btn = ModernButton(self.header_right, text="🌙 Dark Mode", command=self.toggle_theme, button_type="secondary", font=("Segoe UI", 9, "bold"), padding_x=10, padding_y=4)
        self.theme_btn.pack(side="left")
        
        # 2. MAIN WORKSPACE CONTAINER
        self.main_container = tk.Frame(self, relief="flat", bd=0)
        self.main_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
        self.main_container.columnconfigure(0, weight=3)
        self.main_container.columnconfigure(1, weight=7)
        self.main_container.rowconfigure(0, weight=1)
        
        # 2A. LEFT FRAME: BOOK FORM
        self.form_panel = tk.Frame(self.main_container, relief="flat", bd=0)
        self.form_panel.is_panel = True
        self.form_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        self.form_panel.columnconfigure(0, weight=1)
        
        self.form_header = tk.Label(self.form_panel, text="Book Details Manager", font=("Segoe UI", 13, "bold"), anchor="w")
        self.form_header.label_type = "panel_heading"
        self.form_header.in_panel = True
        self.form_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 15))
        
        self.form_fields_frame = tk.Frame(self.form_panel, bd=0)
        self.form_fields_frame.is_panel = True
        self.form_fields_frame.grid(row=1, column=0, sticky="nsew", padx=20)
        self.form_fields_frame.columnconfigure(1, weight=1)
        
        # Fields creation helper
        def make_field(row, label, placeholder, disabled=False, show=""):
            tk.Label(self.form_fields_frame, text=label, font=("Segoe UI", 9, "bold"), anchor="w").grid(row=row, column=0, sticky="w", pady=(0, 2))
            entry = ModernEntry(self.form_fields_frame, placeholder=placeholder, show=show, width=20)
            if disabled: entry.entry.config(state="disabled")
            entry.grid(row=row+1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
            return entry

        self.book_id_entry = make_field(0, "Book ID", "Auto-generated", disabled=True)
        self.title_entry = make_field(2, "Book Title *", "e.g. Clean Code")
        self.author_entry = make_field(4, "Author *", "e.g. Robert C. Martin")
        self.year_entry = make_field(6, "Publication Year *", "e.g. 2008")

        tk.Label(self.form_fields_frame, text="Category *", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=8, column=0, sticky="w", pady=(0, 2))
        self.category_cb_border = tk.Frame(self.form_fields_frame, bg="#cbd5e1", bd=1)
        self.category_cb_border.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        self.category_cb = ttk.Combobox(
            self.category_cb_border, values=["Fiction", "Science", "History", "Biography", "Other"],
            state="readonly", font=("Segoe UI", 10)
        )
        self.category_cb.set("Select")
        self.category_cb.pack(fill="both", expand=True, padx=1, pady=1)
        
        self.form_actions_frame = tk.Frame(self.form_panel, bd=0)
        self.form_actions_frame.is_panel = True
        self.form_actions_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.form_actions_frame.columnconfigure(0, weight=1)
        self.form_actions_frame.columnconfigure(1, weight=1)
        
        buttons_data = [
            ("btn_add", "➕ Add Book", self.add_book, 0, 0, "primary"),
            ("btn_update", "🔄 Update", self.update_book, 0, 1, "primary"),
            ("btn_issue", "📤 Issue Book", self.issue_book, 1, 0, "primary"),
            ("btn_return", "📥 Return Book", self.return_book, 1, 1, "primary"),
            ("btn_clear", "🧹 Clear Form", self.clear_form, 2, 0, "secondary"),
            ("btn_delete", "🗑️ Delete", self.delete_book, 2, 1, "danger")
        ]
        for name, text, cmd, r, c, btype in buttons_data:
            btn = ModernButton(self.form_actions_frame, text=text, command=cmd, button_type=btype)
            btn.grid(row=r, column=c, sticky="ew", padx=(0, 5) if c == 0 else (5, 0), pady=4)
            setattr(self, name, btn)
            
        # 2B. RIGHT FRAME: DATABASE LIST & GRID CONTROLS
        self.grid_panel = tk.Frame(self.main_container, relief="flat", bd=0)
        self.grid_panel.is_panel = True
        self.grid_panel.grid(row=0, column=1, sticky="nsew", padx=(15, 0))
        self.grid_panel.columnconfigure(0, weight=1)
        self.grid_panel.rowconfigure(2, weight=1)
        
        self.search_filter_frame = tk.Frame(self.grid_panel, bd=0)
        self.search_filter_frame.is_panel = True
        self.search_filter_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.search_filter_frame.columnconfigure(0, weight=1)
        
        self.search_entry = ModernEntry(self.search_filter_frame, placeholder="🔍 Live Search by title, author, year...", width=30)
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search_entry.entry.bind("<KeyRelease>", self.on_live_search)
        
        self.filter_cb_border = tk.Frame(self.search_filter_frame, bg="#cbd5e1", bd=1)
        self.filter_cb_border.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        self.filter_cb = ttk.Combobox(
            self.filter_cb_border, values=["All", "Fiction", "Science", "History", "Biography", "Other"],
            state="readonly", font=("Segoe UI", 10), width=18
        )
        self.filter_cb.set("Filter by Category")
        self.filter_cb.pack(fill="both", expand=True, padx=1, pady=1)
        self.filter_cb.bind("<<ComboboxSelected>>", self.on_filter_changed)
        
        self.btn_refresh = ModernButton(self.search_filter_frame, text="🔄 Refresh", command=self.refresh_table, button_type="secondary", font=("Segoe UI", 9, "bold"), padding_x=10, padding_y=5)
        self.btn_refresh.grid(row=0, column=2, sticky="ew")
        
        self.sort_bar = tk.Frame(self.grid_panel, bd=0)
        self.sort_bar.is_panel = True
        self.sort_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        self.sort_bar.columnconfigure(3, weight=1)
        
        lbl_sort = tk.Label(self.sort_bar, text="Sort Options:", font=("Segoe UI", 9, "bold"))
        lbl_sort.in_panel = True
        lbl_sort.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        self.btn_sort_title = ModernButton(self.sort_bar, text="Sort by Title ↕", command=lambda: self.toggle_sort("title"), button_type="secondary", font=("Segoe UI", 8, "bold"), padding_x=8, padding_y=3)
        self.btn_sort_title.grid(row=0, column=1, sticky="w", padx=4)
        
        self.btn_sort_year = ModernButton(self.sort_bar, text="Sort by Year ↕", command=lambda: self.toggle_sort("year"), button_type="secondary", font=("Segoe UI", 8, "bold"), padding_x=8, padding_y=3)
        self.btn_sort_year.grid(row=0, column=2, sticky="w", padx=4)
        
        self.btn_export = ModernButton(self.sort_bar, text="📥 Export to CSV", command=self.export_csv, button_type="success", font=("Segoe UI", 8, "bold"), padding_x=10, padding_y=3)
        self.btn_export.grid(row=0, column=4, sticky="e")
        
        self.table_container = tk.Frame(self.grid_panel, bd=0)
        self.table_container.is_panel = True
        self.table_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.table_container.columnconfigure(0, weight=1)
        self.table_container.rowconfigure(0, weight=1)
        
        self.empty_state_frame = tk.Frame(self.table_container, bd=0)
        self.empty_state_frame.grid(row=0, column=0, sticky="nsew")
        self.empty_state_frame.columnconfigure(0, weight=1)
        self.empty_state_frame.rowconfigure(0, weight=1)
        
        self.empty_lbl = tk.Label(self.empty_state_frame, text="📚 No Books Found\nAdd books or adjust search filter.", font=("Segoe UI", 12, "italic"), fg="#94a3b8")
        self.empty_lbl.label_type = "muted"
        self.empty_lbl.in_panel = True
        self.empty_lbl.grid(row=0, column=0, sticky="nsew")

        columns = ("id", "title", "author", "year", "category", "status")
        self.tree = ttk.Treeview(self.table_container, columns=columns, show="headings", selectmode="browse")
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)
        
        headers_data = [
            ("id", "ID", 50, "center"),
            ("title", "Book Title", 250, "w"),
            ("author", "Author", 180, "w"),
            ("year", "Year", 80, "center"),
            ("category", "Category", 120, "w"),
            ("status", "Status", 100, "center")
        ]
        for col, heading, width, anchor in headers_data:
            self.tree.heading(col, text=heading, anchor=anchor)
            self.tree.column(col, width=width, minwidth=int(width*0.75), anchor=anchor)
            
        self.scrollbar = ttk.Scrollbar(self.table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        # 3. FOOTER & STATISTICS QUICK-VIEW BAR
        self.footer = tk.Frame(self, height=45, relief="flat", bd=0)
        self.footer.grid(row=2, column=0, sticky="ew")
        self.footer.grid_propagate(False)
        self.footer.columnconfigure(1, weight=1)
        self.footer.rowconfigure(0, weight=1)
        
        self.stats_summary_lbl = tk.Label(self.footer, text="Dashboard: Loading statistics...", font=("Segoe UI", 9, "bold"))
        self.stats_summary_lbl.grid(row=0, column=0, padx=20, sticky="w")
        
        self.footer_right = tk.Frame(self.footer)
        self.footer_right.grid(row=0, column=2, padx=20, sticky="e")
        
        self.btn_stats = ModernButton(self.footer_right, text="📊 View Detailed Stats", command=self.show_statistics_modal, button_type="success", font=("Segoe UI", 8, "bold"), padding_x=10, padding_y=3)
        self.btn_stats.pack(side="left", padx=(0, 10))
        
        self.btn_db_settings = ModernButton(self.footer_right, text="⚙️ DB Settings", command=self.show_db_settings_modal, button_type="secondary", font=("Segoe UI", 8, "bold"), padding_x=10, padding_y=3)
        self.btn_db_settings.pack(side="left")

        # 4. FULL SCREEN CONNECTION ERROR OVERLAY FRAME
        self.error_overlay = tk.Frame(self, bd=0)
        self.error_overlay.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
        self.error_overlay.columnconfigure(0, weight=1)
        self.error_overlay.rowconfigure(0, weight=1)
        self.error_overlay.grid_remove()
        
        self.error_box = tk.Frame(self.error_overlay, bd=1, highlightthickness=1)
        self.error_box.is_panel = True
        self.error_box.has_border = True
        self.error_box.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        self.error_box.columnconfigure(0, weight=1)

    # ==========================================================================
    # DATABASE & SYSTEM CONNECTION CONTROL
    # ==========================================================================
    def test_initial_connection(self):
        self.update_status_indicator("connecting", "Connecting...")
        success, message = self.db.connect_and_initialize()
        if success:
            self.is_connected = True
            self.update_status_indicator("connected", "Connected")
            self.error_overlay.grid_remove()
            self.main_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
            self.refresh_table()
        else:
            self.is_connected = False
            self.update_status_indicator("disconnected", "Disconnected")
            self.show_error_screen(message)

    def update_status_indicator(self, state, text):
        self.conn_status_lbl.config(text=text)
        fill_color = {"connected": "#22c55e", "connecting": "#f59e0b"}.get(state, "#ef4444")
        self.conn_dot.itemconfig(self.conn_dot_indicator, fill=fill_color)

    def show_error_screen(self, error_message):
        self.main_container.grid_remove()
        self.error_overlay.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 20))
        for child in self.error_box.winfo_children():
            child.destroy()
            
        colors = self.colors[self.current_theme]
        self.error_box.config(bg=colors["card_bg"], highlightbackground=colors["border"])
        
        tk.Label(self.error_box, text="⚠️ Database Connection Failed", font=("Segoe UI", 14, "bold"), fg="#ef4444", bg=colors["card_bg"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=25, pady=(25, 10))
        tk.Label(self.error_box, text=error_message, font=("Segoe UI", 10), fg=colors["text_muted"], bg=colors["card_bg"], wraplength=480, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", padx=25, pady=(0, 20))
        tk.Label(self.error_box, text="Please ensure MySQL Server is active on localhost, or provide custom settings below:", font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"], justify="left").grid(row=2, column=0, columnspan=2, sticky="w", padx=25, pady=(0, 15))
        
        fields = [("Host Name / IP", "host", 3), ("MySQL Port", "port", 4), ("Username", "user", 5), ("Password", "password", 6)]
        entries = {}
        for label, key, row in fields:
            tk.Label(self.error_box, text=label, font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=row, column=0, sticky="w", padx=(25, 10), pady=4)
            val = str(self.db.config.get(key, ""))
            entry = ModernEntry(self.error_box, show="*" if key == "password" else "", width=20, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
            entry.set_text(val)
            entry.grid(row=row, column=1, sticky="w", padx=(0, 25), pady=4)
            entries[key] = entry
            
        def attempt_reconnect():
            h, p, u, pwd = entries["host"].get(), entries["port"].get(), entries["user"].get(), entries["password"].get()
            if not h or not u or not p:
                messagebox.showerror("Validation Error", "Host, Port, and Username cannot be empty.", parent=self)
                return
            try:
                int(p)
            except ValueError:
                messagebox.showerror("Validation Error", "Port must be an integer.", parent=self)
                return
            self.db.save_config(h, u, pwd, p)
            self.test_initial_connection()
            
        btn_reconnect = ModernButton(self.error_box, text="⚡ Connect & Save Configuration", command=attempt_reconnect, bg_color=colors["primary"], hover_color=colors["primary_light"])
        btn_reconnect.grid(row=7, column=0, columnspan=2, sticky="ew", padx=25, pady=(20, 25))
        self.apply_theme()

    # ==========================================================================
    # CENTRALIZED DATA MANAGEMENT & CORE LOGIC
    # ==========================================================================
    def refresh_table(self):
        if not self.is_connected: return
        f = self.filter_cb.get()
        books = self.db.get_books_filtered_sorted(
            query_str=self.search_entry.get(),
            category_filter="All" if f == "Filter by Category" else f,
            sort_by=self.current_sort_col, order=self.current_sort_order
        )
        self.render_treeview_rows(books)
        self.update_dashboard_stats()

    def render_treeview_rows(self, books):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not books:
            self.tree.pack_forget()
            self.scrollbar.pack_forget()
            self.empty_state_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.empty_state_frame.grid_forget()
            self.tree.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
            for idx, book in enumerate(books):
                self.tree.insert("", "end", values=(book["id"], book["title"], book["author"], book["year"], book["category"], book["status"]), tags=("evenrow" if idx % 2 == 0 else "oddrow",))
        self.selected_book_id = None

    def update_dashboard_stats(self):
        if not self.is_connected:
            self.stats_summary_lbl.config(text="Dashboard: Database Offline")
            return
        s = self.db.get_statistics()
        self.stats_summary_lbl.config(text=f"📊 Library Summary: Total Books: {s['total_books']}  |  Unique Authors: {s['unique_authors']}  |  Available: {s['available_count']}  |  Issued: {s['issued_count']}")

    # ==========================================================================
    # CORE INTERACTIVE COMPONENT EVENT BINDINGS
    # ==========================================================================
    def on_live_search(self, event):
        self.refresh_table()

    def on_filter_changed(self, event):
        self.refresh_table()

    def toggle_sort(self, column):
        self.current_sort_order = "DESC" if (self.current_sort_col == column and self.current_sort_order == "ASC") else "ASC"
        self.current_sort_col = column
        indicator = " ▲" if self.current_sort_order == "ASC" else " ▼"
        self.btn_sort_title.config(text=f"Sort by Title{indicator if column == 'title' else ' ↕'}")
        self.btn_sort_year.config(text=f"Sort by Year{indicator if column == 'year' else ' ↕'}")
        self.refresh_table()

    def on_row_selected(self, event):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0])["values"]
        if not vals: return
        self.selected_book_id = vals[0]
        self.book_id_entry.entry.config(state="normal")
        self.book_id_entry.set_text(str(vals[0]))
        self.book_id_entry.entry.config(state="disabled")
        self.title_entry.set_text(str(vals[1]))
        self.author_entry.set_text(str(vals[2]))
        self.year_entry.set_text(str(vals[3]))
        cat = str(vals[4])
        self.category_cb.set(cat if cat in ["Fiction", "Science", "History", "Biography", "Other"] else "Other")

    # ==========================================================================
    # CORE CRUD OPERATIONS & FLOW LOGIC
    # ==========================================================================
    def validate_form(self):
        t, a, y, c = self.title_entry.get(), self.author_entry.get(), self.year_entry.get(), self.category_cb.get()
        if not t or not a or not y:
            messagebox.showwarning("Validation Error", "All fields marked with * are required.", parent=self)
            return None
        try:
            y_val = int(y)
            if y_val <= 0 or y_val > 2100: raise ValueError
        except ValueError:
            messagebox.showwarning("Validation Error", "Please provide a valid publication year (1 to 2100).", parent=self)
            return None
        if c == "Select":
            messagebox.showwarning("Validation Error", "Please select a valid Book Category.", parent=self)
            return None
        return t, a, y_val, c

    def add_book(self):
        if not self.is_connected: return
        inputs = self.validate_form()
        if not inputs: return
        success, msg = self.db.add_book(*inputs)
        if success:
            messagebox.showinfo("Success", msg, parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def update_book(self):
        if not self.is_connected or not self.selected_book_id:
            if not self.selected_book_id: messagebox.showwarning("Selection Warning", "Select a book to update.", parent=self)
            return
        inputs = self.validate_form()
        if not inputs or not messagebox.askyesno("Confirm Update", f"Are you sure you want to update Book ID {self.selected_book_id}?", parent=self): return
        success, msg = self.db.update_book(self.selected_book_id, *inputs)
        if success:
            messagebox.showinfo("Success", msg, parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def delete_book(self):
        if not self.is_connected or not self.selected_book_id:
            if not self.selected_book_id: messagebox.showwarning("Selection Warning", "Select a book to delete.", parent=self)
            return
        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to permanently delete Book ID: {self.selected_book_id}?", parent=self): return
        success, msg = self.db.delete_book(self.selected_book_id)
        if success:
            messagebox.showinfo("Success", msg, parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def issue_book(self):
        if not self.is_connected or not self.selected_book_id:
            if not self.selected_book_id: messagebox.showwarning("Selection Warning", "Select a book to issue.", parent=self)
            return
        item = self.tree.selection()[0]
        status, title = self.tree.item(item)["values"][5], self.tree.item(item)["values"][1]
        if status == "Issued":
            messagebox.showwarning("Operation Error", f"'{title}' is already issued.", parent=self)
            return
        success, msg = self.db.change_status(self.selected_book_id, "Issued")
        if success:
            messagebox.showinfo("Success", f"Book issued successfully:\n'{title}' is checked out.", parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def return_book(self):
        if not self.is_connected or not self.selected_book_id:
            if not self.selected_book_id: messagebox.showwarning("Selection Warning", "Select a book to return.", parent=self)
            return
        item = self.tree.selection()[0]
        status, title = self.tree.item(item)["values"][5], self.tree.item(item)["values"][1]
        if status == "Available":
            messagebox.showwarning("Operation Error", f"'{title}' is already 'Available'.", parent=self)
            return
        success, msg = self.db.change_status(self.selected_book_id, "Available")
        if success:
            messagebox.showinfo("Success", f"Book returned successfully:\n'{title}' is back in stock.", parent=self)
            self.clear_form()
            self.refresh_table()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def clear_form(self):
        self.selected_book_id = None
        self.book_id_entry.entry.config(state="normal")
        self.book_id_entry.clear()
        self.book_id_entry.entry.config(state="disabled")
        self.title_entry.clear()
        self.author_entry.clear()
        self.year_entry.clear()
        self.category_cb.set("Select")
        self.tree.selection_remove(self.tree.selection())

    # ==========================================================================
    # UTILITIES & EXPORT FEATURES
    # ==========================================================================
    def export_csv(self):
        if not self.is_connected: return
        books = self.db.get_all_books()
        if not books:
            messagebox.showwarning("Export Warning", "No records to export.", parent=self)
            return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], title="Export Books to CSV", parent=self)
        if not fp: return
        try:
            with open(fp, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["ID", "Title", "Author", "Year", "Category", "Status"])
                for b in books:
                    w.writerow([b["id"], b["title"], b["author"], b["year"], b["category"], b["status"]])
            messagebox.showinfo("Export Successful", f"Written successfully to:\n{fp}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Failure", f"An error occurred:\n{str(e)}", parent=self)

    # ==========================================================================
    # MODAL DIALOG POPUPS (DB SETTINGS, FULL STATS)
    # ==========================================================================
    def show_db_settings_modal(self):
        modal = tk.Toplevel(self)
        modal.title("Database Connection Settings")
        modal.geometry("380x360")
        modal.resizable(False, False)
        modal.grab_set()
        modal.focus_set()
        
        x = self.winfo_x() + (self.winfo_width() // 2) - (380 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (360 // 2)
        modal.geometry(f"380x360+{x}+{y}")
        
        colors = self.colors[self.current_theme]
        modal.config(bg=colors["card_bg"])
        tk.Label(modal, text="⚙️ Connection Settings", font=("Segoe UI", 12, "bold"), fg=colors["primary"], bg=colors["card_bg"]).pack(anchor="w", padx=25, pady=(25, 15))
        
        fields_frame = tk.Frame(modal, bg=colors["card_bg"])
        fields_frame.pack(fill="both", expand=True, padx=25)
        fields_frame.columnconfigure(1, weight=1)
        
        fields = [("Host", "host", 0), ("Port", "port", 1), ("Username", "user", 2), ("Password", "password", 3)]
        entries = {}
        for label, key, row in fields:
            tk.Label(fields_frame, text=label, font=("Segoe UI", 9, "bold"), fg=colors["text"], bg=colors["card_bg"]).grid(row=row, column=0, sticky="w", pady=6)
            val = str(self.db.config.get(key, ""))
            entry = ModernEntry(fields_frame, show="*" if key == "password" else "", width=18, bg_color=colors["card_bg"], border_color=colors["border"], focus_color=colors["primary"], text_color=colors["text"])
            entry.set_text(val)
            entry.grid(row=row, column=1, sticky="ew", padx=(15, 0), pady=6)
            entries[key] = entry
            
        def save_and_reconnect():
            h, p, u, pwd = entries["host"].get(), entries["port"].get(), entries["user"].get(), entries["password"].get()
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
            
        btn_frame = tk.Frame(modal, bg=colors["card_bg"])
        btn_frame.pack(fill="x", padx=25, pady=(0, 25))
        ModernButton(btn_frame, text="Cancel", command=modal.destroy, button_type="secondary").pack(side="left")
        ModernButton(btn_frame, text="Save & Connect", command=save_and_reconnect, bg_color=colors["primary"], hover_color=colors["primary_light"]).pack(side="right")
        self._style_widgets_recursive(modal, colors)

    def show_statistics_modal(self):
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
        
        tk.Label(modal, text="📊 Library Dashboard Analytics", font=("Segoe UI", 14, "bold"), fg=colors["primary"], bg=colors["bg"]).pack(anchor="w", padx=25, pady=(25, 10))
        
        metrics_frame = tk.Frame(modal, bg=colors["bg"])
        metrics_frame.pack(fill="x", padx=25, pady=10)
        metrics_frame.columnconfigure((0, 1, 2), weight=1)
        
        metrics = [
            (stats["total_books"], "Total Books", 0),
            (stats["unique_authors"], "Unique Authors", 1),
            (f"{stats['available_count']} / {stats['issued_count']}", "Avail / Issued", 2)
        ]
        for val, lbl, col in metrics:
            card = tk.Frame(metrics_frame, bg=colors["card_bg"], bd=1, highlightthickness=0)
            card.grid(row=0, column=col, sticky="nsew", padx=4 if col != 0 else (0, 4))
            tk.Label(card, text=str(val), font=("Segoe UI", 18, "bold"), fg=colors["primary"], bg=colors["card_bg"]).pack(pady=(12, 2))
            tk.Label(card, text=lbl, font=("Segoe UI", 8, "bold"), fg=colors["text_muted"], bg=colors["card_bg"]).pack(pady=(0, 12))
            
        cat_panel = tk.Frame(modal, bg=colors["card_bg"], bd=1, highlightthickness=0)
        cat_panel.pack(fill="both", expand=True, padx=25, pady=8)
        tk.Label(cat_panel, text="Category Distribution", font=("Segoe UI", 10, "bold"), fg=colors["text"], bg=colors["card_bg"]).pack(anchor="w", padx=15, pady=(15, 10))
        
        tot_books = stats["total_books"]
        if tot_books == 0:
            tk.Label(cat_panel, text="No book records registered to build a distribution.", font=("Segoe UI", 9, "italic"), fg=colors["text_muted"], bg=colors["card_bg"]).pack(anchor="w", padx=15, pady=20)
        else:
            all_cats = ["Fiction", "Science", "History", "Biography", "Other"]
            for cat in all_cats:
                count = stats["by_category"].get(cat, 0)
                pct = (count / tot_books) * 100
                bar_row = tk.Frame(cat_panel, bg=colors["card_bg"])
                bar_row.pack(fill="x", padx=15, pady=4)
                tk.Label(bar_row, text=f"{cat} ({count})", font=("Segoe UI", 9), fg=colors["text"], bg=colors["card_bg"]).pack(side="left")
                tk.Label(bar_row, text=f"{pct:.1f}%", font=("Segoe UI", 8, "bold"), fg=colors["text_muted"], bg=colors["card_bg"]).pack(side="right")
                
                bar_bg = tk.Frame(cat_panel, height=6, bg=colors["border"])
                bar_bg.pack(fill="x", padx=15, pady=(0, 8))
                if pct > 0:
                    bar_fill = tk.Frame(bar_bg, height=6, bg=colors["primary"])
                    bar_fill.place(relx=0, rely=0, relwidth=pct/100, relheight=1.0)
                    
        years_panel = tk.Frame(modal, bg=colors["card_bg"], bd=1, highlightthickness=0)
        years_panel.pack(fill="x", padx=25, pady=(8, 20))
        tk.Label(years_panel, text="Top Book Years Distribution", font=("Segoe UI", 10, "bold"), fg=colors["text"], bg=colors["card_bg"]).pack(anchor="w", padx=15, pady=(15, 8))
        
        top_years = sorted(stats["by_year"].items(), key=lambda x: x[1], reverse=True)[:5]
        y_summary = ",   ".join(f"{y}: {cnt} books" for y, cnt in top_years) if top_years else "No publications registered."
        tk.Label(years_panel, text=y_summary, font=("Segoe UI", 9), fg=colors["text_muted"], bg=colors["card_bg"], wraplength=440, justify="left").pack(anchor="w", padx=15, pady=(0, 15))
        
        ModernButton(modal, text="Close Dashboard", command=modal.destroy, bg_color=colors["primary"], hover_color=colors["primary_light"]).pack(pady=(0, 20))
        self._style_widgets_recursive(modal, colors)

    # ==========================================================================
    # SYSTEM THEMING ENGINE
    # ==========================================================================
    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.theme_btn.config(text="☀️ Light Mode" if self.current_theme == "dark" else "🌙 Dark Mode")
        self.apply_theme()

    def apply_theme(self):
        colors = self.colors[self.current_theme]
        self.config(bg=colors["bg"])
        self.style.theme_use("clam")
        
        self.style.configure(
            "Treeview", background=colors["card_bg"], foreground=colors["text"],
            fieldbackground=colors["card_bg"], rowheight=32, relief="flat", borderwidth=0, font=("Segoe UI", 9)
        )
        self.style.map("Treeview", background=[("selected", colors["primary"])], foreground=[("selected", "#ffffff")])
        
        even_bg = colors["card_bg"]
        odd_bg = colors["bg"] if self.current_theme == "light" else "#24324a"
        self.tree.tag_configure("evenrow", background=even_bg, foreground=colors["text"])
        self.tree.tag_configure("oddrow", background=odd_bg, foreground=colors["text"])
        
        self.style.configure("Treeview.Heading", background=colors["border"], foreground=colors["text"], relief="flat", borderwidth=1, font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview.Heading", background=[("active", colors["border"])])
        
        self.style.configure("Vertical.TScrollbar", background=colors["border"], troughcolor=colors["bg"], arrowcolor=colors["text"], relief="flat", borderwidth=0)
        self.style.map("Vertical.TScrollbar", background=[("active", colors["primary"]), ("pressed", colors["primary_light"])])
        
        self.style.configure("TCombobox", fieldbackground=colors["card_bg"], background=colors["border"], foreground=colors["text"], relief="flat", borderwidth=0, arrowcolor=colors["text"])
        self.style.map("TCombobox", fieldbackground=[("readonly", colors["card_bg"])], selectbackground=[("readonly", colors["primary"])], selectforeground=[("readonly", "#ffffff")])
        
        self._style_widgets_recursive(self, colors)

    def _style_widgets_recursive(self, widget, colors):
        for child in widget.winfo_children():
            w_class = child.winfo_class()
            if isinstance(child, ModernEntry):
                child.set_colors(colors["card_bg"], colors["border"], colors["primary"], colors["text"], colors["text_muted"])
            elif isinstance(child, ModernButton):
                b_type = getattr(child, "button_type", "primary")
                btn_colors = {
                    "primary": (colors["primary"], colors["primary_light"], "#fff"),
                    "danger": ("#ef4444", "#dc2626", "#fff"),
                    "success": ("#22c55e", "#16a34a", "#fff"),
                    "secondary": (colors["border"], colors["bg"], colors["text"])
                }
                child.set_colors(*btn_colors.get(b_type, btn_colors["secondary"]))
            elif w_class in ("Frame", "Labelframe"):
                child.config(bg=colors["card_bg"] if getattr(child, "is_panel", False) else colors["bg"])
                if getattr(child, "has_border", False):
                    child.config(highlightbackground=colors["border"], highlightcolor=colors["border"])
                self._style_widgets_recursive(child, colors)
            elif w_class == "Label":
                l_type, in_panel = getattr(child, "label_type", "normal"), getattr(child, "in_panel", False)
                bg = colors["card_bg"] if in_panel else colors["bg"]
                fg = colors["primary"] if l_type in ("heading", "panel_heading") else (colors["text_muted"] if l_type == "muted" else colors["text"])
                if l_type == "heading": bg = colors["bg"]
                child.config(bg=bg, fg=fg)
            elif w_class == "Canvas":
                child.config(bg=colors["card_bg"] if getattr(child, "in_panel", False) else colors["bg"])
            elif w_class not in ("Entry", "Listbox", "Scrollbar", "TScrollbar", "Combobox"):
                self._style_widgets_recursive(child, colors)

# ==============================================================================
# MAIN LAUNCH BLOCK
# ==============================================================================
if __name__ == "__main__":
    app = LMSApp()
    app.mainloop()