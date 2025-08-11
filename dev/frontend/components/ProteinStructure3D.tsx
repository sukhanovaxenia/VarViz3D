// frontend/components/ProteinStructure3D.tsx
import { Viewer } from 'molstar/lib/apps/viewer/app';
import React, { useEffect, useRef } from 'react';
import * as $3Dmol from '3dmol/build/3Dmol-min.js';
import { Box, Paper, IconButton, Tooltip } from '@mui/material';
import { 
  FullscreenOutlined, 
  CameraAltOutlined,
  RestartAltOutlined 
} from '@mui/icons-material';
import { getPathogenicityColor } from '../utils/colors';

interface ProteinStructure3DProps {
  structure: any;
  mappedVariants: any[];
}

export function ProteinStructure3D({ 
  structure, 
  mappedVariants 
}: ProteinStructure3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || !structure) return;

    // Initialize 3Dmol viewer
    const viewer = $3Dmol.createViewer(containerRef.current, {
      backgroundColor: 'white',
      antialias: true,
      cartoonQuality: 10
    });

    // Load structure
    if (structure.source === 'pdb') {
      viewer.addModel(structure.pdb_data, 'pdb');
    } else {
      viewer.addModel(structure.pdb_data, 'pdb');
    }

    // Set default style
    viewer.setStyle({}, {
      cartoon: { 
        color: 'spectrum',
        thickness: 0.5
      }
    });

    // Highlight variants
    mappedVariants?.forEach(mv => {
      const color = getPathogenicityColor(mv.variant.pathogenicity);
      
      // Add sphere at variant position
      viewer.addSphere({
        center: {
          x: mv.structure_position.x,
          y: mv.structure_position.y,
          z: mv.structure_position.z
        },
        radius: 2.0,
        color: color,
        alpha: 0.8
      });

      // Highlight residue
      viewer.setStyle(
        { resi: mv.variant.protein_position },
        {
          cartoon: { color: color, thickness: 1.0 },
          stick: { color: color }
        }
      );

      // Add label
      viewer.addLabel(
        mv.variant.amino_acid_change || `${mv.variant.protein_position}`,
        {
          position: mv.structure_position,
          backgroundColor: color,
          fontColor: 'white',
          fontSize: 12
        }
      );
    });

    viewer.zoomTo();
    viewer.render();
    viewerRef.current = viewer;

    // Cleanup
    return () => {
      viewer.clear();
    };
  }, [structure, mappedVariants]);

  const handleFullscreen = () => {
    if (containerRef.current) {
      containerRef.current.requestFullscreen();
    }
  };

  const handleScreenshot = () => {
    if (viewerRef.current) {
      const dataUrl = viewerRef.current.pngURI();
      const link = document.createElement('a');
      link.download = 'structure.png';
      link.href = dataUrl;
      link.click();
    }
  };

  const handleReset = () => {
    if (viewerRef.current) {
      viewerRef.current.zoomTo();
    }
  };

  return (
    <Paper elevation={2} sx={{ p: 2, position: 'relative' }}>
      <Box sx={{ position: 'absolute', top: 16, right: 16, zIndex: 1 }}>
        <Tooltip title="Reset view">
          <IconButton onClick={handleReset}>
            <RestartAltOutlined />
          </IconButton>
        </Tooltip>
        <Tooltip title="Screenshot">
          <IconButton onClick={handleScreenshot}>
            <CameraAltOutlined />
          </IconButton>
        </Tooltip>
        <Tooltip title="Fullscreen">
          <IconButton onClick={handleFullscreen}>
            <FullscreenOutlined />
          </IconButton>
        </Tooltip>
      </Box>
      
      <Box 
        ref={containerRef} 
        sx={{ 
          width: '100%', 
          height: 600,
          position: 'relative'
        }} 
      />
    </Paper>
  );
}