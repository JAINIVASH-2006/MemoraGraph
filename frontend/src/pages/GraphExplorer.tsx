import { useState, useCallback } from 'react';
import type { FormEvent } from 'react';
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, type Node, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Search, Share2, Info, Sparkles, Loader } from 'lucide-react';
import { searchGraphEntities, getGraphNeighbors } from '../services/api';
import type { GraphNode } from '../types';

export default function GraphExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<GraphNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [loading, setLoading] = useState(false);

  // Position helper (circular layout for neighbors)
  const layoutNodes = (centerNode: GraphNode, neighbors: GraphNode[], currentEdges: any[]) => {
    const newNodes: Node[] = [];
    
    // Set center node
    newNodes.push({
      id: centerNode.id,
      position: { x: 250, y: 250 },
      data: { label: `${centerNode.type}: ${centerNode.label}` },
      style: {
        background: '#8b5cf6',
        color: '#fff',
        border: '1px solid #7c3aed',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '11px',
        fontWeight: 'bold',
        width: 150,
      },
    });

    // Circular layout for neighbors
    const radius = 200;
    neighbors.forEach((n, index) => {
      if (n.id === centerNode.id) return;
      const angle = (index / Math.max(1, neighbors.length)) * 2 * Math.PI;
      const x = 250 + radius * Math.cos(angle);
      const y = 250 + radius * Math.sin(angle);

      // Determine style by NodeType
      let bg = '#1e293b';
      let border = '#334155';
      if (n.type === 'Employee') { bg = '#0369a1'; border = '#0284c7'; }
      if (n.type === 'Project') { bg = '#0f766e'; border = '#0d9488'; }
      if (n.type === 'Risk') { bg = '#b45309'; border = '#d97706'; }
      if (n.type === 'Decision') { bg = '#6d28d9'; border = '#7c3aed'; }

      newNodes.push({
        id: n.id,
        position: { x, y },
        data: { label: `${n.type}: ${n.label}`, properties: n.properties },
        style: {
          background: bg,
          color: '#fff',
          border: `1px solid ${border}`,
          borderRadius: '6px',
          padding: '8px',
          fontSize: '10px',
          width: 130,
        },
      });
    });

    // Format Edges
    const newEdges: Edge[] = currentEdges.map((e, idx) => ({
      id: e.id || `e-${idx}`,
      source: e.source,
      target: e.target,
      label: e.type,
      style: { stroke: '#64748b', strokeWidth: 1.5 },
      labelStyle: { fill: '#94a3b8', fontSize: 9, fontWeight: 700 },
    }));

    setNodes(newNodes);
    setEdges(newEdges);
  };

  const handleNodeClick = useCallback(async (_event: any, node: Node) => {
    setSelectedNode(node);
    try {
      const centerNode: GraphNode = {
        id: node.id,
        label: node.data.label as string,
        type: (node.data.label as string).split(':')[0],
        properties: (node.data.properties || {}) as any,
      };
      const res = await getGraphNeighbors(node.id);
      
      // Update nodes/edges layout preserving neighbors
      layoutNodes(centerNode, res.nodes, res.edges);
    } catch (err) {
      console.error('Failed to expand neighbors:', err);
    }
  }, [setNodes, setEdges]);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const res = await searchGraphEntities(searchQuery);
      setSearchResults(res.entities);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const selectSeedNode = async (gn: GraphNode) => {
    setLoading(true);
    try {
      const res = await getGraphNeighbors(gn.id);
      layoutNodes(gn, res.nodes, res.edges);
      setSelectedNode({
        id: gn.id,
        position: { x: 250, y: 250 },
        data: { label: `${gn.type}: ${gn.label}`, properties: gn.properties },
      });
      setSearchResults([]);
      setSearchQuery('');
    } catch (err) {
      console.error('Failed loading neighbors:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page flex flex-row h-[calc(100vh-80px)] p-0">
      {/* Search and Node Info sidebar */}
      <div className="w-[320px] bg-[var(--color-bg-card)] border-r border-[var(--color-border)] flex flex-col h-full">
        {/* Search Header */}
        <div className="p-4 border-b border-[var(--color-border)] space-y-3">
          <div>
            <h1 className="text-sm font-bold text-[var(--color-text-primary)] uppercase tracking-wider flex items-center gap-2">
              <Share2 size={16} className="text-violet-400" />
              Graph Explorer
            </h1>
            <p className="text-[10px] text-[var(--color-text-muted)]">Explore knowledge entities and routed paths</p>
          </div>
          <form onSubmit={handleSearch} className="relative">
            <input
              type="text"
              placeholder="Search graph (e.g. Arun, Alpha)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full py-1.5 pl-8 pr-3 bg-[var(--color-bg-input)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-xs rounded-lg placeholder-slate-500 focus:outline-none focus:border-violet-500"
            />
            <Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={12} />
          </form>
        </div>

        {/* Search Results list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <div className="flex justify-center items-center py-10 gap-2 text-[var(--color-text-muted)] text-xs">
              <Loader className="animate-spin" size={14} />
              Searching database...
            </div>
          )}
          
          {searchResults.map((entity) => (
            <button
              key={entity.id}
              onClick={() => selectSeedNode(entity)}
              className="w-full p-2 bg-[var(--color-bg-secondary)] hover:bg-[var(--color-bg-card-hover)] border border-[var(--color-border)] hover:border-violet-600 rounded text-left text-xs transition duration-200 flex justify-between items-center"
            >
              <div>
                <span className="text-[10px] uppercase font-bold text-violet-400 block">{entity.type}</span>
                <span className="text-[var(--color-text-primary)] font-semibold">{entity.label}</span>
              </div>
              <Sparkles size={12} className="text-[var(--color-text-muted)]" />
            </button>
          ))}

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
                  <span className="text-[var(--color-text-primary)] font-medium">{(selectedNode.data.label as string).split(':')[1]}</span>
                </div>
                <div>
                  <span className="text-[var(--color-text-muted)] uppercase text-[9px] block">Type</span>
                  <span className="text-[var(--color-text-primary)] font-medium">{(selectedNode.data.label as string).split(':')[0]}</span>
                </div>
                <div>
                  <span className="text-[var(--color-text-muted)] uppercase text-[9px] block">Entity ID</span>
                  <span className="text-[var(--color-text-primary)] font-mono text-[10px] break-all">{selectedNode.id}</span>
                </div>
                {(selectedNode.data as any).properties && Object.entries((selectedNode.data as any).properties).map(([k, v]: any) => (
                  <div key={k}>
                    <span className="text-[var(--color-text-muted)] uppercase text-[9px] block">{k}</span>
                    <span className="text-[var(--color-text-primary)] font-medium">{String(v)}</span>
                  </div>
                ))}
              </div>
              <div className="text-[9px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-2 italic">
                Tip: Click any neighboring node in the canvas to center and expand its relationships.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Canvas workspace container */}
      <div className="flex-1 bg-[var(--color-bg-secondary)] h-full relative">
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col justify-center items-center text-center p-8 space-y-3 z-10">
            <Share2 className="text-[var(--color-text-muted)] animate-pulse" size={64} />
            <h2 className="text-[var(--color-text-primary)] font-semibold text-sm">Interactive Knowledge Graph Workspace</h2>
            <p className="text-[var(--color-text-secondary)] text-xs max-w-xs">
              Search for an entity in the sidebar (e.g. "Arun" or "Alpha") to initialize the visual graph workspace.
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
          <Background color="#cbd5e1" gap={16} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}
