import sqlite3
import os

class DBHandler:
    def __init__(self, server='zero3', scope='sell'):
        self.server = server
        self.scope = scope
        self.db_path = f'items_{server}_{scope}.db'  # Her sunucu+scope için ayrı DB
        self._init_database()
        
        # icons klasörünü oluştur
        os.makedirs('icons', exist_ok=True)
    
    def _init_database(self):
        """Veritabanını hazırla"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Önce tablo var mı kontrol et
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        table_exists = c.fetchone()
        
        if not table_exists:
            # Tablo yoksa yeni yapıyla oluştur
            c.execute('''
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    name TEXT UNIQUE,
                    price INTEGER,
                    icon_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("✓ Yeni veritabanı oluşturuldu")
        else:
            # Tablo varsa, server ve scope sütunları var mı kontrol et
            c.execute("PRAGMA table_info(items)")
            columns = [column[1] for column in c.fetchall()]
            
            if 'server' not in columns:
                c.execute('ALTER TABLE items ADD COLUMN server TEXT')
                c.execute(f'UPDATE items SET server = "{self.server}" WHERE server IS NULL')
                print("✓ 'server' sütunu eklendi")
            
            if 'scope' not in columns:
                c.execute('ALTER TABLE items ADD COLUMN scope TEXT')
                c.execute(f'UPDATE items SET scope = "{self.scope}" WHERE scope IS NULL')
                print("✓ 'scope' sütunu eklendi")
        
        conn.commit()
        conn.close()
        print(f"✓ Veritabanı hazır ({self.db_path})")
    
    def list_all_items(self):
        """Veritabanındaki tüm itemları listele"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM items')
        total = c.fetchone()[0]
        print(f"\n{'='*60}")
        print(f"[{self.server}/{self.scope}] Toplam {total} item bulundu")
        print(f"{'='*60}\n")
        
        c.execute('SELECT id, server, scope, name, price, created_at FROM items ORDER BY id')
        items = c.fetchall()
        
        for item in items:
            print(f"[{item[0]}] {item[1]}/{item[2]} - {item[3]:<30} {item[4]:<15} ({item[5]})")
        
        conn.close()
    
    def search_item(self, search_term: str):
        """Item ara"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT id, name, price FROM items 
            WHERE name LIKE ? 
            ORDER BY name
        ''', (f'%{search_term}%',))
        
        items = c.fetchall()
        print(f"\n'{search_term}' için {len(items)} sonuç bulundu:\n")
        
        for item in items:
            print(f"[{item[0]}] {item[1]} - {item[2]}")
        
        conn.close()
    
    def get_stats(self):
        """İstatistikler"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM items')
        total = c.fetchone()[0]
        
        c.execute('SELECT COUNT(DISTINCT price) FROM items')
        unique_prices = c.fetchone()[0]
        
        print(f"\n📊 İstatistikler [{self.server}/{self.scope}]:")
        print(f"Toplam item: {total}")
        print(f"Farklı fiyat: {unique_prices}")
        
        conn.close()
        
    def delete_item(self, item_id: int):
        """ID'ye göre item sil"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT name FROM items WHERE id = ?', (item_id,))
        item = c.fetchone()
        
        if item:
            c.execute('DELETE FROM items WHERE id = ?', (item_id,))
            conn.commit()
            print(f"✓ '{item[0]}' silindi (ID: {item_id})")
        else:
            print(f"✗ ID {item_id} bulunamadı")
        
        conn.close()

    def delete_multiple(self, item_ids: list):
        """Birden fazla item sil"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        deleted = 0
        for item_id in item_ids:
            c.execute('SELECT name FROM items WHERE id = ?', (item_id,))
            item = c.fetchone()
            
            if item:
                c.execute('DELETE FROM items WHERE id = ?', (item_id,))
                deleted += 1
                print(f"✓ '{item[0]}' silindi (ID: {item_id})")
            else:
                print(f"✗ ID {item_id} bulunamadı")
        
        conn.commit()
        conn.close()
        print(f"\nToplam {deleted} item silindi")

# Kullanım örneği:
if __name__ == "__main__":
    handler = DBHandler(server='zero3', scope='sell')
    
    # Örnek kullanım - bir sayfa işle
    # img = handler.screen_capture.capture_region(...)
    # handler.process_img(img, page_number=1)
    
    # Tüm itemları listele
 
    # İstatistikleri göster
    
    # for i in range(24799,24835):
    #     handler.delete_item(i)
 
    # handler.delete_multiple([14121, 14122, 14123])
    
    handler.list_all_items()
    
    handler.get_stats()
    # Arama yap
    # handler.search_item("sword")