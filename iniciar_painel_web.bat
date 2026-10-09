@echo off
chcp 65001 > nul
title Painel Web - Gerenciador Financeiro Telegram
echo ======================================================
echo  Iniciando Painel Streamlit do Gerenciador de Contas
echo ======================================================
streamlit run app.py
pause
