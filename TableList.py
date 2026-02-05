import numpy as np
from vision import ScreenCapture
import cv2,os
import sqlite3


class TableListHandler:
    def __init__(self):
        self.column_spacing = [0, 24, 25, 26, 25, 25, 25, 25, 27, 28]
        self.screen_capture = ScreenCapture()
        self.db_path = 'items.db'
        self._init_database()
        os.makedirs('icons', exist_ok=True),
        
    def _init_database(self):
        """Veritabanını hazırla"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price INTEGER,
                icon_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        
    def process_img(self, img: np.ndarray) :
        """Process the captured image region"""
        
        y_offset = 0
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        for idx, space in enumerate(self.column_spacing):
            y_offset += space
            
            
            item_name = img[y_offset+3:y_offset+22, 21:280]
            item_price = img[y_offset+3:y_offset+22, 345:455]
            icon = img[y_offset+1:y_offset+20, 1:20]
            
            name = self.screen_capture.getTextfromImage(item_name, text_type="item")
            price = self.screen_capture.getTextfromImage(item_price, text_type="price")

            print(f"Item: {name}, Price: {price}")
            icon_path = f"icons/{name}.png"
            if not os.path.exists(icon_path):
                cv2.imwrite(icon_path, icon)
            
        #     # Veritabanına ekle
        #     c.execute('''
        #         INSERT INTO items (name, price, icon_path)
        #         VALUES (?, ?, ?)
        #     ''', (name, price, icon_path))
        
        # conn.commit()
        # conn.close()