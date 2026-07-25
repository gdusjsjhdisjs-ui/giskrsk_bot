@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem --- ГИС Красноярье: запуск бота (v14) ---

rem 1. Ищем Python: PATH, потом py -3, потом AppData\Local\Programs\Python
set PYCMD=
where python >nul 2>nul
if %errorlevel%==0 set PYCMD=python
if "%PYCMD%"=="" (
    where py >nul 2>nul
    if %errorlevel%==0 set PYCMD=py -3
)
if "%PYCMD%"=="" (
    for /d %%p in (%LOCALAPPDATA%\Programs\Python\Python3*) do (
        if exist "%%p\python.exe" set PYCMD=%%p\python.exe
    )
)
if "%PYCMD%"=="" (
    echo [ОШИБКА] Python не найден.
    echo Установите Python 3.11+ с python.org
    echo и поставьте галочку "Add python.exe to PATH" при установке.
    pause
    exit /b 1
)
%PYCMD% --version 2>nul
if not %errorlevel%==0 (
    echo [ОШИБКА] Python не работает. Попробуйте переустановить.
    pause
    exit /b 1
)

rem 2. Проверяем .env
if not exist .env (
    copy .env.example .env >nul
    echo [ВНИМАНИЕ] Создан файл .env из шаблона.
    echo Откройте .env в блокноте, заполните BOT_TOKEN и остальные поля,
    echo затем запустите start.bat снова.
    pause
    exit /b 1
)

rem 3. Виртуальное окружение
if not exist venv (
    echo Создаю виртуальное окружение...
    %PYCMD% -m venv venv
)
call venv\Scripts\activate.bat

rem 4. Зависимости
echo Устанавливаю зависимости (первый раз может занять несколько минут)...
pip install -q -r requirements.txt
if not %errorlevel%==0 (
    echo [ОШИБКА] Не удалось установить зависимости. Смотрите текст выше.
    pause
    exit /b 1
)

rem 5. Миграции БД
alembic upgrade head

rem 6. Запуск
echo Запускаю бота...
python -m app.main
pause
