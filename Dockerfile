# Используем официальный образ Python 3.10 как базовый
FROM python:3.10-slim-buster

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл requirements.txt в контейнер по пути /app
COPY requirements.txt .

# Устанавливаем все необходимые пакеты, указанные в requirements.txt
# --no-cache-dir предотвращает создание кэша pip, уменьшая размер образа
RUN pip install --no-cache-dir -r requirements.txt

# Команда для запуска приложения
# bot.py является точкой входа для вашего бота
CMD ["python", "bot.py"]