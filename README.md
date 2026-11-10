# KGLit4Cat-Publications

Proof-of-concept workflow for building a knowledge graph from catalysis literature (KGLit4Cat), developed in the context of [NFDI4Cat](https://nfdi4cat.org/) at TU Dortmund.

> **Status:** Early stage / proof of concept. Contents and structure may change.

## Overview

KGLit4Cat aims to make information from scientific publications in catalysis machine-readable and queryable. The repository currently contains a development notebook that demonstrates the basic workflow.


## Repository contents

| File | Description |
|------|-------------|
| `dev_workflow_poc.ipynb` | Jupyter notebook with the proof-of-concept development workflow |

## Getting started

### Requirements

- Python 3.10 or newer
- [Jupyter](https://jupyter.org/) (JupyterLab or Notebook)

### Installation

```bash
git clone https://github.com/mvoelken-hub/KGLit4Cat-Publications.git
cd KGLit4Cat-Publications

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install jupyterlab
# pip install -r requirements.txt   # once available
```

### Usage

```bash
jupyter lab dev_workflow_poc.ipynb
```

Run the cells from top to bottom.

## Related projects

- [NFDI4Cat](https://nfdi4cat.org/) – National Research Data Infrastructure for Catalysis


## Contact

Marc Völkenrath – TU Dortmund, Faculty of Biochemical and Chemical Engineering, within the NFDI4Cat project
