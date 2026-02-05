import time
import cv2
import os
import sqlite3
import queue
import threading

from vision import ScreenCapture, TemplateMatch
from TableList import TableListHandler
from InterceptionCommunication import InterceptionInput

interception_input = InterceptionInput()
screen_capture = ScreenCapture()
table_handler = TableListHandler()

# Thread-safe queue
processing_queue = queue.Queue()
is_processing = True
NUM_WORKERS = 20  # 20 worker thread


stop_event = threading.Event()

def ocr_worker(worker_id, results_queue):
    """OCR yapar, sonucu queue'ya atar"""
    while is_processing or not processing_queue.empty():
        if stop_event.is_set():
            break
        try:
            page_path = processing_queue.get(timeout=1)
            img = cv2.imread(page_path)
            items = extract_items_from_page(img, page_path)

            if not items:
                print(f"[W{worker_id}] ⛔ {os.path.basename(page_path)} -> Item yok, durma sinyali!")
                stop_event.set()
                processing_queue.task_done()
                break

            results_queue.put(items)
            print(f"[W{worker_id}] ✓ {os.path.basename(page_path)} -> {len(items)} item")
            processing_queue.task_done()
        except queue.Empty:
            continue


def extract_items_from_page(img, page_path):
    """Sayfadan itemları çıkar, database'e yazma"""
    y_offset = 0
    items = []

    for idx, space in enumerate(table_handler.column_spacing):
        y_offset += space

        item_name = img[y_offset+4:y_offset+21, 21:280]
        item_price = img[y_offset+4:y_offset+21, 345:455]
        icon = img[y_offset+1:y_offset+20, 1:20]

        try:
            name = screen_capture.getTextfromImage(item_name, text_type="item")
            price_text = screen_capture.getTextfromImage(item_price, text_type="price")

            name = name.replace('}', '').strip()
            price_text = price_text.strip()

            # Name veya price_text boşsa atlama
            if not name or not price_text:
                print(f"⚠ Atlama: name='{name}' | price_text='{price_text}' (boş)")
                continue

            # Price parsa
            try:
                price = int(price_text)
            except ValueError:
                print(f"⚠ Atlama: price_text='{price_text}' (parse hata)")
                continue

            # Price 0 ise atlama
            if price == 0:
                print(f"⚠ Atlama: name='{name}' | price=0")
                continue

            icon_path = f"icons/{name}.png"
            if not os.path.exists(icon_path):
                cv2.imwrite(icon_path, icon)

            items.append((name, price, icon_path))

        except Exception as e:
            print(f"✗ HATA: {e}")

    return items


def database_writer(results_queue):
    """Tek bir thread tüm database yazımını yapar (lock yok)"""
    while is_processing or not results_queue.empty():
        if stop_event.is_set() and results_queue.empty():
            break
        try:
            items = results_queue.get(timeout=1)

            if not items:
                results_queue.task_done()
                continue

            # Batch insert (tek seferde hepsini yaz)
            conn = sqlite3.connect(table_handler.db_path)
            c = conn.cursor()
            for name, price, icon_path in items: 
                c.execute('''
                    INSERT INTO items (server, scope, name, price, icon_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (table_handler.server, table_handler.scope, name, price, icon_path))
            conn.commit()
            conn.close()
            results_queue.task_done()
        except queue.Empty:
            continue


def collect_pages():
    """Tüm sayfaları PNG olarak kaydet"""
    executed_once = True
    page_count = 0
    last_hash = None

    if os.path.exists('temp_pages'):
        for f in os.listdir('temp_pages'):
            os.remove(os.path.join('temp_pages', f))
    else:
        os.makedirs('temp_pages')

    saved_pages = []

    while True:
        if stop_event.is_set():
            print("\n⛔ Stop sinyali alındı, sayfa toplama durdurulan.")
            break

        screen_capture.update()
        result = screen_capture.find_template("table_left_corner", threshold=0.7)

        if type(result) == TemplateMatch:
            if executed_once:
                lowtohigh_result = screen_capture.find_template("lowtohigh", threshold=0.7)
                if type(lowtohigh_result) == TemplateMatch:
                    interception_input.move(lowtohigh_result.center[0], lowtohigh_result.center[1])
                    interception_input.click("left")
                    time.sleep(0.1)
                executed_once = False
                continue

            region_img = result.region_img
            current_hash = hash(region_img.tobytes())

            if current_hash == last_hash:
                time.sleep(0.1)
                continue

            page_path = f'temp_pages/page_{page_count:04d}.png'
            cv2.imwrite(page_path, region_img)
            saved_pages.append(page_path)
            processing_queue.put(page_path)

            last_hash = current_hash
            page_count += 1
            print(f"✓ Sayfa {page_count} kaydedildi")

 

            next_result = screen_capture.find_template("next", threshold=0.7)
            if type(next_result) == TemplateMatch:
                interception_input.move(next_result.center[0], next_result.center[1])
                interception_input.click("left")
            else:
                print("Next template not found")
                break
        else:
            print("Template not found", result)

        time.sleep(0.02)

    print(f"\n✓ Toplam {len(saved_pages)} sayfa kaydedildi\n")
    return saved_pages


def run_loop():
    global is_processing

    results_queue = queue.Queue()

    # OCR worker thread'leri başlat
    ocr_threads = []
    for i in range(NUM_WORKERS):
        t = threading.Thread(target=ocr_worker, args=(i+1, results_queue), daemon=True)
        t.start()
        ocr_threads.append(t)

    # Database writer thread'i başlat
    db_thread = threading.Thread(target=database_writer, args=(results_queue,), daemon=True)
    db_thread.start()

    print(f"🚀 {NUM_WORKERS} OCR worker başlatıldı\n")
    print("Sayfalar toplanıyor...\n")

    saved_pages = collect_pages()

    if not saved_pages:
        print("Hiç sayfa kaydedilmedi!")
        return

    # OCR queue'nun boşalmasını bekle
    print("\nOCR işlemleri tamamlanıyor...\n")
    while not processing_queue.empty():
        if stop_event.is_set():
            # Kalan sayfaları queue'dan boşalt
            while not processing_queue.empty():
                try:
                    processing_queue.get_nowait()
                    processing_queue.task_done()
                except queue.Empty:
                    break
            break
        time.sleep(0.1)
    processing_queue.join()

    # Database yazımının bitmesini bekle
    print("Database yazılıyor...\n")
    while not results_queue.empty():
        time.sleep(0.1)
    results_queue.join()

    is_processing = False
    stop_event.set()  # Kalan threadları da durdur

    # Thread'lerin bitmesini bekle
    for t in ocr_threads:
        t.join(timeout=2)
    db_thread.join(timeout=2)

    # İstatistikler
    print("\n" + "="*60)
    conn = sqlite3.connect(table_handler.db_path)
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM items')
    total = c.fetchone()[0]

    c.execute('SELECT COUNT(DISTINCT name) FROM items')
    unique_names = c.fetchone()[0]

    print(f"Toplam item: {total}")
    print(f"Farklı item: {unique_names}")
    print(f"Beklenen: {len(saved_pages) * 10}")

    if total < len(saved_pages) * 10:
        print(f"⚠ EKSIK: {len(saved_pages) * 10 - total} item kayıp!")
    else:
        print(f"✓ BAŞARILI: Tüm itemlar kaydedildi!")

    print("="*60)
    conn.close()


if __name__ == "__main__":
    run_loop()
