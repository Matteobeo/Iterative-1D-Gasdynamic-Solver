import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Trash2 } from 'lucide-react';
import { COMPONENT_TYPES } from '../../utils/componentTypes.jsx';

export function ComponentBlock({ id, component, index, onUpdate, onRemove }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 100 : 1,
    opacity: isDragging ? 0.8 : 1,
  };

  const compDef = COMPONENT_TYPES[component.type];

  const handleParamChange = (key, value) => {
    onUpdate(id, {
      ...component,
      params: { ...component.params, [key]: value }
    });
  };

  return (
    <div 
      ref={setNodeRef} 
      style={style} 
      className={`component-block ${isDragging ? 'dragging' : ''} ${component.type === 'solid_grain' ? 'solid-grain-block' : ''}`}
    >
      <div className="comp-header">
        <div className="comp-title">
          <div 
            {...attributes} 
            {...listeners} 
            style={{ cursor: 'grab', padding: '0.25rem', borderRadius: '4px', display: 'flex', alignItems: 'center' }}
          >
            <GripVertical size={18} style={{ color: 'var(--text-muted)' }} />
          </div>
          <span className="badge" style={{ backgroundColor: `${compDef.color}20`, color: compDef.color }}>
            {compDef.icon} {compDef.label}
          </span>
        </div>
        <div className="comp-actions">
          <button onClick={() => onRemove(id)} className="icon-btn danger" title="Remove component">
            <Trash2 size={16} />
          </button>
        </div>
      </div>
      
      <div className="comp-params">
        {Object.entries(component.params).map(([key, val]) => {
          const SOLID_GRAIN_LABELS = {
            rho_b: { label: 'ρ_b (Density)', unit: 'kg/m³' },
            A_b: { label: 'A_b (Burn Area)', unit: 'm²' },
            n: { label: 'n (Press. Exp.)', unit: '' },
            a_coeff: { label: 'a (Temp. Coeff.)', unit: '' },
            T_b: { label: 'T_b (Grain Temp.)', unit: 'K' },
          };

          let displayLabel = key;
          let unitLabel = '';

          if (SOLID_GRAIN_LABELS[key] && component.type === 'solid_grain') {
            displayLabel = SOLID_GRAIN_LABELS[key].label;
            unitLabel = SOLID_GRAIN_LABELS[key].unit;
          } else if (key === 'q') {
            unitLabel = '[J/kg]';
          } else if (key.includes('length') || key.includes('d_')) {
            unitLabel = '[m]';
          }

          return (
            <div key={key} className="param-group">
              <label>
                {displayLabel} {unitLabel && <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>{unitLabel}</span>}
              </label>
              <input 
                type="number" 
                step="any"
                className="input-field" 
                value={val}
                onChange={(e) => handleParamChange(key, e.target.value)}
              />
            </div>
          );
        })}
      </div>
      
      <div style={{ position: 'absolute', bottom: '-20px', left: '50%', transform: 'translateX(-50%)', zIndex: 0 }}>
        <div style={{ width: '4px', height: '32px', backgroundColor: 'var(--border-color)' }}></div>
      </div>
    </div>
  );
}
