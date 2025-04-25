"""
Модуль для проверки возможности последовательного размещения занятий.
"""
from time_utils import time_to_minutes, minutes_to_time

def _check_sequential_scheduling(optimizer, idx_fixed, idx_window, c_fixed, c_window):
    """
    Проверяет возможность последовательного размещения занятий, когда одно имеет
    фиксированное время, а другое - временное окно.
    
    Args:
        optimizer: Экземпляр ScheduleOptimizer
        idx_fixed: Индекс занятия с фиксированным временем
        idx_window: Индекс занятия с временным окном
        c_fixed: Занятие с фиксированным временем (ScheduleClass)
        c_window: Занятие с временным окном (ScheduleClass)
        
    Returns:
        tuple: (bool, str) - возможно ли последовательное размещение и режим размещения
               ("after", "before", "both" или "none")
    """
    fixed_start = time_to_minutes(c_fixed.start_time)
    fixed_end = fixed_start + c_fixed.duration + c_fixed.pause_after
    window_start = time_to_minutes(c_window.start_time)
    window_end = time_to_minutes(c_window.end_time)
    
    print(f"\nANALYZING SEQUENTIAL POSSIBILITY: Same teacher {c_fixed.teacher}, different groups")
    print(f"  Fixed class: {c_fixed.subject} at {c_fixed.start_time} (ends at {minutes_to_time(fixed_end)})")
    print(f"  Window class: {c_window.subject} with window {c_window.start_time}-{c_window.end_time}")
    
    # Проверяем, достаточно ли времени для последовательного размещения
    # Вариант 1: Окно после фиксированного времени
    after_fixed_possible = window_end - fixed_end >= c_window.duration + c_window.pause_before
    
    # Вариант 2: Окно перед фиксированным временем
    window_class_end = window_start + c_window.duration + c_window.pause_after
    before_fixed_possible = fixed_start - window_class_end >= c_fixed.pause_before
    
    # Информация для слотов
    earliest_after_slot = None
    latest_before_slot = None
    
    if after_fixed_possible:
        print(f"  Option 1: Window class can be scheduled AFTER fixed class")
        
        # Находим слот для начала занятия с окном после фиксированного
        fixed_end_time = minutes_to_time(fixed_end)
        for slot_idx, slot_time in enumerate(optimizer.time_slots):
            if slot_time >= fixed_end_time:
                earliest_after_slot = slot_idx
                break
        
        if earliest_after_slot is not None:
            print(f"  Window class can start at or after slot {earliest_after_slot} ({optimizer.time_slots[earliest_after_slot]})")
    
    if before_fixed_possible:
        print(f"  Option 2: Window class can be scheduled BEFORE fixed class")
        
        # Находим последний допустимый слот для окончания занятия с окном
        latest_end_time = minutes_to_time(fixed_start - c_fixed.pause_before)
        latest_end_slot = None
        for slot_idx, slot_time in enumerate(optimizer.time_slots):
            if slot_time > latest_end_time:
                latest_end_slot = slot_idx - 1
                break
        
        # Находим последний допустимый слот для начала занятия с окном
        if latest_end_slot is not None:
            window_duration_slots = (c_window.duration + c_window.pause_after) // optimizer.time_interval
            latest_before_slot = latest_end_slot - window_duration_slots
            
            if latest_before_slot >= 0:
                print(f"  Window class must start at or before slot {latest_before_slot} ({optimizer.time_slots[latest_before_slot]})")
            else:
                print(f"  Window class cannot be scheduled before fixed class (insufficient slots)")
                before_fixed_possible = False
    
    # Определяем режим размещения
    if after_fixed_possible and before_fixed_possible:
        mode = "both"
    elif after_fixed_possible:
        mode = "after"
    elif before_fixed_possible:
        mode = "before"
    else:
        mode = "none"
    
    # Добавляем ограничения в зависимости от режима
    if mode != "none" and not isinstance(optimizer.start_vars[idx_window], int):
        if mode == "both":
            # Создаем булеву переменную для выбора между вариантами
            is_after = optimizer.model.NewBoolVar(f"is_after_{idx_fixed}_{idx_window}")
            
            # Если занятие с окном после фиксированного, то window.start >= earliest_after_slot
            optimizer.model.Add(optimizer.start_vars[idx_window] >= earliest_after_slot).OnlyEnforceIf(is_after)
            
            # Если занятие с окном перед фиксированным, то window.start <= latest_before_slot
            optimizer.model.Add(optimizer.start_vars[idx_window] <= latest_before_slot).OnlyEnforceIf(is_after.Not())
            
            print(f"  Added constraint: Window class either starts after slot {earliest_after_slot} OR before slot {latest_before_slot}")
            
        elif mode == "after":
            optimizer.model.Add(optimizer.start_vars[idx_window] >= earliest_after_slot)
            print(f"  Added constraint: Window class must start at or after slot {earliest_after_slot}")
            
        elif mode == "before":
            optimizer.model.Add(optimizer.start_vars[idx_window] <= latest_before_slot)
            print(f"  Added constraint: Window class must start at or before slot {latest_before_slot}")
    
    return mode != "none", mode

# Глобальный словарь для отслеживания уже обработанных проверок
# Это позволит избежать дублирующих сообщений и ограничений
_processed_window_checks = set()

def check_two_window_classes(optimizer, i, j, c_i, c_j):
    """
    Проверяет возможность последовательного размещения двух занятий с временными окнами.
    
    Args:
        optimizer: Экземпляр ScheduleOptimizer
        i, j: Индексы классов
        c_i, c_j: Экземпляры ScheduleClass с временными окнами
        
    Returns:
        bool: True, если найдено решение для последовательного размещения, иначе False
    """
    global _processed_window_checks
    
    # Создаем уникальный ключ для этой пары классов
    pair_key = (min(i, j), max(i, j))
    
    # Проверяем, обрабатывали ли мы уже эту пару
    if pair_key in _processed_window_checks:
        # Уже обработано, пропускаем повторную обработку
        return True
    
    # Добавляем пару в список обработанных
    _processed_window_checks.add(pair_key)
    
    # Основной код проверки
    window_i_start = time_to_minutes(c_i.start_time)
    window_i_end = time_to_minutes(c_i.end_time)
    window_j_start = time_to_minutes(c_j.start_time)
    window_j_end = time_to_minutes(c_j.end_time)
    
    print(f"\nANALYZING WINDOWS: Same teacher {c_i.teacher}, different groups")
    print(f"  Class {i}: {c_i.subject} with window {c_i.start_time}-{c_i.end_time}")
    print(f"  Class {j}: {c_j.subject} with window {c_j.start_time}-{c_j.end_time}")
    
    # Вычисляем параметры занятий в минутах
    duration_i_min = c_i.duration
    duration_j_min = c_j.duration
    
    pause_before_i_min = c_i.pause_before
    pause_after_i_min = c_i.pause_after
    pause_before_j_min = c_j.pause_before
    pause_after_j_min = c_j.pause_after
    
    # Вычисляем те же параметры в слотах времени
    duration_i_slots = (duration_i_min + optimizer.time_interval - 1) // optimizer.time_interval
    duration_j_slots = (duration_j_min + optimizer.time_interval - 1) // optimizer.time_interval
    
    pause_before_i_slots = pause_before_i_min // optimizer.time_interval
    pause_after_i_slots = pause_after_i_min // optimizer.time_interval
    pause_before_j_slots = pause_before_j_min // optimizer.time_interval
    pause_after_j_slots = pause_after_j_min // optimizer.time_interval
    
    # Проверяем два варианта последовательного размещения
    
    # Вариант 1: класс i, затем класс j
    i_then_j_possible = False
    earliest_i_start_min = window_i_start
    earliest_i_end_min = earliest_i_start_min + duration_i_min + pause_after_i_min
    latest_j_end_min = window_j_end
    latest_j_start_min = latest_j_end_min - duration_j_min
    
    if earliest_i_end_min + pause_before_j_min <= latest_j_start_min and latest_j_end_min <= window_j_end:
        i_then_j_possible = True
        earliest_j_start_min = earliest_i_end_min + pause_before_j_min
        print(f"  Sequential possible: Class {i} then Class {j}")
        print(f"    Class {i} starts no earlier than: {minutes_to_time(earliest_i_start_min)}")
        print(f"    Class {i} finishes no earlier than: {minutes_to_time(earliest_i_end_min)}")
        print(f"    Class {j} can start: {minutes_to_time(earliest_j_start_min)} to {minutes_to_time(latest_j_start_min)}")
        print(f"    Class {j} must end before: {minutes_to_time(latest_j_end_min)}")
    
    # Вариант 2: класс j, затем класс i
    j_then_i_possible = False
    earliest_j_start_min = window_j_start
    earliest_j_end_min = earliest_j_start_min + duration_j_min + pause_after_j_min
    latest_i_end_min = window_i_end
    latest_i_start_min = latest_i_end_min - duration_i_min
    
    if earliest_j_end_min + pause_before_i_min <= latest_i_start_min and latest_i_end_min <= window_i_end:
        j_then_i_possible = True
        earliest_i_start_min = earliest_j_end_min + pause_before_i_min
        print(f"  Sequential possible: Class {j} then Class {i}")
        print(f"    Class {j} starts no earlier than: {minutes_to_time(earliest_j_start_min)}")
        print(f"    Class {j} finishes no earlier than: {minutes_to_time(earliest_j_end_min)}")
        print(f"    Class {i} can start: {minutes_to_time(earliest_i_start_min)} to {minutes_to_time(latest_i_start_min)}")
        print(f"    Class {i} must end before: {minutes_to_time(latest_i_end_min)}")
    
    # Проверяем, какой из вариантов предпочтительнее
    # Критерий: если окно начинается раньше, то занятие должно быть размещено первым
    prefer_j_first = window_j_start < window_i_start
    
    # Оба варианта возможны
    if i_then_j_possible and j_then_i_possible:
        print(f"  Both sequential orders are possible!")
        
        if not (isinstance(optimizer.start_vars[i], int) and isinstance(optimizer.start_vars[j], int)):
            # Создаем жесткие ограничения для каждого занятия в соответствии с их временными окнами
            
            # Находим слоты для временных окон
            i_start_slot = find_slot_for_time(optimizer.time_slots, c_i.start_time)
            i_end_slot = find_slot_for_time(optimizer.time_slots, c_i.end_time)
            j_start_slot = find_slot_for_time(optimizer.time_slots, c_j.start_time)
            j_end_slot = find_slot_for_time(optimizer.time_slots, c_j.end_time)
            
            # Класс i должен начаться не ранее начала своего окна и завершиться не позднее конца окна
            optimizer.model.Add(optimizer.start_vars[i] >= i_start_slot)
            optimizer.model.Add(optimizer.start_vars[i] + duration_i_slots <= i_end_slot)
            
            # Класс j должен начаться не ранее начала своего окна и завершиться не позднее конца окна
            optimizer.model.Add(optimizer.start_vars[j] >= j_start_slot)
            optimizer.model.Add(optimizer.start_vars[j] + duration_j_slots <= j_end_slot)
            
            # Создаем переменную для выбора последовательности
            i_before_j = optimizer.model.NewBoolVar(f"i_before_j_{i}_{j}")
            
            # Создаем переменные для обозначения конца занятий
            end_i = optimizer.model.NewIntVar(0, len(optimizer.time_slots), f"end_time_{i}_{j}")
            end_j = optimizer.model.NewIntVar(0, len(optimizer.time_slots), f"end_time_{j}_{i}")
            
            # Вычисляем конец i-го занятия
            optimizer.model.Add(end_i == optimizer.start_vars[i] + duration_i_slots + pause_after_i_slots)
            
            # Вычисляем конец j-го занятия
            optimizer.model.Add(end_j == optimizer.start_vars[j] + duration_j_slots + pause_after_j_slots)
            
            # Если i перед j, то j.start >= i.end
            optimizer.model.Add(optimizer.start_vars[j] >= end_i).OnlyEnforceIf(i_before_j)
            
            # Если j перед i, то i.start >= j.end
            optimizer.model.Add(optimizer.start_vars[i] >= end_j).OnlyEnforceIf(i_before_j.Not())
            
            # Предпочтение на основе времени начала окна
            if prefer_j_first:
                # Мягкое ограничение: добавляем стимул для j перед i
                preference_var = optimizer.model.NewBoolVar(f"preference_{j}_before_{i}")
                optimizer.model.Add(preference_var == i_before_j.Not())
                print(f"  Preference: Class {j} should be scheduled before Class {i} (earlier window)")
            else:
                # Мягкое ограничение: добавляем стимул для i перед j
                preference_var = optimizer.model.NewBoolVar(f"preference_{i}_before_{j}")
                optimizer.model.Add(preference_var == i_before_j)
                print(f"  Preference: Class {i} should be scheduled before Class {j} (earlier window)")
            
            print(f"  Added constraint: classes must be scheduled sequentially")
            print(f"  Added constraint: Class {i} must start after {c_i.start_time} and end before {c_i.end_time}")
            print(f"  Added constraint: Class {j} must start after {c_j.start_time} and end before {c_j.end_time}")
        
        # Последовательное размещение возможно
        return True
        
    # Только один вариант возможен: i затем j
    elif i_then_j_possible:
        print(f"  Only one order is possible: Class {i} then Class {j}")
        
        if not (isinstance(optimizer.start_vars[i], int) and isinstance(optimizer.start_vars[j], int)):
            # Находим слоты для временных окон и ограничений
            i_start_slot = find_slot_for_time(optimizer.time_slots, c_i.start_time)
            i_end_slot = find_slot_for_time(optimizer.time_slots, c_i.end_time)
            j_start_slot = find_slot_for_time(optimizer.time_slots, c_j.start_time)
            j_end_slot = find_slot_for_time(optimizer.time_slots, c_j.end_time)
            
            # Класс i должен начаться не ранее начала своего окна и завершиться не позднее конца окна
            optimizer.model.Add(optimizer.start_vars[i] >= i_start_slot)
            optimizer.model.Add(optimizer.start_vars[i] + duration_i_slots <= i_end_slot)
            
            # Класс j должен начаться не ранее начала своего окна и завершиться не позднее конца окна
            optimizer.model.Add(optimizer.start_vars[j] >= j_start_slot)
            optimizer.model.Add(optimizer.start_vars[j] + duration_j_slots <= j_end_slot)
            
            # Создаем переменные для конца i-го занятия
            end_i = optimizer.model.NewIntVar(0, len(optimizer.time_slots), f"end_time_{i}")
            optimizer.model.Add(end_i == optimizer.start_vars[i] + duration_i_slots + pause_after_i_slots)
            
            # j должно начинаться после окончания i
            optimizer.model.Add(optimizer.start_vars[j] >= end_i)
            
            print(f"  Added constraint: Class {j} must start after Class {i} ends")
            print(f"  Added constraint: Class {i} must start after {c_i.start_time} and end before {c_i.end_time}")
            print(f"  Added constraint: Class {j} must start after {c_j.start_time} and end before {c_j.end_time}")
            
            # Добавляем стимул для раннего начала i
            # Это будет учтено в целевой функции
        
        # Последовательное размещение возможно
        return True
        
    # Только один вариант возможен: j затем i
    elif j_then_i_possible:
        print(f"  Only one order is possible: Class {j} then Class {i}")
        
        if not (isinstance(optimizer.start_vars[i], int) and isinstance(optimizer.start_vars[j], int)):
            # Находим слоты для временных окон и ограничений
            i_start_slot = find_slot_for_time(optimizer.time_slots, c_i.start_time)
            i_end_slot = find_slot_for_time(optimizer.time_slots, c_i.end_time)
            j_start_slot = find_slot_for_time(optimizer.time_slots, c_j.start_time)
            j_end_slot = find_slot_for_time(optimizer.time_slots, c_j.end_time)
            
            # Класс i должен начаться не ранее начала своего окна и завершиться не позднее конца окна
            optimizer.model.Add(optimizer.start_vars[i] >= i_start_slot)
            optimizer.model.Add(optimizer.start_vars[i] + duration_i_slots <= i_end_slot)
            
            # Класс j должен начаться не ранее начала своего окна и завершиться не позднее конца окна
            optimizer.model.Add(optimizer.start_vars[j] >= j_start_slot)
            optimizer.model.Add(optimizer.start_vars[j] + duration_j_slots <= j_end_slot)
            
            # Создаем переменные для конца j-го занятия
            end_j = optimizer.model.NewIntVar(0, len(optimizer.time_slots), f"end_time_{j}")
            optimizer.model.Add(end_j == optimizer.start_vars[j] + duration_j_slots + pause_after_j_slots)
            
            # i должно начинаться после окончания j
            optimizer.model.Add(optimizer.start_vars[i] >= end_j)
            
            print(f"  Added constraint: Class {i} must start after Class {j} ends")
            print(f"  Added constraint: Class {i} must start after {c_i.start_time} and end before {c_i.end_time}")
            print(f"  Added constraint: Class {j} must start after {c_j.start_time} and end before {c_j.end_time}")
            
            # Добавляем стимул для раннего начала j
            # Это будет учтено в целевой функции
        
        # Последовательное размещение возможно
        return True
    
    # Если ни один вариант не возможен
    print(f"  Sequential scheduling not possible for these time windows")
    return False

def reset_window_checks_cache():
    """
    Сбрасывает кэш обработанных проверок. Эту функцию следует вызывать
    перед каждым новым запуском оптимизатора, чтобы избежать сохранения
    состояния между запусками.
    """
    global _processed_window_checks
    _processed_window_checks = set()
    print("Window checks cache has been reset.")

def find_slot_for_time(time_slots, time_str):
    """
    Находит индекс слота времени для заданной строки времени.
    
    Args:
        time_slots: Список строк времени (HH:MM)
        time_str: Строка времени для поиска
        
    Returns:
        int: Индекс слота или None, если не найден
    """
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