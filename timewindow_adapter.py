"""
Адаптер для улучшения обработки временных окон в планировании расписания.

Этот модуль предоставляет функциональность для анализа возможности последовательного
размещения занятий с учетом временных окон и создания соответствующих ограничений.
"""

from time_utils import time_to_minutes, minutes_to_time
from sequential_scheduling import can_schedule_sequentially, analyze_tanz_classes
from sequential_scheduling_checker import check_two_window_classes
from time_constraint_utils import create_conflict_variables

def apply_timewindow_improvements(optimizer):
    """
    Применяет улучшения для обработки временных окон к оптимизатору.
    
    Args:
        optimizer: Экземпляр ScheduleOptimizer
        
    Returns:
        bool: True, если улучшения применены успешно
    """
    print("\nApplying timewindow scheduling improvements...")

    # Сбрасываем кэш обработанных проверок между занятиями
    try:
        from sequential_scheduling_checker import reset_window_checks_cache
        reset_window_checks_cache()
    except ImportError:
        print("Warning: Could not reset window checks cache.")
    
    # Словарь для отслеживания уже обработанных пар занятий
    processed_pairs = set()
    
    # Специальная обработка для занятий Tanz с преподавателем Melnikov Olga
    tanz_analysis = analyze_tanz_classes(optimizer)

    # Проверяем, инициализированы ли уже переменные оптимизатора
    if not hasattr(optimizer, 'start_vars') or not optimizer.start_vars:
        print("Warning: Optimizer variables not initialized yet. Call optimizer.build_model() before applying timewindow improvements.")
        return False
    
    if tanz_analysis['num_classes'] >= 2 and tanz_analysis['sequential_possible']:
        print(f"Found {tanz_analysis['num_classes']} Tanz classes with Melnikov Olga that can be scheduled sequentially.")
        
        # Получаем все индексы классов Tanz
        tanz_indices = [class_info['index'] for class_info in tanz_analysis['classes']]
        
        # Сортируем индексы классов Tanz по времени начала окна (от раннего к позднему)
        tanz_indices_sorted = []
        for idx in tanz_indices:
            c = optimizer.classes[idx]
            if c.start_time and c.end_time:
                window_start = time_to_minutes(c.start_time)
                tanz_indices_sorted.append((idx, window_start))
        
        tanz_indices_sorted.sort(key=lambda x: x[1])
        
        # Добавляем жесткие ограничения на последовательное размещение 
        # в порядке от раннего окна к позднему
        if len(tanz_indices_sorted) >= 2:
            for i in range(len(tanz_indices_sorted) - 1):
                idx_i, _ = tanz_indices_sorted[i]
                idx_j, _ = tanz_indices_sorted[i + 1]
                c_i = optimizer.classes[idx_i]
                c_j = optimizer.classes[idx_j]
                
                print(f"Setting preferred sequential ordering for Tanz classes:")
                print(f"  Class {idx_i} ({c_i.start_time}-{c_i.end_time}) should be scheduled before")
                print(f"  Class {idx_j} ({c_j.start_time}-{c_j.end_time})")
                
                # Получаем продолжительность в слотах времени
                duration_i_slots = c_i.duration // optimizer.time_interval
                duration_j_slots = c_j.duration // optimizer.time_interval
                
                # Находим временные слоты для границ окон
                i_start_slot = find_slot_for_time(optimizer.time_slots, c_i.start_time)
                i_end_slot = find_slot_for_time(optimizer.time_slots, c_i.end_time)
                j_start_slot = find_slot_for_time(optimizer.time_slots, c_j.start_time)
                j_end_slot = find_slot_for_time(optimizer.time_slots, c_j.end_time)
                
                # Добавляем ограничения на временные окна
                optimizer.model.Add(optimizer.start_vars[idx_i] >= i_start_slot)
                optimizer.model.Add(optimizer.start_vars[idx_i] + duration_i_slots <= i_end_slot)
                optimizer.model.Add(optimizer.start_vars[idx_j] >= j_start_slot)
                optimizer.model.Add(optimizer.start_vars[idx_j] + duration_j_slots <= j_end_slot)
                
                # Создаем переменную для обозначения конца первого занятия
                end_i = optimizer.model.NewIntVar(0, len(optimizer.time_slots), f"end_time_{idx_i}_tanz")
                pause_after_i_slots = c_i.pause_after // optimizer.time_interval
                optimizer.model.Add(end_i == optimizer.start_vars[idx_i] + duration_i_slots + pause_after_i_slots)
                
                # Второе занятие должно начинаться после окончания первого
                pause_before_j_slots = c_j.pause_before // optimizer.time_interval
                optimizer.model.Add(optimizer.start_vars[idx_j] >= end_i + pause_before_j_slots)
                
                # Отмечаем пару как обработанную
                pair_key = (min(idx_i, idx_j), max(idx_i, idx_j))
                processed_pairs.add(pair_key)
        
        # Применяем ограничения для последовательного размещения
        for pair in tanz_analysis['sequential_pairs']:
            if pair['can_schedule']:
                idx_i = pair['class1_idx']
                idx_j = pair['class2_idx']
                
                # Пропускаем уже обработанные пары
                pair_key = (min(idx_i, idx_j), max(idx_i, idx_j))
                if pair_key in processed_pairs:
                    continue
                
                c_i = optimizer.classes[idx_i]
                c_j = optimizer.classes[idx_j]
                info = pair['info']
                
                print(f"Setting sequential constraints for classes {idx_i} and {idx_j}:")
                print(f"  Class {idx_i}: {c_i.subject} - Groups: {c_i.get_groups()}")
                print(f"  Class {idx_j}: {c_j.subject} - Groups: {c_j.get_groups()}")
                
                # Обрабатываем разные случаи
                if c_i.start_time and c_i.end_time and c_j.start_time and c_j.end_time:
                    # Оба занятия с временными окнами - используем check_two_window_classes
                    from sequential_scheduling_checker import check_two_window_classes
                    check_two_window_classes(optimizer, idx_i, idx_j, c_i, c_j)
                    processed_pairs.add(pair_key)
                elif info['reason'] == 'fits_after_fixed':
                    # Одно занятие фиксированное, другое - с окном
                    if c_i.start_time and not c_i.end_time:
                        # c_i фиксировано, c_j с окном
                        fixed_start = time_to_minutes(c_i.start_time)
                        fixed_end = fixed_start + c_i.duration + c_i.pause_after
                        fixed_end_time = minutes_to_time(fixed_end)
                        
                        # Находим ближайший временной слот после окончания фиксированного занятия
                        earliest_slot_for_j = None
                        for slot_idx, slot_time in enumerate(optimizer.time_slots):
                            if time_to_minutes(slot_time) >= fixed_end:
                                earliest_slot_for_j = slot_idx
                                break
                        
                        if earliest_slot_for_j is not None and not isinstance(optimizer.start_vars[idx_j], int):
                            print(f"  Setting constraint: class {idx_j} must start at or after slot {earliest_slot_for_j} ({optimizer.time_slots[earliest_slot_for_j]})")
                            optimizer.model.Add(optimizer.start_vars[idx_j] >= earliest_slot_for_j)
                            
                            # Добавляем ограничение на конец временного окна
                            window_end_time = c_j.end_time
                            window_end_slot = None
                            for slot_idx, slot_time in enumerate(optimizer.time_slots):
                                if time_to_minutes(slot_time) >= time_to_minutes(window_end_time):
                                    window_end_slot = slot_idx
                                    break
                            
                            if window_end_slot is not None:
                                # Рассчитываем максимальное время начала, чтобы уложиться в окно
                                duration_slots = c_j.duration // optimizer.time_interval
                                max_start_slot = window_end_slot - duration_slots
                                print(f"  Setting constraint: class {idx_j} must start at or before slot {max_start_slot} to end before {window_end_time}")
                                optimizer.model.Add(optimizer.start_vars[idx_j] <= max_start_slot)
                            
                            processed_pairs.add(pair_key)
                    else:
                        # c_j фиксировано, c_i с окном
                        fixed_start = time_to_minutes(c_j.start_time)
                        fixed_end = fixed_start + c_j.duration + c_j.pause_after
                        fixed_end_time = minutes_to_time(fixed_end)
                        
                        # Находим ближайший временной слот после окончания фиксированного занятия
                        earliest_slot_for_i = None
                        for slot_idx, slot_time in enumerate(optimizer.time_slots):
                            if time_to_minutes(slot_time) >= fixed_end:
                                earliest_slot_for_i = slot_idx
                                break
                        
                        if earliest_slot_for_i is not None and not isinstance(optimizer.start_vars[idx_i], int):
                            print(f"  Setting constraint: class {idx_i} must start at or after slot {earliest_slot_for_i} ({optimizer.time_slots[earliest_slot_for_i]})")
                            optimizer.model.Add(optimizer.start_vars[idx_i] >= earliest_slot_for_i)
                            
                            # Добавляем ограничение на конец временного окна
                            window_end_time = c_i.end_time
                            window_end_slot = None
                            for slot_idx, slot_time in enumerate(optimizer.time_slots):
                                if time_to_minutes(slot_time) >= time_to_minutes(window_end_time):
                                    window_end_slot = slot_idx
                                    break
                            
                            if window_end_slot is not None:
                                # Рассчитываем максимальное время начала, чтобы уложиться в окно
                                duration_slots = c_i.duration // optimizer.time_interval
                                max_start_slot = window_end_slot - duration_slots
                                print(f"  Setting constraint: class {idx_i} must start at or before slot {max_start_slot} to end before {window_end_time}")
                                optimizer.model.Add(optimizer.start_vars[idx_i] <= max_start_slot)
                            
                            processed_pairs.add(pair_key)
                
                elif info['reason'] == 'fits_in_common_window':
                    # Оба занятия с временными окнами
                    if not (isinstance(optimizer.start_vars[idx_i], int) and isinstance(optimizer.start_vars[idx_j], int)):
                        # Используем улучшенную функцию check_two_window_classes
                        from sequential_scheduling_checker import check_two_window_classes
                        check_two_window_classes(optimizer, idx_i, idx_j, c_i, c_j)
                        processed_pairs.add(pair_key)
                
                elif info['reason'] == 'fixed_times_no_overlap':
                    # Оба занятия с фиксированным временем, но без пересечения
                    print(f"  No additional constraints needed: fixed times don't overlap")
                    processed_pairs.add(pair_key)
                    
    # Общий анализ занятий с временными окнами
    window_classes = []
    for idx, c in enumerate(optimizer.classes):
        if c.start_time and c.end_time:
            window_classes.append((idx, c))
    
    print(f"\nFound {len(window_classes)} classes with time windows.")
    
    # Для каждого занятия с временным окном анализируем возможные конфликты и оптимизации
    for idx_i, c_i in window_classes:
        # Проверяем имеется ли уже фиксированное ограничение для этого занятия
        # и если нет, добавляем ограничения на временное окно
        if not isinstance(optimizer.start_vars[idx_i], int):
            window_start_time = c_i.start_time
            window_end_time = c_i.end_time
            
            # Находим соответствующие временные слоты
            window_start_slot = None
            window_end_slot = None
            
            for slot_idx, slot_time in enumerate(optimizer.time_slots):
                if window_start_slot is None and time_to_minutes(slot_time) >= time_to_minutes(window_start_time):
                    window_start_slot = slot_idx
                if window_end_slot is None and time_to_minutes(slot_time) >= time_to_minutes(window_end_time):
                    window_end_slot = slot_idx
                    break
            
            if window_start_slot is not None and window_end_slot is not None:
                # Рассчитываем максимальное время начала, чтобы уложиться в окно
                duration_slots = c_i.duration // optimizer.time_interval
                max_start_slot = window_end_slot - duration_slots
                
                # Добавляем ограничения на временное окно
                optimizer.model.Add(optimizer.start_vars[idx_i] >= window_start_slot)
                optimizer.model.Add(optimizer.start_vars[idx_i] <= max_start_slot)
                
                print(f"  Added window constraints for class {idx_i}: start between slots {window_start_slot} and {max_start_slot}")
        
        # Ищем занятия, которые могут влиять на планирование текущего
        for idx_j, c_j in enumerate(optimizer.classes):
            if idx_i == idx_j:
                continue
                
            # Пропускаем уже обработанные пары
            pair_key = (min(idx_i, idx_j), max(idx_i, idx_j))
            if pair_key in processed_pairs:
                continue
                
            # Проверяем, есть ли общие ресурсы
            resource_conflict = False
            
            # Общий преподаватель?
            if c_i.teacher == c_j.teacher and c_i.teacher:
                # Но разные группы?
                shared_groups = set(c_i.get_groups()) & set(c_j.get_groups())
                if not shared_groups:
                    # Возможно последовательное планирование с одним преподавателем
                    can_schedule, info = can_schedule_sequentially(c_i, c_j)
                    if can_schedule:
                        print(f"Sequential scheduling possible for classes {idx_i} and {idx_j} with same teacher {c_i.teacher}")
                        
                        # Если оба с временными окнами, используем check_two_window_classes
                        if c_i.start_time and c_i.end_time and c_j.start_time and c_j.end_time:
                            from sequential_scheduling_checker import check_two_window_classes
                            check_two_window_classes(optimizer, idx_i, idx_j, c_i, c_j)
                            processed_pairs.add(pair_key)
                        # Применяем ту же логику, что и для Tanz для других типов
                        elif info['reason'] == 'fits_after_fixed' and c_j.start_time and not c_j.end_time:
                            # c_j фиксировано, c_i с окном
                            fixed_start = time_to_minutes(c_j.start_time)
                            fixed_end = fixed_start + c_j.duration + c_j.pause_after
                            fixed_end_time = minutes_to_time(fixed_end)
                            
                            earliest_slot_for_i = None
                            for slot_idx, slot_time in enumerate(optimizer.time_slots):
                                if time_to_minutes(slot_time) >= fixed_end:
                                    earliest_slot_for_i = slot_idx
                                    break
                            
                            if earliest_slot_for_i is not None and not isinstance(optimizer.start_vars[idx_i], int):
                                print(f"  Setting constraint: class {idx_i} must start at or after slot {earliest_slot_for_i} ({optimizer.time_slots[earliest_slot_for_i]})")
                                optimizer.model.Add(optimizer.start_vars[idx_i] >= earliest_slot_for_i)
                                processed_pairs.add(pair_key)
                
            # Общие аудитории?
            shared_rooms = set(c_i.possible_rooms) & set(c_j.possible_rooms)
            if shared_rooms and pair_key not in processed_pairs:
                # Проверяем возможность последовательного планирования
                can_schedule, info = can_schedule_sequentially(c_i, c_j)
                if can_schedule:
                    print(f"Sequential scheduling possible for classes {idx_i} and {idx_j} in shared rooms {shared_rooms}")
                    
                    # Если оба с временными окнами, используем check_two_window_classes
                    if c_i.start_time and c_i.end_time and c_j.start_time and c_j.end_time:
                        from sequential_scheduling_checker import check_two_window_classes
                        check_two_window_classes(optimizer, idx_i, idx_j, c_i, c_j)
                        processed_pairs.add(pair_key)
                    # Применяем ту же логику что и выше
                    elif info['reason'] == 'fits_after_fixed' and c_j.start_time and not c_j.end_time:
                        # c_j фиксировано, c_i с окном
                        fixed_start = time_to_minutes(c_j.start_time)
                        fixed_end = fixed_start + c_j.duration + c_j.pause_after
                        fixed_end_time = minutes_to_time(fixed_end)
                        
                        earliest_slot_for_i = None
                        for slot_idx, slot_time in enumerate(optimizer.time_slots):
                            if time_to_minutes(slot_time) >= fixed_end:
                                earliest_slot_for_i = slot_idx
                                break
                        
                        if earliest_slot_for_i is not None and not isinstance(optimizer.start_vars[idx_i], int):
                            print(f"  Setting constraint: class {idx_i} must start at or after slot {earliest_slot_for_i} ({optimizer.time_slots[earliest_slot_for_i]})")
                            optimizer.model.Add(optimizer.start_vars[idx_i] >= earliest_slot_for_i)
                            processed_pairs.add(pair_key)
                    
                    elif info['reason'] == 'fits_in_common_window' and c_j.start_time and c_j.end_time and pair_key not in processed_pairs:
                        # Оба занятия с временными окнами
                        from sequential_scheduling_checker import check_two_window_classes
                        check_two_window_classes(optimizer, idx_i, idx_j, c_i, c_j)
                        processed_pairs.add(pair_key)
    
    return True

def find_slot_for_time(time_slots, time_str):
    """
    Находит индекс слота времени для заданной строки времени.
    
    Args:
        time_slots: Список строк времени (HH:MM)
        time_str: Строка времени для поиска
        
    Returns:
        int: Индекс слота или None, если не найден
    """
    from time_utils import time_to_minutes
    
    target_minutes = time_to_minutes(time_str)
    
    # Ищем точное совпадение
    for slot_idx, slot_time in enumerate(time_slots):
        slot_minutes = time_to_minutes(slot_time)
        if slot_minutes == target_minutes:
            return slot_idx
    
    # Если точного совпадения нет, ищем ближайший слот
    best_slot = None
    min_diff = float('inf')
    
    for slot_idx, slot_time in enumerate(time_slots):
        slot_minutes = time_to_minutes(slot_time)
        diff = abs(slot_minutes - target_minutes)
        
        if diff < min_diff:
            min_diff = diff
            best_slot = slot_idx
    
    return best_slot


def add_objective_weights_for_timewindows(optimizer):
    """
    Добавляет веса к целевой функции для улучшения планирования с временными окнами.
    
    Args:
        optimizer: Экземпляр ScheduleOptimizer
        
    Returns:
        list: Дополнительные термы для целевой функции
    """
    additional_terms = []
    
    # 1. Для всех занятий добавляем сильный стимул начинать как можно раньше
    # Это обеспечит более компактное расписание в целом, занятия будут стремиться начаться сразу после начала окна
    for idx, c in enumerate(optimizer.classes):
        if not isinstance(optimizer.start_vars[idx], int):
            # Добавляем штраф пропорциональный времени начала, больший вес чем раньше
            additional_terms.append(optimizer.start_vars[idx] * 5)  # Увеличиваем вес с 1 до 5
    
    # 2. Для занятий с временными окнами добавляем еще более сильный стимул начинать раньше
    # Особенно для окон с большой гибкостью
    for idx, c in enumerate(optimizer.classes):
        if c.start_time and c.end_time and not isinstance(optimizer.start_vars[idx], int):
            window_start = time_to_minutes(c.start_time)
            window_end = time_to_minutes(c.end_time)
            window_size = window_end - window_start
            
            # Находим соответствующий временной слот для начала окна
            window_start_slot = None
            for slot_idx, slot_time in enumerate(optimizer.time_slots):
                slot_minutes = time_to_minutes(slot_time)
                if slot_minutes >= window_start:
                    window_start_slot = slot_idx
                    break
            
            if window_start_slot is not None:
                # Штраф пропорционален расстоянию от начала окна
                delay_var = optimizer.model.NewIntVar(0, len(optimizer.time_slots), f"window_delay_{idx}")
                optimizer.model.Add(delay_var == optimizer.start_vars[idx] - window_start_slot)
                
                # Вес зависит от размера окна
                # Чем шире окно, тем выше вес для стимулирования более раннего начала
                # Увеличиваем веса в 2 раза по сравнению с исходной версией
                flexibility_factor = min(16, 6 + (window_size // 60))  # максимум 16 вместо 8
                additional_terms.append(delay_var * flexibility_factor)
    
    # 3. Для занятий с несколькими временными окнами в один день с одним преподавателем
    # добавляем особый стимул для размещения в правильном порядке
    window_classes_by_teacher = {}
    
    for idx, c in enumerate(optimizer.classes):
        if c.start_time and c.end_time and c.teacher:
            key = f"{c.teacher}_{c.day}"
            if key not in window_classes_by_teacher:
                window_classes_by_teacher[key] = []
            window_classes_by_teacher[key].append((idx, c))
    
    # Для каждого преподавателя в каждый день проверяем занятия с временными окнами
    for key, classes in window_classes_by_teacher.items():
        if len(classes) >= 2:
            # Сортируем занятия по началу временного окна
            sorted_classes = sorted(classes, key=lambda x: time_to_minutes(x[1].start_time))
            
            # Для каждой пары последовательных занятий добавляем стимул правильного порядка
            for i in range(len(sorted_classes) - 1):
                idx_earlier, c_earlier = sorted_classes[i]
                idx_later, c_later = sorted_classes[i + 1]
                
                # Только если оба времени не фиксированы
                if not isinstance(optimizer.start_vars[idx_earlier], int) and not isinstance(optimizer.start_vars[idx_later], int):
                    # Создаем булеву переменную для обнаружения правильного порядка
                    correct_order = optimizer.model.NewBoolVar(f"correct_order_{idx_earlier}_{idx_later}")
                    
                    # Определяем конец первого занятия
                    end_earlier = optimizer.model.NewIntVar(0, len(optimizer.time_slots), f"end_{idx_earlier}")
                    duration_earlier = (c_earlier.duration + c_earlier.pause_after) // optimizer.time_interval
                    optimizer.model.Add(end_earlier == optimizer.start_vars[idx_earlier] + duration_earlier)
                    
                    # Проверяем корректный порядок: первое должно заканчиваться до начала второго
                    pause_slots = c_later.pause_before // optimizer.time_interval
                    optimizer.model.Add(optimizer.start_vars[idx_later] >= end_earlier + pause_slots).OnlyEnforceIf(correct_order)
                    optimizer.model.Add(optimizer.start_vars[idx_later] < end_earlier + pause_slots).OnlyEnforceIf(correct_order.Not())
                    
                    # Большой штраф за неправильный порядок
                    additional_terms.append(correct_order.Not() * 100)  # Очень высокий вес
                    
                    # Дополнительное стимулирование самого раннего расписания для первого занятия
                    additional_terms.append(optimizer.start_vars[idx_earlier] * 8)
    
    # 4. Для преподавателей с несколькими занятиями в один день
    teacher_classes = {}
    for idx, c in enumerate(optimizer.classes):
        if c.teacher:
            if c.teacher not in teacher_classes:
                teacher_classes[c.teacher] = []
            teacher_classes[c.teacher].append((idx, c))
    
    for teacher, classes in teacher_classes.items():
        if len(classes) > 1:
            # Группируем занятия по дням
            day_classes = {}
            for idx, c in classes:
                if c.day not in day_classes:
                    day_classes[c.day] = []
                day_classes[c.day].append((idx, c))
            
            # Для каждого дня с несколькими занятиями одного преподавателя
            for day, day_classes_list in day_classes.items():
                if len(day_classes_list) > 1:
                    # Проверяем общие аудитории
                    shared_rooms = False
                    for i, (idx_i, c_i) in enumerate(day_classes_list):
                        for j, (idx_j, c_j) in enumerate(day_classes_list[i+1:], i+1):
                            if set(c_i.possible_rooms) & set(c_j.possible_rooms):
                                shared_rooms = True
                                break
                        if shared_rooms:
                            break
                    
                    # Если есть общие аудитории, добавляем стимул для компактного расписания
                    if shared_rooms:
                        for idx, c in day_classes_list:
                            if not isinstance(optimizer.start_vars[idx], int):
                                # Стимулируем занятия с временными окнами
                                weight = 8 if (c.start_time and c.end_time) else 5  # Увеличиваем веса
                                additional_terms.append(optimizer.start_vars[idx] * weight)
    
    # 5. Общее улучшение компактности расписания
    # Для каждого дня и каждой аудитории
    room_classes = {}
    for idx, c in enumerate(optimizer.classes):
        for room in c.possible_rooms:
            if room not in room_classes:
                room_classes[room] = {}
            if c.day not in room_classes[room]:
                room_classes[room][c.day] = []
            room_classes[room][c.day].append((idx, c))
    
    # Если в одной аудитории несколько занятий в один день
    for room, day_dict in room_classes.items():
        for day, classes in day_dict.items():
            if len(classes) > 1:
                # Стимулируем раннее начало в загруженных аудиториях
                for idx, c in classes:
                    if not isinstance(optimizer.start_vars[idx], int):
                        additional_terms.append(optimizer.start_vars[idx] * 3)  # Увеличиваем вес
    
    return additional_terms