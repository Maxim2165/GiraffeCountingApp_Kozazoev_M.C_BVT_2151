from flask import Flask, request, jsonify, render_template, send_file  # Импортирую Flask для создания веб-сервера
import cv2  # Импортирую OpenCV для работы с изображениями
import numpy as np  # Импортирую NumPy для работы с массивами
from ultralytics import YOLO  # Импортирую YOLOv8 для детекции объектов
import sqlite3  # Импортирую SQLite для базы данных
from datetime import datetime  # Импортирую datetime для работы с датой и временем
import json  # Импортирую json для обработки данных
import os  # Импортирую os для работы с файлами
from reportlab.lib.pagesizes import letter  # Импортирую размер страницы для PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer  # Импортирую компоненты для создания PDF
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # Импортирую стили для PDF
from reportlab.lib.units import inch  # Импортирую единицы измерения для PDF
from openpyxl import Workbook  # Импортирую Workbook для работы с Excel
from openpyxl.styles import Font  # Импортирую Font для стилизации текста в Excel
import time  # Импортирую time для измерения времени обработки

# Создаю экземпляр Flask для моего веб-сервера
app = Flask(__name__)

# Загружаю предобученную модель YOLOv8 для детекции жирафов
model = YOLO('yolov8n.pt')

# Определяю путь к файлу базы данных SQLite
db_path = os.path.join(os.getcwd(), 'history.db')
# Подключаюсь к базе данных SQLite
conn = sqlite3.connect(db_path, check_same_thread=False)
# Создаю курсор для выполнения SQL-запросов
cursor = conn.cursor()

# Создаю таблицу requests, если её нет, с нужными колонками
cursor.execute('''CREATE TABLE IF NOT EXISTS requests 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, result TEXT, processing_time REAL, filename TEXT)''')
# Проверяю структуру таблицы
cursor.execute("PRAGMA table_info(requests)")
# Получаю список колонок таблицы
columns = [col[1] for col in cursor.fetchall()]
# Добавляю колонку processing_time, если её нет
if 'processing_time' not in columns:
    cursor.execute("ALTER TABLE requests ADD COLUMN processing_time REAL")
# Добавляю колонку filename, если её нет
if 'filename' not in columns:
    cursor.execute("ALTER TABLE requests ADD COLUMN filename TEXT")
# Сохраняю изменения в базе
conn.commit()

# Проверяю наличие папки static и создаю её, если её нет
if not os.path.exists('static'):
    os.makedirs('static')

# Функция для генерации PDF-отчета с деталями
def generate_pdf_report(giraffe_count, timestamp, processing_time, filename, giraffe_details):
    # Определяю путь для сохранения PDF
    pdf_path = os.path.join('static', f'report_{timestamp}.pdf')
    # Создаю документ PDF с заданными размерами и отступами
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=1.25*inch, rightMargin=1.25*inch, topMargin=1.25*inch, bottomMargin=1.25*inch)
    # Загружаю базовые стили
    styles = getSampleStyleSheet()
    # Определяю стиль для обычного текста
    custom_style = ParagraphStyle(name='CustomNormal', parent=styles['Normal'], fontSize=14, leading=21, alignment=0)
    # Определяю стиль для жирного текста
    custom_bold_style = ParagraphStyle(name='CustomBold', parent=styles['Normal'], fontSize=14, leading=21, fontName='Helvetica-Bold')
    # Определяю стиль для заголовка
    custom_heading = ParagraphStyle(name='CustomHeading', parent=styles['Heading1'], fontSize=20, alignment=1)
    # Указываю путь к обработанному изображению
    img_path = os.path.join('static', 'result.jpg')
    # Создаю список элементов для PDF
    elements = [Paragraph("Giraffe Detection Report", custom_heading),  # Добавляю заголовок
                Paragraph(f"File: {filename}", custom_style),  # Добавляю имя файла
                Paragraph(f"Date and Time: {timestamp}", custom_style),  # Добавляю дату и время
                Paragraph(f"Processing Time: {processing_time:.2f} sec", custom_style)]  # Добавляю время обработки
    # Если жирафы есть, добавляю их количество и координаты
    if giraffe_count > 0:
        elements.append(Paragraph(f"Number of Giraffes Detected: {giraffe_count}", custom_style))
        for i, (x, y, w, h) in enumerate(giraffe_details, 1):
            elements.append(Paragraph(f"Giraffe #{i}: Coordinates (x={x:.1f}, y={y:.1f}, width={w:.1f}, height={h:.1f})", custom_style))
    else:
        elements.append(Paragraph("No giraffes detected or invalid image format", custom_style))  # Сообщение при отсутствии жирафов
    # Если изображение существует, добавляю его
    if os.path.exists(img_path):
        elements.append(Spacer(1, 12))  # Добавляю отступ
        elements.append(Paragraph("Processed Image", custom_bold_style))  # Добавляю заголовок изображения
        img = Image(img_path)  # Загружаю изображение
        img_width, img_height = img.drawWidth, img.drawHeight  # Получаю размеры изображения
        max_width, max_height = 400, 600  # Устанавливаю максимальные размеры
        if img_width > max_width or img_height > max_height:
            ratio = min(max_width / img_width, max_height / img_height)  # Расчитываю коэффициент масштабирования
            img.drawWidth = img_width * ratio  # Масштабирую ширину
            img.drawHeight = img_height * ratio  # Масштабирую высоту
        img.hAlign = 'CENTER'  # Центрирую изображение
        elements.append(img)  # Добавляю изображение в документ
    # Собираю и сохраняю PDF
    doc.build(elements)
    return pdf_path  # Возвращаю путь к созданному PDF

# Функция для генерации Excel-отчета с деталями
def generate_excel_report(giraffe_count, timestamp, processing_time, filename, giraffe_details):
    # Определяю путь для сохранения Excel
    excel_path = os.path.join('static', f'report_{timestamp}.xlsx')
    # Создаю новую книгу Excel
    wb = Workbook()
    # Активирую активный лист
    ws = wb.active
    # Назначаю название листа
    ws.title = "Giraffe Detection"
    # Объединяю ячейки для заголовка
    ws.merge_cells('A1:B1')
    # Заполняю заголовок
    ws['A1'] = "Giraffe Detection Report"
    # Делаю заголовок жирным
    ws['A1'].font = Font(bold=True)
    # Добавляю метку для имени файла
    ws['A2'] = "File"
    # Заполняю имя файла
    ws['B2'] = filename
    # Добавляю метку для даты
    ws['A3'] = "Date and Time"
    # Заполняю дату и время
    ws['B3'] = timestamp
    # Добавляю метку для времени обработки
    ws['A4'] = "Processing Time (sec)"
    # Заполняю время обработки
    ws['B4'] = round(processing_time, 2)
    # Если жирафы есть, добавляю их данные
    if giraffe_count > 0:
        ws['A5'] = "Number of Giraffes"  # Метка для количества
        ws['B5'] = giraffe_count  # Количество жирафов
        for i, (x, y, w, h) in enumerate(giraffe_details, 1):
            ws[f"A{i+5}"] = f"Giraffe #{i}"  # Номер жирафа
            ws[f"B{i+5}"] = f"x={x:.1f}, y={y:.1f}, width={w:.1f}, height={h:.1f}"  # Координаты
    else:
        ws['A5'] = "Status"  # Метка для статуса
        ws['B5'] = "No giraffes detected or invalid image format"  # Статус при отсутствии жирафов
    # Сохраняю файл Excel
    wb.save(excel_path)
    return excel_path  # Возвращаю путь к созданному Excel

# Функция для получения истории обработок
def get_history():
    # Запрашиваю последние 5 записей из базы
    cursor.execute('SELECT timestamp, result, processing_time, filename FROM requests ORDER BY id DESC LIMIT 5')
    # Получаю все строки результата
    history = cursor.fetchall()
    # Создаю пустой список для обработанной истории
    parsed_history = []
    # Прохожу по каждой записи
    for item in history:
        timestamp, result_json, processing_time, filename = item  # Распаковываю данные
        result_data = json.loads(result_json)  # Преобразую JSON в данные
        parsed_history.append((timestamp, result_data['count'], processing_time, filename))  # Добавляю в список
    return parsed_history  # Возвращаю обработанную историю

# Определяю маршрут для главной страницы
@app.route('/')
def index():
    # Получаю историю обработок
    history = get_history()
    # Рендерю HTML-страницу с историей
    return render_template('index.html', history=history)

# Определяю маршрут для обработки изображения
@app.route('/process', methods=['POST'])
def process_image():
    # Проверяю, есть ли файл в запросе
    if 'image' not in request.files:
        return jsonify(error="No image uploaded"), 400
    # Получаю загруженный файл
    file = request.files['image']
    # Сохраняю имя файла
    filename = file.filename
    # Проверяю, что файл имеет правильное расширение
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
        return jsonify(error="Invalid file format. Please upload an image (e.g., .png, .jpg, .jpeg)"), 400
    # Читаю данные файла
    img_data = file.read()
    # Проверяю, что файл не пустой
    if not img_data:
        return jsonify(error="Empty file uploaded"), 400
    # Декодирую изображение
    img = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
    # Проверяю, успешно ли декодировано
    if img is None:
        return jsonify(error="Failed to decode image. Please upload a valid image file"), 400
    # Записываю время начала обработки
    start_time = time.time()
    # Обрабатываю изображение моделью
    results = model(img)
    # Создаю визуализацию результатов
    output_img = results[0].plot()
    # Вычисляю время обработки
    processing_time = time.time() - start_time
    # Инициализирую счетчик жирафов
    giraffe_count = 0
    # Создаю список для деталей жирафов
    giraffe_details = []
    # Прохожу по всем обнаруженным объектам
    for box in results[0].boxes:
        class_id = int(box.cls[0])  # Получаю ID класса
        class_name = results[0].names[class_id]  # Получаю имя класса
        # Если объект - жираф, добавляю в счетчик и детали
        if class_name == "giraffe":
            giraffe_count += 1
            x, y, w, h = box.xywh[0].tolist()
            giraffe_details.append((x, y, w, h))
    # Сохраняю обработанное изображение
    cv2.imwrite(os.path.join('static', 'result.jpg'), output_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    # Форматирую текущую дату и время
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    # Подготавливаю данные для записи в базу
    result_data = {'count': giraffe_count, 'classes': results[0].names}
    # Добавляю запись в базу данных
    cursor.execute('INSERT INTO requests (timestamp, result, processing_time, filename) VALUES (?, ?, ?, ?)', 
                  (timestamp, json.dumps(result_data), processing_time, filename))
    # Сохраняю изменения в базе
    conn.commit()
    # Генерирую PDF-отчет
    pdf_path = generate_pdf_report(giraffe_count, timestamp, processing_time, filename, giraffe_details)
    # Генерирую Excel-отчет
    excel_path = generate_excel_report(giraffe_count, timestamp, processing_time, filename, giraffe_details)
    # Выводлю пути к созданным отчетам
    print(f"PDF отчет: {pdf_path}, Excel отчет: {excel_path}")
    # Возвращаю результат в JSON
    return jsonify({'count': giraffe_count, 'timestamp': timestamp})

# Определяю маршрут для получения истории
@app.route('/get_history')
def get_history_route():
    # Получаю историю обработок
    history = get_history()
    # Возвращаю историю в формате JSON
    return jsonify(history)

# Определяю маршрут для очистки истории
@app.route('/clear_history', methods=['POST'])
def clear_history():
    # Удаляю все записи из таблицы
    cursor.execute('DELETE FROM requests')
    # Сохраняю изменения
    conn.commit()
    # Возвращаю успешный статус
    return jsonify({'status': 'success'})

# Определяю маршрут для скачивания отчета
@app.route('/download_report/<report_type>')
def download_report(report_type):
    # Получаю timestamp из запроса
    timestamp = request.args.get('timestamp', '')
    # Если timestamp не указан, беру последнюю запись
    if not timestamp:
        cursor.execute('SELECT timestamp, filename FROM requests ORDER BY id DESC LIMIT 1')
    # Иначе ищу запись по timestamp
    else:
        cursor.execute('SELECT timestamp, filename FROM requests WHERE timestamp = ?', (timestamp,))
    # Получаю результат
    latest = cursor.fetchone()
    # Проверяю, есть ли записи
    if not latest:
        return "No reports available", 404
    # Распаковываю данные
    timestamp, filename = latest
    # Если запрашивают PDF
    if report_type == 'pdf':
        file_path = os.path.join('static', f'report_{timestamp}.pdf')  # Путь к PDF
        # Проверяю существование файла и отправляю его
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=f'report_{filename}.pdf')
        return "PDF not found", 404  # Ошибка, если PDF не найден
    # Если запрашивают Excel
    elif report_type == 'excel':
        file_path = os.path.join('static', f'report_{timestamp}.xlsx')  # Путь к Excel
        # Проверяю существование файла и отправляю его
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=f'report_{filename}.xlsx')
        return "Excel not found", 404  # Ошибка, если Excel не найден
    # Ошибка при неверном типе отчета
    return "Invalid report type", 400

if __name__ == '__main__':
    # Запускаю сервер на всех интерфейсах с отладкой
    app.run(host='0.0.0.0', port=5000, debug=True)