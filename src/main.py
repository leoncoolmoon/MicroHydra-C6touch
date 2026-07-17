"""Base 'apploader' for MicroHydra."""
import machine
from lib.hydra import loader
from lib import sdcard
import sys


# mh_if frozen:
# _LAUNCHER = const(".frozen/launcher/launcher")
# mh_else:
_LAUNCHER = const("/launcher/launcher")
#_LAUNCHER = const("/apps/apptemplate.py")
# mh_end_if
sys.path = ['', '/lib', '.frozen', '.frozen/lib']


# default app path is the path to the launcher
app = _LAUNCHER

# mh_if TDECK:
# # T-Deck must manually power on its peripherals
# machine.Pin(10, machine.Pin.OUT, value=True)
# mh_end_if

# if this was not a power reset, we are probably launching an app:
if machine.reset_cause() != machine.PWRON_RESET:
    args = loader.get_args()
    if args and args != ['']:
        print(f"args={args}")
        
        # ===== 智能提取应用路径 =====
        # 情况1: 第一个参数是模块路径（如 'hydra.downloader'），其他是参数
        # 情况2: 第一个参数是文件路径（如 '/launcher/getapps'）
        # 情况3: 第一个参数是下载消息（如 'DOWNLOADER:START:xxx'），第二个是模块路径
        
        app_path = None
        remaining_args = []
        
        # 遍历 args，找到第一个看起来像应用路径的
        for i, arg in enumerate(args):
            # 检查是否是应用路径：
            # 1. 以 '/' 开头（文件路径）
            # 2. 包含 '.'（模块路径，如 'hydra.downloader'）
            # 3. 不以 'DOWNLOADER:' 开头
            if (arg.startswith('/') or '.' in arg) and not arg.startswith('DOWNLOADER:'):
                app_path = arg
                # 剩余参数（除了当前这个）
                remaining_args = args[:i] + args[i+1:]
                break
        
        # 如果没找到，尝试取最后一个参数
        if app_path is None:
            # 检查最后一个参数是否是模块路径
            last_arg = args[-1]
            if last_arg.startswith('/') or '.' in last_arg:
                app_path = last_arg
                remaining_args = args[:-1]
            else:
                # 否则第一个参数可能是路径
                app_path = args[0]
                remaining_args = args[1:]
        
        print(f"main: app_path={app_path}, remaining_args={remaining_args}")
        
        if app_path:
            app = app_path
            loader.set_args(*remaining_args)

# ===== 智能导入：支持多种路径格式 =====
def import_app(app_path: str):
    """智能导入应用，支持多种路径格式"""
    
    # 1. 如果以 '/' 开头，转换为模块名
    if app_path.startswith('/'):
        module_name = app_path[1:].replace('/', '.')
        if module_name.startswith('.'):
            module_name = module_name[1:]
        print(f"main: 从路径导入模块: {module_name}")
        return __import__(module_name)
    
    # 2. 如果以 '.' 开头，直接导入
    if app_path.startswith('.'):
        print(f"main: 直接导入模块: {app_path}")
        return __import__(app_path)
    
    # 3. 如果包含 '.'，尝试作为模块路径导入
    if '.' in app_path:
        print(f"main: 作为模块导入: {app_path}")
        try:
            return __import__(app_path)
        except ImportError:
            # 如果失败，尝试从 lib 导入
            try:
                print(f"main: 尝试从 lib 导入: lib.{app_path}")
                return __import__(f"lib.{app_path}")
            except ImportError:
                raise
    
    # 4. 处理特殊路径名（如 'launcher/getapps' 或 'apps/xxx'）
    if '/' in app_path:
        module_name = app_path.replace('/', '.')
        print(f"main: 从路径导入模块: {module_name}")
        return __import__(module_name)
    
    # 5. 尝试作为普通模块导入
    print(f"main: 尝试导入: {app_path}")
    try:
        return __import__(app_path)
    except ImportError:
        # 尝试从 lib 导入
        print(f"main: 尝试从 lib 导入: lib.{app_path}")
        return __import__(f"lib.{app_path}")

# ===== SD 卡挂载 =====
if app.startswith("/sd"):
    sdcard.SDCard().mount()

# ===== 导入并执行应用 =====
print(f"main: 导入应用: {app}")
try:
    module = import_app(app)
    
    # 如果模块有 main() 函数，执行它
    if hasattr(module, 'main'):
        print(f"main: 执行 {app}.main()")
        module.main()
    # 如果模块有 run() 函数，执行它
    elif hasattr(module, 'run'):
        print(f"main: 执行 {app}.run()")
        module.run()
    else:
        print(f"main: 模块 {app} 没有 main() 或 run() 函数，已导入")
        
except Exception as e:  # noqa: BLE001
    print(f"main: 导入失败: {e}")
    with open('log.txt', 'a') as log:
        log.write(f"[{app}]\n")
        sys.print_exception(e, log)
    # reboot into launcher
    loader.launch_app(_LAUNCHER)