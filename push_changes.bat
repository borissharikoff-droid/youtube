@echo off
chcp 65001 >nul
cd /d "C:\Users\fillo\OneDrive\Рабочий стол\dek2\youtube"
echo Текущая директория:
cd
echo.
echo Добавляем файлы в git...
git add bot.py
git add chart_generator.py
git add requirements.txt
git add CHANNEL_UPDATE_REPORT.md
git add CHART_GENERATION_REPORT.md
echo.
echo Создаем коммит...
git commit -m "Add chart generation feature: beautiful YouTube analytics charts"
echo.
echo Пушим в GitHub...
git push origin main
echo.
echo Готово!
pause
