import speech_recognition as sr
import pyttsx3
import json
import re
import os
import sqlite3

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

    def listen_for_command(self):
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
            
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()

    def run(self):
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
    finder = EVChargingFinder()
    finder.run()