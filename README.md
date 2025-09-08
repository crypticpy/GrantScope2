# GrantScope: The Grant Data Exploration Dashboard

## Overview
GrantScope is an interactive tool designed to aid grant analysts, grant writers, and individuals in comprehensively understanding and analyzing complex grant data. This tool leverages advanced data processing and visualization techniques to extract actionable insights from grant datasets, facilitating easier identification of funding opportunities, understanding funding trends, and enhancing grant writing and analysis efforts.

## Features
### Interactive Data Visualizations
- **Data Summary**: Offers a concise overview of the dataset, including total counts of unique grants, funders, and recipients. Visualize the top funders by total grant amount and understand the distribution of grants by funder type.
- **Grant Amount Visualizations**: Explore grant amounts through various lenses using interactive charts. Users can examine the distribution of grant amounts across different USD clusters, observe trends over time with scatter plots, and analyze grant amounts across geographical regions and subject areas using heatmaps.
- **Word Clouds**: Visualize the most common themes and keywords in grant descriptions across different segments, providing insights into the focus areas of funders and the nature of funded projects.
- **Treemaps**: Investigate the allocation of grant amounts by subject, population, and strategy. Treemaps allow for a hierarchical exploration of how funds are distributed among different categories.

### AI-Assisted Analysis
- **Contextual Prompts**: Each visualization and analysis section is equipped with an AI-assisted chat feature that generates custom prompts based on the specific context of the data being explored.
- **Predefined Questions**: Users can select from a set of predefined questions relevant to each chart or analysis, guiding them in uncovering key insights and patterns.
- **Custom Questions**: Users have the flexibility to ask their own questions related to the data, leveraging the power of natural language processing to obtain meaningful responses.
- **Focused Insights**: The AI provides focused and relevant insights based on the specific chart or analysis being viewed, avoiding confusion between different sections of the dashboard.

### Detailed Analysis Tools
- **Univariate Analysis**: Perform detailed statistical analysis on numeric columns to understand the distribution, variability, and central tendencies of grant amounts and other numerical data points.
- **Grant Relationship Analysis**: Explore the relationships between funders and recipients, grant amounts, and project subjects or populations served. This feature allows users to uncover patterns and connections within the grant ecosystem.
- **Grant Descriptions Deep Dive**: Dive into the details of grant descriptions using text analysis tools. Identify frequently used terms, analyze sentiment, and extract thematic clusters to gain a deeper understanding of grant narratives.

### User Roles and Customization
The dashboard supports different user roles, providing tailored experiences for grant analysts/writers and general users:
- **Grant Analyst/Writer**: Access to advanced analytics features, including detailed relationship analysis, trend analysis over time, and custom data filters for in-depth research.
- **Normal Grant User**: A simplified interface focusing on key visualizations such as data summaries, basic grant amount distributions, and word clouds, suitable for users seeking a general overview of the grant landscape.

### Downloadable Reports and Data
Users can download customized reports and data extracts based on their analysis, enabling offline review and integration into grant proposals or reports. This feature supports Excel and CSV formats for easy use in various applications.

## How to Use the Dashboard
1. Start by uploading your grant data file or using the preloaded dataset.
2. Select your user role to customize the dashboard experience according to your needs.
3. Explore the dashboard sections to visualize and analyze grant data. Utilize filters and interactive elements to tailor the analysis.
4. Engage with the AI-assisted chat feature to ask questions and gain insights specific to each chart or analysis.
5. Download data extracts and reports for further use.

## Technology Stack
This dashboard is built using Streamlit, enabling an interactive web application experience. Data visualization is powered by Plotly and Matplotlib for dynamic and static charts, respectively. Pandas and NumPy are used for data manipulation and analysis, while advanced text processing features leverage natural language processing libraries. The AI-assisted chat feature is implemented using OpenAI's GPT-5 and the LlamaIndex library.

## Usage
1. Access the web version of the dashboard at [grantscope.streamlit.app](https://grantscope.streamlit.app).

### Run on your own resources
1. Clone the repository to your local machine.
2. Install the required dependencies listed in the `requirements.txt` file.
3. Set up your OpenAI API key either as an environment variable or enter it through the dashboard's user interface.
4. Prepare your grant data in the required JSON format. You can either provide a file path to the JSON file or upload the file through the dashboard's user interface.
5. From the `GrantScope/` directory, run the app: `streamlit run app.py` (or from the repo root: `streamlit run GrantScope/app.py`).
6. Access the dashboard through your web browser at the provided URL.

## Configuration &amp; Secrets

GrantScope uses a centralized configuration module [GrantScope/config.py](GrantScope/config.py) that resolves values with the following precedence:
1) Streamlit st.secrets
2) Environment variables (including values loaded from a local .env)
3) Safe defaults

What this means:
- If running on Streamlit Community Cloud, add your keys using the “Secrets” UI. These override environment and .env values.
- For local development, create a .env file (not committed) from the provided template and set your values there.
- If neither st.secrets nor environment variables are set, some features may be disabled or will show UI to input an API key for the current run only (never persisted).

Expected keys and flags:
- OPENAI_API_KEY: OpenAI API key used by the LLM features
- CANDID_API_KEY: Candid API subscription key used by the fetcher
- OPENAI_MODEL: Optional model name (defaults to gpt-5)
- GS_ENABLE_CHAT_STREAMING: Optional feature flag for streaming chat (truthy: 1, true, yes, on)
- GS_ENABLE_LEGACY_ROUTER: Optional flag to enable the legacy single-page router (temporary)

Local development (.env):
1) Copy .env.example to .env
2) Fill in the values you need

Example .env:
OPENAI_API_KEY=
CANDID_API_KEY=
OPENAI_MODEL=gpt-5
GS_ENABLE_CHAT_STREAMING=0
GS_ENABLE_LEGACY_ROUTER=0

Streamlit Community Cloud (secrets.toml):
Set these keys in your app’s Secrets UI. Example:

OPENAI_API_KEY = "sk-..."
CANDID_API_KEY = "your_candid_key"
OPENAI_MODEL = "gpt-5"
GS_ENABLE_CHAT_STREAMING = "1"
GS_ENABLE_LEGACY_ROUTER = "0"

Where values are used:
- Candid key: used by the data fetcher in [GrantScope/fetch/fetch.py](GrantScope/fetch/fetch.py)
- OpenAI key and model: used by LLM setup in [GrantScope/loaders/llama_index_setup.py](GrantScope/loaders/llama_index_setup.py)

Security notes:
- Keys from st.secrets always take precedence and are never overwritten by UI input.
- When no secrets/env are present, a temporary UI field allows entering an API key for the current run only; it is not persisted to disk or session state.
### Navigation (Multipage)
- GrantScope now uses Streamlit's multipage navigation exclusively. Use the left sidebar to switch between pages such as Data Summary, Distribution, Scatter, Heatmap, Word Clouds, Treemaps, Relationships, and Top Categories.
- Sidebar controls (data upload, AI key input, and global "User Role") are centralized and shared across all pages. The selected "User Role" persists globally via session state so it remains consistent as you navigate.
- You can explore with the bundled sample dataset or upload your own JSON file (see the "Sample & Schema" expander in the sidebar for details and a downloadable sample).

### Experimental: Chat Streaming & Cancel (Feature Flag)
GrantScope includes an experimental streaming chat experience integrated into multiple pages via the AI assistant panels:
- Enabled pages: Data Summary and Grant Amount Distribution.
- Behavior: Answers stream token-by-token; a Cancel button is shown inside the assistant message to stop an in-flight response and leave the UI consistent.
- Guardrails: Responses are constrained to known dataset columns and include grounded context (current filters + a compact data sample) assembled per page.

How to enable:
- Set the environment variable `GS_ENABLE_CHAT_STREAMING=1` (truthy values: 1, true, yes, on) before launching.
- Without this flag, chat will fall back to standard, non-streaming responses.

Notes:
- Streaming requires a valid OpenAI API key in environment/secrets. The model used by the LlamaIndex/OpenAI adapter is configured in [`setup_llama_index()`](GrantScope/loaders/llama_index_setup.py:17).
- Prompt assembly is memoized per page and filter tuple by [`generate_page_prompt()`](GrantScope/utils/utils.py:27), which injects Known Columns, Current Filters, and a compact sample of the active data.

### Legacy single-page router (temporary, optional)
- The legacy single-file selectbox router in [`app.py`](GrantScope/app.py) has been retired by default in favor of multipage navigation.
- For temporary compatibility/testing, you can enable it by setting the environment variable `GS_ENABLE_LEGACY_ROUTER=1` before running the app. This legacy mode will be removed in a future release.

## Contributing
We welcome contributions to enhance the Grant Analysis Dashboard. If you have any ideas, suggestions, or bug reports, please open an issue or submit a pull request. Let's collaborate to make this tool even more valuable for the grant analysis community!

## License
This project is licensed under the GNU General Public License v3.0.

We hope that GrantScope empowers grant analysts and writers to uncover valuable insights, identify potential funding opportunities, and craft compelling grant proposals. Happy exploring and grant writing!
