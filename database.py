import sqlite3
import os
from typing import List, Tuple, Optional

class Database:
    def __init__(self, server: str = 'zero3', scope: str = 'sell'):
        """
        Database bağlantısını başlat
        
        Args:
            server: Sunucu adı (zero3, zero5, vs.)
            scope: İşlem tipi (sell, buy)
        """
        self.server = server
        self.scope = scope
        self.db_path = f'items_{server}_{scope}.db'
        
        # icons klasörünü oluştur
        os.makedirs('icons', exist_ok=True)
        
        # Database'i başlat
        self._init_database()
    
    def _init_database(self):
        """Veritabanını oluştur veya güncelle"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Tablo var mı kontrol et
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        table_exists = c.fetchone()
        
        if not table_exists:
            # Yeni tablo oluştur
            c.execute('''
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    icon_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(server, scope, name)
                )
            ''')
            print(f"✓ Yeni veritabanı oluşturuldu: {self.db_path}")
        else:
            # Mevcut tabloya sütun ekle (gerekirse)
            c.execute("PRAGMA table_info(items)")
            columns = [col[1] for col in c.fetchall()]
            
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
        print(f"✓ Veritabanı hazır: {self.db_path}")
    
    # ============ INSERT ============
    
    def insert_item(self, name: str, price: int, icon_path: str) -> bool:
        """Tek bir item ekle"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT INTO items (server, scope, name, price, icon_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.server, self.scope, name, price, icon_path))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            print(f"⚠ '{name}' zaten mevcut")
            return False
        except Exception as e:
            print(f"✗ Hata: {e}")
            return False
    
    def insert_items_batch(self, items: List[Tuple[str, int, str]]):
        """Birden fazla item ekle (toplu)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        inserted = 0
        for name, price, icon_path in items:
            try:
                c.execute('''
                    INSERT INTO items (server, scope, name, price, icon_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (self.server, self.scope, name, price, icon_path))
                inserted += 1
            except sqlite3.IntegrityError:
                continue
        
        conn.commit()
        conn.close()
        print(f"✓ {inserted}/{len(items)} item eklendi")
        return inserted
    
    # ============ SELECT ============
    
    def get_all_items(self) -> List[Tuple]:
        """Tüm itemları getir"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM items ORDER BY id')
        items = c.fetchall()
        conn.close()
        return items
    
    def get_item_by_id(self, item_id: int) -> Optional[Tuple]:
        """ID'ye göre item getir"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM items WHERE id = ?', (item_id,))
        item = c.fetchone()
        conn.close()
        return item
    
    def search_items(self, search_term: str) -> List[Tuple]:
        """İsme göre arama yap"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT * FROM items 
            WHERE name LIKE ? 
            ORDER BY name
        ''', (f'%{search_term}%',))
        items = c.fetchall()
        conn.close()
        return items
    
    def get_items_by_price_range(self, min_price: int, max_price: int) -> List[Tuple]:
        """Fiyat aralığına göre getir"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT * FROM items 
            WHERE price BETWEEN ? AND ?
            ORDER BY price
        ''', (min_price, max_price))
        items = c.fetchall()
        conn.close()
        return items
    
    # ============ DELETE ============
    
    def delete_item(self, item_id: int) -> bool:
        """ID'ye göre item sil"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT name FROM items WHERE id = ?', (item_id,))
        item = c.fetchone()
        
        if item:
            c.execute('DELETE FROM items WHERE id = ?', (item_id,))
            conn.commit()
            conn.close()
            print(f"✓ '{item[0]}' silindi (ID: {item_id})")
            return True
        
        conn.close()
        print(f"✗ ID {item_id} bulunamadı")
        return False
    
    def delete_items_batch(self, item_ids: List[int]):
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
        
        conn.commit()
        conn.close()
        print(f"\nToplam {deleted}/{len(item_ids)} item silindi")
        return deleted
    
    def clear_all_items(self):
        """TÜM itemları sil (DİKKAT!)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('DELETE FROM items')
        conn.commit()
        conn.close()
        print("⚠ Tüm itemlar silindi!")
    
    # ============ UPDATE ============
    
    def update_price(self, item_id: int, new_price: int) -> bool:
        """Item fiyatını güncelle"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('UPDATE items SET price = ? WHERE id = ?', (new_price, item_id))
        affected = c.rowcount
        conn.commit()
        conn.close()
        
        if affected > 0:
            print(f"✓ ID {item_id} fiyatı güncellendi: {new_price}")
            return True
        print(f"✗ ID {item_id} bulunamadı")
        return False
    
    # ============ STATS ============
    
    def get_stats(self):
        """İstatistikleri göster"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM items')
        total = c.fetchone()[0]
        
        c.execute('SELECT COUNT(DISTINCT name) FROM items')
        unique_names = c.fetchone()[0]
        
        c.execute('SELECT AVG(price) FROM items')
        avg_price = c.fetchone()[0]
        
        c.execute('SELECT MIN(price), MAX(price) FROM items')
        min_price, max_price = c.fetchone()
        
        conn.close()
        
        print(f"\n{'='*60}")
        print(f"📊 İstatistikler [{self.server}/{self.scope}]")
        print(f"{'='*60}")
        print(f"Toplam item       : {total:,}")
        print(f"Benzersiz item    : {unique_names:,}")
        print(f"Ortalama fiyat    : {int(avg_price):,}" if avg_price else "Ortalama fiyat    : -")
        print(f"En ucuz           : {min_price:,}" if min_price else "En ucuz           : -")
        print(f"En pahalı         : {max_price:,}" if max_price else "En pahalı         : -")
        print(f"{'='*60}\n")
        
        return {
            'total': total,
            'unique': unique_names,
            'avg_price': avg_price,
            'min_price': min_price,
            'max_price': max_price
        }
    
    def list_items(self, limit: int = 50):
        """İlk N item'ı listele"""
        items = self.get_all_items()
        
        print(f"\n{'='*60}")
        print(f"[{self.server}/{self.scope}] Toplam {len(items)} item")
        print(f"{'='*60}\n")
        
        for item in items[:limit]:
            print(f"[{item[0]}] {item[3]:<30} {item[4]:>12,} ({item[6]})")
        
        if len(items) > limit:
            print(f"\n... ve {len(items) - limit} item daha")
    
    # ============ UTILITY ============
    
    def export_to_csv(self, filename: str = None):
        """CSV'ye aktar"""
        if not filename:
            filename = f'items_{self.server}_{self.scope}.csv'
        
        import csv
        items = self.get_all_items()
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Server', 'Scope', 'Name', 'Price', 'Icon', 'Created'])
            writer.writerows(items)
        
        print(f"✓ {len(items)} item '{filename}' dosyasına aktarıldı")


# ============ KULLANIM ÖRNEKLERİ ============

if __name__ == "__main__":
    # Database oluştur
    db = Database(server='zero3', scope='sell')
    
    # İstatistikler
    db.get_stats()
    
    # Listeleme
    db.list_items(limit=10)
    
    # Arama
    # results = db.search_items("bow")
    # print(f"{len(results)} sonuç bulundu")
    
    # Yeni item ekle
    # db.insert_item("Test Sword", 1000000, "icons/test.png")
    
    # Toplu ekleme
    # items = [
    #     ("Item 1", 100, "icons/item1.png"),
    #     ("Item 2", 200, "icons/item2.png"),
    # ]
    # db.insert_items_batch(items)
    
    # Silme
    # db.delete_item(123)
    # db.delete_items_batch([1, 2, 3])
    
    # Fiyat güncelleme
    # db.update_price(item_id=100, new_price=5000000)
    
    # CSV'ye aktar
    # db.export_to_csv()