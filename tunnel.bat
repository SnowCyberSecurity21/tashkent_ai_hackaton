@echo off
REM Mezon: public HTTPS link to the local server (phone camera needs HTTPS). Start run.bat first.
setlocal
cd /d "%~dp0"

where cloudflared >nul 2>nul
if errorlevel 1 goto :noclf

curl -s -o nul -m 3 http://127.0.0.1:8000/api/health
if errorlevel 1 echo [!] Server 8000-portda javob bermayapti - avval run.bat ni ishga tushiring.

set "LOG=%TEMP%\mezon-tunnel.log"
if exist "%LOG%" del "%LOG%"
echo cloudflared tunnel ishga tushmoqda...
start "Mezon tunnel" /b cmd /c "cloudflared tunnel --no-autoupdate --url http://localhost:8000 > "%LOG%" 2>&1"

powershell -NoProfile -Command "$d=(Get-Date).AddSeconds(45); while((Get-Date) -lt $d){ $m = Select-String -Path $env:LOG -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1; if($m){ $u=$m.Matches[0].Value; Write-Host ''; Write-Host ('  HTTPS havola:  ' + $u) -ForegroundColor Green; Write-Host ('  QR sahifa:     ' + $u + '/#/connect'); Write-Host ('  Xodimlar:      ' + $u + '/staff.html'); Write-Host ''; exit 0 }; Start-Sleep -Milliseconds 500 }; Write-Host 'Havola 45 s ichida chiqmadi. Jurnal:' $env:LOG -ForegroundColor Yellow; exit 1"

echo Tunnel ishlab turibdi. To'xtatish uchun istalgan tugmani bosing...
pause >nul
taskkill /im cloudflared.exe /f >nul 2>nul
echo Tunnel to'xtatildi.
exit /b 0

:noclf
echo cloudflared o'rnatilmagan. O'rnatish (Windows):
echo.
echo     winget install --id Cloudflare.cloudflared -e
echo.
echo So'ng yangi terminal oching va tunnel.bat ni qayta ishga tushiring.
echo Muqobil: ngrok http 8000
exit /b 1
