// frontend/utils/api.ts
import axios, { AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Types
export interface VariantInput {
  chromosome: string;
  position: number;
  reference: string;
  alternate: string;
}

export interface AnalysisOptions {
  include_literature?: boolean;
  include_structure?: boolean;
  include_conservation?: boolean;
  batch_size?: number;
}

export interface AnalysisResult {
  gene: string;
  variants: any[];
  structure?: any;
  mapped_variants?: any[];
  literature?: any[];
  timestamp: string;
}

// Main analysis function
export async function analyzeVariants(
  gene: string,
  variants: VariantInput[],
  options: AnalysisOptions = {}
): Promise<AnalysisResult> {
  try {
    const response = await apiClient.post<AnalysisResult>('/api/v1/analyze', {
      gene_symbol: gene,
      variants: variants,
      include_literature: options.include_literature ?? true,
      include_structure: options.include_structure ?? true,
      include_conservation: options.include_conservation ?? true,
    });

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message;
      throw new Error(`Analysis failed: ${message}`);
    }
    throw error;
  }
}

// Upload VCF file
export async function uploadVCF(file: File, gene?: string): Promise<VariantInput[]> {
  try {
    const formData = new FormData();
    formData.append('file', file);
    if (gene) {
      formData.append('gene', gene);
    }

    const response = await apiClient.post<{ variants: VariantInput[] }>(
      '/api/v1/upload-vcf',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return response.data.variants;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message;
      throw new Error(`VCF upload failed: ${message}`);
    }
    throw error;
  }
}

// Get protein structure
export async function getProteinStructure(
  gene: string,
  includeVariants: boolean = false
): Promise<any> {
  try {
    const response = await apiClient.get(`/api/v1/structure/${gene}`, {
      params: { include_variants: includeVariants },
    });

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message;
      throw new Error(`Failed to fetch structure: ${message}`);
    }
    throw error;
  }
}

// Get gene suggestions for autocomplete
export async function getGeneSuggestions(query: string): Promise<string[]> {
  try {
    const response = await apiClient.get<{ suggestions: string[] }>(
      '/api/v1/genes/suggest',
      {
        params: { q: query },
      }
    );

    return response.data.suggestions;
  } catch (error) {
    console.error('Failed to fetch gene suggestions:', error);
    return [];
  }
}

// Export results
export async function exportResults(
  jobId: string,
  format: 'csv' | 'json' | 'pdf' = 'csv'
): Promise<Blob> {
  try {
    const response = await apiClient.get(`/api/v1/export/${jobId}`, {
      params: { format },
      responseType: 'blob',
    });

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message;
      throw new Error(`Export failed: ${message}`);
    }
    throw error;
  }
}

// WebSocket connection for real-time updates
export class AnalysisWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(
    private jobId: string,
    private onMessage: (data: any) => void,
    private onError?: (error: Error) => void,
    private onComplete?: () => void
  ) {}

  connect() {
    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/ws/updates/${this.jobId}`;
    
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
        
        if (data.complete) {
          this.onComplete?.();
          this.close();
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.onError?.(new Error('WebSocket connection failed'));
    };

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), 1000 * this.reconnectAttempts);
      }
    };
  }

  close() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Utility function for batch processing
export async function analyzeVariantsBatch(
  gene: string,
  variants: VariantInput[],
  batchSize: number = 50,
  onProgress?: (progress: number) => void
): Promise<AnalysisResult[]> {
  const results: AnalysisResult[] = [];
  const totalBatches = Math.ceil(variants.length / batchSize);

  for (let i = 0; i < totalBatches; i++) {
    const batch = variants.slice(i * batchSize, (i + 1) * batchSize);
    const result = await analyzeVariants(gene, batch);
    results.push(result);
    
    if (onProgress) {
      onProgress((i + 1) / totalBatches);
    }
  }

  // Merge results
  return results;
}

// Cache management
export const cacheManager = {
  get: (key: string): any => {
    try {
      const item = localStorage.getItem(`varviz_${key}`);
      if (!item) return null;
      
      const { data, expiry } = JSON.parse(item);
      if (Date.now() > expiry) {
        localStorage.removeItem(`varviz_${key}`);
        return null;
      }
      
      return data;
    } catch {
      return null;
    }
  },

  set: (key: string, data: any, ttlMinutes: number = 60) => {
    try {
      const item = {
        data,
        expiry: Date.now() + ttlMinutes * 60 * 1000,
      };
      localStorage.setItem(`varviz_${key}`, JSON.stringify(item));
    } catch (error) {
      console.error('Failed to cache data:', error);
    }
  },

  clear: () => {
    Object.keys(localStorage)
      .filter(key => key.startsWith('varviz_'))
      .forEach(key => localStorage.removeItem(key));
  },
};