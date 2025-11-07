# Environment Setup

## Prerequisites
- Python 3.11.4
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup Instructions

### Option 1: Using uv (Recommended)

1. Install uv if you haven't already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Create and activate virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

### Option 2: Using pip

1. Create virtual environment:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Verify Installation

```bash
python --version  # Should show Python 3.11.4
python -c "import numpy; print(numpy.__version__)"  # Should show 2.3.4
```
