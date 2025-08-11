// frontend/components/VariantTable.tsx
import React, { useState, useMemo } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  TextField,
  Chip,
  Tooltip,
  IconButton,
  Button,
  Menu,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Grid,
  Typography,
  LinearProgress
} from '@mui/material';
import {
  FileDownloadOutlined,
  FilterListOutlined,
  InfoOutlined,
  WarningAmberOutlined,
  CheckCircleOutlined,
  HelpOutlineOutlined,
  ErrorOutlineOutlined
} from '@mui/icons-material';

interface VariantTableProps {
  variants: any[];
}

type Order = 'asc' | 'desc';

interface HeadCell {
  id: string;
  label: string;
  numeric: boolean;
  tooltip?: string;
  format?: (value: any) => string;
}

const headCells: HeadCell[] = [
  { id: 'hgvs_g', label: 'Genomic Position', numeric: false },
  { id: 'amino_acid_change', label: 'Protein Change', numeric: false },
  { id: 'pathogenicity', label: 'Pathogenicity', numeric: false },
  { id: 'clinvar_id', label: 'ClinVar', numeric: false },
  { 
    id: 'gnomad_af', 
    label: 'gnomAD AF', 
    numeric: true, 
    tooltip: 'Allele frequency in gnomAD',
    format: (val) => val ? val.toExponential(2) : 'N/A'
  },
  { 
    id: 'cadd_score', 
    label: 'CADD', 
    numeric: true, 
    tooltip: 'CADD Phred score',
    format: (val) => val ? val.toFixed(2) : 'N/A'
  },
  { 
    id: 'sift_score', 
    label: 'SIFT', 
    numeric: true, 
    tooltip: 'SIFT score (0-1, <0.05 deleterious)',
    format: (val) => val ? val.toFixed(3) : 'N/A'
  },
  { 
    id: 'polyphen_score', 
    label: 'PolyPhen', 
    numeric: true, 
    tooltip: 'PolyPhen score (0-1, >0.85 probably damaging)',
    format: (val) => val ? val.toFixed(3) : 'N/A'
  },
  { id: 'protein_domain', label: 'Domain', numeric: false }
];

const pathogenicityColors: Record<string, string> = {
  'pathogenic': '#d32f2f',
  'likely_pathogenic': '#f57c00',
  'uncertain_significance': '#fbc02d',
  'likely_benign': '#388e3c',
  'benign': '#1976d2'
};

const pathogenicityIcons: Record<string, React.ReactNode> = {
  'pathogenic': <ErrorOutlineOutlined fontSize="small" />,
  'likely_pathogenic': <WarningAmberOutlined fontSize="small" />,
  'uncertain_significance': <HelpOutlineOutlined fontSize="small" />,
  'likely_benign': <CheckCircleOutlined fontSize="small" />,
  'benign': <CheckCircleOutlined fontSize="small" />
};

export function VariantTable({ variants }: VariantTableProps) {
  const [order, setOrder] = useState<Order>('asc');
  const [orderBy, setOrderBy] = useState<string>('hgvs_g');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterAnchorEl, setFilterAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedFilters, setSelectedFilters] = useState<Record<string, boolean>>({
    pathogenic: true,
    likely_pathogenic: true,
    uncertain_significance: true,
    likely_benign: true,
    benign: true
  });

  // Sorting logic
  const handleRequestSort = (property: string) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  // Filter and search logic
  const filteredVariants = useMemo(() => {
    return variants.filter(variant => {
      // Search filter
      const searchLower = searchTerm.toLowerCase();
      const matchesSearch = !searchTerm || 
        variant.hgvs_g?.toLowerCase().includes(searchLower) ||
        variant.amino_acid_change?.toLowerCase().includes(searchLower) ||
        variant.gene_symbol?.toLowerCase().includes(searchLower);

      // Pathogenicity filter
      const matchesFilter = selectedFilters[variant.pathogenicity || 'uncertain_significance'];

      return matchesSearch && matchesFilter;
    });
  }, [variants, searchTerm, selectedFilters]);

  // Sort filtered variants
  const sortedVariants = useMemo(() => {
    return [...filteredVariants].sort((a, b) => {
      const aValue = a[orderBy];
      const bValue = b[orderBy];

      if (aValue === null || aValue === undefined) return 1;
      if (bValue === null || bValue === undefined) return -1;

      if (order === 'desc') {
        return bValue > aValue ? 1 : -1;
      }
      return aValue > bValue ? 1 : -1;
    });
  }, [filteredVariants, order, orderBy]);

  // Pagination
  const paginatedVariants = sortedVariants.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  // Export functionality
  const exportToCSV = () => {
    const headers = headCells.map(cell => cell.label).join(',');
    const rows = sortedVariants.map(variant => 
      headCells.map(cell => {
        const value = variant[cell.id];
        if (cell.format) return cell.format(value);
        if (typeof value === 'object') return JSON.stringify(value);
        return value || '';
      }).join(',')
    );
    
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `variants_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  // Render pathogenicity chip
  const renderPathogenicityChip = (pathogenicity: string) => {
    if (!pathogenicity) return <Chip label="Unknown" size="small" />;
    
    return (
      <Chip
        icon={pathogenicityIcons[pathogenicity] as React.ReactElement}
        label={pathogenicity.replace(/_/g, ' ')}
        size="small"
        style={{
          backgroundColor: pathogenicityColors[pathogenicity],
          color: 'white'
        }}
      />
    );
  };

  // Render score with color coding
  const renderScore = (score: number | null, type: 'cadd' | 'sift' | 'polyphen') => {
    if (score === null || score === undefined) return 'N/A';

    let color = 'inherit';
    let severity = '';

    if (type === 'cadd') {
      if (score >= 30) { color = '#d32f2f'; severity = 'High impact'; }
      else if (score >= 20) { color = '#f57c00'; severity = 'Moderate impact'; }
      else if (score >= 10) { color = '#fbc02d'; severity = 'Low impact'; }
      else { color = '#4caf50'; severity = 'Minimal impact'; }
    } else if (type === 'sift') {
      if (score <= 0.05) { color = '#d32f2f'; severity = 'Deleterious'; }
      else { color = '#4caf50'; severity = 'Tolerated'; }
    } else if (type === 'polyphen') {
      if (score >= 0.85) { color = '#d32f2f'; severity = 'Probably damaging'; }
      else if (score >= 0.15) { color = '#f57c00'; severity = 'Possibly damaging'; }
      else { color = '#4caf50'; severity = 'Benign'; }
    }

    return (
      <Tooltip title={severity}>
        <Typography
          variant="body2"
          style={{ color, fontWeight: 'bold' }}
        >
          {score.toFixed(type === 'cadd' ? 1 : 3)}
        </Typography>
      </Tooltip>
    );
  };

  return (
    <Paper sx={{ width: '100%', mb: 2 }}>
      {/* Toolbar */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={6}>
            <TextField
              placeholder="Search variants..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              size="small"
              fullWidth
              InputProps={{
                startAdornment: <FilterListOutlined sx={{ mr: 1, color: 'text.secondary' }} />
              }}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
              <Button
                startIcon={<FilterListOutlined />}
                onClick={(e) => setFilterAnchorEl(e.currentTarget)}
                variant="outlined"
                size="small"
              >
                Filter
              </Button>
              <Button
                startIcon={<FileDownloadOutlined />}
                onClick={exportToCSV}
                variant="outlined"
                size="small"
              >
                Export CSV
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Box>

      {/* Filter Menu */}
      <Menu
        anchorEl={filterAnchorEl}
        open={Boolean(filterAnchorEl)}
        onClose={() => setFilterAnchorEl(null)}
      >
        <Box sx={{ p: 2, minWidth: 200 }}>
          <Typography variant="subtitle2" gutterBottom>
            Pathogenicity Filter
          </Typography>
          {Object.keys(selectedFilters).map(key => (
            <FormControlLabel
              key={key}
              control={
                <Checkbox
                  checked={selectedFilters[key]}
                  onChange={(e) => setSelectedFilters({
                    ...selectedFilters,
                    [key]: e.target.checked
                  })}
                  size="small"
                />
              }
              label={key.replace(/_/g, ' ')}
              sx={{ display: 'block' }}
            />
          ))}
        </Box>
      </Menu>

      {/* Table */}
      <TableContainer sx={{ maxHeight: 600 }}>
        <Table stickyHeader size="small">
          <TableHead>
            <TableRow>
              {headCells.map((headCell) => (
                <TableCell
                  key={headCell.id}
                  align={headCell.numeric ? 'right' : 'left'}
                  sortDirection={orderBy === headCell.id ? order : false}
                >
                  <TableSortLabel
                    active={orderBy === headCell.id}
                    direction={orderBy === headCell.id ? order : 'asc'}
                    onClick={() => handleRequestSort(headCell.id)}
                  >
                    {headCell.label}
                    {headCell.tooltip && (
                      <Tooltip title={headCell.tooltip}>
                        <InfoOutlined sx={{ ml: 0.5, fontSize: 16, verticalAlign: 'middle' }} />
                      </Tooltip>
                    )}
                  </TableSortLabel>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedVariants.map((variant, index) => (
              <TableRow
                key={index}
                hover
                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
              >
                <TableCell>{variant.hgvs_g || 'N/A'}</TableCell>
                <TableCell>{variant.amino_acid_change || 'N/A'}</TableCell>
                <TableCell>{renderPathogenicityChip(variant.pathogenicity)}</TableCell>
                <TableCell>
                  {variant.clinvar_id ? (
                    <Button
                      size="small"
                      href={`https://www.ncbi.nlm.nih.gov/clinvar/variation/${variant.clinvar_id}`}
                      target="_blank"
                    >
                      {variant.clinvar_id}
                    </Button>
                  ) : 'N/A'}
                </TableCell>
                <TableCell align="right">
                  {variant.gnomad_af ? variant.gnomad_af.toExponential(2) : 'N/A'}
                </TableCell>
                <TableCell align="right">
                  {renderScore(variant.cadd_score, 'cadd')}
                </TableCell>
                <TableCell align="right">
                  {renderScore(variant.sift_score, 'sift')}
                </TableCell>
                <TableCell align="right">
                  {renderScore(variant.polyphen_score, 'polyphen')}
                </TableCell>
                <TableCell>
                  {variant.protein_domain ? (
                    <Chip 
                      label={variant.protein_domain.name || 'Domain'} 
                      size="small" 
                      variant="outlined"
                    />
                  ) : 'N/A'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      <TablePagination
        rowsPerPageOptions={[5, 10, 25, 50]}
        component="div"
        count={filteredVariants.length}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={(_, newPage) => setPage(newPage)}
        onRowsPerPageChange={(e) => {
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
      />

      {/* Summary Stats */}
      <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', bgcolor: 'grey.50' }}>
        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Total Variants
            </Typography>
            <Typography variant="h6">{variants.length}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Pathogenic
            </Typography>
            <Typography variant="h6" color="error">
              {variants.filter(v => v.pathogenicity === 'pathogenic').length}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              VUS
            </Typography>
            <Typography variant="h6" color="warning.main">
              {variants.filter(v => v.pathogenicity === 'uncertain_significance').length}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Benign
            </Typography>
            <Typography variant="h6" color="success.main">
              {variants.filter(v => v.pathogenicity === 'benign').length}
            </Typography>
          </Grid>
        </Grid>
      </Box>
    </Paper>
  );
}