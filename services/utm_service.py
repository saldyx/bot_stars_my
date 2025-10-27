"""
Сервис для работы с UTM и статистикой
"""
from typing import List
from models.utm import UTMModel, StatisticsModel


class UTMService:
    """Сервис для работы с UTM-ссылками"""
    
    @staticmethod
    def add_utm_user(user_id: int, utm: str):
        """Добавляет пользователя по UTM-ссылке"""
        UTMModel.add_utm_user(user_id, utm)
    
    @staticmethod
    def get_utm_statistics(utm: str) -> dict:
        """Получает статистику по UTM-ссылке"""
        return {
            'total_users': UTMModel.users_utm_count(utm),
            'passed_op': UTMModel.users_utm_count_op(utm)
        }
    
    @staticmethod
    def mark_utm_passed(user_id: int, utm: str):
        """Отмечает что пользователь прошел ОП по UTM"""
        UTMModel.mark_utm_passed(user_id, utm)
    
    @staticmethod
    def delete_utm(utm: str):
        """Удаляет UTM-ссылку"""
        UTMModel.delete_utm(utm)
    
    @staticmethod
    def create_utm_link(url: str, count_users: int = 0) -> bool:
        """Создает UTM-ссылку"""
        try:
            UTMModel.create_utm(url, count_users)
            return True
        except Exception as e:
            print(f"Ошибка при создании UTM-ссылки: {e}")
            return False
    
    @staticmethod
    def get_all_utm_urls() -> List[str]:
        """Получает все UTM-ссылки"""
        return UTMModel.get_urls_utm()
    
    @staticmethod
    def increment_utm_users(url: str):
        """Увеличивает счетчик пользователей по UTM"""
        UTMModel.users_add_utm(url)
    
    @staticmethod
    def increment_utm_op_users(url: str):
        """Увеличивает счетчик прошедших ОП по UTM"""
        UTMModel.users_add_utm_op(url)
    
    @staticmethod
    def get_user_urls(user_id: int) -> List[str]:
        """Получает URL пользователя"""
        return UTMModel.get_urls_by_id(user_id)
    
    @staticmethod
    def add_user_url(user_id: int, url: str):
        """Добавляет URL для пользователя"""
        UTMModel.add_url(user_id, url)


class StatisticsService:
    """Сервис для статистики"""
    
    @staticmethod
    def get_user_statistics_by_period(period: str) -> dict:
        """Получает статистику пользователей за период"""
        try:
            users_count = StatisticsModel.get_users_by_period(period)
            return {
                'period': period,
                'users_count': users_count
            }
        except Exception as e:
            print(f"Ошибка при получении статистики: {e}")
            return {'period': period, 'users_count': 0}
    
    @staticmethod
    def get_comprehensive_statistics() -> dict:
        """Получает комплексную статистику"""
        from models.user import UserModel
        from services.game_service import ClickService
        
        return {
            'users': {
                'total': UserModel.get_user_count(),
                'day': StatisticsModel.get_users_by_period('day'),
                'week': StatisticsModel.get_users_by_period('week'),
                'month': StatisticsModel.get_users_by_period('month')
            },
            'financial': {
                'total_stars': UserModel.sum_all_stars(),
                'total_withdrawn': UserModel.sum_all_withdrawn()
            },
            'clicks': {
                'day': ClickService.get_click_statistics('day'),
                'week': ClickService.get_click_statistics('week'),
                'month': ClickService.get_click_statistics('month')
            }
        }