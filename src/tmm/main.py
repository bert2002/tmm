#!/usr/bin/env python3
"""
Tendermint Metrics Monitor (tmm)
A Textual-based TUI for monitoring Tendermint/CometBFT blockchain metrics
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from collections import deque
import urllib.request
import urllib.error
import importlib.resources
import pkgutil


from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.screen import Screen
from textual import work
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
import plotext as plt


class MetricPanel(Static):
    """A panel displaying a group of related metrics"""
    
    def __init__(self, title: str, metrics_config: List[Dict], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.metrics_config = metrics_config
        self.metric_values: Dict[str, Any] = {}
    
    def update_metrics(self, parsed_metrics: Dict[str, Any]):
        """Update metric values from parsed Prometheus data"""
        self.metric_values = parsed_metrics
        self.refresh()
    
    def render(self) -> Panel:
        """Render the panel with current metric values"""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="bold green", justify="right")
        
        for metric_config in self.metrics_config:
            name = metric_config["name"]
            value = self.metric_values.get(metric_config["metric"], "N/A")
            formatted_value = self._format_value(value, metric_config.get("format", "int"))
            
            # Color code based on metric type
            if metric_config.get("format") == "bool":
                style = "red" if value == 1 else "green"
                formatted_value = Text(formatted_value, style=style)
            elif "missing" in name.lower() or "byzantine" in name.lower() or "failed" in name.lower():
                if isinstance(value, (int, float)) and value > 0:
                    formatted_value = Text(formatted_value, style="yellow")
            
            table.add_row(name, formatted_value)
            
            # Add block difference row after Latest Block Height
            if name == "Latest Block Height" and value != "N/A":
                block_height = self.metric_values.get("consensus_height", "N/A")
                if block_height != "N/A" and isinstance(value, (int, float)) and isinstance(block_height, (int, float)):
                    diff = int(value) - int(block_height)
                    diff_text = f"{diff:+,}" if diff != 0 else "0"
                    diff_style = "yellow" if diff != 0 else "green"
                    table.add_row("Block Difference", Text(diff_text, style=diff_style))
        
        return Panel(
            table,
            title=f"[bold white]{self.title}[/bold white]",
            border_style="blue",
            padding=(1, 2)
        )
    
    def _format_value(self, value: Any, format_type: str) -> str:
        """Format metric value based on type"""
        if value == "N/A" or value is None:
            return "N/A"
        
        try:
            if format_type == "int":
                return f"{int(float(value)):,}"
            elif format_type == "bytes":
                return self._format_bytes(float(value))
            elif format_type == "duration":
                return self._format_duration(float(value))
            elif format_type == "percent":
                return f"{float(value) * 100:.2f}%"
            elif format_type == "bool":
                return "YES" if int(float(value)) == 1 else "NO"
            elif format_type == "peer_count":
                return str(int(value))
            elif format_type == "bytes_sum":
                return self._format_bytes(float(value))
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)
    
    def _format_bytes(self, bytes_val: float) -> str:
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable format"""
        if seconds < 1:
            return f"{seconds * 1000:.2f}ms"
        elif seconds < 60:
            return f"{seconds:.2f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.2f}m"
        else:
            return f"{seconds / 3600:.2f}h"


class P2PTrafficGraph(Static):
    """Widget displaying P2P traffic graph"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timestamps = deque(maxlen=60)  # Keep last 60 data points
        self.bytes_received = deque(maxlen=60)
        self.bytes_sent = deque(maxlen=60)
    
    def update_data(self, timestamp: datetime, recv_bytes: float, sent_bytes: float):
        """Add new data point"""
        self.timestamps.append(timestamp)
        self.bytes_received.append(recv_bytes)
        self.bytes_sent.append(sent_bytes)
        self.refresh()
    
    def render(self) -> Panel:
        """Render the traffic graph"""
        if len(self.timestamps) < 2:
            return Panel(
                "[yellow]Collecting data... Please wait[/yellow]",
                title="[bold white]📊 P2P Network Traffic[/bold white]",
                border_style="blue"
            )
        
        # Calculate rates (bytes per second)
        recv_rates = []
        sent_rates = []
        time_labels = []
        
        for i in range(1, len(self.timestamps)):
            time_diff = (self.timestamps[i] - self.timestamps[i-1]).total_seconds()
            if time_diff > 0:
                recv_rate = (self.bytes_received[i] - self.bytes_received[i-1]) / time_diff
                sent_rate = (self.bytes_sent[i] - self.bytes_sent[i-1]) / time_diff
                recv_rates.append(recv_rate / 1024)  # Convert to KB/s
                sent_rates.append(sent_rate / 1024)
                time_labels.append(i)
        
        if not recv_rates:
            return Panel(
                "[yellow]Collecting data... Please wait[/yellow]",
                title="[bold white]📊 P2P Network Traffic[/bold white]",
                border_style="blue"
            )
        
        # Create plot
        plt.clf()
        plt.clear_figure()
        
        # Set plot size to fill widget (minus border)
        width = self.size.width
        height = self.size.height
        
        # Fallback/Safe defaults if size is invalid (e.g. startup)
        if width <= 2 or height <= 2:
            width = 100
            height = 30
            
        plt.plot_size(width=width - 4, height=height - 4)  # -4 for border + padding
        
        # Simple title
        plt.title("P2P Network Traffic (KB/s)")
        
        # Plot both lines without labels to avoid legend
        plt.plot(time_labels, recv_rates, color="green")
        plt.plot(time_labels, sent_rates, color="cyan")
        
        # Set canvas and axes colors for clean display
        plt.canvas_color("black")
        plt.axes_color("white")
        
        # Build the plot as a string
        plot_str = plt.build()
        
        # Use Text.from_ansi to ensure correct rendering of ANSI codes without wrapping issues
        return Panel(
            Text.from_ansi(plot_str),
            title="[bold white]📊 P2P Network Traffic - [green]Received[/green] / [cyan]Sent[/cyan][/bold white]",
            border_style="blue",
            padding=(0, 0)
        )

    def on_resize(self, event) -> None:
        """Refresh graph when resized"""
        self.refresh()


class P2PGraphScreen(Screen):
    """Screen showing P2P traffic graph"""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph = P2PTrafficGraph()
    
    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Header(show_clock=True, icon="")
        yield self.graph
        yield Static(
            "[cyan]Press [bold]ESC[/bold] or [bold]Q[/bold] to return to main screen[/cyan]",
            id="help-text"
        )
        yield Footer()
    
    def update_graph(self, timestamp: datetime, recv_bytes: float, sent_bytes: float):
        """Update graph with new data"""
        self.graph.update_data(timestamp, recv_bytes, sent_bytes)


class MetricsMonitor(App):
    """Textual app for monitoring blockchain metrics"""
    
    TITLE = "Tendermint Metrics Monitor"
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #metrics-container {
        height: 100%;
        overflow-y: auto;
    }
    
    .metrics-row {
        height: auto;
        margin: 1;
    }
    
    MetricPanel {
        height: auto;
        width: 1fr;
        margin: 0 1;
    }
    
    #status-bar {
        dock: bottom;
        height: 3;
        background: $panel;
        color: $text;
        padding: 1;
    }
    
    #help-text {
        dock: bottom;
        height: 3;
        background: $panel;
        color: $text;
        padding: 1;
        text-align: center;
    }
    
    P2PTrafficGraph {
        height: 100%;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_now", "Refresh Now"),
        ("ctrl+c", "quit", "Quit"),
        ("g", "show_graph", "P2P Graph"),
        ("n", "show_graph", "Network Graph"),
    ]
    
    def __init__(
        self,
        metrics_url: str,
        refresh_interval: int,
        chain: str,
        namespace: str,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.metrics_url = metrics_url
        self.refresh_interval = refresh_interval
        self.chain = chain
        self.namespace = namespace
        self.chain_config = self._load_chain_config()
        self.panels: List[MetricPanel] = []
        self.last_update = "Never"
        self.error_message = ""
        self.block_height_timestamp = None
        self.last_block_height = None
    
    def _load_chain_config(self) -> Dict:
        """Load chain configuration from JSON file"""
        resource_path = f"chains/{self.chain}.json"
        
        # Fallback logic is tricker with resources, so let's try to load specific resource
        try:
            # We assume 'tmm' is the package name
            ref = importlib.resources.files("tmm") / "chains" / f"{self.chain}.json"
            with ref.open('r') as f:
                return json.load(f)
        except (FileNotFoundError, ModuleNotFoundError):
            # Fallback
            try:
                ref = importlib.resources.files("tmm") / "chains" / "cosmoshub-4.json"
                with ref.open('r') as f:
                   return json.load(f)
            except Exception:
                self.exit(message=f"Error: Chain configuration not found for {self.chain}")
                sys.exit(1)
    
    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Header(show_clock=True, icon="")
        
        with Container(id="metrics-container"):
            # Create panels for each metric group
            metrics = self.chain_config.get("metrics", {})
            
            # First row: Block & Consensus, Validators
            with Horizontal(classes="metrics-row"):
                if "block_consensus" in metrics:
                    panel = MetricPanel("📦 Block & Consensus", metrics["block_consensus"])
                    self.panels.append(panel)
                    yield panel
                
                if "validators" in metrics:
                    panel = MetricPanel("👥 Validators", metrics["validators"])
                    self.panels.append(panel)
                    yield panel
            
            # Second row: Mempool, Network
            with Horizontal(classes="metrics-row"):
                if "mempool" in metrics:
                    panel = MetricPanel("💾 Mempool", metrics["mempool"])
                    self.panels.append(panel)
                    yield panel
                
                if "network" in metrics:
                    panel = MetricPanel("🌐 Network", metrics["network"])
                    self.panels.append(panel)
                    yield panel
            
            # Third row: Performance
            with Horizontal(classes="metrics-row"):
                if "performance" in metrics:
                    panel = MetricPanel("⚡ Performance", metrics["performance"])
                    self.panels.append(panel)
                    yield panel
        
        yield Static(id="status-bar")
        yield Footer()
    
    def on_mount(self) -> None:
        """Start the refresh timer when app is mounted"""
        # Install graph screen
        if "graph" not in self._installed_screens:
            self.install_screen(P2PGraphScreen(), name="graph")
        self.set_interval(self.refresh_interval, self.refresh_metrics)
        self.refresh_metrics()
    
    @work(exclusive=True)
    async def refresh_metrics(self) -> None:
        """Fetch and update metrics"""
        try:
            metrics_data = await self._fetch_metrics()
            parsed = self._parse_metrics(metrics_data)
            
            # Track block age
            current_block_height = parsed.get("consensus_height")
            if current_block_height is not None:
                if self.last_block_height is None or current_block_height != self.last_block_height:
                    # Block height changed, update timestamp
                    self.block_height_timestamp = datetime.now()
                    self.last_block_height = current_block_height
                
                # Calculate block age in seconds
                if self.block_height_timestamp:
                    block_age = (datetime.now() - self.block_height_timestamp).total_seconds()
                    parsed["block_age"] = block_age
            
            # Update P2P graph with new data
            recv_bytes = parsed.get("p2p_peer_receive_bytes_total", 0)
            sent_bytes = parsed.get("p2p_peer_send_bytes_total", 0)
            if isinstance(recv_bytes, (int, float)) and isinstance(sent_bytes, (int, float)):
                # Get graph screen if it exists
                if "graph" in self._installed_screens:
                    graph_screen = self._installed_screens["graph"]
                    graph_screen.update_graph(datetime.now(), recv_bytes, sent_bytes)
            
            # Update all panels
            for panel in self.panels:
                panel.update_metrics(parsed)
            
            self.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.error_message = ""
            
        except Exception as e:
            self.error_message = f"Error: {str(e)}"
        
        self._update_status_bar()
    
    async def _fetch_metrics(self) -> str:
        """Fetch metrics from Prometheus endpoint"""
        try:
            with urllib.request.urlopen(self.metrics_url, timeout=5) as response:
                return response.read().decode('utf-8')
        except urllib.error.URLError as e:
            raise Exception(f"Failed to fetch metrics: {e}")
    
    def _parse_metrics(self, metrics_data: str) -> Dict[str, Any]:
        """Parse Prometheus text format metrics"""
        parsed = {}
        
        for line in metrics_data.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                # Parse metric line: metric_name{labels} value
                if '{' in line:
                    metric_part, rest = line.split('{', 1)
                    labels_part, value_part = rest.rsplit('}', 1)
                    metric_name = metric_part.strip()
                    value = float(value_part.strip().split()[0])
                    
                    # Parse labels
                    labels = {}
                    for label in labels_part.split(','):
                        if '=' in label:
                            key, val = label.split('=', 1)
                            labels[key.strip()] = val.strip().strip('"')
                    
                    # Store with chain_id filter
                    # Check if chain_id matches any of the configured IDs
                    chain_ids = self.chain_config.get("chain_id")
                    if isinstance(chain_ids, str):
                        chain_ids = [chain_ids]
                        
                    if labels.get('chain_id') in chain_ids:
                        # For metrics with additional label filters
                        key = metric_name.replace(f'{self.namespace}_', '')
                        
                        # Handle special cases for labeled metrics
                        if key in ['p2p_peer_send_bytes_total', 'p2p_peer_receive_bytes_total']:
                            parsed[key] = parsed.get(key, 0) + value
                        elif key not in parsed:
                            parsed[key] = value
                        
                        # Store labeled versions
                        if labels:
                            label_key = f"{key}_{labels.get('method', '')}"
                            if labels.get('method'):
                                parsed[label_key] = value
                else:
                    # Simple metric without labels
                    parts = line.split()
                    if len(parts) >= 2:
                        metric_name = parts[0].replace(f'{self.namespace}_', '')
                        value = float(parts[1])
                        parsed[metric_name] = value
            
            except (ValueError, IndexError):
                continue
        
        # Calculate derived metrics
        self._calculate_derived_metrics(parsed)
        
        return parsed
    
    def _calculate_derived_metrics(self, parsed: Dict[str, Any]):
        """Calculate derived metrics like averages from histograms"""
        # For histogram metrics, calculate average from sum/count
        histogram_metrics = [
            'consensus_block_interval_seconds',
            'consensus_round_duration_seconds',
            'abci_connection_method_timing_seconds'
        ]
        
        for metric in histogram_metrics:
            sum_key = f"{metric}_sum"
            count_key = f"{metric}_count"
            
            if sum_key in parsed and count_key in parsed:
                count = parsed[count_key]
                if count > 0:
                    parsed[metric] = parsed[sum_key] / count
        

    
    def _update_status_bar(self):
        """Update the status bar with connection info"""
        status_widgets = self.query("#status-bar")
        if not status_widgets:
            return
            
        status_widget = status_widgets.first()
        
        chain_name = self.chain_config.get("name", self.chain)
        status_text = f"[bold cyan]{chain_name}[/bold cyan] | "
        status_text += f"Endpoint: [yellow]{self.metrics_url}[/yellow] | "
        status_text += f"Last Update: [green]{self.last_update}[/green] | "
        status_text += f"Refresh: [blue]{self.refresh_interval}s[/blue]"
        
        if self.error_message:
            status_text += f" | [bold red]{self.error_message}[/bold red]"
        
        status_widget.update(status_text)
    
    def action_refresh_now(self) -> None:
        """Manually trigger a refresh"""
        self.refresh_metrics()
    
    def action_show_graph(self) -> None:
        """Show P2P traffic graph screen"""
        self.push_screen("graph")
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()


def detect_chain_and_endpoint(preferred_metrics_url: str = None) -> tuple[str, str]:
    """
    Attempt to auto-detect the chain by probing known endpoints.
    Returns (chain_id, metrics_url) or raises Exception if not found.
    """
    candidates = []
    
    try:
        # Use importlib.resources to iterate over files in the chains directory
        chains_dir = importlib.resources.files("tmm") / "chains"
        for entry in chains_dir.iterdir():
            if entry.name.endswith(".json"):
                try:
                    with entry.open('r') as f:
                        config = json.load(f)
                        chain_ids = config.get("chain_id")
                        endpoints = config.get("endpoints", [])
                        if chain_ids:
                            # Ensure chain_id is a list
                            if isinstance(chain_ids, str):
                                chain_ids = [chain_ids]
                            # Store (config_key, chain_ids, endpoints)
                            candidates.append((entry.stem, chain_ids, endpoints))
                except Exception:
                    continue
    except Exception as e:
         print(f"Warning: Could not list chain configurations: {e}", file=sys.stderr)

            
    def check_endpoint(url: str, expected_chain_ids: List[str]) -> str:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                content = response.read().decode('utf-8')
                for chain_id in expected_chain_ids:
                    if f'chain_id="{chain_id}"' in content:
                        return chain_id
                return None
        except Exception:
            return None

    if preferred_metrics_url:
        # Check if the preferred URL matches any known chain
        for key, chain_ids, _ in candidates:
            if check_endpoint(preferred_metrics_url, chain_ids):
                return key, preferred_metrics_url

    # Auto-discovery
    print("Auto-detecting chain...", file=sys.stderr)
    for key, chain_ids, endpoints in candidates:
        for endpoint in endpoints:
            print(f"  Checking {key} ({chain_ids}) at {endpoint}...", file=sys.stderr)
            if check_endpoint(endpoint, chain_ids):
                print(f"  Found {key}!", file=sys.stderr)
                return key, endpoint
                
    raise Exception("No active chain found. Please specify --chain or ensure a known node is running.")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Tendermint Metrics Monitor - A TUI for monitoring blockchain metrics"
    )
    parser.add_argument(
        "--metrics",
        type=str,
        default=None,
        help="Prometheus metrics endpoint URL (default: http://localhost:26660/metrics)"
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=1,
        help="Refresh interval in seconds (default: 1)"
    )
    parser.add_argument(
        "--chain",
        type=str,
        default=None,
        help="Chain identifier (default: auto-detect)"
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="cometbft",
        help="Metrics namespace (default: cometbft)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.1.5",
        help="Show program's version number and exit"
    )

    
    args = parser.parse_args()
    
    chain = args.chain
    metrics_url = args.metrics
    
    if chain is None:
        try:
            chain, detected_url = detect_chain_and_endpoint(metrics_url)
            if metrics_url is None:
                metrics_url = detected_url
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Backward compatibility / strict mode
        if metrics_url is None:
            # Try to find default endpoint for this chain from config
            try:
                ref = importlib.resources.files("tmm") / "chains" / f"{chain}.json"
                if ref.is_file():
                    with ref.open('r') as f:
                        cfg = json.load(f)
                        endpoints = cfg.get("endpoints", [])
                        if endpoints:
                            metrics_url = endpoints[0]
            except Exception:
                pass
                
            if metrics_url is None:
                metrics_url = "http://localhost:26660/metrics"

    app = MetricsMonitor(
        metrics_url=metrics_url,
        refresh_interval=args.refresh,
        chain=chain,
        namespace=args.namespace
    )
    
    app.run()


if __name__ == "__main__":
    main()
