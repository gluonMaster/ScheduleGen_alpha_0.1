#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для генерации CSS-стилей для HTML-версии расписания.
"""

def get_css_styles(cellHeight, dayCellWidth, timeColWidth, borderWidth=1):
    """
    Возвращает строку с CSS-стилями для HTML-расписания.
    
    Args:
        cellHeight (int): Высота ячейки в пикселях
        dayCellWidth (int): Ширина ячейки дня в пикселях
        timeColWidth (int): Ширина столбца времени в пикселях
        borderWidth (int): Толщина границы ячейки в пикселях
        
    Returns:
        str: CSS-стили
    """
    return f"""
    <style>
      /* Задаём box-sizing для всех элементов */
      * {{
        box-sizing: border-box;
      }}

      /* Общие стили страницы */
      body {{
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 10px;
        background-color: #f8f9fa;
      }}
      
      h1, h2 {{
        color: #333;
        text-align: center;
      }}
      
      /* Контейнер с фиксированной шириной и внутренним отступом */
      .schedule-container {{
         position: relative;
         max-height: 700px;
         overflow: auto;
         border: 1px solid #ccc;
         margin-top: 60px;
         padding-left: 20px;
         box-shadow: 0 2px 5px rgba(0,0,0,0.1);
         background-color: #fff;
      }}
      
      /* Сетка расписания */
      .schedule-grid {{
         border-collapse: collapse;
         table-layout: fixed;
         width: auto;
      }}
      
      .schedule-grid th, .schedule-grid td {{
         border: {borderWidth}px solid #ddd;
         padding: 0;
         margin: 0;
         width: {dayCellWidth}px;
         height: {cellHeight}px;
         text-align: center;
         vertical-align: middle;
         box-sizing: border-box;
      }}
      
      .time-cell {{
         width: {timeColWidth}px;
         background: #f0f0f0;
         position: sticky;
         left: 0;
         z-index: 3;
         font-weight: bold;
         font-size: 12px;
      }}
      
      .schedule-grid thead th {{
         position: sticky;
         top: 0;
         background: #e9ecef;
         z-index: 4;
         padding: 5px;
         font-size: 14px;
         border-bottom: 2px solid #aaa;
         white-space: nowrap;
         overflow: hidden;
      }}
      
      /* Фиксированный блок кнопок */
      .sticky-buttons {{
         position: fixed;
         top: 0;
         left: 0;
         right: 0;
         background: #fff;
         padding: 10px;
         z-index: 9999;
         border-bottom: 1px solid #ccc;
         display: flex;
         flex-wrap: wrap;
         justify-content: center;
         box-shadow: 0 2px 5px rgba(0,0,0,0.1);
      }}
      
      /* Кнопки показа/скрытия рабочего дня */
      .toggle-day-button {{
         background-color: #87CEFA; /* приятный голубой */
         border: 1px solid #ccc;
         padding: 8px 12px;
         margin-right: 5px;
         margin-bottom: 5px;
         cursor: pointer;
         transition: background-color 0.3s;
         border-radius: 4px;
      }}
      
      .toggle-day-button.active {{
         background-color: #4682B4; /* темнее при скрытии */
         color: white;
      }}
      
      /* Кнопки сохранения */
      #saveIntermediate {{
         background-color: #90ee90; /* нежно-зелёный */
         border: 1px solid #ccc;
         padding: 8px 12px;
         cursor: pointer;
         margin-right: 5px;
         margin-bottom: 5px;
         border-radius: 4px;
      }}
      
      #saveSchedule {{
         background-color: #ffcccc; /* бледно-красный */
         border: 1px solid #ccc;
         padding: 8px 12px;
         cursor: pointer;
         margin-bottom: 5px;
         border-radius: 4px;
      }}

      #exportToExcel {{
         background-color: #FFD700; /* золотой */
         border: 1px solid #ccc;
         padding: 8px 12px;
         cursor: pointer;
         margin-left: 15px; /* Увеличенный отступ слева */
         margin-right: 5px;
         margin-bottom: 5px;
         border-radius: 4px;
         font-weight: bold; /* Жирный текст для лучшей видимости */
         box-shadow: 0 2px 4px rgba(0,0,0,0.1); /* Небольшая тень для объема */
      }}
      
      /* Блоки активности с центрированием текста */
      .activity-block {{
         position: absolute;
         cursor: move;
         font-size: 10px;
         line-height: 1.2;
         padding: 3px;
         box-sizing: border-box;
         display: flex;
         flex-direction: column; /* располагать содержимое вертикально */
         justify-content: center; /* вертикальное центрирование */
         align-items: center;     /* горизонтальное центрирование */
         text-align: center;      /* центрирование текста */
         border-radius: 3px;
         box-shadow: 0 1px 3px rgba(0,0,0,0.2);
         overflow: hidden;
         /* Удалено свойство color и text-shadow, они теперь определяются динамически */
      }}
      
      /* Обеспечиваем читаемость текста в блоках */
      .activity-block strong {{
         font-weight: bold;
         margin-bottom: 2px;
      }}
      
      /* Стили для финальной статической версии */
      body.static-schedule .activity-block {{
         cursor: default;
         box-shadow: 0 1px 2px rgba(0,0,0,0.1);
      }}
      
      /* Адаптивность для маленьких экранов */
      @media (max-width: 768px) {{
        .sticky-buttons {{
          flex-direction: column;
          align-items: center;
        }}
        
        .toggle-day-button,
        #saveIntermediate,
        #saveSchedule {{
          width: 100%;
          margin-right: 0;
        }}
      }}
    </style>
    """
