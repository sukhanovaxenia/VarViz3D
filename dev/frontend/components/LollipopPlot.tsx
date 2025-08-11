// frontend/components/LollipopPlot.tsx
import React, { useEffect, useRef } from 'react';
import g3viz from 'g3viz';
import { Box, Paper } from '@mui/material';
import { getPathogenicityColor } from '../utils/colors';

interface LollipopPlotProps {
  gene: string;
  variants: any[];
  domains?: any[];
}

export function LollipopPlot({ gene, variants, domains }: LollipopPlotProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || !gene || !variants.length) return;

    // Clear previous chart
    if (chartRef.current) {
      containerRef.current.innerHTML = '';
    }

    // Transform variants for g3viz
    const g3vizData = variants.map(v => ({
      protein_position: v.protein_position,
      mutation_type: v.variant_type,
      count: 1,
      color: getPathogenicityColor(v.pathogenicity),
      tooltip: `
        <div>
          <strong>${v.amino_acid_change || v.hgvs_g}</strong><br/>
          Pathogenicity: ${v.pathogenicity || 'Unknown'}<br/>
          CADD: ${v.cadd_score?.toFixed(2) || 'N/A'}<br/>
          gnomAD AF: ${v.gnomad_af?.toExponential(2) || 'N/A'}
        </div>
      `
    }));

    // Create lollipop plot
    chartRef.current = g3viz.lollipop({
      element: containerRef.current,
      gene: gene,
      mutations: g3vizData,
      options: {
        legend: true,
        zoom: true,
        brush: true,
        tooltip: true,
        height: 300
      }
    });

  }, [gene, variants]);

  return (
    <Paper elevation={2} sx={{ p: 2 }}>
      <Box ref={containerRef} sx={{ width: '100%', minHeight: 400 }} />
    </Paper>
  );
}