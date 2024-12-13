#!/bin/bash
BACKUP_DIR="/opt/youtube-downloader-bot-backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Criar diretório de backups se não existir
mkdir -p $BACKUP_DIR

# Parar containers
docker-compose down

# Criar backup
tar -czvf "$BACKUP_DIR/bot_backup_$TIMESTAMP.tar.gz" .

# Reiniciar containers
docker-compose up -d