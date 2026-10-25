"""Theme and enterprise styling injection for RIOT RADAR Streamlit application.

Enforces:
- Slate enterprise institutional color palette
- Tabular numerals for aligned bottle counts and financial figures
- Compact KPI card styling with zero emojis
- Standard Plotly chart layout wrapper
"""

import streamlit as st
import plotly.graph_objects as go
from config.business_rules import COLOR_TOKENS


def apply_enterprise_theme():
    """Inject institutional CSS to enforce typography, tabular numerals, and compact cards."""
    st.markdown("""
        <style>
        /* Reduce top/bottom whitespace bloat */
        .block-container {
            padding-top: 1.25rem !important;
            padding-bottom: 1.5rem !important;
            max-width: 98% !important;
        }
        /* Hide default Streamlit chrome */
        #MainMenu, footer { visibility: hidden; }
        
        /* Tabular numerals for aligned financial & bottle counts */
        div[data-testid="stMetricValue"], table, td, th {
            font-variant-numeric: tabular-nums !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        
        /* Compact institutional KPI card styling */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #0F172A;
            border-radius: 4px;
            padding: 10px 14px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #475569 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
            font-weight: 700 !important;
            color: #0F172A !important;
        }
        
        /* RAG Ribbon badges */
        .rag-badge {
            display: inline-block;
            padding: 2px 8px;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 3px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .rag-critical {
            background-color: #FEE2E2;
            color: #991B1B;
            border: 1px solid #F87171;
        }
        .rag-warn {
            background-color: #FEF3C7;
            color: #92400E;
            border: 1px solid #FBBF24;
        }
        .rag-ok {
            background-color: #CCFBF1;
            color: #115E59;
            border: 1px solid #2DD4BF;
        }
        .synthetic-badge {
            font-size: 0.70rem;
            color: #64748B;
            font-style: italic;
            border-top: 1px dashed #CBD5E1;
            padding-top: 4px;
            margin-top: 6px;
        }
        </style>
    """, unsafe_allow_html=True)


def style_scm_figure(fig: go.Figure, height: int = 340, y_title: str = "") -> go.Figure:
    """Standardized Plotly styling wrapper ensuring consistent font, margins, and slate gridlines."""
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=32, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color="#1E293B"),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            title=None,
        ),
        xaxis=dict(showgrid=False, linecolor="#CBD5E1", zeroline=False),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            linecolor="#CBD5E1",
            title=y_title,
            zeroline=False,
        ),
    )
    return fig
