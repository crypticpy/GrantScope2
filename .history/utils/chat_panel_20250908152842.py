import streamlit as st
import os
from loaders.llama_index_setup import tool_query, stream_query, resolve_chart_context
from utils.utils import is_feature_enabled
from utils.app_state import get_selected_chart


def _inject_right_sidebar_css_once(width_px: int = 420) -> None:
    """Inject CSS to create a fixed right-side chat area and reserve space in the main content."""
    key = "_chat_right_sidebar_css"
    try:
        if st.session_state.get(key):
            return
    except Exception:
        # session_state might be unavailable in some contexts; continue with injection
        pass

    css = f"""
    <style>
    :root {{
      --chat-panel-top: 4rem;
    }}

    /* Make the chat container (column that includes our anchor) sticky with its own scroll,
       without modifying the main content width or margins. */
    div[data-testid="stVerticalBlock"]:has(.chat-right-anchor) {{
      position: sticky;
      top: var(--chat-panel-top);
      align-self: flex-start;
      max-height: calc(100vh - var(--chat-panel-top));
      overflow-y: auto;
      padding-bottom: 0.75rem;
      box-sizing: border-box;
    }}

    /* Allow chat messages to use full width of the chat column */
    div[data-testid="stVerticalBlock"]:has(.chat-right-anchor) div[data-testid="stChatMessage"] {{
      max-width: none;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    try:
        st.session_state[key] = True
    except Exception:
        pass


def _chat_right_anchor(state_key: str) -> None:
    """Emit a marker so CSS can target the enclosing container as the right chat panel."""
    st.markdown(
        f'<div class="chat-right-anchor" id="chat-right-{state_key}"></div>', unsafe_allow_html=True
    )


def _inject_sidebar_chat_css_once() -> None:
    """Inject CSS to anchor the chat input at the bottom and make only the chat history scroll."""
    key = "_chat_sidebar_css"
    try:
        if st.session_state.get(key):
            return
    except Exception:
        pass

    try:
        offset_px = int(os.getenv("GS_CHAT_SIDEBAR_OFFSET_PX", "240"))
    except Exception:
        offset_px = 240
    try:
        vh_pct = int(os.getenv("GS_CHAT_SIDEBAR_VH", "55"))
    except Exception:
        vh_pct = 55

    css = f"""
    <style>
    :root {{
      --gs-chat-offset: {offset_px}px;
    }}
    /* Root chat container: responsive height (anchored by flex layout) */
    :is(section, div)[data-testid="stSidebar"] .gs-chat-root {{
      display: flex;
      flex-direction: column;
      height: clamp(320px, {vh_pct}vh, calc(100vh - 1rem));
      max-height: calc(100vh - 1rem);
      overflow: hidden; /* prevent the whole sidebar from scrolling due to chat */
      box-sizing: border-box;
    }}
    /* History region: scrolls internally above the input */
    :is(section, div)[data-testid="stSidebar"] .gs-chat-root .gs-chat-history {{
      flex: 1 1 auto;
      min-height: 0; /* allow flex child to shrink for proper scrolling */
      overflow-y: auto;
      padding-bottom: 0.5rem;
    }}
    /* Input region: pinned at bottom of chat root */
    :is(section, div)[data-testid="stSidebar"] .gs-chat-root .gs-chat-input {{
      flex: 0 0 auto;
      background: inherit;
      padding-top: 0.5rem;
      border-top: 1px solid rgba(128, 128, 128, 0.35);
    }}
    /* Allow chat messages to use full width within the sidebar chat panel */
    :is(section, div)[data-testid="stSidebar"] .gs-chat-root div[data-testid="stChatMessage"] {{
      max-width: none;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    try:
        st.session_state[key] = True
    except Exception:
        pass


def _inject_sidebar_layout_css_once() -> None:
    """Inject CSS to make the sidebar a flex column and anchor the chat block to the viewport bottom (no spacer required)."""
    key = "_chat_sidebar_layout_css"
    try:
        if st.session_state.get(key):
            return
    except Exception:
        # session_state might not be available; continue with injection
        pass

    css = """
    <style>
    /* Make the entire sidebar inner content a flex column when our chat anchor is present */
    :is(section, div)[data-testid="stSidebar"] > div:has(.chat-sidebar-anchor) {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }
    /* Default all top-level sidebar blocks to natural height */
    :is(section, div)[data-testid="stSidebar"] > div:has(.chat-sidebar-anchor) > div[data-testid="stVerticalBlock"] {
      flex: 0 0 auto;
    }
    /* Push the block that contains the chat root to the bottom of the viewport */
    :is(section, div)[data-testid="stSidebar"] > div:has(.chat-sidebar-anchor) > div[data-testid="stVerticalBlock"]:has(.gs-chat-root) {
      margin-top: auto;
    }
    /* Neutralize any legacy spacer so it does not consume space */
    :is(section, div)[data-testid="stSidebar"] .gs-sidebar-spacer {
      display: none !important;
      height: 0 !important;
      padding: 0 !important;
      margin: 0 !important;
      flex: 0 0 auto !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    try:
        st.session_state[key] = True
    except Exception:
        pass


def _chat_sidebar_anchor(state_key: str) -> None:
    """Emit a marker so CSS can target the enclosing sidebar container for chat layout."""
    st.markdown(
        f'<div class="chat-sidebar-anchor" id="chat-sidebar-{state_key}"></div>',
        unsafe_allow_html=True,
    )


def _audience_preface() -> str:
    """Return a preface to guide the assistant tone based on user experience level."""
    try:
        from utils.app_state import get_session_profile  # deferred import

        prof = get_session_profile()
        if prof and getattr(prof, "experience_level", "new") == "new":
            return (
                "Explain like I'm new to grants. Use short sentences and plain language. "
                "Give 3 clear next steps at the end."
            )
    except Exception:
        pass
    # Default: concise professional tone
    return "Be concise and specific in your analysis."


def _get_starter_prompts() -> list[str]:
    """Return newbie-friendly starter prompts, or empty list for experienced users.

    This helper is imported by tests to validate prompt quality and is used by the
    chat UI to present a dropdown of starter questions for newcomers.
    """
    try:
        from utils.app_state import get_session_profile  # deferred import

        prof = get_session_profile()
        if prof and getattr(prof, "experience_level", "new") == "new":
            return [
                "What are my first 3 steps to get grant ready for this project?",
                "Am I eligible for typical funders for schools or nonprofits?",
                "Help me write a simple 1-paragraph need statement.",
            ]
    except Exception:
        pass
    return []


def chat_panel(df, pre_prompt: str, state_key: str, title: str = "AI Assistant"):
    """Render a chat panel with optional streaming + cancel support behind a feature flag."""
    # Select chat UI location based on env flag; default to sidebar
    # _inject_right_sidebar_css_once()  # disabled

    # Wrap the entire chat in a single container so CSS can fix/anchor it as one unit
    ui_mode = str(os.getenv("GS_CHAT_UI_MODE", "sidebar")).strip().lower()
    if ui_mode == "sidebar_popover":
        container = st.sidebar.popover(title, use_container_width=True)
    elif ui_mode == "sidebar":
        container = st.sidebar.container()
    else:
        container = st.container()
    # Inject CSS for anchored input and scrolling history in the sidebar mode
    if ui_mode == "sidebar":
        _inject_sidebar_layout_css_once()
        _inject_sidebar_chat_css_once()
    with container:
        if ui_mode == "sidebar":
            _chat_sidebar_anchor(state_key)
        else:
            _chat_right_anchor(state_key)

        history_key = f"chat_{state_key}"
        cancel_key = f"chat_cancel_{state_key}"
        running_key = f"chat_running_{state_key}"
        streaming_enabled = is_feature_enabled("GS_ENABLE_CHAT_STREAMING", default=False)

        if history_key not in st.session_state:
            st.session_state[history_key] = []
        if cancel_key not in st.session_state:
            st.session_state[cancel_key] = False
        if running_key not in st.session_state:
            st.session_state[running_key] = False

        # Resolve chart-specific context once per render
        chart_id = get_selected_chart(None)
        extra_ctx = resolve_chart_context(chart_id) if chart_id else None

        # Chat root with internal scroll area (history) and fixed bottom input
        with st.container():
            st.markdown(
                f'<div class="gs-chat-root" id="gs-chat-root-{state_key}">', unsafe_allow_html=True
            )

            st.subheader(title)

            # History (scrolling) region
            with st.container():
                st.markdown(
                    f'<div class="gs-chat-history" id="gs-chat-history-{state_key}">',
                    unsafe_allow_html=True,
                )

                if chart_id and extra_ctx:
                    st.caption(f"Using chart context: {chart_id}")
                elif chart_id and not extra_ctx:
                    st.info(
                        "Selected chart has no specific context mapping yet; using page-level context."
                    )
                else:
                    st.info("No chart selected; using page-level context.")

                # Replay history so new messages appear ABOVE the input
                for role, content in st.session_state[history_key]:
                    with st.chat_message(role):
                        st.markdown(content)

                st.markdown("</div>", unsafe_allow_html=True)

            # Bottom-anchored input region
            with st.container():
                st.markdown(
                    f'<div class="gs-chat-input" id="gs-chat-input-{state_key}">',
                    unsafe_allow_html=True,
                )

                # Starter prompts for newcomers — presented as a dropdown
                try:
                    starters = _get_starter_prompts()
                    if starters:
                        sentinel = "Unsure what to ask — select a starter"
                        select_key = f"starter_select_{state_key}"
                        # Ensure a default value exists only once per session
                        if select_key not in st.session_state:
                            st.session_state[select_key] = sentinel
                        choice = st.selectbox(
                            sentinel,
                            options=[sentinel] + starters,
                            index=(
                                [sentinel]
                                + starters.index(st.session_state.get(select_key, sentinel))
                                if False
                                else 0
                            ),
                            key=select_key,
                        )
                        if choice and choice != sentinel:
                            st.session_state[f"chat_input_{state_key}"] = choice
                            st.session_state[f"chat_autosend_{state_key}"] = True
                            # Reset dropdown so it doesn't trigger repeatedly on rerun
                            st.session_state[select_key] = sentinel
                            st.rerun()
                except Exception:
                    pass

                with st.form(key=f"chat_form_{state_key}", clear_on_submit=True):
                    user_input = st.text_input(
                        "Ask a question about this view…", key=f"chat_input_{state_key}"
                    )
                    submitted = st.form_submit_button("Send")
                st.markdown("</div>", unsafe_allow_html=True)  # close gs-chat-input
                st.markdown("</div>", unsafe_allow_html=True)  # close gs-chat-root

        # Auto-send when a starter was clicked
        autosend_key = f"chat_autosend_{state_key}"
        if not submitted and st.session_state.get(autosend_key):
            submitted = True
            user_input = st.session_state.get(f"chat_input_{state_key}")
            st.session_state[autosend_key] = False

        # Handle submit outside the layout containers so we don't render messages below the input
        if submitted and user_input:
            # Record user message in history
            st.session_state[history_key].append(("user", user_input))

            if streaming_enabled:
                # Accumulate streamed content, then append to history and rerun so it appears in the history region
                st.session_state[cancel_key] = False
                st.session_state[running_key] = True

                parts: list[str] = []
                error_text: str | None = None
                try:
                    preface = _audience_preface()
                    pre_prompt_user = f"{preface}\n\n{pre_prompt}".strip()
                    pre_prompt_eff = (
                        f"{pre_prompt_user} Additional Chart Context: {extra_ctx}"
                        if extra_ctx
                        else pre_prompt_user
                    )
                    for delta in stream_query(df, user_input, pre_prompt_eff):
                        if st.session_state.get(cancel_key):
                            parts.append("\n\n[Cancelled by user]")
                            break
                        if delta:
                            parts.append(delta)
                except (RuntimeError, ValueError, Exception) as e:
                    error_text = f"Streaming error: {e}"

                if error_text:
                    final_answer = error_text
                else:
                    final_answer = "".join(parts).strip()
                    if not final_answer:
                        # Fallback to non-streaming path if the stream produced no visible content
                        try:
                            preface = _audience_preface()
                            pre_prompt_eff = f"{preface}\n\n{pre_prompt}".strip()
                            fallback = tool_query(df, user_input, pre_prompt_eff, extra_ctx)
                            final_answer = (
                                fallback if str(fallback).strip() else "_No content produced._"
                            )
                        except Exception as e:
                            final_answer = f"Streaming yielded no content and fallback failed: {e}"

                st.session_state[running_key] = False
                st.session_state[history_key].append(("assistant", final_answer))
                st.rerun()
            else:
                with st.spinner("Thinking…"):
                    try:
                        preface = _audience_preface()
                        pre_prompt_eff = f"{preface}\n\n{pre_prompt}".strip()
                        answer = tool_query(df, user_input, pre_prompt_eff, extra_ctx)
                    except (RuntimeError, ValueError, Exception) as e:
                        answer = f"Sorry, I couldn't process that: {e}"
                st.session_state[history_key].append(("assistant", answer))
                st.rerun()
