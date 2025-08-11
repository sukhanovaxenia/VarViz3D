// frontend/pages/index.tsx
import React, { useState, useCallback } from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  Tabs,
  Tab,
  CircularProgress,
  Alert
} from '@mui/material';
import { VariantInput } from '../components/VariantInput';
import { LollipopPlot } from '../components/LollipopPlot';
import { ProteinStructure3D } from '../components/ProteinStructure3D';
import { VariantTable } from '../components/VariantTable';
import { AnnotationPanel } from '../components/AnnotationPanel';
import { analyzeVariants } from '../utils/api';

export default function Home() {
  const [gene, setGene] = useState('');
  const [variants, setVariants] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(0);

  const handleAnalyze = useCallback(async () => {
    if (!gene || variants.length === 0) {
      setError('Please enter a gene symbol and at least one variant');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await analyzeVariants(gene, variants);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [gene, variants]);

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h3" gutterBottom align="center">
        VarViz3D - Genetic Variant Visualization
      </Typography>
      
      <Grid container spacing={3}>
        {/* Input Section */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <VariantInput
              gene={gene}
              onGeneChange={setGene}
              variants={variants}
              onVariantsChange={setVariants}
              onAnalyze={handleAnalyze}
              loading={loading}
            />
          </Paper>
        </Grid>

        {/* Results Section */}
        {error && (
          <Grid item xs={12}>
            <Alert severity="error">{error}</Alert>
          </Grid>
        )}

        {loading && (
          <Grid item xs={12} sx={{ textAlign: 'center' }}>
            <CircularProgress size={60} />
            <Typography variant="h6" sx={{ mt: 2 }}>
              Analyzing variants...
            </Typography>
          </Grid>
        )}

        {results && !loading && (
          <>
            {/* Visualization Tabs */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2 }}>
                <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
                  <Tab label="2D Protein View" />
                  <Tab label="3D Structure" />
                  <Tab label="Variant Table" />
                  <Tab label="Annotations" />
                </Tabs>

                <Box sx={{ mt: 3 }}>
                  {activeTab === 0 && (
                    <LollipopPlot
                      gene={results.gene}
                      variants={results.variants}
                      domains={results.structure?.domains}
                    />
                  )}
                  
                  {activeTab === 1 && (
                    <ProteinStructure3D
                      structure={results.structure}
                      mappedVariants={results.mapped_variants}
                    />
                  )}
                  
                  {activeTab === 2 && (
                    <VariantTable variants={results.variants} />
                  )}
                  
                  {activeTab === 3 && (
                    <AnnotationPanel
                      variants={results.variants}
                      literature={results.literature}
                    />
                  )}
                </Box>
              </Paper>
            </Grid>
          </>
        )}
      </Grid>
    </Container>
  );
}