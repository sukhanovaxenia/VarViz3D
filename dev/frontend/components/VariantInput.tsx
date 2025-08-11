// frontend/components/VariantInput.tsx
import React, { useState, useCallback } from 'react';
import {
  Box,
  TextField,
  Button,
  Grid,
  Paper,
  Typography,
  IconButton,
  Chip,
  Alert,
  CircularProgress,
  Autocomplete,
  Tabs,
  Tab,
  TextareaAutosize
} from '@mui/material';
import {
  AddCircleOutline,
  DeleteOutline,
  CloudUploadOutlined,
  PlayArrowOutlined,
  InfoOutlined
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';

interface Variant {
  chromosome: string;
  position: number;
  reference: string;
  alternate: string;
}

interface VariantInputProps {
  gene: string;
  onGeneChange: (gene: string) => void;
  variants: Variant[];
  onVariantsChange: (variants: Variant[]) => void;
  onAnalyze: () => void;
  loading?: boolean;
}

// Common gene suggestions for autocomplete
const COMMON_GENES = [
  'TP53', 'BRCA1', 'BRCA2', 'EGFR', 'KRAS', 'PIK3CA', 
  'PTEN', 'APC', 'VHL', 'RB1', 'MLH1', 'MSH2', 'BRAF'
];

export function VariantInput({
  gene,
  onGeneChange,
  variants,
  onVariantsChange,
  onAnalyze,
  loading = false
}: VariantInputProps) {
  const [inputTab, setInputTab] = useState(0);
  const [manualVariant, setManualVariant] = useState<Partial<Variant>>({
    chromosome: '',
    position: undefined,
    reference: '',
    alternate: ''
  });
  const [hgvsInput, setHgvsInput] = useState('');
  const [vcfText, setVcfText] = useState('');
  const [error, setError] = useState('');

  // File upload handler
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        parseVCF(text);
      };
      reader.readAsText(file);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/vcf': ['.vcf'],
      'text/plain': ['.txt']
    },
    maxFiles: 1
  });

  // Parse VCF content
  const parseVCF = (vcfContent: string) => {
    try {
      const lines = vcfContent.split('\n');
      const newVariants: Variant[] = [];
      
      for (const line of lines) {
        if (line.startsWith('#') || !line.trim()) continue;
        
        const [chrom, pos, , ref, alt] = line.split('\t');
        if (chrom && pos && ref && alt) {
          newVariants.push({
            chromosome: chrom.replace('chr', ''),
            position: parseInt(pos),
            reference: ref,
            alternate: alt.split(',')[0] // Take first alt if multiple
          });
        }
      }
      
      onVariantsChange([...variants, ...newVariants]);
      setVcfText('');
      setError('');
    } catch (err) {
      setError('Error parsing VCF file');
    }
  };

  // Parse HGVS notation
  const parseHGVS = (hgvs: string) => {
    try {
      // Simple HGVS parser for demo
      // Format: chr17:g.7577120G>A
      const match = hgvs.match(/chr(\d+):g\.(\d+)([A-Z])>([A-Z])/);
      if (match) {
        const [, chr, pos, ref, alt] = match;
        return {
          chromosome: chr,
          position: parseInt(pos),
          reference: ref,
          alternate: alt
        };
      }
      throw new Error('Invalid HGVS format');
    } catch (err) {
      setError('Invalid HGVS notation. Use format: chr17:g.7577120G>A');
      return null;
    }
  };

  // Add variant manually
  const addManualVariant = () => {
    if (manualVariant.chromosome && manualVariant.position && 
        manualVariant.reference && manualVariant.alternate) {
      onVariantsChange([...variants, manualVariant as Variant]);
      setManualVariant({
        chromosome: '',
        position: undefined,
        reference: '',
        alternate: ''
      });
      setError('');
    } else {
      setError('Please fill all variant fields');
    }
  };

  // Add HGVS variants
  const addHGVSVariants = () => {
    const hgvsLines = hgvsInput.split('\n').filter(line => line.trim());
    const newVariants: Variant[] = [];
    
    for (const hgvs of hgvsLines) {
      const variant = parseHGVS(hgvs.trim());
      if (variant) {
        newVariants.push(variant);
      }
    }
    
    if (newVariants.length > 0) {
      onVariantsChange([...variants, ...newVariants]);
      setHgvsInput('');
      setError('');
    }
  };

  // Remove variant
  const removeVariant = (index: number) => {
    onVariantsChange(variants.filter((_, i) => i !== index));
  };

  // Load demo data
  const loadDemoData = () => {
    onGeneChange('TP53');
    onVariantsChange([
      { chromosome: '17', position: 7577120, reference: 'G', alternate: 'A' },
      { chromosome: '17', position: 7577538, reference: 'C', alternate: 'T' },
      { chromosome: '17', position: 7578406, reference: 'C', alternate: 'T' }
    ]);
  };

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Gene Input */}
        <Grid item xs={12} md={6}>
          <Autocomplete
            value={gene}
            onChange={(_, value) => onGeneChange(value || '')}
            options={COMMON_GENES}
            freeSolo
            renderInput={(params) => (
              <TextField
                {...params}
                label="Gene Symbol"
                placeholder="e.g., TP53, BRCA1"
                fullWidth
                helperText="Enter a HUGO gene symbol"
              />
            )}
          />
        </Grid>

        {/* Demo Data Button */}
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', height: '56px' }}>
            <Button
              variant="outlined"
              onClick={loadDemoData}
              startIcon={<InfoOutlined />}
            >
              Load Demo Data
            </Button>
            <Typography variant="body2" color="text.secondary">
              Try with TP53 variants
            </Typography>
          </Box>
        </Grid>

        {/* Variant Input Methods */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Tabs value={inputTab} onChange={(_, v) => setInputTab(v)}>
              <Tab label="Manual Input" />
              <Tab label="HGVS Notation" />
              <Tab label="VCF Upload" />
              <Tab label="Paste VCF" />
            </Tabs>

            <Box sx={{ mt: 3 }}>
              {/* Manual Input Tab */}
              {inputTab === 0 && (
                <Grid container spacing={2} alignItems="center">
                  <Grid item xs={12} sm={2}>
                    <TextField
                      label="Chromosome"
                      value={manualVariant.chromosome}
                      onChange={(e) => setManualVariant({
                        ...manualVariant,
                        chromosome: e.target.value
                      })}
                      placeholder="17"
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <TextField
                      label="Position"
                      type="number"
                      value={manualVariant.position || ''}
                      onChange={(e) => setManualVariant({
                        ...manualVariant,
                        position: parseInt(e.target.value)
                      })}
                      placeholder="7577120"
                      fullWidth
                    />
                  </Grid>
                  <Grid item xs={12} sm={2}>
                    <TextField
                      label="Reference"
                      value={manualVariant.reference}
                      onChange={(e) => setManualVariant({
                        ...manualVariant,
                        reference: e.target.value.toUpperCase()
                      })}
                      placeholder="G"
                      fullWidth
                      inputProps={{ maxLength: 10 }}
                    />
                  </Grid>
                  <Grid item xs={12} sm={2}>
                    <TextField
                      label="Alternate"
                      value={manualVariant.alternate}
                      onChange={(e) => setManualVariant({
                        ...manualVariant,
                        alternate: e.target.value.toUpperCase()
                      })}
                      placeholder="A"
                      fullWidth
                      inputProps={{ maxLength: 10 }}
                    />
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <Button
                      variant="contained"
                      onClick={addManualVariant}
                      startIcon={<AddCircleOutline />}
                      fullWidth
                    >
                      Add Variant
                    </Button>
                  </Grid>
                </Grid>
              )}

              {/* HGVS Input Tab */}
              {inputTab === 1 && (
                <Box>
                  <TextField
                    multiline
                    rows={4}
                    value={hgvsInput}
                    onChange={(e) => setHgvsInput(e.target.value)}
                    placeholder="chr17:g.7577120G>A&#10;chr17:g.7577538C>T"
                    fullWidth
                    helperText="Enter HGVS notations, one per line"
                  />
                  <Button
                    variant="contained"
                    onClick={addHGVSVariants}
                    startIcon={<AddCircleOutline />}
                    sx={{ mt: 2 }}
                  >
                    Add HGVS Variants
                  </Button>
                </Box>
              )}

              {/* VCF Upload Tab */}
              {inputTab === 2 && (
                <Box
                  {...getRootProps()}
                  sx={{
                    border: '2px dashed #ccc',
                    borderRadius: 2,
                    p: 4,
                    textAlign: 'center',
                    cursor: 'pointer',
                    backgroundColor: isDragActive ? 'action.hover' : 'background.paper'
                  }}
                >
                  <input {...getInputProps()} />
                  <CloudUploadOutlined sx={{ fontSize: 48, color: 'text.secondary' }} />
                  <Typography variant="h6" sx={{ mt: 2 }}>
                    {isDragActive
                      ? 'Drop the VCF file here'
                      : 'Drag & drop a VCF file, or click to select'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Supports .vcf and .txt files
                  </Typography>
                </Box>
              )}

              {/* Paste VCF Tab */}
              {inputTab === 3 && (
                <Box>
                  <TextField
                    multiline
                    rows={6}
                    value={vcfText}
                    onChange={(e) => setVcfText(e.target.value)}
                    placeholder="#CHROM&#9;POS&#9;ID&#9;REF&#9;ALT&#10;chr17&#9;7577120&#9;.&#9;G&#9;A"
                    fullWidth
                    helperText="Paste VCF content here"
                    sx={{ fontFamily: 'monospace' }}
                  />
                  <Button
                    variant="contained"
                    onClick={() => parseVCF(vcfText)}
                    startIcon={<AddCircleOutline />}
                    sx={{ mt: 2 }}
                  >
                    Parse VCF
                  </Button>
                </Box>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Error Display */}
        {error && (
          <Grid item xs={12}>
            <Alert severity="error" onClose={() => setError('')}>
              {error}
            </Alert>
          </Grid>
        )}

        {/* Current Variants */}
        {variants.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Current Variants ({variants.length})
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {variants.map((variant, index) => (
                  <Chip
                    key={index}
                    label={`chr${variant.chromosome}:${variant.position} ${variant.reference}>${variant.alternate}`}
                    onDelete={() => removeVariant(index)}
                    color="primary"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Analyze Button */}
        <Grid item xs={12}>
          <Button
            variant="contained"
            size="large"
            onClick={onAnalyze}
            disabled={!gene || variants.length === 0 || loading}
            startIcon={loading ? <CircularProgress size={20} /> : <PlayArrowOutlined />}
            fullWidth
            sx={{ height: 56 }}
          >
            {loading ? 'Analyzing...' : 'Analyze Variants'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}