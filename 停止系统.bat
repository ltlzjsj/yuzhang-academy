@echo off
echo Stopping services...

taskkill /FI "WINDOWTITLE eq AcademyBackend" /T /F
taskkill /FI "WINDOWTITLE eq AcademyWorker" /T /F
taskkill /FI "WINDOWTITLE eq AcademyFrontend" /T /F

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; Get-Process | Where-Object { $_.Path -eq 'D:\Anaconda\envs\geogemma\python.exe' } | Stop-Process -Force; Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'node.exe' -and ($_.CommandLine -like '*vite*' -or $_.CommandLine -like '*npm-cli.js*run dev*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Done.
pause
