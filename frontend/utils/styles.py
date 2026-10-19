from __future__ import annotations

import streamlit as st


def load_global_styles() -> None:
    css = """
    <style>
    :root {
        --bg: #eef6fb;
        --panel: rgba(255, 255, 255, 0.86);
        --panel-strong: #ffffff;
        --line: rgba(35, 91, 138, 0.13);
        --text: #17324d;
        --muted: #64748b;
        --blue: #0ea5e9;
        --cyan: #06b6d4;
        --green: #10b981;
        --orange: #f59e0b;
        --red: #ef4444;
        --purple: #8b5cf6;
        --shadow: 0 18px 45px rgba(18, 64, 102, 0.10);
        --soft-shadow: 0 10px 28px rgba(18, 64, 102, 0.08);
        --radius: 14px;
    }

    #MainMenu,
    footer,
    [data-testid="stToolbar"],
    [data-testid="stStatusWidget"],
    [data-testid="stDecoration"] {
        display: none !important;
    }
    header[data-testid="stHeader"] {
        background: transparent;
        height: 0;
    }

    .stApp {
        background:
            radial-gradient(circle at 12% 12%, rgba(14, 165, 233, 0.10), transparent 30%),
            radial-gradient(circle at 88% 4%, rgba(6, 182, 212, 0.12), transparent 26%),
            linear-gradient(135deg, #eef7fc 0%, #f8fbff 48%, #edf8fb 100%);
        color: var(--text);
    }

    .block-container {
        max-width: 1540px;
        padding-top: 1.2rem;
        padding-bottom: 2.2rem;
        animation: fadeIn 0.35s ease-out;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Agent 对话页 */
    .agent-side-intro {
        padding: 1rem 1.05rem;
        margin-bottom: .75rem;
        border-radius: 18px;
        color: #e0f2fe;
        background:
            radial-gradient(circle at 95% 5%, rgba(103,232,249,.32), transparent 34%),
            linear-gradient(145deg, #075985, #0e7490);
        box-shadow: 0 14px 30px rgba(7,89,133,.18);
    }
    .agent-side-intro span {
        display: block;
        margin-bottom: .35rem;
        color: #a5f3fc;
        font-size: .72rem;
        font-weight: 750;
        letter-spacing: .08em;
        text-transform: uppercase;
    }
    .agent-side-intro strong { color: white; font-size: 1.06rem; }
    .agent-side-intro p {
        margin: .45rem 0 0;
        color: rgba(224,242,254,.82);
        font-size: .8rem;
        line-height: 1.55;
    }
    .suggestion-label {
        margin: 1rem 0 .42rem;
        color: #64748b;
        font-size: .76rem;
        font-weight: 750;
        letter-spacing: .06em;
    }
    .agent-chat-header {
        display: flex;
        align-items: center;
        gap: .85rem;
        min-height: 72px;
        padding: .85rem 1rem;
        margin-bottom: .25rem;
        border: 1px solid rgba(14,116,144,.13);
        border-radius: 20px;
        background: rgba(255,255,255,.82);
        box-shadow: 0 12px 32px rgba(18,64,102,.08);
        backdrop-filter: blur(14px);
    }
    .agent-brand-mark {
        width: 42px;
        height: 42px;
        flex: 0 0 42px;
        display: grid;
        place-items: center;
        border-radius: 14px;
        color: white;
        font-size: 1.3rem;
        background: linear-gradient(145deg, #0284c7, #22d3ee);
        box-shadow: 0 10px 22px rgba(14,165,233,.25);
    }
    .agent-chat-title { min-width: 0; flex: 1; }
    .agent-chat-title strong {
        display: block;
        color: #123657;
        font-size: 1.02rem;
    }
    .agent-chat-title span {
        display: block;
        overflow: hidden;
        color: #64748b;
        font-size: .78rem;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .agent-header-meta {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: .38rem;
        flex-wrap: wrap;
    }
    .agent-header-meta > span {
        padding: .28rem .55rem;
        border: 1px solid rgba(14,116,144,.1);
        border-radius: 999px;
        color: #47647b;
        background: #f4faff;
        font-size: .7rem;
        font-weight: 650;
    }
    .agent-live i {
        display: inline-block;
        width: 6px;
        height: 6px;
        margin-right: .32rem;
        border-radius: 50%;
    }
    .agent-live.online { color: #047857 !important; background: #ecfdf5 !important; }
    .agent-live.online i { background: #10b981; box-shadow: 0 0 0 4px rgba(16,185,129,.12); }
    .agent-live.offline { color: #b45309 !important; background: #fffbeb !important; }
    .agent-live.offline i { background: #f59e0b; }
    .st-key-agent_conversation_scroll {
        position: relative;
        height: min(420px, calc(100vh - 330px)) !important;
        min-height: 300px;
        max-height: 420px;
        margin-top: .15rem;
        margin-bottom: .4rem;
        border: 1px solid rgba(14,116,144,.16) !important;
        border-radius: 20px !important;
        background:
            linear-gradient(180deg, rgba(255,255,255,.9), rgba(247,252,255,.82));
        box-shadow:
            0 14px 34px rgba(18,64,102,.08),
            inset 0 1px 0 rgba(255,255,255,.86);
        clip-path: inset(0 round 20px);
        scroll-behavior: smooth;
        scrollbar-color: rgba(14,116,144,.26) transparent;
        scrollbar-width: thin;
        overscroll-behavior: contain;
    }
    .st-key-agent_conversation_scroll > div {
        padding-left: .65rem;
        padding-right: .55rem;
    }
    .agent-conversation-toolbar {
        position: sticky;
        top: 0;
        z-index: 30;
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 42px;
        margin: 0 -.55rem .35rem -.65rem;
        padding: 0 .9rem;
        border-bottom: 1px solid rgba(14,116,144,.12);
        color: #607b90;
        background: rgba(250,253,255,.96);
        box-shadow: 0 8px 18px rgba(18,64,102,.05);
        backdrop-filter: blur(14px);
    }
    .agent-conversation-toolbar span {
        display: flex;
        align-items: center;
        gap: .42rem;
        color: #325b76;
        font-size: .76rem;
        font-weight: 750;
        letter-spacing: .02em;
    }
    .agent-conversation-toolbar i {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #22c1d6;
        box-shadow: 0 0 0 4px rgba(34,193,214,.12);
    }
    .agent-conversation-toolbar small {
        color: #8ba0b0;
        font-size: .69rem;
    }
    .st-key-agent_conversation_scroll::-webkit-scrollbar {
        width: 6px;
    }
    .st-key-agent_conversation_scroll::-webkit-scrollbar-track {
        background: transparent;
    }
    .st-key-agent_conversation_scroll::-webkit-scrollbar-thumb {
        border-radius: 999px;
        background: rgba(14,116,144,.22);
    }

    [data-testid="stChatMessage"] {
        padding: .75rem .25rem;
        background: transparent;
    }
    [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
        color: #263f55;
        font-size: .93rem;
        line-height: 1.72;
        min-width: 0;
        overflow-wrap: anywhere;
    }
    /* Reports are Markdown documents inside a chat bubble. Streamlit's page-level
       heading scale is far too large here, so give chat documents their own
       compact type hierarchy. */
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h3 {
        color: #173b58 !important;
        letter-spacing: 0 !important;
        overflow-wrap: anywhere;
    }
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h1 {
        margin: 1rem 0 .5rem !important;
        padding-bottom: .38rem;
        border-bottom: 1px solid rgba(14,116,144,.14);
        font-size: 1.22rem !important;
        line-height: 1.35 !important;
        font-weight: 820 !important;
    }
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h1:first-child {
        margin-top: 0 !important;
    }
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h2 {
        margin: .9rem 0 .38rem !important;
        font-size: 1.08rem !important;
        line-height: 1.4 !important;
        font-weight: 800 !important;
    }
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h3 {
        margin: .72rem 0 .32rem !important;
        font-size: 1rem !important;
        line-height: 1.45 !important;
        font-weight: 780 !important;
    }
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p {
        margin: 0 0 .62rem;
        font-size: .93rem;
        line-height: 1.72;
    }
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] ol,
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] ul {
        margin: .25rem 0 .7rem;
        padding-left: 1.35rem;
    }
    [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] li {
        margin: .2rem 0;
        padding-left: .08rem;
        line-height: 1.65;
    }
    [data-testid="stChatMessageContent"] [data-testid="stHeaderActionElements"] {
        display: none;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"])
    [data-testid="stChatMessageContent"] {
        padding: .72rem .9rem;
        border: 1px solid rgba(14,165,233,.12);
        border-radius: 16px 16px 4px 16px;
        background: linear-gradient(145deg, #eaf7ff, #f3fbff);
    }
    .st-key-agent_chat_input {
        position: sticky;
        bottom: .25rem;
        z-index: 50;
        padding: .2rem 0 .35rem;
        background: linear-gradient(180deg, rgba(244,250,254,0), rgba(244,250,254,.96) 28%);
    }
    .st-key-agent_chat_input [data-testid="stChatInput"] {
        border-color: rgba(14,116,144,.18);
        border-radius: 18px;
        background: rgba(255,255,255,.92);
        box-shadow: 0 12px 30px rgba(18,64,102,.1);
        backdrop-filter: blur(14px);
    }
    .agent-thinking {
        width: fit-content;
        display: flex;
        align-items: center;
        gap: .68rem;
        padding: .62rem .78rem;
        border: 1px solid rgba(14,165,233,.1);
        border-radius: 15px;
        background: rgba(240,249,255,.8);
    }
    .agent-thinking strong,
    .agent-thinking small { display: block; }
    .agent-thinking strong { color: #24516e; font-size: .82rem; }
    .agent-thinking small { color: #7890a3; font-size: .7rem; }
    .thinking-orb {
        position: relative;
        width: 34px;
        height: 34px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 3px;
        border-radius: 12px;
        background: linear-gradient(145deg, #0284c7, #22d3ee);
        box-shadow: 0 7px 16px rgba(14,165,233,.2);
        animation: agentBreathe 1.7s ease-in-out infinite;
    }
    .thinking-orb i {
        width: 3px;
        height: 3px;
        border-radius: 50%;
        background: white;
        animation: thinkingDot 1.15s ease-in-out infinite;
    }
    .thinking-orb i:nth-child(2) { animation-delay: .16s; }
    .thinking-orb i:nth-child(3) { animation-delay: .32s; }
    @keyframes agentBreathe {
        0%, 100% { transform: scale(.96); box-shadow: 0 7px 16px rgba(14,165,233,.16); }
        50% { transform: scale(1.04); box-shadow: 0 9px 24px rgba(14,165,233,.32); }
    }
    @keyframes thinkingDot {
        0%, 60%, 100% { transform: translateY(1px); opacity: .45; }
        30% { transform: translateY(-2px); opacity: 1; }
    }
    .recommendation-title {
        display: flex;
        align-items: center;
        gap: .6rem;
        margin-bottom: .55rem;
    }
    .recommendation-title > span {
        width: 32px;
        height: 32px;
        display: grid;
        place-items: center;
        border-radius: 10px;
        color: #7c3aed;
        background: #f3e8ff;
    }
    .recommendation-title strong,
    .recommendation-title small { display: block; }
    .recommendation-title strong { color: #3b3154; font-size: .88rem; }
    .recommendation-title small { color: #7c7190; font-size: .7rem; }

    @media (max-width: 900px) {
        .agent-chat-header { align-items: flex-start; flex-wrap: wrap; }
        .agent-header-meta { width: 100%; justify-content: flex-start; padding-left: 56px; }
        .agent-chat-title span { white-space: normal; }
        .st-key-agent_conversation_scroll {
            height: min(380px, calc(100vh - 360px)) !important;
            min-height: 260px;
        }
    }

    @media (max-height: 760px) and (min-width: 901px) {
        .st-key-agent_conversation_scroll {
            height: calc(100vh - 330px) !important;
            min-height: 280px;
        }
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(242, 250, 255, 0.96), rgba(230, 245, 252, 0.96));
        border-right: 1px solid rgba(14, 116, 144, 0.12);
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.4rem;
    }

    .sidebar-logo {
        padding: 1rem 0.8rem 1.1rem;
        margin: 0 0.2rem 1rem;
        border-radius: 16px;
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.13), rgba(34, 211, 238, 0.14));
        border: 1px solid rgba(14, 165, 233, 0.18);
    }
    .logo-mark {
        width: 48px;
        height: 48px;
        display: grid;
        place-items: center;
        border-radius: 15px;
        background: linear-gradient(135deg, #0ea5e9, #22d3ee);
        color: white;
        font-size: 1.45rem;
        font-weight: 800;
        box-shadow: 0 12px 24px rgba(14, 165, 233, 0.25);
        margin-bottom: 0.65rem;
    }
    .sidebar-title {
        font-size: 1.32rem;
        font-weight: 800;
        color: #0f3b5f;
        letter-spacing: 0;
        margin: 0;
    }
    .sidebar-subtitle {
        font-size: 0.82rem;
        color: var(--muted);
        margin-top: 0.15rem;
    }
    .sidebar-footer {
        margin: 1rem 0.2rem 0;
        padding: 0.9rem;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.58);
        border: 1px solid rgba(14, 116, 144, 0.10);
        color: var(--muted);
        font-size: 0.78rem;
    }

    .stButton > button {
        border-radius: 12px;
        border: 1px solid rgba(14, 116, 144, 0.14);
        background: rgba(255,255,255,0.76);
        color: #174366;
        font-weight: 650;
        min-height: 2.55rem;
        transition: all 0.18s ease;
    }
    .stButton > button:hover {
        border-color: rgba(14, 165, 233, 0.42);
        color: #0369a1;
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(14, 116, 144, 0.10);
    }

    .app-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        padding: 1rem 1.1rem;
        border: 1px solid var(--line);
        border-radius: 18px;
        background: rgba(255,255,255,0.72);
        box-shadow: var(--soft-shadow);
        backdrop-filter: blur(12px);
        margin-bottom: 1.05rem;
    }
    .page-title {
        font-size: 1.52rem;
        line-height: 1.15;
        font-weight: 800;
        color: #123657;
        margin: 0;
    }
    .page-desc {
        color: var(--muted);
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }
    .header-status {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 0.42rem;
        align-items: center;
        color: var(--muted);
        font-size: 0.82rem;
    }

    .hero {
        display: grid;
        grid-template-columns: minmax(0, 1.55fr) minmax(260px, 0.75fr);
        gap: 1rem;
        align-items: stretch;
        padding: 1.25rem;
        border-radius: 20px;
        background:
            linear-gradient(135deg, rgba(14, 165, 233, 0.13), rgba(34, 211, 238, 0.11)),
            rgba(255,255,255,0.74);
        border: 1px solid rgba(14, 165, 233, 0.17);
        box-shadow: var(--shadow);
        margin-bottom: 1rem;
    }
    .hero h1 {
        margin: 0 0 0.35rem;
        font-size: 2.05rem;
        line-height: 1.15;
        color: #0f3556;
        letter-spacing: 0;
    }
    .hero .tagline {
        color: #0477a8;
        font-weight: 750;
        font-size: 1rem;
        margin-bottom: 0.55rem;
    }
    .hero p {
        color: #456178;
        max-width: 850px;
        margin: 0;
        line-height: 1.75;
        font-size: 0.96rem;
    }
    .hero-status-grid {
        display: grid;
        gap: 0.65rem;
        align-content: center;
    }
    .hero-status-card {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        padding: 0.82rem 0.9rem;
        background: rgba(255,255,255,0.72);
        border: 1px solid rgba(14, 116, 144, 0.12);
        border-radius: 14px;
        box-shadow: 0 10px 22px rgba(14, 116, 144, 0.07);
    }
    .multimodal-shell {
        margin: 0.35rem 0 1rem;
        padding: 1rem;
        border: 1px solid rgba(14, 116, 144, 0.14);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.78);
        box-shadow: var(--soft-shadow);
    }
    .multimodal-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 0.8rem;
    }
    .multimodal-heading span {
        display: block;
        color: #64748b;
        font-size: 0.74rem;
        font-weight: 750;
    }
    .multimodal-heading strong {
        display: block;
        margin-top: 0.1rem;
        color: #123657;
        font-size: 1.02rem;
    }
    .fusion-chip {
        padding: 0.34rem 0.68rem;
        border: 1px solid rgba(14, 165, 233, 0.18);
        border-radius: 999px;
        color: #0369a1;
        background: #eef9ff;
        font-size: 0.76rem;
        font-weight: 750;
        white-space: nowrap;
    }
    .modality-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.7rem;
    }
    .modality-card {
        min-width: 0;
        padding: 0.82rem;
        border: 1px solid rgba(14, 116, 144, 0.12);
        border-radius: 10px;
        background: #f8fcff;
    }
    .modality-card.available { border-top: 3px solid #14b8a6; }
    .modality-card.missing { border-top: 3px solid #cbd5e1; }
    .modality-card-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        margin-bottom: 0.6rem;
    }
    .modality-mark {
        width: 30px;
        height: 30px;
        display: grid;
        place-items: center;
        border-radius: 9px;
        color: #0369a1;
        background: #e0f2fe;
        font-size: 0.8rem;
        font-weight: 850;
    }
    .modality-state {
        color: #64748b;
        font-size: 0.7rem;
        font-weight: 700;
    }
    .modality-card strong { color: #17324d; font-size: 0.9rem; }
    .modality-card p {
        min-height: 2.6rem;
        margin: 0.34rem 0 0;
        color: #60758a;
        font-size: 0.76rem;
        line-height: 1.55;
        overflow-wrap: anywhere;
    }
    .status-ring {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: conic-gradient(from 20deg, #10b981, #22d3ee, #0ea5e9, #10b981);
        display: grid;
        place-items: center;
    }
    .status-ring::after {
        content: "";
        width: 22px;
        height: 22px;
        border-radius: 50%;
        background: white;
    }

    .metric-card, .soft-card, .agent-card, .table-card {
        border-radius: var(--radius);
        border: 1px solid var(--line);
        background: var(--panel);
        box-shadow: var(--soft-shadow);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    }
    .metric-card:hover, .soft-card:hover, .agent-card:hover, .table-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow);
        border-color: rgba(14, 165, 233, 0.28);
    }
    .metric-card {
        min-height: 134px;
        padding: 1rem;
        position: relative;
        overflow: hidden;
    }
    .metric-card::after {
        content: "";
        position: absolute;
        width: 112px;
        height: 112px;
        right: -34px;
        top: -36px;
        border-radius: 50%;
        background: rgba(14, 165, 233, 0.08);
    }
    .metric-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.6rem;
        color: var(--muted);
        font-weight: 700;
        font-size: 0.92rem;
    }
    .metric-icon {
        width: 38px;
        height: 38px;
        border-radius: 12px;
        display: grid;
        place-items: center;
        color: white;
        background: linear-gradient(135deg, #0ea5e9, #22d3ee);
        box-shadow: 0 10px 20px rgba(14, 165, 233, 0.18);
        font-size: 1.1rem;
    }
    .metric-value {
        margin-top: 0.65rem;
        font-size: 2rem;
        line-height: 1;
        font-weight: 850;
        color: #0f3556;
    }
    .metric-unit {
        color: var(--muted);
        font-size: 0.98rem;
        font-weight: 700;
        margin-left: 0.2rem;
    }
    .metric-subtitle {
        color: var(--muted);
        margin-top: 0.55rem;
        font-size: 0.86rem;
    }

    .soft-card, .table-card, .agent-card {
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .section-title {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.7rem;
        margin-bottom: 0.8rem;
    }
    .section-title h3 {
        margin: 0;
        color: #123657;
        font-size: 1.08rem;
    }
    .section-subtitle {
        color: var(--muted);
        font-size: 0.84rem;
    }

    .agent-card {
        background:
            linear-gradient(135deg, rgba(79, 70, 229, 0.11), rgba(14, 165, 233, 0.10)),
            rgba(255,255,255,0.84);
        border-color: rgba(99, 102, 241, 0.20);
    }
    .agent-head {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
        margin-bottom: 0.8rem;
    }
    .agent-title {
        font-size: 1.16rem;
        font-weight: 850;
        color: #1e2f66;
        margin: 0;
    }
    .risk-score {
        font-size: 2.1rem;
        line-height: 1;
        font-weight: 900;
        color: #1d4ed8;
    }
    .risk-bar {
        height: 10px;
        border-radius: 999px;
        background: rgba(100, 116, 139, 0.15);
        overflow: hidden;
        margin: 0.7rem 0;
    }
    .risk-bar-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #22c55e, #f59e0b, #ef4444);
    }
    .factor-list {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.65rem;
    }

    .camera-card {
        border-radius: var(--radius);
        border: 1px solid var(--line);
        background: var(--panel);
        box-shadow: var(--soft-shadow);
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .camera-card-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.8rem;
        color: #17324d;
    }
    .camera-frame {
        width: 100%;
        aspect-ratio: 16 / 9;
        overflow: hidden;
        border-radius: 12px;
        border: 1px solid rgba(14, 116, 144, 0.14);
        background: #0f172a;
        display: grid;
        place-items: center;
    }
    .camera-frame img {
        width: 100%;
        height: 100%;
        display: block;
        object-fit: cover;
    }
    .camera-footnote {
        color: var(--muted);
        font-size: 0.78rem;
        margin-top: 0.58rem;
        line-height: 1.55;
    }

    .pill, .status-pill, .risk-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.38rem;
        border-radius: 999px;
        padding: 0.28rem 0.62rem;
        font-weight: 750;
        font-size: 0.78rem;
        white-space: nowrap;
    }
    .pill {
        color: #075985;
        background: rgba(14, 165, 233, 0.10);
        border: 1px solid rgba(14, 165, 233, 0.16);
    }
    .status-normal {
        color: #047857;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.20);
    }
    .status-warning {
        color: #b45309;
        background: rgba(245, 158, 11, 0.13);
        border: 1px solid rgba(245, 158, 11, 0.22);
    }
    .status-danger {
        color: #b91c1c;
        background: rgba(239, 68, 68, 0.13);
        border: 1px solid rgba(239, 68, 68, 0.22);
    }
    .status-agent {
        color: #5b21b6;
        background: rgba(139, 92, 246, 0.13);
        border: 1px solid rgba(139, 92, 246, 0.22);
    }
    .status-muted {
        color: #475569;
        background: rgba(100, 116, 139, 0.11);
        border: 1px solid rgba(100, 116, 139, 0.17);
    }
    .dot {
        width: 0.54rem;
        height: 0.54rem;
        border-radius: 50%;
        display: inline-block;
        background: var(--green);
        box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.12);
    }
    .dot.offline {
        background: #94a3b8;
        box-shadow: 0 0 0 4px rgba(148, 163, 184, 0.12);
    }
    .dot.warn {
        background: var(--orange);
        box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.14);
    }
    .dot.danger {
        background: var(--red);
        box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.14);
    }

    .data-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        overflow: hidden;
        border-radius: 14px;
        border: 1px solid rgba(14, 116, 144, 0.12);
        font-size: 0.86rem;
    }
    .data-table th {
        background: rgba(224, 242, 254, 0.72);
        color: #174366;
        text-align: left;
        padding: 0.72rem 0.75rem;
        font-size: 0.8rem;
    }
    .data-table td {
        padding: 0.72rem 0.75rem;
        border-top: 1px solid rgba(14, 116, 144, 0.08);
        color: #24435f;
        background: rgba(255,255,255,0.56);
    }
    .data-table tr:hover td {
        background: rgba(240, 249, 255, 0.86);
    }

    .step-line {
        display: flex;
        gap: 0.35rem;
        align-items: center;
        flex-wrap: wrap;
        margin: 0.7rem 0 0.45rem;
    }
    .step-node {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 3.1rem;
        padding: 0.34rem 0.48rem;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 750;
        border: 1px solid rgba(100, 116, 139, 0.16);
        background: rgba(241, 245, 249, 0.82);
        color: #64748b;
    }
    .step-node.done {
        background: rgba(16, 185, 129, 0.12);
        color: #047857;
        border-color: rgba(16, 185, 129, 0.22);
    }
    .step-node.current {
        background: linear-gradient(135deg, #0ea5e9, #22d3ee);
        color: white;
        border-color: transparent;
        box-shadow: 0 10px 20px rgba(14, 165, 233, 0.18);
    }
    .step-arrow {
        color: #94a3b8;
    }

    .flow-grid {
        display: grid;
        grid-template-columns: repeat(6, minmax(120px, 1fr));
        gap: 0.55rem;
        align-items: stretch;
    }
    .flow-node {
        position: relative;
        padding: 0.82rem 0.68rem;
        border-radius: 14px;
        background: rgba(255,255,255,0.72);
        border: 1px solid rgba(14, 116, 144, 0.13);
        min-height: 104px;
    }
    .flow-node.agent {
        background: linear-gradient(135deg, rgba(79, 70, 229, 0.16), rgba(14, 165, 233, 0.13));
        border-color: rgba(79, 70, 229, 0.24);
    }
    .flow-title {
        font-weight: 850;
        color: #113b60;
        margin-bottom: 0.3rem;
    }
    .flow-desc {
        color: var(--muted);
        font-size: 0.78rem;
        line-height: 1.55;
    }
    .flow-arrow {
        display: none;
    }
    .flow-caption {
        margin-top: 0.75rem;
        text-align: center;
        color: #0477a8;
        font-weight: 800;
        letter-spacing: 0.05rem;
    }

    .alert-item {
        padding: 0.78rem 0.82rem;
        border-radius: 14px;
        border: 1px solid rgba(14, 116, 144, 0.12);
        background: rgba(255,255,255,0.66);
        margin-bottom: 0.55rem;
    }
    .alert-item.high {
        border-color: rgba(239, 68, 68, 0.28);
        background: rgba(254, 242, 242, 0.82);
    }

    .kv-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.6rem;
    }
    .kv-item {
        padding: 0.65rem 0.7rem;
        border-radius: 12px;
        background: rgba(248, 252, 255, 0.76);
        border: 1px solid rgba(14, 116, 144, 0.10);
    }
    .kv-label {
        color: var(--muted);
        font-size: 0.76rem;
        margin-bottom: 0.18rem;
    }
    .kv-value {
        color: #17324d;
        font-weight: 800;
    }

    @media (max-width: 1100px) {
        .hero { grid-template-columns: 1fr; }
        .flow-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .modality-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .app-header { align-items: flex-start; flex-direction: column; }
        .header-status { justify-content: flex-start; }
    }
    @media (max-width: 720px) {
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
        .hero h1 { font-size: 1.55rem; }
        .flow-grid { grid-template-columns: 1fr; }
        .modality-grid { grid-template-columns: 1fr; }
        .multimodal-heading { align-items: flex-start; flex-direction: column; }
        .kv-grid { grid-template-columns: 1fr; }
    }

    /* Production workspace: restrained, dense and data-first. */
    :root {
        --bg: #f3f6f8;
        --panel: #ffffff;
        --panel-strong: #ffffff;
        --line: #dbe3ea;
        --text: #1f3347;
        --muted: #66788a;
        --blue: #087eae;
        --cyan: #0891a8;
        --shadow: 0 2px 8px rgba(31, 51, 71, 0.06);
        --soft-shadow: 0 1px 3px rgba(31, 51, 71, 0.05);
        --radius: 8px;
    }
    .stApp {
        background: var(--bg);
    }
    .block-container {
        max-width: 1600px;
        padding-top: .8rem;
        padding-bottom: 1.5rem;
        animation: none;
    }
    [data-testid="stSidebar"] {
        background: #f8fafb;
        border-right: 1px solid #dbe3ea;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0;
    }
    [data-testid="stSidebarHeader"] {
        min-height: 3.2rem;
        height: 3.2rem;
    }
    [data-testid="stSidebarUserContent"] {
        padding-top: .1rem;
    }
    [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {
        gap: 0 !important;
    }
    .sidebar-logo {
        display: grid;
        grid-template-columns: 40px minmax(0, 1fr);
        align-items: center;
        gap: .7rem;
        margin: 0 .2rem .45rem;
        padding: .5rem .45rem .8rem;
        border: 0;
        border-bottom: 1px solid #dbe3ea;
        border-radius: 0;
        background: transparent;
    }
    .logo-mark {
        width: 40px;
        height: 40px;
        margin: 0;
        border-radius: 7px;
        background: #087eae;
        box-shadow: none;
        font-size: 1.12rem;
    }
    .sidebar-brand-copy { min-width: 0; }
    .sidebar-title {
        color: #17364e;
        font-size: 1.08rem;
        line-height: 1.25;
    }
    .sidebar-subtitle {
        max-width: 220px;
        margin-top: .12rem;
        color: #718394;
        font-size: .67rem;
        line-height: 1.35;
    }
    .sidebar-section-label {
        display: block;
        box-sizing: border-box;
        position: relative;
        z-index: 3;
        width: 100%;
        height: auto;
        min-height: 0;
        margin: .9rem 0 .38rem;
        padding: 0 .7rem;
        background: #f8fafb;
        color: #7b8b99;
        font-size: .68rem;
        font-weight: 700;
        line-height: 1.25;
        letter-spacing: .08em;
        pointer-events: none;
    }
    [class*="st-key-sidebar_nav_group_"] {
        position: relative;
        z-index: 1;
        margin: 0 .3rem .45rem !important;
        padding: 0;
        overflow: hidden;
        border-radius: 8px;
    }
    [class*="st-key-sidebar_nav_group_"] [data-testid="stVerticalBlock"] {
        gap: .22rem !important;
    }
    [class*="st-key-sidebar_nav_group_"] [data-testid="stElementContainer"] {
        margin: 0 !important;
    }
    [data-testid="stSidebar"] .stButton {
        position: relative;
        z-index: 1;
        margin: 0;
    }
    [data-testid="stSidebar"] .stButton > button {
        box-sizing: border-box;
        width: 100%;
        height: 2.7rem !important;
        min-height: 2.7rem !important;
        justify-content: flex-start !important;
        gap: .68rem !important;
        padding: 0 .8rem !important;
        border-color: transparent;
        border-radius: 8px;
        background: transparent;
        box-shadow: none;
        text-align: left;
        color: #37536a;
        font-size: .88rem;
        font-weight: 560;
    }
    [data-testid="stSidebar"] .stButton > button > div,
    [data-testid="stSidebar"] .stButton > button [data-testid="stMarkdownContainer"] {
        flex: 0 1 auto;
        width: auto;
        justify-content: flex-start !important;
        text-align: left !important;
    }
    [data-testid="stSidebar"] .stButton > button p {
        margin: 0;
        text-align: left !important;
        white-space: nowrap;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        color: #075f82;
        border-color: #c5e3ee;
        border-left: 3px solid #0b8fbd;
        background: #e9f5f9;
        font-weight: 700;
    }
    [data-testid="stSidebar"] .stButton > button span[data-testid="stIconMaterial"] {
        flex: 0 0 1.25rem;
        width: 1.25rem;
        color: #607f94;
        font-size: 1.15rem;
        text-align: center;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] span[data-testid="stIconMaterial"] {
        color: #087eae;
    }
    .stButton > button {
        min-height: 2.35rem;
        border-radius: 6px;
        border-color: #cfd9e2;
        background: #ffffff;
        box-shadow: none;
        transition: border-color .15s ease, background-color .15s ease;
    }
    .stButton > button:hover {
        color: #075f82;
        border-color: #8fc4d8;
        background: #f3fafc;
        transform: none;
        box-shadow: none;
    }
    .app-header {
        margin-bottom: .85rem;
        padding: .2rem .05rem .8rem;
        border: 0;
        border-bottom: 1px solid #dbe3ea;
        border-radius: 0;
        background: transparent;
        box-shadow: none;
        backdrop-filter: none;
    }
    .page-title { font-size: 1.35rem; color: #17364e; }
    .page-desc { margin-top: .18rem; font-size: .82rem; }
    .header-time { color: #718294; font-variant-numeric: tabular-nums; }
    .metric-card, .soft-card, .agent-card, .table-card,
    .multimodal-shell, .camera-card, .alert-item, .agent-chat-header,
    .agent-side-intro, .flow-node, .kv-item {
        border-radius: 8px;
        border-color: #dbe3ea;
        background: #ffffff;
        box-shadow: var(--soft-shadow);
        backdrop-filter: none;
        transition: none;
    }
    .metric-card:hover, .soft-card:hover, .agent-card:hover, .table-card:hover {
        transform: none;
        border-color: #dbe3ea;
        box-shadow: var(--soft-shadow);
    }
    .metric-card {
        min-height: 108px;
        padding: .82rem .9rem;
    }
    .metric-card::after { display: none; }
    .metric-top { font-size: .82rem; }
    .metric-icon {
        width: 30px;
        height: 30px;
        border-radius: 6px;
        color: #087eae;
        background: #eaf5f8;
        box-shadow: none;
        font-size: .86rem;
    }
    .metric-value { margin-top: .45rem; font-size: 1.65rem; color: #17364e; }
    .metric-unit { font-size: .82rem; }
    .metric-subtitle { margin-top: .38rem; font-size: .76rem; }
    .soft-card, .table-card, .agent-card { padding: .9rem; margin-bottom: .8rem; }
    .agent-card {
        border-left: 3px solid #7467c7;
        background: #ffffff;
    }
    .agent-title { color: #303b57; }
    .agent-side-intro {
        color: #334e63;
        background: #ffffff;
    }
    .agent-side-intro span { color: #087eae; }
    .agent-side-intro strong { color: #17364e; }
    .agent-side-intro p { color: #66788a; }
    .agent-brand-mark, .thinking-orb {
        border-radius: 7px;
        background: #087eae;
        box-shadow: none;
    }
    .agent-chat-header { border-radius: 8px; box-shadow: var(--soft-shadow); }
    .st-key-agent_conversation_scroll {
        border-radius: 8px !important;
        background: #ffffff;
        box-shadow: var(--soft-shadow);
        clip-path: inset(0 round 8px);
    }
    .st-key-agent_chat_input [data-testid="stChatInput"] {
        border-radius: 8px;
        box-shadow: var(--soft-shadow);
        backdrop-filter: none;
    }
    .multimodal-shell { padding: .85rem; }
    .modality-grid { gap: .55rem; }
    .modality-card {
        padding: .72rem;
        border-radius: 6px;
        background: #fbfcfd;
    }
    .modality-card.available { border-top: 1px solid #dbe3ea; border-left: 3px solid #168a72; }
    .modality-card.missing { border-top: 1px solid #dbe3ea; border-left: 3px solid #aab7c2; }
    .modality-mark { border-radius: 5px; }
    .fusion-chip, .status-pill, .pill { box-shadow: none; }
    .section-title { margin: .9rem 0 .55rem; }
    .section-title h3 { font-size: 1rem; color: #17364e; }
    .section-subtitle { font-size: .78rem; }
    .kv-grid { gap: .45rem; }
    .kv-item {
        padding: .58rem .65rem;
        border-radius: 6px;
        background: #f9fbfc;
        box-shadow: none;
    }
    .data-table { border-radius: 8px; border-color: #dbe3ea; }
    .data-table th { padding: .62rem .68rem; background: #eef3f6; color: #334e63; }
    .data-table td { padding: .62rem .68rem; background: #ffffff; border-top-color: #e7edf1; }
    .data-table tr:hover td { background: #f7fafb; }
    .alert-item { border-radius: 6px; background: #ffffff; }
    .alert-item.high { background: #fff8f7; }
    .step-node { border-radius: 5px; }
    .step-node.current { background: #087eae; box-shadow: none; }
    .risk-bar { border-radius: 3px; background: #e7edf1; }
    .risk-bar-fill { border-radius: 3px; background: #087eae; }
    .camera-card, .camera-frame { border-radius: 8px; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #dbe3ea;
        border-radius: 8px;
        background: #ffffff;
        box-shadow: var(--soft-shadow);
    }
    [data-testid="stExpander"] {
        border-color: #dbe3ea;
        border-radius: 8px;
        background: #ffffff;
    }
    [data-baseweb="select"] > div,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stChatInput"] textarea {
        border-radius: 6px !important;
    }
    .toolbar-label {
        margin-bottom: .35rem;
        color: #405a70;
        font-size: .86rem;
        font-weight: 650;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
