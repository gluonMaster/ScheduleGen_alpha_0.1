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

      /* === РљРЅРѕРїРєР° "РњРµРЅСЋ" === */
      #menuButton {{
         background-color: #6c757d;
         color: #fff;
         border: 1px solid #5a6268;
         padding: 8px 12px;
         margin-right: 15px;
         margin-bottom: 5px;
         cursor: pointer;
         border-radius: 4px;
         font-size: 14px;
         font-weight: bold;
         transition: background-color 0.2s;
      }}

      #menuButton:hover {{
         background-color: #5a6268;
      }}

      /* === Р’С‹РїР°РґР°СЋС‰РµРµ РјРµРЅСЋ === */
      #menuDropdown {{
         display: none;
         position: absolute;
         top: 50px;
         left: 10px;
         background: #fff;
         border: 1px solid #ccc;
         border-radius: 8px;
         box-shadow: 0 4px 12px rgba(0,0,0,0.15);
         z-index: 10001;
         min-width: 240px;
         padding: 6px 0;
      }}

      #menuDropdown.open {{
         display: block;
      }}

      .menu-item {{
         padding: 10px 20px;
         cursor: pointer;
         font-size: 14px;
         color: #333;
         white-space: nowrap;
      }}

      .menu-item:hover {{
         background-color: #f0f0f0;
      }}

      /* === РљРЅРѕРїРєР° СѓРґР°Р»РµРЅРёСЏ РєРѕР»РѕРЅРєРё РІ Р·Р°РіРѕР»РѕРІРєРµ === */
      .col-delete-btn {{
         display: none;
         position: absolute;
         top: 2px;
         right: 2px;
         width: 16px;
         height: 16px;
         line-height: 14px;
         font-size: 12px;
         text-align: center;
         color: #c00;
         background: rgba(255,255,255,0.85);
         border: 1px solid #c00;
         border-radius: 3px;
         cursor: pointer;
         padding: 0;
         z-index: 5;
      }}

      .col-delete-btn::before {{
         content: '×';
      }}

      .schedule-grid thead th:hover .col-delete-btn {{
         display: block;
      }}

      .schedule-grid thead th.time-cell .col-delete-btn {{
         display: none !important;
      }}

      /* === РњРѕРґР°Р»СЊРЅРѕРµ РѕРєРЅРѕ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ (РјРµРЅСЋ) === */
      .menu-modal-overlay {{
         display: none;
         position: fixed;
         top: 0; left: 0; right: 0; bottom: 0;
         background: rgba(0,0,0,0.4);
         z-index: 10100;
         justify-content: center;
         align-items: center;
      }}

      .menu-modal-overlay.open {{
         display: flex;
      }}

      .menu-modal {{
         background: #fff;
         border-radius: 8px;
         padding: 28px 32px;
         box-shadow: 0 8px 24px rgba(0,0,0,0.2);
         max-width: 420px;
         width: 90%;
         text-align: center;
      }}

      .menu-modal p {{
         font-size: 15px;
         margin-bottom: 20px;
         color: #333;
      }}

      .menu-modal-btn-yes {{
         background: #28a745;
         color: #fff;
         border: none;
         padding: 10px 22px;
         border-radius: 4px;
         cursor: pointer;
         font-size: 14px;
         margin-right: 10px;
      }}

      .menu-modal-btn-yes:hover {{
         background: #218838;
      }}

      .menu-modal-btn-cancel {{
         background: #dc3545;
         color: #fff;
         border: none;
         padding: 10px 22px;
         border-radius: 4px;
         cursor: pointer;
         font-size: 14px;
      }}

      .menu-modal-btn-cancel:hover {{
         background: #c82333;
      }}

      /* === Vertical resize: block being resized === */
      .activity-block.resizing {{
         border-bottom: 2px dashed #1976d2;
         opacity: 0.85;
      }}

      /* === Vertical resize: cursor near bottom edge === */
      .activity-block[data-resize-hover] {{
         cursor: ns-resize;
      }}
    </style>
    """
