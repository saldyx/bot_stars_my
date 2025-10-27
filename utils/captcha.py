"""
Утилиты для работы с капчей
"""
import random
from typing import Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def generate_captcha(difficulty: int = 1) -> Tuple[str, int]:
    """Генерирует математическую капчу"""
    if difficulty == 1:
        min_num, max_num = 0, 9
        operators = ['+', '-', '*']
    elif difficulty == 2:
        min_num, max_num = 0, 20
        operators = ['+', '-', '*']
    else:
        min_num, max_num = 0, 50
        operators = ['+', '-', '*']
    
    num1 = random.randint(min_num, max_num)
    num2 = random.randint(min_num, max_num)
    operator = random.choice(operators)
    
    if operator == '-' and num1 < num2:
        num1, num2 = num2, num1
    
    question = f"<b>{num1} {operator} {num2} =</b>"
    
    if operator == '+':
        answer = num1 + num2
    elif operator == '-':
        answer = num1 - num2
    elif operator == '*':
        answer = num1 * num2
    else:
        answer = None
    
    return question, answer


def create_captcha_keyboard(correct_answer: int, ref_id: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для капчи"""
    answers = set()
    answers.add(correct_answer)
    while len(answers) < 3:
        offset = random.choice([i for i in range(-5, 6) if i != 0])
        candidate = correct_answer + offset
        answers.add(candidate)
    answers_list = list(answers)
    random.shuffle(answers_list)
    
    builder = InlineKeyboardBuilder()
    for answer in answers_list:
        builder.button(text=str(answer), callback_data=f"captcha_{answer}_{ref_id}")
    builder.adjust(3)
    return builder.as_markup()