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
import time
import queue

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
        
        # Variáveis para controle de gravação contínua
        self.is_recording = False
        self.recording_thread = None
        self.audio_queue = queue.Queue()
        self.stop_recording = threading.Event()
        
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
    
    def start_continuous_recording(self):
        """Inicia gravação contínua em thread separada"""
        if self.is_recording:
            return
            
        self.is_recording = True
        self.stop_recording.clear()
        self.audio_queue = queue.Queue()
        
        def record_audio():
            try:
                with sr.Microphone() as source:
                    print("🎤 Iniciando gravação contínua...")
                    
                    # Configurações básicas
                    self.recognizer.dynamic_energy_threshold = False
                    self.recognizer.energy_threshold = 300
                    
                    # Ajuste rápido de ruído
                    print("🔊 Ajustando ruído ambiente...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    print("✅ Pronto para gravar")
                    
                    # Gravar em chunks pequenos continuamente
                    audio_data = []
                    while not self.stop_recording.is_set():
                        try:
                            # Capturar chunk pequeno de áudio (1 segundo)
                            chunk = self.recognizer.listen(source, timeout=1, phrase_time_limit=1)
                            audio_data.append(chunk.frame_data)
                            print("📼 Chunk gravado...")
                        except sr.WaitTimeoutError:
                            # Timeout é normal, continuar gravando
                            continue
                        except Exception as e:
                            print(f"⚠️ Erro no chunk: {e}")
                            continue
                    
                    # Combinar todos os chunks em um único áudio
                    if audio_data:
                        print("🔗 Combinando áudio gravado...")
                        combined_data = b''.join(audio_data)
                        combined_audio = sr.AudioData(combined_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                        self.audio_queue.put(combined_audio)
                        print("✅ Áudio combinado e pronto para processamento")
                    
            except Exception as e:
                print(f"❌ Erro na gravação: {e}")
                self.audio_queue.put(None)
        
        self.recording_thread = threading.Thread(target=record_audio, daemon=True)
        self.recording_thread.start()
        print("🎙️ Gravação contínua iniciada")
    
    def stop_continuous_recording(self):
        """Para a gravação contínua e retorna o áudio"""
        if not self.is_recording:
            return None
            
        print("🛑 Parando gravação...")
        self.stop_recording.set()
        self.is_recording = False
        
        # Aguardar o áudio processado
        try:
            audio = self.audio_queue.get(timeout=5)
            if audio is None:
                raise Exception("Erro na captura de áudio")
            return audio
        except queue.Empty:
            raise Exception("Timeout ao processar áudio")
    
    def listen_for_web(self):
        """Método para uso na interface web - gravação contínua controlada pelo usuário"""
        try:
            # Iniciar gravação contínua
            self.start_continuous_recording()
            
            # Aguardar até que o usuário pare a gravação
            # (isso será controlado pela interface web)
            while self.is_recording:
                time.sleep(0.1)
            
            # Obter o áudio gravado
            audio = self.stop_continuous_recording()
            
            if audio is None:
                raise Exception("Nenhum áudio foi capturado")
            
            print("🔍 Processando áudio capturado...")
            
            # Reconhecer comando usando Google Speech Recognition
            command = self.recognizer.recognize_google(audio, language='pt-PT')
            print(f"✅ Texto reconhecido: {command}")
            return command.lower().strip()
                
        except sr.UnknownValueError:
            print("❌ Erro: Não foi possível entender o áudio")
            raise Exception("Não foi possível entender o áudio. Tente falar mais claramente.")
        except sr.RequestError as e:
            print(f"❌ Erro na requisição ao Google: {str(e)}")
            raise Exception(f"Erro na requisição ao Google: {str(e)}")
        except Exception as e:
            print(f"❌ Erro inesperado: {str(e)}")
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
                # Inserir dados realistas baseados na rede mobiE
                cursor.execute('''
                    INSERT INTO charging_stations (id, location, address, price, power, available)
                    VALUES
                        -- Lisboa (múltiplas opções)
                        ('MOBI-LIS-001', 'Lisboa', 'Avenida da Liberdade 180', 0.28, 22, true),
                        ('MOBI-LIS-002', 'Lisboa', 'Rua Castilho 39 (El Corte Inglés)', 0.32, 50, true),
                        ('MOBI-LIS-003', 'Lisboa', 'Avenida Engenheiro Duarte Pacheco 19', 0.25, 22, true),
                        ('MOBI-LIS-004', 'Lisboa', 'Parque das Nações - Alameda dos Oceanos', 0.43, 150, true),
                        ('MOBI-LIS-005', 'Lisboa', 'Centro Colombo - Avenida Lusíada', 0.35, 50, true),
                        
                        -- Porto (várias localizações)
                        ('MOBI-POR-001', 'Porto', 'Rua de Santa Catarina 312', 0.30, 22, true),
                        ('MOBI-POR-002', 'Porto', 'Via de Cintura Interna (VCI)', 0.45, 150, true),
                        ('MOBI-POR-003', 'Porto', 'Avenida da Boavista 1277', 0.28, 22, true),
                        ('MOBI-POR-004', 'Porto', 'Rua do Campo Alegre 687', 0.33, 50, true),
                        ('MOBI-POR-005', 'Porto', 'Aeroporto Francisco Sá Carneiro', 0.40, 50, true),
                        
                        -- Matosinhos (expandido)
                        ('MOBI-MAT-001', 'Matosinhos', 'Rua Brito Capelo 58', 0.29, 22, true),
                        ('MOBI-MAT-002', 'Matosinhos', 'Avenida General Norton de Matos', 0.35, 50, true),
                        ('MOBI-MAT-003', 'Matosinhos', 'Rua Roberto Ivens 625', 0.27, 22, true),
                        ('MOBI-MAT-004', 'Matosinhos', 'Parque da Cidade do Porto', 0.31, 22, true),
                        
                        -- Coimbra
                        ('MOBI-COI-001', 'Coimbra', 'Rua Ferreira Borges 59', 0.26, 22, true),
                        ('MOBI-COI-002', 'Coimbra', 'Avenida Fernão de Magalhães 199', 0.38, 50, true),
                        ('MOBI-COI-003', 'Coimbra', 'Pólo II da Universidade', 0.24, 22, true),
                        ('MOBI-COI-004', 'Coimbra', 'Forum Coimbra - Rua Antero de Quental', 0.34, 50, true),
                        
                        -- Braga
                        ('MOBI-BRG-001', 'Braga', 'Avenida Central 6', 0.27, 22, true),
                        ('MOBI-BRG-002', 'Braga', 'Rua do Souto 23', 0.29, 22, true),
                        ('MOBI-BRG-003', 'Braga', 'BragaParque - Quinta dos Congregados', 0.36, 50, true),
                        ('MOBI-BRG-004', 'Braga', 'Campus de Gualtar - Universidade do Minho', 0.25, 22, true),
                        
                        -- Aveiro
                        ('MOBI-AVE-001', 'Aveiro', 'Rua João Mendonça 505', 0.28, 22, true),
                        ('MOBI-AVE-002', 'Aveiro', 'Fórum Aveiro - Rua Batalhão Caçadores 10', 0.37, 50, true),
                        ('MOBI-AVE-003', 'Aveiro', 'Universidade de Aveiro - Campus Universitário', 0.23, 22, true),
                        
                        -- Faro
                        ('MOBI-FAR-001', 'Faro', 'Rua de Santo António 56', 0.31, 22, true),
                        ('MOBI-FAR-002', 'Faro', 'Aeroporto de Faro', 0.42, 50, true),
                        ('MOBI-FAR-003', 'Faro', 'Forum Algarve - Avenida do Estádio Algarve', 0.39, 50, true),
                        
                        -- Évora
                        ('MOBI-EVO-001', 'Évora', 'Praça do Giraldo 73', 0.26, 22, true),
                        ('MOBI-EVO-002', 'Évora', 'Universidade de Évora - Largo dos Colegiais', 0.24, 22, true),
                        ('MOBI-EVO-003', 'Évora', 'Évora Plaza - Rua Abel Viana', 0.35, 50, true),
                        
                        -- Setúbal
                        ('MOBI-SET-001', 'Setúbal', 'Avenida Luísa Todi 163', 0.30, 22, true),
                        ('MOBI-SET-002', 'Setúbal', 'AleShopping - Avenida António Bernardo Cabral de Macedo', 0.36, 50, true),
                        
                        -- Leiria
                        ('MOBI-LEI-001', 'Leiria', 'Rua Rodrigues Cordeiro 23', 0.27, 22, true),
                        ('MOBI-LEI-002', 'Leiria', 'LeiriaShopping - Rua de Telheiro', 0.34, 50, true),
                        
                        -- Viseu
                        ('MOBI-VIS-001', 'Viseu', 'Rua Direita 76', 0.28, 22, true),
                        ('MOBI-VIS-002', 'Viseu', 'Palácio do Gelo Shopping - Rua Cidade de Ourém', 0.37, 50, true)
                ''')
                conn.commit()
    
    def get_charging_stations(self, location):
        # Buscar carregadores por localização
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Normalizar acentos para a busca
            def normalize_text(text):
                replacements = {
                    'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a',
                    'é': 'e', 'ê': 'e',
                    'í': 'i',
                    'ó': 'o', 'ô': 'o', 'õ': 'o',
                    'ú': 'u', 'ü': 'u',
                    'ç': 'c'
                }
                text = text.lower()
                for accented, normal in replacements.items():
                    text = text.replace(accented, normal)
                return text
            
            # Buscar com normalização de acentos
            cursor.execute('''
                SELECT id, location, address, price, power, available
                FROM charging_stations
            ''')
            
            all_stations = cursor.fetchall()
            normalized_location = normalize_text(location)
            
            stations = []
            for row in all_stations:
                if normalize_text(row[1]) == normalized_location:
                    stations.append({
                        'id': row[0],
                        'location': row[1],
                        'address': row[2],
                        'price': row[3],
                        'power': row[4],
                        'available': bool(row[5])
                    })
            
            return stations
    
    def extract_location(self, command):
        # Melhorar extração de localização do comando em Português
        command = command.lower()
        print(f"Extraindo localização do comando: {command}")
        
        # Lista de cidades disponíveis na base de dados
        available_cities = [
            'lisboa', 'porto', 'matosinhos', 'coimbra', 'braga', 
            'aveiro', 'faro', 'évora', 'evora', 'setúbal', 'setubal', 
            'leiria', 'viseu'
        ]
        
        # Padrões mais flexíveis para extração de localização
        patterns = [
            r'(?:em|no|na|para|de)\s+([a-záàâãéêíóôõúç]+)',  # "em/no/na/para/de [cidade]"
            r'(?:carregador|posto|carregamento)\s+(?:em|no|na|de|para)?\s*([a-záàâãéêíóôõúç]+)',  # "carregador em [cidade]"
            r'([a-záàâãéêíóôõúç]+)\s+(?:carregador|posto|carregamento)',  # "[cidade] carregador"
            r'(?:procurar|encontrar|buscar)\s+(?:em|no|na|de|para)?\s*([a-záàâãéêíóôõúç]+)',  # "procurar em [cidade]"
            r'\b([a-záàâãéêíóôõúç]+)\b'  # Qualquer palavra que seja uma cidade conhecida
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, command)
            for match in matches:
                location = match.strip()
                # Verificar se a localização está na lista de cidades disponíveis
                if location in available_cities:
                    print(f"Localização encontrada: {location}")
                    return location
                # Verificar variações de acentos
                if location == 'evora' and 'évora' in available_cities:
                    print(f"Localização encontrada (normalizada): évora")
                    return 'évora'
                if location == 'setubal' and 'setúbal' in available_cities:
                    print(f"Localização encontrada (normalizada): setúbal")
                    return 'setúbal'
        
        print("Nenhuma localização encontrada no comando")
        print(f"Cidades disponíveis: {', '.join(available_cities)}")
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
        
        # Usar comando 'say' nativo do macOS para evitar problemas com pyttsx3
        def speak_in_thread():
            try:
                import subprocess
                # Usar o comando 'say' nativo do macOS com voz em português
                subprocess.run(['say', '-v', 'Joana', text], check=True)
                print("✅ Síntese de voz concluída")
            except subprocess.CalledProcessError as e:
                print(f"❌ Erro no comando 'say': {e}")
                # Fallback para pyttsx3 se o comando 'say' falhar
                try:
                    tts = pyttsx3.init()
                    tts.say(text)
                    tts.runAndWait()
                    tts.stop()
                except Exception as e2:
                    print(f"❌ Erro no fallback pyttsx3: {e2}")
            except Exception as e:
                print(f"❌ Erro na síntese de voz: {e}")
        
        threading.Thread(target=speak_in_thread, daemon=True).start()
    
    def setup_routes(self):
        """Configurar rotas Flask para a interface web"""
        
        @self.app.route('/')
        def index():
            return render_template('index.html')
        
        @self.app.route('/start_recording', methods=['POST'])
        def start_recording():
            try:
                self.start_continuous_recording()
                return jsonify({
                    'success': True,
                    'message': 'Gravação iniciada'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                })
        
        @self.app.route('/stop_recording', methods=['POST'])
        def stop_recording():
            try:
                audio = self.stop_continuous_recording()
                if audio is None:
                    raise Exception("Nenhum áudio foi capturado")
                
                # Reconhecer o áudio
                command = self.recognizer.recognize_google(audio, language='pt-PT')
                print(f"✅ Texto reconhecido: {command}")
                
                return jsonify({
                    'success': True,
                    'text': command.lower().strip(),
                    'command': command.lower().strip()
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                })
        
        @self.app.route('/listen', methods=['POST'])
        def listen():
            try:
                command = self.listen_for_web()
                return jsonify({
                    'success': True,
                    'text': command,
                    'command': command  # Manter compatibilidade
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