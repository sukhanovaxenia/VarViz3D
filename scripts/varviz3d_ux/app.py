# app.py - Main Streamlit Interface with fixes
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
import streamlit.components.v1 as components
from typing import Dict, Any, Optional, List
import tempfile
import webbrowser

# Import modules
import gnomad_viz  # Full gene visualization
from literature_agent import LiteratureAgent

st.set_page_config(
    page_title="Variant Analysis Platform",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    /* Remove all Streamlit padding/margins */
    .main .block-container {
        max-width: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Full viewport for tabs */
    [data-testid="stVerticalBlock"] > [style*="flex-direction"] {
        gap: 0 !important;
    }
    
    /* Remove column gaps */
    [data-testid="column"] {
        padding: 0 !important;
    }
    
    /* Full width iframe */
    iframe {
        position: relative !important;
        width: calc(100vw - 320px) !important;  /* Account for sidebar */
        height: 85vh !important;
        left: 0 !important;
        border: none !important;
    }
    
    /* When sidebar collapsed */
    section[data-testid="stSidebar"][aria-expanded="false"] ~ .main iframe {
        width: calc(100vw - 60px) !important;
    }

    /* Force plotly full width */
    .stPlotlyChart {
        width: 100% !important;
    }
    
    /* Remove expander padding */
    .streamlit-expanderContent {
        padding: 0 !important;
    }
    
    div[data-testid="stExpander"] {
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

class BackendAPI:
    """Flask backend wrapper"""
    def __init__(self, base_url="http://localhost:5001"):
        self.base = base_url
    
    def check_status(self) -> bool:
        try:
            r = requests.get(self.base, timeout=2)
            print(f"Backend status: {r.status_code}")  # Debug
            return r.status_code == 200
        except Exception as e:
            print(f"Backend check failed: {e}")  # Debug
            return False
    
    def resolve_gene(self, symbol: str) -> Dict:
        try:
            r = requests.get(f"{self.base}/api/resolve/{symbol}", timeout=10)
            return r.json()
        except:
            return {}
    
    def find_rsid(self, uniprot_id: str, rsid: str) -> Dict:
        try:
            r = requests.get(f"{self.base}/api/rspos/{uniprot_id}/{rsid}", timeout=10)
            return r.json()
        except:
            return {"positions": []}

def main():
    st.title("🧬 Integrated Variant Analysis Platform")
    
    # Initialize
    if 'backend' not in st.session_state:
        st.session_state.backend = BackendAPI()
    if 'lit_agent' not in st.session_state:
        st.session_state.lit_agent = LiteratureAgent()
    
    # Sidebar config
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Status indicators
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.backend.check_status():
                st.success("✅ 3D Backend")
            else:
                st.error("❌ Start backend.py")
        with col2:
            st.info("📚 Lit API: 8000")
        
        st.markdown("---")
        
        # Gene input
        gene_symbol = st.text_input("Gene Symbol", "BRCA1")
        if st.button("Set Gene"):
            result = st.session_state.backend.resolve_gene(gene_symbol)
            if result.get('best'):
                st.session_state.uniprot = result['best']['accession']
                st.session_state.gene = gene_symbol
                st.success(f"UniProt: {st.session_state.uniprot}")
            else:
                st.session_state.gene = gene_symbol
                st.session_state.uniprot = "P38398"  # Default to BRCA1
                st.warning("Using default UniProt P38398")
        
        # Parameters
        st.markdown("---")
        st.subheader("Parameters")
        st.session_state.bin_size = st.slider("Bin Size", 50, 500, 100)
        st.session_state.window_size = st.slider("Window Size", 10, 100, 30)
        st.session_state.dataset = st.selectbox("Dataset", ["gnomad_r4", "gnomad_r3"])
        st.session_state.genome = st.selectbox("Reference", ["GRCh38", "GRCh37"])
        
        # Optional markers
        st.session_state.rsid = st.text_input("Highlight rsID", "")
        st.session_state.marker_pos = st.number_input("Mark Position", 0, step=1000)
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs([
        "📊 2D Gene Overview & gnomAD", 
        "🧬 3D Protein Structure",
        "📚 Literature Analysis"
    ])
    
    # Tab 1: 2D Gene Visualization with error handling
    with tab1:
        if 'gene' not in st.session_state:
            st.info("👈 Enter a gene symbol in the sidebar")
        else:
            gene = st.session_state.gene
            
            st.subheader(f"Gene: {gene}")
            
            if st.button("Generate Full Report", type="primary"):
                with st.spinner("Generating comprehensive gene report..."):
                    try:
                        # Get gene data
                        gj = gnomad_viz.lookup_gene(gene)
                        gene_info = gnomad_viz.build_gene_summary(gj)
                        gene_info["transcripts"] = gnomad_viz.annotate_transcripts(gene_info["transcripts"])
                        
                        # Fetch variants with error handling
                        try:
                            variants = gnomad_viz.fetch_gnomad_variants(
                                gene_info["chrom"],
                                gene_info["start"],
                                gene_info["end"],
                                st.session_state.genome,
                                st.session_state.dataset
                            )
                        except:
                            # Create demo data when API fails
                            import random
                            num_variants = 30
                            variants = []
                            for i in range(num_variants):
                                pos = gene_info["start"] + i * ((gene_info["end"] - gene_info["start"]) // num_variants)
                                variants.append({
                                    "variantId": f"{gene_info['chrom']}-{pos}-A-G",
                                    "chrom": gene_info["chrom"],
                                    "pos": pos,
                                    "ref": "A",
                                    "alt": "G",
                                    "consequence": ["missense_variant", "synonymous_variant"][i % 2],
                                    "genome": {"af": 0.001 * (i + 1)}
                                })
                            st.info("Using demonstration data due to gnomAD connection issues")
                            
                        df_gnomad = gnomad_viz.variants_to_dataframe(variants)

                        # Fetch ClinVar with error handling
                        try:
                            clinvar_variants = gnomad_viz.fetch_clinvar_variants(
                                gene_info["chrom"],
                                gene_info["start"],
                                gene_info["end"],
                                st.session_state.genome
                            )
                        except:
                            clinvar_variants = []
                            st.warning("ClinVar API timeout - no ClinVar data available")
                        
                        df_clinvar = gnomad_viz.clinvar_variants_to_dataframe(clinvar_variants)
                        
                        # Create plots
                        pie_fig = gnomad_viz.create_pie(df_gnomad)
                        bar_fig = gnomad_viz.create_bar_plot(df_gnomad, gene_info, st.session_state.bin_size)
                        clinvar_fig = gnomad_viz.create_clinvar_bar_plot_like_gnomad(
                            df_clinvar, 
                            gene_info, 
                            bin_size=st.session_state.bin_size,
                            gnomad_positions=df_gnomad["pos"] if not df_gnomad.empty else None
                        )
                        gene_struct_fig = gnomad_viz.create_gene_structure_plot(gene_info)
                            
                        # Add marker if specified
                        if st.session_state.marker_pos > 0:
                            for fig in [bar_fig, clinvar_fig, gene_struct_fig]:
                                gnomad_viz.add_marker_line(fig, st.session_state.marker_pos)
                        
                        # Store results
                        st.session_state.gene_info = gene_info
                        st.session_state.gnomad_df = df_gnomad
                        st.session_state.clinvar_df = df_clinvar
                        
                        # Display plots
                        st.success(f"Found {len(df_gnomad)} gnomAD variants, {len(df_clinvar)} ClinVar variants")
                        
                        # Gene info
                        with st.expander("Gene Information", expanded=True):
                            
                            st.markdown(f"""
                            **Ensembl ID:** {gene_info['ensembl_gene_id']}  
                            **Region:** {gene_info['region']}  
                            **Assembly:** {gene_info['assembly']}  
                            **Transcripts:** {len(gene_info['transcripts'])}
                            """)
                            
                        # Variant distributions
                        st.subheader("Variant Distribution Analysis")
                        st.plotly_chart(bar_fig, use_container_width=True)
                        
                        # ClinVar
                        if not df_clinvar.empty:
                            st.subheader("ClinVar Variants")
                            st.plotly_chart(clinvar_fig, use_container_width=True)
                        
                        # Gene structure
                        st.subheader("Gene Structure")
                        st.plotly_chart(gene_struct_fig, use_container_width=True)
                        
                    except Exception as e:
                        st.error(f"Error: {e}")
                        st.info("Try refreshing the page or checking your internet connection")
    
    # Tab 2: 3D Protein Structure
    with tab2:
        if 'gene' not in st.session_state:
            st.info("👈 Set a gene in the sidebar first")
        else:
            # Ensure we have a uniprot ID
            if not hasattr(st.session_state, 'uniprot'):
                st.session_state.uniprot = "P38398"  # Default BRCA1
            
            uid = st.session_state.uniprot
            
            # Controls
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                view_mode = st.selectbox("Mode", ["sstruc", "rainbow", "heat", "domains"])
            with col2:
                variant_class = st.selectbox("Variant Class", ["any", "pathogenic", "benign", "uncertain", "predicted"])
            with col3:
                window = st.number_input("Window", 5, 50, st.session_state.window_size)
            with col4:
                highlight_pos = ""
                if st.session_state.rsid:
                    rsid_data = st.session_state.backend.find_rsid(uid, st.session_state.rsid)
                    if rsid_data.get('positions'):
                        highlight_pos = ','.join(map(str, rsid_data['positions']))
                        st.info(f"rsID pos: {highlight_pos}")
            
            # Build viewer URL
            viewer_url = f"http://localhost:5001/3d/viewer?uniprot={uid}&win={window}&class={variant_class}"
            if highlight_pos:
                viewer_url += f"&highlight={highlight_pos}"
            
            # Embed viewer
            st.markdown("### Interactive 3D Protein Viewer")
            st.markdown(f'<iframe src="{viewer_url}" style="width:100%;height:85vh;border:none;"></iframe>', unsafe_allow_html=True)
            
            # Check if backend is running
            if st.session_state.backend.check_status():
                components.iframe(viewer_url, height=None, width=None, scrolling=True)
            else:
                st.error("3D Backend not running. Please start backend_3d.py")
                st.code("python backend_3d.py", language="bash")
            
            # Instructions
            with st.expander("Controls"):
                st.markdown("""
                **Viewer controls:**
                - Mode buttons: Secondary structure / Rainbow / Variants heatmap / Domains
                - Style: Cartoon / Stick / Sphere
                - Spin: Rotate structure
                - rsID: Enter ID and click Highlight to mark position
                - Click 2D tracks to zoom regions
                """)
    
    # Tab 3: Literature Analysis (unchanged)
    with tab3:
        if 'gene' not in st.session_state:
            st.info("👈 Enter a gene symbol in the sidebar")
        else:
            gene = st.session_state.gene
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(f"Literature Analysis for {gene}")
            with col2:
                if st.button("Fetch Gene Data", type="primary"):
                    with st.spinner("Getting gene overview..."):
                        overview = st.session_state.lit_agent.get_gene_overview(gene)
                        if overview and not overview.get('error'):
                            st.session_state.gene_overview = overview
                            st.success(f"Found {overview['counts']['variants_total']} variants")
            
            if hasattr(st.session_state, 'gene_overview'):
                overview = st.session_state.gene_overview
                
                with st.expander("Gene Summary", expanded=True):
                    if overview.get('summary'):
                        st.info(overview['summary'])
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Variants", overview['counts']['variants_total'])
                    with col2:
                        st.metric("With AF Data", overview['counts']['variants_with_af'])
                    with col3:
                        rsids = [v['rsid'] for v in overview.get('variants', []) if v.get('rsid')]
                        st.metric("With rsIDs", len(rsids))

                if overview.get('variants'):
                    with st.expander("Variant Details", expanded=False):
                        df_variants = pd.DataFrame(overview['variants'])
                        st.dataframe(df_variants, use_container_width=True)
                        
                        # Download button
                        csv = df_variants.to_csv(index=False)
                        st.download_button(
                            label="Download Variants CSV",
                            data=csv,
                            file_name=f"{gene}_variants.csv",
                            mime="text/csv"
                        )

if __name__ == "__main__":
    main()