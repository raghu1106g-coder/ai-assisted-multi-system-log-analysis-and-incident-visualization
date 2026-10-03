import React, { useRef, useEffect, useState } from 'react';
import { Network, ZoomIn, ZoomOut, RotateCcw, Filter, Info, Layers } from 'lucide-react';

interface GraphNode {
  id: string;
  node: string;
  log_family: string;
  event_type: string;
  category?: string;
  severity?: string;
  timestamp: string;
  component?: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface GraphLink {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
  strength: string;
  reason: string;
  confidence: number;
}

interface CorrelationGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}

export const CorrelationGraph: React.FC<CorrelationGraphProps> = ({
  nodes: rawNodes,
  links: rawLinks,
  selectedNodeId,
  onSelectNode,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedFilterType, setSelectedFilterType] = useState<string>('ALL');

  const simulationNodesRef = useRef<GraphNode[]>([]);
  const animationFrameRef = useRef<number | null>(null);

  // Initialize simulation positions
  useEffect(() => {
    if (!rawNodes.length) return;

    const width = 800;
    const height = 500;
    const existingMap = new Map(simulationNodesRef.current.map((n) => [n.id, n]));

    simulationNodesRef.current = rawNodes.map((n, i) => {
      const existing = existingMap.get(n.id);
      if (existing && existing.x !== undefined && existing.y !== undefined) {
        return { ...n, x: existing.x, y: existing.y, vx: 0, vy: 0 };
      }
      // Layout in clusters around node origin
      const angle = (i / rawNodes.length) * 2 * Math.PI;
      const radius = 140 + (i % 3) * 50;
      return {
        ...n,
        x: width / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 30,
        y: height / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 30,
        vx: 0,
        vy: 0,
      };
    });
  }, [rawNodes]);

  // Simulation & rendering loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let iterations = 0;
    const maxIterations = 220;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      const nodes = simulationNodesRef.current;
      const nodeMap = new Map(nodes.map((n) => [n.id, n]));

      // Force layout physics step
      if (iterations < maxIterations) {
        // Node-node repulsion
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const na = nodes[i];
            const nb = nodes[j];
            const dx = (nb.x || 0) - (na.x || 0);
            const dy = (nb.y || 0) - (na.y || 0);
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            if (dist < 160) {
              const force = (160 - dist) / 160;
              const fx = (dx / dist) * force * 1.4;
              const fy = (dy / dist) * force * 1.4;
              na.vx = (na.vx || 0) - fx;
              na.vy = (na.vy || 0) - fy;
              nb.vx = (nb.vx || 0) + fx;
              nb.vy = (nb.vy || 0) + fy;
            }
          }
        }

        // Link spring attraction
        rawLinks.forEach((link) => {
          const sId = typeof link.source === 'string' ? link.source : link.source.id;
          const tId = typeof link.target === 'string' ? link.target : link.target.id;
          const na = nodeMap.get(sId);
          const nb = nodeMap.get(tId);
          if (na && nb) {
            const dx = (nb.x || 0) - (na.x || 0);
            const dy = (nb.y || 0) - (na.y || 0);
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const targetDist = 65;
            const force = (dist - targetDist) * 0.035;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            na.vx = (na.vx || 0) + fx;
            na.vy = (na.vy || 0) + fy;
            nb.vx = (nb.vx || 0) - fx;
            nb.vy = (nb.vy || 0) - fy;
          }
        });

        // Center gravity & velocity dampening
        nodes.forEach((n) => {
          const dx = width / 2 - (n.x || 0);
          const dy = height / 2 - (n.y || 0);
          n.vx = ((n.vx || 0) + dx * 0.006) * 0.82;
          n.vy = ((n.vy || 0) + dy * 0.006) * 0.82;
          n.x = (n.x || 0) + (n.vx || 0);
          n.y = (n.y || 0) + (n.vy || 0);
        });

        iterations++;
      }

      // Draw frame
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(offset.x, offset.y);
      ctx.scale(zoom, zoom);

      // 1. Draw Links
      rawLinks.forEach((link) => {
        if (selectedFilterType !== 'ALL' && link.type !== selectedFilterType) return;

        const sId = typeof link.source === 'string' ? link.source : link.source.id;
        const tId = typeof link.target === 'string' ? link.target : link.target.id;
        const na = nodeMap.get(sId);
        const nb = nodeMap.get(tId);
        if (!na || !nb || na.x === undefined || nb.x === undefined) return;

        const isConnected = sId === selectedNodeId || tId === selectedNodeId;

        ctx.beginPath();
        ctx.moveTo(na.x, na.y!);
        ctx.lineTo(nb.x, nb.y!);

        if (link.type === 'CMD_ACK') {
          ctx.strokeStyle = isConnected ? '#38bdf8' : 'rgba(56, 189, 248, 0.4)';
          ctx.setLineDash([4, 3]);
        } else if (link.type === 'SHARED_PLAN_ID') {
          ctx.strokeStyle = isConnected ? '#c084fc' : 'rgba(192, 132, 252, 0.4)';
          ctx.setLineDash([]);
        } else if (link.type.includes('FAULT') || link.type.includes('CASCADE')) {
          ctx.strokeStyle = isConnected ? '#f87171' : 'rgba(239, 68, 68, 0.5)';
          ctx.setLineDash([]);
        } else {
          ctx.strokeStyle = isConnected ? '#cbd5e1' : 'rgba(100, 116, 139, 0.25)';
          ctx.setLineDash([]);
        }

        ctx.lineWidth = isConnected ? 2 : link.strength === 'STRONG' ? 1.5 : 1;
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // 2. Draw Nodes
      nodes.forEach((n) => {
        if (n.x === undefined || n.y === undefined) return;
        const isSelected = n.id === selectedNodeId;

        // Selection Ring
        if (isSelected) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, 11, 0, 2 * Math.PI);
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(n.x, n.y, 14, 0, 2 * Math.PI);
          ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)';
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Main Node Circle
        ctx.beginPath();
        ctx.arc(n.x, n.y, isSelected ? 6 : 4.5, 0, 2 * Math.PI);

        // Fill by node or category
        if (n.category === 'FAULT' || n.severity === 'CRITICAL' || n.severity === 'ERROR') {
          ctx.fillStyle = '#f87171';
        } else if (n.category === 'RECOVERY') {
          ctx.fillStyle = '#34d399';
        } else if (n.node === 'NODE_A') {
          ctx.fillStyle = '#38bdf8';
        } else if (n.node === 'NODE_B') {
          ctx.fillStyle = '#c084fc';
        } else {
          ctx.fillStyle = '#34d399';
        }

        ctx.fill();
        ctx.strokeStyle = '#090d16';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Node Label
        if (zoom >= 0.85 || isSelected) {
          ctx.fillStyle = isSelected ? '#38bdf8' : '#94a3b8';
          ctx.font = '10px JetBrains Mono, monospace';
          ctx.fillText(n.event_type, n.x + 8, n.y + 3);
        }
      });

      ctx.restore();
      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [rawNodes, rawLinks, selectedNodeId, zoom, offset, selectedFilterType]);

  // Mouse handlers for dragging & clicking
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDragging) {
      setOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = (e.clientX - rect.left - offset.x) / zoom;
    const clickY = (e.clientY - rect.top - offset.y) / zoom;

    // Find clicked node within 12px radius
    for (const n of simulationNodesRef.current) {
      if (n.x !== undefined && n.y !== undefined) {
        const dx = n.x - clickX;
        const dy = n.y - clickY;
        if (Math.sqrt(dx * dx + dy * dy) <= 12) {
          onSelectNode(n.id);
          return;
        }
      }
    }
  };

  const linkTypes = Array.from(new Set(rawLinks.map((l) => l.type)));

  return (
    <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Graph Toolbar */}
      <div className="ops-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Network size={15} color="#c084fc" />
          <span style={{ fontWeight: 700, fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Cross-Node Correlation Topology ({rawNodes.length} Nodes • {rawLinks.length} Edges)
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <select
            value={selectedFilterType}
            onChange={(e) => setSelectedFilterType(e.target.value)}
            className="ops-select"
            style={{ fontSize: '0.74rem' }}
          >
            <option value="ALL">All Edge Types ({rawLinks.length})</option>
            {linkTypes.map((t) => (
              <option key={t} value={t}>
                {t} ({rawLinks.filter((l) => l.type === t).length})
              </option>
            ))}
          </select>

          <button
            className="btn-ops btn-ops-secondary"
            onClick={() => setZoom((z) => Math.min(z * 1.2, 3))}
            style={{ padding: '4px 8px' }}
            title="Zoom In"
          >
            <ZoomIn size={12} />
          </button>
          <button
            className="btn-ops btn-ops-secondary"
            onClick={() => setZoom((z) => Math.max(z / 1.2, 0.4))}
            style={{ padding: '4px 8px' }}
            title="Zoom Out"
          >
            <ZoomOut size={12} />
          </button>
          <button
            className="btn-ops btn-ops-secondary"
            onClick={() => {
              setZoom(1);
              setOffset({ x: 0, y: 0 });
            }}
            style={{ padding: '4px 8px' }}
            title="Reset Canvas View"
          >
            <RotateCcw size={12} />
          </button>
        </div>
      </div>

      {/* Canvas container */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: '#060a14' }}>
        <canvas
          ref={canvasRef}
          width={900}
          height={550}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onClick={handleClick}
          style={{ width: '100%', height: '100%', cursor: isDragging ? 'grabbing' : 'grab' }}
        />

        {/* Floating Legend */}
        <div
          className="ops-panel-subtle"
          style={{
            position: 'absolute',
            bottom: '10px',
            left: '10px',
            padding: '6px 10px',
            fontSize: '0.72rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '3px',
            background: 'rgba(15, 23, 42, 0.9)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#38bdf8' }} />
            <span className="font-mono text-muted">NODE_A</span>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#c084fc', marginLeft: '4px' }} />
            <span className="font-mono text-muted">NODE_B</span>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#34d399', marginLeft: '4px' }} />
            <span className="font-mono text-muted">NODE_C</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#f87171' }} />
            <span className="font-mono text-muted">Fault / Cascade</span>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#34d399', marginLeft: '4px' }} />
            <span className="font-mono text-muted">Recovery</span>
          </div>
        </div>
      </div>
    </div>
  );
};
