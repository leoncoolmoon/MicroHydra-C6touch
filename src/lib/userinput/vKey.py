"""
vKey.py

三层架构里的最上层：把 _touch.py 提供的原始触摸坐标，转换成键盘按键序列。
不碰 _touch.py / userinput.py 的现有接口——本模块只暴露一个 update() 方法，
输入是 touch.get_current_points() 的返回值，输出是一个 keylist（跟物理键盘
get_new_keys() 返回值同一种约定：['q']、['ENT']、['CTL', 'a'] 这样的字符串
列表），供 userinput.py 里的 get_new_keys() 直接拼接使用。

=== 设计上和 _touch.py 的关系（重要，如果想改回去先看这段）===
本模块【不使用】 touch.get_touch_events() / _touch.TouchEvent 那条路径，只用
touch.get_current_points() 逐帧轮询原始坐标，自己维护一套状态机——包括 canvas
区域内的 Tap/Swipe 判定，也是在这里重新实现的（判定逻辑和输出跟你原来写在
userinput.py 里的 inline 代码完全一致：Tap -> ['ENT']，Swipe RIGHT -> ['LEFT']，
Swipe LEFT -> ['RIGHT']，Swipe UP -> ['UP']，Swipe DOWN -> ['DOWN']）。
原因：get_touch_events() 只在一次触摸"结束"（手指抬起）时才会产出 Tap/Swipe，
过程中每帧都是空列表；而虚拟键盘需要在手指还按着、划动到不同列的时候就
实时刷新预览字母，所以必须自己逐帧读原始坐标。既然都要自己逐帧读了，canvas
部分索性也用同一份坐标流处理掉，避免两条数据源分别维护状态、互相对不上。

=== 屏幕区域划分 ===

    支持 canvas 贴屏幕顶部或贴屏幕底部两种布局（由 content_y 决定，见
    __init__ 里 self.gap_y 的计算），不支持 canvas 上下都留白的居中布局。

    下图是 canvas 贴底（content_y = screen_height - content_height，
    比如 37）时的样子——也就是你现在这版实际在用的布局，ESC/候选区在
    canvas 上方：

    (0,0)                                              (320,0)
      ┌────────┬──────────────────────────────┬────────┐
      │        │                                │        │   y: 0~gap_height
      │        │        ESC / 候选区预览          │        │   (比如 37)
      │        │        240 x gap_height         │        │
      ├────────┼──────────────────────────────┼────────┤
      │ 左预览区 │                                │ 右预览区 │
      │        │        canvas（内容区）          │        │   y: content_y~
      │        │        240x135                  │        │   screen_height
      └────────┴──────────────────────────────┴────────┘
    (0,172)                                            (320,172)

    - canvas 区域(x: content_x~content_x+content_width,
      y: content_y~content_y+content_height)：按原有逻辑处理
      Tap(-> ENT) / Swipe(-> 方向键)。
    - ESC/候选区(同 x 范围，y 是 canvas 之外剩下的那段 gap_height)：
      按下瞬间开始显示当前选中行的整行 14 个键（候选预览，见下），
      抬起时如果没什么明显移动 -> ESC。
    - 左/右两条竖列(x < content_x 或 x >= content_x+content_width，
      y: 0~screen_height 整列)：虚拟键盘的按下识别区，行选择用的是
      *整个屏幕*的高度(screen_height)按 1/6、3/6、5/6 分四行，不是内容区
      的 135。左右预览区(y: content_y~content_y+content_height，跟 canvas
      同一段高度)用来实时预览选中的字母；锁定标记区(y 是 gap_y~
      gap_y+gap_height，跟 ESC/候选区同一段高度)用来显示锁定的功能键
      标记。

=== 虚拟键盘手势规则 ===
    1. 手指在左/右竖列按下 -> 按下 y 坐标（按整屏 1/6,3/6,5/6 比例）选定
       KEYMAP 的行（0~3），此时立刻在 ESC/候选区把这一整行 14 个键摆出来
       （候选预览，单字符键白色，功能键用缩写+橙色，见 _get_display_text/
       _is_function_key）。
    2. 手指还没进 canvas 前，如果继续上下移动导致换到另一行的判定区间，
       会实时切换选中的行，候选预览跟着刷新（不再是"按下瞬间定死，之后
       不能改"，可以先上下滑动挑好行再进 canvas）。
    3. 手指划入 canvas 的 x 范围内 -> 开始根据当前 x 坐标（相对 canvas 左边
       缘，按 14 等分）实时选定列（0~13），左右预览区同步刷新选中的大字，
       候选区里对应那一列会有一个半透明蓝色高亮跟着走。
    4. 手指再次划出 canvas 的 x 范围（不管是划回左边还是右边的竖列）->
       视为取消，本次触摸剩余时间都不再响应，抬起也不发字符。
    5. 手指在 canvas 的 x 范围内抬起 -> 发出当前预览的字符（如果是普通字符
       且有 CTL/ALT/OPT 处于锁定态，会和这些锁定的修饰键一起以
       ['CTL', 'x'] 这种形式发出，然后自动解锁；如果选中的是 FN/SHIFT/CTL/
       ALT/OPT 本身，则只切换锁定状态，不发出字符）。抬起后候选预览和左右
       大字预览都会清空。

=== 功能键锁定规则 ===
    - 锁定状态直接存在构造时传入的 locked_keys 列表里（跟 userinput.py 里
      物理键盘用的 self.locked_keys 是同一个 list 的引用，不是各管各的两
      份状态）。'FN' in self.locked_keys 这种判断天然就包含了虚拟键盘锁
      定的结果。
    - FN / SHIFT 互斥：再次选中同一个会从列表里移除（解锁）；选中另一个
      会自动把原来那个从列表里移除、换成新选的这个。
    - CTL / ALT / OPT 可以同时锁定多个；下一次发出普通字符时，会把当前
      锁定在列表里的这几个和这个字符一起发出，然后把它们从列表里移除。
    - 左右锁定标记区显示的字母：FN->F, SHIFT->S, CTL->C, ALT->A, OPT->O，
      当前所有处于锁定状态的键对应字母拼在一起显示（比如同时锁 CTL 和 ALT
      时显示 "CA"）。
    - 因为是共享同一个 list，物理键盘那边 handle_locking_keys() 的锁定
      逻辑不知道"FN/SHIFT 互斥"这条规则，理论上可能出现物理锁了 FN、
      虚拟又锁了 SHIFT 同时存在于列表里的情况——_current_rows() 里定了
      SHIFT 优先的规则兜底，不会报错，只是显示上可能不是你预期的那个。

=== canvas 内 Tap 的长按/短按规则 ===
    - 手指在 canvas 区域按下、抬起时相对按下点的位移没有超过
      swipe_move_thresh（判定为"没怎么动"，也就是 Tap 而不是 Swipe）：
      再看按住的时长——
        * 按住时长 >= touch_time_thresh（毫秒）-> 判定为长按，发出 ['ENT']；
        * 按住时长 <  touch_time_thresh -> 判定为短按（误触/手指刚碰一下
          就抬起），不发出任何按键，返回 []。
      这样可以避免手指轻轻扫过 canvas 边缘时被误判成一次完整的回车。
    - Swipe（位移超过 swipe_move_thresh）不受这条时长规则影响，照样按
      方向直接判定，跟按住多久无关。

=== 使用方式（预留给 userinput.py 接入，接口暂不改动，接入时大概是这样）===

    from . import vKey
    self.vkey = vKey.VKey(
        scrn=Display.instance.scrn,
        screen_width=320,
        screen_height=172,
        content_x=Display.instance.content_x,
        content_y=Display.instance.content_y,
        content_width=Display.instance.content_width,
        content_height=Display.instance.content_height,
        locked_keys=self.locked_keys,  # 关键：传同一个 list 引用进去
    )
    ...
    # get_new_keys() 里，替换掉原来那段 inline 的 Tap/Swipe 处理:
    vkey_out = self.vkey.update(self.get_current_points())
    if vkey_out:
        keylist = vkey_out

    注意 update() 需要每帧都调用（不只是有触摸事件的时候），因为状态机依赖
    连续的按下/移动/抬起帧序列，跳帧会导致预览卡住或者状态判断错误。

    另外 self.locked_keys 必须在创建 VKey 实例之前就已经存在（UserInput.
    __init__ 里目前是先 self.locked_keys = []，再往后才做触摸相关的初始化，
    顺序已经是对的，不用调整）。
"""

import lvgl as lv

# MicroPython 大多数端口 time 模块自带 ticks_ms/ticks_diff；极少数老端口
# 只有 utime 这个名字，这里两个都试一下，实在都没有就退化成用
# time.time() * 1000 凑合算（精度差一些，但不会直接崩）。
try:
    import time
    time.ticks_ms
    time.ticks_diff
except (ImportError, AttributeError):
    try:
        import utime as time
    except ImportError:
        time = None

try:
    import machine
except ImportError:
    # 方便在电脑上跑单元测试（用假的 lv 模块那种）时 import 不报错。
    # 真机上 MicroPython 一定有 machine，这个分支不会触发。
    machine = None


def _ticks_ms():
    """统一的毫秒时间戳获取入口，屏蔽 ticks_ms 是否存在的差异。"""
    if time is not None and hasattr(time, 'ticks_ms'):
        return time.ticks_ms()
    if time is not None:
        return int(time.time() * 1000)
    return 0


def _ticks_diff(a, b):
    """统一的毫秒差值计算入口，优先用 ticks_diff（能正确处理回绕），
    没有的话退化成普通减法。"""
    if time is not None and hasattr(time, 'ticks_diff'):
        return time.ticks_diff(a, b)
    return a - b


# ============================================================
# 键位表：4 行 x 14 列，直接写成二维数组，跟屏幕上的物理排列
# 一一对应，方便肉眼核对第几行第几列是哪个键（调试列错位问题时
# 直接 print(KEYMAP[row][col]) 就能看）。
# ============================================================
KEYMAP = [
    ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'BSPC'],   # 第一行
    ['TAB', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\'],   # 第二行
    ['FN', 'SHIFT', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'", 'ENT'],  # 第三行
    ['CTL', 'OPT', 'ALT', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/', 'SPC'],  # 第四行
]

KEYMAP_SHIFT = [
    ['~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+', 'BSPC'],
    ['TAB', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{', '}', '|'],
    ['FN', 'SHIFT', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':', '"', 'ENT'],
    ['CTL', 'OPT', 'ALT', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<', '>', '?', 'SPC'],
]

KEYMAP_FN = [
    ['ESC', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', '_', '=', 'DEL'],
    ['TAB', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\'],
    ['FN', 'SHIFT', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'UP', "'", 'ENT'],
    ['CTL', 'OPT', 'ALT', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'LEFT', 'DOWN', 'RIGHT', 'SPC'],
]

for _name, _map in (('KEYMAP', KEYMAP), ('KEYMAP_SHIFT', KEYMAP_SHIFT), ('KEYMAP_FN', KEYMAP_FN)):
    if len(_map) != 4 or any(len(_row) != 14 for _row in _map):
        raise ValueError('%s 必须是 4 行 x 14 列' % _name)
del _name, _map


def _pick_font(*names):
    """按顺序尝试拿 lv.font_xxx，返回第一个真实存在于当前固件里的字体。

    不同固件编译时勾选的字体大小不一样，直接写死一个字号在有些板子上
    会因为该字号没编译进去而 AttributeError。这里从大到小试一遍，全部
    找不到才报错（报错信息里会列出到底试了哪些，方便你去 menuconfig /
    编译选项里确认哪些字号是真的编译进了固件）。
    """
    tried = []
    for name in names:
        tried.append(name)
        font = getattr(lv, name, None)
        if font is not None:
            return font
    raise AttributeError(
        '没有找到可用字体，试过: %s。确认一下固件编译时勾选了哪些 '
        'LV_FONT_MONTSERRAT_* 字号，再把对应的 lv.font_montserrat_N '
        '通过 preview_font/badge_font 参数传进来。' % ', '.join(tried)
    )


# 会切换字符表、彼此互斥的锁定键
_CHARMAP_KEYS = ('FN', 'SHIFT')
# 可以叠加锁定、下一个普通字符发出后自动解锁的修饰键
_MOD_KEYS = ('CTL', 'ALT', 'OPT')
# 锁定状态在左右锁定标记区显示的字母
_LOCK_BADGE_CHAR = {'FN': 'F', 'SHIFT': 'S', 'CTL': 'C', 'ALT': 'A', 'OPT': 'O'}

# swipe 方向 -> 输出按键（照搬你原来 inline 代码里的映射，没有改动）
_SWIPE_TO_KEY = {'RIGHT': 'LEFT', 'LEFT': 'RIGHT', 'UP': 'UP', 'DOWN': 'DOWN'}

# 内部状态机
_ST_IDLE = 0        # 没有触摸
_ST_ARMED = 1       # 在左右竖列按下，已选好行，等待划入 canvas
_ST_TRACKING = 2    # 已进入 canvas 的 x 范围，实时选列中
_ST_CANCELLED = 3   # 曾进入过 canvas 又划出去了，本次触摸剩余时间不再响应
_ST_CANVAS = 4      # 在 canvas 内按下，走 Tap/Swipe 判定
_ST_ESC = 5         # 在 ESC 区域按下


def _set_label_clip(label, letter_space=-4):
    """尽量把 label 设成不换行/裁切模式，并减小字间距
    屏蔽掉不同 lvgl 绑定版本里这个枚举名字/挂载位置不一样的问题
    """
    # 设置长文本模式为 CLIP（裁剪）
    try:
        # 尝试直接设置
        label.set_long_mode(lv.label.LONG_MODE.CLIP)
    except:
        try:
            # 有些版本可能用 LABEL_LONG
            label.set_long_mode(lv.LABEL_LONG.CLIP)
        except:
            # 如果都不行，尝试通过样式设置
            mode_enum = getattr(lv, 'LABEL_LONG_MODE', None) or getattr(lv, 'LABEL_LONG', None)
            if mode_enum:
                mode = getattr(mode_enum, 'CLIP', None) or getattr(mode_enum, 'WRAP', None)
                if mode:
                    try:
                        label.set_long_mode(mode)
                    except Exception:
                        pass

    # 减小字间距，让文字更紧凑，防止换行
    try:
        label.set_style_text_letter_space(letter_space, 0)
    except Exception:
        pass


def _is_multichar_key(text):
    """判断是否为多字符功能键（需要特殊显示）"""
    return len(text) > 1


def _get_display_text(key):
    """获取按键在行预览中显示的文本（缩写/符号）"""
    # 特殊功能键映射到短缩写或符号
    special_map = {
        'BSPC': 'BS',   # 退格
        'TAB': 'TA',    # Tab
        'ENT': 'ET',    # 回车
        'SHIFT': 'SF',  # Shift
        'ESC': 'ES',    # Escape
        'SPC': 'SP',    # Space
        'CTL': 'CT',    # Control
        'ALT': 'AT',    # Alt
        'OPT': 'OP',    # Option
        'FN': 'FN',     # Function
        'DEL': 'DL',    # Delete
        'UP': 'Up',     # Up
        'DOWN': 'Dn',   # Down
        'LEFT': 'Lf',   # Left
        'RIGHT': 'Ri',  # Right
        'CAPS': 'CP',   # Caps Lock (虽然没用到)
    }

    if key in special_map:
        return special_map[key]

    # F1-F10 显示为 F1~F0 (F10 用 F0 更紧凑)
    if key.startswith('F') and len(key) > 1 and key[1:].isdigit():
        num = int(key[1:])
        if num == 10:
            return 'F0'  # F10 显示为 F0
        return key  # F1-F9 保持原样

    # 其他多字符键取首字母（作为后备）
    if _is_multichar_key(key):
        return key[0]

    # 普通单字符键直接返回
    return key


def _is_function_key(key):
    """判断是否为功能键（需要特殊颜色/样式）"""
    function_keys = {
        'BSPC', 'TAB', 'ENT', 'SHIFT', 'ESC', 'SPC',
        'CTL', 'ALT', 'OPT', 'FN', 'DEL',
        'UP', 'DOWN', 'LEFT', 'RIGHT',
        'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10'
    }
    return key in function_keys


class VKey:
    """手势识别 + 键盘映射 + LVGL 实时预览。逐帧调用 update()。"""

    def __init__(
            self,
            *,
            scrn,
            screen_width,
            screen_height,
            content_x,
            content_y,
            content_width,
            content_height,
            swipe_move_thresh=20,
            touch_time_thresh=100,
            preview_font=None,
            badge_font=None,
            row_preview_font=None,
            row_preview_small_font=None,
            debug=False,
            locked_keys=None,
            g0_pin=9):
        self.debug = debug
        self.scrn = scrn
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.content_x = content_x
        self.content_y = content_y
        self.content_width = content_width
        self.content_height = content_height
        self.swipe_move_thresh = swipe_move_thresh
        # 注意：原来这行末尾多了个逗号，会把 touch_time_thresh 变成一个
        # 元组 (100,) 而不是数字 100，导致后面跟数字比较直接报错——这里
        # 已经去掉逗号。touch_time_thresh 的单位是毫秒，是区分"长按"
        # (发 ENT) 和"短按"(不发东西) 的分界线。
        self.touch_time_thresh = touch_time_thresh
        self.left_margin_width = content_x
        self.right_margin_width = screen_width - content_x - content_width
        self.badge_zone_height = screen_height - content_height
        # 空白横条（ESC/候选区/锁定标记）所在的 y 位置：canvas 贴顶
        # (content_y == 0) 时空白横条在下面；canvas 贴底
        # (content_y + content_height == screen_height) 时空白横条在上面。
        # 目前只支持"贴一边"这两种布局。
        self.gap_y = 0 if content_y > 0 else content_height

        # ---- 触摸状态机 ----
        self._state = _ST_IDLE
        self._press_x = 0
        self._press_y = 0
        # 本次触摸按下的时刻（毫秒时间戳），用来在抬起时算出按住了多久，
        # 从而区分 canvas 内的长按（发 ENT）和短按（不发任何东西）。
        self._press_time = 0
        self._last_x = 0
        self._last_y = 0
        self._row = 0
        self._col = 0

        # ---- 锁定状态 ----
        # 直接持有 userinput.py 里 self.locked_keys 这同一个 list 的引用
        # （不是复制一份），FN/SHIFT/CTL/ALT/OPT 锁定时直接往这个 list 里
        # append/remove。这样物理键盘那边 get_pressed_keys() 完全不用
        # 关心虚拟键盘的存在，'FN' in self.locked_keys 天然就包含了虚拟
        # 键盘锁定的结果。没传 locked_keys 时退化成自己维护一个独立的
        # list，行为不变，只是不会跟物理键盘共享状态。
        self._locked_keys = locked_keys if locked_keys is not None else []

        # 跟物理版 Keys.get_pressed_keys() 的 self.key_state 语义对齐：
        # "当前正被按住的键"快照。update() 每次调用都会刷新。
        # 目前包含两类来源：
        #   1) 触摸选中的字符（_ST_TRACKING 时最多一个）
        #   2) G0 物理按键（GPIO9，按下是低电平，跟触摸完全独立，只要
        #      按住就一直在这个列表里，不受触摸状态机影响）
        self.key_state = []

        # G0：GPIO9，按下低电平，用内部上拉。传 g0_pin=None 可以彻底
        # 关掉这颗按键的检测（比如你的板子没接这个按钮）。
        self._g0 = g0_pin
        self._build_widgets(preview_font, badge_font, row_preview_font, row_preview_small_font)

    # ------------------------------------------------------------------
    # LVGL 预览控件：直接建在 scrn 上，不占用 canvas 的 _canvas_buf 内存。
    # ------------------------------------------------------------------

    def _build_widgets(self, preview_font, badge_font, row_preview_font, row_preview_small_font):
        # 40px 宽的预览/锁定区能显示相当大的字，优先用 montserrat_20；
        # 固件没编译这个字号的话，往下依次退到更小的字号。
        preview_font = preview_font or _pick_font('font_montserrat_16')
        badge_font = badge_font or _pick_font('font_montserrat_14')

        # 行预览区域：普通键用稍大字体，功能键用更小字体
        self._row_preview_font = row_preview_font or _pick_font('font_montserrat_12')
        #self._row_preview_small_font = row_preview_small_font or _pick_font('LV_FONT_UNSCII_8')

        self._preview_left = self._make_label(
            0, self.content_y, self.left_margin_width, self.content_height, preview_font)
        self._preview_right = self._make_label(
            self.content_x + self.content_width, self.content_y,
            self.right_margin_width, self.content_height, preview_font)

        self._badge_left = self._make_label(
            0, self.gap_y, self.left_margin_width, self.badge_zone_height, badge_font)
        self._badge_left.set_style_text_color(lv.color_hex(0xFF0000), 0)

        self._badge_right = self._make_label(
            self.content_x + self.content_width, self.gap_y,
            self.right_margin_width, self.badge_zone_height, badge_font)
        self._badge_right.set_style_text_color(lv.color_hex(0xFF0000), 0)

        # ---- 行预览区域：canvas 旁边的空白横条 ----
        # 用黑色背景的容器来显示/隐藏（不依赖 set_hidden）
        self._row_preview_container = lv.obj(self.scrn)
        self._row_preview_container.set_pos(self.content_x, self.gap_y)
        self._row_preview_container.set_size(self.content_width, self.badge_zone_height)
        self._row_preview_container.set_style_bg_color(lv.color_hex(0x000000), 0)  # 默认黑色（隐藏）
        self._row_preview_container.set_style_bg_opa(lv.OPA.COVER, 0)
        self._row_preview_container.set_style_border_width(0, 0)

        self._row_preview_container.set_style_pad_all(0, 0)
        self._row_preview_container.set_style_pad_top(0, 0)
        self._row_preview_container.set_style_pad_bottom(0, 0)
        self._row_preview_container.set_style_pad_left(0, 0)
        self._row_preview_container.set_style_pad_right(0, 0)

        try:
            self._row_preview_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        except:
            try:
                self._row_preview_container.set_scrollbar_mode(lv.SCROLLBAR.OFF)
            except:
                pass
        # 创建 14 个格子
        self._row_cells = []
        cell_width = self.content_width // 14
        cell_height = self.badge_zone_height
        for i in range(14):
            cell = lv.label(self._row_preview_container)
            cell.set_pos(i * cell_width, 0)
            cell.set_size(cell_width, cell_height)
            cell.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

            # ---- 去掉 cell 的 margin 和 padding ----
            cell.set_style_pad_all(0, 0)
            cell.set_style_pad_top(0, 0)
            cell.set_style_pad_bottom(0, 0)
            cell.set_style_pad_left(0, 0)
            cell.set_style_pad_right(0, 0)

            # ---- 防止换行 ----
            try:
                cell.set_long_mode(lv.label.LONG_MODE.CLIP)
            except:
                try:
                    cell.set_long_mode(lv.LABEL_LONG.CLIP)
                except:
                    pass

            # 设置字间距为 -2（减小间距，让文字更紧凑）
            cell.set_style_text_letter_space(-4, 0)

            # 默认使用普通字体，后面会根据按键类型切换
            cell.set_style_text_font(self._row_preview_font, 0)
            cell.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
            cell.set_text('')
            self._row_cells.append(cell)

        # 高亮当前列的指示器
        self._highlight_cells = []
        for i in range(14):
            hl = lv.obj(self._row_preview_container)
            hl.set_pos(i * cell_width, 0)
            hl.set_size(cell_width, cell_height)
            hl.set_style_bg_color(lv.color_hex(0x4444FF), 0)
            hl.set_style_bg_opa(lv.OPA.TRANSP, 0)  # 默认透明
            hl.set_style_border_width(0, 0)

            # ---- 去掉高亮层的 margin 和 padding ----
            hl.set_style_pad_all(0, 0)
            hl.set_style_pad_top(0, 0)
            hl.set_style_pad_bottom(0, 0)
            hl.set_style_pad_left(0, 0)
            hl.set_style_pad_right(0, 0)

            self._highlight_cells.append(hl)

        self._update_preview_widgets()
        self._update_lock_badges()
        self._hide_row_preview()

    def _make_label(self, x, y, w, h, font):
        label = lv.label(self.scrn)
        label.set_pos(x, y)
        label.set_size(w, h)
        label.set_style_text_font(font, 0)
        label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        _set_label_clip(label)
        label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        label.set_text('')
        return label

    # ------------------------------------------------------------------
    # 主入口：每帧调用。points 是 touch.get_current_points() 的返回值
    # （0 个或 1 个 TouchPoint）。返回本帧要交给 get_new_keys() 的 keylist，
    # 大多数帧下是空列表 []。
    # ------------------------------------------------------------------
    def update(self, points):

        output = self._update_impl(points)
        g0k = machine.Pin(self._g0, machine.Pin.IN, machine.Pin.PULL_UP).value() == 0
        #print(f"output={output},g0k={g0k}")
        if g0k:
            self.key_state = ['G0']
        else:
            self.key_state = output

        return self.key_state

    def get_pressed_keys(self):
        """跟物理版 Keys.get_pressed_keys() 的接口对齐：返回"当前正被
        按住"的虚拟键列表（其实就是 self.key_state，这里包一层方法只是
        为了让只会调方法、不会去读属性的外部代码也能用）。

        注意跟物理版不是完全一回事：
        - 物理版可以同时有好几个键（比如 CTL+a），这里单指触摸最多同时
          一个。
        - 物理版调用这个方法本身会触发一次硬件 scan()；这里不会做任何
          触摸轮询，只是读取上一次 update() 算出来的状态——真正驱动
          轮询的还是每帧调用的 update()。
        """
        return list(self.key_state)

    def _update_impl(self, points):
        point = points[0] if points else None

        if point is None:
            if self._state == _ST_IDLE:
                return []
            output = self._handle_release()
            self._state = _ST_IDLE
            return output

        x, y = point.x, point.y

        if self._state == _ST_IDLE:
            self._press_x, self._press_y = x, y
            self._press_time = _ticks_ms()  # 记下按下时刻，供抬起时算长/短按
            self._last_x, self._last_y = x, y
            zone = self._zone_for(x, y)
            if zone == 'CANVAS':
                self._state = _ST_CANVAS
            elif zone == 'ESC':
                self._state = _ST_ESC
            else:
                self._state = _ST_ARMED
                self._row = self._row_from_y(y)
                # 按下时立即显示当前行的预览
                self._show_row_preview()
            if self.debug:
                print('vKey press: raw=(%d,%d) zone=%s row=%s' % (
                    x, y, zone, self._row if zone == 'MARGIN' else '-'))
            return []

        self._last_x, self._last_y = x, y

        if self._state == _ST_ARMED:
            # ---- 新增：在进入 canvas 前允许上下移动选行 ----
            # 更新行（根据当前 y 坐标）
            new_row = self._row_from_y(y)
            if new_row != self._row:
                self._row = new_row
                # 刷新行预览显示
                self._show_row_preview()
                if self.debug:
                    print('vKey armed: row changed to %d (y=%d)' % (self._row, y))

            # 检查是否进入 canvas
            if self._x_in_canvas(x):
                self._state = _ST_TRACKING
                self._col = self._col_from_x(x)
                self._update_preview_widgets()
                self._update_row_preview_highlight()
                if self.debug:
                    print('vKey armed->tracking: raw=(%d,%d) row=%d col=%d char=%r' % (
                        x, y, self._row, self._col, self._current_char()))
            return []

        if self._state == _ST_TRACKING:
            if not self._x_in_canvas(x):
                self._state = _ST_CANCELLED
                self._update_preview_widgets()
                self._hide_row_preview()
                if self.debug:
                    print('vKey tracking->cancelled: raw=(%d,%d)' % (x, y))
            else:
                self._col = self._col_from_x(x)
                self._update_preview_widgets()
                self._update_row_preview_highlight()
                if self.debug:
                    print('vKey tracking: raw=(%d,%d) row=%d col=%d char=%r' % (
                        x, y, self._row, self._col, self._current_char()))
            return []

        # _ST_CANCELLED / _ST_CANVAS / _ST_ESC：等抬起再处理
        return []

    # ------------------------------------------------------------------
    # 区域判定
    # ------------------------------------------------------------------
    def _zone_for(self, x, y):
        if self._x_in_canvas(x):
            return 'CANVAS' if self.content_y <= y < self.content_y + self.content_height else 'ESC'
        return 'MARGIN'

    def _x_in_canvas(self, x):
        return self.content_x <= x < self.content_x + self.content_width

    def _row_from_y(self, y):
        h = self.screen_height
        if y < h / 6:
            return 0
        if y < h * 3 / 6:
            return 1
        if y < h * 5 / 6:
            return 2
        return 3

    def _col_from_x(self, x):
        rel = x - self.content_x
        col = int(rel * 14 // self.content_width)
        if col < 0:
            col = 0
        elif col > 13:
            col = 13
        return col

    # ------------------------------------------------------------------
    # 抬起处理：根据抬起前所在的状态，决定要不要发字符/方向键/ESC。
    # ------------------------------------------------------------------
    def _handle_release(self):
        state = self._state
        # 抬起后清掉预览显示
        self._update_preview_widgets(force_clear=True)
        self._hide_row_preview()

        if state == _ST_TRACKING:
            output = self._emit_selected_char()
            if self.debug:
                print('vKey release: state=TRACKING row=%d col=%d -> %r' % (
                    self._row, self._col, output))
            return output

        if state == _ST_CANVAS:
            dx = self._last_x - self._press_x
            dy = self._last_y - self._press_y
            # 按住了多久（毫秒），用来区分长按/短按
            held_ms = _ticks_diff(_ticks_ms(), self._press_time)
            if abs(dx) < self.swipe_move_thresh and abs(dy) < self.swipe_move_thresh:
                # 位移没超过阈值 -> 判定为 Tap（不是 Swipe），
                # 再按时长区分长按/短按：
                #   长按（held_ms >= touch_time_thresh）-> 发 ENT
                #   短按（held_ms <  touch_time_thresh）-> 什么都不发
                if held_ms >= self.touch_time_thresh:
                    output = ['ENT']
                else:
                    output = []
            else:
                direction = self._direction(dx, dy)
                output = [_SWIPE_TO_KEY[direction]]
            if self.debug:
                print('vKey release: state=CANVAS press=(%d,%d) last=(%d,%d) dx=%d dy=%d held=%dms -> %r' % (
                    self._press_x, self._press_y, self._last_x, self._last_y, dx, dy, held_ms, output))
            return output

        if state == _ST_ESC:
            dx = self._last_x - self._press_x
            dy = self._last_y - self._press_y
            output = []
            if abs(dx) < self.swipe_move_thresh and abs(dy) < self.swipe_move_thresh:
                output = ['ESC']
            if self.debug:
                print('vKey release: state=ESC dx=%d dy=%d -> %r' % (dx, dy, output))
            return output

        # _ST_ARMED（一直没划进 canvas）/ _ST_CANCELLED：不发任何东西
        if self.debug:
            print('vKey release: state=%d -> no output' % state)
        return []

    @staticmethod
    def _direction(dx, dy):
        if abs(dx) > abs(dy):
            return 'RIGHT' if dx > 0 else 'LEFT'
        return 'DOWN' if dy > 0 else 'UP'

    # ------------------------------------------------------------------
    # 字符发出 + 锁定键处理
    # ------------------------------------------------------------------
    def get_locked_keys(self):
        """返回当前处于锁定状态、且是这套虚拟键盘认识的功能键
        ('FN'/'SHIFT'/'CTL'/'ALT'/'OPT' 的子集)。

        锁定状态已经直接存在传进来的 locked_keys 列表里了，userinput.py
        那边不需要调用这个方法去同步 get_pressed_keys() 的
        force_fn/force_shift——直接判断 'FN' in self.locked_keys 就已经
        包含虚拟键盘锁定的结果。这个方法留着给需要单独读取"虚拟键盘锁定
        了哪些键"的场景用。
        """
        return [k for k in (_CHARMAP_KEYS + _MOD_KEYS) if k in self._locked_keys]

    def _current_rows(self):
        # 正常来说 FN/SHIFT 互斥（vKey 自己切换时会保证这一点），但因为
        # self._locked_keys 是跟物理键盘共享的同一个 list，物理键盘那边
        # 的锁定逻辑不知道这个互斥规则，理论上可能出现两个同时在里面的
        # 情况——这里定一个优先级（SHIFT 优先）保证不会出错。
        if 'SHIFT' in self._locked_keys:
            return KEYMAP_SHIFT
        if 'FN' in self._locked_keys:
            return KEYMAP_FN
        return KEYMAP

    def _current_char(self):
        return self._current_rows()[self._row][self._col]

    def _emit_selected_char(self):
        char = self._current_char()

        if char in _CHARMAP_KEYS:  # 'FN' / 'SHIFT'，互斥
            if char in self._locked_keys:
                self._locked_keys.remove(char)
            else:
                other = 'SHIFT' if char == 'FN' else 'FN'
                if other in self._locked_keys:
                    self._locked_keys.remove(other)
                self._locked_keys.append(char)
            self._update_lock_badges()
            return []

        if char in _MOD_KEYS:  # 'CTL' / 'ALT' / 'OPT'，可以同时锁多个
            if char in self._locked_keys:
                self._locked_keys.remove(char)
            else:
                self._locked_keys.append(char)
            self._update_lock_badges()
            return []

        # 普通字符：带上当前所有锁定的修饰键一起发出，然后清空这几个
        # （FN/SHIFT 的字符表锁定不受影响，会一直保持，直到再次手动切换）
        active_mods = [k for k in _MOD_KEYS if k in self._locked_keys]
        output = active_mods + [char]
        if active_mods:
            for k in active_mods:
                self._locked_keys.remove(k)
            self._update_lock_badges()
        return output

    # ------------------------------------------------------------------
    # 行预览显示控制（用黑色背景覆盖来实现隐藏/显示）
    # ------------------------------------------------------------------
    def _show_row_preview(self):
        """显示当前行的 14 个按键"""
        row_keys = self._current_rows()[self._row]

        # 更新每个格子的文字
        for i, key in enumerate(row_keys):
            if i < len(self._row_cells):
                display_text = _get_display_text(key)
                self._row_cells[i].set_text(display_text)

                # 判断是否功能键
                is_func = _is_function_key(key)

                # 功能键用更小字体 + 橙色，普通键用正常字体 + 白色
                if is_func:
                    self._row_cells[i].set_style_text_color(lv.color_hex(0xFFA500), 0)
                else:
                    self._row_cells[i].set_style_text_font(self._row_preview_font, 0)
                    self._row_cells[i].set_style_text_color(lv.color_hex(0xFFFFFF), 0)

        # 显示容器：改为深灰色背景
        self._row_preview_container.set_style_bg_color(lv.color_hex(0x222222), 0)
        self._row_preview_container.set_style_bg_opa(lv.OPA.COVER, 0)

        # 清除高亮
        self._clear_highlights()

    def _hide_row_preview(self):
        """隐藏行预览（用黑色覆盖并清空文字）"""
        # 清空所有格子的文字
        for cell in self._row_cells:
            cell.set_text('')

        # 设置为黑色（与背景融合）
        self._row_preview_container.set_style_bg_color(lv.color_hex(0x000000), 0)
        self._row_preview_container.set_style_bg_opa(lv.OPA.COVER, 0)
        self._clear_highlights()

    def _update_row_preview_highlight(self):
        """更新当前列的高亮"""
        if self._state != _ST_TRACKING:
            return

        self._clear_highlights()

        # 高亮当前列
        if 0 <= self._col < len(self._highlight_cells):
            hl = self._highlight_cells[self._col]
            hl.set_style_bg_opa(lv.OPA._20, 0)
            hl.set_style_bg_color(lv.color_hex(0x0000FF), 0)
            # 把高亮层移到最前面
            hl.move_foreground()

    def _clear_highlights(self):
        """清除所有高亮"""
        for hl in self._highlight_cells:
            hl.set_style_bg_opa(lv.OPA.TRANSP, 0)

    # ------------------------------------------------------------------
    # LVGL 显示刷新
    # ------------------------------------------------------------------
    def _update_preview_widgets(self, force_clear=False):
        if not force_clear and self._state == _ST_TRACKING:
            text = self._current_char()
        else:
            text = ''
        self._preview_left.set_text(text)
        self._preview_right.set_text(text)

    def _update_lock_badges(self):
        chars = [_LOCK_BADGE_CHAR[k] for k in (_CHARMAP_KEYS + _MOD_KEYS) if k in self._locked_keys]
        text = ''.join(chars)
        self._badge_left.set_text(text)
        self._badge_right.set_text(text)