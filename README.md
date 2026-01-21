# Tendermint Metrics Monitor (tmm)

![TMM Screenshot](https://raw.githubusercontent.com/bert2002/tmm/main/assets/screenshot.png)

A beautiful terminal-based TUI (Text User Interface) for monitoring Tendermint/CometBFT blockchain metrics from Prometheus endpoints.

## Features

- 📊 **Real-time Metrics Display**: Auto-refreshing dashboard with customizable intervals
- 🎨 **Visually Appealing**: Color-coded metrics with grouped panels for easy reading
- ⚙️ **Configurable**: Chain-specific metric configurations via JSON files
- 🔄 **Auto-refresh**: Configurable refresh intervals (default: 1 second)
- 🌐 **Flexible**: Works with any Prometheus-compatible metrics endpoint

## Supported Chains

| Chain | Network IDs |
|-------|-------------|
| 0G Chain | `0gchain-16602`, `0G-mainnet-aristotle` |
| Babylon | `bbn-1`, `bbn-test-6` |
| Celestia | `celestia`, `mocha-4`, `arabica-11` |
| Cosmos Hub | `cosmoshub-4`, `theta-testnet-001` |
| Dymension | `dymension_1100-1`, `blumbus_111-1` |
| Mantra | `mantra-dukong-1`, `mantra-1` |
| Nillion | `nillion-1`, `nillion-chain-testnet-1` |
| Terra | `phoenix-1`, `pisco-1` |
| Xion | `xion-mainnet-1`, `xion-testnet-2` |

## Installation

### From PyPI

```bash
pip3 install tmm-monitor
```

### From GitHub

```bash
pip3 install git+https://github.com/bert2002/tmm.git
```

### From Source (Local Development)

1. Clone the repository:
   ```bash
   git clone https://github.com/bert2002/tmm.git
   cd tmm
   ```

2. Install in editable mode:
   ```bash
   pip3 install -e .
   ```

This will install the `tmm` command to your environment. Ensure your python binary directory (e.g., `~/.local/bin`) is in your `PATH`.

### Running from Source

If you prefer not to install the package, you can run it directly from the repository:

1. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

2. Run using Python:
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/src
   python3 -m tmm.main [OPTIONS]
   ```


## Usage

### Basic Usage

```bash
tmm
```

This will connect to `http://localhost:26660/metrics` and display metrics for `cosmoshub-4`.

### Command Line Options

```bash
tmm [OPTIONS]
```

**Options:**

- `--metrics <URL>` - Prometheus metrics endpoint (default: `http://localhost:26660/metrics`)
- `--refresh <SECONDS>` - Refresh interval in seconds (default: `1`)
- `--chain <CHAIN_ID>` - Chain identifier (default: auto-detect)
- `--namespace <NAMESPACE>` - Metrics namespace (default: `cometbft`)

### Examples

Monitor a custom endpoint with 2-second refresh:
```bash
tmm --metrics http://validator.example.com:26660/metrics --refresh 2
```

Monitor a different chain:
```bash
tmm --chain osmosis-1 --namespace cometbft
```

### Keyboard Shortcuts

- `q` - Quit the application
- `r` - Refresh metrics immediately

## Metrics Display

The TUI organizes metrics into the following panels:

### 📦 Block & Consensus
- Block height and latest block height
- Block size and interval
- Sync status
- Transaction counts

### 👥 Validators
- Total validators and voting power
- Missing validators and their power
- Byzantine validators (double-signers)
- Precommit statistics

### 💾 Mempool
- Mempool size (transactions and bytes)
- Failed and evicted transactions
- Recheck statistics

### 🌐 Network
- Connected peer count
- Duplicate votes and block parts
- P2P bytes sent and received

### ⚡ Performance
- Round duration
- ABCI method timings (finalize_block, commit, process_proposal)

## Chain Configuration

Chain-specific metrics are defined in JSON files located in the `chains/` directory.

### Creating a Custom Chain Configuration

1. Create a new JSON file in `chains/` directory:
   ```bash
   cp chains/cosmoshub-4.json chains/my-chain.json
   ```

2. Edit the configuration to define which metrics to display:
   ```json
   {
     "name": "My Chain",
     "chain_id": ["my-chain-1", "my-chain-alternative-id"],
     "endpoints": ["http://localhost:26660/metrics"],
     "metrics": {
       "block_consensus": [
         {
           "name": "Block Height",
           "metric": "consensus_height",
           "type": "gauge",
           "format": "int"
         }
       ]
     }
   }
   ```

3. Run tmm with your chain:
   ```bash
   tmm --chain my-chain
   ```

### Metric Configuration Format

Each metric entry supports:

- `name` - Display name
- `metric` - Prometheus metric name (without namespace prefix)
- `type` - Metric type (`gauge`, `counter`, `histogram`)
- `format` - Display format (`int`, `bytes`, `duration`, `percent`, `bool`)
- `stat` - For histograms: `avg`, `sum`, `count`
- `labels` - Optional label filters

### Chain Endpoints & Auto-detection

You can specify a list of `endpoints` in the configuration file. TMM uses these endpoints to auto-detect the active chain when no `--chain` argument is provided.

```json
"endpoints": [
  "http://localhost:26660/metrics",
  "http://IP:26660/metrics"
]
```

When running `tmm` without arguments, it probes these endpoints and selects the first one that returns metrics matching the configuration's `chain_id`.

### Fallback Behavior

If a chain configuration file is not found, tmm automatically falls back to `cosmoshub-4.json`.



## Project Structure

```
tmm/
├── src/
│   └── tmm/                  # Package source
│       ├── main.py           # Entry point
│       └── chains/           # Chain configurations
├── tests/                    # Tests
├── pyproject.toml            # Project configuration
└── README.md                   # This file
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
