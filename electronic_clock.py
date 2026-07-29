# -*- coding: utf-8 -*-

import tkinter as tk
import urllib.request
import urllib.error
import json
import threading
import time
import random
import os
import re

from datetime import datetime, timezone, timedelta
from PIL import Image, ImageTk


# ============================================================
# 配置
# ============================================================

# 是否显示祝福语正文
ZFY = False

# 是否显示祝福语阴影
ZFYY = False

# 是否启动时进入全屏屏保模式
SCREEN_SAVER_MODE = True

# 全屏时隐藏鼠标
HIDE_MOUSE_CURSOR = True

# 全屏时窗口置顶
SCREEN_SAVER_TOPMOST = True

# 本机 Flask JSON 时间接口
TIME_API_URL = "http://[::1]:5000/api/time"

# 北京时间
BEIJING_TIMEZONE = timezone(timedelta(hours=8))

# 每 60 秒同步一次
SYNC_INTERVAL = 60 * 1000

# 每 100 毫秒更新一次显示
DISPLAY_INTERVAL = 100

# 普通文字文件
CONTENT_FILE = "content.txt"

# 节日祝福文件
HOLIDAY_FILE = "holiday.txt"

# 普通背景目录
BACKGROUND_DIR = "backgrounds"

# 节日背景总目录
HOLIDAY_BACKGROUND_DIR = "holiday_images"

# 背景图片切换间隔
BACKGROUND_SWITCH_INTERVAL = 10 * 1000

# 背景切换方式：
# none   直接切换
# fade   淡入淡出
# slide  左右滑动
# random 随机切换
BACKGROUND_STYLE = "fade"

# 是否随机排列背景图片
RANDOM_BACKGROUND_ORDER = False

# 状态文字显示 2 秒
STATUS_HIDE_TIME = 2000

# 支持的图片格式
IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp"
)


# ============================================================
# 电子时钟
# ============================================================

class ElectronicClock(object):

    def __init__(self, root):

        self.root = root

        self.root.title("|")
        self.root.geometry("760x420")
        self.root.minsize(600, 320)
        self.root.configure(bg="#101820")

        # 基本状态
        self.running = True
        self.syncing = False
        self.time_offset = 0.0

        # 状态文字任务
        self.status_hide_job = None

        # 内容日期
        self.current_content_date = None

        # 背景图片状态
        self.background_images = []
        self.background_index = 0
        self.background_date = None
        self.background_pil = None
        self.background_photo = None
        self.current_background_path = None

        # 背景任务
        self.background_switch_job = None
        self.background_transition_job = None

        # 动画状态
        self.transition_old_image = None
        self.transition_new_image = None
        self.transition_step = 0
        self.transition_total_steps = 12

        # 窗口大小
        self.last_window_width = 0
        self.last_window_height = 0

        # 自动创建文件夹和配置文件
        self.create_default_files()

        # 读取普通文字
        self.random_content = self.load_random_content()

        # 创建界面
        self.create_widgets()

        # 绑定快捷键
        self.root.bind(
            "<Escape>",
            self.exit_fullscreen
        )

        self.root.bind(
            "<F11>",
            self.toggle_fullscreen
        )

        self.root.bind(
            "<Control-q>",
            self.exit_program
        )

        self.root.bind(
            "<Button-1>",
            self.focus_window
        )

        self.root.bind(
            "<Configure>",
            self.on_window_resize
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

        # 先更新窗口尺寸
        self.root.update_idletasks()

        # 启动屏保全屏
        if SCREEN_SAVER_MODE:
            self.enter_fullscreen()

        # 加载当天背景
        now = datetime.now(
            BEIJING_TIMEZONE
        )

        self.load_background_for_date(now)

        # 立即同步
        self.sync_time()

        # 启动时钟
        self.update_clock()

        # 安排下一次同步
        self.schedule_next_sync()

    # ========================================================
    # 创建界面
    # ========================================================

    def create_widgets(self):

        # Canvas 作为背景和文字的共同画布
        self.canvas = tk.Canvas(
            self.root,
            bg="#101820",
            bd=0,
            highlightthickness=0
        )

        self.canvas.pack(
            fill=tk.BOTH,
            expand=True
        )

        # 背景图片
        self.background_canvas_item = (
            self.canvas.create_image(
                0,
                0,
                anchor="nw"
            )
        )

        # 时间阴影
        self.time_shadow_item = (
            self.canvas.create_text(
                380,
                110,
                text="00:00:00",
                font=("Consolas", 62, "bold"),
                fill="#000000",
                anchor="center"
            )
        )

        # 时间
        self.time_text_item = (
            self.canvas.create_text(
                378,
                106,
                text="00:00:00",
                font=("Consolas", 62, "bold"),
                fill="#00ff99",
                anchor="center"
            )
        )

        # 日期
        self.date_text_item = (
            self.canvas.create_text(
                380,
                190,
                text="正在获取日期...",
                font=("Microsoft YaHei", 17),
                fill="#ffffff",
                anchor="center"
            )
        )

        # 祝福语阴影
        self.message_shadow_item = (
            self.canvas.create_text(
                382,
                245,
                text=self.random_content,
                font=("Microsoft YaHei", 18, "bold"),
                fill="#000000",
                anchor="center"
            )
        )

        # 祝福语正文
        self.message_text_item = (
            self.canvas.create_text(
                380,
                241,
                text=self.random_content,
                font=("Microsoft YaHei", 18, "bold"),
                fill="#ffd166",
                anchor="center"
            )
        )

        # 状态文字
        self.status_text_item = (
            self.canvas.create_text(
                380,
                290,
                text="",
                font=("Microsoft YaHei", 9),
                fill="#ffd166",
                anchor="center"
            )
        )

        self.update_message_visibility()
        self.raise_text_items()

    # ========================================================
    # 全屏控制
    # ========================================================

    def enter_fullscreen(self, event=None):

        try:

            self.root.attributes(
                "-fullscreen",
                True
            )

            if SCREEN_SAVER_TOPMOST:
                self.root.attributes(
                    "-topmost",
                    True
                )

            if HIDE_MOUSE_CURSOR:
                self.root.configure(
                    cursor="none"
                )

            self.root.update_idletasks()
            self.root.focus_force()

            self.update_text_positions(
                self.root.winfo_width(),
                self.root.winfo_height()
            )

            self.resize_background_image()

        except Exception as error:

            print(
                "进入全屏失败：{}".format(error)
            )

        return "break"

    def exit_fullscreen(self, event=None):

        try:

            self.root.attributes(
                "-fullscreen",
                False
            )

            self.root.attributes(
                "-topmost",
                False
            )

            self.root.configure(
                cursor=""
            )

            self.root.geometry("760x420")
            self.root.minsize(600, 320)
            self.root.focus_force()

        except Exception as error:

            print(
                "退出全屏失败：{}".format(error)
            )

        return "break"

    def toggle_fullscreen(self, event=None):

        try:

            fullscreen = self.root.attributes(
                "-fullscreen"
            )

            if fullscreen:
                self.exit_fullscreen()
            else:
                self.enter_fullscreen()

        except Exception as error:

            print(
                "切换全屏失败：{}".format(error)
            )

        return "break"

    def focus_window(self, event=None):

        try:
            self.root.focus_force()
        except Exception:
            pass

    def exit_program(self, event=None):

        self.on_close()
        return "break"

    # ========================================================
    # 祝福语显示控制
    # ========================================================

    def update_message_visibility(self):

        self.canvas.itemconfig(
            self.message_text_item,
            state="normal" if ZFY else "hidden"
        )

        self.canvas.itemconfig(
            self.message_shadow_item,
            state="normal" if ZFYY else "hidden"
        )

    # ========================================================
    # 调整文字层级
    # ========================================================

    def raise_text_items(self):

        self.canvas.tag_lower(
            self.background_canvas_item
        )

        for item in (
            self.time_shadow_item,
            self.time_text_item,
            self.date_text_item,
            self.message_shadow_item,
            self.message_text_item,
            self.status_text_item
        ):
            self.canvas.tag_raise(item)

        self.update_message_visibility()

    # ========================================================
    # 调整文字位置
    # ========================================================

    def update_text_positions(self, width, height):

        if width <= 1:
            width = 760

        if height <= 1:
            height = 420

        center_x = int(width / 2)

        time_y = int(height * 0.28)
        date_y = int(height * 0.49)
        message_y = int(height * 0.65)
        status_y = int(height * 0.77)

        self.canvas.coords(
            self.time_shadow_item,
            center_x + 2,
            time_y + 3
        )

        self.canvas.coords(
            self.time_text_item,
            center_x,
            time_y
        )

        self.canvas.coords(
            self.date_text_item,
            center_x,
            date_y
        )

        self.canvas.coords(
            self.message_shadow_item,
            center_x + 2,
            message_y + 3
        )

        self.canvas.coords(
            self.message_text_item,
            center_x,
            message_y
        )

        self.canvas.coords(
            self.status_text_item,
            center_x,
            status_y
        )

        self.update_message_visibility()

    # ========================================================
    # 状态文字
    # ========================================================

    def show_status(
        self,
        text,
        color="#ffd166",
        hide_after=STATUS_HIDE_TIME
    ):

        if self.status_hide_job is not None:

            try:
                self.root.after_cancel(
                    self.status_hide_job
                )
            except Exception:
                pass

            self.status_hide_job = None

        self.canvas.itemconfig(
            self.status_text_item,
            text=text,
            fill=color,
            state="normal"
        )

        if hide_after is not None:

            self.status_hide_job = self.root.after(
                hide_after,
                self.hide_status
            )

    def hide_status(self):

        if self.running:

            self.canvas.itemconfig(
                self.status_text_item,
                text=""
            )

        self.status_hide_job = None

    # ========================================================
    # 自动创建文件和文件夹
    # ========================================================

    def create_default_files(self):

        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        try:

            normal_dir = os.path.join(
                base_dir,
                BACKGROUND_DIR
            )

            holiday_dir = os.path.join(
                base_dir,
                HOLIDAY_BACKGROUND_DIR
            )

            if not os.path.exists(normal_dir):
                os.makedirs(normal_dir)

            if not os.path.exists(holiday_dir):
                os.makedirs(holiday_dir)

            content_path = os.path.join(
                base_dir,
                CONTENT_FILE
            )

            if not os.path.exists(content_path):

                with open(
                    content_path,
                    "w",
                    encoding="utf-8"
                ) as file:

                    file.write(
                        "# 每行一条普通文字\n"
                    )
                    file.write("祝你每天开心\n")
                    file.write("愿你平安顺遂\n")
                    file.write("新的一天，加油\n")
                    file.write("生活愉快，万事如意\n")

            holiday_path = os.path.join(
                base_dir,
                HOLIDAY_FILE
            )

            if not os.path.exists(holiday_path):

                with open(
                    holiday_path,
                    "w",
                    encoding="utf-8"
                ) as file:

                    file.write(
                        "# 格式：[月/日,\"祝福语\"]\n"
                    )
                    file.write(
                        "[01/01,\"元旦快乐\"]\n"
                    )
                    file.write(
                        "[02/14,\"情人节快乐\"]\n"
                    )
                    file.write(
                        "[03/08,\"妇女节快乐\"]\n"
                    )
                    file.write(
                        "[05/01,\"劳动节快乐\"]\n"
                    )
                    file.write(
                        "[06/01,\"儿童节快乐\"]\n"
                    )
                    file.write(
                        "[09/10,\"老师节日快乐\"]\n"
                    )
                    file.write(
                        "[10/01,\"国庆节快乐\"]\n"
                    )
                    file.write(
                        "[12/21,\"冬至快乐\"]\n"
                    )
                    file.write(
                        "[12/25,\"圣诞节快乐\"]\n"
                    )

        except Exception as error:

            print(
                "自动创建文件失败：{}".format(error)
            )

    # ========================================================
    # 读取普通文字
    # ========================================================

    def load_random_content(self):

        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        path = os.path.join(
            base_dir,
            CONTENT_FILE
        )

        try:

            contents = []

            with open(
                path,
                "r",
                encoding="utf-8-sig"
            ) as file:

                for line in file:

                    line = line.strip()

                    if line and not line.startswith("#"):
                        contents.append(line)

            if contents:
                return random.choice(contents)

        except Exception as error:

            print(
                "读取 content.txt 失败：{}".format(error)
            )

        return "欢迎使用电子时钟"

    # ========================================================
    # 读取节日祝福
    # ========================================================

    def load_holiday_content(self, month, day):

        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        path = os.path.join(
            base_dir,
            HOLIDAY_FILE
        )

        try:

            with open(
                path,
                "r",
                encoding="utf-8-sig"
            ) as file:

                for line in file:

                    line = line.strip()

                    if not line or line.startswith("#"):
                        continue

                    pattern = (
                        r'^\s*\[\s*'
                        r'(\d{1,2})\s*/\s*'
                        r'(\d{1,2})\s*,\s*'
                        r'["“](.*?)["”]'
                        r'\s*\]\s*$'
                    )

                    result = re.match(
                        pattern,
                        line
                    )

                    if not result:
                        continue

                    m = int(result.group(1))
                    d = int(result.group(2))
                    text = result.group(3).strip()

                    if m == month and d == day and text:
                        return text

        except Exception as error:

            print(
                "读取 holiday.txt 失败：{}".format(error)
            )

        return None

    def get_today_content(self, current_datetime):

        holiday = self.load_holiday_content(
            current_datetime.month,
            current_datetime.day
        )

        if holiday:
            return holiday

        return self.load_random_content()

    # ========================================================
    # 图片文件
    # ========================================================

    def get_image_files(self, folder):

        result = []

        if not os.path.isdir(folder):
            return result

        try:

            for name in os.listdir(folder):

                path = os.path.join(
                    folder,
                    name
                )

                if (
                    os.path.isfile(path)
                    and name.lower().endswith(
                        IMAGE_EXTENSIONS
                    )
                ):
                    result.append(path)

        except Exception as error:

            print(
                "读取图片失败：{}".format(error)
            )

        result.sort()

        if RANDOM_BACKGROUND_ORDER:
            random.shuffle(result)

        return result

    def get_today_background_images(
        self,
        current_datetime
    ):

        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        date_folder = "{:02d}-{:02d}".format(
            current_datetime.month,
            current_datetime.day
        )

        holiday_folder = os.path.join(
            base_dir,
            HOLIDAY_BACKGROUND_DIR,
            date_folder
        )

        holiday_images = self.get_image_files(
            holiday_folder
        )

        if holiday_images:
            return holiday_folder, holiday_images

        normal_folder = os.path.join(
            base_dir,
            BACKGROUND_DIR
        )

        return (
            normal_folder,
            self.get_image_files(normal_folder)
        )

    def load_background_for_date(
        self,
        current_datetime
    ):

        date_value = (
            current_datetime.year,
            current_datetime.month,
            current_datetime.day
        )

        if date_value == self.background_date:
            return

        self.background_date = date_value

        folder, images = (
            self.get_today_background_images(
                current_datetime
            )
        )

        self.background_images = images
        self.background_index = 0

        if not images:

            self.background_pil = None
            self.background_photo = None

            self.canvas.itemconfig(
                self.background_canvas_item,
                image=""
            )

            self.canvas.configure(
                bg="#101820"
            )

            print(
                "没有找到背景图片：{}".format(folder)
            )

            return

        print(
            "使用背景图片目录：{}".format(folder)
        )

        self.show_background_image(images[0])
        self.schedule_background_switch()

    # ========================================================
    # 图片缩放
    # ========================================================

    def fit_image_to_window(
        self,
        image,
        width,
        height
    ):

        source_width, source_height = image.size

        if source_width <= 0:
            source_width = 1

        if source_height <= 0:
            source_height = 1

        scale = max(
            float(width) / source_width,
            float(height) / source_height
        )

        new_width = max(
            1,
            int(source_width * scale)
        )

        new_height = max(
            1,
            int(source_height * scale)
        )

        resized = image.resize(
            (new_width, new_height),
            Image.LANCZOS
        )

        left = max(
            0,
            int((new_width - width) / 2)
        )

        top = max(
            0,
            int((new_height - height) / 2)
        )

        return resized.crop(
            (
                left,
                top,
                left + width,
                top + height
            )
        )

    def prepare_display_image(self, image):

        width = self.root.winfo_width()
        height = self.root.winfo_height()

        if width <= 1:
            width = 760

        if height <= 1:
            height = 420

        return self.fit_image_to_window(
            image,
            width,
            height
        )

    def show_background_image(self, path):

        try:

            self.background_pil = Image.open(
                path
            ).convert("RGB")

            self.current_background_path = path
            self.resize_background_image()

        except Exception as error:

            print(
                "打开背景图片失败：{}".format(error)
            )

    def resize_background_image(self):

        if self.background_pil is None:
            return

        width = self.root.winfo_width()
        height = self.root.winfo_height()

        if width <= 1:
            width = 760

        if height <= 1:
            height = 420

        try:

            image = self.fit_image_to_window(
                self.background_pil,
                width,
                height
            )

            self.background_photo = ImageTk.PhotoImage(
                image
            )

            self.canvas.itemconfig(
                self.background_canvas_item,
                image=self.background_photo
            )

            self.canvas.coords(
                self.background_canvas_item,
                0,
                0
            )

            self.canvas.tag_lower(
                self.background_canvas_item
            )

            self.update_text_positions(
                width,
                height
            )

            self.raise_text_items()

        except Exception as error:

            print(
                "缩放背景失败：{}".format(error)
            )

    # ========================================================
    # 窗口大小变化
    # ========================================================

    def on_window_resize(self, event):

        if event.widget != self.root:
            return

        if event.width <= 1 or event.height <= 1:
            return

        self.last_window_width = event.width
        self.last_window_height = event.height

        self.update_text_positions(
            event.width,
            event.height
        )

        if self.background_transition_job is None:
            self.resize_background_image()

    # ========================================================
    # 背景切换任务
    # ========================================================

    def schedule_background_switch(self):

        if (
            not self.running
            or len(self.background_images) <= 1
        ):
            return

        if self.background_switch_job is not None:

            try:
                self.root.after_cancel(
                    self.background_switch_job
                )
            except Exception:
                pass

        self.background_switch_job = self.root.after(
            BACKGROUND_SWITCH_INTERVAL,
            self.switch_background_image
        )

    def switch_background_image(self):

        if (
            not self.running
            or len(self.background_images) <= 1
        ):
            return

        old_path = self.background_images[
            self.background_index
        ]

        self.background_index += 1

        if (
            self.background_index
            >= len(self.background_images)
        ):
            self.background_index = 0

        new_path = self.background_images[
            self.background_index
        ]

        style = BACKGROUND_STYLE.lower()

        if style == "random":
            style = random.choice(
                ["none", "fade", "slide"]
            )

        if style == "fade":
            self.fade_to_image(
                old_path,
                new_path
            )

        elif style == "slide":
            self.slide_to_image(
                old_path,
                new_path
            )

        else:
            self.show_background_image(
                new_path
            )

        self.schedule_background_switch()

    # ========================================================
    # 淡入淡出动画
    # ========================================================

    def fade_to_image(self, old_path, new_path):

        try:

            old_image = self.prepare_display_image(
                Image.open(old_path).convert("RGB")
            )

            new_image = self.prepare_display_image(
                Image.open(new_path).convert("RGB")
            )

            self.transition_old_image = old_image
            self.transition_new_image = new_image
            self.transition_step = 0

            self.run_fade_step()

        except Exception as error:

            print(
                "淡入淡出失败：{}".format(error)
            )

            self.show_background_image(new_path)

    def run_fade_step(self):

        if not self.running:
            return

        if (
            self.transition_old_image is None
            or self.transition_new_image is None
        ):
            return

        if (
            self.transition_step
            > self.transition_total_steps
        ):

            self.background_pil = (
                self.transition_new_image
            )

            self.background_transition_job = None
            self.resize_background_image()

            return

        ratio = (
            float(self.transition_step)
            / float(self.transition_total_steps)
        )

        image = Image.blend(
            self.transition_old_image,
            self.transition_new_image,
            ratio
        )

        self.background_photo = ImageTk.PhotoImage(
            image
        )

        self.canvas.itemconfig(
            self.background_canvas_item,
            image=self.background_photo
        )

        self.raise_text_items()

        self.transition_step += 1

        self.background_transition_job = self.root.after(
            60,
            self.run_fade_step
        )

    # ========================================================
    # 左右滑动动画
    # ========================================================

    def slide_to_image(self, old_path, new_path):

        try:

            self.transition_old_image = (
                self.prepare_display_image(
                    Image.open(old_path).convert("RGB")
                )
            )

            self.transition_new_image = (
                self.prepare_display_image(
                    Image.open(new_path).convert("RGB")
                )
            )

            self.transition_step = 0

            self.run_slide_step()

        except Exception as error:

            print(
                "滑动切换失败：{}".format(error)
            )

            self.show_background_image(new_path)

    def run_slide_step(self):

        if not self.running:
            return

        if (
            self.transition_old_image is None
            or self.transition_new_image is None
        ):
            return

        width = self.root.winfo_width()
        height = self.root.winfo_height()

        if width <= 1:
            width = 760

        if height <= 1:
            height = 420

        if (
            self.transition_step
            > self.transition_total_steps
        ):

            self.background_pil = (
                self.transition_new_image
            )

            self.background_transition_job = None
            self.resize_background_image()

            return

        ratio = (
            float(self.transition_step)
            / float(self.transition_total_steps)
        )

        offset = int(width * ratio)

        frame = Image.new(
            "RGB",
            (width, height),
            "#101820"
        )

        frame.paste(
            self.transition_old_image,
            (-offset, 0)
        )

        frame.paste(
            self.transition_new_image,
            (width - offset, 0)
        )

        self.background_photo = ImageTk.PhotoImage(
            frame
        )

        self.canvas.itemconfig(
            self.background_canvas_item,
            image=self.background_photo
        )

        self.raise_text_items()

        self.transition_step += 1

        self.background_transition_job = self.root.after(
            45,
            self.run_slide_step
        )

    # ========================================================
    # 请求 JSON 时间
    # ========================================================

    def request_json_time(self):

        request = urllib.request.Request(
            TIME_API_URL,
            headers={
                "User-Agent": "ElectronicClock/1.0"
            }
        )

        response = urllib.request.urlopen(
            request,
            timeout=8
        )

        data = json.loads(
            response.read().decode("utf-8")
        )

        timestamp = data.get("timestamp")

        if timestamp is not None:

            timestamp = float(timestamp)

            if timestamp > 100000000000:
                timestamp /= 1000.0

            return data, timestamp

        date_text = (
            data.get("dateTime")
            or data.get("datetime")
            or data.get("date_time")
            or data.get("time")
        )

        if not date_text:
            raise ValueError(
                "JSON 中没有时间字段"
            )

        date_text = str(date_text).strip()

        if date_text.endswith("Z"):
            date_text = (
                date_text[:-1]
                + "+00:00"
            )

        server_datetime = datetime.fromisoformat(
            date_text
        )

        if server_datetime.tzinfo is None:

            server_datetime = server_datetime.replace(
                tzinfo=BEIJING_TIMEZONE
            )

        return data, server_datetime.timestamp()

    # ========================================================
    # 同步时间
    # ========================================================

    def sync_time(self):

        if self.syncing:
            return

        self.syncing = True

        self.show_status(
            "正在同步 JSON 时间...",
            "#ffd166",
            None
        )

        thread = threading.Thread(
            target=self.sync_thread
        )

        thread.daemon = True
        thread.start()

    def sync_thread(self):

        try:

            data, timestamp = (
                self.request_json_time()
            )

            offset = timestamp - time.time()

            self.root.after(
                0,
                lambda value=offset, result=data:
                    self.sync_success(
                        value,
                        result
                    )
            )

        except urllib.error.HTTPError as error:

            message = "HTTP 错误：{} {}".format(
                error.code,
                error.reason
            )

            self.root.after(
                0,
                lambda text=message:
                    self.sync_failed(text)
            )

        except urllib.error.URLError as error:

            message = "网络连接失败：{}".format(
                str(error)
            )

            self.root.after(
                0,
                lambda text=message:
                    self.sync_failed(text)
            )

        except Exception as error:

            message = "同步失败：{}".format(
                str(error)
            )

            self.root.after(
                0,
                lambda text=message:
                    self.sync_failed(text)
            )

    def sync_success(self, offset, data):

        self.time_offset = offset
        self.syncing = False

        server_name = data.get(
            "timeZone",
            data.get(
                "timezone",
                "Asia/Shanghai"
            )
        )

        self.show_status(
            "已同步：{}    偏差：{:.3f} 秒".format(
                server_name,
                offset
            ),
            "#00ff99",
            STATUS_HIDE_TIME
        )

    def sync_failed(self, error_text):

        self.syncing = False

        self.show_status(
            "同步失败，当前使用本机时间",
            "#ff7777",
            STATUS_HIDE_TIME
        )

        print(error_text)

    # ========================================================
    # 每分钟同步
    # ========================================================

    def schedule_next_sync(self):

        if not self.running:
            return

        self.root.after(
            SYNC_INTERVAL,
            self.run_scheduled_sync
        )

    def run_scheduled_sync(self):

        if not self.running:
            return

        self.sync_time()
        self.schedule_next_sync()

    # ========================================================
    # 更新时钟
    # ========================================================

    def update_clock(self):

        if not self.running:
            return

        timestamp = (
            time.time()
            + self.time_offset
        )

        current = datetime.fromtimestamp(
            timestamp,
            BEIJING_TIMEZONE
        )

        self.canvas.itemconfig(
            self.time_text_item,
            text=current.strftime("%H:%M:%S")
        )

        self.canvas.itemconfig(
            self.time_shadow_item,
            text=current.strftime("%H:%M:%S")
        )

        weekday = {
            0: "星期一",
            1: "星期二",
            2: "星期三",
            3: "星期四",
            4: "星期五",
            5: "星期六",
            6: "星期日"
        }[current.weekday()]

        date_text = "{}年{}月{}日  {}".format(
            current.year,
            current.month,
            current.day,
            weekday
        )

        self.canvas.itemconfig(
            self.date_text_item,
            text=date_text
        )

        today = (
            current.year,
            current.month,
            current.day
        )

        if today != self.current_content_date:

            self.current_content_date = today

            message = self.get_today_content(
                current
            )

            self.canvas.itemconfig(
                self.message_text_item,
                text=message
            )

            self.canvas.itemconfig(
                self.message_shadow_item,
                text=message
            )

            self.update_message_visibility()

        self.load_background_for_date(current)

        self.root.after(
            DISPLAY_INTERVAL,
            self.update_clock
        )

    # ========================================================
    # 窗口关闭
    # ========================================================

    def on_close(self):

        self.running = False

        for job_name in (
            "status_hide_job",
            "background_switch_job",
            "background_transition_job"
        ):

            job = getattr(
                self,
                job_name,
                None
            )

            if job is not None:

                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass

                setattr(
                    self,
                    job_name,
                    None
                )

        try:

            self.root.attributes(
                "-fullscreen",
                False
            )

            self.root.attributes(
                "-topmost",
                False
            )

            self.root.configure(
                cursor=""
            )

        except Exception:
            pass

        self.root.destroy()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = ElectronicClock(root)

    root.mainloop()
