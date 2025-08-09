// frontend/components/InteractiveLollipopPlot.tsx

import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import { Box, Paper, CircularProgress } from '@mui/material';

interface Variant {
  protein_position: number;
  amino_acid_change: string;
  pathogenicity: string;
  cadd_score?: number;
  gnomad_af?: number;
  clinvar_significance?: string;
  // MyVariant.info data
  myvariant_data?: any;
}

export function InteractiveLollipopPlot({ 
  gene, 
  variants,
  proteinLength = 500 
}: {
  gene: string;
  variants: Variant[];
  proteinLength?: number;
}) {
  const [selectedVariant, setSelectedVariant] = useState<Variant | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch additional data from MyVariant when variant is clicked
  const fetchVariantDetails = async (variant: Variant) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/myvariant/${variant.amino_acid_change}`);
      const data = await response.json();
      setSelectedVariant({ ...variant, myvariant_data: data });
    } catch (error) {
      console.error('Error fetching variant details:', error);
    }
    setLoading(false);
  };

  // Prepare data for Plotly
  const x = variants.map(v => v.protein_position);
  const y = variants.map(v => v.cadd_score || 10); // Use CADD score for height
  const text = variants.map(v => v.amino_acid_change);
  const colors = variants.map(v => {
    switch (v.pathogenicity) {
      case 'pathogenic': return '#d32f2f';
      case 'likely_pathogenic': return '#f57c00';
      case 'uncertain_significance': return '#fbc02d';
      case 'likely_benign': return '#388e3c';
      case 'benign': return '#1976d2';
      default: return '#9e9e9e';
    }
  });

  // Lollipop plot data
  const data = [
    // Protein backbone
    {
      x: [0, proteinLength],
      y: [0, 0],
      mode: 'lines',
      line: { color: 'gray', width: 4 },
      showlegend: false,
      hoverinfo: 'skip'
    },
    // Variant lollipops
    {
      x: x,
      y: y,
      mode: 'markers+text',
      marker: {
        size: 12,
        color: colors,
        line: { color: 'black', width: 1 }
      },
      text: text,
      textposition: 'top',
      customdata: variants,
      hovertemplate: 
        '<b>%{text}</b><br>' +
        'Position: %{x}<br>' +
        'CADD Score: %{y}<br>' +
        '<extra></extra>',
      type: 'scatter'
    },
    // Stems
    ...variants.map((v, i) => ({
      x: [v.protein_position, v.protein_position],
      y: [0, v.cadd_score || 10],
      mode: 'lines',
      line: { color: colors[i], width: 2 },
      showlegend: false,
      hoverinfo: 'skip'
    }))
  ];

  const layout = {
    title: `${gene} Protein Variants`,
    xaxis: {
      title: 'Protein Position',
      range: [-10, proteinLength + 10]
    },
    yaxis: {
      title: 'CADD Score',
      range: [-2, 40]
    },
    height: 400,
    hovermode: 'closest',
    // Add protein domains as shapes
    shapes: [
      // Example domain annotation
      {
        type: 'rect',
        x0: 100,
        y0: -1,
        x1: 200,
        y1: 1,
        fillcolor: 'lightblue',
        opacity: 0.3,
        line: { width: 0 },
        layer: 'below'
      }
    ],
    annotations: [
      {
        x: 150,
        y: -1.5,
        text: 'DNA Binding Domain',
        showarrow: false
      }
    ]
  };

  const config = {
    responsive: true,
    displayModeBar: true,
    toImageButtonOptions: {
      format: 'svg',
      filename: `${gene}_variants`
    }
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Plot
        data={data}
        layout={layout}
        config={config}
        onSelected={(event) => {
          if (event.points && event.points.length > 0) {
            const variant = event.points[0].customdata as Variant;
            fetchVariantDetails(variant);
          }
        }}
        onClick={(event) => {
          if (event.points && event.points.length > 0) {
            const variant = (event.points[0] as any).customdata as Variant;
            fetchVariantDetails(variant);
          }
        }}
      />
      
      {/* Variant details panel */}
      {selectedVariant && (
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <h3>Selected Variant: {selectedVariant.amino_acid_change}</h3>
          {loading ? (
            <CircularProgress size={20} />
          ) : (
            <>
              <p>Position: {selectedVariant.protein_position}</p>
              <p>Pathogenicity: {selectedVariant.pathogenicity}</p>
              {selectedVariant.myvariant_data && (
                <>
                  <p>ClinVar: {selectedVariant.myvariant_data.clinvar?.clinical_significance}</p>
                  <p>gnomAD AF: {selectedVariant.myvariant_data.gnomad?.af?.toExponential(2)}</p>
                  <p>SIFT: {selectedVariant.myvariant_data.dbnsfp?.sift?.score}</p>
                </>
              )}
            </>
          )}
        </Box>
      )}
    </Paper>
  );
}