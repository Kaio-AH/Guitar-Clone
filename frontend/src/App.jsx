import React, { useState, useEffect, useRef } from 'react';
import { Music, Upload, Play, Pause, RotateCcw, Zap, AlertCircle, Loader, Flame, Search, Download } from 'lucide-react';

const GuitarHeroGame = () => {
  const [audioFile, setAudioFile] = useState(null);
  const [audioFileName, setAudioFileName] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [score, setScore] = useState(0);
  const [combo, setCombo] = useState(0);
  const [maxCombo, setMaxCombo] = useState(0);
  const [notes, setNotes] = useState([]);
  const [pressedKeys, setPressedKeys] = useState(new Set());
  const [holdingKeys, setHoldingKeys] = useState(new Map());
  const [difficulty, setDifficulty] = useState('medium');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [audioInfo, setAudioInfo] = useState(null);
  const [notesHit, setNotesHit] = useState(0);
  const [notesMissed, setNotesMissed] = useState(0);
  const [multiplier, setMultiplier] = useState(1);
  
  // Estados v3 - Spotify
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedTrack, setSelectedTrack] = useState(null);
  const [viewMode, setViewMode] = useState('search');
  
  const audioRef = useRef(null);
  const animationRef = useRef(null);
  const notesRef = useRef([]);
  const fileInputRef = useRef(null);
  const isTogglingRef = useRef(false);
  const previewAudioRef = useRef(null);

  const LANES = ['A', 'S', 'D', 'J', 'K'];
  const COLORS = ['#22c55e', '#ef4444', '#eab308', '#3b82f6', '#f97316'];
  const NOTE_SPEED = 350;
  const HIT_ZONE = 60;
  const SPAWN_HEIGHT = -100;
  const TARGET_Y = 520;
  const BACKEND_URL = 'http://localhost:5000';

  const handleSpotifySearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchResults([]);
    setAnalysisError(null);

    try {
      const response = await fetch(`${BACKEND_URL}/search/spotify?q=${encodeURIComponent(searchQuery)}&limit=12`);
      const data = await response.json();
      if (data.success) {
        setSearchResults(data.tracks);
      } else {
        setAnalysisError(data.error || 'Erro ao buscar');
      }
    } catch (error) {
      setAnalysisError('Backend offline');
    } finally {
      setIsSearching(false);
    }
  };

  const playPreview = (track) => {
    if (previewAudioRef.current) previewAudioRef.current.pause();
    if (track.preview_url) {
      previewAudioRef.current = new Audio(track.preview_url);
      previewAudioRef.current.play();
    }
  };

  const stopPreview = () => {
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
      previewAudioRef.current = null;
    }
  };

  const handleSelectTrack = async (track) => {
    stopPreview();
    setSelectedTrack(track);
    setIsAnalyzing(true);
    setAnalysisError(null);
    resetGameState();

    try {
      const query = `${track.artist} - ${track.name}`;
      console.log('📥 Enviando para backend:', query);
      
      const response = await fetch(`${BACKEND_URL}/analyze/youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, difficulty })
      });

      const data = await response.json();
      if (data.success) {
        console.log('✅ Análise completa!');
        console.log('🎵 Stream URL:', data.audio_url);
        
        const preparedNotes = data.notes.map(note => ({
          ...note,
          y: SPAWN_HEIGHT,
          hit: false,
          missed: false,
          holding: false,
          holdProgress: 0
        }));

        setNotes(preparedNotes);
        notesRef.current = preparedNotes;
        setAudioInfo(data.audio_info);
        setAudioFileName(`${track.artist} - ${track.name}`);
        
        // USA A URL DE STREAMING DO BACKEND
        const streamUrl = `${BACKEND_URL}${data.audio_url}`;
        console.log('🎧 Configurando stream:', streamUrl);
        
        setAudioFile(streamUrl);
        if (audioRef.current) {
          audioRef.current.src = streamUrl;
          audioRef.current.load();
          console.log('✅ Áudio configurado!');
        }
        
        setViewMode('game');
        setIsAnalyzing(false);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error('❌ Erro:', error);
      setAnalysisError(`Erro: ${error.message}`);
      setIsAnalyzing(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !file.type.startsWith('audio/')) return;

    setAudioFileName(file.name);
    setIsAnalyzing(true);
    resetGameState();

    try {
      const audioUrl = URL.createObjectURL(file);
      setAudioFile(audioUrl);

      const formData = new FormData();
      formData.append('file', file);
      formData.append('difficulty', difficulty);

      const response = await fetch(`${BACKEND_URL}/analyze`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      if (data.success) {
        const preparedNotes = data.notes.map(note => ({
          ...note,
          y: SPAWN_HEIGHT,
          hit: false,
          missed: false,
          holding: false,
          holdProgress: 0
        }));

        setNotes(preparedNotes);
        notesRef.current = preparedNotes;
        setAudioInfo(data.audio_info);
        
        if (audioRef.current) {
          audioRef.current.src = audioUrl;
          audioRef.current.load();
        }
        
        setViewMode('game');
        setIsAnalyzing(false);
      }
    } catch (error) {
      setAnalysisError(error.message);
      setIsAnalyzing(false);
    }
  };

  const resetGameState = () => {
    setScore(0);
    setCombo(0);
    setMaxCombo(0);
    setNotesHit(0);
    setNotesMissed(0);
    setMultiplier(1);
  };

  useEffect(() => {
    if (!isPlaying || !audioRef.current) return;
    let lastTime = 0;
    
    const animate = (timestamp) => {
      if (timestamp - lastTime < 16) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }
      lastTime = timestamp;
      const currentTime = audioRef.current.currentTime;
      
      setNotes(prevNotes => prevNotes.map(note => {
        if (note.hit || note.missed) return note;
        const timeDiff = currentTime - note.time;
        const newY = TARGET_Y + (timeDiff * NOTE_SPEED);
        
        if (note.type === 'hold' && note.holding) {
          const holdProgress = Math.min(1, (currentTime - note.time) / note.duration);
          if (currentTime >= note.time + note.duration) {
            return { ...note, hit: true, holdProgress: 1 };
          }
          return { ...note, y: newY, holdProgress };
        }
        
        if (newY > TARGET_Y + HIT_ZONE && !note.holding) {
          setCombo(0);
          setMultiplier(1);
          setNotesMissed(p => p + 1);
          return { ...note, y: newY, missed: true };
        }
        return { ...note, y: newY };
      }));
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animationRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationRef.current);
  }, [isPlaying]);

  useEffect(() => {
    if (combo >= 50) setMultiplier(4);
    else if (combo >= 30) setMultiplier(3);
    else if (combo >= 10) setMultiplier(2);
    else setMultiplier(1);
  }, [combo]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Enter' && viewMode === 'search') {
        handleSpotifySearch();
        return;
      }
      const key = e.key.toUpperCase();
      if (!LANES.includes(key) || pressedKeys.has(key)) return;
      setPressedKeys(p => new Set([...p, key]));
      if (isPlaying) checkHit(key, 'down');
    };

    const handleKeyUp = (e) => {
      const key = e.key.toUpperCase();
      if (!LANES.includes(key)) return;
      setPressedKeys(p => {
        const n = new Set(p);
        n.delete(key);
        return n;
      });
      if (isPlaying) checkHit(key, 'up');
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [pressedKeys, isPlaying, viewMode]);

  const checkHit = (key, action) => {
    const laneIndex = LANES.indexOf(key);
    if (laneIndex === -1) return;

    setNotes(prevNotes => {
      let hitDetected = false;
      return prevNotes.map(note => {
        if (hitDetected || note.lane !== laneIndex || note.hit || note.missed) return note;
        const distance = Math.abs(note.y - TARGET_Y);
        
        if (action === 'down' && distance < HIT_ZONE) {
          hitDetected = true;
          if (note.type === 'tap') {
            const precision = 1 - (distance / HIT_ZONE);
            const mult = precision > 0.9 ? 2 : precision > 0.7 ? 1.5 : 1.2;
            const points = Math.floor(100 * mult * multiplier);
            setScore(p => p + points);
            setCombo(p => {
              setMaxCombo(c => Math.max(c, p + 1));
              return p + 1;
            });
            setNotesHit(p => p + 1);
            return { ...note, hit: true };
          } else {
            setHoldingKeys(p => new Map(p).set(key, note.id));
            return { ...note, holding: true };
          }
        }
        
        if (action === 'up' && note.type === 'hold' && note.holding) {
          hitDetected = true;
          const currentTime = audioRef.current?.currentTime || 0;
          const holdPerc = Math.min(1, (currentTime - note.time) / note.duration);
          const points = Math.floor(200 * holdPerc * multiplier);
          setScore(p => p + points);
          if (holdPerc >= 0.9) {
            setCombo(p => {
              setMaxCombo(c => Math.max(c, p + 2));
              return p + 2;
            });
            setNotesHit(p => p + 1);
          }
          return { ...note, hit: true, holdProgress: holdPerc };
        }
        return note;
      });
    });
  };

  const togglePlay = () => {
    console.log('togglePlay chamado');
    console.log('audioRef.current:', audioRef.current);
    console.log('audioRef.current.src:', audioRef.current?.src);
    console.log('notes.length:', notes.length);
    
    if (!audioRef.current || notes.length === 0) {
      console.log('❌ Sem áudio ou notas');
      return;
    }
    
    // Verifica se há src configurado
    if (!audioRef.current.src || audioRef.current.src === window.location.href) {
      console.log('❌ Áudio não carregado. Src:', audioRef.current.src);
      setAnalysisError('Áudio não disponível. Esta música só tem preview de 30s do Spotify.');
      return;
    }
    
    if (isPlaying) {
      console.log('⏸️ Pausando');
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      console.log('▶️ Tentando tocar');
      audioRef.current.play()
        .then(() => {
          console.log('✅ Tocando!');
          setIsPlaying(true);
        })
        .catch(err => {
          console.error('❌ Erro ao tocar:', err);
          setAnalysisError('Erro ao reproduzir áudio: ' + err.message);
        });
    }
  };

  const resetGame = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsPlaying(false);
    resetGameState();
    if (notes.length > 0) {
      setNotes(notesRef.current.map(n => ({
        ...n,
        y: SPAWN_HEIGHT,
        hit: false,
        missed: false,
        holding: false,
        holdProgress: 0
      })));
    }
  };

  const newSong = () => {
    stopPreview();
    resetGame();
    setAudioFile(null);
    setNotes([]);
    setAudioInfo(null);
    setViewMode('search');
    setSearchResults([]);
    setSearchQuery('');
  };

  const activeLanes = { easy: 3, medium: 4, hard: 5, expert: 5 }[difficulty] || 5;
  const displayLanes = LANES.slice(0, activeLanes);
  const displayColors = COLORS.slice(0, activeLanes);

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-950 via-gray-900 to-black text-white">
      <div className="p-6 bg-black bg-opacity-70 border-b border-purple-500">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-3">
            <Music className="w-8 h-8 text-purple-400" />
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-green-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                Guitar Hero v3
              </h1>
              <p className="text-xs text-gray-400">🎵 Spotify + YouTube</p>
            </div>
          </div>
          {viewMode === 'game' && (
            <div className="flex gap-6">
              <div className="text-right">
                <div className="text-xs text-gray-400">Score</div>
                <div className="text-2xl font-bold text-yellow-400">{score.toLocaleString()}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-gray-400">Combo</div>
                <div className="text-2xl font-bold text-pink-400">{combo}x {multiplier > 1 && `(${multiplier}x)`}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {viewMode === 'search' && (
        <div className="max-w-4xl mx-auto p-6">
          <div className="text-center mb-8">
            <h2 className="text-4xl font-bold mb-2">Buscar Música</h2>
            <p className="text-gray-400">Spotify + YouTube</p>
          </div>

          <div className="flex gap-3 mb-6">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSpotifySearch()}
              placeholder="Ex: Bohemian Rhapsody..."
              className="flex-1 px-4 py-3 bg-gray-800 border-2 border-gray-700 rounded-xl text-white focus:border-purple-500 focus:outline-none"
            />
            <button
              onClick={handleSpotifySearch}
              disabled={isSearching}
              className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-semibold disabled:opacity-50"
            >
              {isSearching ? <Loader className="w-5 h-5 animate-spin" /> : 'Buscar'}
            </button>
          </div>

          <div className="flex gap-4 mb-6">
            <div className="flex-1 grid grid-cols-4 gap-2">
              {['easy', 'medium', 'hard', 'expert'].map(level => (
                <button
                  key={level}
                  onClick={() => setDifficulty(level)}
                  className={`py-2 rounded-lg uppercase text-xs font-semibold ${
                    difficulty === level ? 'bg-purple-600' : 'bg-gray-800'
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
            <button
              onClick={() => setViewMode('upload')}
              className="px-6 py-2 bg-gray-800 rounded-lg flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              Upload
            </button>
          </div>

          {analysisError && (
            <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-lg flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <div className="text-sm">{analysisError}</div>
            </div>
          )}

          {isAnalyzing && (
            <div className="text-center py-12">
              <Download className="w-16 h-16 mx-auto mb-4 text-purple-400 animate-bounce" />
              <div className="text-xl font-semibold">Baixando e analisando...</div>
              <div className="text-sm text-gray-400 mt-2">30-60 segundos</div>
            </div>
          )}

          {searchResults.length > 0 && !isAnalyzing && (
            <div className="grid grid-cols-4 gap-4">
              {searchResults.map(track => (
                <div key={track.id} className="bg-gray-800 rounded-lg overflow-hidden hover:border-2 hover:border-purple-500 cursor-pointer group">
                  <div className="relative aspect-square">
                    <img src={track.image} alt={track.name} className="w-full h-full object-cover" />
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center">
                      <button
                        onClick={() => handleSelectTrack(track)}
                        className="px-4 py-2 bg-purple-600 rounded-lg font-semibold flex items-center gap-2"
                      >
                        <Play className="w-4 h-4" />
                        Jogar
                      </button>
                    </div>
                  </div>
                  <div className="p-3">
                    <div className="font-semibold text-sm truncate">{track.name}</div>
                    <div className="text-xs text-gray-400 truncate">{track.artist}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {viewMode === 'upload' && (
        <div className="max-w-2xl mx-auto p-6">
          <label className="cursor-pointer block">
            <div className="flex flex-col items-center gap-6 p-16 border-4 border-dashed border-purple-500 rounded-2xl hover:border-pink-500 bg-black/30">
              <Upload className="w-20 h-20 text-purple-400" />
              <div className="text-2xl font-semibold">Upload MP3</div>
            </div>
            <input ref={fileInputRef} type="file" accept="audio/*" onChange={handleFileUpload} className="hidden" />
          </label>
          <div className="mt-6 text-center">
            <button onClick={() => setViewMode('search')} className="text-purple-400">← Voltar</button>
          </div>
        </div>
      )}

      {viewMode === 'game' && notes.length > 0 && (
        <div className="max-w-7xl mx-auto p-6">
          <div className="flex justify-center gap-4 mb-6">
            <button onClick={togglePlay} className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 rounded-lg font-semibold flex items-center gap-2">
              {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
              {isPlaying ? 'Pausar' : 'Jogar'}
            </button>
            <button onClick={resetGame} className="px-6 py-3 bg-gray-700 rounded-lg font-semibold flex items-center gap-2">
              <RotateCcw className="w-5 h-5" />
              Reiniciar
            </button>
            <button onClick={newSong} className="px-6 py-3 bg-pink-600 rounded-lg font-semibold flex items-center gap-2">
              <Search className="w-5 h-5" />
              Nova
            </button>
          </div>

          <div className="grid grid-cols-5 gap-4 mb-6">
            <div className="bg-green-900/30 p-4 rounded-lg text-center border border-green-500/30">
              <div className="text-xs text-gray-400">Acertos</div>
              <div className="text-2xl font-bold text-green-400">{notesHit}</div>
            </div>
            <div className="bg-red-900/30 p-4 rounded-lg text-center border border-red-500/30">
              <div className="text-xs text-gray-400">Erros</div>
              <div className="text-2xl font-bold text-red-400">{notesMissed}</div>
            </div>
            <div className="bg-orange-900/30 p-4 rounded-lg text-center border border-orange-500/30">
              <div className="text-xs text-gray-400">Max Combo</div>
              <div className="text-2xl font-bold text-orange-400">{maxCombo}x</div>
            </div>
            <div className="bg-purple-900/30 p-4 rounded-lg text-center border border-purple-500/30">
              <div className="text-xs text-gray-400">Mult</div>
              <div className="text-2xl font-bold text-purple-400">{multiplier}x {multiplier >= 4 && <Flame className="inline w-5 h-5" />}</div>
            </div>
            <div className="bg-blue-900/30 p-4 rounded-lg text-center border border-blue-500/30">
              <div className="text-xs text-gray-400">Total</div>
              <div className="text-2xl font-bold text-blue-400">{notes.length}</div>
            </div>
          </div>

          <div className="h-[600px] bg-gradient-to-b from-gray-900 to-black rounded-xl overflow-hidden border-4 border-purple-500 relative">
            <div className="absolute inset-0 flex">
              {displayLanes.map((lane, i) => (
                <div key={lane} className="flex-1 border-r-2 border-gray-800 transition-all" style={{ backgroundColor: pressedKeys.has(lane) ? `${displayColors[i]}30` : 'transparent' }} />
              ))}
            </div>

            <div className="absolute inset-x-0 h-24 border-y-4 border-yellow-400 bg-yellow-400/10 z-10" style={{ top: `${TARGET_Y - HIT_ZONE/2}px` }}>
              <div className="flex h-full">
                {displayLanes.map((lane, i) => (
                  <div key={lane} className="flex-1 flex items-center justify-center border-r border-yellow-400">
                    <div className={`text-5xl font-bold ${pressedKeys.has(lane) ? 'scale-125 text-white' : 'text-gray-700'}`}>{lane}</div>
                  </div>
                ))}
              </div>
            </div>

            {notes.map(note => {
              if (note.hit || note.missed || note.y < SPAWN_HEIGHT || note.y > 650 || note.lane >= activeLanes) return null;
              const color = displayColors[note.lane];
              const laneW = 100 / activeLanes;
              const laneL = (note.lane / activeLanes) * 100;

              return (
                <div key={note.id}>
                  {note.type === 'hold' && (
                    <div className="absolute" style={{ bottom: `${650 - note.y}px`, left: `${laneL}%`, width: `${laneW}%`, height: `${note.duration * NOTE_SPEED}px`, zIndex: 3 }}>
                      <div className="mx-8 h-full rounded" style={{ background: `linear-gradient(to top, ${color}DD, ${color}BB, ${color}88)`, border: `2px solid ${color}`, opacity: 0.85 }} />
                    </div>
                  )}
                  <div className="absolute flex items-center justify-center" style={{ top: `${note.y}px`, left: `${laneL}%`, width: `${laneW}%`, height: '56px', zIndex: 5 }}>
                    <div className="w-4/5 h-14 max-w-[70px] rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 40px ${color}`, border: '4px solid white' }} />
                  </div>
                </div>
              );
            })}

            {!isPlaying && (
              <div className="absolute inset-0 bg-black/70 flex items-center justify-center z-20">
                <div className="text-center">
                  <Play className="w-20 h-20 mx-auto mb-4 text-purple-400" />
                  <div className="text-2xl font-bold">Clique em Jogar!</div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 text-center text-gray-400">
            <p>Teclas: <span className="font-bold text-white">{displayLanes.join(' ')}</span></p>
            <p className="text-sm mt-2">Segure para hold notes! 🎹</p>
          </div>
        </div>
      )}

      <audio ref={audioRef} onEnded={() => setIsPlaying(false)} />
    </div>
  );
};

export default GuitarHeroGame;