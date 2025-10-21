# PowerShell script to push changes
Set-Location "C:\Users\fillo\OneDrive\Рабочий стол\dek2\youtube"

Write-Host "Adding files to git..."
git add bot.py
git add chart_generator.py  
git add requirements.txt
git add CHANNEL_UPDATE_REPORT.md
git add CHART_GENERATION_REPORT.md

Write-Host "Creating commit..."
git commit -m "Add chart generation feature: beautiful YouTube analytics charts"

Write-Host "Pushing to GitHub..."
git push origin main

Write-Host "Done!"
