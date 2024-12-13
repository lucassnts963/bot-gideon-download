#!/bin/bash

# Atualizar sistema
sudo apt-get update
sudo apt-get upgrade -y

# Instalar Docker (caso não esteja instalado)
if ! command -v docker &> /dev/null
then
    # Script de instalação do Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    
    # Adicionar usuário ao grupo docker
    sudo usermod -aG docker $USER
fi

# Instalar Docker Compose
sudo apt-get install docker-compose -y

# Definir token do Telegram Bot
read -p "Digite o token do seu Bot do Telegram: " BOT_TOKEN
echo "TELEGRAM_BOT_TOKEN=$BOT_TOKEN" > .env

# Construir e iniciar containers
docker-compose up -d --build