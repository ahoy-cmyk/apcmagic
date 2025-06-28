import rumps
from apcaccess.status import get, parse
import logging

logger = logging.getLogger("apcmagic")

class APCApp(rumps.App):
    """A rumps application for displaying APC UPS status in the macOS menu bar."""

    def __init__(self) -> None:
        super(APCApp, self).__init__("APC UPS Status")
        self.menu = ["Status", "Quit"]

    @rumps.clicked("Status")
    def status(self, _) -> None:
        """Displays the current UPS status in a rumps alert window."""
        try:
            raw_status = get()
            raw_status = get()
            raw_status = get()
            status = parse(raw_status)
            rumps.alert(
                title="APC UPS Status",
                message=f"Status: {status['STATUS']}\n" \
                        f"Battery: {status['BCHARGE']}%\n" \
                        f"Load: {status['LOADPCT']}%\n" \
                        f"Time Left: {status['TIMELEFT']}",
            )
        except Exception as e:
            rumps.alert(title="Error", message=str(e))
            logger.error(f"Error in rumps app status: {e}")

