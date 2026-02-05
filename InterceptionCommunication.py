import time
from interception import *
from consts import *
from win32api import GetSystemMetrics
from typing import Optional
 

# Global context - auto_reconnect ile
_global_context = None
_context_retry_count = 0

def get_context(force_recreate=False):
    """Global context'i lazy olarak oluştur"""
    global _global_context, _context_retry_count
    if _global_context is None or force_recreate:
        if _global_context is not None:
            try:
                for dev in _global_context._context:
                    try:
                        if dev is not None:
                            dev.destroy()
                    except:
                        pass
            except:
                pass
        
        time.sleep(1.5)
        interception._context = []
        _global_context = interception()
        _context_retry_count = 0
        
    return _global_context

def recreate_context():
    """Context'i yeniden oluştur - klavye takıldığında çağrılmalı"""
    global _working_keyboard_device
    _working_keyboard_device = None  # Cache'i temizle
    return get_context(force_recreate=True)

# Mouse cihazını bul
def get_mouse_device():
    """İlk ÇALIŞAN mouse cihazını bul"""
    context = get_context()
    
    for i in range(MAX_DEVICES):
        if interception.is_mouse(i):
            try:
                hwid = context.get_HWID(i)
                if hwid and len(hwid) > 0:
                    # ✅ "SYSTEM_MOUSE" içeren cihazı seç
                    if "SYSTEM_MOUSE" in hwid:
                        return i
            except:
                pass
    
    # Fallback: SYSTEM_MOUSE yoksa ilk mouse
    for i in range(MAX_DEVICES):
        if interception.is_mouse(i):
            try:
                hwid = context.get_HWID(i)
                if hwid and len(hwid) > 0:
                    return i
            except:
                pass
    
    return 10  # Son çare
# Klavye cihazını bul (YENI)
_working_keyboard_device = None  # Cache: Çalışan klavye device'ını sakla

def get_keyboard_device():
    """İlk ÇALIŞAN klavye cihazını bul"""
    global _working_keyboard_device
    
    if _working_keyboard_device is not None:
        try:
            context = get_context()
            hwid = context.get_HWID(_working_keyboard_device)
            if hwid and len(hwid) > 0:
                return _working_keyboard_device
        except:
            pass
        _working_keyboard_device = None
    
    context = get_context()
    keyboard_devices = []
    
    for i in range(MAX_DEVICES):
        if interception.is_keyboard(i):
            try:
                hwid = context.get_HWID(i)
                if hwid and len(hwid) > 0:
                    is_main = "MI_00" in hwid or "SYSTEM_KEYBOARD" in hwid
                    keyboard_devices.append((i, hwid, is_main))
            except:
                pass
    
    if not keyboard_devices:
        return None
    
    main_keyboards = [d for d in keyboard_devices if d[2]]
    other_keyboards = [d for d in keyboard_devices if not d[2]]
    
    all_keyboards = main_keyboards + other_keyboards
    if all_keyboards:
        _working_keyboard_device = all_keyboards[0][0]
        return _working_keyboard_device
    
    return None

screen_width = GetSystemMetrics(0)
screen_height = GetSystemMetrics(1)

class ScreenPoint:
    x = 0
    y = 0
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.screen_height = screen_height
        self.screen_width = screen_width

class KeyboardDriver:

    def __init__(self):
        self.driver = get_context()
        
        self.keycodes = {
            "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "F5": 0x3F, "F6": 0x40, "F7": 0x41, "F8": 0x42,
            "F9": 0x43, "F10": 0x44, "F11": 0x57, "F12": 0x58, "F13": 0x64, "F14": 0x65, "F15": 0x66,
            
            "^": 0x3a,
            "CAPSLOCK": 0x3a,
            "SHIFT": 0x36,
            "BACKSPACE": 0xe,
            "ENTER": 0x1c,
            "TAB": 0xF,
            "CTRL": 0x1D,
            "ALT": 0x38,
            "-": 0xD,
            "+": 0x4E,
            
            "0": 0x0B, "1": 0x02, "2": 0x03, "3": 0x04,
            "4": 0x05, "5": 0x06, "6": 0x07, "7": 0x08,
            "8": 0x09, "9": 0x0A,
            
            "A": 0x1E, "B": 0x30, "C": 0x2E, "D": 0x20, "E": 0x12, "F": 0x21, "G": 0x22,
            "H": 0x23, "I": 0x17, "J": 0x24, "K": 0x25, "L": 0x26, "M": 0x32, "N": 0x31,
            "O": 0x18, "P": 0x19, "Q": 0x10, "R": 0x13, "S": 0x1F, "T": 0x14, "U": 0x16,
            "V": 0x2F, "W": 0x11, "X": 0x2D, "Y": 0x15, "Z": 0x2C
        }

    def pressKey(self, value, gecikme):
        value = value.upper()
        if value not in self.keycodes:
            return
        
        # ✅ Her tuşa basışta klavyeyi dinamik olarak bul
        keyboard = get_keyboard_device()
        if keyboard is None:
            print("⚠️ Klavye bulunamadı, 2 saniye bekleniyor...")
            time.sleep(2)  # KVM switch için ekstra bekle
            recreate_context()
            self.driver = get_context()
            keyboard = get_keyboard_device()
            if keyboard is None:
                print("❌ 2. deneme başarısız, 3 saniye daha bekleniyor...")
                time.sleep(3)
                recreate_context()
                self.driver = get_context()
                keyboard = get_keyboard_device()
                if keyboard is None:
                    print("❌ Klavye hala bulunamadı!")
                    return
        
        # DEBUG: Hangi device'a gönderiyoruz?
        # print(f"🎹 Tuş {value} -> Device {keyboard}")
        
        # HWID kontrolü - cihaz bağlı mı?
        try:
            hwid = self.driver.get_HWID(keyboard)
            if not hwid:
                print("⚠️ HWID boş! 2 saniye bekleniyor...")
                time.sleep(2)
                recreate_context()
                self.driver = get_context()
                keyboard = get_keyboard_device()
                if keyboard is None:
                    print("❌ Yenileme başarısız!")
                    return
                print("✅ Context yenilendi")
        except Exception as e:
            print(f"⚠️ HWID hatası: {e}")
            return
        
        key = self.keycodes[value]
        interception_press = key_stroke(key, interception_key_state.INTERCEPTION_KEY_DOWN.value, 0)
        
        self.driver.send(keyboard, interception_press)
        time.sleep(gecikme)
        interception_press.state = interception_key_state.INTERCEPTION_KEY_UP.value
        self.driver.send(keyboard, interception_press)

    def show_stroke(self):
        keyboard = get_keyboard_device()
        if keyboard is None:
            return
        stroke = self.driver.receive(keyboard)
        if type(stroke) is key_stroke:
            if stroke.code != 0:
                print(stroke.code)

class MouseDriver:
    def __init__(self) -> None:
        self.driver = get_context()
        self.mouse = get_mouse_device()
        self._initialized = False 
    
    def _get_mouse(self):
        """Her işlemde mouse'u yeniden bul (context yenilenmiş olabilir)"""
        return get_mouse_device()
        
    def mouseMove(self, position):
        mouse = self._get_mouse()
        x = int((0xFFFF * position.x) / position.screen_width)
        y = int((0xFFFF * position.y) / position.screen_height)
        
        # ✅ İlk harekette FARKLI bir yere dummy gönder
        if not self._initialized:
            dummy = mouse_stroke(0, interception_mouse_flag.INTERCEPTION_MOUSE_MOVE_ABSOLUTE.value, 0, 0, 0, 0)
            self.driver.send(mouse, dummy)
            time.sleep(0.005)  # 5ms
            self._initialized = True
            mouse = self._get_mouse()
            
        mstroke = mouse_stroke(0, interception_mouse_flag.INTERCEPTION_MOUSE_MOVE_ABSOLUTE.value, 0, x, y, 0)
        self.driver.send(mouse, mstroke)

    def leftclick(self, sleep):
        mouse = self._get_mouse()
        mstroke = mouse_stroke(interception_mouse_state.INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN.value, 0, 0, 0, 0, 0)
        self.driver.send(mouse, mstroke)
        time.sleep(sleep)
        mstroke.state = interception_mouse_state.INTERCEPTION_MOUSE_LEFT_BUTTON_UP.value
        self.driver.send(mouse, mstroke)

    def rightclick(self, sleep):
        mouse = self._get_mouse()
        mstroke = mouse_stroke(interception_mouse_state.INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN.value, 0, 0, 0, 0, 0)
        self.driver.send(mouse, mstroke)
        time.sleep(sleep)
        mstroke.state = interception_mouse_state.INTERCEPTION_MOUSE_RIGHT_BUTTON_UP.value
        self.driver.send(mouse, mstroke)

    def mouse_left_down(self):
        mouse = self._get_mouse()
        interception_press = mouse_stroke(interception_mouse_state.INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN.value, 0, 0, 0, 0, 0)
        self.driver.send(mouse, interception_press)

    def mouse_left_up(self):
        mouse = self._get_mouse()
        interception_up = mouse_stroke(interception_mouse_state.INTERCEPTION_MOUSE_LEFT_BUTTON_UP.value, 0, 0, 0, 0, 0)
        self.driver.send(mouse, interception_up)

    def mouse_right_down(self):
        mouse = self._get_mouse()
        interception_press = mouse_stroke(interception_mouse_state.INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN.value, 0, 0, 0, 0, 0)
        self.driver.send(mouse, interception_press)

    def mouse_right_up(self):
        mouse = self._get_mouse()
        interception_up = mouse_stroke(interception_mouse_state.INTERCEPTION_MOUSE_RIGHT_BUTTON_UP.value, 0, 0, 0, 0, 0)
        self.driver.send(mouse, interception_up)

class InterceptionInput:
    def __init__(self) -> None:
        self.kbd = KeyboardDriver()
        self.mouse = MouseDriver()
        self.keys = self.kbd.keycodes
        self.startFlag = False
         
        
        self.ms = 50/1000

    def eventMacro(self, eventType):
        if self.startFlag:
            self.kbd.pressKey("b", self.ms)
            time.sleep(self.ms)
            self.mouse.rightclick(self.ms)
            time.sleep(self.ms)
            self.mouse.leftclick(self.ms)
            
            if eventType == 4:
                self.mouse.leftclick(self.ms)
    
    def move(self, x, y, speed=None):
        self.mouse.mouseMove(ScreenPoint(x, y))
        
    def click(self, button: str = "left"):
        if button == "left":
            self.mouse.leftclick(self.ms)
        elif button == "right":
            self.mouse.rightclick(self.ms)
            
    def key(self, key):
        self.kbd.pressKey(key, self.ms)
 
    def start_macro(self, eventType: int, speed: Optional[float] = 0.01):
        # ✅ Stop flag kontrolü
        if hasattr(self, 'stop_flag') and self.stop_flag.is_set():
            print("🛑 Macro başlamadan durduruldu")
            return
        self.kbd.pressKey("b", self.ms)
        if hasattr(self, 'stop_flag') and self.stop_flag.is_set():
            print("🛑 Macro durduruldu (1. adım)")
            return
        time.sleep(speed)
        self.mouse.rightclick(self.ms)
        if hasattr(self, 'stop_flag') and self.stop_flag.is_set():
            print("🛑 Macro durduruldu (2. adım)")
            return
        time.sleep(speed)
        self.mouse.leftclick(self.ms)
        
        if hasattr(self, 'stop_flag') and self.stop_flag.is_set():
            print("🛑 Macro durduruldu (3. adım)")
            return
        time.sleep(speed)
        if eventType == 2:
            if hasattr(self, 'stop_flag') and self.stop_flag.is_set():
                print("🛑 Macro durduruldu (4. adım)")
                return
            self.mouse.leftclick(self.ms)
            time.sleep(speed)
        
    def enter_captcha(self, captcha: str, coords: tuple[int, int], speed: Optional[float] = 0.01) -> None:
        MIN_SPEED = 0.005
        MAX_SPEED = 0.120
        speed = min(max(speed, MIN_SPEED), MAX_SPEED)

        self.kbd.pressKey(captcha, self.ms)
        self.mouse.mouseMove(ScreenPoint(coords[0], coords[1]))
        self.mouse.leftclick(self.ms)
        
