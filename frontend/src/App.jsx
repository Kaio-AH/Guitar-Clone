import React, { useState, useEffect, useRef } from 'react';
import { Music, Upload, Play, Pause, RotateCcw, Zap, AlertCircle, Loader, Flame, Search, Download, Smartphone } from 'lucide-react';

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
  const [isMobile, setIsMobile] = useState(false);
  
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
  const HIT_ZONE = 70;
  const SPAWN_HEIGHT = -100;
  const TARGET_Y = 520;
  const BACKEND_URL = 'http://localhost:5000';

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

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
      const response = await fetch(`${BACKEND_URL}/analyze/youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, difficulty })
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
        setAudioFileName(`${track.artist} - ${track.name}`);
        
        const streamUrl = `${BACKEND_URL}${data.audio_url}`;
        setAudioFile(streamUrl);
        if (audioRef.current) {
          audioRef.current.src = streamUrl;
          audioRef.current.load();
        }
        
        setViewMode('game');
        setIsAnalyzing(false);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
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

  const handleMobileTouch = (laneIndex, action) => {
    const key = LANES[laneIndex];
    if (action === 'down') {
      setPressedKeys(p => new Set([...p, key]));
      if (isPlaying) checkHit(key, 'down');
    } else {
      setPressedKeys(p => {
        const n = new Set(p);
        n.delete(key);
        return n;
      });
      if (isPlaying) checkHit(key, 'up');
    }
  };

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
    if (!audioRef.current || notes.length === 0) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(e => {
        setAnalysisError('Erro ao tocar');
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
    <div className="min-h-screen bg-black text-white overflow-hidden">
      {viewMode === 'search' && (
        <div className="max-w-4xl mx-auto p-4 md:p-6">
          <div className="text-center mb-6 md:mb-8">
            <h1 className="text-3xl md:text-5xl font-bold mb-2 bg-gradient-to-r from-green-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Guitar Hero v3
            </h1>
            <p className="text-gray-400 text-sm md:text-base">🎵 Spotify + YouTube</p>
          </div>

          <div className="flex flex-col md:flex-row gap-3 mb-6">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSpotifySearch()}
              placeholder="Buscar música..."
              className="flex-1 px-4 py-3 bg-gray-900 border-2 border-gray-800 rounded-xl text-white focus:border-purple-500 focus:outline-none"
            />
            <button
              onClick={handleSpotifySearch}
              disabled={isSearching}
              className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-semibold disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isSearching ? <Loader className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              <span className="hidden md:inline">Buscar</span>
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
            {['easy', 'medium', 'hard', 'expert'].map(level => (
              <button
                key={level}
                onClick={() => setDifficulty(level)}
                className={`py-2 rounded-lg uppercase text-xs font-bold ${
                  difficulty === level ? 'bg-purple-600' : 'bg-gray-900'
                }`}
              >
                {level}
              </button>
            ))}
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
              <div className="text-xl font-semibold">Baixando...</div>
            </div>
          )}

          {searchResults.length > 0 && !isAnalyzing && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {searchResults.map(track => (
                <div key={track.id} className="bg-gray-900 rounded-lg overflow-hidden hover:ring-2 hover:ring-purple-500 cursor-pointer group">
                  <div className="relative aspect-square">
                    <img src={track.image} alt={track.name} className="w-full h-full object-cover" />
                    <div className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <button
                        onClick={() => handleSelectTrack(track)}
                        className="px-4 py-2 bg-purple-600 rounded-lg font-semibold flex items-center gap-2"
                      >
                        <Play className="w-4 h-4" />
                        <span className="text-sm">Jogar</span>
                      </button>
                    </div>
                  </div>
                  <div className="p-2">
                    <div className="font-semibold text-xs truncate">{track.name}</div>
                    <div className="text-xs text-gray-400 truncate">{track.artist}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {viewMode === 'game' && notes.length > 0 && (
        <div className="relative h-screen flex flex-col">
          {/* HUD Superior */}
          <div className="absolute top-0 left-0 right-0 z-30 p-2 md:p-4 bg-gradient-to-b from-black/90 to-transparent">
            <div className="max-w-7xl mx-auto flex justify-between items-center">
              <div className="flex gap-2 md:gap-4">
                <div className="text-center">
                  <div className="text-xs text-gray-400">Score</div>
                  <div className="text-lg md:text-2xl font-bold text-yellow-400">{score.toLocaleString()}</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-gray-400">Combo</div>
                  <div className="text-lg md:text-2xl font-bold text-pink-400">{combo}x</div>
                </div>
                {multiplier > 1 && (
                  <div className="text-center">
                    <div className="text-xs text-gray-400">Mult</div>
                    <div className="text-lg md:text-2xl font-bold text-orange-400 flex items-center gap-1">
                      {multiplier}x {multiplier >= 4 && <Flame className="w-4 h-4" />}
                    </div>
                  </div>
                )}
              </div>
              <button onClick={newSong} className="px-3 py-1 md:px-4 md:py-2 bg-purple-600 rounded-lg text-sm font-semibold">
                Nova
              </button>
            </div>
          </div>

          {/* Pista de Jogo - Estilo Guitar Hero */}
          <div className="flex-1 relative" style={{ 
            background: 'linear-gradient(180deg, #000 0%, #111 50%, #000 100%)',
            perspective: '1000px'
          }}>
            <div className="absolute inset-0" style={{
              transform: 'rotateX(60deg) translateZ(-200px)',
              transformOrigin: 'center bottom'
            }}>
              {/* Faixas com perspectiva */}
              <div className="absolute inset-0 flex">
                {displayLanes.map((lane, i) => (
                  <div
                    key={lane}
                    className="flex-1 relative"
                    style={{
                      background: `linear-gradient(180deg, transparent 0%, ${displayColors[i]}10 100%)`,
                      borderRight: i < displayLanes.length - 1 ? '2px solid rgba(255,255,255,0.1)' : 'none'
                    }}
                  >
                    {/* Linhas de perspectiva */}
                    <div className="absolute inset-y-0 left-1/2 w-px bg-gradient-to-b from-transparent via-white/20 to-transparent" />
                  </div>
                ))}
              </div>

              {/* Notas */}
              <div className="absolute inset-0">
                {notes.map(note => {
                  if (note.hit || note.missed || note.y < SPAWN_HEIGHT || note.y > 650 || note.lane >= activeLanes) return null;
                  const color = displayColors[note.lane];
                  const laneW = 100 / activeLanes;
                  const laneL = (note.lane / activeLanes) * 100;
                  const scale = 0.4 + ((note.y / 600) * 0.6);

                  return (
                    <div key={note.id}>
                      {/* Cauda hold note */}
                      {note.type === 'hold' && (
                        <div 
                          className="absolute"
                          style={{
                            bottom: `${650 - note.y}px`,
                            left: `${laneL}%`,
                            width: `${laneW}%`,
                            height: `${note.duration * NOTE_SPEED * scale}px`,
                            zIndex: 2,
                            transform: `scale(${scale})`,
                            transformOrigin: 'bottom center'
                          }}
                        >
                          <div 
                            className="mx-auto h-full rounded"
                            style={{
                              width: '60%',
                              background: `linear-gradient(to top, ${color}DD, ${color}AA, ${color}77)`,
                              border: `3px solid ${color}`,
                              opacity: note.holding ? 0.95 : 0.8,
                              boxShadow: `0 0 20px ${color}80`
                            }}
                          />
                        </div>
                      )}
                      
                      {/* Nota circular */}
                      <div
                        className="absolute flex items-center justify-center"
                        style={{
                          top: `${note.y}px`,
                          left: `${laneL}%`,
                          width: `${laneW}%`,
                          height: '80px',
                          zIndex: 4,
                          transform: `scale(${scale})`,
                          transformOrigin: 'center'
                        }}
                      >
                        <div 
                          className="relative rounded-full"
                          style={{
                            width: '70px',
                            height: '70px',
                            backgroundColor: color,
                            border: '5px solid white',
                            boxShadow: `
                              0 0 30px ${color},
                              inset 0 -10px 20px rgba(0,0,0,0.3),
                              inset 0 10px 20px rgba(255,255,255,0.3)
                            `
                          }}
                        >
                          {/* Brilho */}
                          <div className="absolute top-2 left-4 w-6 h-4 rounded-full bg-white opacity-60 blur-sm" />
                          
                          {/* Indicador hold */}
                          {note.type === 'hold' && (
                            <div className="absolute inset-0 flex items-center justify-center">
                              <div className="w-8 h-8 rounded-full border-4 border-white" style={{
                                backgroundColor: note.holding ? 'white' : 'transparent'
                              }} />
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Zona de acerto - Aros coloridos */}
            <div className="absolute bottom-20 md:bottom-32 left-0 right-0 z-20 flex justify-center items-center gap-1">
              {displayLanes.map((lane, i) => (
                <div
                  key={lane}
                  className="relative"
                  style={{ width: isMobile ? '60px' : '90px', height: isMobile ? '60px' : '90px' }}
                  onTouchStart={isMobile ? () => handleMobileTouch(i, 'down') : undefined}
                  onTouchEnd={isMobile ? () => handleMobileTouch(i, 'up') : undefined}
                >
                  <div 
                    className="absolute inset-0 rounded-full transition-all duration-100"
                    style={{
                      border: `6px solid ${displayColors[i]}`,
                      backgroundColor: pressedKeys.has(lane) ? `${displayColors[i]}40` : 'rgba(0,0,0,0.5)',
                      boxShadow: pressedKeys.has(lane) 
                        ? `0 0 30px ${displayColors[i]}, inset 0 0 20px ${displayColors[i]}`
                        : `0 0 15px ${displayColors[i]}80`,
                      transform: pressedKeys.has(lane) ? 'scale(0.9)' : 'scale(1)'
                    }}
                  />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-xl md:text-3xl font-black ${
                      pressedKeys.has(lane) ? 'text-white' : 'text-gray-600'
                    }`}>
                      {isMobile ? (i + 1) : lane}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Controles Mobile */}
            {isMobile && (
              <div className="absolute bottom-2 left-0 right-0 z-30 flex justify-center gap-2">
                <button onClick={togglePlay} className="px-6 py-3 bg-purple-600 rounded-full font-bold">
                  {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
                </button>
                <button onClick={resetGame} className="px-6 py-3 bg-gray-700 rounded-full">
                  <RotateCcw className="w-6 h-6" />
                </button>
              </div>
            )}

            {/* Controles Desktop */}
            {!isMobile && (
              <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-30 flex gap-3">
                <button onClick={togglePlay} className="px-6 py-3 bg-purple-600 rounded-lg font-bold flex items-center gap-2">
                  {isPlaying ? <><Pause className="w-5 h-5" />Pausar</> : <><Play className="w-5 h-5" />Jogar</>}
                </button>
                <button onClick={resetGame} className="px-6 py-3 bg-gray-700 rounded-lg font-bold flex items-center gap-2">
                  <RotateCcw className="w-5 h-5" />Reiniciar
                </button>
              </div>
            )}

            {!isPlaying && (
              <div className="absolute inset-0 bg-black/80 flex items-center justify-center z-25">
                <div className="text-center">
                  <Play className="w-20 h-20 mx-auto mb-4 text-purple-400" />
                  <div className="text-2xl font-bold">
                    {isMobile ? 'Toque nos círculos!' : 'Clique em Jogar!'}
                  </div>
                  {!isMobile && (
                    <div className="mt-2 text-gray-400">
                      Teclas: {displayLanes.join(' ')}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <audio ref={audioRef} onEnded={() => setIsPlaying(false)} />
    </div>
  );
};

export default GuitarHeroGame;