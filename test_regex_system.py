#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste para demonstrar o sistema de regex melhorado com sinônimos
"""

import time
from ZEUS import EVChargingFinder

def test_commands():
    """Comandos de teste em português com variações linguísticas"""
    return [
        # Testes básicos
        "melhor carregador em Leiria",
        "carregador mais barato no Porto", 
        "carregadores rápidos em Lisboa",
        
        # Testes com sinônimos
        "melhor posto em Aveiro",  # posto = carregador
        "estação económica em Coimbra",  # estação = carregador, económica = barata
        "terminal potente em Braga",  # terminal = carregador, potente = rápido
        
        # Frases mais naturais
        "preciso carregar o carro em Leiria",
        "quero um carregador em Faro",
        "há carregadores em Viseu?",
        "existe algum posto perto de Évora",
        
        # Testes de proximidade
        "carregador próximo a Setúbal",
        "ponto de carregamento perto de Beja",
        
        # Teste de destino
        "onde posso carregar no meu destino em Leiria",
        
        # Teste simples
        "Leiria"
    ]

def test_regex_system():
    """Testa o sistema apenas com regex melhorado"""
    print("🧪 Testando Sistema de Regex Melhorado com Sinônimos")
    print("=" * 60)
    
    finder = EVChargingFinder(use_regex_only=True)
    
    commands = test_commands()
    results = []
    total_time = 0
    
    for i, command in enumerate(commands, 1):
        print(f"\n[{i}/{len(commands)}] Testando: '{command}'")
        
        start_time = time.time()
        best_charger = finder.find_best_charger(command)
        end_time = time.time()
        
        processing_time = end_time - start_time
        total_time += processing_time
        
        print(f"⏱️  Tempo: {processing_time:.3f}s")
        
        if best_charger:
            print(f"✅ Encontrado: {best_charger['location']} - {best_charger['address']}")
            print(f"💰 Preço: {best_charger['price']}€/kWh | ⚡ Potência: {best_charger['power']}kW")
            results.append({
                'command': command,
                'time': processing_time,
                'found': True,
                'location': best_charger['location']
            })
        else:
            print("❌ Nenhum carregador encontrado")
            results.append({
                'command': command,
                'time': processing_time,
                'found': False,
                'location': None
            })
    
    # Estatísticas finais
    avg_time = total_time / len(commands)
    success_rate = (sum(1 for r in results if r['found']) / len(results)) * 100
    
    print("\n" + "=" * 60)
    print("📊 ESTATÍSTICAS FINAIS")
    print("=" * 60)
    print(f"⏱️  Tempo total: {total_time:.3f}s")
    print(f"⏱️  Tempo médio: {avg_time:.3f}s")
    print(f"✅ Taxa de sucesso: {success_rate:.1f}%")
    print(f"🔍 Comandos processados: {len(results)}")
    
    # Análise por categoria
    categorias = {
        'Básicos': commands[:3],
        'Sinônimos': commands[3:6],
        'Linguagem Natural': commands[6:10],
        'Proximidade': commands[10:12],
        'Outros': commands[12:]
    }
    
    print("\n📈 ANÁLISE POR CATEGORIA:")
    for categoria, cmds in categorias.items():
        categoria_results = [r for r in results if r['command'] in cmds]
        if categoria_results:
            success = sum(1 for r in categoria_results if r['found'])
            total = len(categoria_results)
            rate = (success / total) * 100 if total > 0 else 0
            print(f"   {categoria}: {success}/{total} ({rate:.1f}%)")
    
    # Verificar se Leiria foi detectada corretamente
    leiria_tests = [r for r in results if 'leiria' in r['command'].lower()]
    if leiria_tests:
        print(f"\n🎯 Testes específicos para Leiria: {len(leiria_tests)}")
        for test in leiria_tests:
            if test['found'] and test['location'] and 'leiria' in test['location'].lower():
                print(f"   ✅ '{test['command']}' → {test['location']} (correto)")
            else:
                print(f"   ❌ '{test['command']}' → {test['location']} (incorreto)")
    
    print("\n🏆 CONCLUSÃO:")
    if avg_time < 0.1 and success_rate >= 90:
        print("   🌟 Sistema de regex está funcionando EXCEPCIONALMENTE!")
        print("   🚀 Rápido, confiável, preciso e com linguagem natural")
    elif avg_time < 0.1 and success_rate >= 80:
        print("   ✅ Sistema de regex está funcionando EXCELENTEMENTE!")
        print("   🚀 Rápido, confiável e preciso")
    elif success_rate >= 70:
        print("   ✅ Sistema de regex está funcionando BEM")
        print("   💡 Boa performance geral")
    else:
        print("   ⚠️  Sistema precisa de ajustes")
        print("   🔧 Considere melhorar os padrões de regex")
    
    # Recomendações
    if success_rate < 100:
        failed_commands = [r['command'] for r in results if not r['found']]
        if failed_commands:
            print("\n🔧 COMANDOS QUE FALHARAM (para melhoria):")
            for cmd in failed_commands:
                print(f"   • '{cmd}'")

if __name__ == "__main__":
    test_regex_system()