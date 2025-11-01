"""
Guitar Hero Backend - v3
Sistema com Spotify + YouTube
Busca músicas no Spotify e baixa áudio do YouTube
AGORA COM STREAMING DE ÁUDIO!

Requisitos:
pip install flask flask-cors librosa numpy soundfile spotipy yt-dlp

Configuração:
1. Crie um app em: https://developer.spotify.com/dashboard
2. Adicione Redirect URI: http://127.0.0.1:5000/callback
3. Copie Client ID e Client Secret
4. Cole abaixo nas variáveis SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET

Uso:
python guitar_hero_backend_v3.py
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import librosa
import numpy as np
import os
import json
from werkzeug.utils import secure_filename
import tempfile
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import re
import hashlib
import time

app = Flask(__name__)
CORS(app)

# ============================================================
# CONFIGURAÇÃO DO SPOTIFY - ADICIONE SUAS CREDENCIAIS AQUI!
# ============================================================
SPOTIFY_CLIENT_ID = '93c97ca549a14093875c81df94b05455'
SPOTIFY_CLIENT_SECRET = '5c7e7aa7d32041e397f6a1fb15f669ed'

# Configurações gerais
UPLOAD_FOLDER = tempfile.gettempdir()
AUDIO_CACHE_FOLDER = os.path.join(tempfile.gettempdir(), 'guitar_hero_cache')
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'm4a'}
MAX_FILE_SIZE = 50 * 1024 * 1024

# Cria pasta de cache se não existir
os.makedirs(AUDIO_CACHE_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Cache de áudios baixados (query -> filepath)
audio_cache = {}

# Inicializa Spotify Client
try:
    if SPOTIFY_CLIENT_ID != 'SEU_CLIENT_ID_AQUI':
        spotify = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(client_credentials_manager=spotify)
        SPOTIFY_ENABLED = True
        print("✅ Spotify API conectada!")
    else:
        SPOTIFY_ENABLED = False
        print("⚠️  Spotify não configurado. Configure SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET")
except Exception as e:
    SPOTIFY_ENABLED = False
    print(f"⚠️  Erro ao conectar Spotify: {e}")


def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def search_youtube_and_download(query, use_cache=True):
    """
    Busca e baixa áudio do YouTube com sistema de cache
    
    Args:
        query: string de busca (ex: "Queen - Bohemian Rhapsody")
        use_cache: usar cache de downloads anteriores
    
    Returns:
        (filepath, cache_id) ou (None, None) se falhar
    """
    # Gera ID único para o cache baseado na query
    cache_id = hashlib.md5(query.encode()).hexdigest()
    cached_path = os.path.join(AUDIO_CACHE_FOLDER, f"{cache_id}.mp3")
    
    # Verifica se já está em cache
    if use_cache and os.path.exists(cached_path):
        print(f"♻️  Usando áudio do cache: {query}")
        return cached_path, cache_id
    
    try:
        print(f"🔍 Buscando no YouTube: {query}")
        
        # Configurações do yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': cached_path.replace('.mp3', '.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'default_search': 'ytsearch1',
            'age_limit': None,
            'nocheckcertificate': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"📥 Tentando extrair informações...")
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            
            if 'entries' in info:
                info = info['entries'][0]
            
            print(f"📹 Vídeo encontrado:")
            print(f"   - Título: {info.get('title', 'N/A')}")
            print(f"   - Canal: {info.get('uploader', 'N/A')}")
            print(f"   - Duração: {info.get('duration', 0)}s")
            
            # Verifica se o arquivo foi criado
            if os.path.exists(cached_path):
                file_size = os.path.getsize(cached_path) / (1024 * 1024)
                print(f"✅ Download completo: {info['title']}")
                print(f"   - Cache ID: {cache_id}")
                print(f"   - Tamanho: {file_size:.2f}MB")
                
                # Adiciona ao cache em memória
                audio_cache[cache_id] = {
                    'query': query,
                    'filepath': cached_path,
                    'title': info['title'],
                    'timestamp': time.time()
                }
                
                return cached_path, cache_id
            else:
                print(f"❌ Arquivo não foi criado")
                return None, None
            
    except yt_dlp.utils.DownloadError as e:
        print(f"❌ Erro de download do YouTube: {str(e)}")
        if 'age' in str(e).lower():
            print(f"   💡 Possível vídeo com restrição de idade")
        if 'copyright' in str(e).lower():
            print(f"   💡 Possível bloqueio por copyright")
        return None, None
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None


def detect_note_duration(y, sr, onset_time, max_duration=2.0):
    """Detecta a duração de uma nota baseado na energia do sinal"""
    onset_frame = librosa.time_to_frames(onset_time, sr=sr)
    max_frames = int(max_duration * sr / 512)
    
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    
    start_idx = onset_frame
    end_idx = min(start_idx + max_frames, len(rms))
    
    if start_idx >= len(rms):
        return 0.1
    
    initial_energy = rms[start_idx]
    threshold = initial_energy * 0.3
    
    duration_frames = 1
    for i in range(start_idx + 1, end_idx):
        if rms[i] < threshold:
            break
        duration_frames += 1
    
    duration = librosa.frames_to_time(duration_frames, sr=sr)
    return float(max(0.1, min(duration, max_duration)))


def analyze_audio(file_path, difficulty='medium'):
    """Analisa o arquivo de áudio e extrai informações para o jogo"""
    try:
        print(f"Carregando áudio: {file_path}")
        y, sr = librosa.load(file_path, sr=22050)
        duration = float(librosa.get_duration(y=y, sr=sr))
        
        print(f"Duração: {duration:.2f}s, Sample rate: {sr}")
        
        tempo_result, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo_result.item()) if hasattr(tempo_result, 'item') else float(tempo_result)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        print(f"BPM detectado: {tempo:.2f}, Beats encontrados: {len(beat_times)}")
        
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True, units='frames')
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        
        print(f"Onsets detectados: {len(onset_times)}")
        
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        
        print(f"Analisando durações de notas...")
        
        notes = generate_notes_with_duration(
            y, sr, beat_times, onset_times, 
            spectral_centroids, chroma, difficulty, duration
        )
        
        audio_info = {
            'duration': duration,
            'tempo': tempo,
            'beats_count': int(len(beat_times)),
            'onsets_count': int(len(onset_times)),
            'notes_count': int(len(notes)),
            'hold_notes_count': int(sum(1 for n in notes if n.get('duration', 0) > 0.3)),
            'difficulty': difficulty,
            'sample_rate': int(sr)
        }
        
        return {
            'success': True,
            'audio_info': audio_info,
            'notes': notes
        }
        
    except Exception as e:
        print(f"Erro na análise: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def generate_notes_with_duration(y, sr, beat_times, onset_times, spectral_centroids, chroma, difficulty, total_duration):
    """Gera notas do jogo COM DURAÇÃO"""
    notes = []
    note_id = 0
    
    difficulty_config = {
        'easy': {
            'use_beats': True,
            'use_onsets': False,
            'density': 0.7,
            'lanes': 3,
            'hold_probability': 0.12,
            'min_hold_duration': 0.5,
            'min_time_gap': 0.4
        },
        'medium': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.6,
            'lanes': 4,
            'hold_probability': 0.25,
            'min_hold_duration': 0.35,
            'min_time_gap': 0.25
        },
        'hard': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.75,
            'lanes': 5,
            'hold_probability': 0.3,
            'min_hold_duration': 0.3,
            'min_time_gap': 0.2
        },
        'expert': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.9,
            'lanes': 5,
            'hold_probability': 0.35,
            'min_hold_duration': 0.25,
            'min_time_gap': 0.15
        }
    }
    
    config = difficulty_config.get(difficulty, difficulty_config['medium'])
    num_lanes = config['lanes']
    min_time_gap = config['min_time_gap']
    
    all_times = []
    if config['use_beats']:
        all_times.extend(beat_times)
    if config['use_onsets']:
        all_times.extend(onset_times)
    
    all_times = sorted(list(set([round(float(t), 3) for t in all_times])))
    
    filtered_times = []
    last_time = -999
    for time in all_times:
        if time - last_time >= min_time_gap:
            filtered_times.append(time)
            last_time = time
    
    step = max(1, int(1 / config['density']))
    selected_times = filtered_times[::step]
    
    print(f"Gerando notas - Tempos totais: {len(all_times)}, Filtrados: {len(filtered_times)}, Selecionados: {len(selected_times)}")
    
    lane_counts = [0] * num_lanes
    
    for i, time in enumerate(selected_times):
        if time < 1.0:
            continue
        if time > total_duration - 2.0:
            break
        
        chroma_index = int((time / total_duration) * chroma.shape[1])
        chroma_index = min(chroma_index, chroma.shape[1] - 1)
        
        chroma_frame = chroma[:, chroma_index]
        top_pitches = np.argsort(chroma_frame)[-3:]
        
        dominant_pitch = top_pitches[-1]
        lane = dominant_pitch % num_lanes
        
        if lane_counts[lane] > np.mean(lane_counts) + 2:
            lane = int(np.argmin(lane_counts))
        
        spectral_index = int((time / total_duration) * len(spectral_centroids))
        spectral_index = min(spectral_index, len(spectral_centroids) - 1)
        normalized_centroid = spectral_centroids[spectral_index] / np.max(spectral_centroids)
        
        if np.random.random() < 0.3:
            lane = int(normalized_centroid * (num_lanes - 1))
        
        lane = max(0, min(lane, num_lanes - 1))
        lane_counts[lane] += 1
        
        is_hold_note = np.random.random() < config['hold_probability']
        
        note_duration = 0.0
        note_type = 'tap'
        
        if is_hold_note:
            note_duration = detect_note_duration(y, sr, time, max_duration=2.5)
            if note_duration >= config['min_hold_duration']:
                note_type = 'hold'
            else:
                note_duration = 0.0
                note_type = 'tap'
        
        note = {
            'id': note_id,
            'time': round(float(time), 3),
            'lane': int(lane),
            'type': note_type,
            'duration': round(float(note_duration), 3) if note_type == 'hold' else 0.0
        }
        
        notes.append(note)
        note_id += 1
    
    hold_count = sum(1 for n in notes if n['type'] == 'hold')
    print(f"Notas geradas: {len(notes)} total ({hold_count} hold notes)")
    print(f"Distribuição por lane: {lane_counts}")
    
    return notes


# ============================================================
# NOVOS ENDPOINTS v3 - SPOTIFY + YOUTUBE
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Verifica status da API"""
    return jsonify({
        'status': 'online',
        'message': 'Guitar Hero Backend v3 - Spotify + YouTube!',
        'version': '3.0',
        'spotify_enabled': SPOTIFY_ENABLED
    })


@app.route('/search/spotify', methods=['GET'])
def search_spotify():
    """
    Busca músicas no Spotify
    
    Query params:
        q: termo de busca
        limit: número de resultados (padrão: 10)
    
    Returns:
        JSON com lista de músicas do Spotify
    """
    if not SPOTIFY_ENABLED:
        return jsonify({
            'success': False,
            'error': 'Spotify não configurado. Configure as credenciais no backend.'
        }), 503
    
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Parâmetro "q" é obrigatório'
        }), 400
    
    try:
        print(f"🔍 Buscando no Spotify: {query}")
        results = sp.search(q=query, limit=limit, type='track')
        
        tracks = []
        for item in results['tracks']['items']:
            track = {
                'id': item['id'],
                'name': item['name'],
                'artist': ', '.join([artist['name'] for artist in item['artists']]),
                'album': item['album']['name'],
                'image': item['album']['images'][0]['url'] if item['album']['images'] else None,
                'preview_url': item['preview_url'],  # 30 segundos de preview
                'duration_ms': item['duration_ms'],
                'spotify_url': item['external_urls']['spotify']
            }
            tracks.append(track)
        
        print(f"✅ Encontradas {len(tracks)} músicas")
        
        return jsonify({
            'success': True,
            'tracks': tracks
        })
        
    except Exception as e:
        print(f"❌ Erro ao buscar no Spotify: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/analyze/youtube', methods=['POST'])
def analyze_from_youtube():
    """
    Baixa música do YouTube e analisa
    AGORA RETORNA O CACHE_ID PARA STREAMING
    
    Body JSON:
        query: string de busca (ex: "Queen - Bohemian Rhapsody")
        difficulty: easy/medium/hard/expert
    
    Returns:
        JSON com notas geradas + cache_id para streaming
    """
    data = request.get_json()
    
    if not data or 'query' not in data:
        return jsonify({
            'success': False,
            'error': 'Campo "query" é obrigatório'
        }), 400
    
    query = data['query']
    difficulty = data.get('difficulty', 'medium')
    
    try:
        # Baixa do YouTube (com cache)
        filepath, cache_id = search_youtube_and_download(query, use_cache=True)
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'error': 'Falha ao baixar áudio do YouTube. Vídeo pode ter restrições.'
            }), 500
        
        # Analisa o áudio
        result = analyze_audio(filepath, difficulty)
        
        # NÃO remove o arquivo - mantém em cache!
        
        if result['success']:
            # Adiciona cache_id e URL de streaming à resposta
            result['cache_id'] = cache_id
            result['audio_url'] = f'/stream/{cache_id}'
            print(f"✅ Análise completa! Stream URL: /stream/{cache_id}")
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/stream/<cache_id>', methods=['GET'])
def stream_audio(cache_id):
    """
    Serve o arquivo de áudio para streaming
    
    Path param:
        cache_id: ID do áudio no cache
    
    Returns:
        Arquivo MP3 para streaming
    """
    try:
        # Verifica se o cache_id existe
        if cache_id in audio_cache:
            filepath = audio_cache[cache_id]['filepath']
        else:
            # Tenta encontrar o arquivo diretamente
            filepath = os.path.join(AUDIO_CACHE_FOLDER, f"{cache_id}.mp3")
        
        if not os.path.exists(filepath):
            print(f"❌ Arquivo não encontrado: {cache_id}")
            return jsonify({
                'success': False,
                'error': 'Áudio não encontrado. Cache expirado?'
            }), 404
        
        print(f"🎵 Servindo áudio: {cache_id}")
        
        # Serve o arquivo com suporte a range requests (para seek)
        return send_file(
            filepath,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name='audio.mp3'
        )
        
    except Exception as e:
        print(f"❌ Erro ao servir áudio: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/analyze', methods=['POST'])
def analyze():
    """Endpoint original - upload de arquivo"""
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'Nenhum arquivo foi enviado'
        }), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'Nome de arquivo inválido'
        }), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': f'Extensão não permitida. Use: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400
    
    difficulty = request.form.get('difficulty', 'medium').lower()
    if difficulty not in ['easy', 'medium', 'hard', 'expert']:
        difficulty = 'medium'
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"Arquivo salvo em: {filepath}")
        
        result = analyze_audio(filepath, difficulty)
        
        try:
            os.remove(filepath)
            print(f"Arquivo temporário removido: {filepath}")
        except:
            pass
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🎸 Guitar Hero Backend v3 - Spotify + YouTube!")
    print("=" * 60)
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Spotify Status: {'✅ Conectado' if SPOTIFY_ENABLED else '⚠️  Não configurado'}")
    print("=" * 60)
    print("\nNovos endpoints v3:")
    print("  GET  /search/spotify?q=QUERY - Busca no Spotify")
    print("  POST /analyze/youtube - Baixa do YouTube e analisa")
    print("  POST /analyze - Upload de arquivo (método antigo)")
    print("\nIniciando servidor...")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)