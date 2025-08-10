# app.py - Main Streamlit Interface
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
    initial_sidebar_state="collapsed"  # Start collapsed for full-screen
)

# Custom CSS for full-screen tabs
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {gap: 24px;}
    .stTabs [data-baseweb="tab"] {height: 50px; padding: 0 20px;}
    .main .block-container {max-width: 100%; padding: 1rem;}
    iframe {border: 1px solid #ddd; border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

class BackendAPI:
    """Flask backend wrapper"""
    def __init__(self, base_url="http://localhost:5001"):
        self.base = base_url
    
    def check_status(self) -> bool:
        try:
            return requests.get(self.base, timeout=2).status_code == 200
        except:
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
                st.warning("No UniProt found, some features limited")
        
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
    
    # Main tabs (full-screen)
    tab1, tab2, tab3 = st.tabs([
        "📊 2D Gene Overview & gnomAD", 
        "🧬 3D Protein Structure",
        "📚 Literature Analysis"
    ])
    
    # Tab 1: Full 2D Gene Visualization
    with tab1:
        if 'gene' not in st.session_state:
            st.info("👈 Enter a gene symbol in the sidebar")
        else:
            gene = st.session_state.gene
            
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                st.subheader(f"Gene: {gene}")
            with col2:
                if st.button("Generate Full Report", type="primary"):
                    with st.spinner("Generating comprehensive gene report..."):
                        try:
                            # Run the full gnomad_viz analysis
                            import tempfile
                            import os
                            from datetime import datetime
                            
                            # Get gene data
                            gj = gnomad_viz.lookup_gene(gene)
                            gene_info = gnomad_viz.build_gene_summary(gj)
                            gene_info["transcripts"] = gnomad_viz.annotate_transcripts(gene_info["transcripts"])
                            
                            # Fetch variants
                            variants = gnomad_viz.fetch_gnomad_variants(
                                gene_info["chrom"],
                                gene_info["start"],
                                gene_info["end"],
                                st.session_state.genome,
                                st.session_state.dataset
                            )
                            df_gnomad = gnomad_viz.variants_to_dataframe(variants)
                            
                            # Fetch ClinVar
                            clinvar_variants = gnomad_viz.fetch_clinvar_variants(
                                gene_info["chrom"],
                                gene_info["start"],
                                gene_info["end"],
                                st.session_state.genome
                            )
                            df_clinvar = gnomad_viz.clinvar_variants_to_dataframe(clinvar_variants)
                            
                            # Create all plots
                            pie_fig = gnomad_viz.create_pie(df_gnomad)
                            bar_fig = gnomad_viz.create_bar_plot(df_gnomad, gene_info, st.session_state.bin_size)
                            clinvar_fig = gnomad_viz.create_clinvar_bar_plot_like_gnomad(
                                df_clinvar, gene_info, st.session_state.bin_size,
                                df_gnomad.get("pos") if not df_gnomad.empty else None
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
                                col1, col2 = st.columns([1, 2])
                                with col1:
                                    st.markdown(f"""
                                    **Ensembl ID:** {gene_info['ensembl_gene_id']}  
                                    **Region:** {gene_info['region']}  
                                    **Assembly:** {gene_info['assembly']}  
                                    **Transcripts:** {len(gene_info['transcripts'])}
                                    """)
                                with col2:
                                    st.plotly_chart(pie_fig, use_container_width=True)
                            
                            # Variant distributions
                            st.subheader("Variant Distribution Analysis")
                            st.plotly_chart(bar_fig, use_container_width=True)
                            
                            # ClinVar
                            st.subheader("ClinVar Variants")
                            st.plotly_chart(clinvar_fig, use_container_width=True)
                            
                            # Gene structure
                            st.subheader("Gene Structure")
                            st.plotly_chart(gene_struct_fig, use_container_width=True)
                            
                            # Generate HTML report
                            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            outfile = f"gene_{gene}_report_{ts}.html"
                            left_summary = gnomad_viz.prepare_left_summary_html(gene_info)
                            gnomad_viz.make_html_page(
                                gene_info, left_summary, pie_fig, bar_fig, 
                                gene_struct_fig, clinvar_fig, outfile
                            )
                            
                            # Download button
                            with open(outfile, 'r') as f:
                                st.download_button(
                                    "📥 Download HTML Report",
                                    f.read(),
                                    file_name=outfile,
                                    mime="text/html"
                                )
                            
                        except Exception as e:
                            st.error(f"Error: {e}")
    
    # Tab 2: 3D Protein Structure
    with tab2:
        if hasattr(st.session_state, 'uniprot'):
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
            
            # Build viewer URL with all parameters
            viewer_url = f"http://localhost:5001/3d/viewer?uniprot={uid}&win={window}&class={variant_class}"
            if highlight_pos:
                viewer_url += f"&highlight={highlight_pos}"
            
            # Embed full-screen viewer
            st.markdown("### Interactive 3D Protein Viewer")
            components.iframe(viewer_url, height=950, scrolling=True)
            
            # Instructions
            with st.expander("Controls"):
                st.markdown("""
                **In the viewer:**
                - Click mode buttons: Secondary structure / Rainbow / Variants heatmap / Domains
                - Click style buttons: Cartoon / Stick / Sphere
                - Click Spin to rotate
                - Enter rsID and click Highlight
                - Click on 2D tracks to zoom regions
                """)
        else:
            st.info("👈 Set a gene with UniProt mapping in sidebar for 3D view")
    
    # Tab 3: Literature Analysis
    with tab3:
        if 'gene' not in st.session_state:
            st.info("👈 Enter a gene symbol in the sidebar")
        else:
            gene = st.session_state.gene
            
            # Gene overview
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
            
            # Display gene summary if available
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
                
                # Individual variant search
                st.markdown("---")
                st.subheader("Individual Variant Literature")
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    search_rsid = st.text_input("rsID", placeholder="rs80357506")
                with col2:
                    sample_size = st.number_input("Sample Size", 5, 50, 10)
                with col3:
                    if st.button("Search", type="primary"):
                        if search_rsid:
                            with st.spinner(f"Searching literature for {search_rsid}..."):
                                result = st.session_state.lit_agent.get_rsid_literature(
                                    search_rsid, gene=gene, sample_size=sample_size
                                )
                                if not result.get('error'):
                                    st.success(f"Found {result['abstract_count']} abstracts")
                                    st.markdown("**Functional Effect Summary:**")
                                    st.info(result['functional_answer'])
                                    
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("PMIDs", result['abstract_count'])
                                    with col2:
                                        st.metric("Sampled", result['sampled_pmids'])
                                    with col3:
                                        st.metric("Gene", result.get('gene', 'N/A'))
                
                # Batch analysis
                if hasattr(st.session_state, 'gene_overview'):
                    st.markdown("---")
                    st.subheader("Batch Literature Coverage")
                    
                    rsids = [v['rsid'] for v in overview.get('variants', [])[:50] if v.get('rsid')]
                    
                    if st.button("Analyze All Variants"):
                        with st.spinner(f"Checking literature for {len(rsids)} variants..."):
                            counts = st.session_state.lit_agent.get_pmid_counts(rsids)
                            
                            if counts:
                                df = pd.DataFrame([
                                    {"rsID": rs, "PMIDs": count}
                                    for rs, count in counts.items()
                                ]).sort_values('PMIDs', ascending=False)
                                
                                # Plot
                                fig = go.Figure(data=[go.Bar(
                                    x=df['rsID'][:20],
                                    y=df['PMIDs'][:20],
                                    marker_color='lightblue'
                                )])
                                fig.update_layout(
                                    title="Top 20 Variants by Literature Coverage",
                                    xaxis_title="rsID",
                                    yaxis_title="PMID Count",
                                    height=500
                                )
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # Table
                                st.dataframe(df, use_container_width=True, height=400)

if __name__ == "__main__":
    main()