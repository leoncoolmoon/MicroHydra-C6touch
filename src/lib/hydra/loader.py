"""Communicate with MicroHydras `main.py`.

Values are stored in the RTC, so that information can be retained on soft reset.
"""
from machine import RTC, reset

_PATH_SEP = const("|//|")

def launch_app(*args: str):
    """Set args and reboot."""
    # 检查 RTC 是否已有消息
    rtc = RTC()
    existing = rtc.memory()
    
    if existing and isinstance(existing, bytes):
        try:
            existing_str = existing.decode('utf-8')
            # 如果已有消息且以 DOWNLOADER 开头，保留它
            if existing_str.startswith('DOWNLOADER:'):
                # 把启动路径附加到消息后面
                full_msg = f"{existing_str}|//|{_PATH_SEP.join(args)}"
                rtc.memory(full_msg.encode())
                print(f"loader: 保留下载消息并附加启动路径: {full_msg}")
                reset()
                return
        except:
            pass
    
    # 正常情况
    set_args(*args)
    print(f"loader: 启动应用: {args}")
    reset()

def set_args(*args: str):
    """Store given args in RTC.

    First arg should typically be an import path.
    """
    RTC().memory(_PATH_SEP.join(args))


def get_args() -> list[str]:
    """Get the args stored in the RTC."""
    data = RTC().memory()
    if isinstance(data, bytes):
        try:
            decoded = data.decode()
            if '|//|' in decoded:
                return decoded.split('|//|')
            return [decoded] if decoded else []
        except:
            return []
    return []

def get_raw_message() -> str:
    """获取原始 RTC 消息"""
    data = RTC().memory()
    if isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except:
            return ""
    return ""