import os
import sqlite3
import logging
from datetime import datetime
import telebot
from telebot import types

class UserContactManager:
    def __init__(self, db_path='users.db'):
        """
        Initialize user contact management system
        
        :param db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        """
        Create database and tables for user contacts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        telegram_id INTEGER UNIQUE,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        language_code TEXT,
                        phone_number TEXT,
                        email TEXT,
                        registration_date TEXT,
                        last_interaction_date TEXT,
                        consent_marketing BOOLEAN DEFAULT 0,
                        total_downloads INTEGER DEFAULT 0,
                        preferred_format TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            logging.error(f"Erro ao configurar banco de dados: {e}")
    
    def save_user_contact(self, user, extra_data=None):
        """
        Save or update user contact information
        
        :param user: Telegram user object
        :param extra_data: Additional user data dictionary
        :return: Boolean indicating successful save
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Upsert user information
                cursor.execute('''
                    INSERT OR REPLACE INTO users (
                        telegram_id, 
                        username, 
                        first_name, 
                        last_name, 
                        language_code, 
                        registration_date,
                        last_interaction_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user.id, 
                    user.username, 
                    user.first_name, 
                    user.last_name, 
                    user.language_code,
                    now,
                    now
                ))
                
                # Update additional data if provided
                if extra_data:
                    update_fields = []
                    update_values = []
                    
                    for key, value in extra_data.items():
                        if key in ['phone_number', 'email', 'consent_marketing', 'preferred_format']:
                            update_fields.append(f"{key} = ?")
                            update_values.append(value)
                    
                    if update_fields:
                        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE telegram_id = ?"
                        update_values.append(user.id)
                        cursor.execute(update_query, tuple(update_values))
                
                conn.commit()
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar contato do usuário: {e}")
            return False
    
    def increment_downloads(self, user_id):
        """
        Increment total downloads for a user
        
        :param user_id: Telegram user ID
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET total_downloads = total_downloads + 1, 
                        last_interaction_date = ?
                    WHERE telegram_id = ?
                ''', (datetime.now().isoformat(), user_id))
                conn.commit()
        except Exception as e:
            logging.error(f"Erro ao incrementar downloads do usuário: {e}")
    
    def request_contact(self, bot, message):
        """
        Request user contact information with consent
        
        :param bot: Telegram bot instance
        :param message: Incoming message
        """
        markup = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
        contact_button = types.KeyboardButton("Compartilhar Contato", request_contact=True)
        no_thanks_button = types.KeyboardButton("Não, obrigado")
        markup.add(contact_button, no_thanks_button)
        
        consent_message = (
            "🤝 Gostaria de compartilhar seus dados de contato?\n\n"
            "Compartilhando, você nos ajuda a:\n"
            "• Personalizar sua experiência\n"
            "• Receber atualizações e novidades\n"
            "• Melhorar o serviço\n\n"
            "Seus dados são 100% seguros e você pode cancelar a qualquer momento."
        )
        
        bot.send_message(
            message.chat.id, 
            consent_message, 
            reply_markup=markup
        )
    
    def handle_contact(self, message, bot):
        """
        Handle user contact sharing
        
        :param message: Incoming message
        :param bot: Telegram bot instance
        """
        try:
            if message.contact:
                # User shared contact
                extra_data = {
                    'phone_number': message.contact.phone_number,
                    'consent_marketing': True
                }
                
                self.save_user_contact(message.from_user, extra_data)
                
                bot.send_message(
                    message.chat.id, 
                    "✅ Obrigado por compartilhar seus dados! "
                    "Agora você receberá atualizações e ofertas especiais.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            
            elif message.text == "Não, obrigado":
                # User declined sharing
                self.save_user_contact(
                    message.from_user, 
                    {'consent_marketing': False}
                )
                
                bot.send_message(
                    message.chat.id, 
                    "👍 Sem problemas! Respeitamos sua privacidade. "
                    "Você pode mudar de ideia a qualquer momento.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
        except Exception as e:
            logging.error(f"Erro no tratamento de contato: {e}")
    
    def get_marketing_users(self, min_downloads=1):
        """
        Retrieve users opted in for marketing
        
        :param min_downloads: Minimum number of downloads to qualify
        :return: List of user IDs
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT telegram_id 
                    FROM users 
                    WHERE consent_marketing = 1 
                    AND total_downloads >= ?
                ''', (min_downloads,))
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar usuários para marketing: {e}")
            return []
    
    def send_marketing_message(self, bot, message, target_users=None):
        """
        Send marketing message to targeted users
        
        :param bot: Telegram bot instance
        :param message: Marketing message text
        :param target_users: Optional list of specific user IDs
        """
        if not target_users:
            target_users = self.get_marketing_users()
        
        for user_id in target_users:
            try:
                bot.send_message(user_id, message)
            except Exception as e:
                logging.error(f"Erro ao enviar mensagem de marketing para {user_id}: {e}")
