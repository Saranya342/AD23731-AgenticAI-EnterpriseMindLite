@echo off
echo ============================================
echo EnterpriseMind-Lite Complete Evaluation
echo ============================================
python evaluation\evaluate_agent1.py
if errorlevel 1 goto end
python evaluation\evaluate_agent2.py
if errorlevel 1 goto end
python evaluation\evaluate_agent3.py
if errorlevel 1 goto end
python evaluation\evaluate_overall.py
:end
pause
