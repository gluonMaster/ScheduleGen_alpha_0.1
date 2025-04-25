"""
Модуль для добавления ограничений по времени и предотвращения конфликтов.
"""
from time_utils import time_to_minutes, minutes_to_time
from time_constraint_utils import create_conflict_variables, add_time_overlap_constraints
from sequential_scheduling_checker import _check_sequential_scheduling, check_two_window_classes

def _add_time_conflict_constraints(optimizer, i, j, c_i, c_j):
    """
    Добавляет ограничения для предотвращения конфликтов времени между занятиями.
    
    Args:
        optimizer: Экземпляр ScheduleOptimizer
        i, j: Индексы классов
        c_i, c_j: Экземпляры ScheduleClass
    """
    # Проверяем возможность последовательного размещения для занятий одного преподавателя
    if c_i.teacher == c_j.teacher and c_i.teacher:
        # Проверяем, что группы разные (нет общих групп)
        shared_groups = set(c_i.get_groups()) & set(c_j.get_groups())
        if not shared_groups:
            # Проверяем временные ограничения
            if c_i.start_time and not c_i.end_time and c_j.start_time and c_j.end_time:
                # c_i фиксировано, c_j с окном
                sequential_possible, mode = _check_sequential_scheduling(optimizer, i, j, c_i, c_j)
                if sequential_possible:
                    # Не добавляем конфликтные ограничения, поскольку последовательное размещение возможно
                    return
                
            elif c_j.start_time and not c_j.end_time and c_i.start_time and c_i.end_time:
                # c_j фиксировано, c_i с окном
                sequential_possible, mode = _check_sequential_scheduling(optimizer, j, i, c_j, c_i)
                if sequential_possible:
                    # Не добавляем конфликтные ограничения, поскольку последовательное размещение возможно
                    return
            
            elif c_i.start_time and c_i.end_time and c_j.start_time and c_j.end_time:
                # Оба занятия с временными окнами
                sequential_possible = check_two_window_classes(optimizer, i, j, c_i, c_j)
                if sequential_possible:
                    # Не добавляем стандартные ограничения конфликтов
                    return
    
    # Если ни один вариант не возможен
    print(f"  Sequential scheduling not possible for these time windows")
    
    # Стандартная обработка конфликтов (для случаев, когда последовательное размещение невозможно)
    print(f"Adding standard conflict constraints between classes {i} and {j}")
    
    # Создаем переменные для конфликта
    conflict, same_day, time_overlap = create_conflict_variables(optimizer, i, j, c_i, c_j)
    
    # Добавляем ограничения для определения перекрытия времени
    add_time_overlap_constraints(optimizer, i, j, c_i, c_j, time_overlap)
    
    # Conflict if same day and time overlap
    optimizer.model.AddBoolAnd([same_day, time_overlap]).OnlyEnforceIf(conflict)
    optimizer.model.AddBoolOr([same_day.Not(), time_overlap.Not()]).OnlyEnforceIf(conflict.Not())
    
    # Prevent conflicts
    optimizer.model.Add(conflict == False)
    
    # Check for room conflicts (only for classes with variable room assignment)
    if not (len(c_i.possible_rooms) == 1 and len(c_j.possible_rooms) == 1):
        # Add constraints to ensure different rooms if conflict potential exists
        same_room = optimizer.model.NewBoolVar(f"same_room_{i}_{j}")
        if isinstance(optimizer.room_vars[i], int) and isinstance(optimizer.room_vars[j], int):
            # Проверяем равенство комнат и устанавливаем значение переменной same_room
            if optimizer.room_vars[i] == optimizer.room_vars[j]:
                optimizer.model.Add(same_room == 1)
            else:
                optimizer.model.Add(same_room == 0)
        elif isinstance(optimizer.room_vars[i], int):
            optimizer.model.Add(optimizer.room_vars[j] == optimizer.room_vars[i]).OnlyEnforceIf(same_room)
            optimizer.model.Add(optimizer.room_vars[j] != optimizer.room_vars[i]).OnlyEnforceIf(same_room.Not())
        elif isinstance(optimizer.room_vars[j], int):
            optimizer.model.Add(optimizer.room_vars[i] == optimizer.room_vars[j]).OnlyEnforceIf(same_room)
            optimizer.model.Add(optimizer.room_vars[i] != optimizer.room_vars[j]).OnlyEnforceIf(same_room.Not())
        else:
            optimizer.model.Add(optimizer.room_vars[i] == optimizer.room_vars[j]).OnlyEnforceIf(same_room)
            optimizer.model.Add(optimizer.room_vars[i] != optimizer.room_vars[j]).OnlyEnforceIf(same_room.Not())
        
        # If same room, check for conflicts
        room_conflict = optimizer.model.NewBoolVar(f"room_conflict_{i}_{j}")
        optimizer.model.AddBoolAnd([same_room, conflict]).OnlyEnforceIf(room_conflict)
        optimizer.model.Add(room_conflict == False)
        