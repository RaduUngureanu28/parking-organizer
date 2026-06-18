import React, { useState, useEffect } from 'react';
import ParkingCanvas from './components/ParkingCanvas';

export default function App() {
  // State placeholders
  const [outline, setOutline] = useState([]);
  const [blockedZones, setBlockedZones] = useState([]);
  const [entrance, setEntrance] = useState(null);
  const [mode, setMode] = useState('DRAW_OUTLINE'); // DRAW_OUTLINE, DRAW_BLOCKED, PLACE_ENTRANCE, VIEW_RESULTS
  const [tempPoints, setTempPoints] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [algorithm, setAlgorithm] = useState('v1');

  useEffect(() => {
    setResults(null);
  }, [outline, blockedZones, entrance]);

  // Handle optimization request
  const handleOptimize = async (selectedAlgo = algorithm) => {
    const finalAlgo = typeof selectedAlgo === 'string' ? selectedAlgo : algorithm;
    if (outline.length < 3) {
      alert("Validation Error: Please draw a basement outline first (at least 3 points).");
      return;
    }
    
    // Check if entrance is set
    if (!entrance) {
      alert("Validation Error: Please set the entrance point first using the 'Set Entrance' tool.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/optimize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          outline,
          blocked_zones: blockedZones,
          entrance,
          algorithm: finalAlgo,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate parking layout');
      }

      const data = await response.json();
      setResults(data);
      setMode('VIEW_RESULTS');
    } catch (error) {
      console.error(error);
      alert('Error generating layout: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAlgoChange = (algo) => {
    setAlgorithm(algo);
    if (results && outline.length >= 3 && entrance) {
      handleOptimize(algo);
    }
  };


  // Reset the drawing board
  const handleReset = () => {
    setOutline([]);
    setBlockedZones([]);
    setEntrance(null);
    setTempPoints([]);
    setResults(null);
    setMode('DRAW_OUTLINE');
    setAlgorithm('v1');
  };

  const handleUndoLastPoint = () => {
    if (tempPoints.length > 0) {
      setTempPoints(tempPoints.slice(0, -1));
    }

    else if (blockedZones.length > 0) {
      const lastZone = blockedZones[blockedZones.length - 1];
      setBlockedZones(blockedZones.slice(0, -1));
      setTempPoints(lastZone.slice(0, -1));
      setMode('DRAW_BLOCKED');
    }

    else if (outline.length > 0){ 
      setTempPoints(outline.slice(0, -1));
      setOutline([]);
      setMode('DRAW_OUTLINE');
    }

  };

  return (
    <div className="app-container">
      <aside className="glass-sidebar">
        <div className="sidebar-header">
          <h1>Parking Organizer</h1>
        </div>

        <div className="sidebar-content">
          {/* Algorithm Selection */}
          <div className="algorithm-selection" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <h2 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>Optimization Algorithm</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <button 
                className={`btn btn-secondary ${algorithm === 'v1' ? 'active' : ''}`}
                style={{ padding: '0.6rem', fontSize: '0.85rem' }}
                onClick={() => handleAlgoChange('v1')}
              >
                Standard (V1)
              </button>
              <button 
                className={`btn btn-secondary ${algorithm === 'v2' ? 'active' : ''}`}
                style={{ padding: '0.6rem', fontSize: '0.85rem' }}
                onClick={() => handleAlgoChange('v2')}
              >
                Mixed (V2)
              </button>
            </div>
          </div>

          {/* Mode Controls */}
          <div className="tool-grid">
            <button 
              className={`btn btn-secondary ${mode === 'DRAW_OUTLINE' ? 'active' : ''}`}
              onClick={() => {
                setTempPoints([]);
                setMode('DRAW_OUTLINE');
              }}
            >
              Draw Outline
            </button>
            <button 
              className={`btn btn-secondary ${mode === 'DRAW_BLOCKED' ? 'active' : ''}`}
              disabled={outline.length < 3}
              onClick={() => {
                setTempPoints([]);
                setMode('DRAW_BLOCKED');
              }}
            >
              Draw Blocked Zone
            </button>
            <button 
              className={`btn btn-secondary ${mode === 'PLACE_ENTRANCE' ? 'active' : ''}`}
              disabled={outline.length < 3}
              onClick={() => {
                setTempPoints([]);
                setMode('PLACE_ENTRANCE');
              }}
            >
              Set Entrance
            </button>

            <button 
              className="btn btn-secondary"
              disabled={tempPoints.length === 0 && blockedZones.length === 0 && outline.length === 0}
              onClick={handleUndoLastPoint} 
            >
              Undo Last Point
            </button>


          </div>

          {/* Stats Display */}
          {results && results.stats && (
            <div className="stats-grid" style={{ marginTop: '1.5rem' }}>
              <div className="stat-card">
                <span className="stat-value primary">{results.stats.spotCount}</span>
                <span className="stat-label">Total Spots</span>
              </div>
              <div className="stat-card">
                <span className="stat-value accent">{(results.stats.efficiency * 100).toFixed(1)}%</span>
                <span className="stat-label">Efficiency</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{results.stats.basementArea.toFixed(1)}m²</span>
                <span className="stat-label">Basement Area</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{results.stats.roadArea.toFixed(1)}m²</span>
                <span className="stat-label">Road Area</span>
              </div>
            </div>
          )}

          <div style={{ marginTop: '2rem' }}>
            <button className="btn btn-danger" onClick={handleReset}>Reset</button>
          </div>
        </div>

        <div className="sidebar-footer">
          <button className="btn btn-primary" style={{ width: '100%' }} onClick={handleOptimize}>
            Generate Layout
          </button>
        </div>
      </aside>

      <main className="main-viewport">
        <ParkingCanvas
          outline={outline}
          setOutline={setOutline}
          blockedZones={blockedZones}
          setBlockedZones={setBlockedZones}
          entrance={entrance}
          setEntrance={setEntrance}
          mode={mode}
          setMode={setMode}
          results={results}
          tempPoints={tempPoints}
          setTempPoints={setTempPoints}
        />
      </main>
    </div>
  );
}
