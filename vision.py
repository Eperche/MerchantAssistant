from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import cv2
import time
import logging
import re
import mss

logger = logging.getLogger(__name__)
import threading

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
 

@dataclass(frozen=True)
class CaptureConfig:
    """Screen capture configuration"""

    fps: int = 100
    party_check_interval: float = 2.0
    hp_check_interval: float = 2.0
    template_threshold: float = 0.8

    captcha_text_check_interval: float = 2.0
    ft_enter_button_check_interval: float = 2.0

    template_dir: Path = Path("Templates")


@dataclass
class TemplateMatch:
    """Result of template matching"""

    left: int
    top: int
    width: int
    height: int
    confidence: float
    region_img: np.ndarray

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)


class TemplateCache:
    """Cache templates to avoid repeated disk I/O"""

    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self._cache: dict[str, np.ndarray] = {}

    def get(self, name: str) -> Optional[np.ndarray]:
        """Get template from cache or load from disk"""
        if name not in self._cache:
            path = self.template_dir / name
            if not path.exists():
                logger.warning(f"Template not found: {path}")
                return None

            template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                logger.error(f"Failed to load template: {path}")
                return None

            self._cache[name] = template
            logger.debug(f"Cached template: {name}")

        return self._cache[name]

    def clear(self) -> None:
        """Clear template cache"""
        self._cache.clear()


class RateLimiter:
    """Generic rate limiter for operations"""

    def __init__(self, interval: float):
        self.interval = interval
        self._last_check = 0

    def should_run(self) -> bool:
        """Check if enough time has passed"""
        now = time.time()
        if now - self._last_check >= self.interval:
            self._last_check = now

            return True

        return False

    def reset(self) -> None:
        """Reset the timer"""
        self._last_check = 0


class ScreenCapture:
    """
    Efficient screen capture with template matching

    Features:
    - FPS-limited screen capture
    - Template caching (no repeated disk I/O)
    - Rate-limited template searches
    - Grayscale frame caching
    """

    def __init__(self, config: Optional[CaptureConfig] = None):

        self.config = config or CaptureConfig()

        # Frame management
        self._frame: Optional[np.ndarray] = None

        self._gray_frame: Optional[np.ndarray] = None
        self._frame_limiter = RateLimiter(1 / self.config.fps)

        # Template management
        self.template_cache = TemplateCache(self.config.template_dir)

        self._thread_local = threading.local()

        # 1) Ekran çözünürlüğü
        with mss.mss() as sct:  # Geçici kullan
            screen = sct.monitors[1]

        sw, sh = screen["width"], screen["height"]

        config_data = {
            "top_offset": 300,
            "left_offset": 50,
            "width_ratio": 1,
            "height_ratio": 1,
        }
        height_ratio = config_data.get("height_ratio", 2 / 3)
        width_ratio = config_data.get("width_ratio", 2 / 3)
        left_offset = config_data.get("left_offset", 50)
        top_offset = config_data.get("top_offset", 300)
        if width_ratio == 1 and height_ratio == 1:
            self.region = {"top": 0, "left": 0, "width": sw, "height": sh}
        else:
            # 2) Orta nokta
            cx, cy = sw // 2, sh // 2
            self.region = {
                "top": cy - top_offset,
                "left": left_offset,
                "width": int(sw * width_ratio),
                "height": int(sh * height_ratio),
            }

        # with mss.mss() as sct:

        #     sct_img = sct.grab(self.region)
        #     mss.tools.to_png(sct_img.rgb, sct_img.size, output="sample.png")

        logger.info(f"ScreenCapture initialized: {self.config.fps} FPS")

    def _get_sct(self):
        """Her thread için ayrı MSS instance döndür"""
        if not hasattr(self._thread_local, "sct"):
            self._thread_local.sct = mss.mss()
            logger.debug(
                f"Created MSS instance for thread {threading.current_thread().name}"
            )
        return self._thread_local.sct

    def update(self, full_region=False) -> bool:
        """
        Update screen capture and tracked elements

        Returns:
            True if frame was captured, False if rate limited
        """
        # Capture new frame if needed
        frame_updated = self._capture_frame(full_region)

        if self._frame is None:
            return False

        return frame_updated

    def _capture_frame(self, full_region) -> bool:
        """Capture screen if FPS limit allows"""
        if not self._frame_limiter.should_run():
            return False

        try:
            # ✅ Thread-safe MSS kullan
            sct = self._get_sct()

            if full_region:
                monitor = sct.monitors[1]
                img = np.array(sct.grab(monitor), dtype=np.uint8)
            else:
                img = np.array(sct.grab(self.region), dtype=np.uint8)

            # BGRA → BGR (alpha atılır, renk korunur)
            self._frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Gray cache invalidate
            self._gray_frame = None
            return True

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return False

    def _get_gray_frame(self) -> Optional[np.ndarray]:
        """Get grayscale version of current frame (cached)"""
        if self._frame is None:
            return None

        if self._gray_frame is None:
            self._gray_frame = cv2.cvtColor(self._frame, cv2.COLOR_BGR2GRAY)

        return self._gray_frame

    def close(self):
        """Release MSS resources"""
        # ✅ Thread-local MSS'leri temizle
        if hasattr(self._thread_local, "sct"):
            self._thread_local.sct.close()
            delattr(self._thread_local, "sct")
            logger.debug("Closed MSS instance")

    def check_custom_location(
        self, template_name: str, region=None
    ) -> Optional[TemplateMatch]:

        try:
            with mss.mss() as sct:
                if region:
                    sct_img = sct.grab(region)
                else:
                    monitor = sct.monitors[1]  # Primary monitor
                    sct_img = sct.grab(monitor)

                self._frame = np.array(sct_img)[:, :, :3]  # BGRA -> BGR
                self._gray_frame = None

        except Exception as e:
            print(f"Error: {e}")

        match = self.find_template(f"{template_name}.png")

        if match:

            # logger.debug(f"found at: {match.bbox}")
            return match
        else:

            # logger.debug(" not found")
            return None

    def find_template(
        self, template_name: str, threshold: Optional[float] = None, full_region=False
    ) -> Optional[TemplateMatch]:
        """
        Find template on current frame

        Args:
            template_name: Filename of template in pictures folder
            threshold: Match confidence threshold (0-1)

        Returns:
            TemplateMatch if found, None otherwise
        """
        template_name = f"{template_name}.png"

        gray = self._get_gray_frame()
        if gray is None:
            return None

        template = self.template_cache.get(template_name)
        if template is None:
            return None

        threshold = threshold or self.config.template_threshold

        try:
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                if full_region:
                    real_left = max_loc[0]
                    real_top = max_loc[1]
                else:
                    real_left = self.region["left"] + max_loc[0]
                    real_top = self.region["top"] + max_loc[1]

                region_img = self._frame[
                    max_loc[1] + 148 : max_loc[1] + 148 + 255,
                    max_loc[0] + 264 : max_loc[0] + 264 + 463,
                ]

                h, w = template.shape
                return TemplateMatch(
                    left=real_left,
                    top=real_top,
                    width=w,
                    height=h,
                    confidence=float(max_val),
                    region_img=region_img,
                )

        except Exception as e:
            logger.error(f"Template matching failed for {template_name}: {e}")

        return max_val

    # Public getters

    def getText(self):
        gray = self._get_gray_frame()
        text = pytesseract.image_to_string(gray)
        return text

    def getTextfromImage(self, image: np.ndarray, text_type: str) -> str:
        # BGR formatında renk aralıkları
        # Kırmızı: (0, 0, 209)
        # Kahverengi/Turuncu: (165, 130, 254)
        # Sarı: (1, 197, 238)
        # Mor/Pembe: (198, 124, 199)
        # Açık Sarı: (0, 254, 254)
        
        # Kırmızı maske
        lower_red = np.array([0, 0, 180])
        upper_red = np.array([50, 50, 255])
        red_mask = cv2.inRange(image, lower_red, upper_red)
        
        # Kahverengi/Turuncu maske
        lower_brown = np.array([140, 100, 230])
        upper_brown = np.array([190, 160, 255])
        brown_mask = cv2.inRange(image, lower_brown, upper_brown)
        
        # Sarı maske
        lower_yellow = np.array([0, 170, 210])
        upper_yellow = np.array([30, 230, 255])
        yellow_mask = cv2.inRange(image, lower_yellow, upper_yellow)
        
        # Açık Sarı maske (BGR: düşük B, yüksek G, yüksek R)
        lower_light_yellow = np.array([0, 230, 230])
        upper_light_yellow = np.array([30, 255, 255])
        light_yellow_mask = cv2.inRange(image, lower_light_yellow, upper_light_yellow)
        
        # Mor/Pembe maske
        lower_purple = np.array([170, 100, 170])
        upper_purple = np.array([230, 160, 230])
        purple_mask = cv2.inRange(image, lower_purple, upper_purple)
        
        # Tüm maskeleri birleştir
        colored_mask = red_mask | brown_mask | yellow_mask | light_yellow_mask | purple_mask
        
        # Renkli metin var mı kontrol et
        has_colored_text = np.any(colored_mask > 0)
        
        if has_colored_text:
            # Renkli varsa beyaza çevir
            image_copy = image.copy()
            image_copy[colored_mask > 0] = [255, 255, 255]
            gray = cv2.cvtColor(image_copy, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            process_img = binary
        else:
            # Beyaz itemlar
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            process_img = gray
        
        if text_type == "price":
            config = '--psm 7 -c tessedit_char_whitelist=0123456789'
        else:
            config = '--psm 6'
        
        text = pytesseract.image_to_string(process_img, config=config) 
        if text_type == "item":
            # Sadece harf, rakam, boşluk, (), + karakterleri tut
            text = re.sub(r'[^a-zA-Z0-9\s()+-]', '', text)
        return text.strip()


    @property
    def frame(self) -> Optional[np.ndarray]:
        """Get current RGB frame"""
        return self._frame

    def get_region(self, x: int, y: int, w: int, h: int) -> Optional[np.ndarray]:
        """Extract region from current frame"""
        if self._frame is None:
            return None

        try:
            return self._frame[y : y + h, x : x + w]
        except IndexError:
            logger.warning(f"Region out of bounds: ({x},{y},{w},{h})")
            return None
