"""
Сервис для работы с заданиями
"""
from typing import Optional, List, Tuple
from models.task import TaskModel, FlyerTaskModel, UserTaskModel, TaskSubscriptionModel
from models.user import UserModel
from services.user_service import UserService


class TaskService:
    """Сервис для работы с заданиями"""
    
    @staticmethod
    def create_user_task(creator_id: int, post_text: str, post_entities: str, 
                        channel_id: int, channel_link: str, target_subscribers: int, 
                        total_cost: float, status: str = 'pending') -> Optional[int]:
        """Создает пользовательское задание"""
        try:
            # Проверяем достаточность средств на рекламном балансе
            ad_balance = UserModel.get_ad_balance(creator_id)
            if ad_balance < total_cost:
                return None
            
            # Списываем средства
            if not UserModel.deduct_ad_balance(creator_id, total_cost):
                return None
            
            # Создаем задание
            task_id = UserTaskModel.create_task(
                creator_id, post_text, post_entities, channel_id, 
                channel_link, target_subscribers, total_cost, status
            )
            
            return task_id
        except Exception as e:
            print(f"Ошибка при создании задания: {e}")
            return None
    
    @staticmethod
    def approve_user_task(task_id: int) -> bool:
        """Одобряет пользовательское задание"""
        return UserTaskModel.approve_task(task_id)
    
    @staticmethod
    def reject_user_task(task_id: int) -> bool:
        """Отклоняет пользовательское задание и возвращает средства"""
        try:
            # Получаем информацию о задании
            task_info = UserTaskModel.get_task_by_id(task_id)
            if not task_info:
                return False
            
            # Получаем стоимость для возврата
            task_cost = UserTaskModel.get_task_cost(task_id)
            creator_id = task_info[1]  # creator_id
            
            # Отклоняем задание
            if UserTaskModel.reject_task(task_id):
                # Возвращаем средства на рекламный баланс
                if task_cost:
                    UserModel.update_ad_balance(creator_id, task_cost)
                return True
            
            return False
        except Exception as e:
            print(f"Ошибка при отклонении задания: {e}")
            return False
    
    @staticmethod
    def complete_task_for_user(user_id: int, task_id: int, task_type: str = 'regular') -> Tuple[bool, Optional[str]]:
        """Выполняет задание для пользователя"""
        try:
            if task_type == 'regular':
                return TaskModel.complete_task_for_user(user_id, task_id)
            elif task_type == 'user_task':
                # Проверяем что задание существует и активно
                task_info = UserTaskModel.get_task_by_id(task_id)
                if not task_info or task_info[8] != 'active':  # status
                    return False, "Задание неактивно"
                
                # Добавляем подписку
                TaskSubscriptionModel.add_subscription(task_id, user_id)
                TaskSubscriptionModel.mark_subscription_rewarded(task_id, user_id)
                
                # Обновляем счетчики
                UserTaskModel.update_task_subscribers(task_id)
                TaskModel.add_completed_task_log(user_id)
                
                return True, None
            else:
                return False, "Неизвестный тип задания"
        except Exception as e:
            print(f"Ошибка при выполнении задания: {e}")
            return False, str(e)
    
    @staticmethod
    def get_next_available_task(user_id: int) -> Optional[Tuple]:
        """Получает следующее доступное задание для пользователя"""
        # Сначала проверяем пользовательские задания (приоритет)
        user_tasks = UserTaskModel.get_active_tasks()
        
        for task in user_tasks:
            task_id = task[0]
            # Проверяем что пользователь не выполнял и не пропускал это задание
            if (not TaskSubscriptionModel.check_subscription(task_id, user_id) and 
                not TaskSubscriptionModel.is_user_task_skipped(task_id, user_id)):
                return task
        
        # Затем проверяем обычные задания
        regular_tasks = TaskModel.get_active_tasks()
        completed_tasks = TaskModel.get_completed_tasks_for_user(user_id)
        
        for task in regular_tasks:
            task_id = task[0]
            if task_id not in completed_tasks:
                return task
        
        return None
    
    @staticmethod
    def skip_user_task(task_id: int, user_id: int):
        """Пропускает пользовательское задание"""
        TaskSubscriptionModel.add_skipped_user_task(task_id, user_id)
    
    @staticmethod
    def skip_flyer_task(task_hash: str, user_id: int):
        """Пропускает Flyer задание"""
        FlyerTaskModel.add_skipped_task(task_hash, user_id)
    
    @staticmethod
    def get_user_tasks_stats(user_id: int) -> dict:
        """Получает статистику заданий пользователя"""
        return {
            'today': TaskModel.get_tasks_count_by_user_for_day(user_id),
            'week': TaskModel.get_tasks_count_by_user_for_week(user_id),
            'month': TaskModel.get_tasks_count_by_user_for_month(user_id),
            'total': TaskModel.get_count_tasks(user_id)
        }
    
    @staticmethod
    def get_user_created_tasks(creator_id: int) -> List[Tuple]:
        """Получает задания созданные пользователем"""
        return UserTaskModel.get_user_tasks(creator_id)
    
    @staticmethod
    def cancel_user_task(task_id: int) -> bool:
        """Отменяет пользовательское задание без возврата средств"""
        return UserTaskModel.cancel_task(task_id)
    
    @staticmethod
    def delete_user_task(task_id: int) -> bool:
        """Удаляет пользовательское задание"""
        return UserTaskModel.delete_task(task_id)