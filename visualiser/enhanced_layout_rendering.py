"""
Миксин для рендеринга блоков расписания
Содержит методы для отрисовки блоков со скругленными углами
"""

from color_manager import get_group_color, get_building_color, get_text_color

class BlockRenderingMixin:
    """Миксин с методами для рендеринга блоков расписания"""
    
    def draw_lesson_block(self, canvas, lesson, x, y, width, height, font_name):
        """
        Рисует блок занятия со скругленными углами
        
        Args:
            canvas: PDF-холст
            lesson (dict): Информация о занятии
            x (float): X-координата блока
            y (float): Y-координата блока
            width (float): Ширина блока
            height (float): Высота блока
            font_name (str): Название шрифта
        """
        # Определяем цвета для блока
        fill_color = get_group_color(lesson['group'])
        border_color = get_building_color(lesson['building'])
        text_color = get_text_color(fill_color)
        
        # Устанавливаем цвета
        canvas.setFillColor(fill_color)
        canvas.setStrokeColor(border_color)
        canvas.setLineWidth(self.block_border_width)
        
        # Рисуем прямоугольник со скругленными углами
        self.draw_rounded_rect(canvas, x, y, width, height, self.corner_radius, fill=1, stroke=1)
        
        # Настраиваем шрифт для текста
        canvas.setFillColor(text_color)
        
        # Отступ для текста внутри блока
        text_padding = 3
        text_x = x + text_padding
        text_y = y - text_padding

        # центр блока по горизонтали
        center_x = x + width / 2

        
        # Вычисляем размер шрифта в зависимости от высоты блока
        font_size = min(10, height / 6)
        line_height = font_size + 1
        
        # Рисуем время занятия
        canvas.setFont(font_name, font_size)
        time_text = f"{lesson['start_time']}-{lesson['end_time']}"
        canvas.drawCentredString(center_x, text_y - line_height, time_text)

        
        # Рисуем группу
        bold_font = f"{font_name}-Bold"
        canvas.setFont(bold_font, font_size + 1)
        group_text = self.truncate_text(lesson['group'], width - 2 * text_padding, font_name, font_size + 1, canvas)
        canvas.drawCentredString(center_x, text_y - 2 * line_height, group_text)
        
        # Рисуем преподавателя
        canvas.setFont(font_name, font_size)
        teacher_text = self.truncate_text(lesson['teacher'], width - 2 * text_padding, font_name, font_size, canvas)
        canvas.drawCentredString(center_x, text_y - 3 * line_height, teacher_text)
        
        # Рисуем аудиторию и здание
        location_text = f"{lesson['room']}, {lesson['building']}"
        location_text = self.truncate_text(location_text, width - 2 * text_padding, font_name, font_size, canvas)
        canvas.drawCentredString(center_x, text_y - 4 * line_height, location_text)

    def draw_rounded_rect(self, canvas, x, y, width, height, radius, fill=1, stroke=1):
        """
        Рисует прямоугольник со скруглёнными углами.
        Параметр y у нас — это верхняя граница, а для roundRect нужно y-ниж.
        """
        # ограничиваем радиус
        radius = min(radius, height/2, width/2)

        # переводим y‑коорд. из top-left в bottom-left
        bottom_y = y - height

        canvas.saveState()
        canvas.setLineWidth(self.block_border_width)
        # если нужно закрасить — используем fill, иначе только обводка
        if radius > 0:
            canvas.roundRect(x, bottom_y, width, height, radius,
                            stroke=stroke, fill=fill)
        else:
            canvas.rect(x, bottom_y, width, height,
                        stroke=stroke, fill=fill)
        canvas.restoreState()

    def truncate_text(self, text, max_width, font_name, font_size, canvas):
        """
        Обрезает текст, если он не помещается в заданную ширину
        
        Args:
            text (str): Исходный текст
            max_width (float): Максимальная ширина текста
            font_name (str): Название шрифта
            font_size (float): Размер шрифта
            canvas: PDF-холст
            
        Returns:
            str: Обрезанный текст (с многоточием, если необходимо)
        """
        if not text:
            return ""
        
        # Проверяем ширину текста
        text_width = canvas.stringWidth(text, font_name, font_size)
        
        if text_width <= max_width:
            return text
        
        # Если текст не помещается, обрезаем его
        for i in range(len(text) - 1, 0, -1):
            truncated = text[:i] + "..."
            if canvas.stringWidth(truncated, font_name, font_size) <= max_width:
                return truncated
        
        # Если даже один символ не помещается
        return text[0] + "..."