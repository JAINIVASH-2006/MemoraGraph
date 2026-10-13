import { useState, useEffect, useCallback, useMemo } from 'react';
import type { FormEvent } from 'react';
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, type Node, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Search, Share2, Info, Sparkles, Loader, RefreshCw, Layers, Database } from 'lucide-react';
import { searchGraphEntities, getGraphNeighbors } from '../services/api';
import type { GraphNode } from '../types';

// Distinctive color palettes by entity type
const getNodeColor = (type?: string) => {
  switch (type) {
    case 'Project':
      return { bg: '#0f766e', border: '#14b8a6', text: '#5eead4', badge: 'bg-teal-900/60 text-teal-300 border-teal-700/50' };
    case 'Employee':
      return { bg: '#0369a1', border: '#38bdf8', text: '#7dd3fc', badge: 'bg-sky-900/60 text-sky-300 border-sky-700/50' };
    case 'Risk':
      return { bg: '#b45309', border: '#f59e0b', text: '#fcd34d', badge: 'bg-amber-900/60 text-amber-300 border-amber-700/50' };
    case 'Decision':
      return { bg: '#6d28d9', border: '#a855f7', text: '#d8b4fe', badge: 'bg-purple-900/60 text-purple-300 border-purple-700/50' };
    case 'Department':
      return { bg: '#15803d', border: '#22c55e', text: '#86efac', badge: 'bg-emerald-900/60 text-emerald-300 border-emerald-700/50' };
    case 'Meeting':
      return { bg: '#4338ca', border: '#818cf8', text: '#c7d2fe', badge: 'bg-indigo-900/60 text-indigo-300 border-indigo-700/50' };
    case 'Technology':
      return { bg: '#0e7490', border: '#22d3ee', text: '#a5f3fc', badge: 'bg-cyan-900/60 text-cyan-300 border-cyan-700/50' };
    case 'Document':
      return { bg: '#334155', border: '#64748b', text: '#cbd5e1', badge: 'bg-slate-800 text-slate-300 border-slate-600/50' };
    default:
      return { bg: '#1e293b', border: '#475569', text: '#cbd5e1', badge: 'bg-slate-800 text-slate-300 border-slate-600/50' };
  }
};

export default function GraphExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<GraphNode[]>([]);
  const [allEntities, setAllEntities] = useState<GraphNode[]>([]);
  const [selectedType, setSelectedType] = useState<string>('ALL');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingGraph, setLoadingGraph] = useState(false);

  // Position helper (circular layout for neighbors)
  const layoutNodes = useCallback((centerNode: GraphNode, neighbors: GraphNode[], currentEdges: any[]) => {
    const newNodes: Node[] = [];
    const centerColor = getNodeColor(centerNode.type);
    
    // Set center node
    newNodes.push({
      id: centerNode.id,
      position: { x: 300, y: 250 },
      data: { label: `${centerNode.type}: ${centerNode.label}`, properties: centerNode.properties },
      style: {
        background: centerColor.bg,
        color: '#ffffff',
        border: `2px solid ${centerColor.border}`,
        borderRadius: '10px',
        padding: '12px 14px',
        fontSize: '11px',
        fontWeight: 'bold',
        width: 160,
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 0 15px rgba(139, 92, 246, 0.3)',
        textAlign: 'center',
      },
    });

    // Circular layout for neighbors
    const validNeighbors = neighbors.filter((n) => n.id !== centerNode.id);
    const radius = Math.max(190, validNeighbors.length * 28);
    validNeighbors.forEach((n, index) => {
      const angle = (index / Math.max(1, validNeighbors.length)) * 2 * Math.PI;
      const x = 300 + radius * Math.cos(angle);
      const y = 250 + radius * Math.sin(angle);
      const color = getNodeColor(n.type);

      newNodes.push({
        id: n.id,
        position: { x, y },
        data: { label: `${n.type}: ${n.label}`, properties: n.properties },
        style: {
          background: color.bg,
          color: '#ffffff',
          border: `1px solid ${color.border}`,
          borderRadius: '8px',
          padding: '8px 12px',
          fontSize: '10px',
          fontWeight: 600,
          width: 140,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
          textAlign: 'center',
        },
      });
    });

    // Format Edges
    const newEdges: Edge[] = currentEdges.map((e, idx) => ({
      id: e.id || `e-${idx}`,
      source: e.source,
      target: e.target,
      label: e.type,
      style: { stroke: '#64748b', strokeWidth: 1.8 },
      labelStyle: { fill: '#cbd5e1', fontSize: 9, fontWeight: 700 },
      animated: true,
    }));

    setNodes(newNodes);
    setEdges(newEdges);
  }, [setNodes, setEdges]);

  // Select an entity and center it with its neighbors
  const selectSeedNode = useCallback(async (gn: GraphNode) => {
    setLoadingGraph(true);
    try {
      const res = await getGraphNeighbors(gn.id);
      layoutNodes(gn, res.nodes, res.edges);
      setSelectedNode({
        id: gn.id,
        position: { x: 300, y: 250 },
        data: { label: `${gn.type}: ${gn.label}`, properties: gn.properties },
      });
    } catch (err) {
      console.error('Failed loading neighbors:', err);
    } finally {
      setLoadingGraph(false);
    }
  }, [layoutNodes]);

  // Load live entities from Neo4j knowledge graph
  const loadEntities = useCallback(async (autoSelect = false) => {
    setLoading(true);
    try {
      const res = await searchGraphEntities('', undefined, 100);
      const entities = res.entities || [];
      setAllEntities(entities);
      
      // Auto-select the first entity to populate the workspace on first load
      if (autoSelect && entities.length > 0) {
        selectSeedNode(entities[0]);
      }
    } catch (err) {
      console.error('Failed to load knowledge graph entities:', err);
    } finally {
      setLoading(false);
    }
  }, [selectSeedNode]);

  // Initial fetch on mount
  useEffect(() => {
    loadEntities(true);
  }, [loadEntities]);

  // Expand node when clicked on canvas
  const handleNodeClick = useCallback(async (_event: any, node: Node) => {
    setSelectedNode(node);
    try {
      const centerNode: GraphNode = {
        id: node.id,
        label: (node.data.label as string).split(':')[1]?.trim() || (node.data.label as string),
        type: (node.data.label as string).split(':')[0]?.trim() || 'Entity',
        properties: (node.data.properties || {}) as any,
      };
      const res = await getGraphNeighbors(node.id);
      layoutNodes(centerNode, res.nodes, res.edges);
    } catch (err) {
      console.error('Failed to expand neighbors:', err);
    }
  }, [layoutNodes]);

  // Debounced search when typing query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await searchGraphEntities(searchQuery.trim(), undefined, 50);
        setSearchResults(res.entities || []);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const res = await searchGraphEntities(searchQuery.trim(), undefined, 50);
      setSearchResults(res.entities || []);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setLoading(false);
    }
  };

  // Unique entity types present in the knowledge graph
  const availableTypes = useMemo(() => {
    const types = Array.from(new Set(allEntities.map((e) => e.type))).filter(Boolean);
    return ['ALL', ...types.sort()];
  }, [allEntities]);

  // Filtered entity list to display in sidebar
  const displayedEntities = useMemo(() => {
    if (searchQuery.trim()) {
      return searchResults;
    }
    if (selectedType === 'ALL') {
      return allEntities;
    }
    return allEntities.filter((e) => e.type === selectedType);
  }, [searchQuery, searchResults, selectedType, allEntities]);

  return (
    <div className="page flex flex-row h-[calc(100vh-80px)] p-0">
      {/* Search and Node Info sidebar */}
      <div className="w-[340px] bg-[var(--color-bg-card)] border-r border-[var(--color-border)] flex flex-col h-full shadow-lg">
        {/* Search Header */}
        <div className="p-4 border-b border-[var(--color-border)] space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-sm font-bold text-[var(--color-text-primary)] uppercase tracking-wider flex items-center gap-2">
                <Share2 size={16} className="text-violet-400" />
                Graph Explorer
              </h1>
              <p className="text-[10px] text-[var(--color-text-muted)]">
                {allEntities.length} active entities indexed in graph
              </p>
            </div>
            <button
              onClick={() => loadEntities(false)}
              title="Refresh entities from graph"
              className="p-1.5 rounded-lg border border-[var(--color-border)] hover:border-violet-500 bg-[var(--color-bg-secondary)] hover:bg-[var(--color-bg-card-hover)] text-[var(--color-text-secondary)] hover:text-violet-300 transition"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>

          <form onSubmit={handleSearch} className="relative">
            <input
              type="text"
              placeholder="Search graph (e.g. Aurora, Arun, Security)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full py-1.5 pl-8 pr-3 bg-[var(--color-bg-input)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-xs rounded-lg placeholder-slate-500 focus:outline-none focus:border-violet-500"
            />
            <Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={12} />
          </form>

          {/* Type Filter Chips */}
          {!searchQuery.trim() && availableTypes.length > 1 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {availableTypes.map((t) => (
                <button
                  key={t}
                  onClick={() => setSelectedType(t)}
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition ${
                    selectedType === t
                      ? 'bg-violet-600 text-white border-violet-500'
                      : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] border-[var(--color-border)] hover:border-slate-500 hover:text-[var(--color-text-primary)]'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Entities list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <div className="flex justify-center items-center py-6 gap-2 text-[var(--color-text-muted)] text-xs">
              <Loader className="animate-spin" size={14} />
              Loading knowledge graph...
            </div>
          )}

          {/* List Header */}
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase font-bold text-[var(--color-text-muted)] tracking-wider flex items-center gap-1.5">
              <Layers size={11} className="text-violet-400" />
              {searchQuery.trim() ? `Search Results (${displayedEntities.length})` : `Indexed Entities (${displayedEntities.length})`}
            </span>
          </div>

          {displayedEntities.length === 0 && !loading && (
            <div className="text-center py-8 px-4 text-[var(--color-text-muted)] text-xs space-y-2">
              <Database size={24} className="mx-auto text-slate-500 opacity-60" />
              <p className="font-semibold text-[var(--color-text-secondary)]">No entities found</p>
              <p className="text-[11px]">
                {searchQuery.trim()
                  ? `No entity matching "${searchQuery}"`
                  : 'Upload documents in the Document Database to populate the knowledge graph.'}
              </p>
            </div>
          )}

          {displayedEntities.map((entity) => {
            const color = getNodeColor(entity.type);
            const isSelected = selectedNode?.id === entity.id;
            return (
              <button
                key={entity.id}
                onClick={() => selectSeedNode(entity)}
                className={`w-full p-2.5 rounded-lg border text-left text-xs transition duration-200 flex justify-between items-center cursor-pointer ${
                  isSelected
                    ? 'bg-violet-950/40 border-violet-500 shadow-sm shadow-violet-900/30'
                    : 'bg-[var(--color-bg-secondary)] hover:bg-[var(--color-bg-card-hover)] border-[var(--color-border)] hover:border-violet-600'
                }`}
              >
                <div className="min-w-0 pr-2">
                  <span className={`inline-block px-1.5 py-0.2 text-[9px] font-bold rounded border uppercase mb-0.5 ${color.badge}`}>
                    {entity.type}
                  </span>
                  <span className="text-[var(--color-text-primary)] font-semibold block truncate">
                    {entity.label}
                  </span>
                </div>
                <Sparkles size={13} className={isSelected ? 'text-violet-400' : 'text-slate-500 opacity-50'} />
              </button>
            );
          })}

          {/* Selected Node Properties Panel */}
          {selectedNode && (
            <div className="mt-4 p-4 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl space-y-3">
              <h2 className="text-xs font-bold text-[var(--color-text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                <Info size={14} className="text-violet-400" />
                Entity Attributes
              </h2>
              <div className="space-y-2 text-xs">
                <div>
                  <span className="text-[var(--color-text-muted)] uppercase text-[9px] block">Label</span>
                  <span className="text-[var(--color-text-primary)] font-medium">
                    {(selectedNode.data.label as string)?.split(':')[1]?.trim() || String(selectedNode.data.label ?? '')}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--color-text-muted)] uppercase text-[9px] block">Type</span>
                  <span className="text-[var(--color-text-primary)] font-medium">
                    {(selectedNode.data.label as string).split(':')[0]?.trim()}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--color-text-muted)] uppercase text-[9px] block">Entity ID</span>
                  <span className="text-[var(--color-text-primary)] font-mono text-[10px] break-all">{selectedNode.id}</span>
                </div>
                {(selectedNode.data as any).properties &&
                  Object.entries((selectedNode.data as any).properties).map(([k, v]: any) => (
                    <div key={k}>
                      <span className="text-[var(--color-text-muted)] uppercase text-[9px] block">{k}</span>
                      <span className="text-[var(--color-text-primary)] font-medium">{String(v)}</span>
                    </div>
                  ))}
              </div>
              <div className="text-[9px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-2 italic">
                Tip: Click any neighbor node in the canvas to center and explore its connections.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Canvas workspace container */}
      <div className="flex-1 bg-[var(--color-bg-secondary)] h-full relative">
        {loadingGraph && (
          <div className="absolute top-4 right-4 z-20 flex items-center gap-2 bg-slate-900/80 backdrop-blur border border-violet-500/40 text-violet-300 px-3 py-1.5 rounded-lg text-xs shadow-lg">
            <Loader size={13} className="animate-spin text-violet-400" />
            Loading connections...
          </div>
        )}

        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col justify-center items-center text-center p-8 space-y-3 z-10">
            <Share2 className="text-[var(--color-text-muted)] animate-pulse" size={64} />
            <h2 className="text-[var(--color-text-primary)] font-semibold text-sm">Interactive Knowledge Graph Workspace</h2>
            <p className="text-[var(--color-text-secondary)] text-xs max-w-xs">
              Select an entity from the sidebar or search to visualize connected entities and relationships.
            </p>
          </div>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          fitView
          style={{ width: '100%', height: '100%' }}
        >
          <Controls />
          <MiniMap nodeStrokeWidth={3} zoomable pannable />
          <Background color="#94a3b8" gap={16} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}
