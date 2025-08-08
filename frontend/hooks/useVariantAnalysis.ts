// frontend/hooks/useVariantAnalysis.ts
import { useState, useCallback } from 'react';
import { useMutation, useQuery } from 'react-query';
import { analyzeVariants, VariantInput, AnalysisResult } from '../utils/api';

export function useVariantAnalysis() {
  const [gene, setGene] = useState('');
  const [variants, setVariants] = useState<VariantInput[]>([]);

  const mutation = useMutation(
    () => analyzeVariants(gene, variants),
    {
      onSuccess: (data) => {
        // Cache the result
        localStorage.setItem(
          `analysis_${gene}_${Date.now()}`,
          JSON.stringify(data)
        );
      },
    }
  );

  const analyze = useCallback(() => {
    if (gene && variants.length > 0) {
      mutation.mutate();
    }
  }, [gene, variants, mutation]);

  return {
    gene,
    setGene,
    variants,
    setVariants,
    analyze,
    isLoading: mutation.isLoading,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}