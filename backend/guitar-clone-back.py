"""
Guitar Hero Backend - v1
Sistema de análise de áudio e API REST para o jogo Guitar Hero

Requisitos:
pip install flask flask-cors librosa numpy soundfile

Uso:
python guitar_hero_backend.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import librosa
import numpy as np
import os
import json
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
CORS(app)  # Permite requisições do frontend

# Configurações
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'm4a'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def analyze_audio(file_path, difficulty='medium'):
    """
    Analisa o arquivo de áudio e extrai informações para o jogo
    
    Args:
        file_path: caminho do arquivo de áudio
        difficulty: nível de dificuldade ('easy', 'medium', 'hard', 'expert')
    
    Returns:
        dict com informações do áudio e notas geradas
    """
    try:
        # Carrega o áudio
        print(f"Carregando áudio: {file_path}")
        y, sr = librosa.load(file_path, sr=22050)
        duration = float(librosa.get_duration(y=y, sr=sr))
        
        print(f"Duração: {duration:.2f}s, Sample rate: {sr}")
        
        # Detecta tempo e beats
        tempo_result, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo_result) if hasattr(tempo_result, '__float__') else float(tempo_result[0] if isinstance(tempo_result, (list, tuple, np.ndarray)) else tempo_result)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        print(f"BPM detectado: {tempo:.2f}, Beats encontrados: {len(beat_times)}")
        
        # Detecta onset (início de notas/eventos musicais)
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        
        print(f"Onsets detectados: {len(onset_times)}")
        
        # Extrai características espectrais para determinar intensidade
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        
        # Gera notas baseadas na dificuldade
        notes = generate_notes(
            beat_times, 
            onset_times, 
            spectral_centroids,
            difficulty,
            duration
        )
        
        # Informações do áudio
        audio_info = {
            'duration': duration,
            'tempo': tempo,
            'beats_count': int(len(beat_times)),
            'onsets_count': int(len(onset_times)),
            'notes_count': int(len(notes)),
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

def generate_notes(beat_times, onset_times, spectral_centroids, difficulty, duration):
    """
    Gera as notas do jogo baseado na análise do áudio
    
    Args:
        beat_times: timestamps dos beats
        onset_times: timestamps dos onsets
        spectral_centroids: características espectrais
        difficulty: nível de dificuldade
        duration: duração total da música
    
    Returns:
        lista de notas para o jogo
    """
    notes = []
    note_id = 0
    
    # Configurações por dificuldade
    difficulty_config = {
        'easy': {
            'use_beats': True,
            'use_onsets': False,
            'density': 0.5,  # 50% das notas
            'lanes': 3,
            'double_notes': 0.1
        },
        'medium': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.7,
            'lanes': 4,
            'double_notes': 0.2
        },
        'hard': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.85,
            'lanes': 5,
            'double_notes': 0.3
        },
        'expert': {
            'use_beats': True,
            'use_onsets': True,
            'density': 1.0,
            'lanes': 5,
            'double_notes': 0.4
        }
    }
    
    config = difficulty_config.get(difficulty, difficulty_config['medium'])
    num_lanes = config['lanes']
    
    # Combina beats e onsets
    all_times = []
    
    if config['use_beats']:
        all_times.extend(beat_times)
    
    if config['use_onsets']:
        all_times.extend(onset_times)
    
    # Remove duplicatas e ordena
    all_times = sorted(list(set([round(t, 3) for t in all_times])))
    
    # Aplica densidade baseada na dificuldade
    step = int(1 / config['density'])
    selected_times = all_times[::step]
    
    print(f"Gerando notas - Tempos totais: {len(all_times)}, Selecionados: {len(selected_times)}")
    
    # Gera notas
    for i, time in enumerate(selected_times):
        if time < 1.0:  # Pula primeiros segundo para dar tempo de preparar
            continue
            
        if time > duration - 2.0:  # Pula últimos 2 segundos
            break
        
        # Determina a lane baseado na frequência espectral
        spectral_index = int((time / duration) * len(spectral_centroids))
        spectral_index = min(spectral_index, len(spectral_centroids) - 1)
        
        # Normaliza centroid para determinar lane (0 a num_lanes-1)
        lane = int((spectral_centroids[spectral_index] / np.max(spectral_centroids)) * (num_lanes - 1))
        lane = max(0, min(lane, num_lanes - 1))
        
        note = {
            'id': note_id,
            'time': round(float(time), 3),
            'lane': int(lane),
            'type': 'single'
        }
        
        notes.append(note)
        note_id += 1
        
        # Adiciona notas duplas baseado na probabilidade
        if np.random.random() < config['double_notes'] and lane < num_lanes - 1:
            double_note = {
                'id': note_id,
                'time': round(float(time), 3),
                'lane': int(lane + 1),
                'type': 'double'
            }
            notes.append(double_note)
            note_id += 1
    
    print(f"Notas geradas: {len(notes)}")
    return notes


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se a API está funcionando"""
    return jsonify({
        'status': 'online',
        'message': 'Guitar Hero Backend v1'
    })


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Endpoint principal para upload e análise de áudio
    
    Parâmetros:
        file: arquivo de áudio (multipart/form-data)
        difficulty: 'easy', 'medium', 'hard', 'expert' (opcional, padrão: medium)
    
    Retorna:
        JSON com informações do áudio e notas geradas
    """
    # Verifica se o arquivo foi enviado
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'Nenhum arquivo foi enviado'
        }), 400
    
    file = request.files['file']
    
    # Verifica se o arquivo tem um nome
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'Nome de arquivo inválido'
        }), 400
    
    # Verifica extensão
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': f'Extensão não permitida. Use: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400
    
    # Pega o nível de dificuldade
    difficulty = request.form.get('difficulty', 'medium').lower()
    if difficulty not in ['easy', 'medium', 'hard', 'expert']:
        difficulty = 'medium'
    
    try:
        # Salva arquivo temporariamente
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"Arquivo salvo em: {filepath}")
        
        # Analisa o áudio
        result = analyze_audio(filepath, difficulty)
        
        # Remove arquivo temporário
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
        print(f"Erro no endpoint /analyze: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao processar arquivo: {str(e)}'
        }), 500


@app.route('/test-generation', methods=['GET'])
def test_generation():
    """
    Endpoint de teste que gera notas sintéticas sem precisar de arquivo
    Útil para testar a integração frontend-backend
    """
    duration = float(request.args.get('duration', 180))  # 3 minutos padrão
    difficulty = request.args.get('difficulty', 'medium')
    
    # Gera beats sintéticos
    bpm = 120
    beat_interval = 60 / bpm
    beat_times = np.arange(0, duration, beat_interval)
    
    # Gera onsets sintéticos (mais frequentes que beats)
    onset_times = np.arange(0, duration, beat_interval / 2)
    
    # Centroids sintéticos
    spectral_centroids = np.random.rand(int(duration * 100)) * 5000
    
    notes = generate_notes(beat_times, onset_times, spectral_centroids, difficulty, duration)
    
    return jsonify({
        'success': True,
        'audio_info': {
            'duration': duration,
            'tempo': bpm,
            'beats_count': len(beat_times),
            'onsets_count': len(onset_times),
            'notes_count': len(notes),
            'difficulty': difficulty,
            'sample_rate': 22050
        },
        'notes': notes
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🎸 Guitar Hero Backend v1")
    print("=" * 60)
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Extensões permitidas: {', '.join(ALLOWED_EXTENSIONS)}")
    print(f"Tamanho máximo: {MAX_FILE_SIZE / (1024*1024)}MB")
    print("=" * 60)
    print("\nEndpoints disponíveis:")
    print("  GET  /health - Verifica status da API")
    print("  POST /analyze - Analisa arquivo de áudio")
    print("  GET  /test-generation - Gera notas de teste")
    print("\nIniciando servidor...")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)