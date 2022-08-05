# Plot Energy Data

Plot a graph of household energy consumption and local air temperature over time.

The temperature data is currently hard-coded to London Heathrow.

## Usage

1. Create a virtualenv:
  1. `python -m venv venv`
  2. `./venv/bin/pip install -r requirements.txt`
2. Create your personal data file `data.tsv` (see below)
3. Run `./venv/bin/python main.py`

### data.tsv

Lines of `(date, electricity, gas)`:

```csv
2021-07-26  32510 13333.794
2021-08-31  32609 13343.765
```

(Note: Unlike this example, columns must be tab-separated.)
