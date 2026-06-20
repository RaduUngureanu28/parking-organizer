import React, { useRef, useState } from 'react';

export default function ParkingCanvas({
  outline,
  setOutline,
  blockedZones,
  setBlockedZones,
  entrance,
  setEntrance,
  mode,
  setMode,
  results,
  tempPoints,
  setTempPoints,
  hoveredBlockedZone,
  setHoveredBlockedZone
}) {
  const svgRef = useRef(null);
  const [isDraggingEntrance, setIsDraggingEntrance] = useState(false);
  const [draggingVertex, setDraggingVertex] = useState(null);
  const [draggingZone, setDraggingZone] = useState(null); 
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });

  const handleVertexMouseDown = (e, type, index, zoneIndex = null) => {
    e.stopPropagation();
    e.preventDefault();
    setDraggingVertex({ type, index, zoneIndex });
  };

  const handleZoneMouseDown = (e, type, zoneIndex = null) => {
    e.stopPropagation();
    e.preventDefault();
    const coords = getCoordinates(e);
    setDraggingZone({ type, zoneIndex, lastCoords: coords });
  };

  // Map mouse clicks from screen space to SVG coordinates (10px = 1m)
  const getCoordinates = (e) => {
    if (!svgRef.current) return { x: 0, y: 0 };
    try {
      const pt = svgRef.current.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      // Transform client coordinates using the inverse of the screen CTM (Coordinate Transform Matrix)
      const svgPoint = pt.matrixTransform(svgRef.current.getScreenCTM().inverse());
      return {
        x: Math.round(svgPoint.x),
        y: Math.round(svgPoint.y)
      };
    } catch (err) {
      // Fallback in case matrix CTM is unavailable
      const rect = svgRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 1000;
      const y = ((e.clientY - rect.top) / rect.height) * 700;
      return { x: Math.round(x), y: Math.round(y) };
    }
  };

  const getNearestPointOnSegment = (p, a, b) => {
    const atob = { x: b.x - a.x, y: b.y - a.y };
    const atop = { x: p.x - a.x, y: p.y - a.y };
    const lenSq = atob.x * atob.x + atob.y * atob.y;
    
    if (lenSq === 0) return a;
    
    let t = (atop.x * atob.x + atop.y * atob.y) / lenSq;
    t = Math.max(0, Math.min(1, t));
    
    return {
      x: Math.round(a.x + t * atob.x),
      y: Math.round(a.y + t * atob.y)
    };
  };
  
  // Find the closest point on the entire outer outline polygon
  const getNearestPointOnPolygon = (point, poly) => {
    if (!poly || poly.length === 0) return point;
    
    let minDistance = Infinity;
    let nearestPoint = poly[0];
    
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i];
      const b = poly[(i + 1) % poly.length];
      const proj = getNearestPointOnSegment(point, a, b);
      
      const dist = Math.hypot(point.x - proj.x, point.y - proj.y);
      if (dist < minDistance) {
        minDistance = dist;
        nearestPoint = proj;
      }
    }
    return nearestPoint;
  };

  const handleEntranceMouseDown = (e) => {
    e.stopPropagation();
    setIsDraggingEntrance(true);
  };

  const handleCanvasMouseMove = (e) => {
    const coords = getCoordinates(e);
    setCursorPos(coords);
    
    if (isDraggingEntrance && outline.length >= 3) {
      const snappedPoint = getNearestPointOnPolygon(coords, outline);
      setEntrance(snappedPoint);
    }

    else if (draggingVertex) {
      if (draggingVertex.type === 'outline') {
        const updated = [...outline];
        updated[draggingVertex.index] = coords;
        setOutline(updated);

        if (entrance) {
          const snappedEntrance = getNearestPointOnPolygon(entrance, updated);
          setEntrance(snappedEntrance);

        }
      }

      else if (draggingVertex.type === 'blocked') {
        const updatedZones = [...blockedZones];
        updatedZones[draggingVertex.zoneIndex][draggingVertex.index] = coords;
        setBlockedZones(updatedZones); 
      }
    }

    else if (draggingZone) {
      const dx = coords.x - draggingZone.lastCoords.x;
      const dy = coords.y - draggingZone.lastCoords.y;

      if (dx !== 0 || dy !== 0) {
        if (draggingZone.type === 'outline') {
          const updated = outline.map(p => ({x: p.x + dx, y: p.y + dy}));
          setOutline(updated);

          if (entrance) {
            setEntrance(prev => prev ? { x: prev.x + dx, y: prev.y + dy } : null);
          }
        }
        else if (draggingZone.type === 'blocked') {
          const updatedZones = [...blockedZones];
          updatedZones[draggingZone.zoneIndex] = updatedZones[draggingZone.zoneIndex].map(p => ({x: p.x + dx, y: p.y + dy}));
          setBlockedZones(updatedZones);
        }
        setDraggingZone(prev => ({ ...prev, lastCoords: coords }));
      }
    }
    
  };

  const handleCanvasMouseUp = () => {
    setIsDraggingEntrance(false);
    setDraggingVertex(null);
    setDraggingZone(null);
  };


  const handleCanvasClick = (e) => {
    const coords = getCoordinates(e);

    if (mode === 'DRAW_OUTLINE') {
      if (tempPoints.length >= 3) {
        const first = tempPoints[0];
        const distance = Math.hypot(coords.x - first.x, coords.y - first.y);

        if (distance < 15) {
          setOutline(tempPoints);
          setTempPoints([]);
          setMode('VIEW_RESULTS');
          return;
        }
      }
      setTempPoints([...tempPoints, coords]);
    }

    else if (mode == 'DRAW_BLOCKED') {
      if (tempPoints.length >= 3) {
        const first = tempPoints[0];
        const distance = Math.hypot(coords.x - first.x, coords.y - first.y);

        if (distance < 15) {
          setBlockedZones([...blockedZones, tempPoints]);
          setTempPoints([]);
          setMode('VIEW_RESULTS');
          return;
        }
      }
      setTempPoints([...tempPoints, coords]);
    }

    else if (mode == 'PLACE_ENTRANCE') {
       if (outline.length < 3) {
          return;
       }

       const snappedPoint = getNearestPointOnPolygon(coords, outline);
       setEntrance(snappedPoint);
       setMode('VIEW_RESULTS');
    }
  }

  const filteredSpots = results?.spots
    ? results.spots.filter(
        spot => !blockedZones.some(zone => arePolygonsIntersecting(spot, zone))
      )
    : [];

  return (
      <div className="canvas-container">
        <svg
          ref={svgRef}
          viewBox="0 0 1000 700"
          className="canvas-svg"
          onClick={handleCanvasClick}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
        >
          {/* Grid pattern, background */}

          {/* Outline Polygon */}
          {outline.length >= 3 && (
            <polygon
              points={outline.map(p => `${p.x},${p.y}`).join(' ')}
              className="svg-outline"
              style={
                mode === 'VIEW_RESULTS'
                  ? { cursor: draggingZone?.type === 'outline' ? 'grabbing' : 'grab' }
                  : { pointerEvents: 'none' }
              }
              onMouseDown={
                mode === 'VIEW_RESULTS'
                  ? (e) => handleZoneMouseDown(e, 'outline')
                  : undefined
              }
            />
          )}


          {/* Temporary Drawing Line */}
          {tempPoints.length > 0 && (
          <>
            <polyline
              points={[...tempPoints, cursorPos].map(p => `${p.x},${p.y}`).join(' ')}
              fill="none"
              stroke={mode === 'DRAW_BLOCKED' ? "var(--color-danger)" : "var(--color-primary)"}
              strokeWidth={3}
              style={{ strokeDasharray: '6 4' }}
            />
            {tempPoints.map((p, idx) => (
              <circle
                key={idx}
                cx={p.x}
                cy={p.y}
                r={5}
                fill={idx === 0 ? (mode === 'DRAW_BLOCKED' ? "var(--color-danger)" : "var(--color-primary)") : "#FFF"}
              />
            ))}
          </>
          )}

          {/* Render Generated Roads (unfiltered) */}
          {results?.roads && results.roads.map((road, rIdx) => (
            <polygon
              key={`road-${rIdx}`}
              points={road.map(p => `${p.x},${p.y}`).join(' ')}
              className="svg-road"
            />
          ))}

          {/* Blocked Zone Background Masks (to visually clip/cover roads underneath) */}
          {blockedZones.map((zone, zIdx) => (
            <polygon
              key={`road-mask-${zIdx}`}
              points={zone.map(p => `${p.x},${p.y}`).join(' ')}
              fill="#0d1220"
              stroke="none"
              style={{ pointerEvents: 'none' }}
            />
          ))}

          {/* Render Generated Parking Spots (filtered to completely hide overlapping ones) */}
          {filteredSpots.map((spot, sIdx) => {
            const xs = spot.map(p => p.x);
            const ys = spot.map(p => p.y);
            const cx = xs.reduce((a, b) => a + b, 0) / spot.length;
            const cy = ys.reduce((a, b) => a + b, 0) / spot.length;

            return (
              <g key={`spot-${sIdx}`}>
                <polygon
                  points={spot.map(p => `${p.x},${p.y}`).join(' ')}
                  className="svg-spot"
                />
                <text
                  x={cx}
                  y={cy}
                  className="svg-spot-text"
                  dominantBaseline="central"
                >
                  {sIdx + 1}
                </text>
              </g>
            );
          })}

           {/*Render Blocked Zone Polygons */}
          {blockedZones.map((zone, zIdx) => {
            const isHovered = hoveredBlockedZone === zIdx;
            return (
              <polygon
                key={zIdx}
                points={zone.map(p => `${p.x},${p.y}`).join(' ')}
                className={`svg-blocked ${isHovered ? 'hovered' : ''}`}
                style={
                  mode === 'VIEW_RESULTS'
                    ? { 
                        cursor: (draggingZone?.type === 'blocked' && draggingZone?.zoneIndex === zIdx) ? 'grabbing' : 'pointer',
                        fill: isHovered ? 'rgba(239, 68, 68, 0.35)' : 'rgba(239, 68, 68, 0.15)',
                        stroke: isHovered ? '#EF4444' : 'var(--color-danger)',
                        strokeWidth: isHovered ? 3 : 2,
                        transition: 'all 0.15s ease'
                      }
                    : { pointerEvents: 'none' }
                }
                onMouseDown={
                  mode === 'VIEW_RESULTS'
                    ? (e) => handleZoneMouseDown(e, 'blocked', zIdx)
                    : undefined
                }
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  if (mode === 'VIEW_RESULTS') {
                    setBlockedZones(blockedZones.filter((_, i) => i !== zIdx));
                    setHoveredBlockedZone(null);
                    setDraggingZone(null);
                    setDraggingVertex(null);
                  }
                }}
                onMouseEnter={() => mode === 'VIEW_RESULTS' && setHoveredBlockedZone(zIdx)}
                onMouseLeave={() => mode === 'VIEW_RESULTS' && setHoveredBlockedZone(null)}
              >
                <title>Double-click to delete this blocked zone</title>
              </polygon>
            );
          })}

          {/*Render Entrance Marker */}
          {entrance && (
            <g>
              <circle
                cx={entrance.x}
                cy={entrance.y}
                r={10}
                className="svg-entrance"
                onMouseDown={handleEntranceMouseDown}
                style={{ cursor: 'grab' }}
              />
              <path
                d={`M ${entrance.x} ${entrance.y - 15} L ${entrance.x} ${entrance.y + 15} M ${entrance.x - 5} ${entrance.y + 10} L ${entrance.x} ${entrance.y + 15} L ${entrance.x + 5} ${entrance.y + 10}`}
                stroke="#FFF"
                strokeWidth={3}
                fill="none"
              />
            </g>
          )}

          {mode === 'VIEW_RESULTS' && outline.map((p, idx) => (
            <circle
              key={`handle-outline-${idx}`}
              cx={p.x}
              cy={p.y}
              r={6}
              fill="#1E293B"
              stroke="#6366F1"
              strokeWidth={2.5}
              style={{ cursor: 'grab' }}
              onMouseDown={(e) => handleVertexMouseDown(e, 'outline', idx)}
            />
          ))}

          {/* Draggable Handles for Blocked Zone Vertices */}
          {mode === 'VIEW_RESULTS' && blockedZones.map((zone, zIdx) =>
            zone.map((p, idx) => (
              <circle
                key={`handle-blocked-${zIdx}-${idx}`}
                cx={p.x}
                cy={p.y}
                r={6}
                fill="#1E293B"
                stroke="#EF4444"
                strokeWidth={2.5}
                style={{ cursor: 'grab' }}
                onMouseDown={(e) => handleVertexMouseDown(e, 'blocked', idx, zIdx)}
              />
            ))
          )}

          {/* Coordinates Tooltip near Cursor */}
          {(mode === 'DRAW_OUTLINE' || mode === 'DRAW_BLOCKED') && (
            <g style={{ pointerEvents: 'none' }}>
              <rect
                x={cursorPos.x + 12}
                y={cursorPos.y - 32}
                width={90}
                height={20}
                rx={4}
                fill="rgba(15, 23, 42, 0.9)"
                stroke="rgba(255, 255, 255, 0.15)"
                strokeWidth={1}
              />
              <text
                x={cursorPos.x + 57}
                y={cursorPos.y - 22}
                fill="#FFF"
                fontSize={9}
                fontWeight="600"
                textAnchor="middle"
                dominantBaseline="central"
              >
                {`${(cursorPos.x / 10).toFixed(1)}m, ${(cursorPos.y / 10).toFixed(1)}m`}
              </text>
            </g>
          )}

          {/* Active Segment Length Ruler */}
          {(mode === 'DRAW_OUTLINE' || mode === 'DRAW_BLOCKED') && tempPoints.length > 0 && (() => {
            const lastPoint = tempPoints[tempPoints.length - 1];
            const dx = cursorPos.x - lastPoint.x;
            const dy = cursorPos.y - lastPoint.y;
            const length = (Math.hypot(dx, dy) / 10).toFixed(1);
            const midX = (lastPoint.x + cursorPos.x) / 2;
            const midY = (lastPoint.y + cursorPos.y) / 2 - 12;

            return (
              <g style={{ pointerEvents: 'none' }}>
                <rect
                  x={midX - 25}
                  y={midY - 10}
                  width={50}
                  height={18}
                  rx={4}
                  fill="rgba(15, 23, 42, 0.95)"
                  stroke={mode === 'DRAW_BLOCKED' ? "var(--color-danger)" : "var(--color-primary)"}
                  strokeWidth={1}
                />
                <text
                  x={midX}
                  y={midY - 1}
                  fill="#FFF"
                  fontSize={10}
                  fontWeight="bold"
                  textAnchor="middle"
                  dominantBaseline="central"
                >
                  {length}m
                </text>
              </g>
            );
          })()}

          {/* Edge Lengths when Dragging a Vertex */}
          {draggingVertex && (() => {
            const isOutline = draggingVertex.type === 'outline';
            const poly = isOutline ? outline : blockedZones[draggingVertex.zoneIndex];
            if (!poly || poly.length < 2) return null;

            const i = draggingVertex.index;
            const prevIdx = (i - 1 + poly.length) % poly.length;
            const nextIdx = (i + 1) % poly.length;

            const pCurr = poly[i];
            const pPrev = poly[prevIdx];
            const pNext = poly[nextIdx];

            const renderEdgeLabel = (p1, p2, key) => {
              const dx = p2.x - p1.x;
              const dy = p2.y - p1.y;
              const length = (Math.hypot(dx, dy) / 10).toFixed(1);
              const midX = (p1.x + p2.x) / 2;
              const midY = (p1.y + p2.y) / 2 - 12;

              return (
                <g key={key} style={{ pointerEvents: 'none' }}>
                  <rect
                    x={midX - 25}
                    y={midY - 10}
                    width={50}
                    height={18}
                    rx={4}
                    fill="rgba(15, 23, 42, 0.95)"
                    stroke={isOutline ? "var(--color-primary)" : "var(--color-danger)"}
                    strokeWidth={1.5}
                  />
                  <text
                    x={midX}
                    y={midY - 1}
                    fill="#FFF"
                    fontSize={10}
                    fontWeight="bold"
                    textAnchor="middle"
                    dominantBaseline="central"
                  >
                    {length}m
                  </text>
                </g>
              );
            };

            return (
              <>
                {renderEdgeLabel(pPrev, pCurr, 'edge-prev')}
                {poly.length > 2 && renderEdgeLabel(pCurr, pNext, 'edge-next')}
              </>
            );
          })()}


        </svg>
      </div>
    );
  }

  // Helper functions for 2D polygon intersection
  function isPointInPolygon(pt, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i].x, yi = poly[i].y;
      const xj = poly[j].x, yj = poly[j].y;
      
      const intersect = ((yi > pt.y) !== (yj > pt.y))
          && (pt.x < (xj - xi) * (pt.y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  function doSegmentsIntersect(p1, q1, p2, q2) {
    function ccw(A, B, C) {
      return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x);
    }
    return (ccw(p1, p2, q2) !== ccw(q1, p2, q2)) && (ccw(p1, q1, p2) !== ccw(p1, q1, q2));
  }

  function arePolygonsIntersecting(polyA, polyB) {
    // 1. Check if any vertex of polyA is inside polyB
    for (const pt of polyA) {
      if (isPointInPolygon(pt, polyB)) return true;
    }
    // 2. Check if any vertex of polyB is inside polyA
    for (const pt of polyB) {
      if (isPointInPolygon(pt, polyA)) return true;
    }
    // 3. Check if any segment of polyA intersects any segment of polyB
    for (let i = 0; i < polyA.length; i++) {
      const a1 = polyA[i];
      const a2 = polyA[(i + 1) % polyA.length];
      for (let j = 0; j < polyB.length; j++) {
        const b1 = polyB[j];
        const b2 = polyB[(j + 1) % polyB.length];
        if (doSegmentsIntersect(a1, a2, b1, b2)) return true;
      }
    }
    return false;
  }

