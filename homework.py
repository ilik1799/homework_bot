import logging
import os
import requests
import sys
import time
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PR_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляем сообщение в Telegram пользователю."""
    try:
        logging.debug('Отправляем сообщение в Telegram: %s', message)
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение успешно отправлено: %s', message)
    except telegram.error.TelegramError as error:
        logging.error(f'Сообщение не отправлено: {error}')


class APIRequestError(Exception):
    """Исключение, возникающее при ошибке запроса к API."""

    pass


def get_api_answer(current_timestamp):
    """Получаем ответ API-сервиса и преобразуем JSON к типам данных Python."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    error_text = (
        'Сбой в работе программы: Эндпоинт {} '
        'недоступен. Код ответа API: {}.'
    )
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise APIRequestError(f'Код ответа API: {response.status_code}. '
                                  f'{error_text}')
    except requests.exceptions.ConnectionError as error:
        raise APIRequestError(f'Ошибка подключения: {error}. '
                              f'{error_text.format("Ошибка подключения")}')
    except requests.exceptions.RequestException as error:
        raise APIRequestError(f'Ошибка запроса: {error}. '
                              f'{error_text.format("Ошибка запроса")}')
    except APIRequestError:
        raise  # Пропускаем повторное возбуждение собственного исключения
    except Exception as error:
        raise APIRequestError(f'Неизвестная ошибка: {error}. '
                              f'{error_text.format("Неизвестная ошибка")}')
    else:
        response = response.json()
        return response


def check_response(response):
    """Проверка соответствия ответа сервера ожиданиям."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API некорректен, неверный тип данных!')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('Ответ API некорректен, '
                       'отсутствует ключ "homeworks"!')
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API некорректен, по ключю "homeworks" '
                        'получен не список!')
    return homeworks


def parse_status(homework):
    """Получаем статус домашней работы."""
    verdict = homework.get('status')
    if verdict is None:
        raise KeyError('Не удалось получить статус работы!')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('Не удалось получить название работы!')
    if verdict not in HOMEWORK_VERDICTS.keys():
        raise ValueError(
            ('Неизвестный статус проверки homework: {}!'
             ).format(verdict)
        )
    return (
        f'Изменился статус проверки работы "{homework_name}".'
        f' {HOMEWORK_VERDICTS.get(verdict)}'
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger = logging.getLogger()
        logger.critical('Отсутствуют переменные окружения!')
        raise ValueError('Отсутствуют обязательные переменные окружения!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    last_status = 'Статус не обновлялся'
    sent_message = ''
    while True:
        try:
            current_timestamp = int(time.time())
            response = get_api_answer(current_timestamp)
            homework_list = check_response(response)
            if not homework_list:
                logger.debug('Отсутствие в ответе новых статусов')
                status = 'Статус не обновлялся'
            else:
                status = parse_status(homework_list[0])
            if status != last_status:
                send_message(bot, status)
                last_status = status
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != sent_message:
                send_message(bot, message)
                sent_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    formatter = '%(asctime)s, %(levelname)s, %(message)s'
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(formatter))
    logger = logging.getLogger()
    logging.getLogger("telegram").setLevel(logging.ERROR)
    logger.setLevel(logging.INFO)
    logger.addHandler(stream_handler)
    main()
