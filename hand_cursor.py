"""
Hand Cursor — Управление курсором и клавиатурой двумя руками.

ЛЕВАЯ рука — мышь:
  🖐️  Ладонь                    → курсор следует за ладонью
  🤏 Щипок (большой + указат.)  → клик / drag
  🤏 Щипок (большой + средний)  → правый клик / камера
  🤏 Щипок (большой + безымян.) → скролл
  ✊ Кулак                      → пауза

ПРАВАЯ рука — ДЖОЙСТИК + действия:
  Рука ВВЕРХ от центра          → W (удержание)
  Рука ВНИЗ от центра           → S (удержание)
  Рука ВЛЕВО от центра          → A (удержание)
  Рука ВПРАВО от центра         → D (удержание)
  ✊ Кулак                      → перекалибровка центра
  🤏 Щипок большой + указат.   → Space (тап)
  🤏 Щипок большой + средний   → 1 (тап)
  🤏 Щипок большой + безымян.  → 2 (тап)
  🤏 Щипок большой + мизинец   → 3 (тап)
  🤙 Мизинец вверх + ост. вниз → E (тап)

Выход: клавиша Q
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import ctypes
import ctypes.wintypes
import time
import math
import os
import sys

# ──────────────────── Windows SendInput API ────────────────────
# Работает на самом низком уровне — видят ВСЕ приложения и игры

user32 = ctypes.windll.user32

# Константы мыши
INPUT_MOUSE       = 0
INPUT_KEYBOARD    = 1
MOUSEEVENTF_MOVE      = 0x0001
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010
MOUSEEVENTF_WHEEL     = 0x0800
MOUSEEVENTF_ABSOLUTE  = 0x8000
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_SCANCODE    = 0x0008


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_ushort),
        ("wScan",       ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("iu",   INPUT_UNION),
    ]


def _screen_size():
    """Размер экрана."""
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _send_mouse(flags, x=0, y=0, data=0):
    """Отправить событие мыши через SendInput."""
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.iu.mi.dx = x
    inp.iu.mi.dy = y
    inp.iu.mi.mouseData = data
    inp.iu.mi.dwFlags = flags
    inp.iu.mi.time = 0
    inp.iu.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def mouse_move(x, y):
    """Переместить курсор в абсолютные координаты экрана."""
    sw, sh = _screen_size()
    # SendInput использует координаты 0..65535
    abs_x = int(x * 65536 / sw)
    abs_y = int(y * 65536 / sh)
    _send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, abs_x, abs_y)


def mouse_down(button='left'):
    """Нажать кнопку мыши."""
    flag = MOUSEEVENTF_LEFTDOWN if button == 'left' else MOUSEEVENTF_RIGHTDOWN
    _send_mouse(flag)


def mouse_up(button='left'):
    """Отпустить кнопку мыши."""
    flag = MOUSEEVENTF_LEFTUP if button == 'left' else MOUSEEVENTF_RIGHTUP
    _send_mouse(flag)


def mouse_click(button='left'):
    """Клик (нажать + отпустить)."""
    down = MOUSEEVENTF_LEFTDOWN if button == 'left' else MOUSEEVENTF_RIGHTDOWN
    up = MOUSEEVENTF_LEFTUP if button == 'left' else MOUSEEVENTF_RIGHTUP
    _send_mouse(down | up)


def mouse_scroll(amount):
    """Скролл колесом. amount > 0 = вверх, < 0 = вниз."""
    _send_mouse(MOUSEEVENTF_WHEEL, data=int(amount))


def _send_key(sc: int, up: bool = False):
    """Отправить scan-код через SendInput (работает в играх)."""
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.iu.ki.wVk        = 0
    inp.iu.ki.wScan      = sc
    inp.iu.ki.dwFlags    = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    inp.iu.ki.time       = 0
    inp.iu.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def update_keys(new_keys: set, held_keys: set) -> set:
    """Удержание: отпустить снятые клавиши, нажать новые."""
    for sc in held_keys - new_keys:
        _send_key(sc, up=True)
    for sc in new_keys - held_keys:
        _send_key(sc, up=False)
    return new_keys


def tap_key(sc: int):
    """Одиночный тап: нажать и сразу отпустить."""
    _send_key(sc, up=False)
    _send_key(sc, up=True)

# ──────────────────────────── НАСТРОЙКИ ────────────────────────────

CAM_WIDTH = 640
CAM_HEIGHT = 480
# CAM_INDEX задается в начале main()

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(base_dir, "hand_landmarker.task")

# Зона управления (ROI)
ROI_LEFT = 0.1
ROI_TOP = 0.1
ROI_RIGHT = 0.9
ROI_BOTTOM = 0.9

# Сглаживание курсора
SMOOTHING = 0.3

# Порог расстояния для щипка
PINCH_THRESHOLD = 0.05

# Максимальное перемещение курсора для квалификации как «клик» (пиксели)
CLICK_MOVE_TOLERANCE = 30

# Максимальная длительность для квалификации как «клик» (секунды)
CLICK_TIME_TOLERANCE = 0.25

# Порог для кулака
FIST_THRESHOLD = 0.25

# Скорость скролла (пикселей движения ладони → единиц скролла)
SCROLL_SPEED = 8000

# Задержка перед mouseDown(пкм) — курсор успевает устакаться (секунд)
RIGHT_DRAG_DELAY = 0.08

# ==========================================
#         НАСТРОЙКИ ДЖОЙСТИКА (ПРАВАЯ РУКА)
# ==========================================

# Включить ли управление второй рукой (джойстик и клавиатура)?
# True  = Управление двумя руками.
# False = Работает только мышь (левая рука), HUD джойстика скрыт.
ENABLE_KEYBOARD_HAND = True

# Сохранять ли центр джойстика, если рука пропадает из кадра?
# True  = Центр остаётся фиксированным. Вы калибруете его ОДИН раз (показав кулак), 
#         и он остаётся там же, даже если вы опустите и поднимете руку.
# False = Каждый раз, когда рука появляется в кадре, центр ставится в текущую точку.
JOYSTICK_PERSISTENT_CENTER = False

# Порог срабатывания WASD. 
# Увеличьте (например, 0.15), чтобы нужно было двигать руку дальше.
# Уменьшите (например, 0.08), чтобы кнопки нажимались от малейшего движения.
STICK_THRESHOLD = 0.12

# ==========================================
#                 ТАП-ЖЕСТЫ
# ==========================================

# Дебаунс жеста "Мизинец вверх" (секунд)
TAP_DEBOUNCE = 0.15

# Кулдаун между повторными тапами одной клавиши при щипке (секунд)
PINCH_TAP_COOLDOWN = 0.35

# Scan-коды клавиш (работают во всех играх через DirectInput/RawInput)
# wVk=0, wScan=<scancode>, dwFlags=KEYEVENTF_SCANCODE
SC_W = 0x11
SC_A = 0x1E
SC_S = 0x1F
SC_D = 0x20
SC_E    = 0x12
SC_1    = 0x02
SC_2    = 0x03
SC_3    = 0x04
SC_SPACE = 0x39

# Алиасы для HUD (используем scan-коды как ключи)
VK_W     = SC_W
VK_A     = SC_A
VK_S     = SC_S
VK_D     = SC_D
VK_E     = SC_E
VK_1     = SC_1
VK_2     = SC_2
VK_3     = SC_3
VK_SPACE = SC_SPACE

# Цвета (BGR)
COLOR_ROI        = (80, 80, 80)
COLOR_LANDMARK   = (0, 255, 128)
COLOR_CONNECTION = (80, 80, 80)
COLOR_PALM       = (255, 200, 0)
COLOR_STATUS_BG  = (20, 20, 20)
COLOR_IDLE       = (100, 100, 100)
COLOR_MOVE       = (0, 255, 128)
COLOR_LCLICK     = (0, 180, 255)
COLOR_RCLICK     = (255, 100, 50)
COLOR_LDRAG      = (50, 50, 255)
COLOR_RDRAG      = (200, 50, 200)
COLOR_PAUSE      = (180, 180, 0)
COLOR_SCROLL     = (100, 255, 255)
COLOR_KB_ACTIVE  = (0, 220, 255)
COLOR_KB_BG      = (25, 25, 25)
COLOR_KB_BORDER  = (70, 70, 70)

# Индексы ключевых точек
WRIST      = 0
THUMB_TIP  = 4
INDEX_MCP  = 5
INDEX_PIP  = 6
INDEX_TIP  = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_TIP = 12
RING_MCP   = 13
RING_PIP   = 14
RING_TIP   = 16
PINKY_MCP  = 17
PINKY_PIP  = 18
PINKY_TIP  = 20

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]


# ──────────────────────────── ФУНКЦИИ ────────────────────────────


def get_palm_center(landmarks):
    """Центр ладони."""
    pts = [landmarks[i] for i in (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)]
    return sum(p.x for p in pts) / 5, sum(p.y for p in pts) / 5


def dist(a, b):
    """Расстояние между двумя landmarks."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def is_fist(landmarks):
    """Кулак — все кончики пальцев близко к запястью."""
    w = landmarks[WRIST]
    return all(dist(landmarks[t], w) < FIST_THRESHOLD
               for t in (INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP))


def _up(lm, tip, pip):
    """Палец явно вытянут: кончик значительно выше PIP."""
    return lm[tip].y < lm[pip].y - 0.035


def _down(lm, tip, mcp):
    """Палец явно согнут: кончик ниже или на уровне MCP."""
    return lm[tip].y > lm[mcp].y - 0.01


def detect_number_gesture(lm) -> int:
    """
    Строгая детекция цифровых жестов по паттерну вверх/вниз:
      1 = указ вверх,  сред+безым+миз вниз
      2 = указ+сред вверх, безым+миз вниз
      3 = указ+сред+безым вверх, миз вниз
      4 = мизинец вверх, указ+сред+безым вниз  (Space)
      0 = ничего
    """
    idx_up  = _up(lm,   INDEX_TIP,  INDEX_PIP)
    mid_up  = _up(lm,   MIDDLE_TIP, MIDDLE_PIP)
    rng_up  = _up(lm,   RING_TIP,   RING_PIP)
    pnk_up  = _up(lm,   PINKY_TIP,  PINKY_PIP)

    idx_dn  = _down(lm, INDEX_TIP,  INDEX_MCP)
    mid_dn  = _down(lm, MIDDLE_TIP, MIDDLE_MCP)
    rng_dn  = _down(lm, RING_TIP,   RING_MCP)
    pnk_dn  = _down(lm, PINKY_TIP,  PINKY_MCP)

    if idx_up  and mid_dn and rng_dn and pnk_dn:  return 1
    if idx_up  and mid_up and rng_dn and pnk_dn:  return 2
    if idx_up  and mid_up and rng_up and pnk_dn:  return 3
    if pnk_up  and idx_dn and mid_dn and rng_dn:  return 4  # Space
    return 0


def map_to_screen(x, y, sw, sh):
    """ROI → экран."""
    nx = max(0, min(1, (x - ROI_LEFT) / (ROI_RIGHT - ROI_LEFT)))
    ny = max(0, min(1, (y - ROI_TOP) / (ROI_BOTTOM - ROI_TOP)))
    return nx * sw, ny * sh


def draw_hand(frame, landmarks, w, h, lm_color=COLOR_LANDMARK):
    """Скелет руки."""
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for s, e in HAND_CONNECTIONS:
        if s < len(pts) and e < len(pts):
            cv2.line(frame, pts[s], pts[e], COLOR_CONNECTION, 1)
    for p in pts:
        cv2.circle(frame, p, 2, lm_color, -1)


def draw_kb_hud(frame, held_keys: set, pinch_keys: set, anchor_set: bool,
                dx: float = 0.0, dy: float = 0.0):
    """HUD джойстика + действий."""
    # Ряд 1: WASD (джойстик)
    row1 = [('W', VK_W), ('A', VK_A), ('S', VK_S), ('D', VK_D)]
    # Ряд 2: действия (пинчи + space)
    row2 = [('E', VK_E), ('1', VK_1), ('2', VK_2), ('3', VK_3), ('SPC', VK_SPACE)]
    layout = [row1, row2]
    kw, kh, pad = 32, 26, 4
    ox, oy = 10, 10
    max_cols = max(len(r) for r in layout)
    bw = max_cols * (kw + pad) + pad
    bh = len(layout) * (kh + pad) + pad
    overlay = frame.copy()
    cv2.rectangle(overlay, (ox - pad, oy - pad), (ox + bw, oy + bh + pad), COLOR_KB_BG, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    all_active = held_keys | pinch_keys
    for ri, row in enumerate(layout):
        for ci, (label, vk) in enumerate(row):
            x = ox + ci * (kw + pad)
            y = oy + ri * (kh + pad)
            active = vk in all_active
            bg  = COLOR_KB_ACTIVE if active else (45, 45, 45)
            txt = (0, 0, 0) if active else (180, 180, 180)
            cv2.rectangle(frame, (x, y), (x + kw, y + kh), bg, -1)
            cv2.rectangle(frame, (x, y), (x + kw, y + kh), COLOR_KB_BORDER, 1)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.putText(frame, label, (x + (kw-tw)//2, y + (kh+th)//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, txt, 1)
    # Мини-джойстик индикатор
    jx = ox + max_cols * (kw + pad) + 18
    jy = oy + bh // 2 + pad
    cv2.circle(frame, (jx, jy), 14, (60, 60, 60), -1)
    cv2.circle(frame, (jx, jy), 14, COLOR_KB_BORDER, 1)
    dot_x = int(jx + max(-12, min(12, dx * 80)))
    dot_y = int(jy + max(-12, min(12, dy * 80)))
    dot_c = COLOR_KB_ACTIVE if anchor_set else (100, 100, 100)
    cv2.circle(frame, (dot_x, dot_y), 4, dot_c, -1)
    lbl = "JOY" if anchor_set else "CAL"
    cv2.putText(frame, lbl, (jx - 10, jy + 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (120, 120, 120), 1)


def draw_pinch_line(frame, landmarks, w, h, tip_id, pinching):
    """Линия щипка между большим пальцем и целевым пальцем."""
    t = landmarks[THUMB_TIP]
    f = landmarks[tip_id]
    p1 = (int(t.x * w), int(t.y * h))
    p2 = (int(f.x * w), int(f.y * h))
    color = (0, 0, 255) if pinching else (100, 100, 100)
    thickness = 3 if pinching else 1
    cv2.line(frame, p1, p2, color, thickness)
    if pinching:
        cv2.circle(frame, p1, 6, color, -1)
        cv2.circle(frame, p2, 6, color, -1)


def draw_palm_dot(frame, landmarks, w, h, color=COLOR_PALM):
    """Точка в центре ладони."""
    cx, cy = get_palm_center(landmarks)
    px, py = int(cx * w), int(cy * h)
    cv2.circle(frame, (px, py), 8, color, -1)
    cv2.circle(frame, (px, py), 12, color, 2)


def draw_status_bar(frame, text, color, fps):
    """Статус-бар."""
    fh, fw = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, fh - 45), (fw, fh), COLOR_STATUS_BG, -1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
    cv2.putText(frame, text, (15, fh - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, f"FPS: {int(fps)}", (fw - 100, fh - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)


def draw_roi(frame):
    """Уголки ROI."""
    fh, fw = frame.shape[:2]
    x1, y1 = int(ROI_LEFT * fw), int(ROI_TOP * fh)
    x2, y2 = int(ROI_RIGHT * fw), int(ROI_BOTTOM * fh)
    c = 20
    for cx, cy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
        dx = c if cx == x1 else -c
        dy = c if cy == y1 else -c
        cv2.line(frame, (cx, cy), (cx + dx, cy), COLOR_ROI, 2)
        cv2.line(frame, (cx, cy), (cx, cy + dy), COLOR_ROI, 2)


# ──────────────────────────── MAIN ────────────────────────────

def main():
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Model not found: {MODEL_PATH}")
        return

    sw, sh = _screen_size()
    print(f"[INFO] Screen: {sw}x{sh}")

    print("\n--- Выбор камеры ---")
    try:
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        devices = graph.get_input_devices()
        if devices:
            print("Доступные камеры:")
            for i, dev_name in enumerate(devices):
                print(f"  [{i}] {dev_name}")
        else:
            print("Камеры не найдены или нет доступа к именам.")
    except Exception:
        print("Не удалось получить список камер с именами.")

    val = input("\nВведите номер камеры [Нажмите Enter для выбора 0]: ")
    cam_index = int(val.strip()) if val.strip().isdigit() else 0

    print("\n--- Режим управления ---")
    print("Включить вторую руку (джойстик WASD и клавиатура)?")
    val_kb = input("Введите 'y' (Да) или 'n' (Нет) [Нажмите Enter для 'y']: ")
    global ENABLE_KEYBOARD_HAND
    if val_kb.strip().lower() in ['n', 'net', 'no', '0', 'н', 'нет']:
        ENABLE_KEYBOARD_HAND = False
    else:
        ENABLE_KEYBOARD_HAND = True

    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    if not cap.isOpened():
        print("[ERROR] Camera failed!")
        return

    print("[INFO] Camera OK. Press Q to quit.")
    print("  Right hand: pinch index=click, middle=rclick, ring=scroll, fist=pause")
    print("  Left  hand: pinch index=W, middle=S, ring=A, pinky=D, fist=E")
    print("              1/2/3 fingers up = keys 1/2/3")

    latest_result = [None]

    def on_result(result, output_image, timestamp_ms):
        latest_result[0] = result

    landmarker = vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=2,
            min_hand_detection_confidence=0.6,
            min_tracking_confidence=0.5,
            result_callback=on_result,
        )
    )

    # ─── Состояние ───
    prev_x, prev_y = sw / 2, sh / 2
    prev_time = time.time()

    # Левый щипок (index)
    l_pinching = False
    l_start_time = 0.0
    l_start_x, l_start_y = 0.0, 0.0
    l_dragging = False

    # Правый щипок (middle)
    r_pinching = False
    r_start_time = 0.0
    r_start_x, r_start_y = 0.0, 0.0
    r_dragging = False
    r_drag_pending = False  # ждём 80мс перед mouseDown(right)

    # Скролл (ring)
    s_pinching = False
    s_start_palm_y = 0.0
    s_accum = 0.0  # накопленный скролл

    # Клавиатурная рука — джойстик
    kb_held: set  = set()    # удерживаемые WASD
    kb_anchor_x: float = 0.5
    kb_anchor_y: float = 0.5
    kb_anchored: bool  = False
    kb_dx: float = 0.0
    kb_dy: float = 0.0
    # Пинч-тапы (E/1/2/3) и Space
    kb_pinch_was    = [False, False, False, False]  # idx/mid/rng/pnk
    kb_pinch_cd     = [0.0,   0.0,   0.0,   0.0 ]  # кулдаун каждого
    kb_pinch_active: set = set()   # для HUD
    kb_space_cand: bool  = False
    kb_space_since: float = 0.0
    kb_space_fired: bool  = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        frame_ts_ms = int(time.time() * 1000)
        landmarker.detect_async(mp_image, frame_ts_ms)

        now = time.time()
        fps = 1.0 / (now - prev_time) if (now - prev_time) > 0 else 0
        prev_time = now

        draw_roi(frame)

        gesture_text = "No hand"
        gesture_color = COLOR_IDLE

        result = latest_result[0]

        # ─── Разделяем руки по handedness ───
        mouse_lm = None
        kb_lm    = None
        if result and result.hand_landmarks:
            for i, hand_lm in enumerate(result.hand_landmarks):
                label = "Right"
                if i < len(result.handedness) and result.handedness[i]:
                    label = result.handedness[i][0].category_name
                # После cv2.flip: "Left" = физически левая рука (мышь)
                if label == "Left":
                    mouse_lm = hand_lm
                else:
                    kb_lm = hand_lm

        # ════════ ПРАВАЯ РУКА — мышь ════════
        if mouse_lm:
            lm = mouse_lm
            draw_hand(frame, lm, w, h)

            l_dist = dist(lm[THUMB_TIP], lm[INDEX_TIP])
            r_dist = dist(lm[THUMB_TIP], lm[MIDDLE_TIP])
            s_dist = dist(lm[THUMB_TIP], lm[RING_TIP])

            l_now = l_dist < PINCH_THRESHOLD
            r_now = r_dist < PINCH_THRESHOLD
            s_now = s_dist < PINCH_THRESHOLD

            draw_pinch_line(frame, lm, w, h, INDEX_TIP,  l_now)
            draw_pinch_line(frame, lm, w, h, MIDDLE_TIP, r_now)
            draw_pinch_line(frame, lm, w, h, RING_TIP,   s_now)

            fist = is_fist(lm)

            if fist and not l_now and not r_now and not s_now:
                # ✊ ПАУЗА
                gesture_text = "PAUSE"
                gesture_color = COLOR_PAUSE
                draw_palm_dot(frame, lm, w, h, COLOR_PAUSE)

                # Сбрасываем всё
                if l_dragging:
                    mouse_up('left')
                    l_dragging = False
                if r_dragging:
                    mouse_up('right')
                    r_dragging = False
                s_pinching = False

            else:
                # ─── Двигаем курсор ВСЕГДА ───
                palm_x, palm_y = get_palm_center(lm)
                tx, ty = map_to_screen(palm_x, palm_y, sw, sh)
                smooth_x = prev_x + (tx - prev_x) * (1 - SMOOTHING)
                smooth_y = prev_y + (ty - prev_y) * (1 - SMOOTHING)
                mouse_move(smooth_x, smooth_y)
                prev_x, prev_y = smooth_x, smooth_y

                draw_palm_dot(frame, lm, w, h)

                # ─── ЛЕВЫЙ ЩИПОК (index) → клик / drag ───

                if l_now and not l_pinching:
                    # Начало левого щипка → сразу mouseDown
                    l_pinching = True
                    l_start_time = now
                    l_start_x, l_start_y = smooth_x, smooth_y
                    mouse_down('left')
                    l_dragging = True

                elif not l_now and l_pinching:
                    # Отпускание левого щипка
                    l_pinching = False
                    mouse_up('left')

                    duration = now - l_start_time
                    moved = math.sqrt((smooth_x - l_start_x)**2 + (smooth_y - l_start_y)**2)

                    if duration < CLICK_TIME_TOLERANCE and moved < CLICK_MOVE_TOLERANCE:
                        # Быстрое нажатие + не двигался → клик
                        gesture_text = "CLICK!"
                        gesture_color = COLOR_LCLICK

                    l_dragging = False

                # ─── ПРАВЫЙ ЩИПОК (middle) → правый клик / камера ───

                if r_now and not r_pinching:
                    # Начало щипка: запоминаем время, не жмём мышь сразу
                    r_pinching = True
                    r_drag_pending = True
                    r_start_time = now
                    r_start_x, r_start_y = smooth_x, smooth_y

                elif r_pinching and r_drag_pending and not r_dragging:
                    # Курсор устаканился — теперь жмём ПКМ
                    if now - r_start_time >= RIGHT_DRAG_DELAY:
                        mouse_down('right')
                        r_dragging = True
                        r_drag_pending = False

                elif not r_now and r_pinching:
                    # Отпускание
                    r_pinching = False
                    r_drag_pending = False
                    if r_dragging:
                        mouse_up('right')
                        r_dragging = False
                    duration = now - r_start_time
                    moved = math.sqrt((smooth_x - r_start_x)**2 + (smooth_y - r_start_y)**2)
                    if duration < CLICK_TIME_TOLERANCE and moved < CLICK_MOVE_TOLERANCE:
                        mouse_click('right')
                        gesture_text = "R-CLICK!"
                        gesture_color = COLOR_RCLICK

                # ─── СКРОЛЛ (ring) → большой + безымянный ───

                if s_now and not s_pinching:
                    # Начало скролла
                    s_pinching = True
                    palm_x, palm_y = get_palm_center(lm)
                    s_start_palm_y = palm_y
                    s_accum = 0.0

                elif not s_now and s_pinching:
                    # Конец скролла
                    s_pinching = False

                elif s_pinching:
                    # Скроллим по дельте вертикального движения ладони
                    palm_x, palm_y = get_palm_center(lm)
                    delta_y = s_start_palm_y - palm_y  # вверх = положительный скролл
                    scroll_amount = delta_y * SCROLL_SPEED
                    s_accum += scroll_amount
                    s_start_palm_y = palm_y

                    # Отправляем скролл порциями (120 = 1 «щелчок» колеса)
                    while abs(s_accum) >= 120:
                        if s_accum > 0:
                            mouse_scroll(120)
                            s_accum -= 120
                        else:
                            mouse_scroll(-120)
                            s_accum += 120

                # ─── Текст статуса ───
                if s_pinching:
                    gesture_text = "SCROLL"
                    gesture_color = COLOR_SCROLL
                elif l_dragging and r_dragging:
                    gesture_text = "L+R HOLD"
                    gesture_color = COLOR_LDRAG
                elif l_dragging:
                    duration = now - l_start_time
                    if duration >= CLICK_TIME_TOLERANCE:
                        gesture_text = "L-DRAG"
                        gesture_color = COLOR_LDRAG
                    else:
                        gesture_text = "..."
                        gesture_color = COLOR_LCLICK
                elif r_dragging:
                    duration = now - r_start_time
                    if duration >= CLICK_TIME_TOLERANCE:
                        gesture_text = "R-HOLD"
                        gesture_color = COLOR_RDRAG
                    else:
                        gesture_text = "..."
                        gesture_color = COLOR_RCLICK
                else:
                    gesture_text = "MOVE"
                    gesture_color = COLOR_MOVE

        else:
            # Мышь-рука пропала
            if l_dragging:
                mouse_up('left')
                l_dragging = False
                l_pinching = False
            if r_dragging:
                mouse_up('right')
                r_dragging = False
                r_pinching = False
            s_pinching = False

        # ════════ ПРАВАЯ РУКА — джойстик + действия ════════
        if ENABLE_KEYBOARD_HAND:
            if kb_lm:
                lm = kb_lm
                draw_hand(frame, lm, w, h, lm_color=(200, 100, 255))

                fist2 = is_fist(lm)
                palm_x, palm_y = get_palm_center(lm)

                # ── Кулак → перекалибровка центра ──
                if fist2:
                    kb_anchor_x, kb_anchor_y = palm_x, palm_y
                    kb_anchored = True
                    kb_held = update_keys(set(), kb_held)
                    kb_dx, kb_dy = 0.0, 0.0
                else:
                    # ── Автокалибровка при первом появлении ──
                    if not kb_anchored:
                        kb_anchor_x, kb_anchor_y = palm_x, palm_y
                        kb_anchored = True

                    kb_dx = palm_x - kb_anchor_x
                    kb_dy = palm_y - kb_anchor_y

                    # ── WASD джойстик ──
                    hold_now: set = set()
                    if kb_dx < -STICK_THRESHOLD: hold_now.add(SC_A)
                    if kb_dx >  STICK_THRESHOLD: hold_now.add(SC_D)
                    if kb_dy < -STICK_THRESHOLD: hold_now.add(SC_W)
                    if kb_dy >  STICK_THRESHOLD: hold_now.add(SC_S)
                    kb_held = update_keys(hold_now, kb_held)

                    # ── Пинч-тапы: Space / 1 / 2 / 3 ──
                    pinch_dists = [
                        dist(lm[THUMB_TIP], lm[INDEX_TIP]),
                        dist(lm[THUMB_TIP], lm[MIDDLE_TIP]),
                        dist(lm[THUMB_TIP], lm[RING_TIP]),
                        dist(lm[THUMB_TIP], lm[PINKY_TIP]),
                    ]
                    pinch_keys_map = [SC_SPACE, SC_1, SC_2, SC_3]
                    vk_keys_map    = [VK_SPACE, VK_1, VK_2, VK_3]
                    kb_pinch_active = set()
                    for pi in range(4):
                        tip_ids = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
                        active = pinch_dists[pi] < PINCH_THRESHOLD
                        draw_pinch_line(frame, lm, w, h, tip_ids[pi], active)
                        if active:
                            kb_pinch_active.add(vk_keys_map[pi])
                        if active and not kb_pinch_was[pi]:
                            if now - kb_pinch_cd[pi] >= PINCH_TAP_COOLDOWN:
                                tap_key(pinch_keys_map[pi])
                                kb_pinch_cd[pi] = now
                        kb_pinch_was[pi] = active

                    # ── E: мизинец вверх, остальные вниз ──
                    g = detect_number_gesture(lm)
                    e_now = (g == 4)
                    if e_now:
                        if not kb_space_cand:
                            kb_space_cand = True
                            kb_space_since = now
                            kb_space_fired = False
                        elif not kb_space_fired and now - kb_space_since >= TAP_DEBOUNCE:
                            tap_key(SC_E)
                            kb_space_fired = True
                            kb_pinch_active.add(VK_E)
                    else:
                        kb_space_cand = False
                        kb_space_fired = False
            else:
                # Рука пропала
                kb_held = update_keys(set(), kb_held)
                if not JOYSTICK_PERSISTENT_CENTER:
                    kb_anchored = False
                kb_pinch_was = [False, False, False, False]
                kb_pinch_active = set()
                kb_space_cand = False
                kb_space_fired = False
                kb_dx, kb_dy = 0.0, 0.0

            draw_kb_hud(frame, kb_held, kb_pinch_active, kb_anchored, kb_dx, kb_dy)
        
        draw_status_bar(frame, gesture_text, gesture_color, fps)
        cv2.imshow("Hand Cursor", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if l_dragging:
        mouse_up('left')
    if r_dragging:
        mouse_up('right')
    update_keys(set(), kb_held)  # отпустить все клавиши

    landmarker.close()
    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Done.")


if __name__ == "__main__":
    main()
