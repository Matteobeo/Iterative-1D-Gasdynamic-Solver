import { v4 as uuidv4 } from 'uuid';

export const COMPONENT_TYPES = {
  convergent: {
    label: "Convergent Nozzle",
    color: "var(--comp-convergent)",
    icon: "↘️",
    defaultParams: { d_in: 0.1, d_out: 0.05, length: 0.2 }
  },
  divergent: {
    label: "Divergent Nozzle",
    color: "var(--comp-divergent)",
    icon: "↗️",
    defaultParams: { d_in: 0.05, d_out: 0.15, length: 0.4 }
  },
  fanno: {
    label: "Fanno Duct (Friction)",
    color: "var(--comp-fanno)",
    icon: "〰️",
    defaultParams: { d_h: 0.05, length: 1.0, f: 0.005 }
  },
  rayleigh: {
    label: "Rayleigh Duct (Heat)",
    color: "var(--comp-rayleigh)",
    icon: "🔥",
    defaultParams: { d_h: 0.05, length: 0.5, q: 50000 }
  }
};

export const createComponent = (type, prevDOut = null) => {
  const params = { ...COMPONENT_TYPES[type].defaultParams };
  
  if (prevDOut !== null) {
    if (type === 'convergent' || type === 'divergent') {
      params.d_in = prevDOut;
      // Maintain logical defaults based on d_in
      if (type === 'convergent') params.d_out = prevDOut / 2;
      if (type === 'divergent') params.d_out = prevDOut * 2;
    } else {
      params.d_h = prevDOut;
    }
  }
  
  return {
    id: uuidv4(),
    type,
    params
  };
};
