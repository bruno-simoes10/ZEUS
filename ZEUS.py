import speech_recognition as sr
import pyttsx3
import json
import re
import os
import sqlite3
from flask import Flask, render_template, request, jsonify
import threading
import signal
import sys

class EVChargingFinder:
    def __init__(self):
        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
        
        # Configure for M3 Mac
        sr.AudioData.FLAC_CONVERTER = "flac"
        sr.AudioData.FLAC_CONVERTER_PATHNAME = "/opt/homebrew/bin/flac"
        
        # Initialize text-to-speech engine with Portuguese
        self.tts_engine = pyttsx3.init()
        voices = self.tts_engine.getProperty('voices')
        # Set Portuguese voice if available
        for voice in voices:
            if 'pt' in voice.languages:
                self.tts_engine.setProperty('voice', voice.id)
                break
        self.tts_engine.setProperty('rate', 150)
        
        # Initialize SQLite database
        self.db_path = 'charging_stations.db'
        self.init_database()
        
        # Initialize Flask app
        self.app = Flask(__name__)
        self.setup_routes()
        self.running = True

    def listen_for_command(self):
        """Método original para uso em linha de comando"""
        with sr.Microphone() as source:
            print("\n=== Sistema de Reconhecimento de Voz ===")
            print("🎤 Ajustando microfone...")
            
            # Ajustes para captura mais completa
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = 1000
            self.recognizer.pause_threshold = 1.2
            self.recognizer.phrase_threshold = 0.3
            self.recognizer.non_speaking_duration = 1.0
            
            # Ajuste de ruído com feedback
            print("🔊 Calibrando para ruído ambiente...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("✅ Calibração concluída")
            
            max_attempts = 3  # Limite máximo de tentativas
            attempt = 0
            
            while attempt < max_attempts:
                try:
                    print("\n🎙️  Pode falar agora...")
                    audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=None)
                    print("🔍 Processando áudio...")
                    
                    command = self.recognizer.recognize_google(audio, language='pt-PT')
                    print("\n📝 Texto reconhecido:")
                    print(f"==> {command}")
                    
                    # Sistema de confirmação simplificado
                    print("\nPressione ENTER se o texto estiver correto, ou qualquer outra tecla para tentar novamente")
                    confirmation = input()
                    
                    if confirmation == "":
                        return command.lower()
                    else:
                        attempt += 1
                        if attempt < max_attempts:
                            print(f"Tentativa {attempt + 1} de {max_attempts}...")
                        continue
                        
                except sr.WaitTimeoutError:
                    print("❌ Nenhuma fala detectada no tempo limite")
                    return None
                except sr.UnknownValueError:
                    print("❌ Não foi possível entender o áudio, tente novamente")
                    attempt += 1
                    if attempt < max_attempts:
                        print(f"Tentativa {attempt + 1} de {max_attempts}...")
                    continue
                except sr.RequestError as e:
                    print(f"❌ Erro na requisição ao Google: {str(e)}")
                    return None
                except Exception as e:
                    print(f"❌ Erro inesperado: {str(e)}")
                    return None
            
            print("\n❌ Número máximo de tentativas atingido")
            return None
    
    def listen_for_web(self):
        """Método simplificado para uso na interface web"""
        try:
            with sr.Microphone() as source:
                # Ajustes para captura
                self.recognizer.dynamic_energy_threshold = False
                self.recognizer.energy_threshold = 1000
                self.recognizer.pause_threshold = 1.2
                self.recognizer.phrase_threshold = 0.3
                self.recognizer.non_speaking_duration = 1.0
                
                # Ajuste de ruído
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                # Capturar áudio
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=None)
                
                # Reconhecer comando
                command = self.recognizer.recognize_google(audio, language='pt-PT')
                return command.lower()
                
        except sr.WaitTimeoutError:
            raise Exception("Nenhuma fala detectada no tempo limite")
        except sr.UnknownValueError:
            raise Exception("Não foi possível entender o áudio")
        except sr.RequestError as e:
            raise Exception(f"Erro na requisição ao Google: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro inesperado: {str(e)}")

    def init_database(self):
        # Inicializar o banco de dados SQLite
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Criar tabela se não existir
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS charging_stations (
                    id VARCHAR(10) PRIMARY KEY,
                    location VARCHAR(100) NOT NULL,
                    address VARCHAR(200) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    power INTEGER NOT NULL,
                    available BOOLEAN NOT NULL DEFAULT true
                )
            ''')
            
            # Verificar se já existem dados
            cursor.execute('SELECT COUNT(*) FROM charging_stations')
            if cursor.fetchone()[0] == 0:
                # Inserir dados iniciais
                cursor.execute('''
                    INSERT INTO charging_stations (id, location, address, price, power, available)
                    VALUES
                        ('1', 'Matosinhos', 'Rua do Mar 123', 0.35, 50, true),
                        ('2', 'Matosinhos', 'Avenida da Praia 456', 0.40, 150, true)
                ''')
                conn.commit()
    
    def get_charging_stations(self, location):
        # Buscar carregadores por localização
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, location, address, price, power, available
                FROM charging_stations
                WHERE LOWER(location) = LOWER(?)
            ''', (location,))
            
            stations = [{
                'id': row[0],
                'location': row[1],
                'address': row[2],
                'price': row[3],
                'power': row[4],
                'available': bool(row[5])
            } for row in cursor.fetchall()]
            
            return stations
    
    def extract_location(self, command):
        # Melhorar extração de localização do comando em Português
        command = command.lower()
        print(f"Extraindo localização do comando: {command}")
        
        patterns = [
            r'(?:em|no|na)\s+([^,\s]+(?!\s+em|\s+no|\s+na))',  # "em/no/na Matosinhos"
            r'(?:carregador|posto)\s+(?:em|no|na|de)?\s*([^,\s]+(?!\s+em|\s+no|\s+na))',  # "carregador em/no/na/de Matosinhos"
            r'([^,\s]+)\s+(?:carregador|posto)',  # "Matosinhos carregador/posto"
            r'^(matosinhos)$'  # Aceitar apenas "matosinhos"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                location = match.group(1).strip()
                print(f"Localização encontrada: {location}")
                return location
        
        print("Nenhuma localização encontrada no comando")
        return None

    def find_best_charger(self, location):
        # Converter localização para minúsculas para garantir correspondência
        location = location.lower()
        
        # Buscar carregadores da localização
        chargers = self.get_charging_stations(location)
        
        if chargers:
            # Encontrar o carregador com o menor preço
            best_charger = min(chargers, key=lambda x: x['price'])
            return best_charger
        return None

    def speak_response(self, text):
        print(f"Falando: {text}")
        responses = {
            "Please specify a location in Portugal": "Por favor, especifique uma localização em Portugal",
            "Sorry, I couldn't find any charging stations in": "Desculpe, não encontrei nenhum posto de carregamento em",
            "The best charging station in": "O melhor posto de carregamento em",
            "is at": "está em",
            "with a price of": "com um preço de",
            "euros per kWh": "euros por kWh"
        }
        
        # Translate the response
        for eng, pt in responses.items():
            text = text.replace(eng, pt)
        
        # Usar threading para evitar conflito com Flask
        def speak_in_thread():
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                print(f"Erro na síntese de voz: {e}")
        
        threading.Thread(target=speak_in_thread, daemon=True).start()
    
    def setup_routes(self):
        """Configurar rotas Flask para a interface web"""
        
        @self.app.route('/')
        def index():
            return render_template('index.html')
        
        @self.app.route('/listen', methods=['POST'])
        def listen():
            try:
                command = self.listen_for_web()
                return jsonify({
                    'success': True,
                    'command': command
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                })
        
        @self.app.route('/process', methods=['POST'])
        def process():
            try:
                data = request.get_json()
                command = data.get('command', '')
                
                location = self.extract_location(command)
                
                if location:
                    best_charger = self.find_best_charger(location)
                    
                    if best_charger:
                        response_text = (f"O melhor posto de carregamento em {location} "
                                       f"está em {best_charger['address']} "
                                       f"com um preço de {best_charger['price']} euros por kWh")
                        
                        # Falar a resposta
                        self.speak_response(response_text)
                        
                        return jsonify({
                            'success': True,
                            'charger': best_charger,
                            'message': response_text
                        })
                    else:
                        error_msg = f"Desculpe, não encontrei nenhum posto de carregamento em {location}"
                        self.speak_response(error_msg)
                        return jsonify({
                            'success': False,
                            'error': error_msg
                        })
                else:
                    error_msg = "Por favor, especifique uma localização em Portugal"
                    self.speak_response(error_msg)
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    })
                    
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                })
        
        @self.app.route('/exit', methods=['POST'])
        def exit_app():
            self.running = False
            # Usar threading para parar o servidor após um pequeno delay
            def shutdown():
                import time
                time.sleep(1)
                os.kill(os.getpid(), signal.SIGTERM)
            
            threading.Thread(target=shutdown).start()
            return jsonify({'success': True})

    def run(self, mode='web'):
        """Executar o sistema em modo web ou linha de comando"""
        if mode == 'web':
            self.run_web()
        else:
            self.run_console()
    
    def run_web(self):
        """Executar interface web Flask"""
        print("🌐 Iniciando interface web...")
        print("📱 Acesse: http://localhost:8000")
        print("🛑 Para parar: Ctrl+C ou use o botão 'Sair' na interface")
        
        try:
            self.app.run(host='0.0.0.0', port=8000, debug=False)
        except KeyboardInterrupt:
            print("\n🛑 Servidor parado pelo usuário")
        except Exception as e:
            print(f"❌ Erro no servidor: {e}")
    
    def run_console(self):
        """Executar em modo linha de comando (original)"""
        while True:
            print("Diga o seu comando...")  # "Say your command..." in Portuguese
            command = self.listen_for_command()
            
            if command:
                location = self.extract_location(command)
                
                if location:
                    best_charger = self.find_best_charger(location)
                    
                    if best_charger:
                        response = (f"O melhor posto de carregamento em {location} "
                                  f"está em {best_charger['address']} "
                                  f"com um preço de {best_charger['price']} euros por kWh")
                    else:
                        response = f"Desculpe, não encontrei nenhum posto de carregamento em {location}"
                    
                    self.speak_response(response)
                else:
                    self.speak_response("Por favor, especifique uma localização em Portugal")
            
            print("\nPressione Enter para pesquisar novamente ou 'q' para sair")
            if input().lower() == 'q':
                break

if __name__ == "__main__":
    import sys
    
    finder = EVChargingFinder()
    
    # Verificar argumentos de linha de comando
    if len(sys.argv) > 1 and sys.argv[1] == '--console':
        print("🎤 Iniciando modo linha de comando...")
        finder.run(mode='console')
    else:
        print("🌐 Iniciando modo interface web...")
        print("💡 Para usar modo linha de comando: python3 ZEUS.py --console")
        finder.run(mode='web')