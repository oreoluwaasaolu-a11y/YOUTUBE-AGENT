import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.logging import RichHandler
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    class MockConsole:
        def print(self, *args, **kwargs):
            print(*args)
        def print_json(self, data):
            print(data)
    console = MockConsole()

# Configure logging
if HAS_RICH:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)]
    )
else:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )

logger = logging.getLogger("youtube_agent")


def print_banner(title: str, subtitle: Optional[str] = None) -> None:
    """Print a styled section header in the terminal."""
    if HAS_RICH:
        text = f"[bold cyan]{title}[/bold cyan]"
        if subtitle:
            text += f"\n[dim]{subtitle}[/dim]"
        console.print(Panel(text, expand=False, border_style="bright_blue"))
    else:
        print("\n" + "=" * 60)
        print(f"   {title}")
        if subtitle:
            print(f"   {subtitle}")
        print("=" * 60 + "\n")


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON object from markdown fenced code blocks or raw text.
    Handles ```json ... ``` blocks gracefully.
    """
    text = text.strip()
    
    # Try finding markdown code block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
            
    # Try finding first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Direct parse
    return json.loads(text)


def retry_with_backoff(
    func: Callable,
    retries: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    exception_types: tuple = (Exception,)
) -> Any:
    """
    Execute a function with exponential backoff retry.
    """
    delay = initial_delay
    last_exception = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except exception_types as e:
            last_exception = e
            logger.warning(
                f"[yellow]Attempt {attempt}/{retries} failed: {e}. Retrying in {delay:.1f}s...[/yellow]"
            )
            if attempt < retries:
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"[red]All {retries} attempts failed.[/red]")
                raise last_exception


def clean_temp_dir(temp_dir: Path) -> None:
    """Safely clear temp directory without removing the folder itself."""
    if not temp_dir.exists():
        temp_dir.mkdir(parents=True, exist_ok=True)
        return
    for item in temp_dir.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            logger.debug(f"Could not delete temp item {item}: {e}")
