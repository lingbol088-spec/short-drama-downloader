"""短剧下载神器桌面版：Tkinter native GUI, no browser server."""
import csv
import json
import os
import queue
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, BooleanVar, StringVar, Tk, Toplevel, Label, messagebox, filedialog
from tkinter import ttk

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

import app as backend


APP_TITLE = "短剧下载神器 · 桌面版"
TASK_STORE = "desktop_tasks.json"


class DesktopApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x780")
        self.root.minsize(1080, 680)
        self.root.configure(bg="#eef6ff")

        self.bg_label = None
        self.bg_original = None
        self.bg_photo = None
        self.wallpaper_path = backend.RESOURCE_DIR / "static" / "assets" / "wallpaper.jpg"

        self.search_rows = []
        self.tasks = []
        self.task_queue = queue.Queue()
        self.running = False
        self.pause_requested = False

        self.keyword_var = StringVar(value="穿越")
        self.page_var = StringVar(value="1")
        self.source_var = StringVar(value="红果短剧")
        self.category_var = StringVar(value="穿越")

        self.device_var = StringVar()
        self.install_var = StringVar()
        self.platform_var = StringVar(value="android")

        self._build_ui()
        self._load_config_status()
        self._load_tasks()
        self._render_tasks()

    # ───────────────────────── UI ─────────────────────────
    def _apply_theme(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        base = "#f3f8ff"
        line = "#b9cde6"
        text = "#203d5b"
        accent = "#2f74c0"
        style.configure("TFrame", background=base)
        style.configure("TLabelframe", background=base, bordercolor=line, relief="solid")
        style.configure("TLabelframe.Label", background=base, foreground=text, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TLabel", background=base, foreground=text, font=("Microsoft YaHei UI", 9))
        style.configure("TButton", background="#e8f2ff", foreground=text, bordercolor=line, padding=(10, 6), font=("Microsoft YaHei UI", 9, "bold"))
        style.map("TButton", background=[("active", "#d6eaff")], foreground=[("active", accent)])
        style.configure("TEntry", fieldbackground="#ffffff", foreground=text, bordercolor=line, insertcolor=text)
        style.configure("TCombobox", fieldbackground="#ffffff", foreground=text, bordercolor=line)
        style.configure("TNotebook", background=base, borderwidth=0)
        style.configure("TNotebook.Tab", background="#e8f2ff", foreground=text, padding=(18, 8), font=("Microsoft YaHei UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", accent)])
        style.configure("Treeview", background="white", fieldbackground="white", foreground=text, rowheight=30, bordercolor=line, font=("Microsoft YaHei UI", 9))
        style.configure("Treeview.Heading", background="#dcecff", foreground="#244766", bordercolor=line, font=("Microsoft YaHei UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#2f74c0")], foreground=[("selected", "white")])

    def _setup_wallpaper(self):
        if Image is None or ImageTk is None or not self.wallpaper_path.exists():
            return
        try:
            self.bg_original = Image.open(self.wallpaper_path).convert("RGB")
            self.bg_label = Label(self.root, borderwidth=0, highlightthickness=0)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_label.lower()
            self.root.bind("<Configure>", self._resize_wallpaper)
            self.root.after(120, lambda: self._resize_wallpaper(None))
        except Exception as exc:
            print(f"[desktop] wallpaper load failed: {exc}")

    def _resize_wallpaper(self, event):
        if self.bg_original is None or self.bg_label is None:
            return
        w = max(self.root.winfo_width(), 1)
        h = max(self.root.winfo_height(), 1)
        if w < 100 or h < 100:
            return
        src_w, src_h = self.bg_original.size
        scale = max(w / src_w, h / src_h)
        nw, nh = int(src_w * scale), int(src_h * scale)
        img = self.bg_original.resize((nw, nh), Image.LANCZOS)
        left = max((nw - w) // 2, 0)
        top = max((nh - h) // 2, 0)
        img = img.crop((left, top, left + w, top + h))
        veil = Image.new("RGB", (w, h), "#eef6ff")
        img = Image.blend(img, veil, 0.38)
        self.bg_photo = ImageTk.PhotoImage(img)
        self.bg_label.configure(image=self.bg_photo)
        self.bg_label.lower()

    def _build_ui(self):
        self._apply_theme()
        self._setup_wallpaper()
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=(12, 10))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text=APP_TITLE, font=("Microsoft YaHei UI", 18, "bold")).pack(side=LEFT)

        self.nb = ttk.Notebook(self.root)
        self.nb.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.search_tab = ttk.Frame(self.nb)
        self.download_tab = ttk.Frame(self.nb)
        self.setting_tab = ttk.Frame(self.nb)
        self.nb.add(self.search_tab, text="全网搜索")
        self.nb.add(self.download_tab, text="下载任务")
        self.nb.add(self.setting_tab, text="设置")

        self._build_search_tab()
        self._build_download_tab()
        self._build_setting_tab()

    def _build_search_tab(self):
        tab = self.search_tab
        tab.rowconfigure(2, weight=1)
        tab.columnconfigure(0, weight=1)

        bar = ttk.LabelFrame(tab, text="搜索筛选区", padding=10)
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        for i in range(10):
            bar.columnconfigure(i, weight=0)
        bar.columnconfigure(1, weight=1)

        ttk.Label(bar, text="搜索关键词").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(bar, textvariable=self.keyword_var, width=30).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Label(bar, text="页码").grid(row=0, column=2, sticky="w")
        ttk.Entry(bar, textvariable=self.page_var, width=8).grid(row=0, column=3, padx=(4, 10))
        ttk.Label(bar, text="数据来源").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            bar,
            textvariable=self.source_var,
            values=["红果短剧", "红果漫剧", "爱奇艺短剧", "FlexTV", "熊猫短剧", "趣看看短剧", "全网聚合"],
            width=16,
            state="readonly",
        ).grid(row=0, column=5, padx=(4, 10))
        ttk.Button(bar, text="开始搜索", command=self.start_search).grid(row=0, column=6, padx=4)
        ttk.Button(bar, text="下载选中", command=self.add_selected_to_tasks).grid(row=0, column=7, padx=4)
        ttk.Button(bar, text="导出数据", command=self.export_search_csv).grid(row=0, column=8, padx=4)

        ttk.Label(bar, text="分类过滤").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(bar, textvariable=self.category_var).grid(row=1, column=1, columnspan=5, sticky="ew", pady=(10, 0), padx=(0, 10))
        ttk.Button(bar, text="清空列表", command=self.clear_search_rows).grid(row=1, column=6, pady=(10, 0), padx=4)
        ttk.Button(bar, text="打开详情", command=self.open_selected_source_url).grid(row=1, column=7, pady=(10, 0), padx=4)

        self.search_status = StringVar(value="红果短剧可返回真实 series_id；官网未公开上线时间时显示“官网未公开”。")
        ttk.Label(tab, textvariable=self.search_status, foreground="#666").grid(row=1, column=0, sticky="ew", padx=12)

        columns = ("idx", "author", "title", "drama_id", "episodes", "duration", "online_time", "category", "source", "source_url")
        self.search_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="extended")
        headings = {
            "idx": "序号", "author": "作者", "title": "剧名", "drama_id": "短剧ID", "episodes": "集数",
            "duration": "时长", "online_time": "上线时间", "category": "分类", "source": "来源", "source_url": "详情链接",
        }
        widths = {"idx": 55, "author": 110, "title": 230, "drama_id": 170, "episodes": 80, "duration": 220, "online_time": 110, "category": 170, "source": 120, "source_url": 280}
        for c in columns:
            self.search_tree.heading(c, text=headings[c])
            self.search_tree.column(c, width=widths[c], anchor="w")
        self.search_tree.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        self.search_tree.bind("<Double-1>", lambda e: self.add_selected_to_tasks())
        yscroll = ttk.Scrollbar(tab, orient="vertical", command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=2, column=1, sticky="ns", pady=8)

    def _build_download_tab(self):
        tab = self.download_tab
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        top = ttk.LabelFrame(tab, text="批量下载", padding=10)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        top.columnconfigure(0, weight=1)
        self.bulk_text = ttk.Entry(top)
        self.bulk_text.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.bulk_text.insert(0, "粘贴短剧ID，多个用逗号或空格分隔")
        ttk.Button(top, text="加入队列", command=self.add_bulk_to_tasks).grid(row=0, column=1, padx=4)
        ttk.Button(top, text="开始下载", command=self.start_download_queue).grid(row=0, column=2, padx=4)
        ttk.Button(top, text="暂停", command=self.pause_queue).grid(row=0, column=3, padx=4)
        ttk.Button(top, text="导出下载链接", command=self.export_tasks_csv).grid(row=0, column=4, padx=4)
        ttk.Button(top, text="清空任务", command=self.clear_tasks).grid(row=0, column=5, padx=4)
        ttk.Button(top, text="复制选中链接", command=self.copy_selected_task_url).grid(row=0, column=6, padx=4)

        columns = ("idx", "title", "id", "status", "url", "msg")
        self.task_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="extended")
        headings = {"idx": "序号", "title": "剧名", "id": "短剧ID", "status": "状态", "url": "下载链接", "msg": "说明"}
        widths = {"idx": 55, "title": 260, "id": 180, "status": 90, "url": 360, "msg": 300}
        for c in columns:
            self.task_tree.heading(c, text=headings[c])
            self.task_tree.column(c, width=widths[c], anchor="w")
        self.task_tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.task_tree.bind("<Double-1>", lambda e: self.copy_selected_task_url())
        yscroll = ttk.Scrollbar(tab, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=1, column=1, sticky="ns", pady=8)

        self.task_status = StringVar(value="等待任务")
        ttk.Label(tab, textvariable=self.task_status, foreground="#666").grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

    def _build_setting_tab(self):
        tab = self.setting_tab
        frm = ttk.LabelFrame(tab, text="本机配置", padding=16)
        frm.pack(fill=X, padx=12, pady=12)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="device_id").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(frm, textvariable=self.device_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(frm, text="install_id").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(frm, textvariable=self.install_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(frm, text="platform").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(frm, textvariable=self.platform_var, values=["android", "ios"], state="readonly", width=12).grid(row=2, column=1, sticky="w", pady=6)
        ttk.Button(frm, text="保存配置", command=self.save_config).grid(row=3, column=1, sticky="w", pady=12)

        self.config_status = StringVar(value="")
        ttk.Label(tab, textvariable=self.config_status, foreground="#666").pack(fill=X, padx=16)

    # ───────────────────────── 搜索 ─────────────────────────
    def start_search(self):
        self.search_status.set("搜索中...")
        threading.Thread(target=self._search_worker, daemon=True).start()

    def _search_worker(self):
        try:
            items = backend.search_short_drama(
                self.keyword_var.get().strip(),
                int(self.page_var.get() or "1"),
                self.source_var.get().strip(),
                self.category_var.get().strip(),
            )
            self.root.after(0, lambda: self._set_search_rows(items))
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("搜索失败", str(exc)))
            self.root.after(0, lambda: self.search_status.set("搜索失败"))

    def _set_search_rows(self, items):
        self.search_rows = list(items or [])
        self.search_tree.delete(*self.search_tree.get_children())
        for i, item in enumerate(self.search_rows, 1):
            self.search_tree.insert("", END, iid=str(i - 1), values=(
                i,
                item.get("author") or item.get("source") or "",
                item.get("title", ""),
                item.get("drama_id", ""),
                item.get("episodes", ""),
                item.get("duration", ""),
                item.get("online_time", ""),
                item.get("category", ""),
                item.get("source", ""),
                item.get("source_url", ""),
            ))
        self.search_status.set(f"搜索完成：{len(self.search_rows)} 条。双击可加入下载队列；非红果结果通常只有详情链接。")

    def selected_search_items(self):
        out = []
        for iid in self.search_tree.selection():
            idx = int(iid)
            if 0 <= idx < len(self.search_rows):
                out.append(self.search_rows[idx])
        return out

    def clear_search_rows(self):
        self.search_rows = []
        self.search_tree.delete(*self.search_tree.get_children())
        self.search_status.set("已清空")

    def open_selected_source_url(self):
        items = self.selected_search_items()
        if not items:
            messagebox.showinfo("提示", "请先选择一条结果")
            return
        url = items[0].get("source_url")
        if url:
            webbrowser.open(url)

    # ───────────────────────── 任务 ─────────────────────────
    def add_selected_to_tasks(self):
        items = self.selected_search_items()
        if not items:
            messagebox.showinfo("提示", "请先选择搜索结果")
            return
        added, skipped = 0, 0
        for item in items:
            did = str(item.get("drama_id") or "").strip()
            if not did or item.get("downloadable") is False:
                skipped += 1
                continue
            if any(t["id"] == did for t in self.tasks):
                continue
            self.tasks.append({"title": item.get("title") or did, "id": did, "status": "等待", "url": "", "msg": "等待下载"})
            added += 1
        self._save_tasks()
        self._render_tasks()
        self.nb.select(self.download_tab)
        messagebox.showinfo("加入队列", f"已加入 {added} 个任务，跳过 {skipped} 个不可直接下载结果")

    def add_bulk_to_tasks(self):
        raw = self.bulk_text.get().strip()
        ids = [x.strip() for x in raw.replace("，", ",").replace(";", ",").replace("；", ",").replace("\n", ",").replace(" ", ",").split(",") if x.strip()]
        added = 0
        for did in ids:
            if any(t["id"] == did for t in self.tasks):
                continue
            self.tasks.append({"title": did, "id": did, "status": "等待", "url": "", "msg": "等待下载"})
            added += 1
        self._save_tasks()
        self._render_tasks()
        messagebox.showinfo("加入队列", f"已加入 {added} 个任务")

    def start_download_queue(self):
        if self.running:
            return
        self.running = True
        self.pause_requested = False
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        for task in self.tasks:
            if self.pause_requested:
                break
            if task.get("status") == "完成":
                continue
            task["status"] = "下载中"
            task["msg"] = "正在解析并下载..."
            self.root.after(0, self._render_tasks)
            try:
                result = backend.handle_video_request(task["id"], None, max_retries=3)
                task["url"] = result.get("url") or result.get("download_url") or ""
                task["status"] = "完成"
                task["msg"] = "完成" if task["url"] else "解析完成但未返回链接"
            except Exception as exc:
                task["status"] = "失败"
                task["msg"] = str(exc)
            self._save_tasks()
            self.root.after(0, self._render_tasks)
        self.running = False
        self.root.after(0, self._render_tasks)

    def pause_queue(self):
        self.pause_requested = True
        self.task_status.set("已请求暂停，当前任务结束后停止")

    def clear_tasks(self):
        if messagebox.askyesno("确认", "确定清空所有下载任务和已保存链接？"):
            self.tasks = []
            self._save_tasks()
            self._render_tasks()

    def _render_tasks(self):
        self.task_tree.delete(*self.task_tree.get_children())
        for i, t in enumerate(self.tasks, 1):
            self.task_tree.insert("", END, iid=str(i - 1), values=(i, t.get("title", ""), t.get("id", ""), t.get("status", ""), t.get("url", ""), t.get("msg", "")))
        done = sum(1 for t in self.tasks if t.get("status") == "完成")
        fail = sum(1 for t in self.tasks if t.get("status") == "失败")
        self.task_status.set(f"共 {len(self.tasks)} 个任务，完成 {done} 个，失败 {fail} 个")

    def copy_selected_task_url(self):
        sel = self.task_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择任务")
            return
        urls = []
        for iid in sel:
            idx = int(iid)
            if 0 <= idx < len(self.tasks) and self.tasks[idx].get("url"):
                urls.append(self.tasks[idx]["url"])
        if not urls:
            messagebox.showinfo("提示", "选中任务还没有下载链接")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(urls))
        messagebox.showinfo("复制成功", f"已复制 {len(urls)} 条下载链接")

    # ───────────────────────── 配置/导出 ─────────────────────────
    def _task_store_path(self) -> Path:
        return backend.parser_module.get_runtime_base_dir() / TASK_STORE

    def _load_tasks(self):
        path = self._task_store_path()
        if path.exists():
            try:
                self.tasks = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.tasks = []

    def _save_tasks(self):
        try:
            self._task_store_path().write_text(json.dumps(self.tasks, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_config_status(self):
        cfg = backend.read_local_config()
        self.platform_var.set(str(cfg.get("platform") or "android"))
        configured = bool((os.getenv("DUANJU_DEVICE_ID") or cfg.get("device_id")) and (os.getenv("DUANJU_INSTALL_ID") or cfg.get("install_id")))
        self.config_status.set(f"配置文件：{backend.get_config_path()}；当前状态：{'已配置' if configured else '未配置'}")

    def save_config(self):
        device_id = self.device_var.get().strip()
        install_id = self.install_var.get().strip()
        if not device_id or not install_id:
            messagebox.showwarning("缺少配置", "请填写 device_id 和 install_id")
            return
        backend.get_config_path().write_text(json.dumps({"device_id": device_id, "install_id": install_id, "platform": self.platform_var.get() or "android"}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.device_var.set("")
        self.install_var.set("")
        self._load_config_status()
        messagebox.showinfo("保存成功", "配置已保存")

    def export_search_csv(self):
        if not self.search_rows:
            messagebox.showinfo("提示", "没有搜索结果可导出")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")], initialfile="短剧搜索结果_含链接.csv")
        if not path:
            return
        fields = ["author", "title", "drama_id", "episodes", "duration", "online_time", "category", "source", "source_url", "downloadable"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in self.search_rows:
                w.writerow({k: row.get(k, "") for k in fields})
        messagebox.showinfo("导出成功", path)

    def export_tasks_csv(self):
        if not self.tasks:
            messagebox.showinfo("提示", "没有任务可导出")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")], initialfile="短剧下载链接.csv")
        if not path:
            return
        fields = ["title", "id", "status", "url", "msg"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in self.tasks:
                w.writerow({k: row.get(k, "") for k in fields})
        messagebox.showinfo("导出成功", path)


def main():
    root = Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

