@echo off
REM Starts both mock services. Ctrl-C stops them.
cd /d "%~dp0"

set BENEFITS_FAILURE_RATE=0.15

start "REST Service" python rest_service.py --port 8081
start "XML Service" python xml_service.py --port 8082 --failure-rate 0.40

echo.
echo   REST  http://127.0.0.1:8081/residents?page=1
echo   XML   http://127.0.0.1:8082/records
echo.
echo Both services started in separate windows. Close those windows to stop them.
