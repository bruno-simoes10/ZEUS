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
from openai import OpenAI
from dotenv import load_dotenv
import datetime
import pickle
import hashlib
from collections import defaultdict
import difflib
import time
import json

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# === SISTEMA DE MÉTRICAS E ANALYTICS (MELHORIA 10) ===
class PerformanceAnalytics:
    """Sistema de métricas e analytics de performance"""
    
    def __init__(self, metrics_file='performance_metrics.json'):
        self.metrics_file = metrics_file
        self.metrics = self.load_metrics()
        self.session_start = time.time()
        
    def load_metrics(self):
        """Carregar métricas existentes"""
        try:
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                'total_queries': 0,
                'total_response_time': 0.0,
                'query_frequency': {},
                'error_count': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'correction_count': 0,
                'daily_stats': {},
                'response_times': [],
                'popular_locations': {},
                'session_count': 0
            }
            
    def save_metrics(self):
        """Salvar métricas no arquivo"""
        try:
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Erro ao salvar métricas: {e}")
            
    def record_query(self, query, response_time, success=True, cache_hit=False, corrections_made=0):
        """Registrar uma consulta e suas métricas"""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Estatísticas gerais
        self.metrics['total_queries'] += 1
        self.metrics['total_response_time'] += response_time
        self.metrics['response_times'].append(response_time)
        
        # Manter apenas os últimos 1000 tempos de resposta
        if len(self.metrics['response_times']) > 1000:
            self.metrics['response_times'] = self.metrics['response_times'][-1000:]
            
        # Frequência de consultas
        query_key = query.lower().strip()
        self.metrics['query_frequency'][query_key] = self.metrics['query_frequency'].get(query_key, 0) + 1
        
        # Cache statistics
        if cache_hit:
            self.metrics['cache_hits'] += 1
        else:
            self.metrics['cache_misses'] += 1
            
        # Correções
        self.metrics['correction_count'] += corrections_made
        
        # Erros
        if not success:
            self.metrics['error_count'] += 1
            
        # Estatísticas diárias
        if today not in self.metrics['daily_stats']:
            self.metrics['daily_stats'][today] = {
                'queries': 0,
                'avg_response_time': 0.0,
                'errors': 0,
                'cache_hits': 0
            }
            
        daily = self.metrics['daily_stats'][today]
        daily['queries'] += 1
        daily['avg_response_time'] = (daily['avg_response_time'] * (daily['queries'] - 1) + response_time) / daily['queries']
        
        if not success:
            daily['errors'] += 1
        if cache_hit:
            daily['cache_hits'] += 1
            
        # Extrair localização da consulta para estatísticas
        self._extract_location_stats(query)
        
        # Salvar métricas
        self.save_metrics()
        
    def _extract_location_stats(self, query):
        """Extrair e registrar estatísticas de localização"""
        locations = ['lisboa', 'porto', 'coimbra', 'braga', 'aveiro', 'faro', 'évora', 'setúbal', 'leiria', 'viseu']
        query_lower = query.lower()
        
        for location in locations:
            if location in query_lower:
                self.metrics['popular_locations'][location] = self.metrics['popular_locations'].get(location, 0) + 1
                break
                
    def get_performance_report(self):
        """Gerar relatório de performance"""
        if self.metrics['total_queries'] == 0:
            return "📊 Nenhuma consulta registrada ainda."
            
        avg_response_time = self.metrics['total_response_time'] / self.metrics['total_queries']
        cache_hit_rate = (self.metrics['cache_hits'] / (self.metrics['cache_hits'] + self.metrics['cache_misses'])) * 100 if (self.metrics['cache_hits'] + self.metrics['cache_misses']) > 0 else 0
        error_rate = (self.metrics['error_count'] / self.metrics['total_queries']) * 100
        
        # Top 5 consultas mais frequentes
        top_queries = sorted(self.metrics['query_frequency'].items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Top 5 localizações mais populares
        top_locations = sorted(self.metrics['popular_locations'].items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Estatísticas de tempo de resposta
        response_times = self.metrics['response_times']
        if response_times:
            min_time = min(response_times)
            max_time = max(response_times)
            median_time = sorted(response_times)[len(response_times)//2] if response_times else 0
        else:
            min_time = max_time = median_time = 0
            
        report = f"""
📊 **RELATÓRIO DE PERFORMANCE ZEUS**

🔢 **Estatísticas Gerais:**
• Total de consultas: {self.metrics['total_queries']}
• Tempo médio de resposta: {avg_response_time:.2f}s
• Tempo mínimo: {min_time:.2f}s
• Tempo máximo: {max_time:.2f}s
• Tempo mediano: {median_time:.2f}s

💾 **Cache Performance:**
• Taxa de acerto: {cache_hit_rate:.1f}%
• Cache hits: {self.metrics['cache_hits']}
• Cache misses: {self.metrics['cache_misses']}

❌ **Erros:**
• Taxa de erro: {error_rate:.1f}%
• Total de erros: {self.metrics['error_count']}

🔧 **Correções:**
• Total de correções aplicadas: {self.metrics['correction_count']}

🔥 **Top 5 Consultas:**
"""
        
        for i, (query, count) in enumerate(top_queries, 1):
            report += f"   {i}. \"{query[:50]}...\" ({count}x)\n"
            
        report += "\n🌍 **Localizações Mais Populares:**\n"
        for i, (location, count) in enumerate(top_locations, 1):
            report += f"   {i}. {location.title()} ({count} consultas)\n"
            
        return report
        
    def get_daily_stats(self, days=7):
        """Obter estatísticas dos últimos N dias"""
        today = datetime.datetime.now()
        stats = []
        
        for i in range(days):
            date = (today - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            if date in self.metrics['daily_stats']:
                day_stats = self.metrics['daily_stats'][date]
                stats.append({
                    'date': date,
                    'queries': day_stats['queries'],
                    'avg_response_time': day_stats['avg_response_time'],
                    'errors': day_stats['errors'],
                    'cache_hits': day_stats['cache_hits']
                })
            else:
                stats.append({
                    'date': date,
                    'queries': 0,
                    'avg_response_time': 0,
                    'errors': 0,
                    'cache_hits': 0
                })
                
        return stats
        
    def start_session(self):
        """Iniciar nova sessão"""
        self.session_start = time.time()
        self.metrics['session_count'] += 1
        self.save_metrics()
        
    def get_session_time(self):
        """Obter tempo da sessão atual"""
        return time.time() - self.session_start

# === SISTEMA DE VALIDAÇÃO E CORREÇÃO AUTOMÁTICA (MELHORIA 9) ===
class TextCorrector:
    """Sistema de correção automática de erros de digitação"""
    
    def __init__(self):
        # Dicionário de palavras-chave válidas do domínio
        self.valid_words = {
            # Localizações
            'lisboa', 'porto', 'coimbra', 'braga', 'aveiro', 'faro', 'évora', 
            'setúbal', 'leiria', 'viseu', 'matosinhos', 'portimão', 'lagos',
            'viana', 'vila real', 'beja', 'santarém', 'castelo branco',
            
            # Termos de carregamento
            'carregador', 'carregadores', 'posto', 'postos', 'estação', 'estações',
            'ponto', 'pontos', 'terminal', 'terminais', 'tomada', 'tomadas',
            'carregamento', 'carregar', 'recarregar', 'abastecer',
            
            # Qualificadores
            'barato', 'económico', 'econômico', 'rápido', 'potente', 'veloz',
            'disponível', 'livre', 'aberto', 'funcional', 'operacional', 'ativo',
            'melhor', 'bom', 'boa', 'excelente', 'óptimo', 'ótimo',
            
            # Conectores e tipos
            'type', 'tipo', 'mennekes', 'chademo', 'ccs', 'combo',
            'corrente', 'alternada', 'contínua', 'fast', 'charge',
            
            # Redes
            'mobie', 'mobiE', 'galp', 'electric', 'edp', 'comercial', 'tesla', 'supercharger',
            
            # Preposições e conectores
            'em', 'no', 'na', 'de', 'do', 'da', 'para', 'até', 'a', 'com', 'sem',
            'perto', 'próximo', 'junto', 'lado', 'redondezas', 'proximidades',
            'preciso', 'necessito', 'quero', 'gostaria', 'desejo', 'procuro',
            'há', 'existe', 'tem', 'encontro', 'onde', 'aonde',
            
            # Números e unidades
            'kw', 'kilowatt', 'quilowatt', 'euros', 'euro', 'km', 'quilómetros', 'quilometros',
            
            # Outros
            'carro', 'veículo', 'automóvel', 'viatura', 'elétrico', 'ev',
            'urgente', 'já', 'agora', 'imediatamente', 'neste', 'momento', 'atualmente',
            'norte', 'centro', 'sul', 'algarve', 'alentejo', 'região', 'zona', 'área',
            'universidade', 'campus', 'faculdade', 'shopping', 'mall', 'aeroporto', 'airport'
        }
        
        # Correções comuns específicas
        self.common_corrections = {
            'lixboa': 'lisboa',
            'lisbao': 'lisboa',
            'lisbon': 'lisboa',
            'poto': 'porto',
            'oporto': 'porto',
            'coimbr': 'coimbra',
            'coimbra': 'coimbra',
            'brag': 'braga',
            'avero': 'aveiro',
            'fro': 'faro',
            'evora': 'évora',
            'setubal': 'setúbal',
            'leria': 'leiria',
            'visu': 'viseu',
            'carregadro': 'carregador',
            'carregadore': 'carregadores',
            'posto': 'posto',
            'estacão': 'estação',
            'barato': 'barato',
            'economico': 'económico',
            'rapido': 'rápido',
            'disponivel': 'disponível',
            'livre': 'livre',
            'melhor': 'melhor',
            'proximo': 'próximo',
            'perto': 'perto'
        }
        
    def correct_text(self, text):
        """Corrigir texto automaticamente"""
        if not text or len(text.strip()) == 0:
            return text
            
        original_text = text
        words = text.lower().split()
        corrected_words = []
        corrections_made = []
        
        for word in words:
            # Remover pontuação para análise
            clean_word = ''.join(c for c in word if c.isalnum())
            
            if not clean_word:
                corrected_words.append(word)
                continue
                
            # Verificar correções específicas primeiro
            if clean_word in self.common_corrections:
                corrected = self.common_corrections[clean_word]
                corrected_words.append(corrected)
                corrections_made.append(f"{clean_word} → {corrected}")
                continue
                
            # Verificar se a palavra já está correta
            if clean_word in self.valid_words:
                corrected_words.append(word)
                continue
                
            # Tentar encontrar palavra similar
            suggestion = self._find_best_match(clean_word)
            if suggestion and suggestion != clean_word:
                corrected_words.append(suggestion)
                corrections_made.append(f"{clean_word} → {suggestion}")
            else:
                corrected_words.append(word)
                
        corrected_text = ' '.join(corrected_words)
        
        # Mostrar correções se houver
        if corrections_made:
            print(f"🔧 Correções aplicadas: {', '.join(corrections_made)}")
            print(f"📝 Texto original: {original_text}")
            print(f"✅ Texto corrigido: {corrected_text}")
            
        return corrected_text
        
    def _find_best_match(self, word):
        """Encontrar a melhor correspondência para uma palavra"""
        if len(word) < 3:  # Palavras muito curtas não são corrigidas
            return word
            
        # Usar difflib para encontrar correspondências próximas
        matches = difflib.get_close_matches(
            word, 
            self.valid_words, 
            n=1, 
            cutoff=0.6  # 60% de similaridade mínima
        )
        
        if matches:
            return matches[0]
            
        return word
        
    def suggest_corrections(self, text):
        """Sugerir correções sem aplicá-las automaticamente"""
        words = text.lower().split()
        suggestions = []
        
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            
            if clean_word and clean_word not in self.valid_words:
                suggestion = self._find_best_match(clean_word)
                if suggestion and suggestion != clean_word:
                    suggestions.append({
                        'original': clean_word,
                        'suggestion': suggestion,
                        'confidence': difflib.SequenceMatcher(None, clean_word, suggestion).ratio()
                    })
                    
        return suggestions

# === SISTEMA DE CACHE INTELIGENTE (MELHORIA 8) ===
class QueryCache:
    """Sistema de cache para consultas frequentes"""
    
    def __init__(self, cache_file='query_cache.pkl', max_size=100):
        self.cache_file = cache_file
        self.max_size = max_size
        self.cache = self.load_cache()
        self.query_stats = defaultdict(int)
        
    def load_cache(self):
        """Carregar cache de consultas"""
        try:
            with open(self.cache_file, 'rb') as f:
                return pickle.load(f)
        except (FileNotFoundError, EOFError):
            return {}
            
    def save_cache(self):
        """Salvar cache de consultas"""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.cache, f)
            
    def _generate_key(self, query):
        """Gerar chave única para a consulta"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
        
    def get(self, query):
        """Obter resultado do cache"""
        key = self._generate_key(query)
        if key in self.cache:
            # Atualizar timestamp de último acesso
            self.cache[key]['last_accessed'] = datetime.datetime.now().isoformat()
            self.cache[key]['access_count'] += 1
            print(f"📋 Cache hit para consulta: {query[:50]}...")
            return self.cache[key]['result']
        return None
        
    def set(self, query, result):
        """Armazenar resultado no cache"""
        key = self._generate_key(query)
        
        # Limpar cache se atingir tamanho máximo
        if len(self.cache) >= self.max_size:
            self._cleanup_cache()
            
        self.cache[key] = {
            'query': query,
            'result': result,
            'created': datetime.datetime.now().isoformat(),
            'last_accessed': datetime.datetime.now().isoformat(),
            'access_count': 1
        }
        self.save_cache()
        print(f"💾 Resultado armazenado no cache para: {query[:50]}...")
        
    def _cleanup_cache(self):
        """Limpar entradas menos utilizadas do cache"""
        # Ordenar por frequência de acesso e remover 20% das menos utilizadas
        sorted_items = sorted(self.cache.items(), key=lambda x: x[1]['access_count'])
        items_to_remove = int(len(sorted_items) * 0.2)
        
        for i in range(items_to_remove):
            del self.cache[sorted_items[i][0]]
            
        print(f"🧹 Cache limpo: removidas {items_to_remove} entradas")
        
    def get_stats(self):
        """Obter estatísticas do cache"""
        total_entries = len(self.cache)
        total_accesses = sum(entry['access_count'] for entry in self.cache.values())
        
        return {
            'total_entries': total_entries,
            'total_accesses': total_accesses,
            'cache_size': f"{total_entries}/{self.max_size}"
        }

# === SISTEMA DE APRENDIZAGEM (MELHORIA 6) ===
class PatternLearner:
    """Sistema de aprendizagem para padrões não reconhecidos"""
    
    def __init__(self, log_file='unmatched_patterns.pkl'):
        self.log_file = log_file
        self.unmatched_commands = self.load_logs()
        
    def load_logs(self):
        """Carregar logs de comandos não reconhecidos"""
        try:
            with open(self.log_file, 'rb') as f:
                return pickle.load(f)
        except (FileNotFoundError, EOFError):
            return []
            
    def save_logs(self):
        """Salvar logs de comandos não reconhecidos"""
        with open(self.log_file, 'wb') as f:
            pickle.dump(self.unmatched_commands, f)
            
    def log_unmatched(self, command, context=None):
        """Registar comando que não foi reconhecido"""
        entry = {
            'command': command,
            'timestamp': datetime.datetime.now().isoformat(),
            'context': context,
            'frequency': 1
        }
        
        # Verificar se comando já existe
        for existing in self.unmatched_commands:
            if existing['command'].lower() == command.lower():
                existing['frequency'] += 1
                existing['last_seen'] = entry['timestamp']
                self.save_logs()
                return
                
        # Adicionar novo comando
        self.unmatched_commands.append(entry)
        self.save_logs()
        print(f"📝 Comando não reconhecido registado: {command}")
        
    def suggest_patterns(self, min_frequency=2):
        """Sugerir novos padrões baseados em comandos frequentes"""
        frequent_commands = [cmd for cmd in self.unmatched_commands if cmd['frequency'] >= min_frequency]
        
        suggestions = []
        for cmd in frequent_commands:
            # Análise simples para sugerir padrões
            command_text = cmd['command'].lower()
            
            # Detectar padrões comuns
            if 'carregador' in command_text and any(city in command_text for city in ['lisboa', 'porto', 'coimbra', 'braga', 'aveiro']):
                pattern = f"Padrão sugerido para '{cmd['command']}': (r'.*carregador.*cidade.*', lambda m: 'SELECT * FROM charging_stations WHERE...')"
                suggestions.append(pattern)
                
        return suggestions
        
    def get_learning_stats(self):
        """Obter estatísticas de aprendizagem"""
        total_commands = len(self.unmatched_commands)
        frequent_commands = len([cmd for cmd in self.unmatched_commands if cmd['frequency'] >= 2])
        
        return {
            'total_unmatched': total_commands,
            'frequent_patterns': frequent_commands,
            'suggestions_available': len(self.suggest_patterns())
        }

class EVChargingFinder:
    def __init__(self, use_regex_only=False):
        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
        
        # Configuração do sistema NLP
        self.use_regex_only = use_regex_only
        if use_regex_only:
            print("🚀 Modo apenas regex ativado (mais rápido e confiável)")
        
        # Sistema de sinônimos expandido baseado na rede mobiE e linguagem natural portuguesa
        self.sinonimos = {
            # Termos para carregador (baseado na rede mobiE)
            'carregador': ['posto', 'estação', 'terminal', 'ponto', 'tomada', 'plug', 'socket'],
            'posto de carregamento': ['carregador'],
            'estação de carregamento': ['carregador'],
            'ponto de carregamento': ['carregador'],
            'terminal de carregamento': ['carregador'],
            
            # Termos de preço e economia
            'barato': ['económico', 'econômico', 'em conta', 'acessível', 'baixo preço', 'mais em conta', 'menor preço'],
            'económico': ['barato'],
            'econômico': ['barato'],
            'acessível': ['barato'],
            'em conta': ['barato'],
            
            # Termos de velocidade e potência
            'rápido': ['veloz', 'potente', 'forte', 'super', 'alta potência', 'high power', 'turbo'],
            'potente': ['rápido'],
            'veloz': ['rápido'],
            'forte': ['rápido'],
            'super': ['rápido'],
            'turbo': ['rápido'],
            
            # Termos de qualidade
            'melhor': ['bom', 'top', 'excelente', 'ideal', 'óptimo', 'ótimo', 'perfeito', 'recomendado'],
            'bom': ['melhor'],
            'excelente': ['melhor'],
            'ideal': ['melhor'],
            'óptimo': ['melhor'],
            'ótimo': ['melhor'],
            'perfeito': ['melhor'],
            
            # Termos de localização
            'onde': ['aonde', 'local', 'sítio', 'lugar', 'localização', 'posição'],
            'local': ['onde'],
            'sítio': ['onde'],
            'lugar': ['onde'],
            'localização': ['onde'],
            
            # Termos de ação
            'carregar': ['carregamento', 'abastecer', 'recarregar', 'alimentar', 'energizar'],
            'carregamento': ['carregar'],
            'abastecer': ['carregar'],
            'recarregar': ['carregar'],
            
            # Termos de veículo
            'carro': ['veículo', 'automóvel', 'viatura', 'EV', 'elétrico', 'tesla', 'leaf'],
            'veículo': ['carro'],
            'automóvel': ['carro'],
            'viatura': ['carro'],
            'elétrico': ['carro'],
            
            # Termos de disponibilidade
            'disponível': ['livre', 'aberto', 'funcional', 'operacional', 'ativo'],
            'livre': ['disponível'],
            'aberto': ['disponível'],
            'funcional': ['disponível'],
            'operacional': ['disponível'],
            
            # Termos de proximidade
            'perto': ['próximo', 'cerca', 'junto', 'ao lado', 'nas redondezas'],
            'próximo': ['perto'],
            'junto': ['perto'],
            'ao lado': ['perto'],
            'nas redondezas': ['perto'],
            
            # Termos de necessidade/urgência
            'preciso': ['necessito', 'quero', 'gostaria', 'desejo', 'procuro'],
            'necessito': ['preciso'],
            'quero': ['preciso'],
            'gostaria': ['preciso'],
            'desejo': ['preciso'],
            'procuro': ['preciso'],
            
            # Conectores e tipos específicos da mobiE
            'type 2': ['tipo 2', 'mennekes'],
            'chademo': ['chademo'],
            'ccs': ['combo'],
            'ac': ['corrente alternada'],
            'dc': ['corrente contínua', 'fast charge'],
            
            # Redes específicas portuguesas
            'mobie': ['mobiE', 'rede mobie'],
            'galp': ['galp electric'],
            'edp': ['edp comercial'],
            'tesla': ['supercharger']
        }
        
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
        
        # Inicializar cliente OpenAI
        self.openai_client = None
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if self.openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                print("✅ Cliente OpenAI inicializado com sucesso!")
            except Exception as e:
                print(f"⚠️ Erro ao inicializar OpenAI: {e}")
                print("💡 Usando sistema de regex como fallback")
        else:
            print("⚠️ OPENAI_API_KEY não encontrada nas variáveis de ambiente")
            print("💡 Usando sistema de regex como fallback")
        
        # Initialize SQLite database
        self.db_path = 'charging_stations.db'
        self.init_database()
        
        # Inicializar sistema de aprendizagem
        self.pattern_learner = PatternLearner()
        
        # Inicializar sistema de cache
        self.query_cache = QueryCache()
        
        # Inicializar sistema de correção de texto
        self.text_corrector = TextCorrector()
        
        # Inicializar sistema de analytics
        self.analytics = PerformanceAnalytics()
        self.analytics.start_session()
        
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
            
            # === MELHORIAS NA BASE DE DADOS (MELHORIA 7) ===
            # Criar tabela expandida com novos campos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS charging_stations (
                    id VARCHAR(10) PRIMARY KEY,
                    location VARCHAR(100) NOT NULL,
                    address VARCHAR(200) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    power INTEGER NOT NULL,
                    available BOOLEAN NOT NULL DEFAULT true,
                    connector_type VARCHAR(50) DEFAULT 'Type 2',
                    network VARCHAR(50) DEFAULT 'mobiE',
                    status VARCHAR(20) DEFAULT 'operational',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Verificar se já existem dados
            cursor.execute('SELECT COUNT(*) FROM charging_stations')
            if cursor.fetchone()[0] == 0:
                # Inserir dados realistas baseados na rede mobiE com novos campos
                cursor.execute('''
                    INSERT INTO charging_stations (id, location, address, price, power, available, connector_type, network, status)
                    VALUES
                        -- Lisboa (múltiplas opções)
                        ('MOBI-LIS-001', 'Lisboa', 'Avenida da Liberdade 180', 0.28, 22, true, 'Type 2', 'mobiE', 'operational'),
                        ('MOBI-LIS-002', 'Lisboa', 'Rua Castilho 39 (El Corte Inglés)', 0.32, 50, true, 'CCS', 'Galp Electric', 'operational'),
                        ('MOBI-LIS-003', 'Lisboa', 'Avenida Engenheiro Duarte Pacheco 19', 0.25, 22, true, 'Type 2', 'mobiE', 'operational'),
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
    
    def text_to_sql_with_chatgpt(self, command):
        """Converte texto natural em query SQL usando ChatGPT"""
        if not self.openai_client:
            print("🔄 OpenAI não disponível, usando sistema de regex")
            return self.text_to_sql_regex(command)
        
        try:
            # Prompt engineering para gerar SQL preciso
            system_prompt = """
            Você é um especialista em SQL que converte comandos em português para queries SQL precisas.
            
            SCHEMA DA BASE DE DADOS:
            Tabela: charging_stations
            Colunas:
            - id (VARCHAR): Identificador único do carregador (ex: 'MOBI-LIS-001')
            - location (VARCHAR): Cidade onde está localizado
            - address (VARCHAR): Endereço completo
            - price (DECIMAL): Preço por kWh em euros
            - power (INTEGER): Potência em kW
            - available (BOOLEAN): Se está disponível (sempre true)
            
            CIDADES DISPONÍVEIS: Lisboa, Porto, Matosinhos, Coimbra, Braga, Aveiro, Faro, Évora, Setúbal, Leiria, Viseu
            
            REGRAS IMPORTANTES:
            1. SEMPRE retorne apenas a query SQL, sem explicações
            2. Use LOWER() para comparações de texto insensíveis a maiúsculas
            3. Use LIKE '%termo%' para buscas parciais
            4. Para "melhor" ou "mais barato": ORDER BY price ASC LIMIT 1
            5. Para "mais rápido" ou "mais potente": ORDER BY power DESC LIMIT 1
            6. Para busca por cidade: WHERE LOWER(location) LIKE '%cidade%'
            7. Para busca por potência específica: WHERE power >= valor
            8. Se não especificar cidade, não adicione filtro de localização
            9. Sempre inclua ORDER BY para resultados consistentes
            10. Use LIMIT quando apropriado para evitar muitos resultados
            
            EXEMPLOS:
            "melhor carregador em Lisboa" → SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%lisboa%' ORDER BY price ASC LIMIT 1
            "carregador mais rápido" → SELECT * FROM charging_stations ORDER BY power DESC LIMIT 1
            "carregadores no Porto" → SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%porto%' ORDER BY price ASC
            """
            
            user_prompt = f"Converta este comando para SQL: {command}"
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Limpar a resposta (remover markdown se presente)
            if sql_query.startswith('```sql'):
                sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            elif sql_query.startswith('```'):
                sql_query = sql_query.replace('```', '').strip()
            
            print(f"🤖 SQL gerado pelo ChatGPT: {sql_query}")
            return sql_query
            
        except Exception as e:
            print(f"❌ Erro ao usar ChatGPT: {e}")
            print("🔄 Usando sistema de regex como fallback")
            return self.text_to_sql_regex(command)
    
    def expand_synonyms(self, text):
        """
        Expande sinônimos no texto para melhor reconhecimento
        """
        text_expanded = text.lower()
        
        # Substituir sinônimos por palavras-chave principais
        for palavra_chave, sinonimos in self.sinonimos.items():
            for sinonimo in sinonimos:
                # Usar word boundaries para evitar substituições parciais
                import re
                pattern = r'\b' + re.escape(sinonimo) + r'\b'
                text_expanded = re.sub(pattern, palavra_chave, text_expanded)
        
        return text_expanded
    
    def text_to_sql_regex(self, command):
        """Converte texto natural em query SQL usando regex (sistema original)"""
        # Expandir sinônimos primeiro
        command = self.expand_synonyms(command)
        print(f"📝 Texto expandido: {command}")
        
        command = command.lower().strip()
        print(f"Convertendo comando para SQL com regex: {command}")
        
        # Padrões de conversão baseados em regras inteligentes expandidas (ordem específica -> geral)
        sql_patterns = [
            # === PADRÕES MAIS ESPECÍFICOS PRIMEIRO ===
            
            # === SISTEMA DE FILTROS AVANÇADOS (MELHORIA 4) ===
            # Múltiplos critérios com operadores E/OU
            (r'(?:carregador|posto|estação).*?(?:barato|económico).*?(?:e|and|\+).*?(?:rápido|potente).*?(?:e|and|\+).*?(?:disponível|livre).*?(?:em|no|na)\s+(\w+)',
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' AND price <= (SELECT AVG(price) FROM charging_stations) AND power >= (SELECT AVG(power) FROM charging_stations) AND available = true ORDER BY price ASC, power DESC"),
            
            # Filtros com comparações numéricas
            (r'(?:carregador|posto|estação).*?(?:menos|menor|até)\s+(\d+)\s*(?:euros?|€).*?(?:mais|maior|acima)\s+(\d+)\s*(?:kw|kilowatt).*?(?:em|no|na)\s+(\w+)',
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(3).lower()}%' AND price <= {m.group(1)} AND power >= {m.group(2)} ORDER BY price ASC, power DESC"),
            
            # Filtros OU (alternativas)
            (r'(?:carregador|posto|estação).*?(?:barato|económico).*?(?:ou|or).*?(?:rápido|potente).*?(?:em|no|na)\s+(\w+)',
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' AND (price <= (SELECT AVG(price) FROM charging_stations) OR power >= (SELECT AVG(power) FROM charging_stations)) ORDER BY price ASC, power DESC"),
            
            # Padrões de necessidade/urgência com contexto específico
            (r'(?:preciso|necessito|quero|gostaria|desejo|procuro)\s+(?:de\s+)?(?:carregar|carregamento|abastecer|recarregar).*?(?:carro|veículo|automóvel|viatura|elétrico|EV).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            (r'(?:preciso|necessito|quero|gostaria|desejo|procuro).*?(?:carregar|carregamento|abastecer|recarregar).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Padrões com múltiplos critérios (preço + velocidade + localização)
            (r'(?:carregador|posto|estação).*?(?:barato|económico|econômico).*?(?:e|and|\+).*?(?:rápido|potente|veloz).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' AND price <= (SELECT AVG(price) FROM charging_stations) AND power >= (SELECT AVG(power) FROM charging_stations) ORDER BY price ASC, power DESC"),
            
            (r'(?:carregador|posto|estação).*?(?:rápido|potente|veloz).*?(?:e|and|\+).*?(?:barato|económico|econômico).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' AND price <= (SELECT AVG(price) FROM charging_stations) AND power >= (SELECT AVG(power) FROM charging_stations) ORDER BY power DESC, price ASC"),
            
            # Padrões de disponibilidade em tempo real
            (r'(?:carregador|posto|estação).*?(?:disponível|livre|aberto|funcional|operacional|ativo).*?(?:agora|neste momento|atualmente).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' AND available = true ORDER BY price ASC"),
            
            (r'(?:há|existe|tem).*?(?:carregador|posto|estação).*?(?:disponível|livre|aberto|funcional|operacional|ativo).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' AND available = true ORDER BY price ASC"),
            
            # Padrões de tipos de conectores específicos da mobiE
            (r'(?:carregador|posto|estação).*?(?:type 2|tipo 2|mennekes|chademo|ccs|combo).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Padrões de potência específica com unidades
            (r'(?:carregador|posto|estação).*?(\d+)\s*(?:kw|kilowatt|quilowatt).*?(?:ou mais|no mínimo|pelo menos).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE power >= {m.group(1)} AND LOWER(location) LIKE '%{m.group(2).lower()}%' ORDER BY price ASC"),
            
            # Padrões de redes específicas portuguesas
            (r'(?:carregador|posto|estação).*?(?:mobie|mobiE|rede mobie|galp|galp electric|edp|edp comercial|tesla|supercharger).*?(?:em|no|na|para|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Padrões de destino e viagem
            (r'.*?(?:destino|ir|viajar|viagem|caminho).*?(?:em|para|até|do|da)\s+(\w+)', 
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            (r'(?:no caminho|na rota|entre).*?(?:para|até)\s+(\w+)', 
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Perguntas com "há", "existe", "tem" - versão expandida
            (r'(?:há|existe|tem|encontro).*?(?:carregador|posto|estação|ponto|terminal|tomada).*?(?:perto|próximo|junto|ao lado|nas redondezas).*?(?:de|a|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            (r'(?:há|existe|tem|encontro).*?(?:carregador|posto|estação|ponto|terminal|tomada).*?(?:em|no|na|do|da)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Padrões de contexto geográfico expandido
            (r'(?:carregador|posto|estação).*?(?:norte|centro|sul).*?(?:de\s+)?portugal', 
             lambda m: "SELECT * FROM charging_stations WHERE LOWER(location) IN ('porto', 'braga', 'aveiro', 'coimbra', 'viseu', 'leiria') ORDER BY price ASC"),
            
            (r'(?:carregador|posto|estação).*?(?:região|zona|área).*?(?:de\s+)?(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Padrões de urgência temporal
             (r'(?:preciso|necessito).*?(?:urgente|rápido|já|agora|imediatamente).*?(?:carregador|posto|estação).*?(?:em|no|na|para|do|da)\s+(\w+)', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' AND available = true ORDER BY power DESC, price ASC LIMIT 3"),
             
             # === PADRÕES DE CONTEXTO GEOGRÁFICO ===
             
             # Padrões de contexto geográfico por região
             (r'(?:carregador|posto|estação).*?(?:no|na|do|da)\s+norte\s+(?:de\s+)?portugal', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%porto%' OR LOWER(location) LIKE '%braga%' OR LOWER(location) LIKE '%viana%' OR LOWER(location) LIKE '%vila real%' ORDER BY price ASC"),
             
             (r'(?:carregador|posto|estação).*?(?:no|na|do|da)\s+centro\s+(?:de\s+)?portugal', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%coimbra%' OR LOWER(location) LIKE '%aveiro%' OR LOWER(location) LIKE '%viseu%' OR LOWER(location) LIKE '%leiria%' ORDER BY price ASC"),
             
             (r'(?:carregador|posto|estação).*?(?:no|na|do|da)\s+sul\s+(?:de\s+)?portugal', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%lisboa%' OR LOWER(location) LIKE '%setúbal%' OR LOWER(location) LIKE '%évora%' ORDER BY price ASC"),
             
             (r'(?:carregador|posto|estação).*?(?:no|na|do|da)\s+algarve', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%faro%' OR LOWER(location) LIKE '%portimão%' OR LOWER(location) LIKE '%lagos%' ORDER BY price ASC"),
             
             (r'(?:carregador|posto|estação).*?(?:no|na|do|da)\s+alentejo', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%évora%' OR LOWER(location) LIKE '%beja%' ORDER BY price ASC"),
             
             # Padrões de proximidade avançada
             (r'(?:carregador|posto|estação).*?(?:perto|próximo|nas\s+redondezas|nas\s+proximidades).*?(?:de|a)\s+(\w+)', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
             
             (r'(?:há|existe|tem).*?(?:carregador|posto|estação).*?(?:perto|próximo|nas\s+redondezas).*?(?:de|a)\s+(\w+)', 
              lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
             
             # Padrões de rotas entre cidades
             (r'(?:carregador|posto|estação).*?(?:no\s+caminho|na\s+rota|entre).*?(\w+)\s+(?:e|para|até)\s+(\w+)', 
              lambda m: f"SELECT * FROM charging_stations WHERE (LOWER(location) LIKE '%{m.group(1).lower()}%' OR LOWER(location) LIKE '%{m.group(2).lower()}%') ORDER BY price ASC"),
             
             (r'(?:onde|aonde).*?(?:carregar|carregamento).*?(?:no\s+caminho|na\s+rota|entre).*?(\w+)\s+(?:e|para|até)\s+(\w+)', 
              lambda m: f"SELECT * FROM charging_stations WHERE (LOWER(location) LIKE '%{m.group(1).lower()}%' OR LOWER(location) LIKE '%{m.group(2).lower()}%') ORDER BY price ASC"),
             
             (r'(?:viagem|ida|deslocação).*?(?:de|desde)\s+(\w+)\s+(?:para|até|a)\s+(\w+)', 
              lambda m: f"SELECT * FROM charging_stations WHERE (LOWER(location) LIKE '%{m.group(1).lower()}%' OR LOWER(location) LIKE '%{m.group(2).lower()}%') ORDER BY price ASC"),
             
             # Padrões de distância específica
              (r'(?:carregador|posto|estação).*?(?:a|até)\s+(\d+)\s*(?:km|quilómetros|quilometros).*?(?:de|desde)\s+(\w+)', 
               lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(2).lower()}%' ORDER BY price ASC")
        ]
        
        # === PADRÕES INTERMEDIÁRIOS ===
        sql_patterns.extend([
            # Busca por "melhor carregador do/da cidade"
            (r'(?:melhor|bom).*?(?:carregador|posto).*?(?:do|da|em|no|na)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC LIMIT 1"),
            
            # Proximidade: "perto de", "próximo a" (mais específico)
            (r'(?:carregador|posto|estação|ponto).*?(?:perto|próximo).*?(?:de|a)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Proximidade geral
            (r'(?:perto|próximo).*?(?:de|a)\s+(\w+)', 
             lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Busca por preço com cidade específica
            (r'(?:mais\s+)?(?:barato|económico|menor\s+preço).*?(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC LIMIT 1"),
            
            # Busca por potência com cidade específica
            (r'(?:mais\s+)?(?:rápido|potente|alta\s+potência).*?(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY power DESC LIMIT 1"),
            
            # Busca por cidade específica com carregador
            (r'(?:carregador|posto|carregamento).*?(?:em|no|na|de|para|do|da)\s+(\w+)', 
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Busca por "onde carregar em cidade"
            (r'(?:onde|aonde).*?(?:carregar|carregamento).*?(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Busca por "em cidade" ou "do/da cidade" (mais geral)
            (r'(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Busca por preço (sem cidade específica)
            (r'(?:mais\s+)?(?:barato|económico|menor\s+preço)(?!.*(?:em|no|na|de|para|do|da))',
                lambda m: "SELECT * FROM charging_stations ORDER BY price ASC LIMIT 1"),
            
            # Busca por potência (sem cidade específica)
            (r'(?:mais\s+)?(?:rápido|potente|alta\s+potência)(?!.*(?:em|no|na|de|para|do|da))',
                lambda m: "SELECT * FROM charging_stations ORDER BY power DESC LIMIT 1"),
            
            # Busca por potência específica com cidade
            (r'(?:carregador|posto).*?(\d+)\s*kw.*?(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE power >= {m.group(1)} AND LOWER(location) LIKE '%{m.group(2).lower()}%' ORDER BY price ASC"),
            
            # Busca por potência específica (sem cidade)
            (r'(?:carregador|posto).*?(\d+)\s*kw',
                lambda m: f"SELECT * FROM charging_stations WHERE power >= {m.group(1)} ORDER BY price ASC"),
            
            # Busca por universidade/campus com cidade
            (r'(?:universidade|campus|faculdade).*?(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(address) LIKE '%universidade%' AND LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Busca por universidade/campus (sem cidade)
            (r'(?:universidade|campus|faculdade)',
                lambda m: "SELECT * FROM charging_stations WHERE LOWER(address) LIKE '%universidade%' ORDER BY price ASC"),
            
            # Busca por shopping/centro comercial com cidade
            (r'(?:shopping|centro\s+comercial|mall).*?(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE (LOWER(address) LIKE '%shopping%' OR LOWER(address) LIKE '%forum%' OR LOWER(address) LIKE '%centro%') AND LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Busca por shopping/centro comercial (sem cidade)
            (r'(?:shopping|centro\s+comercial|mall)',
                lambda m: "SELECT * FROM charging_stations WHERE (LOWER(address) LIKE '%shopping%' OR LOWER(address) LIKE '%forum%' OR LOWER(address) LIKE '%centro%') ORDER BY price ASC"),
            
            # Busca por aeroporto com cidade
            (r'(?:aeroporto|airport).*?(?:em|no|na|de|para|do|da)\s+(\w+)',
                lambda m: f"SELECT * FROM charging_stations WHERE LOWER(address) LIKE '%aeroporto%' AND LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC"),
            
            # Busca por aeroporto (sem cidade)
            (r'(?:aeroporto|airport)',
                lambda m: "SELECT * FROM charging_stations WHERE LOWER(address) LIKE '%aeroporto%' ORDER BY price ASC"),
            
            # Busca genérica por cidade (apenas uma palavra)
            (r'^(\w+)$',
                 lambda m: f"SELECT * FROM charging_stations WHERE LOWER(location) LIKE '%{m.group(1).lower()}%' ORDER BY price ASC")
        ])
        
        # Tentar encontrar padrão correspondente (ordem específica -> geral)
        for pattern, sql_generator in sql_patterns:
            match = re.search(pattern, command)
            if match:
                try:
                    sql_query = sql_generator(match)
                    print(f"✅ Padrão encontrado: {pattern[:50]}...")
                    print(f"🔍 SQL gerado: {sql_query}")
                    return sql_query
                except Exception as e:
                    print(f"❌ Erro ao gerar SQL: {e}")
                    continue
        
        # Fallback: busca genérica
        print("Usando busca genérica")
        return "SELECT * FROM charging_stations ORDER BY price ASC LIMIT 5"
    
    def text_to_sql(self, command):
        """Função principal que decide qual sistema usar (regex prioritário, ChatGPT como fallback) com cache, correção e analytics"""
        start_time = time.time()
        cache_hit = False
        corrections_made = 0
        
        try:
            # Aplicar correção automática primeiro
            corrected_command = self.text_corrector.correct_text(command)
            if corrected_command != command:
                corrections_made = 1
            
            # Verificar cache com comando corrigido
            cached_result = self.query_cache.get(corrected_command)
            if cached_result:
                cache_hit = True
                response_time = time.time() - start_time
                self.analytics.record_query(corrected_command, response_time, True, cache_hit, corrections_made)
                return cached_result
            
            print("🚀 Usando sistema de regex (mais confiável)")
            
            # Primeiro tentar com regex usando comando corrigido
            sql_query = self.text_to_sql_regex(corrected_command)
            
            # Se modo apenas regex, retornar sempre o resultado do regex
            if self.use_regex_only:
                print("✅ Modo apenas regex - retornando resultado")
                # Armazenar no cache
                self.query_cache.set(corrected_command, sql_query)
                response_time = time.time() - start_time
                self.analytics.record_query(corrected_command, response_time, True, cache_hit, corrections_made)
                return sql_query
            
            # Verificar se o regex gerou uma query específica (não genérica)
            if sql_query and "ORDER BY price ASC LIMIT 5" not in sql_query:
                print("✅ Query específica gerada pelo sistema de regex")
                # Armazenar no cache
                self.query_cache.set(corrected_command, sql_query)
                response_time = time.time() - start_time
                self.analytics.record_query(corrected_command, response_time, True, cache_hit, corrections_made)
                return sql_query
            
            # Se regex não foi específico, tentar ChatGPT como fallback
            print("🔄 Regex não foi específico, tentando ChatGPT como fallback")
            chatgpt_result = self.text_to_sql_with_chatgpt(corrected_command)
            # Armazenar resultado do ChatGPT no cache
            self.query_cache.set(corrected_command, chatgpt_result)
            response_time = time.time() - start_time
            self.analytics.record_query(corrected_command, response_time, True, cache_hit, corrections_made)
            return chatgpt_result
            
        except Exception as e:
            response_time = time.time() - start_time
            self.analytics.record_query(command, response_time, False, cache_hit, corrections_made)
            raise e
    
    def execute_sql_query(self, sql_query):
        """Executa query SQL e retorna resultados"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql_query)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'id': row[0],
                        'location': row[1],
                        'address': row[2],
                        'price': row[3],
                        'power': row[4],
                        'available': bool(row[5])
                    })
                
                print(f"Encontrados {len(results)} carregadores")
                return results
                
        except Exception as e:
            print(f"Erro ao executar SQL: {e}")
            return []
    
    def extract_location(self, command):
        """Método mantido para compatibilidade - agora usa AI para SQL"""
        # Este método agora é um wrapper que usa o novo sistema AI
        sql_query = self.text_to_sql(command)
        results = self.execute_sql_query(sql_query)
        
        if results:
            # Retornar a localização do primeiro resultado
            return results[0]['location'].lower()
        
        print("Nenhuma localização encontrada no comando")
        return None

    def find_best_charger(self, command):
        """Encontra o melhor carregador usando AI para interpretar o comando"""
        print(f"Processando comando com AI: {command}")
        
        # Usar AI para converter texto em SQL
        sql_query = self.text_to_sql(command)
        results = self.execute_sql_query(sql_query)
        
        if results:
            # Retornar o primeiro resultado (já ordenado pela query SQL)
            best_charger = results[0]
            print(f"Melhor carregador encontrado: {best_charger['id']} em {best_charger['location']}")
            return best_charger
        
        print("Nenhum carregador encontrado")
        return None

    def speak_response(self, text, with_confirmation=False, suggestions=None):
        """Interface de voz melhorada com confirmações e sugestões proativas (MELHORIA 5)"""
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
            
        # Adicionar confirmação se solicitada
        if with_confirmation:
            text += ". Está correto?"
            
        # Adicionar sugestões proativas
        if suggestions:
            if len(suggestions) == 1:
                text += f". Posso também sugerir: {suggestions[0]}"
            elif len(suggestions) > 1:
                text += f". Outras opções incluem: {', '.join(suggestions[:2])}"
        
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
                
                if not command.strip():
                    error_msg = "Por favor, diga um comando válido"
                    self.speak_response(error_msg)
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    })
                
                # Usar AI para processar o comando completo
                best_charger = self.find_best_charger(command)
                
                if best_charger:
                    # Gerar resposta inteligente baseada no tipo de busca
                    if 'barato' in command.lower() or 'económico' in command.lower():
                        response_text = (f"O carregador mais barato encontrado está em {best_charger['location']}, "
                                       f"localizado em {best_charger['address']}, "
                                       f"com um preço de {best_charger['price']} euros por kWh")
                    elif 'rápido' in command.lower() or 'potente' in command.lower():
                        response_text = (f"O carregador mais rápido encontrado está em {best_charger['location']}, "
                                       f"localizado em {best_charger['address']}, "
                                       f"com {best_charger['power']} kW de potência e preço de {best_charger['price']} euros por kWh")
                    elif 'universidade' in command.lower() or 'campus' in command.lower():
                        response_text = (f"Encontrei um carregador na universidade em {best_charger['location']}, "
                                       f"localizado em {best_charger['address']}, "
                                       f"com preço de {best_charger['price']} euros por kWh")
                    elif 'shopping' in command.lower() or 'centro comercial' in command.lower():
                        response_text = (f"Encontrei um carregador no shopping em {best_charger['location']}, "
                                       f"localizado em {best_charger['address']}, "
                                       f"com preço de {best_charger['price']} euros por kWh")
                    elif 'aeroporto' in command.lower():
                        response_text = (f"Encontrei um carregador no aeroporto em {best_charger['location']}, "
                                       f"localizado em {best_charger['address']}, "
                                       f"com preço de {best_charger['price']} euros por kWh")
                    else:
                        response_text = (f"O melhor carregador encontrado está em {best_charger['location']}, "
                                       f"localizado em {best_charger['address']}, "
                                       f"com um preço de {best_charger['price']} euros por kWh")
                    
                    # Falar a resposta
                    self.speak_response(response_text)
                    
                    return jsonify({
                        'success': True,
                        'charger': best_charger,
                        'message': response_text
                    })
                else:
                    error_msg = "Desculpe, não encontrei nenhum carregador que corresponda ao seu pedido"
                    self.speak_response(error_msg)
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    })
                    
            except Exception as e:
                error_msg = f"Erro ao processar comando: {str(e)}"
                return jsonify({
                    'success': False,
                    'error': error_msg
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
        elif mode == 'text':
            self.run_text()
        else:
            self.run_console()
    
    def run_web(self):
        """Executar interface web Flask"""
        print("🌐 Iniciando interface web...")
        print("📱 Acesse: http://localhost:8002")
        print("🛑 Para parar: Ctrl+C ou use o botão 'Sair' na interface")
        
        try:
            self.app.run(host='0.0.0.0', port=8002, debug=False)
        except KeyboardInterrupt:
            print("\n🛑 Servidor parado pelo usuário")
        except Exception as e:
            print(f"❌ Erro no servidor: {e}")
    
    def run_console(self):
        """Executar em modo linha de comando (original com voz)"""
        while True:
            print("Diga o seu comando...")  # "Say your command..." in Portuguese
            command = self.listen_for_command()
            
            if command:
                best_charger = self.find_best_charger(command)
                
                if best_charger:
                    # Gerar resposta inteligente baseada no tipo de busca
                    if 'barato' in command.lower() or 'económico' in command.lower():
                        response = (f"O carregador mais barato encontrado está em {best_charger['location']}, "
                                  f"localizado em {best_charger['address']}, "
                                  f"com um preço de {best_charger['price']} euros por kWh")
                    elif 'rápido' in command.lower() or 'potente' in command.lower():
                        response = (f"O carregador mais rápido encontrado está em {best_charger['location']}, "
                                  f"localizado em {best_charger['address']}, "
                                  f"com {best_charger['power']} kW de potência e preço de {best_charger['price']} euros por kWh")
                    else:
                        response = (f"O melhor carregador encontrado está em {best_charger['location']}, "
                                  f"localizado em {best_charger['address']}, "
                                  f"com um preço de {best_charger['price']} euros por kWh")
                else:
                    response = "Desculpe, não encontrei nenhum carregador que corresponda ao seu pedido"
                
                self.speak_response(response)
            
            print("\nPressione Enter para pesquisar novamente ou 'q' para sair")
            if input().lower() == 'q':
                break
    
    def run_text(self):
        """Executar em modo texto (com voz na saída)"""
        print("\n🖊️  Modo Texto Ativado - Digite seus comandos! (com voz na saída)")
        print("💡 Exemplos: 'melhor carregador em Lisboa', 'carregador mais barato no Porto', 'carregadores em Coimbra'")
        print("🚪 Digite 'sair' ou 'q' para terminar\n")
        
        while True:
            try:
                command = input("➤ Digite seu comando: ").strip()
                
                if not command:
                    continue
                    
                if command.lower() in ['sair', 'q', 'quit', 'exit']:
                    print("👋 Até logo!")
                    break
                
                print(f"🔍 Processando: '{command}'...")
                best_charger = self.find_best_charger(command)
                
                if best_charger:
                    # Gerar resposta inteligente baseada no tipo de busca
                    if 'barato' in command.lower() or 'económico' in command.lower():
                        response = (f"💰 O carregador mais barato encontrado está em {best_charger['location']}, "
                                  f"localizado em {best_charger['address']}, "
                                  f"com um preço de {best_charger['price']} euros por kWh")
                    elif 'rápido' in command.lower() or 'potente' in command.lower():
                        response = (f"⚡ O carregador mais rápido encontrado está em {best_charger['location']}, "
                                  f"localizado em {best_charger['address']}, "
                                  f"com {best_charger['power']} kW de potência e preço de {best_charger['price']} euros por kWh")
                    else:
                        response = (f"🎯 O melhor carregador encontrado está em {best_charger['location']}, "
                                  f"localizado em {best_charger['address']}, "
                                  f"com um preço de {best_charger['price']} euros por kWh")
                else:
                    response = "❌ Desculpe, não encontrei nenhum carregador que corresponda ao seu pedido"
                
                print(f"\n✅ {response}\n")
                
                # Adicionar saída de voz
                self.speak_response(response)
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrompido pelo utilizador. Até logo!")
                break
            except Exception as e:
                print(f"\n❌ Erro: {e}\n")

if __name__ == "__main__":
    import sys
    
    # Verificar se deve usar apenas regex
    use_regex_only = '--regex-only' in sys.argv
    if use_regex_only:
        sys.argv.remove('--regex-only')
    
    finder = EVChargingFinder(use_regex_only=use_regex_only)
    
    # Verificar argumentos de linha de comando
    if len(sys.argv) > 1:
        if sys.argv[1] == '--console':
            print("🎤 Iniciando modo linha de comando (com voz)...")
            finder.run(mode='console')
        elif sys.argv[1] == '--text':
            print("🖊️  Iniciando modo texto (com voz na saída)...")
            finder.run(mode='text')
        elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("\n🚀 ZEUS - Sistema de Busca de Carregadores EV")
            print("\n📋 Modos disponíveis:")
            print("   python ZEUS.py              → Interface web (com voz na saída)")
            print("   python ZEUS.py --console    → Modo voz (microfone + fala)")
            print("   python ZEUS.py --text       → Modo texto (digitação + voz na saída)")
            print("   python ZEUS.py --regex-only → Usar apenas sistema de regex (mais rápido)")
            print("   python ZEUS.py --help       → Mostrar esta ajuda")
            print("\n💡 Exemplos de comandos:")
            print("   • 'melhor carregador em Lisboa'")
            print("   • 'carregador mais barato no Porto'")
            print("   • 'carregadores em Coimbra'")
            print("   • 'carregador mais rápido'\n")
            print("\n⚡ Dica: Use --regex-only para um sistema mais rápido e confiável")
        else:
            print(f"❌ Opção desconhecida: {sys.argv[1]}")
            print("💡 Use 'python ZEUS.py --help' para ver as opções disponíveis")
    else:
        print("🌐 Iniciando modo interface web...")
        print("💡 Outros modos: --console (voz completa) | --text (digitação + voz) | --help | --regex-only")
        finder.run(mode='web')