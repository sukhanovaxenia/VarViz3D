`
import argparse
import requests
import pandas as pd
import plotly.graph_objs as go
import vcf
import sys
import plotly.express as px

MYVARIANT_URL = "https://myvariant.info/v1/variant/"

def fetch_variant_data(variant_id):
    """Fetch variant annotation from MyVariant.info."""
    try:
        response = requests.get(f"{MYVARIANT_URL}{variant_id}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[!] Failed to fetch {variant_id}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"[!] Error fetching {variant_id}: {e}")
        return None


def parse_variant_info(data):
    """Extract key data for plotting from MyVariant info."""
    try:
        hgvs = data.get('_id', '')
        gene = data.get('gene', {}).get('symbol', 'Unknown')
        cadd_score = data.get('cadd', {}).get('phred')
        consequence = data.get('snpeff', {}).get('ann', [{}])[0].get('putative_impact', '')
        protein_pos = None

        # Try parsing protein position from hgvs if available
        if 'protein' in hgvs:
            import re
            match = re.search(r'p\.\D+(\d+)', hgvs)
            if match:
                protein_pos = int(match.group(1))

        clinvar = data.get('clinvar', {})
    pathogenicity = None
    if isinstance(clinvar, dict):
        pathogenicity = clinvar.get('clinical_significance', {}).get('description')

    return {
        'variant': hgvs,
        'gene': gene,
        'pos': protein_pos,
        'cadd': cadd_score,
        'impact': consequence,
        'clinvar': pathogenicity
    }
    except Exception as e:
        print(f"[!] Failed to parse variant data: {e}")
        return None

def read_variants_from_vcf(vcf_path):
    """Read variants from a VCF file and convert to HGVS."""
    vcf_reader = vcf.Reader(filename=vcf_path)
    hgvs_variants = []

    for record in vcf_reader:
        chrom = record.CHROM
        pos = record.POS
        ref = record.REF
        alt = str(record.ALT[0])
        hgvs = f"{chrom}:g.{pos}{ref}>{alt}"
        hgvs_variants.append(hgvs)
    return hgvs_variants

def plot_lollipop(df, gene, output_file='lollipop_plot.html', color_by='impact'):
    """
    Create an interactive lollipop plot.
    
    Parameters:
        df (pd.DataFrame): DataFrame with variant information
        gene (str): Gene symbol
        output_file (str): Output HTML file name
        color_by (str): Column to use for coloring ('impact', 'clinvar', 'cadd')
    """
    import plotly.express as px

    if color_by == 'clinvar':
        # Prepare color map for ClinVar significance
        color_map = {
            'Pathogenic': 'red',
            'Likely_pathogenic': 'orange',
            'Benign': 'green',
            'Likely_benign': 'lightgreen',
            'Uncertain_significance': 'gray'
        }
        df['clinvar_color'] = df['clinvar'].map(
            lambda x: color_map.get(str(x).replace(" ", "_"), 'black')
        )
        color = df['clinvar_color']
        color_label = 'ClinVar Significance'
        hover_info = df['clinvar']
    elif color_by == 'cadd':
        color = df['cadd']
        color_label = 'CADD Score'
        hover_info = df['cadd']
    else:  # Default: color by 'impact'
        color = df['impact']
        color_label = 'Consequence'
        hover_info = df['impact']

    fig = px.scatter(
        df,
        x='pos',
        y=[1] * len(df),
        color=color,
        size='cadd',  # Optional: or use impact_count, etc.
        hover_data={
            'variant': df['variant'],
            color_label: hover_info,
            'Protein Position': df['pos'],
            'CADD': df['cadd']
        },
        title=f"Lollipop Plot for {gene}",
        labels={'pos': 'Protein Position'}
    )

    fig.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
    fig.update_layout(
        yaxis=dict(visible=False),
        showlegend=True,
        width=1100,
        height=400
    )

    fig.write_html(output_file)
    print(f"[✓] Lollipop plot saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Lollipop plot for variants via MyVariant.info")
    parser.add_argument('--vcf', help='VCF file with variants')
    parser.add_argument('--variants', nargs='+', help='List of HGVS or chrom:g.posREF>ALT variants')
    parser.add_argument('--output', default='lollipop_plot.html', help='Output plot HTML file')
    parser.add_argument('--color_by', choices=['impact', 'clinvar', 'cadd'], default='impact',
                    help='Column to color the plot by')
    args = parser.parse_args()

    if not args.vcf and not args.variants:
        print("[!] You must provide either --vcf or --variants")
        sys.exit(1)

    if args.vcf:
        variant_ids = read_variants_from_vcf(args.vcf)
    else:
        variant_ids = args.variants

    print(f"[✓] Total variants to query: {len(variant_ids)}")

    variant_data = []
    for var_id in variant_ids:
        raw = fetch_variant_data(var_id)
        if raw:
            parsed = parse_variant_info(raw)
            if parsed and parsed['pos'] is not None:
                variant_data.append(parsed)

    if not variant_data:
        print("[!] No variants could be plotted.")
        return

    df = pd.DataFrame(variant_data)
    gene_name = df['gene'].iloc[0]
    plot_lollipop(df, gene_name, args.output, color_by=args.color_by)

if name == '__main__':
    main()