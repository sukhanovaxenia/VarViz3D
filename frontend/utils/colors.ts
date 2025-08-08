// frontend/utils/colors.ts

// Pathogenicity color scheme based on clinical standards
export const PATHOGENICITY_COLORS = {
    pathogenic: '#d32f2f',          // Red
    likely_pathogenic: '#f57c00',    // Orange
    uncertain_significance: '#fbc02d', // Yellow
    likely_benign: '#388e3c',        // Green
    benign: '#1976d2',               // Blue
    unknown: '#9e9e9e'               // Gray
  } as const;
  
  // Alternative color schemes for accessibility
  export const PATHOGENICITY_COLORS_ACCESSIBLE = {
    pathogenic: '#b71c1c',           // Darker red
    likely_pathogenic: '#e65100',     // Darker orange
    uncertain_significance: '#f9a825', // Darker yellow
    likely_benign: '#2e7d32',         // Darker green
    benign: '#1565c0',                // Darker blue
    unknown: '#616161'                // Darker gray
  } as const;
  
  // 3D structure visualization colors
  export const STRUCTURE_COLORS = {
    default: '#cccccc',
    highlight: '#ffeb3b',
    domain: {
      dna_binding: '#2196f3',
      kinase: '#4caf50',
      transmembrane: '#ff9800',
      zinc_finger: '#9c27b0',
      other: '#607d8b'
    },
    secondary_structure: {
      helix: '#ff1744',
      sheet: '#ffd600',
      turn: '#00e676',
      coil: '#cccccc'
    }
  } as const;
  
  // Score-based color gradients
  export const SCORE_GRADIENTS = {
    cadd: [
      { threshold: 0, color: '#4caf50' },    // Green (benign)
      { threshold: 10, color: '#8bc34a' },
      { threshold: 15, color: '#cddc39' },
      { threshold: 20, color: '#ffeb3b' },   // Yellow (moderate)
      { threshold: 25, color: '#ffc107' },
      { threshold: 30, color: '#ff9800' },
      { threshold: 35, color: '#ff5722' },   // Orange (deleterious)
      { threshold: 40, color: '#f44336' }    // Red (highly deleterious)
    ],
    conservation: [
      { threshold: -5, color: '#1976d2' },   // Blue (not conserved)
      { threshold: -2, color: '#42a5f5' },
      { threshold: 0, color: '#66bb6a' },
      { threshold: 2, color: '#ffca28' },    // Yellow (moderately conserved)
      { threshold: 4, color: '#ff7043' },
      { threshold: 6, color: '#ef5350' }     // Red (highly conserved)
    ]
  } as const;
  
  // Main function to get pathogenicity color
  export function getPathogenicityColor(
    pathogenicity: string | null | undefined,
    useAccessible: boolean = false
  ): string {
    if (!pathogenicity) return PATHOGENICITY_COLORS.unknown;
    
    const colors = useAccessible ? PATHOGENICITY_COLORS_ACCESSIBLE : PATHOGENICITY_COLORS;
    const key = pathogenicity.toLowerCase().replace(/ /g, '_') as keyof typeof PATHOGENICITY_COLORS;
    
    return colors[key] || colors.unknown;
  }
  
  // Get color for numeric scores
  export function getScoreColor(
    score: number | null | undefined,
    type: 'cadd' | 'sift' | 'polyphen' | 'conservation'
  ): string {
    if (score === null || score === undefined) {
      return PATHOGENICITY_COLORS.unknown;
    }
  
    // SIFT: lower scores are more deleterious (opposite of others)
    if (type === 'sift') {
      if (score <= 0.05) return PATHOGENICITY_COLORS.pathogenic;
      return PATHOGENICITY_COLORS.benign;
    }
  
    // PolyPhen-2: 0-1 scale
    if (type === 'polyphen') {
      if (score >= 0.85) return PATHOGENICITY_COLORS.pathogenic;
      if (score >= 0.15) return PATHOGENICITY_COLORS.uncertain_significance;
      return PATHOGENICITY_COLORS.benign;
    }
  
    // CADD and conservation: use gradients
    const gradients = type === 'cadd' ? SCORE_GRADIENTS.cadd : SCORE_GRADIENTS.conservation;
    
    for (let i = gradients.length - 1; i >= 0; i--) {
      if (score >= gradients[i].threshold) {
        return gradients[i].color;
      }
    }
    
    return gradients[0].color;
  }
  
  // Get color for allele frequency
  export function getFrequencyColor(frequency: number | null | undefined): string {
    if (frequency === null || frequency === undefined) {
      return PATHOGENICITY_COLORS.unknown;
    }
  
    // Common variants (>1%) - likely benign
    if (frequency > 0.01) return PATHOGENICITY_COLORS.benign;
    
    // Low frequency (0.1-1%) - possibly benign
    if (frequency > 0.001) return PATHOGENICITY_COLORS.likely_benign;
    
    // Rare (0.01-0.1%) - uncertain
    if (frequency > 0.0001) return PATHOGENICITY_COLORS.uncertain_significance;
    
    // Very rare (<0.01%) - possibly pathogenic
    return PATHOGENICITY_COLORS.likely_pathogenic;
  }
  
  // Generate color scale for heatmaps
  export function generateColorScale(
    startColor: string,
    endColor: string,
    steps: number = 10
  ): string[] {
    const start = hexToRgb(startColor);
    const end = hexToRgb(endColor);
    
    if (!start || !end) return [];
    
    const colors: string[] = [];
    
    for (let i = 0; i < steps; i++) {
      const ratio = i / (steps - 1);
      const r = Math.round(start.r + (end.r - start.r) * ratio);
      const g = Math.round(start.g + (end.g - start.g) * ratio);
      const b = Math.round(start.b + (end.b - start.b) * ratio);
      colors.push(rgbToHex(r, g, b));
    }
    
    return colors;
  }
  
  // Utility functions
  function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : null;
  }
  
  function rgbToHex(r: number, g: number, b: number): string {
    return '#' + [r, g, b].map(x => {
      const hex = x.toString(16);
      return hex.length === 1 ? '0' + hex : hex;
    }).join('');
  }
  
  // Get contrasting text color (black or white) based on background
  export function getContrastingTextColor(backgroundColor: string): string {
    const rgb = hexToRgb(backgroundColor);
    if (!rgb) return '#000000';
    
    // Calculate luminance
    const luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
    
    return luminance > 0.5 ? '#000000' : '#ffffff';
  }
  
  // Domain color assignment
  export function getDomainColor(domainType: string): string {
    const normalizedType = domainType.toLowerCase();
    
    for (const [key, color] of Object.entries(STRUCTURE_COLORS.domain)) {
      if (normalizedType.includes(key.replace('_', ' '))) {
        return color;
      }
    }
    
    return STRUCTURE_COLORS.domain.other;
  }
  
  // Export color palette for use in charts
  export const CHART_COLORS = {
    primary: ['#2196f3', '#f44336', '#4caf50', '#ff9800', '#9c27b0'],
    secondary: ['#03a9f4', '#e91e63', '#8bc34a', '#ffc107', '#673ab7'],
    tertiary: ['#00bcd4', '#ff5722', '#cddc39', '#ff5722', '#3f51b5']
  };
  
  // Opacity utilities
  export function addOpacity(color: string, opacity: number): string {
    const rgb = hexToRgb(color);
    if (!rgb) return color;
    
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${opacity})`;
  }
  
  // Theme-aware colors
  export function getThemedColor(
    lightColor: string,
    darkColor: string,
    isDarkMode: boolean
  ): string {
    return isDarkMode ? darkColor : lightColor;
  }