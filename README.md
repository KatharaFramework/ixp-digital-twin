# IXP Digital Twin

## Getting started

You need at least Python 3.11 to run the Digital Twin.

1. Configure the IXP Digital Twin by copying the `ixp.conf.example` file in `ixp.conf` and filling the fields.
2. Add the required files into the `resources` folder.
3. Install dependencies:
```bash
python3 -m pip install requirements.txt
```
4. Run:
```bash
python3 start.py
```

# Update Route Server Configurations
1. Update the configuration files in `resources`.
2. Run: 
```bash
python3 reload.py
```