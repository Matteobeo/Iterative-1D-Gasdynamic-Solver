import React from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';

import { ComponentBlock } from '../ComponentBlock/ComponentBlock';

export function Canvas({ components, setComponents, config }) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setComponents((items) => {
        const oldIndex = items.findIndex(i => i.id === active.id);
        const newIndex = items.findIndex(i => i.id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };

  const updateComponent = (id, newComp) => {
    setComponents(comps => comps.map(c => c.id === id ? newComp : c));
  };

  const removeComponent = (id) => {
    setComponents(comps => comps.filter(c => c.id !== id));
  };

  return (
    <div className="canvas-area">
      <div className="canvas-wrapper">

        {/* Reservoir box */}
        <div className="boundary-box">
          <span style={{ fontSize: '1.5rem' }}>🔵</span>
          <div>
            <div className="label">Reservoir</div>
            <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>
              P₀ = {Number(config.P0).toLocaleString()} Pa &nbsp;|&nbsp;
              T₀ = {config.T0} K
            </div>
          </div>
        </div>

        {/* Arrow down */}
        <div className="boundary-arrow">↓</div>

        {/* Pipeline */}
        <div className={`pipeline-container ${components.length > 0 ? 'active' : ''}`}>
          <div className="pipeline-header">
            <h3>🔩 Pipeline Assembly</h3>
            <span className="pipeline-badge">
              {components.length} component{components.length !== 1 ? 's' : ''}
              &nbsp;— drag to reorder
            </span>
          </div>

          {components.length === 0 ? (
            <div className="empty-state">
              <div style={{ fontSize: '3rem', opacity: 0.3 }}>🛠️</div>
              <h3 style={{ color: 'var(--text-muted)' }}>Pipeline Empty</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                Click a component in the left panel to add it here.
              </p>
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={components.map(c => c.id)}
                strategy={verticalListSortingStrategy}
              >
                {components.map((comp, index) => (
                  <React.Fragment key={comp.id}>
                    {index > 0 && (
                      <div className="flow-connector">↓ flow</div>
                    )}
                    <ComponentBlock
                      id={comp.id}
                      component={comp}
                      index={index}
                      onUpdate={updateComponent}
                      onRemove={removeComponent}
                    />
                  </React.Fragment>
                ))}
              </SortableContext>
            </DndContext>
          )}
        </div>

        {/* Arrow down to exit */}
        <div className="boundary-arrow">↓</div>

        {/* Exit box */}
        <div className="boundary-box">
          <span style={{ fontSize: '1.5rem' }}>🟡</span>
          <div>
            <div className="label">Ambient Exit</div>
            <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>
              Pₐ = {Number(config.P_amb).toLocaleString()} Pa
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
