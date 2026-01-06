import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, colorchooser, Menu
from PIL import Image, ImageTk
import os
import json
import tempfile
import math
import copy
import re  # 正規表現用

class PDFEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python PDF Editor (Lv.30 - 注文日時順並び替え版)")
        self.root.geometry("1500x950")

        # --- 変数初期化 ---
        self.doc = None
        self.current_page_num = 0
        self.image_ref = None # 背景PDF用
        self.photo_refs = {}  # 追加画像用 (GC対策)
        self.pdf_path = None
        self.zoom_level = 1.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.annotations = {} 
        self.clipboard = None
        self.history = [] # 元に戻す用スタック
        
        self.drag_data = {"item": None, "x": 0, "y": 0}
        self.selected_item_id = None
        self.mode = None 
        
        # グリッド設定
        self.show_grid = False
        self.grid_size = 20 # ピクセル

        self.linestyles = {
            "実線": None, "点線": (2, 2), "破線": (6, 4), "一点鎖線": (6, 3, 2, 3)
        }

        # --- UIレイアウト ---
        # 1. ツールバー
        toolbar = tk.Frame(root, bd=1, relief=tk.RAISED, bg="#f0f0f0")
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # ファイル操作
        file_frame = tk.LabelFrame(toolbar, text="ファイル", bg="#f0f0f0")
        file_frame.pack(side=tk.LEFT, padx=5, pady=2)
        tk.Button(file_frame, text="開く", command=self.open_pdf, bg="#e1f5fe").pack(side=tk.LEFT, padx=1)
        tk.Button(file_frame, text="保存(prj)", command=self.save_project, bg="#fff9c4").pack(side=tk.LEFT, padx=1)
        tk.Button(file_frame, text="再開/テンプレ", command=self.load_project, bg="#fff9c4").pack(side=tk.LEFT, padx=1)
        tk.Button(file_frame, text="PDF保存", command=self.save_as, bg="#ffab91").pack(side=tk.LEFT, padx=1)
        tk.Button(file_frame, text="🖨印刷", command=self.print_pdf, bg="#b3e5fc").pack(side=tk.LEFT, padx=1)
        # ★変更: ボタン名を変更
        tk.Button(file_frame, text="🔗結合(注文日時順)", command=self.merge_pdfs, bg="#c8e6c9").pack(side=tk.LEFT, padx=1)

        # 編集操作
        edit_ope_frame = tk.LabelFrame(toolbar, text="操作", bg="#f0f0f0")
        edit_ope_frame.pack(side=tk.LEFT, padx=5, pady=2)
        tk.Button(edit_ope_frame, text="↶ 元に戻す", command=self.undo, width=8).pack(side=tk.LEFT, padx=1)
        tk.Button(edit_ope_frame, text="コピー", command=self.copy_selection).pack(side=tk.LEFT, padx=1)
        tk.Button(edit_ope_frame, text="貼付", command=self.paste_selection).pack(side=tk.LEFT, padx=1)
        
        # ツール
        tool_frame = tk.LabelFrame(toolbar, text="ツール", bg="#f0f0f0")
        tool_frame.pack(side=tk.LEFT, padx=5, pady=2)
        tk.Button(tool_frame, text="文字", command=lambda: self.set_mode("text"), bg="#ffffff", width=4).pack(side=tk.LEFT, padx=1)
        tk.Button(tool_frame, text="✔", command=lambda: self.set_mode("check"), bg="#ffffff", width=2).pack(side=tk.LEFT, padx=1)
        tk.Button(tool_frame, text="白塗", command=lambda: self.set_mode("whiteout"), bg="#ffffff", width=4).pack(side=tk.LEFT, padx=1)
        tk.Button(tool_frame, text="画像", command=self.add_image_from_file, bg="#ffffff", width=4).pack(side=tk.LEFT, padx=1)

        self.shape_var = tk.StringVar()
        self.shape_var.set("図形...")
        shape_options = ["〇 丸", "□ 四角", "▽ 逆三角", "ー 直線", "→ 矢印", "★ 星"]
        shape_menu = tk.OptionMenu(tool_frame, self.shape_var, *shape_options, command=self.on_shape_menu)
        shape_menu.config(bg="#e1bee7", width=5)
        shape_menu.pack(side=tk.LEFT, padx=1)

        # アイテム編集
        edit_frame = tk.LabelFrame(toolbar, text="選択中アイテム編集", bg="#f0f0f0")
        edit_frame.pack(side=tk.LEFT, padx=5, pady=2)
        
        tk.Button(edit_frame, text="太字", command=self.toggle_bold, width=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=1)
        tk.Button(edit_frame, text="明/ゴ", command=self.toggle_font, width=3).pack(side=tk.LEFT, padx=1)
        tk.Button(edit_frame, text="修正", command=self.edit_text_content, width=3, bg="#fff9c4").pack(side=tk.LEFT, padx=1)

        tk.Label(edit_frame, text="|", bg="#f0f0f0").pack(side=tk.LEFT, padx=2)
        tk.Button(edit_frame, text="大", command=lambda: self.resize_selection(2, 2), width=2).pack(side=tk.LEFT, padx=0)
        tk.Button(edit_frame, text="小", command=lambda: self.resize_selection(-2, -2), width=2).pack(side=tk.LEFT, padx=0)
        tk.Button(edit_frame, text="幅+", command=lambda: self.resize_selection(5, 0), width=3, fg="blue").pack(side=tk.LEFT, padx=0)
        tk.Button(edit_frame, text="幅-", command=lambda: self.resize_selection(-5, 0), width=3, fg="blue").pack(side=tk.LEFT, padx=0)
        tk.Button(edit_frame, text="高+", command=lambda: self.resize_selection(0, 5), width=3, fg="green").pack(side=tk.LEFT, padx=0)
        tk.Button(edit_frame, text="高-", command=lambda: self.resize_selection(0, -5), width=3, fg="green").pack(side=tk.LEFT, padx=0)
        
        tk.Button(edit_frame, text="色", command=self.change_color_selection, width=2).pack(side=tk.LEFT, padx=1)
        
        self.linestyle_btn = tk.Menubutton(edit_frame, text="線", relief=tk.RAISED, width=2)
        self.linestyle_menu = Menu(self.linestyle_btn, tearoff=0)
        self.linestyle_btn.config(menu=self.linestyle_menu)
        for name, value in self.linestyles.items():
            self.linestyle_menu.add_command(label=name, command=lambda v=value: self.change_linestyle_selection(v))
        self.linestyle_btn.pack(side=tk.LEFT, padx=1)

        tk.Button(edit_frame, text="削除", command=self.delete_selection, fg="red", width=3).pack(side=tk.LEFT, padx=1)

        # 表示オプション
        view_frame = tk.LabelFrame(toolbar, text="表示", bg="#f0f0f0")
        view_frame.pack(side=tk.LEFT, padx=5, pady=2)
        self.grid_btn = tk.Button(view_frame, text="# グリッド", command=self.toggle_grid, relief=tk.RAISED)
        self.grid_btn.pack(side=tk.LEFT, padx=2)

        self.status_label = tk.Label(toolbar, text="準備完了", fg="blue", bg="#f0f0f0")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Canvas
        self.canvas_frame = tk.Frame(root, bg="gray")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.canvas = tk.Canvas(self.canvas_frame, bg="gray",
                                yscrollcommand=self.v_scroll.set,
                                xscrollcommand=self.h_scroll.set)
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)
        self.canvas.bind("<Motion>", self.on_mouse_move) 
        self.canvas.bind("<Double-1>", self.on_canvas_double_click)
        self.canvas.bind("<Configure>", self.on_resize)
        
        self.root.bind("<Delete>", lambda e: self.delete_selection())
        self.root.bind("<Control-c>", lambda e: self.copy_selection())
        self.root.bind("<Control-v>", lambda e: self.paste_selection())
        self.root.bind("<Control-z>", lambda e: self.undo()) 

        # Footer
        bottom_bar = tk.Frame(root, bd=1, relief=tk.SUNKEN)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(bottom_bar, text="< 前へ", command=self.prev_page).pack(side=tk.LEFT, padx=10)
        self.page_label = tk.Label(bottom_bar, text="0 / 0")
        self.page_label.pack(side=tk.LEFT, padx=10)
        tk.Button(bottom_bar, text="次へ >", command=self.next_page).pack(side=tk.LEFT, padx=10)
        self.zoom_label = tk.Label(bottom_bar, text="100%")
        self.zoom_label.pack(side=tk.RIGHT, padx=10)

    # --- Core Functions ---
    def save_state(self):
        """現在の状態を履歴に保存（Undo用）"""
        if len(self.history) > 20: self.history.pop(0)
        self.history.append(copy.deepcopy(self.annotations))

    def undo(self):
        """直前の状態に戻す"""
        if self.history:
            self.annotations = self.history.pop()
            self.selected_item_id = None
            self.redraw_annotations()
            self.status_label.config(text="元に戻しました")
        else:
            self.status_label.config(text="これ以上戻せません")

    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not path: return
        self.pdf_path = path
        try:
            self.doc = fitz.open(self.pdf_path)
            self.current_page_num = 0
            self.annotations = {}
            self.history = []
            self.zoom_level = 1.0
            self.show_page()
            self.status_label.config(text="PDFを開きました")
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def on_resize(self, event):
        if self.doc: self.show_page()

    def on_zoom(self, event):
        if not self.doc: return
        if event.delta > 0: self.zoom_level += 0.1
        else: self.zoom_level = max(0.2, self.zoom_level - 0.1)
        self.show_page()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        if self.show_grid:
            self.grid_btn.config(relief=tk.SUNKEN, bg="#ccc")
        else:
            self.grid_btn.config(relief=tk.RAISED, bg="#f0f0f0")
        self.show_page() 

    def draw_grid_lines(self, width, height):
        if not self.show_grid: return
        step = self.grid_size * self.zoom_level
        
        for i in range(0, int(width), int(step)):
            x = self.offset_x + i
            self.canvas.create_line(x, self.offset_y, x, self.offset_y + height, fill="#ddd", tags="grid")
        for i in range(0, int(height), int(step)):
            y = self.offset_y + i
            self.canvas.create_line(self.offset_x, y, self.offset_x + width, y, fill="#ddd", tags="grid")

    def show_page(self):
        if not self.doc: return
        self.page_label.config(text=f"{self.current_page_num + 1} / {len(self.doc)}")
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        
        page = self.doc[self.current_page_num]
        mat = fitz.Matrix(self.zoom_level, self.zoom_level)
        pix = page.get_pixmap(matrix=mat)
        
        self.scale_x = page.rect.width / pix.width
        self.scale_y = page.rect.height / pix.height

        img_data = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.image_ref = ImageTk.PhotoImage(img_data)

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        img_w, img_h = pix.width, pix.height

        if canvas_width > img_w: self.offset_x = (canvas_width - img_w) // 2
        else: self.offset_x = 0
        if canvas_height > img_h: self.offset_y = (canvas_height - img_h) // 2
        else: self.offset_y = 0

        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, image=self.image_ref, anchor=tk.NW, tags="background")
        
        self.draw_grid_lines(img_w, img_h) 
        
        self.canvas.config(scrollregion=(0, 0, max(canvas_width, img_w), max(canvas_height, img_h)))
        self.redraw_annotations()

    def get_canvas_coords(self, pdf_x, pdf_y):
        cx = (pdf_x / self.scale_x) + self.offset_x
        cy = (pdf_y / self.scale_y) + self.offset_y
        return cx, cy

    def get_pdf_coords(self, canvas_x, canvas_y):
        px = (canvas_x - self.offset_x) * self.scale_x
        py = (canvas_y - self.offset_y) * self.scale_y
        return px, py

    def snap_value(self, val, scale):
        if not self.show_grid: return val
        grid_step = self.grid_size * scale
        return round(val / grid_step) * grid_step

    def get_snapped_pdf_coords(self, canvas_x, canvas_y):
        px, py = self.get_pdf_coords(canvas_x, canvas_y)
        if self.show_grid:
            px = self.snap_value(px, self.scale_x)
            py = self.snap_value(py, self.scale_y)
        return px, py

    # --- Actions ---
    def set_mode(self, mode):
        self.mode = mode
        self.deselect_all()
        self.canvas.config(cursor="cross")
        self.status_label.config(text=f"モード: {mode} (クリックで配置)")

    def on_shape_menu(self, value):
        mode_map = {"丸": "circle", "四角": "rect", "逆三角": "triangle", 
                    "直線": "line", "矢印": "arrow", "星": "star"}
        for key, mode in mode_map.items():
            if key in value:
                self.set_mode(mode)
                break
        self.shape_var.set("図形...")

    def add_image_from_file(self):
        if not self.doc: return
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if not path: return
        
        self.save_state() 
        item_id = str(len(self.annotations.get(self.current_page_num, [])) + 30000)
        
        data = {
            "id": item_id, "type": "image",
            "x": 50, "y": 50, "width": 100, "height": 100,
            "image_path": path
        }
        
        if self.current_page_num not in self.annotations:
            self.annotations[self.current_page_num] = []
        self.annotations[self.current_page_num].append(data)
        self.redraw_annotations()
        self.select_item(item_id)
        self.status_label.config(text="画像を追加しました")

    def find_item_at_position(self, cx, cy):
        items = self.canvas.find_withtag("annot")
        for item in reversed(items):
            bbox = self.canvas.bbox(item)
            if bbox:
                margin = 5 
                if (bbox[0]-margin) <= cx <= (bbox[2]+margin) and (bbox[1]-margin) <= cy <= (bbox[3]+margin):
                    tags = self.canvas.gettags(item)
                    for tag in tags:
                        if tag.startswith("item_"):
                            return tag.replace("item_", "")
        return None

    def on_mouse_move(self, event):
        if self.mode: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        item_id = self.find_item_at_position(cx, cy)
        self.canvas.config(cursor="hand2" if item_id else "arrow")

    def on_canvas_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if self.mode:
            self.save_state() 
            px, py = self.get_snapped_pdf_coords(cx, cy) 
            self.add_annotation(px, py, self.mode)
            self.mode = None
            self.canvas.config(cursor="arrow")
            self.status_label.config(text="選択中")
        else:
            clicked_id = self.find_item_at_position(cx, cy)
            if clicked_id:
                self.select_item(clicked_id)
                self.drag_data = {"item": f"item_{clicked_id}", "x": cx, "y": cy}
            else:
                self.deselect_all()

    def on_canvas_double_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked_id = self.find_item_at_position(cx, cy)
        if clicked_id:
            self.select_item(clicked_id)
            self.edit_text_content()

    def add_annotation(self, pdf_x, pdf_y, type_):
        item_id = str(len(self.annotations.get(self.current_page_num, [])) + 10000)
        data = {
            "id": item_id, "type": type_, 
            "x": pdf_x, "y": pdf_y,
            "color": "#000000", "rgb": (0, 0, 0),
            "width": 20, "height": 20, 
            "linestyle": None, "text": "",
            "font": "gothic", "bold": False
        }
        if type_ == "text":
            text = self.ask_multiline_text("入力", "テキストを入力 (Enterで改行):")
            if not text: return
            data["text"] = text
            data["width"] = 20 
        elif type_ == "check": data.update({"text": "✔", "width": 24})
        elif type_ == "whiteout":
            data.update({"width": 50, "height": 20, "color": "#FFFFFF", "rgb": (1, 1, 1)})
        elif type_ == "triangle": data.update({"width": 30, "height": 25})
        elif type_ == "circle": data.update({"width": 20, "height": 20})
        elif type_ == "rect": data.update({"width": 30, "height": 20})
        elif type_ in ["line", "arrow"]: data.update({"width": 50, "height": 0})
        elif type_ == "star": data.update({"width": 25, "height": 25})

        if self.current_page_num not in self.annotations:
            self.annotations[self.current_page_num] = []
        self.annotations[self.current_page_num].append(data)
        self.redraw_annotations()
        self.select_item(item_id)

    def ask_multiline_text(self, title, prompt, initial=""):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x300")
        dialog.grab_set()
        tk.Label(dialog, text=prompt).pack(pady=5)
        text_area = tk.Text(dialog, height=10, width=40, font=("Arial", 12))
        text_area.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        text_area.insert("1.0", initial)
        text_area.focus_set()
        result = [None]
        def on_ok(event=None):
            result[0] = text_area.get("1.0", "end-1c")
            dialog.destroy()
        def on_cancel(): dialog.destroy()
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill=tk.X, pady=10)
        tk.Button(btn_frame, text="キャンセル", command=on_cancel).pack(side=tk.RIGHT, padx=10)
        tk.Button(btn_frame, text="OK (Shift+Enter)", command=on_ok, bg="#ddffdd", width=15).pack(side=tk.RIGHT, padx=10)
        text_area.bind("<Shift-Return>", on_ok)
        self.root.wait_window(dialog)
        return result[0]

    def redraw_annotations(self):
        self.canvas.delete("annot")
        self.canvas.delete("selection")
        if self.current_page_num in self.annotations:
            for data in self.annotations[self.current_page_num]:
                self.draw_single_item(data)
        if self.selected_item_id:
            self.draw_selection_box(self.selected_item_id)

    def draw_single_item(self, data):
        cx, cy = self.get_canvas_coords(data["x"], data["y"])
        w, h = data["width"] * self.zoom_level, data["height"] * self.zoom_level
        tag, ls = f"item_{data['id']}", data["linestyle"]
        display_fs = int(w)
        if display_fs < 1: display_fs = 1

        if data["type"] in ["text", "check"]:
            f_family = "MS Gothic" if data.get("font", "gothic") == "gothic" else "MS Mincho"
            f_weight = "bold" if data.get("bold", False) else "normal"
            self.canvas.create_text(cx, cy, text=data["text"], fill=data["color"],
                                    font=(f_family, display_fs, f_weight), anchor=tk.NW, tags=("annot", tag))
        
        elif data["type"] == "image":
            img_path = data.get("image_path")
            if img_path and os.path.exists(img_path):
                if item_id := data["id"]:
                    try:
                        pil_img = Image.open(img_path)
                        pil_img = pil_img.resize((int(w*2), int(h*2)), Image.LANCZOS) 
                        tk_img = ImageTk.PhotoImage(pil_img)
                        self.photo_refs[item_id] = tk_img
                        self.canvas.create_image(cx, cy, image=tk_img, anchor=tk.NW, tags=("annot", tag))
                    except: pass
        
        elif data["type"] == "whiteout":
            self.canvas.create_rectangle(cx, cy, cx+w, cy+h, fill="white", outline="white", tags=("annot", tag))

        elif data["type"] == "circle":
            self.canvas.create_oval(cx-w, cy-h, cx+w, cy+h, outline=data["color"], width=2, dash=ls, tags=("annot", tag))
        elif data["type"] == "rect":
            self.canvas.create_rectangle(cx-w, cy-h, cx+w, cy+h, outline=data["color"], width=2, dash=ls, tags=("annot", tag))
        elif data["type"] == "triangle":
            points = [cx, cy+h, cx-w, cy-h, cx+w, cy-h]
            self.canvas.create_polygon(points, outline=data["color"], fill="", width=2, dash=ls, tags=("annot", tag))
        elif data["type"] in ["line", "arrow"]:
            arrow_opt = tk.LAST if data["type"] == "arrow" else tk.NONE
            self.canvas.create_line(cx-w, cy, cx+w, cy, fill=data["color"], width=2, arrow=arrow_opt, dash=ls, tags=("annot", tag))
        elif data["type"] == "star":
            points = self.calculate_star_points(cx, cy, w, h, 5)
            self.canvas.create_polygon(points, outline=data["color"], fill="", width=2, dash=ls, tags=("annot", tag))

    def calculate_star_points(self, cx, cy, rx, ry, num_points):
        inner_rx, inner_ry = rx * 0.4, ry * 0.4
        angle_step = math.pi / num_points
        current_angle = -math.pi / 2
        points = []
        for i in range(num_points * 2):
            rad_x = rx if i % 2 == 0 else inner_rx
            rad_y = ry if i % 2 == 0 else inner_ry
            points.append(cx + rad_x * math.cos(current_angle))
            points.append(cy + rad_y * math.sin(current_angle))
            current_angle += angle_step
        return points

    def select_item(self, item_id):
        self.selected_item_id = item_id
        self.draw_selection_box(item_id)
        self.linestyle_btn.config(state=tk.NORMAL)

    def deselect_all(self):
        self.selected_item_id = None
        self.canvas.delete("selection")
        self.linestyle_btn.config(state=tk.DISABLED)

    def draw_selection_box(self, item_id):
        self.canvas.delete("selection")
        bbox = self.canvas.bbox(f"item_{item_id}")
        if bbox: self.canvas.create_rectangle(bbox, outline="blue", width=2, dash=(2, 2), tags="selection")

    def copy_selection(self):
        if not self.selected_item_id: return
        items = self.annotations.get(self.current_page_num, [])
        target = next((d for d in items if d["id"] == self.selected_item_id), None)
        if target:
            self.clipboard = copy.deepcopy(target)
            self.status_label.config(text="コピーしました")

    def paste_selection(self):
        if not self.clipboard: return
        self.save_state()
        new_id = str(len(self.annotations.get(self.current_page_num, [])) + 20000)
        new_item = copy.deepcopy(self.clipboard)
        new_item["id"] = new_id
        new_item["x"] += 10.0
        new_item["y"] += 10.0
        if self.current_page_num not in self.annotations:
            self.annotations[self.current_page_num] = []
        self.annotations[self.current_page_num].append(new_item)
        self.redraw_annotations()
        self.select_item(new_id)
        self.status_label.config(text="貼り付けました")

    def toggle_bold(self):
        if not self.selected_item_id: return
        self.save_state()
        self.update_selected_item(lambda d: {"bold": not d.get("bold", False)})

    def toggle_font(self):
        if not self.selected_item_id: return
        self.save_state()
        def switch(d):
            current = d.get("font", "gothic")
            return {"font": "mincho" if current == "gothic" else "gothic"}
        self.update_selected_item(switch)

    def resize_selection(self, dw, dh):
        if not self.selected_item_id: return
        self.save_state()
        self.update_selected_item(lambda d: {"width": max(5, d["width"] + dw), "height": max(5, d["height"] + dh)})

    def edit_text_content(self):
        if not self.selected_item_id: return
        items = self.annotations.get(self.current_page_num, [])
        target_item = next((d for d in items if d["id"] == self.selected_item_id), None)
        if target_item and target_item["type"] == "text":
            self.save_state()
            new_text = self.ask_multiline_text("編集", "テキストを修正:", initial=target_item["text"])
            if new_text is not None:
                target_item["text"] = new_text
                self.redraw_annotations()

    def change_color_selection(self):
        if not self.selected_item_id: return
        c = colorchooser.askcolor()[1]
        if c:
            self.save_state()
            rgb = self.root.winfo_rgb(c)
            self.update_selected_item(lambda d: {"color": c, "rgb": (rgb[0]/65535, rgb[1]/65535, rgb[2]/65535)})

    def change_linestyle_selection(self, linestyle_value):
        if not self.selected_item_id: return
        self.save_state()
        self.update_selected_item(lambda d: {"linestyle": linestyle_value})

    def delete_selection(self):
        if not self.selected_item_id: return
        self.save_state()
        items = self.annotations.get(self.current_page_num, [])
        self.annotations[self.current_page_num] = [d for d in items if d["id"] != self.selected_item_id]
        self.deselect_all()
        self.redraw_annotations()

    def update_selected_item(self, update_func):
        items = self.annotations.get(self.current_page_num, [])
        for d in items:
            if d["id"] == self.selected_item_id:
                d.update(update_func(d))
                break
        self.redraw_annotations()

    def on_canvas_drag(self, event):
        if not self.selected_item_id: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        dx = cx - self.drag_data["x"]
        dy = cy - self.drag_data["y"]
        self.canvas.move(f"item_{self.selected_item_id}", dx, dy)
        self.canvas.move("selection", dx, dy)
        self.drag_data["x"] = cx
        self.drag_data["y"] = cy

    def on_canvas_release(self, event):
        if not self.selected_item_id: return
        self.save_state()
        tag = f"item_{self.selected_item_id}"
        
        if "text" in tag or "check" in tag or "image" in tag or "whiteout" in tag:
            coords = self.canvas.coords(tag)
            if coords:
                px, py = self.get_snapped_pdf_coords(coords[0], coords[1])
                self.update_selected_item(lambda d: {"x": px, "y": py})
        else: 
            coords = self.canvas.coords(tag)
            if len(coords) == 4:
                center_cx = (coords[0] + coords[2]) / 2
                center_cy = (coords[1] + coords[3]) / 2
            else:
                xs = coords[0::2]
                ys = coords[1::2]
                center_cx = (min(xs) + max(xs)) / 2
                center_cy = (min(ys) + max(ys)) / 2
            
            px, py = self.get_snapped_pdf_coords(center_cx, center_cy)
            self.update_selected_item(lambda d: {"x": px, "y": py})
        
        self.redraw_annotations()

    def prev_page(self):
        if self.doc and self.current_page_num > 0:
            self.current_page_num -= 1
            self.show_page()
    def next_page(self):
        if self.doc and self.current_page_num < len(self.doc) - 1:
            self.current_page_num += 1
            self.show_page()

    def save_project(self):
        if not self.doc: return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Project Files", "*.json")])
        if path:
            data = {"pdf_path": self.pdf_path, "annotations": self.annotations}
            try:
                with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", "保存しました")
            except Exception as e: messagebox.showerror("エラー", f"保存失敗: {e}")

    def load_project(self):
        path = filedialog.askopenfilename(filetypes=[("Project Files", "*.json")])
        if not path: return
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
            
            if self.doc:
                if messagebox.askyesno("確認", "現在のPDFに、このプロジェクトの配置を適用しますか？\n(テンプレートとして使用)"):
                    loaded_annots = {int(k): v for k, v in data.get("annotations", {}).items()}
                    self.annotations = loaded_annots 
                    self.show_page()
                    messagebox.showinfo("完了", "配置を適用しました")
                    return

            pdf_path = data.get("pdf_path")
            if not os.path.exists(pdf_path):
                pdf_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")], title="元のPDFが見つかりません。開くPDFを選択してください")
                if not pdf_path: return
            
            self.pdf_path = pdf_path
            self.doc = fitz.open(self.pdf_path)
            self.annotations = {int(k): v for k, v in data.get("annotations", {}).items()}
            self.current_page_num = 0
            self.show_page()
            messagebox.showinfo("成功", "再開します")
        except Exception as e: messagebox.showerror("エラー", f"読込失敗: {e}")

    # ★変更: 「注文日時」で並び替え
    def merge_pdfs(self):
        # 1. ファイル選択 (複数)
        file_paths = filedialog.askopenfilenames(
            title="結合するPDFを選択（複数可）",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not file_paths:
            return

        # 日付抽出用関数（内部メソッド）
        def get_order_date_from_text(doc_obj, filename):
            try:
                # 1ページ目のテキストを取得
                page_text = doc_obj[0].get_text()
                
                # 正規表現で「注文日時」または「注文日」周辺の日付を探す
                # パターン: "注文日時" または "注文日" + (記号など) + YYYY年MM月DD日 または YYYY/MM/DD
                match = re.search(r"注文日時?\D*?(\d{4}[\/年\.-]\d{1,2}[\/月\.-]\d{1,2})", page_text)
                
                if match:
                    date_str = match.group(1)
                    # 比較用に数字だけ抽出して連結 (2025/01/01 -> 20250101)
                    sortable_date = re.sub(r"\D", "", date_str)
                    
                    if len(sortable_date) == 8: return int(sortable_date)
                    elif len(sortable_date) < 8: return int(sortable_date.ljust(8, '0')) # 簡易補正
                    return int(sortable_date)
            except Exception:
                pass
            
            return 99999999

        # 2. リスト作成
        pdf_list = []
        for path in file_paths:
            try:
                with fitz.open(path) as doc:
                    o_date = get_order_date_from_text(doc, path)
                    pdf_list.append({"path": path, "date": o_date})
            except Exception as e:
                print(f"Skip {path}: {e}")
                continue
        
        if not pdf_list:
            messagebox.showerror("エラー", "有効なPDFが見つかりませんでした")
            return

        # 3. 注文日時順（昇順）に並べ替え
        pdf_list.sort(key=lambda x: x["date"])

        # 4. 結合処理
        try:
            merged_doc = fitz.open()
            for item in pdf_list:
                with fitz.open(item["path"]) as src:
                    merged_doc.insert_pdf(src)
            
            # 5. 保存
            save_path = filedialog.asksaveasfilename(
                title="結合したPDFを保存",
                defaultextension=".pdf",
                filetypes=[("PDF Files", "*.pdf")]
            )
            if save_path:
                merged_doc.save(save_path)
                messagebox.showinfo("完了", f"{len(pdf_list)}ファイルを結合しました！\n（注文日時順）")
            
            merged_doc.close()

        except Exception as e:
            messagebox.showerror("エラー", f"結合中にエラーが発生しました:\n{e}")


    def print_pdf(self):
        if not self.doc: return
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp: temp_path = tmp.name
            self.execute_save(temp_path, silent=True)
            try: os.startfile(temp_path, "print")
            except OSError:
                messagebox.showinfo("印刷", "直接印刷ができません。\nPDFを開きますので、そこから印刷してください。")
                os.startfile(temp_path)
        except Exception as e:
            messagebox.showerror("エラー", f"印刷エラー: {e}")

    def save_as(self):
        if self.doc:
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
            if path: 
                pw = None
                if messagebox.askyesno("セキュリティ", "パスワードを設定しますか？"):
                    pw = simpledialog.askstring("パスワード", "設定するパスワードを入力:", show='*')
                
                self.execute_save(path, user_pw=pw)

    def execute_save(self, path, silent=False, user_pw=None):
        work_doc = fitz.open(self.pdf_path)
        try:
            for p_num, items in self.annotations.items():
                if p_num >= len(work_doc): continue
                page = work_doc[p_num]
                for d in items:
                    p = fitz.Point(d["x"], d["y"])
                    color, ls = d["rgb"], d["linestyle"]
                    w, h = d["width"], d["height"]
                    
                    if d["type"] in ["text", "check"]:
                        font_key = d.get("font", "gothic")
                        if font_key == "mincho":
                            font_path = "C:/Windows/Fonts/msmincho.ttc"
                            fontname = "msmincho"
                        else:
                            font_path = "C:/Windows/Fonts/msgothic.ttc"
                            fontname = "msgothic"
                        if not os.path.exists(font_path): font_path = None; fontname = "helv"

                        fontsize = w
                        if fontsize < 1: fontsize = 1
                        
                        p_adjusted = fitz.Point(p.x, p.y + fontsize)

                        is_bold = d.get("bold", False)
                        if font_path:
                            page.insert_text(p_adjusted, d["text"], fontname=fontname, fontfile=font_path, fontsize=fontsize, color=color)
                            if is_bold:
                                page.insert_text(fitz.Point(p_adjusted.x+0.5, p_adjusted.y), d["text"], fontname=fontname, fontfile=font_path, fontsize=fontsize, color=color)
                        else:
                            page.insert_text(p_adjusted, d["text"], fontsize=fontsize, color=color)

                    elif d["type"] == "image":
                        img_path = d.get("image_path")
                        if img_path and os.path.exists(img_path):
                            rect = fitz.Rect(d["x"], d["y"], d["x"]+w*2, d["y"]+h*2)
                            page.insert_image(rect, filename=img_path)

                    elif d["type"] == "whiteout":
                        r = fitz.Rect(d["x"], d["y"], d["x"]+w, d["y"]+h)
                        page.draw_rect(r, fill=(1,1,1), color=(1,1,1))

                    elif d["type"] == "circle":
                        r = fitz.Rect(d["x"]-w, d["y"]-h, d["x"]+w, d["y"]+h)
                        page.draw_oval(r, color=color, width=1.5, dashes=ls)
                    elif d["type"] == "rect":
                        r = fitz.Rect(d["x"]-w, d["y"]-h, d["x"]+w, d["y"]+h)
                        page.draw_rect(r, color=color, width=1.5, dashes=ls)
                    elif d["type"] == "triangle":
                        p1, p2, p3 = fitz.Point(d["x"], d["y"]+h), fitz.Point(d["x"]-w, d["y"]-h), fitz.Point(d["x"]+w, d["y"]-h)
                        shape = page.new_shape()
                        shape.draw_polyline([p1, p2, p3, p1])
                        shape.finish(color=color, width=1.5, dashes=ls)
                        shape.commit()
                    elif d["type"] in ["line", "arrow"]:
                        p_start, p_end = fitz.Point(d["x"]-w, d["y"]), fitz.Point(d["x"]+w, d["y"])
                        shape = page.new_shape()
                        shape.draw_line(p_start, p_end)
                        shape.finish(color=color, width=1.5, dashes=ls)
                        shape.commit()
                    elif d["type"] == "star":
                        points = self.calculate_star_points(d["x"], d["y"], w, h, 5)
                        fitz_points = [fitz.Point(points[i], points[i+1]) for i in range(0, len(points), 2)]
                        fitz_points.append(fitz_points[0])
                        shape = page.new_shape()
                        shape.draw_polyline(fitz_points)
                        shape.finish(color=color, width=1.5, dashes=ls)
                        shape.commit()
            
            encrypt_method = fitz.PDF_ENCRYPT_AES_256 if user_pw else fitz.PDF_ENCRYPT_KEEP
            work_doc.save(path, garbage=4, deflate=True, encryption=encrypt_method, user_pw=user_pw, owner_pw=user_pw)
            
            if not silent: messagebox.showinfo("成功", "保存しました！")
        except Exception as e:
            if not silent: messagebox.showerror("エラー", f"保存失敗: {e}")
            else: raise e
        finally: work_doc.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFEditorApp(root)
    root.mainloop()