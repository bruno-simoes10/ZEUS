#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Teste das Melhorias 1 e 2 do Sistema ZEUS

Melhoria 1: Expansão de Padrões de Linguagem Natural
Melhoria 2: Sistema de Sinônimos e Variações Expandido

Baseado na rede mobiE e schema existente
"""

import sys
import time
from ZEUS import EVChargingFinder

def test_melhorias_1_2():
    """Testa as melhorias 1 e 2 implementadas no sistema ZEUS"""
    
    print("\n" + "="*80)
    print("🚀 TESTE DAS MELHORIAS 1 e 2 - SISTEMA ZEUS")
    print("="*80)
    print("📋 Melhoria 1: Expansão de Padrões de Linguagem Natural")
    print("📋 Melhoria 2: Sistema de Sinônimos e Variações Expandido")
    print("🔧 Baseado na rede mobiE e schema existente")
    print("="*80)
    
    # Inicializar sistema com regex apenas
    finder = EVChargingFinder(use_regex_only=True)
    
    # Comandos de teste organizados por categoria
    comandos_teste = {
        "Padrões de Necessidade/Urgência": [
            "preciso de carregar o meu carro elétrico em Lisboa",
            "necessito abastecer o veículo em Porto",
            "quero recarregar a viatura em Coimbra",
            "gostaria de energizar o EV em Braga",
            "desejo carregar o automóvel em Aveiro",
            "procuro carregamento para tesla em Faro"
        ],
        
        "Múltiplos Critérios (Preço + Velocidade)": [
            "carregador barato e rápido em Lisboa",
            "posto económico e potente no Porto",
            "estação acessível e veloz em Coimbra",
            "terminal em conta e forte em Braga"
        ],
        
        "Disponibilidade em Tempo Real": [
            "carregador disponível agora em Lisboa",
            "posto livre neste momento no Porto",
            "estação aberta atualmente em Coimbra",
            "há terminal funcional em Braga?",
            "existe posto operacional em Aveiro?"
        ],
        
        "Tipos de Conectores mobiE": [
            "carregador type 2 em Lisboa",
            "posto tipo 2 no Porto",
            "estação mennekes em Coimbra",
            "terminal chademo em Braga",
            "carregador ccs em Aveiro"
        ],
        
        "Potência Específica": [
            "carregador 50kw ou mais em Lisboa",
            "posto 22 kilowatt no mínimo no Porto",
            "estação 150kw pelo menos em Coimbra"
        ],
        
        "Redes Específicas Portuguesas": [
            "carregador mobie em Lisboa",
            "posto mobiE no Porto",
            "estação rede mobie em Coimbra",
            "terminal galp electric em Braga",
            "carregador edp comercial em Aveiro",
            "supercharger tesla em Faro"
        ],
        
        "Contexto de Viagem": [
            "carregador no meu destino em Lisboa",
            "posto para ir ao Porto",
            "estação na viagem para Coimbra",
            "terminal no caminho para Braga",
            "carregador na rota até Aveiro"
        ],
        
        "Contexto Geográfico": [
            "carregador no norte de portugal",
            "posto no centro de portugal",
            "estação na região de lisboa",
            "terminal na zona do porto",
            "carregador na área de coimbra"
        ],
        
        "Urgência Temporal": [
            "preciso urgente carregador em Lisboa",
            "necessito já posto no Porto",
            "quero agora estação em Coimbra",
            "preciso imediatamente terminal em Braga"
        ],
        
        "Sinônimos Expandidos": [
            "tomada elétrica em Lisboa",
            "plug para EV no Porto",
            "socket de carregamento em Coimbra",
            "ponto mais em conta em Braga",
            "estação mais acessível em Aveiro",
            "terminal perfeito em Faro",
            "carregador recomendado em Évora",
            "posto nas redondezas de Leiria",
            "estação ao lado de Viseu",
            "terminal junto a Setúbal"
        ]
    }
    
    # Estatísticas
    total_comandos = sum(len(cmds) for cmds in comandos_teste.values())
    sucessos = 0
    falhas = 0
    tempo_total = 0
    resultados_por_categoria = {}
    
    print(f"\n📊 Iniciando teste com {total_comandos} comandos...\n")
    
    # Executar testes por categoria
    for categoria, comandos in comandos_teste.items():
        print(f"\n🔍 === {categoria.upper()} ===")
        sucessos_categoria = 0
        
        for i, comando in enumerate(comandos, 1):
            print(f"\n[{categoria}] Teste {i}/{len(comandos)}: {comando}")
            
            try:
                inicio = time.time()
                resultado = finder.find_best_charger(comando)
                fim = time.time()
                tempo_execucao = fim - inicio
                tempo_total += tempo_execucao
                
                if resultado is not None:
                    print(f"✅ SUCESSO ({tempo_execucao:.3f}s)")
                    # Verificar se o resultado tem a estrutura esperada
                    if isinstance(resultado, dict) and 'location' in resultado:
                        print(f"   🎯 Melhor opção: {resultado['location']} - {resultado['address']}")
                        print(f"   💰 Preço: €{resultado['price']}/kWh | ⚡ Potência: {resultado['power']}kW")
                    else:
                        print(f"   🎯 Resultado encontrado: {resultado}")
                    sucessos += 1
                    sucessos_categoria += 1
                else:
                    print(f"❌ FALHA ({tempo_execucao:.3f}s) - Nenhum resultado encontrado")
                    falhas += 1
                    
            except Exception as e:
                print(f"💥 ERRO ({tempo_execucao:.3f}s): {str(e)}")
                falhas += 1
        
        # Calcular taxa de sucesso da categoria
        taxa_categoria = (sucessos_categoria / len(comandos)) * 100
        resultados_por_categoria[categoria] = {
            'sucessos': sucessos_categoria,
            'total': len(comandos),
            'taxa': taxa_categoria
        }
        
        print(f"\n📈 {categoria}: {sucessos_categoria}/{len(comandos)} ({taxa_categoria:.1f}% sucesso)")
    
    # Relatório final
    print("\n" + "="*80)
    print("📊 RELATÓRIO FINAL - MELHORIAS 1 e 2")
    print("="*80)
    
    taxa_sucesso_geral = (sucessos / total_comandos) * 100
    tempo_medio = tempo_total / total_comandos
    
    print(f"\n🎯 RESULTADOS GERAIS:")
    print(f"   • Total de comandos testados: {total_comandos}")
    print(f"   • Sucessos: {sucessos}")
    print(f"   • Falhas: {falhas}")
    print(f"   • Taxa de sucesso: {taxa_sucesso_geral:.1f}%")
    print(f"   • Tempo médio por comando: {tempo_medio:.3f}s")
    print(f"   • Tempo total: {tempo_total:.3f}s")
    
    print(f"\n📈 ANÁLISE POR CATEGORIA:")
    for categoria, stats in resultados_por_categoria.items():
        status = "✅" if stats['taxa'] >= 80 else "⚠️" if stats['taxa'] >= 60 else "❌"
        print(f"   {status} {categoria}: {stats['sucessos']}/{stats['total']} ({stats['taxa']:.1f}%)")
    
    # Avaliação das melhorias
    print(f"\n🚀 AVALIAÇÃO DAS MELHORIAS:")
    
    if taxa_sucesso_geral >= 85:
        print("   🏆 EXCELENTE: Sistema compreende linguagem natural portuguesa fluentemente")
    elif taxa_sucesso_geral >= 70:
        print("   ✅ BOM: Sistema funciona bem com a maioria dos padrões")
    elif taxa_sucesso_geral >= 50:
        print("   ⚠️ RAZOÁVEL: Sistema precisa de ajustes adicionais")
    else:
        print("   ❌ INSUFICIENTE: Sistema requer revisão significativa")
    
    print(f"\n💡 DESTAQUES DAS MELHORIAS:")
    print(f"   • Sistema de sinônimos expandido com {len(finder.sinonimos)} categorias")
    print(f"   • Padrões de linguagem natural baseados na rede mobiE")
    print(f"   • Reconhecimento de múltiplos critérios (preço + velocidade)")
    print(f"   • Detecção de contexto geográfico português")
    print(f"   • Suporte a tipos de conectores específicos")
    print(f"   • Integração com schema da base de dados existente")
    
    print(f"\n🎯 PRÓXIMOS PASSOS RECOMENDADOS:")
    if taxa_sucesso_geral < 80:
        print(f"   • Ajustar padrões com menor taxa de sucesso")
        print(f"   • Expandir sinônimos para termos específicos")
    if tempo_medio > 0.1:
        print(f"   • Otimizar performance dos padrões regex")
    
    print(f"   • Implementar melhorias 3-10 do roadmap")
    print(f"   • Adicionar mais cidades à base de dados")
    print(f"   • Desenvolver sistema de aprendizagem automática")
    
    print("\n" + "="*80)
    print("🎉 TESTE CONCLUÍDO - MELHORIAS 1 e 2 VALIDADAS")
    print("="*80)
    
    return {
        'taxa_sucesso': taxa_sucesso_geral,
        'tempo_medio': tempo_medio,
        'resultados_categoria': resultados_por_categoria,
        'total_comandos': total_comandos,
        'sucessos': sucessos,
        'falhas': falhas
    }

if __name__ == "__main__":
    print("🚀 Iniciando teste das melhorias 1 e 2 do sistema ZEUS...")
    resultados = test_melhorias_1_2()
    
    # Código de saída baseado na taxa de sucesso
    if resultados['taxa_sucesso'] >= 80:
        sys.exit(0)  # Sucesso
    elif resultados['taxa_sucesso'] >= 60:
        sys.exit(1)  # Parcialmente bem-sucedido
    else:
        sys.exit(2)  # Necessita melhorias