import os
import logging
import telebot
import pytubefix as pytube
import zipfile
import json
from telebot import types
from pytubefix import YouTube, Playlist
from moviepy import VideoFileClip
from dotenv import load_dotenv

from user_manager import UserContactManager

load_dotenv()

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')

user_data = {}

class YouTubeDownloader:
    def __init__(self, bot_token):
        """
        Initialize the YouTube Downloader Telegram Bot with enhanced error handling
        
        :param bot_token: Telegram Bot Token
        """
        self.bot = telebot.TeleBot(bot_token)
        self.contact_manager = UserContactManager()
        self.failed_downloads = {}  # Track failed download attempts
        self.setup_handlers()
        
        # Ensure necessary directories exist
        for dir in ['downloads', 'playlist_zip', 'failed_lists']:
            os.makedirs(dir, exist_ok=True)
        
    def setup_handlers(self):
        """
        Setup bot message handlers with enhanced error management
        """
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            welcome_text = (
                "Bem-vindo ao YouTube Downloader Bot! 🎥\n\n"
                "Comandos disponíveis:\n"
                "/download - Baixar vídeo ou playlist\n"
                "/retry - Tentar novamente downloads com falha\n"
                "/help - Mostrar ajuda"
            )
            self.contact_manager.save_user_contact(message.from_user)
            self.bot.reply_to(message, welcome_text)
        
        @self.bot.message_handler(commands=['retry'])
        def handle_retry(message):
            """
            Handle retry of failed downloads
            """
            chat_id = message.chat.id
            
            # Check if there are failed downloads for this user
            if str(chat_id) not in self.failed_downloads or not self.failed_downloads[str(chat_id)]:
                self.bot.send_message(chat_id, "Não há downloads com falha para tentar novamente.")
                return
            
            # Create retry markup
            markup = types.ReplyKeyboardMarkup(row_width=2)
            retry_all_btn = types.KeyboardButton('Tentar Todos')
            retry_select_btn = types.KeyboardButton('Selecionar Específicos')
            cancel_btn = types.KeyboardButton('Cancelar')
            markup.add(retry_all_btn, retry_select_btn, cancel_btn)
            
            # Send retry options
            retry_msg = "Escolha uma opção de retry:"
            failed_list = self.failed_downloads[str(chat_id)]
            retry_msg += "\n\nVídeos com falha:"
            for idx, (url, format_choice) in enumerate(failed_list, 1):
                retry_msg += f"\n{idx}. {url} (Formato: {format_choice})"
            
            self.bot.send_message(chat_id, retry_msg, reply_markup=markup)
            self.bot.register_next_step_handler_by_chat_id(chat_id, self.process_retry_selection)
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_url(message):
            try:
                # Check if message contains a valid YouTube URL
                if 'youtube.com' in message.text or 'youtu.be' in message.text:
                    markup = types.ReplyKeyboardMarkup(row_width=2)
                    mp3_button = types.KeyboardButton('MP3')
                    mp4_button = types.KeyboardButton('MP4')
                    markup.add(mp3_button, mp4_button)

                    user_data[message.chat.id] = {'url': message.text}
                    
                    # Store URL in user session
                    self.bot.send_message(
                        message.chat.id, 
                        "Escolha o formato de download:", 
                        reply_markup=markup,
                    )
                    
                    # Register next step handler
                    self.bot.register_next_step_handler(
                        message, 
                        self.process_format_selection
                    )
            except Exception as e:
                logging.error(f"Erro ao processar URL: {e}")
                self.bot.reply_to(message, f"Erro ao processar URL: {e}")
    
    def start_bot(self):
        """
        Start the Telegram Bot with error handling and logging
        """
        try:
            logging.info("Iniciando bot de download do YouTube...")
            print("Bot iniciado. Pressione Ctrl+C para parar.")
            
            # Configure logging
            # logging.basicConfig(
            #     level=logging.INFO,
            #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            #     filename='/app/logs/youtube_downloader.log'
            # )
            
            # Start bot polling
            self.bot.polling(none_stop=True, interval=0, timeout=0)
        
        except KeyboardInterrupt:
            # logging.info("Bot interrompido pelo usuário.")
            print("\nBot interrompido.")
        
        except Exception as e:
            # logging.error(f"Erro crítico no bot: {e}")
            print(f"Erro crítico: {e}")

    def process_retry_selection(self, message):
        """
        Process user's retry selection
        """
        chat_id = message.chat.id
        selection = message.text
        
        try:
            if selection == 'Cancelar':
                self.bot.send_message(chat_id, "Operação de retry cancelada.")
                return
            
            failed_list = self.failed_downloads.get(str(chat_id), [])
            
            if selection == 'Tentar Todos':
                # Retry all failed downloads
                for url, format_choice in failed_list:
                    if 'list=' in url:
                        self.download_playlist(chat_id, url, format_choice)
                    else:
                        self.download_video(chat_id, url, format_choice)
                
                # Clear failed downloads after retry
                self.failed_downloads[str(chat_id)] = []
            
            elif selection == 'Selecionar Específicos':
                # Prepare selection message
                select_msg = "Escolha os números dos vídeos para retry (separados por vírgula):\n"
                for idx, (url, format_choice) in enumerate(failed_list, 1):
                    select_msg += f"{idx}. {url} (Formato: {format_choice})\n"
                
                self.bot.send_message(chat_id, select_msg)
                self.bot.register_next_step_handler_by_chat_id(
                    chat_id, 
                    self.process_specific_retry
                )
        
        except Exception as e:
            logging.error(f"Erro no processo de retry: {e}")
            self.bot.send_message(chat_id, f"Erro no processo de retry: {e}")
    
    def process_specific_retry(self, message):
        """
        Process retry for specific videos
        """
        chat_id = message.chat.id
        selection = message.text
        
        try:
            # Parse selected indices
            selected_indices = [int(x.strip()) - 1 for x in selection.split(',')]
            failed_list = self.failed_downloads.get(str(chat_id), [])
            
            # Retry selected videos
            for idx in selected_indices:
                if 0 <= idx < len(failed_list):
                    url, format_choice = failed_list[idx]
                    if 'playlist' in url:
                        self.download_playlist(chat_id, url, format_choice)
                    else:
                        self.download_video(chat_id, url, format_choice)
            
            # Remove successfully retried videos
            self.failed_downloads[str(chat_id)] = [
                item for idx, item in enumerate(failed_list) 
                if idx not in selected_indices
            ]
            
            self.bot.send_message(chat_id, "Retry concluído.")
        
        except Exception as e:
            logging.error(f"Erro no retry específico: {e}")
            self.bot.send_message(chat_id, f"Erro no retry: {e}")
    
    def process_format_selection(self, message):
        """
        Process user's format selection and initiate download
        
        :param message: Telegram message object
        """
        try:
            # Retrieve stored URL from previous message
            url = url = user_data.get(message.chat.id, {}).get('url')

            if not url:
              self.bot.send_message(message.chat.id, "URL não encontrada. Reinicie o processo.")
              return

            format_choice = message.text.upper()
            
            if format_choice not in ['MP3', 'MP4']:
                self.bot.reply_to(message, "Formato inválido. Escolha MP3 ou MP4.")
                return
            
            # Determine if playlist or single video
            if 'list=' in url:
                self.download_playlist(message.chat.id, url, format_choice)
            else:
                self.download_video(message.chat.id, url, format_choice)
        
        except Exception as e:
            logging.error(f"Erro no download: {e}")
            self.bot.send_message(message.chat.id, f"Erro no download: {e}")
    
    def download_video(self, chat_id, url, format_choice, max_retries=3):
        """
        Download single YouTube video with retry mechanism
        
        :param chat_id: Telegram chat ID
        :param url: YouTube video URL
        :param format_choice: MP3 or MP4
        :param max_retries: Maximum number of retry attempts
        """
        for attempt in range(max_retries):
            try:
                yt = YouTube(url)
                
                # Create download directory
                os.makedirs(f'downloads', exist_ok=True)
                
                if format_choice == 'MP4':
                    stream = yt.streams.get_highest_resolution()
                    file_path = stream.download('downloads')
                else:  # MP3
                    stream = yt.streams.get_highest_resolution()
                    file_path = stream.download('downloads')
                    file_path = self.convert_to_mp3(file_path)
                
                # Send file to user
                with open(file_path, 'rb') as file:
                    self.bot.send_document(chat_id, file)
                
                # Clean up files
                os.remove(file_path)
                return
            
            except Exception as e:
                logging.error(f"Erro no download do vídeo (Tentativa {attempt + 1}): {e}")
                
                if attempt == max_retries - 1:
                    # Final attempt failed
                    self.bot.send_message(
                        chat_id, 
                        f"Falha no download após {max_retries} tentativas. Detalhes: {e}"
                    )
                    
                    # Track failed download for retry
                    if str(chat_id) not in self.failed_downloads:
                        self.failed_downloads[str(chat_id)] = []
                    
                    self.failed_downloads[str(chat_id)].append((url, format_choice))
                    
                    # Save failed list to file
                    self.save_failed_list(chat_id)
    
    def download_playlist(self, chat_id, url, format_choice, max_retries=3):
        """
        Download YouTube playlist with comprehensive error handling
        
        :param chat_id: Telegram chat ID
        :param url: YouTube playlist URL
        :param format_choice: MP3 or MP4
        :param max_retries: Maximum number of retry attempts
        """
        try:
            playlist = Playlist(url)
            
            # Create directories
            os.makedirs('downloads', exist_ok=True)
            os.makedirs('playlist_zip', exist_ok=True)
            
            downloaded_files = []
            failed_videos = []
            
            # Download each video
            for video_url in playlist.video_urls:
                video_download_success = False
                
                for attempt in range(max_retries):
                    try:
                        yt = YouTube(video_url)
                        
                        if format_choice == 'MP4':
                            stream = yt.streams.get_highest_resolution()
                            file_path = stream.download('downloads')
                        else:  # MP3
                            stream = yt.streams.get_highest_resolution()
                            file_path = stream.download('downloads')
                            file_path = self.convert_to_mp3(file_path)
                        
                        downloaded_files.append(file_path)
                        video_download_success = True
                        break
                    
                    except Exception as e:
                        logging.error(f"Erro no download do vídeo {video_url} (Tentativa {attempt + 1}): {e}")
                        
                        if attempt == max_retries - 1:
                            failed_videos.append((video_url, format_choice))
            
            # Create zip file if downloads succeeded
            if downloaded_files:
                zip_filename = f'playlist_{format_choice}_{chat_id}.zip'
                zip_path = os.path.join(f'playlist_zip', zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in downloaded_files:
                        zipf.write(file, os.path.basename(file))
                
                # Send zip file
                with open(zip_path, 'rb') as file:
                    self.bot.send_document(chat_id, file)
                
                # Clean up files
                for file in downloaded_files:
                    os.remove(file)
                os.remove(zip_path)
            
            # Handle failed videos
            if failed_videos:
                fail_msg = "Alguns vídeos não puderam ser baixados:\n"
                for url, _ in failed_videos:
                    fail_msg += f"- {url}\n"
                
                self.bot.send_message(chat_id, fail_msg)
                
                # Track failed downloads for retry
                if str(chat_id) not in self.failed_downloads:
                    self.failed_downloads[str(chat_id)] = []
                
                self.failed_downloads[str(chat_id)].extend(failed_videos)
                self.save_failed_list(chat_id)
        
        except Exception as e:
            logging.error(f"Erro no download da playlist: {e}")
            self.bot.send_message(chat_id, f"Erro no download da playlist: {e}")
    
    def save_failed_list(self, chat_id):
        """
        Save failed download list to a JSON file
        
        :param chat_id: Telegram chat ID
        """
        try:
            failed_list_path = f'failed_lists/{chat_id}_failed_downloads.json'
            with open(failed_list_path, 'w') as f:
                json.dump(self.failed_downloads.get(str(chat_id), []), f)
        except Exception as e:
            logging.error(f"Erro ao salvar lista de downloads com falha: {e}")
    
    def convert_to_mp3(self, file_path):
      """
      Convert a video file to MP3 format using MoviePy
      
      :param file_path: Path to the input video file
      :return: Path to the converted MP3 file
      """
      try:
          # Create directory for audio files if it doesn't exist
          os.makedirs('downloads', exist_ok=True)
          
          # Load the video file
          video = VideoFileClip(file_path)
          
          # Generate MP3 filename by replacing video extension with .mp3
          mp3_filename = os.path.splitext(os.path.basename(file_path))[0] + '.mp3'
          mp3_path = os.path.join('downloads', mp3_filename)
          
          # Extract audio and save as MP3
          video.audio.write_audiofile(mp3_path)
          
          # Close the video file to free up resources
          video.close()
          
          # Remove the original video file
          os.remove(file_path)
          
          return mp3_path
      
      except Exception as e:
          logging.error(f"Erro ao converter para MP3: {e}")
          # If conversion fails, return the original file path
          return file_path

# # Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/app/logs/youtube_downloader.log'
)

def main():
    downloader = YouTubeDownloader(BOT_TOKEN)
    downloader.start_bot()

if __name__ == '__main__':
    main()