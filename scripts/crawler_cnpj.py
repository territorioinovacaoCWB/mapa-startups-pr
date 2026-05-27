import csv
import json
import os
import time
import requests

# Configurações
ARQUIVO_ENTRADA_CSV = 'dados_cnpjs.csv'
ARQUIVO_SAIDA_JSON = 'startups_data.json'

def consultar_cnpj(cnpj):
    """Consulta dados públicos do CNPJ via BrasilAPI"""
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
    try:
        response = requests.get(url, timeout=15 )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"[-] Erro na API de CNPJ ({cnpj}): {e}")
        return None

def obter_coordenadas(logradouro, numero, bairro, municipio, estado):
    """Busca geolocalização via Nominatim (OpenStreetMap)"""
    endereco = f"{logradouro}, {numero}, {bairro}, {municipio}, {estado}, Brasil"
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'MapaStartupsPR_Bot/2.0 (contato@seusite.com )'}
    params = {'q': endereco, 'format': 'json', 'limit': 1}
    
    try:
        # Delay obrigatório para respeitar os termos do Nominatim (1 req/seg)
        time.sleep(1.1) 
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200 and response.json():
            res = response.json()[0]
            return float(res['lat']), float(res['lon'])
    except Exception as e:
        print(f"[-] Erro na geolocalização: {e}")
    
    return None, None

def processar():
    print("[*] Iniciando processamento...")
    
    # 1. Carregar dados existentes para fazer cache
    startups_existentes = []
    if os.path.exists(ARQUIVO_SAIDA_JSON):
        try:
            with open(ARQUIVO_SAIDA_JSON, 'r', encoding='utf-8') as f:
                startups_existentes = json.load(f)
        except:
            print("[!] Arquivo JSON atual corrompido, iniciando do zero.")

    # Criar índice de CNPJs já processados
    cnpjs_processados = {str(s.get('cnpj', '')) for s in startups_existentes}
    
    novas_startups = list(startups_existentes)
    
    # 2. Ler CSV de entrada
    if not os.path.exists(ARQUIVO_ENTRADA_CSV):
        print(f"[-] Erro: {ARQUIVO_ENTRADA_CSV} não encontrado.")
        return

    with open(ARQUIVO_ENTRADA_CSV, mode='r', encoding='utf-8') as f:
        # Tenta detectar o separador (vírgula ou ponto e vírgula)
        content = f.read(1024)
        f.seek(0)
        dialect = csv.Sniffer().sniff(content)
        leitor = csv.DictReader(f, dialect=dialect)
        
        for linha in leitor:
            cnpj = linha.get('cnpj') or linha.get('CNPJ')
            if not cnpj or str(cnpj) in cnpjs_processados:
                continue
            
            print(f"[+] Processando novo CNPJ: {cnpj}")
            dados = consultar_cnpj(cnpj)
            
            if dados:
                # Extrair endereço para geolocalização
                lat, lng = obter_coordenadas(
                    dados.get('logradouro', ''),
                    dados.get('numero', ''),
                    dados.get('bairro', ''),
                    dados.get('municipio', ''),
                    dados.get('uf', '')
                )
                
                # Se falhar a geolocalização, usa Curitiba como padrão ou pula
                if not lat:
                    lat, lng = -25.4296, -49.2719 
                
                dados['lat'] = lat
                dados['lng'] = lng
                dados['cnpj'] = cnpj # Garante o campo para o cache
                
                novas_startups.append(dados)
                
                # Salva a cada 5 novas para não perder progresso se o GitHub parar
                if len(novas_startups) % 5 == 0:
                    with open(ARQUIVO_SAIDA_JSON, 'w', encoding='utf-8') as f_out:
                        json.dump(novas_startups, f_out, indent=4, ensure_ascii=False)

    # 3. Salvar resultado final
    with open(ARQUIVO_SAIDA_JSON, 'w', encoding='utf-8') as f_out:
        json.dump(novas_startups, f_out, indent=4, ensure_ascii=False)
    
    print(f"[*] Sucesso! Total de startups no mapa: {len(novas_startups)}")

if __name__ == "__main__":
    processar()
