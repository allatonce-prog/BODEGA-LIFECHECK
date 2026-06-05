import os
import sys
import datetime
import json
import sqlite3
import math
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess

class ReloadConflictDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Reload Batch Conflict")
        self.geometry("380x160")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Center dialog
        self.update_idletasks()
        rx = parent.winfo_x()
        ry = parent.winfo_y()
        rw = parent.winfo_width()
        rh = parent.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        self.geometry(f"+{x}+{y}")
        
        self.configure(bg="#f8fafc")
        self.result = None  # 'append' (Overwrite/Add), 'replace', or None
        
        lbl = tk.Label(
            self,
            text="Active dispatch table is not empty.\nChoose how to load the history batch:",
            font=("Segoe UI", 10, "bold"),
            bg="#f8fafc",
            fg="#0f172a",
            pady=15
        )
        lbl.pack()
        
        btn_frame = tk.Frame(self, bg="#f8fafc")
        btn_frame.pack(fill=tk.X, pady=10)
        
        # 'Overwrite' maps to append (adding to the current selected items)
        btn_add = tk.Button(
            btn_frame,
            text="Overwrite (Add)",
            font=("Segoe UI", 9, "bold"),
            bg="#0ea5e9",
            fg="#ffffff",
            activebackground="#0284c7",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=6,
            command=self.on_add
        )
        btn_add.pack(side=tk.LEFT, padx=(30, 10), expand=True)
        
        # 'Replace' maps to replacing current selected items entirely
        btn_replace = tk.Button(
            btn_frame,
            text="Replace Current",
            font=("Segoe UI", 9, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=6,
            command=self.on_replace
        )
        btn_replace.pack(side=tk.LEFT, padx=(10, 30), expand=True)
        
        # Bind close window to cancel
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
    def on_add(self):
        self.result = 'append'
        self.destroy()
        
    def on_replace(self):
        self.result = 'replace'
        self.destroy()
        
    def on_cancel(self):
        self.result = None
        self.destroy()

class AutocompleteDropdown:
    def __init__(self, entry, get_suggestions_func, on_select_callback):
        self.entry = entry
        self.get_suggestions_func = get_suggestions_func
        self.on_select_callback = on_select_callback
        self.dropdown = None
        self.listbox = None
        
        # Bindings on the entry widget
        self.entry.bind("<KeyRelease>", self.on_key_release)
        self.entry.bind("<FocusOut>", self.on_focus_out)
        self.entry.bind("<Down>", self.on_arrow_down)
        
    def on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        self.show_dropdown()
        
    def show_dropdown(self):
        query = self.entry.get().strip()
        if not query:
            self.hide_dropdown()
            return
            
        suggestions = self.get_suggestions_func(query)
        if not suggestions:
            self.hide_dropdown()
            return
            
        if not self.dropdown:
            self.dropdown = tk.Toplevel(self.entry.winfo_toplevel())
            self.dropdown.wm_overrideredirect(True)
            
            # Listbox container to allow styling border
            container = tk.Frame(self.dropdown, bg="#cbd5e1", bd=1)
            container.pack(fill=tk.BOTH, expand=True)
            
            # Add scrollbar for larger matches list
            scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.listbox = tk.Listbox(
                container,
                font=self.entry.cget("font"),
                bg="#ffffff",
                fg="#0f172a",
                selectbackground="#0ea5e9",
                selectforeground="#ffffff",
                bd=0,
                highlightthickness=0,
                yscrollcommand=scrollbar.set
            )
            self.listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=self.listbox.yview)
            
            self.listbox.bind("<ButtonRelease-1>", self.on_click_select)
            self.listbox.bind("<Return>", self.on_enter_select)
            self.listbox.bind("<Escape>", lambda e: self.hide_dropdown())
            
        # Update content
        self.listbox.delete(0, tk.END)
        for s in suggestions[:12]:  # Limit to top 12 suggestions for compact display
            self.listbox.insert(tk.END, s)
            
        # Position dropdown right below the entry widget
        self.entry.update_idletasks()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w = self.entry.winfo_width()
        
        # Calculate dynamic height based on item count
        item_count = min(12, len(suggestions))
        h = item_count * 22 + 4 # approx 22px per item + 4px padding
        self.dropdown.wm_geometry(f"{w}x{h}+{x}+{y}")
        self.dropdown.deiconify()
        self.dropdown.lift()
        
    def hide_dropdown(self):
        if self.dropdown:
            try:
                self.dropdown.destroy()
            except Exception:
                pass
            self.dropdown = None
            self.listbox = None
            
    def on_focus_out(self, event):
        # Small delay allows mouse click events to register on listbox before destruction
        self.entry.after(180, self.hide_dropdown)
        
    def on_arrow_down(self, event):
        if self.listbox and self.dropdown:
            self.listbox.focus_set()
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            
    def on_click_select(self, event):
        if self.listbox:
            sel = self.listbox.curselection()
            if sel:
                val = self.listbox.get(sel[0])
                self.on_select_callback(val)
            self.hide_dropdown()
            
    def on_enter_select(self, event):
        if self.listbox:
            sel = self.listbox.curselection()
            if sel:
                val = self.listbox.get(sel[0])
                self.on_select_callback(val)
            self.hide_dropdown()

class BodegaStockOutApp:
    def __init__(self, root):
        self.root = root
        self.root.title("STOCKOUT")
        self.root.geometry("960x680")  # Comfortable width for the 3-column layout
        self.root.minsize(920, 580)
        
        # Load local database (SQLite persistence)
        self.products_file = "products.json"
        self.history_file = "history.json"
        self.db_path = "bodega.db"
        self.products = []
        self.history = []
        self.dispatch_items = []
        self.load_data()
        
        # Configure overall themes and styles
        self.configure_styles()
        
        # Main application outer grid container
        self.main_container = tk.Frame(self.root, bg="#f8fafc")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # 1. Top Banner Panel (Dark Slate with Blue Accent Accent Bar)
        self.create_header_banner()
        
        # 2. Custom Sleek Web-like Navigation Tab Bar
        self.create_navigation_bar()
        
        # 3. Tab Container Panel (Fills the remaining area)
        self.tab_container = tk.Frame(self.main_container, bg="#f8fafc")
        self.tab_container.pack(fill=tk.BOTH, expand=True)
        
        # Instantiation of each tab's UI frames (unpacked by default)
        self.create_dispatch_tab()
        self.create_inventory_tab()
        self.create_history_tab()
        self.create_settings_tab()
        
        # 4. Sticky Footer Status Bar at the bottom
        self.create_footer_status()
        
        # Bind smart keyboard shortcuts based on focused tab
        self.root.bind("<Delete>", self.handle_delete_shortcut)
        self.root.bind("<Control-p>", lambda e: self.print_report() if self.active_tab == "dispatch" else None)
        self.root.bind("<Control-P>", lambda e: self.print_report() if self.active_tab == "dispatch" else None)
        self.root.bind("<Control-Key-1>", lambda e: self.switch_tab("dispatch"))
        self.root.bind("<Control-Key-2>", lambda e: self.switch_tab("inventory"))
        self.root.bind("<Control-Key-3>", lambda e: self.switch_tab("history"))
        self.root.bind("<Control-Key-4>", lambda e: self.switch_tab("settings"))
        
        # Select and show default Tab
        self.active_tab = None
        self.switch_tab("dispatch")
        
        # Restore recent session if unsaved items exist (deferred to avoid focus issues)
        self.root.after(100, self.check_and_restore_session)
        
    def configure_styles(self):
        """Sets up a modern, custom flat theme for ttk widgets using standard Tkinter."""
        self.root.configure(bg="#f8fafc") # Elegant light slate background
        
        style = ttk.Style()
        style.theme_use("clam") # Clean base engine
        
        # Configure overall Treeview aesthetics
        style.configure(
            "Custom.Treeview",
            background="#ffffff",
            foreground="#1e293b",
            rowheight=24,
            fieldbackground="#ffffff",
            font=("Segoe UI", 10),
            borderwidth=1,
            relief="flat"
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", "#0284c7")], # Sleek sky blue color when selected
            foreground=[("selected", "#ffffff")]
        )
        
        # Custom Treeview headers
        style.configure(
            "Custom.Treeview.Heading",
            background="#f1f5f9",
            foreground="#475569",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            relief="flat",
            padding=8
        )
        style.map(
            "Custom.Treeview.Heading",
            background=[("active", "#e2e8f0")]
        )

        # Style standard scrollbar
        style.configure(
            "Vertical.TScrollbar",
            background="#e2e8f0",
            arrowcolor="#475569",
            troughcolor="#f8fafc",
            borderwidth=0,
            relief="flat"
        )
        
    def create_header_banner(self):
        """Creates an elegant top header banner representing state-of-the-art design aesthetics."""
        banner = tk.Frame(self.main_container, bg="#0f172a", height=85) # Very dark slate background
        banner.pack(fill=tk.X, side=tk.TOP)
        banner.pack_propagate(False)
        
        # Elegant vertical accent bar
        accent_bar = tk.Frame(banner, bg="#0ea5e9", width=6)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)
        
        title_frame = tk.Frame(banner, bg="#0f172a", padx=20)
        title_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, anchor="w")
        
        # Main title label
        self.title_lbl = tk.Label(
            title_frame, 
            text=self.system_title, 
            font=("Segoe UI", 16, "bold"), 
            fg="#f8fafc", 
            bg="#0f172a",
            anchor="w"
        )
        self.title_lbl.pack(anchor="w", pady=(15, 2))
        
        # Modern subtle subtitle
        self.subtitle_lbl = tk.Label(
            title_frame, 
            text=self.system_description, 
            font=("Segoe UI", 9), 
            fg="#94a3b8", 
            bg="#0f172a",
            anchor="w"
        )
        self.subtitle_lbl.pack(anchor="w")

        # Session indicator bubble
        indicator_frame = tk.Frame(banner, bg="#1e293b", padx=15, pady=8, bd=0)
        indicator_frame.pack(side=tk.RIGHT, padx=25, pady=18)
        
        indicator_lbl = tk.Label(
            indicator_frame, 
            text="OFFLINE MODE", 
            font=("Segoe UI", 9, "bold"), 
            fg="#38bdf8", 
            bg="#1e293b"
        )
        indicator_lbl.pack()
        
    def create_navigation_bar(self):
        """Creates an elegant flat horizontal navigation bar for custom tab management."""
        self.nav_frame = tk.Frame(self.main_container, bg="#1e293b", height=42)
        self.nav_frame.pack(fill=tk.X)
        self.nav_frame.pack_propagate(False)
        
        self.tabs = {}
        
        # Build 4 navigation tabs
        self.tabs["dispatch"] = self.create_nav_tab_button(
            self.nav_frame, "📤 Stock-Out Dispatch", "dispatch", lambda: self.switch_tab("dispatch")
        )
        self.tabs["inventory"] = self.create_nav_tab_button(
            self.nav_frame, "📦 ITEMS", "inventory", lambda: self.switch_tab("inventory")
        )
        self.tabs["history"] = self.create_nav_tab_button(
            self.nav_frame, "📜 Stock-Out History", "history", lambda: self.switch_tab("history")
        )
        self.tabs["settings"] = self.create_nav_tab_button(
            self.nav_frame, "⚙️ Settings", "settings", lambda: self.switch_tab("settings")
        )
        
    def create_nav_tab_button(self, parent, text, tab_name, select_command):
        """Creates a custom tab layout (button + bottom highlight indicator bar)."""
        tab_btn_frame = tk.Frame(parent, bg="#1e293b")
        tab_btn_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        btn = tk.Button(
            tab_btn_frame,
            text=text,
            font=("Segoe UI", 10, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#1e293b",
            activeforeground="#38bdf8",
            bd=0,
            cursor="hand2",
            command=select_command,
            padx=20
        )
        btn.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        indicator = tk.Frame(tab_btn_frame, bg="#1e293b", height=3)
        indicator.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind elegant hover behaviors for non-active states
        btn.bind("<Enter>", lambda e: btn.config(fg="#38bdf8") if self.active_tab != tab_name else None)
        btn.bind("<Leave>", lambda e: btn.config(fg="#94a3b8") if self.active_tab != tab_name else None)
        
        return {"frame": tab_btn_frame, "button": btn, "indicator": indicator}
        
    def switch_tab(self, target_tab):
        """Transitions between tab layouts safely, refreshing lists and tracking application states."""
        if self.active_tab == target_tab:
            return
            
        # Hide all tab panels
        self.dispatch_frame.pack_forget()
        self.inventory_frame.pack_forget()
        self.history_frame.pack_forget()
        self.settings_frame.pack_forget()
        
        # Reset all nav buttons and indicators
        for name, tab_widgets in self.tabs.items():
            tab_widgets["button"].config(fg="#94a3b8", bg="#1e293b")
            tab_widgets["indicator"].config(bg="#1e293b")
            
        # Highlight active tab selection
        active_widgets = self.tabs[target_tab]
        active_widgets["button"].config(fg="#38bdf8", bg="#0f172a") # bright text, deep background
        active_widgets["indicator"].config(bg="#0ea5e9") # sky blue bottom line
        
        # Display matching layout panel
        if target_tab == "dispatch":
            self.dispatch_frame.pack(fill=tk.BOTH, expand=True)
            self.status_lbl.config(text="Ready. Operating fully offline.")
            self.refresh_quick_products()
            self.item_name_entry.focus_set()
        elif target_tab == "inventory":
            self.inventory_frame.pack(fill=tk.BOTH, expand=True)
            self.status_lbl.config(text="Manage ITEMS Product Catalog.")
            self.refresh_inventory_list()
            self.inv_name_entry.focus_set()
        elif target_tab == "history":
            self.history_frame.pack(fill=tk.BOTH, expand=True)
            self.status_lbl.config(text="Browse or reprint past stock-out dispatch sheets.")
            self.refresh_history_list()
        elif target_tab == "settings":
            self.settings_frame.pack(fill=tk.BOTH, expand=True)
            self.status_lbl.config(text="Configure app Title and Subtitle Description settings.")
            
        self.active_tab = target_tab
        
    def create_dispatch_tab(self):
        """Creates the primary dispatch tab frame layout (3 columns)."""
        self.dispatch_frame = tk.Frame(self.tab_container, bg="#f8fafc")
        
        # 3-column layout container
        dispatch_content = tk.Frame(self.dispatch_frame, bg="#f8fafc", padx=15, pady=15)
        dispatch_content.pack(fill=tk.BOTH, expand=True)
        
        # ========================================================
        # COLUMN 1: Quick Products Catalog Drawer (Leftmost)
        # ========================================================
        self.quick_catalog_panel = tk.LabelFrame(
            dispatch_content, 
            text="  Quick Products  ",
            font=("Segoe UI", 9, "bold"),
            fg="#475569", 
            bg="#ffffff", 
            bd=1, 
            relief="solid", 
            padx=10, 
            pady=10
        )
        self.quick_catalog_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        self.quick_catalog_panel.pack_propagate(False)
        self.quick_catalog_panel.config(width=230)
        
        # Search entry
        lbl_qsearch = tk.Label(
            self.quick_catalog_panel, 
            text="Search Catalog", 
            font=("Segoe UI", 8, "bold"),
            fg="#64748b", 
            bg="#ffffff"
        )
        lbl_qsearch.pack(anchor="w", pady=(0, 2))
        
        self.quick_search_var = tk.StringVar()
        self.quick_search_entry = tk.Entry(
            self.quick_catalog_panel,
            textvariable=self.quick_search_var,
            font=("Segoe UI", 9),
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#0f172a",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#0ea5e9"
        )
        self.quick_search_entry.pack(fill=tk.X, pady=(0, 8), ipady=3)
        self.quick_search_var.trace_add("write", self.filter_quick_products)
        
        # Products treeview container
        quick_tree_container = tk.Frame(self.quick_catalog_panel, bg="#cbd5e1", bd=1, relief="solid")
        quick_tree_container.pack(fill=tk.BOTH, expand=True)
        
        q_scrollbar = ttk.Scrollbar(quick_tree_container, orient=tk.VERTICAL, style="Vertical.TScrollbar")
        q_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.quick_tree = ttk.Treeview(
            quick_tree_container,
            columns=("name",),
            show="headings",
            selectmode="browse",
            yscrollcommand=q_scrollbar.set,
            style="Custom.Treeview"
        )
        self.quick_tree.pack(fill=tk.BOTH, expand=True)
        q_scrollbar.config(command=self.quick_tree.yview)
        
        self.quick_tree.heading("name", text="PRODUCT CATALOG")
        self.quick_tree.column("name", anchor="w", width=180)
        
        # Style row tags
        self.quick_tree.tag_configure("even", background="#ffffff")
        self.quick_tree.tag_configure("odd", background="#f8fafc")
        
        # Bind events for mouse action productivity
        self.quick_tree.bind("<<TreeviewSelect>>", lambda e: self.quick_select_click())
        self.quick_tree.bind("<Double-1>", lambda e: self.quick_add_double_click())
        self.quick_tree.bind("<Button-1>", lambda e: self.handle_tree_deselect(e, self.quick_tree), add="+")
        
        # Quick help label
        lbl_qhelp = tk.Label(
            self.quick_catalog_panel,
            text="✨ Click/Double-click to select.\n   Then type qty & press Enter.",
            font=("Segoe UI", 7, "italic"),
            fg="#94a3b8",
            bg="#ffffff",
            justify=tk.LEFT
        )
        lbl_qhelp.pack(fill=tk.X, pady=(8, 0))
        
        # Dev test panel (for testing print output)
        dev_frame = tk.Frame(self.quick_catalog_panel, bg="#ffffff")
        dev_frame.pack(fill=tk.X, pady=(10, 0))
        
        lbl_dev = tk.Label(
            dev_frame,
            text="🧪 DEV TOOLS (Test Print scaling):",
            font=("Segoe UI", 7, "bold"),
            fg="#ef4444",
            bg="#ffffff"
        )
        lbl_dev.pack(anchor="w", pady=(0, 2))
        
        # Row 1 of buttons
        row1_frame = tk.Frame(dev_frame, bg="#ffffff")
        row1_frame.pack(fill=tk.X, pady=(2, 2))
        
        btn_dev50 = tk.Button(
            row1_frame,
            text="Load 50 Items",
            font=("Segoe UI", 8, "bold"),
            bg="#f1f5f9",
            fg="#475569",
            activebackground="#e2e8f0",
            bd=1,
            relief="solid",
            cursor="hand2",
            command=lambda: self.populate_test_items(50)
        )
        btn_dev50.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        btn_dev100 = tk.Button(
            row1_frame,
            text="Load 100 Items",
            font=("Segoe UI", 8, "bold"),
            bg="#f1f5f9",
            fg="#475569",
            activebackground="#e2e8f0",
            bd=1,
            relief="solid",
            cursor="hand2",
            command=lambda: self.populate_test_items(100)
        )
        btn_dev100.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Row 2 of buttons
        row2_frame = tk.Frame(dev_frame, bg="#ffffff")
        row2_frame.pack(fill=tk.X, pady=(2, 0))
        
        btn_append100 = tk.Button(
            row2_frame,
            text="+100 Items (Append)",
            font=("Segoe UI", 8, "bold"),
            bg="#f1f5f9",
            fg="#10b981",
            activebackground="#e2e8f0",
            bd=1,
            relief="solid",
            cursor="hand2",
            command=lambda: self.append_test_items(100)
        )
        btn_append100.pack(fill=tk.X)
        
        # ========================================================
        # COLUMN 2: Manual Data Entry & Actions (Middle)
        # ========================================================
        self.left_panel = tk.Frame(dispatch_content, bg="#f8fafc", width=230)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        self.left_panel.pack_propagate(False)
        
        entry_card = tk.LabelFrame(
            self.left_panel, 
            text="  Add Dispatched Item  ", 
            font=("Segoe UI", 10, "bold"),
            fg="#475569", 
            bg="#ffffff", 
            bd=1, 
            relief="solid", 
            padx=12, 
            pady=12
        )
        entry_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        
        lbl_item = tk.Label(
            entry_card, 
            text="Item Name / Description", 
            font=("Segoe UI", 9, "bold"),
            fg="#64748b", 
            bg="#ffffff"
        )
        lbl_item.pack(anchor="w", pady=(2, 2))
        
        self.item_name_var = tk.StringVar()
        self.item_name_entry = tk.Entry(
            entry_card, 
            textvariable=self.item_name_var,
            font=("Segoe UI", 10),
            bg="#f8fafc", 
            fg="#0f172a", 
            insertbackground="#0f172a",
            bd=1, 
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#0ea5e9"
        )
        self.item_name_entry.pack(fill=tk.X, pady=(0, 8), ipady=3)
        
        # Wire up Autocomplete Dropdown suggestions from product catalog
        def get_suggestions(query):
            q = query.lower()
            return [prod for prod in self.products if q in prod.lower()]
            
        def on_select_autocomplete(val):
            self.item_name_var.set(val)
            self.qty_entry.focus_set()
            
        self.autocomplete = AutocompleteDropdown(
            self.item_name_entry, 
            get_suggestions_func=get_suggestions, 
            on_select_callback=on_select_autocomplete
        )
        
        lbl_qty = tk.Label(
            entry_card, 
            text="Quantity", 
            font=("Segoe UI", 9, "bold"),
            fg="#64748b", 
            bg="#ffffff"
        )
        lbl_qty.pack(anchor="w", pady=(2, 2))
        
        self.qty_var = tk.StringVar()
        self.qty_entry = tk.Entry(
            entry_card, 
            textvariable=self.qty_var,
            font=("Segoe UI", 10),
            bg="#f8fafc", 
            fg="#0f172a", 
            insertbackground="#0f172a",
            bd=1, 
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#0ea5e9"
        )
        self.qty_entry.pack(fill=tk.X, pady=(0, 10), ipady=3)
        self.qty_entry.bind("<Return>", lambda event: self.add_item())
        
        tip_lbl = tk.Label(
            entry_card, 
            text="💡 Tip: Select from catalog or type a name,\nenter quantity & press ENTER to add.", 
            font=("Segoe UI", 8, "italic"),
            fg="#64748b",
            bg="#ffffff",
            justify=tk.LEFT
        )
        tip_lbl.pack(fill=tk.X, pady=(2, 10))
        
        self.btn_add = tk.Button(
            entry_card,
            text="+ Add to List",
            font=("Segoe UI", 9, "bold"),
            bg="#0ea5e9", 
            fg="#ffffff",
            activebackground="#0284c7",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.add_item,
            padx=10,
            pady=6
        )
        self.btn_add.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_add, "#0ea5e9", "#0284c7")
        
        # Actions layout at bottom
        actions_card = tk.Frame(self.left_panel, bg="#f8fafc")
        actions_card.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_delete = tk.Button(
            actions_card,
            text="Remove Selected",
            font=("Segoe UI", 9, "bold"),
            bg="#f1f5f9",
            fg="#ef4444", 
            activebackground="#e2e8f0",
            activeforeground="#b91c1c",
            bd=0,
            cursor="hand2",
            command=self.delete_selected_item,
            pady=5
        )
        self.btn_delete.pack(fill=tk.X, pady=(0, 6))
        self.setup_hover_effect(self.btn_delete, "#f1f5f9", "#e2e8f0")
        
        self.btn_clear = tk.Button(
            actions_card,
            text="Clear Session List",
            font=("Segoe UI", 9, "bold"),
            bg="#f1f5f9",
            fg="#64748b", 
            activebackground="#e2e8f0",
            activeforeground="#0f172a",
            bd=0,
            cursor="hand2",
            command=self.clear_list,
            pady=5
        )
        self.btn_clear.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_clear, "#f1f5f9", "#e2e8f0")
        
        # ========================================================
        # COLUMN 3: Active Batch Table (Rightmost)
        # ========================================================
        self.right_panel = tk.Frame(dispatch_content, bg="#f8fafc")
        self.right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        table_header_frame = tk.Frame(self.right_panel, bg="#f8fafc")
        table_header_frame.pack(fill=tk.X, pady=(0, 6))
        
        table_title = tk.Label(
            table_header_frame, 
            text="Current Dispatch Batch", 
            font=("Segoe UI", 11, "bold"), 
            fg="#1e293b", 
            bg="#f8fafc"
        )
        table_title.pack(side=tk.LEFT)
        
        self.count_var = tk.StringVar(value="0 items")
        self.count_lbl = tk.Label(
            table_header_frame,
            textvariable=self.count_var,
            font=("Segoe UI", 9, "bold"),
            fg="#64748b",
            bg="#e2e8f0",
            padx=8,
            pady=2
        )
        self.count_lbl.pack(side=tk.RIGHT)
        
        # Real-time Batch Search Bar
        search_batch_frame = tk.Frame(self.right_panel, bg="#ffffff", bd=1, relief="solid", padx=10, pady=6)
        search_batch_frame.pack(fill=tk.X, pady=(0, 8))
        
        lbl_batch_search = tk.Label(
            search_batch_frame,
            text="🔍 Search Batch:",
            font=("Segoe UI", 9, "bold"),
            fg="#475569",
            bg="#ffffff"
        )
        lbl_batch_search.pack(side=tk.LEFT, padx=(0, 8))
        
        self.batch_search_var = tk.StringVar()
        self.batch_search_entry = tk.Entry(
            search_batch_frame,
            textvariable=self.batch_search_var,
            font=("Segoe UI", 10),
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#0f172a",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#0ea5e9"
        )
        self.batch_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.batch_search_var.trace_add("write", lambda *args: self.refresh_dispatch_tree())
        
        table_container = tk.Frame(
            self.right_panel, 
            bg="#cbd5e1", 
            bd=1, 
            relief="solid"
        )
        table_container.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        
        scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, style="Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(
            table_container, 
            columns=("description", "qty"), 
            show="headings", 
            selectmode="browse",
            yscrollcommand=scrollbar.set,
            style="Custom.Treeview"
        )
        self.tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)
        
        self.tree.heading("description", text="ITEM DESCRIPTION")
        self.tree.heading("qty", text="QTY")
        
        self.tree.column("description", anchor="w", width=250)
        self.tree.column("qty", anchor="center", width=80, minwidth=60, stretch=False)
        
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f8fafc")
        self.tree.bind("<Button-1>", lambda e: self.handle_tree_deselect(e, self.tree), add="+")
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<plus>", self.on_tree_increment)
        self.tree.bind("<equal>", self.on_tree_increment)
        self.tree.bind("<minus>", self.on_tree_decrement)
        self.tree.bind("<KP_Add>", self.on_tree_increment)
        self.tree.bind("<KP_Subtract>", self.on_tree_decrement)
        
        # Print bar at the bottom
        self.print_container = tk.Frame(self.right_panel, bg="#ffffff", bd=1, relief="solid", padx=12, pady=12)
        self.print_container.pack(fill=tk.X)
        
        self.btn_print = tk.Button(
            self.print_container,
            text="🖨️ Print Stock-Out Sheet (A4)",
            font=("Segoe UI", 11, "bold"),
            bg="#10b981", 
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.print_report,
            pady=10
        )
        self.btn_print.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_print, "#10b981", "#059669")

    def create_inventory_tab(self):
        """Creates the Master Inventory tab frame for adding and managing products (name-only)."""
        self.inventory_frame = tk.Frame(self.tab_container, bg="#f8fafc")
        
        content_frame = tk.Frame(self.inventory_frame, bg="#f8fafc", padx=20, pady=15)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left Panel (Add New Product form)
        left_p = tk.Frame(content_frame, bg="#f8fafc", width=280)
        left_p.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_p.pack_propagate(False)
        
        add_card = tk.LabelFrame(
            left_p, 
            text="  Fast Product Adder  ", 
            font=("Segoe UI", 10, "bold"),
            fg="#475569", 
            bg="#ffffff", 
            bd=1, 
            relief="solid", 
            padx=15, 
            pady=15
        )
        add_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        lbl_name = tk.Label(
            add_card, 
            text="Product Name / Label", 
            font=("Segoe UI", 9, "bold"),
            fg="#64748b", 
            bg="#ffffff"
        )
        lbl_name.pack(anchor="w", pady=(5, 3))
        
        self.inv_name_var = tk.StringVar()
        self.inv_name_entry = tk.Entry(
            add_card, 
            textvariable=self.inv_name_var,
            font=("Segoe UI", 11),
            bg="#f8fafc", 
            fg="#0f172a", 
            insertbackground="#0f172a",
            bd=1, 
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#6366f1"
        )
        self.inv_name_entry.pack(fill=tk.X, pady=(0, 15), ipady=4)
        self.inv_name_entry.bind("<Return>", lambda e: self.add_inventory_product())
        
        lbl_tip = tk.Label(
            add_card,
            text="💡 Fast Add Tip:\nJust type the product name and press\nENTER to immediately register it!\nNo stocks required, name only.",
            font=("Segoe UI", 8, "italic"),
            fg="#64748b",
            bg="#ffffff",
            justify=tk.LEFT
        )
        lbl_tip.pack(fill=tk.X, pady=(5, 20))
        
        self.btn_add_inv = tk.Button(
            add_card,
            text="+ Add Product",
            font=("Segoe UI", 10, "bold"),
            bg="#6366f1",  # Modern elegant Indigo accent
            fg="#ffffff",
            activebackground="#4f46e5",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.add_inventory_product,
            padx=10,
            pady=8
        )
        self.btn_add_inv.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_add_inv, "#6366f1", "#4f46e5")
        
        # Right Panel (List of current catalog)
        right_p = tk.Frame(content_frame, bg="#f8fafc")
        right_p.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        header_p = tk.Frame(right_p, bg="#f8fafc")
        header_p.pack(fill=tk.X, pady=(0, 8))
        
        title_lbl = tk.Label(
            header_p,
            text="ITEMS",
            font=("Segoe UI", 12, "bold"),
            fg="#1e293b",
            bg="#f8fafc"
        )
        title_lbl.pack(side=tk.LEFT)
        
        self.catalog_count_var = tk.StringVar(value="0 products")
        self.catalog_count_lbl = tk.Label(
            header_p,
            textvariable=self.catalog_count_var,
            font=("Segoe UI", 9, "bold"),
            fg="#64748b",
            bg="#e2e8f0",
            padx=10,
            pady=2
        )
        self.catalog_count_lbl.pack(side=tk.RIGHT)
        
        # Search panel
        search_card = tk.Frame(right_p, bg="#ffffff", bd=1, relief="solid", padx=10, pady=8)
        search_card.pack(fill=tk.X, pady=(0, 10))
        
        lbl_search = tk.Label(
            search_card,
            text="🔍 Search ITEMS:",
            font=("Segoe UI", 9, "bold"),
            fg="#475569",
            bg="#ffffff"
        )
        lbl_search.pack(side=tk.LEFT, padx=(0, 10))
        
        self.inv_search_var = tk.StringVar()
        self.inv_search_entry = tk.Entry(
            search_card,
            textvariable=self.inv_search_var,
            font=("Segoe UI", 10),
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#0f172a",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#6366f1"
        )
        self.inv_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.inv_search_var.trace_add("write", self.filter_inventory_list)
        
        # Catalog Treeview table
        tree_container = tk.Frame(right_p, bg="#cbd5e1", bd=1, relief="solid")
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, style="Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.inv_tree = ttk.Treeview(
            tree_container,
            columns=("name",),
            show="headings",
            selectmode="browse",
            yscrollcommand=scrollbar.set,
            style="Custom.Treeview"
        )
        self.inv_tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.inv_tree.yview)
        
        self.inv_tree.heading("name", text="PRODUCT NAME")
        self.inv_tree.column("name", anchor="w", width=400)
        
        self.inv_tree.tag_configure("even", background="#ffffff")
        self.inv_tree.tag_configure("odd", background="#f8fafc")
        self.inv_tree.bind("<Button-3>", self.on_inv_tree_right_click)
        self.inv_tree.bind("<Button-2>", self.on_inv_tree_right_click)
        self.inv_tree.bind("<Button-1>", lambda e: self.handle_tree_deselect(e, self.inv_tree), add="+")
        
        # Delete action container directly under the treeview table
        delete_container = tk.Frame(right_p, bg="#f8fafc")
        delete_container.pack(fill=tk.X, pady=(10, 0))
        
        self.btn_del_inv = tk.Button(
            delete_container,
            text="❌ Delete Selected Product",
            font=("Segoe UI", 10, "bold"),
            bg="#ef4444",  # A vibrant premium red button
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.delete_inventory_product,
            pady=8
        )
        self.btn_del_inv.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_del_inv, "#ef4444", "#b91c1c")

    def create_history_tab(self):
        """Creates the Stock-Out History and monospace reprint viewer tab."""
        self.history_frame = tk.Frame(self.tab_container, bg="#f8fafc")
        
        content_frame = tk.Frame(self.history_frame, bg="#f8fafc", padx=20, pady=15)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left Panel (History list table)
        left_p = tk.Frame(content_frame, bg="#f8fafc", width=350)
        left_p.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_p.pack_propagate(False)
        
        left_title = tk.Label(
            left_p,
            text="Past Dispatch Batches",
            font=("Segoe UI", 11, "bold"),
            fg="#1e293b",
            bg="#f8fafc"
        )
        left_title.pack(anchor="w", pady=(0, 8))
        
        # Search & Filter Frame in left panel
        search_filter_frame = tk.Frame(left_p, bg="#f8fafc")
        search_filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Search Input
        search_lbl = tk.Label(
            search_filter_frame,
            text="Search Date (e.g. january 7):",
            font=("Segoe UI", 9, "bold"),
            fg="#475569",
            bg="#f8fafc"
        )
        search_lbl.pack(anchor="w")
        
        self.hist_search_var = tk.StringVar()
        self.hist_search_entry = tk.Entry(
            search_filter_frame,
            textvariable=self.hist_search_var,
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#0f172a",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#0ea5e9"
        )
        self.hist_search_entry.pack(fill=tk.X, pady=(2, 8), ipady=3)
        self.hist_search_var.trace_add("write", self.filter_history_list_by_search_or_time)
        
        # Timeframe Filter combobox
        filter_lbl = tk.Label(
            search_filter_frame,
            text="Timeframe Filter:",
            font=("Segoe UI", 9, "bold"),
            fg="#475569",
            bg="#f8fafc"
        )
        filter_lbl.pack(anchor="w")
        
        self.hist_filter_var = tk.StringVar(value="Recent (All)")
        self.hist_filter_cb = ttk.Combobox(
            search_filter_frame,
            textvariable=self.hist_filter_var,
            values=["Recent (All)", "Yesterday", "Last 7 Days"],
            state="readonly",
            font=("Segoe UI", 10)
        )
        self.hist_filter_cb.pack(fill=tk.X, pady=(2, 0))
        self.hist_filter_cb.bind("<<ComboboxSelected>>", self.filter_history_list_by_search_or_time)
        
        tree_container = tk.Frame(left_p, bg="#cbd5e1", bd=1, relief="solid")
        tree_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, style="Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.hist_tree = ttk.Treeview(
            tree_container,
            columns=("date", "ref", "qty"),
            show="headings",
            selectmode="browse",
            yscrollcommand=scrollbar.set,
            style="Custom.Treeview"
        )
        self.hist_tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.hist_tree.yview)
        
        self.hist_tree.heading("date", text="DATE / TIME")
        self.hist_tree.heading("ref", text="REF ID")
        self.hist_tree.heading("qty", text="QTY")
        
        self.hist_tree.column("date", anchor="w", width=130)
        self.hist_tree.column("ref", anchor="w", width=120)
        self.hist_tree.column("qty", anchor="center", width=60, minwidth=50, stretch=False)
        
        self.hist_tree.tag_configure("even", background="#ffffff")
        self.hist_tree.tag_configure("odd", background="#f8fafc")
        
        # Bind history click and right click context menu
        self.hist_tree.bind("<<TreeviewSelect>>", self.on_history_select)
        self.hist_tree.bind("<Button-3>", self.on_hist_tree_right_click)
        self.hist_tree.bind("<Button-2>", self.on_hist_tree_right_click)
        self.hist_tree.bind("<Button-1>", lambda e: self.handle_tree_deselect(e, self.hist_tree), add="+")
        
        # Actions at the bottom of left history panel
        actions_p = tk.Frame(left_p, bg="#f8fafc")
        actions_p.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_del_hist = tk.Button(
            actions_p,
            text="❌ Delete Selected Log Record",
            font=("Segoe UI", 9, "bold"),
            bg="#f1f5f9",
            fg="#ef4444",
            activebackground="#e2e8f0",
            activeforeground="#b91c1c",
            bd=0,
            cursor="hand2",
            command=self.delete_history_record,
            pady=8
        )
        self.btn_del_hist.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_del_hist, "#f1f5f9", "#e2e8f0")
        
        # Right Panel (Monospace Report Viewer)
        right_p = tk.Frame(content_frame, bg="#f8fafc")
        right_p.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_title = tk.Label(
            right_p,
            text="A4 Document Preview (Monospace Raw Visuals)",
            font=("Segoe UI", 11, "bold"),
            fg="#1e293b",
            bg="#f8fafc"
        )
        right_title.pack(anchor="w", pady=(0, 8))
        
        # Monospace viewer container
        viewer_container = tk.Frame(right_p, bg="#cbd5e1", bd=1, relief="solid")
        viewer_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Monospace Text Box using standard library scrolledtext
        self.hist_text = scrolledtext.ScrolledText(
            viewer_container,
            font=("Consolas", 9),
            bg="#0f172a",  # Deep dark slate aesthetic
            fg="#38bdf8",  # Highly legible cyber sky blue
            insertbackground="#f8fafc",
            wrap=tk.WORD,
            bd=0,
            padx=15,
            pady=15
        )
        self.hist_text.pack(fill=tk.BOTH, expand=True)
        self.hist_text.insert(tk.END, "Select a stock-out record from the left list to view printed dispatch report.")
        self.hist_text.config(state=tk.DISABLED)
        
        # Reprint bar at the bottom
        hist_print_p = tk.Frame(right_p, bg="#ffffff", bd=1, relief="solid", padx=12, pady=12)
        hist_print_p.pack(fill=tk.X)
        
        self.btn_reprint = tk.Button(
            hist_print_p,
            text="🖨️ Reprint Selected Report (A4)",
            font=("Segoe UI", 11, "bold"),
            bg="#10b981",
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.reprint_history_record,
            pady=10
        )
        self.btn_reprint.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_reprint, "#10b981", "#059669")
        
        # Disable action buttons by default until item selected
        self.btn_reprint.config(state=tk.DISABLED, bg="#94a3b8")
        self.btn_del_hist.config(state=tk.DISABLED, fg="#94a3b8")

    def create_settings_tab(self):
        """Creates the Settings tab frame to configure system Title and Subtitle Description."""
        self.settings_frame = tk.Frame(self.tab_container, bg="#f8fafc")
        
        content_frame = tk.Frame(self.settings_frame, bg="#f8fafc", padx=40, pady=30)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Settings Card
        settings_card = tk.LabelFrame(
            content_frame, 
            text="  System Banner Configurations  ", 
            font=("Segoe UI", 11, "bold"),
            fg="#475569", 
            bg="#ffffff", 
            bd=1, 
            relief="solid", 
            padx=25, 
            pady=25
        )
        settings_card.pack(fill=tk.X, anchor="n")
        
        # Title Label & Entry
        lbl_title = tk.Label(
            settings_card, 
            text="Header System Title", 
            font=("Segoe UI", 10, "bold"),
            fg="#64748b", 
            bg="#ffffff"
        )
        lbl_title.pack(anchor="w", pady=(5, 3))
        
        self.settings_title_var = tk.StringVar(value=self.system_title)
        self.settings_title_entry = tk.Entry(
            settings_card, 
            textvariable=self.settings_title_var,
            font=("Segoe UI", 11),
            bg="#f8fafc", 
            fg="#0f172a", 
            insertbackground="#0f172a",
            bd=1, 
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#0ea5e9"
        )
        self.settings_title_entry.pack(fill=tk.X, pady=(0, 20), ipady=5)
        
        # Description Label & Entry
        lbl_desc = tk.Label(
            settings_card, 
            text="Header Subtitle Description", 
            font=("Segoe UI", 10, "bold"),
            fg="#64748b", 
            bg="#ffffff"
        )
        lbl_desc.pack(anchor="w", pady=(5, 3))
        
        self.settings_desc_var = tk.StringVar(value=self.system_description)
        self.settings_desc_entry = tk.Entry(
            settings_card, 
            textvariable=self.settings_desc_var,
            font=("Segoe UI", 11),
            bg="#f8fafc", 
            fg="#0f172a", 
            insertbackground="#0f172a",
            bd=1, 
            relief="solid",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#0ea5e9"
        )
        self.settings_desc_entry.pack(fill=tk.X, pady=(0, 25), ipady=5)
        
        # Save Settings Button
        self.btn_save_settings = tk.Button(
            settings_card,
            text="💾 Save Configurations",
            font=("Segoe UI", 11, "bold"),
            bg="#0ea5e9", 
            fg="#ffffff",
            activebackground="#0284c7",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.save_settings,
            padx=20,
            pady=10
        )
        self.btn_save_settings.pack(fill=tk.X)
        self.setup_hover_effect(self.btn_save_settings, "#0ea5e9", "#0284c7")

        # Database Cleanup Card
        cleanup_card = tk.LabelFrame(
            content_frame, 
            text="  Database Compacting & Cleanup Tools  ", 
            font=("Segoe UI", 11, "bold"),
            fg="#475569", 
            bg="#ffffff", 
            bd=1, 
            relief="solid", 
            padx=25, 
            pady=25
        )
        cleanup_card.pack(fill=tk.X, anchor="n", pady=(20, 0))
        
        lbl_cleanup_desc = tk.Label(
            cleanup_card,
            text="Maintenance tools to keep your local database lightweight and fast over years of operation.",
            font=("Segoe UI", 9, "italic"),
            fg="#64748b",
            bg="#ffffff"
        )
        lbl_cleanup_desc.pack(anchor="w", pady=(0, 15))
        
        # Grid/row frame for cleanup actions
        actions_frame = tk.Frame(cleanup_card, bg="#ffffff")
        actions_frame.pack(fill=tk.X)
        
        self.btn_vacuum = tk.Button(
            actions_frame,
            text="🧹 Compact Database (Vacuum)",
            font=("Segoe UI", 10, "bold"),
            bg="#0ea5e9", 
            fg="#ffffff",
            activebackground="#0284c7",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.vacuum_db,
            padx=15,
            pady=8
        )
        self.btn_vacuum.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.setup_hover_effect(self.btn_vacuum, "#0ea5e9", "#0284c7")
        
        self.btn_purge_90 = tk.Button(
            actions_frame,
            text="🗑️ Purge Logs > 90 Days",
            font=("Segoe UI", 10, "bold"),
            bg="#ef4444", 
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=lambda: self.purge_logs(90),
            padx=15,
            pady=8
        )
        self.btn_purge_90.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        self.setup_hover_effect(self.btn_purge_90, "#ef4444", "#b91c1c")
        
        self.btn_purge_180 = tk.Button(
            actions_frame,
            text="🗑️ Purge Logs > 6 Months",
            font=("Segoe UI", 10, "bold"),
            bg="#ef4444", 
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=lambda: self.purge_logs(180),
            padx=15,
            pady=8
        )
        self.btn_purge_180.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        self.setup_hover_effect(self.btn_purge_180, "#ef4444", "#b91c1c")

    def save_settings(self):
        """Saves Title & Description config variables to database, and updates header banner in real-time."""
        title = self.settings_title_var.get().strip()
        desc = self.settings_desc_var.get().strip()
        
        if not title:
            messagebox.showwarning("Input Warning", "System Title cannot be empty.")
            self.settings_title_entry.focus_set()
            return
            
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE config SET value = ? WHERE key = 'system_title'", (title,))
            cursor.execute("UPDATE config SET value = ? WHERE key = 'system_description'", (desc,))
            conn.commit()
            
            # Update local memory
            self.system_title = title
            self.system_description = desc
            
            # Update banner labels in real-time
            self.title_lbl.config(text=self.system_title)
            self.subtitle_lbl.config(text=self.system_description)
            
            self.status_lbl.config(text="System configurations saved and updated successfully.")
            messagebox.showinfo("Success", "System configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Save Error", f"Unable to save settings:\n{str(e)}")
        finally:
            conn.close()

    def vacuum_db(self):
        """Compacts the SQLite database file to reclaim unused space."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("VACUUM")
            conn.commit()
            messagebox.showinfo("Success", "Database compacted and optimized successfully!")
            self.status_lbl.config(text="Database vacuum completed.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to compact database:\n{str(e)}")
        finally:
            conn.close()
            
    def purge_logs(self, days):
        """Purges history logs older than the specified number of days."""
        confirm = messagebox.askyesno(
            "Purge Old Logs?",
            f"Are you sure you want to permanently delete all history logs older than {days} days?\n"
            "This action is irreversible.",
            parent=self.root
        )
        if not confirm:
            return
            
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ref_id, timestamp FROM history")
            rows = cursor.fetchall()
            
            to_delete = []
            for ref_id, timestamp_str in rows:
                parsed_dt = None
                for fmt in ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        parsed_dt = datetime.datetime.strptime(timestamp_str, fmt)
                        break
                    except ValueError:
                        continue
                if parsed_dt and parsed_dt < cutoff_date:
                    to_delete.append(ref_id)
            
            if to_delete:
                for ref_id in to_delete:
                    cursor.execute("DELETE FROM history WHERE ref_id = ?", (ref_id,))
                conn.commit()
                
                # Compact database after deletion
                cursor.execute("VACUUM")
                conn.commit()
                
                deleted_count = len(to_delete)
            else:
                deleted_count = 0
                
            # Refresh history list UI
            self.load_history_from_db()
            self.refresh_history_list()
            
            messagebox.showinfo("Success", f"Successfully deleted {deleted_count} logs older than {days} days.")
            self.status_lbl.config(text=f"Purged {deleted_count} logs older than {days} days.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to purge logs:\n{str(e)}")
        finally:
            conn.close()

    def create_footer_status(self):
        """Creates the bottom status bar with session information."""
        self.status_bar = tk.Frame(self.main_container, bg="#f1f5f9", height=28, bd=1, relief="solid")
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_bar.pack_propagate(False)
        
        self.status_lbl = tk.Label(
            self.status_bar, 
            text="Ready. System is operating fully offline.", 
            font=("Segoe UI", 8), 
            fg="#64748b", 
            bg="#f1f5f9", 
            padx=10
        )
        self.status_lbl.pack(side=tk.LEFT)
        
        time_lbl = tk.Label(
            self.status_bar, 
            text="Shortcuts: Ctrl+1/2/3/4 (Tabs) | Enter (Add) | Delete (Remove) | Ctrl+P (Print)", 
            font=("Segoe UI", 8), 
            fg="#94a3b8", 
            bg="#f1f5f9", 
            padx=10
        )
        time_lbl.pack(side=tk.RIGHT)
        
    def setup_hover_effect(self, widget, normal_color, hover_color):
        """Binds mouse enter/leave actions to custom widget background colors to simulate smooth modern UI feedback."""
        widget.bind("<Enter>", lambda event: widget.config(bg=hover_color) if str(widget['state']) != 'disabled' else None)
        widget.bind("<Leave>", lambda event: widget.config(bg=normal_color) if str(widget['state']) != 'disabled' else None)
        
    def handle_tree_deselect(self, event, tree):
        """Deselects all items in the tree if click falls on empty space."""
        item = tree.identify_row(event.y)
        if not item:
            tree.selection_remove(*tree.selection())
        
    def save_active_session(self):
        """Persists the current active dispatch session items to the database."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            items_json = json.dumps(self.dispatch_items)
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('active_dispatch_batch', ?)", (items_json,))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def check_and_restore_session(self):
        """Checks if there is a persistent active session in the database and prompts to restore it."""
        conn = sqlite3.connect(self.db_path)
        saved_items = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = 'active_dispatch_batch'")
            row = cursor.fetchone()
            if row and row[0]:
                saved_items = json.loads(row[0])
        except Exception:
            pass
        finally:
            conn.close()
            
        if saved_items:
            # Prompt to restore recent session
            restore = messagebox.askyesno(
                "Restore Recent Session",
                f"We found an unsaved stock-out batch from your previous session with {len(saved_items)} item(s).\n"
                "Would you like to restore it?",
                parent=self.root
            )
            if restore:
                self.dispatch_items = saved_items
                self.refresh_dispatch_tree()
                self.status_lbl.config(text=f"Restored {len(self.dispatch_items)} items from previous session.")
            else:
                # User declined, clear it from database
                self.dispatch_items = []
                self.refresh_dispatch_tree()
                self.save_active_session()
            
            # Explicitly force focus back to item entry to make sure all entry inputs are focusable/interactive
            self.item_name_entry.focus_set()

    # ========================================================
    # SQLite DATABASE PERSISTENCE LAYER
    # ========================================================
    def init_db(self):
        """Creates relational schema for products, print transactions, and config settings if not exists."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Products table (Unique product names, no stock/counts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)
            
            # History log table (Reference IDs, timestamps, quantities, and receipt details)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    ref_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    total_qty INTEGER NOT NULL,
                    receipt_text TEXT NOT NULL,
                    items_json TEXT NOT NULL
                )
            """)
            
            # Config table (Key-Value settings)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('system_title', 'BODEGA STOCK-OUT SYSTEM')")
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('system_description', 'Offline Session Dispatch & Paper Receipt Formatter')")
            
            conn.commit()
        finally:
            conn.close()

    def load_settings(self):
        """Loads system configuration settings from SQLite config table."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM config")
            rows = cursor.fetchall()
            settings = dict(rows)
            self.system_title = settings.get("system_title", "BODEGA STOCK-OUT SYSTEM")
            self.system_description = settings.get("system_description", "Offline Session Dispatch & Paper Receipt Formatter")
        except Exception:
            self.system_title = "BODEGA STOCK-OUT SYSTEM"
            self.system_description = "Offline Session Dispatch & Paper Receipt Formatter"
        finally:
            conn.close()

    def load_data(self):
        """Initializes SQLite databases, runs file wipe routines, and populates lists."""
        self.init_db()
        self.load_settings()
        
        # Wipes old JSON file references completely to fulfill "remove all the data"
        for old_file in [self.products_file, self.history_file]:
            if os.path.exists(old_file):
                try:
                    os.remove(old_file)
                except Exception:
                    pass
                    
        self.load_products_from_db()
        self.load_history_from_db()

    def load_products_from_db(self):
        """Retrieves and populates catalog list sorted alphabetically directly from SQLite."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM products")
            self.products = sorted([row[0] for row in cursor.fetchall()], key=lambda x: x.lower())
        finally:
            conn.close()

    def load_history_from_db(self):
        """Retrieves history logs ordered by chronological timestamp directly from SQLite."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ref_id, timestamp, total_qty, receipt_text, items_json FROM history ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            self.history = []
            for row in rows:
                self.history.append({
                    "ref_id": row[0],
                    "timestamp": row[1],
                    "total_qty": row[2],
                    "receipt_text": row[3],
                    "items": json.loads(row[4])
                })
        finally:
            conn.close()

    def save_products(self):
        """Synchronizes and reloads SQLite database products list."""
        self.load_products_from_db()

    def save_history(self):
        """Synchronizes and reloads SQLite database history log list."""
        self.load_history_from_db()

    # ========================================================
    # INTER-TAB DATA SYNCHRONIZATION HELPERS
    # ========================================================
    def refresh_quick_products(self):
        """Refreshes the sidebar product quick adder treeview."""
        self.filter_quick_products()

    def filter_quick_products(self, *args):
        """Filters the quick-adder catalog sidebar in Dispatch view."""
        search_term = self.quick_search_var.get().lower()
        search_words = search_term.split()
        self.quick_tree.delete(*self.quick_tree.get_children())
        
        if search_words:
            matches = [prod for prod in self.products if all(word in prod.lower() for word in search_words)]
        else:
            matches = list(self.products)
        
        idx = 0
        for prod in matches:
            tag = "even" if idx % 2 == 0 else "odd"
            self.quick_tree.insert("", tk.END, values=(prod,), tags=(tag,))
            idx += 1

    def refresh_inventory_list(self):
        """Refreshes the catalog master manager treeview list."""
        self.filter_inventory_list()

    def filter_inventory_list(self, *args):
        """Filters the master catalog manager treeview list."""
        search_term = self.inv_search_var.get().lower()
        search_words = search_term.split()
        self.inv_tree.delete(*self.inv_tree.get_children())
        
        if search_words:
            matches = [prod for prod in self.products if all(word in prod.lower() for word in search_words)]
        else:
            matches = list(self.products)
            
        total_matches = len(matches)
        
        idx = 0
        for prod in matches:
            tag = "even" if idx % 2 == 0 else "odd"
            self.inv_tree.insert("", tk.END, values=(prod,), tags=(tag,))
            idx += 1
            
        if search_term:
            self.catalog_count_var.set(f"Found {total_matches} (Showing {idx})")
        else:
            self.catalog_count_var.set(f"{len(self.products)} products")

    def parse_search_date(self, search_str):
        """Parses standard inputs for custom date matching (e.g. january 7, jan 7)."""
        import re
        cleaned = re.sub(r'[,]', ' ', search_str.lower())
        tokens = [t.strip() for t in cleaned.split() if t.strip()]
        if not tokens:
            return None
            
        months_map = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12
        }
        
        matched_months = []
        day = None
        year = None
        
        for tok in tokens:
            if tok.isdigit():
                val = int(tok)
                if len(tok) == 4 or val > 31:
                    year = val
                else:
                    if day is None:
                        day = val
                    elif year is None:
                        year = val
            else:
                curr_matches = []
                for m_name, m_num in months_map.items():
                    if m_name.startswith(tok):
                        if m_num not in curr_matches:
                            curr_matches.append(m_num)
                if curr_matches:
                    matched_months.extend(curr_matches)
                    
        matched_months = list(set(matched_months))
        return {
            "months": matched_months,
            "day": day,
            "year": year,
            "tokens_count": len(tokens)
        }

    def filter_history_list_by_search_or_time(self, *args):
        """Filters the history logs list by search term and selected timeframe."""
        self.hist_tree.delete(*self.hist_tree.get_children())
        
        search_term = self.hist_search_var.get().strip().lower()
        filter_type = self.hist_filter_var.get()
        
        now = datetime.datetime.now()
        
        # Parse search term
        parsed = None
        if search_term:
            parsed = self.parse_search_date(search_term)
            
        filtered_records = []
        for record in self.history:
            # Parse record timestamp (Format: YYYY-MM-DD HH:MM:SS)
            rec_time = None
            try:
                rec_time = datetime.datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
                
            # Time filter logic
            if filter_type == "Yesterday":
                if not rec_time:
                    continue
                yesterday = now - datetime.timedelta(days=1)
                if rec_time.date() != yesterday.date():
                    continue
            elif filter_type == "Last 7 Days":
                if not rec_time:
                    continue
                limit = now - datetime.timedelta(days=7)
                if rec_time < limit:
                    continue
            
            # Date search filter logic
            if search_term:
                matched = False
                if parsed:
                    match_ok = True
                    if rec_time:
                        if parsed["months"] and rec_time.month not in parsed["months"]:
                            match_ok = False
                        if parsed["day"] is not None and rec_time.day != parsed["day"]:
                            match_ok = False
                        if parsed["year"] is not None and rec_time.year != parsed["year"]:
                            match_ok = False
                        # Fallback if no months/day/year could be parsed (e.g. partial year search)
                        if not parsed["months"] and parsed["day"] is None and parsed["year"] is None:
                            match_ok = search_term in record["timestamp"].lower()
                    else:
                        match_ok = search_term in record["timestamp"].lower()
                    matched = match_ok
                else:
                    matched = search_term in record["timestamp"].lower()
                    
                if not matched:
                    continue
                    
            filtered_records.append(record)
            
        # Post-filter: If user didn't specify a year, restrict to the latest year found in matches
        if search_term and parsed and parsed["year"] is None and filtered_records:
            years = []
            for record in filtered_records:
                try:
                    rt = datetime.datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
                    years.append(rt.year)
                except Exception:
                    pass
            if years:
                latest_year = max(years)
                final_records = []
                for record in filtered_records:
                    try:
                        rt = datetime.datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
                        if rt.year == latest_year:
                            final_records.append(record)
                    except Exception:
                        final_records.append(record)
                filtered_records = final_records
            
        for idx, record in enumerate(filtered_records):
            tag = "even" if idx % 2 == 0 else "odd"
            self.hist_tree.insert(
                "", 
                tk.END, 
                values=(record["timestamp"], record["ref_id"], record["total_qty"]),
                tags=(tag,)
            )
            
        self.clear_history_viewer()

    def refresh_history_list(self):
        """Populates the history logs list in reverse chronological order respecting current filters."""
        self.filter_history_list_by_search_or_time()

    def clear_history_viewer(self):
        """Resets the A4 viewer layout content and locks history commands."""
        self.hist_text.config(state=tk.NORMAL)
        self.hist_text.delete("1.0", tk.END)
        self.hist_text.insert(tk.END, "Select a stock-out record from the left list to view printed dispatch report.")
        self.hist_text.config(state=tk.DISABLED)
        self.btn_reprint.config(state=tk.DISABLED, bg="#94a3b8")
        self.btn_del_hist.config(state=tk.DISABLED, fg="#94a3b8")

    # ========================================================
    # KEYBOARD & SHORTCUT ROUTING LAYER
    # ========================================================
    def handle_delete_shortcut(self, event):
        """Routes the standard keyboard 'Delete' button depending on active tab."""
        if self.active_tab == "dispatch":
            self.delete_selected_item()
        elif self.active_tab == "inventory":
            self.delete_inventory_product()
        elif self.active_tab == "history":
            self.delete_history_record()

    # ========================================================
    # TAB 1: STOCK-OUT DISPATCH INTERACTIVE BUSINESS LOGIC
    # ========================================================
    def quick_select_click(self):
        """Fills item name from catalog selection and moves focus to quantity field."""
        selected = self.quick_tree.selection()
        if not selected:
            self.item_name_entry.config(state=tk.NORMAL)
            self.item_name_var.set("")
            self.qty_var.set("")
            self.status_lbl.config(text="Ready. Operating fully offline.")
            return
        prod_name = self.quick_tree.item(selected[0], 'values')[0]
        self.item_name_entry.config(state=tk.NORMAL)
        self.item_name_var.set(prod_name)
        self.status_lbl.config(text=f"Selected: '{prod_name}' — enter quantity and press Enter to add.")
        self.qty_var.set("")
        self.qty_entry.focus_set()

    def quick_add_double_click(self):
        """Double-click fills item name from catalog — user must enter qty then press Enter."""
        selected = self.quick_tree.selection()
        if not selected:
            return
        prod_name = self.quick_tree.item(selected[0], 'values')[0]
        self.item_name_entry.config(state=tk.NORMAL)
        self.item_name_var.set(prod_name)
        self.status_lbl.config(text=f"Selected: '{prod_name}' — enter quantity and press Enter to add.")
        self.qty_var.set("")
        self.qty_entry.focus_set()

    def update_item_count(self):
        """Updates the total items count badge using complete in-memory dispatch_items."""
        total_items = len(self.dispatch_items)
        total_qty = sum(item["qty"] for item in self.dispatch_items)
            
        if total_items == 1:
            self.count_var.set(f"1 item (Total Qty: {total_qty})")
        else:
            self.count_var.set(f"{total_items} items (Total Qty: {total_qty})")

    def refresh_dispatch_tree(self):
        """Sorts dispatch_items alphabetically and filters them based on the search query."""
        self.dispatch_items.sort(key=lambda x: x["desc"].lower())
        self.tree.delete(*self.tree.get_children())
        
        search_query = self.batch_search_var.get().strip().lower()
        idx = 0
        for item in self.dispatch_items:
            if not search_query or search_query in item["desc"].lower():
                tag = "even" if idx % 2 == 0 else "odd"
                self.tree.insert("", tk.END, values=(item["desc"], item["qty"]), tags=(tag,))
                idx += 1
                
        self.update_item_count()
        self.save_active_session()
            
    def add_item(self):
        """Performs validation and adds a new item to the active session list."""
        desc = self.item_name_var.get().strip()
        qty_str = self.qty_var.get().strip()
        
        # 1. Validation check - empty description
        if not desc:
            messagebox.showwarning(
                "Input Warning", 
                "Item Name/Description cannot be blank.\nPlease enter a valid item description."
            )
            # Unlock field so user can type manually
            self.item_name_entry.config(state=tk.NORMAL)
            self.item_name_entry.focus_set()
            return
            
        # 2. Validation check - empty quantity
        if not qty_str:
            messagebox.showwarning(
                "Input Warning", 
                "Quantity cannot be blank.\nPlease enter a positive numeric value."
            )
            self.qty_entry.focus_set()
            return
            
        # 3. Validation check - numeric integer quantity
        try:
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Input Warning", 
                "Quantity must be a positive whole number greater than zero."
            )
            self.qty_entry.focus_set()
            return
            
        # Check duplicate item in the memory list (case-insensitive)
        for item in self.dispatch_items:
            if item["desc"].lower() == desc.lower():
                messagebox.showwarning(
                    "Duplicate Item",
                    f"'{desc}' has already been added to the current batch."
                )
                self.item_name_entry.config(state=tk.NORMAL)
                self.item_name_var.set("")
                self.qty_var.set("")
                for sel in self.quick_tree.selection():
                    self.quick_tree.selection_remove(sel)
                self.item_name_entry.focus_set()
                return
                
        # Add to memory list
        self.dispatch_items.append({"desc": desc, "qty": qty})
        
        # Refresh tree view (which sorts & filters it)
        self.refresh_dispatch_tree()
        
        # Update status and reset inputs
        self.status_lbl.config(text=f"Added: '{desc}' x {qty} to current batch.")
        
        # Reset input fields — unlock name entry and clear catalog selection
        self.item_name_entry.config(state=tk.NORMAL)
        self.item_name_var.set("")
        self.qty_var.set("")
        # Deselect catalog sidebar so next click registers fresh
        for sel in self.quick_tree.selection():
            self.quick_tree.selection_remove(sel)
        self.item_name_entry.focus_set()
        
    def delete_selected_item(self):
        """Removes the currently highlighted row from the Treeview and memory list."""
        selected_item = self.tree.selection()
        if not selected_item:
            self.status_lbl.config(text="No item selected to remove.")
            return
            
        values = self.tree.item(selected_item[0], 'values')
        desc = values[0]
        
        # Remove from memory list
        self.dispatch_items = [item for item in self.dispatch_items if item["desc"].lower() != desc.lower()]
        
        # Refresh tree
        self.refresh_dispatch_tree()
        
        self.status_lbl.config(text=f"Removed: '{desc}' from session batch.")
        self.item_name_entry.focus_set()

    def on_tree_double_click(self, event):
        """Double-click on dispatch table triggers inline quantity editing dialog."""
        # Find item under the mouse click
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        # Select the item
        self.tree.selection_set(item_id)
        
        # Get current values
        values = self.tree.item(item_id, 'values')
        if not values:
            return
            
        desc, qty = values[0], values[1]
        
        from tkinter import simpledialog
        new_qty_str = simpledialog.askstring(
            "Edit Quantity",
            f"Enter new quantity for '{desc}':",
            parent=self.root,
            initialvalue=str(qty)
        )
        
        if new_qty_str is None:
            return
            
        try:
            new_qty = int(new_qty_str.strip())
            if new_qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Input Warning",
                "Quantity must be a positive whole number greater than zero."
            )
            return
            
        for item in self.dispatch_items:
            if item["desc"].lower() == desc.lower():
                item["qty"] = new_qty
                break
                
        self.refresh_dispatch_tree()
        self.status_lbl.config(text=f"Updated: '{desc}' quantity changed to {new_qty}.")

    def on_tree_increment(self, event):
        """Key '+' or '=' increments selected dispatch item qty by 1."""
        selected = self.tree.selection()
        if not selected:
            return
        self.adjust_tree_item_qty(selected[0], 1)

    def on_tree_decrement(self, event):
        """Key '-' decrements selected dispatch item qty by 1."""
        selected = self.tree.selection()
        if not selected:
            return
        self.adjust_tree_item_qty(selected[0], -1)

    def adjust_tree_item_qty(self, item_id, delta):
        """Increments or decrements item quantity, removing item if qty reaches 0."""
        values = self.tree.item(item_id, 'values')
        if not values:
            return
        desc, qty = values[0], int(values[1])
        new_qty = qty + delta
        if new_qty <= 0:
            self.dispatch_items = [item for item in self.dispatch_items if item["desc"].lower() != desc.lower()]
            self.refresh_dispatch_tree()
            self.status_lbl.config(text=f"Removed: '{desc}' (quantity reached 0).")
        else:
            for item in self.dispatch_items:
                if item["desc"].lower() == desc.lower():
                    item["qty"] = new_qty
                    break
            self.refresh_dispatch_tree()
            self.status_lbl.config(text=f"Updated: '{desc}' quantity to {new_qty}.")
        
    def on_inv_tree_right_click(self, event):
        """Triggers product name editing on right-click."""
        # Find item under the mouse click
        item_id = self.inv_tree.identify_row(event.y)
        if not item_id:
            return
            
        # Select the item
        self.inv_tree.selection_set(item_id)
        
        # Get current values
        values = self.inv_tree.item(item_id, 'values')
        if not values:
            return
            
        old_name = values[0]
        
        from tkinter import simpledialog
        new_name = simpledialog.askstring(
            "Edit Product Name",
            f"Enter new name for product '{old_name}':",
            parent=self.root,
            initialvalue=old_name
        )
        
        if new_name is None:
            return
            
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning(
                "Input Warning",
                "Product name cannot be blank."
            )
            return
            
        # Check if the name changed
        if new_name == old_name:
            return
            
        # Check duplicate case-insensitive in memory list first (excluding the current one)
        matches = [p for p in self.products if p.lower() == new_name.lower() and p.lower() != old_name.lower()]
        if matches:
            messagebox.showwarning(
                "Catalog Conflict", 
                f"Product '{new_name}' already exists in the catalog database!"
            )
            return
            
        # Update database
        conn = sqlite3.connect(self.db_path)
        success = True
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE products SET name = ? WHERE name = ?", (new_name, old_name))
            conn.commit()
        except sqlite3.IntegrityError:
            success = False
        finally:
            conn.close()
            
        if not success:
            messagebox.showwarning("Catalog Conflict", f"Product '{new_name}' already exists!")
            return
            
        # Reload products and refresh UI
        self.load_products_from_db()
        self.refresh_inventory_list()
        self.refresh_quick_products()
        self.status_lbl.config(text=f"Renamed: '{old_name}' to '{new_name}'.")
        
    def populate_test_items(self, count):
        """Helper to quickly add mock items to active dispatch batch for printing/layout testing."""
        self.dispatch_items = []
        # Try to use names from catalog, fallback to 'Mock Product X'
        for i in range(1, count + 1):
            if i - 1 < len(self.products):
                name = self.products[i - 1]
            else:
                name = f"Mock Product {i}"
            qty = (i % 5) + 1
            self.dispatch_items.append({"desc": name, "qty": qty})
        self.refresh_dispatch_tree()
        self.status_lbl.config(text=f"Loaded {count} mock test items for print testing.")
        
    def append_test_items(self, count):
        """Appends count mock items to the active dispatch list without clearing existing ones."""
        start_id = len(self.dispatch_items) + 1
        for i in range(start_id, start_id + count):
            if i - 1 < len(self.products):
                name = self.products[i - 1]
            else:
                name = f"Mock Product {i}"
            qty = (i % 5) + 1
            
            # Check duplicate to avoid warning popup
            duplicate = False
            for item in self.dispatch_items:
                if item["desc"].lower() == name.lower():
                    duplicate = True
                    break
            if not duplicate:
                self.dispatch_items.append({"desc": name, "qty": qty})
                
        self.refresh_dispatch_tree()
        self.status_lbl.config(text=f"Appended {count} mock test items to current batch.")
        
    def clear_list(self):
        """Wipes the active session lists after user confirms."""
        if not self.dispatch_items:
            self.status_lbl.config(text="Session list is already empty.")
            return
            
        confirm = messagebox.askyesno(
            "Clear Current Batch", 
            "Are you sure you want to clear the entire list of items?\nThis action cannot be undone."
        )
        if confirm:
            self.dispatch_items = []
            self.refresh_dispatch_tree()
            self.status_lbl.config(text="Current batch wiped clean.")
            self.item_name_entry.focus_set()
            
    def format_header_date(self, date_val):
        if isinstance(date_val, datetime.datetime):
            return f"{date_val.strftime('%b')}. {date_val.day} {date_val.year}"
        if isinstance(date_val, str):
            for fmt in ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.datetime.strptime(date_val, fmt)
                    return f"{dt.strftime('%b')}. {dt.day} {dt.year}"
                except ValueError:
                    continue
        return date_val

    def format_receipt_text(self, date_str, items_data, total_qty, ref_id, paper_size="Long",
                            header_title=None, show_date=True, show_ref_id=True, font_size=10):
        """
        Formats the current list into the simplified LIFECHECK PHARMA layout with paging.
        """
        def wrap_text(text, width):
            if not text:
                return [""]
            words = text.split()
            lines = []
            current_line = []
            current_length = 0
            for word in words:
                if len(word) > width:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = []
                        current_length = 0
                    for i in range(0, len(word), width):
                        lines.append(word[i:i+width])
                    continue
                if current_length + len(word) + (1 if current_line else 0) <= width:
                    current_line.append(word)
                    current_length += len(word) + (1 if current_line else 0)
                else:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)
            if current_line:
                lines.append(" ".join(current_line))
            return lines if lines else [""]

        # Dynamic lines capacity based on selected font size and Long paper height (936 pt)
        line_height_points = font_size * 1.35
        header_overhead_lines = 10  # 2 spaces at top, Title, Date, Ref ID, spaces, and table headers
        
        # Non-last page capacity: safe zone is very small (only needs to clear page number at bottom)
        # We reserve margins (30 pt) and small footer zone (1.5 lines of text)
        normal_lines_capacity = int((936.0 - (line_height_points * 1.5 + 30.0)) / line_height_points) - header_overhead_lines
        
        # Last page capacity: safe zone is larger (needs to reserve space for the signature block)
        # We reserve margins (60 pt) and signatures zone (6 lines of signature + space = ~80 pt)
        last_lines_capacity = int((936.0 - (line_height_points * 6.5 + 90.0)) / line_height_points) - header_overhead_lines
        
        # Paginate items dynamically based on wrapped sub-rows count
        pages_data = []
        current_items = list(items_data)
        
        while current_items:
            # Check if all remaining items fit on the last page
            mid_last = math.ceil(len(current_items) / 2)
            left_last = current_items[:mid_last]
            right_last = current_items[mid_last:]
            rows_last = 0
            if left_last or right_last:
                left_rows = sum(len(wrap_text(item[0], 35)) for item in left_last)
                right_rows = sum(len(wrap_text(item[0], 35)) for item in right_last)
                rows_last = max(left_rows, right_rows)
                
            if rows_last <= last_lines_capacity:
                pages_data.append((current_items, True))
                current_items = []
            else:
                # Find the maximum items we can fit on this normal page
                fit_count = 0
                for count in range(1, len(current_items) + 1):
                    test_items = current_items[:count]
                    mid_test = math.ceil(count / 2)
                    left_test = test_items[:mid_test]
                    right_test = test_items[mid_test:]
                    left_rows = sum(len(wrap_text(item[0], 35)) for item in left_test)
                    right_rows = sum(len(wrap_text(item[0], 35)) for item in right_test)
                    test_rows = max(left_rows, right_rows)
                    if test_rows <= normal_lines_capacity:
                        fit_count = count
                    else:
                        break
                        
                if fit_count == 0:
                    fit_count = 1  # Always take at least one item
                    
                pages_data.append((current_items[:fit_count], False))
                current_items = current_items[fit_count:]
                
        if not pages_data:
            pages_data = [([], True)]
            
        total_pages = len(pages_data)
        title_text = header_title if header_title is not None else self.system_title
        pages_list = []
        
        for p, (page_items, is_last_page) in enumerate(pages_data):
            page_num = p + 1
            
            # Divide items into left and right columns
            mid = math.ceil(len(page_items) / 2)
            left_col = page_items[:mid]
            right_col = page_items[mid:]
            
            lines = []
            lines.append("")
            lines.append("")
            lines.append(title_text.center(96))
            if show_date:
                formatted_date = self.format_header_date(date_str)
                lines.append(f"Date: {formatted_date}".center(96))
            if show_ref_id:
                lines.append(f"Ref ID: {ref_id}".center(96))
            lines.append("")
            
            # Excel style grid table headers (QTY first, then ITEM) - 2 columns side-by-side with solid Unicode lines
            # Each table: 45 chars, Gap: 6 chars. Total width = 45 + 6 + 45 = 96 characters
            lines.append("┌─────┬─────────────────────────────────────┐      ┌─────┬─────────────────────────────────────┐")
            lines.append("│ QTY │" + "ITEM".center(37) + "│      │ QTY │" + "ITEM".center(37) + "│")
            lines.append("├─────┼─────────────────────────────────────┤      ├─────┼─────────────────────────────────────┤")
            
            max_rows = max(len(left_col), len(right_col))
            for i in range(max_rows):
                l_desc, l_qty = left_col[i] if i < len(left_col) else ("", None)
                r_desc, r_qty = right_col[i] if i < len(right_col) else ("", None)
                
                l_wrapped = wrap_text(l_desc, 35) if l_qty is not None else []
                r_wrapped = wrap_text(r_desc, 35) if r_qty is not None else []
                
                sub_rows = max(len(l_wrapped), len(r_wrapped))
                for s in range(sub_rows):
                    # Left cell line
                    if l_qty is not None:
                        l_line = l_wrapped[s] if s < len(l_wrapped) else ""
                        l_qty_str = f" {l_qty:<3} " if s == 0 else "     "
                        l_desc_str = f" {l_line:<35} "
                        left_cell = f"│{l_qty_str}│{l_desc_str}│"
                    else:
                        left_cell = "                                             "
                        
                    # Right cell line
                    if r_qty is not None:
                        r_line = r_wrapped[s] if s < len(r_wrapped) else ""
                        r_qty_str = f" {r_qty:<3} " if s == 0 else "     "
                        r_desc_str = f" {r_line:<35} "
                        right_cell = f"│{r_qty_str}│{r_desc_str}│"
                    else:
                        right_cell = "                                             "
                        
                    lines.append(f"{left_cell}      {right_cell}")
                
            lines.append("└─────┴─────────────────────────────────────┘      └─────┴─────────────────────────────────────┘")
            
            # Pad with empty lines to push the signatures and page number to the bottom
            num_content_lines = len(lines)
            footer_lines_count = 6 if is_last_page else 2
            
            # Total page lines possible (dynamic)
            page_total_lines = (last_lines_capacity if is_last_page else normal_lines_capacity) + header_overhead_lines
            
            padding_needed = page_total_lines - num_content_lines - footer_lines_count
            for _ in range(max(0, padding_needed)):
                lines.append("")
                
            if is_last_page:
                lines.append("Received by: ____________________   Checked by: ____________________".center(96))
                lines.append("")
                
            lines.append(f"Page {page_num} of {total_pages}".center(96))
            lines.append("")
            # Metadata marker at end - stripped by PS before printing, used only for page count
            lines.append(f"[PAGE:{page_num}OF:{total_pages}]")
            
            pages_list.append("\n".join(lines))
            
        return "\f".join(pages_list)
        
    def get_system_printers(self):
        """Fetches list of system printers and identifies the default printer."""
        printers = []
        default_printer = ""
        if sys.platform == "win32":
            try:
                import winreg
                # 1. Get all installed printers
                devices_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Devices")
                num_devices = winreg.QueryInfoKey(devices_key)[1]
                for i in range(num_devices):
                    name, value, type = winreg.EnumValue(devices_key, i)
                    printers.append(name)
                winreg.CloseKey(devices_key)
                
                # 2. Get default printer
                try:
                    windows_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Windows")
                    device_val, _ = winreg.QueryValueEx(windows_key, "Device")
                    winreg.CloseKey(windows_key)
                    if device_val:
                        default_printer = device_val.split(',')[0].strip()
                except Exception:
                    pass
            except Exception:
                try:
                    cmd = ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"]
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    printers = [p.strip() for p in res.stdout.split('\n') if p.strip()]
                    
                    cmd_def = ["powershell", "-Command", "(Get-CimInstance Win32_Printer | Where-Object {$_.Default}).Name"]
                    res_def = subprocess.run(cmd_def, capture_output=True, text=True)
                    default_printer = res_def.stdout.strip()
                except Exception:
                    try:
                        res = subprocess.run(["wmic", "printer", "get", "name"], capture_output=True, text=True)
                        lines = res.stdout.split('\n')
                        printers = [l.strip() for l in lines[1:] if l.strip() and not l.strip().startswith("Name")]
                    except Exception:
                        pass
        else:
            try:
                res = subprocess.run(["lpstat", "-a"], capture_output=True, text=True)
                for line in res.stdout.split('\n'):
                    if line.strip():
                        parts = line.split()
                        if parts:
                            printers.append(parts[0])
                res_def = subprocess.run(["lpstat", "-d"], capture_output=True, text=True)
                if "destination:" in res_def.stdout:
                    default_printer = res_def.stdout.split("destination:")[-1].strip()
            except Exception:
                pass
                
        unique_printers = []
        for p in printers:
            if p not in unique_printers:
                unique_printers.append(p)
                
        return unique_printers, default_printer

    def show_print_preview_dialog(self, filepath, date_str, items_data, total_qty, ref_id, on_success_callback):
        """Displays a print preview dialog where the user reviews the text, selects a printer, and selects paper size."""
        preview_win = tk.Toplevel(self.root)
        preview_win.title("Print Review & Printer Selection")
        preview_win.geometry("780x780")  # Wider to accommodate 2-column side-by-side grid layout
        preview_win.transient(self.root)
        preview_win.grab_set()
        
        # Define dropdown variables first so they can be referenced by the preview generator
        paper_var = tk.StringVar(value="8.5'' x 13'' (Long)")
        font_size_var = tk.StringVar(value="10")
        
        # Center dialog
        preview_win.update_idletasks()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        w = preview_win.winfo_width()
        h = preview_win.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        preview_win.geometry(f"+{x}+{y}")
        
        preview_win.configure(bg="#f8fafc")
        
        title_lbl = tk.Label(
            preview_win,
            text="Review Report Details",
            font=("Segoe UI", 12, "bold"),
            bg="#f8fafc",
            fg="#1e293b",
            pady=10
        )
        title_lbl.pack(fill=tk.X)
        
        # ── Header Options Panel ──────────────────────────────────────────────
        hdr_panel = tk.Frame(preview_win, bg="#e0f2fe", bd=1, relief="solid", padx=12, pady=8)
        hdr_panel.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        hdr_section_lbl = tk.Label(
            hdr_panel,
            text="Header Options",
            font=("Segoe UI", 8, "bold"),
            bg="#e0f2fe",
            fg="#0369a1"
        )
        hdr_section_lbl.pack(anchor="w")
        
        # Title entry row
        title_row = tk.Frame(hdr_panel, bg="#e0f2fe")
        title_row.pack(fill=tk.X, pady=(4, 0))
        
        tk.Label(
            title_row,
            text="Title:",
            font=("Segoe UI", 9, "bold"),
            bg="#e0f2fe",
            fg="#0c4a6e",
            width=7,
            anchor="w"
        ).pack(side=tk.LEFT)
        
        header_title_var = tk.StringVar(value=self.system_title)
        title_entry = tk.Entry(
            title_row,
            textvariable=header_title_var,
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#0f172a",
            relief="solid",
            bd=1
        )
        title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Toggles row
        toggle_row = tk.Frame(hdr_panel, bg="#e0f2fe")
        toggle_row.pack(fill=tk.X, pady=(6, 0))
        
        show_date_var = tk.BooleanVar(value=True)
        show_refid_var = tk.BooleanVar(value=True)
        
        date_chk = tk.Checkbutton(
            toggle_row,
            text="Show Date",
            variable=show_date_var,
            font=("Segoe UI", 9),
            bg="#e0f2fe",
            fg="#0c4a6e",
            activebackground="#e0f2fe",
            selectcolor="#ffffff",
            cursor="hand2"
        )
        date_chk.pack(side=tk.LEFT, padx=(0, 16))
        
        refid_chk = tk.Checkbutton(
            toggle_row,
            text="Show Ref ID",
            variable=show_refid_var,
            font=("Segoe UI", 9),
            bg="#e0f2fe",
            fg="#0c4a6e",
            activebackground="#e0f2fe",
            selectcolor="#ffffff",
            cursor="hand2"
        )
        refid_chk.pack(side=tk.LEFT)
        # ─────────────────────────────────────────────────────────────────────
        
        # Create control panel frame first at the bottom so it allocates its height first
        ctrl_frame = tk.Frame(preview_win, bg="#ffffff", bd=1, relief="solid", padx=15, pady=15)
        ctrl_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Create text preview frame that occupies the remaining space in the middle
        text_frame = tk.Frame(preview_win, bg="#cbd5e1", bd=1, relief="solid")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        txt_box = scrolledtext.ScrolledText(
            text_frame,
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#38bdf8",
            wrap=tk.WORD,
            bd=0,
            padx=12,
            pady=12
        )
        txt_box.pack(fill=tk.BOTH, expand=True)
        # Helper to strip metadata lines for cleaner preview
        def get_display_content(text):
            pages = text.split("\x0c")
            clean_pages = []
            for p in pages:
                lines = p.split("\n")
                clean_lines = [l for l in lines if not (l.startswith("[PAGE:") and l.endswith("]"))]
                clean_pages.append("\n".join(clean_lines))
            return "\n\n--- PAGE BREAK ---\n\n".join(clean_pages)

        # Default load is 8.5'' x 13'' (Long) receipt format
        try:
            default_font_size = int(font_size_var.get())
        except ValueError:
            default_font_size = 10
        receipt_content = self.format_receipt_text(
            date_str, items_data, total_qty, ref_id, "Long",
            header_title=header_title_var.get(),
            show_date=show_date_var.get(),
            show_ref_id=show_refid_var.get(),
            font_size=default_font_size
        )
        txt_box.insert(tk.END, get_display_content(receipt_content))
        txt_box.config(state=tk.DISABLED)
        
        # Options Row: Paper Size (left) + Font Size (right)
        options_row = tk.Frame(ctrl_frame, bg="#ffffff")
        options_row.pack(fill=tk.X, pady=(0, 12))
        
        # -- Paper Size Column --
        paper_col = tk.Frame(options_row, bg="#ffffff")
        paper_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        
        paper_lbl = tk.Label(
            paper_col,
            text="Paper Size:",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#475569"
        )
        paper_lbl.pack(anchor="w", pady=(0, 2))
        
        paper_cb = ttk.Combobox(
            paper_col,
            textvariable=paper_var,
            values=["8.5'' x 13'' (Long)"],
            state="readonly",
            font=("Segoe UI", 10)
        )
        paper_cb.pack(fill=tk.X)
        
        # -- Font Size Column --
        font_col = tk.Frame(options_row, bg="#ffffff")
        font_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        
        font_lbl = tk.Label(
            font_col,
            text="Font Size (Print):",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#475569"
        )
        font_lbl.pack(anchor="w", pady=(0, 2))
        
        font_size_cb = ttk.Combobox(
            font_col,
            textvariable=font_size_var,
            values=["7", "8", "9", "10", "11", "12", "14", "16", "18", "20"],
            state="readonly",
            font=("Segoe UI", 10)
        )
        font_size_cb.pack(fill=tk.X)
        
        def refresh_preview(*args):
            """Regenerate the preview whenever any header option or paper size changes."""
            selected_size = "Long"
            try:
                current_font_size = int(font_size_var.get())
            except ValueError:
                current_font_size = 10
            new_content = self.format_receipt_text(
                date_str=date_str,
                items_data=items_data,
                total_qty=total_qty,
                ref_id=ref_id,
                paper_size=selected_size,
                header_title=header_title_var.get(),
                show_date=show_date_var.get(),
                show_ref_id=show_refid_var.get(),
                font_size=current_font_size
            )
            txt_box.config(state=tk.NORMAL)
            txt_box.delete("1.0", tk.END)
            txt_box.insert(tk.END, get_display_content(new_content))
            txt_box.config(state=tk.DISABLED)
            
            # Save updated content to file
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
            except Exception:
                pass
                
            # Update DB history record
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE history SET receipt_text = ? WHERE ref_id = ?",
                    (new_content, ref_id)
                )
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()
                
            if self.active_tab == "history":
                self.load_history_from_db()

        # Wire all header controls to live-refresh the preview
        paper_cb.bind("<<ComboboxSelected>>", refresh_preview)
        font_size_cb.bind("<<ComboboxSelected>>", refresh_preview)
        show_date_var.trace_add("write", refresh_preview)
        show_refid_var.trace_add("write", refresh_preview)
        title_entry.bind("<KeyRelease>", refresh_preview)
        
        printer_lbl = tk.Label(
            ctrl_frame,
            text="Select Printer (Loading...):",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#475569"
        )
        printer_lbl.pack(anchor="w", pady=(0, 5))
        
        printer_var = tk.StringVar()
        printer_var.set("Loading system printers...")
        
        printer_cb = ttk.Combobox(
            ctrl_frame,
            textvariable=printer_var,
            values=["Loading system printers..."],
            state="disabled",
            font=("Segoe UI", 10)
        )
        printer_cb.pack(fill=tk.X, pady=(0, 15))
        
        def load_printers_async():
            import threading
            def run():
                printers, default_printer = self.get_system_printers()
                printers_options = ["Default System Printer"] + printers
                
                def update_gui():
                    if preview_win.winfo_exists():
                        printer_cb.config(values=printers_options, state="readonly")
                        if default_printer and default_printer in printers:
                            printer_var.set(default_printer)
                        else:
                            printer_var.set("Default System Printer")
                        printer_lbl.config(text="Select Printer:")
                        
                if preview_win.winfo_exists():
                    preview_win.after(0, update_gui)
            
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            
        load_printers_async()
        
        btn_row = tk.Frame(ctrl_frame, bg="#ffffff")
        btn_row.pack(fill=tk.X)
        
        def handle_print():
            selected_printer = printer_var.get()
            selected_size = "Long" if paper_var.get().startswith("Long") else "A4"
            try:
                chosen_font_size = int(font_size_var.get())
            except ValueError:
                chosen_font_size = 10
            print_btn.config(state="disabled", text="Printing...")
            cancel_btn.config(state="disabled")
            
            def run_print():
                try:
                    if sys.platform == "win32":
                        escaped_path = filepath.replace("'", "''")
                        printer_setting = ""
                        if selected_printer != "Default System Printer":
                            escaped_printer = selected_printer.replace("'", "''")
                            printer_setting = f"$doc.PrinterSettings.PrinterName = '{escaped_printer}'"
                        
                        # Try setting standard Folio size (8.5'' x 13'') if supported by the driver, otherwise use custom size
                        paper_size_setting = """
$paper = $doc.PrinterSettings.PaperSizes | Where-Object { $_.Kind -eq [System.Drawing.Printing.PaperKind]::Folio }
if (-not $paper) {
    $paper = New-Object System.Drawing.Printing.PaperSize("Custom 8.5x13", 850, 1300)
}
$doc.DefaultPageSettings.PaperSize = $paper
"""
                        
                        ps_script = f"""
Add-Type -AssemblyName System.Drawing
$doc = New-Object System.Drawing.Printing.PrintDocument
{printer_setting}
{paper_size_setting}
$doc.DefaultPageSettings.Margins.Top = 60
$doc.DefaultPageSettings.Margins.Bottom = 70
$doc.DefaultPageSettings.Margins.Left = 30
$doc.DefaultPageSettings.Margins.Right = 30
$fontSize = {chosen_font_size}
$font = New-Object System.Drawing.Font("Consolas", $fontSize)
$allText = [System.IO.File]::ReadAllText('{escaped_path}')
$pages = $allText -split [char]12
$totalPages = $pages.Count
$script:pageIndex = 0
$doc.add_PrintPage({{
    param($sender, $e)
    $g  = $e.Graphics
    $pb = $e.PageBounds
    # Margin bounds matching margins (60 top/left/right, 70 bottom)
    $topY    = 60.0
    $bottomY = [float]($pb.Height - 70)
    $leftX   = 30.0
    $rightX  = [float]($pb.Width  - 30)
    # Measure font height to calculate exact spacing for signature block
    $charHeight = ($g.MeasureString("A", $font)).Height
    # Reserve safe bottom zone for page number and signatures (4 lines of height to prevent overlap)
    $bottomZone = ($charHeight * 4.0) + 20
    # Strip the footer lines and metadata from body text to avoid double printing
    $rawText    = $pages[$script:pageIndex]
    $pageLines  = $rawText -split "`r?`n"
    $bodyLines  = $pageLines | Where-Object {{
        $_ -notmatch '^\[PAGE:\d+OF:\d+\]$' -and
        $_ -notmatch '^\s*Received by: .* Checked by: .*\s*$' -and
        $_ -notmatch '^\s*Page \d+ of \d+\s*$'
    }}
    
    # Split header lines and table lines dynamically based on border markers
    $headerLines = @()
    $tableLines  = @()
    $inTable     = $false
    foreach ($line in $bodyLines) {{
        if ($line.StartsWith("+") -or $line.StartsWith("|") -or $line.StartsWith("┌") -or $line.StartsWith("│") -or $line.StartsWith("├") -or $line.StartsWith("└")) {{
            $inTable = $true
        }}
        if ($inTable) {{
            $tableLines += $line
        }} else {{
            if ($line.Trim() -ne "") {{
                $headerLines += $line
            }}
        }}
    }}
    $cleanHeaderLines = $headerLines | ForEach-Object {{ $_.Trim() }}
    $titleLines    = $cleanHeaderLines | Where-Object {{ $_ -notmatch '^Date:' -and $_ -notmatch '^Ref ID:' }}
    $subHeaderLines = $cleanHeaderLines | Where-Object {{ $_ -match '^Date:' -or $_ -match '^Ref ID:' }}
    $titleText     = $titleLines -join "`n"
    $subHeaderText = $subHeaderLines -join "`n"
    $tableText     = $tableLines -join "`n"
    
    # Draw title (15pt Bold) centered
    $headerFont = New-Object System.Drawing.Font("Consolas", 15, [System.Drawing.FontStyle]::Bold)
    $headerCharHeight = ($g.MeasureString("A", $headerFont)).Height
    $sfHeader = New-Object System.Drawing.StringFormat
    $sfHeader.Alignment = [System.Drawing.StringAlignment]::Center
    $titleRect = New-Object System.Drawing.RectangleF(0, $topY, $pb.Width, ($headerCharHeight * 1.5))
    $g.DrawString($titleText, $headerFont, [System.Drawing.Brushes]::Black, $titleRect, $sfHeader)
    
    # Draw date/ref ID (11pt Regular) centered, below the title
    $subFont = New-Object System.Drawing.Font("Consolas", 11, [System.Drawing.FontStyle]::Regular)
    $subCharHeight = ($g.MeasureString("A", $subFont)).Height
    $subY = $topY + ($headerCharHeight * 1.5) + 4
    $sfSub = New-Object System.Drawing.StringFormat
    $sfSub.Alignment = [System.Drawing.StringAlignment]::Center
    $subRect = New-Object System.Drawing.RectangleF(0, $subY, $pb.Width, ($subCharHeight * 2.5))
    $g.DrawString($subHeaderText, $subFont, [System.Drawing.Brushes]::Black, $subRect, $sfSub)
    
    # Align the table starting below the sub-header lines, left-aligned close to the side
    $x = $leftX
    $tableY = $subY + ($subCharHeight * 2.5) + 10
    $tableLinesArray = $tableText -split "`r?`n"
    $currentY = $tableY
    $lineHeight = $font.GetHeight($g) * 0.92
    foreach ($line in $tableLinesArray) {
        $g.DrawString($line, $font, [System.Drawing.Brushes]::Black, $leftX, $currentY)
        $currentY += $lineHeight
    }
    
    # Pinned page number centered at the very bottom, using a smaller font
    $pageLabel = "Page $($script:pageIndex + 1) of $totalPages"
    $smallFont = New-Object System.Drawing.Font("Consolas", [float]($fontSize * 0.8))
    $pageSize  = $g.MeasureString($pageLabel, $smallFont)
    $pageX     = ($pb.Width - $pageSize.Width) / 2
    $pageY     = $pb.Height - 35
    $g.DrawString($pageLabel, $smallFont, [System.Drawing.Brushes]::Black, $pageX, $pageY)
    
    # Align signatures (moved slightly higher and made larger)
    $sigFont   = New-Object System.Drawing.Font("Consolas", [float]($fontSize * 1.15))
    $sigY      = $bottomY - $charHeight - 35
    $g.DrawString("Received by: ____________________", $sigFont, [System.Drawing.Brushes]::Black, $leftX, $sigY)
    
    $checkedStr  = "Checked by: ____________________"
    $checkedSize = $g.MeasureString($checkedStr, $sigFont)
    $g.DrawString($checkedStr, $sigFont, [System.Drawing.Brushes]::Black, ($rightX - $checkedSize.Width), $sigY)
    
    $script:pageIndex++
    $e.HasMorePages = ($script:pageIndex -lt $totalPages)
}})
$doc.Print()
"""
                        cmd = ["powershell", "-Command", ps_script]
                        subprocess.run(cmd, check=True)
                    else:
                        if selected_printer == "Default System Printer":
                            subprocess.run(["lp", filepath], check=True)
                        else:
                            subprocess.run(["lp", "-d", selected_printer, filepath], check=True)
                    
                    def success():
                        if preview_win.winfo_exists():
                            preview_win.destroy()
                            on_success_callback()
                    if preview_win.winfo_exists():
                        preview_win.after(0, success)
                        
                except Exception as e:
                    def failure(err_msg):
                        if preview_win.winfo_exists():
                            print_btn.config(state="normal", text="🖨️ Confirm Print")
                            cancel_btn.config(state="normal")
                            messagebox.showerror(
                                "Print Error",
                                f"An error occurred while printing:\n{err_msg}"
                            )
                    if preview_win.winfo_exists():
                        preview_win.after(0, lambda: failure(str(e)))
            
            import threading
            threading.Thread(target=run_print, daemon=True).start()
                
        def handle_cancel():
            preview_win.destroy()
            
        cancel_btn = tk.Button(
            btn_row,
            text="Cancel",
            font=("Segoe UI", 10, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            padx=15,
            pady=8,
            command=handle_cancel
        )
        cancel_btn.pack(side=tk.LEFT)
        self.setup_hover_effect(cancel_btn, "#ef4444", "#b91c1c")
        
        print_btn = tk.Button(
            btn_row,
            text="🖨️ Confirm Print",
            font=("Segoe UI", 10, "bold"),
            bg="#10b981",
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            padx=20,
            pady=8,
            command=handle_print
        )
        print_btn.pack(side=tk.RIGHT)
        self.setup_hover_effect(print_btn, "#10b981", "#059669")

    def print_report(self):
        """Generates, saves locally as .txt, triggers printer review & selection modal, and logs to persistent SQLite history."""
        if not self.dispatch_items:
            messagebox.showerror(
                "Print Error", 
                "There are no items in the session dispatch table.\nPlease add items before printing."
            )
            self.item_name_entry.focus_set()
            return
            
        # Compile lists
        items_data = []
        total_qty = 0
        for item in self.dispatch_items:
            desc = item["desc"]
            qty = int(item["qty"])
            items_data.append((desc, qty))
            total_qty += qty
            
        # Time generation
        now = datetime.datetime.now()
        timestamp_file = now.strftime("%Y%m%d_%H%M%S")
        timestamp_display = now.strftime("%Y-%m-%d %I:%M:%S %p")
        
        # Generate sequential LIFECHECK ref_id
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM history")
            count = cursor.fetchone()[0] + 1
            date_part = now.strftime("%Y%m%d")
            ref_id = f"LIFECHECK_{count:04d}_{date_part}"
        finally:
            conn.close()
            
        # Format receipt contents
        receipt_content = self.format_receipt_text(
            date_str=timestamp_display,
            items_data=items_data,
            total_qty=total_qty,
            ref_id=ref_id
        )
        
        # Filename creation
        filename = f"StockOut_{timestamp_file}.txt"
        filepath = os.path.abspath(filename)
        
        try:
            # Write plain text file locally
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(receipt_content)
                
            # Log printed slip transaction permanently in local SQLite database
            items_list = [{"name": item[0], "qty": item[1]} for item in items_data]
            items_json_str = json.dumps(items_list)
            
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO history (ref_id, timestamp, total_qty, receipt_text, items_json) VALUES (?, ?, ?, ?, ?)",
                    (ref_id, timestamp_display, total_qty, receipt_content, items_json_str)
                )
                conn.commit()
            finally:
                conn.close()
            
            self.load_history_from_db()
            
            self.status_lbl.config(text=f"Report saved locally to {filename}. Reviewing print options...")
            
            def on_success():
                # Success confirmation popup
                messagebox.showinfo(
                    "Dispatch Report Printed", 
                    f"Report successfully saved as:\n{filename}\n\n"
                    f"Dispatched to selected printer.\n"
                    "The current session table will now be cleared."
                )
                
                # Wipe list after successful report completion
                self.dispatch_items = []
                self.refresh_dispatch_tree()
                self.status_lbl.config(text=f"Session report printed & logged in history. Cleared active batch.")
                
            self.show_print_preview_dialog(filepath, timestamp_display, items_data, total_qty, ref_id, on_success)
            
        except Exception as e:
            messagebox.showerror(
                "Printing/Writing Error",
                f"An error occurred while generating or printing the report:\n{str(e)}"
            )
            self.status_lbl.config(text="Error generating print file.")
            
        # Return focus to beginning
        self.item_name_entry.focus_set()

    # ========================================================
    # TAB 2: INVENTORY PRODUCT MANAGEMENT BUSINESS LOGIC
    # ========================================================
    def add_inventory_product(self):
        """Adds a brand new product to the master catalog (name-only) directly in SQLite."""
        name = self.inv_name_var.get().strip()
        
        if not name:
            messagebox.showwarning(
                "Blank Input Warning", 
                "Product Name/Label cannot be empty.\nPlease enter a product description."
            )
            self.inv_name_entry.focus_set()
            return
            
        # Check duplicate case-insensitive in memory list first
        matches = [p for p in self.products if p.lower() == name.lower()]
        if matches:
            messagebox.showwarning(
                "Catalog Conflict", 
                f"Product '{name}' already exists in the catalog database!"
            )
            self.inv_name_entry.focus_set()
            return
            
        # Write directly to SQLite products table
        conn = sqlite3.connect(self.db_path)
        success = True
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO products (name) VALUES (?)", (name,))
            conn.commit()
        except sqlite3.IntegrityError:
            success = False
        finally:
            conn.close()
        
        if not success:
            messagebox.showwarning("Catalog Conflict", f"Product '{name}' already exists!")
            self.inv_name_entry.focus_set()
            return
            
        self.load_products_from_db()
        self.inv_name_var.set("")
        self.refresh_inventory_list()
        self.status_lbl.config(text=f"Successfully Cataloged: '{name}'")
        self.inv_name_entry.focus_set()

    def delete_inventory_product(self):
        """Deletes selected master product from SQLite database catalog."""
        selected = self.inv_tree.selection()
        if not selected:
            self.status_lbl.config(text="Select a product to remove first.")
            return
            
        prod_name = self.inv_tree.item(selected[0], 'values')[0]
        confirm = messagebox.askyesno(
            "Remove Catalog Item", 
            f"Are you sure you want to completely remove:\n'{prod_name}'\nfrom the master product list?\n\n(Past stock-out sheets containing this item will not be modified.)"
        )
        if confirm:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM products WHERE name = ?", (prod_name,))
                conn.commit()
            finally:
                conn.close()
            
            self.load_products_from_db()
            self.refresh_inventory_list()
            self.status_lbl.config(text=f"Deleted '{prod_name}' from catalog database.")
            self.inv_name_entry.focus_set()

    # ========================================================
    # TAB 3: STOCK-OUT PRINTING HISTORY BUSINESS LOGIC
    # ========================================================
    def on_history_select(self, event):
        """Triggers rendering the exact matching printed document into the monospace ScrolledText area."""
        selected = self.hist_tree.selection()
        if not selected:
            self.clear_history_viewer()
            return
            
        ref_id = self.hist_tree.item(selected[0], 'values')[1]
        
        # Look up records matching ref_id
        record = None
        for r in self.history:
            if r["ref_id"] == ref_id:
                record = r
                break
                
        if record:
            self.hist_text.config(state=tk.NORMAL)
            self.hist_text.delete("1.0", tk.END)
            self.hist_text.insert(tk.END, record["receipt_text"].replace("\x0c", "\n\n--- PAGE BREAK ---\n\n"))
            self.hist_text.config(state=tk.DISABLED)
            
            # Enable actions
            self.btn_reprint.config(state=tk.NORMAL, bg="#10b981")
            self.btn_del_hist.config(state=tk.NORMAL, fg="#ef4444")
        else:
            self.clear_history_viewer()

    def delete_history_record(self):
        """Removes a specific transaction log history permanently from SQLite database."""
        selected = self.hist_tree.selection()
        if not selected:
            return
            
        ref_id = self.hist_tree.item(selected[0], 'values')[1]
        confirm = messagebox.askyesno(
            "Delete History Log",
            f"Are you sure you want to permanently delete history log:\n{ref_id}?\n\nThis cannot be undone."
        )
        if confirm:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM history WHERE ref_id = ?", (ref_id,))
                conn.commit()
            finally:
                conn.close()
            
            self.load_history_from_db()
            self.refresh_history_list()
            self.status_lbl.config(text=f"Deleted history record {ref_id}.")

    def on_hist_tree_right_click(self, event):
        """Displays a context menu on right-click to reload selected batch items."""
        item_id = self.hist_tree.identify_row(event.y)
        if not item_id:
            return
            
        self.hist_tree.selection_set(item_id)
        
        # Create context menu
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Reload into Dispatch", command=self.reload_selected_history)
        menu.post(event.x_root, event.y_root)

    def reload_selected_history(self):
        selected = self.hist_tree.selection()
        if not selected:
            return
            
        ref_id = self.hist_tree.item(selected[0], 'values')[1]
        
        # Find history record
        record = None
        for r in self.history:
            if r["ref_id"] == ref_id:
                record = r
                break
                
        if not record:
            return
            
        # Confirm reloading (if there are already items in dispatch, warn/ask user with choices)
        action = 'replace'
        if self.dispatch_items:
            dialog = ReloadConflictDialog(self.root)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return  # Cancelled
            action = dialog.result
                
        # Load / merge items
        if action == 'replace':
            self.dispatch_items = []
            
        for item in record["items"]:
            h_name = item["name"]
            h_qty = int(item["qty"])
            
            # Check duplicate to sum quantities when appending
            found = False
            for disp_item in self.dispatch_items:
                if disp_item["desc"].lower() == h_name.lower():
                    disp_item["qty"] += h_qty
                    found = True
                    break
            if not found:
                self.dispatch_items.append({
                    "desc": h_name,
                    "qty": h_qty
                })
            
        # Switch tab to dispatch
        self.switch_tab("dispatch")
        self.refresh_dispatch_tree()
        self.status_lbl.config(text=f"Reloaded {len(self.dispatch_items)} items from history ref: {ref_id}.")

    def reprint_history_record(self):
        """Reprints standard physical A4 paper print slip matching the selected historical text file."""
        selected = self.hist_tree.selection()
        if not selected:
            return
            
        ref_id = self.hist_tree.item(selected[0], 'values')[1]
        
        record = None
        for r in self.history:
            if r["ref_id"] == ref_id:
                record = r
                break
                
        if not record:
            return
            
        receipt_content = record["receipt_text"]
        
        items_data = [(item["name"], item["qty"]) for item in record["items"]]
        date_str = record["timestamp"]
        total_qty = record["total_qty"]
        
        # Convert ref_id into a safe filename
        safe_name = ref_id.replace('/', '_').replace('\\', '_')
        filename = f"StockOut_{safe_name}.txt"
        filepath = os.path.abspath(filename)
        
        try:
            # Save the file locally again
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(receipt_content)
                
            self.status_lbl.config(text=f"Reprinting saved local log {ref_id}...")
            
            def on_success():
                messagebox.showinfo(
                    "Reprint Triggered",
                    f"Historical record {ref_id} successfully dispatched to print system!\n"
                    f"Saved print text: {filename}"
                )
            
            self.show_print_preview_dialog(filepath, date_str, items_data, total_qty, ref_id, on_success)
            
        except Exception as e:
            messagebox.showerror(
                "Reprint Error",
                f"Unable to trigger reprint logs:\n{str(e)}"
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = BodegaStockOutApp(root)
    root.mainloop()
