// frontend/types/index.d.ts

// Extend window object for g3viz
declare global {
    interface Window {
      g3viz: any;
      $3Dmol: any;
    }
  }
  
  // g3viz module declaration
  declare module 'g3viz' {
    export interface G3VizOptions {
      element: string | HTMLElement;
      gene: string;
      mutations: any[];
      options?: {
        legend?: boolean;
        zoom?: boolean;
        brush?: boolean;
        tooltip?: boolean;
        height?: number;
      };
    }
  
    export function lollipop(config: G3VizOptions): any;
  }
  
  // 3Dmol declarations
  declare module '3dmol/build/3Dmol-min.js' {
    export function createViewer(
      element: HTMLElement,
      config?: any
    ): any;
  }
  
  export {};