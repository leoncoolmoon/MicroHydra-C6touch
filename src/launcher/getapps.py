"""This app lets you download new apps from the MicroHydra apps repo.

This built-in app was partially inspired by RealClearwave's "AppStore.py",
which was contributed to the MH apps repo with commit 014f080.
Thank you for your contributions!
"""

import ujson as json
import os
import sys
import time

import machine
import network
import requests
import gc
from lib.device import Device
from lib.hydra.config import Config
from lib.hydra.i18n import I18n
from lib.hydra.simpleterminal import SimpleTerminal
from lib.zipextractor import ZipExtractor

# ===== 内存监控工具 =====
def log_memory(stage: str):
    """记录内存使用情况"""
    gc.collect()
    free = gc.mem_free()
    alloc = gc.mem_alloc()
    total = free + alloc
    print(f"[MEM] {stage}: free={free}, alloc={alloc}, total={total}")
    return free

# 启动内存
log_memory("启动")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ _CONSTANTS: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
_MH_DISPLAY_HEIGHT = const(135)
_MH_DISPLAY_WIDTH = const(240)
_DISPLAY_WIDTH_HALF = const(_MH_DISPLAY_WIDTH // 2)

_CHAR_WIDTH = const(8)
_CHAR_WIDTH_HALF = const(_CHAR_WIDTH // 2)

_RETRYS = 30

_TRANS = const("""[
{"en": "Enabling wifi...", "zh": "正在启用wifi...", "ja": "WiFiを有効にしています..."},
{"en": "Connected!", "zh": "已连接!", "ja": "接続されました!"},
{"en": "Getting app catalog...", "zh": "获取应用目录中...", "ja": "アプリカタログを取得中..."},
{"en": "Failed to get catalog.", "zh": "获取目录失败。", "ja": "カタログの取得に失敗しました。"},
{"en": "Connecting to GitHub...", "zh": "正在连接到GitHub...", "ja": "GitHubに接続中..."},
{"en": "Failed to get app.", "zh": "获取应用失败。", "ja": "アプリの取得に失敗しました。"},
{"en": "Downloading zip...", "zh": "正在下载zip文件...", "ja": "zipファイルをダウンロード中..."},
{"en": "Finished downloading 'tempapp.zip'", "zh": "已完成下载 'tempapp.zip'", "ja": "'tempapp.zip' のダウンロードが完了しました"},
{"en": "Finished extracting.", "zh": "解压完成。", "ja": "解凍が完了しました。"},
{"en": "Removing 'tempapp.zip'...", "zh": "正在删除 'tempapp.zip'...", "ja": "'tempapp.zip' を削除しています..."},
{"en": "Failed to extract from zip file.", "zh": "从zip文件解压失败。", "ja": "zipファイルからの解凍に失敗しました。"},
{"en": "Done!", "zh": "完成!", "ja": "完了!"},
{"en": "Author:", "zh": "作者:", "ja": "著者:"},
{"en": "Description:", "zh": "描述:", "ja": "説明:"}
]""")  # noqa: E501

print("getapps!")

# ===== 延迟初始化：先只加载必要的模块 =====
CONFIG = Config()
log_memory("Config 加载后")

NIC = network.WLAN(network.STA_IF)
log_memory("WiFi 对象创建后")

# ===== 注意：先不加载 Display、UserInput、SimpleTerminal、I18N =====
# 这些会占用大量内存，我们在网络请求完成后再加载

# --------------------------------------------------------------------------------------------------
# -------------------------------------- function_definitions: -------------------------------------
# --------------------------------------------------------------------------------------------------

def goto_Setting():
    """跳转到设置页面（需要显示模块时再加载）"""
    # 延迟加载显示模块
    from lib.display import Display
    from lib import userinput
    
    DISPLAY = Display(use_tiny_buf=False)
    INPUT = userinput.UserInput()
    
    # 使用简单的打印，因为此时没有 TERM
    print("(Press any key to go to settings...)")
    time.sleep_ms(500)
    while not INPUT.get_new_keys():
        time.sleep_ms(10)
    machine.RTC().memory("/launcher/settings")
    machine.reset()

def check_wifi():
    """Verify WiFi has been configured, print error and exit if not."""
    if not CONFIG['wifi_ssid']:
        print("Error: WiFi SSID is blank!")
        print("Please use the Settings app to set up your WiFi access.")
        print('')
        goto_Setting()

def connect_wifi():
    """Connect to the configured WiFi network."""
    print("Enabling wifi...")

    if not NIC.active():
        NIC.active(True)

    if not NIC.isconnected():
        while True:
            try:
                NIC.connect(CONFIG['wifi_ssid'], CONFIG['wifi_pass'])
                print(f"SSID={CONFIG['wifi_ssid']},PASS={CONFIG['wifi_pass']}")
                break
            except OSError as e:
                print(f"Error: {e}")
                time.sleep_ms(500)

        attempts = 0
        while not NIC.isconnected() and attempts < _RETRYS:
            print(f"connecting... {attempts+1}")
            time.sleep_ms(1000)
            attempts += 1
    
    if NIC.isconnected():
        print("Connected!")
        log_memory("WiFi 连接后")
    else:
        print("Unable to connect!")
        goto_Setting()

def request_file(file_path: str) -> requests.Response:
    """Get the specific app file from GitHub."""
    print(f"{Device.name} Making request...")
    
    # 记录请求前内存
    log_memory("请求前")
    
    response = requests.get(
        f'https://raw.githubusercontent.com/echo-lalia/MicroHydra-Apps/main/catalog-output/{file_path}',
        headers={
            "accept": "application/vnd.github.v3.raw",
            "User-Agent": f"{Device.name} - MicroHydra",
        },
        timeout=30
    )
    
    # 记录请求后内存
    log_memory(f"请求后 (状态码: {response.status_code})")
    
    print(f"Returned code: {response.status_code}")
    return response

def try_request_file(file_path: str) -> requests.Response:
    """Capture errors and keep trying to get requested file."""
    wait = 1
    while True:
        try:
            return request_file(file_path)
        except (OSError, ValueError, MemoryError) as e:
            print(f"Request failed: {e}")
            # 检查是否是内存问题
            gc.collect()
            free = gc.mem_free()
            print(f"失败后内存: {free}")
            if "ENOMEM" in str(e) or "12" in str(e):
                print("⚠️ 内存不足！尝试强制清理...")
                for _ in range(5):
                    gc.collect()
                    time.sleep_ms(50)
                free_after = gc.mem_free()
                print(f"清理后内存: {free_after}")
                if free_after == free:
                    print("❌ 内存清理无效，可能是总内存不足")
            time.sleep(wait)
            wait += 1
            if wait > 10:
                wait = 10

def fetch_app_catalog() -> dict:
    """Download compact app catalog from apps repo."""
    
    log_memory("开始获取应用目录")
    print("Getting app catalog...")
    
    # 多次强制 GC
    for _ in range(5):
        gc.collect()
        time.sleep_ms(20)
    
    log_memory("GC 清理后")
    
    response = try_request_file(f"{Device.name.lower()}.json")
    
    # 记录响应内容大小
    content_size = len(response.content)
    print(f"响应内容大小: {content_size} 字节 ({content_size/1024:.1f} KB)")
    log_memory("JSON 解析前")
    
    try:
        result = json.loads(response.content)
        log_memory("JSON 解析后")
        print(f"解析成功，应用数量: {len(result)-1}")
    except MemoryError as e:
        print(f"JSON 解析内存不足: {e}")
        log_memory("JSON 解析失败")
        raise
    finally:
        response.close()
        del response
        gc.collect()
        log_memory("响应对象释放后")
    
    return result

_MAX_WBITS = const(15)

def fetch_app(app_name, mpy_matches):
    """触发应用下载（通过独立的下载器）"""
    from lib.hydra import loader
    
    # 1. 清理内存
    gc.collect()
    print(f"[GETAPPS] 触发下载: {app_name}")
    
    # 2. 写入 RTC 消息（标准化格式）
    rtc = machine.RTC()
    compiled = "compiled" if mpy_matches else "raw"
    msg = f"DOWNLOADER:START:{app_name}:{compiled}"
    rtc.memory(msg.encode())
    print(f"[GETAPPS] RTC 已写入: {msg}")
    
    # 3. 显示提示（如果有显示可用）
    try:
        DISPLAY.fill(CONFIG.palette[2])
        DISPLAY.text(
            "Downloading...",
            _DISPLAY_WIDTH_HALF - 60,
            _MH_DISPLAY_HEIGHT // 2 - 4,
            CONFIG.palette[8]
        )
        DISPLAY.text(
            "System will restart",
            _DISPLAY_WIDTH_HALF - 70,
            _MH_DISPLAY_HEIGHT // 2 + 16,
            CONFIG.palette[6]
        )
        DISPLAY.show()
        time.sleep(1)
    except:
        print("[GETAPPS] 下载中，系统即将重启...")
        time.sleep(1)
    
    # 4. 关闭 WiFi（释放资源）
    try:
        NIC.active(False)
    except:
        pass
    
    # 5. 通过 loader 启动下载器
    print("[GETAPPS] 启动下载器...")
    time.sleep_ms(500)
    
    # 使用模块路径（不包含 /lib/ 前缀）
    loader.launch_app('hydra.downloader')
# ===== 现在加载显示相关模块（在获取数据后） =====
def init_display_modules():
    """延迟加载显示、输入、终端和国际化模块"""
    from lib.display import Display
    from lib import userinput
    from lib.hydra.simpleterminal import SimpleTerminal
    
    log_memory("加载显示模块前")
    
    DISPLAY = Display(use_tiny_buf=False)
    log_memory("Display 加载后")
    
    INPUT = userinput.UserInput()
    log_memory("UserInput 加载后")
    
    TERM = SimpleTerminal()
    log_memory("SimpleTerminal 加载后")
    
    I18N = I18n(_TRANS)
    log_memory("I18N 加载后")
    
    return DISPLAY, INPUT, TERM, I18N

# --------------------------------------------------------------------------------------------------
# ---------------------------------------- ClassDefinitions: ---------------------------------------
# --------------------------------------------------------------------------------------------------

_AUTHOR_Y = const(_MH_DISPLAY_HEIGHT // 2)
_NAME_Y = const(_MH_DISPLAY_HEIGHT // 4 - 8)
_DESC_Y = const(_AUTHOR_Y + _NAME_Y + 6)
_MAX_H_CHARS = const(_MH_DISPLAY_WIDTH // 8)

class CatalogDisplay:
    """Construct for displaying and selecting catalog options."""

    def __init__(self, catalog: dict, display, input_obj, term, i18n):
        """Create a Catalog using given dict."""
        self.DISPLAY = display
        self.INPUT = input_obj
        self.TERM = term
        self.I18N = i18n
        self.CONFIG = CONFIG
        
        self.mpy_version = catalog.pop("mpy_version")
        self.names = list(catalog.keys())
        self.names.sort(key=lambda st: st.lower())
        self.catalog = catalog
        self.idx = 0

    def move(self, val: int):
        self.idx += val
        self.idx %= len(self.names)

    def jump_to(self, letter):
        for i in range(1, len(self.names)):
            i = (i + self.idx) % len(self.names)
            name = self.names[i]
            if name.lower().startswith(letter):
                self.idx = i
                return

    @staticmethod
    def split_lines(text: str) -> list:
        lines = []
        current_line = ''
        words = text.split()
        for word in words:
            if len(word) + len(current_line) >= _MAX_H_CHARS:
                lines.append(current_line)
                current_line = word
            elif len(current_line) == 0:
                current_line += word
            else:
                current_line += ' ' + word
        lines.append(current_line)
        return lines

    def draw(self):
        name = self.names[self.idx]
        *desc, author = self.catalog[name].split(' - ')
        desc = ' - '.join(desc)

        self.DISPLAY.fill(self.CONFIG.palette[2])
        self.DISPLAY.rect(0, _NAME_Y - 8, _MH_DISPLAY_WIDTH, 24, self.CONFIG.palette[3], fill=True)

        self.DISPLAY.text('<', 8, _NAME_Y, self.CONFIG.palette[4])
        self.DISPLAY.text('>', _MH_DISPLAY_WIDTH - 16, _NAME_Y, self.CONFIG.palette[4])
        self.DISPLAY.text(name, _DISPLAY_WIDTH_HALF - (len(name) * 4), _NAME_Y+1, self.CONFIG.palette[5])
        self.DISPLAY.text(name, _DISPLAY_WIDTH_HALF - (len(name) * 4), _NAME_Y, self.CONFIG.palette[8])

        self.DISPLAY.text(self.I18N["Author:"], _DISPLAY_WIDTH_HALF - 28, _AUTHOR_Y - 14, self.CONFIG.palette[3])
        self.DISPLAY.text(author, _DISPLAY_WIDTH_HALF - (len(author) * 4), _AUTHOR_Y, self.CONFIG.palette[5])

        self.DISPLAY.text(self.I18N["Description:"], _DISPLAY_WIDTH_HALF - 48, _DESC_Y - 14, self.CONFIG.palette[3])
        desc_y = _DESC_Y
        desc_lines = self.split_lines(desc)
        for line in desc_lines:
            self.DISPLAY.text(line, _DISPLAY_WIDTH_HALF - (len(line) * 4), desc_y, self.CONFIG.palette[6])
            desc_y += 9


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Loop: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main_loop():
    
    print("getapps_main")    
    # === 检查下载状态 ===
    rtc = machine.RTC()
    rtc_mem = rtc.memory()
    
    if isinstance(rtc_mem, bytes):
        try:
            rtc_str = rtc_mem.decode('utf-8')
        except:
            rtc_str = ""
    else:
        rtc_str = ""
    
    # 检查下载完成
    if rtc_str.startswith("DOWNLOADER_DONE:"):
        app_name = rtc_str.replace("DOWNLOADER_DONE:", "")
        print(f"[GETAPPS] 应用下载完成: {app_name}")
        rtc.memory(b"")
        show_done_msg = app_name
    elif rtc_str.startswith("DOWNLOADER_ERROR:"):
        # 解析错误信息
        parts = rtc_str.split(':')
        if len(parts) >= 3:
            error_type = parts[1]
            app_name = parts[2] if len(parts) > 2 else "unknown"
            print(f"[GETAPPS] 下载失败: {error_type} - {app_name}")
        rtc.memory(b"")
        show_done_msg = None
    else:
        show_done_msg = None
    
    # === 继续原来的 main_loop 逻辑 ===
    log_memory("进入 main_loop")
    
    """Run the main loop of the program."""
    
    print("getapps_main_checkwifi") 
    # 1. WiFi 连接（不需要显示）
    check_wifi()
    connect_wifi()
    print("getapps_main_done_wifi") 
    # 2. 获取数据（不需要显示）
    log_memory("获取数据前")
    catalog = fetch_app_catalog()
    log_memory("获取数据后")
    
    # 3. 现在才加载显示相关模块
    log_memory("加载显示模块前")
    DISPLAY, INPUT, TERM, I18N = init_display_modules()
    log_memory("显示模块加载完成")
    
    # 4. 对比 MPY 版本
    mpy_str = f"{sys.implementation._mpy & 0xff}.{sys.implementation._mpy >> 8 & 3}"
    mpy_matches = (mpy_str == catalog["mpy_version"])
    
    time.sleep_ms(400)
    
    # 5. 创建显示对象
    log_memory("创建 CatalogDisplay 前")
    catalog_display = CatalogDisplay(catalog, DISPLAY, INPUT, TERM, I18N)
    catalog_display.draw()
    log_memory("CatalogDisplay 创建后")
    
    # 添加提示
    DISPLAY.text(
        "Select an app to download:",
        _DISPLAY_WIDTH_HALF - 104,
        2,
        CONFIG.palette[0],
    )
    DISPLAY.text(
        "Press backspace to exit",
        _DISPLAY_WIDTH_HALF - 92,
        _MH_DISPLAY_HEIGHT-10,
        CONFIG.palette[0],
    )
    DISPLAY.show()
    log_memory("显示完成")
    if show_done_msg:
        # 在目录列表上方显示完成通知
        DISPLAY.text(
            f"✓ {show_done_msg} installed!",
            _DISPLAY_WIDTH_HALF - 80,
            2,
            CONFIG.palette[8]  # 亮色
        )
        DISPLAY.show()
        time.sleep(2)
    # 6. 主循环
    while True:
        keys = INPUT.get_new_keys()
        INPUT.ext_dir_keys(keys)

        if keys:
            for key in keys:
                if key == 'RIGHT':
                    catalog_display.move(1)
                elif key == 'LEFT':
                    catalog_display.move(-1)
                elif key in {'G0', 'ENT', 'SPC'}:
                    fetch_app(catalog_display.names[catalog_display.idx], mpy_matches)
                    time.sleep(2)
                elif key in {'ESC', 'BSPC'}:
                    NIC.active(False)
                    machine.reset()
                elif len(key) == 1:
                    catalog_display.jump_to(key)

            catalog_display.draw()
            DISPLAY.show()

        time.sleep_ms(10)


main_loop()
