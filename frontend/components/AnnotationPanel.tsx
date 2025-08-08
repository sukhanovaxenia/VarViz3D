// frontend/components/AnnotationPanel.tsx
import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Link,
  Grid,
  Card,
  CardContent,
  Divider,
  Button,
  TextField,
  InputAdornment,
  Tooltip,
  Badge,
  Tab,
  Tabs
} from '@mui/material';
import {
  ExpandMoreOutlined,
  ArticleOutlined,
  FunctionsOutlined,
  DomainOutlined,
  LocalPharmacyOutlined,
  BiotechOutlined,
  SearchOutlined,
  OpenInNewOutlined,
  InfoOutlined,
  LabelOutlined,
  ScienceOutlined
} from '@mui/icons-material';

interface AnnotationPanelProps {
  variants: any[];
  literature?: any[];
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

export function AnnotationPanel({ variants, literature = [] }: AnnotationPanelProps) {
  const [expandedVariant, setExpandedVariant] = useState<string | false>(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [tabValue, setTabValue] = useState(0);

  // Filter variants based on search
  const filteredVariants = variants.filter(variant => {
    const search = searchTerm.toLowerCase();
    return !searchTerm || 
      variant.hgvs_g?.toLowerCase().includes(search) ||
      variant.amino_acid_change?.toLowerCase().includes(search) ||
      variant.gene_symbol?.toLowerCase().includes(search);
  });

  // Aggregate GO terms across all variants
  const aggregatedGOTerms = variants.reduce((acc, variant) => {
    if (variant.affected_go_terms) {
      variant.affected_go_terms.forEach((term: any) => {
        const key = term.go_id;
        if (!acc[key]) {
          acc[key] = { ...term, count: 0, variants: [] };
        }
        acc[key].count++;
        acc[key].variants.push(variant.hgvs_g);
      });
    }
    return acc;
  }, {} as Record<string, any>);

  // Sort GO terms by count
  const sortedGOTerms = Object.values(aggregatedGOTerms).sort((a: any, b: any) => b.count - a.count);

  return (
    <Box>
      {/* Search Bar */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <TextField
          fullWidth
          placeholder="Search annotations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlined />
              </InputAdornment>
            )
          }}
        />
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 2 }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          <Tab label="Variant Details" icon={<BiotechOutlined />} iconPosition="start" />
          <Tab label="GO Terms" icon={<FunctionsOutlined />} iconPosition="start" />
          <Tab label="Literature" icon={<ArticleOutlined />} iconPosition="start" />
          <Tab label="Drug Interactions" icon={<LocalPharmacyOutlined />} iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Variant Details Tab */}
      <TabPanel value={tabValue} index={0}>
        {filteredVariants.map((variant, index) => (
          <Accordion
            key={index}
            expanded={expandedVariant === `variant-${index}`}
            onChange={(_, isExpanded) => 
              setExpandedVariant(isExpanded ? `variant-${index}` : false)
            }
            sx={{ mb: 1 }}
          >
            <AccordionSummary expandIcon={<ExpandMoreOutlined />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                <Typography variant="subtitle1" sx={{ fontFamily: 'monospace' }}>
                  {variant.amino_acid_change || variant.hgvs_g}
                </Typography>
                <Chip
                  label={variant.pathogenicity || 'Unknown'}
                  size="small"
                  color={
                    variant.pathogenicity === 'pathogenic' ? 'error' :
                    variant.pathogenicity === 'likely_pathogenic' ? 'warning' :
                    'default'
                  }
                />
                {variant.protein_domain && (
                  <Chip
                    icon={<DomainOutlined />}
                    label={variant.protein_domain.name}
                    size="small"
                    variant="outlined"
                  />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                {/* Basic Information */}
                <Grid item xs={12} md={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle2" color="primary" gutterBottom>
                        Basic Information
                      </Typography>
                      <List dense>
                        <ListItem>
                          <ListItemText
                            primary="Genomic Position"
                            secondary={variant.hgvs_g}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="Transcript"
                            secondary={variant.transcript_id || 'N/A'}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="Variant Type"
                            secondary={variant.variant_type || 'N/A'}
                          />
                        </ListItem>
                      </List>
                    </CardContent>
                  </Card>
                </Grid>

                {/* Prediction Scores */}
                <Grid item xs={12} md={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle2" color="primary" gutterBottom>
                        Prediction Scores
                      </Typography>
                      <List dense>
                        <ListItem>
                          <ListItemText
                            primary="CADD Score"
                            secondary={variant.cadd_score?.toFixed(2) || 'N/A'}
                          />
                          {variant.cadd_score && variant.cadd_score > 20 && (
                            <Chip label="Deleterious" size="small" color="error" />
                          )}
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="SIFT"
                            secondary={variant.sift_score?.toFixed(3) || 'N/A'}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="PolyPhen-2"
                            secondary={variant.polyphen_score?.toFixed(3) || 'N/A'}
                          />
                        </ListItem>
                      </List>
                    </CardContent>
                  </Card>
                </Grid>

                {/* GO Terms */}
                {variant.affected_go_terms && variant.affected_go_terms.length > 0 && (
                  <Grid item xs={12}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="subtitle2" color="primary" gutterBottom>
                          Affected GO Terms
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                          {variant.affected_go_terms.map((term: any, idx: number) => (
                            <Chip
                              key={idx}
                              icon={<FunctionsOutlined />}
                              label={`${term.go_name} (${term.go_id})`}
                              size="small"
                              variant="outlined"
                              component="a"
                              href={`http://amigo.geneontology.org/amigo/term/${term.go_id}`}
                              target="_blank"
                              clickable
                            />
                          ))}
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                )}

                {/* Conservation */}
                <Grid item xs={12}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle2" color="primary" gutterBottom>
                        Conservation Scores
                      </Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={6}>
                          <Typography variant="body2" color="text.secondary">
                            PhyloP Score
                          </Typography>
                          <Typography variant="h6">
                            {variant.phylop_score?.toFixed(2) || 'N/A'}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="body2" color="text.secondary">
                            GERP Score
                          </Typography>
                          <Typography variant="h6">
                            {variant.gerp_score?.toFixed(2) || 'N/A'}
                          </Typography>
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>
        ))}
      </TabPanel>

      {/* GO Terms Tab */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={2}>
          {sortedGOTerms.length > 0 ? (
            sortedGOTerms.map((term: any) => (
              <Grid item xs={12} md={6} key={term.go_id}>
                <Card variant="outlined">
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="subtitle1">
                        {term.go_name}
                      </Typography>
                      <Badge badgeContent={term.count} color="primary">
                        <FunctionsOutlined />
                      </Badge>
                    </Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      {term.go_id} • {term.go_namespace}
                    </Typography>
                    <Typography variant="body2" paragraph>
                      {term.go_definition || 'No description available'}
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="caption" color="text.secondary">
                        Affected in {term.count} variant{term.count > 1 ? 's' : ''}
                      </Typography>
                      <Button
                        size="small"
                        endIcon={<OpenInNewOutlined />}
                        href={`http://amigo.geneontology.org/amigo/term/${term.go_id}`}
                        target="_blank"
                      >
                        View in AmiGO
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))
          ) : (
            <Grid item xs={12}>
              <Typography variant="body1" color="text.secondary" align="center">
                No GO term annotations available for these variants
              </Typography>
            </Grid>
          )}
        </Grid>
      </TabPanel>

      {/* Literature Tab */}
      <TabPanel value={tabValue} index={2}>
        {literature.length > 0 ? (
          <Grid container spacing={2}>
            {literature.map((article, index) => (
              <Grid item xs={12} key={index}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      {article.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" paragraph>
                      {article.authors?.join(', ')} • {article.journal} ({article.year})
                    </Typography>
                    {article.variant_mentions && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" color="primary" gutterBottom>
                          Variant Mentions:
                        </Typography>
                        {article.variant_mentions.map((mention: any, idx: number) => (
                          <Typography key={idx} variant="body2" sx={{ ml: 2 }}>
                            "...{mention.context}..."
                          </Typography>
                        ))}
                      </Box>
                    )}
                    <Box sx={{ display: 'flex', gap: 2 }}>
                      <Button
                        size="small"
                        startIcon={<ArticleOutlined />}
                        href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}`}
                        target="_blank"
                      >
                        PubMed
                      </Button>
                      {article.pmc_id && (
                        <Button
                          size="small"
                          href={`https://www.ncbi.nlm.nih.gov/pmc/articles/${article.pmc_id}`}
                          target="_blank"
                        >
                          Full Text
                        </Button>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        ) : (
          <Typography variant="body1" color="text.secondary" align="center">
            No literature references found for these variants
          </Typography>
        )}
      </TabPanel>

      {/* Drug Interactions Tab */}
      <TabPanel value={tabValue} index={3}>
        <Typography variant="body1" color="text.secondary" align="center">
          Drug interaction data coming soon...
        </Typography>
        <Box sx={{ mt: 2, textAlign: 'center' }}>
          <Button
            variant="outlined"
            startIcon={<LocalPharmacyOutlined />}
            href="https://www.pharmgkb.org/"
            target="_blank"
          >
            Visit PharmGKB
          </Button>
        </Box>
      </TabPanel>
    </Box>
  );
}